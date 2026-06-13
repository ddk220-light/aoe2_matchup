"""Produce AI-upscaled pose references for each unit in graphics/units/<slug>/.

For each slug this builds the enhanced native composite (red player color + soft SLD
shadow layer, via build_unit_assets.enhanced_pose_ref) and writes two 4x upscales:

  <slug>_idle_dir06_ultrasharp4x.png   — 4x-UltraSharp (crispest detail)
  <slug>_idle_dir06_dat4x.png          — 4xNomos8kDAT (most natural look)

Halo-free alpha workflow (same as graphics/upscale_sprites.py): edge-bleed the RGB,
run the model on opaque RGB, upscale the ORIGINAL alpha with Lanczos, recombine.

Environment
-----------
Needs torch + spandrel + CUDA — run under the visomaster env:
  C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/upscale_refs.py [--slugs kona]

Models (downloaded from OpenModelDB/HuggingFace, ~67–155 MB each):
  .scratch/tools/models/4x-UltraSharp.pth
  .scratch/tools/models/4xNomos8kDAT.pth
"""
import os, sys, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_unit_assets import UNITS, UNITS_DIR, IDLE_DIR_ANGLE, enhanced_pose_ref
from upscale_sprites import edge_bleed
from PIL import Image
import numpy as np
import torch
from spandrel import ModelLoader

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = {
    'ultrasharp4x': os.path.join(ROOT, '.scratch', 'tools', 'models', '4x-UltraSharp.pth'),
    'dat4x':        os.path.join(ROOT, '.scratch', 'tools', 'models', '4xNomos8kDAT.pth'),
}
SCALE = 4


def _run(model, img_rgb):
    arr = np.asarray(img_rgb.convert('RGB')).astype('float32') / 255.0
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to('cuda')
    with torch.no_grad():
        o = model(t)
    o = o.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()
    return Image.fromarray((o * 255).round().astype('uint8'), 'RGB')


def upscale_rgba(rgba, model):
    """Halo-free, supersampled model upscale of an RGBA image.

    Two model passes (16x) downsampled to 4x — supersampling smooths the BC1
    block artifacts that a single pass amplifies on small (<128px) sprites.
    """
    bled = edge_bleed(rgba)
    rgb = _run(model, _run(model, bled))                       # 16x
    target = (rgba.width * SCALE, rgba.height * SCALE)
    rgb = rgb.resize(target, Image.LANCZOS)                    # -> 4x
    a = rgba.split()[3].resize(target, Image.LANCZOS)
    return Image.merge('RGBA', (*rgb.split(), a))


def upscale_rgba_single(rgba, model):
    """Halo-free single-pass 4x upscale (no supersample) — much faster, used for GIFs."""
    rgb = _run(model, edge_bleed(rgba))                        # 4x, one pass
    target = (rgba.width * SCALE, rgba.height * SCALE)
    if rgb.size != target:
        rgb = rgb.resize(target, Image.LANCZOS)
    a = rgba.split()[3].resize(target, Image.LANCZOS)
    return Image.merge('RGBA', (*rgb.split(), a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset of slugs (default: all in UNITS)')
    args = ap.parse_args()
    slugs = args.slugs or list(UNITS)

    models = {}
    for name, pth in MODELS.items():
        if not os.path.exists(pth):
            print(f'MISSING model {pth} — download it first'); sys.exit(1)
        models[name] = ModelLoader().load_from_file(pth).to('cuda').eval()

    for slug in slugs:
        if slug not in UNITS:
            print(f'SKIP {slug}: not in UNITS'); continue
        stub, _icon_id = UNITS[slug]
        ref = enhanced_pose_ref(stub)
        if ref is None:
            print(f'SKIP {slug}: could not build enhanced ref'); continue
        udir = os.path.join(UNITS_DIR, slug)
        os.makedirs(udir, exist_ok=True)
        for name, model in models.items():
            t0 = time.time()
            out = upscale_rgba(ref, model)
            dst = os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}_{name}.png')
            out.save(dst)
            print(f'  {slug} {name}: {ref.size} -> {out.size} ({time.time()-t0:.1f}s)')


if __name__ == '__main__':
    main()
