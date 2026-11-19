"""Freeze only the 80 detailed-map Cavalier trials affected by auto-Paladin upgrades.

Chinese Cavaliers cost the same, so counts and buffers must stay unchanged.
Original local plans/media remain evidence. The user's replacement authorization
is bound to exact old archive rows and index hashes, never a filename glob.
"""
import contextlib
import copy
import dataclasses
import io
import json
import shutil
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from compact_recording_archive import digest
from prepare_jomsviking_capture import DAT, audited_price
from prepare_norse_standard_capture import CATALOGS, available
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'data/local/detailed-standard-cavalier-retakes'
ORIGINAL = ROOT/'data/local/detailed-standard-capture'
SHARE = Path(r'\\100.123.128.35\AoE2-Incoming')


def main():
    if WORK.exists():
        raise FileExistsError('Correction already prepared; resume, never reprepare')
    queue = read(ORIGINAL/'queue.json')
    delivery = read(ROOT/'data/local/detailed-standard-delivery/status.json')
    if read(ORIGINAL/'status.json').get('state') != 'COMPLETE' or delivery['state'] != 'COMPLETE':
        raise ValueError('Original capture and delivery workers must be finished')
    audit = read(ROOT/'data/local/dat-release-audit/audit.json')
    if sha256(DAT) != audit['sources']['installed_dat']['sha256']:
        raise ValueError('Installed DAT changed; cost/stat audit required')
    import aoe2x.dbgen.unit_analyzer as module
    module.OUTPUT_DIR = ROOT/'data/local/dat-release-audit/installed'
    analyzer = module.UnitAnalyzer()
    available('Chinese', 283)
    stats = analyzer.calculate_unique_unit_stats('Chinese', dict(base_id=283,
        display_name='Cavalier', unit_class=analyzer.get_unit(283)['class']), 4)
    if stats['stats'].hp != 140:
        raise ValueError('Expected fully upgraded Chinese Cavalier with 140 HP')

    # Bind every replacement before touching catalogs or launching the game.
    selections = []
    for campaign in queue['campaigns']:
        old = Path(campaign['workDirectory'])
        rows = [r for r in read(old/'manifest.json')['matchups'] if r['opponentIndex'] == 3]
        if len(rows) not in (5, 10) or any(r['civ3'] != 'Spanish' or r['side3'] != 'cavalier_spanish' for r in rows):
            raise ValueError('Unexpected original Cavalier trials')
        receipt = delivery['packages'][campaign['key']]
        destination = Path(receipt['identity']['destination'])
        if not destination.is_relative_to(SHARE):
            raise ValueError('Destination escaped the authorized share')
        index_path = destination/'run.json'
        if digest(index_path) != receipt['indexSha256']:
            raise ValueError('Archive changed since delivery; do not overwrite it')
        index = read(index_path)
        archived = {r['jobId']: r for r in index['matchups']}
        captured = {r['jobId']: r for r in read(old/'capture/status.json')['results']}
        evidence = []
        for row in rows:
            source = Path(captured[row['id']]['runDirectory'])
            bundle = read(source/'recording.json')
            opening = read(source/bundle['files']['hp']['path'])['rows'][0]['side2']
            per_unit = opening['hp']/opening['count']
            if abs(per_unit-180) > .1:
                raise ValueError(f'Correction scope requires recorded Paladin HP: {row["id"]}')
            if row['id'] not in archived:
                raise ValueError('Original row absent from archive')
            evidence.append(dict(oldJobId=row['id'], recordedOpponentHpPerUnit=per_unit,
                                 expectedChineseHpPerUnit=140))
        selections.append((campaign, rows, index, receipt, evidence))
    assert sum(len(s[1]) for s in selections) == 80
    WORK.mkdir(parents=True)
    catalogs = {n: read(ROOT/'data'/n) for n in CATALOGS}
    for name, obj in catalogs.items():
        save(WORK/'provenance'/name, obj)
    row = dict(civ='Chinese', slug='cavalier_chinese', label='Cavalier', master=283,
        scenarioKey='cavalier', **{'class':'melee'}, baseCost=dict(food=60,wood=0,gold=75),
        costSource='Installed DAT; fully upgraded Chinese Cavalier, no Paladin upgrade')
    subjects = catalogs['recording-subjects.json']['units']
    existing = next((r for r in subjects if r['slug'] == row['slug']), None)
    if existing is None:
        subjects.append(row)
    elif existing != row:
        raise ValueError('Conflicting Chinese Cavalier registration')
    price = audited_price(analyzer, row)
    if price['effectiveCost'] != dict(food=60,wood=0,gold=75):
        raise ValueError('Unexpected Chinese Cavalier cost')
    identity = 'Chinese|cavalier_chinese'
    catalogs['recording-costs.json']['units'][identity] = price
    catalogs['recording-balance.json']['units'][identity] = dict(master=283,population=1.0,
        sharedAcrossCivilizations=True, populationEvidence='One comparison population per physical unit',
        classificationEvidence='Standard unit; full discounts')
    for name in ('recording-subjects.json','recording-costs.json','recording-balance.json'):
        save(ROOT/'data'/name, catalogs[name])
    config = load_config()
    stack = _load_stack(config)
    campaigns = []
    for campaign, originals, index, receipt, evidence in selections:
        work = WORK/campaign['key']
        old = Path(campaign['workDirectory'])
        requests = []
        for original in originals:
            request = copy.deepcopy(original)
            request.update(id=original['id'].replace('dstd_', 'dstd_chinese_cav_', 1),
                           civ3='Chinese', side3='cavalier_chinese')
            requests.append(request)
        save(work/'requested.json', dict(schemaVersion=1, matchups=requests))
        mapping, cases = [], set()
        for original, request, parsed in zip(originals, requests, _load_batch(work/'requested.json')[1]):
            prior = read(old/'plans'/f'{original["id"]}.json')
            plan = plan_matchup(config, parsed)
            validate_plan_costs(plan)
            for side in ('side2','side3'):
                for key in ('count','effectiveCost','weightedCost','armyWeightedResources'):
                    if prior[side][key] != plan[side][key]:
                        raise ValueError(f'Unrelated army change: {side}.{key}')
            if plan['scenario'] != prior['scenario']:
                raise ValueError('Unrelated scenario/buffer/scenery change')
            save(work/'plans'/f'{plan["jobId"]}.json', plan)
            case = plan['scenario']['family']
            if case not in cases:
                target = work/'preflight-scenarios'/f'{request["bufferSetting"]}.aoe2scenario'
                target.parent.mkdir(parents=True,exist_ok=True)
                sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2','side3')]
                with contextlib.redirect_stdout(io.StringIO()):
                    stack['build_run'](*sides, target, counts=tuple(plan[k]['count'] for k in ('side2','side3')),
                        template=capture_template_path(config, plan), player4_count=plan['scenario'].get('player4Count'),
                        remove_player4_buffer=plan['scenario'].get('player4Buffer') == 'none')
                    validation = _validate_scenario(config, plan, target, stack)
                save(target.with_suffix('.validation.json'), validation)
                cases.add(case)
            mapping.append(dict(oldJobId=original['id'], jobId=request['id'],
                iteration=request['iteration'],opponentIndex=3,bufferSetting=request['bufferSetting'],
                bufferComparisonApplicable=request['bufferComparisonApplicable'],
                counts=[plan[k]['count'] for k in ('side2','side3')],hussars=plan['scenario'].get('player4Count',0)))
        for name in CATALOGS:
            save(work/'frozen-catalogs'/name, read(ROOT/'data'/name))
        save(work/'subject-stats.json', read(old/'subject-stats.json'))
        save(work/'pilot.json', dict(schemaVersion=1,matchups=requests[:1]))
        save(work/'pilot-opponent-expectations.json', {requests[0]['id']: dict(civ='Chinese',master=283,hpPerUnit=140)})
        save(work/'manifest.json', dict(schemaVersion=1,matchups=requests))
        save(work/'preflight.json', dict(state='PASSED',total=len(requests),jobs=mapping,evidence=evidence))
        save(work/'replacement.json', dict(destination=receipt['identity']['destination'],
            previousIndexSha256=receipt['indexSha256'],mapping=mapping,
            reason='Spanish Cavaliers auto-upgraded to Paladins in Post-Imperial; replace with Chinese Cavaliers',
            authorization='User explicitly requested replacement of these Cavalier files in AoE2-Incoming'))
        save(work/'previous-run.json', index)
        campaigns.append(dict(campaign, total=len(requests), workDirectory=str(work)))
    save(WORK/'opponent-reference.json', dict(civ='Chinese',master=283,price=price,
        stats=dataclasses.asdict(stats['stats']),datSha256=sha256(DAT)))
    save(WORK/'queue.json', dict(schemaVersion=1,captureOnly=True,total=80,campaigns=campaigns,
        captureAndReplaceInOrder=True,preserveOriginalLocalCaptures=True))
    print(json.dumps(dict(work=str(WORK),total=80,firstThree=20,remaining=60),indent=2))


if __name__ == '__main__':
    main()
