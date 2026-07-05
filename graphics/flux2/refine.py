"""FLUX.2 unit-art *refiner* — clarify/upscale an already-extracted unit asset.

Unlike generate.py (text-to-image from a sprite+icon with a long descriptive
prompt), this takes the unit's already-extracted high-res assets as the
references and asks FLUX.2 to reproduce the SAME unit at higher resolution and
sharper detail — no invented content. Inputs come from graphics/units/<slug>/:

  <slug>_idle_dir06_dat4x.png         full-body idle pose  (composition target)
  <slug>_idle_dir06_ultrasharp4x.png  same pose, crisper upscale
  icon.png                            hi-res game icon (face / equipment detail)

Output -> graphics/units/<slug>/<slug>_flux_hd.png

Environment
-----------
    C:/Users/ddk22/miniconda3/envs/visomaster/python.exe graphics/flux2/refine.py --slug kona
"""
import os, sys, time, argparse
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
import torch
from diffusers import Flux2Pipeline
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UNITS_DIR = os.path.join(ROOT, 'graphics', 'units')

BG = (232, 232, 234)   # light neutral studio background for composed references

# Short per-unit subject phrase + kind (keep the prompt minimal — refs carry the form).
# kind: 'mounted' | 'foot' — only changes whether the keep-list mentions the mount.
SUBJECTS = {
    'kona':                   ('a mounted warrior on a grey horse', 'mounted'),
    'elite_kona':             ('a mounted warrior on a grey horse', 'mounted'),
    'elite_guecha_warrior':   ('a single warrior standing on foot', 'foot'),
    'elite_blackwood_archer': ('an olden-times American tribal warrior, an archer on foot', 'foot'),
}

# Optional minimal per-unit correction appended to the prompt (fixes a specific drift
# without otherwise changing the faithful-refine intent).
EXTRAS = {
    'elite_blackwood_archer': 'His face is clean-shaven with no beard and no facial hair.',
}


def round16(x: float) -> int:
    return int(round(x / 16)) * 16


def out_dims(w: int, h: int, long_edge: int = 1024) -> tuple[int, int]:
    """Output canvas preserving the reference aspect, long edge == long_edge."""
    if w >= h:
        return long_edge, max(256, round16(long_edge * h / w))
    return max(256, round16(long_edge * w / h)), long_edge


def fit_rgba(path: str, W: int, H: int, bg=BG, fill: float = 0.96) -> Image.Image:
    """Composite an RGBA asset, centered, onto a W*H neutral RGB canvas."""
    im = Image.open(path).convert('RGBA')
    canvas = Image.new('RGB', (W, H), bg)
    sc = min(W * fill / im.width, H * fill / im.height)
    up = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    canvas.paste(up, ((W - up.width) // 2, (H - up.height) // 2), up)
    return canvas


def build_prompt(subject: str, kind: str, extra: str = '') -> str:
    mount = 'mount, ' if kind == 'mounted' else ''
    extra = (' ' + extra) if extra else ''
    return (
        f"These reference images all show the SAME single Age of Empires 2 unit: {subject}. "
        "Recreate this exact unit as one high-resolution, sharply detailed HD portrait — keep "
        f"the identical pose, body, {mount}clothing, gear, colours and markings shown in the "
        "references. Do not add, remove or invent anything; only make the existing details "
        f"cleaner, crisper and more refined at higher resolution.{extra} One single subject, plain "
        "neutral background, no text, no logo, no nameplate, no duplicate, no second copy."
    )


def prepare(slug: str, long_edge: int):
    """Validate inputs and build the (refs, prompt, dims) bundle for one slug."""
    udir = os.path.join(UNITS_DIR, slug)
    dat = os.path.join(udir, f'{slug}_idle_dir06_dat4x.png')
    ult = os.path.join(udir, f'{slug}_idle_dir06_ultrasharp4x.png')
    ico = os.path.join(udir, 'icon.png')
    for p in (dat, ult, ico):
        if not os.path.exists(p):
            print(f'  SKIP {slug}: missing {p}')
            return None

    with Image.open(dat) as im:                  # aspect follows the upscaled idle
        W, H = out_dims(im.width, im.height, long_edge)
    refs = [
        fit_rgba(dat, W, H),                     # 1. composition / pose target
        fit_rgba(ult, W, H),                     # 2. same pose, sharper detail
        Image.open(ico).convert('RGB'),          # 3. icon — extra face/equipment detail
    ]
    subject, kind = SUBJECTS.get(slug, ('a single unit', 'foot'))
    prompt = build_prompt(subject, kind, EXTRAS.get(slug, ''))
    return dict(slug=slug, udir=udir, W=W, H=H, refs=refs, prompt=prompt)


def main() -> None:
    ap = argparse.ArgumentParser(description='FLUX.2 refine extracted unit assets.')
    ap.add_argument('--slugs', nargs='+', default=['kona'],
                    help='unit slugs under graphics/units/ (default: kona)')
    ap.add_argument('--long-edge', type=int, default=1024, help='output long edge px (default: 1024)')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--seeds', type=int, nargs='+', default=None,
                    help='multiple seeds -> one render each, saved as _flux_hd_s<seed>.png')
    ap.add_argument('--steps', type=int, default=44)
    ap.add_argument('--guidance', type=float, default=4.0)
    args = ap.parse_args()

    jobs = [j for j in (prepare(s, args.long_edge) for s in args.slugs) if j]
    if not jobs:
        print('Nothing to do.')
        return
    for j in jobs:
        print(f'[{j["slug"]}] output {j["W"]}x{j["H"]}')
        print(f'  PROMPT: {j["prompt"]}')

    print('\nLoading FLUX.2-dev 4-bit ...', flush=True)
    t0 = time.time()
    pipe = Flux2Pipeline.from_pretrained('diffusers/FLUX.2-dev-bnb-4bit', torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()
    pipe.set_progress_bar_config(disable=True)
    print(f'Loaded in {round(time.time()-t0, 1)} s', flush=True)

    seeds = args.seeds or [args.seed]
    multi = len(seeds) > 1
    for j in jobs:
        for sd in seeds:
            generator = torch.Generator('cuda').manual_seed(sd)
            t1 = time.time()
            result = pipe(
                image=j['refs'], prompt=j['prompt'],
                height=j['H'], width=j['W'],
                num_inference_steps=args.steps, guidance_scale=args.guidance,
                generator=generator,
            ).images[0]
            suffix = f'_s{sd}' if multi else ''
            dst = os.path.join(j['udir'], f'{j["slug"]}_flux_hd{suffix}.png')
            result.save(dst)
            peak_gb = torch.cuda.max_memory_allocated() / 1e9
            print(f'  {j["slug"]} seed {sd} -> {dst} ({round(time.time()-t1,1)}s, '
                  f'{j["W"]}x{j["H"]}, peak {peak_gb:.1f}GB)', flush=True)


if __name__ == '__main__':
    main()
