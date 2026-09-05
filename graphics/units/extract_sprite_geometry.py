"""Recover shared native pixel scale for every published unit sprite.

Run with genieutils-py, Pillow and numpy installed:
  python graphics/units/extract_sprite_geometry.py --game-data /path/to/AgeOfEmpires2Data

Reads the game installation only. Outputs compact metadata, not game images.
The existing web exporter independently caps every sprite at 384px; these
measurements restore the original relative scale without measuring bodies or
including weapon height in a normalization target. All measurements are x1
pixels, even when the installed source is x2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "graphics"), str(Path(__file__).parent)]

import numpy as np
from PIL import Image

import sld_decode as decoder
from aoe2x.extract.extract_units import UNIT_NAMES
from build_unit_assets import NAME_FORCE_ID, decode_red, decode_shadow
from resolve_sprites import LAND_SLD, NAVAL_SLD

MANIFEST = ROOT / "apps/website/static/data/unit_sprites.json"
EVIDENCE = ROOT / "graphics/units/unit_sprite_geometry.json"
RUNTIME = ROOT / "aoe2x/js_simulation/viewer/unit-sprite-geometry.js"
REFERENCE = "halberdier"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_geometry(path):
    """Mirror build_idle_refs' first nonempty dir06 pose and shadow crop."""
    data = path.read_bytes()
    _, frames = decoder.parse(data)
    # Match the existing exporter: a few files have a trailing extra frame
    # after their 16 directional runs (e.g. Arambai has 721 = 16*45 + 1).
    count = len(frames) // 16
    if count < 1:
        raise ValueError(f"{path.name}: no full directional run")
    resolution = 2 if path.stem.endswith("_x2") else 1
    for index in range(6 * count, 7 * count):
        frame = frames[index]
        main = decode_red(data, frame)
        if main is not None and main.getbbox():
            break
    else:
        raise ValueError(f"{path.name}: no nonempty dir06 pose")
    canvas = Image.new("RGBA", main.size)
    shadow = decode_shadow(data, frame)
    if shadow:
        (x, y), alpha = shadow
        pixels = np.zeros((*alpha.shape, 4), dtype=np.uint8)
        pixels[..., 3] = (alpha * 0.55).astype(np.uint8)
        canvas.alpha_composite(Image.fromarray(pixels), (x, y))
    canvas.alpha_composite(main)
    crop = canvas.getbbox()
    return {
        "source_file": path.name,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_resolution": resolution,
        "frame_index": index,
        "source_frame_count": len(frames),
        "direction_frame_count": count,
        "canvas": [frame["w"] / resolution, frame["h"] / resolution],
        "hotspot": [frame["hx"] / resolution, frame["hy"] / resolution],
        "crop": [value / resolution for value in crop],
        "width": (crop[2] - crop[0]) / resolution,
        "height": (crop[3] - crop[1]) / resolution,
    }


def resolve_source(name, slug, dat, graphic_by_id, graphics_dir):
    forced = LAND_SLD.get(slug) or NAVAL_SLD.get(slug)
    ids = [NAME_FORCE_ID[name]] if name in NAME_FORCE_ID else [
        uid for uid, display in UNIT_NAMES.items() if display == name
    ]
    candidates = [(None, forced)] if forced else []
    if not forced:
        for uid in ids:
            unit = dat.civs[0].units[uid]
            graphic = graphic_by_id.get(unit.standing_graphic[0]) if unit else None
            if graphic and ("idle" in graphic.file_name.lower()
                            or graphic.file_name.startswith("u_shp_")):
                candidates.append((uid, graphic.file_name))
    for uid, stem in candidates:
        stem = re.sub(r"_x[12]$", "", stem)
        # Prefer the higher resolution used by the web asset pipeline, but
        # divide its measurements by two to retain a single native pixel unit.
        for resolution in (2, 1):
            path = graphics_dir / f"{stem}_x{resolution}.sld"
            if path.is_file():
                return uid, path
    raise ValueError(f"No source idle graphic for {name} ({slug})")


def generate(game_data, evidence_path=EVIDENCE, runtime_path=RUNTIME):
    from genieutils.datfile import DatFile

    dat_path = game_data / "resources/_common/dat/empires2_x2_p1.dat"
    graphics_dir = game_data / "resources/_common/drs/graphics"
    dat = DatFile.parse(dat_path)
    graphics = {graphic.id: graphic for graphic in dat.graphics if graphic}
    manifest = json.loads(MANIFEST.read_text())
    units = {}
    for name, published in sorted(manifest.items()):
        slug = published["slug"]
        uid, path = resolve_source(name, slug, dat, graphics, graphics_dir)
        entry = native_geometry(path)
        # x1/x2 edge quantization and cropping introduce small differences.
        # A large mismatch indicates different art/pose: fail instead of
        # silently assigning a scale to the wrong web image.
        aspect_error = abs((entry["width"] / entry["height"])
                           / (published["w"] / published["h"]) - 1)
        if aspect_error > 0.1:
            raise ValueError(f"{slug}: native/web aspect mismatch {aspect_error:.1%}")
        entry.update(name=name, unit_id=uid,
                     source_override=slug in LAND_SLD or slug in NAVAL_SLD,
                     web_width=published["w"], web_height=published["h"],
                     aspect_error=round(aspect_error, 6))
        units[slug] = entry
    document = {
        "schema_version": 1,
        "reference_unit": REFERENCE,
        "measurement": "x1 native pixels; first nonempty dir06 idle pose including shadow crop",
        "dat_sha256": digest(dat_path),
        "web_manifest_sha256": digest(MANIFEST),
        "units": units,
    }
    evidence_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    lines = [
        "// Generated by graphics/units/extract_sprite_geometry.py; do not edit.",
        "// Native x1 crop heights, not body heights. A shared pixel scale keeps",
        "// long weapons from shrinking their carrier. Evidence: graphics/units/unit_sprite_geometry.json.",
        f"export const NATIVE_REFERENCE_HEIGHT = {units[REFERENCE]['height']};",
        "export const NATIVE_SPRITE_HEIGHTS = Object.freeze({",
    ]
    lines += [f"  {json.dumps(slug)}: {entry['height']}," for slug, entry in sorted(units.items())]
    lines += ["});", ""]
    runtime_path.write_text("\n".join(lines))
    print(f"Extracted {len(units)}/{len(manifest)} sprites; reference {REFERENCE}: "
          f"{units[REFERENCE]['height']:g} native px")
    print(f"Largest native/web aspect difference: {max(e['aspect_error'] for e in units.values()):.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", required=True, type=Path)
    args = parser.parse_args()
    generate(args.game_data)
