"""Run the approved Monaspa capture pass after Flemish publication, with thermal checks."""
import subprocess, sys, time
from finish_pending_production import ROOT, LAB, read, write, pause_check

def main():
    receipt=LAB/'compilations/flemish-militia-unique-units/upload-completion.json'
    print('Waiting for Flemish publication to complete',flush=True)
    while not receipt.exists() or read(receipt)['state']!='COMPLETE':
        pause_check()
        current=read(ROOT/'data/local/flemish-production-status.json')
        if current['state']=='NEEDS_ATTENTION': raise RuntimeError('Flemish publisher requires attention')
        time.sleep(20)
    print('Flemish complete; starting Elite Monaspa captures',flush=True)
    report=LAB/'campaigns/elite-monaspa-all-unique'
    if (report/'status.json').exists() and read(report/'status.json')['state']=='COMPLETE':return
    pause_check()
    q=read(ROOT/'data/video-production-queue.json')
    e=next(x for x in q['episodes'] if x['key']=='elite-monaspa')
    e.update(status='capturing',startedAt=time.time(),recordingReports=str(report))
    write(ROOT/'data/video-production-queue.json',q)
    previous=read(report/'status.json') if (report/'status.json').exists() else {}
    verified=[r for r in previous.get('results',[]) if r['status']=='verified']
    done={r['jobId'] for r in verified}
    manifest=read(ROOT/e['manifest'])
    manifest['matchups']=[r for r in manifest['matchups'] if r['id'] not in done]
    pending=ROOT/'data/local/elite-monaspa-pending.json';write(pending,manifest)
    active_report=report/'resume-pending'
    write(ROOT/'data/local/elite-monaspa-resume-baseline.json',previous)
    p=subprocess.Popen([sys.executable,'-u','-m','aoe2x.lab.recording_campaign',str(pending),'--reports',str(active_report)],cwd=ROOT)
    while p.poll() is None:
        time.sleep(10);pause_check()
    q=read(ROOT/'data/video-production-queue.json');e=next(x for x in q['episodes'] if x['key']=='elite-monaspa')
    result=read(active_report/'status.json')
    result['results']=verified+result['results'];result['total']=73
    result['manifest']=str(ROOT/e['manifest'])
    from aoe2x.lab.recording_campaign import checkpoint
    checkpoint(report,result,report=True)
    e.update(status='captures_complete' if p.returncode==0 else 'capture_needs_attention',verifiedRecordings=result.get('completed',0),failedRecordings=result.get('failed',0))
    write(ROOT/'data/video-production-queue.json',q)
    print('Monaspa capture finished:',result['state'],flush=True)
    sys.exit(p.returncode)

if __name__=='__main__': main()
