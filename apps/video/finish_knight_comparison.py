"""Wait for this episode's render, assemble approved bookends, and upload once."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from build_knight_comparison_series import read,save,REPO
from prepare_knight_comparison_upload import prepare


def finish(unit):
    plan=REPO/f'apps/video/intro/{unit}-comparison.json'
    series=REPO/f'data/local/{unit}-comparison-full'
    intro=REPO/f'data/local/{unit}-comparison-intro'
    state=series/'production-status.json'
    deadline=time.monotonic()+12*3600
    while True:
        status=read(series/'status.json') if (series/'status.json').exists() else {}
        if status.get('state')=='NEEDS_ATTENTION':raise RuntimeError(status.get('error'))
        review_pending=(intro/'narration-review-pending.json').exists()
        if status.get('state')=='COMPLETE' and (intro/'bookends-ready.json').exists() and not review_pending:break
        if time.monotonic()>deadline:raise TimeoutError('Episode render did not complete within 12 hours')
        save(state,dict(state='WAITING_FOR_NARRATION_REVIEW' if review_pending else 'WAITING_FOR_RENDER',completed=status.get('completed'),updatedAt=time.time()))
        time.sleep(30)
    save(state,dict(state='ASSEMBLING',updatedAt=time.time()))
    subprocess.run([sys.executable,str(REPO/'apps/video/build_champi_comparison_bookends.py'),
        '--plan',str(plan),'--output',str(intro),'--series-dir',str(series),'--assemble-only'],check=True)
    preparation=prepare(plan,series,intro,True)
    save(state,dict(state='UPLOADING',preparation=str(preparation),updatedAt=time.time()))
    key=unit+'-four-civs-v1'
    subprocess.run([sys.executable,'-u',str(REPO/'apps/video/upload_youtube.py'),
        '--preparation',str(preparation),'--state-key',key,'--processing-wait-seconds','60'],check=True)
    upload=read(REPO/f'data/local/youtube/{key}-upload-status.json')
    save(state,dict(state='UPLOAD_RETURNED',upload=upload,updatedAt=time.time()))
    print(json.dumps(upload),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('unit',choices=['paladin','cavalier']);a=p.parse_args()
    try:finish(a.unit)
    except BaseException as e:
        save(REPO/f'data/local/{a.unit}-comparison-full/production-status.json',dict(state='NEEDS_ATTENTION',error=str(e),updatedAt=time.time()))
        raise
