"""Keep the single game recorder busy independently of offline media production.

The capture lane adopts an already running campaign and advances in roster order.
The overlay lane is a separate bounded worker; neither lane waits for publishing.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from aoe2x.lab.io import read_json, write_json, utc_now

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
OUT = LAB / 'continuous-production'
FINISHED = {'COMPLETE', 'COMPLETE_WITH_FAILURES'}


def campaign_name(episode):
    return Path(episode['manifest']).stem.removeprefix('aoe2lab.recorder.')


def capture_decision(episode, status, alive):
    # A published/pruned episode must never be recreated because files are absent.
    if episode.get('status') == 'complete':
        return 'skip'
    if status.get('state') == 'FINALIZING' and status.get('captureReleased') is True:
        return 'advance'
    if alive:
        return 'adopt'
    if status.get('state') in FINISHED:
        return 'advance'
    if status.get('state') in {'CRASHED', 'STOPPED_AFTER_ERRORS', 'STOPPED'}:
        return 'attention'
    return 'start' if not status else 'attention'


def process_alive(pid):
    if not pid:
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return ctypes.get_last_error() == 5  # Access denied: never duplicate it.
    try:
        code = ctypes.c_ulong()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


def load(path):
    return read_json(path) if path.exists() else {}


def paused():
    return (ROOT / 'data/local/thermal/PAUSED.json').exists() or (OUT / 'STOP').exists()


def run(lane):
    state = {'pid': os.getpid(), 'lane': lane, 'startedAt': utc_now(), 'episodes': {}}
    previous = load(OUT / f'{lane}.json')
    attempted = previous.get('attempted', {})

    def save(label, key=None, **extra):
        state.update(state=label, currentEpisode=key, updatedAt=utc_now(), attempted=attempted, **extra)
        write_json(OUT / f'{lane}.json', state)

    while True:
        if paused():
            save('PAUSED'); time.sleep(5); continue
        episodes = sorted(read_json(ROOT / 'data/video-production-queue.json')['episodes'], key=lambda e: e['order'])
        pending = False
        for episode in episodes:
            key = episode['key']
            if episode.get('status') == 'complete':
                continue
            report = LAB / 'campaigns' / campaign_name(episode)
            status = load(report / 'status.json')
            if lane == 'capture':
                action = capture_decision(episode, status, process_alive(status.get('pid')))
                state['episodes'][key] = {'captureState': status.get('state'), 'verified': status.get('completed', 0), 'failed': status.get('failed', 0)}
                if action in {'skip', 'advance'}:
                    continue
                if action == 'attention':
                    save('NEEDS_ATTENTION', key, error='Recorder stopped or disappeared; inspect game before restarting.')
                    return 2
                if action == 'adopt':
                    save('CAPTURING', key, workerPid=status['pid'])
                    pending = True
                    break
                report.mkdir(parents=True, exist_ok=True)
                if paused():
                    pending = True; break
                with (report / 'continuous.stdout.log').open('a', encoding='utf-8') as out, (report / 'continuous.stderr.log').open('a', encoding='utf-8') as err:
                    worker = subprocess.Popen([sys.executable, '-u', '-m', 'aoe2x.lab.recording_campaign', str(ROOT / episode['manifest']), '--reports', str(report)], cwd=ROOT, stdout=out, stderr=err)
                    save('CAPTURING', key, workerPid=worker.pid)
                    # Advance once the worker explicitly releases the game lock;
                    # its offline export thread may continue independently.
                    while worker.poll() is None:
                        current = load(report / 'status.json')
                        state['episodes'][key] = {'captureState': current.get('state'), 'verified': current.get('completed', 0), 'failed': current.get('failed', 0)}
                        save('CAPTURING', key, workerPid=worker.pid)
                        if capture_decision(episode, current, True) == 'advance':
                            break
                        time.sleep(2)
                    released = capture_decision(episode, load(report / 'status.json'), worker.poll() is None) == 'advance'
                    if not released and (worker.returncode not in (0, 2) or load(report / 'status.json').get('state') not in FINISHED):
                        save('NEEDS_ATTENTION', key, exitCode=worker.returncode)
                        return 2
                pending = True
                break
            else:
                output = report.with_name(report.name + '-overlays')
                overlay_status = load(output / 'status.json')
                if overlay_status.get('state') == 'COMPLETE':
                    continue
                pending = True
                if not status:
                    continue
                if process_alive(overlay_status.get('pid')):
                    save('OVERLAYS_RUNNING', key, workerPid=overlay_status['pid'])
                    break
                # Failed offline work must not block subsequent episodes. Retry
                # on a new capture attempt, or after removing this lane's stamp.
                signature = status.get('startedAt')
                if attempted.get(key) == signature:
                    continue
                if paused():
                    break
                output.mkdir(parents=True, exist_ok=True)
                attempted[key] = signature
                with (output / 'continuous.stdout.log').open('a', encoding='utf-8') as out, (output / 'continuous.stderr.log').open('a', encoding='utf-8') as err:
                    worker = subprocess.Popen([sys.executable, '-u', str(ROOT / 'apps/video/render_campaign_overlays.py'), '--manifest', str(ROOT / episode['manifest']), '--output', str(output), '--workers', '1', '--recording-status', str(report / 'status.json')], cwd=ROOT, stdout=out, stderr=err)
                    save('OVERLAYS_RUNNING', key, workerPid=worker.pid)
                    while worker.poll() is None:
                        time.sleep(2)
                    state['episodes'][key] = {'overlayState': load(output / 'status.json').get('state')}
                    save('SCANNING')
                break
        if lane == 'capture' and not pending:
            save('ALL_CAPTURES_FINISHED'); return 0
        save('SCANNING' if lane == 'overlays' else state['state'], state.get('currentEpisode'))
        time.sleep(2 if lane == 'capture' else 10)


def main():
    import msvcrt
    parser = argparse.ArgumentParser()
    parser.add_argument('--lane', required=True, choices=('capture', 'overlays'))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ['PYTHONPATH'] = str(ROOT / 'apps/video') + os.pathsep + str(ROOT)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    with (OUT / f'{args.lane}.lock').open('a+b') as lock:
        lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        return run(args.lane)


if __name__ == '__main__':
    raise SystemExit(main())
