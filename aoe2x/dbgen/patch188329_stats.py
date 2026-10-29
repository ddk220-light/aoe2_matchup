"""Selected 188329 balance changes on the existing 185872 data (not a DAT rebuild).

The owner requested only Elephant Archer HP/cost and non-elite Bolas speed.
The raw-unit overlay runs before upgrade calculation on future extractions.
The migration validates the existing chains and updates both reference DBs,
current V3 profiles/hashes and the flat unit table in one attached transaction.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3

SOURCE = "https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-188329/"
ELEPHANTS = {873: (230, 220), 875: (280, 270)}
BOLAS = 2569  # 2571 is Elite and keeps 1.5 tiles/sec.


def patch_base_unit(unit):
    """Copy the selected raw attributes before applying civilization techs."""
    unit_id = unit.get("id")
    if unit_id not in {*ELEPHANTS, BOLAS}:
        return unit
    result = dict(unit)
    if unit_id in ELEPHANTS:
        old_hp, new_hp = ELEPHANTS[unit_id]
        if unit.get("hit_points") not in (old_hp, new_hp):
            raise ValueError("188329 overlay: unexpected Elephant Archer base HP")
        if unit.get("cost", {}).get("food") not in (60, 70):
            raise ValueError("188329 overlay: unexpected Elephant Archer food cost")
        result["hit_points"] = new_hp
        result["cost"] = {**unit["cost"], "food": 70}
    else:
        if unit.get("speed") not in (1.5, 1.45):
            raise ValueError("188329 overlay: unexpected non-elite Bolas speed")
        result["speed"] = 1.45
    return result


def provenance(master):
    if master not in {*ELEPHANTS, BOLAS}:
        return {}
    return {"balance_overrides": [{"build": 188329, "source": SOURCE,
        "scope": "Elephant Archer base HP/food cost" if master in ELEPHANTS
                 else "non-elite Bolas Rider base speed"}]}


def migrate(golden_dir):
    from .v3_mechanics import canonical_json, mechanics_hash, validate_runtime_profile
    from aoe2x.js_simulation.battle_setup import effective_cost
    golden_dir = Path(golden_dir)
    paths = [golden_dir / name for name in (
        "aoe2_reference_simulation.db", "aoe2_reference.db", "aoe2_units.db")]
    if not all(path.is_file() for path in paths):
        raise ValueError("all three existing unit databases are required")
    changes = []
    with sqlite3.connect(paths[0]) as c:
        c.row_factory = sqlite3.Row
        c.execute("ATTACH DATABASE ? AS display", (str(paths[1]),))
        c.execute("ATTACH DATABASE ? AS flat", (str(paths[2]),))
        c.execute("BEGIN IMMEDIATE")
        for schema in ("main", "display"):
            rows = c.execute(f"SELECT * FROM {schema}.ref_units WHERE unit_master IN (873,875,2569)").fetchall()
            for row in rows:
                r = dict(row)
                # There are no non-elite Bolas rows in the current Imperial
                # roster; handle future rows via base extraction, not guessing
                # their upgrade chain in this narrow migration.
                if r["unit_master"] == BOLAS:
                    raise ValueError("non-elite Bolas reference row needs a fresh upgrade calculation")
                old_hp, new_hp = ELEPHANTS[r["unit_master"]]
                if r["base_hp"] == new_hp and r["base_cost_food"] == 70:
                    continue
                if (r["base_hp"], r["base_cost_food"]) != (old_hp, 60):
                    raise ValueError("unexpected Elephant Archer reference baseline")
                chain = c.execute(f"SELECT * FROM {schema}.ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order", (r["id"],)).fetchall()
                if not chain or any(x["hp"] not in (old_hp, old_hp + 20)
                                    or x["cost_food"] not in (60, 45) for x in chain):
                    raise ValueError("unrecognized HP/cost modifier; regenerate from raw inputs")
                # Existing chains contain only additive Bloodlines and the
                # Gurjara 25% food discount. Preserve both at every step.
                for step in chain:
                    c.execute(f"UPDATE {schema}.ref_stat_chain SET hp=?,cost_food=? WHERE id=?",
                              (step["hp"] - 10, step["cost_food"] * 70 / 60, step["id"]))
                hp, food = round(chain[-1]["hp"] - 10), round(chain[-1]["cost_food"] * 70 / 60)
                c.execute(f"UPDATE {schema}.ref_units SET base_hp=?,final_hp=?,base_cost_food=70,final_cost_food=? WHERE id=?",
                          (new_hp, hp, food, r["id"]))
                r.update(base_hp=new_hp, final_hp=hp, base_cost_food=70, final_cost_food=food)
                for m in c.execute(f"SELECT * FROM {schema}.ref_unit_mechanics WHERE ref_unit_id=?", (r["id"],)).fetchall():
                    p = json.loads(m["mechanics_json"])
                    if mechanics_hash(p) != m["mechanics_hash"]:
                        raise ValueError("existing mechanics hash mismatch")
                    p.update(hp=hp, cost=effective_cost(r)[0], **provenance(r["unit_master"]))
                    validate_runtime_profile(p)
                    c.execute(f"UPDATE {schema}.ref_unit_mechanics SET mechanics_json=?,mechanics_hash=? WHERE ref_unit_id=? AND mode=?",
                              (canonical_json(p), mechanics_hash(p), r["id"], m["mode"]))
                c.execute(f"INSERT INTO {schema}.ref_special_effects (ref_unit_id,property_name,property_value,source,description) VALUES (?,?,?,?,?)",
                          (r["id"], "patch188329:unit_stats", json.dumps(provenance(r["unit_master"])), SOURCE,
                           "Selected balance overlay; original DAT source hash remains 185872. Costs use existing generator rounding."))
                if schema == "display":
                    c.execute("UPDATE flat.unit_stats SET hp=?,cost_food=? WHERE civ_id=(SELECT id FROM flat.civilizations WHERE name=?) "
                              "AND unit_id IN (SELECT id FROM flat.units WHERE slug=?) AND has_unit=1",
                              (hp, food, r["civ_name"], r["unit_slug"]))
                changes.append({"database": schema, "civilization": r["civ_name"], "hp": hp, "food": food})
        return changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("golden_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(migrate(args.golden_dir), indent=2))
