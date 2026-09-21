"""Finish the transfer receipt after the bounded archive workers exit."""
import ctypes
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data/local/storage-audit'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def alive(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == 258
    finally:
        kernel.CloseHandle(handle)


def snapshot():
    state = dict(camelCompleted=0, camelTarget=665, freedBytes=0, errors=[])
    for campaign in ['camel-comparison', 'camel-baseline']:
        path = ROOT / 'data/local' / campaign / 'archive-status.json'
        if not path.exists():
            continue
        receipt = read(path)
        complete = [r for r in receipt['completed'].values() if r['phase'] == 'complete']
        state['camelCompleted'] += len(complete)
        state['freedBytes'] += receipt['deletedBytes']
    for prefix in ['legacy-transfer', 'remaining-media']:
        plan = read(WORK / ('legacy-transfer-plan.json' if prefix == 'legacy-transfer' else 'remaining-media-plan.json'))
        moved = []
        for row in plan['files']:
            source = Path(row['source'])
            target = Path(plan['destinationRoot']) / row['relative']
            if source.is_symlink() and source.resolve() == target.resolve() and target.stat().st_size == row['bytes']:
                moved.append(row)
        state[prefix] = dict(completed=len(moved), total=len(plan['files']))
        state['freedBytes'] += sum(row['bytes'] for row in moved)
    done = state['camelCompleted'] == 665 and all(state[p]['completed'] == state[p]['total'] for p in ['legacy-transfer','remaining-media'])
    if done:
        indexed = 0
        for index in Path('D:/AoE2 Renders').glob('camel-comparison-*/run.json'):
            for row in read(index)['matchups']:
                for f in row['files'].values():
                    if (index.parent/f['path']).stat().st_size != f['bytes']:
                        raise ValueError(f'Archive verification mismatch: {index}')
                indexed += 1
        if indexed != 665:
            raise ValueError(f'Expected 665 archived rows, found {indexed}')
    state['state'] = 'COMPLETE' if done else 'RUNNING' if any(alive(p) for p in [6164,11892,20312]) else 'NEEDS_ATTENTION'
    state['cFreeGiB'] = round(shutil.disk_usage('C:/').free/2**30, 2)
    state['externalFreeGiB'] = round(shutil.disk_usage('D:/').free/2**30, 2)
    state['updatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return state


if __name__ == '__main__':
    while True:
        try:
            state = snapshot()
        except Exception as exc:
            state = dict(state='NEEDS_ATTENTION', error=str(exc))
        temporary = WORK/'SAFEHOUSE-progress.partial.json'
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(WORK/'SAFEHOUSE-progress.json')
        if state['state'] != 'RUNNING':
            break
        time.sleep(60)
