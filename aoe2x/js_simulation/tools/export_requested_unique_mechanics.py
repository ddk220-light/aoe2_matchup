#!/usr/bin/env python3
"""Export the fully-upgraded mechanics for the captured unique-unit roster.

The list is the exact 19-unit subject roster preserved by the 2026-08-31
Arbalester/Paladin capture manifest.  Values still come from the reference DB
and Genie dat through ``export_unit_mechanics``; this file only records the
stable unit selector and output filename for reproducible regeneration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_unit_mechanics import export_unit_mechanics


UNITS = (
    ("jian_swordsman_wu", "Wu", 1974),
    ("xianbei_raider_wei", "Wei", 1952),
    ("mounted_trebuchet_khitans", "Khitans", 1923),
    ("grenadier_jurchens", "Jurchens", 1911),
    ("war_chariot_shu", "Shu", 1962),
    ("elite_white_feather_guard_shu", "Shu", 1961),
    ("elite_tiger_cavalry_wei", "Wei", 1951),
    ("elite_blackwood_archer_tupi", "Tupi", 2581),
    ("elite_ibirapema_warrior_tupi", "Tupi", 2584),
    ("elite_temple_guard_muisca", "Muisca", 2587),
    ("elite_guecha_warrior_muisca", "Muisca", 2564),
    ("elite_bolas_rider_mapuche", "Mapuche", 2571),
    ("elite_kona_mapuche", "Mapuche", 2568),
    ("elite_hussite_wagon_bohemians", "Bohemians", 1706),
    ("elite_samurai_japanese", "Japanese", 560),
    ("elite_chu_ko_nu_chinese", "Chinese", 559),
    ("elite_kipchak_cumans", "Cumans", 1233),
    ("elite_coustillier_burgundians", "Burgundians", 1657),
    ("elite_obuch_poles", "Poles", 1703),
)

CAPTURE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "aoe2x" / "js_simulation" / "calibration" / "live_observations"
    / "requested_roster_vs_arb_paladin_1x_2026-08-31"
)
UNIT_OPTIONS = {
    "war_chariot_shu": {
        "concrete_form": True,
        "extra_projectile_count": 6,
        "volley_release_interval_seconds": 1 / 3,
        "volley_release_size": 1,
        "volley_release_source": (
            "war_chariot_shu_vs_arbalester run_001 frames.bin: complete "
            "seven-bolt Focus Fire volleys release at 0.334 s median intervals"
        ),
        "weapon_mode": "focus_fire",
    },
    "elite_chu_ko_nu_chinese": {
        "volley_release_interval_seconds": 0.27,
        "volley_release_size": 1,
        "volley_double_release_percent": 34.0,
        "volley_release_source": (
            "elite_chu_ko_nu_chinese_vs_arbalester run_001 frames.bin: "
            "source-attributed arrows release in groups of one or two at "
            "roughly 0.28 s intervals; 91 of 269 complete-volley release "
            "groups contain two arrows"
        ),
        "weapon_mode": "repeating_volley",
    },
}

BARRAGE = {
    "output_slug": "war_chariot_shu_barrage",
    "reference_slug": "war_chariot_shu",
    "civ": "Shu",
    "master": 1980,
    "options": {
        "concrete_form": True,
        # DAT barrage has 9 projectiles; fully researched Bolt Magazine adds
        # the same two projectiles observed on the 5 -> 7 Focus Fire form.
        "extra_projectile_count": 10,
        "volley_release_interval_seconds": 1 / 3,
        "volley_release_size": 1,
        "volley_release_source": (
            "mechanics hypothesis inherited from sibling Focus Fire form "
            "sharing attack graphic 12976; no live Barrage tape is preserved"
        ),
        "weapon_mode": "barrage",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument(
        "--slug",
        action="append",
        choices=[slug for slug, _, _ in UNITS] + [BARRAGE["output_slug"]],
        help="export only this roster slug (repeatable); defaults to all",
    )
    args = parser.parse_args()
    selected = set(args.slug or ())
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for slug, civ, master in UNITS:
        if selected and slug not in selected:
            continue
        fixture = export_unit_mechanics(
            args.reference_db, args.dat, slug, civ, master,
            **UNIT_OPTIONS.get(slug, {}),
        )
        if slug in UNIT_OPTIONS:
            capture_key = (
                "war_chariot_shu_vs_arbalester"
                if slug == "war_chariot_shu"
                else "elite_chu_ko_nu_chinese_vs_arbalester"
            )
            fixture["mode_validation"] = {
                "live_frames_bin": str(
                    CAPTURE_ROOT / capture_key / "run_001" / "raw recordings"
                    / f"{capture_key}.frames.bin"
                ),
                "run": 1,
            }
        output = args.output_directory / f"{slug}_imperial.json"
        output.write_text(
            json.dumps(fixture, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(output)
    if not selected or BARRAGE["output_slug"] in selected:
        barrage = export_unit_mechanics(
            args.reference_db,
            args.dat,
            BARRAGE["reference_slug"],
            BARRAGE["civ"],
            BARRAGE["master"],
            **BARRAGE["options"],
        )
        barrage["mode_validation"] = {
            "live_frames_bin": None,
            "run": None,
            "note": "The preserved live batch contains Focus Fire only.",
        }
        barrage_output = (
            args.output_directory / f"{BARRAGE['output_slug']}_imperial.json"
        )
        barrage_output.write_text(
            json.dumps(barrage, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(barrage_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
