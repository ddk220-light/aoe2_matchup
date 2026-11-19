"""Incrementally copy verified recording bundles; preserve every local source.

The destination must be new, or owned by this worker's durable local receipt.
Existing media is checksum-verified, never overwritten. Only our own run.json
index may be extended, after checking its previous checksum. --follow waits for
the finite capture manifest to complete; it does not create a scheduled task.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path
import shutil
import time
import traceback

from compact_recording_archive import digest, prepare, read
from run_champi_comparison_capture import save

ROOT = Path(__file__).resolve().parents[2]
RUNS = (ROOT / 'aoe2x/js_simulation/calibration/lab/runs').resolve()
RESERVE = 4 * 2**30


def now():
    return datetime.now(timezone.utc).isoformat()


def check_disk(destination, label, serial):
    found_label = ctypes.create_unicode_buffer(261)
    found_serial = wintypes.DWORD()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        destination.anchor, found_label, len(found_label), ctypes.byref(found_serial),
        None, None, None, 0)
    if not ok or found_label.value != label or found_serial.value != int(serial, 16):
        raise RuntimeError('Archive drive disconnected or identity changed; sources preserved')
    if destination.resolve() != destination:
        raise RuntimeError('Archive destination is redirected')


def copy_file(info, target, guard):
    guard()
    if target.exists():
        if target.stat().st_size != info['bytes'] or digest(target) != info['sha256']:
            raise RuntimeError(f'Existing archive conflict: {target}')
        return
    if shutil.disk_usage(target.parent).free < RESERVE + info['bytes']:
        raise RuntimeError('External drive would fall below 4 GiB reserve')
    partial = target.with_suffix(target.suffix + '.partial')
    if not partial.exists():
        with Path(info['source']).open('rb') as source, partial.open('xb') as output:
            shutil.copyfileobj(source, output, 4 * 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
    if partial.stat().st_size != info['bytes'] or digest(partial) != info['sha256']:
        raise RuntimeError(f'Partial copy failed verification; preserved: {partial}')
    guard()
    # Windows rename refuses to replace a target that appeared concurrently.
    partial.rename(target)


def main(args):
    campaign = args.campaign.resolve()
    destination = args.destination.absolute()
    work = campaign / 'copy-to-external'
    work.mkdir(exist_ok=True)
    state_path = work / 'status.json'
    manifest = read(campaign / 'manifest.json')
    expected = [r['id'] for r in manifest['matchups']]
    if len(set(expected)) != len(expected):
        raise ValueError('Duplicate manifest jobs')
    identity = dict(label=args.volume_label, volumeSerial=args.volume_serial.upper(),
                    destination=str(destination), manifestSha256=digest(campaign / 'manifest.json'))

    def guard():
        check_disk(destination, args.volume_label, args.volume_serial)
        if (work / 'PAUSE').exists() or (ROOT / 'data/local/thermal/PAUSED.json').exists():
            raise RuntimeError('Copy paused; local sources preserved')

    with (work / 'copy.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        guard()
        if state_path.exists():
            state = read(state_path)
            if state['identity'] != identity:
                raise RuntimeError('Existing copy receipt belongs to another destination or manifest')
        else:
            if destination.exists():
                raise FileExistsError('Refusing to claim an existing external folder')
            state = dict(identity=identity, startedAt=now(), verified=0, total=len(expected),
                         localSourcesRetained=True, sourceDeletionAuthorized=False,
                         indexSha256=None)
            save(state_path, state)
        destination.mkdir(parents=True, exist_ok=True)

        def persist(phase, **fields):
            state.update(state=phase, pid=os.getpid(), updatedAt=now(), **fields)
            save(state_path, state)

        try:
            while True:
                guard()
                index_path = destination / 'run.json'
                index = dict(schemaVersion=1, kind='aoe2lab.compact-archive',
                    title=args.title, matchups=[], finalVideo=None,
                    sourceDeletionAuthorizedByThisTool=False)
                if index_path.exists():
                    if digest(index_path) != state['indexSha256']:
                        raise RuntimeError('Archive index changed outside this worker; refusing overwrite')
                    index = read(index_path)
                    if index['title'] != args.title:
                        raise RuntimeError('Archive title conflict')
                elif state['verified']:
                    raise RuntimeError('Verified archive index is missing')
                copied = {r['jobId']: r for r in index['matchups']}
                if not set(copied).issubset(expected):
                    raise RuntimeError('Unexpected archived jobs')
                status = read(campaign / 'capture/status.json')
                ready = {r['jobId']: r for r in status.get('results', []) if r['status'] == 'verified'}
                for job in expected:
                    if job in copied or job not in ready:
                        continue
                    guard()
                    source = Path(ready[job]['runDirectory']).resolve()
                    if not source.is_relative_to(RUNS / job / 'live'):
                        raise ValueError('Capture source escaped its job directory')
                    row = prepare(source)  # Verifies source sizes/hashes and reconstruction metadata.
                    if row['jobId'] != job or any(r['name'].casefold() == row['name'].casefold() for r in copied.values()):
                        raise ValueError('Duplicate or mismatched archive identity')
                    persist('COPYING', currentJob=job)
                    for info in row['files'].values():
                        target = destination / info['path']
                        if target.parent != destination:
                            raise ValueError('Unsafe archive filename')
                        copy_file(info, target, guard)
                    index['matchups'].append(row)
                    guard()
                    # Only extend our checksum-bound index, never foreign external data.
                    if index_path.exists() and digest(index_path) != state['indexSha256']:
                        raise RuntimeError('Archive index changed during copy')
                    save(index_path, index)
                    copied[job] = row
                    persist('COPYING', verified=len(copied), indexSha256=digest(index_path),
                            bytes=sum(f['bytes'] for r in copied.values() for f in r['files'].values()))
                    print(f'{len(copied)}/{len(expected)} copied and SHA-256 verified', flush=True)
                complete = (set(copied) == set(expected) and status.get('completed') == len(expected)
                            and not status.get('failed') and not status.get('pendingExports'))
                persist('COMPLETE' if complete else 'WAITING_FOR_CAPTURE', currentJob=None,
                        externalFreeBytes=shutil.disk_usage(destination).free)
                if complete or not args.follow:
                    return
                if status.get('state') in ('CRASHED', 'COMPLETE_WITH_FAILURES', 'STOPPED_AFTER_ERRORS'):
                    raise RuntimeError('Capture needs attention; all completed copies preserved')
                time.sleep(30)
        except Exception:
            persist('NEEDS_ATTENTION', error=traceback.format_exc())
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--volume-label', required=True)
    parser.add_argument('--volume-serial', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--follow', action='store_true')
    main(parser.parse_args())
