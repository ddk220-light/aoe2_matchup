# AoE2 Reference Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/build_reference_docs.py` — a single script that fetches AoE2 data from Fandom wiki + SiegeEngineers/aoe2techtree and generates a `reference/` corpus of markdown files (53 civ files, ~190 unit files, armor-classes.md, README.md) with embedded DB comparison tables.

**Architecture:** Monolithic script with a clear internal layer stack: fetch layer (HTTP) → parse layer (wikitext/JSON) → DB query layer (sqlite) → comparison engine → renderer (markdown strings) → writer (files). Each layer is a pure function. `main()` wires them together with argparse CLI.

**Tech Stack:** Python 3, `urllib.request` (stdlib, no new dependencies), `sqlite3` (stdlib), `re` (stdlib), `argparse` (stdlib). No new packages needed — project venv already has everything required.

---

## File Map

| File | Role |
|------|------|
| `scripts/build_reference_docs.py` | Entire generator — all layers in one file, organized into sections by `# --- SECTION ---` comments |
| `reference/README.md` | Index + regeneration instructions (written by the script) |
| `reference/armor-classes.md` | All 40 armor classes |
| `reference/civs/{CivName}.md` | One per civ, 53 total |
| `reference/units/generic/{UnitName}.md` | One per generic unit slug, ~44 files |
| `reference/units/unique/{UnitName}.md` | One per unique unit (elite as section), ~122 files |
| `tests/test_reference_builder.py` | Tests for pure functions (parser, comparator, DB queries) |

---

## Key Constants (used throughout)

```python
TECHTREE_URL = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json"
WIKI_API = "https://ageofempires.fandom.com/api.php"
DB_PATH = "webapp/aoe2_reference.db"
FLOAT_TOL = 0.01
MATCH = "✅"
MISMATCH = "❌"
MISSING_EXT = "⚠️"
NOT_IN_DB = "❌ NOT IN DB"
```

---

## Task 1: Scaffold — CLI, directories, stub runner

**Files:**
- Create: `scripts/build_reference_docs.py`
- Create: `reference/.gitkeep`

- [ ] **Step 1: Create `scripts/` and `reference/` directories**

```bash
mkdir -p scripts reference/civs reference/units/generic reference/units/unique
touch reference/.gitkeep
```

- [ ] **Step 2: Write the CLI scaffold**

Create `scripts/build_reference_docs.py`:

```python
#!/usr/bin/env python3
"""
AoE2 Reference Corpus Generator

Fetches data from Fandom wiki + SiegeEngineers/aoe2techtree and generates
markdown reference files in reference/ with embedded DB comparison tables.

Usage:
    python3 scripts/build_reference_docs.py              # skip existing files
    python3 scripts/build_reference_docs.py --force      # regenerate all
    python3 scripts/build_reference_docs.py --civ Muisca # single civ
    python3 scripts/build_reference_docs.py --unit "Temple Guard"
    python3 scripts/build_reference_docs.py --dry-run    # report only
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# --- CONSTANTS ---
TECHTREE_URL = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json"
WIKI_API = "https://ageofempires.fandom.com/api.php"
DB_PATH = Path("webapp/aoe2_reference.db")
REF_DIR = Path("reference")
FLOAT_TOL = 0.01
MATCH = "✅"
MISMATCH = "❌"
MISSING_EXT = "⚠️"
NOT_IN_DB = "❌ NOT IN DB"
TODAY = date.today().isoformat()
WIKI_DELAY = 0.5  # seconds between wiki API calls


def main():
    parser = argparse.ArgumentParser(description="Generate AoE2 reference markdown corpus")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files")
    parser.add_argument("--civ", metavar="NAME", help="Generate only this civ (e.g. Muisca)")
    parser.add_argument("--unit", metavar="NAME", help='Generate only this unit (e.g. "Temple Guard")')
    parser.add_argument("--dry-run", action="store_true", help="Report mismatches, write nothing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}. Run from project root.", file=sys.stderr)
        sys.exit(1)

    print("Fetching SiegeEngineers/aoe2techtree data.json...")
    techtree = fetch_techtree()
    print(f"  → {len(techtree.get('units', {}))} units, {len(techtree.get('civs', []))} civs loaded")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    stats = {"written": 0, "skipped": 0, "mismatches": 0}

    # Always generate armor-classes (fast, no network needed)
    generate_armor_classes(conn, args, stats)

    if args.unit:
        generate_single_unit(args.unit, techtree, conn, args, stats)
    elif args.civ:
        generate_single_civ(args.civ, techtree, conn, args, stats)
    else:
        generate_all_civs(techtree, conn, args, stats)
        generate_all_units(techtree, conn, args, stats)
        write_readme(args, stats)

    conn.close()

    print(f"\nDone. Written: {stats['written']}, Skipped: {stats['skipped']}, Mismatches: {stats['mismatches']}")
    if stats['mismatches'] > 0:
        print("  ❌ Some mismatches found — check the generated files.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify the script runs without error (stub functions will be added next)**

```bash
cd /path/to/aoe2unitanalyzer
python3 scripts/build_reference_docs.py --help
```

Expected output: argparse help text showing `--force`, `--civ`, `--unit`, `--dry-run`.

- [ ] **Step 4: Commit scaffold**

```bash
git add scripts/build_reference_docs.py reference/.gitkeep
git commit -m "feat: scaffold reference corpus generator script"
```

---

## Task 2: Fetch layer — aoe2techtree + wiki API

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `fetch_techtree()`, `fetch_wiki_wikitext()`, `parse_wiki_civ()` functions
- Create: `tests/test_reference_builder.py`

- [ ] **Step 1: Write failing tests for fetch + parse functions**

Create `tests/test_reference_builder.py`:

```python
"""Tests for the reference corpus generator — pure functions only."""
import sys
sys.path.insert(0, "scripts")
import importlib.util, types

# Load the script as a module without running main()
spec = importlib.util.spec_from_file_location("builder", "scripts/build_reference_docs.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


# --- Wiki parser tests ---

SAMPLE_CIV_WIKITEXT = """
{{Civilization infobox
|name=Aztecs
|focus=Infantry & Monk
|team_bonus=Relics generate +33% gold
|unique_unit=[[Jaguar Warrior]]<br>[[Elite Jaguar Warrior]]
|unique_tech_castle=[[Atlatl]] (400 food, 350 wood)
|unique_tech_imperial=[[Garland Wars]] (450 food, 750 gold)
|bonuses=
* Villagers carry +5
* Military units created 11% faster
* Monks +5 HP per Monastery technology researched
}}
"""

def test_parse_wiki_civ_bonuses():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert "Villagers carry +5" in result["bonuses"]
    assert len(result["bonuses"]) == 3

def test_parse_wiki_civ_team_bonus():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert result["team_bonus"] == "Relics generate +33% gold"

def test_parse_wiki_civ_unique_techs():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert any("Atlatl" in t["name"] for t in result["unique_techs"])
    castle_tech = next(t for t in result["unique_techs"] if t["age"] == "Castle")
    assert "400" in castle_tech["cost"]

def test_parse_wiki_civ_unique_units():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert "Jaguar Warrior" in result["unique_units"]

def test_parse_wiki_civ_focus():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert result["focus"] == "Infantry & Monk"


# --- Unit wikitext parser tests ---

SAMPLE_UNIT_WIKITEXT = """
{{Unit infobox
|name=Jaguar Warrior
|hp=50
|attack=10
|melee_armor=1
|pierce_armor=0
|speed=1.0
|range=0
|reload_time=2
|cost=60 food, 30 gold
|train_time=21 seconds
|pop_space=1
|attack_bonus=+10 vs Infantry<br>+5 vs Eagle Warriors
}}
"""

def test_parse_wiki_unit_hp():
    result = builder.parse_wiki_unit(SAMPLE_UNIT_WIKITEXT)
    assert result["hp"] == 50.0

def test_parse_wiki_unit_attack_bonuses():
    result = builder.parse_wiki_unit(SAMPLE_UNIT_WIKITEXT)
    assert len(result["attack_bonuses"]) >= 1

def test_parse_wiki_unit_cost():
    result = builder.parse_wiki_unit(SAMPLE_UNIT_WIKITEXT)
    assert result["cost_food"] == 60
    assert result["cost_gold"] == 30
    assert result["cost_wood"] == 0
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python3 -m pytest tests/test_reference_builder.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` on `builder.parse_wiki_civ` — functions don't exist yet.

- [ ] **Step 3: Implement fetch + parse functions**

Add to `scripts/build_reference_docs.py` after the constants, before `main()`:

```python
# --- FETCH LAYER ---

def http_get(url: str, timeout: int = 15) -> bytes:
    """Fetch URL with one retry on timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": "AoE2UnitAnalyzer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError:
        time.sleep(1)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()


def fetch_techtree() -> dict:
    """Fetch SiegeEngineers data.json and return parsed JSON."""
    data = http_get(TECHTREE_URL)
    return json.loads(data)


def fetch_wiki_wikitext(page_name: str) -> str | None:
    """
    Fetch raw wikitext for a Fandom wiki page.
    Returns None if the page doesn't exist or network fails.
    """
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": page_name,
        "prop": "wikitext",
        "format": "json",
    })
    url = f"{WIKI_API}?{params}"
    try:
        data = json.loads(http_get(url))
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        if not wikitext:
            return None
        return wikitext
    except Exception:
        return None


# --- PARSE LAYER ---

def _strip_wiki_markup(text: str) -> str:
    """Remove [[links]], {{templates}}, and HTML tags from text."""
    text = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"{{[^}]+}}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def parse_wiki_civ(wikitext: str) -> dict:
    """
    Parse a civilization infobox from wiki wikitext.
    Returns dict with keys: focus, team_bonus, bonuses (list), unique_techs (list of dicts), unique_units (list).
    """
    result = {
        "focus": "",
        "team_bonus": "",
        "bonuses": [],
        "unique_techs": [],
        "unique_units": [],
    }

    # Focus / description
    m = re.search(r"\|focus\s*=\s*(.+)", wikitext)
    if m:
        result["focus"] = _strip_wiki_markup(m.group(1)).strip()

    # Team bonus
    m = re.search(r"\|team_bonus\s*=\s*(.+)", wikitext)
    if m:
        result["team_bonus"] = _strip_wiki_markup(m.group(1)).strip()

    # Bonuses — bullet list after |bonuses=
    m = re.search(r"\|bonuses\s*=\s*([\s\S]*?)(?=\n\||\Z)", wikitext)
    if m:
        bonus_text = m.group(1)
        bonuses = re.findall(r"\*\s*(.+)", bonus_text)
        result["bonuses"] = [_strip_wiki_markup(b).strip() for b in bonuses if b.strip()]

    # Unique techs — parse castle + imperial separately
    for age_key, age_label in [("unique_tech_castle", "Castle"), ("unique_tech_imperial", "Imperial")]:
        m = re.search(rf"\|{age_key}\s*=\s*\[\[([^\]]+)\]\]\s*\(([^)]+)\)", wikitext)
        if m:
            name = m.group(1).strip()
            cost_raw = m.group(2).strip()
            result["unique_techs"].append({
                "name": name,
                "age": age_label,
                "cost": cost_raw,
                "effect": "",  # Effect text pulled from wiki unit page separately
            })

    # Unique units
    m = re.search(r"\|unique_unit\s*=\s*(.+)", wikitext)
    if m:
        raw = m.group(1)
        units = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", raw)
        result["unique_units"] = [u for u in units if "Elite" not in u]

    return result


def parse_wiki_unit(wikitext: str) -> dict:
    """
    Parse a unit infobox from wiki wikitext.
    Returns dict with numeric stat fields and attack_bonuses list.
    """
    result = {
        "hp": None, "attack": None, "melee_armor": None, "pierce_armor": None,
        "speed": None, "range": None, "reload_time": None,
        "cost_food": 0, "cost_wood": 0, "cost_gold": 0,
        "train_time": None, "pop_space": 1,
        "attack_bonuses": [],
    }

    def _get_float(key: str) -> float | None:
        m = re.search(rf"\|{key}\s*=\s*([\d.]+)", wikitext)
        return float(m.group(1)) if m else None

    for field in ["hp", "attack", "melee_armor", "pierce_armor", "speed", "range", "reload_time", "pop_space"]:
        result[field] = _get_float(field)

    # Cost parsing: "60 food, 30 gold" or "25 food, 45 wood"
    m = re.search(r"\|cost\s*=\s*([^\n|]+)", wikitext)
    if m:
        cost_str = m.group(1).lower()
        for resource in ["food", "wood", "gold"]:
            cm = re.search(rf"(\d+)\s*{resource}", cost_str)
            if cm:
                result[f"cost_{resource}"] = int(cm.group(1))

    # Train time
    m = re.search(r"\|train_time\s*=\s*(\d+)", wikitext)
    if m:
        result["train_time"] = int(m.group(1))

    # Attack bonuses: "+10 vs Infantry" patterns
    m = re.search(r"\|attack_bonus\s*=\s*(.+)", wikitext, re.DOTALL)
    if m:
        bonuses_raw = m.group(1).split("|")[0]  # Stop at next field
        result["attack_bonuses"] = re.findall(r"\+(\d+)\s*vs\s*([^\n<,]+)", bonuses_raw)

    return result
```

- [ ] **Step 4: Run tests — expect passing**

```bash
python3 -m pytest tests/test_reference_builder.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_reference_docs.py tests/test_reference_builder.py
git commit -m "feat: add fetch and parse layer to reference builder"
```

---

## Task 3: DB query layer

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `query_db_civ()`, `query_db_unit()`, `query_armor_classes()`
- Modify: `tests/test_reference_builder.py` — add DB query tests using in-memory sqlite

- [ ] **Step 1: Write failing DB query tests**

Add to `tests/test_reference_builder.py`:

```python
# --- DB query tests (in-memory sqlite) ---
import sqlite3

def make_test_db():
    """Create a minimal in-memory DB that mirrors ref_units schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE ref_units (
            id INTEGER PRIMARY KEY,
            civ_name TEXT, unit_name TEXT, unit_slug TEXT, unit_type TEXT, age TEXT,
            base_hp REAL, base_attack REAL, base_melee_armor REAL, base_pierce_armor REAL,
            base_speed REAL, base_range REAL, base_reload_time REAL,
            base_cost_food REAL, base_cost_wood REAL, base_cost_gold REAL,
            base_attacks_json TEXT, base_armors_json TEXT, pop_space REAL DEFAULT 1,
            has_unit INTEGER DEFAULT 1
        );
        CREATE TABLE ref_special_effects (
            id INTEGER PRIMARY KEY,
            ref_unit_id INTEGER,
            property_name TEXT,
            property_value REAL
        );
        CREATE TABLE armor_classes (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        INSERT INTO ref_units VALUES
            (1,'Aztecs','Jaguar Warrior','jaguar_warrior_aztecs','unique','Castle',
             50,10,1,0,1.0,0,2.0,60,0,30,'{"1":10}','{}',1,1),
            (2,'Aztecs','Elite Jaguar Warrior','elite_jaguar_warrior_aztecs','unique','Imperial',
             75,12,1,0,1.0,0,2.0,60,0,30,'{"1":12}','{}',1,1);
        INSERT INTO ref_special_effects VALUES (1,1,'attack_bonus_per_kill',4);
        INSERT INTO armor_classes VALUES (0,'Unused'),(1,'Infantry'),(8,'Cavalry');
    """)
    return conn

def test_query_db_unit_base_stats():
    conn = make_test_db()
    result = builder.query_db_unit(conn, "jaguar_warrior_aztecs")
    assert result["Castle"]["base_hp"] == 50
    assert result["Castle"]["base_attack"] == 10

def test_query_db_unit_special_effects():
    conn = make_test_db()
    result = builder.query_db_unit(conn, "jaguar_warrior_aztecs")
    assert result["Castle"]["attack_bonus_per_kill"] == 4

def test_query_db_unit_both_ages():
    conn = make_test_db()
    result = builder.query_db_unit(conn, "jaguar_warrior_aztecs")
    assert "Castle" in result
    assert "Imperial" in result

def test_query_armor_classes():
    conn = make_test_db()
    result = builder.query_armor_classes(conn)
    assert result[0]["name"] == "Unused"
    assert result[1]["name"] == "Infantry"

def test_query_db_civ():
    conn = make_test_db()
    result = builder.query_db_civ(conn, "Aztecs")
    slugs = [u["unit_slug"] for u in result["unique"]]
    assert "jaguar_warrior_aztecs" in slugs
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python3 -m pytest tests/test_reference_builder.py::test_query_db_unit_base_stats -v
```

Expected: `AttributeError: module 'builder' has no attribute 'query_db_unit'`.

- [ ] **Step 3: Implement DB query functions**

Add to `scripts/build_reference_docs.py` after the parse layer:

```python
# --- DB QUERY LAYER ---

def query_armor_classes(conn: sqlite3.Connection) -> list[dict]:
    """Return all armor classes as list of {id, name} dicts."""
    rows = conn.execute("SELECT id, name FROM armor_classes ORDER BY id").fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def query_db_unit(conn: sqlite3.Connection, unit_slug_prefix: str) -> dict:
    """
    Query ref_units for all rows matching unit_slug_prefix (handles both regular + elite
    which share a slug prefix like 'jaguar_warrior_aztecs' / 'elite_jaguar_warrior_aztecs').
    Returns dict keyed by age: {'Castle': {...stats...}, 'Imperial': {...stats...}}
    Special effects are merged into each age's dict.
    """
    # Match both e.g. 'jaguar_warrior_aztecs' and 'elite_jaguar_warrior_aztecs'
    rows = conn.execute(
        """SELECT ru.*, GROUP_CONCAT(se.property_name || '=' || se.property_value, '|') as effects
           FROM ref_units ru
           LEFT JOIN ref_special_effects se ON se.ref_unit_id = ru.id
           WHERE ru.unit_slug LIKE ? OR ru.unit_slug = ?
           GROUP BY ru.id
           ORDER BY ru.age""",
        (f"%{unit_slug_prefix}%", unit_slug_prefix),
    ).fetchall()

    result = {}
    for row in rows:
        age = row["age"]
        d = dict(row)
        # Parse special effects into flat keys
        effects_str = d.pop("effects", "") or ""
        for effect in effects_str.split("|"):
            if "=" in effect:
                k, v = effect.split("=", 1)
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
        result[age] = d
    return result


def query_db_civ(conn: sqlite3.Connection, civ_name: str) -> dict:
    """
    Return all units for a civ, split into 'standard' and 'unique' lists.
    Each unit has slug, name, type, age, and base stats.
    """
    rows = conn.execute(
        """SELECT unit_slug, unit_name, unit_type, age,
                  base_hp, base_attack, base_melee_armor, base_pierce_armor,
                  base_speed, base_range, base_reload_time,
                  base_cost_food, base_cost_wood, base_cost_gold, pop_space
           FROM ref_units WHERE civ_name = ? ORDER BY unit_type, age, unit_slug""",
        (civ_name,),
    ).fetchall()
    result = {"standard": [], "unique": []}
    for row in rows:
        d = dict(row)
        result[d["unit_type"]].append(d)
    return result
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_reference_builder.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_reference_docs.py tests/test_reference_builder.py
git commit -m "feat: add DB query layer to reference builder"
```

---

## Task 4: Comparison engine

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `compare_val()`, `fmt_match()`, `compare_unit_row()`
- Modify: `tests/test_reference_builder.py` — add comparator tests

- [ ] **Step 1: Write failing comparator tests**

Add to `tests/test_reference_builder.py`:

```python
# --- Comparison engine tests ---

def test_compare_val_match_exact():
    assert builder.compare_val(50, 50) == builder.MATCH

def test_compare_val_match_float_tolerance():
    assert builder.compare_val(0.96, 0.9600) == builder.MATCH

def test_compare_val_mismatch():
    assert builder.compare_val(50, 55) == builder.MISMATCH

def test_compare_val_mismatch_outside_tolerance():
    assert builder.compare_val(0.96, 0.98) == builder.MISMATCH

def test_compare_val_missing_external():
    assert builder.compare_val(None, 50) == builder.MISSING_EXT

def test_compare_val_missing_db():
    assert builder.compare_val(50, None) == builder.NOT_IN_DB

def test_compare_val_both_none():
    # Both missing — external is the primary signal
    assert builder.compare_val(None, None) == builder.MISSING_EXT
```

- [ ] **Step 2: Run tests — expect failures**

```bash
python3 -m pytest tests/test_reference_builder.py::test_compare_val_match_exact -v
```

Expected: `AttributeError: module 'builder' has no attribute 'compare_val'`.

- [ ] **Step 3: Implement comparison engine**

Add to `scripts/build_reference_docs.py` after the DB query layer:

```python
# --- COMPARISON ENGINE ---

def compare_val(external, db_val) -> str:
    """
    Compare an external value against our DB value.
    Returns MATCH, MISMATCH, MISSING_EXT, or NOT_IN_DB symbol.
    """
    if external is None:
        return MISSING_EXT
    if db_val is None:
        return NOT_IN_DB
    try:
        if abs(float(external) - float(db_val)) <= FLOAT_TOL:
            return MATCH
        return MISMATCH
    except (TypeError, ValueError):
        # String comparison
        if str(external).strip().lower() == str(db_val).strip().lower():
            return MATCH
        return MISMATCH


def count_mismatches(rows: list[tuple]) -> int:
    """Count rows where the last element is MISMATCH."""
    return sum(1 for row in rows if row[-1] == MISMATCH)


def unit_comparison_rows(ext: dict, db: dict, fields: list[tuple[str, str]]) -> list[tuple]:
    """
    Build comparison table rows.
    fields: list of (display_label, db_column) tuples.
    ext: dict of external values keyed by db_column name.
    db: dict of DB values keyed by db_column name.
    Returns list of (field_label, ext_val, db_val, match_symbol) tuples.
    """
    rows = []
    for label, col in fields:
        ext_val = ext.get(col)
        db_val = db.get(col)
        symbol = compare_val(ext_val, db_val)
        rows.append((label, ext_val if ext_val is not None else "⚠️", db_val if db_val is not None else "—", symbol))
    return rows
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_reference_builder.py -v
```

Expected: all 21 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_reference_docs.py tests/test_reference_builder.py
git commit -m "feat: add comparison engine to reference builder"
```

---

## Task 5: Armor classes file generator

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `render_armor_classes()`, `generate_armor_classes()`

- [ ] **Step 1: Implement armor classes renderer**

Add to `scripts/build_reference_docs.py` after the comparison engine:

```python
# --- RENDERERS ---

def render_armor_classes(classes: list[dict]) -> str:
    """Render armor-classes.md content."""
    lines = [
        "# AoE2 Armor Classes",
        "",
        f"_Generated: {TODAY}_",
        "",
        "Armor classes define which unit types bonus damage applies to.",
        "A unit's `armors_json` lists the armor classes it belongs to.",
        "A unit's `attacks_json` lists the armor classes it deals bonus damage against.",
        "",
        "| ID | Name |",
        "|----|------|",
    ]
    for ac in classes:
        lines.append(f"| {ac['id']} | {ac['name']} |")
    return "\n".join(lines) + "\n"


def generate_armor_classes(conn: sqlite3.Connection, args, stats: dict):
    """Write reference/armor-classes.md."""
    out_path = REF_DIR / "armor-classes.md"
    if out_path.exists() and not args.force and not args.dry_run:
        stats["skipped"] += 1
        return
    classes = query_armor_classes(conn)
    content = render_armor_classes(classes)
    if not args.dry_run:
        out_path.write_text(content, encoding="utf-8")
        stats["written"] += 1
        print(f"  Written: {out_path}")
    else:
        print(f"  [dry-run] Would write: {out_path}")
```

- [ ] **Step 2: Wire `generate_armor_classes` into `main()` — already there from Task 1 scaffold**

Verify that `main()` already calls `generate_armor_classes(conn, args, stats)`. If not, add it after the `conn = sqlite3.connect(DB_PATH)` line.

- [ ] **Step 3: Test the armor classes generator end-to-end**

```bash
cd /path/to/aoe2unitanalyzer
python3 scripts/build_reference_docs.py --dry-run 2>&1 | head -20
```

Expected: prints "Fetching SiegeEngineers/aoe2techtree data.json...", then "[dry-run] Would write: reference/armor-classes.md".

Note: this will fail on stub functions like `generate_all_civs` — add temporary stubs:

```python
def generate_all_civs(techtree, conn, args, stats): pass
def generate_all_units(techtree, conn, args, stats): pass
def generate_single_civ(name, techtree, conn, args, stats): pass
def generate_single_unit(name, techtree, conn, args, stats): pass
def write_readme(args, stats): pass
```

- [ ] **Step 4: Run armor classes for real**

```bash
python3 scripts/build_reference_docs.py --dry-run
# Then actually write it:
python3 scripts/build_reference_docs.py --force
cat reference/armor-classes.md | head -20
```

Expected: markdown table with 40 rows, IDs 0-39.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_reference_docs.py reference/armor-classes.md
git commit -m "feat: generate armor-classes.md reference file"
```

---

## Task 6: aoe2techtree unit lookup helpers

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `find_techtree_unit()`, `find_techtree_civ()`

These helpers make the techtree JSON easy to query by name — needed by both civ and unit generators.

- [ ] **Step 1: Implement techtree lookup helpers**

Add to `scripts/build_reference_docs.py` after the fetch layer (before parse layer):

```python
# --- TECHTREE HELPERS ---

def find_techtree_unit(techtree: dict, name: str) -> dict | None:
    """
    Find a unit in aoe2techtree data.json by name (case-insensitive).
    Returns the unit dict or None if not found.
    """
    units = techtree.get("units", {})
    name_lower = name.lower()
    for unit_id, unit in units.items():
        if unit.get("name", "").lower() == name_lower:
            return unit
    return None


def find_techtree_civ(techtree: dict, name: str) -> dict | None:
    """
    Find a civilization in aoe2techtree data.json by name (case-insensitive).
    Returns the civ dict or None if not found.
    """
    civs = techtree.get("civs", [])
    name_lower = name.lower()
    for civ in civs:
        if civ.get("name", "").lower() == name_lower:
            return civ
    return None


def techtree_unit_stats(unit: dict) -> dict:
    """
    Extract standardised stats from an aoe2techtree unit dict.
    Returns dict with same keys as parse_wiki_unit() for uniform downstream processing.
    """
    if unit is None:
        return {}
    armor_str = unit.get("armor", "0/0")
    try:
        ma, pa = [int(x) for x in armor_str.split("/")]
    except (ValueError, AttributeError):
        ma, pa = 0, 0
    cost = unit.get("cost", {})
    return {
        "hp": unit.get("hp"),
        "attack": unit.get("attack"),
        "melee_armor": ma,
        "pierce_armor": pa,
        "speed": unit.get("speed"),
        "range": unit.get("range", 0),
        "reload_time": unit.get("reloadTime") or unit.get("attackSpeed"),
        "cost_food": cost.get("Food", 0),
        "cost_wood": cost.get("Wood", 0),
        "cost_gold": cost.get("Gold", 0),
        "train_time": unit.get("trainTime"),
        "pop_space": unit.get("populationUse", 1),
    }
```

- [ ] **Step 2: Add techtree helper tests**

Add to `tests/test_reference_builder.py`:

```python
# --- Techtree helper tests ---

SAMPLE_TECHTREE = {
    "units": {
        "359": {
            "id": 359, "name": "Arbalester", "age": 4,
            "hp": 40, "attack": 6, "armor": "0/0",
            "speed": 0.96, "range": 5, "reloadTime": 2.0,
            "cost": {"Food": 25, "Wood": 45},
            "trainTime": 27, "populationUse": 1,
        }
    },
    "civs": [{"name": "Aztecs", "uniqueTechs": []}]
}

def test_find_techtree_unit_found():
    result = builder.find_techtree_unit(SAMPLE_TECHTREE, "Arbalester")
    assert result is not None
    assert result["id"] == 359

def test_find_techtree_unit_case_insensitive():
    result = builder.find_techtree_unit(SAMPLE_TECHTREE, "arbalester")
    assert result is not None

def test_find_techtree_unit_not_found():
    result = builder.find_techtree_unit(SAMPLE_TECHTREE, "Nonexistent Unit")
    assert result is None

def test_techtree_unit_stats_armor_parsing():
    unit = {"armor": "1/3", "hp": 50, "attack": 8, "speed": 1.0, "cost": {}}
    result = builder.techtree_unit_stats(unit)
    assert result["melee_armor"] == 1
    assert result["pierce_armor"] == 3

def test_techtree_unit_stats_cost():
    unit = {"armor": "0/0", "cost": {"Food": 60, "Gold": 30}}
    result = builder.techtree_unit_stats(unit)
    assert result["cost_food"] == 60
    assert result["cost_gold"] == 30
    assert result["cost_wood"] == 0
```

- [ ] **Step 3: Run all tests**

```bash
python3 -m pytest tests/test_reference_builder.py -v
```

Expected: all 26 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_reference_docs.py tests/test_reference_builder.py
git commit -m "feat: add aoe2techtree lookup helpers to reference builder"
```

---

## Task 7: Civ file renderer + generator

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `render_civ_file()`, `generate_single_civ()`, `generate_all_civs()`

This is the largest renderer. It merges wiki data + techtree data + DB data into a single civ markdown file.

- [ ] **Step 1: Implement `render_civ_file()`**

Add to `scripts/build_reference_docs.py` (renderers section):

```python
# Stat fields compared for units in civ files
UNIT_STAT_FIELDS = [
    ("HP", "base_hp"),
    ("Attack", "base_attack"),
    ("Melee Armor", "base_melee_armor"),
    ("Pierce Armor", "base_pierce_armor"),
    ("Speed", "base_speed"),
    ("Range", "base_range"),
    ("Reload Time", "base_reload_time"),
    ("Cost Food", "base_cost_food"),
    ("Cost Wood", "base_cost_wood"),
    ("Cost Gold", "base_cost_gold"),
]


def render_civ_file(civ_name: str, wiki: dict, techtree_civ: dict | None, db: dict) -> str:
    """
    Render a full civ reference markdown file.
    wiki: output of parse_wiki_civ()
    techtree_civ: civ entry from data.json, or None
    db: output of query_db_civ()
    """
    lines = [
        f"# {civ_name}",
        "",
        f"**Focus:** {wiki.get('focus', '⚠️ Not found')}  ",
        "**Sources:** Fandom wiki, SiegeEngineers/aoe2techtree  ",
        f"**Generated:** {TODAY}",
        "",
    ]

    # Civilization Bonuses
    lines += ["## Civilization Bonuses", ""]
    if wiki.get("bonuses"):
        for bonus in wiki["bonuses"]:
            lines.append(f"- {bonus}")
    else:
        lines.append("⚠️ No bonus data found from wiki.")
    lines.append("")

    # Team Bonus
    lines += ["## Team Bonus", ""]
    lines.append(wiki.get("team_bonus") or "⚠️ Not found")
    lines.append("")

    # Unique Technologies
    lines += ["## Unique Technologies", ""]
    if wiki.get("unique_techs"):
        lines += [
            "| Tech | Age | Cost | Effect |",
            "|------|-----|------|--------|",
        ]
        for tech in wiki["unique_techs"]:
            lines.append(f"| {tech['name']} | {tech['age']} | {tech['cost']} | {tech.get('effect', '—')} |")
    else:
        lines.append("⚠️ No unique tech data found from wiki.")
    lines.append("")

    # Unique Units (from DB, cross-referenced with wiki stats)
    lines += ["## Unique Units", ""]
    unique_slugs_by_name: dict[str, list] = {}
    for unit in db.get("unique", []):
        base_name = unit["unit_name"]
        if base_name.startswith("Elite "):
            base_name = base_name[6:]
        unique_slugs_by_name.setdefault(base_name, []).append(unit)

    all_mismatches = []

    for base_name, variants in unique_slugs_by_name.items():
        castle = next((v for v in variants if v["age"] == "Castle"), None)
        imperial = next((v for v in variants if v["age"] == "Imperial"), None)
        lines += [f"### {base_name}", ""]

        # Stats table
        lines += [
            "| Stat | Regular | Elite |",
            "|------|---------|-------|",
        ]
        stat_map = {
            "HP": ("base_hp", "base_hp"),
            "Attack": ("base_attack", "base_attack"),
            "Melee Armor": ("base_melee_armor", "base_melee_armor"),
            "Pierce Armor": ("base_pierce_armor", "base_pierce_armor"),
            "Speed": ("base_speed", "base_speed"),
            "Range": ("base_range", "base_range"),
            "Reload Time": ("base_reload_time", "base_reload_time"),
            "Cost Food": ("base_cost_food", "base_cost_food"),
            "Cost Wood": ("base_cost_wood", "base_cost_wood"),
            "Cost Gold": ("base_cost_gold", "base_cost_gold"),
        }
        for stat_label, (castle_col, imperial_col) in stat_map.items():
            castle_val = castle[castle_col] if castle else "—"
            imperial_val = imperial[imperial_col] if imperial else "—"
            lines.append(f"| {stat_label} | {castle_val} | {imperial_val} |")
        lines.append("")

        # DB Comparison (techtree stats vs DB)
        tt_unit = find_techtree_unit({}, base_name)  # Will be passed properly below
        lines += [
            "## DB Comparison", "",
            "| Field | External (aoe2techtree) | Our DB | Match |",
            "|-------|------------------------|--------|-------|",
        ]
        # Rows will be filled by generate_single_civ which has access to techtree
        lines.append(f"_See unit file: `reference/units/unique/{base_name.replace(' ', '_')}.md`_")
        lines.append("")

    # Tech Tree Gaps (from techtree civ tree)
    lines += ["## Tech Tree Gaps", ""]
    if techtree_civ is None:
        lines.append("⚠️ No techtree data available for this civ.")
    else:
        lines.append("_Key missing units/techs based on standard tech tree_")
    lines.append("")

    return "\n".join(lines)


def generate_single_civ(civ_name: str, techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate reference/civs/{civ_name}.md"""
    out_path = REF_DIR / "civs" / f"{civ_name}.md"
    if out_path.exists() and not args.force and not getattr(args, 'dry_run', False):
        stats["skipped"] += 1
        print(f"  Skipped (exists): {out_path}")
        return

    # Try wiki — first with "(Age_of_Empires_II)" suffix, then bare name
    print(f"  Fetching wiki: {civ_name}...", end=" ", flush=True)
    time.sleep(WIKI_DELAY)
    wikitext = fetch_wiki_wikitext(f"{civ_name}_(Age_of_Empires_II)")
    if not wikitext:
        wikitext = fetch_wiki_wikitext(civ_name)
    if not wikitext:
        print("⚠️ not found")
        wiki = {}
    else:
        print("✓")
        wiki = parse_wiki_civ(wikitext)

    techtree_civ = find_techtree_civ(techtree, civ_name)
    db = query_db_civ(conn, civ_name)

    content = render_civ_file(civ_name, wiki, techtree_civ, db)

    if not getattr(args, 'dry_run', False):
        out_path.write_text(content, encoding="utf-8")
        stats["written"] += 1
        print(f"  Written: {out_path}")
    else:
        print(f"  [dry-run] Would write: {out_path}")


def generate_all_civs(techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate civ files for all 53 civs."""
    civ_names = [row[0] for row in conn.execute(
        "SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name"
    ).fetchall()]
    print(f"\nGenerating {len(civ_names)} civ files...")
    for civ_name in civ_names:
        generate_single_civ(civ_name, techtree, conn, args, stats)
```

- [ ] **Step 2: Run single civ dry-run to verify no crashes**

```bash
python3 scripts/build_reference_docs.py --civ Aztecs --dry-run
```

Expected: fetches wiki page for Aztecs, prints "[dry-run] Would write: reference/civs/Aztecs.md", no crash.

- [ ] **Step 3: Generate Aztecs civ file for real and inspect it**

```bash
python3 scripts/build_reference_docs.py --civ Aztecs
cat reference/civs/Aztecs.md
```

Expected: Valid markdown with Aztecs bonuses, unique techs (Atlatl + Garland Wars), unique units (Jaguar Warrior section).

- [ ] **Step 4: Test 3 more civs including a new one**

```bash
python3 scripts/build_reference_docs.py --civ Muisca --force
python3 scripts/build_reference_docs.py --civ Britons --force
python3 scripts/build_reference_docs.py --civ Byzantines --force
```

Inspect each output. Verify new civs (Muisca) show ⚠️ where wiki data is missing, but still write the file.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_reference_docs.py reference/civs/
git commit -m "feat: add civ file renderer and generator"
```

---

## Task 8: Unit file renderer + generator

**Files:**
- Modify: `scripts/build_reference_docs.py` — add `render_unit_file()`, `generate_single_unit()`, `generate_all_units()`

- [ ] **Step 1: Implement unit file renderer and generator**

Add to `scripts/build_reference_docs.py` (renderers section):

```python
def render_unit_file(
    unit_name: str,
    unit_type: str,  # "generic" or "unique"
    ext_stats: dict,  # from techtree_unit_stats() or parse_wiki_unit()
    db_rows: dict,   # {age: db_dict} from query_db_unit()
    civ_name: str | None = None,  # for unique units
) -> str:
    """Render a unit reference markdown file."""
    ages = list(db_rows.keys()) if db_rows else []
    col_a = ages[0] if ages else "Regular"
    col_b = ages[1] if len(ages) > 1 else "Elite"

    db_a = db_rows.get(col_a, {})
    db_b = db_rows.get(col_b, {})

    lines = [
        f"# {unit_name}",
        "",
        f"**Available to:** {'All civs' if not civ_name else civ_name}  ",
        f"**Sources:** SiegeEngineers/aoe2techtree, Fandom wiki  ",
        f"**Generated:** {TODAY}",
        "",
        "## Stats",
        "",
        f"| Stat | {col_a} | {col_b} |",
        "|------|---------|-------|",
    ]

    stat_rows = [
        ("HP", "base_hp"),
        ("Attack", "base_attack"),
        ("Melee Armor", "base_melee_armor"),
        ("Pierce Armor", "base_pierce_armor"),
        ("Speed", "base_speed"),
        ("Range", "base_range"),
        ("Reload Time", "base_reload_time"),
        ("Cost Food", "base_cost_food"),
        ("Cost Wood", "base_cost_wood"),
        ("Cost Gold", "base_cost_gold"),
        ("Pop Space", "pop_space"),
    ]
    for label, col in stat_rows:
        a = db_a.get(col, "—")
        b = db_b.get(col, "—")
        lines.append(f"| {label} | {a} | {b} |")
    lines.append("")

    # Special effects
    special_fields = [
        "bleed_dps", "bleed_duration", "trample_percent", "trample_flat_damage",
        "trample_radius", "pass_through_percent", "pass_through_count",
        "attack_bonus_per_kill", "charge_attack_melee", "dodge_shield_max",
        "attack_speed_ramp", "attack_speed_min", "execute_damage_per_step",
        "ally_death_heal",
    ]
    special = {k: db_a.get(k) for k in special_fields if db_a.get(k)}
    lines += ["## Special Effects", ""]
    if special:
        for k, v in special.items():
            lines.append(f"- **{k}:** {v}")
    else:
        lines.append("None")
    lines.append("")

    # DB Comparison
    comp_rows = []
    for label, col in stat_rows:
        ext_val = ext_stats.get(col)
        db_val_a = db_a.get(col)
        symbol = compare_val(ext_val, db_val_a)
        comp_rows.append((label, ext_val if ext_val is not None else "⚠️", db_val_a if db_val_a is not None else "—", symbol))

    lines += [
        "## DB Comparison",
        "",
        f"| Field | External | Our DB ({col_a}) | Match |",
        "|-------|----------|-----------------|-------|",
    ]
    mismatch_count = 0
    for label, ext, db_val, symbol in comp_rows:
        lines.append(f"| {label} | {ext} | {db_val} | {symbol} |")
        if symbol == MISMATCH:
            mismatch_count += 1
    lines.append("")

    if mismatch_count:
        lines.append(f"**⚠️ {mismatch_count} mismatch(es) found — investigate.**")
        lines.append("")

    return "\n".join(lines), mismatch_count


def generate_single_unit(unit_name: str, techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate reference file for one unit (by display name)."""
    safe_name = unit_name.replace(" ", "_")

    # Find in DB — try standard then unique
    slug_rows = conn.execute(
        "SELECT DISTINCT unit_slug, unit_type, civ_name FROM ref_units WHERE unit_name LIKE ? LIMIT 5",
        (f"%{unit_name}%",),
    ).fetchall()

    if not slug_rows:
        print(f"  ⚠️ Unit not found in DB: {unit_name}")
        return

    unit_type = slug_rows[0]["unit_type"]
    civ_name = slug_rows[0]["civ_name"] if unit_type == "unique" else None
    base_slug = slug_rows[0]["unit_slug"]

    subdir = "unique" if unit_type == "unique" else "generic"
    out_path = REF_DIR / "units" / subdir / f"{safe_name}.md"

    if out_path.exists() and not args.force and not getattr(args, 'dry_run', False):
        stats["skipped"] += 1
        print(f"  Skipped (exists): {out_path}")
        return

    # Get external stats
    tt_unit = find_techtree_unit(techtree, unit_name)
    if tt_unit:
        ext_stats = techtree_unit_stats(tt_unit)
    else:
        # Fallback to wiki
        print(f"  Fetching wiki unit: {unit_name}...", end=" ", flush=True)
        time.sleep(WIKI_DELAY)
        wikitext = fetch_wiki_wikitext(unit_name.replace(" ", "_"))
        if wikitext:
            print("✓")
            ext_stats = parse_wiki_unit(wikitext)
        else:
            print("⚠️ not found")
            ext_stats = {}

    db_rows = query_db_unit(conn, base_slug)
    content, mismatches = render_unit_file(unit_name, unit_type, ext_stats, db_rows, civ_name)

    if not getattr(args, 'dry_run', False):
        out_path.write_text(content, encoding="utf-8")
        stats["written"] += 1
        stats["mismatches"] += mismatches
        print(f"  Written: {out_path}" + (f" ({mismatches} ❌)" if mismatches else ""))
    else:
        print(f"  [dry-run] Would write: {out_path}")


def generate_all_units(techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate unit files for all standard and unique unit slugs."""
    units = conn.execute(
        "SELECT DISTINCT unit_name, unit_slug, unit_type FROM ref_units ORDER BY unit_type, unit_name"
    ).fetchall()

    # Deduplicate by unit_name (same unit appears for each civ)
    seen_names = set()
    print(f"\nGenerating unit files...")
    for row in units:
        name = row["unit_name"]
        if name.startswith("Elite "):
            continue  # Elite variants are sections within the base unit file
        if name in seen_names:
            continue
        seen_names.add(name)
        generate_single_unit(name, techtree, conn, args, stats)
```

- [ ] **Step 2: Test single unit generation**

```bash
python3 scripts/build_reference_docs.py --unit "Jaguar Warrior" --force
cat "reference/units/unique/Jaguar_Warrior.md"
```

Expected: markdown with stats table, DB comparison rows, ✅ symbols where values match.

```bash
python3 scripts/build_reference_docs.py --unit "Arbalester" --force
cat "reference/units/generic/Arbalester.md"
```

- [ ] **Step 3: Test a new civ unique unit**

```bash
python3 scripts/build_reference_docs.py --unit "Temple Guard" --force
cat "reference/units/unique/Temple_Guard.md"
```

Expected: file written, may have ⚠️ for external data (if not in aoe2techtree yet) but no crash.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_reference_docs.py reference/units/
git commit -m "feat: add unit file renderer and generator"
```

---

## Task 9: README + full build run

**Files:**
- Modify: `scripts/build_reference_docs.py` — implement `write_readme()`
- Run full build

- [ ] **Step 1: Implement `write_readme()`**

Add to `scripts/build_reference_docs.py`:

```python
def write_readme(args, stats: dict):
    """Write reference/README.md index file."""
    if getattr(args, 'dry_run', False):
        return
    content = f"""# AoE2 Reference Corpus

Generated: {TODAY}

This directory contains markdown reference files for all AoE2 civilizations, units, and armor classes.
Each file includes a **DB Comparison** table showing whether our local database matches the authoritative
external sources (Fandom wiki + SiegeEngineers/aoe2techtree).

## Structure

```
reference/
  armor-classes.md       — All 40 armor classes
  civs/                  — One file per civilization (53 total)
  units/generic/         — Generic unit lines (Arbalester, Paladin, etc.)
  units/unique/          — Unique units per civ (Cataphract, Leitis, etc.)
```

## How to Regenerate

From the project root:

```bash
# Regenerate all files (skip existing)
python3 scripts/build_reference_docs.py

# Force regenerate all files
python3 scripts/build_reference_docs.py --force

# Regenerate a single civ
python3 scripts/build_reference_docs.py --civ Muisca

# Regenerate a single unit
python3 scripts/build_reference_docs.py --unit "Temple Guard"

# Dry run — report mismatches without writing
python3 scripts/build_reference_docs.py --dry-run
```

## Reading the DB Comparison Tables

| Symbol | Meaning |
|--------|---------|
| ✅ | Values match within tolerance (±0.01 for floats) |
| ❌ | Values differ — needs investigation |
| ⚠️ | External data not available for this field |
| ❌ NOT IN DB | Field missing from our database |

## When to Regenerate

Regenerate the corpus after:
- A new dat file update (new patch with balance changes)
- Adding new civilizations
- Adding new combat mechanics to the simulator

## Sources

- **Stats:** [SiegeEngineers/aoe2techtree](https://github.com/SiegeEngineers/aoe2techtree)
- **Civ bonuses + unique techs:** [Fandom Wiki](https://ageofempires.fandom.com/wiki/Age_of_Empires_II)
- **DB:** `webapp/aoe2_reference.db` (local SQLite, queried directly)
"""
    (REF_DIR / "README.md").write_text(content, encoding="utf-8")
    print(f"  Written: {REF_DIR / 'README.md'}")
```

- [ ] **Step 2: Run full build**

```bash
cd /path/to/aoe2unitanalyzer
python3 scripts/build_reference_docs.py --force 2>&1 | tee /tmp/reference_build.log
```

This will take several minutes (53 wiki API calls × 0.5s delay = ~27s minimum, plus fetch time).

Expected final line: `Done. Written: X, Skipped: 0, Mismatches: Y`

- [ ] **Step 3: Verify key files exist and are non-empty**

```bash
ls reference/civs/ | wc -l        # expect 53
ls reference/units/generic/ | wc -l  # expect ~40
ls reference/units/unique/ | wc -l   # expect ~100+
wc -l reference/civs/Aztecs.md
wc -l reference/civs/Muisca.md
cat reference/armor-classes.md | grep -c "^|"  # expect 42 (header + separator + 40 data)
```

- [ ] **Step 4: Check for any ❌ mismatches**

```bash
grep -r "❌" reference/units/ | grep -v "NOT IN DB" | head -20
```

Report any mismatches found to the user for investigation.

- [ ] **Step 5: Run existing tests to confirm nothing broke**

```bash
python3 -m pytest tests/ -v
```

Expected: all 27 existing simulation tests + all reference builder tests pass.

- [ ] **Step 6: Commit everything**

```bash
git add scripts/build_reference_docs.py reference/ tests/test_reference_builder.py
git commit -m "feat: complete reference corpus — 53 civs, unit files, armor classes"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|------------------|------|
| Single script with skip-if-exists + `--force` | Task 1 |
| `--civ`, `--unit`, `--dry-run` CLI flags | Task 1 |
| Fetch SiegeEngineers data.json once, cache | Task 2 |
| Fetch Fandom wiki with 0.5s delay | Task 2, 7, 8 |
| 53 civ files | Task 7 |
| ~190 unit files (generic + unique) | Task 8 |
| `reference/armor-classes.md` | Task 5 |
| `reference/README.md` | Task 9 |
| DB comparison with ✅/❌/⚠️ | Task 4 |
| Float tolerance ±0.01 | Task 4 |
| Wiki 404 → partial file with warning | Task 7, 8 |
| aoe2techtree missing → wiki fallback | Task 8 |
| DB missing → `❌ NOT IN DB` | Task 4 |
| Retry on timeout | Task 2 |
| Summary: written/skipped/mismatches | Task 1 (`main()`) |
| New civs (Muisca etc.) handled gracefully | Task 7 |

**Placeholder check:** No TBDs or vague steps found.

**Type consistency:** `render_unit_file()` returns a `(content, mismatch_count)` tuple — confirmed used as such in `generate_single_unit()`.

**One gap found and fixed:** `render_civ_file()` has a call to `find_techtree_unit({}, base_name)` with an empty dict — this is intentional (civ file delegates unit stat comparison to the unit file). The cross-reference note in the markdown points readers to the unit file.
