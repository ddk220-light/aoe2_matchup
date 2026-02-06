# AoE2 Unit Stats Reference Data - Verification Request

## Instructions

You are given extracted unit stats data for Age of Empires II: Definitive Edition, covering 13 original civilizations. Your task is to verify this data against reliable online sources and produce a mismatch report.

### Scope
- 13 civilizations: Britons, Byzantines, Celts, Chinese, Franks, Goths, Japanese, Mongols, Persians, Saracens, Teutons, Turks, Vikings
- Castle Age and Imperial Age military units (fully upgraded for that age)
- Standard units and unique units

### What to verify

For each civilization's units, compare the following against the AoE2 wiki (https://ageofempires.fandom.com/wiki/Age_of_Empires_II) or other reliable AoE2:DE sources:

1. **Base stats** (before any techs): HP, attack, melee armor, pierce armor, range, speed, reload time, attack delay, accuracy, LOS, cost
2. **Upgrades available**: Which blacksmith, university, stable, archery range, barracks, monastery, and unique techs are available to each civ
3. **Final fully-upgraded stats**: The stats after all available techs for that civ and age are applied
4. **Attack classes**: Bonus damage values against unit classes (e.g., Pikeman bonus vs Cavalry)
5. **Armor classes**: Which armor classes the unit has and their values
6. **Special properties**: Trample damage, splash radius, ignore armor, etc.

### Important notes
- "attack" in base_stats refers to the unit's main attack class value (Base Pierce for ranged, Base Melee for melee). The full breakdown is in base_attack_classes/final_attack_classes.
- "final_stats.attack" stores the same main class value as base - check final_attack_classes for the actual upgraded value
- Reload time is in seconds (e.g., 2.0 = fires every 2 seconds)
- Speed is tiles per second
- Accuracy is a percentage (50 = 50%)
- Cost values of 0 mean that resource is not required

### Output format

Produce a document titled "AoE2 Reference Data Mismatch Report" with:

1. **Summary**: Total units checked, total mismatches found
2. **Mismatches by civilization**: For each civ with mismatches, list:
   - Unit name and age
   - Stat name
   - Our value vs. expected value (with source)
   - Whether the mismatch is in base stats, upgrades, or final stats
3. **Missing units**: Any units that should be available to a civ but are missing from our data
4. **Extra units**: Any units in our data that shouldn't be available to that civ
5. **Notes**: Any observations about systematic errors or patterns

Focus on **concrete numeric mismatches**. Minor floating-point differences (e.g., 0.96 vs 0.96) are not mismatches. Flag anything where the difference would affect gameplay calculations.

## Data

```json
{
  "Britons": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 11.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 90.0,
        "los": 13.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, +1 Archer range",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        },
        {
          "tech_name": "C-Bonus, archer range +1",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        },
        {
          "tech_name": "British Yeoman",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Capped Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_armor_classes": {
        "Base Melee": -2,
        "Base Pierce": 190,
        "Rams": 1,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 16.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Longbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 1.0,
        "range": 6.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 80.0,
        "los": 8.0,
        "cost": {
          "food": 0.0,
          "wood": 35.0,
          "gold": 40.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 7.0,
        "melee_armor": 3.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 80.0,
        "los": 14.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 5,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, +1 Archer range",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        },
        {
          "tech_name": "C-Bonus, archer range +1",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        },
        {
          "tech_name": "British Yeoman",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Britons City Rights",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "+0.5 attr_22; set Accuracy=100%"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 9.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, +1 Archer range",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        },
        {
          "tech_name": "British Yeoman",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, +1 Archer range",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23; -1 Range; -1 LOS; -1 attr_23"
        },
        {
          "tech_name": "British Yeoman",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Longbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 70.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 35.0,
          "gold": 40.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 9.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 70.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, +1 Archer range",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        },
        {
          "tech_name": "British Yeoman",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+1 Range; +1 LOS; +1 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Byzantines": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 14.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 16.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Cataphract",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 150.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.7,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 70.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 14.0,
        "melee_armor": 5.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.7,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Infantry": 12,
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Infantry": 18,
        "Base Melee": 14,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 16,
        "Base Pierce": 5,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Byzantine Logistica",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "+0.5 attr_22; +6 attack (Infantry)"
        }
      ],
      "special_properties": {
        "trample_percent": {
          "value": "0.5",
          "source": "UNIQUE_COMBAT_PROPERTIES"
        },
        "trample_radius": {
          "value": "0.5",
          "source": "UNIQUE_COMBAT_PROPERTIES"
        }
      },
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 8.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 8,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Skirms Pikes cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.75 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Camel Rider",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 9.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 7,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 9,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Base Pierce": 4,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Skirms Pikes cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.75 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 75.0,
        "attack": 9.0,
        "melee_armor": 3.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Paladin",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 160.0,
        "attack": 14.0,
        "melee_armor": 2.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.9,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 160.0,
        "attack": 16.0,
        "melee_armor": 5.0,
        "pierce_armor": 7.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 7,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 12,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 19.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Camel Rider",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 8.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 6,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 8,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 2,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Skirms Pikes cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.75 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cataphract",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 110.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 70.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 110.0,
        "attack": 11.0,
        "melee_armor": 4.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Infantry": 9,
        "Base Melee": 9,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Infantry": 9,
        "Base Melee": 11,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 12,
        "Base Pierce": 3,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {
        "trample_percent": {
          "value": "0.5",
          "source": "UNIQUE_COMBAT_PROPERTIES"
        },
        "trample_radius": {
          "value": "0.5",
          "source": "UNIQUE_COMBAT_PROPERTIES"
        }
      },
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.18 Reload"
        },
        {
          "tech_name": "C-Bonus, Skirms Pikes cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.75 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Skirms Pikes cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.75 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Celts": [
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.15,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Infantry +5% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +10% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +15% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +20% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x1.04 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Woad Raider",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 85.0,
        "attack": 15.0,
        "melee_armor": 0.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.17,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 70.0,
          "wood": 0.0,
          "gold": 25.0
        }
      },
      "final_stats": {
        "hp": 85.0,
        "attack": 19.0,
        "melee_armor": 3.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 15,
        "Eagle Warriors": 3,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 19,
        "Eagle Warriors": 3,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 5,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry +5% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +10% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +15% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +20% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x1.04 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.2,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry +5% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +10% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +15% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +20% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x1.04 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 80.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 84.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 2.88,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        },
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        },
        {
          "tech_name": "Celtic Furor Celtica",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.4 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 75.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Paladin",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 160.0,
        "attack": 14.0,
        "melee_armor": 2.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.9,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 160.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 5,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Siege Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 70.0,
        "attack": 75.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 98.0,
        "attack": 76.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 4.8,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 75,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 76,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        },
        {
          "tech_name": "Celtic Furor Celtica",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.4 HP"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 10.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 378.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 4.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        },
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        },
        {
          "tech_name": "Celtic Furor Celtica",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.4 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 210.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 8.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        },
        {
          "tech_name": "Celtic Furor Celtica",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.4 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 4.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Infantry +5% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +10% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +15% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x1.05 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 4.8,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.15,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry +5% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +10% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +15% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x1.05 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 2.88,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "C-Bonus, Siege fire rate",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Woad Raider",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.17,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 70.0,
          "wood": 0.0,
          "gold": 25.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 13.0,
        "melee_armor": 2.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 2,
        "Standard Buildings": 2,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 13,
        "Eagle Warriors": 2,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 3,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry +5% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +10% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.05 Speed"
        },
        {
          "tech_name": "C-Bonus, Infantry +15% speed",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x1.05 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    }
  ],
  "Chinese": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 16.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 5,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Chu Ko Nu",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 10.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 85.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 35.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 5.0,
        "pierce_armor": 5.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.4,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Base Melee": 0,
        "Cavalry": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Base Melee": 0,
        "Cavalry": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Archers": 0,
        "Base Pierce": 5,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x0.941 Reload"
        },
        {
          "tech_name": "Hero Shadow Tech",
          "type": "standard",
          "building": "N/A",
          "age": "Dark",
          "effect": "+50 HP; +3 attack (Base Pierce); +2 armor (Base Melee); +1 armor (Base Pierce); +3 attr_46; +2 attr_48; +1 attr_49"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 5.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 7.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Chinese Rocketry",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; x4.22e+03 Attack; x893 Attack; x5.24e+03 Attack; x3.45e+03 Attack; x8.83e+03 Attack; x1.4e+03 Attack; x9.6e+03 Attack; x381 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 41.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 41,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 19.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Chu Ko Nu",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 45.0,
        "attack": 8.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 85.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 35.0
        }
      },
      "final_stats": {
        "hp": 45.0,
        "attack": 8.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 0.96,
        "reload_time": 2.4,
        "accuracy": 85.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Base Melee": 0,
        "Cavalry": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Base Melee": 0,
        "Cavalry": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce); +0 armor (Base Melee); +0 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce); +0 armor (Base Melee); +0 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x0.941 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 3.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.18 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Franks": [
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 13.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 15.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Capped Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_armor_classes": {
        "Base Melee": -2,
        "Base Pierce": 190,
        "Rams": 1,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Throwing Axeman",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": true,
      "base_stats": {
        "hp": 70.0,
        "attack": 8.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.0,
        "reload_time": 2.0,
        "attack_delay": 0.467,
        "accuracy": 100.0,
        "los": 6.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 25.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 6.0,
        "speed": 1.1,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Melee": 8,
        "Eagle Warriors": 2,
        "Standard Buildings": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Eagle Warriors": 2,
        "Standard Buildings": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 4,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Frankish Bearded Axe",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+2 Range; +2 attr_23; +2 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 3.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 2,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 72.0,
        "attack": 7.0,
        "melee_armor": 3.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 80.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 3,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Cavalry +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 72.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "C-Bonus, Cavalry +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Paladin",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 160.0,
        "attack": 14.0,
        "melee_armor": 2.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.9,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 192.0,
        "attack": 18.0,
        "melee_armor": 5.0,
        "pierce_armor": 7.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 7,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Cavalry +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Cavalry +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Cavalry +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 72.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "C-Bonus, Cavalry +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Throwing Axeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 3.0,
        "speed": 1.0,
        "reload_time": 2.0,
        "attack_delay": 0.467,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 25.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 5.0,
        "speed": 1.1,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 7,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Frankish Bearded Axe",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+2 Range; +2 attr_23; +2 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    }
  ],
  "Goths": [
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 14.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Capped Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_armor_classes": {
        "Base Melee": -2,
        "Base Pierce": 190,
        "Rams": 1,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 16.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 7,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age2",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age4",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -15%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.85 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -20%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.938 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x0.947 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -30%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x0.929 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 9,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Huskarl",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 12.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 0.0,
        "speed": 1.05,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 75.0,
          "wood": 0.0,
          "gold": 35.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 16.0,
        "melee_armor": 2.0,
        "pierce_armor": 10.0,
        "range": 0.0,
        "speed": 1.16,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 10,
        "Eagle Warriors": 3,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 10,
        "Eagle Warriors": 3,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 10,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age2",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age4",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -15%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.85 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -20%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.938 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x0.947 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -30%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x0.929 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 4,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age2",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age4",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -15%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.85 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -20%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.938 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x0.947 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -30%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x0.929 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 7.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 95.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 19.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Huskarl",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.05,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 75.0,
          "wood": 0.0,
          "gold": 35.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 8.0,
        "range": 0.0,
        "speed": 1.16,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "Eagle Warriors": 2,
        "Standard Buildings": 2,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "Eagle Warriors": 2,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 8,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age2",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -15%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.85 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -20%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.938 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x0.947 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age2",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -15%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.85 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -20%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.938 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x0.947 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age2",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf v Building Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -15%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.85 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -20%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.938 Cost (all)"
        },
        {
          "tech_name": "C-Bonus, Infantry Cost -25%",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x0.947 Cost (all)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Japanese": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Capped Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_armor_classes": {
        "Base Melee": -2,
        "Base Pierce": 190,
        "Rams": 1,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 16.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 1.5,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Inf Attack Spd",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Samurai",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 80.0,
        "attack": 12.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 1.9,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 30.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 16.0,
        "melee_armor": 4.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 1.425,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Unique Units": 12,
        "Eagle Warriors": 3,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Unique Units": 12,
        "Eagle Warriors": 3,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 5,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf Attack Spd",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 2.25,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf Attack Spd",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 7.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 6,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 2,
        "Elephants": -2,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 5,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Parthian Tactics",
          "type": "standard",
          "building": "Archery Range",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce); +2 attack (Spearmen)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        },
        {
          "tech_name": "C-Bonus, CA vs Archers",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "+2 attack (Archers); -2 attack (Elephants)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 7.5,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Japanese Kataparuto",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x4 attr_13; x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 2,
        "Elephants": -2,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        },
        {
          "tech_name": "C-Bonus, CA vs Archers",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "+2 attack (Archers); -2 attack (Elephants)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.18 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 1.5,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Inf Attack Spd",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 2.25,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf Attack Spd",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Samurai",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 10.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 1.9,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 30.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 12.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 1.425,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Unique Units": 10,
        "Eagle Warriors": 2,
        "Standard Buildings": 2,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Unique Units": 10,
        "Eagle Warriors": 2,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf Attack Spd",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x0.75 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Mongols": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 16.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 5,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Mangudai",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 8.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.1,
        "attack_delay": 0.383,
        "accuracy": 95.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 55.0,
          "gold": 65.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 8.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.428,
        "accuracy": 95.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 8,
        "Siege Weapons": 5,
        "Spearmen": 1,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 12,
        "Siege Weapons": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Parthian Tactics",
          "type": "standard",
          "building": "Archery Range",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce); +2 attack (Spearmen)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        },
        {
          "tech_name": "C-Bonus (Tech 394)",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Steppe Lancer",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 80.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 1.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 70.0,
          "wood": 0.0,
          "gold": 40.0
        }
      },
      "final_stats": {
        "hp": 124.0,
        "attack": 15.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 1.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 11,
        "Siege Weapons": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 15,
        "Siege Weapons": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 4,
        "Cavalry": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "[FTT] Move Lancers",
          "type": "standard",
          "building": "N/A",
          "age": "Dark",
          "effect": "set attr_43=14"
        },
        {
          "tech_name": "C-Bonus, Light Cavalry +20% HP + BL",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x100 HP; -2e+03 HP; x1.2 HP; +2e+03 HP; x0.01 HP"
        },
        {
          "tech_name": "C-Bonus, Light Cavalry +30% HP + BL",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x100 HP; -2e+03 HP; x1.08 HP; +2e+03 HP; x0.01 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Camel Rider",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 7,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 11,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 2,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 7.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.44,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 6,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 4,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Parthian Tactics",
          "type": "standard",
          "building": "Archery Range",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce); +2 attack (Spearmen)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        },
        {
          "tech_name": "C-Bonus (Tech 394)",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.98,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        },
        {
          "tech_name": "Mongol Siege Drill",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.5 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 117.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Light Cavalry +20% HP + BL",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x100 HP; -2e+03 HP; x1.2 HP; +2e+03 HP; x0.01 HP"
        },
        {
          "tech_name": "C-Bonus, Light Cavalry +30% HP + BL",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "x100 HP; -2e+03 HP; x1.08 HP; +2e+03 HP; x0.01 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 8.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 8,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Siege Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 70.0,
        "attack": 75.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 76.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 9.0,
        "speed": 0.9,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 75,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 76,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Mongol Siege Drill",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.5 Speed"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 10.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.9,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        },
        {
          "tech_name": "Mongol Siege Drill",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x1.5 Speed"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Camel Rider",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 8.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 6,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 8,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 2,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.44,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        },
        {
          "tech_name": "C-Bonus (Tech 394)",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Coustillier",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 0.0,
        "pierce_armor": 1.0,
        "range": 1.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 70.0,
          "wood": 0.0,
          "gold": 40.0
        }
      },
      "final_stats": {
        "hp": 92.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 3.0,
        "range": 1.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Siege Weapons": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Siege Weapons": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 3,
        "Cavalry": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "[FTT] Move Lancers",
          "type": "standard",
          "building": "N/A",
          "age": "Dark",
          "effect": "set attr_43=14"
        },
        {
          "tech_name": "C-Bonus, Light Cavalry +20% HP + BL",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x100 HP; -2e+03 HP; x1.2 HP; +2e+03 HP; x0.01 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.18 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 92.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Light Cavalry +20% HP + BL",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "x100 HP; -2e+03 HP; x1.2 HP; +2e+03 HP; x0.01 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Mangudai",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.1,
        "attack_delay": 0.383,
        "accuracy": 95.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 55.0,
          "gold": 65.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.428,
        "accuracy": 95.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Siege Weapons": 3,
        "Spearmen": 1,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Siege Weapons": 3,
        "Spearmen": 1,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        },
        {
          "tech_name": "C-Bonus (Tech 394)",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x0.8 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Persians": [
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 14.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        },
        {
          "tech_name": "Persians UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "-45 Cost (gold); +25 Cost (wood)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite War Elephant",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 600.0,
        "attack": 20.0,
        "melee_armor": 1.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 0.8,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 8.0,
        "cost": {
          "food": 170.0,
          "wood": 0.0,
          "gold": 85.0
        }
      },
      "final_stats": {
        "hp": 620.0,
        "attack": 24.0,
        "melee_armor": 4.0,
        "pierce_armor": 7.0,
        "range": 0.0,
        "speed": 0.88,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "All Buildings": 30,
        "Stone Defense": 30,
        "Base Melee": 20,
        "Archers": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "All Buildings": 30,
        "Stone Defense": 30,
        "Base Melee": 24,
        "Archers": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "War Elephants": 0,
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 7,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {
        "trample_percent": {
          "value": "0.5",
          "source": "extracted_data"
        },
        "trample_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Camel Rider",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 7,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 11,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Base Pierce": 4,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 7.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 80.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 6,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 5,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Parthian Tactics",
          "type": "standard",
          "building": "Archery Range",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce); +2 attack (Spearmen)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 95.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Militia",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 13.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 13,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Savar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 145.0,
        "attack": 14.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 165.0,
        "attack": 18.0,
        "melee_armor": 6.0,
        "pierce_armor": 8.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Archers": 2,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Archers": 2,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 6,
        "Cavalry": 0,
        "Base Pierce": 8,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 19.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Camel Rider",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 8.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 6,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 8,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 2,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        },
        {
          "tech_name": "Persians UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "-45 Cost (gold); +25 Cost (wood)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.18 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "War Elephant",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 450.0,
        "attack": 15.0,
        "melee_armor": 1.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 0.8,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 7.0,
        "cost": {
          "food": 170.0,
          "wood": 0.0,
          "gold": 85.0
        }
      },
      "final_stats": {
        "hp": 470.0,
        "attack": 17.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 0.88,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "All Buildings": 30,
        "Stone Defense": 30,
        "Base Melee": 15,
        "Archers": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "All Buildings": 30,
        "Stone Defense": 30,
        "Base Melee": 17,
        "Archers": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "War Elephants": 0,
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {
        "trample_percent": {
          "value": "0.5",
          "source": "extracted_data"
        },
        "trample_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 0.0,
      "total_projectiles": 0.0,
      "min_range": 0.0
    }
  ],
  "Saracens": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 13.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 15.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Mameluke",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 10.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 3.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 85.0
        }
      },
      "final_stats": {
        "hp": 145.0,
        "attack": 14.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 3.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 12,
        "Base Melee": 10,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 12,
        "Base Melee": 14,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Heroes & Kings": 0,
        "Base Pierce": 4,
        "Camels": 0,
        "Unique Units": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Camels +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        },
        {
          "tech_name": "Saracen Zealotry",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Dark",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Camel Rider",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 195.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 7,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 11,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Base Pierce": 4,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Camels +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        },
        {
          "tech_name": "Saracen Zealotry",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Dark",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 7.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 6,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 5,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Parthian Tactics",
          "type": "standard",
          "building": "Archery Range",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce); +2 attack (Spearmen)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 95.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Knight",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 14.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 14,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 8.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 8,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 12,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Siege Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 70.0,
        "attack": 75.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 76.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 75,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 76,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Counterweights",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x2.93e+03 Attack; x1.14e+03 Attack; x5.24e+03 Attack; x9.59e+03 Attack"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 10.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Counterweights",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "x2.93e+03 Attack; x883 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Camel Rider",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 170.0,
        "attack": 8.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 6,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 8,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 2,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Camels +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        },
        {
          "tech_name": "Saracen Zealotry",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Dark",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.18 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mameluke",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 8.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 3.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.4,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 85.0
        }
      },
      "final_stats": {
        "hp": 145.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 3.0,
        "speed": 1.54,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 8,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 10,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Heroes & Kings": 0,
        "Base Pierce": 2,
        "Camels": 0,
        "Unique Units": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Camels +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        },
        {
          "tech_name": "Saracen Zealotry",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Dark",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Teutons": [
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 6.0,
        "pierce_armor": 5.0,
        "range": 13.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 15.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 6,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Capped Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": -2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 200.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 190.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_attack_classes": {
        "All Buildings": 160,
        "Siege Weapons": 50,
        "Base Melee": 3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 190,
        "Rams": 1,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        },
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 6.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 9,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 3,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 6.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 6,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 armor (Base Melee)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age4",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee)"
        },
        {
          "tech_name": "Teuton Crenellations",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "set attr_130=-2.5"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Teutonic Knight",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 110.0,
        "attack": 17.0,
        "melee_armor": 10.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 0.8,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 85.0,
          "wood": 0.0,
          "gold": 30.0
        }
      },
      "final_stats": {
        "hp": 110.0,
        "attack": 21.0,
        "melee_armor": 13.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 0.88,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 17,
        "Eagle Warriors": 4,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 21,
        "Eagle Warriors": 4,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 13,
        "Base Pierce": 6,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Teuton Crenellations",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "set attr_130=-2.5"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Halberdier",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 10.0,
        "melee_armor": 5.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "Cavalry": 32,
        "War Elephants": 28,
        "Camels": 26,
        "Ships & Saboteurs": 17,
        "Mamelukes": 17,
        "Heroes & Kings": 7,
        "Base Melee": 10,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 5,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 armor (Base Melee)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age4",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee)"
        },
        {
          "tech_name": "Teuton Crenellations",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "set attr_130=-2.5"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 5.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        },
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Paladin",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 160.0,
        "attack": 14.0,
        "melee_armor": 2.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.9,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 180.0,
        "attack": 18.0,
        "melee_armor": 7.0,
        "pierce_armor": 7.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 7,
        "Cavalry": 0,
        "Base Pierce": 7,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 armor (Base Melee)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age4",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Siege Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 70.0,
        "attack": 75.0,
        "melee_armor": 0.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 76.0,
        "melee_armor": 4.0,
        "pierce_armor": 8.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 75,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 76,
        "All Buildings": 60,
        "Unused": 50,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 10.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 5.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        },
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": 1.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 5.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf Cav +1 armor Age3",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Castle",
          "effect": "+1 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 4.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Teutons UT",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+4 armor (Base Melee)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Teutonic Knight",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 90.0,
        "attack": 14.0,
        "melee_armor": 7.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 0.8,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 85.0,
          "wood": 0.0,
          "gold": 30.0
        }
      },
      "final_stats": {
        "hp": 90.0,
        "attack": 16.0,
        "melee_armor": 9.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 0.88,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 4,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Eagle Warriors": 4,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 9,
        "Base Pierce": 4,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    }
  ],
  "Turks": [
    {
      "unit_name": "Bombard Cannon",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 80.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 12.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "attack_delay": 0.117,
        "accuracy": 100.0,
        "los": 14.0,
        "cost": {
          "food": 0.0,
          "wood": 225.0,
          "gold": 225.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 40.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 14.0,
        "speed": 0.7,
        "reload_time": 6.5,
        "accuracy": 100.0,
        "los": 16.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Ships & Saboteurs": 40,
        "Base Melee": 40,
        "Stone Defense": 40,
        "Mamelukes": 40,
        "Unused": 40,
        "Siege Weapons": 20
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 5,
        "Siege Weapons": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "C-Bonus, Gunpowder +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        },
        {
          "tech_name": "Turkish Artillery",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "+2 Range; +2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "0.5",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 4.0,
      "total_projectiles": 1.0,
      "min_range": 5.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 16.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 70.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 5,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 9,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Janissary",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 22.0,
        "melee_armor": 2.0,
        "pierce_armor": 0.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.0,
        "accuracy": 65.0,
        "los": 10.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 55.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 22.0,
        "melee_armor": 5.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 65.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 22,
        "Rams": 3,
        "All Buildings": 0
      },
      "final_attack_classes": {
        "Base Pierce": 22,
        "Rams": 3,
        "All Buildings": 0
      },
      "final_armor_classes": {
        "Base Melee": 5,
        "Archers": 0,
        "Base Pierce": 4,
        "Unique Units": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Gunpowder +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Hand Cannoneer",
      "age": "Imperial",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.25,
        "accuracy": 75.0,
        "los": 9.0,
        "cost": {
          "food": 45.0,
          "wood": 0.0,
          "gold": 50.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 17.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 75.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Infantry": 10,
        "Rams": 2,
        "Spearmen": 1,
        "All Buildings": 0,
        "Condottieri": -10
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Archers": 0,
        "Base Pierce": 4,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Gunpowder +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Camel Rider",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 140.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 7,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 18,
        "Ships & Saboteurs": 9,
        "Camels": 9,
        "Mamelukes": 9,
        "Base Melee": 11,
        "Heroes & Kings": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Base Pierce": 4,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.767,
        "accuracy": 80.0,
        "los": 6.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 7.0,
        "melee_armor": 5.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 80.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 4,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 6,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 5,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Parthian Tactics",
          "type": "standard",
          "building": "Archery Range",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce); +2 attack (Spearmen)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        },
        {
          "tech_name": "Sipahi",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Hussar",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 75.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 1.9,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 95.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 7.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 1.9,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 12,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 12,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Cavalry": 0,
        "Base Pierce": 7,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Plate Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 attr_23; +2 LOS"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Light cavalry +1P armor",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 41.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 41,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 55.0,
        "attack": 8.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 8,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 19.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Camel Rider",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.45,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 55.0,
          "wood": 0.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 8.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.6,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 6,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Cavalry": 9,
        "Base Melee": 8,
        "Ships & Saboteurs": 5,
        "Camels": 5,
        "Mamelukes": 5,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Base Pierce": 2,
        "Camels": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 90.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.54,
        "reload_time": 1.8,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload; x1.06 Reload"
        },
        {
          "tech_name": "Sipahi",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 1.7,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Thumb Ring",
          "type": "standard",
          "building": "Archery Range",
          "age": "Castle",
          "effect": "set Accuracy=100%; x0.85 Reload"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Janissary",
      "age": "Castle",
      "unit_class": "Hand Cannoneer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 17.0,
        "melee_armor": 1.0,
        "pierce_armor": 0.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "attack_delay": 0.2,
        "accuracy": 50.0,
        "los": 10.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 55.0
        }
      },
      "final_stats": {
        "hp": 44.0,
        "attack": 17.0,
        "melee_armor": 3.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.45,
        "accuracy": 50.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 17,
        "Rams": 2,
        "All Buildings": 0
      },
      "final_attack_classes": {
        "Base Pierce": 17,
        "Rams": 2,
        "All Buildings": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 2,
        "Unique Units": 0,
        "Gunpowder Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Gunpowder +25% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "x1.25 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.5,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.49,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 80.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.65,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 5,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Husbandry",
          "type": "standard",
          "building": "Stable",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Bloodlines",
          "type": "standard",
          "building": "Stable",
          "age": "Feudal",
          "effect": "+20 HP"
        },
        {
          "tech_name": "C-Bonus, Light cavalry +1P armor",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Dark",
          "effect": "+1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 45.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 45.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 15,
        "Cavalry": 15,
        "Camels": 12,
        "Ships & Saboteurs": 9,
        "Mamelukes": 9,
        "Base Melee": 3,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Heroes & Kings": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 15,
        "Cavalry": 15,
        "Camels": 12,
        "Ships & Saboteurs": 9,
        "Mamelukes": 9,
        "Base Melee": 5,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Heroes & Kings": 0,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ],
  "Vikings": [
    {
      "unit_name": "Arbalester",
      "age": "Imperial",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.333,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 8.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 90.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 3,
        "Archers": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Bogsveigar",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalier",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 120.0,
        "attack": 12.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.433,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 120.0,
        "attack": 16.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 16,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Imperial",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 7.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 8.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 10,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 3,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bracer",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Ring Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Champion",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 70.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 84.0,
        "attack": 18.0,
        "melee_armor": 4.0,
        "pierce_armor": 6.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 8,
        "Standard Buildings": 4,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 8,
        "Standard Buildings": 6,
        "Cavalry": 5,
        "Camels": 4,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 4,
        "Base Pierce": 6,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Inf +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        },
        {
          "tech_name": "Viking Chieftains",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+5 attack (Cavalry); +4 attack (Camels)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Berserk",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 62.0,
        "attack": 14.0,
        "melee_armor": 2.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.05,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 5.0,
        "cost": {
          "food": 65.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 74.0,
        "attack": 18.0,
        "melee_armor": 5.0,
        "pierce_armor": 5.0,
        "range": 0.0,
        "speed": 1.16,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 3,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 18,
        "Eagle Warriors": 3,
        "Standard Buildings": 5,
        "Cavalry": 5,
        "Camels": 4,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 5,
        "Base Pierce": 5,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        },
        {
          "tech_name": "Viking Chieftains",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+5 attack (Cavalry); +4 attack (Camels)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Heavy Scorpion",
      "age": "Imperial",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.1,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 14.0,
        "melee_armor": 1.0,
        "pierce_armor": 8.0,
        "range": 8.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Base Pierce": 14,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 15,
        "War Elephants": 10,
        "All Buildings": 6,
        "Rams": 2,
        "Infantry": 2,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 8,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attr_23; +1 Range; +1 LOS; x2.94e+03 Attack"
        }
      ],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Imperial",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 11.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 11,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Onager",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 60.0,
        "attack": 50.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 8.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 10.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 51.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 9.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 11.0
      },
      "base_attack_classes": {
        "Base Melee": 50,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_attack_classes": {
        "Base Melee": 51,
        "Unused": 50,
        "All Buildings": 45,
        "Siege Weapons": 12
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {
        "splash_radius": {
          "value": "1.25",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 8.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Imperial",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 66.0,
        "attack": 8.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 27,
        "Camels": 22,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 8,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Blast Furnace",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+2 attack (Base Melee)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Plate Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Imperial",
          "effect": "+1 armor (Base Melee); +2 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        },
        {
          "tech_name": "Viking Chieftains",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+5 attack (Cavalry); +4 attack (Camels)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Siege Ram",
      "age": "Imperial",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 270.0,
        "attack": 4.0,
        "melee_armor": -1.0,
        "pierce_armor": 195.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_attack_classes": {
        "All Buildings": 200,
        "Siege Weapons": 65,
        "Base Melee": 4
      },
      "final_armor_classes": {
        "Base Melee": -1,
        "Base Pierce": 195,
        "Rams": 2,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS; -1 Range"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Trebuchet",
      "age": "Imperial",
      "unit_class": "Unpacked Siege Unit",
      "is_ranged": true,
      "base_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 16.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "attack_delay": 0.4,
        "accuracy": 15.0,
        "los": 19.0,
        "cost": {
          "food": 0.0,
          "wood": 200.0,
          "gold": 200.0
        }
      },
      "final_stats": {
        "hp": 150.0,
        "attack": 200.0,
        "melee_armor": 1.0,
        "pierce_armor": 150.0,
        "range": 17.0,
        "speed": 0.0,
        "reload_time": 10.0,
        "accuracy": 15.0,
        "los": 20.0
      },
      "base_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 200
      },
      "final_attack_classes": {
        "All Buildings": 250,
        "Base Pierce": 201
      },
      "final_armor_classes": {
        "Base Melee": 1,
        "Base Pierce": 150,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Chemistry",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "+1 attack (Base Pierce)"
        },
        {
          "tech_name": "Siege Engineers",
          "type": "standard",
          "building": "University",
          "age": "Imperial",
          "effect": "x2.94e+03 Attack; +1 Range; +1 attr_23; +1 LOS"
        }
      ],
      "special_properties": {},
      "projectile_speed": 3.5,
      "total_projectiles": 1.0,
      "min_range": 4.0
    },
    {
      "unit_name": "Battering Ram",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": false,
      "base_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 175.0,
        "attack": 2.0,
        "melee_armor": -3.0,
        "pierce_armor": 180.0,
        "range": 0.0,
        "speed": 0.6,
        "reload_time": 5.0,
        "accuracy": 100.0,
        "los": 3.0
      },
      "base_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_attack_classes": {
        "All Buildings": 150,
        "Siege Weapons": 40,
        "Base Melee": 2
      },
      "final_armor_classes": {
        "Base Melee": -3,
        "Base Pierce": 180,
        "Rams": 0,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Berserk",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 54.0,
        "attack": 12.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 1.05,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 3.0,
        "cost": {
          "food": 65.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 65.0,
        "attack": 14.0,
        "melee_armor": 3.0,
        "pierce_armor": 3.0,
        "range": 0.0,
        "speed": 1.16,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 5.0
      },
      "base_attack_classes": {
        "Base Melee": 12,
        "Eagle Warriors": 2,
        "Standard Buildings": 2,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 14,
        "Eagle Warriors": 2,
        "Standard Buildings": 4,
        "Cavalry": 5,
        "Camels": 4,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 3,
        "Unique Units": 0,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        },
        {
          "tech_name": "Viking Chieftains",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+5 attack (Cavalry); +4 attack (Camels)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Cavalry Archer",
      "age": "Castle",
      "unit_class": "Cavalry Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 4.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "attack_delay": 0.583,
        "accuracy": 50.0,
        "los": 5.0,
        "cost": {
          "food": 0.0,
          "wood": 40.0,
          "gold": 60.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 6.0,
        "speed": 1.4,
        "reload_time": 2.0,
        "accuracy": 50.0,
        "los": 7.0
      },
      "base_attack_classes": {
        "Base Pierce": 6,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Pierce": 8,
        "Spearmen": 2,
        "Standard Buildings": 0,
        "Rams": 0,
        "Archers": 0,
        "Elephants": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Cavalry Archers": 0,
        "Base Melee": 2,
        "Archers": 0,
        "Cavalry": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Crossbowman",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.25,
        "accuracy": 85.0,
        "los": 7.0,
        "cost": {
          "food": 0.0,
          "wood": 25.0,
          "gold": 45.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 5.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "accuracy": 85.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 5,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_attack_classes": {
        "Base Pierce": 7,
        "Spearmen": 3,
        "Standard Buildings": 0,
        "Rams": 0,
        "Stone Defense": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Elite Skirmisher",
      "age": "Castle",
      "unit_class": "Archer",
      "is_ranged": true,
      "base_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 0.0,
        "pierce_armor": 4.0,
        "range": 5.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "attack_delay": 0.317,
        "accuracy": 90.0,
        "los": 7.0,
        "cost": {
          "food": 25.0,
          "wood": 35.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 35.0,
        "attack": 3.0,
        "melee_armor": 2.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.96,
        "reload_time": 3.0,
        "accuracy": 90.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 3,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_attack_classes": {
        "Spearmen": 4,
        "Archers": 4,
        "Base Pierce": 5,
        "Cavalry Archers": 2,
        "Standard Buildings": 0,
        "Rams": 0
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Archers": 0,
        "Base Pierce": 6,
        "Leitis": 0,
        "Elephants": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Fletching",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Bodkin Arrow",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Pierce); +1 LOS; +1 Range; +1 attr_23"
        },
        {
          "tech_name": "Padded Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Leather Archer Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 7.0,
      "total_projectiles": 1.0,
      "min_range": 1.0
    },
    {
      "unit_name": "Knight",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 100.0,
        "attack": 10.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "attack_delay": 0.217,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 60.0,
          "wood": 0.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 100.0,
        "attack": 12.0,
        "melee_armor": 4.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.35,
        "reload_time": 1.8,
        "accuracy": 100.0,
        "los": 4.0
      },
      "base_attack_classes": {
        "Base Melee": 10,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Base Melee": 12,
        "Archers": 0,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 4,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Light Cavalry",
      "age": "Castle",
      "unit_class": "Cavalry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 7.0,
        "melee_armor": 0.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "attack_delay": 0.167,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 80.0,
          "wood": 0.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 2.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.5,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 10.0
      },
      "base_attack_classes": {
        "Monks": 10,
        "Base Melee": 7,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_attack_classes": {
        "Monks": 10,
        "Base Melee": 9,
        "All Buildings": 0,
        "Standard Buildings": 0,
        "Archers": 0,
        "Elephants": 0,
        "Siege Weapons": 0,
        "Leitis": 0,
        "Mounted Archers": -3
      },
      "final_armor_classes": {
        "Base Melee": 2,
        "Cavalry": 0,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Auto upgrade Scout Feudal Age",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Barding Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Feudal Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Imperial Age",
          "type": "standard",
          "building": "Town Center",
          "age": "Castle",
          "effect": "+2 LOS; +2 attr_23"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Long Swordsman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 60.0,
        "attack": 9.0,
        "melee_armor": 1.0,
        "pierce_armor": 1.0,
        "range": 0.0,
        "speed": 0.96,
        "reload_time": 2.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 50.0,
          "wood": 0.0,
          "gold": 20.0
        }
      },
      "final_stats": {
        "hp": 72.0,
        "attack": 11.0,
        "melee_armor": 3.0,
        "pierce_armor": 4.0,
        "range": 0.0,
        "speed": 1.06,
        "reload_time": 2.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "Base Melee": 9,
        "Eagle Warriors": 6,
        "Standard Buildings": 3,
        "Cavalry": 0,
        "Camels": 0,
        "Archers": 0
      },
      "final_attack_classes": {
        "Base Melee": 11,
        "Eagle Warriors": 6,
        "Standard Buildings": 5,
        "Cavalry": 5,
        "Camels": 4,
        "Archers": 0
      },
      "final_armor_classes": {
        "Infantry": 0,
        "Base Melee": 3,
        "Base Pierce": 4,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "Kshatriyas + Supplies",
          "type": "standard",
          "building": "N/A",
          "age": "Castle",
          "effect": "set Cost (food)=30"
        },
        {
          "tech_name": "Gambesons",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "+1 armor (Base Pierce)"
        },
        {
          "tech_name": "C-Bonus, Inf +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        },
        {
          "tech_name": "Viking Chieftains",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+5 attack (Cavalry); +4 attack (Camels)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Mangonel",
      "age": "Castle",
      "unit_class": "Siege Weapon",
      "is_ranged": true,
      "base_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 160.0,
          "gold": 135.0
        }
      },
      "final_stats": {
        "hp": 50.0,
        "attack": 40.0,
        "melee_armor": 0.0,
        "pierce_armor": 6.0,
        "range": 7.0,
        "speed": 0.6,
        "reload_time": 6.0,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_attack_classes": {
        "Base Melee": 40,
        "Unused": 40,
        "All Buildings": 35,
        "Siege Weapons": 12,
        "Monks": -1
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 6,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {
        "splash_radius": {
          "value": "1.0",
          "source": "extracted_data"
        }
      },
      "projectile_speed": 3.5,
      "total_projectiles": 6.0,
      "min_range": 3.0
    },
    {
      "unit_name": "Pikeman",
      "age": "Castle",
      "unit_class": "Infantry",
      "is_ranged": false,
      "base_stats": {
        "hp": 55.0,
        "attack": 4.0,
        "melee_armor": 0.0,
        "pierce_armor": 0.0,
        "range": 0.0,
        "speed": 1.0,
        "reload_time": 3.0,
        "attack_delay": 0.0,
        "accuracy": 100.0,
        "los": 4.0,
        "cost": {
          "food": 35.0,
          "wood": 25.0,
          "gold": 0.0
        }
      },
      "final_stats": {
        "hp": 66.0,
        "attack": 6.0,
        "melee_armor": 2.0,
        "pierce_armor": 2.0,
        "range": 0.0,
        "speed": 1.1,
        "reload_time": 3.0,
        "accuracy": 100.0,
        "los": 6.0
      },
      "base_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 22,
        "Camels": 18,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 4,
        "Eagle Warriors": 1,
        "Standard Buildings": 1,
        "Archers": 0
      },
      "final_attack_classes": {
        "War Elephants": 25,
        "Cavalry": 27,
        "Camels": 22,
        "Ships & Saboteurs": 16,
        "Mamelukes": 16,
        "Heroes & Kings": 7,
        "Base Melee": 6,
        "Eagle Warriors": 1,
        "Standard Buildings": 3,
        "Archers": 0
      },
      "final_armor_classes": {
        "Spearmen": 0,
        "Infantry": 0,
        "Base Melee": 2,
        "Base Pierce": 2,
        "Leitis": 0
      },
      "upgrades_applied": [
        {
          "tech_name": "Forging",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Iron casting",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 attack (Base Melee)"
        },
        {
          "tech_name": "Scale Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Feudal",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Chain Mail Armor",
          "type": "standard",
          "building": "Blacksmith",
          "age": "Castle",
          "effect": "+1 armor (Base Melee); +1 armor (Base Pierce)"
        },
        {
          "tech_name": "Tracking",
          "type": "standard",
          "building": "N/A",
          "age": "Feudal",
          "effect": "+2 LOS; +2 attr_23"
        },
        {
          "tech_name": "Squires",
          "type": "standard",
          "building": "Barracks",
          "age": "Castle",
          "effect": "x1.1 Speed"
        },
        {
          "tech_name": "Arson",
          "type": "standard",
          "building": "Barracks",
          "age": "Feudal",
          "effect": "+2 attack (Standard Buildings)"
        },
        {
          "tech_name": "C-Bonus, Inf +20% HP",
          "type": "civ_bonus",
          "building": "N/A",
          "age": "Feudal",
          "effect": "x1.2 HP"
        },
        {
          "tech_name": "Viking Chieftains",
          "type": "unique_tech",
          "building": "Castle",
          "age": "Castle",
          "effect": "+5 attack (Cavalry); +4 attack (Camels)"
        }
      ],
      "special_properties": {},
      "projectile_speed": 0.0,
      "total_projectiles": 1.0,
      "min_range": 0.0
    },
    {
      "unit_name": "Scorpion",
      "age": "Castle",
      "unit_class": "Ballista",
      "is_ranged": true,
      "base_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "attack_delay": 0.2,
        "accuracy": 100.0,
        "los": 9.0,
        "cost": {
          "food": 0.0,
          "wood": 75.0,
          "gold": 75.0
        }
      },
      "final_stats": {
        "hp": 40.0,
        "attack": 11.0,
        "melee_armor": 0.0,
        "pierce_armor": 7.0,
        "range": 7.0,
        "speed": 0.65,
        "reload_time": 3.6,
        "accuracy": 100.0,
        "los": 9.0
      },
      "base_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_attack_classes": {
        "Base Pierce": 11,
        "War Elephants": 7,
        "All Buildings": 3,
        "Rams": 1,
        "Infantry": 1,
        "Base Melee": 0
      },
      "final_armor_classes": {
        "Base Melee": 0,
        "Base Pierce": 7,
        "Siege Weapons": 0,
        "Leitis": 0
      },
      "upgrades_applied": [],
      "special_properties": {},
      "projectile_speed": 6.0,
      "total_projectiles": 1.0,
      "min_range": 2.0
    }
  ]
}
```
