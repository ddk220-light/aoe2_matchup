# Unique Unit Stats Verification — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify all unique unit base stats against the AoE2 Fandom Wiki using parallel sub-agents, producing a discrepancy report.

**Architecture:** Phase 1 extracts base stats from `database_creation/extracted_data/units.json` (not the DB, which has civ upgrades baked in). Phase 2 launches ~55 parallel haiku agents — one per wiki page — each comparing base+elite stats. Phase 3 reads all background agent outputs and compiles a markdown report.

**Tech Stack:** Claude Code Task tool (general-purpose agents, haiku model), WebFetch, Python for data extraction, markdown for reporting.

**Key insight:** Our DB (`unit_stats`) stores fully-upgraded civ-specific stats. The wiki shows BASE stats. We compare against `extracted_data/units.json` which has the raw base stats matching the wiki.

---

## Task 1: Extract Base Stats Script

**Files:**
- Create: `scripts/extract_unique_stats.py`

**Step 1: Write the extraction script**

```python
#!/usr/bin/env python3
"""Extract base stats for all unique units from extracted_data/units.json.

Outputs a JSON file mapping unit display names to their base stats,
grouped by wiki page (base + elite on same page).
"""
import json
import sys
import os

def main():
    json_path = os.path.join(os.path.dirname(__file__), '..', 'database_creation', 'extracted_data', 'units.json')
    with open(json_path) as f:
        units = json.load(f)

    # Build lookup of unique unit names from DB
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', 'webapp', 'aoe2_units.db')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        SELECT DISTINCT us.unit_name
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        WHERE us.has_unit = 1 AND u.unit_type = 'unique'
    ''')
    db_unique_names = {row[0] for row in cur.fetchall()}
    conn.close()

    # Match extracted units to DB unique unit names
    wiki_pages = {}  # wiki_page_name -> {base: {...}, elite: {...}}

    for u in units:
        if u.get('type') != 70:
            continue
        name = u['name']
        if name not in db_unique_names:
            continue

        # Determine wiki page name (strip "Elite " prefix)
        is_elite = name.startswith('Elite ')
        base_name = name[6:] if is_elite else name
        wiki_page = base_name

        if wiki_page not in wiki_pages:
            wiki_pages[wiki_page] = {'base': None, 'elite': None, 'wiki_url': None}

        # Build wiki URL
        wiki_name = base_name.replace(' ', '_')
        wiki_pages[wiki_page]['wiki_url'] = f'https://ageofempires.fandom.com/wiki/{wiki_name}_(Age_of_Empires_II)'

        # Extract stats
        stats = {
            'name': name,
            'id': u['id'],
            'hp': u.get('hit_points'),
            'attack': u.get('displayed_attack', u.get('base_attack')),
            'range': u.get('range'),
            'accuracy': u.get('accuracy'),
            'reload_time': u.get('reload_time'),
            'attack_delay': u.get('attack_delay'),
            'melee_armor': u.get('melee_armor', u.get('displayed_melee_armor', 0)),
            'pierce_armor': u.get('pierce_armor', u.get('displayed_pierce_armor', 0)),
            'speed': u.get('speed'),
            'line_of_sight': u.get('line_of_sight'),
            'cost': u.get('cost'),
            'train_time': u.get('train_time'),
            'attacks': u.get('attacks', []),
            'armors': u.get('armors', []),
            'projectile_speed': u.get('projectile_speed'),
            'blast_damage': u.get('blast_damage'),
            'max_total_projectiles': u.get('max_total_projectiles'),
            'class_name': u.get('class_name'),
        }

        if is_elite:
            wiki_pages[wiki_page]['elite'] = stats
        else:
            wiki_pages[wiki_page]['base'] = stats

    # Output
    output_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'unique_unit_base_stats.json')
    with open(output_path, 'w') as f:
        json.dump(wiki_pages, f, indent=2)

    print(f'Extracted {len(wiki_pages)} wiki pages ({sum(1 for p in wiki_pages.values() if p["base"])} base, {sum(1 for p in wiki_pages.values() if p["elite"])} elite)')
    print(f'Saved to {output_path}')

if __name__ == '__main__':
    main()
```

**Step 2: Run the script**

Run: `python3 scripts/extract_unique_stats.py`
Expected: Output like "Extracted 55 wiki pages (55 base, 53 elite)" and creates `docs/unique_unit_base_stats.json`

**Step 3: Verify output looks correct**

Run: `python3 -c "import json; d=json.load(open('docs/unique_unit_base_stats.json')); print(json.dumps(d['Mangudai'], indent=2))"`
Expected: Mangudai base stats with hp=60, attack=6, range=4.0, speed=1.4

**Step 4: Commit**

```bash
git add scripts/extract_unique_stats.py docs/unique_unit_base_stats.json
git commit -m "feat: add script to extract unique unit base stats for wiki verification"
```

---

## Task 2: Launch Parallel Wiki-Fetch Agents

This task is orchestration — it uses the Claude Code `Task` tool to launch ~55 agents in parallel.

**Step 1: Read the extracted stats file**

Read `docs/unique_unit_base_stats.json` to get the full list of units and their wiki URLs.

**Step 2: Launch all agents in parallel**

For EACH wiki page entry in the JSON, launch a `Task` tool call with:
- `subagent_type`: `general-purpose`
- `model`: `haiku`
- `run_in_background`: `true`
- `description`: `Verify {unit_name} stats`
- `prompt`: (template below)

**Agent prompt template** (substitute `{UNIT_NAME}`, `{WIKI_URL}`, `{BASE_STATS_JSON}`, `{ELITE_STATS_JSON}`):

```
You are verifying Age of Empires II unit stats. Your job:

1. Fetch this wiki page: {WIKI_URL}
   Use WebFetch with prompt: "Extract ALL stats for {UNIT_NAME} and Elite {UNIT_NAME} (if exists). Return structured data: HP, Attack (base damage value), Attack bonuses (class name and amount), Range, Accuracy, Rate of Fire, Melee Armor, Pierce Armor, Speed, Line of Sight, Training Time, Cost (food/wood/gold). List base and elite versions separately."

2. Compare wiki stats against our database values below.

OUR BASE STATS:
{BASE_STATS_JSON}

OUR ELITE STATS:
{ELITE_STATS_JSON}

3. Return your findings as EXACTLY this JSON format (no other text):
{
  "unit_name": "{UNIT_NAME}",
  "wiki_url": "{WIKI_URL}",
  "wiki_fetch_status": "success" or "failed",
  "base_comparison": {
    "status": "match" or "discrepancy" or "no_data",
    "discrepancies": [
      {"field": "hp", "ours": 60, "wiki": 65, "note": "optional explanation"}
    ]
  },
  "elite_comparison": {
    "status": "match" or "discrepancy" or "no_data",
    "discrepancies": []
  },
  "notes": "Any additional observations"
}

COMPARISON RULES:
- Rate of Fire on wiki = our reload_time (should match)
- Wiki "Attack" = our "attack" field (base pierce/melee damage)
- Attack bonuses: compare wiki bonus amounts vs our attacks[] entries by class_name
- Numeric tolerance: +/- 0.05 for floats
- If wiki shows a stat we don't have, note it but don't flag as discrepancy
- If we have a stat wiki doesn't show, mark as "not_on_wiki" in notes
- Wiki cost format may differ (e.g., "55W 65G") — normalize before comparing
- "Rate of Fire" on wiki is time between attacks (our reload_time)
```

**Step 3: Record all background task IDs**

After launching, save the list of `{unit_name: task_id}` mappings. Each `Task` tool returns an output_file path — save these for Phase 3.

**Important:** Launch ALL agents in a SINGLE message with multiple Task tool calls to maximize parallelism. Group into batches of 10-15 if the tool has limits on concurrent calls.

---

## Task 3: Monitor and Collect Agent Results

**Step 1: Wait for agents to complete**

Use `Read` tool on each agent's output_file path to check results. If an agent hasn't finished yet, use `TaskOutput` with `block=true` to wait.

**Step 2: Parse each agent's JSON output**

Extract the JSON result from each agent's output. Handle cases where:
- Agent returned valid JSON → parse it
- Agent failed or returned malformed output → mark as `fetch_failed`
- Agent timed out → mark as `timeout`

**Step 3: Save raw results**

Save all parsed results to `docs/stats-verification-raw-results.json`

---

## Task 4: Generate Discrepancy Report

**Files:**
- Create: `docs/stats-verification-report.md`

**Step 1: Compile the report**

From the collected results, generate a markdown report with these sections:

```markdown
# AoE2 Unique Unit Stats Verification Report

Generated: {date}
Source: AoE2 Fandom Wiki vs extracted_data/units.json

## Summary
- Total units checked: X
- Perfect matches: Y
- Units with discrepancies: Z
- Failed wiki fetches: W

## Discrepancies

| Unit | Field | Our Value | Wiki Value | Notes |
|------|-------|-----------|------------|-------|
| ... | ... | ... | ... | ... |

## Failed Fetches
- Unit Name: error reason

## Units Not Found on Wiki
- Unit Name: (3K units may not be on wiki yet)

## Perfect Matches
- Unit Name 1
- Unit Name 2
- ...
```

**Step 2: Save and commit**

```bash
git add docs/stats-verification-report.md docs/stats-verification-raw-results.json
git commit -m "feat: add unique unit stats verification report"
```

---

## Task 5: Analyze Results

**Step 1: Review the discrepancy report**

Present the report to the user with analysis:
- Which discrepancies are real bugs in our data?
- Which are expected (e.g., wiki is outdated, 3K units not on wiki)?
- Which fields are most commonly mismatched?
- Recommended fixes for confirmed discrepancies

**Step 2: Create follow-up tasks**

For any confirmed data bugs, create actionable tasks describing what needs fixing and in which file (e.g., `database_creation/config.py`, `extracted_data/`, or `generate_main_db.py`).

---

## Execution Notes

### Wiki URL Patterns
Most units: `https://ageofempires.fandom.com/wiki/{Name}_(Age_of_Empires_II)`
Special cases to handle:
- `Ratha (Melee)` / `Ratha (Ranged)` → both on `Ratha_(Age_of_Empires_II)` page
- `Chu Ko Nu` → `Chu_Ko_Nu_(Age_of_Empires_II)`
- 3K units (Fire Archer, Iron Pagoda, Tiger Cavalry, War Chariot, Xianbei Raider, Jian Swordsman, Grenadier, Mounted Trebuchet, Liao Dao, White Feather Crossbowman, Warrior Priest) — may not exist on wiki yet

### Parallelism Limits
- Launch agents in batches if needed (10-15 per batch)
- Each WebFetch takes 5-15 seconds
- Total expected time: 1-3 minutes for all agents

### Base vs Upgraded Stats
- We compare `extracted_data/units.json` (BASE stats) against wiki (BASE stats)
- This is an apples-to-apples comparison
- The DB `unit_stats` table has civ upgrades applied — DO NOT use for comparison
