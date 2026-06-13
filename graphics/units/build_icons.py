"""Bulk icon.png extraction for EVERY military unit.

Writes ONLY the opaque, red (player-2) `icon.png` into graphics/units/<slug>/ for
every distinct named combat unit in the repo's canonical roster
(`aoe2x.extract.extract_units.UNIT_NAMES`). No icon_transparent.png, no sprites,
no animations — that's the per-unit finalize step (finalize_units.py).

Single source of truth:
  * the unit roster + display names  -> aoe2x/extract/extract_units.UNIT_NAMES
  * each unit's icon_id              -> the .dat (genieutils), Gaia civ
  * the red tint + DDS blend         -> build_unit_assets.ICON_TINT / save logic

slug = slugified display name (e.g. "Two-Handed Swordsman" -> two_handed_swordsman).
One folder per DISTINCT display name (every upgrade tier is its own unit).

Existing curated folders are LEFT UNTOUCHED: any slug in SKIP_SLUGS is skipped so
its finalized asset set is never overwritten.

Run with the conda base python (has genieutils + numpy + Pillow):
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_icons.py
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_icons.py --slugs archer knight
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_icons.py --list   # dry run
"""
import os, sys, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import numpy as np
from PIL import Image
from build_unit_assets import ICON_TINT, DDS_DIR, UNITS_DIR, NAME_FORCE_ID, NAME_DROP
from aoe2x.extract.extract_units import UNIT_NAMES

DAT = 'D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat'

# Curated folders that already hold a finalized asset set — never overwrite.
# (The elite reference sets; their plain-slug base units get a normal icon.)
SKIP_SLUGS = {'elite_kona', 'elite_guecha_warrior', 'elite_blackwood_archer'}


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def icon_map_from_dat():
    """distinct display name -> icon_id (first valid), via UNIT_NAMES + the dat."""
    from genieutils.datfile import DatFile
    df = DatFile.parse(DAT)
    icon_by_id = {u.id: u.icon_id for u in df.civs[0].units if u}
    name_icon = {}
    for uid, name in UNIT_NAMES.items():
        if name in NAME_DROP:
            continue
        if name in NAME_FORCE_ID:
            uid = NAME_FORCE_ID[name]
        ic = icon_by_id.get(uid, -1)
        if ic and ic > 0 and name not in name_icon:
            name_icon[name] = ic
    return name_icon


def save_icon_opaque(icon_id, dst):
    """Write ONLY the opaque red icon.png (DDS alpha = player-color mask)."""
    src = os.path.join(DDS_DIR, f'{icon_id:03d}_50730.DDS')
    if not os.path.exists(src):
        return False
    arr = np.array(Image.open(src)).astype(float)
    rgb, a = arr[..., :3], arr[..., 3]
    m = ((255 - a) / 255.0)[..., None]
    L = (rgb[..., 0] * 0.30 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11)[..., None]
    out = np.clip(rgb * (1 - m) + L * np.array(ICON_TINT) * m, 0, 255)
    opaque = np.dstack([out, np.full(a.shape, 255.0)]).astype('uint8')
    Image.fromarray(opaque).save(dst)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset of slugs (default: all)')
    ap.add_argument('--list', action='store_true', help='dry run: print slug -> icon_id and exit')
    ap.add_argument('--overwrite-skip', action='store_true',
                    help='also (re)write icon.png in SKIP_SLUGS folders')
    args = ap.parse_args()

    name_icon = icon_map_from_dat()
    plan = sorted((slugify(n), ic, n) for n, ic in name_icon.items())
    if args.slugs:
        want = set(args.slugs)
        plan = [p for p in plan if p[0] in want]

    if args.list:
        for slug, ic, name in plan:
            tag = '  [SKIP curated]' if slug in SKIP_SLUGS and not args.overwrite_skip else ''
            print(f'{slug:32s} icon {ic:4d}  {name}{tag}')
        print(f'\n{len(plan)} units')
        return

    made = skipped = failed = 0
    for slug, ic, name in plan:
        if slug in SKIP_SLUGS and not args.overwrite_skip:
            skipped += 1
            continue
        udir = os.path.join(UNITS_DIR, slug)
        os.makedirs(udir, exist_ok=True)
        if save_icon_opaque(ic, os.path.join(udir, 'icon.png')):
            made += 1
        else:
            failed += 1
            print(f'  MISSING DDS for {slug} (icon {ic})')
    print(f'icons written: {made} | skipped (curated): {skipped} | failed: {failed}')
    print(f'-> {UNITS_DIR}')


if __name__ == '__main__':
    main()
