"""Audit recorded Saxon Guard counts; optionally freeze only proven cost retakes.

Original plans, receipts and media are read-only. The audit works without the
archive drive because verified recording metadata remains on the recording PC.
--prepare updates one live price entry and writes a separate, resumable queue.
"""
import argparse
import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.planner import plan_matchup
from prepare_jomsviking_capture import DAT, ROOT, audited_price
from run_champi_comparison_capture import read, save

OLD = ROOT / 'data/local/varangian-guard-capture/saxons'
AUDIT = ROOT / 'data/local/saxon-guard-cost-audit'
WORK = ROOT / 'data/local/saxon-guard-cost-retakes'
KEY = 'Saxons|elite_varangian_guard_saxons'
PREFIX = 'varangian_guard_saxons_discount_'
SOURCE_URL = 'https://www.ageofempires.com/news/saxons-civilization-deep-dive/'


def evidence(path):
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def corrected_counts(opponent_cost):
    cost = 52 + 1.1 * 36
    smaller = max(1, math.floor(27 * math.sqrt(min(cost, opponent_cost) / max(cost, opponent_cost)) + .5))
    return [27, smaller] if cost <= opponent_cost else [smaller, 27]


def audit():
    original = read(OLD.parent / 'release-cost-audit.json')
    if evidence(DAT)['sha256'] != original['datSha256']:
        raise ValueError('Installed DAT changed; review it before making a cost-only retake')
    extracted = ROOT / 'data/local/dat-release-audit/installed'
    for name, digest in original['extractionHashes'].items():
        if evidence(extracted / name)['sha256'] != digest:
            raise ValueError(f'Original installed extraction changed: {name}')
    status = read(OLD / 'capture/status.json')
    results = {r['jobId']: r for r in status['results'] if r['status'] == 'verified'}
    requests = read(OLD / 'manifest.json')['matchups']
    if len(requests) != 77 or len(results) != 77 or status.get('pendingExports'):
        raise ValueError('Expected the completed original 77-match Saxon campaign')
    rows = []
    for request in requests:
        path = OLD / 'plans' / (request['id'] + '.json')
        plan = read(path)
        receipt_path = Path(results[request['id']]['runDirectory']) / 'recording.json'
        receipt = read(receipt_path)
        before = [receipt['sides'][s]['count'] for s in ('side1', 'side2')]
        if before != [plan[s]['count'] for s in ('side2', 'side3')] or receipt['planHash'] != plan['planHash']:
            raise ValueError(f'Original plan/recording conflict: {request["id"]}')
        if plan['side2']['effectiveCost'] != dict(food=65, wood=0, gold=45):
            raise ValueError('Original price differs from the diagnosed omission')
        cost = plan['side3']['weightedCost']
        after = corrected_counts(cost)
        before_buffer = plan['scenario'].get('player4Count', 0)
        # Independent arithmetic check against the production buffer function.
        after_buffer = math.floor(max(5, min(10, 5 + (after[1] * cost - 1000) / 1800)) + .5) if plan['side3']['ranged'] else 0
        rows.append(dict(oldJobId=request['id'], opponent=plan['side3']['label'],
            opponentCiv=plan['side3']['civ'], opponentSlug=plan['side3']['slug'],
            opponentWeightedCost=cost, recordedCounts=before, correctedCounts=after,
            recordedHussars=before_buffer, correctedHussars=after_buffer,
            needsRetake=before != after or before_buffer != after_buffer,
            plan=evidence(path), verifiedRecordingMetadata=evidence(receipt_path)))
    report = dict(checkedAt=datetime.now(timezone.utc).isoformat(), subject=KEY,
        sourceUrl=SOURCE_URL, installedHelpKey=120209, dat=evidence(DAT),
        originalDatSha256=original['datSha256'], datUnchanged=True,
        discount=dict(perBuildingPercent=5, maximumPercent=20, assumedTownCentersAndCastles=4),
        oldPrice=dict(food=65, wood=0, gold=45, weighted=114.5),
        correctPrice=dict(food=52, wood=0, gold=36, weighted=91.6),
        rawArchiveRequiredForCountAudit=False,
        total=len(rows), retakes=sum(r['needsRetake'] for r in rows),
        bufferChanges=sum(r['recordedHussars'] != r['correctedHussars'] for r in rows),
        sourceManifest=evidence(OLD / 'manifest.json'), matchups=rows)
    save(AUDIT / 'audit.json', report)
    lines = ['# Saxon Varangian Guard cost correction', '',
        'Confirmed omission: the original pricing helper applied the Saxon foot-soldier discount only to Hearth Troops. Varangian Guards also qualify.', '',
        f'Source: [official Saxon civilization description]({SOURCE_URL}); installed English help 120209 specifies 5% per controlled Town Center/Castle, capped at 20%.', '',
        'The installed DAT is unchanged from the original capture audit. The approved maximum discount changes 65F + 45G to **52F + 36G**, or **91.6 weighted resources** instead of 114.5.', '',
        f'**{report["retakes"]}/{len(rows)} count pairs require retakes; {report["bufferChanges"]} Hussar buffers also change.** Other Guard civilizations are unaffected by this omission. Hearth Troop already had the discount; Mounted Crossbowmen are not foot soldiers.', '',
        'Evidence: all original plans agree with the retained verified recording metadata. Raw videos/frames are archived externally and were not needed to calculate this correction. JSON includes source paths and SHA-256 hashes. No originals are modified.', '',
        'Counts below are Saxon Guards versus the opponent. Cheaper weighted unit: 27; expensive unit: round half up of 27 × sqrt(cheaper cost / expensive cost). Weights: food 1, wood 0.9, gold 1.1; full discounts; no resource ceiling. Extra Hussars use the ranged army’s corrected fielded cost.', '',
        '| Opponent | Recorded | Correct | Hussars: recorded → correct |',
        '|---|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["opponentCiv"]}: {r["opponent"]} | {r["recordedCounts"][0]} vs {r["recordedCounts"][1]} | {r["correctedCounts"][0]} vs {r["correctedCounts"][1]} | {r["recordedHussars"]} → {r["correctedHussars"]} |')
    (AUDIT / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def prepare(report):
    if (WORK / 'queue.json').exists() or (WORK / 'saxons/manifest.json').exists():
        raise FileExistsError('Retakes already prepared; resume the frozen queue')
    import aoe2x.dbgen.unit_analyzer as module
    module.OUTPUT_DIR = ROOT / 'data/local/dat-release-audit/installed'
    analyzer = module.UnitAnalyzer()
    catalog_path = ROOT / 'data/recording-costs.json'
    old_bytes = catalog_path.read_bytes()
    costs = json.loads(old_bytes)
    corrected = audited_price(analyzer, costs['units'][KEY])
    if corrected['effectiveCost'] != dict(food=52, wood=0, gold=36):
        raise ValueError('Corrected price does not match the independent audit')
    old_requests = read(OLD / 'manifest.json')['matchups']
    audit_by_id = {r['oldJobId']: r for r in report['matchups']}
    for row in old_requests:
        plan = read(OLD / 'plans' / (row['id'] + '.json'))
        other = costs['units'][row['civ3'] + '|' + row['side3']]
        if other['effectiveCost'] != plan['side3']['effectiveCost']:
            raise ValueError(f'Unrelated opponent price changed: {row["id"]}')
    save(WORK / 'provenance/recording-costs-before.json', costs)
    costs['units'][KEY] = corrected
    save(catalog_path, costs)
    work = WORK / 'saxons'
    selected = [r for r in old_requests if audit_by_id[r['id']]['needsRetake']]
    rows = []
    for original in selected:
        row = copy.deepcopy(original)
        row['id'] = PREFIX + original['id'].removeprefix('varangian_guard_saxons_v3_unique_')
        rows.append(row)
    save(work / 'requested.json', dict(schemaVersion=1, matchups=rows))
    jobs = []
    try:
        config = load_config()
        for original, request in zip(selected, _load_batch(work / 'requested.json')[1]):
            prior = read(OLD / 'plans' / (original['id'] + '.json'))
            expected = audit_by_id[original['id']]
            plan = plan_matchup(config, request)
            validate_plan_costs(plan)
            if [plan[s]['count'] for s in ('side2', 'side3')] != expected['correctedCounts']:
                raise ValueError('Planner disagrees with independent count audit')
            if plan['scenario'].get('player4Count', 0) != expected['correctedHussars']:
                raise ValueError('Planner disagrees with independent buffer audit')
            for key in ('family', 'goldenSha256', 'placementRule', 'hasPlayer4Gate', 'preserveOwnerOrientation'):
                if plan['scenario'].get(key) != prior['scenario'].get(key):
                    raise ValueError(f'Unrelated scenario setting changed: {key}')
            for side in ('side2', 'side3'):
                for key in ('slug', 'civ', 'mechanicsCiv', 'class', 'ranged'):
                    if plan[side][key] != prior[side][key]:
                        raise ValueError(f'Unrelated unit setting changed: {side}.{key}')
            save(work / 'plans' / (plan['jobId'] + '.json'), plan)
            jobs.append(dict(oldJobId=original['id'], jobId=plan['jobId'], counts=expected['correctedCounts'], hussars=expected['correctedHussars']))
    except Exception:
        catalog_path.write_bytes(old_bytes)
        raise
    for name in ('recording-costs.json', 'recording-balance.json', 'recording-subjects.json', 'unique-unit-roster.json'):
        save(work / 'frozen-catalogs' / name, read(ROOT / 'data' / name))
    stats = read(OLD / 'subject-stats.json')
    stats[0]['stats'].update(cost_food=52, cost_wood=0, cost_gold=36)
    stats[0]['conditionalCostEvidence'] = corrected['effects'][-1]
    save(work / 'subject-stats.json', stats)
    save(work / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
    save(work / 'manifest.json', dict(schemaVersion=1, matchups=rows))
    save(work / 'preflight.json', dict(state='PASSED', total=len(rows), jobs=jobs, audit=evidence(AUDIT / 'audit.json')))
    save(WORK / 'queue.json', dict(state='READY', captureOnly=True, total=len(rows), retention='raw',
        authorization='September 27: correct the omitted maximum Saxon Varangian Guard discount and redo only battles with changed counts. Preserve historical sources.',
        campaigns=[dict(key='saxons', civilization='Saxons', unit='Elite Varangian Guard',
            slug='elite_varangian_guard_saxons', jobPrefix=PREFIX, workDirectory=str(work), total=len(rows))]))
    return dict(work=str(WORK), total=len(rows), changedCatalogIdentities=[KEY])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    report = audit()
    result = dict(total=report['total'], retakes=report['retakes'], bufferChanges=report['bufferChanges'], report=str(AUDIT / 'REPORT.md'))
    if args.prepare:
        result['prepared'] = prepare(report)
    print(json.dumps(result, indent=2))
