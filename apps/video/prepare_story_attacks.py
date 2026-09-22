"""Build lossless, alpha-aware attack frames for story Shorts.

Uses the existing native x2 SLD decoder and local HAT Sharper weights. Native
poses, silhouettes and cadence are retained; no generative animation is added.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO/'graphics'), str(REPO/'graphics/units')]


def tint_native(rgba, mask, tint):
    """Blend the team tint by mask coverage, retaining native facial detail.

    Thresholding the BC4 mask and multiplying every selected pixel by the full
    tint crushed partially painted skin and the Blackwood Archer's face.
    """
    pixels = np.array(rgba)
    coverage = np.asarray(mask, dtype=np.float32)[...,None]/255
    pixels[...,:3] = np.rint(pixels[...,:3]*(1-coverage+coverage*np.asarray(tint))).astype(np.uint8)
    return Image.fromarray(pixels)


def recover_shadows(rgba, gamma):
    """Lift existing shadow detail before HAT, preserving hue, alpha and whites."""
    pixels = np.array(rgba)
    peak = pixels[...,:3].max(axis=2, keepdims=True)/255
    scale = np.maximum(peak, 1/255)**(gamma-1)
    pixels[...,:3] = np.clip(np.rint(pixels[...,:3]*scale), 0, 255).astype(np.uint8)
    return Image.fromarray(pixels)


def attack_canvas_bounds(frames):
    boxes = [frame.getbbox() for frame in frames]
    return (max(0, min(b[0] for b in boxes)-4), max(0, min(b[1] for b in boxes)-4),
            min(frames[0].width, max(b[2] for b in boxes)+4),
            min(frames[0].height, max(b[3] for b in boxes)+4))


def native_shadow_frames(source, tile_size, direction=6):
    """Original game shadows registered to the enhanced sprite's stable crop."""
    import sld_decode
    from build_unit_assets import decode_shadow
    data = Path(source).read_bytes()
    _, records = sld_decode.parse(data)
    count = len(records)//16
    records = records[direction*count:(direction+1)*count]
    box = attack_canvas_bounds([sld_decode.decode_main(data, record) for record in records])
    sx, sy = tile_size[0]/(box[2]-box[0]), tile_size[1]/(box[3]-box[1])
    shadows = []
    for record in records:
        (x, y), mask = decode_shadow(data, record)
        layer = Image.new('RGBA', (mask.shape[1], mask.shape[0]))
        layer.putalpha(Image.fromarray(np.rint(mask*.55).astype(np.uint8)))
        layer = layer.resize((round(layer.width*sx), round(layer.height*sy)), Image.Resampling.LANCZOS)
        shadows.append((layer, (round((x-box[0])*sx), round((y-box[1])*sy))))
    return shadows


def native_attack(source, color):
    import sld_decode
    from build_unit_assets import SPRITE_TINT, SPRITE_TINT_BLUE
    data = Path(source).read_bytes()
    _, records = sld_decode.parse(data)
    count = len(records)//16
    tint = SPRITE_TINT_BLUE if color == 'blue' else SPRITE_TINT
    frames = []
    for record in records[6*count:7*count]:
        frame = sld_decode.decode_main(data, record)
        x, y, width, height, _ = sld_decode._main_geometry(data, record)
        values = sld_decode._decode_player_mask(data, record, width, height)
        if values is not None:
            layer = Image.new('L', (width,height))
            layer.putdata([value for row in values for value in row])
            mask = Image.new('L', frame.size)
            mask.paste(layer, (x,y))
            frame = tint_native(frame, mask, tint)
        frames.append(frame)
    box = attack_canvas_bounds(frames)
    return [frame.crop(box) for frame in frames]


def prepare(output, weights, units=None):
    from spandrel import ModelLoader
    from upscale_refs import upscale_rgba_single
    model = ModelLoader().load_from_file(str(weights)).cuda().eval()
    if units is None:
        units = [('elite_blackwood_archer','u_arc_blackwood_archer_elite','blue',.6),
                 ('elite_huskarl','u_inf_huskarl_elite','red',1)]
    for slug, stub, color, shadow_gamma in units:
        source = REPO/'graphics/game_raw_files'/f'{stub}_attackA_x2.sld'
        frames = native_attack(source, color)
        folder = output/slug
        folder.mkdir(parents=True, exist_ok=True)
        names = []
        for index, frame in enumerate(frames):
            frame = recover_shadows(frame, shadow_gamma)
            enhanced = upscale_rgba_single(frame, model)
            # Preserve soft alpha and full RGB, unlike the old paletted GIF.
            # Supersample the small native sprite before phone-size delivery.
            enhanced = enhanced.resize((frame.width*6, frame.height*6), Image.Resampling.LANCZOS)
            name = f'{index:04d}.png'
            enhanced.save(folder/name)
            names.append(name)
            if index % 10 == 0:
                print(f'{slug}: {index+1}/{len(frames)}', flush=True)
        (folder/'animation.json').write_text(json.dumps({
            'frames':names, 'durationsMs':[50]*len(names), 'source':str(source.resolve()),
            'direction':6, 'teamColor':color, 'model':str(weights.resolve()),
            'teamColorMethod':'Native RGB blended by continuous BC4 mask; no threshold/full-tint replacement',
            'shadowGamma':shadow_gamma, 'shadowRecovery':'Peak-channel curve preserving RGB ratios; no painted or generated face',
            'modelScale':4, 'canvasScale':6, 'alpha':'Native mask, Lanczos; no palette quantization',
            'cadence':'Matches original 50 ms GIF poses; no motion interpolation'}, indent=2))
        print(folder, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--weights', required=True, type=Path)
    parser.add_argument('--units', type=Path, help='JSON array of [slug, native sprite stub, team color, shadow gamma]')
    args = parser.parse_args()
    prepare(args.output, args.weights, json.loads(args.units.read_text()) if args.units else None)
