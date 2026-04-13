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
        "redirects": "1",
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
    """
    Clean wiki markup to plain text:
    - {{tt|display|tooltip}} → display value
    - {{resources|gold = +50}} → '+50 gold'
    - <br /> → ' / '
    - <ref>...</ref> → removed
    - [[page|display]] / [[page]] → display text
    - remaining {{templates}} → removed
    - remaining HTML tags → removed
    """
    # {{tt|display|tooltip}} → keep display
    text = re.sub(r"\{\{tt\|([^|}]+)\|[^}]*\}\}", r"\1", text)
    # {{2class|ClassName}} → ClassName (armor class icon template)
    text = re.sub(r"\{\{2class\|([^|}]+?)(?:\|[^}]*)?\}\}", r"\1", text)
    # {{2icons|Name}} used inline (not as a tech reference) → Name
    text = re.sub(r"\{\{2icons\|([^|}]+?)(?:\|[^}]*)?\}\}", r"\1", text)
    # {{resources|food = 200|gold = 100}} → '200 food, 100 gold'
    def _fmt_resources(m: re.Match) -> str:
        parts = []
        for seg in m.group(1).split("|"):
            rm = re.match(r"\s*(\w+)\s*=\s*(.+)", seg.strip())
            if rm:
                parts.append(f"{rm.group(2).strip()} {rm.group(1)}")
        return ", ".join(parts)
    text = re.sub(r"\{\{resources\|([^}]+)\}\}", _fmt_resources, text)
    # <br /> or <br> → separator
    text = re.sub(r"<br\s*/?>", " / ", text, flags=re.IGNORECASE)
    # <ref ...>...</ref> → remove
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    # [[page|display]] or [[page]] → display
    text = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", text)
    # remaining {{templates}} → remove (single-depth; handles most cases)
    text = re.sub(r"\{\{[^{}]+\}\}", "", text)
    # remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def parse_wiki_civ(wikitext: str) -> dict:
    """
    Parse a civilization page from wiki wikitext.
    Handles the real Fandom format: {{Infobox civilization with |Focus =,
    and === Characteristics === subsections for bonuses/team bonus/unique techs.
    Returns dict with keys: focus, team_bonus, bonuses (list), unique_techs (list of dicts), unique_units (list).
    """
    result = {
        "focus": "",
        "team_bonus": "",
        "bonuses": [],
        "unique_techs": [],
        "unique_units": [],
    }

    # Focus — |Focus = [[Cavalry unit...|Cavalry]] in {{Infobox civilization
    m = re.search(r"\|Focus\s*=\s*(.+)", wikitext, re.IGNORECASE)
    if m:
        result["focus"] = _strip_wiki_markup(m.group(1)).strip()

    def _section(heading: str) -> str:
        """Extract text between === heading === and the next === or end."""
        pat = rf"===\s*{re.escape(heading)}\s*===\s*\n([\s\S]*?)(?====|\Z)"
        sm = re.search(pat, wikitext, re.IGNORECASE)
        return sm.group(1) if sm else ""

    # Civilization bonuses — bullet list under === Civilization bonuses ===
    bonus_text = _section("Civilization bonuses")
    if bonus_text:
        bonuses = re.findall(r"\*\s*(.+)", bonus_text)
        result["bonuses"] = [_strip_wiki_markup(b).strip() for b in bonuses if b.strip()]

    # Team bonus — colon-prefixed line under === Team bonus ===
    team_text = _section("Team bonus")
    if team_text:
        tm = re.search(r":\s*(.+)", team_text)
        if tm:
            result["team_bonus"] = _strip_wiki_markup(tm.group(1)).strip()

    # Unique technologies — supports:
    #   * {{2icons|Name}} (effect)      — most civs
    #   : {{2icons|Name}}: effect       — Khmer (colon-prefix)
    #   * {{AoEII Icons|Name}}: effect  — Spanish, Mayans (different icon template)
    #   * {{tt|{{AoEII Icons|Name}}: effect|old name}}  — Mayans (versioned wrapper)
    tech_text = _section("Unique technologies")
    if tech_text:
        for line in re.findall(r"[*:]\s*(.+)", tech_text):
            name_m = re.search(r"\{\{(?:2icons|AoEII\s*Icons)\|([^}|]+)", line)
            if not name_m:
                continue
            tech_name = name_m.group(1).strip()
            # Effect = text after the closing }} of the icon template, strip remaining markup
            close_pos = line.find("}}", name_m.end())
            after = line[close_pos + 2:].lstrip() if close_pos != -1 else ""
            # Strip leading colon/parens delimiters
            after = re.sub(r"^[:()\s]+", "", after)
            # Strip {{tt}} tooltip tail: |old text}} that may follow nested templates
            after = re.sub(r"\|[^|{}]*\}\}[^}]*$", "", after)
            effect = _strip_wiki_markup(after).rstrip(".")
            # Fallback: parentheses in stripped full line
            if not effect:
                eff_m = re.search(r"\(([^)]+)\)", _strip_wiki_markup(line))
                effect = eff_m.group(1).strip() if eff_m else ""
            result["unique_techs"].append({"name": tech_name, "effect": effect})

    # Unique units — from === Unique unit === subsection
    unit_text = _section("Unique unit")
    if unit_text:
        for name_m in re.finditer(r"\{\{2icons\|([^}|]+)", unit_text):
            name = _strip_wiki_markup(name_m.group(1)).strip()
            if name and "Elite" not in name:
                result["unique_units"].append(name)
    if not result["unique_units"]:
        # Fallback: |Unit = {{2icons|Name}} in the infobox
        um = re.search(r"\|Unit\s*=\s*(.+)", wikitext)
        if um:
            for name_m in re.finditer(r"\{\{2icons\|([^}|]+)", um.group(1)):
                name = _strip_wiki_markup(name_m.group(1)).strip()
                if name and "Elite" not in name:
                    result["unique_units"].append(name)

    return result


def parse_wiki_unit(wikitext: str) -> dict:
    """
    Parse a unit infobox from wiki wikitext.
    Supports both real Fandom format ({{Infobox AoE2 unit, |HP =, |MAttack =, |Food =)
    and simplified test format (|hp=, |attack=, |cost=60 food, 30 gold).
    Returns dict with numeric stat fields and attack_bonuses list.
    """
    result = {
        "hp": None, "attack": None, "melee_armor": None, "pierce_armor": None,
        "speed": None, "range": None, "reload_time": None,
        "cost_food": 0, "cost_wood": 0, "cost_gold": 0,
        "train_time": None, "pop_space": 1,
        "attack_bonuses": [],
    }

    def _get_field(*keys) -> float | None:
        """Try multiple field name variants (case-insensitive value extraction)."""
        for key in keys:
            m = re.search(rf"\|{key}\s*=\s*([\d.]+)", wikitext, re.IGNORECASE)
            if m:
                return float(m.group(1))
        return None

    # Real wiki field names first, simplified fallbacks second
    result["hp"]           = _get_field("HP", "hp")
    result["attack"]       = _get_field("MAttack", "PAttack", "attack")  # melee or ranged
    result["melee_armor"]  = _get_field("Armor", "melee_armor")
    result["pierce_armor"] = _get_field("PierceArmor", "pierce_armor")
    result["speed"]        = _get_field("Speed", "speed")
    result["range"]        = _get_field("Range", "range")
    result["reload_time"]  = _get_field("ROF", "reload_time")
    result["pop_space"]    = _get_field("PopSpace", "pop_space")

    # Real wiki: separate |Food =, |Wood =, |Gold = fields
    for resource in ["Food", "Wood", "Gold"]:
        m = re.search(rf"\|{resource}\s*=\s*(\d+)", wikitext, re.IGNORECASE)
        if m:
            result[f"cost_{resource.lower()}"] = int(m.group(1))

    # Simplified format fallback: |cost=60 food, 30 gold
    if result["cost_food"] == 0 and result["cost_wood"] == 0 and result["cost_gold"] == 0:
        m = re.search(r"\|cost\s*=\s*([^\n|]+)", wikitext)
        if m:
            cost_str = m.group(1).lower()
            for resource in ["food", "wood", "gold"]:
                cm = re.search(rf"(\d+)\s*{resource}", cost_str)
                if cm:
                    result[f"cost_{resource}"] = int(cm.group(1))

    # Train time: real wiki "|Time = 27 seconds", simplified "|train_time = 27"
    m = re.search(r"\|Time\s*=\s*(\d+)", wikitext, re.IGNORECASE) or \
        re.search(r"\|train_time\s*=\s*(\d+)", wikitext)
    if m:
        result["train_time"] = int(m.group(1))

    # Attack bonuses
    m = re.search(r"\|attack_bonus\s*=\s*(.+)", wikitext, re.DOTALL)
    if m:
        bonuses_raw = m.group(1).split("|")[0]
        result["attack_bonuses"] = re.findall(r"\+(\d+)\s*vs\s*([^\n<,]+)", bonuses_raw)

    return result


def _extract_brace_block(text: str, tag: str) -> str:
    """
    Find {{tag ...}} in text and return the block content (after the tag line, before closing }}).
    Uses brace-depth counting so nested {{ }} don't cause early termination.
    Returns empty string if not found.
    """
    start = text.find("{{" + tag)
    if start == -1:
        return ""
    pos = start + 2  # skip opening {{
    depth = 1
    while pos < len(text) and depth > 0:
        if text[pos:pos+2] == "{{":
            depth += 1
            pos += 2
        elif text[pos:pos+2] == "}}":
            depth -= 1
            if depth == 0:
                break
            pos += 2
        else:
            pos += 1
    # Return content between the tag name and closing }}
    content_start = start + 2 + len(tag)
    return text[content_start:pos]


def _extract_wiki_display_names(text: str) -> list:
    """Extract display names from [[page|display]] or [[page]] wiki links."""
    results = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', text):
        inner = m.group(1)
        if "|" in inner:
            display = inner.split("|", 1)[1]
        else:
            display = re.sub(r'\s*\(Age of Empires II\)', '', inner)
        display = display.strip().rstrip("s")  # strip trailing plural 's' added outside link
        if display and "File:" not in display:
            results.append(display)
    return results


def parse_wiki_unit_extras(wikitext: str) -> dict:
    """
    Parse enhancement data from a unit wiki page:
    - Technologies that boost the unit ({{Boosts|Technologies}})
    - Civilization bonuses ({{Boosts|Civilization bonuses}})
    - Team bonuses ({{Boosts|Team bonuses}})
    - Strengths & Weaknesses ({{S&W}})
    Returns dict with keys: techs, civ_bonuses, team_bonuses, strong_vs, weak_vs.
    Each boost section is a dict of {stat_label: [list of entry strings]}.
    """
    result = {"techs": {}, "civ_bonuses": {}, "team_bonuses": {}, "strong_vs": [], "weak_vs": []}

    def _parse_boosts_block(section_name: str) -> dict:
        """Extract |Stat = items from a {{Boosts|section_name}} template, brace-safe."""
        block = _extract_brace_block(wikitext, f"Boosts|{section_name}")
        if not block:
            return {}
        out = {}
        for stat in ["HP", "Attack", "Armor", "Speed", "Conversion", "Creation", "LOS", "Other"]:
            sm = re.search(rf'\|{stat}\s*=\s*(.+?)(?=\n\||\Z)', block, re.DOTALL)
            if not sm:
                continue
            raw = sm.group(1).strip()
            # Split individual entries on <br />
            items_raw = re.split(r'<br\s*/?>', raw)
            items = []
            for item in items_raw:
                item = item.strip()
                if not item:
                    continue
                # Name: from {{2icons|Name}} template
                nm = re.search(r'\{\{2icons\|([^}|]+)', item)
                name = nm.group(1).strip() if nm else ""
                # Value: the part in outer parentheses (...), which may contain nested {{ }}
                # Use brace-aware extraction: find first '(' and scan to matching ')'
                val = ""
                pi = item.find("(")
                if pi != -1:
                    depth = 0
                    for i, ch in enumerate(item[pi:], pi):
                        if ch == "(":
                            depth += 1
                        elif ch == ")":
                            depth -= 1
                            if depth == 0:
                                raw_val = item[pi+1:i]
                                # Clean: {{tt|+20%|+32}} → +20%
                                raw_val = re.sub(r'\{\{tt\|([^|]+)\|[^}]+\}\}', r'\1', raw_val)
                                # Clean: {{Armor|melee = +1|pierce = +1}} → melee=+1, pierce=+1
                                raw_val = re.sub(
                                    r'\{\{Armor\|([^}]+)\}\}',
                                    lambda mv: mv.group(1).replace(" = ", "=").replace("|", ", "),
                                    raw_val
                                )
                                val = _strip_wiki_markup(raw_val).strip()
                                break
                if name or val:
                    entry = name + (f" ({val})" if val else "")
                    items.append(entry.strip())
            if items:
                out[stat] = items
        return out

    result["techs"] = _parse_boosts_block("Technologies")
    result["civ_bonuses"] = _parse_boosts_block("Civilization bonuses")
    result["team_bonuses"] = _parse_boosts_block("Team bonuses")

    # Strengths & Weaknesses from {{S&W}}
    sw_block = _extract_brace_block(wikitext, "S&W")
    if sw_block:
        for key, field in [("strong_vs", "S"), ("weak_vs", "W")]:
            sm = re.search(rf'\|{field}\s*=\s*(.+?)(?=\n\||\Z)', sw_block, re.DOTALL)
            if sm:
                result[key] = _extract_wiki_display_names(sm.group(1))

    return result


# --- DB QUERY LAYER ---

def query_armor_classes(conn: sqlite3.Connection) -> list:
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
    Return all units for a civ, split into 'standard', 'unique', and 'disabled' lists.
    'disabled' = standard units available in 20+ civs that this civ lacks.
    Each unit has slug, name, type, age, and base stats.
    """
    rows = conn.execute(
        """SELECT unit_slug, unit_name, unit_type, age,
                  base_hp, base_attack, base_melee_armor, base_pierce_armor,
                  base_speed, base_range, base_reload_time,
                  base_cost_food, base_cost_wood, base_cost_gold, pop_space
           FROM ref_units WHERE civ_name = ? AND unit_type IN ('standard', 'unique') ORDER BY unit_type, age, unit_slug""",
        (civ_name,),
    ).fetchall()
    result: dict = {"standard": [], "unique": [], "disabled": []}
    for row in rows:
        d = dict(row)
        key = d["unit_type"]
        result[key].append(d)

    # Disabled standard units: appear in 20+ civs but not in this civ
    # Use a subquery to pick the most-common name per slug (avoids arbitrary GROUP BY name pick)
    civ_slugs = {d["unit_slug"] for d in result["standard"]}
    widespread = conn.execute(
        """SELECT unit_slug, COUNT(DISTINCT civ_name) as cnt
           FROM ref_units WHERE unit_type='standard'
           GROUP BY unit_slug HAVING cnt >= 20 ORDER BY unit_slug"""
    ).fetchall()
    for slug, cnt in widespread:
        if slug not in civ_slugs:
            # Canonical name = most frequent unit_name for this slug
            name_row = conn.execute(
                """SELECT unit_name FROM ref_units WHERE unit_slug=? AND unit_type='standard'
                   GROUP BY unit_name ORDER BY COUNT(*) DESC LIMIT 1""",
                (slug,),
            ).fetchone()
            name = name_row[0] if name_row else slug
            result["disabled"].append({"unit_slug": slug, "unit_name": name, "civ_count": cnt})

    return result


# --- COMPARISON ENGINE ---

def compare_val(external, db_val) -> str:
    """
    Compare an external value against our DB value.
    Returns MATCH, MISMATCH, MISSING_EXT, or NOT_IN_DB symbol.
    Float comparison uses FLOAT_TOL tolerance (0.01).
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
        if str(external).strip().lower() == str(db_val).strip().lower():
            return MATCH
        return MISMATCH


def count_mismatches(rows: list) -> int:
    """Count rows where the last element equals MISMATCH."""
    return sum(1 for row in rows if row[-1] == MISMATCH)


def unit_comparison_rows(ext: dict, db: dict, fields: list) -> list:
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


# --- TECHTREE HELPERS ---

def find_techtree_unit(techtree: dict, name: str):
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


def find_techtree_civ(techtree: dict, name: str):
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


# --- RENDERERS ---

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


def render_armor_classes(classes: list) -> str:
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


def render_civ_file(civ_name: str, wiki: dict, techtree_civ, db: dict) -> tuple:
    """
    Render a full civ reference markdown file.
    wiki: output of parse_wiki_civ() — may be empty dict if wiki not found
    techtree_civ: civ entry from data.json, or None
    db: output of query_db_civ()
    Returns (content_string, mismatch_count) tuple.
    """
    lines = [
        f"# {civ_name}",
        "",
        f"**Focus:** {wiki.get('focus') or '⚠️ Not found'}  ",
        "**Sources:** Fandom wiki, SiegeEngineers/aoe2techtree  ",
        f"**Generated:** {TODAY}",
        "",
    ]

    # Civilization Bonuses
    lines += ["## Civilization Bonuses", ""]
    bonuses = wiki.get("bonuses", [])
    if bonuses:
        for bonus in bonuses:
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
    unique_techs = wiki.get("unique_techs", [])
    if unique_techs:
        lines += [
            "| Tech | Effect |",
            "|------|--------|",
        ]
        for tech in unique_techs:
            lines.append(f"| {tech['name']} | {tech.get('effect') or '—'} |")
    else:
        lines.append("⚠️ No unique tech data found from wiki.")
    lines.append("")

    # Unique Units (from DB)
    lines += ["## Unique Units", ""]
    unique_units = db.get("unique", [])

    if not unique_units:
        lines.append("⚠️ No unique units found in DB for this civ.")
        lines.append("")

    # Group by base name (Castle = regular, Imperial = elite)
    by_base: dict = {}
    for unit in unique_units:
        name = unit["unit_name"]
        base = name[6:] if name.startswith("Elite ") else name
        by_base.setdefault(base, {})[unit["age"]] = unit

    mismatch_count = 0

    for base_name, variants in sorted(by_base.items()):
        castle = variants.get("Castle", {})
        imperial = variants.get("Imperial", {})
        lines += [f"### {base_name}", ""]

        lines += [
            "| Stat | Regular | Elite |",
            "|------|---------|-------|",
        ]
        for label, col in UNIT_STAT_FIELDS:
            castle_val = castle.get(col, "—")
            imperial_val = imperial.get(col, "—")
            lines.append(f"| {label} | {castle_val} | {imperial_val} |")
        lines.append("")

        # Cross-reference note — full comparison is in the unit file
        lines.append(f"_Full stat comparison: see `reference/units/unique/{base_name.replace(' ', '_')}.md`_")
        lines.append("")

    # Unit Availability
    lines += ["## Standard Units Available", ""]
    standard_units = db.get("standard", [])
    if standard_units:
        # Deduplicate by unit_name (Elite Skirmisher may appear under two slugs)
        names = sorted({u["unit_name"] for u in standard_units})
        lines.append(", ".join(names))
    else:
        lines.append("⚠️ No standard units found in DB.")
    lines.append("")

    # Disabled Standard Units
    disabled = db.get("disabled", [])
    lines += ["## Disabled Standard Units", ""]
    if disabled:
        for d in disabled:
            lines.append(f"- {d['unit_name']} _(available to {d['civ_count']}/53 civs)_")
    else:
        lines.append("_None — this civ has access to all widely-available standard units._")
    lines.append("")

    # DB Summary
    lines += ["## DB Summary", ""]
    all_units = db.get("standard", []) + db.get("unique", [])
    lines.append(f"- Total units in DB: {len(all_units)}")
    lines.append(f"- Unique units: {len(db.get('unique', []))}")
    lines.append(f"- Standard units: {len(db.get('standard', []))}")
    lines.append(f"- Disabled standard units: {len(disabled)}")
    lines.append("")

    return "\n".join(lines), mismatch_count


def generate_single_civ(civ_name: str, techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate reference/civs/{civ_name}.md"""
    out_path = REF_DIR / "civs" / f"{civ_name}.md"
    if out_path.exists() and not args.force and not args.dry_run:
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

    content, mismatches = render_civ_file(civ_name, wiki, techtree_civ, db)

    if not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        stats["written"] += 1
        stats["mismatches"] += mismatches
        print(f"  Written: {out_path}")
    else:
        print(f"  [dry-run] Would write: {out_path}")


def generate_all_civs(techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate civ files for all civs in the DB."""
    civ_names = [row[0] for row in conn.execute(
        "SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name"
    ).fetchall()]
    print(f"\nGenerating {len(civ_names)} civ files...")
    for civ_name in civ_names:
        generate_single_civ(civ_name, techtree, conn, args, stats)


def render_unit_file(
    unit_name: str,
    unit_type: str,
    ext_stats: dict,
    db_rows: dict,
    civ_name: str = None,
    extras: dict = None,
    armor_class_map: dict = None,
) -> tuple:
    """
    Render a unit reference markdown file.
    ext_stats: from techtree_unit_stats() or parse_wiki_unit() — external source values
    db_rows: {age: db_dict} from query_db_unit()
    Returns (content_string, mismatch_count) tuple.
    """
    ages = list(db_rows.keys()) if db_rows else []
    col_a = ages[0] if ages else "Regular"
    col_b = ages[1] if len(ages) > 1 else "Elite"

    db_a = db_rows.get(col_a, {})
    db_b = db_rows.get(col_b, {})

    lines = [
        f"# {unit_name}",
        "",
        f"**Type:** {unit_type.capitalize()}  ",
        f"**Available to:** {'All civs' if not civ_name else civ_name}  ",
        "**Sources:** SiegeEngineers/aoe2techtree, Fandom wiki  ",
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

    # DB Comparison table (external vs our DB for first age)
    lines += [
        "## DB Comparison",
        "",
        f"| Field | External | Our DB ({col_a}) | Match |",
        "|-------|----------|-----------------|-------|",
    ]
    mismatch_count = 0

    # Map db column names → external stat keys (pre-computed reverse)
    db_to_ext = {
        "base_hp": "hp",
        "base_attack": "attack",
        "base_melee_armor": "melee_armor",
        "base_pierce_armor": "pierce_armor",
        "base_speed": "speed",
        "base_range": "range",
        "base_reload_time": "reload_time",
        "base_cost_food": "cost_food",
        "base_cost_wood": "cost_wood",
        "base_cost_gold": "cost_gold",
    }
    for label, col in stat_rows[:10]:  # skip pop_space (not in external sources)
        ext_key = db_to_ext.get(col, col)
        ext_val = ext_stats.get(ext_key)
        db_val = db_a.get(col)
        symbol = compare_val(ext_val, db_val)
        ext_display = ext_val if ext_val is not None else "⚠️"
        db_display = db_val if db_val is not None else "—"
        lines.append(f"| {label} | {ext_display} | {db_display} | {symbol} |")
        if symbol == MISMATCH:
            mismatch_count += 1
    lines.append("")

    if mismatch_count:
        lines.append(f"**⚠️ {mismatch_count} mismatch(es) found — investigate.**")
        lines.append("")

    # --- Attack Bonuses (from DB attacks_json) ---
    acmap = armor_class_map or {}
    attacks_raw = db_a.get("base_attacks_json") or "{}"
    try:
        attacks = json.loads(attacks_raw)
    except (json.JSONDecodeError, TypeError):
        attacks = {}
    bonus_entries = [
        (int(cid), val) for cid, val in attacks.items()
        if int(cid) not in (3, 4) and val != 0  # skip base melee/pierce class; skip zeros
    ]
    lines += ["## Attack Bonuses", ""]
    if bonus_entries:
        lines += ["| Bonus | Armor Class |", "|-------|-------------|"]
        for cid, val in sorted(bonus_entries, key=lambda x: -abs(x[1])):
            name = acmap.get(cid, f"Class {cid}")
            sign = "+" if val > 0 else ""
            lines.append(f"| {sign}{val} | {name} |")
    else:
        lines.append("No bonus damage entries.")
    lines.append("")

    # --- Armor Classes (what this unit belongs to → what counters it) ---
    armors_raw = db_a.get("base_armors_json") or "{}"
    try:
        armors = json.loads(armors_raw)
    except (json.JSONDecodeError, TypeError):
        armors = {}
    armor_entries = [
        (int(cid), val) for cid, val in armors.items()
        if int(cid) not in (3, 4)  # skip base melee/pierce
    ]
    lines += ["## Armor Classes (Vulnerability)", ""]
    lines.append("_Units with attack bonuses against these classes deal extra damage to this unit._")
    lines.append("")
    if armor_entries:
        lines += ["| Armor Class | Armor Value |", "|-------------|-------------|"]
        for cid, val in sorted(armor_entries, key=lambda x: x[0]):
            name = acmap.get(cid, f"Class {cid}")
            lines.append(f"| {name} | {val} |")
    else:
        lines.append("No non-base armor classes.")
    lines.append("")

    # --- Extras from wiki ---
    if extras:
        # Strengths & Weaknesses
        strong = extras.get("strong_vs", [])
        weak   = extras.get("weak_vs", [])
        if strong or weak:
            lines += ["## Strengths & Weaknesses", ""]
            if strong:
                lines.append(f"**Strong vs:** {', '.join(strong)}")
            if weak:
                lines.append(f"**Weak vs:** {', '.join(weak)}")
            lines.append("")

        # Technologies
        techs = extras.get("techs", {})
        if techs:
            lines += ["## Technologies", ""]
            lines += ["| Stat | Technology (Effect) |", "|------|---------------------|"]
            for stat, items in techs.items():
                for item in items:
                    lines.append(f"| {stat} | {item} |")
            lines.append("")

        # Civilization Bonuses
        civ_bonuses = extras.get("civ_bonuses", {})
        team_bonuses = extras.get("team_bonuses", {})
        if civ_bonuses or team_bonuses:
            lines += ["## Civilization Bonuses", ""]
            if civ_bonuses:
                lines += ["**Unique to civ:**", ""]
                lines += ["| Stat | Civ (Bonus) |", "|------|-------------|"]
                for stat, items in civ_bonuses.items():
                    for item in items:
                        lines.append(f"| {stat} | {item} |")
                lines.append("")
            if team_bonuses:
                lines += ["**Team bonuses:**", ""]
                lines += ["| Stat | Civ (Bonus) |", "|------|-------------|"]
                for stat, items in team_bonuses.items():
                    for item in items:
                        lines.append(f"| {stat} | {item} |")
                lines.append("")

    return "\n".join(lines), mismatch_count


def generate_single_unit(unit_name: str, techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate reference file for one unit by display name."""
    safe_name = unit_name.replace(" ", "_")

    # Find in DB — get type and one slug to use as prefix
    slug_rows = conn.execute(
        "SELECT DISTINCT unit_slug, unit_type, civ_name FROM ref_units WHERE unit_name = ? LIMIT 5",
        (unit_name,),
    ).fetchall()

    if not slug_rows:
        print(f"  ⚠️ Unit not found in DB: {unit_name}")
        return

    unit_type = slug_rows[0]["unit_type"]
    civ_name = slug_rows[0]["civ_name"] if unit_type == "unique" else None
    base_slug = slug_rows[0]["unit_slug"]

    subdir = "unique" if unit_type == "unique" else "generic"
    out_path = REF_DIR / "units" / subdir / f"{safe_name}.md"

    if out_path.exists() and not args.force and not args.dry_run:
        stats["skipped"] += 1
        print(f"  Skipped (exists): {out_path}")
        return

    # Fetch wiki wikitext — needed for extras (techs, civ bonuses, S&W) regardless of techtree
    print(f"  Fetching wiki unit: {unit_name}...", end=" ", flush=True)
    time.sleep(WIKI_DELAY)
    wikitext = fetch_wiki_wikitext(unit_name.replace(" ", "_"))
    if not wikitext:
        # Try with disambig suffix
        wikitext = fetch_wiki_wikitext(f"{unit_name.replace(' ', '_')}_(Age_of_Empires_II)")
    if wikitext:
        print("✓")
    else:
        print("⚠️ not found")

    # External stats: prefer techtree (more reliable for numbers), fall back to wiki
    tt_unit = find_techtree_unit(techtree, unit_name)
    if tt_unit:
        ext_stats = techtree_unit_stats(tt_unit)
    elif wikitext:
        ext_stats = parse_wiki_unit(wikitext)
    else:
        ext_stats = {}

    # Parse wiki extras (techs, civ bonuses, strengths/weaknesses)
    extras = parse_wiki_unit_extras(wikitext) if wikitext else {}

    # Build armor class map for rendering attack/armor sections
    armor_classes = query_armor_classes(conn)
    acmap = {ac["id"]: ac["name"] for ac in armor_classes}

    db_rows = query_db_unit(conn, base_slug)
    content, mismatches = render_unit_file(
        unit_name, unit_type, ext_stats, db_rows, civ_name,
        extras=extras, armor_class_map=acmap,
    )

    if not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        stats["written"] += 1
        stats["mismatches"] += mismatches
        suffix = f" ({mismatches} ❌)" if mismatches else ""
        print(f"  Written: {out_path}{suffix}")
    else:
        print(f"  [dry-run] Would write: {out_path}")


def generate_all_units(techtree: dict, conn: sqlite3.Connection, args, stats: dict):
    """Generate unit files for all distinct unit names in the DB."""
    units = conn.execute(
        """SELECT DISTINCT unit_name, unit_type
           FROM ref_units
           WHERE unit_name NOT LIKE 'Elite %'
           ORDER BY unit_type, unit_name"""
    ).fetchall()
    print(f"\nGenerating {len(units)} unit files...")
    for row in units:
        generate_single_unit(row["unit_name"], techtree, conn, args, stats)


# --- STUB FUNCTIONS (to be implemented in later tasks) ---

TECHTREE_STRINGS_URL = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/locales/en/strings.json"


def fetch_techtree() -> dict:
    """
    Fetch SiegeEngineers data.json, normalize and return a dict with:
      - 'units': {str_id: unit_dict} with lowercase stat keys + 'name' (display name where available)
      - 'civs': list of {name: str, ...} dicts
    """
    raw = json.loads(http_get(TECHTREE_URL))

    # Fetch English strings for display names (best-effort; may be incomplete)
    try:
        strings: dict = json.loads(http_get(TECHTREE_STRINGS_URL))
    except Exception:
        strings = {}

    # Normalize civs: raw is {civ_name: {...}} → list of dicts with 'name' key
    raw_civs = raw.get("civs", {})
    if isinstance(raw_civs, dict):
        civs_list = []
        for civ_name, civ_data in raw_civs.items():
            entry = dict(civ_data) if isinstance(civ_data, dict) else {}
            entry.setdefault("name", civ_name)
            civs_list.append(entry)
    else:
        civs_list = list(raw_civs)

    # Normalize units: raw is data.Unit[id] with PascalCase keys → lowercase keys + 'name'
    raw_units = raw.get("data", {}).get("Unit", {})
    units_dict: dict = {}
    for uid, u in raw_units.items():
        if not isinstance(u, dict):
            continue
        ma = u.get("MeleeArmor", 0) or 0
        pa = u.get("PierceArmor", 0) or 0
        cost_raw = u.get("Cost", {}) or {}
        lang_id = str(u.get("LanguageNameId", ""))
        # Try to get display name from strings; fall back to internal_name
        display_name = strings.get(lang_id, "") or ""
        # Clean up HTML line breaks in names
        display_name = re.sub(r"<br\s*/?>", " ", display_name).strip()
        if not display_name:
            display_name = u.get("internal_name", f"Unit_{uid}")
        units_dict[str(uid)] = {
            "id": u.get("ID", int(uid)),
            "name": display_name,
            "internal_name": u.get("internal_name", ""),
            "hp": u.get("HP"),
            "attack": u.get("Attack"),
            "armor": f"{ma}/{pa}",
            "melee_armor": ma,
            "pierce_armor": pa,
            "speed": u.get("Speed"),
            "range": u.get("Range", 0),
            "reloadTime": u.get("ReloadTime"),
            "attackSpeed": u.get("ReloadTime"),
            "cost": {
                "Food": cost_raw.get("Food", 0),
                "Wood": cost_raw.get("Wood", 0),
                "Gold": cost_raw.get("Gold", 0),
            },
            "trainTime": u.get("TrainTime"),
            "populationUse": u.get("PopulationUse", 1),
        }

    return {"units": units_dict, "civs": civs_list}

def generate_armor_classes(conn: sqlite3.Connection, args, stats: dict):
    """Write reference/armor-classes.md."""
    out_path = REF_DIR / "armor-classes.md"
    if out_path.exists() and not args.force and not args.dry_run:
        stats["skipped"] += 1
        return
    classes = query_armor_classes(conn)
    content = render_armor_classes(classes)
    if not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        stats["written"] += 1
        print(f"  Written: {out_path}")
    else:
        print(f"  [dry-run] Would write: {out_path}")
def write_readme(args, stats: dict):
    """Write reference/README.md index file."""
    if args.dry_run:
        return
    content = """# AoE2 Reference Corpus

Generated: {today}

This directory contains markdown reference files for all AoE2 civilizations, units, and armor classes.
Each file includes a **DB Comparison** table showing whether our local database matches the authoritative
external sources (Fandom wiki + SiegeEngineers/aoe2techtree).

## Structure

```
reference/
  armor-classes.md       — All armor classes
  civs/                  — One file per civilization (53 total)
  units/generic/         — Generic unit lines (Arbalester, Paladin, etc.)
  units/unique/          — Unique units per civ
```

## How to Regenerate

From the project root (activate venv first: `source venv/bin/activate`):

```bash
# Regenerate all files (skip existing)
python3 scripts/build_reference_docs.py

# Force regenerate all files
python3 scripts/build_reference_docs.py --force

# Regenerate a single civ
python3 scripts/build_reference_docs.py --civ Muisca

# Regenerate a single unit
python3 scripts/build_reference_docs.py --unit "Temple Guard"

# Dry run — report what would be written
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
""".format(today=TODAY)
    readme_path = REF_DIR / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(content, encoding="utf-8")
    print(f"  Written: {readme_path}")


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
