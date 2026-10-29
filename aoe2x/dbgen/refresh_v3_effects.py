"""Refresh reference-backed V3 abilities without re-extracting DAT geometry.

This deliberately does not regenerate stats, animations, weapon forms or raw
projectiles. Use generate_v3_mechanics for a complete DAT-backed rebuild.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from aoe2x.js_simulation.tools.export_unit_mechanics import _runtime_effects
from .v3_mechanics import canonical_json, mechanics_hash, validate_runtime_profile
from .v3_runtime_config import EXPORT_OPTIONS_BY_CIV_SLUG, ADDITIONAL_MODES_BY_CIV_SLUG


def reference_effects_for_profile(reference, profile):
    effects = dict(_runtime_effects(reference, reference["unit_slug"]) or {})
    key = reference["civ_name"], reference["unit_slug"]
    concrete = EXPORT_OPTIONS_BY_CIV_SLUG.get(key, {}).get("concrete_form", False)
    concrete |= any(spec["mode"] == profile["mode"] and spec["options"].get("concrete_form")
                    for spec in ADDITIONAL_MODES_BY_CIV_SLUG.get(key, ()))
    if concrete:
        # These fields were derived from the concrete body's DAT rather than
        # the public shell. Preserve their exact presence as well as values.
        previous = profile.get("effects") or {}
        for name in ("base_accuracy", "extra_projectiles", "trample_percent",
                     "trample_radius", "trample_flat_damage", "pass_through_percent",
                     "pass_through_count"):
            effects.pop(name, None)
            if name in previous:
                effects[name] = previous[name]
    return effects or None


def refresh(reference_db: Path, *, write=False):
    with sqlite3.connect(reference_db) as connection:
        connection.row_factory = sqlite3.Row
        pending = []
        regen_updates = {}
        for row in connection.execute("SELECT * FROM ref_unit_mechanics ORDER BY ref_unit_id,mode"):
            profile = json.loads(row["mechanics_json"])
            if mechanics_hash(profile) != row["mechanics_hash"]:
                raise ValueError(f"existing profile hash mismatch: {row['ref_unit_id']}:{row['mode']}")
            reference = dict(connection.execute("SELECT * FROM ref_units WHERE id=?",
                                                (row["ref_unit_id"],)).fetchone())
            reference["applied_tech_ids"] = [r[0] for r in connection.execute(
                "SELECT tech_id FROM ref_techs_applied WHERE ref_unit_id=?",
                (row["ref_unit_id"],))]
            profile["effects"] = reference_effects_for_profile(reference, profile)
            if reference["civ_name"] == "Khitans":
                corrected = (profile["effects"] or {}).get("hp_regen_in_combat", 0)
                if reference.get("hp_regen_in_combat") != corrected:
                    regen_updates[row["ref_unit_id"]] = corrected
            validate_runtime_profile(profile)
            new_hash = mechanics_hash(profile)
            if new_hash != row["mechanics_hash"]:
                pending.append((canonical_json(profile), new_hash, row["ref_unit_id"], row["mode"]))
        if write:
            connection.executemany("UPDATE ref_units SET hp_regen_in_combat=? WHERE id=?",
                                   [(value, key) for key, value in regen_updates.items()])
            connection.executemany("UPDATE ref_unit_mechanics SET mechanics_json=?,mechanics_hash=? "
                                   "WHERE ref_unit_id=? AND mode=?", pending)
        return {"changed_profiles": len(pending), "written": write, "corrected_regen_rows": len(regen_updates)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_db", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.reference_db.is_file():
        parser.error("reference database does not exist")
    print(json.dumps(refresh(args.reference_db, write=args.write)))


if __name__ == "__main__":
    main()
