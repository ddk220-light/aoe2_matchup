"""YouTube thumbnail generator for the "<Unit> vs all unique units" sim series.

Concept — "lone champion vs the shadow horde":
  * cool->warm cinematic background, warm rim-glow behind the hero
  * a darkened, cool-tinted scatter of EVERY other unique-unit icon = "all unique units"
  * the unit's FLUX-refined render, cut out, as a large hero on the right (facing the horde)
  * bold stacked title: <NAME> / VS / ALL UNIQUE UNITS  + small AoE2 kicker

Output: 1280x720 PNG (YouTube's standard thumbnail size, 16:9).

    D:/miniconda3/python.exe graphics/youtube_thumb.py --slug kona --name Kona
"""
import os, sys, math, random, argparse, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNITS_DIR = os.path.join(ROOT, 'graphics', 'units')
FONTS = os.path.join(ROOT, 'graphics', 'fonts')
SCRATCH = os.path.join(ROOT, '.scratch_nb')

W, H = 1280, 720

# --- palette ---------------------------------------------------------------
NAVY     = (10, 18, 30)      # deep cool base
NAVY2    = (18, 30, 46)
GLOW     = (255, 150, 60)    # warm amber rim glow
GOLD_TOP = (255, 222, 130)
GOLD_BOT = (224, 140, 32)
RED      = (228, 52, 40)
CREAM    = (247, 238, 221)
DARK     = (8, 11, 16)
HORDE_TINT = np.array([62, 100, 150], float)  # cool steel-blue for the shadow army

F_BIG  = os.path.join(FONTS, 'BigShoulders-Bold.ttf')
F_KICK = 'C:/Windows/Fonts/bahnschrift.ttf'


# --- helpers ---------------------------------------------------------------
def vgrad(size, top, bot):
    w, h = size
    t = np.linspace(0, 1, h)[:, None, None]
    col = (np.array(top)[None, None, :] * (1 - t) + np.array(bot)[None, None, :] * t)
    arr = np.broadcast_to(col, (h, w, 3)).astype(np.uint8)
    a = np.full((h, w, 1), 255, np.uint8)
    return Image.fromarray(np.concatenate([arr, a], 2), 'RGBA')


def background():
    """Diagonal cool gradient + a warm radial glow on the right."""
    base = np.asarray(vgrad((W, H), NAVY2, NAVY)).astype(float)
    yy, xx = np.mgrid[0:H, 0:W]
    # diagonal cool darkening toward bottom-left
    d = ((xx / W) * 0.5 + (1 - yy / H) * 0.5)
    base[..., :3] *= (0.72 + 0.28 * d)[..., None]
    # warm radial glow behind hero (right-centre)
    cx, cy, r = W * 0.72, H * 0.46, W * 0.46
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    g = np.clip(1 - dist / r, 0, 1) ** 2.2
    base[..., :3] += np.array(GLOW)[None, None, :] * g[..., None] * 0.85
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), 'RGBA')


def tint_icon(im, opacity):
    """Map an icon to a flat cool silhouette (luminance -> steel-blue)."""
    a = np.asarray(im.convert('RGBA')).astype(float)
    rgb, al = a[..., :3], a[..., 3:]
    lum = (rgb * np.array([0.3, 0.59, 0.11])).sum(2, keepdims=True) / 255
    lum = 0.40 + 0.60 * lum                       # lift so shapes stay readable
    out = np.concatenate([lum * HORDE_TINT[None, None, :], al * opacity], 2)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def build_horde(exclude_slug, rng):
    """Scatter darkened unique-unit icons across the canvas (denser left/bottom)."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    icons = [p for p in glob.glob(os.path.join(UNITS_DIR, '*', 'icon_transparent.png'))
             if os.path.basename(os.path.dirname(p)) != exclude_slug]
    rng.shuffle(icons)
    # loose grid with jitter; thin out (don't fully clear) the hero zone on the right
    cols, rows = 10, 7
    for r in range(rows):
        for c in range(cols):
            if not icons:
                break
            if c >= 6 and 1 <= r <= 5 and rng.random() < 0.55:
                continue
            p = icons.pop()
            gx = (c + 0.5) / cols * (W * 0.98) + rng.uniform(-36, 36)
            gy = (r + 0.5) / rows * (H * 1.04) + rng.uniform(-32, 32)
            depth = rng.uniform(0.40, 1.0)                 # far->near
            sz = int(64 + 70 * depth)
            op = 0.30 + 0.45 * depth
            ic = tint_icon(Image.open(p).resize((sz, sz), Image.LANCZOS), op)
            if depth < 0.62:
                ic = ic.filter(ImageFilter.GaussianBlur(1.4))
            layer.alpha_composite(ic, (int(gx - sz / 2), int(gy - sz / 2)))
    return layer.filter(ImageFilter.GaussianBlur(0.4))


def get_hero(slug, hero_arg):
    if hero_arg:
        return Image.open(hero_arg).convert('RGBA')
    os.makedirs(SCRATCH, exist_ok=True)
    cut = os.path.join(SCRATCH, f'{slug}_hero_cut.png')
    if os.path.exists(cut):
        return Image.open(cut).convert('RGBA')
    from rembg import remove
    src = os.path.join(UNITS_DIR, slug, f'{slug}_flux_hd.png')
    im = remove(Image.open(src).convert('RGBA'))
    im = im.crop(im.getbbox())
    im.save(cut)
    return im


def fit_font(text, path, max_w, size, min_size=20):
    while size > min_size:
        f = ImageFont.truetype(path, size)
        if ImageFont.truetype(path, size).getbbox(text)[2] <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(path, min_size)


def text_block(text, font, fill_top, fill_bot, stroke_col, stroke_w):
    """Return an RGBA layer of `text` with a gradient fill + dark stroke + shadow."""
    dummy = ImageDraw.Draw(Image.new('RGBA', (4, 4)))
    bx = dummy.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
    w, h = bx[2] - bx[0], bx[3] - bx[1]
    pad = stroke_w + 14
    size = (w + 2 * pad, h + 2 * pad)
    ox, oy = pad - bx[0], pad - bx[1]

    # shadow
    sh = Image.new('RGBA', size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((ox, oy), text, font=font, fill=(0, 0, 0, 220), stroke_width=stroke_w)
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    layer.alpha_composite(sh, (5, 7))

    # stroke + white body
    body = Image.new('RGBA', size, (0, 0, 0, 0))
    ImageDraw.Draw(body).text((ox, oy), text, font=font, fill=(255, 255, 255, 255),
                              stroke_width=stroke_w, stroke_fill=stroke_col + (255,))
    # gradient over the interior only
    fillmask = Image.new('L', size, 0)
    ImageDraw.Draw(fillmask).text((ox, oy), text, font=font, fill=255)
    grad = vgrad(size, fill_top, fill_bot)
    body = Image.composite(grad, body, fillmask)
    layer.alpha_composite(body)
    return layer


def vignette(img, strength=0.55):
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W / 2, H / 2
    d = np.sqrt(((xx - cx) / (W / 2)) ** 2 + ((yy - cy) / (H / 2)) ** 2)
    v = np.clip(1 - (d - 0.6) * strength, 0, 1)
    a = np.asarray(img).astype(float)
    a[..., :3] *= v[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


# --- compose ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', default='kona')
    ap.add_argument('--name', default='Kona')
    ap.add_argument('--hero', default=None, help='pre-cut hero PNG (else rembg the flux_hd)')
    ap.add_argument('--subtitle', default=None,
                    help='replace the "VS ALL UNIQUE UNITS" block with this cream strapline '
                         '(e.g. "Unit Matchup Guide"); words are balanced over two lines')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    canvas = background()
    canvas.alpha_composite(build_horde(args.slug, rng))

    # left scrim so the title reads over the horde
    scrim = np.zeros((H, W, 4), float)
    xfade = np.clip(1 - np.linspace(0, 1, W) / 0.50, 0, 1)[None, :]
    scrim[..., 3] = (xfade * 120)
    canvas.alpha_composite(Image.fromarray(scrim.astype(np.uint8), 'RGBA'))

    # hero — cap width so the wide mount stays fully in frame with a right margin
    hero = get_hero(args.slug, args.hero)
    sc = min((H * 0.96) / hero.height, (W * 0.47) / hero.width)
    hero = hero.resize((int(hero.width * sc), int(hero.height * sc)), Image.LANCZOS)
    hx = W - hero.width - 26
    hy = H - hero.height - 4
    # warm rim halo (pop) + soft drop shadow (ground). Both are built full-canvas:
    # blurring a layer cropped to the hero's bbox clips the falloff into a visible
    # rectangle around tall/narrow heroes.
    halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    halo.paste(GLOW + (255,), (hx, hy), hero)
    canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(26)))
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 165), (hx + 14, hy + 16), hero)
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))
    canvas.alpha_composite(hero, (hx, hy))

    canvas = vignette(canvas, strength=0.38)

    # --- type -------------------------------------------------------------
    M = 70                                   # left margin
    col_w = int(W * 0.46)                     # keep title clear of the hero
    text_right = hx + int(hero.width * 0.18)  # title may run just into the hero's halo

    # kicker
    kick = ImageFont.truetype(F_KICK, 25)
    ktxt = 'AGE OF EMPIRES II : DE  ·  BATTLE SIMULATION'
    kl = Image.new('RGBA', (col_w + 40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(kl).text((0, 0), ktxt, font=kick, fill=CREAM + (235,))
    canvas.alpha_composite(kl, (M + 4, 54))
    # red rule under kicker
    ImageDraw.Draw(canvas).rectangle([M + 4, 92, M + 4 + 250, 97], fill=RED + (255,))

    # NAME (gold) — one big line for short names, stacked words for long ones
    words = args.name.upper().split()
    if len(words) == 1:
        nlines, nsize = [words[0]], 240
    else:
        mid = (len(words) + 1) // 2
        nlines, nsize = [' '.join(words[:mid]), ' '.join(words[mid:])], 170
    nf = ImageFont.truetype(F_BIG, nsize)
    while nsize > 60 and max(nf.getbbox(l)[2] for l in nlines) > col_w:
        nsize -= 4
        nf = ImageFont.truetype(F_BIG, nsize)
    y = 92
    for l in nlines:
        canvas.alpha_composite(text_block(l, nf, GOLD_TOP, GOLD_BOT, DARK, 9), (M - 14, y))
        y += int(nsize * 0.84)
    y += 8

    if args.subtitle:
        # cream strapline filling the column the VS block would have used
        swords = args.subtitle.upper().split()
        mid = (len(swords) + 1) // 2
        slines = [' '.join(swords)] if len(swords) <= 2 else \
                 [' '.join(swords[:mid]), ' '.join(swords[mid:])]
        avail = max(190, text_right - (M - 8) - 10)
        sf = fit_font(max(slines, key=len), F_BIG, avail, 96)
        sy = y - 2
        for l in slines:
            canvas.alpha_composite(text_block(l, sf, CREAM, (210, 198, 178), DARK, 7), (M - 8, sy))
            sy += int(sf.size * 0.86)
    else:
        # VS (red) + ALL UNIQUE / UNITS (cream) stacked beside it
        fvs = ImageFont.truetype(F_BIG, 104)
        vs_layer = text_block('VS', fvs, (255, 150, 140), RED, CREAM, 8)
        canvas.alpha_composite(vs_layer, (M - 8, y))
        vx = M - 8 + vs_layer.width - 18
        avail = max(190, text_right - vx - 10)
        fa = fit_font('ALL UNIQUE', F_BIG, avail, 84)
        canvas.alpha_composite(text_block('ALL UNIQUE', fa, CREAM, (210, 198, 178), DARK, 7), (vx, y - 2))
        canvas.alpha_composite(text_block('UNITS', fa, CREAM, (210, 198, 178), DARK, 7),
                               (vx, y - 2 + int(fa.size * 0.86)))

    out = args.out or os.path.join(SCRATCH, f'{args.slug}_youtube_thumb.png')
    canvas.convert('RGB').save(out, quality=95)
    print(f'saved {out} ({W}x{H})')


if __name__ == '__main__':
    main()
