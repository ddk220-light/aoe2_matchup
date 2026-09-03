#!/usr/bin/env python3
"""Export fully-upgraded mechanics for the 2026-09-02 unique-unit batch.

The roster and concrete DAT masters are the exact forms placed by
``record_ranged_matrix_repeats.py --matrix next-unique``.  Combat values are
still derived by ``export_unit_mechanics`` from the reference database and
current game DAT; this file contains no matchup outcomes or calibration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_unit_mechanics import export_unit_mechanics
from aoe2x.dbgen.v3_runtime_config import DISMOUNT_FORM_BY_CIV_SLUG


UNITS = (
    ("elite_ratha_(melee)_bengalis", "Bengalis", 1740),
    ("elite_ratha_(ranged)_bengalis", "Bengalis", 1761),
    ("elite_konnik_bulgarians", "Bulgarians", 1227),
    ("elite_arambai_burmese", "Burmese", 1128),
    ("elite_urumi_swordsman_dravidians", "Dravidians", 1737),
    ("elite_shrivamsha_rider_gurjaras", "Gurjaras", 1753),
    ("elite_liao_dao_khitans", "Khitans", 1922),
    ("elite_ballista_elephant_khmer", "Khmer", 1122),
    ("elite_fire_archer_wu", "Wu", 1970),
)

# Alternate forms are real DAT units.  Export their complete, fully upgraded
# mechanics rather than copying a few headline stats into the mounted body.
# The ids are the same generation-time inputs used by dbgen/config_combat.py.
DISMOUNT_FORMS = {
    slug: DISMOUNT_FORM_BY_CIV_SLUG[(civ, slug)]
    for slug, civ, _master in UNITS
    if (civ, slug) in DISMOUNT_FORM_BY_CIV_SLUG
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument(
        "--slug",
        action="append",
        choices=[slug for slug, _, _ in UNITS],
        help="export only this roster slug (repeatable); defaults to all",
    )
    args = parser.parse_args()
    selected = set(args.slug or ())
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for slug, civ, master in UNITS:
        if selected and slug not in selected:
            continue
        fixture = export_unit_mechanics(
            args.reference_db,
            args.dat,
            slug,
            civ,
            master,
        )
        dismount_master = DISMOUNT_FORMS.get(slug)
        if dismount_master is not None:
            fixture["dismount_form"] = export_unit_mechanics(
                args.reference_db,
                args.dat,
                slug,
                civ,
                dismount_master,
                concrete_form=True,
            )
            death_animation = fixture.get("death_animation")
            if not death_animation:
                raise ValueError(
                    f"{slug} needs a mounted death animation for its dismount delay"
                )
            fixture["dismount_form"]["spawn_delay_seconds"] = round(
                float(death_animation["seconds"]), 6
            )
            fixture["provenance"]["fields"]["dismount_form"] = (
                "aoe2x.dbgen.unit_analyzer.calculate_form_stats"
                f"(civilization='{civ}', unit_id={dismount_master}, max_age=4)"
                " + the concrete DAT unit's animations and footprint; "
                "spawn_delay_seconds = the mounted DAT unit's full death "
                "animation duration"
            )
        output = args.output_directory / f"{slug}_imperial.json"
        output.write_text(
            json.dumps(fixture, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
