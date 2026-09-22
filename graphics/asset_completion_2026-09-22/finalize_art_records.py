"""Collect generation evidence, image checks, and local review montages."""
from pathlib import Path
import json, shutil
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.scratch/asset-completion'
slugs=sorted(json.loads((HERE/'art-descriptions.json').read_text()))
review=HERE/'review'; review.mkdir(exist_ok=True)
records=HERE/'generation'; records.mkdir(exist_ok=True)
results=[]
for s in slugs:
    paths={kind:ROOT/f'graphics/art/flux2_hybrid/{s}_idle_dir05_{kind}.png' for kind in ('bg','nobg','icon')}
    if not all(p.exists() for p in paths.values()):continue
    result={'slug':s,'checks':{},'owner_approval':'pending'}
    for kind,p in paths.items():
        with Image.open(p) as im:
            im.load()
            assert im.width>0 and im.height>0
            check={'path':p.relative_to(ROOT).as_posix(),'size':list(im.size),'mode':im.mode}
            if kind!='bg':
                assert im.mode=='RGBA'
                extrema=im.getchannel('A').getextrema()
                assert extrema[0]==0 and extrema[1]==255
                check['alpha_extrema']=list(extrema)
            if kind=='icon':assert im.size==(256,256)
            result['checks'][kind]=check
    results.append(result)
    for suffix in ('review','detail'):
        source=WORK/f'{s}-{suffix}.jpg'
        if source.exists():shutil.copy2(source,review/f'{s}-{suffix}.jpg')
    source=WORK/f'{s}-generation.json'
    if source.exists():shutil.copy2(source,records/source.name)

for start in range(0,len(results),5):
    batch=results[start:start+5]
    sheet=Image.new('RGB',(1100,len(batch)*560),(60,61,65)); draw=ImageDraw.Draw(sheet)
    for row,result in enumerate(batch):
        s=result['slug']; draw.text((20,row*560+12),s.replace('_',' ').title(),fill='white')
        for col,p in enumerate([ROOT/f'graphics/units/{s}/icon.png',ROOT/result['checks']['nobg']['path']]):
            im=Image.open(p).convert('RGBA'); im.thumbnail((500,515),Image.Resampling.LANCZOS)
            sheet.paste(im,(col*550+(550-im.width)//2,row*560+38+(515-im.height)//2),im)
    sheet.save(review/f'batch-{start//5+1}.jpg',quality=93)
(HERE/'art-validation.json').write_text(json.dumps({'expected_sets':len(slugs),'complete_sets':len(results),'results':results},indent=2))
notes=json.loads((HERE/'visual-review.json').read_text())['units']
lines=['# Generated artwork review','',f'{len(results)} of {len(slugs)} requested new art sets are present. These are local review candidates; owner approval is pending.','', '## Comparison sheets','']
flagged=[s for s,note in notes.items() if 'OWNER REVIEW REQUIRED' in note]
if flagged:
    lines[3:3]=['','## Remaining visual fidelity issues','']+[f'- **{s.replace("_"," ").title()}**: {notes[s]}' for s in flagged]+['']
for p in sorted(review.glob('batch-*.jpg')):
    lines.append(f'- [Icon versus generated artwork: {p.stem}](<{p.as_posix()}>)')
lines+=['','## Per-unit references and checks','','| Unit | Full comparison | Equipment detail | Review |','|---|---|---|---|']
for result in results:
    s=result['slug']
    panel=review/f'{s}-review.jpg'; detail=review/f'{s}-detail.jpg'
    links=[f'[View](<{p.as_posix()}>)' if p.exists() else 'Pending' for p in (panel,detail)]
    lines.append('| '+s.replace('_',' ').title()+' | '+' | '.join(links)+' | '+notes.get(s,'Reference review pending.')+' |')
lines+=['','## Earlier alternatives for revised units','']
for s in ('heavy_mounted_crossbowman','savar'):
    variants=[]
    for number,folder in [(1,'superseded-first-renders'),(2,'superseded-second-render')]:
        p=WORK/folder/f'{s}_idle_dir05_bg.png'
        if p.exists():variants.append(f'[Attempt {number}](<{p.as_posix()}>)')
    lines.append('- '+s.replace('_',' ').title()+': '+' · '.join(variants))
(HERE/'REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f'Validated {len(results)}/{len(slugs)} generated sets; review sheets and generation records saved.')
