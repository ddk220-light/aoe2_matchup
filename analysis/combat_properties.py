"""Combat property extraction and lookup functions."""

import json
from collections import defaultdict

from .config import (
    CIV_COMBAT_PROPERTIES,
    COMBAT_PROPERTIES,
    PAIRED_UNITS,
    UNIQUE_COMBAT_PROPERTIES,
    UNIQUE_UNIT_BUILDING,
)

# Pre-compute reverse index: civ_name -> list of (base_slug, props)
# Avoids O(n) scan over all CIV_COMBAT_PROPERTIES on every call.
_CIV_PROPS_BY_CIV = defaultdict(list)
for (civ, base_slug), props in CIV_COMBAT_PROPERTIES.items():
    _CIV_PROPS_BY_CIV[civ].append((base_slug, props))


def get_extracted_combat_properties(unit_id, units_data):
    """Read combat properties from extracted dat file data for a given game unit ID.

    Maps extracted fields to simulation combat property columns:
    - min_range → min_attack_range
    - projectile_speed (from projectile unit) → projectile_speed
    - class=13 + blast_width>0 + blast_damage≥1 → is_siege_projectile + splash_radius
    - total_projectiles → extra_projectiles (Chu Ko Nu, Kipchak, Organ Gun)
    - charge_type=6 + max_total_projectiles → extra_projectiles (Fire Archer)
    - charge_type=7 + max-total → first_attack_extra_projectiles (Xianbei)
    - secondary_projectile_attacks → extra_projectile_attacks_json
    - blast_width + blast_damage (0<dmg<1, level=2) → trample_percent + trample_radius
    - blast_width (level=11) → splash_on_hit_radius (Grenadier)
    - charge_type=4 → dodge_shield_max + dodge_shield_recharge (Shrivamsha)
    - bonus_damage_resistance → bonus_damage_reduction
    """
    if not unit_id or unit_id not in units_data:
        return {}

    unit = units_data[unit_id]
    props = {}

    # --- min_attack_range ---
    min_range = unit.get("min_range", 0) or 0
    if min_range > 0:
        props["min_attack_range"] = round(min_range, 2)

    # --- Projectile speed (from projectile unit's speed) ---
    proj_speed = unit.get("projectile_speed", 0) or 0
    if proj_speed > 0:
        props["projectile_speed"] = round(proj_speed, 2)

    # --- Siege projectile detection ---
    # Ranged siege units (class 13) with blast_width > 0 and blast_damage = 1.0 fire splash
    # projectiles (Mangonel, Siege Onager, Bombard Cannon).
    # Excludes melee siege (Rams, Siege Towers) and Organ Gun (blast_width=0).
    unit_class = unit.get("class", 0)
    blast_width = unit.get("blast_width", 0) or 0
    blast_damage = unit.get("blast_damage", 0) or 0
    blast_level = unit.get("blast_attack_level", 0) or 0
    unit_range = unit.get("range", 0) or 0

    if (
        unit_class == 13
        and blast_width > 0
        and blast_damage >= 1.0
        and unit_range >= 1.0
    ):
        props["is_siege_projectile"] = 1
        props["splash_radius"] = round(blast_width, 2)

    # --- Extra projectiles from total_projectiles ---
    # Units with total_projectiles > 1 fire extra arrows per attack.
    # Siege class (13) with blast_width > 0 fires stones (handled as splash above).
    # Organ Gun (class 13, blast_width=0) fires real extra projectiles like archers.
    total_proj = unit.get("total_projectiles", 1)
    is_siege_splash = unit_class == 13 and blast_width > 0 and blast_damage >= 1.0
    if total_proj and total_proj > 1 and not is_siege_splash:
        props["extra_projectiles"] = int(total_proj) - 1

    # --- Fire Archer extra projectiles from charge_type=6 ---
    # Fire Archer: total_proj=1, max_proj=3, charge_type=6 → 2 extra projectiles
    # Fire Lancer: total_proj=0 (melee), max_proj=3 → uses charge_projectile_count instead
    max_proj = unit.get("max_total_projectiles", 0)
    charge_type = unit.get("charge_type", 0)
    if (
        charge_type == 6
        and max_proj
        and max_proj > 1
        and total_proj
        and total_proj >= 1
    ):
        props["extra_projectiles"] = int(max_proj) - 1

    # --- First attack extra projectiles (burst) ---
    # Xianbei Raider (1952): total=1, max=6 → 5 extra on first attack
    if max_proj and total_proj and max_proj > total_proj:
        if charge_type == 7:
            props["first_attack_extra_projectiles"] = int(max_proj) - int(total_proj)

    # --- Secondary projectile attacks (different damage for extra projectiles) ---
    # Only relevant when unit actually fires extra projectiles (regular or burst)
    sec_attacks = unit.get("secondary_projectile_attacks")
    has_extra = (
        props.get("extra_projectiles", 0) > 0
        or props.get("first_attack_extra_projectiles", 0) > 0
    )
    if sec_attacks and has_extra:
        attacks_dict = {str(a["class"]): a["amount"] for a in sec_attacks}
        props["extra_projectile_attacks_json"] = json.dumps(attacks_dict)

    # --- Charge projectile attacks (Fire Lancer, Fire Archer, etc.) ---
    charge_proj_attacks = unit.get("charge_projectile_attacks")
    if charge_proj_attacks:
        attacks_dict = {str(a["class"]): a["amount"] for a in charge_proj_attacks}
        props["charge_projectile_attacks_json"] = json.dumps(attacks_dict)
    charge_proj_speed = unit.get("charge_projectile_speed", 0)
    if charge_proj_speed:
        props["charge_projectile_speed"] = charge_proj_speed
    charge_proj_count = 0
    if charge_type == 6 and max_proj and max_proj > 0:
        # Charge projectiles = max - base (melee units have total_proj=0)
        base_proj = int(total_proj) if total_proj else 0
        charge_proj_count = int(max_proj) - max(base_proj, 0)
    elif charge_type == 7 and max_proj and total_proj and max_proj > total_proj:
        charge_proj_count = int(max_proj) - int(total_proj)
    if charge_proj_count > 0:
        props["charge_projectile_count"] = charge_proj_count

    # --- Trample / splash from blast fields ---
    if blast_width > 0:
        if blast_level == 2 and 0 < blast_damage < 1.0:
            # Fractional trample: Battle Elephant (0.25), Ratha melee (0.2), War Elephant (0.5)
            props["trample_percent"] = round(blast_damage, 4)
            props["trample_radius"] = round(blast_width, 2)
        elif blast_level == 11:
            # Grenadier splash on hit (AoE around target)
            props["splash_on_hit_radius"] = round(blast_width, 2)

    # NOTE: blast_damage=-5.0 is standard for infantry/cavalry (means "no trample").
    # Cataphract trample comes from Logistica tech, not base unit stats - in CIV_COMBAT_PROPERTIES.

    # --- Dodge shield from charge_type=4 (Shrivamsha Rider) ---
    charge_attack = unit.get("charge_attack", 0)
    charge_recharge = unit.get("charge_recharge_rate", 0)

    if charge_type == 4 and charge_attack and charge_recharge:
        props["dodge_shield_max"] = int(charge_attack)
        props["dodge_shield_recharge"] = round(charge_attack / charge_recharge, 2)

    # --- Pass-through damage (Scorpion bolts) ---
    # Scorpions have blast_attack_level=3 AND secondary_projectile_attacks with
    # multiple attack classes (pierce + bonus vs infantry/elephants/buildings).
    # Regular archers also have blast_level=3 + secondary attacks but only a
    # single Base Pierce entry — those are NOT pass-through.
    if blast_level == 3 and sec_attacks and not has_extra and len(sec_attacks) > 1:
        primary_pierce = 0
        secondary_pierce = 0
        for a in unit.get("attacks", []):
            if a["class"] == 3:  # Base Pierce
                primary_pierce = a["amount"]
                break
        for a in sec_attacks:
            if a["class"] == 3:  # Base Pierce
                secondary_pierce = a["amount"]
                break
        if primary_pierce > 0 and secondary_pierce > 0:
            props["pass_through_percent"] = round(secondary_pierce / primary_pierce, 4)

    # --- Bonus damage reduction ---
    bonus_resist = unit.get("bonus_damage_resistance", 0)
    if bonus_resist and bonus_resist > 0:
        props["bonus_damage_reduction"] = round(bonus_resist, 4)

    # --- HP regeneration (attribute 109, stored as rear_attack_modifier in dat) ---
    hp_regen = unit.get("hp_regen", 0)
    if hp_regen and hp_regen > 0:
        props["hp_regen"] = round(hp_regen, 1)

    return props


def get_combat_properties(unit_slug, civ_name=None, unit_id=None, units_data=None):
    """Look up combat properties for a unit slug, optionally with civ-specific overrides.

    For unique units, the slug has a civ suffix (e.g., 'leitis_lithuanians').
    We strip the suffix and look up in UNIQUE_COMBAT_PROPERTIES.

    Priority order (later overrides earlier):
    1. Defaults (all zeros)
    2. Extracted dat file data (data-driven stats like trample, extra projectiles)
    3. Hardcoded COMBAT_PROPERTIES / UNIQUE_COMBAT_PROPERTIES (ability flags, special cases)
    4. Civ-conditional CIV_COMBAT_PROPERTIES
    """
    props = {
        "min_attack_range": 0,
        "is_siege_projectile": 0,
        "splash_radius": 0,
        "projectile_speed": 0,
        "ignores_pierce_armor": 0,
        "ignores_melee_armor": 0,
        "trample_percent": 0,
        "trample_radius": 0,
        "trample_flat_damage": 0,
        "bonus_damage_reduction": 0,
        "unit_category": "military",
        "paired_unit_slug": None,
        "extra_projectiles": 0,
        "extra_projectile_attacks_json": None,
        "charge_projectile_count": 0,
        "charge_projectile_attacks_json": None,
        "charge_projectile_speed": 0,
        "charge_attack_range": 0,
        "charge_ignores_armor": 0,
        "splash_on_hit_radius": 0,
        "dodge_shield_max": 0,
        "dodge_shield_recharge": 0,
        "bleed_dps": 0,
        "bleed_duration": 0,
        "block_first_melee": 0,
        "attack_bonus_per_kill": 0,
        "first_attack_extra_projectiles": 0,
        "hp_transform_threshold": 0,
        "transform_unit_id": 0,
        "dismount_unit_id": 0,
        "hp_regen": 0,
        "pass_through_percent": 0,
        "pass_through_count": 1,
        "extra_proj_scatter": 0,
        "miss_damage_percent": 0,
        "hp_per_kill": 0,
        "hp_per_kill_max": 0,
        "charge_slow_percent": 0,
        "charge_slow_duration": 0,
        "attack_speed_ramp": 0,
        "attack_speed_min": 0,
        "execute_damage_per_step": 0,
        "execute_hp_step": 0,
        "ally_death_heal": 0,
        "ally_death_heal_duration": 0,
    }

    # Apply extracted data from dat file (data-driven stats)
    if unit_id and units_data:
        extracted = get_extracted_combat_properties(unit_id, units_data)
        props.update(extracted)

    # Hardcoded overrides: standard combat properties (exact slug match)
    if unit_slug in COMBAT_PROPERTIES:
        props.update(COMBAT_PROPERTIES[unit_slug])

    # Hardcoded overrides: unique unit properties (strip civ suffix)
    for base_slug, unique_props in UNIQUE_COMBAT_PROPERTIES.items():
        if unit_slug == base_slug or unit_slug.startswith(base_slug + "_"):
            props.update(unique_props)
            break

    # Civ-conditional properties (e.g., Slavs champion gets Druzhina trample)
    if civ_name:
        # For standard units, key is (civ_name, unit_slug)
        civ_key = (civ_name, unit_slug)
        if civ_key in CIV_COMBAT_PROPERTIES:
            props.update(CIV_COMBAT_PROPERTIES[civ_key])

        # For unique units, try base slug (strip civ suffix) against CIV_COMBAT_PROPERTIES
        for base_slug, civ_props in _CIV_PROPS_BY_CIV.get(civ_name, []):
            if base_slug != unit_slug and unit_slug.startswith(base_slug + "_"):
                props.update(civ_props)
                break

    # Check paired units
    for paired_slug, partner_slug in PAIRED_UNITS.items():
        if unit_slug == paired_slug or unit_slug.startswith(paired_slug + "_"):
            # Build the full partner slug with same civ suffix
            if unit_slug.startswith(paired_slug + "_"):
                suffix = unit_slug[len(paired_slug) :]
                props["paired_unit_slug"] = partner_slug + suffix
            else:
                props["paired_unit_slug"] = partner_slug
            break

    return props
