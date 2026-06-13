"""Upscaled animation GIFs: upscale every dir06 frame, then assemble into a GIF.

Writes graphics/units/<slug>/<slug>_<anim>_dir06_<model>.gif for
  anim  in idle / attack / death
  model in ultrasharp4x / dat4x

Pipeline per animation:
  1. re-decode all dir06 frames on the shared full canvas (red player color)
  2. crop every frame to ONE union bbox -> identical, aligned frame size
  3. upscale each frame 4x, halo-free + supersampled (build_unit_assets / upscale_refs)
  4. composite on a flat matte and save the GIF (GIF = 1-bit alpha only)

Note: each frame is upscaled independently, so the model can introduce mild temporal
flicker on textured regions. For these sprites it is usually acceptable.

Environment: torch + spandrel + CUDA -> visomaster env.
  C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/build_gifs_upscaled.py \
      [--slugs kona] [--models ultrasharp4x dat4x] [--matte 48,50,54]
"""
import os, sys, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_unit_assets import UNITS, UNITS_DIR, IDLE_DIR_ANGLE
from build_gifs import aligned_frames, DURATION_MS, ANIMS
from upscale_refs import MODELS, upscale_rgba
from PIL import Image
from spandrel import ModelLoader


def union_crop(frames, pad=4):
    bbox = None
    for im in frames:
        bb = im.getbbox()
        if bb is None:
            continue
        bbox = bb if bbox is None else (min(bbox[0], bb[0]), min(bbox[1], bb[1]),
                                        max(bbox[2], bb[2]), max(bbox[3], bb[3]))
    if bbox is None:
        return frames
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(frames[0].width, x1 + pad), min(frames[0].height, y1 + pad)
    return [im.crop((x0, y0, x1, y1)) for im in frames]


def save_gif(frames_rgba, matte, dst, duration):
    flat = []
    for im in frames_rgba:
        bg = Image.new('RGBA', im.size, matte + (255,))
        bg.alpha_composite(im)
        flat.append(bg.convert('P', palette=Image.ADAPTIVE, colors=255))
    flat[0].save(dst, save_all=True, append_images=flat[1:], duration=duration,
                 loop=0, disposal=1, optimize=True)


def save_webp(frames_rgba, dst, duration):
    """Transparent animated WebP — full alpha, clean edges (unlike 1-bit GIF)."""
    frames_rgba[0].save(dst, save_all=True, append_images=frames_rgba[1:],
                        duration=duration, loop=0, format='WEBP',
                        lossless=True, exact=True, method=4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset of slugs (default: all)')
    ap.add_argument('--models', nargs='*', default=list(MODELS), choices=list(MODELS))
    ap.add_argument('--matte', default='48,50,54')
    ap.add_argument('--anims', nargs='*', default=list(ANIMS), choices=list(ANIMS))
    ap.add_argument('--transparent', action='store_true',
                    help='output transparent animated WebP instead of matte GIF')
    args = ap.parse_args()
    matte = tuple(int(c) for c in args.matte.split(','))
    slugs = args.slugs or list(UNITS)
    anims = args.anims

    models = {n: ModelLoader().load_from_file(MODELS[n]).to('cuda').eval() for n in args.models}

    for slug in slugs:
        if slug not in UNITS:
            print(f'SKIP {slug}: not in UNITS'); continue
        stub, _ = UNITS[slug]
        udir = os.path.join(UNITS_DIR, slug); os.makedirs(udir, exist_ok=True)
        print(f'{slug}:')
        for anim in anims:
            frames = union_crop(aligned_frames(stub, anim))
            if not frames:
                print(f'    {anim}: no frames'); continue
            for mname, model in models.items():
                t0 = time.time()
                up = [upscale_rgba(f, model) for f in frames]
                ext = 'webp' if args.transparent else 'gif'
                dst = os.path.join(udir, f'{slug}_{anim}_dir{IDLE_DIR_ANGLE:02d}_{mname}.{ext}')
                if args.transparent:
                    save_webp(up, dst, DURATION_MS[anim])
                else:
                    save_gif(up, matte, dst, DURATION_MS[anim])
                kb = os.path.getsize(dst) // 1024
                print(f'    {anim} {mname}: {len(frames)}f {frames[0].size}->{up[0].size} '
                      f'({kb} KB, {time.time()-t0:.1f}s)')


if __name__ == '__main__':
    main()
