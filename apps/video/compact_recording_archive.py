"""Copy verified captures into a compact archive; never delete source evidence.

Each matchup retains battle.mp4 + frames.bin. A single run.json preserves
non-derivable clock alignment, provenance and checksums for the whole campaign.
Legacy captures without a complete battle/frames pair fail closed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare(source):
    source = source.resolve()
    bundle = read(source / 'recording.json')
    if bundle.get('overlayApplied') is not False:
        raise ValueError('Expected an unoverlaid recording')
    job = bundle['jobId']
    if Path(job).name != job or '/' in job or '\\' in job or job in ('.', '..'):
        raise ValueError('Unsafe job identifier')
    files = {}
    for key, name in [('battleVideo', 'battle.mp4'), ('frames', 'frames.bin')]:
        entry = bundle['files'][key]
        path = (source / entry['path']).resolve()
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError(f'Missing or escaped input: {path}')
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError(f'Input checksum mismatch: {path}')
        files[name] = dict(source=str(path), bytes=entry['bytes'], sha256=entry['sha256'])
    hp = read(source / bundle['files']['battleHp']['path'])
    if hp.get('clock') != 'video' or hp.get('video_game_start_s') is None:
        raise ValueError('Missing battle-video alignment')
    plan = read(source.parents[1] / 'plan.json')
    stem = re.sub(r'[^\w-]+', '_', '_vs_'.join(
        f"{plan[key]['civ']}_{plan[key]['label']}" for key in ('side2', 'side3'))).strip('_')
    for name, entry in files.items():
        entry['path'] = stem + ('.mp4' if name == 'battle.mp4' else '.frames.bin')
    return dict(jobId=job, name=stem, files=files, recording=bundle,
                timing={k: v for k, v in hp.items() if k != 'rows'},
                capture=read(source / 'manifest.json'),
                plan=plan,
                streamMetadata=read(source / bundle['files']['metadata']['path']))


def export(sources, destination, title, final_video=None):
    destination = destination.resolve()
    # Never mix a compact archive with the original working directory.
    for source in sources:
        source = source.resolve()
        if destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ValueError('Archive and capture directories must be separate')
    rows = [prepare(source) for source in sources]
    if len({r['jobId'] for r in rows}) != len(rows):
        raise ValueError('Duplicate matchup IDs')
    if len({r['name'].casefold() for r in rows}) != len(rows):
        raise ValueError('Duplicate matchup names: separate different run variants')
    previous = read(destination / 'run.json') if (destination / 'run.json').exists() else None
    if previous and (previous['title'] != title or [r['jobId'] for r in previous['matchups']] != [r['jobId'] for r in rows]):
        raise ValueError('Existing archive has a different campaign; do not overwrite')
    assets = [(f, destination / f['path'])
              for row in rows for name, f in row['files'].items()]
    final = None
    if final_video:
        final = dict(source=str(final_video.resolve()), bytes=final_video.stat().st_size,
                     sha256=digest(final_video))
        final['path'] = re.sub(r'[^\w-]+', '_', title).strip('_') + '_Full_Video.mp4'
        assets.append((final, destination / final['path']))
    parent = destination
    while not parent.exists():
        parent = parent.parent
    needed = sum(f['bytes'] for f, target in assets if not target.exists())
    if shutil.disk_usage(parent).free < needed + 2 * 1024**3:
        raise ValueError('Insufficient free space for the complete copy plus 2 GiB reserve')
    for f, target in assets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            partial = target.with_suffix(target.suffix + '.partial')
            shutil.copyfile(f['source'], partial)
            if partial.stat().st_size != f['bytes'] or digest(partial) != f['sha256']:
                raise ValueError(f'Copy verification failed: {partial}; source retained')
            partial.replace(target)
        if target.stat().st_size != f['bytes'] or digest(target) != f['sha256']:
            raise ValueError(f'Archive conflict: {target}; source retained')
    index = dict(schemaVersion=1, kind='aoe2lab.compact-archive', title=title,
                 matchups=rows, finalVideo=final, sourceDeletionAuthorizedByThisTool=False)
    temporary = destination / 'run.partial.json'
    temporary.write_text(json.dumps(index, indent=2), encoding='utf-8')
    temporary.replace(destination / 'run.json')
    return index


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, action='append', required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--final-video', type=Path)
    a = p.parse_args()
    result = export(a.source, a.destination, a.title, a.final_video)
    print(json.dumps(dict(matchups=len(result['matchups']), destination=str(a.destination), verified=True)))
