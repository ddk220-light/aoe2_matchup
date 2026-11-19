"""Freeze five Elite Varangian Guard campaigns against the current unique roster.

Only new subject registrations and plans are created. Existing opponent costs,
the opponent roster, Golden templates and historical recordings remain intact.
"""
from dataclasses import asdict
import hashlib
import json

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.artifacts import create_job
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import safe_slug
from aoe2x.lab.planner import plan_matchup
from build_run import unit_const
from prepare_jomsviking_capture import DAT, ROOT, audited_price
from run_champi_comparison_capture import read, save

WORK = ROOT / 'data/local/varangian-guard-capture'
EXTRACTED = ROOT / 'data/local/dat-release-audit/installed'
CIVS = ('Byzantines', 'Danes', 'Saxons', 'Varangians', 'Vikings')
MASTER, KEY, LABEL = 2704, 'elite_varangian_guard', 'Elite Varangian Guard'


def main():
    import aoe2x.dbgen.unit_analyzer as module

    if (WORK / 'queue.json').exists() or list(WORK.glob('*/manifest.json')):
        raise FileExistsError('Already prepared; resume the frozen queue, do not recreate it')
    audit = read(ROOT / 'data/local/dat-release-audit/audit.json')
    dat_hash = hashlib.sha256(DAT.read_bytes()).hexdigest()
    if dat_hash != audit['sources']['installed_dat']['sha256']:
        raise ValueError('Installed DAT changed; update its cost audit before planning')
    extraction_hashes = {}
    for source in audit['sources']['audit_extractions']:
        path = EXTRACTED / source['path'].replace('\\', '/').split('/')[-1]
        if '/installed/' not in source['path'].replace('\\', '/'):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source['sha256']:
            raise ValueError(f'Installed extraction changed: {path.name}')
        extraction_hashes[path.name] = digest
    if set(extraction_hashes) != {p.name for p in EXTRACTED.glob('*.json')}:
        raise ValueError('Incomplete extraction provenance')
    availability = {r['civ'] for r in audit['current_costs'] if r['id'] == MASTER}
    if availability != set(CIVS) or unit_const(KEY) != MASTER:
        raise ValueError('Guard identity or civilization availability changed')
    module.OUTPUT_DIR = EXTRACTED
    analyzer = module.UnitAnalyzer()
    unit = analyzer.get_unit(MASTER)
    if unit['name'] != LABEL or unit['class'] != 6:
        raise ValueError('Expected the installed Elite Varangian Guard infantry unit')
    names = ('recording-costs.json', 'recording-balance.json',
             'recording-subjects.json', 'unique-unit-roster.json')
    paths = [ROOT / 'data' / name for name in names]
    costs, balance, subjects, roster = map(read, paths)
    if costs['releaseAudit']['datSha256'] != dat_hash or len(roster['units']) != 77:
        raise ValueError('Opponent catalog must match the approved 77-unit release')
    for row in roster['units']:
        price = audited_price(analyzer, row)
        if price['effectiveCost'] != costs['units'][row['civ']+'|'+row['slug']]['effectiveCost']:
            raise ValueError(f'Opponent cost needs review: {row["slug"]}')
    for path in paths:
        save(WORK / 'provenance' / path.name, read(path))
    stats, prices = {}, {}
    for civ in CIVS:
        slug = KEY + '_' + civ.lower()
        identity = civ + '|' + slug
        row = dict(civ=civ, slug=slug, label=LABEL, master=MASTER,
                   **{'class': 'melee'}, scenarioKey=KEY,
                   baseCost=dict(food=65, wood=0, gold=45),
                   costSource='Installed release DAT, own-civilization Imperial cost effects')
        price = audited_price(analyzer, row)
        expected_cost = dict(food=52, wood=0, gold=36) if civ == 'Saxons' else dict(food=65, wood=0, gold=45)
        if price['effectiveCost'] != expected_cost:
            raise ValueError(f'Unexpected Guard cost for {civ}: {price}')
        policy = dict(master=MASTER, population=1.0, sharedAcrossCivilizations=True,
                      classificationEvidence='Shared Barracks regional infantry; user explicitly selects melee for all five civilizations',
                      populationEvidence='One comparison population per physical unit')
        for table, value in ((costs['units'], price), (balance['units'], policy)):
            if identity in table and table[identity] != value:
                raise ValueError(f'Existing subject conflict: {identity}')
            table[identity] = value
        old = next((r for r in subjects['units'] if r['slug'] == slug), None)
        if old and old != row:
            raise ValueError(f'Existing roster subject conflict: {slug}')
        if not old:
            subjects['units'].append(row)
        result = analyzer.calculate_unique_unit_stats(civ, dict(
            base_id=MASTER, display_name=LABEL, unit_class=unit['class']), 4)
        stats[civ] = dict(civ_name=civ, final_hp=result['stats'].hp,
                          stats=asdict(result['stats']), appliedBonuses=result['applied_bonuses'])
        prices[civ] = price
    # Finish every registration before freezing any plan/catalog hash.
    for path, value in zip(paths[:3], (costs, balance, subjects)):
        save(path, value)
    save(WORK / 'release-cost-audit.json', dict(datSha256=dat_hash,
         extractionHashes=extraction_hashes, availableCivilizations=list(CIVS),
         subjects=prices, opponentPriceChanges=[], opponentCount=77))
    config = load_config()
    campaigns = []
    for civ in CIVS:
        slug = KEY + '_' + civ.lower()
        work = WORK / civ.lower()
        prefix = f'varangian_guard_{civ.lower()}_v3_unique_'
        rows = [dict(id=safe_slug(f'{prefix}{i:02}_{r["slug"]}'), side2=slug, civ2=civ,
                     side3=r['slug'], civ3=r['civ'], balance=dict(
                         mode='geometric_shared_discount', cap=27,
                         weights=dict(food=1, wood=.9, gold=1.1)))
                for i, r in enumerate(roster['units'], 1)]
        save(work / 'requested.json', dict(schemaVersion=1, matchups=rows))
        evidence = []
        for request in _load_batch(work / 'requested.json')[1]:
            plan = plan_matchup(config, request)
            create_job(config.artifacts_root, plan['jobId'])  # Validate the recorder's identifier contract without writing a job.
            validate_plan_costs(plan)
            expected_weighted = sum(prices[civ]['effectiveCost'][r] * w for r, w in (('food', 1), ('wood', .9), ('gold', 1.1)))
            if plan['side2']['ranged'] or plan['side2']['weightedCost'] != expected_weighted or 'maxResources' in plan['balance']:
                raise ValueError('Guard melee classification or current count policy differs')
            save(work / 'plans' / f'{plan["jobId"]}.json', plan)
            evidence.append(dict(jobId=plan['jobId'], opponent=plan['side3']['label'],
                counts=[plan[s]['count'] for s in ('side2', 'side3')], scenario=plan['scenario']))
        for path in paths:
            save(work / 'frozen-catalogs' / path.name, read(path))
        save(work / 'subject-stats.json', [stats[civ]])
        save(work / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(work / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        save(work / 'preflight.json', dict(state='PASSED', total=len(rows), jobs=evidence))
        campaigns.append(dict(key=civ.lower(), civilization=civ, unit=LABEL, slug=slug,
                              jobPrefix=prefix, workDirectory=str(work), total=len(rows)))
        print(f'{civ}: {len(rows)} plans passed; cost {prices[civ]["effectiveCost"]}; melee; pilot HP {stats[civ]["final_hp"]}', flush=True)
    save(WORK / 'queue.json', dict(state='READY', captureOnly=True, total=385,
         campaigns=campaigns, retention='raw',
         authorization='Capture all five Elite Varangian Guard civilizations sequentially against the unchanged 77-unit roster. Save raw videos, frames and reconstruction metadata; no rendering or upload.'))
    print(json.dumps(dict(work=str(WORK), total=385, civilizations=list(CIVS)), indent=2))


if __name__ == '__main__':
    main()
