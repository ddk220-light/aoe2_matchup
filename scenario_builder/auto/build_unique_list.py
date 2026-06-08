"""build_unique_list.py — enumerate every civ's unique unit(s) into a matchup list.

A "unique unit" = a castle-trained unique OR a civ-specific special land unit
(Jian Swordsman for Wu, Bolas Rider for Mapuche, Warrior Priest for Armenians, …).
Source of truth: `webapp/aoe2_reference.db` `ref_units` — unique units carry a civ
suffix on their slug (`elite_jaguar_warrior_aztecs`). We take the Imperial-age
(fully-upgraded) form of each, validate it is actually matchup-able (resolves to
both a card *and* a scenario unit id), drop naval units (they can't fight on land),
and write the ordered list to `unique_units.json` for the batch runner to consume.

  python -m auto.build_unique_list          # writes auto/unique_units.json + prints a table
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
REPO = SB.parent
sys.path.insert(0, str(SB))
sys.path.insert(0, str(SB / "overlay"))

from auto.orchestrate_matchup import resolve_side   # noqa: E402
from build_run import unit_const                     # noqa: E402

REF_DB = REPO / "webapp" / "aoe2_reference.db"
OUT_JSON = HERE / "unique_units.json"

# names that mark a NAVAL unique (can't fight in the land arena) — excluded
NAVAL = ("dromon", "xebec", "lou chuan", "thirisadai", "catapult galleon",
         "turtle ship", "caravel", "longboat")
# the Bengali Ratha is ONE unit with two modes; keep the melee form, drop the ranged
# duplicate so the list is one-entry-per-unit
DROP_DUP = ("(ranged)",)
# siege by class OR by name — the Khitan Mounted Trebuchet is class "Cavalry" in the
# DB but is functionally a siege weapon (min attack range, won't fight point-blank).
SIEGE_CLASSES = ("siege", "ballista")
SIEGE_NAMES = ("trebuchet", "ballista", "organ gun", "hussite")


def enumerate_uniques():
    db = sqlite3.connect(str(REF_DB))
    db.row_factory = sqlite3.Row
    civs = [r[0] for r in db.execute("SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name")]
    units, skipped = [], []
    for civ in civs:
        suffix = "_" + civ.lower()
        rows = db.execute(
            "SELECT unit_slug, unit_name, unit_class_name FROM ref_units "
            "WHERE civ_name=? AND age='Imperial' AND unit_slug LIKE '%'||? ORDER BY unit_slug",
            (civ, suffix)).fetchall()
        for r in rows:
            slug, name, cls = r["unit_slug"], r["unit_name"], (r["unit_class_name"] or "")
            nl = name.lower()
            if any(k in nl for k in NAVAL):
                skipped.append((civ, name, "naval")); continue
            if any(d in slug for d in DROP_DUP):
                skipped.append((civ, name, "dup-mode")); continue
            try:                                   # must resolve to a card + scenario unit
                _, key, label = resolve_side(civ, slug)
                unit_const(key)
            except Exception as e:
                skipped.append((civ, name, f"unresolved ({type(e).__name__})")); continue
            is_siege = (any(s in cls.lower() for s in SIEGE_CLASSES)
                        or any(k in label.lower() for k in SIEGE_NAMES))
            units.append({"civ": civ, "slug": slug, "name": label,
                          "unit_class": cls, "is_siege": is_siege})
    return units, skipped


def main():
    units, skipped = enumerate_uniques()
    OUT_JSON.write_text(json.dumps(units, indent=2))
    # readable table
    print(f"{'#':>3}  {'CIV':<12} {'UNIT':<28} {'CLASS':<16} {'SLUG'}")
    print("-" * 96)
    for i, u in enumerate(units, 1):
        flag = " [siege]" if u["is_siege"] else ""
        print(f"{i:>3}  {u['civ']:<12} {u['name']:<28} {u['unit_class']:<16} {u['slug']}{flag}")
    print(f"\n{len(units)} unique units written to {OUT_JSON.relative_to(REPO)}")
    if skipped:
        print(f"\nExcluded ({len(skipped)}):")
        for civ, name, why in skipped:
            print(f"  - {civ} {name}  ({why})")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
