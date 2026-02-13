# Unique Unit Stats Verification — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify ALL unique unit stats — core stats, attack/armor class bonuses, special abilities, upgrades — against the AoE2 Fandom Wiki using parallel sub-agents, producing a comprehensive discrepancy report.

**Architecture:** Phase 1 extracts TWO data sets: (a) base stats from `extracted_data/units.json` for core stat comparison, and (b) combat properties from the DB `unit_stats` table for special ability verification. Phase 2 launches ~55 parallel haiku agents — one per wiki page — each comparing base+elite stats AND special abilities. Phase 3 aggregates results into a report.

**Tech Stack:** Claude Code Task tool (general-purpose agents, haiku model), WebFetch, Python for data extraction, markdown for reporting.

**Key insight:** Our DB (`unit_stats`) stores fully-upgraded civ-specific stats (HP, attack, armor, speed, range include civ tech bonuses). The wiki shows BASE stats. For core stats we compare against `extracted_data/units.json` (raw base). For special abilities (trample, charge, dodge, etc.) we compare DB combat property columns against wiki descriptions.

---

## Data Sources

| What to verify | Our source | Wiki source |
|----------------|-----------|-------------|
| Core stats (HP, attack, armor, speed, range, cost) | `extracted_data/units.json` (base values) | Stats infobox |
| Attack bonuses (+X vs Cavalry, etc.) | `extracted_data/units.json` → `attacks[]` array | "Attack bonuses" section |
| Armor classes | `extracted_data/units.json` → `armors[]` array | "Armor classes" section |
| Special abilities (trample, charge, dodge, bleed, etc.) | DB `unit_stats` combat property columns | Wiki prose/ability descriptions |
| Elite upgrade cost | DB `unit_stats.upgrade_cost` | Wiki upgrade section |
| Elite stat changes | Diff between base and elite in `extracted_data` | Wiki elite section |

### Units with Special Abilities (from DB)

These units have non-trivial combat properties that MUST be verified:

| Unit | Special Properties |
|------|--------------------|
| Ballista Elephant | pass_through 67% |
| Berserk | hp_regen 40 |
| Cataphract | trample (flat 5, radius 0.5) — Logistica tech |
| Centurion | charge_attack_melee 5, recharge 4s |
| Chakram Thrower | pass_through 100% |
| Chu Ko Nu | extra_projectiles 2/4 (base/elite), 3 pierce each |
| Composite Bowman | ignores_pierce_armor |
| Coustillier | charge_attack_melee 20/25, recharge 40s |
| Fire Archer | extra_projectiles 2, charge projectiles |
| Hussite Wagon | extra_projectiles 5, multi-class damage |
| Iron Pagoda | block_first_melee |
| Jaguar Warrior | attack_bonus_per_kill 4 |
| Jian Swordsman | hp_regen, hp_transform_threshold |
| Kipchak | extra_projectiles 2/3 |
| Leitis | ignores_melee_armor |
| Liao Dao | bleed (2/3 dps, 5s duration) |
| Monaspa | hp_regen 8/14 |
| Mounted Trebuchet | hp_regen 20, min_range 3 |
| Obuch | armor_strip_per_hit 1 |
| Organ Gun | extra_projectiles 4/5, min_range 1 |
| Ratha | trample (melee), bonus_damage_reduction |
| Serjeant | bonus_damage_reduction 0.4 |
| Shrivamsha Rider | dodge_shield 5/7, recharge 20 |
| Tiger Cavalry | attack_bonus_per_kill 4 |
| Urumi Swordsman | trample 50%, ignores_melee_armor (elite) |
| War Chariot | extra_projectiles 1, trample 40% |
| War Elephant | trample 50% |
| Xianbei Raider | charge burst projectiles (5 count) |

---

## Task 1: Extract Complete Unit Data

**Files:**
- Create: `scripts/extract_unique_stats.py`

**Step 1: Write the extraction script**

This script pulls BOTH base stats from extracted JSON AND combat properties from the DB, merging them into one file per wiki page.

```python
#!/usr/bin/env python3
"""Extract all unique unit data for wiki verification.

Combines:
- Base stats from extracted_data/units.json (for core stat comparison)
- Combat properties from webapp/aoe2_units.db (for special ability verification)

Output: docs/unique_unit_verification_data.json
"""
import json
import sqlite3
import os

COMBAT_PROPERTY_COLS = [
    'extra_projectiles', 'extra_projectile_attacks_json',
    'splash_radius', 'splash_on_hit_radius', 'splash_on_hit_fraction',
    'trample_percent', 'trample_radius', 'trample_flat_damage',
    'charge_projectile_count', 'charge_projectile_attacks_json', 'charge_projectile_speed',
    'charge_attack_range', 'charge_ignores_armor', 'charge_attack_melee', 'charge_recharge_time',
    'dodge_shield_max', 'dodge_shield_recharge',
    'ignores_pierce_armor', 'ignores_melee_armor',
    'bleed_dps', 'bleed_duration',
    'block_first_melee', 'attack_bonus_per_kill',
    'first_attack_extra_projectiles', 'hp_regen',
    'pass_through_percent', 'hp_transform_threshold',
    'bonus_damage_reduction', 'armor_strip_per_hit',
    'min_attack_range', 'projectile_speed', 'is_siege_projectile',
]

def main():
    base_dir = os.path.join(os.path.dirname(__file__), '..')

    # --- Load extracted base stats ---
    with open(os.path.join(base_dir, 'database_creation', 'extracted_data', 'units.json')) as f:
        extracted_units = json.load(f)

    # --- Load DB combat properties + upgrade costs ---
    db_path = os.path.join(base_dir, 'webapp', 'aoe2_units.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get unique unit names from DB
    cur.execute('''
        SELECT DISTINCT us.unit_name
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        WHERE us.has_unit = 1 AND u.unit_type = 'unique'
    ''')
    db_unique_names = {row[0] for row in cur.fetchall()}

    # Get combat properties for each unique unit (one representative row per unit_name)
    cur.execute('''
        SELECT us.unit_name, us.upgrade_cost, us.attacks_json, us.armors_json,
               ''' + ', '.join(f'us.{col}' for col in COMBAT_PROPERTY_COLS) + '''
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        WHERE us.has_unit = 1 AND u.unit_type = 'unique'
        GROUP BY us.unit_name
    ''')
    db_combat = {}
    for row in cur.fetchall():
        props = {}
        for col in COMBAT_PROPERTY_COLS:
            val = row[col]
            if val not in (None, 0, 0.0, '', '{}', '[]'):
                props[col] = val
        db_combat[row['unit_name']] = {
            'combat_properties': props,
            'upgrade_cost': row['upgrade_cost'],
            'attacks_json': row['attacks_json'],
            'armors_json': row['armors_json'],
        }
    conn.close()

    # --- Build wiki page entries ---
    wiki_pages = {}

    for u in extracted_units:
        if u.get('type') != 70:
            continue
        name = u['name']
        if name not in db_unique_names:
            continue

        is_elite = name.startswith('Elite ')
        base_name = name[6:] if is_elite else name

        if base_name not in wiki_pages:
            wiki_pages[base_name] = {
                'base': None, 'elite': None, 'wiki_url': None,
                'base_db_combat': None, 'elite_db_combat': None,
            }

        # Wiki URL
        wiki_name = base_name.replace(' ', '_')
        wiki_pages[base_name]['wiki_url'] = (
            f'https://ageofempires.fandom.com/wiki/{wiki_name}_(Age_of_Empires_II)'
        )

        # Extracted base stats
        stats = {
            'name': name,
            'id': u['id'],
            'hp': u.get('hit_points'),
            'attack': u.get('displayed_attack', u.get('base_attack')),
            'range': u.get('range'),
            'accuracy': u.get('accuracy'),
            'reload_time': u.get('reload_time'),
            'attack_delay': u.get('attack_delay'),
            'melee_armor': u.get('displayed_melee_armor', u.get('melee_armor', 0)),
            'pierce_armor': u.get('displayed_pierce_armor', u.get('pierce_armor', 0)),
            'speed': u.get('speed'),
            'line_of_sight': u.get('line_of_sight'),
            'cost': u.get('cost'),
            'train_time': u.get('train_time'),
            'attacks': u.get('attacks', []),
            'armors': u.get('armors', []),
            'class_name': u.get('class_name'),
            'max_total_projectiles': u.get('max_total_projectiles'),
        }

        if is_elite:
            wiki_pages[base_name]['elite'] = stats
            wiki_pages[base_name]['elite_db_combat'] = db_combat.get(name, {})
        else:
            wiki_pages[base_name]['base'] = stats
            wiki_pages[base_name]['base_db_combat'] = db_combat.get(name, {})

    # Output
    output_path = os.path.join(base_dir, 'docs', 'unique_unit_verification_data.json')
    with open(output_path, 'w') as f:
        json.dump(wiki_pages, f, indent=2)

    n_base = sum(1 for p in wiki_pages.values() if p['base'])
    n_elite = sum(1 for p in wiki_pages.values() if p['elite'])
    n_special = sum(1 for p in wiki_pages.values()
                    if (p.get('base_db_combat') or {}).get('combat_properties')
                    or (p.get('elite_db_combat') or {}).get('combat_properties'))

    print(f'Extracted {len(wiki_pages)} wiki pages ({n_base} base, {n_elite} elite, {n_special} with special abilities)')
    print(f'Saved to {output_path}')

if __name__ == '__main__':
    main()
```

**Step 2: Run the script**

Run: `python3 scripts/extract_unique_stats.py`
Expected: Output like "Extracted 55 wiki pages (55 base, 53 elite, 30+ with special abilities)"

**Step 3: Verify output for a unit with special abilities**

Run: `python3 -c "import json; d=json.load(open('docs/unique_unit_verification_data.json')); print(json.dumps(d['Cataphract'], indent=2))"`
Expected: Cataphract entry with base stats + elite_db_combat showing trample_flat_damage=5, trample_radius=0.5

**Step 4: Commit**

```bash
git add scripts/extract_unique_stats.py docs/unique_unit_verification_data.json
git commit -m "feat: extract unique unit stats + combat properties for wiki verification"
```

---

## Task 2: Launch Parallel Wiki-Fetch Agents

This task is orchestration — launch ~55 agents in parallel using the Claude Code `Task` tool.

**Step 1: Read the extracted data file**

Read `docs/unique_unit_verification_data.json` to get the full list of units, their wiki URLs, base/elite stats, and combat properties.

**Step 2: Launch all agents in parallel**

For EACH wiki page entry, launch a `Task` tool call with:
- `subagent_type`: `general-purpose`
- `model`: `haiku`
- `run_in_background`: `true`
- `description`: `Verify {unit_name} stats`
- `prompt`: (expanded template below)

**Agent prompt template** (substitute `{UNIT_NAME}`, `{WIKI_URL}`, `{BASE_STATS_JSON}`, `{ELITE_STATS_JSON}`, `{BASE_COMBAT_JSON}`, `{ELITE_COMBAT_JSON}`):

```
You are verifying Age of Empires II unit stats for: {UNIT_NAME}

## Step 1: Fetch Wiki Page

Use WebFetch on: {WIKI_URL}
With prompt: "Extract EVERYTHING about {UNIT_NAME} and Elite {UNIT_NAME}. I need:
1. STATS: HP, Attack (base damage), Range, Accuracy, Rate of Fire, Melee Armor, Pierce Armor, Speed, Line of Sight, Training Time, Cost
2. ATTACK BONUSES: Every attack bonus listed (e.g., +10 vs Infantry, +5 vs Siege)
3. ARMOR CLASSES: All armor classes listed (e.g., Archer, Cavalry, Unique Unit)
4. SPECIAL ABILITIES: Any unique mechanics described (trample damage, charge attack, ignores armor, extra projectiles, HP regeneration, dodge mechanic, bleeding damage, armor stripping, pass-through projectiles, bonus damage reduction, etc.)
5. ELITE UPGRADE: Cost and what stats change from base to elite
List base and elite versions separately with ALL details."

If the fetch fails or the page doesn't exist, try the alternate URL without the _(Age_of_Empires_II) suffix:
{WIKI_URL_ALT}

## Step 2: Compare Against Our Data

### OUR BASE STATS (from game data extraction):
{BASE_STATS_JSON}

### OUR ELITE STATS (from game data extraction):
{ELITE_STATS_JSON}

### OUR BASE COMBAT PROPERTIES (from database):
{BASE_COMBAT_JSON}

### OUR ELITE COMBAT PROPERTIES (from database):
{ELITE_COMBAT_JSON}

## Step 3: Return Results

Return EXACTLY this JSON (no other text before or after):
{
  "unit_name": "{UNIT_NAME}",
  "wiki_url": "{WIKI_URL}",
  "wiki_fetch_status": "success" or "failed",
  "base_comparison": {
    "status": "match" or "discrepancy" or "no_wiki_data",
    "core_stat_discrepancies": [
      {"field": "hp", "ours": 60, "wiki": 65, "note": ""}
    ],
    "attack_bonus_discrepancies": [
      {"class": "Cavalry", "ours": 10, "wiki": 12, "note": ""}
    ],
    "armor_class_discrepancies": [
      {"class": "Archer", "ours": 0, "wiki": 2, "note": ""}
    ],
    "special_ability_discrepancies": [
      {"ability": "trample_flat_damage", "ours": 5, "wiki": "5 trample damage", "match": true, "note": ""}
    ]
  },
  "elite_comparison": {
    "status": "match" or "discrepancy" or "no_wiki_data",
    "core_stat_discrepancies": [],
    "attack_bonus_discrepancies": [],
    "armor_class_discrepancies": [],
    "special_ability_discrepancies": []
  },
  "elite_upgrade": {
    "wiki_cost": "1000F 800G",
    "our_cost": 1800,
    "match": true,
    "stat_changes_on_wiki": "description of what changes"
  },
  "wiki_mentions_not_in_our_data": ["any abilities or stats the wiki mentions that we don't track"],
  "our_data_not_on_wiki": ["any properties we have that wiki doesn't mention"],
  "notes": "Any observations, especially about special mechanics"
}

## Comparison Rules

CORE STATS:
- "Rate of Fire" on wiki = our "reload_time" (should match)
- Wiki "Attack" = our "attack" field (base pierce or melee damage number)
- Numeric tolerance: +/- 0.05 for floats
- Wiki cost like "55W 65G" → compare wood and gold separately against our cost object
- "Rate of Fire" on wiki is time between attacks (our reload_time), NOT attacks per second

ATTACK BONUSES:
- Compare each wiki bonus (e.g., "+10 vs Infantry") against our "attacks" array
- Our attacks[] has entries like {"class": 4, "class_name": "Base Melee", "amount": 12}
- Only flag entries where amounts differ, not where class names differ slightly
- Ignore attack classes with amount=0 or negative amounts (those are internal mechanics)

ARMOR CLASSES:
- Compare wiki armor classes against our "armors" array
- Our armors[] has entries like {"class": 8, "class_name": "Cavalry", "amount": 0}
- Only flag actual value differences

SPECIAL ABILITIES (compare against our combat_properties):
- extra_projectiles: wiki might say "fires X secondary projectiles"
- trample_percent/trample_flat_damage: wiki might say "deals trample/splash damage"
- ignores_melee_armor/ignores_pierce_armor: wiki says "ignores armor"
- charge_attack_melee: wiki says "charge attack deals X damage"
- dodge_shield_max: wiki says "dodge shield absorbs X damage"
- hp_regen: wiki says "regenerates X HP per minute" (CONVERT: wiki HP/min ÷ 60 ≈ our value? No — our hp_regen value is in HP per minute already for Berserk=40)
- bleed_dps/bleed_duration: wiki says "causes bleeding for X damage over Y seconds"
- armor_strip_per_hit: wiki says "reduces enemy armor by X per hit"
- pass_through_percent: wiki says "projectiles pass through units"
- bonus_damage_reduction: wiki says "receives X% less bonus damage"
- block_first_melee: wiki says "blocks first melee attack"
- attack_bonus_per_kill: wiki says "gains X attack per kill"
- If wiki describes an ability we don't have in combat_properties, note it in wiki_mentions_not_in_our_data
- If we have a property wiki doesn't mention, note it in our_data_not_on_wiki
```

**Step 3: Record all background task IDs**

After launching, collect all `{unit_name: output_file_path}` mappings from the Task tool results.

**Important:** Launch ALL agents in a SINGLE message with multiple Task tool calls to maximize parallelism. If there are limits, batch into groups of 10-15.

---

## Task 3: Monitor and Collect Agent Results

**Step 1: Wait for agents to complete**

Use `Read` tool on each agent's output_file path to check results. Use `TaskOutput` with `block=true, timeout=60000` for agents that haven't finished.

**Step 2: Parse each agent's JSON output**

Extract the JSON result from each agent's output. Handle:
- Valid JSON → parse normally
- Malformed output → attempt to extract JSON from text, else mark as `parse_failed`
- Timeout / no output → mark as `timeout`

**Step 3: Save raw results**

Save all parsed results to `docs/stats-verification-raw-results.json`

---

## Task 4: Generate Discrepancy Report

**Files:**
- Create: `docs/stats-verification-report.md`

**Step 1: Compile the report**

From collected results, generate a markdown report:

```markdown
# AoE2 Unique Unit Stats Verification Report

Generated: {date}
Source: AoE2 Fandom Wiki vs our game data extraction + database

## Summary
- Total wiki pages checked: X
- Total unit variants verified: Y (base + elite)
- Perfect matches: Z
- Units with core stat discrepancies: A
- Units with attack bonus discrepancies: B
- Units with armor class discrepancies: C
- Units with special ability discrepancies: D
- Failed wiki fetches: E

## Core Stat Discrepancies

| Unit | Variant | Field | Our Value | Wiki Value | Notes |
|------|---------|-------|-----------|------------|-------|

## Attack Bonus Discrepancies

| Unit | Variant | Attack Class | Our Value | Wiki Value | Notes |
|------|---------|-------------|-----------|------------|-------|

## Armor Class Discrepancies

| Unit | Variant | Armor Class | Our Value | Wiki Value | Notes |
|------|---------|------------|-----------|------------|-------|

## Special Ability Discrepancies

| Unit | Variant | Ability | Our Value | Wiki Description | Match? | Notes |
|------|---------|---------|-----------|-----------------|--------|-------|

## Elite Upgrade Discrepancies

| Unit | Our Cost | Wiki Cost | Match? |
|------|----------|-----------|--------|

## Data We Have But Wiki Doesn't Mention
(May indicate data-driven properties not widely known)

## Wiki Mentions We Don't Track
(May indicate missing features in our model)

## Failed Fetches / Missing Pages

## Perfect Matches
```

**Step 2: Save and commit**

```bash
git add docs/stats-verification-report.md docs/stats-verification-raw-results.json
git commit -m "feat: add comprehensive unit stats verification report"
```

---

## Task 5: Analyze Results and Create Follow-ups

**Step 1: Review the discrepancy report with the user**

Categorize discrepancies:
- **Confirmed bugs:** Our data clearly wrong (e.g., wrong HP, missing attack bonus)
- **Wiki outdated:** Wiki hasn't been updated for recent patches
- **3K units not on wiki:** Expected — these are new expansion units
- **Interpretation differences:** e.g., HP regen units (HP/min vs HP/sec)
- **Upgrade-related:** Our DB has upgrades applied, wiki shows base
- **Special ability gaps:** Abilities we model that wiki doesn't mention, or vice versa

**Step 2: Create follow-up tasks**

For confirmed data bugs, create actionable tasks specifying:
- Which file to fix (`database_creation/config.py`, `extracted_data/`, `generate_main_db.py`)
- What the correct value should be
- Which units are affected

---

## Execution Notes

### Wiki URL Patterns
Primary: `https://ageofempires.fandom.com/wiki/{Name}_(Age_of_Empires_II)`
Fallback: `https://ageofempires.fandom.com/wiki/{Name}`
Special cases:
- `Ratha (Melee)` / `Ratha (Ranged)` → both on `Ratha_(Age_of_Empires_II)` page
- `Chu Ko Nu` → `Chu_Ko_Nu_(Age_of_Empires_II)`
- 3K units (Fire Archer, Iron Pagoda, Tiger Cavalry, War Chariot, Xianbei Raider, Jian Swordsman, Grenadier, Mounted Trebuchet, Liao Dao, White Feather Crossbowman, Warrior Priest) — may not exist on wiki yet

### HP Regen Units
Our `hp_regen` value for Berserk is 40.0 (HP per minute). Wiki typically says "regenerates 40 HP per minute". These should match directly. For other units, verify the unit (HP/min vs HP/sec).

### Parallelism Limits
- Launch agents in batches of 10-15 if needed
- Each WebFetch takes 5-15 seconds
- Total expected time: 1-3 minutes for all agents

### Data Source Mapping
- Core stats → `extracted_data/units.json` (BASE, pre-upgrade) vs wiki base stats
- Combat properties → DB `unit_stats` table (may include civ-specific tech effects like Logistica for Cataphract trample)
- When a combat property comes from a civ tech (not base unit), note this — wiki may list it under the tech, not the unit
