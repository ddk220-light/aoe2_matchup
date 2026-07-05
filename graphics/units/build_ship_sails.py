"""Composite region sails onto generic ship hulls -> static (red+blue) + animated GIF.

For every (region, ship) pair: overlay the region's assigned sail rig on the hull
(hotspot-aligned), tint hull+sail player-color regions (red=player2, blue=player1),
crop, and emit:
    <out>/<region>/<slug>.png        static, player-2 red
    <out>/<region>/<slug>_blue.png   static, player-1 blue
    <out>/<region>/<slug>.gif        animated (billowing sail over static hull), red

Hull is static; only the sail animates (dir06's 30-frame block). Sail decodes are
cached per (region, sail) and reused across ships that share a rig.

  python build_ship_sails.py --regions west            # one region (validate)
  python build_ship_sails.py                           # all regions
  python build_ship_sails.py --no-gif                  # static only
  python build_ship_sails.py --stride 2                # halve GIF frames
Run with conda base python.
"""
import os, sys, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sail_lib as S
from PIL import Image

IDLE_DIR = S.IDLE_DIR
GIF_MS = 70          # per-frame duration
PAD = 8              # transparent margin around crop


def crop_pad(img, bbox=None):
    bb = bbox or img.getbbox()
    if not bb:
        return img
    c = img.crop(bb)
    out = Image.new('RGBA', (c.width + 2*PAD, c.height + 2*PAD), (0, 0, 0, 0))
    out.alpha_composite(c, (PAD, PAD))
    return out


def to_gif(frames_rgba, path, ms=GIF_MS):
    """Save RGBA frames as a transparent looping GIF."""
    pal = []
    for im in frames_rgba:
        a = im.split()[3]
        p = im.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
        mask = a.point(lambda v: 255 if v <= 128 else 0)
        p.paste(255, mask)
        pal.append(p)
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=ms,
                loop=0, transparency=255, disposal=2, optimize=True)


class Cache:
    def __init__(self):
        self.hull = {}     # (slug,color) -> (img,fr)
        self.sail_rep = {} # (region,cls,n,color) -> (img,fr)
        self.sail_anim = {}# (region,cls,n,color) -> [(img,fr)...]

    def hull_frame(self, slug, color):
        key = (slug, color)
        if key not in self.hull:
            sld = S.load(S.SHIP_HULLS[slug])
            tint = S.TINT_RED if color == 'red' else S.TINT_BLUE
            self.hull[key] = S.first_nonempty(sld, IDLE_DIR, tint=tint)[:2] if sld else (None, None)
        return self.hull[key]

    def sail_rep_frame(self, region, cls, n, color):
        key = (region, cls, n, color)
        if key not in self.sail_rep:
            sld = S.load(S.sail_basename(region, cls, n))
            tint = S.TINT_RED if color == 'red' else S.TINT_BLUE
            self.sail_rep[key] = S.first_nonempty(sld, IDLE_DIR, tint=tint)[:2] if sld else (None, None)
        return self.sail_rep[key]

    def sail_anim_frames(self, region, cls, n, color, stride):
        key = (region, cls, n, color, stride)
        if key not in self.sail_anim:
            sld = S.load(S.sail_basename(region, cls, n))
            tint = S.TINT_RED if color == 'red' else S.TINT_BLUE
            out = []
            if sld:
                last = None
                for i, idx in enumerate(S.dir_frame_indices(sld, IDLE_DIR)):
                    if i % stride:
                        continue
                    im, fr = S.decode_frame(sld, idx, tint=tint)
                    if im is None:
                        if last is None:
                            continue
                        im, fr = last
                    last = (im, fr)
                    out.append((im, fr))
            self.sail_anim[key] = out
        return self.sail_anim[key]


def build(out_dir, regions, do_gif, stride, gif_ms):
    cache = Cache()
    n_png = n_gif = 0
    for region in regions:
        rdir = os.path.join(out_dir, region)
        os.makedirs(rdir, exist_ok=True)
        for slug in S.SHIP_HULLS:
            cls, num = S.SAIL_ASSIGN[slug]
            t0 = time.time()
            # static red + blue
            for color, suffix in (('red', ''), ('blue', '_blue')):
                himg, hfr = cache.hull_frame(slug, color)
                if himg is None:
                    continue
                simg, sfr = cache.sail_rep_frame(region, cls, num, color)
                comp = S.overlay(himg, hfr, simg, sfr) if simg is not None else himg.copy()
                crop_pad(comp).save(os.path.join(rdir, f'{slug}{suffix}.png'))
                n_png += 1
            # animated (red)
            if do_gif:
                himg, hfr = cache.hull_frame(slug, 'red')
                frames = cache.sail_anim_frames(region, cls, num, 'red', stride)
                if himg is not None and frames:
                    comps = [S.overlay(himg, hfr, simg, sfr) for simg, sfr in frames]
                    # union bbox so the GIF doesn't jitter
                    ub = None
                    for c in comps:
                        bb = c.getbbox()
                        if not bb:
                            continue
                        ub = bb if ub is None else (min(ub[0],bb[0]), min(ub[1],bb[1]),
                                                    max(ub[2],bb[2]), max(ub[3],bb[3]))
                    if ub:
                        to_gif([crop_pad(c, ub) for c in comps],
                               os.path.join(rdir, f'{slug}.gif'), ms=gif_ms)
                        n_gif += 1
            print(f"  {region}/{slug}: {time.time()-t0:.1f}s")
    print(f"done: {n_png} PNGs, {n_gif} GIFs -> {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(S._ROOT, '.scratch', 'ship_out'))
    ap.add_argument('--regions', nargs='*', default=list(S.SAIL_REGIONS))
    ap.add_argument('--no-gif', action='store_true')
    ap.add_argument('--stride', type=int, default=1)
    ap.add_argument('--gif-ms', type=int, default=GIF_MS)
    a = ap.parse_args()
    build(a.out, a.regions, not a.no_gif, a.stride, a.gif_ms)


if __name__ == '__main__':
    main()
