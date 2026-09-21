"""Retire one proven Obuch intermediate and finish the approved archive moves."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data/local/storage-consolidation-20260916'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    plan = read(WORK / 'plan.json')
    folder = Path(plan['destinationRoot']) / 'elite-obuch/compilation/final-cost-v2'
    final = folder / 'elite-obuch-complete-corrected-costs.mp4'
    intermediate = folder / 'elite-obuch-battles-only.mp4'
    full_manifest = read(folder / 'manifest.json')
    battles_manifest = read(folder / 'battles-manifest.json')
    assert full_manifest['fullDecode'] == battles_manifest['fullDecode'] == 'passed'
    assert full_manifest['matchups'] == battles_manifest['matchups'] == 73
    # The final master includes the same battles, shifted by its intro duration.
    fields = ('jobId', 'durationSeconds', 'result', 'winnerHp', 'winnerSurvivors')
    assert [[r[k] for k in fields] for r in full_manifest['results']] == [
        [r[k] for k in fields] for r in battles_manifest['results']]
    assert final.stat().st_size == int(full_manifest['media']['format']['size'])
    assert intermediate.stat().st_size == int(battles_manifest['media']['format']['size'])
    inventory = read(ROOT / 'data/local/media-reuse-audit/inventory.json')
    for row in full_manifest['results']:
        candidates = inventory['jobs'][row['jobId']]
        assert any(c['video'] and c['frames'] and
                   Path(c['paths']['battleVideo']).is_file() and
                   Path(c['paths']['frames']).is_file()
                   for c in candidates if c.get('battleVideo'))
    with final.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    prune = dict(path=str(intermediate), bytes=intermediate.stat().st_size,
                 reason='Redundant Obuch battles-only compilation; identical 73 battles retained in final master and raw/frame pairs',
                 guards=[dict(path=str(final), bytes=final.stat().st_size, sha256=digest)])
    mappings = {r['source']: r for r in plan['moves']}
    mappings.update({r['source']: r for r in read(WORK / 'conflict-retry-plan.json')['moves']})
    remaining = []
    for issue in read(WORK / 'verification.json')['workerExceptions']:
        source = issue.get('source')
        if source not in mappings:
            raise ValueError(f'Unexpected exception: {issue}')
        path = Path(source)
        if path.is_junction():
            continue
        assert path.is_dir() and path.resolve().is_relative_to(ROOT)
        size = 0
        for base, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not (Path(base)/d).is_junction() and not (Path(base)/d).is_symlink()]
            size += sum((Path(base)/f).stat().st_size for f in files if not (Path(base)/f).is_symlink())
        remaining.append({**mappings[source], 'bytes': size})
    remaining = list({r['source']: r for r in remaining}.values())
    output = {**plan, 'prunes': [prune], 'moves': remaining}
    (WORK / 'final-retry-plan.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(dict(pruneGiB=prune['bytes']/1024**3, remainingGiB=sum(r['bytes'] for r in remaining)/1024**3,
                          packages=len(remaining), retainedObuchRawPairs=73)))


if __name__ == '__main__':
    main()
