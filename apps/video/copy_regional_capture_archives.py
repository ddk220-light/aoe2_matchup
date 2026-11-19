"""Copy completed Guard/mounted-crossbow sets to SAFEHOUSE; never delete sources.

Runs separately from capture and waits for complete, verified civilization sets.
Only folders claimed in the local receipt may be resumed. Existing external
files are verified or rejected, never overwritten. No game/catalog mutations.
"""
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

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/storage-audit/regional-copy'
DEST = Path('D:/AoE2 Renders')
IDENTITY = dict(label='SAFEHOUSE', volumeSerial='5EA9EEEF',
                physicalSerial='00000107000079B6', model='BUFFALO HD-PCFU3')
QUEUES = [('varangian-guard-capture', 'varangian-guard'),
          ('mounted-crossbow-capture', 'mounted-crossbow')]
RESERVE = 4 * 2**30


def configured_queues():
    queues = list(QUEUES)
    if (ROOT / 'data/local/mounted-crossbow-expansion/queue.json').is_file():
        queues.append(('mounted-crossbow-expansion', 'mounted-crossbow'))
    return queues


def expected_total():
    return sum(read(ROOT / 'data/local' / name / 'queue.json')['total']
               for name, _ in configured_queues())


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def check_disk():
    label = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        'D:\\', label, len(label), ctypes.byref(serial), None, None, None, 0)
    if not ok or label.value != IDENTITY['label'] or serial.value != int(IDENTITY['volumeSerial'], 16):
        raise RuntimeError('SAFEHOUSE unavailable or drive identity changed; sources preserved')
    if not DEST.is_dir() or DEST.resolve() != DEST:
        raise RuntimeError('Expected archive directory is missing or redirected')


def ready(campaign):
    work = Path(campaign['workDirectory'])
    path = work / 'capture/status.json'
    if not path.exists():
        return None
    status = read(path)
    if status.get('state') != 'COMPLETE':
        return None
    expected = [m['id'] for m in read(work / 'manifest.json')['matchups']]
    results = status['results']
    actual = [r['jobId'] for r in results if r['status'] == 'verified']
    if (len(expected) != 77 or len(results) != 77 or len(set(actual)) != 77
            or set(actual) != set(expected) or status.get('completed') != 77
            or status.get('failed', 0) or status.get('pendingExports', 0)):
        raise RuntimeError(f'Completed campaign is not fully verified: {work}')
    by_id = {r['jobId']: r for r in results}
    return [Path(by_id[j]['runDirectory']) for j in expected]


def check_pause():
    if (WORK / 'PAUSE').exists() or (ROOT / 'data/local/thermal/PAUSED.json').exists():
        raise RuntimeError('Copy paused by local/thermal safeguard; sources preserved')


def copy_file(info, target):
    check_pause()
    check_disk()
    if target.exists():
        if target.stat().st_size != info['bytes'] or digest(target) != info['sha256']:
            raise RuntimeError(f'Existing archive conflict: {target}')
        return
    if shutil.disk_usage(DEST).free < info['bytes'] + RESERVE:
        raise RuntimeError('Archive free space would fall below 4 GiB reserve')
    partial = target.with_suffix(target.suffix + '.partial')
    if not partial.exists():
        # Exclusive creation protects even an unexpected pre-existing partial.
        with Path(info['source']).open('rb') as src, partial.open('xb') as dst:
            shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
    if partial.stat().st_size != info['bytes'] or digest(partial) != info['sha256']:
        raise RuntimeError(f'Partial copy does not verify; retained for inspection: {partial}')
    check_disk()
    # On Windows rename fails if the target already exists (no replacement).
    partial.rename(target)


def run(state):
    def persist(phase, **extra):
        state.update(state=phase, pid=os.getpid(), updatedAt=now(), **extra)
        save(WORK / 'status.json', state)

    while True:
        check_disk()
        check_pause()
        for queue_name, prefix in configured_queues():
            for campaign in read(ROOT / 'data/local' / queue_name / 'queue.json')['campaigns']:
                key = prefix + '-' + campaign['key']
                dest = DEST / key
                prior = state['campaigns'].get(key)
                if prior and prior.get('state') == 'COMPLETE':
                    if not (dest / 'run.json').is_file():
                        raise RuntimeError(f'Completed archive index missing: {dest}')
                    continue
                sources = ready(campaign)
                if sources is None:
                    continue
                if prior is None:
                    if dest.exists():
                        raise RuntimeError(f'Refusing to modify unowned existing folder: {dest}')
                    prior = state['campaigns'][key] = dict(state='COPYING',
                        destination=str(dest), copied=0, total=77, startedAt=now())
                    persist('COPYING', current=key)
                dest.mkdir(exist_ok=True)
                if dest.resolve() != dest or dest.parent != DEST:
                    raise RuntimeError('Archive destination is redirected or outside expected root')
                title = f"{campaign['civilization']} {campaign['unit']} Unique Unit Matchups"
                rows = []
                names = set()
                for source in sources:
                    check_disk()
                    check_pause()
                    if not source.resolve().is_relative_to(ROOT / 'aoe2x/js_simulation/calibration/lab/runs'):
                        raise RuntimeError('Capture source outside approved recording root')
                    row = prepare(source)
                    if row['name'].casefold() in names:
                        raise RuntimeError('Duplicate archive filename')
                    names.add(row['name'].casefold())
                    for info in row['files'].values():
                        copy_file(info, dest / info['path'])
                    rows.append(row)
                    prior.update(copied=len(rows), updatedAt=now())
                    persist('COPYING', current=key)
                    if len(rows) % 10 == 0:
                        print(f'{key}: {len(rows)}/77 copied and checksum verified', flush=True)
                index = dict(schemaVersion=1, kind='aoe2lab.compact-archive', title=title,
                    matchups=rows, finalVideo=None, sourceDeletionAuthorizedByThisTool=False)
                check_disk()
                index_path = dest / 'run.json'
                if index_path.exists():
                    if read(index_path) != index:
                        raise RuntimeError(f'Existing index conflict: {index_path}')
                else:
                    with index_path.open('x', encoding='utf-8') as f:
                        json.dump(index, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                prior.update(state='COMPLETE', verified=77, completedAt=now(),
                    indexSha256=digest(index_path),
                    bytes=sum(i['bytes'] for r in rows for i in r['files'].values()),
                    localSourcesRetained=True)
                persist('COPYING', current=key)
                print(f'{key}: COMPLETE, 77 videos + frames + run.json; sources retained', flush=True)
        done = sum(c.get('verified', 0) for c in state['campaigns'].values() if c['state'] == 'COMPLETE')
        total = expected_total()
        persist('COMPLETE' if done == total else 'WAITING_FOR_CAPTURE', current=None,
                verified=done, total=total, localFreeBytes=shutil.disk_usage('C:/').free,
                externalFreeBytes=shutil.disk_usage(DEST).free)
        if done == total:
            return
        time.sleep(30)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'copy.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        path = WORK / 'status.json'
        state = read(path) if path.exists() else dict(schemaVersion=1, drive=IDENTITY,
            startedAt=now(), campaigns={}, sourceDeletionAuthorized=False)
        if state['drive'] != IDENTITY:
            raise RuntimeError('Receipt belongs to a different drive')
        try:
            run(state)
        except Exception:
            state.update(state='NEEDS_ATTENTION', error=traceback.format_exc(), updatedAt=now())
            save(path, state)
            raise


if __name__ == '__main__':
    main()
