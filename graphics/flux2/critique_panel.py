"""Build a labeled side-by-side critique panel for grading a FLUX.2 render.

Panel layout:   SPRITE (truth: pose+weapon) | REFERENCE ICON (colors+kit) | RENDER (grade this)

Usage
-----
  python graphics/flux2/critique_panel.py <slug> <sld_filename> <icon_filename> <render_png> [dir_angle]

Arguments
---------
  slug           kebab-case unit slug (used as output filename)
  sld_filename   filename in graphics/game_raw_files/ (e.g. u_cav_arambai_elite_idleA_x2.sld)
  icon_filename  filename in apps/website/static/img/units/ (e.g. Elite_Arambai.png)
  render_png     path to the FLUX.2 render to grade (absolute or relative to repo root)
  dir_angle      0..15 — which sprite direction to show; default 5

Output
------
  graphics/flux2/critique/<slug>.png

After viewing, also zoom individual elements:
  weapon, shield, head/helmet, mount — the thumbnail hides errors that zooming reveals.
  See docs/flux2-unit-art-workflow.md §Step 3.5 for the full grading checklist.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sld_decode as D
from PIL import Image, ImageDraw, ImageFont

ROOT    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW     = os.path.join(ROOT, 'graphics', 'game_raw_files')
ICO     = os.path.join(ROOT, 'apps', 'website', 'static', 'img', 'units')
OUT_DIR = os.path.join(os.path.dirname(__file__), 'critique')

if len(sys.argv) < 5:
    print(__doc__)
    sys.exit(1)

slug       = sys.argv[1]
sld_file   = sys.argv[2]
icon_file  = sys.argv[3]
render_png = sys.argv[4]
dir_angle  = int(sys.argv[5]) if len(sys.argv) > 5 else 5

os.makedirs(OUT_DIR, exist_ok=True)

# --- sprite frame ---------------------------------------------------------
data = open(os.path.join(RAW, sld_file), 'rb').read()
_hdr, frames = D.parse(data)
fc = len(frames) // 16

sprite = None
for off in range(6):
    idx = min(dir_angle * fc + off, len(frames) - 1)
    im = D.decode_main(data, frames[idx], player_color=None)
    if im:
        sprite = D._finish(im, crop=True, margin=4)
        break

# --- icon -----------------------------------------------------------------
icon_im = Image.open(os.path.join(ICO, icon_file)).convert('RGBA')
if min(icon_im.size) < 200:
    icon_im = icon_im.resize((256, 256), Image.NEAREST)

# --- render ---------------------------------------------------------------
render_path = render_png if os.path.isabs(render_png) else os.path.join(ROOT, render_png)
render_im = Image.open(render_path).convert('RGBA')

# --- layout ---------------------------------------------------------------
CELL    = 520
PAD     = 18
LABEL_H = 30
BG      = (32, 34, 40)
FG      = (235, 220, 170)

try:
    font = ImageFont.truetype('arialbd.ttf', 22)
except Exception:
    font = ImageFont.load_default()


def fit(im: Image.Image, box: int) -> Image.Image:
    sc = min(box / im.width, box / im.height)
    return im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)


cols = [
    ('SPRITE (truth: pose+weapon)', sprite),
    ('REFERENCE ICON (colors+kit)', icon_im),
    ('RENDER (grade this)',         render_im),
]
W = PAD + len(cols) * (CELL + PAD)
H = LABEL_H + PAD + CELL + PAD
canvas = Image.new('RGB', (W, H), BG)
d = ImageDraw.Draw(canvas)
x = PAD
for label, im in cols:
    d.text((x, PAD - 2), label, fill=FG, font=font)
    cell_bg = Image.new('RGBA', (CELL, CELL), BG + (255,))
    if im is not None:
        f = fit(im, CELL)
        overlay = Image.new('RGBA', (CELL, CELL), (0, 0, 0, 0))
        overlay.alpha_composite(f, ((CELL - f.width) // 2, (CELL - f.height) // 2))
        cell_bg = Image.alpha_composite(cell_bg, overlay)
    canvas.paste(cell_bg.convert('RGB'), (x, LABEL_H + PAD))
    x += CELL + PAD

out_path = os.path.join(OUT_DIR, f'{slug}.png')
canvas.save(out_path)
print(f'Panel -> {out_path}  {canvas.size}')
print('Next: zoom weapon, shield, head/helmet — see docs/flux2-unit-art-workflow.md §Step 3.5')
