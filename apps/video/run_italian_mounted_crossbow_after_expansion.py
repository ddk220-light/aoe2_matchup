"""Append the authorized Italian set once the four active variants finish.

Does not interrupt capture or modify active catalogs. Reuses completed campaigns
and existing archive receipts; no scheduled Codex monitor is created.
"""
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import prepare_mounted_crossbow_capture as prepare
from run_champi_comparison_capture import read, save

ROOT = prepare.ROOT
WORK = ROOT / 'data/local/mounted-crossbow-expansion'
ARCHIVES = ROOT / 'data/local/storage-audit/regional-copy'
EXPECTED = ('britons', 'celts', 'bohemians', 'burgundians')


def status(state, **fields):
    save(WORK / 'italian-handoff-status.json', dict(state=state, pid=os.getpid(),
        updatedAt=time.time(), additionalCaptures=77, combinedTotal=385, **fields))


def paused():
    return ((WORK / 'PAUSE').exists()
            or (ROOT / 'data/local/thermal/PAUSED.json').exists()
            or bool(list(WORK.glob('*/PAUSE'))))


def acquire(path):
    handle = path.open('a+b')
    try:
        # Windows byte-range locks also prohibit reading the locked byte.
        # Inspect length instead, so a live owner's lock is normal contention
        # rather than an uncaught PermissionError before LK_NBLCK.
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def ensure_archive_workers():
    # Existing workers discover the appended campaign through queue.json. If
    # they already finished, restart once; their receipts skip completed work.
    for kind, script in [('copy', 'copy_regional_capture_archives.py'),
                         ('move', 'move_verified_regional_sources.py')]:
        probe = acquire(ARCHIVES / (kind + '.lock'))
        if probe is None:
            continue
        probe.close()
        state_path = ARCHIVES / ('status.json' if kind == 'copy' else 'move-status.json')
        state = read(state_path)
        if state.get('state') == 'NEEDS_ATTENTION':
            raise RuntimeError(f'{kind} archive worker needs attention: {state.get("error")}')
        if state.get('state') == 'COMPLETE' and state.get('total') == 1386:
            continue
        with (ARCHIVES / f'italian-{kind}-output.log').open('a', encoding='utf-8') as out, \
                (ARCHIVES / f'italian-{kind}-error.log').open('a', encoding='utf-8') as err:
            subprocess.Popen([sys.executable, '-u', str(ROOT / 'apps/video' / script)],
                cwd=ROOT, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    owner = acquire(WORK / 'italian-handoff.lock')
    if owner is None:
        return
    with owner:
        try:
            while True:
                if paused():
                    status('PAUSED'); return
                queue = read(WORK / 'queue.json')
                keys = tuple(c['key'] for c in queue['campaigns'])
                if keys == EXPECTED + ('italians',):
                    break
                if keys != EXPECTED or queue['total'] != 308:
                    raise RuntimeError('Unexpected predecessor queue; existing plans preserved')
                current = read(WORK / 'status.json')
                if current.get('state') in ('NEEDS_ATTENTION', 'NEEDS_RETAKES', 'PAUSED', 'SUPERSEDED'):
                    status('PREDECESSOR_NEEDS_ATTENTION', predecessorState=current['state']); return
                if prepare.queue_complete(WORK, 308, 4):
                    gate = acquire(WORK / 'queue.lock')
                    if gate is not None:
                        with gate:
                            if not prepare.queue_complete(WORK, 308, 4) or paused():
                                continue
                            status('PREPARING_ITALIANS')
                            prepare.WORK = WORK
                            prepare.CIVS = ('Italians',)
                            audit, analyzer = prepare.audit_subjects()
                            prior_audit = read(WORK / 'release-cost-audit.json')
                            if audit['datSha256'] != prior_audit['datSha256']:
                                raise RuntimeError('Game data changed since the original plans')
                            save(WORK / 'italian-release-cost-audit.json', audit)
                            prepare.activate(audit, analyzer, append=True)
                            prior_audit['subjects'].extend(audit['subjects'])
                            save(WORK / 'release-cost-audit.json', prior_audit)
                            request = read(WORK / 'follow-on-request.json')
                            request.update(total=385, civilizations=[c['civilization']
                                for c in read(WORK / 'queue.json')['campaigns']])
                            save(WORK / 'follow-on-request.json', request)
                        break
                status('WAITING_FOR_FOUR_VARIANTS')
                time.sleep(30)
            if paused():
                status('PAUSED'); return
            ensure_archive_workers()
            status('CAPTURING_ITALIANS')
            # The established runner skips the four COMPLETE campaigns, whose
            # video sources may already be archived, and captures only Italians.
            child = subprocess.Popen([sys.executable, '-u', str(ROOT / 'apps/video/run_knight_expansion.py'),
                '--work', str(WORK)], cwd=ROOT)
            while child.poll() is None:
                time.sleep(30)
                ensure_archive_workers()
            if child.returncode or not prepare.queue_complete(WORK, 385, 5):
                status('NEEDS_ATTENTION', queueState=read(WORK / 'status.json').get('state'))
                return
            ensure_archive_workers()
            status('CAPTURES_COMPLETE_ARCHIVE_WORKERS_ACTIVE')
        except Exception:
            status('NEEDS_ATTENTION', error=traceback.format_exc())
            raise


if __name__ == '__main__':
    main()
