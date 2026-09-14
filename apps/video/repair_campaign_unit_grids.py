"""Rebuild HP grids from preserved frames, retaining measured video alignment."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from aoe2x.lab.io import write_json
from aoe2x.lab.postprocess_campaign import source_hash

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    args = p.parse_args()
    import msvcrt
    with (args.output / 'worker.lock').open('a+b') as lock:
        lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        state = json.loads((args.output / 'status.json').read_text())
        audit = json.loads(args.audit.read_text())
        affected = {j for master in ('1880', '2565') for j in audit.get(master, [])}
        revision = source_hash()
        state.update(state='RUNNING', pid=os.getpid(), sourceHash=revision,
                     repair='Exclude installed projectile/effect masters 1880 and 2565 from army grids')
        pending = []
        for row in state['jobs']:
            if row['jobId'] in affected and row.get('overlay', {}).get('gridRepairRevision') != revision:
                row['overlay'] = {'status': 'pending'}
                pending.append(row)

        def save():
            state.update(updatedAt=time.time(), completed=sum(j['overlay']['status']=='complete' for j in state['jobs']),
                         failed=sum(j['overlay']['status']=='failed' for j in state['jobs']))
            write_json(args.output / 'status.json', state)

        save()
        for row in pending:
            while (ROOT / 'data/local/thermal/PAUSED.json').exists():
                time.sleep(5)
            row['overlay'] = {'status': 'running'}; save()
            run = LAB / 'runs' / row['jobId'] / 'live/run_001'
            try:
                with (run/'unit-hp-overlay/grid-repair.log').open('w', encoding='utf-8') as log:
                    subprocess.run([sys.executable, '-u', '-m', 'overlay.unit_hp', str(run)], cwd=ROOT,
                                   stdout=log, stderr=log, check=True, timeout=1800)
                data = json.loads((run/'unit-hp-overlay/units.json').read_text())
                assert not any(u['masterId'] in (1880,2565) for r in data['rows'] for us in r['sides'].values() for u in us)
                import cv2
                sizes=[]
                video=run/'unit-hp-overlay/battle-with-unit-hp.mp4'
                for path in (run/'battle.mp4', video):
                    cap=cv2.VideoCapture(str(path));sizes.append([cap.get(x) for x in (3,4,7,5)]);cap.release()
                assert sizes[0]==sizes[1] and video.stat().st_size>10000
                row['overlay']={'status':'complete','sourceHash':revision,'gridRepairRevision':revision,
                                'video':str(video),'mediaValidation':sizes[1],
                                'alignment':'Existing measured HP-bar/video alignment retained; effect entities removed from army counts'}
            except Exception as e:
                row['overlay']={'status':'failed','error':repr(e)}
            save(); print(json.dumps({'job':row['jobId'],'completed':state['completed'],'failed':state['failed']}),flush=True)
        state['state']='COMPLETE' if not state['failed'] else 'NEEDS_ATTENTION';save()


if __name__ == '__main__':
    main()
