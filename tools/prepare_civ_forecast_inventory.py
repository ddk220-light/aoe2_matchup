"""Freeze the remaining production forecasts without changing any prediction."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'aoe2x/js_simulation/calibration/campaigns'
CAMPAIGN = BASE / 'civ-matchups-forecast-validation-2026-11-07'
WEBSITE_COMMIT = 'c907cc23668611851a2112911893929c3b905696'
BASELINE_SHA = '36626bc0f74242de5482d98362695cec15226eb87cba8767371841a62bd231d5'
# These are frozen categories, not calibrated probabilities or new forecasts.
ORDER = ['predicted_close', 'opponent_specific_forecast', 'weak_model_agreement',
         'broader_agreement', 'stronger_support']


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def write_rows(name, rows):
    data = ''.join(encode(row) + '\n' for row in rows).encode()
    (CAMPAIGN / name).write_bytes(gzip.compress(data, mtime=0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=Path('/workspace/aoe2_advisor_release/data/golden/civ_matchups_first_pass.db'))
    args = parser.parse_args()
    assert not CAMPAIGN.exists(), 'Inventory already exists; never overwrite it.'
    assert hashlib.sha256(args.database.read_bytes()).hexdigest() == BASELINE_SHA
    old = BASE / 'civ-matchups-mismatch-validation-2026-11-05'
    owner = json.loads((old / 'user-reviews/2026-11-07-five-blocked-winners.json').read_text())
    declared = {r['originalEvidenceId']: r for r in owner['outcomes']}
    assert len(declared) == 5
    with sqlite3.connect(f'file:{args.database}?mode=ro', uri=True) as db:
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        cell_counts = dict(db.execute('SELECT evidence_id,COUNT(*) FROM cells GROUP BY evidence_id'))
        units = [json.loads(data) for (data,) in db.execute('SELECT data FROM units ORDER BY id')]
        metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
        assert metadata['mismatch_validation']['reviewedContexts'] == 10222
        forecasts = []
        for identifier, blob in db.execute('SELECT id,data FROM evidence ORDER BY id'):
            evidence = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            if evidence['evidenceType'] == 'predicted_unvalidated':
                assert not evidence.get('mismatchValidation') and not evidence['verified']
                forecasts.append((identifier, evidence))
    assert len(forecasts) == 39148
    tiers = collections.Counter()
    ready, held, originals, inventory = [], [], [], []
    for identifier, evidence in forecasts:
        context = evidence['context']
        digest = hashlib.sha256(encode(context).encode()).hexdigest()
        tier = evidence['predictionTier']
        tiers[tier] += 1
        job = {'id': 'fv_' + digest[:24], 'contextHash': digest, 'context': context,
               'pairKey': evidence['pairKey'], 'profileHashes': context['profiles'],
               'counts': context['counts'], 'family': context['family'],
               'engineFamily': context['engineFamily'], 'scenarioHash': context['scenarioHash'],
               'evidenceIds': [identifier], 'displayedCells': cell_counts[identifier],
               'predictionTier': tier, 'categories': ['remaining_forecast'],
               'validationMode': 'fresh_seed_set'}
        assert sorted(job['profileHashes']) == job['pairKey'].split('|')
        originals.append({'evidenceId': identifier, 'evidence': evidence})
        if identifier in declared:
            assert evidence == declared[identifier]['originalEvidence']
            reason = 'owner_confirmed_outcome_but_diagnosed_native_stall'
            record = dict(job, status='unfinished_not_a_result', reason=reason,
                          diagnosisPath=declared[identifier]['diagnosisPath'],
                          diagnosisSha256=declared[identifier]['diagnosisSha256'],
                          userSuppliedWinnerTeamKey=declared[identifier]['userSuppliedWinnerTeamKey'])
            held.append(record)
        elif tier == 'repaired_engine_projection':
            assert evidence.get('recoveryProjection')
            record = dict(job, status='unfinished_not_a_result',
                          reason='prior_source_blocker_with_cross_engine_projection_requires_separate_native_recovery_review',
                          recoveryProjection=evidence['recoveryProjection'])
            held.append(record)
        else:
            assert tier in ORDER, 'Unknown confidence tier must be reviewed before queueing.'
            job['priority'] = ORDER.index(tier)
            ready.append(job)
        inventory.append(dict(job, queueStatus='held' if any(r['id'] == job['id'] for r in held) else 'ready'))
    ready.sort(key=lambda job: (job['priority'], job['evidenceIds'][0]))
    assert len(ready) == 39124 and len(held) == 24
    assert len({r['contextHash'] for r in inventory}) == len(inventory)
    assert not {r['id'] for r in ready} & {r['id'] for r in held}
    CAMPAIGN.mkdir(parents=True)
    (CAMPAIGN / 'sources').mkdir()
    shutil.copyfile(args.database, CAMPAIGN / 'sources/production-baseline.db')
    (CAMPAIGN / 'sources/variant-profiles.json').write_text(encode(units) + '\n')
    write_rows('jobs.jsonl.gz', ready)
    write_rows('all-forecast-contexts.jsonl.gz', inventory)
    write_rows('held-contexts.jsonl.gz', held)
    write_rows('original-evidence.jsonl.gz', originals)
    write_rows('expected-native-records.jsonl.gz', [])
    summary = {'sourceWebsiteCommit': WEBSITE_COMMIT, 'currentDatabaseSha256': BASELINE_SHA,
               'totalForecastContexts': len(forecasts), 'runnableContexts': len(ready),
               'heldContexts': len(held), 'forecastTiers': dict(tiers),
               'queueTierOrder': ORDER, 'runnableTiers': dict(collections.Counter(r['predictionTier'] for r in ready)),
               'displayedForecastCells': sum(cell_counts[i] for i, _ in forecasts),
               'policy': 'Preserve physical contexts and all original evidence; complete fresh required seeds plus independent exact replay; no training, physics, ranking, UI or website changes.',
               'heldPolicy': 'Native failures stay unfinished. Neither user declarations nor cross-engine projections count as native verification. No blind retry of the held contexts.'}
    (CAMPAIGN / 'inventory-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
