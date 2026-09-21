"""Freeze the eight historical knight variants under the current count policy.

Preserves every original capture. Nine isolated Leitis corrections make the
completed expansion use the same approved four-relic opponent. No catalog or
Golden edits, game interaction, renders, or uploads occur during preparation.
"""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.planner import plan_matchup
from capture_storage_guard import archive_storage_error
from prepare_camel_comparison import DAT, ROOT
from run_champi_comparison_capture import read, save

WORK = ROOT / 'data/local/knight-v2-recapture'
SUBJECTS = (
    ('Franks', 'paladin_franks', 'Paladin'),
    ('Teutons', 'paladin_teutons', 'Paladin'),
    ('Lithuanians', 'paladin_lithuanians_four_relics', 'Paladin'),
    ('Persians', 'savar_persians', 'Savar'),
    ('Bulgarians', 'cavalier_bulgarians', 'Cavalier'),
    ('Poles', 'cavalier_poles', 'Cavalier'),
    ('Burmese', 'cavalier_burmese', 'Cavalier'),
    ('Sicilians', 'cavalier_sicilians', 'Cavalier'),
)
GUARD = dict(root='D:/AoE2 Renders', label='SAFEHOUSE', volumeSerial=1588195055,
             physicalSerial='00000107000079B6', reserveGiB=4)


def requests_for_subject(civ, slug, opponents):
    rows = []
    for original in opponents:
        if slug == original['side3']:
            continue
        row = copy.deepcopy(original)
        suffix = row['id'].removeprefix('camel_turks_unique_')
        row.update(id=f'knight_v2_{civ.lower()}_{suffix}', side2=slug, civ2=civ)
        row['balance'] = dict(mode='geometric_shared_discount', cap=27)
        scenario = row.setdefault('scenario', {})
        if civ == 'Lithuanians':
            scenario['lithuanianRelics'] = 4
        if row['side3'] == 'elite_leitis_lithuanians':
            scenario['opponentLithuanianRelics'] = 4
        rows.append(row)
    return rows


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Queue exists; resume it without replanning')
    error = archive_storage_error(GUARD)
    if error:
        raise RuntimeError(error)
    catalogs = {n: read(ROOT / 'data' / n) for n in
                ('recording-costs.json', 'recording-balance.json', 'recording-subjects.json')}
    if hashlib.sha256(DAT.read_bytes()).hexdigest() != catalogs['recording-balance.json']['datSha256']:
        raise ValueError('Installed DAT differs from the audited game data')
    extraction = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT / 'data/local/cost-audit-extracted').glob('*.json')}
    if extraction != catalogs['recording-costs.json']['extractionHashes']:
        raise ValueError('Cost extraction changed')
    opponents = read(ROOT / 'data/local/camel-baseline/manifest.json')['matchups']
    assert len(opponents) == 74 and len({r['side3'] for r in opponents}) == 74
    cfg = load_config()
    db = sqlite3.connect(f'file:{ROOT / "data/golden/aoe2_reference.db"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    queue = []

    def freeze(key, rows, subjects, archive_prefix, job_prefix, title):
        work = WORK / key
        if (work / 'preflight.json').exists():
            raise FileExistsError(f'Prepared campaign already exists: {work}')
        if any((Path(GUARD['root']) / f'{archive_prefix}-{c.lower()}').exists() for c, _, _ in subjects):
            raise FileExistsError('New archive destination already exists; never overwrite it')
        save(work / 'requested.json', dict(schemaVersion=1, matchups=rows))
        _, requests = _load_batch(work / 'requested.json')
        evidence = []
        for request in requests:
            plan = plan_matchup(cfg, request)
            validate_plan_costs(plan)
            assert plan['balance']['comparisonPolicy'] == 'geometric_shared_discount_unit_count_v2'
            assert 'maxResources' not in plan['balance']
            assert all(plan[s]['comparison']['population'] == 1 for s in ('side2', 'side3'))
            if plan['side2']['civ'] == 'Lithuanians':
                assert plan['scenario']['lithuanianRelics'] == 4
            if plan['side3']['slug'] == 'elite_leitis_lithuanians':
                assert plan['scenario']['opponentLithuanianRelics'] == 4
            save(work / 'plans' / f'{plan["jobId"]}.json', plan)
            evidence.append(dict(jobId=plan['jobId'], counts=[plan[s]['count'] for s in ('side2', 'side3')],
                                 policy=plan['balance']['comparisonPolicy'], scenario=plan['scenario']))
        stats = []
        for civ, slug, label in subjects:
            db_label = 'Heavy Hei-Kuang Cavalry' if 'hei_guang' in slug else label
            stat = db.execute("SELECT * FROM ref_units WHERE age='Imperial' AND civ_name=? AND unit_name=?",
                              (civ, db_label)).fetchone()
            if stat is None:
                raise ValueError(f'Missing reference stats: {civ} {label}')
            stats.append(dict(stat))
        for name, value in catalogs.items():
            save(work / 'frozen-catalogs' / name, value)
        save(work / 'subject-stats.json', stats)
        save(work / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(work / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        save(work / 'archive-guard.json', GUARD)
        save(work / 'pilot-phase/archive-guard.json', GUARD)
        save(work / 'preflight.json', dict(state='PASSED', total=len(rows), jobs=evidence,
             policy='geometric_shared_discount_unit_count_v2', preserveOriginals=True))
        queue.append(dict(key=key, civilization=subjects[0][0], unit=title, slug=subjects[0][1],
             workDirectory=str(work), total=len(rows), jobPrefix=job_prefix,
             archivePrefix=archive_prefix, archiveCivilizations=[c.lower() for c, _, _ in subjects]))
        print(f'{key}: {len(rows)} frozen plans passed', flush=True)

    for civ, slug, unit in SUBJECTS:
        key=f'{unit.lower()}-{civ.lower()}'
        freeze(key, requests_for_subject(civ, slug, opponents), [(civ, slug, unit)],
               'knight-v2-' + unit.lower(), f'knight_v2_{civ.lower()}_', unit + ' Current Count Policy')
    expanded = read(ROOT / 'data/local/knight-expansion/queue.json')['campaigns']
    fixes, subjects = [], []
    for campaign in expanded:
        old = next(row for row in read(Path(campaign['workDirectory']) / 'manifest.json')['matchups']
                   if row['side3'] == 'elite_leitis_lithuanians')
        row = copy.deepcopy(old)
        row.update(id='knight_v2_leitis4_' + campaign['civilization'].lower(),
                   scenario={**row.get('scenario', {}), 'opponentLithuanianRelics': 4})
        fixes.append(row)
        subjects.append((campaign['civilization'], campaign['slug'], campaign['unit']))
    freeze('expansion-leitis-four-relics', fixes, subjects, 'knight-v2-leitis4',
           'knight_v2_leitis4_', 'Knight Line Four Relic Leitis Retake')
    assert sum(c['total'] for c in queue) == 600
    save(WORK / 'queue.json', dict(state='READY', captureOnly=True, total=600, campaigns=queue,
         archiveRoot=GUARD['root'], archiveGuard=GUARD, preserveOriginals=True,
         authorization='User requested all eight historical knight-line variants re-recorded under the current count formula for comparable rankings; include nine isolated Leitis corrections to honor the approved four-relic opponent.'))
    save(WORK / 'comparison-scope.json', dict(olderVariants=8, newVariantCaptures=591,
         expansionLeitisCorrections=9, total=600, expectedRankedVariants=17,
         commonOpponentsForRanking=73, excludedSelfMatch='Savar vs Savar',
         previousExpansion=str(ROOT / 'data/local/knight-expansion/queue.json'),
         pendingRanking=str(ROOT / 'data/local/knight-line-ranking')))
    db.close()
    print('READY: 600 captures; no originals or existing archives changed')


if __name__ == '__main__':
    main()
