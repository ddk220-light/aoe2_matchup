#!/usr/bin/env python3
"""Extract data from the game's dat file into JSON files.

Usage:
    python3 -m extraction.run
"""

import json
import sys
from pathlib import Path

from genieutils.datfile import DatFile


def extract_all(dat_path, output_dir):
    """Parse dat file once and write all 8 JSON files.

    Args:
        dat_path: Path to empires2_x2_p1.dat
        output_dir: Directory to write JSON files into
    """
    from .extract_constants import ARMOR_CLASSES, CIV_NAMES
    from .extract_effects import (
        extract_civ_tech_trees,
        extract_effects,
        extract_tech_effects,
    )
    from .extract_techs import extract_technologies, generate_tech_ages
    from .extract_units import extract_units

    output_dir.mkdir(exist_ok=True)

    print(f"Loading {dat_path}...")
    df = DatFile.parse(dat_path)
    print("Loaded successfully!")

    # --- Units ---
    print("\nExtracting units...")
    units = extract_units(df)
    print(f"  {len(units)} units")
    with open(output_dir / "units.json", "w") as f:
        json.dump(units, f, indent=2)

    # --- Technologies ---
    print("Extracting technologies...")
    techs = extract_technologies(df)
    print(f"  {len(techs)} technologies")
    with open(output_dir / "technologies.json", "w") as f:
        json.dump(techs, f, indent=2)

    # --- Tech Ages ---
    print("Generating tech ages...")
    tech_ages = generate_tech_ages(techs)
    print(f"  {len(tech_ages['techs'])} standard techs with age data")
    with open(output_dir / "tech_ages.json", "w") as f:
        json.dump(tech_ages, f, indent=2)

    # --- Civilizations ---
    print("Extracting civilizations...")
    civs = []
    for i, civ in enumerate(df.civs):
        if i == 0 or i >= len(CIV_NAMES):
            continue
        if CIV_NAMES[i] is None:
            continue
        civ_data = {"id": i, "name": CIV_NAMES[i]}
        available_units = []
        for unit in civ.units:
            if unit is not None and hasattr(unit, "hit_points") and unit.hit_points > 0:
                if hasattr(unit, "type") and unit.type in [70, 80]:
                    available_units.append(unit.id)
        civ_data["unit_count"] = len(available_units)
        civs.append(civ_data)
    print(f"  {len(civs)} civilizations")
    with open(output_dir / "civilizations.json", "w") as f:
        json.dump(civs, f, indent=2)

    # --- Armor Classes ---
    print("Saving armor classes...")
    armor_classes = [{"id": k, "name": v} for k, v in sorted(ARMOR_CLASSES.items())]
    with open(output_dir / "armor_classes.json", "w") as f:
        json.dump(armor_classes, f, indent=2)

    # --- Effects ---
    print("Extracting effects...")
    effects = extract_effects(df)
    print(f"  {len(effects)} effects")
    with open(output_dir / "effects.json", "w") as f:
        json.dump(effects, f, indent=2)

    # --- Civ Tech Trees ---
    # Build name lookups from already-extracted data (no need to re-read JSON)
    units_by_id = {u["id"]: u for u in units}
    techs_by_id = {t["id"]: t for t in techs}

    print("Extracting civ tech trees...")
    civ_tech_trees = extract_civ_tech_trees(df, techs_by_id, units_by_id)
    print(f"  {len(civ_tech_trees)} civ tech trees")
    with open(output_dir / "civ_tech_trees.json", "w") as f:
        json.dump(civ_tech_trees, f, indent=2)

    # --- Tech Effects ---
    print("Extracting tech effects...")
    tech_effects = extract_tech_effects(df)
    print(f"  {len(tech_effects)} tech effects")
    with open(output_dir / "tech_effects.json", "w") as f:
        json.dump(tech_effects, f, indent=2)

    print("\nExtraction complete!")


def main():
    from aoe2x.paths import INPUTS_DIR, EXTRACTED_DIR
    dat_path = INPUTS_DIR / "empires2_x2_p1.dat"
    output_dir = EXTRACTED_DIR

    if not dat_path.exists():
        print(f"ERROR: dat file not found at {dat_path}")
        print("Copy empires2_x2_p1.dat from your AoE2:DE install into data/inputs/.")
        sys.exit(1)

    print("=" * 60)
    print("Extracting data from dat file...")
    print("=" * 60)
    extract_all(dat_path, output_dir)
    print(f"\nDone! JSON files written to {output_dir}/")


if __name__ == "__main__":
    main()
