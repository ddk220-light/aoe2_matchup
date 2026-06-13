"""Build looping GIFs of the dir06 idle / attack / death animations per unit.

Writes graphics/units/<slug>/<slug>_<anim>_dir06.gif for anim in idle/attack/death.

Uses BASE resolution (not the 4x refs). Frames are re-decoded on the SHARED full canvas
(red player color applied) and cropped to one common bounding box across the whole
animation, so the figure stays put instead of jittering (the saved per-frame PNGs are each
tight-cropped individually, which would wobble). Composited onto a flat matte for clean GIF
edges (GIF has only 1-bit transparency).

Usage
-----
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_gifs.py [--slugs kona] [--matte 48,50,54]
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_unit_assets import UNITS, UNITS_DIR, IDLE_DIR_ANGLE, find_sld, decode_red
import sld_decode as D
from PIL import Image

ANIMS = ('idle', 'attack', 'death')
DURATION_MS = {'idle': 90, 'attack': 55, 'death': 80}   # per-frame; idle is slow/breathing


def aligned_frames(stub, anim):
    """All dir06 frames of an animation, full-canvas aligned (red), None-skipped."""
    sld = find_sld(stub, anim)
    if not sld:
        return []
    data = open(sld, 'rb').read()
    _hdr, frames = D.parse(data)
    fc = len(frames) // 16
    out = []
    for i in range(fc):
        idx = IDLE_DIR_ANGLE * fc + i
        if idx >= len(frames):
            break
        im = decode_red(data, frames[idx])      # full canvas or None (reuse frames)
        if im is not None:
            out.append(im)
    return out


def make_gif(frames, matte, dst, duration):
    if not frames:
        return False
    # union bbox across all frames -> stable crop
    bbox = None
    for im in frames:
        bb = im.getbbox()
        if bb is None:
            continue
        bbox = bb if bbox is None else (min(bbox[0], bb[0]), min(bbox[1], bb[1]),
                                        max(bbox[2], bb[2]), max(bbox[3], bb[3]))
    pad = 4
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(frames[0].width, x1 + pad), min(frames[0].height, y1 + pad)
    flat = []
    for im in frames:
        bg = Image.new('RGBA', im.size, matte + (255,))
        bg.alpha_composite(im)
        flat.append(bg.crop((x0, y0, x1, y1)).convert('P', palette=Image.ADAPTIVE, colors=255))
    flat[0].save(dst, save_all=True, append_images=flat[1:], duration=duration,
                 loop=0, disposal=1, optimize=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset of slugs (default: all in UNITS)')
    ap.add_argument('--matte', default='48,50,54', help='background R,G,B (default 48,50,54)')
    args = ap.parse_args()
    matte = tuple(int(c) for c in args.matte.split(','))
    slugs = args.slugs or list(UNITS)

    for slug in slugs:
        if slug not in UNITS:
            print(f'SKIP {slug}: not in UNITS'); continue
        stub, _icon_id = UNITS[slug]
        udir = os.path.join(UNITS_DIR, slug); os.makedirs(udir, exist_ok=True)
        print(f'{slug}:')
        for anim in ANIMS:
            frames = aligned_frames(stub, anim)
            dst = os.path.join(udir, f'{slug}_{anim}_dir{IDLE_DIR_ANGLE:02d}.gif')
            if make_gif(frames, matte, dst, DURATION_MS[anim]):
                kb = os.path.getsize(dst) // 1024
                print(f'    {anim}: {len(frames)} frames -> {os.path.basename(dst)} ({kb} KB)')
            else:
                print(f'    {anim}: no frames')


if __name__ == '__main__':
    main()
