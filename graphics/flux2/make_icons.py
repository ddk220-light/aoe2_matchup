"""Promote flux2_hybrid icon renders to the website static unit icons.

For each finished unit in JOBS, the 256×256 transparent icon
(graphics/art/flux2_hybrid/<slug>_idle_dir05_icon.png) overwrites the
corresponding PNG(s) in apps/website/static/img/units/.

Usage
-----
1.  Add the unit to JOBS below (slug -> list of website icon filenames).
2.  Run from the repo root:
      python graphics/flux2/make_icons.py

    To preview what would be written without actually writing:
      python graphics/flux2/make_icons.py --dry-run

Notes
-----
- A unit that exists as both base and elite typically maps to two icons
  (e.g. 'janissary' -> ['Janissary.png', 'Elite_Janissary.png']).
- Run this only after cut_renders.py has created the _icon.png for the slug.
- The function also accepts a custom source path for one-offs where the icon
  lives outside flux2_hybrid/ (e.g. a manually edited crop).
"""
import os, sys, argparse, shutil
from PIL import Image

ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC    = os.path.join(ROOT, 'graphics', 'art', 'flux2_hybrid')
ICO    = os.path.join(ROOT, 'apps', 'website', 'static', 'img', 'units')
SIZE   = 256
MARGIN = 0.96

# ---------------------------------------------------------------------------
# JOBS — add entries here as units are finished
# fmt:  'slug': ['Website_Icon.png', 'Elite_Website_Icon.png']
# ---------------------------------------------------------------------------
JOBS: dict[str, list[str]] = {
    'arambai':            ['Arambai.png', 'Elite_Arambai.png'],
    'ballista_elephant':  ['Ballista_Elephant.png', 'Elite_Ballista_Elephant.png'],
    'battle_elephant':    ['Battle_Elephant.png', 'Elite_Battle_Elephant.png'],
    'berserker':          ['Berserk.png', 'Elite_Berserk.png'],
    'blackwood_archer':   ['Blackwood_Archer.png', 'Elite_Blackwood_Archer.png'],
    'bolas_rider':        ['Bolas_Rider.png', 'Elite_Bolas_Rider.png'],
    'boyar':              ['Boyar.png', 'Elite_Boyar.png'],
    'camel_archer':       ['Camel_Archer.png', 'Elite_Camel_Archer.png'],
    'caravel':            ['Caravel.png', 'Elite_Caravel.png'],
    'cataphract':         ['Cataphract.png', 'Elite_Cataphract.png'],
    'centurion':          ['Centurion.png', 'Elite_Centurion.png'],
    'chakram_thrower':    ['Chakram_Thrower.png', 'Elite_Chakram_Thrower.png'],
    'champi_warrior':     ['Champi_Warrior.png', 'Elite_Champi_Warrior.png'],
    'chukonu':            ['Chu_Ko_Nu.png', 'Elite_Chu_Ko_Nu.png'],
    'composite_bowman':   ['Composite_Bowman.png', 'Elite_Composite_Bowman.png'],
    'conquistador':       ['Conquistador.png', 'Elite_Conquistador.png'],
    'coustillier':        ['Coustillier.png', 'Elite_Coustillier.png'],
    'elephant_archer':    ['Elephant_Archer.png', 'Elite_Elephant_Archer.png'],
    'fire_archer':        ['Fire_Archer.png', 'Elite_Fire_Archer.png'],
    'fire_lancer':        ['Fire_Lancer.png', 'Elite_Fire_Lancer.png'],
    'gbeto':              ['Gbeto.png', 'Elite_Gbeto.png'],
    'genitour':           ['Genitour.png', 'Elite_Genitour.png'],
    'genoesecrossbowman': ['Genoese_Crossbowman.png', 'Elite_Genoese_Crossbowman.png'],
    'ghulam':             ['Ghulam.png', 'Elite_Ghulam.png'],
    'guecha_warrior':     ['Guecha_Warrior.png', 'Elite_Guecha_Warrior.png'],
    'huskarl':            ['Huskarl.png', 'Elite_Huskarl.png'],
    'hussite_wagon':      ['Hussite_Wagon.png', 'Elite_Hussite_Wagon.png'],
    'ibirapema':          ['Ibirapema_Warrior.png', 'Elite_Ibirapema_Warrior.png'],
    'iron_pagoda':        ['Iron_Pagoda.png', 'Elite_Iron_Pagoda.png'],
    'jaguarwarrior':      ['Jaguar_Warrior.png', 'Elite_Jaguar_Warrior.png'],
    'janissary':          ['Janissary.png', 'Elite_Janissary.png'],
    'kamayuk':            ['Kamayuk.png', 'Elite_Kamayuk.png'],
    'karambitwarrior':    ['Karambit_Warrior.png', 'Elite_Karambit_Warrior.png'],
    'keshik':             ['Keshik.png', 'Elite_Keshik.png'],
    'kipchak':            ['Kipchak.png', 'Elite_Kipchak.png'],
    'konnik':             ['Konnik.png', 'Elite_Konnik.png'],
    'leitis':             ['Leitis.png', 'Elite_Leitis.png'],
    'liao_dao':           ['Liao_Dao.png', 'Elite_Liao_Dao.png'],
    'longboat':           ['Longboat.png', 'Elite_Longboat.png'],
    'longbowman':         ['Longbowman.png', 'Elite_Longbowman.png'],
    'magyar_huszar':      ['Magyar_Huszar.png', 'Elite_Magyar_Huszar.png'],
    'mameluke':           ['Mameluke.png', 'Elite_Mameluke.png'],
    'mangudai':           ['Mangudai.png', 'Elite_Mangudai.png'],
    'monaspa':            ['Monaspa.png', 'Elite_Monaspa.png'],
    'obuch':              ['Obuch.png', 'Elite_Obuch.png'],
    'organ':              ['Organ_Gun.png', 'Elite_Organ_Gun.png'],
    'paladin':            ['Paladin.png'],
    'plumedarcher':       ['Plumed_Archer.png', 'Elite_Plumed_Archer.png'],
    'ratha':              ['Ratha.png', 'Elite_Ratha.png'],
    'rattanarcher':       ['Rattan_Archer.png', 'Elite_Rattan_Archer.png'],
    'samurai':            ['Samurai.png', 'Elite_Samurai.png'],
    'serjeant':           ['Serjeant.png', 'Elite_Serjeant.png'],
    'shotelwarrior':      ['Shotel_Warrior.png', 'Elite_Shotel_Warrior.png'],
    'shrivamsha_rider':   ['Shrivamsha_Rider.png', 'Elite_Shrivamsha_Rider.png'],
    'steppe_lancer':      ['Steppe_Lancer.png', 'Elite_Steppe_Lancer.png'],
    'tarkan':             ['Tarkan.png', 'Elite_Tarkan.png'],
    'teutonic_knight':    ['Teutonic_Knight.png', 'Elite_Teutonic_Knight.png'],
    'throwingaxeman':     ['Throwing_Axeman.png', 'Elite_Throwing_Axeman.png'],
    'tiger_cavalry':      ['Tiger_Cavalry.png', 'Elite_Tiger_Cavalry.png'],
    'turtle_ship':        ['Turtle_Ship.png', 'Elite_Turtle_Ship.png'],
    'urumi_swordsman':    ['Urumi_Swordsman.png', 'Elite_Urumi_Swordsman.png'],
    'war_elephant':       ['War_Elephant.png', 'Elite_War_Elephant.png'],
    'war_wagon':          ['War_Wagon.png', 'Elite_War_Wagon.png'],
    'woadraider':         ['Woad_Raider.png', 'Elite_Woad_Raider.png'],
    # temple_guard has a custom source path (added via --slug / manual call):
    'temple_guard':       ['Temple_Guard.png', 'Elite_Temple_Guard.png'],
}


def square_icon(src_path: str, size: int = SIZE, margin: float = MARGIN) -> Image.Image:
    """Load a transparent render and fit it tightly into a square canvas."""
    im = Image.open(src_path).convert('RGBA')
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    box = int(size * margin)
    sc = min(box / im.width, box / im.height)
    w, h = max(1, int(im.width * sc)), max(1, int(im.height * sc))
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im.resize((w, h), Image.LANCZOS), ((size - w) // 2, (size - h) // 2))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description='Write flux2 icons to website static dir.')
    ap.add_argument('--slugs', nargs='*',
                    help='Slugs to process; default = all keys in JOBS')
    ap.add_argument('--dry-run', action='store_true',
                    help='Print what would be written without writing')
    args = ap.parse_args()

    slugs = args.slugs or list(JOBS.keys())
    n_written = 0

    for slug in slugs:
        if slug not in JOBS:
            print(f'  SKIP {slug}: not in JOBS dict')
            continue
        src = os.path.join(SRC, f'{slug}_idle_dir05_icon.png')
        if not os.path.exists(src):
            print(f'  SKIP {slug}: {src} not found — run cut_renders.py first')
            continue
        icon = square_icon(src)
        for target in JOBS[slug]:
            dst = os.path.join(ICO, target)
            if args.dry_run:
                print(f'  DRY-RUN  {slug} -> {target}')
            else:
                icon.save(dst)
                print(f'  wrote {target}  {icon.size} {icon.mode}')
                n_written += 1

    if not args.dry_run:
        print(f'Done — {n_written} file(s) written to {ICO}')


if __name__ == '__main__':
    main()
