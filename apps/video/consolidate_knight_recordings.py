"""Consolidate the selected knight footage; preserve missing-result evidence.

Preparation reads existing indexes and verified local captures. Copying writes
only a new canonical directory, verifies every media checksum, and records
receipts. Source deletion is deliberately a separate, explicit operation.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time

from compact_recording_archive import digest, read

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/knight-storage-consolidation'
DEST = Path('E:/AoE2 Renders/knight-line-canonical')
RUNS = ROOT / 'aoe2x/js_simulation/calibration/lab/runs'
ARCHIVE_ROOTS = (Path('D:/AoE2 Renders'), ROOT / 'data/local/knight-reused-indexes')
VOLUME_SERIAL = int('F274E9A2', 16)
RESERVE = 4 * 2**30


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def guard():
    import win32api
    label, serial, _, _, _ = win32api.GetVolumeInformation('E:/')
    if label != 'Archives' or (serial & 0xFFFFFFFF) != VOLUME_SERIAL:
        raise RuntimeError('Original archive drive identity changed; preserve sources')
    if shutil.disk_usage('E:/').free < RESERVE:
        raise RuntimeError('External reserve reached; preserve sources')


def local_row(job):
    live = RUNS / job / 'live/run_001'
    bundle = read(live / 'recording.json')
    if bundle.get('overlayApplied') is not False or bundle['jobId'] != job:
        raise ValueError('Expected a clean matching capture')
    plan = read(live.parents[1] / 'plan.json')
    hp = read(live / bundle['files']['battleHp']['path'])
    if hp.get('clock') != 'video' or hp.get('video_game_start_s') is None:
        raise ValueError('Missing video/frame alignment')
    stem = re.sub(r'[^\w-]+', '_', '_vs_'.join(
        f"{plan[k]['civ']}_{plan[k]['label']}" for k in ('side2', 'side3'))).strip('_')
    files = {}
    for key, name in [('battleVideo', 'battle.mp4'), ('frames', 'frames.bin')]:
        entry = bundle['files'][key]
        source = (live / entry['path']).resolve()
        if not source.is_relative_to(live.resolve()) or not source.is_file() or source.stat().st_size != entry['bytes']:
            raise ValueError(f'Missing local source: {source}')
        files[name] = dict(entry, source=str(source), path=stem + ('.mp4' if key == 'battleVideo' else '.frames.bin'))
    return dict(jobId=job, name=stem, files=files, recording=bundle,
                timing={k: v for k, v in hp.items() if k != 'rows'},
                capture=read(live / 'manifest.json'), plan=plan,
                streamMetadata=read(live / bundle['files']['metadata']['path']))


def prepare():
    guard()
    if (WORK / 'plan.json').exists() or DEST.exists():
        raise FileExistsError('Consolidation exists; resume the frozen plan')
    specs = read(ROOT / 'apps/video/ranking_sources.json')['knight']
    # Verified repeats are usable when the original result has no available raw
    # pair. Select by availability, never by winner or HP.
    state = read(ROOT / 'data/local/knight-v2-recapture/cavalier-poles/capture/status.json')
    local = {}
    for result in state['results']:
        if result['status'] == 'verified':
            row = local_row(result['jobId'])
            local[row['plan']['side3']['slug']] = row
    variants, sources, assets, missing = [], {}, [], []
    for spec in specs:
        selected = {}
        for folder in spec['folders'] + spec.get('optionalOverrides', []):
            path = next((r / folder / 'run.json' for r in ARCHIVE_ROOTS if (r / folder / 'run.json').is_file()), None)
            if path is None:
                raise FileNotFoundError(folder)
            index = read(path)
            sources[str(path)] = dict(sha256=digest(path), index=index)
            for entry in index['matchups']:
                row = deepcopy(entry)
                row['provenanceIndex'] = str(path.resolve())
                if row.get('files'):
                    for f in row['files'].values():
                        source = (path.parent / f['path']).resolve()
                        if not source.is_relative_to(path.parent.resolve()) or not source.is_file() or source.stat().st_size != f['bytes']:
                            raise ValueError(f'Missing indexed media: {source}')
                        f['source'] = str(source)
                selected[row['plan']['side3']['slug']] = row
        rows = []
        for slug, row in selected.items():
            if not row.get('files') and spec['key'] == 'cavalier-poles' and slug in local:
                original = row
                row = deepcopy(local[slug])
                row['replacedResult'] = original
                row['selectionReason'] = 'Original raw pair unavailable; retain the existing verified repeat, without selecting by outcome'
            row['mediaAvailable'] = bool(row.get('files'))
            if row['mediaAvailable']:
                row['metadataOnly'] = False
                for name in ('battle.mp4', 'frames.bin'):
                    f = row['files'][name]
                    target = DEST / spec['key'] / f['path']
                    if target.parent != DEST / spec['key']:
                        raise ValueError('Unsafe archive filename')
                    assets.append(dict(source=f['source'], destination=str(target),
                                       bytes=f['bytes'], sha256=f['sha256'], jobId=row['jobId'], variant=spec['key']))
            else:
                missing.append(dict(variant=spec['key'], jobId=row['jobId'], opponent=slug,
                                    expectedMedia=row.get('expectedMedia', {})))
            rows.append(row)
        if len(rows) != (73 if spec['key'] == 'paladin-persians' else 74):
            raise ValueError('Incomplete result roster')
        variants.append(dict(key=spec['key'], label=spec['label'], matchups=rows))
    needed = sum(a['bytes'] for a in assets)
    if shutil.disk_usage('E:/').free < needed + RESERVE:
        raise RuntimeError('Insufficient room for all known sources and reserve')
    if len({a['destination'].casefold() for a in assets}) != len(assets):
        raise ValueError('Duplicate destination names')
    plan = dict(schemaVersion=1, createdAt=now(), destination=str(DEST),
                disk=dict(label='Archives', volumeSerial=VOLUME_SERIAL, physicalSerial='WXB1A11Y1348'),
                variants=variants, assets=assets, missing=missing, sourceIndexes=sources,
                bytes=needed, sourceDeletionAuthorizedByThisTool=False)
    save(WORK / 'plan.json', plan)
    print(json.dumps(dict(variants=len(variants), pairedRecordings=len(assets)//2,
                          missingPairs=len(missing), GiB=needed/2**30)))


def copy_all():
    import msvcrt
    guard()
    plan = read(WORK / 'plan.json')
    if Path(plan['destination']) != DEST:
        raise ValueError('Destination changed')
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'copy.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        receipts_path = WORK / 'copy-receipts.jsonl'
        receipts = {}
        if receipts_path.exists():
            for line in receipts_path.read_text().splitlines():
                item = json.loads(line); receipts[item['destination']] = item
        started = time.monotonic()
        copied = sum(a['bytes'] for a in plan['assets'] if a['destination'] in receipts)
        initial = copied
        for number, asset in enumerate(plan['assets'], 1):
            guard()
            target, source = Path(asset['destination']), Path(asset['source'])
            if not target.resolve().is_relative_to(DEST.resolve()):
                raise ValueError('Escaped archive target')
            if target.exists():
                if target.stat().st_size != asset['bytes'] or digest(target) != asset['sha256']:
                    raise ValueError(f'Existing file conflict: {target}; source retained')
            else:
                if not source.is_file() or source.stat().st_size != asset['bytes']:
                    raise ValueError(f'Source changed: {source}')
                if shutil.disk_usage('E:/').free < asset['bytes'] + RESERVE:
                    raise RuntimeError('Archive reserve would be crossed')
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_suffix(target.suffix + '.partial')
                if partial.exists():
                    raise FileExistsError(f'Interrupted copy retained for inspection: {partial}')
                before = source.stat()
                checksum = hashlib.sha256()
                with source.open('rb') as reader, partial.open('xb') as writer:
                    for block in iter(lambda: reader.read(8 * 1024**2), b''):
                        checksum.update(block); writer.write(block)
                    writer.flush(); os.fsync(writer.fileno())
                if (source.stat().st_mtime_ns != before.st_mtime_ns
                        or checksum.hexdigest() != asset['sha256']
                        or partial.stat().st_size != asset['bytes']
                        or digest(partial) != asset['sha256']):
                    raise ValueError(f'Checksum verification failed: {source}; all sources retained')
                guard()
                partial.rename(target)
            if asset['destination'] not in receipts:
                receipt = dict(asset, verifiedAt=now())
                with receipts_path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(receipt)+'\n'); stream.flush(); os.fsync(stream.fileno())
                receipts[asset['destination']] = receipt
                copied += asset['bytes']
            elapsed = max(time.monotonic()-started, .001)
            save(WORK / 'status.json', dict(state='COPYING_VERIFIED', updatedAt=now(),
                files=number, totalFiles=len(plan['assets']), copiedBytes=copied,
                totalBytes=plan['bytes'], MiBPerSecond=(copied-initial)/elapsed/1024**2,
                currentVariant=asset['variant'], sourceDeletionPerformed=False))
        for variant in plan['variants']:
            save(DEST / variant['key'] / 'run.json', dict(schemaVersion=1,
                kind='aoe2lab.canonical-recording-set', title=variant['label'],
                matchups=variant['matchups'], finalVideo=None,
                allMediaAvailable=all(r['mediaAvailable'] for r in variant['matchups'])))
        save(DEST / 'catalog.json', dict(schemaVersion=1, createdAt=now(),
            variants=[dict(key=v['key'], label=v['label'], results=len(v['matchups']),
                           pairedRecordings=sum(r['mediaAvailable'] for r in v['matchups']),
                           index=v['key']+'/run.json') for v in plan['variants']],
            pairedRecordings=len(plan['assets'])//2, missingPairs=len(plan['missing']),
            complete=not plan['missing']))
        save(DEST / 'missing-recordings.json', plan['missing'])
        save(DEST / 'source-index-history.json', plan['sourceIndexes'])
        save(WORK / 'status.json', dict(state='AVAILABLE_MEDIA_VERIFIED', updatedAt=now(),
            copiedBytes=copied, files=len(plan['assets']), pairedRecordings=len(plan['assets'])//2,
            missingPairs=len(plan['missing']), sourceDeletionPerformed=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'copy'))
    args = parser.parse_args()
    try:
        prepare() if args.action == 'prepare' else copy_all()
    except Exception as exc:
        save(WORK / 'error.json', dict(at=now(), error=str(exc), sourcesPreserved=True))
        raise
