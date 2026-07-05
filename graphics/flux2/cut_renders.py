"""Background-remove raw FLUX.2 renders and save three forms to graphics/art/flux2_hybrid/.

Each slug gets:
  <slug>_idle_dir05_bg.png   — full-res with background (raw render, archived)
  <slug>_idle_dir05_nobg.png — full-res transparent (rembg isnet-general-use)
  <slug>_idle_dir05_icon.png — 256×256 transparent, full figure centered (margin 0.96)

Usage
-----
  # After running generate.py, cut the batch:
  python graphics/flux2/cut_renders.py --src graphics/flux2/renders/batch13 --slugs boyar cataphract

  # Or cut every .png in the source dir:
  python graphics/flux2/cut_renders.py --src graphics/flux2/renders/batch13

  # Overwrite even if output already exists:
  python graphics/flux2/cut_renders.py --src ... --slugs ... --force

Environment
-----------
Uses base conda env (C:/Users/ddk22/miniconda3/python.exe) which has rembg installed.
Do NOT run under the visomaster diffusion env (different rembg/onnx version).
"""
import os, sys, argparse
from rembg import remove, new_session
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DST  = os.path.join(ROOT, 'graphics', 'art', 'flux2_hybrid')


def icon256(transparent: Image.Image, size: int = 256, margin: float = 0.96) -> Image.Image:
    """Fit the figure tightly into a square canvas with a small margin."""
    im = transparent
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    box = int(size * margin)
    sc = min(box / im.width, box / im.height)
    w, h = max(1, int(im.width * sc)), max(1, int(im.height * sc))
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im.resize((w, h), Image.LANCZOS), ((size - w) // 2, (size - h) // 2))
    return canvas


def cut_slug(slug: str, src_dir: str, sess, force: bool = False) -> bool:
    src = os.path.join(src_dir, f'{slug}.png')
    if not os.path.exists(src):
        print(f'  SKIP {slug}: {src} not found')
        return False
    os.makedirs(DST, exist_ok=True)
    bg_path   = os.path.join(DST, f'{slug}_idle_dir05_bg.png')
    nobg_path = os.path.join(DST, f'{slug}_idle_dir05_nobg.png')
    icon_path = os.path.join(DST, f'{slug}_idle_dir05_icon.png')
    if not force and all(os.path.exists(p) for p in (bg_path, nobg_path, icon_path)):
        print(f'  skip {slug} (already cut; use --force to redo)')
        return False
    raw = Image.open(src).convert('RGB')
    raw.save(bg_path)
    cut = remove(raw, session=sess)
    bb = cut.getbbox()
    if bb:
        cut = cut.crop(bb)
    cut.save(nobg_path)
    icon256(cut).save(icon_path)
    print(f'  {slug} -> bg / nobg / icon', flush=True)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description='Cut FLUX.2 renders to bg/nobg/icon.')
    ap.add_argument('--src', required=True,
                    help='Source dir containing <slug>.png raw renders '
                         '(relative to repo root or absolute)')
    ap.add_argument('--slugs', nargs='*',
                    help='Slugs to process; if omitted, all .png files in --src are cut')
    ap.add_argument('--force', action='store_true', help='Overwrite existing outputs')
    args = ap.parse_args()

    src_dir = args.src if os.path.isabs(args.src) else os.path.join(ROOT, args.src)
    if not os.path.isdir(src_dir):
        print(f'Source dir not found: {src_dir}')
        sys.exit(1)

    if args.slugs:
        slugs = args.slugs
    else:
        slugs = [os.path.splitext(f)[0] for f in os.listdir(src_dir) if f.endswith('.png')]

    print(f'Loading rembg (isnet-general-use) ...', flush=True)
    sess = new_session('isnet-general-use')
    print(f'Cutting {len(slugs)} unit(s) from {src_dir}', flush=True)
    n = sum(cut_slug(s, src_dir, sess, args.force) for s in slugs)
    print(f'Done — {n} unit(s) saved to {DST}')


if __name__ == '__main__':
    main()
