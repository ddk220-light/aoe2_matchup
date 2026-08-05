"""Nano Banana Pro (Gemini 3 Pro Image) unit art generator — A/B test vs FLUX.2.

Mirrors graphics/flux2/generate.py exactly (same sprite-pose + icon-color two-reference
conditioning, same TONE / NEG clauses), but sends the two references to Google's
`gemini-3-pro-image-preview` instead of FLUX.2. Lets us compare best-in-class API SOTA
against the local FLUX.2-dev pipeline on the same units.

Usage
-----
    set GEMINI_API_KEY=...   (or pass --api-key)
    D:/miniconda3/python.exe graphics/nanobanana/generate.py --out renders/batch_nb

Outputs land in graphics/nanobanana/renders/<batch>/<slug>.png

Notes
-----
- Uses the SAME dir05 sprite frame (pose anchor) + icon (colors/identity) as FLUX.
- Nano Banana Pro follows instructions better than FLUX, so we keep the prompt SHORT
  (the workflow doc's #1 lesson) and let the references carry the form.
- Aspect ratio is requested via image_config; the sprite ref still drives the actual shape.
"""
import os, sys, time, argparse, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sld_decode as D
from PIL import Image
from google import genai
from google.genai import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW  = os.path.join(ROOT, 'graphics', 'game_raw_files')
ICO  = os.path.join(ROOT, 'apps', 'website', 'static', 'img', 'units')
UNITS_DIR = os.path.join(ROOT, 'graphics', 'units')   # per-unit asset folders
MODEL = 'gemini-3-pro-image-preview'   # Nano Banana Pro

# --- Shared prompt clauses — identical intent to flux2/generate.py --------------------
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
_SUBJECT = {
    'foot':    ("Render ONE SINGLE full-body figure of this unit standing in the exact same "
                "pose, body angle and facing direction as the sprite reference"),
    'mounted': ("Render ONE SINGLE full-body figure of this unit in the exact same pose, body "
                "angle and facing direction as the sprite reference, keeping the animal/mount "
                "and everything carried on it together as one subject"),
    'ship':    ("Render ONE SINGLE armored warship, the whole ship as one subject, seen from "
                "the same side and angle as the sprite reference"),
    'vehicle': ("Render this vehicle together with its horse as ONE single subject, in the exact "
                "same composition and facing as the sprite reference, keeping them together"),
}
# Gemini image aspect ratio by kind (sprite ref still governs the real silhouette)
_ASPECT = {'foot': '3:4', 'mounted': '4:3', 'ship': '16:9', 'vehicle': '4:3'}

# --- UNITS — current batch -------------------------------------------------------------
# (slug, display_name, kind, description)
# References are loaded from graphics/units/<slug>/: the hi-res game icon (icon.png) and
# the dir06 idle pose frame (<slug>_idle_dir06.png).
UNITS = [
    ('blackwood_archer', 'Blackwood Archer', 'foot',
     "a lean bare-chested Tupi/Amazonian foot archer with brown skin painted with WHITE dots and "
     "circles across his chest, arms and face. He wears a crown of white feathers, red-and-white "
     "beaded bands and a simple loincloth, barefoot. A large fan of green, red, yellow and white "
     "feathers spreads like a tail across his back. He holds a plain wooden bow with an arrow nocked "
     "and drawn on the string, aiming; a quiver of arrows rides on his back."),
    ('guecha_warrior', 'Guecha Warrior', 'foot',
     "a Muisca Guecha warrior with dark skin, wearing a flowing WHITE robe with gold trim and a "
     "white head-wrap topped by a gold diadem and a single white feather. A square gold-framed "
     "turquoise pectoral hangs on his chest. He rests a long atlatl (spear-thrower) with a dart "
     "against his shoulder in one hand, and carries a net bag full of round trophy skulls on his "
     "back. Gold bracelets, bare arms."),
    ('kona', 'Kona', 'mounted',
     "a Mapuche Kona, a light cavalryman on a GREY horse. He has dark skin and a bare muscular "
     "torso, wears a white hood/head-wrap with a long white cloth trailing down his back and a white "
     "tunic bearing a blue eight-pointed star emblem at the hip, with woven patterned leggings. He "
     "carries TWO weapons: a long wooden lance leveled forward in his right hand and a flat wooden "
     "macana club in his left hand."),
]

# --- Helpers (shared shape with flux2/generate.py) ------------------------------------
def extract_frame(data, frames, fc, dir_angle):
    for off in range(6):
        idx = min(dir_angle * fc + off, len(frames) - 1)
        im = D.decode_main(data, frames[idx], player_color=None)
        if im:
            return D._finish(im, crop=True, margin=4)
    return None


def make_sprite_ref(rgba, side=1024, fill=0.92):
    """Composite the sprite onto a neutral gray square via its own alpha."""
    bg = Image.new('RGB', (side, side), (70, 70, 74))
    sc = min(side * 0.94 / rgba.width, side * fill / rgba.height)
    up = rgba.resize((max(1, int(rgba.width * sc)), max(1, int(rgba.height * sc))), Image.LANCZOS)
    bg.paste(up, ((side - up.width) // 2, (side - up.height) // 2), up)
    return bg


def load_icon(path):
    ic = Image.open(path).convert('RGB')
    if min(ic.size) < 64:
        ic = ic.resize((256, 256), Image.NEAREST)
    return ic


def build_prompt(name, kind, description):
    subject = _SUBJECT.get(kind, _SUBJECT['foot'])
    return (
        f"This is official unit portrait art for the video game Age of Empires II (AoE2), depicting "
        f"the {name} unit. The FIRST reference image is the in-game AoE2 sprite of the {name} - use "
        f"it for the EXACT pose, build, silhouette and facing direction. The SECOND reference image "
        f"is the unit's official AoE2 icon - use it for the colors, markings and equipment. The unit "
        f"is {description}. {subject}. Show the COMPLETE unit as a single full-body figure from head "
        f"to toe with nothing cut off or cropped. The unit FACES TO THE LEFT at a slight downward "
        f"three-quarter angle (oriented toward the bottom-left), exactly matching the facing of both "
        f"reference images. {NEG} {TONE} Sharp, highly detailed, professional Age of Empires 2 game "
        f"character art, one subject only, one view only."
    )


def part_from_image(im):
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return types.Part.from_bytes(data=buf.getvalue(), mime_type='image/png')


def save_response_image(resp, dst):
    for part in resp.candidates[0].content.parts:
        if getattr(part, 'inline_data', None) and part.inline_data.data:
            Image.open(io.BytesIO(part.inline_data.data)).save(dst)
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description='Generate Nano Banana Pro unit renders.')
    ap.add_argument('--out', default='renders/batch_nb',
                    help='Output dir relative to graphics/nanobanana/ (default: renders/batch_nb)')
    ap.add_argument('--api-key', default=os.environ.get('GEMINI_API_KEY'),
                    help='Gemini API key (default: $GEMINI_API_KEY)')
    ap.add_argument('--skip-existing', action='store_true', default=True)
    args = ap.parse_args()

    if not args.api_key:
        print('ERROR: no API key. Set GEMINI_API_KEY or pass --api-key.')
        sys.exit(1)

    out_dir = os.path.join(os.path.dirname(__file__), args.out)
    os.makedirs(out_dir, exist_ok=True)
    client = genai.Client(api_key=args.api_key)

    todo = [u for u in UNITS
            if not (args.skip_existing and os.path.exists(os.path.join(out_dir, f'{u[0]}.png')))]
    if not todo:
        print('All units already generated.'); return

    t0 = time.time()
    for slug, name, kind, description in todo:
        udir = os.path.join(UNITS_DIR, slug)
        pose_path = os.path.join(udir, f'{slug}_idle_dir06.png')   # canonical dir06 pose ref
        icon_path = os.path.join(udir, 'icon.png')                 # hi-res game UI icon
        if not os.path.exists(pose_path):
            print(f'  SKIP {slug}: missing {pose_path} (run build_unit_assets.py)'); continue
        if not os.path.exists(icon_path):
            print(f'  SKIP {slug}: missing {icon_path} (run build_unit_assets.py)'); continue

        pose = Image.open(pose_path).convert('RGBA')
        sprite_ref = make_sprite_ref(pose)
        icon_ref = load_icon(icon_path)
        prompt = build_prompt(name, kind, description)

        t1 = time.time()
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[prompt, part_from_image(sprite_ref), part_from_image(icon_ref)],
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    image_config=types.ImageConfig(aspect_ratio=_ASPECT.get(kind, '3:4')),
                ),
            )
        except Exception as e:
            print(f'  ERROR {slug}: {e}'); continue

        dst = os.path.join(out_dir, f'{slug}.png')
        if save_response_image(resp, dst):
            print(f'  {slug} -> {dst} ({round(time.time()-t1,1)}s, {kind}, hi-res refs)',
                  flush=True)
        else:
            txt = getattr(resp, 'text', None)
            print(f'  NO IMAGE for {slug}: {txt}')

    print(f'Done. Total {round((time.time()-t0)/60,1)} min')
    print(f'Next: python graphics/nanobanana/compare.py {" ".join(u[0] for u in todo)}')


if __name__ == '__main__':
    main()
