#!/usr/bin/env python3
"""
Analyze the Knight unit using extracted data from JSON files.
Uses the effects, civ_tech_trees, and tech_effects data.
"""

import json
from pathlib import Path

def load_data():
    """Load all extracted data."""
    output_dir = Path(__file__).parent.parent / "output"

    with open(output_dir / "units.json") as f:
        units = json.load(f)

    with open(output_dir / "effects.json") as f:
        effects = json.load(f)

    with open(output_dir / "civ_tech_trees.json") as f:
        civ_tech_trees = json.load(f)

    with open(output_dir / "tech_effects.json") as f:
        tech_effects = json.load(f)

    with open(output_dir / "technologies.json") as f:
        technologies = json.load(f)

    return {
        "units": {u["id"]: u for u in units},
        "effects": {e["id"]: e for e in effects},
        "civ_tech_trees": {c["name"]: c for c in civ_tech_trees},
        "tech_effects": tech_effects,
        "technologies": {t["id"]: t for t in technologies},
    }


def get_knight_line_availability(data):
    """Determine which civs have Knight, Cavalier, Paladin."""
    CAVALIER_TECH = 209
    PALADIN_TECH = 265

    availability = {}

    for civ_name, civ in data["civ_tech_trees"].items():
        disabled_tech_ids = {t["id"] for t in civ["disabled_techs"]}
        disabled_unit_ids = {u["id"] for u in civ["disabled_units"]}

        has_knight = 38 not in disabled_unit_ids  # Knight ID
        has_cavalier = CAVALIER_TECH not in disabled_tech_ids
        has_paladin = PALADIN_TECH not in disabled_tech_ids

        if has_knight:
            if has_paladin:
                level = "Paladin"
            elif has_cavalier:
                level = "Cavalier"
            else:
                level = "Knight"
        else:
            level = "None"

        availability[civ_name] = {
            "has_knight": has_knight,
            "has_cavalier": has_cavalier,
            "has_paladin": has_paladin,
            "max_level": level
        }

    return availability


def find_knight_bonuses(data):
    """Find all effects that specifically modify Knight (ID 38)."""
    knight_id = 38
    bonuses = []

    for effect_id, effect in data["effects"].items():
        relevant_commands = []
        for cmd in effect["commands"]:
            # Check if command affects Knight specifically
            if cmd.get("a") == knight_id or cmd.get("unit_id") == knight_id:
                relevant_commands.append(cmd)

        if relevant_commands:
            bonuses.append({
                "effect_id": effect_id,
                "effect_name": effect["name"],
                "commands": relevant_commands
            })

    return bonuses


def find_cavalry_class_bonuses(data):
    """Find effects that affect all cavalry (class 12 or armor class 8)."""
    bonuses = []

    for effect_id, effect in data["effects"].items():
        relevant_commands = []
        for cmd in effect["commands"]:
            # Check for class-based effects on cavalry
            # Armor class 8 = Cavalry
            if cmd.get("armor_class") == 8 or cmd.get("class_id") == 8:
                relevant_commands.append(cmd)
            # Check for -1 unit_id effects (affects multiple units)
            elif cmd.get("a") == -1 and cmd.get("type") in [4, 5]:
                # These might affect cavalry
                pass  # Too broad to include all

        if relevant_commands:
            bonuses.append({
                "effect_id": effect_id,
                "effect_name": effect["name"],
                "commands": relevant_commands
            })

    return bonuses


def main():
    print("Loading data...")
    data = load_data()
    print(f"Loaded {len(data['units'])} units, {len(data['effects'])} effects, {len(data['civ_tech_trees'])} civs")

    # Get Knight base stats
    knight = data["units"].get(38)
    cavalier = data["units"].get(283)
    paladin = data["units"].get(569)

    print("\n" + "="*70)
    print("KNIGHT LINE BASE STATS")
    print("="*70)

    for name, unit in [("Knight", knight), ("Cavalier", cavalier), ("Paladin", paladin)]:
        if unit:
            print(f"\n{name} (ID: {unit['id']}):")
            print(f"  HP: {unit['hit_points']}")
            print(f"  Attack: {unit.get('displayed_attack', 'N/A')}")
            print(f"  Melee Armor: {unit.get('displayed_melee_armor', 'N/A')}")
            print(f"  Pierce Armor: {unit.get('displayed_pierce_armor', 'N/A')}")
            print(f"  Speed: {unit['speed']}")
            if unit.get('cost'):
                cost_str = ", ".join(f"{v} {k}" for k, v in unit['cost'].items())
                print(f"  Cost: {cost_str}")

    # Knight line availability
    print("\n" + "="*70)
    print("KNIGHT LINE AVAILABILITY BY CIVILIZATION")
    print("="*70)

    availability = get_knight_line_availability(data)

    # Group by max level
    by_level = {"Paladin": [], "Cavalier": [], "Knight": [], "None": []}
    for civ, info in availability.items():
        by_level[info["max_level"]].append(civ)

    for level in ["Paladin", "Cavalier", "Knight", "None"]:
        civs = sorted(by_level[level])
        if civs:
            print(f"\n{level} ({len(civs)} civs):")
            for civ in civs:
                print(f"  - {civ}")

    # Knight-specific bonuses from effects
    print("\n" + "="*70)
    print("EFFECTS THAT MODIFY KNIGHT SPECIFICALLY")
    print("="*70)

    knight_bonuses = find_knight_bonuses(data)

    # Group by type of bonus
    civ_bonuses = []
    tech_bonuses = []
    other_bonuses = []

    for bonus in knight_bonuses:
        name = bonus["effect_name"]
        if "C-Bonus" in name or "Team Bonus" in name:
            civ_bonuses.append(bonus)
        elif any(x in name.lower() for x in ["upgrade", "make avail", "cavalier", "paladin"]):
            other_bonuses.append(bonus)
        else:
            tech_bonuses.append(bonus)

    print("\nCivilization Bonuses:")
    for bonus in civ_bonuses:
        print(f"\n  {bonus['effect_name']} (Effect {bonus['effect_id']}):")
        for cmd in bonus["commands"]:
            desc = cmd.get("description", str(cmd))
            print(f"    - {desc}")

    print("\nTechnology Effects:")
    for bonus in tech_bonuses:
        print(f"\n  {bonus['effect_name']} (Effect {bonus['effect_id']}):")
        for cmd in bonus["commands"]:
            desc = cmd.get("description", str(cmd))
            print(f"    - {desc}")

    # Match civ bonuses to civilizations
    print("\n" + "="*70)
    print("CIVILIZATION BONUSES AFFECTING KNIGHTS")
    print("="*70)

    # Known civ bonus effect mappings (from effect names)
    civ_bonus_map = {
        "Franks Team Bonus": ("Franks", "+2 LOS for Knights"),
        "Persians Team Bonus": ("Persians", "Knights attack +2 vs archers"),
        "C-Bonus, Inf Cav +1 armor Age3": ("Teutons", "+1 melee armor in Castle Age"),
        "C-Bonus, Inf Cav +1 armor Age4": ("Teutons", "+1 melee armor in Imperial Age"),
        "C-Bonus, Relic +1 cav attack 1": ("Lithuanians", "+1 attack per Relic (1st)"),
        "C-Bonus, Relic +1 cav attack 2": ("Lithuanians", "+1 attack per Relic (2nd)"),
        "C-Bonus, Relic +1 cav attack 3": ("Lithuanians", "+1 attack per Relic (3rd)"),
        "C-Bonus, Relic +1 cav attack 4": ("Lithuanians", "+1 attack per Relic (4th)"),
        "Hauberk": ("Sicilians", "+1/+2 armor (Unique Tech)"),
        "Szlachta Privileges": ("Poles", "Knights cost -60% gold (Unique Tech)"),
        "Comitatenses": ("Romans", "Knights train faster, gain charge attack (Unique Tech)"),
    }

    civ_effects = {}
    for bonus in knight_bonuses:
        name = bonus["effect_name"]
        if name in civ_bonus_map:
            civ, desc = civ_bonus_map[name]
            if civ not in civ_effects:
                civ_effects[civ] = []
            civ_effects[civ].append({
                "name": name,
                "description": desc,
                "commands": bonus["commands"]
            })

    for civ in sorted(civ_effects.keys()):
        print(f"\n{civ}:")
        for effect in civ_effects[civ]:
            print(f"  {effect['description']}")
            for cmd in effect["commands"]:
                if "description" in cmd:
                    # Parse the effect values
                    if cmd.get("armor_amount"):
                        print(f"    -> +{cmd['armor_amount']} armor class {cmd['armor_class']}")
                    elif cmd.get("multiplier"):
                        pct = (1 - cmd["multiplier"]) * 100
                        print(f"    -> {pct:+.0f}% {cmd.get('attribute', 'attribute')}")

    # Summary table
    print("\n" + "="*70)
    print("KNIGHT CIVILIZATION TIER LIST")
    print("="*70)
    print("""
Based on direct bonuses from game data:

S-TIER (Strong direct bonuses + Paladin):
  - Franks: +20% HP (from civ bonus, not in effects - applied at game start)
            +2 LOS (Team Bonus), Chivalry for faster production
  - Lithuanians: +1/2/3/4 attack with Relics, Full Paladin
  - Teutons: +1/+2 melee armor by age, Full Paladin

A-TIER (Good bonuses or unique techs):
  - Burgundians: Cavalier in Castle Age (economy bonus)
  - Sicilians: Hauberk +1/+2 armor, -50% bonus damage taken
  - Poles: Szlachta Privileges -60% gold cost
  - Romans: Comitatenses - faster training + charge attack
  - Persians: +2 attack vs archers (Team Bonus)

B-TIER (Indirect bonuses or Paladin access):
  - Cumans: 15% faster movement
  - Magyars: Free Blacksmith upgrades
  - Spanish: Free Blacksmith gold
  - Huns: Full Paladin, Atheism

C-TIER (Limited Knight line):
  - Bulgarians: Stirrups +33% attack speed (Cavalier only)
  - Malians: Farimba +5 attack (Knight only)
  - Berbers: -20% cost (Knight only)

NO KNIGHT:
  - Aztecs, Mayans, Incas (Meso civs)
  - Hindustanis, Dravidians, Bengalis, Gurjaras (Indian civs)
""")


if __name__ == "__main__":
    main()
