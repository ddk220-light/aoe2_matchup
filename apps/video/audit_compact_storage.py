"""Inventory available battle/frames pairs without deleting or altering media."""
import json
from pathlib import Path
from compact_recording_archive import read

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
OUT = ROOT / 'data/local/compact-storage'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    associations = {}
    for compilation in (LAB / 'compilations').iterdir():
        if not compilation.is_dir():
            continue
        for path in [compilation / 'manifest.json', *compilation.glob('final*/manifest.json')]:
            if not path.exists():
                continue
            try:
                data = read(path)
                group = compilation.name + '--' + (path.parent.name if path.parent != compilation else 'final')
                for row in data.get('chapters', []) + data.get('results', []):
                    job = row.get('jobId')
                    if job:
                        associations.setdefault(job, set()).add(group)
            except (ValueError, TypeError):
                continue
    verified = {r['jobId'] for r in read(ROOT / 'data/local/champi-standard-comparison/capture/status.json')['results'] if r['status'] == 'verified'}
    rows, exceptions = [], []
    for job in (LAB / 'runs').iterdir():
        if job.name.startswith('champi_standard_') and job.name not in verified:
            continue
        if any(s in job.name for s in ('elite_obuch', 'blackwood_five', 'comp4')):
            continue  # Active production or explicitly abandoned experiment.
        source = job / 'live/run_001'
        if not (source / 'recording.json').exists():
            continue
        try:
            bundle = read(source / 'recording.json')
            files = bundle['files']
            missing = [k for k in ('battleVideo', 'frames', 'battleHp', 'metadata')
                       if k not in files or not (source / files[k]['path']).is_file()]
            groups = sorted(associations.get(job.name, []))
            if job.name.startswith('champi_standard_'):
                groups = ['champi-standard-' + job.name.split('_')[2]]
            if missing or len(groups) != 1:
                exceptions.append(dict(jobId=job.name, missing=missing, groups=groups,
                                       source=str(source), reason='Missing inputs or ambiguous campaign; preserve originals'))
                continue
            rows.append(dict(jobId=job.name, source=str(source), group=groups[0],
                             destination=str(Path('D:/AoE2 Renders') / groups[0]),
                             bytes=sum((source / files[k]['path']).stat().st_size for k in ('battleVideo', 'frames'))))
        except (OSError, KeyError, ValueError) as e:
            exceptions.append(dict(jobId=job.name, reason=str(e)))
    payload = dict(state='INVENTORIED', eligible=rows, exceptions=exceptions,
                   eligibleBytes=sum(r['bytes'] for r in rows), sourceDeletionPerformed=False)
    (OUT / 'capture-inventory.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(dict(eligible=len(rows), exceptions=len(exceptions), GiB=payload['eligibleBytes']/2**30)))


if __name__ == '__main__':
    main()
