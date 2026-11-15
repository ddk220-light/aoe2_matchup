"""Siege fallback data for the Matchup Advisor (owner 2026-11-15).

Writes ``data/golden/advisor_siege.json``:
- ``targets``: advisor unit names Onagers / Bombard Cannons counter (slow siege and wagons,
  foot archers, skirmishers, foot gunpowder, elephant archers). Owner-reviewed list.
- ``civs``: civ -> its siege options, from ``aoe2_reference_simulation.db``: "Siege Onager",
  "Onager" (only with Siege Engineers), "Bombard Cannon" ("Houfnice" when available).
  Cross-checked against aoe2techtree on 2026-11-15 (all 56 civs agree).

Usage: python tools/economy/advisor_eco/build_advisor_siege.py
"""
from __future__ import annotations

import json
import sqlite3

from common import REPO, advisor_units, connect

DESTINATION = REPO / "data" / "golden" / "advisor_siege.json"
REFERENCE = REPO / "data" / "golden" / "aoe2_reference_simulation.db"
TARGETS = [
    # slow siege and wagons
    "Scorpion", "Heavy Scorpion", "Elite Ballista Elephant", "Elite Hussite Wagon", "Elite War Wagon",
    "Elite Organ Gun", "Mounted Trebuchet", "War Chariot",
    # foot archers
    "Arbalester", "Crossbowman", "Archer", "Elite Longbowman", "Elite Chu Ko Nu", "Elite Plumed Archer",
    "Elite Rattan Archer", "Elite Genoese Crossbowman", "Elite Composite Bowman", "Elite Blackwood Archer",
    "Elite Fire Archer", "Elite Guecha Warrior",
    # skirmishers
    "Elite Skirmisher", "Imperial Skirmisher", "Skirmisher", "Elite Genitour",
    # foot gunpowder and throwers
    "Hand Cannoneer", "Elite Janissary", "Elite Gbeto", "Elite Chakram Thrower", "Elite Throwing Axeman",
    "Slinger", "Grenadier", "Elite Jarl",
    # elephant archers
    "Elite Elephant Archer",
]


def build():
    names = {u["name"] for u in advisor_units(connect()).values()}
    missing = [t for t in TARGETS if t not in names]
    assert not missing, f"not advisor units: {missing}"
    db = sqlite3.connect(f"file:{REFERENCE}?mode=ro", uri=True)
    civs = {}
    for civ in sorted(r[0] for r in db.execute("SELECT DISTINCT civ_name FROM ref_units")):
        rows = {name: rid for rid, name in db.execute(
            "SELECT id, unit_name FROM ref_units WHERE civ_name=? AND unit_name IN "
            "('Onager','Siege Onager','Bombard Cannon','Houfnice')", (civ,))}
        options = []
        if "Siege Onager" in rows:
            options.append("Siege Onager")
        elif "Onager" in rows and db.execute("SELECT 1 FROM ref_techs_applied WHERE ref_unit_id=? AND tech_name LIKE "
                                             "'%Siege Engineers%'", (rows["Onager"],)).fetchone():
            options.append("Onager")
        if "Houfnice" in rows:
            options.append("Houfnice")
        elif "Bombard Cannon" in rows:
            options.append("Bombard Cannon")
        civs[civ] = options
    return {"schemaVersion": 1, "description": "Siege fallback for the Matchup Advisor "
            "(tools/economy/advisor_eco/build_advisor_siege.py)", "targets": TARGETS, "civs": civs}


def main():
    data = build()
    DESTINATION.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(DESTINATION.relative_to(REPO), sum(1 for v in data["civs"].values() if v), "civs with siege of", len(data["civs"]))


if __name__ == "__main__":
    main()
