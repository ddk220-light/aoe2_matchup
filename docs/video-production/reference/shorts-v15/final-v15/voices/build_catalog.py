"""Resolve and decode the installed DAT's native attack-command responses."""

from __future__ import annotations

import argparse
from array import array
import json
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH_ROOT = HERE.parents[1]
REPO = BATCH_ROOT.parents[2]
sys.path.insert(0, str(BATCH_ROOT))
import run_batch  # noqa: F401,E402 - initializes the local game/video environment

from extract_intro_music import extract  # noqa: E402
from extract_intro_reference import fnv1  # noqa: E402
from genieutils.datfile import DatFile  # noqa: E402
from overlay.static_stats import GAME  # noqa: E402


DECODER = (
    BATCH_ROOT.parent
    / "video-recreate-blackwood-20260920/story-short-gameart-v8/audio/vgmstream/vgmstream-cli.exe"
)
PACKAGE = GAME / "wwise/Base.pck"
BANK_ID = 232745270
OBJECTS_PATH = BATCH_ROOT / "command-voice-preview/Base-232745270-objects.json"
FIXTURES = REPO / "aoe2x/js_simulation/fixtures/unit_stats"
DAT_PATH = GAME / "resources/_common/dat/empires2_x2_p1.dat"

FIXTURE_ALIASES = {
    "elite_boyar": "elite_boyar_slavs",
    "elite_teutonic_knight": "elite_teutonic_knight_teutons",
    "elite_huskarl": "elite_huskarl_goths",
    "imp_slinger_incas": "imp_slinger_mapuche",
    "elite_magyar_huszar": "elite_magyar_huszar_magyars",
    "paladin_franks": "paladin_spanish",
    "paladin_teutons": "paladin_spanish",
    "elite_genoese_crossbowman": "elite_genoese_crossbowman_italians",
    "elite_leitis": "elite_leitis_lithuanians",
    "elite_plumed_archer": "elite_plumed_archer_mayans",
}

DAT_CIV_ALIASES = {
    "Franks": "French",
    "Mayans": "Mayan",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_folder(item: dict) -> str:
    if item.get("sourceJob"):
        return item["sourceJob"]
    return Path(item["sourceRun"]).parents[1].name


def event_target(entries: dict, event_id: int) -> tuple[int, int]:
    event = entries[str(event_id)]
    raw = bytes.fromhex(event["data"])
    assert event["kind"] == 4
    action_ids = struct.unpack_from(f"<{raw[0]}I", raw, 1)
    # Xianbei Raider layers three actions: a ten-variant weapon/exertion set,
    # a five-variant mounted effect set, and this four-variant spoken response.
    # Keep only the speech action; the other two are retained in
    # xianbei-actions.json as exclusion evidence.
    action_id = 915835144 if event_id == 13823237 else action_ids[0]
    assert action_id in action_ids and (len(action_ids) == 1 or event_id == 13823237)
    action = entries[str(action_id)]
    data = bytes.fromhex(action["data"])
    assert action["kind"] == 3 and data[:2] == b"\x03\x04"
    return action_id, struct.unpack_from("<I", data, 2)[0]


def switch_nodes(entries: dict, container_id: int, civilization: str) -> tuple[int, ...]:
    node = entries[str(container_id)]
    assert node["kind"] == 6
    raw = bytes.fromhex(node["data"])
    marker = struct.pack("<I", fnv1("Civilization"))
    group_at = raw.index(marker)
    cursor = group_at + 9
    child_count = struct.unpack_from("<I", raw, cursor)[0]
    children = struct.unpack_from(f"<{child_count}I", raw, cursor + 4)
    cursor += 4 + child_count * 4
    mapping_count = struct.unpack_from("<I", raw, cursor)[0]
    cursor += 4
    mapping = {}
    for _ in range(mapping_count):
        switch_id, count = struct.unpack_from("<II", raw, cursor)
        mapping[switch_id] = struct.unpack_from(f"<{count}I", raw, cursor + 8)
        cursor += 8 + count * 4
    selected = mapping[fnv1(civilization)]
    assert all(node_id in children for node_id in selected)
    return selected


def random_sounds(entries: dict, container_id: int) -> list[int]:
    node = entries[str(container_id)]
    assert node["kind"] == 5
    raw = bytes.fromhex(node["data"])
    matches = []
    for count in range(1, 65):
        offset = len(raw) - 6 - 12 * count
        if offset < 0 or struct.unpack_from("<I", raw, offset)[0] != count:
            continue
        children = list(struct.unpack_from(f"<{count}I", raw, offset + 4))
        playlist = offset + 4 + 4 * count
        if struct.unpack_from("<H", raw, playlist)[0] != count:
            continue
        ordered = [struct.unpack_from("<I", raw, playlist + 2 + 8 * i)[0] for i in range(count)]
        if sorted(ordered) != sorted(children):
            continue
        if not all(str(child) in entries and entries[str(child)]["kind"] == 2 for child in children):
            continue
        matches.append(ordered)
    assert len(matches) == 1, (container_id, len(matches))
    return matches[0]


def sound_variants(entries: dict, event_id: int, civilization: str):
    action_id, target_id = event_target(entries, event_id)
    target_kind = entries[str(target_id)]["kind"]
    if target_kind == 6:
        containers = switch_nodes(entries, target_id, civilization)
        switch_container_id = target_id
    else:
        containers = (target_id,)
        switch_container_id = None
    variants = []
    for container_id in containers:
        kind = entries[str(container_id)]["kind"]
        sound_ids = random_sounds(entries, container_id) if kind == 5 else [container_id]
        for sound_id in sound_ids:
            sound = entries[str(sound_id)]
            assert sound["kind"] == 2
            media_id = struct.unpack_from("<I", bytes.fromhex(sound["data"]), 5)[0]
            variants.append((container_id, sound_id, media_id))
    return action_id, target_id, switch_container_id, variants


def measure_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        frames = source.getnframes()
        width = source.getsampwidth()
        assert width == 2
        values = array("h")
        values.frombytes(source.readframes(frames))
    peak = max(abs(value) for value in values)
    threshold = peak * 0.02
    audible_frames = [
        index // channels for index, value in enumerate(values) if abs(value) >= threshold
    ]
    first = min(audible_frames)
    last = max(audible_frames)
    target_peak = 32767 * (10 ** (-6 / 20))
    gain = target_peak / peak
    return {
        "durationSeconds": frames / rate,
        "sampleRate": rate,
        "channels": channels,
        "peak": peak / 32767,
        "normalizationGain": gain,
        "normalizationGainDb": 20 * math.log10(gain),
        "audibleThreshold": "2% of file peak",
        "audibleOnsetSeconds": first / rate,
        "audibleEndSeconds": (last + 1) / rate,
        "trailingSilenceSeconds": (frames - last - 1) / rate,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--numbers", nargs="*", type=int)
    args = parser.parse_args()
    wanted = set(args.numbers or range(1, 11))
    batch = read_json(BATCH_ROOT / "batch.json")
    entries = read_json(OBJECTS_PATH)
    dat = DatFile.parse(str(DAT_PATH))
    selected = []
    all_variants = []
    for item in batch["items"]:
        if item["number"] not in wanted:
            continue
        folder = source_folder(item)
        plan_path = BATCH_ROOT / "sources" / folder / "plan.json"
        plan = read_json(plan_path)
        stats_path = BATCH_ROOT / "sources" / folder / "live/run_001/static-stats-overlay/stats.json"
        stats = read_json(stats_path)["units"]
        for side, stat_record in zip(("side2", "side3"), stats, strict=True):
            side_record = plan[side]
            assert stat_record["unit"] == side_record["label"]
            stat = stat_record["stats"]
            assert stat["civ_name"] == side_record["civ"]
            fixture_slug = FIXTURE_ALIASES.get(side_record["slug"], side_record["slug"])
            fixture_path = FIXTURES / f"{fixture_slug}_imperial.json"
            fixture = read_json(fixture_path)
            unit_id = fixture["unit_master"]
            dat_civ = DAT_CIV_ALIASES.get(side_record["civ"], side_record["civ"])
            civ = next(civ for civ in dat.civs if civ.name == dat_civ)
            unit = civ.units[unit_id]
            event_id = unit.bird.wwise_attack_sound_id & 0xFFFFFFFF
            action_id, target_id, switch_container_id, variants = sound_variants(
                entries, event_id, side_record["civ"]
            )
            unit_variants = []
            stem = f"{item['number']:02d}-{side_record['slug']}-{side_record['civ'].lower()}"
            for variant_index, (container_id, sound_id, media_id) in enumerate(variants):
                wem = HERE / f"{stem}-v{variant_index}.wem"
                wav = HERE / f"{stem}-v{variant_index}.wav"
                if not wav.exists():
                    extract(PACKAGE, media_id, wem)
                    subprocess.run(
                        [str(DECODER), "-i", "-o", str(wav), str(wem)],
                        check=True,
                        capture_output=True,
                    )
                measurement = measure_wav(wav)
                record = {
                    "matchupNumber": item["number"],
                    "matchupKey": item["key"],
                    "side": side,
                    "unit": stat_record["unit"],
                    "civilization": stat["civ_name"],
                    "unitId": unit_id,
                    "eventId": event_id,
                    "actionId": action_id,
                    "switchGroup": "Civilization" if switch_container_id else None,
                    "switchId": fnv1(side_record["civ"]) if switch_container_id else None,
                    "switchContainerId": switch_container_id,
                    "eventTargetId": target_id,
                    "containerId": container_id,
                    "soundId": sound_id,
                    "mediaId": media_id,
                    "variant": variant_index,
                    "variantCount": len(variants),
                    "wav": str(wav.resolve()),
                    "rawWav": str(wav.resolve()),
                    "wem": str(wem.resolve()),
                    "bankId": BANK_ID,
                    "bankObjects": str(OBJECTS_PATH.resolve()),
                    "bankPackage": str(PACKAGE.resolve()),
                    "mediaPackage": str(PACKAGE.resolve()),
                    "dat": str(DAT_PATH.resolve()),
                    "fixture": str(fixture_path.resolve()),
                    "plan": str(plan_path.resolve()),
                    "spoken": event_id != 3139909899,
                    "classification": (
                        "generic cavalry/horse command response; same attack/move event and media across civilizations"
                        if event_id == 3139909899
                        else (
                            "unit-specific spoken action from a three-action command event; weapon/exertion and mounted-effect actions excluded"
                            if event_id == 13823237
                            else "civilization-switched spoken attack-command response"
                        )
                    ),
                    "excludedEventActions": (
                        [798346743, 760424777] if event_id == 13823237 else []
                    ),
                    **measurement,
                }
                unit_variants.append(record)
                all_variants.append(record)
            chosen = max(unit_variants, key=lambda record: record["durationSeconds"])
            selected.append(chosen)
            print(
                item["number"], chosen["unit"], chosen["civilization"],
                chosen["eventId"], chosen["variant"], chosen["durationSeconds"],
                chosen["audibleOnsetSeconds"], flush=True,
            )
    payload = {
        "selection": "Longest measured variant for each installed DAT attack-command event; spoken=false records are evidence, not approved voice cues",
        "normalization": "Catalog WAVs are raw; compositor applies constant gain to -6 dBFS",
        "selected": selected,
        "variants": all_variants,
    }
    (HERE / "catalog.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
