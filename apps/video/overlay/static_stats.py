"""Static in-game-style unit panels, rendered from installed game UI assets.

No live HP ingestion: base + technology stats stay fixed throughout the clip.
Matchup bonuses are annotations, not changes to the underlying unit stats.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from overlay.ffutil import find_ffmpeg
from overlay.civ_theme import panel_art, theme_for

REPO = Path(__file__).resolve().parents[3]
# Offline art/intro tools share this override; capture paths remain in aoe2lab.toml.
GAME = Path(os.environ.get("AOE2_GAME_DIR", "C:/Program Files (x86)/Steam/steamapps/common/AoE2DE"))
INK = (57, 28, 27, 255)
GREEN = (24, 112, 35, 255)


class GameFont:
    """Render the installed game's multichannel signed-distance font atlas."""
    def __init__(self, game: Path):
        self.root = game / "resources/_common/fonts"
        self.glyphs = {}
        pattern = re.compile(r"Glyph - '(.)'.*?UV\(([^,]+), ([^)]+)\), ST\(([^,]+), ([^)]+)\), Atlas\((\d+)\), XO\(([^)]+)\), YO\(([^)]+)\), HAdvance\(([^)]+)\)")
        for line in (self.root / "combined.txt").read_text(encoding="utf-8").splitlines():
            match = pattern.search(line)
            if match:
                ch, *values = match.groups()
                self.glyphs[ch] = list(map(float, values))
        self.pages = {}

    def width(self, text, size):
        return sum(self.glyphs[c][-1] for c in text) * size / 64

    def draw(self, canvas, xy, text, size, color=INK):
        x, y = xy
        scale = size / 64
        for ch in text:
            u, v, s, t, page, xo, yo, advance = self.glyphs[ch]
            if ch != " ":
                page = int(page)
                if page not in self.pages:
                    self.pages[page] = Image.open(self.root / f"combined_{page:04}.png").convert("RGB")
                atlas = self.pages[page]
                box = tuple(round(z * atlas.width) for z in (u, v, s, t))
                glyph = atlas.crop(box)
                glyph = glyph.resize((max(1, round(glyph.width * scale)), max(1, round(glyph.height * scale))), Image.Resampling.BILINEAR)
                distance = np.median(np.asarray(glyph).astype(float), axis=2) / 255
                alpha = (np.clip((distance - .5) * 8 * scale + .5, 0, 1) * 255).astype('uint8')
                layer = Image.new("RGBA", glyph.size, color)
                layer.putalpha(Image.fromarray(alpha))
                canvas.alpha_composite(layer, (round(x + xo * scale), round(y + yo * scale)))
            x += advance * scale
        return x


def number(value):
    return f"{value:g}"


def upgraded(unit, key):
    base, final = unit[f"base_{key}"], unit[f"final_{key}"]
    delta = final - base
    return number(base) + (f"{delta:+g}" if delta else "")


def portrait_path(name):
    if name == 'Missionary':
        stats = json.loads(Path(__file__).with_name('supplemental-stats.json').read_text())['missionary_spanish']
        return GAME / f"resources/_common/wpfg/resources/uniticons/{stats['icon_id']}_50730.png"
    aliases = {'Elite Ratha (Melee)': 'Elite Ratha', 'Elite Ratha (Ranged)': 'Elite Ratha',
               'Elite White Feather Guard': 'Elite White Feather Crossbowman',
               'War Chariot (Focus Fire)': 'War Chariot', 'War Chariot (Barrage)': 'War Chariot'}
    return REPO / 'apps/website/static/img/units' / (aliases.get(name, name).replace(' ', '_') + '.png')


def resolve_stats(connection, side):
    supplemental = Path(__file__).with_name('supplemental-stats.json')
    if supplemental.exists():
        row = json.loads(supplemental.read_text()).get(side['slug'])
        if row: return row
    name = 'War Chariot' if side['label'].startswith('War Chariot (') else side['label']
    rows = connection.execute('SELECT * FROM ref_units WHERE unit_name=? AND civ_name=? AND age=?',
                              (name, side['civ'], 'Imperial')).fetchall()
    if len(rows) != 1:
        raise ValueError(f"No unambiguous reference stats for {side['label']} / {side['civ']}")
    result = dict(rows[0]); result['unit_name'] = side['label']
    if name != side['label']:
        profile = json.loads((REPO / 'aoe2x/js_simulation/fixtures/unit_stats' / (side['slug']+'_imperial.json')).read_text())
        result.update(final_attacks_json=json.dumps(profile['attack_classes']),
                      final_attack=max(profile['attack_classes'].get('3',0),profile['attack_classes'].get('4',0)),
                      final_range=profile['attack_range_tiles'],final_reload_time=profile['reload_seconds'])
    return result


def bonus_damage(attacker, defender):
    attacks = {int(k): v for k, v in json.loads(attacker['final_attacks_json']).items()}
    armors = {int(k): v for k, v in json.loads(defender['final_armors_json']).items()}
    return sum(max(0, amount - armors[c]) for c, amount in attacks.items()
               if c not in (3, 4) and c in armors and amount > 0) * (1-(defender.get('bonus_damage_reduction') or 0))


def modifiers(unit, enemy):
    return {'attackBonus': bonus_damage(unit, enemy)}


def effective_cost(side):
    """Recorded, discounted per-unit price (already normalized for batch units)."""
    return {resource:side['effectiveCost'][resource] for resource in ('food','wood','gold')}


def special_effects(unit, *, relics=0):
    notes = (['Per kill: +10 HP, +1 attack', 'Maximum: +40 HP, +4 attack']
             if unit['unit_slug'] == 'elite_tiger_cavalry_wei' else
             ['Arrows ignore pierce armor.'] if unit['ignores_pierce_armor'] else
             ['Attacks ignore melee armor.'] if unit['ignores_melee_armor'] else [])
    if unit.get('bleed_dps',0) > 0 and unit.get('bleed_duration',0) > 0:
        notes.append('Poison damage' if 'blackwood_archer' in unit['unit_slug'] else 'Damage over time')
    if unit.get('armor_strip_per_hit',0) > 0:
        notes.append('Strips armor on each hit')
    if unit.get('charge_attack_melee',0):
        notes.append('Melee charge attack')
    if unit.get('attack_bonus_nearby',0) > 0:
        notes.append('Nearby cavalry boost attack')
    if unit.get('hp_regen',0) > 0:
        notes.append('Regenerates HP')
    if unit.get('splash_on_hit_radius',0) > 0:
        notes.append('Splash damage on impact')
    if unit.get('total_projectiles',1) > 1:
        notes.append('Fires multiple projectiles')
    if unit.get('charge_projectile_count',0) > 0:
        notes.append('Charged projectile volley')
    if relics and unit['unit_slug'] == 'elite_leitis_lithuanians':
        notes.append(f'{relics} relics (+{relics} attack)')
    return notes


def panel(unit, enemy, font, game, color, *, details=None):
    width, height = 590, 390 if details is not None else 344
    theme = theme_for(game, unit['civ_name'])
    image = panel_art(theme, (width, height))
    draw = ImageDraw.Draw(image)
    title_size = min(37, 480 / font.width(unit['unit_name'], 1))
    font.draw(image, (43, 47), unit['unit_name'], title_size)
    portrait = Image.open(portrait_path(unit['unit_name'])).convert('RGBA')
    portrait = portrait.resize((132, 132), Image.Resampling.LANCZOS)
    draw.rectangle((28, 74, 165, 211), fill=(25, 23, 23), outline=(97, 77, 52), width=3)
    image.alpha_composite(portrait, (31, 77))
    draw.rectangle((29, 214, 164, 225), fill=color, outline=INK, width=2)
    # The Polish frame's embroidered inner edge is wider than the other themes.
    hp_x = 43 if unit['civ_name'] == 'Poles' else 30
    font.draw(image, (hp_x, 234), f"{number(unit['final_hp'])}/{number(unit['final_hp'])}", 28)
    emblem = Image.open(theme['emblemPath']).convert('RGBA')
    emblem = emblem.crop(emblem.getbbox())
    emblem.thumbnail((44, 48), Image.Resampling.LANCZOS)
    # Center the badge on the portrait frame corner, like a subscript.
    image.alpha_composite(emblem, (165 - emblem.width // 2, 211 - emblem.height // 2))
    mod = modifiers(unit, enemy)
    pierce = json.loads(unit['final_attacks_json']).get('3', 0) > json.loads(unit['final_attacks_json']).get('4', 0)
    attack_icon = 'pierceAttackBypass' if pierce and unit['ignores_pierce_armor'] else 'pierceAttack' if pierce else 'damage'
    rows = [(attack_icon, upgraded(unit, 'attack'), mod['attackBonus']),
            ('armor', upgraded(unit, 'melee_armor') + ' / ' + upgraded(unit, 'pierce_armor'), 0)]
    if unit['final_range'] > 0:
        rows.append(('range', upgraded(unit, 'range'), 0))
    rows += [('reloadTime', f"{unit['final_reload_time']:.2f}", 0),
             ('movementSpeed', f"{unit['final_speed']:.2f}", 0)]
    for i, (icon, value, delta) in enumerate(rows):
        y = 78 + i * 35
        symbol = Image.open(game / f'widgetui/textures/ingame/staticons/{icon}.png').convert('RGBA')
        symbol.thumbnail((31, 31), Image.Resampling.LANCZOS)
        image.alpha_composite(symbol, (194, y - 3))
        end = font.draw(image, (239, y), value, 29)
        if delta:
            label = f'({number(delta)} bonus damage)'
            size = min(24, (526 - end - 12) / font.width(label, 1))
            font.draw(image, (end + 12, y + 3), label, size, GREEN)
    draw.line((190, 251, 526, 251), fill=(133, 95, 57), width=1)
    notes = (['Per kill: +10 HP, +1 attack', 'Maximum: +40 HP, +4 attack']
             if unit['unit_slug'] == 'elite_tiger_cavalry_wei' else
             ['Arrows ignore pierce armor.'] if unit['ignores_pierce_armor'] else
             ['Attacks ignore melee armor.'] if unit['ignores_melee_armor'] else [])
    if details is not None:
        notes = details['effects']
    for i, line in enumerate(notes):
        font.draw(image, (192, 258 + i * (22 if details is not None else 18)), line, 22 if details is not None else 20,
                  GREEN if details is not None else INK)
    if details is not None:
        costs = [(resource,number(details['cost'][resource]))
                 for resource in ('food','wood','gold') if details['cost'][resource] > 0]
        row_width = sum(35+font.width(value,28) for _,value in costs)+60*(len(costs)-1)
        x = round((width-row_width)/2)
        for resource, value in costs:
            symbol = Image.open(game/f'widgetui/textures/ingame/staticons/{resource}.png').convert('RGBA')
            symbol.thumbnail((29,29), Image.Resampling.LANCZOS)
            image.alpha_composite(symbol, (x,303))
            font.draw(image, (x+35,305), value, 28)
            x += round(35+font.width(value,28)+60)
    return image, mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--game', type=Path, default=GAME)
    parser.add_argument('--panels-only', action='store_true', help='Build panel assets without encoding a static video')
    args = parser.parse_args()
    run = args.run_directory.resolve()
    plan = json.loads((run.parent.parent / 'plan.json').read_text())
    connection = sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    units = [resolve_stats(connection, plan[key]) for key in ('side2', 'side3')]
    connection.close()
    out = run / 'static-stats-overlay'
    out.mkdir(exist_ok=True)
    font = GameFont(args.game)
    overlay = Image.new('RGBA', (2560, 1440))
    metadata = []
    for index, unit in enumerate(units):
        card, mod = panel(unit, units[1-index], font, args.game, (46, 92, 226) if index == 0 else (204, 42, 37))
        overlay.alpha_composite(card, (24 if index == 0 else 2560-24-card.width, 1440-18-card.height))
        metadata.append({'unit': unit['unit_name'], 'stats': unit, 'matchupModifiers': mod,
                         'theme': theme_for(args.game, unit['civ_name'])})
    overlay.save(out / 'panels.png')
    (out / 'stats.json').write_text(json.dumps({'static': True, 'font': 'installed game combined MSDF atlas',
        'source': 'data/golden/aoe2_reference.db', 'units': metadata,
        'modifierMeaning': 'Green parentheses: outgoing bonus damage after matching bonus armor, separate from base attack and upgrades. No armor penalties are displayed.'}, indent=2)+'\n')
    if args.panels_only:
        print(out / 'panels.png')
        return
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('FFmpeg is required; put the installed executable on PATH.')
    command = [ffmpeg, '-y', '-v', 'error', '-threads', '2', '-i', str(run / 'battle.mp4'),
        '-i', str(out / 'panels.png'), '-filter_complex_threads', '1',
        '-filter_complex', '[0:v][1:v]overlay=0:0:format=auto[v]', '-map', '[v]', '-map', '0:a?',
        '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'copy', '-movflags', '+faststart', str(out / 'battle-with-stats.mp4')]
    with (out / 'render.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=log, check=True)
    print(out / 'battle-with-stats.mp4')


if __name__ == '__main__':
    main()
