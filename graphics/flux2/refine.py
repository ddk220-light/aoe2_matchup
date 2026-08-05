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
    D:/miniconda3/envs/visomaster/python.exe graphics/flux2/refine.py --slug kona
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
    'elite_temple_guard':     ('a single temple guardian warrior standing on foot, wearing a gold '
                               'face mask and a dark red feathered headdress, holding a tall '
                               'gold-tipped ceremonial staff', 'foot'),
    'elite_champi_warrior':   ('a single Andean warrior standing on foot, wearing a spiked gold '
                               'helmet-crown over a red-and-white patterned headband, a round gold '
                               'sun-disc medallion on his chest, a red and white tunic with dark '
                               'spiked shoulder guards, carrying a square red-bordered shield with '
                               'a black-and-red geometric step pattern and a gold star-headed mace',
                               'foot'),
    'elite_ibirapema_warrior': ('a single bare-chested Tupi warrior wearing a tall fan of dark-red '
                               'feathers on a gold headband, red face paint, a salmon-pink feather '
                               'shoulder cape, stacked gold neck rings and a pale straw skirt, '
                               'gripping one long honey-brown wooden club two-handed', 'foot'),
    'slinger':                ('a single Andean slinger wearing a red cloth headband with a gold '
                               'plaque and a red-and-white feather plume, a white sleeveless tunic '
                               'with a red centre stripe, and a golden-yellow woven cloth panel at '
                               'his front bearing a red stepped-square motif, holding a braided '
                               'brown fibre sling', 'foot'),
    'elite_bolas_rider':      ('a single Andean rider on a pale cream horse, wearing a white poncho '
                               'with broad red stripes and red stepped-cross motifs and a gold '
                               'headband with an upright red feather, whirling overhead a three-cord '
                               'bolas of braided tan rope with mottled black-and-white stone balls',
                               'mounted'),
    'warrior_priest':         ('a single bearded warrior-priest in a dark studded leather skullcap '
                               'and a red-and-cream diamond-lattice tabard over dark grey mail, '
                               'shouldering a broad steel-bladed axe on a plain wooden haft while '
                               'holding a slim straight sword with a gold disc pommel', 'foot'),
    'elite_iron_pagoda':      ('a single armoured Jurchen heavy cavalryman on a fully barded horse, '
                               'his face hidden behind a close-fitting dark grey riveted iron '
                               'face-mask under a polished steel helmet with gold brow bands and a '
                               'tall red horsehair plume, dark grey gold-trimmed '
                               'lamellar over red robes, holding one long pole-glaive, the horse in '
                               'grey lamellar barding', 'mounted'),
    'elite_tiger_cavalry':    ('a single horseman wearing a white tiger-head helm with the pelt '
                               'draping over his shoulders, grey lamellar with a gilt brass pauldron '
                               'and a deep-red silk sash, holding one long steel-bladed spear with a '
                               'red pennant, riding a pale dapple-grey horse in white lamellar '
                               'barding', 'mounted'),
    'elite_white_feather_guard': ('a single foot guardsman in a domed gold helmet with two tall '
                               'dark-red feather plumes and a grey iron face-mask, dark grey scale '
                               'armour with gold-edged pauldrons and a red-striped skirt, holding '
                               'one crescent-bladed pole-axe and a tall brown wooden shield with '
                               'gold scrollwork', 'foot'),
    'jian_swordsman':         ('a single Chinese foot swordsman in a dark iron helmet with red-lined '
                               'edges and a black two-pronged crest, a scarlet cloak and cream '
                               'fur-trimmed shoulder garment, holding a straight steel sword with a '
                               'gold hilt and a tall red-planked shield with a silver zigzag rim',
                               'foot'),
    'elite_fire_archer':      ('a single Chinese foot archer dressed mainly in a long deep-crimson '
                               'red robe reaching his ankles, with only a small burnt-orange quilted '
                               'shoulder-and-upper-chest panel laced in red over it and a square '
                               'silver mirror-plate on the chest, wearing a red cloth turban with a '
                               'tall dark plume, drawing a LARGE dark recurve bow whose nocked arrow '
                               'has a gold dragon-head arrowhead engulfed in bright yellow flame',
                               'foot'),
    'xianbei_raider':         ('a single bare-headed Xianbei horse archer with long black hair in a '
                               'white-cloth topknot, a crimson robe under a shaggy cream sheepskin '
                               'shoulder cape, holding a pale horn recurve bow, riding a stocky '
                               'grey-dun steppe pony with a dark-red gold-studded saddle blanket',
                               'mounted'),
    'heavy_hei_kuang_cavalry': ('a single armoured Chinese lancer in a silver domed helmet with gold '
                               'ribs, two tall black feather plumes and a gold scale aventail, a deep '
                               'red cloth surcoat painted with a white Chinese character over '
                               'blue-grey lamellar, tall red back banners, couching one long lance, '
                               'on a red-barded horse', 'mounted'),
}

# Optional minimal per-unit correction appended to the prompt (fixes a specific drift
# without otherwise changing the faithful-refine intent).
EXTRAS = {
    'elite_blackwood_archer': 'His face is clean-shaven with no beard and no facial hair.',
    'elite_temple_guard': ('He is a TALL, full-height adult with long legs and normal athletic '
                           'proportions - not squat, not stocky, not dwarfish. He stands upright '
                           'with his head level and facing forward, not tilted down.'),
    # Champi has historically rendered squat and barefoot - state both up front (workflow doc S8).
    'elite_champi_warrior': ('He is a TALL, full-height adult with long legs and normal athletic '
                             'proportions - not squat, not stocky, not dwarfish. He stands upright '
                             'with his head level. He WEARS BOOTS on his feet - he is not barefoot. '
                             'He holds exactly ONE mace and ONE shield.'),
    'elite_ibirapema_warrior': ('He is BAREFOOT, with bare feet and visible toes. He carries exactly '
                             'ONE long two-handed wooden club held horizontally across his waist - '
                             'not a spear, not two weapons. He is a TALL, full-height adult with '
                             'long legs, not squat or stocky.'),
    'slinger':               ('He wears open tan leather sandals with ankle straps - not boots and '
                              'not barefoot. He carries NO shield: the golden-yellow panel is a '
                              'hanging cloth. The sling hangs slack in his hand, not whirling. He is '
                              'a TALL, full-height adult with long legs, not squat or stocky.'),
    'elite_bolas_rider':     ('The bolas has exactly THREE cords meeting at one knot in his raised '
                              'fist, held up behind his head. The horse tack is braided tan '
                              'plant-fibre rope and woven matting, not leather or metal, and there '
                              'are no stirrups.'),
    'warrior_priest':        ('He carries TWO weapons at once: a broad axe resting over his left '
                              'shoulder and a slim straight sword held low in his right hand. He '
                              'wears grey-brown ankle shoes with cream cloth strips wound around his '
                              'shins. He has a thick dark beard. There is NO cross and no religious '
                              'insignia anywhere on him.'),
    # Face is masked, but by a SHORT fitted plate - not the long draping mail curtain, and not
    # a bare face. Both wrong readings have been rendered once each; state the shape exactly.
    'elite_iron_pagoda':     ('His face is COMPLETELY COVERED by a close-fitting dark grey riveted '
                              'iron face-mask that stops at the jaw line - no skin, no eyes, no '
                              'moustache, no bare face anywhere. It is a SHORT fitted plate mask '
                              'hugging the face, NOT a long hanging mail curtain and NOT a veil '
                              'draping down over his chest. A separate gold beast-face ornament with '
                              'red-outlined eyes and fangs sits low on the armour beside him, well '
                              'below the helmet and not on his face. He holds exactly ONE '
                              'long glaive angled up over his shoulder. The horse is armoured in '
                              'dark grey iron lamellar down to the knees with a pale silver face '
                              'plate and a gold fan crest; its lower legs are bare.'),
    'elite_tiger_cavalry':   ('The headgear is a real WHITE TIGER head worn as a helm - white fur '
                              'with faint dark stripes, erect ears and a black nose - and no human '
                              'face is visible at all. He holds exactly ONE polearm. The horse wears '
                              'a gold face mask and a long skirt of white square lamellar edged in '
                              'red with red tassels.'),
    'elite_white_feather_guard': ('The two helmet plumes are DARK RED, not white - there is no white '
                              'feather anywhere on this unit; the only white is a cream sash at the '
                              'waist. The shield is an enormous tall rectangular wooden pavise '
                              'reaching from ankle to shoulder, reddish-brown planks in an ornate '
                              'gold scrollwork border with a round red jewel at its centre. He wears '
                              'dark shoes.'),
    'jian_swordsman':        ('He holds exactly ONE straight double-edged sword raised in his right '
                              'hand, and ONE tall shield of vertical RED planks with a broad dark '
                              'diagonal band, a round silver boss and a silver rim notched into a '
                              'stepped zigzag. He wears dark green-black shin greaves over tan '
                              'leather boots. No back banners.'),
    # Nocked-arrow geometry is FLUX's worst failure mode (workflow doc S1), but the drawn bow
    # and burning arrowhead ARE this unit's identity - so state the geometry explicitly instead
    # of dodging it: one clean arc, one straight taut string, one straight shaft.
    'elite_fire_archer':     ('The bow is LARGE - a tall dark recurve bow about as long as he is '
                              'tall - held drawn across his body, left hand on the grip and right '
                              'hand pulling the string. Render the bow as ONE clean continuous arc '
                              'with ONE straight taut bowstring, and exactly ONE straight arrow '
                              'shaft lying across the grip. ARROW ORIENTATION IS CRITICAL: the arrow '
                              'points FORWARD, away from the archer. The burning gold dragon head IS '
                              'the arrowhead and sits at the very FRONT TIP of the shaft, the point '
                              'furthest from the archer, wrapped in bright yellow-orange flame that '
                              'streams backwards from it. NOTHING is in front of the dragon head - '
                              'no feathers and no metal point ahead of it. The feather fletching is '
                              'at the REAR of the shaft, back beside the bowstring and his drawing '
                              'hand. There is no second arrowhead anywhere on the shaft. '
                              'COLOUR BALANCE IS CRITICAL: the DEEP CRIMSON RED ROBE IS THE '
                              'DOMINANT GARMENT and covers most of his body, shoulders to ankles. '
                              'The burnt-orange quilted piece is SMALL - a shoulder and upper-chest '
                              'panel only - and must NOT become a full-length vest, a long apron or '
                              'the main colour of the figure. Red clearly outweighs orange. His face '
                              'has a moustache and a light goatee only, NOT a full thick beard. A '
                              'second flaming gold dragon-head arrow sits in the quiver at his hip. '
                              'His headgear is soft red cloth, not metal. He wears tan leather '
                              'boots.'),
    'xianbei_raider':        ('His weapon is a BOW, not a sword and not a sabre: a pale horn-coloured '
                              'recurve bow held horizontally across the horse neck, AT REST and not '
                              'drawn, with a single white-shafted arrow laid across it. He wears NO '
                              'helmet - long loose black hair gathered into a topknot under a small '
                              'white cloth cap. He wears brown boots in the stirrups.'),
    'heavy_hei_kuang_cavalry': ('The red panel on his chest is a CLOTH surcoat bearing a painted '
                              'white Chinese character - it is NOT a shield and he carries no shield. '
                              'He holds exactly ONE long lance levelled to his side. Two or three '
                              'tall poles carrying dark red rectangular banners rise from his back. '
                              'The horse wears red quilted cloth barding with white swirling cloud '
                              'motifs edged in gold, and a gold latticed face plate.'),
}


# A few units have a corrupted *_idle_dir06_dat4x upscale (black background + shard
# artifacts). For those, take the pose/aspect reference from the clean ultrasharp render
# instead, so the composition ref does not poison the result.
COMP_FALLBACK_TO_ULTRASHARP = {'heavy_hei_kuang_cavalry'}


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
    ult = os.path.join(udir, f'{slug}_idle_dir06_ultrasharp4x.png')
    dat = (ult if slug in COMP_FALLBACK_TO_ULTRASHARP
           else os.path.join(udir, f'{slug}_idle_dir06_dat4x.png'))
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
