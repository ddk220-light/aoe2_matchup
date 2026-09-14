"""One-shot thermal check for the 15-minute Codex heartbeat.

Suspends the AoE2 workload on confirmed high temperatures. No recurring loop,
automatic resume, process termination, or machine power-setting changes.
"""
import argparse
import ctypes
import datetime as dt
import json
import math
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/local/thermal'
CPU_LIMIT, GPU_LIMIT = 90.0, 85.0
CPU_RESUME, GPU_RESUME = 80.0, 75.0


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp.json')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def now():
    return dt.datetime.now(dt.timezone.utc)


def cpu_reading(sample, current):
    timestamp = dt.datetime.fromisoformat(sample['timestamp'].replace('Z', '+00:00'))
    age = (current - timestamp).total_seconds()
    if not 0 <= age <= 90:
        raise ValueError('CPU sensor data is stale')
    values = [float(s['celsius']) for s in sample.get('sensors', [])
              if 'distance to tjmax' not in s.get('name', '').lower()]
    if not values or any(not math.isfinite(v) or not 0 < v < 130 for v in values):
        raise ValueError(sample.get('error', 'CPU temperature unavailable; administrator sensor setup required'))
    return max(values)


def readings():
    record = {'timestamp': now().isoformat(), 'cpuC': None, 'gpuC': None, 'errors': []}
    try:
        record['cpuC'] = cpu_reading(json.loads((OUT/'cpu.json').read_text(encoding='utf-8-sig')), now())
    except Exception as error:
        record['errors'].append('CPU: '+str(error))
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        values = [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        if not values or any(not math.isfinite(v) or not 0 < v < 130 for v in values):
            raise ValueError('No valid GPU temperature')
        record['gpuC'] = max(values)
    except Exception as error:
        record['errors'].append('GPU: '+str(error))
    return record


def hot(record):
    return [kind for kind, limit in [('cpuC', CPU_LIMIT), ('gpuC', GPU_LIMIT)]
            if record.get(kind) is not None and record[kind] >= limit]


def processes():
    command = "@(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='created';e={$_.CreationDate.ToUniversalTime().ToString('o')}}) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True, check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout)


def workload(rows, own_pid):
    """Include project workers, their children and AoE2, excluding this checker."""
    excluded = {own_pid}
    by_id = {r['ProcessId']: r for r in rows}
    cursor = own_pid
    while cursor in by_id:
        cursor = by_id[cursor]['ParentProcessId']
        if cursor in excluded:
            break
        excluded.add(cursor)
    root = str(ROOT).lower().replace('\\', '/')
    selected = set()
    for r in rows:
        name = r['Name'].lower()
        command = (r.get('CommandLine') or '').lower().replace('\\', '/')
        if r['ProcessId'] in excluded:
            continue
        if name == 'aoe2de_s.exe' or (name in ('python.exe', 'pythonw.exe', 'node.exe', 'ffmpeg.exe') and root in command):
            selected.add(r['ProcessId'])
    changed = True
    while changed:
        before = len(selected)
        for r in rows:
            if r['ParentProcessId'] in selected and r['ProcessId'] not in excluded:
                selected.add(r['ProcessId'])
        changed = len(selected) != before
    # Parents first, so they cannot launch more encoders while being paused.
    return sorted([r for r in rows if r['ProcessId'] in selected], key=lambda r: (r['ParentProcessId'] in selected, r['ProcessId']))


def control(pid, expected_created, resume=False):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    native = ctypes.WinDLL('ntdll')
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    fn = native.NtResumeProcess if resume else native.NtSuspendProcess
    fn.argtypes = [ctypes.c_void_p]
    fn.restype = ctypes.c_long
    handle = kernel.OpenProcess(0x0800 | 0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        times = [ctypes.c_ulonglong() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in times]):
            raise ctypes.WinError(ctypes.get_last_error())
        created = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(microseconds=times[0].value / 10)
        expected = dt.datetime.fromisoformat(expected_created.replace('Z', '+00:00'))
        if abs((created - expected).total_seconds()) > .002:
            raise ValueError(f'PID {pid} was reused; refusing to change unrelated process')
        result = fn(handle)
        if result < 0:
            raise OSError(f'Process operation returned NTSTATUS {result & 0xffffffff:08x}')
    finally:
        kernel.CloseHandle(handle)


def pause(record):
    flag = OUT/'PAUSED.json'
    state = json.loads(flag.read_text()) if flag.exists() else {'pausedAt': now().isoformat(), 'trigger': record, 'processes': []}
    write(flag, state)  # Latch before touching any worker. Other tasks must honor it.
    known = {(p['pid'], p['created']) for p in state['processes']}
    user_pause = ROOT/'data/local/cost-audit-pause/PAUSED.json'
    if user_pause.exists():
        # Media may remain user-paused while corrected capture is resumed.
        # Never increment those processes' suspend counts a second time.
        known.update((p['pid'], p['created']) for p in json.loads(user_pause.read_text()).get('processes', []) if p.get('status') == 'suspended')
    for p in workload(processes(), os.getpid()):
        key = (p['ProcessId'], p['created'])
        if key in known:
            continue  # Never add another suspend count to an already paused PID.
        saved = {'pid': p['ProcessId'], 'name': p['Name'], 'created': p['created'], 'status': 'attempting'}
        state['processes'].append(saved)
        write(flag, state)
        try:
            control(saved['pid'], saved['created'])
            saved['status'] = 'suspended'
        except Exception as error:
            saved.update(status='error', error=str(error))
        write(flag, state)
    return state


def resume(record):
    if record['errors'] or record['cpuC'] >= CPU_RESUME or record['gpuC'] >= GPU_RESUME:
        raise ValueError('Resume requires fresh CPU <80 C and GPU <75 C; never resume automatically')
    flag = OUT/'PAUSED.json'
    state = json.loads(flag.read_text())
    failures = []
    current = {(p['ProcessId'], p['created']) for p in processes()}
    for p in reversed(state['processes']):
        if p['status'] == 'resumed' or (p['pid'], p['created']) not in current:
            continue
        if p['status'] != 'suspended':
            failures.append(p)
            continue
        try:
            control(p['pid'], p['created'], resume=True)
            p['status'] = 'resumed'
        except Exception as error:
            p['resumeError'] = str(error)
            failures.append(p)
        write(flag, state)
    if failures:
        raise RuntimeError('Some processes need manual inspection; pause latch retained')
    state['resumedAt'] = now().isoformat()
    write(OUT/'last-resume.json', state)
    flag.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true', help='Only after explicit user request; interrupted capture must be reviewed')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with (OUT/'check.lock').open('a+b') as lock:
        lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        record = readings()
        record['thresholdsC'] = {'cpu': CPU_LIMIT, 'gpu': GPU_LIMIT}
        if args.dry_run:
            record['state'] = 'DRY_RUN'
            record['wouldPause'] = hot(record)
            record['targets'] = [{'pid': p['ProcessId'], 'name': p['Name']} for p in workload(processes(), os.getpid())]
        elif args.resume:
            resume(record)
            record['state'] = 'RESUMED_REVIEW_INTERRUPTED_CAPTURE'
        elif hot(record) or (OUT/'PAUSED.json').exists():
            state = pause(record)
            record['state'] = 'PAUSED'
            record['pauseErrors'] = [p for p in state['processes'] if p['status'] != 'suspended']
        else:
            record['state'] = 'SENSOR_UNAVAILABLE' if record['errors'] else 'OK'
        write(OUT/'status.json', record)
        with (OUT/'history.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps(record)+'\n')
        print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
