"""Decode active-fighter participation for one mixed-golden live matchup.

This is a thin parameterized wrapper around the full-rate participation
decoder. It keeps each source ``frames.bin`` path and repeat explicit and does
not feed any observation back into runtime simulation parameters.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_live_engagement_participation as participation
import analyze_live_melee_group_variance as group


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "remaining_six_fresh_5x_2026-08-31"
)
FIXTURES = {
    "arbalester": "arbalester_chinese_imperial.json",
    "hand_cannoneer": "hand_cannoneer_spanish_imperial.json",
    "heavy_cav_archer": "heavy_cav_archer_saracens_imperial.json",
    "paladin": "paladin_spanish_imperial.json",
    "elite_steppe": "elite_steppe_lancer_cumans_imperial.json",
    "champion": "champion_chinese_imperial.json",
    "heavy_camel": "heavy_camel_turks_imperial.json",
    "scout_cavalry": "scout_cavalry_spanish_imperial.json",
}


def mechanics(slug: str) -> dict:
    path = ROOT / "fixtures" / "unit_stats" / FIXTURES[slug]
    row = json.loads(path.read_text(encoding="utf-8"))
    return {
        "range": float(row["attack_range_tiles"]),
        "min_range": float((row.get("ranged") or {}).get("min_range_tiles", 0)),
        "outline": float(row["outline_size_tiles"]["x"]),
        "collision": float(row["collision_size_tiles"]["x"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--matchup", required=True)
    parser.add_argument("--repeat", action="append", type=int, default=[])
    parser.add_argument("--window-seconds", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    capture_root = args.capture_root.resolve()
    manifest = json.loads(
        (capture_root / "capture_manifest.json").read_text(encoding="utf-8")
    )
    matchup = manifest["matchups"][args.matchup]
    if matchup["family"] not in {"ranged_vs_melee", "melee_vs_ranged"}:
        raise SystemExit(f"{args.matchup} is not a mixed ranged/melee family")
    repeats = args.repeat or [1]
    side2 = matchup["side1"]
    side3 = matchup["side2"]

    participation.MATCHUP_KEY = args.matchup
    participation.CAPTURE_ROOT = capture_root / args.matchup
    participation.WINDOW_SECONDS = args.window_seconds
    master_by_slug = {
        "arbalester": 492,
        "hand_cannoneer": 5,
        "heavy_cav_archer": 474,
        "paladin": 569,
        "elite_steppe": 1372,
        "champion": 567,
        "heavy_camel": 330,
    }
    participation.EXPECTED = {
        2: (master_by_slug[side2["slug"]], side2["count"]),
        3: (master_by_slug[side3["slug"]], side3["count"]),
    }
    # Player 4 is not part of the principal outcome aggregate, but retaining
    # its authored screen in the entity graph lets the decoder distinguish
    # the opening auxiliary engagement from the post-trigger army fight.
    participation.AUXILIARY_EXPECTED = {4: (448, 9)}
    participation.MECHANICS = {
        2: mechanics(side2["slug"]),
        3: mechanics(side3["slug"]),
        4: mechanics("scout_cavalry"),
    }
    group.EXPECTED = participation.EXPECTED

    runs = []
    for repeat in repeats:
        print(f"decoding {args.matchup} run {repeat}", flush=True)
        runs.append(participation.decode_run(repeat))
    mean_rows = participation.mean_per_second(runs)
    output = args.output or (
        capture_root / args.matchup / "live_participation_selected.json"
    )
    output = output.resolve()
    report = {
        "schemaVersion": 1,
        "matchup": args.matchup,
        "family": matchup["family"],
        "side2": side2,
        "side3": side3,
        "windowSeconds": args.window_seconds,
        "sources": [
            {"repeat": run["repeat"], "framesBin": run["framesBin"]}
            for run in runs
        ],
        "runs": runs,
        "meanPerSecond": mean_rows,
        "wholeWindow": participation.window_summary(mean_rows, args.window_seconds),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
