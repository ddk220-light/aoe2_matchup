from pathlib import Path
import json, sys, os
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'.scratch/asset-completion'
os.environ['NUMBA_CACHE_DIR']=str(WORK/'numba-cache')
(WORK/'numba-cache').mkdir(exist_ok=True)
from rembg import new_session, remove
ART=ROOT/'graphics/art/flux2_hybrid'
slugs=sys.argv[1:] or json.loads((WORK/'art-targets.json').read_text())
session=None
for s in slugs:
    bg=ART/f'{s}_idle_dir05_bg.png'; cut=ART/f'{s}_idle_dir05_nobg.png'; icon=ART/f'{s}_idle_dir05_icon.png'
    if not bg.exists(): continue
    if not cut.exists():
        if session is None: session=new_session('isnet-general-use',providers=['CPUExecutionProvider'])
        im=remove(Image.open(bg).convert('RGB'),session=session).convert('RGBA')
        im=im.crop(im.getbbox()); im.save(cut)
        print('CUT',s,flush=True)
    if not icon.exists():
        im=Image.open(cut).convert('RGBA'); im.thumbnail((246,246),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(256,256)); canvas.alpha_composite(im,((256-im.width)//2,(256-im.height)//2)); canvas.save(icon)
    # Full-size comparison: sprite, icon, generated cutout, preserving detail for review.
    sheet=Image.new('RGB',(1800,1100),(60,61,65)); draw=ImageDraw.Draw(sheet)
    for col,(label,p) in enumerate([('DAT sprite',WORK/f'{s}_dir05.png'),('Game icon',ROOT/'graphics/units'/s/'icon.png'),('FLUX.2 transparent',cut)]):
        draw.text((col*600+15,12),s+' / '+label,fill='white')
        im=Image.open(p).convert('RGBA'); scale=min(570/im.width,1024/im.height)
        im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST if col==0 else Image.Resampling.LANCZOS)
        sheet.paste(im,(col*600+(600-im.width)//2,50+(1024-im.height)//2),im)
    sheet.save(WORK/f'{s}-review.jpg',quality=92)
print('Available complete art sets',sum((ART/f'{s}_idle_dir05_icon.png').exists() for s in slugs),'/',len(slugs),flush=True)
