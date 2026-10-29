"""Audit every committed V3 profile against its reference row and upgrade chain.

This is a consistency/coverage audit, NOT an independent DAT verification or
a simulation-versus-live calibration. Raw-source absence is always reported.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from .ability_registry import ABILITIES
from .refresh_v3_effects import reference_effects_for_profile
from .v3_mechanics import mechanics_hash, validate_runtime_profile
from aoe2x.js_simulation.tools.export_unit_mechanics import REFERENCE_EFFECT_COLUMNS
from aoe2x.js_simulation.battle_setup import effective_cost


# A consumer inventory, not a claim that identifier presence proves semantics.
# Unit behavior regressions exercise these consumers separately.
ABILITY_CONSUMERS = {
    "extra_projectiles": "ranged/charge weapon blocks; world.releaseRangedVolley",
    "first_attack_burst": "effects.first_attack_extra_projectiles; world.releaseRangedVolley",
    "charge_projectile_volley": "charge; attacks.chargeSpec; world.releaseChargeVolley",
    "extra_proj_scatter": "ranged.scatter_volley; world.releaseRangedVolley",
    "siege_splash": "blast and ranged secondary projectiles; world.processChargeProjectiles",
    "splash_on_hit": "ranged impact_splash fields; world.processChargeProjectiles",
    "trample": "blast; attacks.trampleSpec; world.commitReadyAttacks",
    "pass_through": "ranged/charge pass_through fields; world.processChargeProjectiles",
    "melee_charge": "melee_charge/effects; world.meleeAttackAmount",
    "ranged_charge_mods": "charge; attacks.chargeProjectileDamage",
    "charge_slow": "effects; world.applyCommittedDamage",
    "bleed": "effects; world.applyCommittedDamage/advanceSpecialEffects",
    "attack_per_kill": "effects; world.applyCommittedDamage; attacks.calculateDamage",
    "hp_per_kill": "effects; world.applyCommittedDamage",
    "resources_per_kill": "effects; unit specialState.resourcesGained (not ranking credit)",
    "ignore_armor": "effects; attacks.calculateDamage",
    "armor_strip": "effects; world.applyCommittedDamage; attacks.calculateDamage",
    "bonus_damage_reduction": "effects; attacks.calculateDamage",
    "damage_reflect": "effects; world.applyCommittedDamage",
    "dodge_shield": "effects; unit-defenses.advanceDefenseCharge/consumeDamageBlock",
    "block_first_melee": "effects plus melee_block_recharge_seconds; unit-defenses.consumeDamageBlock",
    "attack_aura": "effects plus group/step/radius; world.refreshNearbyAuras",
    "hp_aura": "effects; world.refreshNearbyAuras",
    "ally_death_heal": "effects plus group/radius; world.applyCommittedDamage/advanceSpecialEffects",
    "dismount_on_death": "dismount_form; world.applyPendingDismounts and replacement-aware outcome",
    "hp_transform": "effects.transform_*; world.advanceSpecialEffects; attacks.calculateDamage",
    "attack_speed_ramp": "effects; world.reloadTicksForUnit/applyCommittedDamage",
    "execute": "effects; attacks.calculateDamage",
    "miss_damage": "effects; world.processChargeProjectiles",
    "pop_space": "population_space; website battle sizing",
    "hp_regen": "effects; world.advanceSpecialEffects",
    "hp_regen_in_combat": "effects; world.advanceAttackActivity (owner-approved melee attack/reload ticks)",
    "projectile_speed": "ranged/charge projectile_speed_tiles_per_second",
}

NESTED_REFERENCE_FIELDS = frozenset({
    "is_siege_projectile", "splash_radius", "projectile_speed", "pop_space",
    "dismount_unit_id", "dismount_hp", "dismount_attack", "dismount_melee_armor",
    "dismount_pierce_armor", "dismount_attack_speed", "dismount_attack_delay",
    "dismount_movement_speed", "dismount_attacks_json", "dismount_armors_json",
})

# Upgrade-selection classes are occasionally broader than the concrete DAT
# body's class. These exceptions are explicit in config_units.py, not inferred
# from combat results. Any new divergence needs review.
CLASS_ALIASES = {
    ("Bohemians", "elite_hussite_wagon_bohemians", 13, 55),
    ("Khmer", "elite_ballista_elephant_khmer", 55, 12),
    ("Teutons", "hussar", 12, 47),
}

UNIT_FOLLOWUPS = {
    "elite_keshik_tatars": ["Animation-based fighting income implemented from published task analysis; exact live gold timing remains uncalibrated."],
    "elite_varangian_guard": ["Task151 fighting income implemented for all five civs; exact live gold timing remains uncalibrated."],
}

# Deliberate scope choices, not missing implementations in this stage.
UNIT_SCOPE_NOTES = {
    "elite_hussite_wagon_bohemians": "Owner scope 2026-10-29: projectile shielding skipped.",
    "elite_fire_archer_wu": "Owner scope 2026-10-29: anti-unit weapon only; building/ship mode deferred.",
    "warrior_priest_armenians": "Owner scope 2026-10-29: healing/relic commands excluded; no conversion ability.",
    "elite_iron_pagoda_jurchens": "Owner scope 2026-10-29: block ordinary melee component only; specials/explosions bypass it.",
}



def equal(left, right, tolerance=1e-6):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, abs_tol=tolerance, rel_tol=1e-8)
    return left == right


def audit(reference_db: Path):
    connection = sqlite3.connect(f"file:{reference_db.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    errors, records = [], []
    abilities = Counter()
    source_builds = set()
    stat_pairs = {
        "hp": "final_hp", "attack_classes": "final_attacks_json",
        "armor_classes": "final_armors_json", "attack_range_tiles": "final_range",
        "line_of_sight_tiles": "final_los", "population_space": "pop_space",
    }
    for reference_row in connection.execute("SELECT * FROM ref_units ORDER BY civ_name,unit_slug,age"):
        reference = dict(reference_row)
        label = f"{reference['civ_name']}/{reference['unit_slug']}/{reference['age']}"
        techs = [dict(r) for r in connection.execute(
            "SELECT tech_id,tech_name,tech_type FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id",
            (reference["id"],))]
        reference["applied_tech_ids"] = [r["tech_id"] for r in techs]
        chain = connection.execute("SELECT * FROM ref_stat_chain WHERE ref_unit_id=? "
                                   "ORDER BY step_order DESC LIMIT 1", (reference["id"],)).fetchone()
        profiles = connection.execute("SELECT * FROM ref_unit_mechanics WHERE ref_unit_id=? ORDER BY mode",
                                      (reference["id"],)).fetchall()
        if sum(r["is_default"] for r in profiles) != 1:
            errors.append(f"{label}: expected exactly one default runtime profile")
        active = []
        for name, ability in ABILITIES.items():
            if any(reference.get(p.name) not in (None, "", "{}")
                   and reference.get(p.name) != p.default for p in ability.params if p.name in reference):
                active.append(name)
                abilities[name] += 1
                if name not in ABILITY_CONSUMERS:
                    errors.append(f"{label}: unclassified ability {name}")
                for param in ability.params:
                    if param.name in reference and reference[param.name] not in (None, "", "{}") \
                            and reference[param.name] != param.default \
                            and param.name not in REFERENCE_EFFECT_COLUMNS \
                            and param.name not in NESTED_REFERENCE_FIELDS:
                        errors.append(f"{label}: active ability field has no runtime mapping: {param.name}")
        for row in profiles:
            profile = json.loads(row["mechanics_json"])
            issues, notes = [], []
            source_builds.add(row["source_build"])
            try:
                validate_runtime_profile(profile)
            except (ValueError, TypeError) as exc:
                issues.append(str(exc))
            if mechanics_hash(profile) != row["mechanics_hash"]:
                issues.append("runtime hash mismatch")
            for key, expected in (("civilization", reference["civ_name"]), ("age", reference["age"]),
                                  ("unit_slug", reference["unit_slug"]), ("mode", row["mode"])):
                if profile.get(key) != expected:
                    issues.append(f"identity mismatch: {key}")
            if row["is_default"] and profile["unit_master"] != reference["unit_master"]:
                issues.append("default unit master differs from reference")
            if profile.get("unit_class") != reference["unit_class"]:
                alias = (reference["civ_name"], reference["unit_slug"],
                         reference["unit_class"], profile.get("unit_class"))
                if alias in CLASS_ALIASES:
                    notes.append(f"Configured upgrade class {alias[2]} differs from DAT body class {alias[3]}; explicit config_units alias")
                else:
                    issues.append("unreviewed upgrade-class/DAT-class difference")
            if profile.get("cost") != effective_cost(reference)[0]:
                issues.append("runtime cost differs from the reference cost/discount policy")
            if profile.get("ranged"):
                ranged = profile["ranged"]
                if not equal(ranged["projectile_speed_tiles_per_second"], reference["projectile_speed"], 1e-5):
                    issues.append("projectile speed differs from reference")
                if not equal(ranged["accuracy_percent"], reference["final_accuracy"]):
                    if reference["unit_slug"] == "war_chariot_shu" and row["mode"] == "barrage" \
                            and ranged["accuracy_percent"] == 0:
                        notes.append("Barrage deliberately uses the concrete scatter weapon's zero accuracy, not the Focus Fire shell")
                    else:
                        issues.append("ranged accuracy differs from reference")
            for key, field in stat_pairs.items():
                expected = reference[field]
                if field.endswith("_json"):
                    expected = json.loads(expected)
                if not equal(profile.get(key), expected):
                    issues.append(f"{key}: runtime={profile.get(key)!r}, reference={expected!r}")
            if chain is None:
                issues.append("missing upgrade stat chain")
            else:
                for key, field in (("attack_classes", "attacks_json"), ("armor_classes", "armors_json")):
                    if profile.get(key) != json.loads(chain[field]):
                        issues.append(f"{key}: differs from final upgrade-chain step")
                if reference["final_hp"] != round(chain["hp"]):
                    issues.append("final HP differs from generator's rounded final chain HP")
                if not equal(chain["hp"], reference["final_hp"]):
                    notes.append(f"HP rounds {chain['hp']} to {reference['final_hp']}; raw-game rounding unverified")
                if not equal(profile["speed_tiles_per_second"], chain["speed"]):
                    if reference["unit_slug"] == "war_chariot_shu" and equal(
                            profile["speed_tiles_per_second"], round(chain["speed"], 2)):
                        notes.append("concrete weapon-form speed uses analyzer rounding; DAT rebuild pending")
                    else:
                        issues.append("speed differs from exact upgrade-chain speed")
            reload = reference["final_reload_time"]
            if reference["civ_name"] == "Spanish" and reference["unit_slug"] in {
                    "hand_cannoneer", "bombard_cannon", "cannon_galleon"}:
                reload *= 0.85
                notes.append("Spanish DAT tech-tree reload multiplier applied by exporter, outside reference stat chain")
            if not equal(profile["reload_seconds"], reload):
                issues.append("reload differs from reference plus documented DAT multiplier")
            if profile.get("effects") != reference_effects_for_profile(reference, profile):
                issues.append("reference-backed effects missing/stale in runtime")
            followups = list(UNIT_FOLLOWUPS.get(reference["unit_slug"], ()))
            scope_note = UNIT_SCOPE_NOTES.get(reference["unit_slug"])
            if scope_note:
                notes.append(scope_note)
            if reference["unit_slug"] == "war_chariot_shu" and row["mode"] == "barrage":
                notes.append("Owner scope 2026-10-29: Barrage excluded; use default Focus Fire.")
            if 1474 in reference["applied_tech_ids"]:
                followups.append("Gothikon uses owner-specified independent 30s recharge slots and current 1.6s weapon cycle; exact live throw cadence unverified.")
            records.append({"civilization": reference["civ_name"], "unit": reference["unit_slug"],
                            "name": reference["unit_name"], "mode": row["mode"], "unit_master": profile["unit_master"],
                            "stats": {key: profile[key] for key in (*stat_pairs, "speed_tiles_per_second", "reload_seconds")},
                            "upgrades": techs, "abilities": active, "runtime_effects": profile.get("effects"),
                            "consistency_errors": issues, "source_notes": notes, "followups": followups})
            errors.extend(f"{label}/{row['mode']}: {issue}" for issue in issues)
    auxiliary_count = 0
    for row in connection.execute("SELECT * FROM ref_auxiliary_mechanics"):
        auxiliary_count += 1
        p = json.loads(row["mechanics_json"])
        validate_runtime_profile(p)
        source_builds.add(row["source_build"])
        if mechanics_hash(p) != row["mechanics_hash"]:
            errors.append(f"auxiliary {row['actor_slug']}: hash mismatch")
    if len(source_builds) != 1:
        errors.append("mixed DAT source builds")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        errors.append(f"database integrity: {integrity}")
    connection.close()
    return {
        "scope": "Committed reference-to-runtime consistency and unit-ability inventory; not live calibration",
        "database_sha256": hashlib.sha256(reference_db.read_bytes()).hexdigest(),
        "source_builds": sorted(source_builds), "raw_source_verified": False,
        "raw_source_blocker": "Patch DAT, extraction and resolved civilization tech trees are unavailable in this checkout",
        "summary": {"reference_units": len({(r['civilization'], r['unit']) for r in records}),
                    "runtime_profiles": len(records), "civilizations": len({r['civilization'] for r in records}),
                    "auxiliary_profiles": auxiliary_count, "consistency_errors": len(errors),
                    "profiles_with_followups": sum(bool(r["followups"]) for r in records)},
        "abilities": {name: {"reference_units": count, "consumer": ABILITY_CONSUMERS.get(name),
                             "source": ABILITIES[name].source}
                      for name, count in sorted(abilities.items())},
        "errors": errors, "units": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_db", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--csv", type=Path, help="compact per-unit review table")
    args = parser.parse_args()
    report = audit(args.reference_db)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(["civilization", "unit", "name", "mode", "master", "hp", "melee_attack", "pierce_attack",
                             "melee_armor", "pierce_armor", "speed", "range", "reload", "tech_ids", "abilities",
                             "runtime_effects", "consistency_errors", "source_notes", "followups"])
            for unit in report["units"]:
                stats = unit["stats"]
                writer.writerow([unit["civilization"], unit["unit"], unit["name"], unit["mode"], unit["unit_master"], stats["hp"],
                    stats["attack_classes"].get("4", 0), stats["attack_classes"].get("3", 0),
                    stats["armor_classes"].get("4", 0), stats["armor_classes"].get("3", 0),
                    stats["speed_tiles_per_second"], stats["attack_range_tiles"], stats["reload_seconds"],
                    ";".join(str(t["tech_id"]) for t in unit["upgrades"]), ";".join(unit["abilities"]),
                    json.dumps(unit["runtime_effects"], sort_keys=True), "; ".join(unit["consistency_errors"]),
                    "; ".join(unit["source_notes"]), "; ".join(unit["followups"])])
    print(json.dumps({"summary": report["summary"], "errors": report["errors"],
                      "raw_source_verified": False}, indent=2))
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
