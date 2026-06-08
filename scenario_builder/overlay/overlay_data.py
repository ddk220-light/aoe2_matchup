"""
overlay_data.py — pull a unit's display data (stats, cost, upgrades, civ bonuses,
unique techs) from the project's reference DB, shaped for a video overlay card.

Mirrors what the aoe2matchup webapp shows for a unit in a unit-vs-unit sim:
final fully-upgraded stats + cost + the techs/bonuses that were applied.

Source of truth: webapp/aoe2_reference.db
    ref_units          - base + final stats, cost, attacks/armors json
    ref_techs_applied  - every tech/bonus applied (tech_type: standard / civ_bonus
                         / unique_tech / work_rate), with building/age/cost
    armor_classes      - id -> name (to label attack bonuses)
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

# repo-root-relative paths
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]  # scenario_builder/overlay/ -> repo root
REF_DB = _REPO / "webapp" / "aoe2_reference.db"
ICON_DIR = _REPO / "webapp" / "static" / "img" / "units"

# class ids that represent the *base* attack, not a bonus
_BASE_ATTACK_CLASSES = {3, 4}  # Base Pierce, Base Melee


def _icon_path(unit_name: str) -> str:
    """Resolve a unit icon. The webapp maps names to files by spaces->underscores."""
    candidate = ICON_DIR / f"{unit_name.replace(' ', '_')}.png"
    if candidate.exists():
        return str(candidate)
    return ""  # caller can fall back to a placeholder


def _armor_class_map(conn) -> dict[int, str]:
    return {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM armor_classes")}


def get_unit_card(civ: str, slug: str, age: str = "Imperial",
                  db_path: str | os.PathLike = REF_DB) -> dict:
    """Return a dict describing a fully-upgraded unit for the overlay card."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
            (civ, slug, age),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? ORDER BY age DESC LIMIT 1",
                (civ, slug),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unit not found: {civ}/{slug}")

        cls = _armor_class_map(conn)
        keys = row.keys()

        def g(col, default=0):
            return row[col] if col in keys else default

        # attack bonuses (vs armor class), excluding base attack classes
        bonuses = []
        try:
            atk = json.loads(g("final_attacks_json") or "{}")
        except (TypeError, ValueError):
            atk = {}
        for cid, amount in atk.items():
            cid = int(cid)
            if cid in _BASE_ATTACK_CLASSES or not amount:
                continue
            name = cls.get(cid, f"class {cid}")
            if name in ("Unused",):
                continue
            bonuses.append({"vs": name, "amount": int(amount), "vs_id": cid})

        # the armor classes this unit BELONGS to — an opponent's "+X vs <class>" only
        # applies if that class id is in here (the value can be 0; membership is what
        # matters). Used to filter bonuses down to the ones relevant to a matchup.
        try:
            arm = json.loads(g("final_armors_json") or "{}")
        except (TypeError, ValueError):
            arm = {}
        armor_class_ids = sorted(int(k) for k in arm)

        # techs applied, grouped by type
        techs = conn.execute(
            """SELECT tech_name, tech_type, building, age_available,
                      cost_food, cost_wood, cost_gold
               FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
            (row["id"],),
        ).fetchall()

        upgrades, civ_bonuses, unique_techs = [], [], []
        for t in techs:
            ttype = (t["tech_type"] or "").lower()
            entry = {
                "name": t["tech_name"],
                "building": t["building"],
                "age": t["age_available"],
                "cost": {"food": t["cost_food"] or 0, "wood": t["cost_wood"] or 0,
                         "gold": t["cost_gold"] or 0},
            }
            if "unique" in ttype:
                unique_techs.append(entry)
            elif "civ" in ttype or "bonus" in ttype:
                civ_bonuses.append(entry)
            elif ttype in ("standard",):
                upgrades.append(entry)
            # work_rate etc. are folded into civ bonuses if they carry a name
            elif ttype == "work_rate" and t["tech_name"]:
                civ_bonuses.append(entry)

        is_ranged = bool(g("is_ranged"))
        f, w, gd = g("final_cost_food"), g("final_cost_wood"), g("final_cost_gold")

        # ordered stat list (only show range/accuracy for ranged units)
        stats = [
            ("HP", _num(g("final_hp"))),
            ("Attack", _num(g("final_attack"))),
            ("Melee Armor", _num(g("final_melee_armor"))),
            ("Pierce Armor", _num(g("final_pierce_armor"))),
            ("Speed", _num(g("final_speed"))),
        ]
        if is_ranged or g("final_range"):
            stats.insert(4, ("Range", _num(g("final_range"))))
            if g("final_accuracy"):
                stats.append(("Accuracy", f"{_num(g('final_accuracy'))}%"))
        if g("final_reload_time"):
            stats.append(("Reload", f"{_num(g('final_reload_time'))}s"))

        return {
            "name": row["unit_name"],
            "civ": civ,
            "age": row["age"],
            "unit_type": g("unit_class_name") or g("unit_type") or "",
            "is_ranged": is_ranged,
            "icon": _icon_path(row["unit_name"]),
            "stats": stats,
            "attack_bonuses": bonuses,
            "armor_class_ids": armor_class_ids,
            "cost": {"food": _num(f), "wood": _num(w), "gold": _num(gd),
                     "total": _num((f or 0) + (w or 0) + (gd or 0))},
            "upgrades": [u["name"] for u in upgrades],
            "civ_bonuses": [c["name"] for c in civ_bonuses],
            "unique_techs": unique_techs,
            "bonuses_summary": g("applied_bonuses_summary") or "",
        }
    finally:
        conn.close()


def _num(v):
    """Render numbers cleanly: 40.0 -> 40, 0.96 -> 0.96."""
    if v is None:
        return 0
    f = float(v)
    return int(f) if f == int(f) else round(f, 2)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for civ, slug in (("Wu", "elite_fire_archer_wu"), ("Wu", "jian_swordsman_wu")):
        c = get_unit_card(civ, slug)
        print(f"\n=== {c['name']} ({c['civ']}) — {c['unit_type']} ===")
        print("  stats:", c["stats"])
        print("  bonuses:", c["attack_bonuses"])
        print("  cost:", c["cost"])
        print("  upgrades:", c["upgrades"])
        print("  unique_techs:", [u["name"] for u in c["unique_techs"]])
        print("  icon:", c["icon"])
