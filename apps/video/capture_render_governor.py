"""Give game capture priority over one explicitly selected offline renderer.

Sample system load every five seconds. Suspend only the verified render process
tree on sustained >80% CPU or memory pressure; resume with hysteresis. Request a
capture-boundary wait if pressure persists, never interrupt a recorded battle.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import time

from thermal_guard import processes, control

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/local/capture-render-governor'


class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
        ('total','available','pageTotal','pageAvailable','virtualTotal','virtualAvailable','extended')]


def sample(previous=None):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    idle,kern,user=[ctypes.c_ulonglong() for _ in range(3)]
    if not kernel.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kern),ctypes.byref(user)):raise ctypes.WinError()
    current=(idle.value,kern.value+user.value)
    cpu=None if previous is None else 100*(1-(current[0]-previous[0])/max(1,current[1]-previous[1]))
    mem=Memory();mem.length=ctypes.sizeof(mem)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(mem)):raise ctypes.WinError()
    return current,dict(cpuPercent=cpu,memoryPercent=mem.load,availableGiB=mem.available/2**30)


def pressure(metrics):
    return metrics['cpuPercent']>80 or metrics['memoryPercent']>=80 or metrics['availableGiB']<4


def recovered(metrics):
    return metrics['cpuPercent']<65 and metrics['memoryPercent']<73 and metrics['availableGiB']>=5


def save(value):
    value.update(pid=os.getpid(),updatedAt=time.time())
    temp=OUT/'status.tmp.json';temp.write_text(json.dumps(value,indent=2));temp.replace(OUT/'status.json')


def render_tree(rows, root):
    selected={root['ProcessId']}
    while True:
        added={p['ProcessId'] for p in rows if p['ParentProcessId'] in selected and 'thermal_guard.py' not in (p.get('CommandLine') or '')}
        if added<=selected:break
        selected|=added
    return [p for p in rows if p['ProcessId'] in selected]


def lower_priority(rows):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    mask=(1<<max(1,os.cpu_count()//2))-1
    for row in rows:
        handle=kernel.OpenProcess(0x0200,False,row['ProcessId'])
        if not handle:raise ctypes.WinError()
        try:
            if not kernel.SetPriorityClass(handle,0x4000):raise ctypes.WinError()
            if not kernel.SetProcessAffinityMask(handle,mask):raise ctypes.WinError()
        finally:kernel.CloseHandle(handle)
    return mask


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--render-pid',type=int,required=True)
    args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    rows=processes();root=next(r for r in rows if r['ProcessId']==args.render_pid)
    if 'build_champi_comparison_series.py' not in (root.get('CommandLine') or ''):
        raise ValueError('Target is not the requested Champi renderer')
    mask=lower_priority(render_tree(rows,root));previous,_=sample();high=low=0;held=[]
    def release():
        live={(r['ProcessId'],r['created']) for r in processes()}
        for row in reversed(held):
            if (row['ProcessId'],row['created']) in live:control(row['ProcessId'],row['created'],resume=True)
        held.clear()
    try:
        while not (OUT/'STOP').exists():
            time.sleep(5);previous,m=sample(previous)
            high=high+1 if pressure(m) else 0;low=low+1 if recovered(m) else 0
            if not held and high>=2:
                rows=processes()
                if not any(r['ProcessId']==root['ProcessId'] and r['created']==root['created'] for r in rows):break
                # Suspend parent first, then its workers; record exactly our own
                # suspend operations, so thermal pauses retain their own count.
                tree=render_tree(rows,root)
                tree.sort(key=lambda r:r['ProcessId']!=root['ProcessId'])
                for row in tree:
                    control(row['ProcessId'],row['created']);held.append(row)
            if held and low>=3 and not (ROOT/'data/local/thermal/PAUSED.json').exists():release()
            value=dict(**m,rendererPid=root['ProcessId'],rendererAffinityMask=mask,
                       state='RENDER_PAUSED' if held else 'RUNNING',suspended=held,
                       waitForCaptureBoundary=bool(held and pressure(m)))
            save(value)
            with (OUT/'history.jsonl').open('a') as log:log.write(json.dumps(value)+'\n')
    finally:
        release()
        save(dict(state='STOPPED',waitForCaptureBoundary=False))


if __name__=='__main__':main()
