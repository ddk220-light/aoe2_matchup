"""Record the explicitly requested seed-policy change after a safe interruption.

Never changes the base manifest, frozen inventory, existing reviews or physics.
"""
import datetime
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
OVERRIDES = [f'aoe2x/js_simulation/node/civ-matchups/{name}' for name in (
    'forecast-validation-lib.mjs', 'run-forecast-validation.mjs', 'export-forecast-reviews.mjs')]
ADDITIONAL = [
    'aoe2x/js_simulation/node/civ-matchups/forecast-screening-policy.mjs',
    'aoe2x/js_simulation/tests/forecast-screening-policy.test.mjs',
    'tools/record_forecast_sampling_amendment.py',
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    target = CAMPAIGN / 'sampling-policy-v2.json'
    assert not target.exists(), 'Never overwrite a recorded policy amendment'
    state = json.loads((CAMPAIGN / 'state.json').read_text())
    assert state['status'] == 'interrupted' and not state.get('active')
    assert not (CAMPAIGN / '.runner.lock').exists(), 'Drain the live runner first'
    with (CAMPAIGN / '.supervisor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_bytes = (CAMPAIGN / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_bytes)
        frozen = {r['path']: r['sha256'] for r in manifest['inputFiles']}
        for record in manifest['runtimeFiles'] + manifest['inputFiles']:
            if record['path'] not in OVERRIDES:
                assert sha((ROOT / record['path']).read_bytes()) == record['sha256'], record['path']
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        journal = (CAMPAIGN / 'runs.jsonl').read_bytes()
        assert subprocess.check_output(['git', 'show', f'{source}:{(CAMPAIGN / "runs.jsonl").relative_to(ROOT)}'], cwd=ROOT) == journal
        rows = [json.loads(line) for line in journal.splitlines() if line]
        reviews = []
        reviewed_ids = set()
        for path in sorted((CAMPAIGN / 'pair-reviews').glob('*.json')):
            relative = str(path.relative_to(ROOT))
            data = path.read_bytes()
            assert subprocess.check_output(['git', 'show', f'{source}:{relative}'], cwd=ROOT) == data
            reviews.append({'path': relative, 'sha256': sha(data)})
            reviewed_ids.add(json.loads(data)['jobId'])
        assert len(reviews) == state['reviewedJobs']
        prior = CAMPAIGN / 'policy-transitions/decisive-agreement-v2'
        prior.mkdir(parents=True, exist_ok=False)
        archive = prior / 'runs-before-amendment.jsonl.gz'
        archive.write_bytes(gzip.compress(journal, mtime=0))
        (prior / 'attempts-before-amendment.jsonl.gz').write_bytes(gzip.compress((CAMPAIGN / 'attempts.jsonl').read_bytes(), mtime=0))
        (prior / 'state-before-amendment.json').write_bytes((CAMPAIGN / 'state.json').read_bytes())
        overrides = []
        for path in OVERRIDES:
            assert sha(subprocess.check_output(['git', 'show', f'{source}:{path}'], cwd=ROOT)) == frozen[path]
            overrides.append({'path': path, 'originalSha256': frozen[path], 'sha256': sha((ROOT / path).read_bytes())})
        policy = {
            'version': 'decisive-agreement-screen-v2',
            'baseCampaignHash': manifest['campaignHash'],
            'baseManifestSha256': sha(manifest_bytes),
            'recordedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'authorization': {
                'sourceRole': 'user',
                'sourceMessage': 'Use this as the approach to go forward. Update the scheduled tasks and the runner so that this is the logic that is used in this process.',
                'requestedApproach': 'One decisive run agreeing with the guess can stop; close or disagreeing results need more runs.',
                'durationApproval': 'Existing Yes start approval remains valid; this amendment reduces seed execution within the same research inventory.',
            },
            'minimumWinnerHpFraction': 0.25,
            'independentExactReplayRequired': True,
            'initialSeedsOnEscalation': [0, 1, 2],
            'extraSeedsOnMixedWinners': [3, 4, 5, 6, 7, 8, 9],
            'legacyInProgressJobs': sorted({r['matchupId'] for r in rows} - reviewed_ids),
            'transition': {
                'sourceCommit': source,
                'journalFile': str(archive.relative_to(ROOT)),
                'journalSha256': sha(archive.read_bytes()),
                'journalRecords': len(rows),
                'reviewedJobs': len(reviews),
                'pairReviewHashes': reviews,
                'blockedJobs': state['blockedJobs'],
            },
            'sourceOverrides': overrides,
            'additionalSourceFiles': [{'path': p, 'sha256': sha((ROOT / p).read_bytes())} for p in ADDITIONAL],
            'limitations': 'A single seed plus replay confirms that seed only. Agreement-dependent stopping is not an unbiased accuracy estimate. Originals, held contexts, failures and prior evidence stay unchanged; no website release.',
        }
        # Use the runtime canonical JSON implementation for the amendment hash.
        result = subprocess.run(['node', '--input-type=module', '-e',
            "import {hashCanonicalJson} from './aoe2x/js_simulation/src/canonical-json.js'; import {readFileSync} from 'node:fs'; process.stdout.write(hashCanonicalJson(JSON.parse(readFileSync(0,'utf8'))));"],
            cwd=ROOT, input=json.dumps(policy), text=True, capture_output=True, check=True)
        policy['amendmentHash'] = result.stdout
        with target.open('x') as output:
            output.write(json.dumps(policy, indent=2) + '\n')
        print(json.dumps({'policyHash': policy['amendmentHash'], 'sourceCommit': source,
                          'preservedReviews': len(reviews), 'legacyInProgressJobs': policy['legacyInProgressJobs']}))


if __name__ == '__main__':
    main()
