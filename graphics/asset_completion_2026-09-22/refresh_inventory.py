from pathlib import Path
import json, subprocess
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'asset-manifest.json').read_text())
units=manifest['units']; tracked=set(subprocess.check_output(['git','ls-files','-z','--','graphics/units','graphics/art'],cwd=ROOT,text=True).split('\0'))
files=sorted(p for folder in ('graphics/units','graphics/art') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix.lower() in ('.png','.gif','.webp','.jpg','.jpeg'))
folders=sorted(p for p in (ROOT/'graphics/units').iterdir() if p.is_dir() and any(f.parent==p for f in files))
def link(p,label=None):
    return f'[{label or p.name}](<{p.as_posix()}>)' if p.exists() else 'Pending'
def standard(s):
    d=ROOT/'graphics/units'/s
    return [(d/'icon.png','Icon'),(d/'icon_transparent.png','Transparent'),(d/f'{s}_idle_dir06.png','Native'),(d/f'{s}_idle_dir06_dat4x.png','DAT 4x'),(d/f'{s}_idle_dir06_ultrasharp4x.png','UltraSharp 4x'),(d/f'{s}_idle_dir06_dat4x_blue.png','Blue 4x'),(d/f'{s}_attack_dir06_dat4x.gif','GIF')]
missing=[]
for u in units:
    paths=standard(u['slug'])+[(ROOT/u['art_source'],'Art')]
    u['missing']=[label for p,label in paths if not p.exists()]
    u['complete']=not u['missing']
    if u['missing']:missing.append(u['label']+': '+', '.join(u['missing']))
reviewnotes=json.loads((HERE/'visual-review.json').read_text())['units']
for u in units:
    note=reviewnotes.get(u['slug'],'')
    u['visual_review_status']='owner-review-required' if 'OWNER REVIEW REQUIRED' in note else ('assistant-reviewed; owner approval pending' if note.startswith('Reviewed:') or note.startswith('Reviewed against') else 'existing asset or review pending')
(HERE/'asset-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
newfiles=[p for p in files if p.relative_to(ROOT).as_posix() not in tracked]
lines=['# Unit asset inventory — 2026-09-22','',f'{len(folders)} unit folders; {len(files)} image/GIF files in graphics/units and graphics/art. {len(files)-len(newfiles)} are Git-tracked; {len(newfiles)} are not Git-tracked, including any pre-existing local references. This completion batch has not been committed or published.','',f'Confirmed generation scope: 74 working-roster entries plus 10 new land-unit entries. {sum(u["complete"] for u in units)}/84 scoped units have all seven standard assets and a generated-art source.','', '## Working roster and new units','', 'Unit names open their folders. The seven standard assets are the game icon, transparent icon, native idle, DAT 4x idle, UltraSharp 4x idle, blue DAT 4x idle and DAT 4x attack GIF. The game icon is 256px; the upscaled image is the full-body sprite.','', 'Generated art reuses existing unit HD images or the established FLUX family-art collection where available. Shared family files retain their original names and are identified in the source column; this inventory does not relabel them as newly approved tier-specific artwork. War Chariot modes share the same DAT visual sources and generated artwork.','', 'Flemish Militia now uses the correct current DAT icon 354 for unit 1699. The previous incorrect icon pair is preserved in the working backup folder.','', '| Unit | Standard assets | Generated art | Source |','|---|---|---|---|']
for u in sorted(units,key=lambda x:(x['origin']!='new-game-data',x['label'])):
    s=u['slug']; art=ROOT/u['art_source']
    artlinks=link(art,'View artwork')
    if art.name.endswith('_idle_dir05_nobg.png'):
        stem=art.name.removesuffix('_nobg.png')
        artlinks=' · '.join(link(art.parent/f'{stem}_{kind}.png',label) for kind,label in [('bg','Background'),('nobg','Transparent'),('icon','Icon')])
        panel=HERE/'review'/f'{stem.removesuffix("_idle_dir05")}-review.jpg'
        if panel.exists():artlinks+=' · '+link(panel,'Reference comparison')
    lines.append('| '+link(ROOT/'graphics/units'/s,u['label'])+' | '+' · '.join(link(p,label) for p,label in standard(s))+' | '+artlinks+' | '+u['art_source_kind']+' |')
lines += ['', '## Remaining scoped gaps','']+(['- '+m for m in missing] if missing else ['None for standard assets and a generated-art source within the confirmed 84-unit scope.'])
flagged=[u['label'] for u in units if u['visual_review_status']=='owner-review-required']
if flagged:lines+=['','Visual fidelity still needs owner review: '+', '.join(flagged)+'. These candidates are present but are not golden.']
lines += ['', '## Generation records and review','',link(HERE/'README.md','Workflow, current DAT source, model settings and special animation cases')+' · '+link(HERE/'asset-manifest.json','Machine-readable asset manifest')+' · '+link(HERE/'sprite-validation.json','Standard asset validation'),'', 'New generated art is available for owner review. Git tracking and file presence are distinct from owner visual approval.','', '## All unit folders','', 'A dash denotes an absent optional file outside the scoped completion work.','', '| Unit folder | Game icon | Transparent icon | Native idle | DAT 4x | UltraSharp 4x | Blue DAT 4x | Attack GIF | Unit HD art |','|---|---|---|---|---|---|---|---|---|']
listed=set()
for d in folders:
    s=d.name; cells=[]
    for p,label in standard(s)+[(d/f'{s}_flux_hd.png','HD art')]:
        cells.append(link(p,label) if p.exists() else '—')
        if p.exists():listed.add(p)
    lines.append('| '+link(d,s.replace('_',' ').title())+' | '+' | '.join(cells)+' |')
lines += ['', '## Generated FLUX.2 sets','', '| Art slug | Background render | Transparent render | 256px generated icon |','|---|---|---|---|']
artdir=ROOT/'graphics/art/flux2_hybrid'
for bg in sorted(artdir.glob('*_idle_dir05_bg.png')):
    s=bg.name.removesuffix('_idle_dir05_bg.png'); paths=[(bg,'Background'),(artdir/f'{s}_idle_dir05_nobg.png','Transparent'),(artdir/f'{s}_idle_dir05_icon.png','Icon')]
    lines.append('| '+s+' | '+' | '.join(link(p,label) for p,label in paths)+' |')
    listed.update(p for p,_ in paths if p.exists())
lines += ['', '## Explicit golden images and other art references','']
for p in files:
    if p not in listed: lines.append('- '+link(p)); listed.add(p)
assert listed==set(files)
(ROOT/'graphics/ASSET_INVENTORY_2026-09-22.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'folders':len(folders),'images':len(files),'untracked_files':len(newfiles),'complete_scoped_units':sum(u['complete'] for u in units),'scoped_units':len(units),'gaps':missing},indent=2))
