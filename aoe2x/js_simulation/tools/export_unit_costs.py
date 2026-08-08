"""Print base costs for the registry's units, straight from the reference DB.

The purchase rule uses dat BASE costs, not the civ-adjusted final costs -- a
Berbers Hussar costs 80 in the rule and 64 after the civ bonus. This prints
both so the registry's committed numbers can be eyeballed against the source.

    python aoe2x/js_simulation/tools/export_unit_costs.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "golden" / "aoe2_reference.db"

UNITS = [
    ("arbalester", "Chinese"),
    ("champion", "Chinese"),
    ("elite_elephant", "Burmese"),
    ("elite_fire_lancer", "Chinese"),
    ("elite_steppe", "Cumans"),
    ("halberdier", "Bulgarians"),
    ("hand_cannoneer", "Bohemians"),
    ("heavy_camel", "Berbers"),
    ("heavy_cav_archer", "Saracens"),
    ("heavy_scorpion", "Japanese"),
    ("hussar", "Berbers"),
    ("imp_elite_skirm", "Chinese"),
    ("paladin", "Spanish"),
    ("siege_onager", "Slavs"),
]

QUERY = """
    SELECT base_cost_food, base_cost_wood, base_cost_gold,
           final_cost_food, final_cost_wood, final_cost_gold
    FROM ref_units
    WHERE unit_slug = ? AND civ_name = ? AND age = 'Imperial'
"""


def main() -> None:
    uri = f"{DB.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        print(f"{'slug':20s} {'civ':12s} {'base F/W/G':>18s} {'weighted':>9s} {'final weighted':>15s}")
        for slug, civ in UNITS:
            rows = connection.execute(QUERY, (slug, civ)).fetchall()
            if len(rows) != 1:
                raise SystemExit(f"expected exactly one {civ} Imperial {slug}, found {len(rows)}")
            bf, bw, bg, ff, fw, fg = (value or 0 for value in rows[0])
            base = bf + bw + 1.5 * bg
            final = ff + fw + 1.5 * fg
            flag = "" if abs(base - final) < 1e-9 else "   <- civ bonus differs"
            print(f"{slug:20s} {civ:12s} {bf:>5}/{bw:>5}/{bg:>5} {base:>9.1f} {final:>15.1f}{flag}")


if __name__ == "__main__":
    main()
