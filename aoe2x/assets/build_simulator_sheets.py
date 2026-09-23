"""Compile the ten approved patch185872 GIFs into existing canvas-sheet format.

No new art or source changes. Generated media stays in an ignored output folder;
only the selected sheet metadata/native geometry joins the shared manifests.
An explicit --publish-staging uploads only these ten generated sheet keys.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageSequence
from aoe2x.assets.build_civilization_release import NEW_NAMES, slug

ROOT = Path(__file__).resolve().parents[2]


def publish_staging(outputs):
    from aoe2x.assets import bucket, config
    name = config.bucket_settings()["bucket"]
    assert config.asset_env() == "staging" and name == "aoe2-assets-eu7bi-vhbher4", "staging bucket only"
    client = bucket._client()
    for key, path in outputs:
        client.upload_file(str(path), name, f"sheets/{key}.webp", ExtraArgs={"ContentType": "image/webp"})
        assert client.head_object(Bucket=name, Key=f"sheets/{key}.webp")["ContentLength"] == path.stat().st_size
        print("Verified staging sheet", key)


def build_sheet(attack, idle, destination):
    with Image.open(attack) as gif, Image.open(idle) as idle_image:
        original_size = gif.size
        factor = 96 / max(original_size)
        size = tuple(round(d * factor) for d in original_size)
        frames = [frame.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
                  for frame in ImageSequence.Iterator(gif)]
        durations = [frame.info["duration"] for frame in ImageSequence.Iterator(gif)]
        assert len(set(durations)) == 1, "canvas sheets require uniform frame timing"
        scale = max(original_size) / max(idle_image.size)
    strip = Image.new("RGBA", (size[0] * len(frames), size[1]))
    for index, frame in enumerate(frames):
        strip.paste(frame, (index * size[0], 0))
    strip.save(destination, format="WEBP", lossless=True, exact=True)
    with Image.open(destination) as saved:
        assert saved.size == strip.size
        assert saved.convert("RGBA").tobytes() == strip.tobytes()
    return dict(frames=len(frames), fw=size[0], fh=size[1], dur=durations[0], scale=round(scale, 6))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--game-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish-staging", action="store_true")
    args = parser.parse_args()
    args.output.resolve().relative_to((ROOT / "data/local/generated").resolve())
    if args.publish_staging:
        publish_staging([(slug(name), args.output / f"{slug(name)}.webp") for name in NEW_NAMES.values()])
        return
    args.output.mkdir(parents=True, exist_ok=True)
    metadata_path = ROOT / "apps/website/static/data/anim_sheets.json"
    metadata = json.loads(metadata_path.read_text())
    from graphics.units.extract_sprite_geometry import native_geometry, resolve_source
    from genieutils.datfile import DatFile
    dat = DatFile.parse(args.game_data / "resources/_common/dat/empires2_x2_p1.dat")
    graphic_by_id = {g.id: g for g in dat.graphics if g}
    graphics_dir = args.game_data / "resources/_common/drs/graphics"
    evidence_path = ROOT / "graphics/units/unit_sprite_geometry.json"
    evidence = json.loads(evidence_path.read_text())
    manifest = json.loads((ROOT / "apps/website/static/data/unit_sprites.json").read_text())
    outputs = []
    for name in NEW_NAMES.values():
        key = slug(name)
        source = args.assets / key
        destination = args.output / f"{key}.webp"
        metadata[key] = build_sheet(source / f"{key}_attack_dir06_dat4x.gif",
                                    source / f"{key}_idle_dir06_dat4x.png", destination)
        uid, native_path = resolve_source(name, key, dat, graphic_by_id, graphics_dir)
        entry = native_geometry(native_path)
        published = manifest[name]
        entry.update(name=name, unit_id=uid, source_override=False,
                     web_width=published["w"], web_height=published["h"],
                     aspect_error=round(abs((entry["width"] / entry["height"])
                         / (published["w"] / published["h"]) - 1), 6))
        evidence["units"][key] = entry
        outputs.append((key, destination))
        print(key, metadata[key], destination.stat().st_size)
    metadata_path.write_text(json.dumps(metadata, sort_keys=True) + "\n")
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    runtime = ROOT / "aoe2x/js_simulation/viewer/unit-sprite-geometry.js"
    prefix = runtime.read_text().split("export const NATIVE_SPRITE_HEIGHTS", 1)[0]
    lines = [prefix + "export const NATIVE_SPRITE_HEIGHTS = Object.freeze({"]
    lines += [f'  {json.dumps(key)}: {entry["height"]},' for key, entry in sorted(evidence["units"].items())]
    runtime.write_text("\n".join(lines + ["});", ""]))


if __name__ == "__main__":
    main()
