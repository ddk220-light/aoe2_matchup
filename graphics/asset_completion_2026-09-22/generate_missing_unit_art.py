"""Documented two-reference FLUX.2 workflow; never replace an existing render."""
from pathlib import Path
import json, sys, time, os
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'.scratch/asset-completion'
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import torch
from PIL import Image
from diffusers import Flux2Pipeline
descriptions=json.loads((WORK/'art-descriptions.json').read_text())
slugs=sys.argv[1:] or sorted(descriptions)
dest=ROOT/'graphics/art/flux2_hybrid'
todo=[s for s in slugs if not (dest/f'{s}_idle_dir05_bg.png').exists()]
if not todo: print('All requested renders exist'); sys.exit(0)
print('Loading documented FLUX.2-dev NF4 model',flush=True)
pipe=Flux2Pipeline.from_pretrained(str(ROOT/'.scratch/tools/models/flux2-dev-bnb-4bit'),torch_dtype=torch.bfloat16,local_files_only=True)
pipe.enable_model_cpu_offload()
for s in todo:
    pose=Image.open(WORK/f'{s}_dir05.png').convert('RGBA')
    aspect=pose.width/pose.height
    if aspect>=1: width=1024; height=round(1024/aspect/16)*16
    else: height=1024; width=round(1024*aspect*1.12/16)*16
    canvas=Image.new('RGB',(width,height),(70,70,74))
    scale=min(width*.88/pose.width,height*.9/pose.height)
    ref=pose.resize((round(pose.width*scale),round(pose.height*scale)),Image.Resampling.NEAREST)
    canvas.paste(ref,((width-ref.width)//2,(height-ref.height)//2),ref)
    icon=Image.open(ROOT/'graphics/units'/s/'icon.png').convert('RGB')
    prompt=(f'Image 1 is the Age of Empires II {s.replace("_"," ")} sprite and is the exact pose and facing reference. Image 2 is its official icon and is the equipment and colour reference. '
        +descriptions[s]+' Render ONE faithful highly detailed complete unit in the exact three-quarter pose of image 1, with the equipment and colours of image 2. '
        'Plain solid neutral studio background, muted weathered historic colours, matte textures, soft realistic lighting and the grounded painterly look of authentic Age of Empires II art. '
        'Output exactly ONE complete unit, one view, no duplicate, no grid, no extra figure, no inset or thumbnail, no text, no logo, no nameplate and no pedestal. Keep the whole unit inside the frame with a small clear margin.')
    record=dict(slug=s,model='diffusers/FLUX.2-dev-bnb-4bit',seed=7,steps=44,guidance=4.0,width=width,height=height,prompt=prompt,reference_pose=str(WORK/f'{s}_dir05.png'),reference_icon=str(ROOT/'graphics/units'/s/'icon.png'))
    (WORK/f'{s}-generation.json').write_text(json.dumps(record,indent=2))
    print('GENERATING',s,width,height,flush=True); start=time.time()
    im=pipe(image=[canvas,icon],prompt=prompt,height=height,width=width,num_inference_steps=44,guidance_scale=4.0,generator=torch.Generator('cuda').manual_seed(7)).images[0]
    im.save(dest/f'{s}_idle_dir05_bg.png')
    print('SAVED',s,round(time.time()-start,1),'seconds',flush=True)
