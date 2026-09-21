"""Record the approved nine variants serially, then compact verified sources.

Each campaign uses the existing pilot HP/count gate, ten-match checkpoints,
capture mutex, and 15-minute thermal/disk checks. No renders or uploads run.
"""
import subprocess
import sys
import traceback
from pathlib import Path

from prepare_knight_expansion import ROOT, WORK
from run_champi_comparison_capture import read, save


def status(state, **fields):
    save(WORK/'status.json', dict(state=state, captureOnly=True, **fields))


def compact(campaign, archive_root):
    # Reuse the established copy/checksum/receipt/delete workflow on local disk.
    # Source metadata stays available; raw imagery and frames live in run.json's
    # named pair. This avoids retaining both untrimmed MOV and battle MP4.
    import archive_champi_geometric as archive
    archive.OUT=Path(campaign['workDirectory'])
    archive.DEST=archive_root
    archive.JOB_PREFIX='knight_expansion_'+campaign['slug']+'_'
    archive.ARCHIVE_PREFIX='knight-expansion-'+campaign['slug'].removesuffix('_'+campaign['civilization'].lower()).replace('_','-')
    archive.CIVS=(campaign['civilization'].lower(),)
    archive.TITLE_PREFIX=campaign['unit']
    archive.PRESERVE_BASELINE=False
    archive.main()


def main():
    import msvcrt
    queue=read(WORK/'queue.json')
    completed=[]; failures=[]
    # Prevent duplicate queue supervisors, in addition to the recorder mutex.
    with (WORK/'queue.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        for campaign in queue['campaigns']:
            if (WORK/'PAUSE').exists() or (ROOT/'data/local/thermal/PAUSED.json').exists():
                status('PAUSED',completed=completed,failures=failures)
                return
            work=Path(campaign['workDirectory'])
            old=read(work/'capture/status.json') if (work/'capture/status.json').exists() else {}
            already_complete=old.get('completed')==campaign['total'] and not old.get('failed') and not old.get('pendingExports')
            status('CAPTURING',current=campaign,completed=completed,failures=failures,total=queue['total'])
            if not already_complete:
                with (work/'worker-output.log').open('a',encoding='utf-8') as stdout, (work/'worker-error.log').open('a',encoding='utf-8') as stderr:
                    result=subprocess.run([sys.executable,'-u',str(ROOT/'apps/video/run_camel_comparison_capture.py'),
                                           '--work',str(work)],cwd=ROOT,stdout=stdout,stderr=stderr)
                current=read(work/'capture/status.json') if (work/'capture/status.json').exists() else {}
                pilot=read(work/'pilot-validation.json') if (work/'pilot-validation.json').exists() else {}
                if result.returncode:
                    # Do not allow a bad pilot or system/UI fault to poison the
                    # rest of the queue. Isolated battle failures can be reviewed
                    # after other verified campaigns have made progress.
                    failures.append(dict(key=campaign['key'],state=current.get('state'),
                                         failed=[r for r in current.get('results',[]) if r['status']=='failed']))
                    if pilot.get('state')!='PASSED' or current.get('state')!='COMPLETE_WITH_FAILURES':
                        status('NEEDS_ATTENTION',current=campaign,completed=completed,failures=failures)
                        return
            status('COMPACTING',current=campaign,completed=completed,failures=failures)
            compact(campaign,Path(queue['archiveRoot']))
            current=read(work/'capture/status.json')
            completed.append(dict(key=campaign['key'],verified=current['completed'],total=campaign['total']))
        verified=sum(r['verified'] for r in completed)
        status('COMPLETE' if verified==queue['total'] else 'NEEDS_RETAKES',completed=completed,failures=failures,
               verified=verified,total=queue['total'])


if __name__=='__main__':
    try:
        main()
    except Exception:
        status('NEEDS_ATTENTION',error=traceback.format_exc())
        raise
