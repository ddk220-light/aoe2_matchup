"""Audit the eight requested mounted crossbow variants; activate after Guards.

Default invocation saves only a follow-on request and price/HP audit. --activate
registers subjects and freezes plans, but only after all Guards are verified.
"""
import argparse
from dataclasses import asdict
import hashlib
import json

from aoe2x.lab.artifacts import create_job
from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import safe_slug
from aoe2x.lab.planner import plan_matchup
from build_run import unit_const
from prepare_jomsviking_capture import DAT, ROOT, audited_price
from run_champi_comparison_capture import read, save

WORK = ROOT / 'data/local/mounted-crossbow-capture'
PREDECESSOR = ROOT / 'data/local/varangian-guard-capture'
EXTRACTED = ROOT / 'data/local/dat-release-audit/installed'
CIVS = ('Danes', 'Saxons', 'Varangians', 'Franks', 'Portuguese', 'Sicilians', 'Poles', 'Teutons')
TOTAL = 77 * len(CIVS)
CATALOG_NAMES = ('recording-costs.json', 'recording-balance.json',
                 'recording-subjects.json', 'unique-unit-roster.json')


def queue_complete(work, total, campaign_count):
    """Require verified per-campaign receipts, not just a stale top-level label."""
    if not (work / 'status.json').exists():
        return False
    status = read(work / 'status.json')
    if status.get('state') != 'COMPLETE' or status.get('verified') != total:
        return False
    queue = read(work / 'queue.json')
    if queue['total'] != total or len(queue['campaigns']) != campaign_count:
        return False
    for campaign in queue['campaigns']:
        path = work / campaign['key']
        state = read(path / 'capture/status.json')
        expected = {r['id'] for r in read(path / 'manifest.json')['matchups']}
        actual = [r['jobId'] for r in state.get('results', []) if r['status'] == 'verified']
        if (state.get('state') != 'COMPLETE' or state.get('completed') != 77
                or state.get('failed') or state.get('pendingExports')
                or len(expected) != 77 or len(actual) != 77 or set(actual) != expected):
            return False
    return True


def guards_complete(work=PREDECESSOR):
    return queue_complete(work, 385, 5)


def audit_subjects():
    import aoe2x.dbgen.unit_analyzer as module
    audit = read(ROOT / 'data/local/dat-release-audit/audit.json')
    dat_hash = hashlib.sha256(DAT.read_bytes()).hexdigest()
    if dat_hash != audit['sources']['installed_dat']['sha256']:
        raise ValueError('Installed DAT changed; review costs before planning')
    hashes = {}
    for source in audit['sources']['audit_extractions']:
        if '/installed/' not in source['path'].replace('\\', '/'):
            continue
        name = source['path'].replace('\\', '/').split('/')[-1]
        hashes[name] = hashlib.sha256((EXTRACTED / name).read_bytes()).hexdigest()
        if hashes[name] != source['sha256']:
            raise ValueError(f'Installed extraction changed: {name}')
    if set(hashes) != {p.name for p in EXTRACTED.glob('*.json')}:
        raise ValueError('Incomplete extraction provenance')
    module.OUTPUT_DIR = EXTRACTED
    analyzer = module.UnitAnalyzer()
    subjects = []
    for civ in CIVS:
        available = {r['id'] for r in audit['current_costs'] if r['civ'] == civ}
        master = 2701 if 2701 in available else 2700
        if master not in available:
            raise ValueError(f'Mounted Crossbowman availability differs for {civ}')
        key = 'heavy_mounted_crossbowman' if master == 2701 else 'mounted_crossbowman'
        unit = analyzer.get_unit(master)
        if unit_const(key) != master or unit['class'] != 36:
            raise ValueError('Unexpected mounted crossbow unit identity')
        row = dict(civ=civ, slug=f'{key}_{civ.lower()}', master=master,
                   label=unit['name'], **{'class': 'mobile_ranged'}, scenarioKey=key,
                   baseCost=dict(food=0, wood=40, gold=65),
                   costSource='Installed DAT; highest available Imperial unit and all own-civilization discounts')
        price = audited_price(analyzer, row)
        gold = {'Franks': 39, 'Portuguese': 52}.get(civ, 65)
        if price['effectiveCost'] != dict(food=0, wood=40, gold=gold):
            raise ValueError(f'Mounted crossbow cost differs for {civ}')
        result = analyzer.calculate_unique_unit_stats(civ, dict(
            base_id=master, display_name=unit['name'], unit_class=unit['class']), 4)
        subjects.append(dict(subject=row, price=price, stats=dict(civ_name=civ,
            final_hp=result['stats'].hp, stats=asdict(result['stats']),
            appliedBonuses=result['applied_bonuses'])))
    return dict(datSha256=dat_hash, extractionHashes=hashes, subjects=subjects), analyzer


def activate(audit, analyzer, *, append=False):
    if not guards_complete():
        raise RuntimeError('All 385 Varangian Guard captures must verify before changing catalogs')
    previous = read(WORK / 'queue.json') if append else None
    if append:
        if not queue_complete(WORK, previous['total'], len(previous['campaigns'])):
            raise RuntimeError('Finish the existing queue before appending a new civilization')
        for item in audit['subjects']:
            if (WORK / item['subject']['civ'].lower()).exists():
                raise FileExistsError('Additional civilization already exists; resume instead of preparing again')
    elif (WORK / 'queue.json').exists() or list(WORK.glob('*/manifest.json')):
        raise FileExistsError('Already prepared or partially prepared; resume/review, do not overwrite')
    paths = [ROOT / 'data' / name for name in CATALOG_NAMES]
    costs, balance, subjects, roster = map(read, paths)
    if len(roster['units']) != 77 or costs['releaseAudit']['datSha256'] != audit['datSha256']:
        raise ValueError('Expected the approved 77-unit release roster')
    for opponent in roster['units']:
        if audited_price(analyzer, opponent)['effectiveCost'] != costs['units'][opponent['civ']+'|'+opponent['slug']]['effectiveCost']:
            raise ValueError(f'Opponent cost needs review: {opponent["slug"]}')
    for path in paths:
        if not (WORK / 'provenance' / path.name).exists():
            save(WORK / 'provenance' / path.name, read(path))
    for item in audit['subjects']:
        row = item['subject']; identity = row['civ'] + '|' + row['slug']
        policy = dict(master=row['master'], population=1.0, sharedAcrossCivilizations=True,
                      classificationEvidence='Shared regional cavalry archer; all discounts fully effective',
                      populationEvidence='One comparison population per physical unit')
        for table, value in ((costs['units'], item['price']), (balance['units'], policy)):
            if identity in table and table[identity] != value:
                raise ValueError(f'Existing identity conflict: {identity}')
            table[identity] = value
        old = next((r for r in subjects['units'] if r['slug'] == row['slug']), None)
        if old and old != row:
            raise ValueError(f'Existing subject conflict: {identity}')
        if not old:
            subjects['units'].append(row)
    for path, value in zip(paths[:3], (costs, balance, subjects)):
        save(path, value)
    config = load_config(); campaigns = list(previous['campaigns']) if previous else []
    for item in audit['subjects']:
        subject = item['subject']; civ = subject['civ']; work = WORK / civ.lower()
        prefix = f'mounted_crossbow_{civ.lower()}_v3_unique_'
        rows = [dict(id=safe_slug(f'{prefix}{i:02}_{r["slug"]}'),
            side2=subject['slug'], civ2=civ, side3=r['slug'], civ3=r['civ'],
            balance=dict(mode='geometric_shared_discount', cap=27,
                         weights=dict(food=1, wood=.9, gold=1.1)))
            for i, r in enumerate(roster['units'], 1)]
        save(work / 'requested.json', dict(schemaVersion=1, matchups=rows))
        evidence = []
        for request in _load_batch(work / 'requested.json')[1]:
            plan = plan_matchup(config, request)
            create_job(config.artifacts_root, plan['jobId'])
            validate_plan_costs(plan)
            if not plan['side2']['ranged'] or 'maxResources' in plan['balance']:
                raise ValueError('Mounted crossbow classification or count policy differs')
            save(work / 'plans' / f'{plan["jobId"]}.json', plan)
            evidence.append(dict(jobId=plan['jobId'], counts=[plan[s]['count'] for s in ('side2', 'side3')], scenario=plan['scenario']))
        for path in paths:
            save(work / 'frozen-catalogs' / path.name, read(path))
        save(work / 'subject-stats.json', [item['stats']])
        save(work / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(work / 'preflight.json', dict(state='PASSED', total=77, jobs=evidence))
        save(work / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        campaigns.append(dict(key=civ.lower(), civilization=civ, unit=subject['label'],
            slug=subject['slug'], jobPrefix=prefix, workDirectory=str(work), total=77))
        print(f'{civ}: 77 plans passed', flush=True)
    save(WORK / 'queue.json', dict(state='READY', captureOnly=True,
        total=sum(c['total'] for c in campaigns), retention='raw', campaigns=campaigns,
        authorization='Approved mounted crossbow civilizations: ' + ', '.join(c['civilization'] for c in campaigns) + '; raw video, frames and metadata, followed by verified external archival.'))


def main():
    global WORK, CIVS, TOTAL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--additional', action='store_true',
        help='Prepare the approved Briton, Celt, Bohemian and Burgundian follow-on without changing the original queue')
    parser.add_argument('--include-italians', action='store_true',
        help='Add Italians only when separately authorized, with --additional')
    args = parser.parse_args()
    if args.include_italians and not args.additional:
        parser.error('--include-italians requires --additional')
    if args.additional:
        if not queue_complete(WORK, 616, 8):
            raise RuntimeError('The original eight mounted crossbow sets must finish before preparing additional variants')
        WORK = ROOT / 'data/local/mounted-crossbow-expansion'
        CIVS = ('Britons', 'Celts', 'Bohemians', 'Burgundians')
        if args.include_italians:
            CIVS += ('Italians',)
        TOTAL = 77 * len(CIVS)
    if args.activate and not guards_complete():
        raise RuntimeError('Varangian Guards are still incomplete; active catalogs left unchanged')
    audit, analyzer = audit_subjects()
    save(WORK / 'release-cost-audit.json', audit)
    save(WORK / 'follow-on-request.json', dict(state='AUTHORIZED', total=TOTAL,
        prerequisite=str(ROOT / 'data/local/mounted-crossbow-capture' if args.additional else PREDECESSOR),
        civilizations=list(CIVS), keepLocal=True,
        countsPolicy='geometric_full_discount_weighted_resources_v3', opponentCount=77))
    if args.activate:
        activate(audit, analyzer)
    print(json.dumps([dict(civ=i['subject']['civ'], unit=i['subject']['label'],
        cost=i['price']['effectiveCost'], pilotHp=i['stats']['final_hp']) for i in audit['subjects']], indent=2))


if __name__ == '__main__':
    main()
