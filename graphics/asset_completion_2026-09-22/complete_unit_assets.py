"""Fill only missing working-roster assets using current DAT graphic references."""
from pathlib import Path
import json, re, sys, time, shutil
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'graphics/units'),str(ROOT/'graphics')]
from PIL import Image
import sld_decode as D
from build_unit_assets import save_icon, decode_red, SPRITE_TINT_BLUE
from build_idle_refs import idle_assets
from build_gifs_upscaled import union_crop
from finalize_units import transparent_gif
from upscale_refs import MODELS, upscale_rgba_single
from spandrel import ModelLoader

DAT=json.loads((ROOT/'.scratch/current-asset-dat.json').read_text())
BY={u['id']:u for u in DAT['units']}
GAME=Path('D:/SteamLibrary/steamapps/common/AoE2DE')
WORK=ROOT/'.scratch/asset-completion'; WORK.mkdir(exist_ok=True)
def slug(name): return re.sub('[^a-z0-9]+','_',name.lower()).strip('_')
def source(g):
    stub=re.sub('_x[12]$','',g['file_name'])
    for res in ('x2','x1'):
        p=GAME/'resources/_common/drs/graphics'/f'{stub}_{res}.sld'
        if p.exists(): return p
    raise FileNotFoundError(g['file_name'])
roster=json.loads((ROOT/'data/unique-unit-roster.json').read_text())['units']
jobs=[dict(slug=u['scenarioKey'],label=u['label'],master=u['master'],origin='working-roster') for u in roster]
jobs += [dict(slug=slug(u['name']),label=u['name'],master=u['id'],origin='new-game-data') for u in DAT['units'] if 2700<=u['id']<=2712]
for j in jobs:
    u=BY[j['master']]; j['icon_id']=u['icon']; j['idle_source']=str(source(u['idle'])); j['attack_source']=str(source(u['attack']))
    j['attack_graphic']=u['attack']; j['idle_graphic']=u['idle']
(WORK/'jobs.json').write_text(json.dumps(dict(dat=DAT['dat'],sha256=DAT['sha256'],units=jobs),indent=2))
mode=sys.argv[1] if len(sys.argv)>1 else 'prepare'
if mode=='prepare':
    for j in jobs:
        s=j['slug']; dest=ROOT/'graphics/units'/s; dest.mkdir(exist_ok=True)
        if not (dest/'icon.png').exists() and not (dest/'icon_transparent.png').exists(): save_icon(j['icon_id'],str(dest/'icon.png'))
        data=Path(j['idle_source']).read_bytes(); _,fs=D.parse(data); n=len(fs)//16
        pose=D._finish(decode_red(data,fs[5*n]),crop=True,margin=4)
        pose.save(WORK/f'{s}_dir05.png')
        print('REFERENCE',s,flush=True)
elif mode=='sprites':
    models={k:ModelLoader().load_from_file(p).to('cuda').eval() for k,p in MODELS.items()}
    completed={}
    for j in jobs:
        s=j['slug']; dest=ROOT/'graphics/units'/s
        expected=['icon.png','icon_transparent.png',f'{s}_idle_dir06.png',f'{s}_idle_dir06_dat4x.png',f'{s}_idle_dir06_ultrasharp4x.png',f'{s}_idle_dir06_dat4x_blue.png',f'{s}_attack_dir06_dat4x.gif']
        missing=[n for n in expected if not (dest/n).exists()]
        if not missing: continue
        key=(j['idle_source'],j['attack_source'],j['icon_id'])
        if key in completed:
            prev=completed[key]
            for name in missing:
                src=ROOT/'graphics/units'/prev/name.replace(s,prev)
                if src.exists(): shutil.copy2(src,dest/name)
            print('REUSED_IDENTICAL_DAT',s,prev,flush=True); continue
        started=time.time(); print('START',s,missing,flush=True)
        if any('_idle_' in n for n in missing):
            native,ref=idle_assets(j['idle_source'])
            if not (dest/f'{s}_idle_dir06.png').exists(): native.save(dest/f'{s}_idle_dir06.png')
            for model in ('dat4x','ultrasharp4x'):
                p=dest/f'{s}_idle_dir06_{model}.png'
                if not p.exists(): upscale_rgba_single(ref,models[model]).save(p)
            p=dest/f'{s}_idle_dir06_dat4x_blue.png'
            if not p.exists():
                _,ref=idle_assets(j['idle_source'],tint=SPRITE_TINT_BLUE)
                upscale_rgba_single(ref,models['dat4x']).save(p)
        p=dest/f'{s}_attack_dir06_dat4x.gif'
        if not p.exists():
            data=Path(j['attack_source']).read_bytes(); _,fs=D.parse(data); n=len(fs)//16
            frames=[decode_red(data,f) for f in fs[6*n:7*n]]
            frames=union_crop([f for f in frames if f is not None])
            up=[]
            for i,frame in enumerate(frames):
                up.append(upscale_rgba_single(frame,models['dat4x']))
                if i%10==0: print('FRAME',s,i+1,'/',len(frames),flush=True)
            transparent_gif(up,str(p),55)
        assert all((dest/n).exists() for n in expected)
        completed[key]=s
        print('DONE',s,round(time.time()-started,1),'seconds',flush=True)
