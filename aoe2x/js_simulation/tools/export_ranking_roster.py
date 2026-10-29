"""Freeze the agreed Imperial land-ranking roster, including patch 185872 units."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from aoe2x.rank.derive_unit_rankings import build_slug_to_line
from aoe2x.sim.unit_lines import CIV_MISSING_UNITS, UNIT_LINES

# These additions are present in the patched reference DB but not in the older
# website line registry. This campaign mapping does not change the website.
PATCH_LINES = {
    "heavy_mounted_crossbowman": "cav_archer",
    "elite_varangian_guard": "militia",
    "elite_hearth_troop_saxons": "militia",
    "elite_jomsviking_danes": "militia",
    "elite_jarl_varangians": "gunpowder",  # Ranged, as specified by the owner.
}
GROUPS = {"Infantry": "infantry", "Ranged": "archery", "Cavalry": "stable"}


def export_roster(database: str) -> dict:
    lines = build_slug_to_line() | PATCH_LINES
    groups = {line: group for group, aggregate in GROUPS.items()
              for line in UNIT_LINES[aggregate]["sub_lines"]}
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""SELECT u.id,u.civ_name,u.unit_slug,u.unit_name,u.unit_type,
        m.mode,m.is_default,m.mechanics_json FROM ref_units u
        LEFT JOIN ref_unit_mechanics m ON u.id=m.ref_unit_id AND m.is_default=1
        WHERE u.age='Imperial' ORDER BY u.civ_name,u.unit_slug""").fetchall()
    units, excluded = [], []
    seen = set()
    for row in rows:
        key = (row["civ_name"], row["unit_slug"])
        if key in seen:
            raise ValueError(f"Duplicate default profile: {key}")
        seen.add(key)
        line = lines.get(row["unit_slug"])
        group = groups.get(line)
        entry = {"referenceId": row["id"], "civilization": key[0], "slug": key[1],
                 "name": row["unit_name"], "line": line, "group": group, "mode": row["mode"]}
        if key in CIV_MISSING_UNITS:
            excluded.append(entry | {"reason": "civilization cannot field this line"})
        elif group:
            if not row["mechanics_json"]:
                raise ValueError(f"Missing mechanics: {key}")
            if key[1] == "war_chariot_shu" and row["mode"] != "focus_fire":
                raise ValueError("War Chariot must use focus mode")
            units.append(entry)
        else:
            if line is None and not (row["unit_type"] == "naval" or any(
                    name in key[1] for name in ("galleon", "longship", "xebec"))):
                raise ValueError(f"Unclassified Imperial land unit: {key}")
            excluded.append(entry | {"reason": "naval or anti-building/siege group outside agreed land pools"})
    conn.close()
    return {"scope": "Imperial Infantry, Ranged and Cavalry; scoring deferred",
            "source": "UNIT_LINES first-line-wins plus explicit patch185872 additions",
            "units": units, "excluded": excluded,
            "counts": dict(Counter(u["group"] for u in units)),
            "civilizations": len({u["civilization"] for u in units})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="data/golden/aoe2_reference_simulation.db")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    roster = export_roster(args.database)
    Path(args.output).write_text(json.dumps(roster, indent=2) + "\n")
    print(json.dumps({"counts": roster["counts"], "civilizations": roster["civilizations"],
                      "units": len(roster["units"]), "excluded": len(roster["excluded"])}))
