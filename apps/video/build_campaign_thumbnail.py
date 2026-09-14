"""Compose the approved campaign parchment cover from an episode intro plan."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops
from overlay.static_stats import GameFont, GAME


def build(plan_path, prefix, title, subtitle='Matchup'):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    catalog = json.loads((plan_path.parent / 'campaign_catalog.json').read_text())
    theme = plan.get('backgroundTheme') or catalog['preferredByCivilization'].get(plan['civilization'].upper(), catalog['fallback'])
    source = Image.open(GAME / 'widgetui' / theme['background']).convert('RGB')
    art = Image.open(plan_path.parent / plan['art']).convert('RGBA')
    font = GameFont(GAME)
    for mode in ('long', 'shorts'):
        if mode == 'long':
            bg = source.resize((2560, 1080), Image.Resampling.LANCZOS).crop((320, 0, 2240, 1080))
            max_art, top, ys, size = (470, 490), 260, (750, 802), 51
            labels = [title, subtitle]
        else:
            bg = source.resize((4551, 1920), Image.Resampling.LANCZOS).crop((1735, 0, 2815, 1920))
            max_art, top, ys, size = (720, 720), 440, (1220, 1300, 1380), 70
            labels = [title, subtitle.removesuffix(' Matchup'), 'Matchup'] if subtitle.endswith(' Matchup') else [title, subtitle]
        drawing = art.copy()
        drawing.thumbnail(max_art, Image.Resampling.LANCZOS)
        x = (bg.width - drawing.width) // 2
        box = (x, top, x + drawing.width, top + drawing.height)
        bg.paste(ImageChops.multiply(bg.crop(box), drawing.convert('RGB')), box, drawing.getchannel('A'))
        bg = bg.convert('RGBA')
        for label, y in zip(labels, ys):
            fitted = min(size, (bg.width - 120) / font.width(label, 1))
            font.draw(bg, ((bg.width - font.width(label, fitted)) / 2, y), label, fitted)
        if mode == 'long':
            bg = bg.resize((1280, 720), Image.Resampling.LANCZOS)
        output = Path(str(prefix) + '-' + mode + '.jpg')
        output.parent.mkdir(parents=True, exist_ok=True)
        bg.convert('RGB').save(output, quality=92)
        assert output.stat().st_size < 2097152


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--subtitle', default='Matchup')
    args = parser.parse_args()
    build(args.plan, args.prefix, args.title, args.subtitle)
