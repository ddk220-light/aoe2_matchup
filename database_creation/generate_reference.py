#!/usr/bin/env python3
"""Generate the AoE2 reference/audit database with detailed stat breakdowns.

Usage:
    python3 -m database_creation.generate_reference
    # or from project root:
    python3 database_creation/generate_reference.py
"""

import json
import sqlite3
from pathlib import Path

from .combat_properties import get_combat_properties
from .config import (
    ATTR_ACCURACY,
    ATTR_ARMOR,
    ATTR_ATTACK,
    ATTR_DISPLAY_NAMES,
    BUILDING_NAMES,
    BUILDING_WORK_RATE_TECHS,
    CASTLE_AGE,
    CASTLE_UNITS,
    CIV_COMBAT_PROPERTIES,
    CIV_TEAM_BONUS_ATTACK,
    CIV_TEAM_BONUS_WORK_RATE,
    CMD_ADD_ATTRIBUTE,
    CMD_MULTIPLY_ATTRIBUTE,
    CMD_SET_ATTRIBUTE,
    COMBAT_PROPERTIES,
    IMPERIAL_AGE,
    IMPERIAL_UNITS,
    ORIGINAL_13_CIVS,
    OUTPUT_DIR,
    REF_DB_PATH,
    UNIQUE_COMBAT_PROPERTIES,
    UNIQUE_UNIT_BUILDING,
    UNIQUE_UNITS,
    UNIQUE_UNITS_IN_BARRACKS,
    UNIT_CLASS_TO_BUILDING,
    _tech_age_name,
)
from .unit_analyzer import UnitAnalyzer


def _describe_effect_cmd(cmd, armor_class_names):
    """Generate a human-readable description of a single effect command."""
    cmd_type = cmd.get("type", 0)
    c = cmd.get("c", 0)
    d = cmd.get("d", 0)

    if cmd_type == CMD_SET_ATTRIBUTE:
        attr_name = ATTR_DISPLAY_NAMES.get(c, f"attr_{c}")
        if c == ATTR_ACCURACY:
            return f"set {attr_name}={d:.0f}%"
        return f"set {attr_name}={d:.3g}"
    elif cmd_type == CMD_ADD_ATTRIBUTE:
        if c == ATTR_ATTACK:
            d_int = int(d)
            if d_int >= 0:
                atk_class = d_int // 256
                amount = d_int % 256
                if amount > 127:
                    amount -= 256
            else:
                d_int_abs = abs(d_int)
                atk_class = d_int_abs // 256
                amount = -(d_int_abs % 256)
            cls_name = armor_class_names.get(atk_class, f"class {atk_class}")
            sign = "+" if amount >= 0 else ""
            return f"{sign}{amount} attack ({cls_name})"
        elif c == ATTR_ARMOR:
            d_int = int(d)
            if d_int >= 0:
                arm_class = d_int // 256
                amount = d_int % 256
                if amount > 127:
                    amount -= 256
            else:
                d_int_abs = abs(d_int)
                arm_class = d_int_abs // 256
                amount = -(d_int_abs % 256)
            cls_name = armor_class_names.get(arm_class, f"class {arm_class}")
            sign = "+" if amount >= 0 else ""
            return f"{sign}{amount} armor ({cls_name})"
        else:
            attr_name = ATTR_DISPLAY_NAMES.get(c, f"attr_{c}")
            sign = "+" if d >= 0 else ""
            return f"{sign}{d:.3g} {attr_name}"
    elif cmd_type == CMD_MULTIPLY_ATTRIBUTE:
        attr_name = ATTR_DISPLAY_NAMES.get(c, f"attr_{c}")
        return f"x{d:.3g} {attr_name}"
    return f"cmd_{cmd_type} attr_{c}={d}"


def _get_tech_building(tech_data):
    """Get building name for a tech from its research_location."""
    rl = tech_data.get("research_location", -1)
    if rl >= 0:
        return BUILDING_NAMES.get(rl, f"Building_{rl}")
    return "N/A"


def _snapshot_stats(stats):
    """Capture a snapshot of current stats as a dict."""
    return {
        "hp": stats.hp,
        "attack": stats.attack,
        "melee_armor": stats.melee_armor,
        "pierce_armor": stats.pierce_armor,
        "speed": stats.speed,
        "range": stats.range,
        "reload_time": stats.reload_time,
        "accuracy": stats.accuracy,
        "los": stats.los,
        "train_time": stats.train_time,
        "cost_food": stats.cost_food,
        "cost_wood": stats.cost_wood,
        "cost_gold": stats.cost_gold,
        "attacks": dict(stats.attacks),
        "armors": dict(stats.armors),
    }


def _diff_stats(before, after, armor_class_names):
    """Describe what changed between two stat snapshots."""
    changes = []
    for key, label in [
        ("hp", "HP"),
        ("attack", "Attack"),
        ("melee_armor", "MA"),
        ("pierce_armor", "PA"),
        ("speed", "Speed"),
        ("range", "Range"),
        ("reload_time", "Reload"),
        ("accuracy", "Accuracy"),
        ("los", "LOS"),
        ("train_time", "Train Time"),
    ]:
        old_val = before[key]
        new_val = after[key]
        if abs(new_val - old_val) > 0.001:
            diff = new_val - old_val
            # Check if multiplicative (ratio-based)
            if (
                old_val != 0
                and abs(diff / old_val) > 0.01
                and key in ("reload_time", "speed", "hp")
            ):
                ratio = new_val / old_val
                if abs(ratio - round(ratio)) > 0.001:  # Not a clean additive
                    changes.append(f"x{ratio:.3g} {label}")
                    continue
            sign = "+" if diff > 0 else ""
            changes.append(f"{sign}{diff:.3g} {label}")

    # Cost changes
    for key, label in [
        ("cost_food", "food"),
        ("cost_wood", "wood"),
        ("cost_gold", "gold"),
    ]:
        old_val = before[key]
        new_val = after[key]
        if abs(new_val - old_val) > 0.01:
            diff = new_val - old_val
            if old_val != 0:
                ratio = new_val / old_val
                if abs(ratio - round(ratio)) > 0.001:
                    changes.append(f"x{ratio:.3g} {label}")
                    continue
            sign = "+" if diff > 0 else ""
            changes.append(f"{sign}{diff:.3g} {label}")

    # Attack class changes
    for cls_id in sorted(
        set(list(before["attacks"].keys()) + list(after["attacks"].keys()))
    ):
        old_val = before["attacks"].get(cls_id, 0)
        new_val = after["attacks"].get(cls_id, 0)
        if abs(new_val - old_val) > 0.001:
            cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
            sign = "+" if (new_val - old_val) > 0 else ""
            changes.append(f"{sign}{new_val - old_val:.0f} atk ({cls_name})")

    # Armor class changes
    for cls_id in sorted(
        set(list(before["armors"].keys()) + list(after["armors"].keys()))
    ):
        old_val = before["armors"].get(cls_id, 0)
        new_val = after["armors"].get(cls_id, 0)
        if abs(new_val - old_val) > 0.001:
            cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
            sign = "+" if (new_val - old_val) > 0 else ""
            changes.append(f"{sign}{new_val - old_val:.0f} armor ({cls_name})")

    return ", ".join(changes) if changes else "(no change)"


def generate_reference_database(analyzer):
    """Generate the reference/audit database with detailed stat breakdowns."""
    ref_db_path = REF_DB_PATH
    if ref_db_path.exists():
        ref_db_path.unlink()

    conn = sqlite3.connect(str(ref_db_path))
    cursor = conn.cursor()

    # Load armor class names
    armor_class_names = {}
    ac_file = OUTPUT_DIR / "armor_classes.json"
    if ac_file.exists():
        for ac in json.load(open(ac_file)):
            armor_class_names[ac["id"]] = ac["name"]

    # Create tables
    cursor.executescript("""
        CREATE TABLE ref_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ_name TEXT NOT NULL,
            unit_name TEXT NOT NULL,
            unit_slug TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            age TEXT NOT NULL,
            unit_class INTEGER,
            unit_class_name TEXT,
            is_ranged INTEGER DEFAULT 0,
            base_hp REAL, base_attack REAL, base_melee_armor REAL, base_pierce_armor REAL,
            base_speed REAL, base_range REAL, base_reload_time REAL, base_attack_delay REAL,
            base_accuracy REAL, base_los REAL,
            base_cost_food REAL, base_cost_wood REAL, base_cost_gold REAL,
            base_attacks_json TEXT, base_armors_json TEXT,
            final_hp REAL, final_attack REAL, final_melee_armor REAL, final_pierce_armor REAL,
            final_speed REAL, final_range REAL, final_reload_time REAL, final_attack_delay REAL,
            final_accuracy REAL, final_los REAL,
            final_cost_food REAL, final_cost_wood REAL, final_cost_gold REAL,
            final_attacks_json TEXT, final_armors_json TEXT,
            base_train_time REAL, final_train_time REAL,
            total_projectiles REAL, projectile_speed REAL, min_range REAL,
            outline_size_x REAL DEFAULT 0.2,
            applied_bonuses_summary TEXT,
            upgrade_cost_food INTEGER DEFAULT 0,
            upgrade_cost_wood INTEGER DEFAULT 0,
            upgrade_cost_gold INTEGER DEFAULT 0,
            -- Combat properties (inline for direct sim access)
            extra_projectiles INTEGER DEFAULT 0,
            extra_projectile_attacks_json TEXT,
            first_attack_extra_projectiles INTEGER DEFAULT 0,
            charge_projectile_count INTEGER DEFAULT 0,
            charge_projectile_attacks_json TEXT,
            charge_projectile_speed REAL DEFAULT 0,
            charge_attack_range REAL DEFAULT 0,
            charge_ignores_armor INTEGER DEFAULT 0,
            ignores_melee_armor INTEGER DEFAULT 0,
            ignores_pierce_armor INTEGER DEFAULT 0,
            trample_percent REAL DEFAULT 0,
            trample_radius REAL DEFAULT 0,
            trample_flat_damage INTEGER DEFAULT 0,
            bonus_damage_reduction REAL DEFAULT 0,
            splash_on_hit_radius REAL DEFAULT 0,
            splash_on_hit_fraction REAL DEFAULT 1.0,
            dodge_shield_max INTEGER DEFAULT 0,
            dodge_shield_recharge REAL DEFAULT 0,
            bleed_dps REAL DEFAULT 0,
            bleed_duration REAL DEFAULT 0,
            block_first_melee INTEGER DEFAULT 0,
            attack_bonus_per_kill REAL DEFAULT 0,
            hp_transform_threshold REAL DEFAULT 0,
            hp_regen REAL DEFAULT 0,
            pass_through_percent REAL DEFAULT 0,
            pop_space REAL DEFAULT 1.0,
            armor_strip_per_hit INTEGER DEFAULT 0,
            charge_attack_melee INTEGER DEFAULT 0,
            charge_recharge_time REAL DEFAULT 0,
            damage_reflect_percent REAL DEFAULT 0,
            splash_radius REAL DEFAULT 0,
            is_siege_projectile INTEGER DEFAULT 0,
            -- Dismount on death (Konnik etc.)
            dismount_unit_id INTEGER DEFAULT 0,
            dismount_hp INTEGER,
            dismount_attack INTEGER,
            dismount_melee_armor INTEGER,
            dismount_pierce_armor INTEGER,
            dismount_attack_speed REAL,
            dismount_attack_delay REAL,
            dismount_movement_speed REAL,
            dismount_attacks_json TEXT,
            dismount_armors_json TEXT,
            -- Transform on HP threshold (Jian Swordsman etc.)
            transform_hp INTEGER,
            transform_attack INTEGER,
            transform_melee_armor INTEGER,
            transform_pierce_armor INTEGER,
            transform_attack_speed REAL,
            transform_attack_delay REAL,
            transform_movement_speed REAL,
            transform_attacks_json TEXT,
            transform_armors_json TEXT
        );
        CREATE TABLE ref_techs_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            tech_id INTEGER,
            tech_name TEXT NOT NULL,
            tech_type TEXT NOT NULL,
            building TEXT,
            age_available TEXT,
            effect_description TEXT,
            cost_food INTEGER DEFAULT 0,
            cost_wood INTEGER DEFAULT 0,
            cost_gold INTEGER DEFAULT 0,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE ref_stat_chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            tech_name TEXT NOT NULL,
            tech_type TEXT NOT NULL,
            hp REAL, attack REAL, melee_armor REAL, pierce_armor REAL,
            speed REAL, range_val REAL, reload_time REAL,
            accuracy REAL, los REAL, train_time REAL,
            cost_food REAL, cost_wood REAL, cost_gold REAL,
            attacks_json TEXT, armors_json TEXT,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE ref_special_effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            property_name TEXT NOT NULL,
            property_value TEXT,
            source TEXT,
            description TEXT,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE ref_projectiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            projectile_type TEXT NOT NULL,
            projectile_count INTEGER,
            projectile_speed REAL,
            attacks_json TEXT,
            blast_radius REAL,
            is_siege_projectile INTEGER DEFAULT 0,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE armor_classes (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
    """)

    # Populate armor_classes from extracted data
    for ac in armor_class_names.items():
        cursor.execute("INSERT INTO armor_classes (id, name) VALUES (?, ?)", ac)

    cursor.execute("""
        CREATE TABLE battle_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_slug TEXT NOT NULL,
            age TEXT NOT NULL,
            civ_name TEXT NOT NULL,
            unit_slug TEXT NOT NULL,
            score_type TEXT NOT NULL,
            score_value REAL NOT NULL
        );
    """)
    cursor.execute(
        "CREATE INDEX idx_battle_scores_line_age ON battle_scores (line_slug, age);"
    )

    # Class names from unit data
    class_names = {}
    for uid, u in analyzer.units.items():
        cls_id = u.get("class", -1)
        cls_name = u.get("class_name", "")
        if cls_id >= 0 and cls_name:
            class_names[cls_id] = cls_name

    def _insert_stat_chain_row(ref_unit_id, step, tech_name, tech_type, snap):
        cursor.execute(
            """INSERT INTO ref_stat_chain
               (ref_unit_id, step_order, tech_name, tech_type,
                hp, attack, melee_armor, pierce_armor,
                speed, range_val, reload_time, accuracy, los, train_time,
                cost_food, cost_wood, cost_gold,
                attacks_json, armors_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ref_unit_id,
                step,
                tech_name,
                tech_type,
                snap["hp"],
                snap["attack"],
                snap["melee_armor"],
                snap["pierce_armor"],
                snap["speed"],
                snap["range"],
                snap["reload_time"],
                snap["accuracy"],
                snap["los"],
                snap["train_time"],
                snap["cost_food"],
                snap["cost_wood"],
                snap["cost_gold"],
                json.dumps(snap["attacks"]),
                json.dumps(snap["armors"]),
            ),
        )

    def _insert_tech_applied(
        ref_unit_id,
        tech_id,
        tech_name,
        tech_type,
        building,
        age_available,
        effect_desc,
        cost,
    ):
        cursor.execute(
            """INSERT INTO ref_techs_applied
               (ref_unit_id, tech_id, tech_name, tech_type, building,
                age_available, effect_description, cost_food, cost_wood, cost_gold)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                ref_unit_id,
                tech_id,
                tech_name,
                tech_type,
                building,
                age_available,
                effect_desc,
                cost.get("food", 0),
                cost.get("wood", 0),
                cost.get("gold", 0),
            ),
        )

    def process_unit_audited(
        civ_name,
        unit_id,
        unit_class,
        unit_name,
        unit_slug,
        unit_type,
        age_label,
        max_age,
        unit_data,
        excluded_tech_ids=None,
    ):
        """Process one unit with full audit trail. Returns ref_unit_id or None.

        unit_class can be an int or tuple of ints (for dual-class units).
        The primary class (first element) is stored in DB; the full value
        is used for tech filtering.
        """
        stats = analyzer.get_base_stats(unit_data)
        base_snap = _snapshot_stats(stats)
        is_ranged = 1 if unit_data.get("range", 0) > 1 else 0

        # For DB storage, use primary class only
        db_class = (
            unit_class[0] if isinstance(unit_class, (list, tuple)) else unit_class
        )

        # Insert ref_units row (will fill final stats later)
        cursor.execute(
            """INSERT INTO ref_units
               (civ_name, unit_name, unit_slug, unit_type, age,
                unit_class, unit_class_name, is_ranged,
                base_hp, base_attack, base_melee_armor, base_pierce_armor,
                base_speed, base_range, base_reload_time, base_attack_delay,
                base_accuracy, base_los,
                base_cost_food, base_cost_wood, base_cost_gold,
                base_attacks_json, base_armors_json,
                base_train_time,
                total_projectiles, projectile_speed, min_range,
                outline_size_x)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                civ_name,
                unit_name,
                unit_slug,
                unit_type,
                age_label,
                db_class,
                class_names.get(db_class, ""),
                is_ranged,
                base_snap["hp"],
                base_snap["attack"],
                base_snap["melee_armor"],
                base_snap["pierce_armor"],
                base_snap["speed"],
                base_snap["range"],
                base_snap["reload_time"],
                unit_data.get("attack_delay", 0),
                base_snap["accuracy"],
                base_snap["los"],
                base_snap["cost_food"],
                base_snap["cost_wood"],
                base_snap["cost_gold"],
                json.dumps(base_snap["attacks"]),
                json.dumps(base_snap["armors"]),
                base_snap["train_time"],
                unit_data.get("total_projectiles", 1),
                unit_data.get("projectile_speed", 0),
                unit_data.get("min_range", 0),
                unit_data.get("outline_size_x", 0.2),
            ),
        )
        ref_unit_id = cursor.lastrowid

        # Step 0: base stats
        step = 0
        _insert_stat_chain_row(ref_unit_id, step, "Base Stats", "base", base_snap)
        step += 1

        disabled_techs = analyzer.get_disabled_techs(civ_name)
        _excluded = set(excluded_tech_ids or [])
        all_tech_names = []

        # Phase 1: Standard techs
        standard_techs = analyzer.find_techs_affecting_unit(
            unit_id, unit_class, max_age
        )
        for tech_id in sorted(standard_techs):
            if tech_id in disabled_techs or tech_id in _excluded:
                continue
            if tech_id not in analyzer.tech_effect_map:
                continue

            te = analyzer.tech_effect_map[tech_id]
            tech_data = analyzer.techs.get(tech_id, {})
            tech_name = tech_data.get("name", f"Tech {tech_id}")
            building = _get_tech_building(tech_data)
            tech_age = analyzer.get_tech_age(tech_id)
            cost = tech_data.get("cost", {})

            before = _snapshot_stats(stats)
            applied = False
            effects = []
            applied_attrs = set()
            for cmd in te.get("commands", []):
                # Deduplicate: skip if same (type, attr, value) already applied
                # in this tech (e.g. monk HP techs target class AND unit_id)
                attr_key = (cmd.get("type", 0), cmd.get("c", 0), cmd.get("d", 0))
                if attr_key in applied_attrs:
                    continue
                if analyzer.apply_effect_command(cmd, stats, unit_id, unit_class):
                    applied = True
                    applied_attrs.add(attr_key)
                    effects.append(_describe_effect_cmd(cmd, armor_class_names))

            if applied:
                after = _snapshot_stats(stats)
                effect_desc = "; ".join(effects)
                _insert_tech_applied(
                    ref_unit_id,
                    tech_id,
                    tech_name,
                    "standard",
                    building,
                    _tech_age_name(tech_age),
                    effect_desc,
                    cost,
                )
                _insert_stat_chain_row(ref_unit_id, step, tech_name, "standard", after)
                step += 1
                all_tech_names.append(tech_name)

        # Phase 2: Civ bonus techs
        civ_bonus_techs = analyzer.get_civ_bonus_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in civ_bonus_techs:
            tech_id = te.get("tech_id", 0)
            tech_data = analyzer.techs.get(tech_id, {})
            tech_name = tech_data.get("name", f"Tech {tech_id}")
            if tech_name in ("None", "", None):
                tech_name = f"C-Bonus (Tech {tech_id})"
            tech_age = analyzer.get_tech_age_recursive(tech_id)
            cost = tech_data.get("cost", {})

            before = _snapshot_stats(stats)
            applied = False
            effects = []
            applied_attrs = set()
            for cmd in te.get("commands", []):
                attr_key = (cmd.get("type", 0), cmd.get("c", 0), cmd.get("d", 0))
                if attr_key in applied_attrs:
                    continue
                if analyzer.apply_effect_command(cmd, stats, unit_id, unit_class):
                    applied = True
                    applied_attrs.add(attr_key)
                    effects.append(_describe_effect_cmd(cmd, armor_class_names))

            if applied:
                after = _snapshot_stats(stats)
                effect_desc = "; ".join(effects)
                _insert_tech_applied(
                    ref_unit_id,
                    tech_id,
                    tech_name,
                    "civ_bonus",
                    "N/A",
                    _tech_age_name(tech_age),
                    effect_desc,
                    cost,
                )
                _insert_stat_chain_row(ref_unit_id, step, tech_name, "civ_bonus", after)
                step += 1
                all_tech_names.append(tech_name)

        # Phase 2b: Team bonus attack bonuses
        team_atk_bonuses = CIV_TEAM_BONUS_ATTACK.get(civ_name, [])
        for bonus in team_atk_bonuses:
            matched = False
            if len(bonus) == 3:
                b_unit_id, atk_class, amount = bonus
                matched = b_unit_id == unit_id
            elif len(bonus) == 4:
                b_unit_id, atk_class, amount, b_class_id = bonus
                if isinstance(unit_class, (list, tuple)):
                    matched = b_unit_id == -1 and b_class_id in unit_class
                else:
                    matched = b_unit_id == -1 and b_class_id == unit_class
            if matched:
                before = _snapshot_stats(stats)
                if atk_class in stats.attacks:
                    stats.attacks[atk_class] += amount
                else:
                    stats.attacks[atk_class] = amount
                after = _snapshot_stats(stats)
                tb_name = f"{civ_name} Team Bonus"
                cls_name = armor_class_names.get(atk_class, f"Class {atk_class}")
                effect_desc = f"+{amount} attack ({cls_name})"
                _insert_tech_applied(
                    ref_unit_id,
                    0,
                    tb_name,
                    "civ_bonus",
                    "N/A",
                    "N/A",
                    effect_desc,
                    {},
                )
                _insert_stat_chain_row(ref_unit_id, step, tb_name, "civ_bonus", after)
                step += 1
                all_tech_names.append(tb_name)

        # Phase 3: Unique techs
        unique_techs = analyzer.get_unique_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in unique_techs:
            tech_id = te.get("tech_id", 0)
            tech_data = analyzer.techs.get(tech_id, {})
            tech_name = te.get("tech_name", tech_data.get("name", f"Tech {tech_id}"))
            building = _get_tech_building(tech_data)
            tech_age = analyzer.get_tech_age_recursive(tech_id)
            cost = tech_data.get("cost", {})

            before = _snapshot_stats(stats)
            applied = False
            effects = []
            applied_attrs = set()
            for cmd in te.get("commands", []):
                attr_key = (cmd.get("type", 0), cmd.get("c", 0), cmd.get("d", 0))
                if attr_key in applied_attrs:
                    continue
                if analyzer.apply_effect_command(cmd, stats, unit_id, unit_class):
                    applied = True
                    applied_attrs.add(attr_key)
                    effects.append(_describe_effect_cmd(cmd, armor_class_names))

            if applied:
                after = _snapshot_stats(stats)
                effect_desc = "; ".join(effects)
                _insert_tech_applied(
                    ref_unit_id,
                    tech_id,
                    tech_name,
                    "unique_tech",
                    building,
                    _tech_age_name(tech_age),
                    effect_desc,
                    cost,
                )
                _insert_stat_chain_row(
                    ref_unit_id, step, tech_name, "unique_tech", after
                )
                step += 1
                all_tech_names.append(tech_name)

        # Final stats
        final_snap = _snapshot_stats(stats)

        # Apply building work rate to creation time
        if final_snap["train_time"] > 0:
            if unit_type == "unique":
                bld_id = UNIQUE_UNIT_BUILDING
                # Strip civ suffix from slug for lookup (e.g. elite_huskarl_goths → elite_huskarl)
                unit_slug_key = unit_slug
                civ_suffix = "_" + civ_name.lower()
                if unit_slug_key.endswith(civ_suffix):
                    unit_slug_key = unit_slug_key[: -len(civ_suffix)]
                barracks_key = (civ_name, unit_slug_key)
                castle_rate = analyzer.get_building_work_rate(
                    civ_name, UNIQUE_UNIT_BUILDING, max_age
                )
                if barracks_key in UNIQUE_UNITS_IN_BARRACKS:
                    barracks_id = UNIQUE_UNITS_IN_BARRACKS[barracks_key]
                    barracks_rate = analyzer.get_building_work_rate(
                        civ_name, barracks_id, max_age
                    )
                    best_rate = max(castle_rate, barracks_rate)
                    if barracks_rate > castle_rate:
                        bld_id = barracks_id
                else:
                    best_rate = castle_rate
            else:
                bld_id = UNIT_CLASS_TO_BUILDING.get(db_class)
                best_rate = (
                    analyzer.get_building_work_rate(civ_name, bld_id, max_age)
                    if bld_id
                    else 1.0
                )

            if best_rate > 1.0:
                final_snap["train_time"] = final_snap["train_time"] / best_rate
                # Add stat chain step and tech applied entries for work rate techs
                disabled_techs = analyzer.get_disabled_techs(civ_name)
                civ_id = analyzer.civ_name_to_id.get(civ_name, -1)
                work_rate_techs = []
                for tech_id, (
                    tech_civ_id,
                    bldg_mults,
                ) in BUILDING_WORK_RATE_TECHS.items():
                    if bld_id not in bldg_mults:
                        continue
                    if tech_id in disabled_techs:
                        continue
                    if tech_civ_id != -1 and tech_civ_id != civ_id:
                        continue
                    tech_age = analyzer.get_tech_age_recursive(tech_id)
                    if tech_age > max_age:
                        continue
                    te = analyzer.tech_effect_map.get(tech_id, {})
                    tname = te.get("tech_name", f"Tech {tech_id}")
                    work_rate_techs.append(tname)
                    # Add tech applied entry
                    building = te.get("building", "")
                    cost = te.get("cost", {})
                    mult = bldg_mults[bld_id]
                    effect_desc = f"Building work rate ×{mult} (train time ÷{mult})"
                    _insert_tech_applied(
                        ref_unit_id,
                        tech_id,
                        tname,
                        "work_rate",
                        building,
                        _tech_age_name(tech_age),
                        effect_desc,
                        cost,
                    )
                    all_tech_names.append(tname)
                # Add team bonus work rate if applicable
                team_bonus = CIV_TEAM_BONUS_WORK_RATE.get(civ_name, {})
                if bld_id in team_bonus:
                    tb_mult = team_bonus[bld_id]
                    tb_name = f"{civ_name} Team Bonus"
                    work_rate_techs.append(tb_name)
                    effect_desc = (
                        f"Building work rate ×{tb_mult} (train time ÷{tb_mult})"
                    )
                    _insert_tech_applied(
                        ref_unit_id,
                        -1,
                        tb_name,
                        "civ_bonus",
                        "N/A",
                        "Dark",
                        effect_desc,
                        {},
                    )
                    all_tech_names.append(tb_name)
                # Add stat chain step showing the work rate effect
                work_rate_snap = dict(final_snap)
                _insert_stat_chain_row(
                    ref_unit_id,
                    step,
                    "Building Work Rate (" + ", ".join(work_rate_techs) + ")",
                    "work_rate",
                    work_rate_snap,
                )
                step += 1

        cursor.execute(
            """UPDATE ref_units SET
               final_hp=?, final_attack=?, final_melee_armor=?, final_pierce_armor=?,
               final_speed=?, final_range=?, final_reload_time=?, final_attack_delay=?,
               final_accuracy=?, final_los=?,
               final_cost_food=?, final_cost_wood=?, final_cost_gold=?,
               final_attacks_json=?, final_armors_json=?,
               final_train_time=?,
               hp_regen=?,
               applied_bonuses_summary=?
               WHERE id=?""",
            (
                round(final_snap["hp"]),
                round(final_snap["attack"]),
                round(final_snap["melee_armor"]),
                round(final_snap["pierce_armor"]),
                round(final_snap["speed"], 2),
                round(final_snap["range"], 1),
                round(final_snap["reload_time"], 3),
                unit_data.get("attack_delay", 0),
                round(final_snap["accuracy"]),
                round(final_snap["los"], 1),
                round(final_snap["cost_food"]),
                round(final_snap["cost_wood"]),
                round(final_snap["cost_gold"]),
                json.dumps(
                    {str(k): round(v) for k, v in final_snap["attacks"].items()}
                ),
                json.dumps({str(k): round(v) for k, v in final_snap["armors"].items()}),
                round(final_snap["train_time"]),
                round(stats.hp_regen, 1),
                ", ".join(all_tech_names),
                ref_unit_id,
            ),
        )

        # Compute total upgrade cost (sum of all tech costs, with data-driven overrides)
        tech_costs = cursor.execute(
            """SELECT tech_id, cost_food, cost_wood, cost_gold
               FROM ref_techs_applied WHERE ref_unit_id=?""",
            (ref_unit_id,),
        ).fetchall()
        total_food, total_wood, total_gold = 0, 0, 0
        for tc_tech_id, tc_food, tc_wood, tc_gold in tech_costs:
            modified = analyzer.get_modified_tech_cost(civ_name, tc_tech_id)
            if modified is not None:
                tc_food, tc_wood, tc_gold = modified
            total_food += tc_food
            total_wood += tc_wood
            total_gold += tc_gold
        cursor.execute(
            """UPDATE ref_units SET upgrade_cost_food=?, upgrade_cost_wood=?, upgrade_cost_gold=?
               WHERE id=?""",
            (total_food, total_wood, total_gold, ref_unit_id),
        )

        # Special effects (combat properties)
        combat_props = get_combat_properties(
            unit_slug, civ_name=civ_name, unit_id=unit_id, units_data=analyzer.units
        )
        # Merge hp_regen from tech effects (e.g. Wu infantry regen civ bonus)
        # The analyzer tracks attr 109 additions; use the higher value
        if stats.hp_regen > combat_props.get("hp_regen", 0):
            combat_props["hp_regen"] = round(stats.hp_regen, 1)

        # Upgrade transform stats: apply same tech deltas as normal form
        # delta = transform_base - normal_base; transform_final = normal_final + delta
        if combat_props.get("hp_transform_threshold") and combat_props.get("transform_attack") is not None:
            t_base_atk = combat_props["transform_attack"]
            t_base_ma = combat_props["transform_melee_armor"]
            t_base_pa = combat_props["transform_pierce_armor"]
            t_base_spd = combat_props.get("transform_movement_speed", 1.0)

            n_base_atk = base_snap["attack"]
            n_base_ma = base_snap["melee_armor"]
            n_base_pa = base_snap["pierce_armor"]
            n_base_spd = base_snap["speed"]

            combat_props["transform_attack"] = round(final_snap["attack"] + (t_base_atk - n_base_atk))
            combat_props["transform_melee_armor"] = max(0, round(final_snap["melee_armor"] + (t_base_ma - n_base_ma)))
            combat_props["transform_pierce_armor"] = max(0, round(final_snap["pierce_armor"] + (t_base_pa - n_base_pa)))
            speed_ratio = t_base_spd / n_base_spd if n_base_spd > 0 else 1.0
            combat_props["transform_movement_speed"] = round(final_snap["speed"] * speed_ratio, 2)

            # Upgrade attacks_json: per-class deltas
            t_attacks = json.loads(combat_props.get("transform_attacks_json", "{}"))
            b_attacks = {int(k): v for k, v in base_snap["attacks"].items()}
            f_attacks = {int(k): v for k, v in final_snap["attacks"].items()}
            upgraded_attacks = {}
            for cls in set(list(t_attacks.keys()) + list(f_attacks.keys())):
                cls_int = int(cls)
                delta = int(t_attacks.get(cls_int, t_attacks.get(str(cls_int), 0))) - b_attacks.get(cls_int, 0)
                upgraded_attacks[str(cls_int)] = round(f_attacks.get(cls_int, 0) + delta)
            combat_props["transform_attacks_json"] = json.dumps(upgraded_attacks)

            # Upgrade armors_json: per-class deltas
            t_armors = json.loads(combat_props.get("transform_armors_json", "{}"))
            b_armors = {int(k): v for k, v in base_snap["armors"].items()}
            f_armors = {int(k): v for k, v in final_snap["armors"].items()}
            upgraded_armors = {}
            for cls in set(list(t_armors.keys()) + list(f_armors.keys())):
                cls_int = int(cls)
                delta = int(t_armors.get(cls_int, t_armors.get(str(cls_int), 0))) - b_armors.get(cls_int, 0)
                upgraded_armors[str(cls_int)] = max(0, round(f_armors.get(cls_int, 0) + delta))
            combat_props["transform_armors_json"] = json.dumps(upgraded_armors)

        special_props = [
            ("ignores_melee_armor", "Unit ignores melee armor"),
            ("ignores_pierce_armor", "Unit ignores pierce armor"),
            ("trample_percent", "Trample damage percent"),
            ("trample_radius", "Trample damage radius"),
            ("trample_flat_damage", "Flat trample damage"),
            ("bonus_damage_reduction", "Reduces bonus damage taken"),
            ("splash_radius", "Splash damage radius"),
            ("splash_on_hit_radius", "Splash on hit radius"),
            ("splash_on_hit_fraction", "Splash on hit damage fraction"),
            ("dodge_shield_max", "Dodge shield charges"),
            ("dodge_shield_recharge", "Dodge shield recharge time"),
            ("bleed_dps", "Bleed damage per second"),
            ("bleed_duration", "Bleed duration"),
            ("block_first_melee", "Blocks first melee hit"),
            ("attack_bonus_per_kill", "Attack bonus per kill"),
            ("charge_attack_range", "Charge attack range"),
            ("charge_ignores_armor", "Charge attack ignores armor"),
            ("hp_transform_threshold", "HP threshold for form change"),
            ("dismount_unit_id", "Dismounts to unit on death"),
            ("hp_regen", "HP regeneration per minute"),
            ("pass_through_percent", "Pass-through damage percent"),
            ("pop_space", "Population space per unit"),
            ("armor_strip_per_hit", "Armor stripped per hit"),
            ("charge_attack_melee", "Melee charge bonus damage"),
            ("charge_recharge_time", "Charge recharge time in seconds"),
            ("dismount_hp", "Dismounted unit HP"),
            ("dismount_attack", "Dismounted unit attack"),
            ("dismount_melee_armor", "Dismounted unit melee armor"),
            ("dismount_pierce_armor", "Dismounted unit pierce armor"),
            ("dismount_attack_speed", "Dismounted unit attack speed"),
            ("dismount_attack_delay", "Dismounted unit attack delay"),
            ("dismount_movement_speed", "Dismounted unit movement speed"),
            ("attack_bonus_nearby", "Attack bonus per nearby ally"),
            ("nearby_bonus_count", "Max nearby allies for bonus"),
            ("damage_reflect_percent", "Reflects percentage of melee damage"),
            ("bonus_hp_nearby", "HP bonus per nearby ally"),
            ("nearby_hp_bonus_count", "Max nearby allies for HP bonus"),
            ("transform_hp", "Transformed unit HP"),
            ("transform_attack", "Transformed unit attack"),
            ("transform_melee_armor", "Transformed unit melee armor"),
            ("transform_pierce_armor", "Transformed unit pierce armor"),
            ("transform_attack_speed", "Transformed unit attack speed"),
            ("transform_attack_delay", "Transformed unit attack delay"),
            ("transform_movement_speed", "Transformed unit movement speed"),
        ]
        # Also store JSON-valued properties (attacks/armors for dismount/transform)
        for json_prop in (
            "dismount_attacks_json",
            "dismount_armors_json",
            "transform_attacks_json",
            "transform_armors_json",
        ):
            val = combat_props.get(json_prop)
            if val:
                cursor.execute(
                    """INSERT INTO ref_special_effects
                       (ref_unit_id, property_name, property_value)
                       VALUES (?, ?, ?)""",
                    (ref_unit_id, json_prop, val),
                )
        for prop_name, desc in special_props:
            val = combat_props.get(prop_name, 0)
            if val and val != 0:
                # Determine source
                source = "extracted_data"
                base_slug = unit_slug
                for bs in UNIQUE_COMBAT_PROPERTIES:
                    if unit_slug == bs or unit_slug.startswith(bs + "_"):
                        if prop_name in UNIQUE_COMBAT_PROPERTIES[bs]:
                            source = "UNIQUE_COMBAT_PROPERTIES"
                        base_slug = bs
                        break
                civ_key = (civ_name, unit_slug)
                if (
                    civ_key in CIV_COMBAT_PROPERTIES
                    and prop_name in CIV_COMBAT_PROPERTIES[civ_key]
                ):
                    source = "CIV_COMBAT_PROPERTIES"
                else:
                    # For unique units with civ suffix, try base slug matching
                    for civ, civ_base_slug in CIV_COMBAT_PROPERTIES:
                        if civ == civ_name and unit_slug.startswith(
                            civ_base_slug + "_"
                        ):
                            if prop_name in CIV_COMBAT_PROPERTIES[(civ, civ_base_slug)]:
                                source = "CIV_COMBAT_PROPERTIES"
                            break
                cursor.execute(
                    "INSERT INTO ref_special_effects (ref_unit_id, property_name, property_value, source, description) VALUES (?,?,?,?,?)",
                    (ref_unit_id, prop_name, str(val), source, desc),
                )

        # Projectile data
        extra_proj = combat_props.get("extra_projectiles", 0)
        proj_speed = combat_props.get("projectile_speed", 0)
        splash = combat_props.get("splash_radius", 0)
        is_siege = combat_props.get("is_siege_projectile", 0)
        total_proj = unit_data.get("total_projectiles", 1)

        if total_proj > 0 or proj_speed > 0:
            cursor.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, projectile_count, projectile_speed, blast_radius, is_siege_projectile) VALUES (?,?,?,?,?,?)",
                (ref_unit_id, "primary", int(total_proj), proj_speed, splash, is_siege),
            )
        if extra_proj > 0:
            extra_atk_json = combat_props.get("extra_projectile_attacks_json")
            cursor.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, projectile_count, projectile_speed, attacks_json, blast_radius, is_siege_projectile) VALUES (?,?,?,?,?,?,?)",
                (
                    ref_unit_id,
                    "extra",
                    int(extra_proj),
                    proj_speed,
                    extra_atk_json,
                    splash,
                    is_siege,
                ),
            )

        # Charge projectile data (Fire Lancer, Fire Archer, etc.)
        charge_proj_count = combat_props.get("charge_projectile_count", 0)
        charge_proj_atk_json = combat_props.get("charge_projectile_attacks_json")
        charge_proj_speed = combat_props.get("charge_projectile_speed", 0)
        if charge_proj_count > 0 and charge_proj_atk_json:
            cursor.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, projectile_count, projectile_speed, attacks_json, blast_radius, is_siege_projectile) VALUES (?,?,?,?,?,?,?)",
                (
                    ref_unit_id,
                    "charge",
                    int(charge_proj_count),
                    charge_proj_speed,
                    charge_proj_atk_json,
                    0,
                    0,
                ),
            )

        # Update ref_units with combat properties (inline columns for direct sim access)
        _has_transform = combat_props.get("transform_hp") or combat_props.get(
            "hp_transform_threshold"
        )
        cursor.execute(
            """UPDATE ref_units SET
               extra_projectiles=?, extra_projectile_attacks_json=?,
               first_attack_extra_projectiles=?,
               charge_projectile_count=?, charge_projectile_attacks_json=?,
               charge_projectile_speed=?, charge_attack_range=?, charge_ignores_armor=?,
               ignores_melee_armor=?, ignores_pierce_armor=?,
               trample_percent=?, trample_radius=?, trample_flat_damage=?,
               bonus_damage_reduction=?,
               splash_on_hit_radius=?, splash_on_hit_fraction=?,
               dodge_shield_max=?, dodge_shield_recharge=?,
               bleed_dps=?, bleed_duration=?,
               block_first_melee=?, attack_bonus_per_kill=?,
               hp_transform_threshold=?, hp_regen=?, pass_through_percent=?,
               pop_space=?, armor_strip_per_hit=?,
               charge_attack_melee=?, charge_recharge_time=?,
               damage_reflect_percent=?,
               splash_radius=?, is_siege_projectile=?,
               dismount_unit_id=?,
               dismount_hp=?, dismount_attack=?,
               dismount_melee_armor=?, dismount_pierce_armor=?,
               dismount_attack_speed=?, dismount_attack_delay=?,
               dismount_movement_speed=?,
               dismount_attacks_json=?, dismount_armors_json=?,
               transform_hp=?, transform_attack=?,
               transform_melee_armor=?, transform_pierce_armor=?,
               transform_attack_speed=?, transform_attack_delay=?,
               transform_movement_speed=?,
               transform_attacks_json=?, transform_armors_json=?
               WHERE id=?""",
            (
                combat_props.get("extra_projectiles", 0),
                combat_props.get("extra_projectile_attacks_json"),
                combat_props.get("first_attack_extra_projectiles", 0),
                combat_props.get("charge_projectile_count", 0),
                combat_props.get("charge_projectile_attacks_json"),
                combat_props.get("charge_projectile_speed", 0),
                combat_props.get("charge_attack_range", 0),
                combat_props.get("charge_ignores_armor", 0),
                combat_props.get("ignores_melee_armor", 0),
                combat_props.get("ignores_pierce_armor", 0),
                combat_props.get("trample_percent", 0),
                combat_props.get("trample_radius", 0),
                combat_props.get("trample_flat_damage", 0),
                combat_props.get("bonus_damage_reduction", 0),
                combat_props.get("splash_on_hit_radius", 0),
                combat_props.get("splash_on_hit_fraction", 1.0),
                combat_props.get("dodge_shield_max", 0),
                combat_props.get("dodge_shield_recharge", 0),
                combat_props.get("bleed_dps", 0),
                combat_props.get("bleed_duration", 0),
                combat_props.get("block_first_melee", 0),
                combat_props.get("attack_bonus_per_kill", 0),
                combat_props.get("hp_transform_threshold", 0),
                combat_props.get("hp_regen", 0),
                combat_props.get("pass_through_percent", 0),
                combat_props.get("pop_space", 1.0),
                combat_props.get("armor_strip_per_hit", 0),
                combat_props.get("charge_attack_melee", 0),
                combat_props.get("charge_recharge_time", 0),
                combat_props.get("damage_reflect_percent", 0),
                combat_props.get("splash_radius", 0),
                combat_props.get("is_siege_projectile", 0),
                combat_props.get("dismount_unit_id", 0),
                int(combat_props["dismount_hp"])
                if combat_props.get("dismount_hp")
                else None,
                int(combat_props["dismount_attack"])
                if combat_props.get("dismount_hp")
                else None,
                int(combat_props.get("dismount_melee_armor", 0))
                if combat_props.get("dismount_hp")
                else None,
                int(combat_props.get("dismount_pierce_armor", 0))
                if combat_props.get("dismount_hp")
                else None,
                combat_props.get("dismount_attack_speed")
                if combat_props.get("dismount_hp")
                else None,
                combat_props.get("dismount_attack_delay")
                if combat_props.get("dismount_hp")
                else None,
                combat_props.get("dismount_movement_speed")
                if combat_props.get("dismount_hp")
                else None,
                combat_props.get("dismount_attacks_json"),
                combat_props.get("dismount_armors_json"),
                int(combat_props["transform_hp"])
                if _has_transform and combat_props.get("transform_hp")
                else None,
                int(combat_props.get("transform_attack", 0))
                if _has_transform and combat_props.get("transform_hp")
                else None,
                int(combat_props.get("transform_melee_armor", 0))
                if _has_transform and combat_props.get("transform_hp")
                else None,
                int(combat_props.get("transform_pierce_armor", 0))
                if _has_transform and combat_props.get("transform_hp")
                else None,
                combat_props.get("transform_attack_speed")
                if _has_transform and combat_props.get("transform_hp")
                else None,
                combat_props.get("transform_attack_delay")
                if _has_transform and combat_props.get("transform_hp")
                else None,
                combat_props.get("transform_movement_speed")
                if _has_transform and combat_props.get("transform_hp")
                else None,
                combat_props.get("transform_attacks_json"),
                combat_props.get("transform_armors_json"),
                ref_unit_id,
            ),
        )

        return ref_unit_id

    # Process all units for all 13 civs
    print("\nGenerating reference database...")
    for civ_name in ORIGINAL_13_CIVS:
        print(f"  {civ_name}...")
        disabled_techs = analyzer.get_disabled_techs(civ_name)

        # Castle Age units
        for slug, config in CASTLE_UNITS.items():
            if civ_name not in config.get("civ_only", [civ_name]):
                continue
            result = analyzer.calculate_unit_stats_for_civ(civ_name, config, CASTLE_AGE)
            if not result["has_unit"]:
                continue
            final_unit_id = result.get("unit_id", config["base_id"])
            unit_data = analyzer.get_unit(final_unit_id)
            if not unit_data:
                continue
            process_unit_audited(
                civ_name,
                final_unit_id,
                config["unit_class"],
                result["unit_name"],
                slug,
                "standard",
                "Castle",
                CASTLE_AGE,
                unit_data,
            )

        # Imperial Age units
        for slug, config in IMPERIAL_UNITS.items():
            if civ_name not in config.get("civ_only", [civ_name]):
                continue
            result = analyzer.calculate_unit_stats_for_civ(
                civ_name, config, IMPERIAL_AGE
            )
            if not result["has_unit"]:
                continue
            final_unit_id = result.get("unit_id", config["base_id"])
            unit_data = analyzer.get_unit(final_unit_id)
            if not unit_data:
                continue
            process_unit_audited(
                civ_name,
                final_unit_id,
                config["unit_class"],
                result["unit_name"],
                slug,
                "standard",
                "Imperial",
                IMPERIAL_AGE,
                unit_data,
            )

        # Unique units
        if civ_name in UNIQUE_UNITS:
            for uu_config in UNIQUE_UNITS[civ_name]:
                # Build effective unit_class (tuple if extra_unit_classes present)
                uc = uu_config["unit_class"]
                extra = uu_config.get("extra_unit_classes", [])
                effective_class = (uc, *extra) if extra else uc

                # Castle Age (base version)
                base_id = uu_config["base_id"]
                unit_data = analyzer.get_unit(base_id)
                if unit_data:
                    slug = (
                        uu_config["display_name"]
                        .lower()
                        .replace(" ", "_")
                        .replace("-", "_")
                    )
                    excluded = uu_config.get("excluded_tech_ids")
                    process_unit_audited(
                        civ_name,
                        base_id,
                        effective_class,
                        uu_config["display_name"],
                        f"{slug}_{civ_name.lower()}",
                        "unique",
                        "Castle",
                        CASTLE_AGE,
                        unit_data,
                        excluded_tech_ids=excluded,
                    )

                # Imperial Age (elite version, or same base unit with Imp techs)
                elite_id = uu_config.get("elite_id")
                if elite_id:
                    elite_data = analyzer.get_unit(elite_id)
                    if elite_data:
                        elite_name = uu_config.get(
                            "elite_name", f"Elite {uu_config['display_name']}"
                        )
                        elite_slug = f"elite_{slug}_{civ_name.lower()}"
                        process_unit_audited(
                            civ_name,
                            elite_id,
                            effective_class,
                            elite_name,
                            elite_slug,
                            "unique",
                            "Imperial",
                            IMPERIAL_AGE,
                            elite_data,
                            excluded_tech_ids=excluded,
                        )
                elif unit_data:
                    # No elite version — show base unit in Imperial with Imp techs
                    process_unit_audited(
                        civ_name,
                        base_id,
                        effective_class,
                        uu_config["display_name"],
                        f"{slug}_{civ_name.lower()}",
                        "unique",
                        "Imperial",
                        IMPERIAL_AGE,
                        unit_data,
                        excluded_tech_ids=excluded,
                    )

    conn.commit()

    # Count records
    cursor.execute("SELECT COUNT(*) FROM ref_units")
    unit_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ref_techs_applied")
    tech_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ref_stat_chain")
    chain_count = cursor.fetchone()[0]

    print(f"\n  Reference DB created at: {ref_db_path}")
    print(f"  Units: {unit_count}")
    print(f"  Techs applied: {tech_count}")
    print(f"  Stat chain steps: {chain_count}")

    # Print detailed display
    print_reference_display(conn, armor_class_names)

    conn.close()


def print_reference_display(conn, armor_class_names):
    """Print the detailed per-stat breakdown for all units."""
    cursor = conn.cursor()

    for civ_name in ORIGINAL_13_CIVS:
        print(f"\n{'=' * 80}")
        print(f"=== {civ_name} ===")
        print(f"{'=' * 80}")

        cursor.execute(
            "SELECT * FROM ref_units WHERE civ_name=? ORDER BY age, unit_type, unit_name",
            (civ_name,),
        )
        columns = [desc[0] for desc in cursor.description]
        units = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for unit in units:
            ref_id = unit["id"]

            # Get techs applied for this unit
            cursor.execute(
                """SELECT tech_name, tech_type, building, effect_description, age_available
                   FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
                (ref_id,),
            )
            techs = cursor.fetchall()

            # Get stat chain
            cursor.execute(
                """SELECT tech_name, tech_type, hp, attack, melee_armor, pierce_armor,
                          speed, range_val, reload_time, accuracy, los, train_time,
                          cost_food, cost_wood, cost_gold, attacks_json, armors_json
                   FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
                (ref_id,),
            )
            chain = cursor.fetchall()

            # Get special effects
            cursor.execute(
                "SELECT property_name, property_value, source FROM ref_special_effects WHERE ref_unit_id=?",
                (ref_id,),
            )
            specials = cursor.fetchall()

            # Get projectiles
            cursor.execute(
                "SELECT projectile_type, projectile_count, projectile_speed, blast_radius, is_siege_projectile, attacks_json FROM ref_projectiles WHERE ref_unit_id=?",
                (ref_id,),
            )
            projectiles = cursor.fetchall()

            # Determine main attack class
            main_atk_class = 3 if unit["is_ranged"] else 4

            # Build upgrade descriptions per stat
            stat_upgrades = _build_stat_upgrade_descriptions(
                chain, techs, armor_class_names, main_atk_class
            )

            print(
                f"\nUnit: {unit['unit_name']} | Age: {unit['age']} | Class: {unit.get('unit_class_name', '')} ({unit.get('unit_class', '')})"
            )

            # HP
            _print_stat_line(
                "HP", unit["base_hp"], unit["final_hp"], stat_upgrades.get("hp", [])
            )

            # Attack (main class) - use attacks_json for correct ranged/melee tracking
            base_attacks = (
                json.loads(unit["base_attacks_json"])
                if unit["base_attacks_json"]
                else {}
            )
            final_attacks = (
                json.loads(unit["final_attacks_json"])
                if unit["final_attacks_json"]
                else {}
            )
            base_main_atk = base_attacks.get(str(main_atk_class), 0)
            final_main_atk = final_attacks.get(str(main_atk_class), 0)
            main_cls_name = armor_class_names.get(
                main_atk_class, f"class {main_atk_class}"
            )
            atk_label = f"Attack (class {main_atk_class}: {main_cls_name})"
            _print_stat_line(
                atk_label,
                base_main_atk,
                final_main_atk,
                stat_upgrades.get("attack", []),
            )

            # Bonus attack classes (base_attacks/final_attacks already parsed above)
            bonus_atk_parts = []
            for cls_id_str in sorted(
                set(list(base_attacks.keys()) + list(final_attacks.keys()))
            ):
                cls_id = int(cls_id_str)
                if cls_id == main_atk_class:
                    continue  # Skip main attack class
                cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
                base_val = base_attacks.get(
                    cls_id_str, base_attacks.get(str(cls_id), 0)
                )
                final_val = final_attacks.get(
                    cls_id_str, final_attacks.get(str(cls_id), 0)
                )
                if base_val != 0 or final_val != 0:
                    bonus_atk_parts.append(
                        f"class {cls_id} {cls_name}: base={base_val}, final={final_val}"
                    )
            if bonus_atk_parts:
                print(f"  Bonus Atk: {' | '.join(bonus_atk_parts)}")

            # MA
            _print_stat_line(
                "MA",
                unit["base_melee_armor"],
                unit["final_melee_armor"],
                stat_upgrades.get("melee_armor", []),
            )

            # PA
            _print_stat_line(
                "PA",
                unit["base_pierce_armor"],
                unit["final_pierce_armor"],
                stat_upgrades.get("pierce_armor", []),
            )

            # All armor classes
            base_armors = (
                json.loads(unit["base_armors_json"]) if unit["base_armors_json"] else {}
            )
            final_armors = (
                json.loads(unit["final_armors_json"])
                if unit["final_armors_json"]
                else {}
            )
            armor_parts = []
            for cls_id_str in sorted(final_armors.keys(), key=lambda x: int(x)):
                cls_id = int(cls_id_str)
                cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
                val = final_armors[cls_id_str]
                armor_parts.append(f"class {cls_id} {cls_name}: {val}")
            if armor_parts:
                print(f"  All Armor: {' | '.join(armor_parts)}")

            # Range
            _print_stat_line(
                "Range",
                unit["base_range"],
                unit["final_range"],
                stat_upgrades.get("range", []),
            )

            # Speed
            _print_stat_line(
                "Speed",
                unit["base_speed"],
                unit["final_speed"],
                stat_upgrades.get("speed", []),
            )

            # Reload
            _print_stat_line(
                "Reload",
                unit["base_reload_time"],
                unit["final_reload_time"],
                stat_upgrades.get("reload_time", []),
            )

            # Accuracy
            _print_stat_line(
                "Accuracy",
                unit["base_accuracy"],
                unit["final_accuracy"],
                stat_upgrades.get("accuracy", []),
            )

            # LOS
            _print_stat_line(
                "LOS", unit["base_los"], unit["final_los"], stat_upgrades.get("los", [])
            )

            # Attack delay (not upgradeable)
            print(f"  Atk Delay: {unit.get('base_attack_delay', 0)}")

            # Projectile
            for p in projectiles:
                p_type, p_count, p_speed, p_blast, p_siege, p_atk_json = p
                parts = [f"type={p_type}", f"count={p_count}", f"speed={p_speed}"]
                if p_blast:
                    parts.append(f"blast={p_blast}")
                if p_siege:
                    parts.append("siege=yes")
                if p_atk_json:
                    # Show attack classes with names
                    atk_dict = json.loads(p_atk_json)
                    atk_parts = []
                    for cls_id_str, amount in sorted(
                        atk_dict.items(), key=lambda x: x[1], reverse=True
                    ):
                        cls_name = armor_class_names.get(
                            int(cls_id_str), f"class {cls_id_str}"
                        )
                        atk_parts.append(f"{cls_name}={amount}")
                    parts.append(f"attacks=[{', '.join(atk_parts)}]")
                print(f"  Projectile: {', '.join(parts)}")

            # Train time
            _print_stat_line(
                "Train Time",
                unit["base_train_time"],
                unit["final_train_time"],
                stat_upgrades.get("train_time", []),
            )

            # Cost
            base_cost = _format_cost(
                unit["base_cost_food"], unit["base_cost_wood"], unit["base_cost_gold"]
            )
            final_cost = _format_cost(
                unit.get("final_cost_food", unit["base_cost_food"]),
                unit.get("final_cost_wood", unit["base_cost_wood"]),
                unit.get("final_cost_gold", unit["base_cost_gold"]),
            )
            cost_upgrades = stat_upgrades.get("cost", [])
            if cost_upgrades:
                print(
                    f"  Cost:      Base={base_cost} | Upgrades: {', '.join(cost_upgrades)} | Final={final_cost}"
                )
            else:
                print(
                    f"  Cost:      Base={base_cost} | Upgrades: (none) | Final={final_cost}"
                )

            # Special effects
            if specials:
                special_strs = [f"{name}={val} ({src})" for name, val, src in specials]
                print(f"  Special:   {', '.join(special_strs)}")

            # Unique tech effects (from techs_applied with type unique_tech)
            ut_list = [t for t in techs if t[1] == "unique_tech"]
            if ut_list:
                ut_strs = [f"{t[0]} ({t[3]})" for t in ut_list]
                print(f"  Unique Techs: {'; '.join(ut_strs)}")


def _build_stat_upgrade_descriptions(chain, techs, armor_class_names, main_atk_class=4):
    """Build per-stat upgrade descriptions by comparing consecutive chain entries.

    main_atk_class: 3 for ranged (Base Pierce), 4 for melee (Base Melee).
    """
    upgrades = {}  # stat_name -> [change_str, ...]

    if len(chain) < 2:
        return upgrades

    # chain columns: tech_name, tech_type, hp, attack, ma, pa, speed, range, reload,
    #                accuracy, los, train_time, cost_food, cost_wood, cost_gold, attacks_json, armors_json
    stat_indices = {
        "hp": 2,
        "melee_armor": 4,
        "pierce_armor": 5,
        "speed": 6,
        "range": 7,
        "reload_time": 8,
        "accuracy": 9,
        "los": 10,
        "train_time": 11,
    }

    # Match chain entries to techs for building info
    tech_buildings = {}
    for t in techs:
        tech_buildings[t[0]] = t[2]  # tech_name -> building

    for i in range(1, len(chain)):
        prev = chain[i - 1]
        curr = chain[i]
        tech_name = curr[0]
        tech_type = curr[1]
        building = tech_buildings.get(tech_name, "N/A")

        # Track main attack class from attacks_json (column index 15)
        prev_attacks = json.loads(prev[15]) if prev[15] else {}
        curr_attacks = json.loads(curr[15]) if curr[15] else {}
        prev_main_atk = prev_attacks.get(
            str(main_atk_class), prev_attacks.get(main_atk_class, 0)
        )
        curr_main_atk = curr_attacks.get(
            str(main_atk_class), curr_attacks.get(main_atk_class, 0)
        )
        if abs(curr_main_atk - prev_main_atk) > 0.001:
            diff = curr_main_atk - prev_main_atk
            sign = "+" if diff > 0 else ""
            change = f"{sign}{diff:.3g} {building} ({tech_name})"
            upgrades.setdefault("attack", []).append(change)

        for stat_name, idx in stat_indices.items():
            old_val = prev[idx] or 0
            new_val = curr[idx] or 0
            if abs(new_val - old_val) > 0.001:
                diff = new_val - old_val
                # Multiplicative check
                if old_val != 0 and stat_name in (
                    "reload_time",
                    "speed",
                    "hp",
                    "train_time",
                ):
                    ratio = new_val / old_val
                    if (
                        abs(ratio - round(ratio)) > 0.001
                        and abs(diff - round(diff)) > 0.01
                    ):
                        change = f"x{ratio:.3g} {building} ({tech_name})"
                        upgrades.setdefault(stat_name, []).append(change)
                        continue

                sign = "+" if diff > 0 else ""
                change = f"{sign}{diff:.3g} {building} ({tech_name})"
                upgrades.setdefault(stat_name, []).append(change)

        # Cost changes
        cost_changed = False
        cost_parts = []
        for ci, cname in [(12, "food"), (13, "wood"), (14, "gold")]:
            old_val = prev[ci] or 0
            new_val = curr[ci] or 0
            if abs(new_val - old_val) > 0.01:
                cost_changed = True
                diff = new_val - old_val
                if old_val != 0:
                    ratio = new_val / old_val
                    if abs(ratio - round(ratio)) > 0.001:
                        cost_parts.append(f"x{ratio:.3g} {cname}")
                        continue
                sign = "+" if diff > 0 else ""
                cost_parts.append(f"{sign}{diff:.3g} {cname}")
        if cost_changed:
            change = f"{', '.join(cost_parts)} {building} ({tech_name})"
            upgrades.setdefault("cost", []).append(change)

    return upgrades


def _print_stat_line(label, base_val, final_val, upgrade_list):
    """Print a single stat line in Base | Upgrades | Final format."""
    label_padded = f"{label}:".ljust(12)
    if base_val is None:
        base_val = 0
    if final_val is None:
        final_val = base_val

    # Format values
    if isinstance(base_val, float) and base_val == int(base_val):
        base_str = str(int(base_val))
    else:
        base_str = f"{base_val:.3g}" if isinstance(base_val, float) else str(base_val)

    if isinstance(final_val, float) and final_val == int(final_val):
        final_str = str(int(final_val))
    else:
        final_str = (
            f"{final_val:.3g}" if isinstance(final_val, float) else str(final_val)
        )

    if upgrade_list:
        upgrades_str = ", ".join(upgrade_list)
        print(
            f"  {label_padded} Base={base_str} | Upgrades: {upgrades_str} | Final={final_str}"
        )
    else:
        print(
            f"  {label_padded} Base={base_str} | Upgrades: (none) | Final={final_str}"
        )


def _format_cost(food, wood, gold):
    """Format cost as string like '25W 45G'."""
    parts = []
    if food and food > 0:
        parts.append(f"{int(food)}F")
    if wood and wood > 0:
        parts.append(f"{int(wood)}W")
    if gold and gold > 0:
        parts.append(f"{int(gold)}G")
    return " ".join(parts) if parts else "Free"


def main():
    print("AoE2 Reference Database Generator")
    print("=" * 60)
    print("Reading data directly from JSON files...")

    analyzer = UnitAnalyzer()
    print(f"  Loaded {len(analyzer.units)} units")
    print(f"  Loaded {len(analyzer.civs)} civilizations")
    print(f"  Loaded {len(analyzer.techs)} technologies")

    generate_reference_database(analyzer)


if __name__ == "__main__":
    main()
