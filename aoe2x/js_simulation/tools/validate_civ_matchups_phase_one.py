#!/usr/bin/env python3
"""Validate inference-only output without importing or executing combat."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-inference-phase1-2026-10-31'
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT


def rows(name):
    with gzip.open(OUT / f'{name}.jsonl.gz', 'rt') as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


manifest = json.loads((OUT / 'manifest.json').read_text())
summary = json.loads((OUT / 'summary.json').read_text())
assert manifest['phase'] == 'infer-only'
assert manifest['simulationJobsRun'] == summary['simulationJobsRun'] == 0
assert summary['manifestHash'] == manifest['buildHash']
for item in manifest['sourceFiles']:
    assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
for item in manifest['outputs']:
    assert hashlib.sha256((OUT / item['file']).read_bytes()).hexdigest() == item['sha256'], item['file']

source = json.loads((ROOT / 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-consolidated-2026-10-29/manifest.json').read_text())
variants = {f"{u['civilization']}|{u['slug']}" for u in source['roster']['units']}
assert len(variants) == 555
variant_profiles = {x['key']: x['profileHash'] for x in json.loads((OUT / 'variant-profiles.json').read_text())}
assert set(variant_profiles) == variants
expected = set()
ordered = sorted(variants)
for i, a in enumerate(ordered):
    for b in ordered[i + 1:]:
        if a.split('|', 1)[0] != b.split('|', 1)[0]:
            expected.add((a, b))
assert len(expected) == 151223

evidence = list(rows('evidence-ledger'))
assert len(evidence) == 7677
by_matchup = collections.defaultdict(list)
for run in evidence:
    by_matchup[run['matchupId']].append(run)
profiles = {}
profile_counts = collections.Counter()
for record in rows('profile-matchups'):
    key = record['pairKey']
    assert key not in profiles
    assert record['profiles'] == sorted(record['profiles'])
    assert record['aliases'] > 0
    assert record['outcome'] in ('a_win', 'b_win', 'equivalent', 'close_uncertain', 'unresolved')
    if record['outcome'] in ('a_win', 'b_win'):
        winner = record['profiles'][0 if record['outcome'] == 'a_win' else 1]
        assert record['winnerProfileHash'] == winner
        if record['evidenceType'] == 'observed':
            assert record['sourceMatchups']
            for matchup in record['sourceMatchups']:
                runs = [r for r in by_matchup[matchup] if r['corrected']]
                assert len({r['seed'] for r in runs}) >= 3
                assert {0, 1, 2} <= {r['seed'] for r in runs}
                assert {r['winnerHash'] for r in runs} == {winner}
        elif record['evidenceType'] == 'inferred':
            assert record['ruleId'] and record['rootAnchorIds']
            assert all(any(r['corrected'] for r in by_matchup[mid]) for mid in record['rootAnchorIds'])
            assert 'unitRemainingHp' not in record and 'winProbability' not in record
        else:
            raise AssertionError('decisive pair missing evidence')
    elif record['outcome'] == 'unresolved':
        assert record['needsSim'] and record['reasonCodes']
    elif record['outcome'] == 'equivalent':
        assert record['profiles'][0] == record['profiles'][1]
    profiles[key] = record
    profile_counts[record['outcome']] += 1
assert len(profiles) == 68916
assert dict(profile_counts) == summary['coverage']['profiles']

seen = set()
aliases = collections.Counter()
cell_counts = collections.Counter()
civ_pairs = set()
for cell in rows('civ-matchups'):
    left, right = f"{cell['civA']}|{cell['unitA']}", f"{cell['civB']}|{cell['unitB']}"
    assert cell['civA'] < cell['civB']
    key = tuple(sorted((left, right)))
    assert key in expected and key not in seen
    seen.add(key)
    civ_pairs.add((cell['civA'], cell['civB']))
    parent = profiles[cell['pairKey']]
    aliases[cell['pairKey']] += 1
    assert cell['evidenceType'] == parent['evidenceType']
    assert cell['needsSim'] == parent['needsSim']
    assert cell['outcome'] in ('a_win', 'b_win', 'equivalent', 'close_uncertain', 'unresolved')
    if 'winnerProfileHash' in parent:
        winner = parent['winnerProfileHash']
        assert cell['outcome'] == ('a_win' if winner == variant_profiles[left] else 'b_win')
    else:
        assert cell['outcome'] == parent['outcome']
    if 'candidateWinnerProfileHash' in parent:
        assert cell['candidateOutcome'] == ('a_win' if parent['candidateWinnerProfileHash'] == variant_profiles[left] else 'b_win')
    else:
        assert cell['candidateOutcome'] is None
    cell_counts[cell['outcome']] += 1
assert seen == expected
assert len(civ_pairs) == 1540
assert all(aliases[k] == v['aliases'] for k, v in profiles.items())
assert dict(cell_counts) == summary['coverage']['cells']

needs = list(rows('needs-sim'))
assert len(needs) == summary['uniqueNeedsSim'] == profile_counts['unresolved']
assert {x['pairKey'] for x in needs} == {k for k, v in profiles.items() if v['needsSim']}
requirements = list(rows('requirements'))
assert sum(r['affectedProfilePairs'] for r in requirements) == len(needs)
assert sum(r['affectedCells'] for r in requirements) == cell_counts['unresolved']
assert len(requirements) == summary['groupedRequirements']

review = json.loads((OUT / 'review.json').read_text())
britons = review['britonsAztecs']
assert len(britons) == 6
assert all(r['outcome'] == 'unresolved' for r in britons)
assert all(r['candidateOutcome'] == 'b_win' for r in britons if r['nameA'] == 'Pikeman')
assert all(r['candidateOutcome'] is None for r in britons if r['nameA'] != 'Pikeman')

print(json.dumps({'status': 'passed', 'manifestHash': manifest['buildHash'],
                  'profilePairs': len(profiles), 'cells': len(seen),
                  'coverage': dict(profile_counts), 'unresolvedRequirements': len(requirements),
                  'simulationsRun': 0}, indent=2))
