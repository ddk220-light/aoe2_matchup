"""Read-only media inventory. Presence/size checks, not a fresh checksum audit."""
import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/local/media-reuse-audit'
ROOTS = [Path('D:/AoE2 Renders'), ROOT / 'aoe2x/js_simulation/calibration/lab', ROOT / 'data/local', Path('C:/Users/ddk22/Videos/aoe2_matchups')]

def read(p):
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None

def main():
    files, indexes, recordings, manifests, uploads = {}, [], [], [], []
    errors = []
    for root in ROOTS:
        for directory, dirs, names in os.walk(root, followlinks=False, onerror=lambda e: errors.append(str(e))):
            dirs[:] = [d for d in dirs if d not in {'.venv', 'node_modules', '.git', '__pycache__', 'media-reuse-audit', 'code-quality-deps', 'cost-audit-deps'} and not (Path(directory)/d).is_symlink() and not (Path(directory)/d).is_junction()]
            for name in names:
                p = Path(directory) / name
                if name.lower().endswith(('.mp4', '.mov', '.mkv', '.bin')):
                    try:
                        files[str(p)] = p.stat().st_size
                    except OSError as e:
                        errors.append(str(e))
                elif name in {'run.json', 'recording.json', 'manifest.json'} or 'upload' in name and name.endswith('.json'):
                    obj = read(p)
                    if not isinstance(obj, dict):
                        continue
                    if obj.get('kind') == 'aoe2lab.compact-archive':
                        indexes.append((p, obj))
                    if name == 'recording.json' and obj.get('jobId'):
                        recordings.append((p, obj))
                    for key in ['chapters', 'results']:
                        if isinstance(obj.get(key), list) and obj[key] and obj[key][0].get('jobId'):
                            manifests.append((p, dict(obj, captureRows=obj[key])))
                            break
                    if obj.get('videoId') and (obj.get('title') or obj.get('videoUrl')):
                        uploads.append(dict(path=str(p), **{k: obj.get(k) for k in ['videoId','title','kind','state','preparation','subject']}))
    by_job = defaultdict(list)
    for p, obj in indexes:
        for row in obj.get('matchups', []):
            assets = row.get('files', {})
            resolved = {key: p.parent / entry['path'] for key,entry in assets.items()}
            ok = {key: str(path) in files and files[str(path)] == assets[key]['bytes'] for key,path in resolved.items()}
            by_job[row['jobId']].append(dict(source=str(p), format='compact', video=ok.get('battle.mp4',False), frames=ok.get('frames.bin',False), paths={k:str(v) for k,v in resolved.items()}))
    for p,obj in recordings:
        assets = obj.get('files',{})
        resolved = {key:p.parent/entry['path'] for key,entry in assets.items() if key in {'battleVideo','video','frames'} and isinstance(entry,dict) and entry.get('path')}
        ok = {key: str(path) in files and files[str(path)] > 0 and (not assets[key].get('bytes') or files[str(path)] == assets[key]['bytes']) for key,path in resolved.items()}
        by_job[obj['jobId']].append(dict(source=str(p),format='recording',video=ok.get('battleVideo',False) or ok.get('video',False),battleVideo=ok.get('battleVideo',False),untrimmedVideo=ok.get('video',False),frames=ok.get('frames',False),paths={k:str(v) for k,v in resolved.items()}))
    episodes = []
    for p,obj in manifests:
        rows=[]
        for ch in obj['captureRows']:
            candidates=by_job.get(ch['jobId'],[])
            rows.append(dict(jobId=ch['jobId'],title=ch.get('title'),paired=any(c['video'] and c['frames'] for c in candidates),video=any(c['video'] for c in candidates),frames=any(c['frames'] for c in candidates)))
        episodes.append(dict(manifest=str(p),total=len(rows),paired=sum(r['paired'] for r in rows),videos=sum(r['video'] for r in rows),frames=sum(r['frames'] for r in rows),rows=rows))
    report=dict(at=datetime.now(timezone.utc).isoformat(),method='Nonempty files and declared sizes checked; no new full checksum/decode pass.',roots=[str(r) for r in ROOTS],errors=errors,uploads=uploads,episodes=episodes,jobs=by_job,files=files,archives=[dict(path=str(p),total=len(o['matchups']),paired=sum(any(c['video'] and c['frames'] for c in by_job[r['jobId']]) for r in o['matchups'])) for p,o in indexes])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'inventory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(files=len(files),jobs=len(by_job),archives=report['archives'],episodes=[{k:v for k,v in e.items() if k!='rows'} for e in episodes],uploads=uploads,errors=errors),indent=2))

if __name__=='__main__':
    main()
