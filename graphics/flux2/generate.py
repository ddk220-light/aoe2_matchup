"""FLUX.2 unit art generator — run a batch of elite unique unit renders.

Usage
-----
1.  Edit the UNITS list below with the units you want to generate.
2.  Run from the repo root (so sld_decode is importable):
      python graphics/flux2/generate.py [--out renders/batch_name]
3.  Inspect outputs in graphics/flux2/renders/<batch_name>/
4.  Run cut_renders.py to bg-remove and promote to graphics/art/flux2_hybrid/

Environment
-----------
- Must use the diffusion conda env:
    C:/Users/ddk22/miniconda3/envs/visomaster/python.exe
  (has torch 2.8 cu129, diffusers 0.38, bitsandbytes 0.49)
- Model: diffusers/FLUX.2-dev-bnb-4bit (download once via download_model.py)
- ~110-230 s/render on RTX 5090

Unit list format
----------------
Each entry is a tuple:
  (slug, sld_filename, icon_filename, display_name, kind, dir_angle, description)

  slug          str  kebab-case id, matches graphics/art/flux2_hybrid/<slug>_*
  sld_filename  str  filename in graphics/game_raw_files/ (usually elite idleA x2)
  icon_filename str  filename in apps/website/static/img/units/ (Elite_Name.png)
  display_name  str  human-readable name used in the prompt
  kind          str  'foot' | 'mounted' | 'ship' | 'vehicle'
  dir_angle     int  0..15; use 5 for most units, 0 for ships
  description   str  researched unit description — see docs/flux2-unit-art-workflow.md

Design constants (shared across all units)
-------------------------------------------
TONE   — darker/muted/weathered AoE2 palette clause (do not change)
NEG    — no emblem/banner/inset/text clause (do not change)
"""
import os, sys, time, argparse
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sld_decode as D
import torch
from diffusers import Flux2Pipeline
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW  = os.path.join(ROOT, 'graphics', 'game_raw_files')
ICO  = os.path.join(ROOT, 'apps', 'website', 'static', 'img', 'units')

# ---------------------------------------------------------------------------
# Shared prompt clauses — do not change; see docs/flux2-unit-art-workflow.md
# ---------------------------------------------------------------------------
TONE = (
    "Render it with a darker, muted, slightly desaturated historical color palette and soft "
    "realistic lighting, with weathered matte textures and natural shadows - the grounded, "
    "slightly somber, painterly look of an authentic Age of Empires 2 unit portrait. "
    "Not bright, not glossy, not neon, not cartoonish."
)
NEG = (
    "Plain solid neutral studio background and nothing else: no text, no logo, no emblem, "
    "no crest, no banner, no nameplate, no base or pedestal, and NO inset image, no thumbnail, "
    "no picture-in-picture, no small framed icon in any corner - just the single subject. "
    "Output EXACTLY ONE single figure - no duplicate, no second copy, no grid, no extra person "
    "in the background."
)

# Subject clause by unit kind — drives the "render X" sentence
_SUBJECT = {
    'foot':    ("Render ONE SINGLE full-body figure of this unit standing in the exact same "
                "pose, body angle and facing direction as image 1"),
    'mounted': ("Render ONE SINGLE full-body figure of this unit in the exact same pose, "
                "body angle and facing direction as image 1, keeping the animal/mount and "
                "everything carried on it together as one subject"),
    'ship':    ("Render ONE SINGLE armored warship, the whole ship as one subject, seen from "
                "the same side and angle as image 1"),
    'vehicle': ("Render this vehicle together with its horse as ONE single subject, in the "
                "exact same composition and facing as image 1, keeping the vehicle and horse "
                "together"),
}

# ---------------------------------------------------------------------------
# UNITS — edit this list for each batch
# ---------------------------------------------------------------------------
# fmt: (slug, sld_filename, icon_filename, display_name, kind, dir_angle, description)
# Skip units already in graphics/art/flux2_hybrid/ (generate.py checks before running)
UNITS: list = [
    # Example — replace with the units you actually want to generate:
    # ('boyar', 'u_cav_boyar_elite_idleA_x2.sld', 'Elite_Boyar.png', 'Boyar', 'mounted', 5,
    #  "a Slavic Boyar, a heavily armored cavalry warrior ..."),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def round16(x: float) -> int:
    return int(round(x / 16)) * 16


def canvas_dims(aspect: float) -> tuple[int, int]:
    """Return (W, H) for the output canvas given sprite aspect ratio."""
    if aspect >= 1:
        return (1024, max(512, min(1024, round16(1024 / aspect))))
    else:
        return (max(480, min(1024, round16(1024 * aspect * 1.12))), 1024)


def extract_frame(data: bytes, frames: list, fc: int, dir_angle: int) -> Image.Image | None:
    """Decode the first non-empty frame at dir_angle (tries up to 6 offsets)."""
    for off in range(6):
        idx = min(dir_angle * fc + off, len(frames) - 1)
        im = D.decode_main(data, frames[idx], player_color=None)
        if im:
            return D._finish(im, crop=True, margin=4)
    return None


def make_sprite_ref(rgba: Image.Image, W: int, H: int, fill: float = 0.9) -> Image.Image:
    """Composite the sprite onto a neutral gray canvas at generation resolution."""
    bg = Image.new('RGB', (W, H), (70, 70, 74))
    max_w, max_h = int(W * 0.94), int(H * fill)
    sc = min(max_w / rgba.width, max_h / rgba.height)
    up = rgba.resize((max(1, int(rgba.width * sc)), max(1, int(rgba.height * sc))), Image.LANCZOS)
    bg.paste(up, ((W - up.width) // 2, (H - up.height) // 2), up)
    return bg


def load_icon(path: str) -> Image.Image:
    """Load icon; upscale small (palette) icons to 256px with NEAREST to avoid blur."""
    ic = Image.open(path).convert('RGB')
    if min(ic.size) < 64:
        ic = ic.resize((256, 256), Image.NEAREST)
    return ic


def build_prompt(name: str, kind: str, description: str) -> str:
    subject = _SUBJECT.get(kind, _SUBJECT['foot'])
    return (
        f"Reference image 1 is a sprite of the Age of Empires 2 {name} unit - use it for the "
        f"EXACT pose, shape and facing. The final image is the unit's official icon - use it for "
        f"colors and equipment. The unit is {description}. {subject}. {NEG} {TONE} Sharp, highly "
        f"detailed, professional game character art, one subject only, one view only."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description='Generate FLUX.2 unit renders.')
    ap.add_argument('--out', default='renders/batch',
                    help='Output dir relative to graphics/flux2/ (default: renders/batch)')
    ap.add_argument('--seed', type=int, default=7, help='Generation seed (default: 7)')
    ap.add_argument('--steps', type=int, default=44, help='Inference steps (default: 44)')
    ap.add_argument('--guidance', type=float, default=4.0, help='Guidance scale (default: 4.0)')
    ap.add_argument('--skip-existing', action='store_true', default=True,
                    help='Skip slugs that already have a render in --out (default: on)')
    args = ap.parse_args()

    out_dir = os.path.join(os.path.dirname(__file__), args.out)
    os.makedirs(out_dir, exist_ok=True)

    if not UNITS:
        print('UNITS list is empty — edit generate.py and add units before running.')
        return

    todo = []
    for entry in UNITS:
        slug = entry[0]
        dst = os.path.join(out_dir, f'{slug}.png')
        if args.skip_existing and os.path.exists(dst):
            print(f'  skip {slug} (already exists)')
        else:
            todo.append(entry)
    if not todo:
        print('All units already generated.')
        return

    print('Loading FLUX.2-dev 4-bit ...', flush=True)
    t0 = time.time()
    pipe = Flux2Pipeline.from_pretrained('diffusers/FLUX.2-dev-bnb-4bit', torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()
    pipe.set_progress_bar_config(disable=True)
    print(f'Loaded in {round(time.time()-t0, 1)} s', flush=True)

    gen_kwargs = dict(num_inference_steps=args.steps, guidance_scale=args.guidance)
    generator = torch.Generator('cuda').manual_seed(args.seed)

    for slug, sld, ico, name, kind, dir_angle, description in todo:
        sld_path = os.path.join(RAW, sld)
        ico_path = os.path.join(ICO, ico)
        if not os.path.exists(sld_path):
            print(f'  SKIP {slug}: SLD not found at {sld_path}')
            continue
        if not os.path.exists(ico_path):
            print(f'  SKIP {slug}: icon not found at {ico_path}')
            continue

        data = open(sld_path, 'rb').read()
        _hdr, frames = D.parse(data)
        fc = len(frames) // 16
        pose = extract_frame(data, frames, fc, dir_angle)
        if pose is None:
            print(f'  SKIP {slug}: could not decode dir{dir_angle:02d} frame')
            continue

        W, H = canvas_dims(pose.width / pose.height)
        refs  = [make_sprite_ref(pose, W, H), load_icon(ico_path)]
        prompt = build_prompt(name, kind, description)

        t1 = time.time()
        result = pipe(
            image=refs, prompt=prompt,
            height=H, width=W,
            generator=generator,
            **gen_kwargs,
        ).images[0]
        dst = os.path.join(out_dir, f'{slug}.png')
        result.save(dst)
        elapsed = round(time.time() - t1, 1)
        peak_gb = torch.cuda.max_memory_allocated() / 1e9
        print(f'  {slug} -> {dst} ({elapsed}s, {W}x{H}, {kind} dir{dir_angle:02d}, '
              f'peak {peak_gb:.1f}GB)', flush=True)

    print(f'Done. Total {round((time.time()-t0)/60, 1)} min', flush=True)
    print(f'Next step: python graphics/flux2/cut_renders.py --src {os.path.relpath(out_dir, ROOT)}'
          f' --slugs {" ".join(e[0] for e in todo)}')


if __name__ == '__main__':
    main()
