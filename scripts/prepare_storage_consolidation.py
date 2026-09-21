"""Prepare an explicit, reviewable retention/transfer plan; does not delete files."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
DEST = Path('D:/AoE2 Renders')
WORK = ROOT / 'data/local/storage-consolidation-20260916'

def read(p):
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None

def walk(root):
    for base, ds, fs in os.walk(root):
        ds[:] = [d for d in ds if d not in {'.venv', 'node_modules', '__pycache__', 'code-quality-deps', 'cost-audit-deps'} and not (Path(base)/d).is_junction() and not (Path(base)/d).is_symlink()]
        for f in fs:
            yield Path(base)/f

def main():
    WORK.mkdir(parents=True, exist_ok=True)
    files = list(walk(LAB)) + list(walk(ROOT/'data/local')) + list(walk(DEST))
    sizes = {}
    for p in files:
        try:
            sizes[str(p)] = p.stat().st_size
        except OSError:
            pass
    prunes, external_jobs = [], {}
    for p in files:
        if p.name != 'recording.json':
            continue
        o = read(p)
        if not isinstance(o, dict) or o.get('overlayApplied') is not False:
            continue
        entries = o.get('files', {})
        if str(p).startswith('D:'):
            external_jobs[o['jobId']] = str(p.parents[2])
        def valid(key):
            e = entries.get(key,{})
            path = p.parent / e.get('path','__missing__')
            return (path, e) if sizes.get(str(path),-1) == e.get('bytes',-2) and e.get('sha256') else None
        frame, battle, original = valid('frames'), valid('battleVideo'), valid('video')
        if frame:
            expanded = p.parent/'unit-hp-overlay/units.json'
            if str(expanded) in sizes:
                prunes.append(dict(path=str(expanded),bytes=sizes[str(expanded)],reason='Expanded HP telemetry; retained frames recreate it',guards=[{**frame[1],'path':str(frame[0])}]))
        if frame and battle and original and original[0].suffix == '.mov' and (p.parent/'battle.hp.json').is_file():
            prunes.append(dict(path=str(original[0]),bytes=sizes[str(original[0])],reason='Untrimmed capture duplicate; clean battle MP4, frames and timing retained',guards=[{**e,'path':str(path)} for path,e in [frame,battle]]))
    # Derived comparison renders are safe to discard only with all source archives present.
    families = {
        'champi': [DEST/f'champi-geometric-{c}/run.json' for c in ['incas','mapuche','muisca','tupi']],
        'paladin': [DEST/f'paladin-line-{c}/run.json' for c in ['franks','teutons','lithuanians','persians']],
        'cavalier': [DEST/f'cavalier-{c}/run.json' for c in ['bulgarians','poles','burmese','sicilians']],
    }
    guards = {}
    for family, indexes in families.items():
        checks=[]
        for index in indexes:
            o=read(index)
            if not o or not o.get('matchups'):
                raise ValueError(f'Missing source archive {index}')
            for row in o['matchups']:
                for entry in row['files'].values():
                    target=index.parent/entry['path']
                    if sizes.get(str(target)) != entry['bytes']:
                        raise ValueError(f'Archive size mismatch {target}')
            checks.append(str(index))
        guards[family]=checks
    comparison_roots = {
        ROOT/'data/local/champi-comparison-full':('champi',None),
        ROOT/'data/local/champi-overlay-v3':('champi','Champi_Four_Civs_Complete_With_Intro.mp4'),
        ROOT/'data/local/champi-comparison-first-five':('champi',None),
        ROOT/'data/local/champi-comparison-overlay-v2':('champi',None),
        ROOT/'data/local/paladin-comparison-full':('paladin','Paladin_Four_Civs_Complete_With_Intro.mp4'),
        DEST/'cavalier-four-civs-production':('cavalier','Cavalier_Four_Civs_Complete_With_Intro.mp4'),
    }
    for base,(family,keep) in comparison_roots.items():
        for p in files:
            if not p.is_relative_to(base):
                continue
            rel=p.relative_to(base)
            # Raw materialized sources remain subject to verified transfer; only renders/cache here.
            is_render=p.suffix=='.mp4' and 'render-workspace' not in rel.parts and 'rebuild' not in rel.parts and p.name!='battle.mp4'
            is_timeline=p.name=='timeline.json'
            if (is_render or is_timeline) and p.name!=keep:
                prunes.append(dict(path=str(p),bytes=sizes.get(str(p),0),reason='Regenerable comparison render/cache; archived raw sources retained',guards=[],archiveGuards=guards[family]))
    # Never move credentials, source code, or environment dependencies.
    moves=[]
    for source in (LAB/'runs').iterdir():
        if not source.is_dir() or source.is_junction() or source.is_symlink():continue
        group=re.split(r'_unique_|_\d\d_',source.name)[0].replace('_','-')
        target=Path(external_jobs.get(source.name,str(DEST/group/'captures'/source.name)))
        moves.append(dict(source=str(source),destination=str(target)))
    for category in ['compilations','campaigns','shorts','analysis','recording-retakes']:
        for source in (LAB/category).iterdir() if (LAB/category).is_dir() else []:
            if source.is_dir() and not source.is_junction() and not source.is_symlink():
                moves.append(dict(source=str(source),destination=str(DEST/source.name/category)))
    special={
        'paladin-comparison-full':'paladin-four-civs-production',
        'champi-overlay-v3':'champi-four-civs-production',
        'comp4-champi-all-unique':'champi-four-arena-experiment',
    }
    for source in (ROOT/'data/local').iterdir():
        if not source.is_dir() or source.is_junction() or source.is_symlink() or source.name.startswith(('storage-','youtube','media-reuse','code-quality','cost-audit')):continue
        prefix=str(source)+'\\'
        size=sum(n for s,n in sizes.items() if s.startswith(prefix))
        if size>100_000_000:
            moves.append(dict(source=str(source),destination=str(DEST/special.get(source.name,source.name)/'production')))
    prunes=list({p['path']:p for p in prunes}.values())
    removed={p['path'] for p in prunes}
    retained_totals={}
    for s,n in sizes.items():
        if s in removed:continue
        for parent in Path(s).parents:
            key=str(parent)
            retained_totals[key]=retained_totals.get(key,0)+n
    for row in moves:
        row['bytes']=retained_totals.get(row['source'],0)
    # Preserve raw captures and final videos before expendable simulation traces.
    moves.sort(key=lambda m: ('campaigns' in m['source'] or 'analysis' in m['source'], 'compilations' in m['source'], -m['bytes']))
    plan=dict(sourceRoot=str(ROOT),destinationRoot=str(DEST),prunes=prunes,moves=moves,reserveBytes=4*1024**3)
    (WORK/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    print(json.dumps(dict(pruneFiles=len(prunes),pruneGB={drive:round(sum(p['bytes'] for p in prunes if p['path'].startswith(drive))/1e9,2) for drive in ['C:','D:']},moveGB=round(sum(m['bytes'] for m in moves)/1e9,2),packages=len(moves)),indent=2))

if __name__=='__main__':main()
