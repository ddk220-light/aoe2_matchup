"""Role: serving + derive — per-civ top unit per line at Imperial Age
(load_top_units serves civ_top_units.json; compute_top_units rebuilds it offline).

The app only deals with fully-upgraded Imperial-age units. For each civ and each
unit line, this resolves the ACTUAL highest-tier unit that civ fields at Imperial
age -- e.g. the Korean knight line is "Cavalier" (Koreans lack the Paladin
upgrade), Persians get "Savar", Franks get "Paladin".

Source of truth: UNIT_LINES (line -> standard imperial_slug + per-civ unique
units) crossed with ref_units' Imperial rows (whose unit_name already reflects
the highest upgrade the civ reaches by Imperial age). A line is included for a
civ only if that civ actually has an Imperial row for it (post phantom-fix
availability).

Usage:
    from aoe2x.advisor.top_units import compute_top_units, load_top_units
    data = load_top_units()           # reads committed civ_top_units.json
    data["Koreans"]["knight"]["units"][0]["unit"]   # -> "Cavalier"

Regenerate the JSON:
    python -m aoe2x.advisor.top_units
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

from aoe2x.sim.unit_lines import UNIT_LINES
from aoe2x.paths import GOLDEN_DIR as _DATA_DIR

REF_DB = os.path.join(str(_DATA_DIR), "aoe2_reference.db")
OUT_JSON = os.path.join(str(_DATA_DIR), "civ_top_units.json")

# Lines that are real unit lines (have an imperial_slug). The "*_effectiveness"
# aggregate pseudo-lines (archery/infantry/stable/siege/naval) have no slug.
_REAL_LINES = {k: v for k, v in UNIT_LINES.items() if v.get("imperial_slug")}


def _imperial_unique_slugs(line: dict, civ: str) -> list[str]:
    """Imperial unique-unit slug(s) this civ fields in `line`, or []."""
    uu = line.get("unique_units", {}).get(civ)
    if uu is None:
        return []
    # uu is either a (castle, imperial) tuple or a list of such tuples.
    pairs = uu if isinstance(uu, list) else [uu]
    return [imp for (_castle, imp) in pairs if imp]


def _imperial_unique_pairs(line: dict, civ: str) -> list[tuple]:
    """(castle_slug, imperial_slug) unique-unit pairs this civ fields in `line`."""
    uu = line.get("unique_units", {}).get(civ)
    if uu is None:
        return []
    return uu if isinstance(uu, list) else [uu]


def compute_top_units(ref_db: str = REF_DB) -> dict:
    """Return {civ: {line_key: {line_name, building, units: [...]}}}.

    Each `units` entry is {slug, unit, is_unique}. The unit shown is the highest
    tier the civ reaches by Imperial age: the Imperial-slug row if the civ has
    the upgrade, else the Castle-slug row (units a civ keeps un-upgraded into
    Imperial, e.g. Cumans Camel Rider, Dravidians Battle Elephant). Only lines
    the civ actually fields are included.
    """
    conn = sqlite3.connect(ref_db)
    conn.row_factory = sqlite3.Row
    rows = {  # (civ, slug, age) -> unit_name
        (r["civ_name"], r["unit_slug"], r["age"]): r["unit_name"]
        for r in conn.execute("SELECT civ_name, unit_slug, unit_name, age FROM ref_units")
    }
    civs = sorted({civ for (civ, _s, _a) in rows})
    conn.close()

    def resolve(civ, castle_slug, imperial_slug):
        """Highest tier the civ fields: Imperial-slug row, else Castle-slug row."""
        if imperial_slug and (civ, imperial_slug, "Imperial") in rows:
            return imperial_slug, rows[(civ, imperial_slug, "Imperial")]
        if castle_slug and (civ, castle_slug, "Castle") in rows:
            return castle_slug, rows[(civ, castle_slug, "Castle")]
        return None, None

    out: dict = {}
    for civ in civs:
        civ_lines: dict = {}
        for line_key, line in _REAL_LINES.items():
            entries = []
            # Standard line unit (e.g. Cavalier/Paladin/Savar for knight,
            # Camel Rider for upgrade-less camel civs).
            slug, unit = resolve(civ, line.get("castle_slug"), line.get("imperial_slug"))
            if unit:
                entries.append({"slug": slug, "unit": unit, "is_unique": False})
            # Unique unit(s) for this line, if the civ has one.
            for castle_u, imp_u in _imperial_unique_pairs(line, civ):
                uslug, uunit = resolve(civ, castle_u, imp_u)
                if uunit:
                    entries.append({"slug": uslug, "unit": uunit, "is_unique": True})
            if entries:
                civ_lines[line_key] = {
                    "line_name": line.get("name", line_key),
                    "building": line.get("building"),
                    "units": entries,
                }
        out[civ] = civ_lines
    return out


def load_top_units(path: str = OUT_JSON) -> dict | None:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def main() -> int:
    data = compute_top_units()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    n_lines = sum(len(v) for v in data.values())
    print(f"Wrote {OUT_JSON}: {len(data)} civs, {n_lines} civ-line entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
