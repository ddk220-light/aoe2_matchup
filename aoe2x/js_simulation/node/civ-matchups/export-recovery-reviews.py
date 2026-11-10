"""Export complete, audited research reviews to a NEW directory; never imports a DB."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--audit', type=Path, action='append', required=True)
parser.add_argument('--collision', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[4]
source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
cache = {}
verified_files = {}


def read_committed(path):
    path = path.resolve()
    if path in cache:
        return cache[path]
    repo = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=path.parent, text=True).strip())
    commit = source_commit if repo == root else subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    blob = subprocess.check_output(['git', 'show', f'{commit}:{path.relative_to(repo)}'], cwd=repo)
    assert blob == path.read_bytes(), f'Export requires a committed, unchanged source: {path}'
    verified_files[str(path)] = {'commit': commit, 'sha256': hashlib.sha256(blob).hexdigest()}
    cache[path] = blob
    return blob


cases = {}
for audit_path in args.audit:
    audit = json.loads(read_committed(audit_path))
    assert audit['simulationExecutionsForAudit'] == 0
    for case in audit['results']:
        if case['complete']:
            if case['jobId'] in cases:
                assert cases[case['jobId']]['seeds'] == case['seeds'], 'Conflicting completed reviews'
            cases[case['jobId']] = case

collision = json.loads(read_committed(args.collision / 'review.json'))
collision_input = json.loads(read_committed(args.collision / 'input.json'))
raw = read_committed(args.collision / 'runs.jsonl').splitlines(keepends=True)
assert len(raw) == 1 and collision['status'] == 'candidate_protocol_complete'
row = json.loads(raw[0])
cases[row['matchupId']] = {
    'jobId': row['matchupId'], 'label': 'Chinese Heavy Scorpion / Poles Heavy Mounted Crossbowman',
    'category': 'collision_exception', 'complete': True, 'displayedCells': collision_input['job']['displayedCells'],
    'evidenceLevel': collision['samplingDecision']['evidenceLevel'], 'outcome': collision['outcome'],
    'originalOutcomes': collision_input['originalOutcomes'],
    'changed': any(o != collision['outcome'] for o in collision_input['originalOutcomes']),
    'mixedWinners': False, 'physicsVersions': [row['physicsVersion']], 'review': str(args.collision / 'review.json'),
    'seeds': [{'path': str(args.collision / 'runs.jsonl'), 'line': 1,
               'sha256IncludingNewline': hashlib.sha256(raw[0]).hexdigest(), 'seed': row['seed'],
               'winnerOwner': row['winnerOwner'], 'hp': [row['unitRemainingHp'], row['opponentRemainingHp']],
               'physicsVersion': row['physicsVersion']}],
}

run_rows = []
for case in cases.values():
    seen = set()
    for ref in case['seeds']:
        assert ref['seed'] not in seen, 'Repeated completed seed'
        seen.add(ref['seed'])
        line = read_committed(Path(ref['path'])).splitlines(keepends=True)[ref['line'] - 1]
        assert hashlib.sha256(line).hexdigest() == ref['sha256IncludingNewline']
        record = json.loads(line)
        assert record['seed'] == ref['seed'] and record['winnerOwner'] == ref['winnerOwner']
        run_rows.append({'recoveryContextId': case['jobId'], 'label': case['label'],
                         'sourceReference': ref, 'record': record})
    assert len(seen) in (1, 3, 10)
    assert seen == set(range(len(seen)))

assert not args.output.exists(), 'Never overwrite a correction/research snapshot'
args.output.mkdir(parents=True)


def write_json(name, value):
    (args.output / name).write_text(json.dumps(value, indent=2) + '\n')


write_json('matchup-reviews.json', list(cases.values()))
with (args.output / 'matchups.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['context_id', 'matchup', 'category', 'displayed_cells', 'evidence_level', 'seed_count',
                     'outcome', 'original_outcomes', 'changed', 'mixed_winners', 'engine_versions', 'review'])
    for case in cases.values():
        writer.writerow([case['jobId'], case['label'], case['category'], case['displayedCells'], case['evidenceLevel'],
                         len(case['seeds']), case['outcome'], '|'.join(case['originalOutcomes']), case['changed'],
                         case['mixedWinners'], '|'.join(case['physicsVersions']), case['review']])
with (args.output / 'runs.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['context_id', 'matchup', 'seed', 'physics_version', 'winner_owner', 'owner2_starting_hp',
                     'owner3_starting_hp', 'owner2_hp_left', 'owner3_hp_left', 'owner2_survivors', 'owner3_survivors',
                     'ticks', 'simulation_seconds', 'wall_seconds', 'final_state_hash', 'event_log_hash', 'source_path', 'source_line'])
    for run in run_rows:
        row, ref = run['record'], run['sourceReference']
        writer.writerow([run['recoveryContextId'], run['label'], *[row[k] for k in ['seed', 'physicsVersion', 'winnerOwner',
                         'unitStartingHp', 'opponentStartingHp', 'unitRemainingHp', 'opponentRemainingHp',
                         'unitSurvivors', 'opponentSurvivors', 'ticks', 'simulationSeconds', 'wallSeconds', 'finalStateHash', 'eventLogHash']],
                         ref['path'], ref['line']])
with (args.output / 'runs.jsonl.gz').open('wb') as f:
    with gzip.GzipFile(fileobj=f, mode='wb', mtime=0) as compressed:
        for row in run_rows:
            compressed.write((json.dumps(row, separators=(',', ':')) + '\n').encode())
write_json('verification.json', {
    'sourceCommit': source_commit, 'reviewedOnly': True, 'contexts': len(cases), 'displayedCells': sum(c['displayedCells'] for c in cases.values()),
    'singleSeedConfirmations': sum(c['evidenceLevel'] == 'single_seed_confirmation' for c in cases.values()),
    'multiSeedValidations': sum(c['evidenceLevel'] == 'multi_seed_validation' for c in cases.values()),
    'changed': sum(c['changed'] for c in cases.values()), 'retained': sum(not c['changed'] for c in cases.values()),
    'mixedWinners': sum(c['mixedWinners'] for c in cases.values()),
    'mixedEngineVersionSets': sum(len(c['physicsVersions']) > 1 for c in cases.values()),
    'individualSeedRecords': len(run_rows), 'sourceFilesVerifiedAgainstLocalGitObjects': verified_files,
    'outputSha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir()},
    'simulationsExecutedForExport': 0, 'productionEligible': False, 'publication': 'local only',
    'limitations': ['These are separately versioned recovery results; frozen campaign records and production are unchanged.',
                    'Mixed-engine seed sets retain original per-run provenance and must not be called homogeneous frozen-engine validation.',
                    'Agreement-dependent stopping cannot estimate unbiased global forecast accuracy.',
                    'Per-run terminal measurements and evidence hashes are included. This is not a frame-by-frame event recording.'],
})
print(json.dumps({'output': str(args.output), 'contexts': len(cases), 'individualSeedRecords': len(run_rows), 'sourceCommit': source_commit}))
