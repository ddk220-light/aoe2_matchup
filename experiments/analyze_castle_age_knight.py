#!/usr/bin/env python3
"""
Castle Age Knight Comparison

Compares Knights across civilizations considering ONLY:
- Castle Age blacksmith techs (Forging, Scale Barding, Chain Barding)
- Stable techs (Bloodlines, Husbandry)
- Civ bonuses that apply in Castle Age

Excludes Imperial Age techs and Paladin/Cavalier upgrades.
"""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Castle Age tech IDs
CASTLE_AGE_TECHS = {
    67: ("Forging", "+1 melee attack"),
    81: ("Scale Barding Armor", "+1/+1 armor"),
    82: ("Chain Barding Armor", "+1/+1 armor"),  # Available late Castle
    435: ("Bloodlines", "+20 HP"),
    39: ("Husbandry", "+10% speed"),
}

# Imperial Age techs (excluded from Castle Age comparison)
IMPERIAL_TECHS = {
    68: "Iron Casting",
    75: "Blast Furnace",
    80: "Plate Barding Armor",
    209: "Cavalier",
    265: "Paladin",
}

# Knight base stats
KNIGHT_BASE = {
    "hp": 100,
    "attack": 10,
    "melee_armor": 2,
    "pierce_armor": 2,
    "speed": 1.35,
    "rof": 1.8,  # Rate of fire (reload time)
}

# Civ bonuses affecting Knights in Castle Age
# Format: civ_name -> list of (bonus_description, stat_changes)
CIV_BONUSES = {
    "Franks": [
        ("Free Farm upgrades (eco)", {}),
        ("+20% cavalry HP", {"hp_percent": 0.20}),
    ],
    "Teutons": [
        ("+1 melee armor (Castle Age)", {"melee_armor": 1}),
        # +2 in Imperial, but we only count Castle Age
    ],
    "Lithuanians": [
        ("+150 food start", {}),
        ("Relics: +1 attack per relic (up to +4)", {"attack_per_relic": 1}),
    ],
    "Berbers": [
        ("Stable units 15% cheaper Castle Age", {"cost_discount": 0.15}),
    ],
    "Huns": [
        ("Stable units train 20% faster", {"train_time_percent": -0.20}),
    ],
    "Magyars": [
        ("Scout line free", {}),
        ("Forging, Iron Casting, Blast Furnace free (attack upgrades)", {"free_techs": [67]}),
    ],
    "Malians": [
        ("Stable units +3 pierce armor (Farimba is Imperial)", {"pierce_armor": 3}),
    ],
    "Persians": [
        ("Knights +2 attack vs archers", {"bonus_vs_archers": 2}),
    ],
    "Burmese": [
        ("+1/+2/+3 cavalry attack per age", {"attack": 2}),  # +2 in Castle Age
    ],
    "Bulgarians": [
        ("Blacksmith upgrades cost -50% food", {"blacksmith_discount": 0.50}),
    ],
    "Burgundians": [
        ("Stable techs -50% cost", {"stable_tech_discount": 0.50}),
        ("Eco upgrades available one age earlier", {}),
    ],
    "Cumans": [
        ("Steppe Husbandry: +50% creation speed (Castle Age UT)", {"train_time_percent": -0.33}),
    ],
    "Poles": [
        ("Regenerate 5 HP/min on stone mining camp", {}),
        ("Szlachta Privileges: Knights cost -60% gold (Castle UT)", {"gold_discount": 0.60}),
    ],
    "Sicilians": [
        ("Land military +50% resistance to bonus damage", {"bonus_damage_resist": 0.50}),
    ],
    "Georgians": [
        ("Regenerate HP when idle (2 HP/sec)", {"regen": 2}),
    ],
    "Gurjaras": [
        ("No Knights - have Shrivamsha Rider instead", {"no_knight": True}),
    ],
    "Indians": [
        ("Have Knights (in older dat file as 'Indians')", {}),
    ],
    "Incas": [
        ("No Knights", {"no_knight": True}),
    ],
    "Mayans": [
        ("No Knights", {"no_knight": True}),
    ],
    "Aztecs": [
        ("No Knights", {"no_knight": True}),
    ],
    "Chinese": [
        ("Techs -10%/-15%/-20% per age", {"tech_discount": 0.15}),
    ],
    "Spanish": [
        ("Blacksmith upgrades don't cost gold", {"blacksmith_no_gold": True}),
    ],
    "Slavs": [
        ("Supplies/Squires free, military buildings +15% HP", {}),
    ],
    "Vietnamese": [
        ("Archery Range units +20% HP (not cavalry)", {}),
    ],
    "Tatars": [
        ("+2 LOS for cavalry", {"los": 2}),
        ("Free Thumb Ring/Parthian Tactics (archers)", {}),
    ],
    "Mongols": [
        ("Cavalry +30% HP (only Scout line, not Knights)", {}),
    ],
    "Romans": [
        ("Cavalry +5% speed per age (Castle: +10%)", {"speed_percent": 0.10}),
    ],
}


def load_data():
    """Load extracted game data."""
    data = {}
    data["units"] = {u["id"]: u for u in json.load(open(OUTPUT_DIR / "units.json"))}
    data["techs"] = {t["id"]: t for t in json.load(open(OUTPUT_DIR / "technologies.json"))}
    data["civs"] = json.load(open(OUTPUT_DIR / "civilizations.json"))
    data["civ_tech_trees"] = json.load(open(OUTPUT_DIR / "civ_tech_trees.json"))
    data["effects"] = {e["id"]: e for e in json.load(open(OUTPUT_DIR / "effects.json"))}
    return data


def get_disabled_techs(data, civ_name):
    """Get list of disabled tech IDs for a civilization."""
    for civ in data["civ_tech_trees"]:
        if civ["name"] == civ_name:
            disabled = civ.get("disabled_techs", [])
            # disabled_techs is a list of dicts with 'id' and 'name'
            return set(t["id"] for t in disabled if isinstance(t, dict))
    return set()


def calculate_castle_age_stats(civ_name, data, with_all_techs=True):
    """
    Calculate Knight stats for a civ in Castle Age.

    Args:
        civ_name: Civilization name
        data: Game data
        with_all_techs: If True, assume all available techs are researched

    Returns:
        Dict with final stats and breakdown
    """
    # Start with base stats
    stats = KNIGHT_BASE.copy()
    stats["cost_food"] = 60
    stats["cost_gold"] = 75
    stats["train_time"] = 30

    breakdown = {
        "base": KNIGHT_BASE.copy(),
        "techs_applied": [],
        "bonuses_applied": [],
    }

    # Check if civ has Knights
    bonuses = CIV_BONUSES.get(civ_name, [])
    for desc, effects in bonuses:
        if effects.get("no_knight"):
            return None

    disabled_techs = get_disabled_techs(data, civ_name)

    if with_all_techs:
        # Apply Castle Age techs
        for tech_id, (tech_name, description) in CASTLE_AGE_TECHS.items():
            if tech_id in disabled_techs:
                breakdown["techs_applied"].append(f"{tech_name}: DISABLED")
                continue

            if tech_id == 67:  # Forging
                stats["attack"] += 1
                breakdown["techs_applied"].append(f"{tech_name}: +1 attack")
            elif tech_id == 81:  # Scale Barding
                stats["melee_armor"] += 1
                stats["pierce_armor"] += 1
                breakdown["techs_applied"].append(f"{tech_name}: +1/+1 armor")
            elif tech_id == 82:  # Chain Barding
                stats["melee_armor"] += 1
                stats["pierce_armor"] += 1
                breakdown["techs_applied"].append(f"{tech_name}: +1/+1 armor")
            elif tech_id == 435:  # Bloodlines
                stats["hp"] += 20
                breakdown["techs_applied"].append(f"{tech_name}: +20 HP")
            elif tech_id == 39:  # Husbandry
                stats["speed"] *= 1.10
                breakdown["techs_applied"].append(f"{tech_name}: +10% speed")

    # Apply civ bonuses
    for desc, effects in bonuses:
        if not effects:
            continue

        applied = False
        if "hp_percent" in effects:
            bonus_hp = int(stats["hp"] * effects["hp_percent"])
            stats["hp"] += bonus_hp
            applied = True
        if "attack" in effects:
            stats["attack"] += effects["attack"]
            applied = True
        if "melee_armor" in effects:
            stats["melee_armor"] += effects["melee_armor"]
            applied = True
        if "pierce_armor" in effects:
            stats["pierce_armor"] += effects["pierce_armor"]
            applied = True
        if "speed_percent" in effects:
            stats["speed"] *= (1 + effects["speed_percent"])
            applied = True
        if "cost_discount" in effects:
            stats["cost_food"] = int(stats["cost_food"] * (1 - effects["cost_discount"]))
            stats["cost_gold"] = int(stats["cost_gold"] * (1 - effects["cost_discount"]))
            applied = True
        if "gold_discount" in effects:
            stats["cost_gold"] = int(stats["cost_gold"] * (1 - effects["gold_discount"]))
            applied = True
        if "train_time_percent" in effects:
            stats["train_time"] = int(stats["train_time"] * (1 + effects["train_time_percent"]))
            applied = True
        if "free_techs" in effects:
            applied = True
        if "bonus_vs_archers" in effects:
            stats["bonus_vs_archers"] = effects["bonus_vs_archers"]
            applied = True
        if "bonus_damage_resist" in effects:
            stats["bonus_damage_resist"] = effects["bonus_damage_resist"]
            applied = True
        if "attack_per_relic" in effects:
            stats["attack_per_relic"] = effects["attack_per_relic"]
            applied = True
        if "regen" in effects:
            stats["regen"] = effects["regen"]
            applied = True

        if applied:
            breakdown["bonuses_applied"].append(desc)

    stats["speed"] = round(stats["speed"], 2)
    return {"stats": stats, "breakdown": breakdown}


def print_comparison_table(results):
    """Print a formatted comparison table."""
    # Sort by effective HP * attack as a rough power ranking
    def power_score(r):
        s = r["stats"]
        hp_effective = s["hp"]
        atk = s["attack"]
        if s.get("attack_per_relic"):
            atk += 2  # Assume 2 relics average
        return hp_effective * atk

    sorted_results = sorted(results.items(), key=lambda x: power_score(x[1]), reverse=True)

    print("\n" + "="*90)
    print("CASTLE AGE KNIGHT COMPARISON (with all available techs)")
    print("="*90)
    print(f"{'Civ':<15} {'HP':>5} {'Atk':>5} {'M/P Armor':>10} {'Speed':>6} {'Cost':>12} {'Special':<25}")
    print("-"*90)

    for civ_name, result in sorted_results:
        s = result["stats"]
        cost = f"{s['cost_food']}F/{s['cost_gold']}G"

        specials = []
        if s.get("bonus_vs_archers"):
            specials.append(f"+{s['bonus_vs_archers']} vs arch")
        if s.get("attack_per_relic"):
            specials.append(f"+{s['attack_per_relic']}/relic")
        if s.get("bonus_damage_resist"):
            specials.append(f"{int(s['bonus_damage_resist']*100)}% bonus res")
        if s.get("regen"):
            specials.append(f"regen {s['regen']}/s")
        if s["train_time"] < 30:
            specials.append(f"train {s['train_time']}s")

        special_str = ", ".join(specials) if specials else "-"

        print(f"{civ_name:<15} {s['hp']:>5} {s['attack']:>5} {s['melee_armor']}/{s['pierce_armor']:>7} {s['speed']:>6} {cost:>12} {special_str:<25}")


def print_tier_list(results):
    """Print a tier list based on Knight power in Castle Age."""
    print("\n" + "="*70)
    print("CASTLE AGE KNIGHT TIER LIST")
    print("="*70)

    tiers = {
        "S": [],  # Best Knights
        "A": [],  # Strong Knights
        "B": [],  # Above average
        "C": [],  # Average
        "D": [],  # Below average
    }

    for civ_name, result in results.items():
        s = result["stats"]
        bonuses = result["breakdown"]["bonuses_applied"]

        # Scoring
        score = 0

        # HP bonus
        if s["hp"] >= 144:  # Franks level
            score += 3
        elif s["hp"] >= 120:
            score += 2
        elif s["hp"] >= 100:
            score += 1

        # Attack bonus
        if s["attack"] >= 13:
            score += 2
        elif s["attack"] >= 12:
            score += 1

        # Armor bonus
        total_armor = s["melee_armor"] + s["pierce_armor"]
        if total_armor >= 11:  # Malians level
            score += 2
        elif total_armor >= 9:
            score += 1

        # Special bonuses
        if s.get("attack_per_relic"):
            score += 2  # Lithuanians relic bonus is strong
        if s.get("bonus_damage_resist"):
            score += 1
        if s.get("regen"):
            score += 1
        if s.get("bonus_vs_archers"):
            score += 1

        # Cost efficiency
        if s["cost_gold"] <= 30:  # Poles
            score += 2
        elif s["cost_food"] + s["cost_gold"] < 120:
            score += 1

        # Assign tier
        if score >= 5:
            tiers["S"].append((civ_name, bonuses))
        elif score >= 4:
            tiers["A"].append((civ_name, bonuses))
        elif score >= 2:
            tiers["B"].append((civ_name, bonuses))
        elif score >= 1:
            tiers["C"].append((civ_name, bonuses))
        else:
            tiers["D"].append((civ_name, bonuses))

    for tier, civs in tiers.items():
        if civs:
            print(f"\n{tier}-TIER:")
            for civ_name, bonuses in sorted(civs):
                bonus_str = f" ({', '.join(bonuses)})" if bonuses else ""
                print(f"  - {civ_name}{bonus_str}")


def print_detailed_breakdown(civ_name, result):
    """Print detailed breakdown for a specific civ."""
    print(f"\n{civ_name} Knight Breakdown:")
    print("-" * 40)

    b = result["breakdown"]
    s = result["stats"]

    print("Base Stats: HP=100, Atk=10, Armor=2/2, Speed=1.35")
    print("\nTechs Applied:")
    for tech in b["techs_applied"]:
        print(f"  + {tech}")

    if b["bonuses_applied"]:
        print("\nCiv Bonuses:")
        for bonus in b["bonuses_applied"]:
            print(f"  + {bonus}")

    print(f"\nFinal: HP={s['hp']}, Atk={s['attack']}, Armor={s['melee_armor']}/{s['pierce_armor']}, Speed={s['speed']}")


def main():
    print("Loading data...")
    data = load_data()

    # Get all civs
    civ_names = [c["name"] for c in data["civs"]]

    # Calculate stats for each civ
    results = {}
    no_knights = []

    for civ_name in civ_names:
        result = calculate_castle_age_stats(civ_name, data)
        if result is None:
            no_knights.append(civ_name)
        else:
            results[civ_name] = result

    print(f"Analyzed {len(results)} civs with Knights, {len(no_knights)} without")

    # Print results
    print_comparison_table(results)
    print_tier_list(results)

    # Print civs without knights
    if no_knights:
        print("\n" + "="*70)
        print("CIVILIZATIONS WITHOUT KNIGHTS")
        print("="*70)
        for civ in sorted(no_knights):
            print(f"  - {civ}")

    # Detailed breakdown for top civs
    print("\n" + "="*70)
    print("DETAILED BREAKDOWN - TOP KNIGHT CIVS")
    print("="*70)

    top_civs = ["Franks", "Lithuanians", "Teutons", "Malians", "Poles", "Burgundians"]
    for civ in top_civs:
        if civ in results:
            print_detailed_breakdown(civ, results[civ])


if __name__ == "__main__":
    main()
