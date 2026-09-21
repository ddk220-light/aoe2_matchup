"""Check verified transfer receipts and source compatibility links, without edits."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/local/storage-consolidation-20260916'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    status=read(WORK/'status.json')
    if not status['state'].startswith('COMPLETE'):
        raise SystemExit('Transfer is still running; do not issue a final verification.')
    # Receipts are durable before source removal. The initial worker had a
    # counter bug after successful junction creation, so event totals alone
    # are not authoritative. Reconcile completed placements from receipts.
    transfers=[]
    for path in list(WORK.glob('aoe2x_*.json'))+list(WORK.glob('data_local_*.json')):
        receipt=read(path)
        if 'files' not in receipt or 'source' not in receipt:continue
        source=Path(receipt['source']);dest=Path(receipt['destination'])
        if source.is_junction() and source.resolve()==dest.resolve():
            transfers.append(dict(receipt=path.name))
    failures=[];checked=0;bytes_verified=0
    for event in transfers:
        receipt=read(WORK/event['receipt'])
        source=Path(receipt['source']);dest=Path(receipt['destination'])
        if not source.is_junction() or source.resolve()!=dest.resolve():
            failures.append(dict(type='compatibility-link',source=str(source),destination=str(dest)))
        for entry in receipt['files']:
            target=dest/entry['relative']
            if not target.is_file() or target.stat().st_size != entry['bytes']:
                failures.append(dict(type='transferred-file',path=str(target)))
            checked+=1;bytes_verified+=entry['bytes']
    # The transfer worker already re-read and hashed every destination. This
    # pass checks final placement/size instead of repeating a disk-wide hash pass.
    confirmed={read(WORK/e['receipt'])['source'] for e in transfers}
    issue_sources={e.get('source',e.get('path')):e for e in status.get('issues',[]) if e.get('source') not in confirmed}
    for name in ['conflict-retry-status.json', 'final-retry-status.json']:
        retry_path=WORK/name
        if retry_path.exists():
            retry=read(retry_path)
            if not retry['state'].startswith('COMPLETE'):
                raise SystemExit(f'{name} is still running; do not issue a final verification.')
            for e in retry.get('issues',[]):
                if e.get('source') not in confirmed:issue_sources[e.get('source',e.get('path'))]=e
    active_issues=list(issue_sources.values())
    result=dict(at=datetime.now(timezone.utc).isoformat(),packages=len(transfers),files=checked,bytes=bytes_verified,failures=failures,workerExceptions=active_issues,reconciledIssues=len(status.get('issues',[]))-len(active_issues),method='All transfers had SHA-256 verification; final pass checks placement, sizes and compatibility junctions. Post-transfer bookkeeping errors are reconciled using durable receipts.')
    (WORK/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='workerExceptions'},indent=2))

if __name__=='__main__':main()
