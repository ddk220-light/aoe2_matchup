"""Static stat panels plus timestamped portrait/HP queues from archived gRPC."""
from __future__ import annotations

import argparse
import json
import subprocess
from functools import lru_cache
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from overlay.ffutil import find_ffmpeg
from overlay.static_stats import GAME, REPO, GameFont, portrait_path
from overlay.unit_timeline import decode, ordered_units, sample_at

GRID_W, GRID_H = 256, 800
GRID_Y = 270
COLS, ROWS = 3, 9
TILE = 72
STEP_X, STEP_Y = 80, 81
WHITE = (250, 239, 214, 255)


class UnitGrid:
    def __init__(self, name, color, font):
        self.color, self.font = color, font
        self.portrait = Image.open(portrait_path(name)).convert('RGBA').resize((TILE - 4, TILE - 4), Image.Resampling.LANCZOS)
        self.dead = ImageEnhance.Brightness(ImageOps.grayscale(self.portrait).convert('RGBA')).enhance(.35)

    @lru_cache(maxsize=512)
    def tile(self, hp, max_hp):
        im = Image.new('RGBA', (TILE, STEP_Y - 3), (18, 17, 15, 240))
        d = ImageDraw.Draw(im)
        im.alpha_composite(self.portrait if hp > 0 else self.dead, (2, 2))
        d.rectangle((0, 0, TILE - 1, TILE - 1), outline=(192, 162, 104, 255) if hp > 0 else (74, 71, 66, 255), width=2)
        d.rectangle((1, TILE, TILE - 2, STEP_Y - 5), fill=(20, 19, 17, 255))
        if hp > 0:
            length = round((TILE - 4) * min(1, hp / max(1, max_hp)))
            if length:
                d.rectangle((2, TILE + 1, 1 + length, STEP_Y - 6), fill=self.color)
        return im

    def render(self, units):
        columns = max(COLS, (sum(u['hp'] > 0 for u in units) + ROWS - 1) // ROWS)
        step_x = min(STEP_X, 240 // columns)
        im = Image.new('RGBA', (GRID_W, GRID_H))
        count = sum(u['hp'] > 0 for u in units)
        total = sum(u['hp'] for u in units)
        # Dark header makes the real game font readable against terrain.
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, 239, 55), radius=6, fill=(20, 17, 13, 210))
        self.font.draw(im, (12, 17), str(count), 42, WHITE)
        self.font.draw(im, (86, 25), f'{total:g} HP', 25, WHITE)
        # Replacement bodies can accumulate more historical ids than opening
        # slots. Keep every survivor and only as many dimmed deaths as fit.
        for index, unit in enumerate(ordered_units(units)[:columns * ROWS]):
            # Fill down each column, then advance right: a vertical queue.
            col, row = divmod(index, ROWS)
            renderer = getattr(self, 'entity_renderers', {}).get(unit['id'], self)
            tile = renderer.tile(unit['hp'], unit['maxHp'])
            if step_x < STEP_X:
                tile = tile.resize((step_x - 8, round(tile.height * (step_x - 8) / TILE)), Image.Resampling.LANCZOS)
            im.alpha_composite(tile, (col * step_x, 64 + row * STEP_Y))
        return im


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--preview-only', action='store_true')
    args = parser.parse_args()
    run = args.run_directory.resolve()
    stats_dir = run / 'static-stats-overlay'
    stats = json.loads((stats_dir / 'stats.json').read_text())
    out = run / 'unit-hp-overlay'
    out.mkdir(exist_ok=True)
    data = decode(run)
    if not data['mapping']['alignment']:
        raise ValueError('A verified unit-hp-overlay/alignment.json is required before rendering live HP.')
    (out / 'units.json').write_text(json.dumps(data, separators=(',', ':')))
    rows = data['rows']
    times = [r['videoSeconds'] for r in rows]
    font = GameFont(GAME)
    grids = [UnitGrid(u['unit'], color, font) for u, color in zip(stats['units'], [(46, 92, 226, 255), (204, 42, 37, 255)])]
    for grid in grids:
        variants = [UnitGrid(u['unit'], grid.color, font) for u in stats['units']]
        grid.entity_renderers = {u['id']: variants[i] for i, owner in enumerate(('2','3')) for u in rows[0]['sides'][owner]}
    capture = cv2.VideoCapture(str(run / 'battle.mp4'))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(capture.get(3)), int(capture.get(4))
    if (width, height) != (2560, 1440):
        raise ValueError('This approved layout requires 2560x1440 footage.')
    panels = Image.open(stats_dir / 'panels.png').convert('RGBA')

    def dynamic(t):
        row = sample_at(rows, times, t)
        strip = Image.new('RGBA', (GRID_W * 2, GRID_H))
        for i, owner in enumerate(('2', '3')):
            strip.alpha_composite(grids[i].render(row['sides'][owner]), (GRID_W * i, 0))
        return strip

    for t in sorted({0, min(8, (frames-1)/fps), min(15, (frames-1)/fps), min(18, (frames-1)/fps)}):
        capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = capture.read()
        if not ok:
            raise ValueError(f'Cannot decode preview at {t}s')
        preview = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA))
        preview.alpha_composite(panels)
        strip = dynamic(t)
        preview.alpha_composite(strip.crop((0, 0, GRID_W, GRID_H)), (24, GRID_Y))
        preview.alpha_composite(strip.crop((GRID_W, 0, GRID_W * 2, GRID_H)), (width - 24 - 240, GRID_Y))
        preview.convert('RGB').save(out / f'preview-{t:05.2f}.jpg')
    capture.release()
    if args.preview_only:
        print(out)
        return
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('FFmpeg is required')
    # Feed only the narrow dynamic strips, preserving 60 fps event timing while
    # avoiding a full-size Python raster pass over each gameplay frame.
    filters = ('[1:v]split[l0][r0];[l0]crop=256:800:0:0[l];'
               '[r0]crop=256:800:256:0[r];'
               '[0:v][2:v]overlay=0:0:format=auto[base];'
               '[base][l]overlay=24:270:format=auto[left];'
               '[left][r]overlay=2296:270:format=auto[v]')
    command = [ffmpeg, '-y', '-v', 'error', '-threads', '2', '-i', str(run / 'battle.mp4'),
               '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '512x800',
               '-framerate', str(fps), '-i', 'pipe:0', '-i', str(stats_dir / 'panels.png'),
               '-filter_complex_threads', '1', '-filter_complex', filters,
               '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-threads', '2',
               '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
               '-c:a', 'copy', '-movflags', '+faststart', str(out / 'battle-with-unit-hp.partial.mp4')]
    with (out / 'render.log').open('w') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            for index in range(frames):
                process.stdin.write(dynamic(index / fps).tobytes())
            process.stdin.close()
            if process.wait() != 0:
                raise RuntimeError(f'FFmpeg failed; see {out / "render.log"}')
        except BaseException:
            process.kill()
            process.wait()
            raise
    (out / 'battle-with-unit-hp.partial.mp4').replace(out / 'battle-with-unit-hp.mp4')
    print(out / 'battle-with-unit-hp.mp4')


if __name__ == '__main__':
    main()
