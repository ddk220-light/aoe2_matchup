"""Wait for the verified Guard queue, then prepare and run mounted crossbows.

Does not control the active game, alter its catalogs, or restart stopped Guards.
An hourly app monitor handles failures; this process only performs the handoff.
"""
import os
import subprocess
import sys
import time
import traceback

from prepare_mounted_crossbow_capture import PREDECESSOR, ROOT, WORK, TOTAL, guards_complete
from run_champi_comparison_capture import read, save


def status(state, **fields):
    save(WORK / 'handoff-status.json', dict(state=state, pid=os.getpid(),
        updatedAt=time.time(), keepLocal=True, **fields))


def paused():
    return (any(p.exists() for p in (WORK / 'PAUSE', PREDECESSOR / 'PAUSE',
            ROOT / 'data/local/thermal/PAUSED.json'))
            or any(PREDECESSOR.glob('*/PAUSE')) or any(WORK.glob('*/PAUSE')))


def main():
    import msvcrt
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'handoff.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        # Exit quietly if another handoff owns the lock; do not replace its status.
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            while not guards_complete():
                if paused():
                    status('PAUSED'); return
                previous = read(PREDECESSOR / 'status.json')
                if previous.get('state') in ('NEEDS_ATTENTION', 'NEEDS_RETAKES', 'PAUSED', 'SUPERSEDED'):
                    status('PREDECESSOR_NEEDS_ATTENTION', predecessorState=previous['state']); return
                status('WAITING_FOR_VARANGIAN_GUARDS')
                time.sleep(30)
            if paused():
                status('PAUSED'); return
            # Wait for the completed predecessor to release its queue lock before
            # changing catalogs. Hold it throughout one-time activation.
            with (PREDECESSOR / 'queue.lock').open('r+b') as guard_lock:
                while True:
                    try:
                        guard_lock.seek(0)
                        msvcrt.locking(guard_lock.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if paused():
                            status('PAUSED'); return
                        time.sleep(2)
                if not guards_complete() or paused():
                    status('PAUSED'); return
                if not (WORK / 'queue.json').exists():
                    status('PREPARING_MOUNTED_CROSSBOWS')
                    subprocess.run([sys.executable, '-u', str(ROOT / 'apps/video/prepare_mounted_crossbow_capture.py'),
                                    '--activate'], cwd=ROOT, check=True)
            if paused():
                status('PAUSED'); return
            status('CAPTURING_MOUNTED_CROSSBOWS')
            subprocess.run([sys.executable, '-u', str(ROOT / 'apps/video/run_knight_expansion.py'),
                            '--work', str(WORK)], cwd=ROOT, check=True)
            result = read(WORK / 'status.json')
            status('COMPLETE' if result.get('state') == 'COMPLETE' and result.get('verified') == TOTAL
                   else 'NEEDS_ATTENTION', queueState=result.get('state'), verified=result.get('verified'))
        except Exception:
            status('NEEDS_ATTENTION', error=traceback.format_exc())
            raise


if __name__ == '__main__':
    main()
