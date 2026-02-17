"""
Best units logic: civ power units (pre-computed) + matchup recommendations (on-the-fly).
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
POWER_UNITS_PATH = os.path.join(os.path.dirname(__file__), "civ_power_units.json")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_unit_stats(conn, civ_name, unit_slug, age="Imperial"):
    """Fetch summary stats for a unit from ref_units."""
    rc = conn.cursor()
    rc.execute(
        """SELECT unit_name, final_hp, final_attack, final_melee_armor,
                  final_pierce_armor, final_speed, final_range,
                  final_cost_food, final_cost_wood, final_cost_gold
           FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?""",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        return None, None
    stats = {
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "speed": row["final_speed"],
        "range": row["final_range"] or 0,
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
    }
    return row["unit_name"], stats


# Role definitions: (role_key, line_slugs, score_type)
ROLE_DEFS = [
    ("cavalry", ["stable"], "stable_effectiveness"),
    ("ranged", ["archer", "cav_archer", "scorpion", "gunpowder"], "ranged_effectiveness"),
    ("infantry", ["militia", "shock_infantry"], "militia_value"),
    ("anti_cavalry", ["spear", "militia"], "anti_cav_value"),
    ("siege", ["siege"], "anti_building_score"),
]

# Trash role handled separately (needs gold cost filter)
TRASH_LINES = ["stable", "militia", "spear", "shock_infantry", "archer", "cav_archer",
               "scorpion", "gunpowder", "skirmisher"]


def _classify_strength(rank, median_delta):
    """Classify a unit's strength tier based on rank and median_delta."""
    if rank is not None and rank <= 5 and median_delta is not None and median_delta > 20:
        return "signature"
    if median_delta is not None and median_delta > 10:
        return "strong"
    if median_delta is not None and median_delta < -10:
        return "weak"
    return "average"


# Techs that meaningfully impact combat — used for "missing techs" tooltip
IMPACTFUL_TECHS = {
    # Blacksmith - melee
    "Forging", "Iron casting", "Blast Furnace",
    "Scale Mail Armor", "Chain Mail Armor", "Plate Mail Armor",
    # Blacksmith - ranged
    "Fletching", "Bodkin Arrow", "Bracer",
    "Padded Archer Armor", "Leather Archer Armor", "Ring Archer Armor",
    # Blacksmith - cavalry
    "Scale Barding Armor", "Chain Barding Armor", "Plate Barding Armor",
    # Stable
    "Bloodlines", "Husbandry",
    # Barracks
    "Squires", "Arson", "Gambesons",
    # Castle
    "Conscription",
    # University
    "Ballistics", "Chemistry", "Siege Engineers",
    # Archery Range
    "Thumb Ring", "Parthian Tactics",
}

# Special effect labels for tooltip display
_EFFECT_LABELS = {
    "trample_percent": "Trample {v:.0f}%",
    "ignores_melee_armor": "Ignores melee armor",
    "ignores_pierce_armor": "Ignores pierce armor",
    "bleed_dps": "Bleed {v:.0f} dps",
    "dodge_shield_max": "Dodge shield ({v:.0f} charges)",
    "block_first_melee": "Blocks first melee hit",
    "hp_regen": "+{v:.1f} HP/min regen",
    "charge_attack_melee": "Charge +{v:.0f} melee",
    "attack_bonus_per_kill": "+{v:.0f} attack per kill",
    "bonus_damage_reduction": "{v:.0f}% bonus damage reduction",
    "splash_radius": "Splash damage ({v:.1f} radius)",
    "extra_projectiles": "+{v:.0f} extra projectiles",
    "splash_on_hit_radius": "Splash on hit ({v:.1f} radius)",
    "armor_strip_per_hit": "Strips {v:.0f} armor/hit",
    "pass_through_percent": "Pass-through damage",
    "hp_per_kill": "+{v:.0f} HP per kill",
}

# Scout line slugs for cavalry narrative
SCOUT_SLUGS = {"hussar", "light_cavalry", "winged_hussar"}

# Teuton Paladin speed — threshold for "strong but lacks mobility"
SLOW_CAV_THRESHOLD = 1.35


def _build_reference_techs(conn, age="Imperial"):
    """Build a dict: unit_slug -> set of standard tech names available to ANY civ.

    This is the 'full tech tree' reference. For each unit_slug at the given age,
    we collect all standard techs that appear in ref_techs_applied for any civ's
    version of that unit, filtered to IMPACTFUL_TECHS only.
    """
    rc = conn.cursor()
    rc.execute(
        """SELECT ru.unit_slug, rta.tech_name
           FROM ref_units ru
           JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
           WHERE ru.age = ? AND rta.tech_name NOT LIKE 'C-Bonus%'
             AND rta.tech_name NOT LIKE '%UT%'""",
        (age,),
    )
    ref = {}
    for row in rc.fetchall():
        slug = row["unit_slug"]
        tech = row["tech_name"]
        if tech in IMPACTFUL_TECHS:
            ref.setdefault(slug, set()).add(tech)
    return ref


def _get_unit_techs_and_bonuses(conn, civ_name, unit_slug, age="Imperial"):
    """Get missing techs, bonus abilities, and special effects for a unit.

    Returns (standard_techs: list[str], bonus_abilities: list[str], special_effects: list[str])
    """
    rc = conn.cursor()

    # Get ref_unit_id
    rc.execute(
        "SELECT id FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        return [], [], []
    ref_unit_id = row["id"]

    # Get all techs applied to this unit
    rc.execute(
        "SELECT tech_name FROM ref_techs_applied WHERE ref_unit_id=?",
        (ref_unit_id,),
    )
    civ_techs = {r["tech_name"] for r in rc.fetchall()}

    # Extract bonus abilities from civ bonuses and unique techs
    bonus_abilities = []
    for tech in sorted(civ_techs):
        if tech.startswith("C-Bonus, "):
            bonus_abilities.append(tech[len("C-Bonus, "):])
        elif " UT" in tech or tech.endswith(" UT"):
            bonus_abilities.append(tech)

    # Get special effects
    rc.execute(
        "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
        (ref_unit_id,),
    )
    special_effects = []
    for r in rc.fetchall():
        pname = r["property_name"]
        label = _EFFECT_LABELS.get(pname)
        if not label:
            continue
        try:
            v = float(r["property_value"])
        except (ValueError, TypeError):
            continue
        if v == 0:
            continue
        # Boolean-style effects (1.0 = yes)
        if pname in ("ignores_melee_armor", "ignores_pierce_armor",
                      "block_first_melee", "pass_through_percent"):
            special_effects.append(label.split("{")[0].strip())
        else:
            special_effects.append(label.format(v=v))

    # Standard techs only (for missing_techs comparison)
    standard_techs = [t for t in sorted(civ_techs) if not t.startswith("C-Bonus") and " UT" not in t]

    return standard_techs, bonus_abilities, special_effects


def _compute_missing_techs(civ_standard_techs, reference_techs_for_slug):
    """Compute which impactful techs this civ is missing vs the reference."""
    if not reference_techs_for_slug:
        return []
    missing = reference_techs_for_slug - set(civ_standard_techs)
    return sorted(missing)


def _batch_fetch_civ_tech_data(conn, civ_name, age="Imperial"):
    """Batch-fetch all techs and special effects for a civ in one pass.

    Returns two dicts keyed by unit_slug:
      techs_by_slug: {slug: [tech_name, ...]}
      effects_by_slug: {slug: [(property_name, property_value), ...]}
    """
    rc = conn.cursor()

    # All techs for this civ's units at this age
    rc.execute(
        """SELECT ru.unit_slug, rta.tech_name
           FROM ref_units ru
           JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
           WHERE ru.civ_name = ? AND ru.age = ?""",
        (civ_name, age),
    )
    techs_by_slug = {}
    for row in rc.fetchall():
        techs_by_slug.setdefault(row["unit_slug"], []).append(row["tech_name"])

    # All special effects for this civ's units at this age
    rc.execute(
        """SELECT ru.unit_slug, rse.property_name, rse.property_value
           FROM ref_units ru
           JOIN ref_special_effects rse ON rse.ref_unit_id = ru.id
           WHERE ru.civ_name = ? AND ru.age = ?""",
        (civ_name, age),
    )
    effects_by_slug = {}
    for row in rc.fetchall():
        effects_by_slug.setdefault(row["unit_slug"], []).append(
            (row["property_name"], row["property_value"])
        )

    return techs_by_slug, effects_by_slug


def _parse_techs_and_bonuses(techs_list, effects_list):
    """Parse raw tech/effect lists into (standard_techs, bonus_abilities, special_effects).

    Args:
        techs_list: list of tech_name strings from ref_techs_applied
        effects_list: list of (property_name, property_value) tuples from ref_special_effects
    """
    civ_techs = set(techs_list or [])

    # Bonus abilities from civ bonuses and unique techs
    bonus_abilities = []
    for tech in sorted(civ_techs):
        if tech.startswith("C-Bonus, "):
            bonus_abilities.append(tech[len("C-Bonus, "):])
        elif " UT" in tech or tech.endswith(" UT"):
            bonus_abilities.append(tech)

    # Special effects
    special_effects = []
    for pname, pval in (effects_list or []):
        label = _EFFECT_LABELS.get(pname)
        if not label:
            continue
        try:
            v = float(pval)
        except (ValueError, TypeError):
            continue
        if v == 0:
            continue
        if pname in ("ignores_melee_armor", "ignores_pierce_armor",
                      "block_first_melee", "pass_through_percent"):
            special_effects.append(label.split("{")[0].strip())
        else:
            special_effects.append(label.format(v=v))

    # Standard techs (for missing_techs comparison)
    standard_techs = [t for t in sorted(civ_techs) if not t.startswith("C-Bonus") and " UT" not in t]

    return standard_techs, bonus_abilities, special_effects


def _build_unit_entry(row, civ_name, conn, db_age, reference_techs, techs_by_slug, effects_by_slug):
    """Build a single unit entry dict with stats, techs, bonuses, and effects."""
    slug = row["unit_slug"]
    unit_name, stats = _fetch_unit_stats(conn, civ_name, slug, db_age)
    standard_techs, bonus_abilities, special_effects = _parse_techs_and_bonuses(
        techs_by_slug.get(slug, []), effects_by_slug.get(slug, [])
    )
    missing = _compute_missing_techs(standard_techs, reference_techs.get(slug, set()))
    strength = _classify_strength(row["rank"], row["median_delta"])
    speed = stats["speed"] if stats else 0

    return {
        "unit_slug": slug,
        "unit_name": unit_name or slug,
        "line_slug": row["line_slug"],
        "score": round(row["score_value"], 1),
        "rank": row["rank"],
        "median_delta": round(row["median_delta"], 1),
        "strength": strength,
        "is_signature": strength == "signature",
        "stats": stats,
        "speed": speed,
        "missing_techs": missing,
        "bonus_abilities": bonus_abilities,
        "special_effects": special_effects,
    }


def _build_role_dict(all_units, role_key):
    """Build the role-level dict from a list of unit entries."""
    if not all_units:
        return None
    best = all_units[0]
    narrative_key = _determine_narrative_key(role_key, all_units)
    above_avg = [u for u in all_units if u["median_delta"] > 0]
    has_sig = any(u["is_signature"] for u in all_units)
    return {
        # Backward-compat fields from best unit
        "unit_slug": best["unit_slug"],
        "unit_name": best["unit_name"],
        "line_slug": best["line_slug"],
        "score": best["score"],
        "rank": best["rank"],
        "median_delta": best["median_delta"],
        "is_signature": best["is_signature"],
        "strength": best["strength"],
        "stats": None,  # stats now per all_units entry only
        # New expanded fields
        "all_units": all_units,
        "narrative_key": narrative_key,
        "above_avg_count": len(above_avg),
        "total_count": len(all_units),
        "has_signature": has_sig,
        "best_unit": best["unit_slug"],
    }


def _determine_narrative_key(role_key, all_units):
    """Determine the narrative key for a role based on unit analysis."""
    above_avg = [u for u in all_units if u["median_delta"] > 0]

    if role_key == "cavalry":
        above_avg_non_scout = [u for u in above_avg if u["unit_slug"] not in SCOUT_SLUGS]
        best = all_units[0] if all_units else None
        if not above_avg:
            return "cav_none"
        if above_avg and not above_avg_non_scout:
            return "cav_trash_only"
        if best and best["speed"] <= SLOW_CAV_THRESHOLD and best["median_delta"] > 0:
            return "cav_strong_slow"
        if len(above_avg) == 1:
            return "cav_one_strong"
        return "cav_all_strong"

    elif role_key == "ranged":
        if len(above_avg) >= 2:
            return "ranged_strong"
        if len(above_avg) == 1:
            return "ranged_one_strong"
        return "ranged_none"

    elif role_key == "infantry":
        if len(above_avg) >= 2:
            return "inf_strong"
        if len(above_avg) == 1:
            return "inf_one_strong"
        return "inf_none"

    elif role_key == "anti_cavalry":
        if len(above_avg) >= 2:
            return "anticav_strong"
        if len(above_avg) == 1:
            return "anticav_one_strong"
        return "anticav_weak"

    elif role_key == "trash":
        if above_avg:
            return "trash_strong"
        return "trash_weak"

    elif role_key == "siege":
        if len(above_avg) >= 2:
            return "siege_strong"
        if len(above_avg) == 1:
            return "siege_one_strong"
        return "siege_weak"

    return "unknown"


def compute_civ_power_units():
    """Pre-compute power units for all civs. Returns dict keyed by civ_name."""
    conn = _get_db()
    rc = conn.cursor()

    # Get all civ names
    rc.execute("SELECT DISTINCT civ_name FROM battle_scores ORDER BY civ_name")
    all_civs = [row["civ_name"] for row in rc.fetchall()]

    # Get trash unit slugs (gold cost = 0) from ref_units
    rc.execute(
        "SELECT DISTINCT civ_name, unit_slug FROM ref_units WHERE final_cost_gold = 0 AND age = 'Imperial'"
    )
    trash_by_civ = {}
    for row in rc.fetchall():
        trash_by_civ.setdefault(row["civ_name"], set()).add(row["unit_slug"])

    # Build reference tech sets once (for missing tech computation)
    reference_techs = _build_reference_techs(conn, "Imperial")

    result = {}

    for civ in all_civs:
        civ_data = {"imperial": None, "castle": None}

        for age_key in ["imperial"]:  # Start with imperial only
            db_age = "Imperial" if age_key == "imperial" else "Castle"
            power_units = {}

            # Batch-fetch all techs and effects for this civ (2 queries instead of N*3)
            techs_by_slug, effects_by_slug = _batch_fetch_civ_tech_data(conn, civ, db_age)

            for role_key, line_slugs, score_type in ROLE_DEFS:
                # Safe: placeholders generated from hardcoded ROLE_DEFS constants
                placeholders = ",".join("?" for _ in line_slugs)
                rc.execute(
                    f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                        FROM battle_scores
                        WHERE civ_name = ?
                          AND LOWER(age) = ?
                          AND score_type = ?
                          AND line_slug IN ({placeholders})
                        ORDER BY median_delta DESC""",
                    [civ, age_key, score_type] + line_slugs,
                )
                all_units = [
                    _build_unit_entry(row, civ, conn, db_age, reference_techs,
                                      techs_by_slug, effects_by_slug)
                    for row in rc.fetchall()
                ]
                power_units[role_key] = _build_role_dict(all_units, role_key)

            # Trash: best general_combat among zero-gold units
            civ_trash = trash_by_civ.get(civ, set())
            if civ_trash:
                trash_placeholders = ",".join("?" for _ in civ_trash)
                line_placeholders = ",".join("?" for _ in TRASH_LINES)
                rc.execute(
                    f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                        FROM battle_scores
                        WHERE civ_name = ?
                          AND LOWER(age) = ?
                          AND score_type = 'general_combat'
                          AND line_slug IN ({line_placeholders})
                          AND unit_slug IN ({trash_placeholders})
                        ORDER BY median_delta DESC""",
                    [civ, age_key] + TRASH_LINES + list(civ_trash),
                )
                all_units = [
                    _build_unit_entry(row, civ, conn, db_age, reference_techs,
                                      techs_by_slug, effects_by_slug)
                    for row in rc.fetchall()
                ]
                power_units["trash"] = _build_role_dict(all_units, "trash")
            else:
                power_units["trash"] = None

            # Build strength profile
            strength_profile = {}
            for role_key in ["cavalry", "ranged", "infantry", "anti_cavalry", "trash", "siege"]:
                entry = power_units.get(role_key)
                strength_profile[role_key] = entry["strength"] if entry else "weak"

            # Build strategic summary
            main_roles = ["cavalry", "ranged", "infantry", "anti_cavalry", "siege"]
            strong_areas = []
            weak_areas = []
            signature_areas = []
            for rk in main_roles:
                entry = power_units.get(rk)
                if not entry:
                    weak_areas.append(rk)
                    continue
                if entry.get("has_signature"):
                    signature_areas.append(rk)
                    strong_areas.append(rk)
                elif entry["strength"] in ("strong", "signature"):
                    strong_areas.append(rk)
                elif entry["strength"] == "weak":
                    weak_areas.append(rk)

            total_strong = len(strong_areas)
            if total_strong >= 3:
                summary_key = "multi_flexible"
            elif total_strong >= 1:
                summary_key = "one_area_strong"
            else:
                summary_key = "none_exceptional"

            primary_strength = strong_areas[0] if strong_areas else None

            strategic_summary = {
                "strong_areas": strong_areas,
                "weak_areas": weak_areas,
                "signature_areas": signature_areas,
                "summary_key": summary_key,
                "primary_strength": primary_strength,
            }

            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
                "strategic_summary": strategic_summary,
            }

        result[civ] = civ_data

    conn.close()
    return result


def save_civ_power_units():
    """Compute and write civ_power_units.json."""
    data = compute_civ_power_units()
    with open(POWER_UNITS_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote {POWER_UNITS_PATH} ({len(data)} civs)")
    return data


def load_civ_power_units():
    """Load pre-computed civ power units. Returns dict or None if file missing."""
    if not os.path.exists(POWER_UNITS_PATH):
        return None
    with open(POWER_UNITS_PATH, "r") as f:
        return json.load(f)


###############################################################################
# Phase B: Matchup Recommendations (on-the-fly with targeted simulation)
###############################################################################

from simulation import prepare_combat_unit, simulate_battle


def _calc_weighted_cost(food, wood, gold):
    """Resource cost with gold weighted higher."""
    cost = 0.8 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)
    return int(cost) if cost > 0 else 100


# Counter-role mapping: opponent strength -> what Civ A should query
COUNTER_MAP = {
    "cavalry": [
        # (lines_to_search, score_type, description)
        (["spear", "militia"], "anti_cav_value", "anti-cavalry specialist"),
        (["stable"], "anti_cav", "camel/cavalry counter"),
    ],
    "ranged": [
        (["stable"], "general_combat", "cavalry closes distance on ranged"),
        (["archer", "cav_archer", "scorpion", "gunpowder", "skirmisher"], "anti_archer", "anti-archer unit"),
    ],
    "infantry": [
        (["archer", "cav_archer", "scorpion", "gunpowder"], "general_combat", "ranged vs infantry"),
        (["stable"], "general_combat", "cavalry vs infantry"),
    ],
    "siege": [
        (["stable"], "general_combat", "cavalry snipes siege"),
    ],
}

# Trash pairing logic: gold_unit_line -> preferred trash partner
TRASH_PAIRING = {
    "stable": "skirmisher",       # cavalry + skirm (skirm handles halbs)
    "archer": "stable",           # archers + hussar (hussar tanks & raids)
    "cav_archer": "stable",       # cav archers + hussar
    "scorpion": "spear",          # scorpion + halbs (halbs screen from cav)
    "gunpowder": "spear",         # hand cannoneers + halbs
    "militia": "stable",          # infantry + hussar
    "spear": "skirmisher",        # spearmen + skirm
    "shock_infantry": "stable",   # shock infantry + hussar
    "skirmisher": "stable",       # skirm + hussar
    "siege": "spear",             # siege + halbs
}


def _load_combat_unit(civ_name, unit_slug, age="Imperial"):
    """Load a single combat-ready unit from ref_units."""
    conn = _get_db()
    rc = conn.cursor()
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        conn.close()
        return None

    reload_time = row["final_reload_time"] or 2.0
    attack_speed = 1.0 / reload_time if reload_time > 0 else 0.5

    combat_dict = {
        "slug": row["unit_slug"],
        "unit_name": row["unit_name"],
        "unit_category": "military",
        "paired_unit_slug": None,
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "attack_range": row["final_range"] if row["is_ranged"] else 0,
        "attack_speed": attack_speed,
        "attack_delay": row["final_attack_delay"] or 0,
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "movement_speed": row["final_speed"],
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
        "upgrade_cost_food": row["upgrade_cost_food"] or 0,
        "upgrade_cost_wood": row["upgrade_cost_wood"] or 0,
        "upgrade_cost_gold": row["upgrade_cost_gold"] or 0,
        "attacks_json": row["final_attacks_json"],
        "armors_json": row["final_armors_json"],
        "accuracy": row["final_accuracy"] or 100,
        "min_attack_range": row["min_range"] or 0,
        "projectile_speed": row["projectile_speed"] or 0,
        "is_siege_projectile": row["is_siege_projectile"] or 0,
        "splash_radius": row["splash_radius"] or 0,
        "extra_projectiles": row["extra_projectiles"] or 0,
        "extra_projectile_attacks_json": row["extra_projectile_attacks_json"],
        "trample_percent": row["trample_percent"] or 0,
        "trample_radius": row["trample_radius"] or 0,
        "trample_flat_damage": row["trample_flat_damage"] or 0,
        "hp_regen": row["hp_regen"] or 0,
        "charge_projectile_count": row["charge_projectile_count"] or 0,
        "charge_projectile_speed": row["charge_projectile_speed"] or 0,
        "charge_projectile_attacks_json": row["charge_projectile_attacks_json"],
        "charge_attack_range": float(row["charge_attack_range"] or 0),
        "charge_ignores_armor": int(row["charge_ignores_armor"] or 0),
        "ignores_pierce_armor": int(row["ignores_pierce_armor"] or 0),
        "ignores_melee_armor": int(row["ignores_melee_armor"] or 0),
        "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
        "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
        "splash_on_hit_fraction": row["splash_on_hit_fraction"] or 1.0,
        "dodge_shield_max": int(row["dodge_shield_max"] or 0),
        "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
        "bleed_dps": row["bleed_dps"] or 0,
        "bleed_duration": row["bleed_duration"] or 0,
        "block_first_melee": int(row["block_first_melee"] or 0),
        "attack_bonus_per_kill": int(row["attack_bonus_per_kill"] or 0),
        "first_attack_extra_projectiles": int(row["first_attack_extra_projectiles"] or 0),
        "pass_through_percent": row["pass_through_percent"] or 0,
        "pass_through_count": row["pass_through_count"] or 1,
        "extra_proj_scatter": row["extra_proj_scatter"] or 0,
        "miss_damage_percent": row["miss_damage_percent"] or 0,
        "hp_per_kill": int(row["hp_per_kill"] or 0),
        "hp_per_kill_max": int(row["hp_per_kill_max"] or 0),
        "hp_transform_threshold": row["hp_transform_threshold"] or 0,
        "pop_space": row["pop_space"] or 1.0,
        "armor_strip_per_hit": int(row["armor_strip_per_hit"] or 0),
        "charge_attack_melee": int(row["charge_attack_melee"] or 0),
        "charge_recharge_time": row["charge_recharge_time"] or 0,
        "attack_bonus_nearby": row["attack_bonus_nearby"] or 0,
        "nearby_bonus_count": int(row["nearby_bonus_count"] or 0),
        "damage_reflect_percent": row["damage_reflect_percent"] or 0,
        "hp_nearby_percent_per_unit": row["hp_nearby_percent_per_unit"] or 0,
        "hp_nearby_max_units": int(row["hp_nearby_max_units"] or 0),
        "dismount_hp": row["dismount_hp"],
        "dismount_attack": row["dismount_attack"],
        "dismount_melee_armor": row["dismount_melee_armor"],
        "dismount_pierce_armor": row["dismount_pierce_armor"],
        "dismount_attack_speed": row["dismount_attack_speed"],
        "dismount_attack_delay": row["dismount_attack_delay"],
        "dismount_movement_speed": row["dismount_movement_speed"],
        "dismount_attacks_json": row["dismount_attacks_json"],
        "dismount_armors_json": row["dismount_armors_json"],
        "transform_hp": row["transform_hp"],
        "transform_attack": row["transform_attack"],
        "transform_melee_armor": row["transform_melee_armor"],
        "transform_pierce_armor": row["transform_pierce_armor"],
        "transform_attack_speed": row["transform_attack_speed"],
        "transform_attack_delay": row["transform_attack_delay"],
        "transform_movement_speed": row["transform_movement_speed"],
        "transform_attacks_json": row["transform_attacks_json"],
        "transform_armors_json": row["transform_armors_json"],
    }
    conn.close()
    cu = prepare_combat_unit(combat_dict)
    cu["cost_food"] = combat_dict["cost_food"]
    cu["cost_wood"] = combat_dict["cost_wood"]
    cu["cost_gold"] = combat_dict["cost_gold"]
    return cu


def _sim_score(unit_a, unit_b):
    """Run two battle scenarios and return composite score (-100..+100) from unit_a's perspective."""
    cost_a = _calc_weighted_cost(unit_a["cost_food"], unit_a["cost_wood"], unit_a["cost_gold"])
    cost_b = _calc_weighted_cost(unit_b["cost_food"], unit_b["cost_wood"], unit_b["cost_gold"])

    # 3K resource battle (cost efficiency)
    w1, _, _, hp1_1, hp2_1 = simulate_battle(
        unit_a, unit_b, 3000, cost1_override=cost_a, cost2_override=cost_b, return_hp=True
    )
    res_score = hp1_1 * 100 if w1 == 1 else (-hp2_1 * 100 if w1 == 2 else 0)

    # 30v30 fixed count (pop efficiency)
    w2, _, _, hp1_2, hp2_2 = simulate_battle(
        unit_a, unit_b, 0, fixed_count=30, return_hp=True
    )
    pop_score = hp1_2 * 100 if w2 == 1 else (-hp2_2 * 100 if w2 == 2 else 0)

    composite = 0.6 * res_score + 0.4 * pop_score
    return round(res_score, 1), round(pop_score, 1), round(composite, 1)


def _generate_reasoning(gold_unit, trash_unit, opponent_unit):
    """Generate human-readable reasoning for a composition recommendation."""
    reasons = []
    g_name = gold_unit.get("unit_name", gold_unit.get("slug", "Unit"))
    o_name = opponent_unit.get("unit_name", opponent_unit.get("slug", "Opponent"))
    t_name = trash_unit.get("unit_name", trash_unit.get("slug", "Support")) if trash_unit else None

    g_speed = gold_unit.get("movement_speed", 0)
    o_speed = opponent_unit.get("movement_speed", 0)
    g_range = gold_unit.get("attack_range", 0)
    o_range = opponent_unit.get("attack_range", 0)

    if g_speed > o_speed and g_range == 0:
        reasons.append(f"{g_name} closes distance on {o_name}")
    if g_range > o_range and g_range > 0:
        reasons.append(f"{g_name} outranges {o_name}")
    if g_range > 0 and o_range == 0:
        reasons.append(f"{g_name} kites melee {o_name}")
    if not reasons:
        reasons.append(f"{g_name} is strong against {o_name}")
    if t_name:
        reasons.append(f"{t_name} covers weakness")
    return "; ".join(reasons)


def get_matchup_recommendations(civ_a, civ_b, age="imperial"):
    """Get recommended units and compositions for civ_a vs civ_b.

    Returns dict with opponent_strengths, recommended_compositions, individual_counters.
    """
    power_data = load_civ_power_units()
    if not power_data:
        return {"error": "civ_power_units.json not found -- run best_units.py first"}

    civ_a_data = power_data.get(civ_a, {}).get(age)
    civ_b_data = power_data.get(civ_b, {}).get(age)
    if not civ_a_data or not civ_b_data:
        return {"error": f"No data for {civ_a} or {civ_b} in {age}"}

    # Step 1: Identify opponent's strengths (strong or signature)
    opponent_strengths = []
    for role_key in ["cavalry", "ranged", "infantry", "siege"]:
        entry = civ_b_data["power_units"].get(role_key)
        if entry and entry["strength"] in ("strong", "signature"):
            opponent_strengths.append({
                "role": role_key,
                "unit_slug": entry["unit_slug"],
                "strength": entry["strength"],
                "median_delta": entry["median_delta"],
            })

    # If opponent has no clear strengths, use their best roles anyway
    if not opponent_strengths:
        best_role = max(
            ["cavalry", "ranged", "infantry"],
            key=lambda r: (civ_b_data["power_units"].get(r) or {}).get("median_delta", -999),
        )
        entry = civ_b_data["power_units"].get(best_role)
        if entry:
            opponent_strengths.append({
                "role": best_role,
                "unit_slug": entry["unit_slug"],
                "strength": entry["strength"],
                "median_delta": entry["median_delta"],
            })

    # Step 2: Find counter candidates from battle_scores
    conn = _get_db()
    rc = conn.cursor()
    db_age = "Imperial" if age == "imperial" else "Castle"

    counter_candidates = []  # list of (unit_slug, line_slug, score, vs_role)
    seen_slugs = set()

    for opp in opponent_strengths:
        counter_defs = COUNTER_MAP.get(opp["role"], [])
        for line_slugs, score_type, desc in counter_defs:
            placeholders = ",".join("?" for _ in line_slugs)
            rc.execute(
                f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                    FROM battle_scores
                    WHERE civ_name = ?
                      AND LOWER(age) = ?
                      AND score_type = ?
                      AND line_slug IN ({placeholders})
                    ORDER BY median_delta DESC
                    LIMIT 3""",
                [civ_a, age, score_type] + line_slugs,
            )
            for row in rc.fetchall():
                slug = row["unit_slug"]
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    counter_candidates.append({
                        "unit_slug": slug,
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "median_delta": round(row["median_delta"], 1),
                        "vs_role": opp["role"],
                        "vs_unit_slug": opp["unit_slug"],
                    })

    conn.close()

    # Step 3: Simulate top candidates vs opponent power units
    individual_counters = []

    for cand in counter_candidates[:6]:  # Cap at 6 to limit sim count
        cu_a = _load_combat_unit(civ_a, cand["unit_slug"], db_age)
        cu_b = _load_combat_unit(civ_b, cand["vs_unit_slug"], db_age)
        if not cu_a or not cu_b:
            continue
        res_score, pop_score, composite = _sim_score(cu_a, cu_b)
        individual_counters.append({
            "unit_slug": cand["unit_slug"],
            "line_slug": cand["line_slug"],
            "vs_unit": cand["vs_unit_slug"],
            "resource_score": res_score,
            "pop_score": pop_score,
            "composite": composite,
        })

    # Sort by composite score descending
    individual_counters.sort(key=lambda x: x["composite"], reverse=True)

    # Step 4: Composition generation
    # Find civ_a's best trash unit
    civ_a_trash = civ_a_data["power_units"].get("trash")
    compositions = []

    for counter in individual_counters[:2]:  # Top 2 gold units
        gold_slug = counter["unit_slug"]
        gold_line = counter["line_slug"]

        # Determine trash partner
        trash_line = TRASH_PAIRING.get(gold_line, "stable")
        # Get actual trash unit for civ_a in that line
        trash_slug = None
        if civ_a_trash:
            trash_slug = civ_a_trash["unit_slug"]
        # Try to find a better match from the preferred line
        tconn = _get_db()
        trc = tconn.cursor()
        trc.execute(
            """SELECT unit_slug FROM ref_units
               WHERE civ_name=? AND age=? AND final_cost_gold=0
               ORDER BY final_hp DESC LIMIT 1""",
            (civ_a, db_age),
        )
        trash_row = trc.fetchone()
        if trash_row:
            trash_slug = trash_row["unit_slug"]
        tconn.close()

        if not trash_slug:
            trash_slug = civ_a_trash["unit_slug"] if civ_a_trash else None

        # Load units for reasoning
        gold_cu = _load_combat_unit(civ_a, gold_slug, db_age)
        trash_cu = _load_combat_unit(civ_a, trash_slug, db_age) if trash_slug else None
        opp_cu = _load_combat_unit(civ_b, counter["vs_unit"], db_age)

        reasoning = ""
        if gold_cu and opp_cu:
            reasoning = _generate_reasoning(gold_cu, trash_cu, opp_cu)

        compositions.append({
            "rank": len(compositions) + 1,
            "gold_unit": {
                "unit_slug": gold_slug,
                "line_slug": gold_line,
            },
            "trash_unit": {
                "unit_slug": trash_slug,
            } if trash_slug else None,
            "resource_split": {"gold_pct": 70, "trash_pct": 30},
            "scores": {
                "resource_efficiency": counter["resource_score"],
                "pop_efficiency": counter["pop_score"],
                "composite": counter["composite"],
            },
            "reasoning": reasoning,
        })

    return {
        "civ_a": civ_a,
        "civ_b": civ_b,
        "age": age,
        "opponent_strengths": opponent_strengths,
        "recommended_compositions": compositions,
        "individual_counters": individual_counters,
    }


if __name__ == "__main__":
    save_civ_power_units()
