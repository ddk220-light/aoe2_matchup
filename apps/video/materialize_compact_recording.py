"""Restore disposable overlay inputs from a compact archive without game access.

The restored workspace is for offline renderers, not recorder resume validation.
It deliberately does not invent a scenario or a pre-trim recording.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from compact_recording_archive import digest, read


def materialize(index, job_id, workspace):
    index = index.resolve()
    data = read(index)
    row = next(r for r in data['matchups'] if r['jobId'] == job_id)
    if Path(job_id).name != job_id or '/' in job_id or '\\' in job_id:
        raise ValueError('Invalid job ID')
    workspace = workspace.resolve()
    if workspace.is_relative_to(index.parent) or index.parent.is_relative_to(workspace):
        raise ValueError('Rendering workspace must be separate from archive')
    job = workspace / job_id
    if job.exists():
        raise ValueError('Use an empty workspace; existing files are not overwritten')
    run = job / 'live/run_001'
    recording = deepcopy(row['recording'])
    inputs = []
    for logical, short in [('battleVideo', 'battle.mp4'), ('frames', 'frames.bin')]:
        entry = row['files'][short]
        source = (index.parent / entry['path']).resolve()
        if not source.is_relative_to(index.parent):
            raise ValueError('Input escapes archive')
        if source.stat().st_size != entry['bytes'] or digest(source) != entry['sha256']:
            raise ValueError('Archive input failed verification')
        inputs.append((source, run / short))
        recording['files'][logical]['path'] = short
    run.mkdir(parents=True)
    for source, target in inputs:
        shutil.copyfile(source, target)
    for target, value in [(job / 'plan.json', row['plan']),
                          (run / 'recording.json', recording),
                          (run / 'manifest.json', row['capture']),
                          (run / 'compact-source.json', dict(index=str(index), jobId=job_id))]:
        target.write_text(json.dumps(value, indent=2), encoding='utf-8')
    alignment = recording.get('verifiedAlignment')
    if alignment:
        if alignment['videoSha256'] != recording['files']['battleVideo']['sha256']:
            raise ValueError('Saved alignment belongs to another video')
        folder = run / 'unit-hp-overlay'
        folder.mkdir(exist_ok=True)
        (folder / 'alignment.json').write_text(json.dumps(alignment, indent=2))
    return run


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--job', required=True)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    print(materialize(a.index, a.job, a.workspace))
