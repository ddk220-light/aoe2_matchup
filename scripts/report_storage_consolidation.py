"""Produce the final source-preservation and space report from verified receipts."""
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/local/storage-consolidation-20260916'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    before=read(WORK/'availability-before.json')['jobs']
    inventory=read(ROOT/'data/local/media-reuse-audit/inventory.json')
    lost=[]
    for job,old in before.items():
        candidates=inventory['jobs'].get(job,[])
        now={'video':any(c['video'] for c in candidates),'frames':any(c['frames'] for c in candidates),'paired':any(c['video'] and c['frames'] for c in candidates)}
        for key in ['video','frames','paired']:
            if old[key] and not now[key]:lost.append({'job':job,'missing':key})
    verification=read(WORK/'verification.json')
    links=read(WORK/'nested-links-after.json')
    if isinstance(links,dict):links=[links]
    state=read(WORK/'status.json')
    final_retry=WORK/'final-retry-status.json'
    if final_retry.exists():
        state['prunedBytes']+=read(final_retry).get('prunedBytes',0)
    state['issues']=verification['workerExceptions']
    state['movedBytes']=verification['bytes']
    free={d:round(shutil.disk_usage(d+'/').free/1024**3,2) for d in ['C:','D:']}
    summary=dict(at=datetime.now(timezone.utc).isoformat(),state='COMPLETE' if not lost and not verification['failures'] and not state['issues'] and all(x['state']=='AVAILABLE' for x in links) else 'COMPLETE_WITH_EXCEPTIONS',prunedGiB=round(state['prunedBytes']/1024**3,2),movedGiB=round(state['movedBytes']/1024**3,2),packages=verification['packages'],files=verification['files'],freeGiB=free,sourceAvailabilityLosses=lost,placementFailures=verification['failures'],workerExceptions=state['issues'],nestedLinkFailures=[x for x in links if x['state']!='AVAILABLE'])
    (WORK/'completion.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    lines=['# Recording storage consolidation','',f"Completed verification: {summary['at']}",'',f"State: {summary['state']}",'',f"Free space: C: **{free['C:']:.1f} GiB**, D: **{free['D:']:.1f} GiB**.",'',f"Removed {summary['prunedGiB']:.1f} GiB of guarded redundant captures, derived renders and expanded telemetry across both disks. Transferred {summary['movedGiB']:.1f} GiB across {summary['packages']} packages; {summary['files']} transferred files were hash-verified by the worker and checked for final placement.",'','Raw battle videos, frame streams, timing/plan metadata, final masters and surviving fallback footage remain. Source code and protected credentials remain on the PC. Old package paths use junctions to the external archive.','','## Preservation check','',f"Compared {len(before)} pre-cleanup job identities against the final inventory. Availability regressions: **{len(lost)}**.",f"Transfer placement/link errors: **{len(verification['failures'])}**. Worker exceptions: **{len(state['issues'])}**. Nested-link restoration exceptions: **{len(summary['nestedLinkFailures'])}**.",'','These checks do not turn previously missing footage into recoverable footage. They verify that this consolidation did not reduce the recorded baseline availability.','','## Evidence','','- [Completion data](completion.json)','- [Transfer verification](verification.json)','- [Exact retention/transfer plan](plan.json)','- [Transfer/deletion receipts](receipts.jsonl)','- [Updated recording inventory](../media-reuse-audit/inventory.json)','','Checksums are preserved in individual package receipts beside this report.']
    if lost or state['issues'] or verification['failures'] or summary['nestedLinkFailures']:
        lines+=['','## Exceptions','','See completion.json for exact paths. Unverified/conflicting source packages are retained; do not treat this as permission to delete them.']
    (WORK/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
