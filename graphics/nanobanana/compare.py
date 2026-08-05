"""Build a 4-up A/B panel: SPRITE | ICON | FLUX.2 | NANO BANANA PRO, per unit.

Usage
-----
  D:/miniconda3/python.exe graphics/nanobanana/compare.py leitis woad_raider mangudai

Reads the FLUX render from graphics/art/flux2_hybrid/<slug>_idle_dir05_bg.png and the Nano
Banana render from graphics/nanobanana/renders/batch_nb/<slug>.png. Output panels land in
graphics/nanobanana/critique/<slug>.png.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sld_decode as D
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW  = os.path.join(ROOT, 'graphics', 'game_raw_files')
ICO  = os.path.join(ROOT, 'apps', 'website', 'static', 'img', 'units')
FLUX = os.path.join(ROOT, 'graphics', 'art', 'flux2_hybrid')
NB   = os.path.join(os.path.dirname(__file__), 'renders', 'batch_nb')
OUT  = os.path.join(os.path.dirname(__file__), 'critique')

# slug -> (sld, icon)
META = {
    'leitis':      ('u_cav_leitis_elite_idleA_x2.sld', 'Elite_Leitis.png'),
    'woad_raider': ('u_inf_woadraider_elite_idleA_x2.sld', 'Elite_Woad_Raider.png'),
    'mangudai':    ('u_cav_mangudai_elite_idleA_x2.sld', 'Elite_Mangudai.png'),
}

CELL, PAD, LABEL_H = 520, 18, 30
BG, FG = (32, 34, 40), (235, 220, 170)


def sprite_frame(sld, dir_angle=5):
    data = open(os.path.join(RAW, sld), 'rb').read()
    _h, frames = D.parse(data); fc = len(frames) // 16
    for off in range(6):
        idx = min(dir_angle * fc + off, len(frames) - 1)
        im = D.decode_main(data, frames[idx], player_color=None)
        if im:
            return D._finish(im, crop=True, margin=4)
    return None


def fit(im, box):
    sc = min(box / im.width, box / im.height)
    return im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)


def load(path):
    return Image.open(path).convert('RGBA') if os.path.exists(path) else None


def main():
    slugs = sys.argv[1:] or list(META)
    os.makedirs(OUT, exist_ok=True)
    try:
        font = ImageFont.truetype('arialbd.ttf', 22)
    except Exception:
        font = ImageFont.load_default()

    for slug in slugs:
        if slug not in META:
            print(f'  SKIP {slug}: not in META'); continue
        sld, icon = META[slug]
        sprite = sprite_frame(sld)
        icon_im = load(os.path.join(ICO, icon))
        if icon_im and min(icon_im.size) < 200:
            icon_im = icon_im.resize((256, 256), Image.NEAREST)
        flux = load(os.path.join(FLUX, f'{slug}_idle_dir05_bg.png'))
        nb = load(os.path.join(NB, f'{slug}.png'))

        cols = [('SPRITE (pose truth)', sprite), ('ICON (color truth)', icon_im),
                ('FLUX.2-dev', flux), ('NANO BANANA PRO', nb)]
        W = PAD + len(cols) * (CELL + PAD)
        H = LABEL_H + PAD + CELL + PAD
        canvas = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(canvas)
        x = PAD
        for label, im in cols:
            d.text((x, PAD - 2), label, fill=FG, font=font)
            cell = Image.new('RGBA', (CELL, CELL), BG + (255,))
            if im is not None:
                f = fit(im, CELL)
                ov = Image.new('RGBA', (CELL, CELL), (0, 0, 0, 0))
                ov.alpha_composite(f, ((CELL - f.width) // 2, (CELL - f.height) // 2))
                cell = Image.alpha_composite(cell, ov)
            canvas.paste(cell.convert('RGB'), (x, LABEL_H + PAD))
            x += CELL + PAD
        p = os.path.join(OUT, f'{slug}.png')
        canvas.save(p)
        print(f'  panel -> {p}  {canvas.size}')


if __name__ == '__main__':
    main()
