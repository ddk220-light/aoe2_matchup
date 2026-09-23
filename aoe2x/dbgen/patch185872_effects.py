"""Record build 185872 mechanics as evidence, without enabling runtime behavior.

The existing scalar ability model cannot express several Viking Sagas rules.
Namespaced JSON audit rows preserve their DAT commands, tasks and conditions for
the later simulation phase. This module never updates ref_units or engine data.
"""

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from aoe2x.js_simulation.tools.export_unit_mechanics import REFERENCE_TO_DAT_CIV, _parsed_dat


PREFIX = "patch185872:"
NEW_CIVS = {60: "Saxons", 61: "Varangians", 62: "Danes"}
NEW_UNITS = (2700, 2701, 2703, 2704, 2705, 2706, 2708, 2709, 2711, 2712)
RESOURCE_IDS = (33, 275, 291, 297, 298, 299, 551)
AGE_NUMBERS = {"dark": 1, "feudal": 2, "castle": 3, "imperial": 4}
AGE_TECHS = {101: 2, 102: 3, 103: 4}
STAT_POLICY = {
    "health": "full_health",
    "shield_wall_formation_bonus": "not_evaluated",
    "saxon_controlled_town_centers": None,
    "saxon_controlled_castles": None,
    "saxon_discount_evaluation": "not_evaluated; reference costs remain undiscounted",
    "saxon_discount_rule": "5% per controlled Town Center or Castle, capped at 20%",
    "runtime": "Evidence only; conditional mechanics require subsequent runtime validation.",
}

# These labels explain the actual commands, not the frequently stale DAT names.
# Numeric effect values below are always read from the supplied DAT.
NOTES = {
    1452: ("Cranequins", "Mounted crossbow range/LOS and infantry bonus; ordinary stat effects."),
    1464: ("Shield Wall", "Infantry armor depends on nearby infantry. Resource 33 selects engine rule 31; numerical thresholds and radius are not specified by this command."),
    1465: ("Dropsite resources", "New dropsites provide food and stone; economy evidence, no combat stat adjustment."),
    1469: ("Foot soldier discount", "Foot soldiers cost 5% less per controlled Town Center or Castle, capped at 20%. No building count is selected and no discount is evaluated; reference costs remain undiscounted."),
    1470: ("Saxon ship HP", "Longship and Catapult Galleon HP multiplier; ordinary stat effect."),
    1473: ("Vendel Legacy", "Knight-line blast radius and flat-trample encoding. Existing base-unit extraction does not apply this technology to ability fields."),
    1474: ("Gothikon", "Varangian Guards gain a capacity-two projectile charge. Preserve charge event, projectile inheritance and target rules; a single generic recharge timer is insufficient evidence."),
    1475: ("Gathering gold", "Gold from shepherding, hunting and fishing; economy evidence."),
    1478: ("Varangian Guard attack rate", "Guard reload multiplier; do not apply another curated speed bonus after ordinary stat calculation."),
    1479: ("Varangian ship attack rate", "Longship and Catapult Galleon reload multiplier; ordinary stat effect."),
    1483: ("Northmen's Fury", "Siege building attacks use unsigned encoded 140% multipliers; Mangonel-line and Catapult Galleon range/LOS also increase. Decode multiplier bytes separately from signed additive attack values."),
    1484: ("Hamask", "Infantry damage depends on the attacker's missing HP. Resource 33 selects engine rule 30; this is not target-missing-HP execute damage. Full-health stats remain unchanged."),
    1485: ("Razing bounty", "Building destruction can return 25% of the building's resource cost. Conditional economy benefit is not subtracted from unit cost."),
    1486: ("Danish Guard and Longship speed", "Movement-speed multiplier; ordinary stat effect."),
    1488: ("Varangian Guard gold", "Resource 297 multiplier conflicts with the shipped +50% gold tooltip; retain both claims pending validation."),
    1489: ("Varangian Bloodlines", "Additional HP after Bloodlines. Read the commands rather than the stale internal +65% name."),
    1490: ("Varangian Caravan", "Additional trade speed/work-rate after Caravan; economy evidence."),
    1491: ("Clerical Recruitment", "Monk conversion range/LOS and training-time changes; conversion behavior is not enabled by recording this evidence."),
    1492: ("Barracks and Siege upgrade gold", "Research gold-cost multipliers, not free upgrades despite the internal DAT name."),
    1493: ("Saxon fortification arrows", "Castle-Age tower/castle base and maximum projectile-count increases."),
    1494: ("Danish bonus food", "Food drop-off productivity; shipped tooltip says +5%, despite the internal +10% name."),
}

UNIT_NOTES = {
    2700: "Mounted Crossbowman uses ordinary projectile attacks; retain negative class-39 attack and the Cranequins technology separately.",
    2701: "Heavy Mounted Crossbowman uses ordinary projectile attacks; retain negative class-39 attack and the Cranequins technology separately.",
    2703: "Fighting gold is task based, not gold_per_kill. Gothikon is a separate technology; base charge fields are not the upgraded fields.",
    2704: "Fighting gold is task based, not gold_per_kill. Gothikon is a separate technology; base charge fields are not the upgraded fields.",
    2705: "Javelin count, profile and speed are already extracted. Launch/recharge event and target mask still require validation; do not add a second projectile.",
    2706: "Javelin count, profile and speed are already extracted. Launch/recharge event and target mask still require validation; do not add a second projectile.",
    2708: "Ranged melee attack. Shipped civ tip confirms armor reduction; amount, duration and reset behavior are unresolved. Do not assume the existing Obuch armor-strip scalar is equivalent.",
    2709: "Ranged melee attack. Shipped civ tip confirms armor reduction; amount, duration and reset behavior are unresolved. Do not assume the existing Obuch armor-strip scalar is equivalent.",
    2711: "Torch projectile is restricted to buildings and ships by charge_target=320. Generic unrestricted charge behavior is not equivalent; projectile has no independent attack entries.",
    2712: "Torch projectile is restricted to buildings and ships by charge_target=320. Generic unrestricted charge behavior is not equivalent; projectile has no independent attack entries.",
}


def _fields(value, names):
    return {name: getattr(value, name) for name in names if hasattr(value, name)}


def _resources(civ):
    return {str(i): civ.resources[i] for i in RESOURCE_IDS if i < len(civ.resources)}


def _projectile_evidence(civ, pid):
    projectile = civ.units[pid]
    return {
        "unit_id": pid, "name": projectile.name, "speed": projectile.speed,
        "type_50": asdict(projectile.type_50),
        "projectile": asdict(projectile.projectile),
    }


def _minimum_age(data, tech_id, seen=None):
    if tech_id in AGE_TECHS:
        return AGE_TECHS[tech_id]
    seen = set() if seen is None else seen
    if tech_id in seen or not 0 <= tech_id < len(data.techs):
        return 1
    seen.add(tech_id)
    return max([1] + [_minimum_age(data, tid, seen)
                      for tid in data.techs[tech_id].required_techs if tid > 0])


def _matches(mechanic, row, applied_techs):
    if mechanic["civ_name"] and mechanic["civ_name"] != row["civ_name"]:
        return False
    if AGE_NUMBERS[row["age"].lower()] < mechanic["minimum_age"]:
        return False
    tid = mechanic["tech_id"]
    if tid in (1464, 1484):
        return row["unit_class"] == 6
    if tid == 1469:
        return row["unit_class"] in (0, 6, 44)
    if tid == 1488:
        return row["unit_master"] in (2703, 2704)
    if tid == 1485:
        return True  # A civilization-wide conditional benefit of razing.
    if tid in (1475, 1494):
        return False  # Gatherers are outside the military reference roster.
    if tid == 1452 and tid not in applied_techs:
        return False  # Shared research availability differs by civilization.
    for cmd in mechanic["commands"]:
        kind, unit_id, unit_class = cmd["type"], cmd["a"], cmd["b"]
        if kind in (0, 4, 5, 10, 14, 15):
            if unit_id == row["unit_master"] or (unit_id == -1 and unit_class == row["unit_class"]):
                return True
        elif kind == 2 and unit_id == row["unit_master"]:
            return True
        elif kind == 3 and row["unit_master"] == unit_class:
            return True
        elif kind == 101 and unit_id in applied_techs:
            return True
    return False


def _mechanics(data):
    result = []
    selected = [(tid, tech.civ, tech.effect_id, "technology")
                for tid, tech in enumerate(data.techs)
                if tech.effect_id >= 0 and (tech.civ in NEW_CIVS or tid in range(1450, 1455))]
    selected += [(None, cid, data.civs[cid].team_bonus_id, "team_bonus")
                 for cid in NEW_CIVS if data.civs[cid].team_bonus_id >= 0]
    for tid, cid, effect_id, kind in selected:
        effect = data.effects[effect_id]
        tech = data.techs[tid] if tid is not None else None
        label, note = NOTES.get(tid, (effect.name, "Raw DAT effect; recording does not enable runtime behavior."))
        commands = [asdict(command) for command in effect.effect_commands]
        entry = {
            "property_name": PREFIX + label + "_json",
            "label": label, "description": note,
            "civ_id": cid if cid >= 0 else None,
            "civ_name": NEW_CIVS.get(cid),
            "tech_id": tid, "effect_id": effect_id, "kind": kind,
            "dat_tech_name": tech.name if tech else None,
            "dat_effect_name": effect.name,
            "required_techs": list(tech.required_techs) if tech else [],
            "resource_costs": [asdict(cost) for cost in tech.resource_costs] if tech else [],
            "research_locations": [asdict(location) for location in tech.research_locations] if tech else [],
            # DAT 8.8 stores research time per location. Keep every raw location
            # above; the first is the normal displayed research time.
            "research_time": tech.research_locations[0].research_time if tech and tech.research_locations else None,
            "minimum_age": _minimum_age(data, tid) if tid is not None else 1,
            "commands": commands,
            "runtime_status": "validation_pending",
            "recording_role": "source_evidence_only",
            "recorded_for_ref_unit_ids": [],
        }
        if cid in NEW_CIVS:
            entry["resource_evidence"] = _resources(data.civs[cid])
            projectile_ids = {int(c["d"]) for c in commands if c["type"] == 0 and c["c"] == 125 and c["d"] >= 0}
            if projectile_ids:
                entry["projectile_evidence"] = [_projectile_evidence(data.civs[cid], pid)
                                                for pid in sorted(projectile_ids)]
        if tid == 1488:
            multiplier = next(c["d"] for c in commands if c["type"] == 6 and c["a"] == 297)
            entry["discrepancy"] = {
                "dat_resource_297_base": data.civs[cid].resources[297],
                "dat_multiplier": multiplier,
                "dat_resource_297_after_effect": data.civs[cid].resources[297] * multiplier,
                "tooltip_multiplier": 1.5,
                "tooltip_source": "resources/en/strings/key-value/key-value-strings-utf8.txt:120210",
                "resolution": "pending; no runtime gold rate inferred",
            }
        if tid == 1483:
            entry["attack_multipliers"] = [
                {"armor_class": value // 256, "percent": value % 256,
                 "multiplier": (value % 256) / 100}
                for value in sorted({int(c["d"]) for c in commands if c["type"] == 5 and c["c"] == 9})
            ]
        result.append(entry)
    return result


def _unit_evidence(civ, master):
    unit = civ.units[master]
    charge = _fields(unit.creatable, (
        "max_charge", "recharge_rate", "charge_event", "charge_type",
        "charge_target", "charge_projectile_unit", "total_projectiles", "max_total_projectiles",
    ))
    projectile_ids = {getattr(unit.type_50, "projectile_unit_id", -1),
                      charge.get("charge_projectile_unit", -1)}
    projectiles = []
    for pid in sorted(projectile_ids):
        if pid >= 0:
            projectiles.append(_projectile_evidence(civ, pid))
    return {
        "unit_id": master, "dat_name": unit.name, "charge": charge,
        "tasks": [asdict(task) for task in unit.bird.tasks],
        "projectiles": projectiles, "resource_evidence": _resources(civ),
        "description": UNIT_NOTES[master], "runtime_status": "validation_pending",
        "recording_role": "source_evidence_only",
    }


def record_patch_effects(reference_db: Path, dat_path: Path, *, data=None) -> dict:
    """Attach source evidence to existing military rows and return its audit bundle.

    Call after generating the reference database. Only this recorder's namespaced
    audit rows are replaced on repeat calls; scalar stats and other effects stay
    untouched. The cached DAT object is read only, never patched in memory.
    """
    if data is None:
        data = _parsed_dat(str(Path(dat_path).resolve()))
    mechanics = _mechanics(data)
    civ_by_name = {civ.name: civ for civ in data.civs}
    unit_records = []
    inserted = []
    with sqlite3.connect(reference_db) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,civ_name,unit_master,unit_slug,unit_class,age FROM ref_units ORDER BY id").fetchall()
        applied = {}
        for ref_id, tid in db.execute("SELECT ref_unit_id,tech_id FROM ref_techs_applied"):
            applied.setdefault(ref_id, set()).add(tid)
        for mechanic in mechanics:
            matching = [row for row in rows if _matches(mechanic, row, applied.get(row["id"], set()))]
            mechanic["recorded_for_ref_unit_ids"] = [row["id"] for row in matching]
            for row in matching:
                inserted.append((row["id"], mechanic["property_name"], json.dumps(mechanic, sort_keys=True),
                                 f"dat:185872:effect:{mechanic['effect_id']}", mechanic["description"]))
        for row in rows:
            master = row["unit_master"]
            if master not in NEW_UNITS:
                continue
            # Regional units also appear in existing civilizations.
            civ = civ_by_name[REFERENCE_TO_DAT_CIV.get(row["civ_name"], row["civ_name"])]
            if civ.units[master] is None:
                continue
            evidence = _unit_evidence(civ, master)
            evidence.update(ref_unit_id=row["id"], civ_name=row["civ_name"], age=row["age"])
            unit_records.append(evidence)
            inserted.append((row["id"], PREFIX + "unit-mechanics_json", json.dumps(evidence, sort_keys=True),
                             f"dat:185872:unit:{master}", evidence["description"]))
        db.execute("DELETE FROM ref_special_effects WHERE property_name LIKE ?", (PREFIX + "%",))
        db.executemany("""INSERT INTO ref_special_effects
            (ref_unit_id,property_name,property_value,source,description) VALUES (?,?,?,?,?)""", inserted)
    return {
        "build": 185872, "dat_path": str(Path(dat_path).resolve()), "dat_version": data.version,
        "stat_policy": dict(STAT_POLICY), "mechanics": mechanics, "unit_mechanics": unit_records,
        "recorded_effect_rows": len(inserted),
        "covered_reference_rows": len({row[0] for row in inserted}),
        "coverage_notes": [
            "Source records are not assertions that simulation handlers exist or are correct.",
            "Hamask and Shield Wall resource selectors are included even when ordinary stat discovery omits them.",
            "Economy, repair and fortification effects remain in this bundle when no corresponding military reference row exists.",
            "No team composition is assumed: a team bonus is attached only to its own civilization's relevant rows.",
            "New-unit base charges and separate technology commands are preserved without applying a second bonus or projectile.",
        ],
    }
