"""Static in-game-style unit panels, rendered from installed game UI assets.

No live HP ingestion: base + technology stats stay fixed throughout the clip.
Matchup bonuses are annotations, not changes to the underlying unit stats.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from overlay.ffutil import find_ffmpeg

REPO = Path(__file__).resolve().parents[3]
GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/AoE2DE")
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


def bonus_damage(attacker, defender):
    attacks = {int(k): v for k, v in json.loads(attacker['final_attacks_json']).items()}
    armors = {int(k): v for k, v in json.loads(defender['final_armors_json']).items()}
    return sum(max(0, amount - armors[c]) for c, amount in attacks.items()
               if c not in (3, 4) and c in armors and amount > 0)


def modifiers(unit, enemy):
    return {'attackBonus': bonus_damage(unit, enemy)}


def panel(unit, enemy, font, game, color):
    width, height = 590, 344
    texture = Image.open(game / 'widgetui/textures/ingame/panels/single-selection-panel_full.png').convert('RGBA')
    # Exclude the native expand/collapse control strip at the right edge.
    texture = texture.crop((0, 0, 755, 376)).resize((width, height), Image.Resampling.LANCZOS)
    image = texture.copy()
    draw = ImageDraw.Draw(image)
    title_size = min(37, 496 / font.width(unit['unit_name'], 1))
    font.draw(image, (43, 47), unit['unit_name'], title_size)
    portrait = Image.open(REPO / 'apps/website/static/img/units' / (unit['unit_name'].replace(' ', '_') + '.png')).convert('RGBA')
    portrait = portrait.resize((132, 132), Image.Resampling.LANCZOS)
    draw.rectangle((28, 74, 165, 211), fill=(25, 23, 23), outline=(97, 77, 52), width=3)
    image.alpha_composite(portrait, (31, 77))
    draw.rectangle((29, 214, 164, 225), fill=color, outline=INK, width=2)
    font.draw(image, (30, 234), f"{number(unit['final_hp'])}/{number(unit['final_hp'])}", 28)
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
            size = min(24, (550 - end - 12) / font.width(label, 1))
            font.draw(image, (end + 12, y + 3), label, size, GREEN)
    draw.line((190, 251, 555, 251), fill=(133, 95, 57), width=1)
    notes = (['Per kill: +10 HP, +1 attack', 'Maximum: +40 HP, +4 attack']
             if unit['unit_slug'] == 'elite_tiger_cavalry_wei' else
             ['Arrows ignore pierce armor.'])
    for i, line in enumerate(notes):
        font.draw(image, (192, 258 + i * 18), line, 20)
    return image, mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--game', type=Path, default=GAME)
    args = parser.parse_args()
    run = args.run_directory.resolve()
    plan = json.loads((run.parent.parent / 'plan.json').read_text())
    expected = ('elite_tiger_cavalry_wei', 'elite_composite_bowman_armenians')
    if (plan['side2']['slug'], plan['side3']['slug']) != expected:
        raise ValueError('This first overlay design supports the approved Tiger/Composite pilot only.')
    connection = sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    units = [dict(connection.execute('SELECT * FROM ref_units WHERE unit_slug=? AND civ_name=? AND age=?',
             (plan[key]['slug'], plan[key]['civ'], 'Imperial')).fetchone()) for key in ('side2', 'side3')]
    connection.close()
    out = run / 'static-stats-overlay'
    out.mkdir(exist_ok=True)
    font = GameFont(args.game)
    overlay = Image.new('RGBA', (2560, 1440))
    metadata = []
    for index, unit in enumerate(units):
        card, mod = panel(unit, units[1-index], font, args.game, (46, 92, 226) if index == 0 else (204, 42, 37))
        overlay.alpha_composite(card, (24 if index == 0 else 2560-24-card.width, 1440-18-card.height))
        metadata.append({'unit': unit['unit_name'], 'stats': unit, 'matchupModifiers': mod})
    overlay.save(out / 'panels.png')
    (out / 'stats.json').write_text(json.dumps({'static': True, 'font': 'installed game combined MSDF atlas',
        'source': 'data/golden/aoe2_reference.db', 'units': metadata,
        'modifierMeaning': 'Green parentheses: outgoing bonus damage after matching bonus armor, separate from base attack and upgrades. No armor penalties are displayed.'}, indent=2)+'\n')
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
