"""Produce a bounded duplicate-media deletion plan after compact-copy verification."""
import json
from pathlib import Path
from compact_recording_archive import read, digest

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'data/local/compact-storage'

def main():
    capture=read(ROOT/'data/local/champi-standard-comparison/capture/status.json')
    if capture['state']!='COMPLETE' or capture['completed']!=296 or capture['failed']:
        raise ValueError('Capture campaign must be fully verified and stopped')
    if not read(WORK/'restore-validation.json')['perUnitTimelineAndTimingMatch']:
        raise ValueError('Compact restore validation required')
    deletions=[]
    for civ in ('incas','mapuche','muisca','tupi'):
        folder=Path('D:/AoE2 Renders')/('champi-standard-'+civ)
        index=read(folder/'run.json')
        if len(index['matchups'])!=74:raise ValueError('Incomplete archive')
        for row in index['matchups']:
            run=ROOT/'aoe2x/js_simulation/calibration/lab/runs'/row['jobId']/'live/run_001'
            if not row['jobId'].startswith('champi_standard_'+civ+'_'):raise ValueError('Unexpected job')
            proofs=[]
            for short in ('battle.mp4','frames.bin'):
                entry=row['files'][short];target=(folder/entry['path']).resolve()
                if not target.is_relative_to(folder.resolve()) or target.stat().st_size!=entry['bytes'] or digest(target)!=entry['sha256']:
                    raise ValueError('Archive verification failed')
                proofs.append(dict(path=str(target),bytes=entry['bytes'],sha256=entry['sha256']))
            for key in ('video','battleVideo','frames'):
                entry=row['recording']['files'][key];source=(run/entry['path']).resolve()
                if not source.is_relative_to(run.resolve()):raise ValueError('Source escaped run')
                if not source.exists():continue
                if source.stat().st_size!=entry['bytes'] or digest(source)!=entry['sha256']:
                    raise ValueError('Source changed')
                deletions.append(dict(source=str(source),bytes=entry['bytes'],sha256=entry['sha256'],replacements=proofs,jobId=row['jobId']))
        print(civ,'verified',flush=True)
    value=dict(state='READY_FOR_REVIEW',files=deletions,bytes=sum(r['bytes'] for r in deletions),recursiveDelete=False)
    (WORK/'champi-media-cleanup-plan.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(len(deletions),'files;',round(value['bytes']/2**30,2),'GiB',flush=True)

if __name__=='__main__':main()
