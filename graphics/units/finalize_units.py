"""Produce the FINAL 6-file output set per unit and discard everything else.

Per graphics/units/<slug>/ the only files kept are:
  icon.png                              opaque red game icon
  icon_transparent.png                  background removed
  <slug>_idle_dir06.png                 native red idle pose
  <slug>_idle_dir06_dat4x.png           4x DAT idle pose (red + shadow, supersampled)
  <slug>_idle_dir06_ultrasharp4x.png    4x UltraSharp idle pose (supersampled)
  <slug>_attack_dir06_dat4x.gif         transparent DAT-4x attack animation (single pass)

The idle/attack/death frame-dump subfolders and any other files (incl. death GIFs) are deleted.
Idle pose PNGs stay supersampled (static, quality matters); the GIF uses a single pass (faster).

Run under the visomaster env (torch + spandrel + scipy):
  C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/finalize_units.py [--slugs kona]
"""
import os, sys, argparse, shutil, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_unit_assets import (UNITS, UNITS_DIR, IDLE_DIR_ANGLE, save_icon,
                               enhanced_pose_ref, find_sld, decode_red)
from build_gifs import aligned_frames, DURATION_MS
from build_gifs_upscaled import union_crop
from upscale_refs import MODELS, upscale_rgba, upscale_rgba_single
import sld_decode as D
from PIL import Image
from spandrel import ModelLoader


def base_idle_png(stub, dst):
    data = open(find_sld(stub, 'idle'), 'rb').read()
    _hdr, frames = D.parse(data)
    fc = len(frames) // 16
    for i in range(fc):
        im = decode_red(data, frames[IDLE_DIR_ANGLE * fc + i])
        if im is not None:
            D._finish(im, crop=True, margin=4).save(dst)
            return


def transparent_gif(frames_rgba, dst, duration):
    """Combine upscaled RGBA frames into a transparent (1-bit alpha) GIF."""
    out = []
    for im in frames_rgba:
        rgba = im.convert('RGBA')
        q = rgba.convert('RGB').quantize(colors=255, method=Image.MEDIANCUT)
        transp = rgba.split()[3].point(lambda a: 255 if a < 128 else 0)
        q.paste(255, mask=transp)
        out.append(q)
    out[0].save(dst, save_all=True, append_images=out[1:], duration=duration,
                loop=0, transparency=255, disposal=2, optimize=False)


def gif_is_transparent(path):
    try:
        return Image.open(path).info.get('transparency') is not None
    except Exception:
        return False


def keep_set(slug):
    return {
        'icon.png', 'icon_transparent.png',
        f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}.png',
        f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}_dat4x.png',
        f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}_ultrasharp4x.png',
        f'{slug}_attack_dir{IDLE_DIR_ANGLE:02d}_dat4x.gif',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset (default: all)')
    ap.add_argument('--force-gifs', action='store_true', help='rebuild GIFs even if already transparent')
    args = ap.parse_args()
    slugs = args.slugs or list(UNITS)

    dat = ModelLoader().load_from_file(MODELS['dat4x']).to('cuda').eval()
    ultra = None

    for slug in slugs:
        stub, icon_id = UNITS[slug]
        udir = os.path.join(UNITS_DIR, slug)
        os.makedirs(udir, exist_ok=True)
        print(f'{slug}:', flush=True)

        # 1. icons (opaque + transparent)
        save_icon(icon_id, os.path.join(udir, 'icon.png'))
        print('    icons', flush=True)

        # 2. native idle pose
        base_idle_png(stub, os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}.png'))

        # 3. upscaled idle refs (skip if present)
        ref = None
        for mname, pth in MODELS.items():
            dst = os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}_{mname}.png')
            if os.path.exists(dst):
                continue
            if ref is None:
                ref = enhanced_pose_ref(stub)
            mdl = dat if mname == 'dat4x' else (ultra or ModelLoader().load_from_file(pth).to('cuda').eval())
            if mname != 'dat4x':
                ultra = mdl
            upscale_rgba(ref, mdl).save(dst)
        print('    idle refs', flush=True)

        # 4. transparent single-pass DAT-4x attack GIF (death dropped)
        for anim in ('attack',):
            dst = os.path.join(udir, f'{slug}_{anim}_dir{IDLE_DIR_ANGLE:02d}_dat4x.gif')
            if not args.force_gifs and gif_is_transparent(dst):
                print(f'    {anim} gif: already transparent, skip', flush=True); continue
            t0 = time.time()
            frames = union_crop(aligned_frames(stub, anim))
            up = [upscale_rgba_single(f, dat) for f in frames]   # single pass — faster, fine for GIF
            transparent_gif(up, dst, DURATION_MS[anim])
            print(f'    {anim} gif: {len(frames)}f -> {up[0].size} '
                  f'({os.path.getsize(dst)//1024} KB, {time.time()-t0:.0f}s)', flush=True)

        # 5. cleanup — remove subfolders and any non-keep file
        keep = keep_set(slug)
        for sub in ('idle', 'attack', 'death'):
            shutil.rmtree(os.path.join(udir, sub), ignore_errors=True)
        for f in os.listdir(udir):
            p = os.path.join(udir, f)
            if os.path.isfile(p) and f not in keep:
                os.remove(p); print(f'    removed {f}', flush=True)
        print(f'    -> {sorted(os.listdir(udir))}', flush=True)


if __name__ == '__main__':
    main()
