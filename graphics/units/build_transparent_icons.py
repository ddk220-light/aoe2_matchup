"""Write icon_transparent.png for every unit folder that has an icon.png.

The opaque icon.png already holds the red-tinted RGB render; we just compute the
background alpha from it (build_unit_assets._bg_alpha: border flood of the baked
black bg + continuous >=100px pure-black pocket removal) and save RGBA.

Idempotent: skips folders that already have icon_transparent.png unless --force.
Run with conda base python (numpy + Pillow + scipy):
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_transparent_icons.py
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
from PIL import Image
from build_unit_assets import UNITS_DIR, _bg_alpha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset (default: all)')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    slugs = args.slugs or sorted(
        f for f in os.listdir(UNITS_DIR)
        if os.path.isdir(os.path.join(UNITS_DIR, f)) and f != '__pycache__'
    )

    made = skipped = nofile = 0
    for slug in slugs:
        udir = os.path.join(UNITS_DIR, slug)
        src = os.path.join(udir, 'icon.png')
        dst = os.path.join(udir, 'icon_transparent.png')
        if not os.path.exists(src):
            nofile += 1
            continue
        if os.path.exists(dst) and not args.force:
            skipped += 1
            continue
        arr = np.array(Image.open(src).convert('RGBA')).astype(float)
        rgb = arr[..., :3]
        out = np.dstack([rgb, _bg_alpha(rgb)]).astype('uint8')
        Image.fromarray(out).save(dst)
        made += 1
    print(f'transparent icons: {made} written | {skipped} skipped | {nofile} no icon.png')


if __name__ == '__main__':
    main()
