"""One bounded retake pass after the main ordered capture queue releases the game."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from aoe2x.lab.io import read_json, write_json, utc_now
from continue_capture_queue import ROOT, LAB, OUT, FINISHED, paused, load


def ready(controller, campaign, is_paused):
    return (not is_paused and controller.get('state') == 'ALL_CAPTURES_FINISHED'
            and campaign.get('state') in FINISHED)


def main():
    import msvcrt
    OUT.mkdir(exist_ok=True)
    with (OUT/'retakes.lock').open('a+b') as lock:
        lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        state={'pid':os.getpid(),'state':'WAITING_FOR_MAIN_CAPTURE','startedAt':utc_now()}
        def save(label, **values):
            state.update(state=label,updatedAt=utc_now(),**values)
            write_json(OUT/'retakes.json',state)
        ledger_path=OUT/'deferred-retakes.json'
        while load(OUT/'capture.json').get('state') != 'ALL_CAPTURES_FINISHED' or paused():
            save('WAITING_FOR_MAIN_CAPTURE'); time.sleep(3)
        # Reload here to include failures added while the main queue was running.
        ledger=read_json(ledger_path)
        manifests=list(dict.fromkeys(j['manifest'] for j in ledger['jobs'] if j['state']=='pending'))
        for manifest in manifests:
            name=Path(manifest).stem.removeprefix('aoe2lab.recorder.')
            report=LAB/'campaigns'/name
            while not ready(load(OUT/'capture.json'),load(report/'status.json'),paused()):
                current=load(report/'status.json')
                if current.get('state') in {'CRASHED','STOPPED_AFTER_ERRORS','STOPPED'}:
                    save('NEEDS_ATTENTION',manifest=manifest,error='Recorder requires inspection before retake.')
                    return 2
                save('WAITING_FOR_EXPORTS',manifest=manifest); time.sleep(3)
            jobs=[j for j in ledger['jobs'] if j['manifest']==manifest and j['state']=='pending']
            for job in jobs:
                run=LAB/'runs'/job['jobId']
                backup=run/'retake-evidence'/utc_now().replace(':','-')
                backup.mkdir(parents=True,exist_ok=True)
                for source in [run/'failure.json', *(run/'live/run_001').glob('failure_attempt_*'),
                               *(run/'live/run_001').glob('capture_attempt_*.log')]:
                    if source.is_file():shutil.copy2(source,backup/source.name)
                job['evidenceBackup']=str(backup)
            write_json(ledger_path,ledger)
            if paused():
                save('PAUSED'); return 2
            with (report/'deferred-retake.stdout.log').open('a',encoding='utf-8') as out, (report/'deferred-retake.stderr.log').open('a',encoding='utf-8') as err:
                worker=subprocess.Popen([sys.executable,'-u','-m','aoe2x.lab.recording_campaign',
                    str(ROOT/manifest),'--reports',str(report)],cwd=ROOT,stdout=out,stderr=err)
                save('RETAKING',manifest=manifest,workerPid=worker.pid)
                code=worker.wait()
            result=load(report/'status.json')
            statuses={r['jobId']:r['status'] for r in result.get('results',[])}
            for job in jobs:
                job.update(state='complete' if statuses.get(job['jobId'])=='verified' else 'needs_review',
                           attemptedAt=utc_now())
            write_json(ledger_path,ledger)
            if code not in (0,2) or result.get('state') not in FINISHED:
                save('NEEDS_ATTENTION',manifest=manifest,exitCode=code); return 2
        failed=[j['jobId'] for j in ledger['jobs'] if j['state']!='complete']
        save('COMPLETE_WITH_ERRORS' if failed else 'COMPLETE',unresolved=failed)
        return 2 if failed else 0


if __name__=='__main__':
    raise SystemExit(main())
