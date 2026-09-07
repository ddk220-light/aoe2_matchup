"""Resolve authentic HUD themes and emblems from the installed game registry."""
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image


@lru_cache(maxsize=4)
def civilizations(game):
    return json.loads((Path(game) / 'resources/_common/dat/civilizations.json').read_text(encoding='utf-8'))['civilization_list']


def theme_for(game, civ):
    record = next((r for r in civilizations(game) if r['internal_name'].casefold() == civ.casefold()), None)
    if record is None:
        raise ValueError(f'No installed civilization theme for {civ}')
    style = record['hud_style']
    folder = style.removeprefix('Civ').upper()
    panel = Path(game) / f'widgetui/textures/ingame/panels/{folder}/single-selection-panel.png'
    # The registry's emblem_image_path is a monochrome parchment watermark.
    # Its tech-tree key also identifies the colored shield used in civ menus.
    key = Path(record['tech_tree_image_path']).stem.removeprefix('menu_techtree_')
    emblem = Path(game) / f'widgetui/textures/menu/civs/{key}.png'
    for path in (panel, emblem):
        if not path.is_file():
            raise FileNotFoundError(f'Missing civilization artwork: {path}')
    return {'civilization': record['internal_name'], 'hudStyle': style,
            'panelPath': str(panel), 'emblemPath': str(emblem), 'emblemKind': 'colored civilization shield',
            'source': 'installed resources/_common/dat/civilizations.json'}


def nine_slice(source, size, edge=28):
    """Resize the parchment while keeping border/corner thickness consistent."""
    target = Image.new('RGBA', size)
    sx, sy = [0, edge, source.width-edge, source.width], [0, edge, source.height-edge, source.height]
    dx, dy = [0, edge, size[0]-edge, size[0]], [0, edge, size[1]-edge, size[1]]
    for x in range(3):
        for y in range(3):
            tile = source.crop((sx[x], sy[y], sx[x+1], sy[y+1]))
            tile = tile.resize((dx[x+1]-dx[x], dy[y+1]-dy[y]), Image.Resampling.LANCZOS)
            target.alpha_composite(tile, (dx[x], dy[y]))
    return target


def panel_art(theme, size):
    source = Image.open(theme['panelPath']).convert('RGBA')
    # Standard themed HUD textures share a 1255px frame and a decorative
    # right-hand strip. Exclude its interactive collapse button.
    frame = source.crop((0, 48, 1255, 413))
    output = Image.new('RGBA', size)
    output.alpha_composite(nine_slice(frame, (size[0]-44, size[1])))
    ornament = source.crop((1255, 112, min(source.width, 1338), 413))
    ornament.thumbnail((44, size[1]-100), Image.Resampling.LANCZOS)
    output.alpha_composite(ornament, (size[0]-44, size[1]-ornament.height))
    return output
