"""Reclaim local sources only after a complete regional set is safely archived.

Authorized September 23 after the initial copy-only request. The independent
copy worker continues publishing immutable complete archives. This worker reads
those receipts, rechecks archive hashes, and removes only named local media and
rebuildable HP JSON. Small provenance files and an archive pointer remain local.
No external file is modified; active/incomplete civilization sets are excluded.
"""
import msvcrt
import os
from pathlib import Path
import shutil
import time
import traceback

from copy_regional_capture_archives import (
    DEST, IDENTITY, ROOT, WORK, check_disk, check_pause, now, ready, save,
    configured_queues, expected_total,
)
from compact_recording_archive import digest, read

RUNS = (ROOT / 'aoe2x/js_simulation/calibration/lab/runs').resolve()
STATUS = WORK / 'move-status.json'


def reclaim(campaign, key, receipt, state):
    # The whole civilization must have finished before any local deletion.
    sources = ready(campaign)
    if sources is None or len(sources) != 77:
        raise RuntimeError(f'Archive campaign is not complete: {key}')
    destination = DEST / key
    if Path(receipt['destination']) != destination or destination.resolve() != destination:
        raise RuntimeError('Unexpected or redirected archive destination')
    index_path = destination / 'run.json'
    check_disk()
    if digest(index_path) != receipt['indexSha256']:
        raise RuntimeError('Archive index changed; local sources preserved')
    index = read(index_path)
    expected = {p.parents[1].name: p.resolve() for p in sources}
    rows = index['matchups']
    if len(rows) != 77 or {r['jobId'] for r in rows} != set(expected):
        raise RuntimeError('Archive/capture set mismatch')
    progress = state['campaigns'].setdefault(key, dict(state='MOVING', jobs={},
        index=str(index_path), deletedBytes=0, startedAt=now()))
    for row in rows:
        job = row['jobId']
        if progress['jobs'].get(job, {}).get('state') == 'COMPLETE':
            continue
        check_pause()
        check_disk()
        source = expected[job]
        if (not job.startswith(campaign['jobPrefix'])
                or source != (RUNS / job / 'live/run_001')
                or not source.is_relative_to(RUNS)):
            raise RuntimeError('Source escaped the approved capture job')
        # Recheck the durable pair immediately before retiring its local inputs.
        for info in row['files'].values():
            target = (destination / info['path']).resolve()
            if target.parent != destination or not target.is_file():
                raise RuntimeError('Archive file is missing or outside its folder')
            if target.stat().st_size != info['bytes'] or digest(target) != info['sha256']:
                raise RuntimeError('Archive checksum mismatch; local sources preserved')
        disposable = []
        bundle = row['recording']
        for logical in ['video', 'battleVideo', 'frames', 'hp', 'battleHp']:
            entry = bundle['files'].get(logical)
            if not entry:
                continue
            path = (source / entry['path']).resolve()
            allowed = (path.suffix.lower() in ('.mov', '.mp4', '.bin')
                       if logical in ('video', 'battleVideo', 'frames')
                       else path.name.endswith('.hp.json'))
            if not path.is_relative_to(source) or not allowed:
                raise RuntimeError('Unsafe local disposable path')
            if path.exists() and (path.stat().st_size != entry['bytes']
                                   or digest(path) != entry['sha256']):
                raise RuntimeError(f'Local source changed; preserved: {path}')
            disposable.append((path, entry))
        pointer = dict(jobId=job, index=str(index_path),
                       adapter='apps/video/materialize_compact_recording.py')
        pointer_path = source / 'archived.json'
        if pointer_path.exists() and read(pointer_path) != pointer:
            raise RuntimeError('Existing local archive pointer differs')
        save(pointer_path, pointer)
        prior = progress['jobs'].get(job, {})
        deleted = dict(prior.get('deletedFiles', {}))
        progress['jobs'][job] = dict(state='VERIFIED_FOR_LOCAL_CLEANUP',
            indexSha256=receipt['indexSha256'], archiveVerifiedAt=now(), deletedFiles=deleted)
        state.update(state='MOVING', current=key, updatedAt=now())
        save(STATUS, state)
        for path, entry in disposable:
            check_disk()
            check_pause()
            if not path.exists():
                continue
            # Each resolved absolute path was verified above. No recursive delete.
            if path.resolve() != path or not path.is_relative_to(source):
                raise RuntimeError('Local path changed after verification')
            if path.stat().st_size != entry['bytes']:
                raise RuntimeError('Local source size changed after verification')
            path.unlink()
            deleted[str(path)] = entry['bytes']
            progress['jobs'][job]['deletedFiles'] = deleted
            save(STATUS, state)
        progress['jobs'][job].update(state='COMPLETE', completedAt=now())
        progress['deletedBytes'] = sum(sum(j.get('deletedFiles', {}).values())
                                       for j in progress['jobs'].values())
        progress['moved'] = sum(j['state'] == 'COMPLETE' for j in progress['jobs'].values())
        state.update(updatedAt=now(), deletedBytes=sum(c['deletedBytes']
                     for c in state['campaigns'].values()))
        save(STATUS, state)
        if progress['moved'] % 10 == 0:
            print(f"{key}: {progress['moved']}/77 moved; {state['deletedBytes']/2**30:.1f} GiB reclaimed", flush=True)
    progress.update(state='COMPLETE', completedAt=now(), localSourcesRetained=False)
    save(STATUS, state)
    print(f'{key}: complete archive retained; local media reclaimed', flush=True)


def run(state):
    while True:
        check_disk()
        check_pause()
        copied = read(WORK / 'status.json')
        if copied['drive'] != IDENTITY:
            raise RuntimeError('Copy receipt belongs to another disk')
        for queue_name, prefix in configured_queues():
            for campaign in read(ROOT / 'data/local' / queue_name / 'queue.json')['campaigns']:
                key = prefix + '-' + campaign['key']
                if state['campaigns'].get(key, {}).get('state') == 'COMPLETE':
                    continue
                receipt = copied['campaigns'].get(key)
                if receipt and receipt.get('state') == 'COMPLETE' and receipt.get('verified') == 77:
                    reclaim(campaign, key, receipt, state)
        moved = sum(c.get('moved', 0) for c in state['campaigns'].values())
        total = expected_total()
        state.update(state='COMPLETE' if moved == total else 'WAITING_FOR_VERIFIED_ARCHIVE',
            moved=moved, total=total, updatedAt=now(), current=None,
            localFreeBytes=shutil.disk_usage('C:/').free,
            externalFreeBytes=shutil.disk_usage(DEST).free)
        save(STATUS, state)
        if moved == total:
            return
        time.sleep(30)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'move.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        state = read(STATUS) if STATUS.exists() else dict(schemaVersion=1,
            drive=IDENTITY, startedAt=now(), campaigns={}, deletedBytes=0,
            sourceDeletionAuthorized=True,
            authorization='User requested moving each completed regional unit set and freeing the PC on September 23, 2026; only verified archived media and derived HP JSON are retired.')
        if state['drive'] != IDENTITY:
            raise RuntimeError('Move receipt belongs to another disk')
        state['pid'] = os.getpid()
        try:
            run(state)
        except Exception:
            state.update(state='NEEDS_ATTENTION', error=traceback.format_exc(), updatedAt=now())
            save(STATUS, state)
            raise


if __name__ == '__main__':
    main()
