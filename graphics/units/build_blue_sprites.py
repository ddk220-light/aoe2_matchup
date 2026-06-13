"""Generate the BLUE (player-1) idle sprite for the website's two-team rendering.

Writes graphics/units/<slug>/<slug>_idle_dir06_dat4x_blue.png for every unit whose
idle SLD was resolved (.scratch/sprite_paths.json). Only the DAT-4x single-pass
variant is produced (that is the one used as the in-app icon); the red set already
covers native + ultrasharp.

Run in visomaster env (torch + spandrel):
  C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/units/build_blue_sprites.py
  ... --slugs knight archer        # subset / tint test
"""
import os, sys, json, argparse, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_unit_assets import UNITS_DIR, IDLE_DIR_ANGLE, SPRITE_TINT_BLUE
from build_idle_refs import idle_assets
from upscale_refs import MODELS, upscale_rgba_single
from spandrel import ModelLoader

SPRITE_PATHS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            '.scratch', 'sprite_paths.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset (default: all resolved)')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    paths = json.load(open(SPRITE_PATHS))
    slugs = args.slugs or sorted(paths)
    dat = ModelLoader().load_from_file(MODELS['dat4x']).to('cuda').eval()

    done = skipped = failed = 0
    t0 = time.time()
    for k, slug in enumerate(slugs, 1):
        if slug not in paths:
            skipped += 1
            continue
        udir = os.path.join(UNITS_DIR, slug)
        os.makedirs(udir, exist_ok=True)
        dst = os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}_dat4x_blue.png')
        if os.path.exists(dst) and not args.force:
            skipped += 1
            continue
        try:
            _native, ref = idle_assets(paths[slug], tint=SPRITE_TINT_BLUE)
            if ref is None:
                failed += 1
                print(f'[{k}/{len(slugs)}] {slug}: empty, FAIL', flush=True)
                continue
            upscale_rgba_single(ref, dat).save(dst)
            done += 1
            print(f'[{k}/{len(slugs)}] {slug}: ok', flush=True)
        except Exception:
            failed += 1
            print(f'[{k}/{len(slugs)}] {slug}: ERROR\n{traceback.format_exc()}', flush=True)

    print(f'\nDONE: {done} blue | {skipped} skipped | {failed} failed | {time.time()-t0:.0f}s',
          flush=True)


if __name__ == '__main__':
    main()
