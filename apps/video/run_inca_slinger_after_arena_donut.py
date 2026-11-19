"""Finite handoff: finish recording/copying, then capture missing Slinger cells.

Wait for both predecessor locks to release before binding its destination
indexes. Capture serially, copy each completed subject concurrently with the
next, and exit. No schedules, renders, simulator runs, cleanup or uploads.
"""
import msvcrt
import os
import subprocess
import sys
import time
import traceback

from copy_capture_campaign import now
from prepare_inca_slinger_standard import PREDECESSOR, ROOT, WORK, predecessor_complete
from run_champi_comparison_capture import read, save


def status(state, **fields):
    save(WORK / 'handoff-status.json', dict(state=state, pid=os.getpid(), updatedAt=now(), **fields))


def paused():
    return (any(p.exists() for p in (WORK / 'PAUSE', PREDECESSOR / 'PAUSE',
        ROOT / 'data/local/thermal/PAUSED.json')) or any(WORK.glob('*/PAUSE'))
        or any(PREDECESSOR.glob('*/PAUSE')))


def try_lock(path):
    stream = path.open('a+b')
    stream.seek(0)
    if not stream.read(1):
        stream.write(b'0'); stream.flush()
    stream.seek(0)
    try:
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        stream.close()
        return None
    return stream


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    handoff = try_lock(WORK / 'handoff.lock')
    if handoff is None:
        return  # Another authorized handoff owns this finite job.
    with handoff:
        try:
            while True:
                if paused():
                    status('PAUSED'); return
                if predecessor_complete():
                    capture_lock = try_lock(PREDECESSOR / 'queue.lock')
                    if capture_lock is not None:
                        with capture_lock:
                            copy_lock = try_lock(PREDECESSOR / 'delivery/copy.lock')
                            if copy_lock is not None:
                                with copy_lock:
                                    if not predecessor_complete() or paused():
                                        status('PAUSED'); return
                                    if not (WORK / 'queue.json').exists():
                                        status('PREPARING_SLINGER')
                                        subprocess.run([sys.executable, '-u', str(ROOT / 'apps/video/prepare_inca_slinger_standard.py')],
                                            cwd=ROOT, check=True)
                                    break
                for path in (PREDECESSOR / 'status.json', PREDECESSOR / 'delivery/status.json'):
                    if path.exists() and read(path).get('state') in (
                            'NEEDS_ATTENTION', 'NEEDS_RETAKES', 'PAUSED', 'CAPTURE_NEEDS_ATTENTION'):
                        status('PREDECESSOR_NEEDS_ATTENTION', predecessorState=read(path)['state']); return
                status('WAITING_FOR_PREDECESSOR_RECORDING_AND_COPY')
                time.sleep(30)
            if paused():
                status('PAUSED'); return
            # Both children have their own mutexes. Keep all local sources.
            delivery = WORK / 'delivery'
            delivery.mkdir(exist_ok=True)
            with (delivery / 'worker-output.log').open('a', encoding='utf-8') as output, \
                 (delivery / 'worker-error.log').open('a', encoding='utf-8') as errors:
                copier = subprocess.Popen([sys.executable, '-u', str(ROOT / 'apps/video/copy_arena_donut_to_share.py'),
                    '--work', str(WORK), '--follow'], cwd=ROOT, stdout=output, stderr=errors,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                status('CAPTURING_SLINGER', copyPid=copier.pid)
                subprocess.run([sys.executable, '-u', str(ROOT / 'apps/video/run_knight_expansion.py'),
                    '--work', str(WORK)], cwd=ROOT, check=True)
                result = read(WORK / 'status.json')
                if result.get('state') != 'COMPLETE':
                    status('NEEDS_ATTENTION', queueState=result.get('state')); return
                status('WAITING_FOR_SLINGER_COPY', verified=result.get('verified'), total=result.get('total'))
                while copier.poll() is None:
                    if paused():
                        status('PAUSED'); return
                    time.sleep(30)
                copied = read(delivery / 'status.json')
                done = (copier.returncode == 0 and copied.get('state') == 'COMPLETE'
                        and copied.get('verified') == result['total'] == result.get('verified'))
                status('COMPLETE' if done else 'NEEDS_ATTENTION', verified=result.get('verified'),
                    total=result.get('total'), copied=copied.get('verified'), localSourcesRetained=True)
        except Exception:
            status('NEEDS_ATTENTION', error=traceback.format_exc())
            raise


if __name__ == '__main__':
    main()
