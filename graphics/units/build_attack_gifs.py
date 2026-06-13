"""Generate the transparent attack GIF (single-pass DAT 4x) for every unit whose
idle SLD was resolved (.scratch/sprite_paths.json) and that has a matching attack SLD.

Per graphics/units/<slug>/<slug>_attack_dir06_dat4x.gif:
  all dir06 attack frames -> red player color -> union-cropped -> single-pass DAT 4x
  -> 1-bit transparent GIF (transparency idx 255, disposal 2), 55ms/frame.

The attack SLD is derived from the unit's idle sprite stub: strip the idle suffix,
then look for <stub>_attackA_x2.sld (x1 / attackB fallbacks), in game_raw_files then
the AoE2:DE drs/graphics dir.

Idempotent: a unit whose attack GIF already exists (and is transparent) is skipped.
Run in visomaster env (torch + spandrel):
  C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/build_attack_gifs.py
  ... --slugs knight archer
"""
import os, sys, re, json, argparse, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sld_decode as D
from PIL import Image
from build_unit_assets import UNITS_DIR, IDLE_DIR_ANGLE, RAW, GAME, decode_red
from build_gifs import DURATION_MS
from build_gifs_upscaled import union_crop
from finalize_units import transparent_gif, gif_is_transparent
from upscale_refs import MODELS, upscale_rgba_single
from spandrel import ModelLoader

DRS = os.path.join(GAME, 'resources', '_common', 'drs', 'graphics')
SPRITE_PATHS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            '.scratch', 'sprite_paths.json')


def attack_sld_for(idle_path):
    """From an idle SLD path derive the unit stub and locate its attack SLD."""
    base = os.path.basename(idle_path)
    stub = re.sub(r'_idle[A-Z]?_x[12]\.sld$', '', base)
    if stub == base:                       # idle suffix didn't match -> bail
        return None
    for anim in ('attackA', 'attackB'):
        for res in ('_x2', '_x1'):
            nm = f'{stub}_{anim}{res}.sld'
            for d in (RAW, DRS):
                p = os.path.join(d, nm)
                if os.path.exists(p):
                    return p
    return None


def attack_frames(sld_path):
    """All dir06 attack frames, full-canvas aligned, red player color, None-skipped."""
    data = open(sld_path, 'rb').read()
    _hdr, frames = D.parse(data)
    fc = len(frames) // 16
    out = []
    for i in range(fc):
        idx = IDLE_DIR_ANGLE * fc + i
        if idx >= len(frames):
            break
        im = decode_red(data, frames[idx])
        if im is not None:
            out.append(im)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset (default: all resolved)')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    paths = json.load(open(SPRITE_PATHS))
    slugs = args.slugs or sorted(paths)
    dat = ModelLoader().load_from_file(MODELS['dat4x']).to('cuda').eval()

    done = skipped = noattack = failed = 0
    t_start = time.time()
    for k, slug in enumerate(slugs, 1):
        if slug not in paths:
            skipped += 1
            continue
        udir = os.path.join(UNITS_DIR, slug)
        os.makedirs(udir, exist_ok=True)
        dst = os.path.join(udir, f'{slug}_attack_dir{IDLE_DIR_ANGLE:02d}_dat4x.gif')
        if not args.force and gif_is_transparent(dst):
            skipped += 1
            continue
        asld = attack_sld_for(paths[slug])
        if not asld:
            noattack += 1
            print(f'[{k}/{len(slugs)}] {slug}: no attack SLD', flush=True)
            continue
        t0 = time.time()
        try:
            frames = attack_frames(asld)
            if not frames:
                noattack += 1
                print(f'[{k}/{len(slugs)}] {slug}: empty attack frames', flush=True)
                continue
            cropped = union_crop(frames)
            up = [upscale_rgba_single(f, dat) for f in cropped]
            transparent_gif(up, dst, DURATION_MS['attack'])
            done += 1
            print(f'[{k}/{len(slugs)}] {slug}: ok {len(frames)}f -> {up[0].size} '
                  f'({os.path.getsize(dst)//1024}KB, {time.time()-t0:.0f}s)', flush=True)
        except Exception:
            failed += 1
            print(f'[{k}/{len(slugs)}] {slug}: ERROR\n{traceback.format_exc()}', flush=True)

    print(f'\nDONE: {done} gifs | {skipped} skipped | {noattack} no-attack-sld | '
          f'{failed} failed | {time.time()-t_start:.0f}s', flush=True)


if __name__ == '__main__':
    main()
