"""Generate the idle_dir06 trio (native + DAT4x + UltraSharp4x) for EVERY unit
whose idle SLD was resolved by resolve_sprites.py (.scratch/sprite_paths.json).

Per graphics/units/<slug>/:
  <slug>_idle_dir06.png              native red idle pose (dir06, first non-empty frame)
  <slug>_idle_dir06_dat4x.png        4x DAT (red + shadow, single pass)
  <slug>_idle_dir06_ultrasharp4x.png 4x UltraSharp (single pass)

Idempotent: a unit whose 3 files already exist is skipped (so the 6 finalized
units are left alone). The native + both upscales come from the SAME chosen frame,
so the pose is consistent. Single-pass 4x is used for every unit — reliable and
memory-safe on large mounted/elephant sprites (supersample OOMs at 16x).

Run in visomaster env (torch + spandrel + scipy):
  C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/build_idle_refs.py
  ... --slugs knight archer        # subset
"""
import os, sys, json, argparse, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
from PIL import Image
import sld_decode as D
from build_unit_assets import UNITS_DIR, IDLE_DIR_ANGLE, decode_red, decode_shadow
from upscale_refs import MODELS, upscale_rgba, upscale_rgba_single
from spandrel import ModelLoader

SPRITE_PATHS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            '.scratch', 'sprite_paths.json')


def idle_assets(sld_path, shadow_opacity=0.55, tint=None):
    """Return (native_rgba, pose_ref_rgba) from the first non-empty dir06 frame.
    `tint` selects the player color (None = red default; SPRITE_TINT_BLUE = blue)."""
    data = open(sld_path, 'rb').read()
    _hdr, frames = D.parse(data)
    fc = len(frames) // 16
    chosen = None
    dkw = {} if tint is None else {'tint': tint}
    for i in range(fc):
        idx = IDLE_DIR_ANGLE * fc + i
        if idx >= len(frames):
            break
        im = decode_red(data, frames[idx], **dkw)
        if im is not None:
            chosen = (frames[idx], im)
            break
    if not chosen:
        return None, None
    fr, im = chosen
    native = D._finish(im, crop=True, margin=4)
    canvas = Image.new('RGBA', (fr['w'], fr['h']), (0, 0, 0, 0))
    sh = decode_shadow(data, fr)
    if sh:
        (sx, sy), g = sh
        layer = np.zeros((g.shape[0], g.shape[1], 4), dtype=np.uint8)
        layer[..., 3] = (g * shadow_opacity).astype(np.uint8)
        canvas.alpha_composite(Image.fromarray(layer), (sx, sy))
    canvas.alpha_composite(im, (0, 0))
    return native, canvas.crop(canvas.getbbox())


def up(ref, mdl):
    """Single-pass 4x upscale (no supersample — reliable, no OOM on large sprites)."""
    return upscale_rgba_single(ref, mdl), False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset (default: all resolved)')
    ap.add_argument('--force', action='store_true', help='rebuild even if files exist')
    args = ap.parse_args()

    paths = json.load(open(SPRITE_PATHS))
    slugs = args.slugs or sorted(paths)
    models = {n: ModelLoader().load_from_file(p).to('cuda').eval() for n, p in MODELS.items()}

    done = skipped = failed = 0
    fell_back = []
    t_start = time.time()
    for k, slug in enumerate(slugs, 1):
        if slug not in paths:
            print(f'[{k}/{len(slugs)}] {slug}: no sprite path, skip', flush=True)
            skipped += 1
            continue
        udir = os.path.join(UNITS_DIR, slug)
        os.makedirs(udir, exist_ok=True)
        outs = {n: os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}_{n}.png') for n in MODELS}
        native_dst = os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}.png')
        if not args.force and os.path.exists(native_dst) and all(os.path.exists(p) for p in outs.values()):
            skipped += 1
            continue
        t0 = time.time()
        try:
            native, ref = idle_assets(paths[slug])
            if native is None:
                print(f'[{k}/{len(slugs)}] {slug}: empty dir06, FAIL', flush=True)
                failed += 1
                continue
            native.save(native_dst)
            for n, mdl in models.items():
                img, fb = up(ref, mdl)
                img.save(outs[n])
                if fb:
                    fell_back.append(f'{slug}:{n}')
            done += 1
            print(f'[{k}/{len(slugs)}] {slug}: ok ({time.time()-t0:.0f}s)', flush=True)
        except Exception:
            failed += 1
            print(f'[{k}/{len(slugs)}] {slug}: ERROR\n{traceback.format_exc()}', flush=True)

    print(f'\nDONE: {done} generated | {skipped} skipped | {failed} failed '
          f'| {time.time()-t_start:.0f}s total', flush=True)
    if fell_back:
        print('single-pass fallback (OOM):', fell_back, flush=True)


if __name__ == '__main__':
    main()
