#!/usr/bin/env python3
"""
Analyze the Knight unit across all civilizations.
- Which civs have knights?
- Which civs don't have knights?
- What civ bonuses apply to knights?
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genieutils.datfile import DatFile

# Civilization names
CIV_NAMES = [
    "Gaia", "Britons", "Franks", "Goths", "Teutons", "Japanese", "Chinese",
    "Byzantines", "Persians", "Saracens", "Turks", "Vikings", "Mongols", "Celts",
    "Spanish", "Aztecs", "Mayans", "Huns", "Koreans", "Italians", "Indians",
    "Incas", "Magyars", "Slavs", "Portuguese", "Ethiopians", "Malians", "Berbers",
    "Khmer", "Malay", "Burmese", "Vietnamese", "Bulgarians", "Tatars", "Cumans",
    "Lithuanians", "Burgundians", "Sicilians", "Poles", "Bohemians", "Dravidians",
    "Bengalis", "Gurjaras", "Romans", "Armenians", "Georgians"
]

# Knight line unit IDs
KNIGHT_ID = 38
CAVALIER_ID = 283
PALADIN_ID = 529

# Technology IDs for knight line upgrades
CAVALIER_TECH = 209  # Cavalier upgrade
PALADIN_TECH = 265   # Paladin upgrade

# Known civs that DON'T have access to Knight line (from game knowledge)
# These civs replace knights with other units or simply don't have them
CIVS_WITHOUT_KNIGHT = {
    "Aztecs",      # Meso civ - no cavalry
    "Mayans",      # Meso civ - no cavalry
    "Incas",       # Meso civ - no cavalry
    "Indians",     # Hindustanis - no knights, have Ghulam/Camels
    "Dravidians",  # No knights - have Urumi, elephant focus
    "Gurjaras",    # No knights - have Shrivamsha Rider, camel focus
    "Bengalis",    # No knights - have Ratha, elephant focus
}

# Known civs that don't get Cavalier
CIVS_WITHOUT_CAVALIER = CIVS_WITHOUT_KNIGHT | {
    "Berbers",     # Stop at Knight
    "Mongols",     # Stop at Knight (have Mangudai instead)
    "Turks",       # Stop at Knight
    "Vietnamese",  # Stop at Knight
    "Byzantines",  # Stop at Knight (have Cataphract)
    "Saracens",    # Stop at Knight (have Mameluke)
    "Malians",     # Stop at Knight
    "Sicilians",   # Stop at Knight
    "Britons",     # Stop at Knight
    "Celts",       # Stop at Knight
    "Ethiopians",  # Stop at Knight
    "Koreans",     # Stop at Knight
    "Japanese",    # Stop at Knight
    "Khmer",       # Stop at Cavalier (no Paladin)
    "Portuguese",  # Stop at Cavalier
    "Malay",       # Stop at Cavalier
    "Bohemians",   # Stop at Cavalier
    "Chinese",     # Stop at Cavalier
    "Goths",       # Stop at Cavalier
    "Italians",    # Stop at Cavalier
    "Poles",       # Stop at Cavalier (have Winged Hussar)
    "Slavs",       # Stop at Cavalier (have Boyar)
    "Tatars",      # Stop at Cavalier
    "Vietnamese",  # Stop at Cavalier
}

# Known civs that get Paladin
CIVS_WITH_PALADIN = {
    "Franks",
    "Teutons",
    "Persians",
    "Spanish",
    "Huns",
    "Magyars",
    "Lithuanians",
    "Burgundians",
    "Cumans",
    "Bulgarians",
    "Romans",
    "Armenians",
    "Georgians",
    "Burmese",
}


def main():
    dat_path = Path(__file__).parent.parent / "empires2_x2_p1.dat"

    print("Loading game data...")
    df = DatFile.parse(dat_path)
    print(f"Loaded {len(df.civs)} civilizations\n")

    # Get base Knight stats from Gaia
    print("="*70)
    print("BASE KNIGHT STATS")
    print("="*70)

    base_knight = df.civs[0].units[KNIGHT_ID]
    print(f"\n  Knight (ID: {KNIGHT_ID})")
    print(f"  HP: {int(base_knight.hit_points)}")
    print(f"  Speed: {base_knight.speed:.2f}")
    print(f"  Line of Sight: {base_knight.line_of_sight}")

    if hasattr(base_knight, 'type_50') and base_knight.type_50:
        t = base_knight.type_50
        print(f"  Attack: {t.displayed_attack}")
        print(f"  Melee Armor: {t.displayed_melee_armour}")
        print(f"  Reload Time: {t.reload_time:.2f}s")

        # Get armor classes
        print("\n  Armor Classes (for bonus damage):")
        armor_class_names = {
            3: "Base Pierce", 4: "Base Melee", 8: "Cavalry",
            19: "Unique Unit", 31: "Leitis"
        }
        for arm in t.armours:
            name = armor_class_names.get(arm.class_, f"Class {arm.class_}")
            print(f"    {name}: {arm.amount}")

    if hasattr(base_knight, 'creatable') and base_knight.creatable:
        c = base_knight.creatable
        print(f"\n  Pierce Armor: {c.displayed_pierce_armour}")
        print(f"  Train Time: {c.train_locations[0].train_time if c.train_locations else 'N/A'}s")

        cost_parts = []
        for rc in c.resource_costs:
            if rc.amount > 0 and rc.type in [0, 1, 2, 3]:
                res_names = {0: "Food", 1: "Wood", 2: "Stone", 3: "Gold"}
                cost_parts.append(f"{int(rc.amount)} {res_names.get(rc.type)}")
        print(f"  Cost: {', '.join(cost_parts)}")

    # Knight line availability
    print("\n" + "="*70)
    print("KNIGHT LINE AVAILABILITY")
    print("="*70)

    # Based on game knowledge
    all_civs = set(CIV_NAMES[1:])  # Exclude Gaia
    civs_with_knight = all_civs - CIVS_WITHOUT_KNIGHT

    print(f"\nCivs WITH Knight ({len(civs_with_knight)}):")
    for civ in sorted(civs_with_knight):
        if civ in CIVS_WITH_PALADIN:
            print(f"  {civ}: Knight -> Cavalier -> Paladin")
        elif civ not in CIVS_WITHOUT_CAVALIER:
            print(f"  {civ}: Knight -> Cavalier")
        else:
            print(f"  {civ}: Knight only")

    print(f"\nCivs WITHOUT Knight ({len(CIVS_WITHOUT_KNIGHT)}):")
    for civ in sorted(CIVS_WITHOUT_KNIGHT):
        if civ in ["Aztecs", "Mayans", "Incas"]:
            print(f"  {civ}: Meso civ (no cavalry)")
        elif civ == "Dravidians":
            print(f"  {civ}: No knights (have Urumi Swordsman, elephants)")
        elif civ == "Gurjaras":
            print(f"  {civ}: No knights (have Shrivamsha Rider, camels)")
        elif civ == "Bengalis":
            print(f"  {civ}: No knights (have Ratha, elephants)")
        elif civ == "Indians":
            print(f"  {civ}: Hindustanis - no knights (have Ghulam, camels)")
        else:
            print(f"  {civ}")

    # Civ bonuses for knights
    print("\n" + "="*70)
    print("CIVILIZATION BONUSES FOR KNIGHTS")
    print("="*70)

    knight_bonuses = {
        "Franks": [
            "+20% HP (120 HP base instead of 100)",
            "+2 Line of Sight per age (starting Feudal)",
            "Chivalry (UT): Stables work 40% faster",
            "Bearded Axe (UT): Throwing Axemen +1 range (not knight related)",
        ],
        "Teutons": [
            "+1 melee armor in Castle Age, +2 in Imperial Age",
            "Ironclad (UT): Siege +4 melee armor (not knight)",
            "Crenellations (UT): Castles +3 range (not knight)",
        ],
        "Persians": [
            "Mahouts (UT): Elephants faster (not knight)",
            "Kamandaran removed - was archer bonus",
            "No direct knight bonus currently",
        ],
        "Lithuanians": [
            "+1 attack per Relic collected (up to +4)",
            "Hill Forts (UT): TC +3 range (not knight)",
            "Tower Shields (UT): Spearman/Skirm +2 pierce armor (not knight)",
        ],
        "Burgundians": [
            "Cavalier upgrade available in Castle Age",
            "Stable technologies cost -50%",
            "Economic upgrades available one age earlier",
            "Flemish Revolution (UT): Villagers become Flemish Militia",
        ],
        "Berbers": [
            "Knights cost -15% in Castle Age, -20% in Imperial Age",
            "Villagers move 10% faster",
            "Maghrebi Camels (UT): Camel units regenerate",
        ],
        "Magyars": [
            "Scout line costs -15% (includes Scout -> Light Cav -> Hussar)",
            "Forging, Iron Casting, Blast Furnace free",
            "Corvinian Army (UT): Magyar Huszar costs no gold",
        ],
        "Sicilians": [
            "Knights take -50% bonus damage (33% in Feudal/Castle)",
            "First Crusade (UT): TC spawn Serjeants",
            "Hauberk (UT): Knights get +1/+2 armor",
        ],
        "Bulgarians": [
            "Stirrups (UT): Cavalry attack 33% faster",
            "Blacksmith/Siege upgrades cost -50%",
            "Krepost: Unique building that trains Konniks",
        ],
        "Cumans": [
            "Cavalry move 5% faster in Feudal, 10% Castle, 15% Imperial",
            "Siege Workshop/Ram available in Feudal Age",
            "Steppe Husbandry (UT): Scout, Steppe Lancer, CA train 100% faster",
        ],
        "Huns": [
            "Cavalry Archers cost -10% Castle Age, -20% Imperial Age",
            "Atheism (UT): Spies/Treason cost -50%, relic/wonder victory +100 years",
            "Marauders (UT): Tarkans trainable at Stables",
        ],
        "Spanish": [
            "Blacksmith upgrades don't cost gold",
            "Cannon Galleons fire faster (+15%)",
            "Inquisition (UT): Monks convert faster",
            "Supremacy (UT): Villagers combat buffed",
        ],
        "Malians": [
            "Farimba (UT): Cavalry get +5 attack",
            "Buildings cost -15% wood",
            "Infantry get +1 pierce armor per age",
            "Tigui (UT): TC fires arrows without garrison",
        ],
        "Burmese": [
            "Manipur Cavalry (UT): Cavalry +4 attack vs archers",
            "Howdah (UT): Battle Elephants +1/+2 armor",
            "Free lumber camp upgrades",
            "Monastery techs cost -50%",
        ],
        "Tatars": [
            "Silk Armor (UT): Scout line, Steppe Lancers, CA get +1 pierce armor",
            "Timurid Siegecraft (UT): Trebuchet +2 range",
            "Herdables contain +50% food",
            "Units deal +25% damage when fighting from higher ground",
        ],
        "Slavs": [
            "Druzhina (UT): Infantry deal splash damage (not cavalry)",
            "Farmers work 10% faster",
            "Military buildings cost -15% wood",
            "Detinets (UT): Replace stone cost with wood for towers/TC",
        ],
        "Chinese": [
            "Technologies cost -10%/-15%/-20% per age",
            "Start with +3 villagers but -150 food",
            "Demolition ships +50% HP",
            "Rocketry (UT): Chu Ko Nu +2 attack, Scorpions +4 attack",
        ],
        "Mongols": [
            "Cavalry Archers fire 25% faster",
            "Scout line +30% HP",
            "Hunters work 40% faster",
            "Nomads (UT): Houses don't lose pop when destroyed",
        ],
    }

    print()
    for civ in sorted(civs_with_knight):
        if civ in knight_bonuses:
            print(f"{civ}:")
            for bonus in knight_bonuses[civ]:
                print(f"  - {bonus}")
            print()

    # Summary: Best knight civs
    print("="*70)
    print("TOP KNIGHT CIVILIZATIONS (ranked)")
    print("="*70)
    print("""
1. Franks
   - +20% HP is massive (120 base HP)
   - +2 LOS per age helps micro
   - Full Paladin upgrade
   - Chivalry for faster production

2. Lithuanians
   - Up to +4 attack with Relics
   - Full Paladin upgrade
   - Makes Paladin 14+4 = 18 attack

3. Teutons
   - +1/+2 melee armor stacks with Blacksmith
   - Paladin with 5 melee armor is tanky
   - Slow but tough

4. Burgundians
   - Cavalier in Castle Age is powerful timing
   - Cheap stable techs
   - Full Paladin upgrade

5. Bulgarians
   - Stirrups: 33% faster attack
   - Makes knights DPS machines
   - No Paladin but very strong Cavalier

6. Sicilians
   - 50% less bonus damage
   - Halberdiers deal 16 instead of 32 bonus
   - Hauberk for extra armor
   - Only Cavalier but very tanky

7. Cumans
   - 15% faster movement in Imperial
   - Very fast knights for raiding
   - Full Paladin upgrade

8. Malians
   - Farimba: +5 attack
   - Knight with 15 attack
   - Only Knight, no Cavalier/Paladin

9. Berbers
   - 20% cheaper in Imperial
   - Good economy bonus
   - Full Paladin upgrade

10. Huns
    - No direct knight bonus
    - But Paladin + Tarkan options
    - Atheism helps in late game
""")


if __name__ == "__main__":
    main()
