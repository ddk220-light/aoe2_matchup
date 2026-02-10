"""
Data-driven battle simulation engine (damage-only, no positions).

All unit-specific behaviors (siege projectiles, trample, armor-ignoring, etc.)
are read from unit dict fields populated from the database — no hardcoded slug lookups.

Uses a tick-based damage loop with pre-calculated opening volleys for
range/kiting advantages. No XY positions or unit movement.
"""

import json
import random

# Simulation constants
DT = 0.1  # 100ms time step
MAX_TICKS = 2500  # 250 seconds max battle time
MELEE_RANGE = 0.5
MAP_SPACE = 22.0  # ~tiles of combat space (MAP_MAX - 2*start_offset)
RETARGET_DIST = 1.5  # tiles to walk when switching to a new melee target
UNIT_SPACING = 0.75  # approximate unit spacing in melee clump
RETREAT_MAX = 10.0  # max tiles ranged retreats before standing to fight


def _parse_dismount(row):
    """Parse dismount-on-death data from a DB row. Returns dict or None."""
    keys = row.keys() if hasattr(row, "keys") else row
    if "dismount_hp" not in keys or not row["dismount_hp"]:
        return None
    attacks = (
        json.loads(row["dismount_attacks_json"]) if row["dismount_attacks_json"] else {}
    )
    armors = (
        json.loads(row["dismount_armors_json"]) if row["dismount_armors_json"] else {}
    )
    attacks = {int(k): v for k, v in attacks.items()}
    armors = {int(k): v for k, v in armors.items()}
    return {
        "hp": row["dismount_hp"],
        "attack": row["dismount_attack"],
        "melee_armor": row["dismount_melee_armor"],
        "pierce_armor": row["dismount_pierce_armor"],
        "attack_speed": row["dismount_attack_speed"],
        "attack_delay": row["dismount_attack_delay"] or 0,
        "movement_speed": row["dismount_movement_speed"] or 0.9,
        "attacks": attacks,
        "armors": armors,
    }


def _parse_transform(row):
    """Parse HP-transform data from a DB row. Returns dict or None."""
    keys = row.keys() if hasattr(row, "keys") else row
    if "transform_hp" not in keys or not row["transform_hp"]:
        return None
    attacks = (
        json.loads(row["transform_attacks_json"])
        if row["transform_attacks_json"]
        else {}
    )
    armors = (
        json.loads(row["transform_armors_json"]) if row["transform_armors_json"] else {}
    )
    attacks = {int(k): v for k, v in attacks.items()}
    armors = {int(k): v for k, v in armors.items()}
    return {
        "hp": row["transform_hp"],
        "attack": row["transform_attack"],
        "melee_armor": row["transform_melee_armor"],
        "pierce_armor": row["transform_pierce_armor"],
        "attack_speed": row["transform_attack_speed"],
        "attack_delay": row["transform_attack_delay"] or 0,
        "movement_speed": row["transform_movement_speed"] or 1.0,
        "attacks": attacks,
        "armors": armors,
    }


def prepare_combat_unit(row):
    """Convert a DB row (sqlite3.Row or dict) into a combat-ready unit dict.

    Parses JSON fields once so simulate_battle() never has to.
    Call this ONCE per unit before running simulations.
    """
    attacks = json.loads(row["attacks_json"]) if row["attacks_json"] else {}
    armors = json.loads(row["armors_json"]) if row["armors_json"] else {}
    attacks = {int(k): v for k, v in attacks.items()}
    armors = {int(k): v for k, v in armors.items()}
    cost = (row["cost_food"] or 0) + (row["cost_wood"] or 0) + (row["cost_gold"] or 0)

    return {
        "hp": row["hp"],
        "attack": row["attack"],
        "attack_range": row["attack_range"] or 0,
        "attack_speed": row["attack_speed"],
        "attack_delay": row["attack_delay"] or 0,
        "melee_armor": row["melee_armor"],
        "pierce_armor": row["pierce_armor"],
        "movement_speed": row["movement_speed"] or 1.0,
        "attacks": attacks,
        "armors": armors,
        "cost": cost,
        "cost_food": row["cost_food"] or 0,
        "cost_wood": row["cost_wood"] or 0,
        "cost_gold": row["cost_gold"] or 0,
        # Combat properties from DB
        "min_attack_range": row["min_attack_range"] or 0,
        "is_siege_projectile": row["is_siege_projectile"] or 0,
        "splash_radius": row["splash_radius"] or 0,
        "projectile_speed": row["projectile_speed"] or 0,
        "accuracy": row.get("accuracy", 100) if hasattr(row, "get") else 100,
        "ignores_pierce_armor": row["ignores_pierce_armor"] or 0,
        "ignores_melee_armor": row["ignores_melee_armor"] or 0,
        "trample_percent": row["trample_percent"] or 0,
        "trample_radius": row["trample_radius"] or 0,
        "trample_flat_damage": row["trample_flat_damage"] or 0,
        "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
        # Unique unit mechanics
        "extra_projectiles": row["extra_projectiles"] or 0,
        "extra_projectile_attacks": {
            int(k): v
            for k, v in json.loads(row["extra_projectile_attacks_json"]).items()
        }
        if row["extra_projectile_attacks_json"]
        else None,
        "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
        "dodge_shield_max": row["dodge_shield_max"] or 0,
        "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
        "bleed_dps": row["bleed_dps"] or 0,
        "bleed_duration": row["bleed_duration"] or 0,
        "block_first_melee": row["block_first_melee"] or 0,
        "attack_bonus_per_kill": row["attack_bonus_per_kill"] or 0,
        "first_attack_extra_projectiles": row["first_attack_extra_projectiles"] or 0,
        "hp_regen": row["hp_regen"] or 0,
        "pass_through_percent": row["pass_through_percent"] or 0,
        "hp_transform_threshold": row["hp_transform_threshold"] or 0,
        # Metadata
        "slug": row["slug"]
        if "slug" in (row.keys() if hasattr(row, "keys") else row)
        else "",
        "unit_name": row["unit_name"]
        if "unit_name" in (row.keys() if hasattr(row, "keys") else row)
        else "",
        "unit_category": row["unit_category"]
        if "unit_category" in (row.keys() if hasattr(row, "keys") else row)
        else "military",
        "paired_unit_slug": row["paired_unit_slug"]
        if "paired_unit_slug" in (row.keys() if hasattr(row, "keys") else row)
        else None,
        # Dismount on death (Konnik)
        "transform": _parse_transform(row),
        "dismount": _parse_dismount(row),
    }


def _calc_damage(
    attacker_attacks,
    attacker_attack,
    defender_armors,
    defender_melee_armor,
    defender_pierce_armor,
    is_ranged,
    ignores_pierce=False,
    ignores_melee=False,
    bonus_damage_reduction=0,
):
    """Calculate damage per hit between two unit types."""
    if is_ranged:
        base_damage = attacker_attacks.get(3, attacker_attacks.get(4, attacker_attack))
        target_armor = (
            0 if ignores_pierce else defender_armors.get(3, defender_pierce_armor)
        )
    else:
        base_damage = attacker_attacks.get(4, attacker_attack)
        target_armor = (
            0 if ignores_melee else defender_armors.get(4, defender_melee_armor)
        )

    bonus_damage = 0
    for armor_class, armor_value in defender_armors.items():
        if armor_class in attacker_attacks and armor_class not in (3, 4):
            attack_bonus = attacker_attacks[armor_class]
            if attack_bonus > 0:
                bonus_damage += max(0, attack_bonus - armor_value)

    if bonus_damage_reduction > 0:
        bonus_damage = int(bonus_damage * (1 - bonus_damage_reduction))

    return max(1, base_damage + bonus_damage - target_armor)


def _splash_targets(radius):
    """How many extra targets a splash/trample hits (no positions)."""
    if radius <= 0:
        return 0
    return max(1, int(radius / UNIT_SPACING))


def _get_alive_targets(hp_arr, count):
    """Return list of alive unit indices."""
    return [i for i in range(count) if hp_arr[i] > 0]


def _assign_targets_spread(my_alive, enemy_alive):
    """Assign each alive attacker to an alive enemy, distributing evenly."""
    if not enemy_alive:
        return {}
    assignments = {}
    n_my = len(my_alive)
    n_en = len(enemy_alive)
    for li, i in enumerate(my_alive):
        assignments[i] = enemy_alive[li * n_en // n_my]
    return assignments


def _assign_targets_focus(my_alive, enemy_alive, enemy_hp, dmg_per_hit, num_proj):
    """Focus-fire targeting: group just enough attackers to kill each enemy.

    Assigns attackers to the first enemy until enough are assigned to kill it
    (based on current HP and damage per hit), then moves to the next enemy.
    """
    if not enemy_alive:
        return {}
    assignments = {}
    e_idx = 0  # current enemy target index
    assigned_dmg = 0.0  # damage assigned to current target so far
    for i in my_alive:
        if e_idx >= len(enemy_alive):
            e_idx = 0  # wrap around if more attackers than needed
            assigned_dmg = 0.0
        assignments[i] = enemy_alive[e_idx]
        assigned_dmg += dmg_per_hit * num_proj
        if assigned_dmg >= enemy_hp[enemy_alive[e_idx]]:
            e_idx += 1
            assigned_dmg = 0.0
    return assignments


def _find_alive_target(target_idx, enemy_hp, enemy_alive):
    """If assigned target is dead, find nearest alive enemy."""
    if enemy_hp[target_idx] > 0:
        return target_idx
    for idx in enemy_alive:
        if enemy_hp[idx] > 0:
            return idx
    return -1


def simulate_battle(
    unit1,
    unit2,
    resources,
    fixed_count=None,
    cost1_override=None,
    cost2_override=None,
    return_hp=False,
):
    """
    Tick-based battle simulation with no positions/movement.

    Phase 1: Opening volley (range/kiting advantage shots)
    Phase 2: Tick-based combat loop with all mechanics
    Phase 3: Winner determination

    Args:
        unit1/unit2: dicts from prepare_combat_unit()
        resources: total resource pool for army sizing
        fixed_count: if set, both sides get this many units
        cost1_override/cost2_override: override unit costs for army sizing
        return_hp: if True, returns 5-tuple with HP totals

    Returns: (winner, unit1_remaining, unit2_remaining) or
             (winner, unit1_remaining, unit2_remaining, hp_pct1, hp_pct2) if return_hp
        winner: 1 if unit1 wins, 2 if unit2 wins, 0 if draw
        hp_pct1/hp_pct2: remaining HP as fraction of starting total (0.0-1.0)
    """
    # --- Army sizes ---
    if fixed_count is not None:
        count1 = fixed_count
        count2 = fixed_count
    else:
        cost1 = cost1_override or (unit1["cost"] if unit1["cost"] > 0 else 100)
        cost2 = cost2_override or (unit2["cost"] if unit2["cost"] > 0 else 100)
        count1 = int(max(1, resources // cost1))
        count2 = int(max(1, resources // cost2))

    # --- Unit properties ---
    range1 = unit1["attack_range"]
    range2 = unit2["attack_range"]
    is_ranged1 = range1 >= 1.0
    is_ranged2 = range2 >= 1.0
    speed1 = unit1["movement_speed"]
    speed2 = unit2["movement_speed"]
    # Accuracy: main projectile hit chance (0-100). Extra projectiles use ~50% (scatter).
    accuracy1 = unit1.get("accuracy", 100) / 100.0  # fraction 0.0-1.0
    accuracy2 = unit2.get("accuracy", 100) / 100.0
    EXTRA_PROJ_ACCURACY = 0.5  # secondary projectiles scatter significantly

    # Attack timing
    aspeed1 = unit1["attack_speed"] or 0.5
    aspeed2 = unit2["attack_speed"] or 0.5
    reload1 = 1.0 / aspeed1 if aspeed1 > 0 else 2.0
    reload2 = 1.0 / aspeed2 if aspeed2 > 0 else 2.0
    delay1 = unit1["attack_delay"]
    delay2 = unit2["attack_delay"]
    min_range1 = unit1["min_attack_range"]
    min_range2 = unit2["min_attack_range"]

    # Pre-compute damage
    dmg1 = _calc_damage(
        unit1["attacks"],
        unit1["attack"],
        unit2["armors"],
        unit2["melee_armor"],
        unit2["pierce_armor"],
        is_ranged1,
        ignores_pierce=unit1["ignores_pierce_armor"],
        ignores_melee=unit1["ignores_melee_armor"],
        bonus_damage_reduction=unit2["bonus_damage_reduction"],
    )
    dmg2 = _calc_damage(
        unit2["attacks"],
        unit2["attack"],
        unit1["armors"],
        unit1["melee_armor"],
        unit1["pierce_armor"],
        is_ranged2,
        ignores_pierce=unit2["ignores_pierce_armor"],
        ignores_melee=unit2["ignores_melee_armor"],
        bonus_damage_reduction=unit1["bonus_damage_reduction"],
    )

    # Trample (melee only)
    tp1, tr1, tf1 = (
        unit1["trample_percent"],
        unit1["trample_radius"],
        unit1["trample_flat_damage"],
    )
    has_trample1 = (tp1 > 0 or tf1 > 0) and not is_ranged1
    trample_dmg1 = (int(dmg1 * tp1) + tf1) if has_trample1 else 0
    trample_extra1 = _splash_targets(tr1) if has_trample1 else 0

    tp2, tr2, tf2 = (
        unit2["trample_percent"],
        unit2["trample_radius"],
        unit2["trample_flat_damage"],
    )
    has_trample2 = (tp2 > 0 or tf2 > 0) and not is_ranged2
    trample_dmg2 = (int(dmg2 * tp2) + tf2) if has_trample2 else 0
    trample_extra2 = _splash_targets(tr2) if has_trample2 else 0

    # Siege splash
    is_siege1 = unit1["is_siege_projectile"] == 1
    is_siege2 = unit2["is_siege_projectile"] == 1
    siege_splash1 = _splash_targets(unit1["splash_radius"]) if is_siege1 else 0
    siege_splash2 = _splash_targets(unit2["splash_radius"]) if is_siege2 else 0

    # Splash on hit
    splash_hit1 = _splash_targets(unit1["splash_on_hit_radius"])
    splash_hit2 = _splash_targets(unit2["splash_on_hit_radius"])

    # Pass-through damage (Scorpion bolts, Pirotecnia)
    pass_through1 = unit1["pass_through_percent"]
    pass_through2 = unit2["pass_through_percent"]

    # Extra projectiles
    extra_proj1 = unit1["extra_projectiles"]
    extra_proj2 = unit2["extra_projectiles"]
    first_burst1 = unit1["first_attack_extra_projectiles"]
    first_burst2 = unit2["first_attack_extra_projectiles"]

    # Extra projectile damage (secondary projectile has different attacks)
    # e.g. Chu Ko Nu extra arrows: 3 pierce only, vs main: 8 pierce + anti-spearman
    extra_proj_attacks1 = unit1.get("extra_projectile_attacks")
    extra_proj_attacks2 = unit2.get("extra_projectile_attacks")

    if extra_proj_attacks1 and (extra_proj1 > 0 or first_burst1 > 0):
        sec_base1 = extra_proj_attacks1.get(3, extra_proj_attacks1.get(4, 0))
        extra_proj_dmg1 = _calc_damage(
            extra_proj_attacks1,
            sec_base1,
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
        )
    else:
        extra_proj_dmg1 = dmg1  # No secondary attacks: extra proj same as main

    if extra_proj_attacks2 and (extra_proj2 > 0 or first_burst2 > 0):
        sec_base2 = extra_proj_attacks2.get(3, extra_proj_attacks2.get(4, 0))
        extra_proj_dmg2 = _calc_damage(
            extra_proj_attacks2,
            sec_base2,
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
        )
    else:
        extra_proj_dmg2 = dmg2

    # Unique mechanics
    dodge_max1 = unit1["dodge_shield_max"]
    dodge_max2 = unit2["dodge_shield_max"]
    dodge_recharge1 = unit1["dodge_shield_recharge"]
    dodge_recharge2 = unit2["dodge_shield_recharge"]
    bleed_dps1, bleed_dur1 = unit1["bleed_dps"], unit1["bleed_duration"]
    bleed_dps2, bleed_dur2 = unit2["bleed_dps"], unit2["bleed_duration"]
    # HP regen: stored as HP/minute, convert to HP/tick
    regen_per_tick1 = unit1["hp_regen"] / 60.0 * DT if unit1["hp_regen"] > 0 else 0.0
    regen_per_tick2 = unit2["hp_regen"] / 60.0 * DT if unit2["hp_regen"] > 0 else 0.0
    max_hp1 = float(unit1["hp"])
    max_hp2 = float(unit2["hp"])
    block_melee1 = unit1["block_first_melee"]
    block_melee2 = unit2["block_first_melee"]
    kill_bonus1 = unit1["attack_bonus_per_kill"]
    kill_bonus2 = unit2["attack_bonus_per_kill"]
    transform_thresh1 = unit1["hp_transform_threshold"]
    transform_thresh2 = unit2["hp_transform_threshold"]

    # Kiting: ranged vs melee only
    should_kite1 = is_ranged1 and not is_ranged2
    should_kite2 = is_ranged2 and not is_ranged1

    # Min range: units with high min_range can't attack in melee phase
    # (e.g. mangonels min_range=3, can't hit units at melee range)
    cant_attack_melee1 = is_ranged1 and min_range1 >= 2.0 and not is_ranged2
    cant_attack_melee2 = is_ranged2 and min_range2 >= 2.0 and not is_ranged1

    # --- Per-unit state (plain Python lists) ---
    hp1 = [float(unit1["hp"])] * count1
    hp2 = [float(unit2["hp"])] * count2
    cooldown1 = [0.0] * count1
    cooldown2 = [0.0] * count2
    bonus_atk1 = [0.0] * count1
    bonus_atk2 = [0.0] * count2
    used_first1 = [False] * count1
    used_first2 = [False] * count2
    transformed1 = [False] * count1
    transformed2 = [False] * count2
    shield1 = [float(dodge_max1)] * count1
    shield2 = [float(dodge_max2)] * count2
    shield_timer1 = [0.0] * count1
    shield_timer2 = [0.0] * count2
    has_blocked1 = [False] * count1
    has_blocked2 = [False] * count2
    bleed_on1 = {}  # idx -> (dps, remaining)
    bleed_on2 = {}
    committed1 = {}  # idx -> (target, time_remaining)
    committed2 = {}
    prev_target1 = [-1] * count1  # last attacked target per unit (for retarget delay)
    prev_target2 = [-1] * count2

    # Dismount on death (Konnik): pre-compute dismount damage
    dismount1 = unit1.get("dismount")
    dismount2 = unit2.get("dismount")
    dismounted1 = [False] * count1 if dismount1 else None
    dismounted2 = [False] * count2 if dismount2 else None

    if dismount1:
        # Dismounted team1 attacking team2
        dmg1_dismount = _calc_damage(
            dismount1["attacks"],
            dismount1["attack"],
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            False,  # dismounted is always melee
        )
        # Team2 attacking dismounted team1 (different armor classes!)
        dmg2_vs_dismount1 = _calc_damage(
            unit2["attacks"],
            unit2["attack"],
            dismount1["armors"],
            dismount1["melee_armor"],
            dismount1["pierce_armor"],
            is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
        )
        reload1_dismount = (
            1.0 / dismount1["attack_speed"] if dismount1["attack_speed"] > 0 else 2.0
        )
        delay1_dismount = dismount1["attack_delay"]
    if dismount2:
        # Dismounted team2 attacking team1
        dmg2_dismount = _calc_damage(
            dismount2["attacks"],
            dismount2["attack"],
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            False,
        )
        # Team1 attacking dismounted team2 (different armor classes!)
        dmg1_vs_dismount2 = _calc_damage(
            unit1["attacks"],
            unit1["attack"],
            dismount2["armors"],
            dismount2["melee_armor"],
            dismount2["pierce_armor"],
            is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
        )
        reload2_dismount = (
            1.0 / dismount2["attack_speed"] if dismount2["attack_speed"] > 0 else 2.0
        )
        delay2_dismount = dismount2["attack_delay"]

    # HP transform (Jian Swordsman): pre-compute transformed damage
    transform1 = unit1.get("transform")
    transform2 = unit2.get("transform")

    if transform1:
        # Transformed team1 attacking team2
        dmg1_transform = _calc_damage(
            transform1["attacks"],
            transform1["attack"],
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
        )
        # Team2 attacking transformed team1 (different armor!)
        dmg2_vs_transform1 = _calc_damage(
            unit2["attacks"],
            unit2["attack"],
            transform1["armors"],
            transform1["melee_armor"],
            transform1["pierce_armor"],
            is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
        )
    if transform2:
        dmg2_transform = _calc_damage(
            transform2["attacks"],
            transform2["attack"],
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
        )
        dmg1_vs_transform2 = _calc_damage(
            unit1["attacks"],
            unit1["attack"],
            transform2["armors"],
            transform2["melee_armor"],
            transform2["pierce_armor"],
            is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
        )

    start_total_hp1 = float(unit1["hp"]) * count1
    start_total_hp2 = float(unit2["hp"]) * count2

    # =========================================================
    # PHASE 1: Opening volley (range/kiting advantage)
    # =========================================================

    def _apply_opening_hit(attacker_team, target_idx, damage, attacker_idx):
        """Apply a single opening hit with all mechanics."""
        if attacker_team == 1:
            t_hp, t_shield, t_shield_timer = hp2, shield2, shield_timer2
            t_blocked, t_bleed = has_blocked2, bleed_on2
            a_bonus, a_used_first = bonus_atk1, used_first1
            a_is_ranged = is_ranged1
            d_dodge_max, d_recharge = dodge_max2, dodge_recharge2
            d_block = block_melee2
            a_kill_bonus = kill_bonus1
            a_bleed_dps, a_bleed_dur = bleed_dps1, bleed_dur1
            a_splash_hit = splash_hit1
            a_siege_splash = siege_splash1
            a_is_siege = is_siege1
            a_pass_through = pass_through1
            t_alive_fn = lambda: _get_alive_targets(hp2, count2)
        else:
            t_hp, t_shield, t_shield_timer = hp1, shield1, shield_timer1
            t_blocked, t_bleed = has_blocked1, bleed_on1
            a_bonus, a_used_first = bonus_atk2, used_first2
            a_is_ranged = is_ranged2
            d_dodge_max, d_recharge = dodge_max1, dodge_recharge1
            d_block = block_melee1
            a_kill_bonus = kill_bonus2
            a_bleed_dps, a_bleed_dur = bleed_dps2, bleed_dur2
            a_splash_hit = splash_hit2
            a_siege_splash = siege_splash2
            a_is_siege = is_siege2
            a_pass_through = pass_through2
            t_alive_fn = lambda: _get_alive_targets(hp1, count1)

        if t_hp[target_idx] <= 0:
            return

        # Dodge shield (ranged only)
        if d_dodge_max > 0 and a_is_ranged and t_shield[target_idx] > 0:
            t_shield[target_idx] -= 1
            t_shield_timer[target_idx] = d_recharge
            return

        # Block first melee
        if d_block and not a_is_ranged and not t_blocked[target_idx]:
            t_blocked[target_idx] = True
            return

        hit_dmg = damage + int(a_bonus[attacker_idx])
        was_alive = t_hp[target_idx] > 0
        t_hp[target_idx] -= hit_dmg

        if a_kill_bonus > 0 and was_alive and t_hp[target_idx] <= 0:
            a_bonus[attacker_idx] += a_kill_bonus

        # Siege splash: hit extra targets
        if a_is_siege and a_siege_splash > 0:
            alive = t_alive_fn()
            splashed = 0
            for idx in alive:
                if idx != target_idx and splashed < a_siege_splash:
                    t_hp[idx] -= hit_dmg
                    splashed += 1

        # Splash on hit: hit extra targets near the target
        if a_splash_hit > 0:
            alive = t_alive_fn()
            splashed = 0
            for idx in alive:
                if idx != target_idx and splashed < a_splash_hit:
                    t_hp[idx] -= hit_dmg
                    splashed += 1

        # Pass-through: 1 additional unit takes a fraction of the damage
        if a_pass_through > 0:
            alive = t_alive_fn()
            pt_dmg = max(1, int(hit_dmg * a_pass_through))
            for idx in alive:
                if idx != target_idx:
                    t_hp[idx] -= pt_dmg
                    break

        if a_bleed_dps > 0 and was_alive:
            t_bleed[target_idx] = (a_bleed_dps, a_bleed_dur)

    def _do_opening_volley(
        attacker_team,
        num_shots,
        attacker_count,
        target_count,
        damage,
        extra_proj_damage,
        a_extra_proj,
        a_first_burst,
        a_used_first_arr,
        target_hp_arr,
        a_accuracy=1.0,
    ):
        """Apply num_shots opening shots from attacker_team using focus fire."""
        if num_shots <= 0:
            return
        a_alive = list(range(attacker_count))
        for shot_round in range(num_shots):
            t_alive = [i for i in range(target_count) if target_hp_arr[i] > 0]
            if not t_alive:
                break
            # Use focus-fire targeting: concentrate fire to get kills
            targets = _assign_targets_focus(
                a_alive, t_alive, target_hp_arr, damage, 1 + a_extra_proj
            )
            for a_idx in a_alive:
                t_alive_now = [i for i in range(target_count) if target_hp_arr[i] > 0]
                if not t_alive_now:
                    break
                target = targets.get(a_idx, t_alive_now[0])
                if target_hp_arr[target] <= 0:
                    target = t_alive_now[0]
                num_proj = 1 + a_extra_proj
                if a_first_burst > 0 and not a_used_first_arr[a_idx]:
                    num_proj += a_first_burst
                    a_used_first_arr[a_idx] = True
                # Main projectile: hit chance = unit accuracy
                if a_accuracy >= 1.0 or random.random() < a_accuracy:
                    _apply_opening_hit(attacker_team, target, damage, a_idx)
                # Extra projectiles: low accuracy (~50%), they scatter
                for _ in range(num_proj - 1):
                    if random.random() < EXTRA_PROJ_ACCURACY:
                        _apply_opening_hit(
                            attacker_team, target, extra_proj_damage, a_idx
                        )

    # Calculate opening shots for each side
    opening1 = 0
    opening2 = 0
    closing_time1 = 0.0  # actual closing time for team2 melee reaching team1 ranged
    closing_time2 = 0.0  # actual closing time for team1 melee reaching team2 ranged

    if is_ranged1 and not is_ranged2:
        # Team 1 ranged vs team 2 melee
        # Ranged retreats while melee chases. During each attack cycle,
        # ranged pauses for attack_delay (frame delay) then moves for the rest.
        # Effective retreat speed is reduced by the fraction spent animating.
        fire_dist = range1 - max(min_range1, MELEE_RANGE)
        if fire_dist > 0 and speed2 > 0:
            # Ranged effective retreat speed: stationary during attack_delay,
            # moving during (reload - attack_delay) of each reload cycle
            move_frac1 = max(0.0, 1.0 - delay1 / reload1) if reload1 > 0 else 1.0
            eff_retreat_speed1 = speed1 * move_frac1
            net_speed = speed2 - eff_retreat_speed1
            if net_speed > 0:
                retreat_time = (
                    min(RETREAT_MAX / eff_retreat_speed1, fire_dist / net_speed)
                    if eff_retreat_speed1 > 0
                    else fire_dist / net_speed
                )
                retreat_dist_closed = net_speed * retreat_time
                remaining_dist = fire_dist - retreat_dist_closed
            else:
                retreat_time = (
                    RETREAT_MAX / eff_retreat_speed1 if eff_retreat_speed1 > 0 else 0
                )
                remaining_dist = fire_dist
            # Phase 2: ranged stopped, melee closes remaining distance
            # Melee also has frame delay on first hit after arriving
            stand_time = remaining_dist / speed2 if remaining_dist > 0 else 0
            closing_time = retreat_time + stand_time + delay2
            closing_time1 = closing_time
            if closing_time > delay1:
                opening1 = 1 + int((closing_time - delay1) / reload1)
        # Kiting bonus: if ranged is faster than melee (even accounting for
        # frame delay pauses), they can keep distance after retreat
        eff_spd1 = eff_retreat_speed1 if fire_dist > 0 and speed2 > 0 else speed1
        if eff_spd1 > speed2 and speed2 > 0:
            speed_diff = eff_spd1 - speed2
            kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX
            if kite_dist > 0:
                kite_time = kite_dist / speed_diff
                opening1 += max(0, int(kite_time / reload1))
    elif not is_ranged1 and is_ranged2:
        # Team 2 ranged vs team 1 melee (mirror logic)
        fire_dist = range2 - max(min_range2, MELEE_RANGE)
        if fire_dist > 0 and speed1 > 0:
            move_frac2 = max(0.0, 1.0 - delay2 / reload2) if reload2 > 0 else 1.0
            eff_retreat_speed2 = speed2 * move_frac2
            net_speed = speed1 - eff_retreat_speed2
            if net_speed > 0:
                retreat_time = (
                    min(RETREAT_MAX / eff_retreat_speed2, fire_dist / net_speed)
                    if eff_retreat_speed2 > 0
                    else fire_dist / net_speed
                )
                retreat_dist_closed = net_speed * retreat_time
                remaining_dist = fire_dist - retreat_dist_closed
            else:
                retreat_time = (
                    RETREAT_MAX / eff_retreat_speed2 if eff_retreat_speed2 > 0 else 0
                )
                remaining_dist = fire_dist
            stand_time = remaining_dist / speed1 if remaining_dist > 0 else 0
            closing_time = retreat_time + stand_time + delay1
            closing_time2 = closing_time
            if closing_time > delay2:
                opening2 = 1 + int((closing_time - delay2) / reload2)
        eff_spd2 = eff_retreat_speed2 if fire_dist > 0 and speed1 > 0 else speed2
        if eff_spd2 > speed1 and speed1 > 0:
            speed_diff = eff_spd2 - speed1
            kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX
            if kite_dist > 0:
                kite_time = kite_dist / speed_diff
                opening2 += max(0, int(kite_time / reload2))
    elif is_ranged1 and is_ranged2:
        # Both ranged: side with more range gets bonus shots
        range_diff = range1 - range2
        if range_diff > 0:
            opening1 = max(0, int(range_diff / 2))
        elif range_diff < 0:
            opening2 = max(0, int(-range_diff / 2))

    # Apply opening volleys and set post-opening cooldowns
    if opening1 > 0:
        _do_opening_volley(
            1,
            opening1,
            count1,
            count2,
            dmg1,
            extra_proj_dmg1,
            extra_proj1,
            first_burst1,
            used_first1,
            hp2,
            a_accuracy=accuracy1,
        )
        # Set cooldowns to reflect time elapsed since last opening shot
        if is_ranged1 and not is_ranged2 and closing_time1 > 0:
            last_shot_t = delay1 + (opening1 - 1) * reload1
            remaining_cd = max(0.0, reload1 - (closing_time1 - last_shot_t))
            for i in range(count1):
                cooldown1[i] = remaining_cd
    if opening2 > 0:
        _do_opening_volley(
            2,
            opening2,
            count2,
            count1,
            dmg2,
            extra_proj_dmg2,
            extra_proj2,
            first_burst2,
            used_first2,
            hp1,
            a_accuracy=accuracy2,
        )
        if is_ranged2 and not is_ranged1 and closing_time2 > 0:
            last_shot_t = delay2 + (opening2 - 1) * reload2
            remaining_cd = max(0.0, reload2 - (closing_time2 - last_shot_t))
            for i in range(count2):
                cooldown2[i] = remaining_cd

    # =========================================================
    # PHASE 2: Tick-based combat loop
    # =========================================================

    for tick in range(MAX_TICKS):
        alive1 = _get_alive_targets(hp1, count1)
        alive2 = _get_alive_targets(hp2, count2)

        if not alive1 or not alive2:
            break

        # Decrement cooldowns
        for i in alive1:
            cooldown1[i] = max(0.0, cooldown1[i] - DT)
        for i in alive2:
            cooldown2[i] = max(0.0, cooldown2[i] - DT)

        # Assign targets: ranged use focus fire, melee spread evenly
        if is_ranged1:
            targets1 = _assign_targets_focus(alive1, alive2, hp2, dmg1, 1 + extra_proj1)
        else:
            targets1 = _assign_targets_spread(alive1, alive2)
        if is_ranged2:
            targets2 = _assign_targets_focus(alive2, alive1, hp1, dmg2, 1 + extra_proj2)
        else:
            targets2 = _assign_targets_spread(alive2, alive1)

        # Collect pending damage: (target_team, target_idx, damage, attacker_idx)
        pending_damage = []

        # Alternate which team acts first
        if tick % 2 == 0:
            team_order = [1, 2]
        else:
            team_order = [2, 1]

        for team_id in team_order:
            if team_id == 1:
                my_alive = alive1
                my_targets = targets1
                my_cooldown, my_committed = cooldown1, committed1
                my_bonus_atk, my_used_first = bonus_atk1, used_first1
                t_is_ranged, t_is_siege = is_ranged1, is_siege1
                t_speed = speed1
                t_accuracy = accuracy1
                t_reload, t_delay = reload1, delay1
                t_extra_proj, t_first_burst = extra_proj1, first_burst1
                t_dmg = dmg1
                t_extra_proj_dmg = extra_proj_dmg1
                t_dmg_vs_dismount = dmg1_vs_dismount2 if dismount2 else dmg1
                t_enemy_dismounted = dismounted2
                t_dmg_transform = dmg1_transform if transform1 else dmg1
                t_dmg_vs_transform = dmg2_vs_transform1 if transform1 else dmg2
                my_transformed = transformed1
                t_enemy_transformed = transformed2
                t_cant_attack = cant_attack_melee1
                my_prev_target = prev_target1
                enemy_hp = hp2
                enemy_alive = alive2
                enemy_team = 2
            else:
                my_alive = alive2
                my_targets = targets2
                my_cooldown, my_committed = cooldown2, committed2
                my_bonus_atk, my_used_first = bonus_atk2, used_first2
                t_is_ranged, t_is_siege = is_ranged2, is_siege2
                t_speed = speed2
                t_accuracy = accuracy2
                t_reload, t_delay = reload2, delay2
                t_extra_proj, t_first_burst = extra_proj2, first_burst2
                t_dmg = dmg2
                t_extra_proj_dmg = extra_proj_dmg2
                t_dmg_vs_dismount = dmg2_vs_dismount1 if dismount1 else dmg2
                t_enemy_dismounted = dismounted1
                t_dmg_transform = dmg2_transform if transform2 else dmg2
                t_dmg_vs_transform = dmg1_vs_transform2 if transform2 else dmg1
                my_transformed = transformed2
                t_enemy_transformed = transformed1
                t_cant_attack = cant_attack_melee2
                my_prev_target = prev_target2
                enemy_hp = hp1
                enemy_alive = alive1
                enemy_team = 1

            for i in my_alive:
                # Check if this unit has dismounted (Konnik)
                i_dismounted = (team_id == 1 and dismounted1 and dismounted1[i]) or (
                    team_id == 2 and dismounted2 and dismounted2[i]
                )

                # Handle committed melee attacks
                if i in my_committed:
                    target_idx, time_left = my_committed[i]
                    time_left -= DT
                    if time_left <= 0:
                        if enemy_hp[target_idx] > 0:
                            if i_dismounted:
                                base = dmg1_dismount if team_id == 1 else dmg2_dismount
                            elif my_transformed and my_transformed[i]:
                                base = t_dmg_transform
                            elif t_enemy_dismounted and t_enemy_dismounted[target_idx]:
                                base = t_dmg_vs_dismount
                            elif (
                                t_enemy_transformed and t_enemy_transformed[target_idx]
                            ):
                                base = t_dmg_vs_transform
                            else:
                                base = t_dmg
                            hit_dmg = base + int(my_bonus_atk[i])
                            pending_damage.append(
                                (enemy_team, target_idx, hit_dmg, i, team_id)
                            )
                        del my_committed[i]
                        if i_dismounted:
                            my_cooldown[i] = (
                                reload1_dismount if team_id == 1 else reload2_dismount
                            )
                        else:
                            my_cooldown[i] = t_reload
                    else:
                        my_committed[i] = (target_idx, time_left)
                    continue

                if my_cooldown[i] > 0:
                    continue

                # Can't attack if min_range prevents it in melee phase
                if t_cant_attack:
                    continue

                # Find target
                target_idx = my_targets.get(i, -1)
                if target_idx < 0:
                    continue
                target_idx = _find_alive_target(target_idx, enemy_hp, enemy_alive)
                if target_idx < 0:
                    continue
                # Retarget delay: melee units need time to walk to new target
                prev = my_prev_target[i]
                if prev >= 0 and target_idx != prev and not t_is_ranged:
                    retarget_time = RETARGET_DIST / t_speed if t_speed > 0 else 2.0
                    my_cooldown[i] = retarget_time
                    my_prev_target[i] = target_idx
                    continue
                my_prev_target[i] = target_idx

                if i_dismounted:
                    # Dismounted: always melee, use dismount stats
                    i_dmg = (dmg1_dismount if team_id == 1 else dmg2_dismount) + int(
                        my_bonus_atk[i]
                    )
                    i_delay = delay1_dismount if team_id == 1 else delay2_dismount
                    i_reload = reload1_dismount if team_id == 1 else reload2_dismount
                    if i_delay > 0:
                        my_committed[i] = (target_idx, i_delay)
                    else:
                        pending_damage.append(
                            (enemy_team, target_idx, i_dmg, i, team_id)
                        )
                        my_cooldown[i] = i_reload
                elif t_is_ranged:
                    # Ranged: fire instantly, apply accuracy
                    num_extra = t_extra_proj
                    if t_first_burst > 0 and not my_used_first[i]:
                        num_extra += t_first_burst
                        my_used_first[i] = True
                    if t_enemy_dismounted and t_enemy_dismounted[target_idx]:
                        base = t_dmg_vs_dismount
                    elif t_enemy_transformed and t_enemy_transformed[target_idx]:
                        base = t_dmg_vs_transform
                    else:
                        base = t_dmg
                    # Main projectile: hit chance = unit accuracy
                    if t_accuracy >= 1.0 or random.random() < t_accuracy:
                        hit_dmg = base + int(my_bonus_atk[i])
                        pending_damage.append(
                            (enemy_team, target_idx, hit_dmg, i, team_id)
                        )
                    # Extra projectiles: low accuracy (~50%), they scatter
                    if num_extra > 0:
                        extra_base = t_extra_proj_dmg
                        extra_hit = extra_base + int(my_bonus_atk[i])
                        for _ in range(num_extra):
                            if random.random() < EXTRA_PROJ_ACCURACY:
                                pending_damage.append(
                                    (enemy_team, target_idx, extra_hit, i, team_id)
                                )
                    my_cooldown[i] = t_reload
                else:
                    # Melee: commit with delay or hit instantly
                    if t_delay > 0:
                        my_committed[i] = (target_idx, t_delay)
                    else:
                        if my_transformed and my_transformed[i]:
                            base = t_dmg_transform
                        elif t_enemy_dismounted and t_enemy_dismounted[target_idx]:
                            base = t_dmg_vs_dismount
                        elif t_enemy_transformed and t_enemy_transformed[target_idx]:
                            base = t_dmg_vs_transform
                        else:
                            base = t_dmg
                        hit_dmg = base + int(my_bonus_atk[i])
                        pending_damage.append(
                            (enemy_team, target_idx, hit_dmg, i, team_id)
                        )
                        my_cooldown[i] = t_reload

        # --- Apply all pending damage atomically ---
        for (
            target_team,
            target_idx,
            damage,
            attacker_idx,
            attacker_team,
        ) in pending_damage:
            if target_team == 1:
                t_hp = hp1
                t_shield, t_shield_timer = shield1, shield_timer1
                t_blocked, t_bleed = has_blocked1, bleed_on1
                a_bonus = bonus_atk2
                a_is_ranged = is_ranged2
                d_dodge_max, d_recharge = dodge_max1, dodge_recharge1
                d_block = block_melee1
                a_kill_bonus = kill_bonus2
                a_bleed_dps, a_bleed_dur = bleed_dps2, bleed_dur2
                a_trample_dmg, a_trample_extra = trample_dmg2, trample_extra2
                a_splash_hit = splash_hit2
                a_siege_splash = siege_splash2
                a_is_siege = is_siege2
                a_pass_through = pass_through2
                all_alive = alive1
            else:
                t_hp = hp2
                t_shield, t_shield_timer = shield2, shield_timer2
                t_blocked, t_bleed = has_blocked2, bleed_on2
                a_bonus = bonus_atk1
                a_is_ranged = is_ranged1
                d_dodge_max, d_recharge = dodge_max2, dodge_recharge2
                d_block = block_melee2
                a_kill_bonus = kill_bonus1
                a_bleed_dps, a_bleed_dur = bleed_dps1, bleed_dur1
                a_trample_dmg, a_trample_extra = trample_dmg1, trample_extra1
                a_splash_hit = splash_hit1
                a_siege_splash = siege_splash1
                a_is_siege = is_siege1
                a_pass_through = pass_through1
                all_alive = alive2

            if t_hp[target_idx] <= 0:
                continue

            # Dodge shield (ranged attacks only)
            if d_dodge_max > 0 and a_is_ranged and t_shield[target_idx] > 0:
                t_shield[target_idx] -= 1
                t_shield_timer[target_idx] = d_recharge
                continue

            # Block first melee
            if d_block and not a_is_ranged and not t_blocked[target_idx]:
                t_blocked[target_idx] = True
                continue

            was_alive = t_hp[target_idx] > 0
            t_hp[target_idx] -= damage

            # Kill bonus
            if a_kill_bonus > 0 and was_alive and t_hp[target_idx] <= 0:
                a_bonus[attacker_idx] += a_kill_bonus

            # Trample: damage extra nearby alive enemies
            if a_trample_dmg > 0 and a_trample_extra > 0:
                splashed = 0
                for idx in all_alive:
                    if (
                        idx != target_idx
                        and t_hp[idx] > 0
                        and splashed < a_trample_extra
                    ):
                        t_hp[idx] -= a_trample_dmg
                        splashed += 1

            # Siege splash: extra targets
            if a_is_siege and a_siege_splash > 0:
                splashed = 0
                for idx in all_alive:
                    if (
                        idx != target_idx
                        and t_hp[idx] > 0
                        and splashed < a_siege_splash
                    ):
                        t_hp[idx] -= damage
                        splashed += 1

            # Splash on hit: extra targets near the target
            if a_splash_hit > 0:
                splashed = 0
                for idx in all_alive:
                    if idx != target_idx and t_hp[idx] > 0 and splashed < a_splash_hit:
                        t_hp[idx] -= damage
                        splashed += 1

            # Pass-through: 1 additional unit takes a fraction of the damage
            if a_pass_through > 0:
                pt_dmg = max(1, int(damage * a_pass_through))
                for idx in all_alive:
                    if idx != target_idx and t_hp[idx] > 0:
                        t_hp[idx] -= pt_dmg
                        break

            # Bleed
            if a_bleed_dps > 0 and was_alive:
                t_bleed[target_idx] = (a_bleed_dps, a_bleed_dur)

        # --- Tick-based effects ---

        # Dodge shield recharge
        if dodge_max1 > 0:
            for i in alive1:
                if shield_timer1[i] > 0:
                    shield_timer1[i] -= DT
                    if shield_timer1[i] <= 0 and shield1[i] < dodge_max1:
                        shield1[i] += 1
                        if shield1[i] < dodge_max1:
                            shield_timer1[i] = dodge_recharge1
                        else:
                            shield_timer1[i] = 0.0
        if dodge_max2 > 0:
            for i in alive2:
                if shield_timer2[i] > 0:
                    shield_timer2[i] -= DT
                    if shield_timer2[i] <= 0 and shield2[i] < dodge_max2:
                        shield2[i] += 1
                        if shield2[i] < dodge_max2:
                            shield_timer2[i] = dodge_recharge2
                        else:
                            shield_timer2[i] = 0.0

        # Bleed damage
        for idx in list(bleed_on1):
            if hp1[idx] > 0:
                dps, remaining = bleed_on1[idx]
                hp1[idx] -= dps * DT
                remaining -= DT
                if remaining > 0:
                    bleed_on1[idx] = (dps, remaining)
                else:
                    del bleed_on1[idx]
            else:
                del bleed_on1[idx]
        for idx in list(bleed_on2):
            if hp2[idx] > 0:
                dps, remaining = bleed_on2[idx]
                hp2[idx] -= dps * DT
                remaining -= DT
                if remaining > 0:
                    bleed_on2[idx] = (dps, remaining)
                else:
                    del bleed_on2[idx]
            else:
                del bleed_on2[idx]

        # HP regeneration
        if regen_per_tick1 > 0:
            for idx in alive1:
                if hp1[idx] < max_hp1:
                    hp1[idx] = min(max_hp1, hp1[idx] + regen_per_tick1)
        if regen_per_tick2 > 0:
            for idx in alive2:
                if hp2[idx] < max_hp2:
                    hp2[idx] = min(max_hp2, hp2[idx] + regen_per_tick2)

        # HP transform (e.g. Jian Swordsman — switch to unshielded form)
        if transform_thresh1 > 0:
            threshold_hp = unit1["hp"] * transform_thresh1
            for idx in alive1:
                if not transformed1[idx] and hp1[idx] <= threshold_hp and hp1[idx] > 0:
                    transformed1[idx] = True
        if transform_thresh2 > 0:
            threshold_hp = unit2["hp"] * transform_thresh2
            for idx in alive2:
                if not transformed2[idx] and hp2[idx] <= threshold_hp and hp2[idx] > 0:
                    transformed2[idx] = True

        # Dismount on death: respawn dead mounted units as dismounted
        if dismount1:
            for idx in range(count1):
                if hp1[idx] <= 0 and not dismounted1[idx]:
                    dismounted1[idx] = True
                    hp1[idx] = float(dismount1["hp"])
                    cooldown1[idx] = reload1_dismount
                    if idx in committed1:
                        del committed1[idx]
        if dismount2:
            for idx in range(count2):
                if hp2[idx] <= 0 and not dismounted2[idx]:
                    dismounted2[idx] = True
                    hp2[idx] = float(dismount2["hp"])
                    cooldown2[idx] = reload2_dismount
                    if idx in committed2:
                        del committed2[idx]

    # =========================================================
    # PHASE 3: Winner determination
    # =========================================================

    remaining1 = sum(1 for h in hp1 if h > 0)
    remaining2 = sum(1 for h in hp2 if h > 0)
    total_hp1 = sum(max(0, h) for h in hp1)
    total_hp2 = sum(max(0, h) for h in hp2)
    hp_pct1 = total_hp1 / start_total_hp1 if start_total_hp1 > 0 else 0.0
    hp_pct2 = total_hp2 / start_total_hp2 if start_total_hp2 > 0 else 0.0

    def _result(winner):
        if return_hp:
            return (winner, remaining1, remaining2, hp_pct1, hp_pct2)
        return (winner, remaining1, remaining2)

    if remaining1 > 0 and remaining2 == 0:
        return _result(1)
    elif remaining2 > 0 and remaining1 == 0:
        return _result(2)
    else:
        lost1 = count1 - remaining1
        lost2 = count2 - remaining2
        if lost1 > lost2:
            return _result(2)
        elif lost2 > lost1:
            return _result(1)
        else:
            if hp_pct1 < hp_pct2:
                return _result(2)
            elif hp_pct2 < hp_pct1:
                return _result(1)
            else:
                return _result(0)


def simulate_mixed_battle(units_team1, units_team2, return_hp=False):
    """Simulate a battle with 2 unit types per side (mixed army).

    Simplified vs simulate_battle(): no dismount, no transform, no dodge shield,
    no block first melee, no bleed, no kill bonus. Covers core mechanics:
    damage, armor, bonus damage, accuracy, reload, speed, trample, siege splash,
    extra projectiles, HP regen, opening volley, retarget delay.

    Args:
        units_team1: list of (combat_unit, count) tuples, e.g. [(knight, 15), (hussar, 10)]
        units_team2: list of (combat_unit, count) tuples
        return_hp: if True, returns 5-tuple with HP totals

    Returns: (winner, team1_remaining, team2_remaining) or
             (winner, team1_remaining, team2_remaining, hp_pct1, hp_pct2) if return_hp
    """

    # --- Flatten teams into per-unit arrays ---
    # Each unit gets a type_idx (0 or 1) within its team
    def _flatten_team(unit_list):
        """Build per-unit arrays from [(combat_unit, count), ...]."""
        total = sum(c for _, c in unit_list)
        if total == 0:
            return None
        hp = [0.0] * total
        max_hp = [0.0] * total
        reload_arr = [0.0] * total
        delay_arr = [0.0] * total
        speed_arr = [0.0] * total
        accuracy_arr = [0.0] * total
        is_ranged_arr = [False] * total
        type_idx_arr = [0] * total
        extra_proj_arr = [0] * total
        first_burst_arr = [0] * total
        regen_arr = [0.0] * total
        min_range_arr = [0.0] * total

        idx = 0
        templates = []
        for ti, (cu, count) in enumerate(unit_list):
            rng = cu["attack_range"]
            is_rng = rng >= 1.0
            aspd = cu["attack_speed"] or 0.5
            rl = 1.0 / aspd if aspd > 0 else 2.0
            acc = cu.get("accuracy", 100) / 100.0
            spd = cu["movement_speed"]
            regen = cu["hp_regen"] / 60.0 * DT if cu["hp_regen"] > 0 else 0.0

            templates.append(
                {
                    "cu": cu,
                    "is_ranged": is_rng,
                    "range": rng,
                    "reload": rl,
                    "delay": cu["attack_delay"],
                    "speed": spd,
                    "accuracy": acc,
                    "extra_proj": cu["extra_projectiles"],
                    "first_burst": cu["first_attack_extra_projectiles"],
                    "is_siege": cu["is_siege_projectile"] == 1,
                    "siege_splash": _splash_targets(cu["splash_radius"])
                    if cu["is_siege_projectile"] == 1
                    else 0,
                    "splash_hit": _splash_targets(cu["splash_on_hit_radius"]),
                    "has_trample": (
                        cu["trample_percent"] > 0 or cu["trample_flat_damage"] > 0
                    )
                    and not is_rng,
                    "trample_radius": cu["trample_radius"],
                    "pass_through": cu["pass_through_percent"],
                    "min_range": cu["min_attack_range"],
                    "regen_per_tick": regen,
                }
            )

            for j in range(count):
                hp[idx] = float(cu["hp"])
                max_hp[idx] = float(cu["hp"])
                reload_arr[idx] = rl
                delay_arr[idx] = cu["attack_delay"]
                speed_arr[idx] = spd
                accuracy_arr[idx] = acc
                is_ranged_arr[idx] = is_rng
                type_idx_arr[idx] = ti
                extra_proj_arr[idx] = cu["extra_projectiles"]
                first_burst_arr[idx] = cu["first_attack_extra_projectiles"]
                regen_arr[idx] = regen
                min_range_arr[idx] = cu["min_attack_range"]
                idx += 1

        return {
            "total": total,
            "hp": hp,
            "max_hp": max_hp,
            "reload": reload_arr,
            "delay": delay_arr,
            "speed": speed_arr,
            "accuracy": accuracy_arr,
            "is_ranged": is_ranged_arr,
            "type_idx": type_idx_arr,
            "extra_proj": extra_proj_arr,
            "first_burst": first_burst_arr,
            "regen": regen_arr,
            "min_range": min_range_arr,
            "templates": templates,
            "units": unit_list,
        }

    t1 = _flatten_team(units_team1)
    t2 = _flatten_team(units_team2)
    if not t1 or not t2:
        if return_hp:
            return (0, 0, 0, 0.0, 0.0)
        return (0, 0, 0)

    count1, count2 = t1["total"], t2["total"]
    EXTRA_PROJ_ACCURACY = 0.5

    # --- Pre-compute damage matrix ---
    # dmg[attacker_type][defender_type] = (main_dmg, extra_proj_dmg, trample_dmg, trample_extra)
    n_types1 = len(t1["templates"])
    n_types2 = len(t2["templates"])

    # Team1 attacking team2
    dmg_1v2 = {}
    for ati in range(n_types1):
        a = t1["templates"][ati]["cu"]
        a_ranged = t1["templates"][ati]["is_ranged"]
        for dti in range(n_types2):
            d = t2["templates"][dti]["cu"]
            main = _calc_damage(
                a["attacks"],
                a["attack"],
                d["armors"],
                d["melee_armor"],
                d["pierce_armor"],
                a_ranged,
                ignores_pierce=a["ignores_pierce_armor"],
                ignores_melee=a["ignores_melee_armor"],
                bonus_damage_reduction=d["bonus_damage_reduction"],
            )
            # Extra projectile damage
            epa = a.get("extra_projectile_attacks")
            if epa and (
                a["extra_projectiles"] > 0 or a["first_attack_extra_projectiles"] > 0
            ):
                sec_base = epa.get(3, epa.get(4, 0))
                extra = _calc_damage(
                    epa,
                    sec_base,
                    d["armors"],
                    d["melee_armor"],
                    d["pierce_armor"],
                    a_ranged,
                    ignores_pierce=a["ignores_pierce_armor"],
                    ignores_melee=a["ignores_melee_armor"],
                    bonus_damage_reduction=d["bonus_damage_reduction"],
                )
            else:
                extra = main
            # Trample
            tmpl = t1["templates"][ati]
            if tmpl["has_trample"]:
                t_dmg = int(main * a["trample_percent"]) + a["trample_flat_damage"]
                t_extra = _splash_targets(a["trample_radius"])
            else:
                t_dmg, t_extra = 0, 0
            dmg_1v2[(ati, dti)] = (main, extra, t_dmg, t_extra)

    # Team2 attacking team1
    dmg_2v1 = {}
    for ati in range(n_types2):
        a = t2["templates"][ati]["cu"]
        a_ranged = t2["templates"][ati]["is_ranged"]
        for dti in range(n_types1):
            d = t1["templates"][dti]["cu"]
            main = _calc_damage(
                a["attacks"],
                a["attack"],
                d["armors"],
                d["melee_armor"],
                d["pierce_armor"],
                a_ranged,
                ignores_pierce=a["ignores_pierce_armor"],
                ignores_melee=a["ignores_melee_armor"],
                bonus_damage_reduction=d["bonus_damage_reduction"],
            )
            epa = a.get("extra_projectile_attacks")
            if epa and (
                a["extra_projectiles"] > 0 or a["first_attack_extra_projectiles"] > 0
            ):
                sec_base = epa.get(3, epa.get(4, 0))
                extra = _calc_damage(
                    epa,
                    sec_base,
                    d["armors"],
                    d["melee_armor"],
                    d["pierce_armor"],
                    a_ranged,
                    ignores_pierce=a["ignores_pierce_armor"],
                    ignores_melee=a["ignores_melee_armor"],
                    bonus_damage_reduction=d["bonus_damage_reduction"],
                )
            else:
                extra = main
            tmpl = t2["templates"][ati]
            if tmpl["has_trample"]:
                t_dmg = int(main * a["trample_percent"]) + a["trample_flat_damage"]
                t_extra = _splash_targets(a["trample_radius"])
            else:
                t_dmg, t_extra = 0, 0
            dmg_2v1[(ati, dti)] = (main, extra, t_dmg, t_extra)

    # --- Per-unit state ---
    cooldown1 = [0.0] * count1
    cooldown2 = [0.0] * count2
    used_first1 = [False] * count1
    used_first2 = [False] * count2
    prev_target1 = [-1] * count1
    prev_target2 = [-1] * count2

    start_total_hp1 = sum(t1["hp"])
    start_total_hp2 = sum(t2["hp"])

    hp1 = t1["hp"]
    hp2 = t2["hp"]

    # =========================================================
    # PHASE 1: Opening volley
    # =========================================================
    # Group attackers by type, calculate opening shots per type.
    # Only ranged types get opening shots.

    def _calc_opening_shots(attacker_tmpl, defender_templates, a_count):
        """Calculate number of free opening shots for one ranged attacker type
        vs the enemy team. Returns (shots, infinite_kite).
        infinite_kite=True means ranged can kite forever and never be caught."""
        if not attacker_tmpl["is_ranged"]:
            return 0, False

        a_range = attacker_tmpl["range"]
        a_speed = attacker_tmpl["speed"]
        a_reload = attacker_tmpl["reload"]
        a_delay = attacker_tmpl["delay"]
        a_min_range = attacker_tmpl["min_range"]

        # Check if any defender is melee (ranged vs melee = free shots)
        has_melee_enemy = any(not dt["is_ranged"] for dt in defender_templates)
        has_ranged_enemy = any(dt["is_ranged"] for dt in defender_templates)

        shots = 0
        if has_melee_enemy:
            # Use fastest melee enemy for closing time calc
            fastest_melee_speed = max(
                (dt["speed"] for dt in defender_templates if not dt["is_ranged"]),
                default=1.0,
            )
            fastest_melee_delay = min(
                (dt["delay"] for dt in defender_templates if not dt["is_ranged"]),
                default=0.0,
            )
            fire_dist = a_range - max(a_min_range, MELEE_RANGE)
            if fire_dist > 0 and fastest_melee_speed > 0:
                move_frac = max(0.0, 1.0 - a_delay / a_reload) if a_reload > 0 else 1.0
                eff_retreat = a_speed * move_frac
                net_speed = fastest_melee_speed - eff_retreat
                # Infinite kite: ranged effective retreat speed >= melee speed
                if net_speed <= 0:
                    return 0, True
                retreat_time = (
                    min(RETREAT_MAX / eff_retreat, fire_dist / net_speed)
                    if eff_retreat > 0
                    else fire_dist / net_speed
                )
                remaining_dist = fire_dist - net_speed * retreat_time
                stand_time = (
                    remaining_dist / fastest_melee_speed if remaining_dist > 0 else 0
                )
                closing_time = retreat_time + stand_time + fastest_melee_delay
                if closing_time > a_delay:
                    shots = 1 + int((closing_time - a_delay) / a_reload)
                # Kiting bonus: after initial retreat, ranged can keep distance
                if eff_retreat > 0 and fastest_melee_speed > eff_retreat:
                    speed_diff = fastest_melee_speed - eff_retreat
                    kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX
                    if kite_dist > 0:
                        kite_time = kite_dist / speed_diff
                        shots += max(0, int(kite_time / a_reload))
        elif has_ranged_enemy:
            # Both ranged: range difference gives bonus shots
            max_enemy_range = max(
                dt["range"] for dt in defender_templates if dt["is_ranged"]
            )
            max_enemy_speed = max(
                dt["speed"] for dt in defender_templates if dt["is_ranged"]
            )
            range_diff = a_range - max_enemy_range
            if range_diff > 0:
                shots = max(0, int(range_diff / 2))
                # If we also have more speed, we kite forever
                if a_speed > max_enemy_speed:
                    return shots, True

        return shots, False

    def _calc_mixed_opening_dmg(
        a_tmpl_idx, shots, a_team, d_team, dmg_matrix, a_used_first
    ):
        """Calculate opening volley damage into a pending list (not applied yet).
        Uses a simulated HP copy for focus-fire targeting.
        Returns list of (target_idx, damage) tuples."""
        if shots <= 0:
            return []
        tmpl = a_team["templates"][a_tmpl_idx]
        a_indices = [
            i for i in range(a_team["total"]) if a_team["type_idx"][i] == a_tmpl_idx
        ]
        if not a_indices:
            return []

        pending = []
        sim_hp = list(d_team["hp"])

        for _ in range(shots):
            d_alive = [i for i in range(d_team["total"]) if sim_hp[i] > 0]
            if not d_alive:
                break

            for a_idx in a_indices:
                d_alive_now = [i for i in range(d_team["total"]) if sim_hp[i] > 0]
                if not d_alive_now:
                    break

                target = min(d_alive_now, key=lambda i: sim_hp[i])
                d_type = d_team["type_idx"][target]

                main_dmg, extra_dmg, _, _ = dmg_matrix[(a_tmpl_idx, d_type)]
                num_extra = tmpl["extra_proj"]
                if tmpl["first_burst"] > 0 and not a_used_first[a_idx]:
                    num_extra += tmpl["first_burst"]
                    a_used_first[a_idx] = True

                # Main projectile
                if tmpl["accuracy"] >= 1.0 or random.random() < tmpl["accuracy"]:
                    pending.append((target, main_dmg))
                    sim_hp[target] -= main_dmg
                    # Siege splash
                    if tmpl["is_siege"] and tmpl["siege_splash"] > 0:
                        splashed = 0
                        for idx in d_alive_now:
                            if (
                                idx != target
                                and sim_hp[idx] > 0
                                and splashed < tmpl["siege_splash"]
                            ):
                                pending.append((idx, main_dmg))
                                sim_hp[idx] -= main_dmg
                                splashed += 1
                    # Splash on hit
                    if tmpl["splash_hit"] > 0:
                        splashed = 0
                        for idx in d_alive_now:
                            if (
                                idx != target
                                and sim_hp[idx] > 0
                                and splashed < tmpl["splash_hit"]
                            ):
                                pending.append((idx, main_dmg))
                                sim_hp[idx] -= main_dmg
                                splashed += 1
                    # Pass-through
                    if tmpl["pass_through"] > 0:
                        pt_dmg = max(1, int(main_dmg * tmpl["pass_through"]))
                        for idx in d_alive_now:
                            if idx != target and sim_hp[idx] > 0:
                                pending.append((idx, pt_dmg))
                                sim_hp[idx] -= pt_dmg
                                break

                # Extra projectiles (scatter)
                for _ in range(num_extra):
                    if random.random() < EXTRA_PROJ_ACCURACY:
                        pending.append((target, extra_dmg))
                        sim_hp[target] -= extra_dmg

        return pending

    # Calculate opening volleys for both teams simultaneously, then apply
    opening_dmg_vs_t2 = []
    opening_dmg_vs_t1 = []
    t1_infinite_kite = False
    t2_infinite_kite = False
    for ti in range(n_types1):
        shots, inf_kite = _calc_opening_shots(
            t1["templates"][ti], t2["templates"], count1
        )
        if inf_kite:
            t1_infinite_kite = True
        opening_dmg_vs_t2.extend(
            _calc_mixed_opening_dmg(ti, shots, t1, t2, dmg_1v2, used_first1)
        )
    for ti in range(n_types2):
        shots, inf_kite = _calc_opening_shots(
            t2["templates"][ti], t1["templates"], count2
        )
        if inf_kite:
            t2_infinite_kite = True
        opening_dmg_vs_t1.extend(
            _calc_mixed_opening_dmg(ti, shots, t2, t1, dmg_2v1, used_first2)
        )

    # Infinite kite: if one side can kite forever and the other can't,
    # the kiting side wins without needing full simulation
    if t1_infinite_kite and not t2_infinite_kite:

        def _result(winner):
            if return_hp:
                return (winner, count1, 0, 1.0, 0.0)
            return (winner, count1, 0)

        return _result(1)
    if t2_infinite_kite and not t1_infinite_kite:

        def _result(winner):
            if return_hp:
                return (winner, 0, count2, 0.0, 1.0)
            return (winner, 0, count2)

        return _result(2)

    # Apply opening damage atomically (both teams fire simultaneously)
    for target_idx, damage in opening_dmg_vs_t2:
        hp2[target_idx] -= damage
    for target_idx, damage in opening_dmg_vs_t1:
        hp1[target_idx] -= damage

    # =========================================================
    # PHASE 2: Tick-based combat loop
    # =========================================================

    for tick in range(MAX_TICKS):
        alive1 = _get_alive_targets(hp1, count1)
        alive2 = _get_alive_targets(hp2, count2)
        if not alive1 or not alive2:
            break

        # Decrement cooldowns
        for i in alive1:
            cooldown1[i] = max(0.0, cooldown1[i] - DT)
        for i in alive2:
            cooldown2[i] = max(0.0, cooldown2[i] - DT)

        # Assign targets per unit:
        # - Melee: engage enemy melee first (spread, up to 2:1), overflow to enemy ranged
        # - Ranged: target enemy melee first (focus fire), then enemy ranged
        def _assign_mixed(my_alive, my_team, enemy_alive, enemy_hp, enemy_team):
            targets = {}
            if not enemy_alive:
                return targets

            # Split enemies into melee and ranged
            enemy_melee = [e for e in enemy_alive if not enemy_team["is_ranged"][e]]
            enemy_ranged = [e for e in enemy_alive if enemy_team["is_ranged"][e]]

            # Split my units into melee and ranged
            my_melee = [i for i in my_alive if not my_team["is_ranged"][i]]
            my_ranged = [i for i in my_alive if my_team["is_ranged"][i]]

            # Melee targeting: engage enemy melee first (2 per enemy melee), overflow to ranged
            melee_capacity = (
                len(enemy_melee) * 2
            )  # each enemy melee can be engaged by up to 2
            melee_on_melee = my_melee[:melee_capacity]
            melee_overflow = my_melee[melee_capacity:]

            # Assign melee-on-melee (spread evenly among enemy melee)
            if enemy_melee and melee_on_melee:
                for li, i in enumerate(melee_on_melee):
                    targets[i] = enemy_melee[
                        li * len(enemy_melee) // len(melee_on_melee)
                    ]

            # Overflow melee engage enemy ranged (spread evenly)
            if enemy_ranged and melee_overflow:
                for li, i in enumerate(melee_overflow):
                    targets[i] = enemy_ranged[
                        li * len(enemy_ranged) // len(melee_overflow)
                    ]
            elif melee_overflow and enemy_melee:
                # No enemy ranged, put overflow on enemy melee
                for li, i in enumerate(melee_overflow):
                    targets[i] = enemy_melee[
                        li * len(enemy_melee) // len(melee_overflow)
                    ]

            # Ranged targeting: focus fire enemy melee first, then enemy ranged
            if my_ranged:
                if enemy_melee:
                    # Focus fire lowest HP enemy melee
                    best = min(enemy_melee, key=lambda e: enemy_hp[e])
                    for i in my_ranged:
                        targets[i] = best
                elif enemy_ranged:
                    # Focus fire lowest HP enemy ranged
                    best = min(enemy_ranged, key=lambda e: enemy_hp[e])
                    for i in my_ranged:
                        targets[i] = best

            return targets

        targets1 = _assign_mixed(alive1, t1, alive2, hp2, t2)
        targets2 = _assign_mixed(alive2, t2, alive1, hp1, t1)

        pending_damage = []

        if tick % 2 == 0:
            team_order = [1, 2]
        else:
            team_order = [2, 1]

        for team_id in team_order:
            if team_id == 1:
                my_alive, my_team, my_targets = alive1, t1, targets1
                my_cooldown, my_used_first = cooldown1, used_first1
                my_prev_target = prev_target1
                enemy_hp, enemy_alive, enemy_team_data = hp2, alive2, t2
                dmg_matrix = dmg_1v2
                enemy_team_id = 2
            else:
                my_alive, my_team, my_targets = alive2, t2, targets2
                my_cooldown, my_used_first = cooldown2, used_first2
                my_prev_target = prev_target2
                enemy_hp, enemy_alive, enemy_team_data = hp1, alive1, t1
                dmg_matrix = dmg_2v1
                enemy_team_id = 1

            for i in my_alive:
                if my_cooldown[i] > 0:
                    continue

                my_ti = my_team["type_idx"][i]
                tmpl = my_team["templates"][my_ti]

                # Min range check: siege can't attack at melee range
                if tmpl["is_ranged"] and tmpl["min_range"] >= 2.0:
                    # Check if any enemy is melee (already closed in)
                    has_melee_enemy = any(
                        not enemy_team_data["is_ranged"][e] for e in enemy_alive
                    )
                    if has_melee_enemy:
                        continue

                target_idx = my_targets.get(i, -1)
                if target_idx < 0:
                    continue
                target_idx = _find_alive_target(target_idx, enemy_hp, enemy_alive)
                if target_idx < 0:
                    continue

                # Retarget delay for melee
                prev = my_prev_target[i]
                if prev >= 0 and target_idx != prev and not tmpl["is_ranged"]:
                    retarget_time = (
                        RETARGET_DIST / tmpl["speed"] if tmpl["speed"] > 0 else 2.0
                    )
                    my_cooldown[i] = retarget_time
                    my_prev_target[i] = target_idx
                    continue
                my_prev_target[i] = target_idx

                d_ti = enemy_team_data["type_idx"][target_idx]
                main_dmg, extra_dmg, trample_dmg, trample_extra = dmg_matrix[
                    (my_ti, d_ti)
                ]

                if tmpl["is_ranged"]:
                    num_extra = tmpl["extra_proj"]
                    if tmpl["first_burst"] > 0 and not my_used_first[i]:
                        num_extra += tmpl["first_burst"]
                        my_used_first[i] = True
                    # Main projectile with accuracy
                    if tmpl["accuracy"] >= 1.0 or random.random() < tmpl["accuracy"]:
                        pending_damage.append(
                            (enemy_team_id, target_idx, main_dmg, i, team_id)
                        )
                    # Extra projectiles
                    for _ in range(num_extra):
                        if random.random() < EXTRA_PROJ_ACCURACY:
                            pending_damage.append(
                                (enemy_team_id, target_idx, extra_dmg, i, team_id)
                            )
                    my_cooldown[i] = tmpl["reload"]
                else:
                    # Melee with delay
                    if tmpl["delay"] > 0:
                        # Simplified: add delay to cooldown, damage next cycle
                        my_cooldown[i] = tmpl["delay"]
                        # Queue damage at delay time (approximate: apply immediately)
                        pending_damage.append(
                            (enemy_team_id, target_idx, main_dmg, i, team_id)
                        )
                        my_cooldown[i] = tmpl["reload"]
                    else:
                        pending_damage.append(
                            (enemy_team_id, target_idx, main_dmg, i, team_id)
                        )
                        my_cooldown[i] = tmpl["reload"]

        # --- Apply pending damage ---
        for (
            target_team,
            target_idx,
            damage,
            attacker_idx,
            attacker_team,
        ) in pending_damage:
            if target_team == 1:
                t_hp = hp1
                all_alive = alive1
            else:
                t_hp = hp2
                all_alive = alive2

            if t_hp[target_idx] <= 0:
                continue

            t_hp[target_idx] -= damage

            # Get attacker info for splash/trample
            if attacker_team == 1:
                a_ti = t1["type_idx"][attacker_idx]
                a_tmpl = t1["templates"][a_ti]
                d_ti_lookup = (
                    t2["type_idx"][target_idx]
                    if target_team == 2
                    else t1["type_idx"][target_idx]
                )
                matrix = dmg_1v2
            else:
                a_ti = t2["type_idx"][attacker_idx]
                a_tmpl = t2["templates"][a_ti]
                d_ti_lookup = (
                    t1["type_idx"][target_idx]
                    if target_team == 1
                    else t2["type_idx"][target_idx]
                )
                matrix = dmg_2v1

            _, _, trample_dmg, trample_extra = matrix[(a_ti, d_ti_lookup)]

            # Trample
            if trample_dmg > 0 and trample_extra > 0:
                splashed = 0
                for idx in all_alive:
                    if idx != target_idx and t_hp[idx] > 0 and splashed < trample_extra:
                        t_hp[idx] -= trample_dmg
                        splashed += 1

            # Siege splash
            if a_tmpl["is_siege"] and a_tmpl["siege_splash"] > 0:
                splashed = 0
                for idx in all_alive:
                    if (
                        idx != target_idx
                        and t_hp[idx] > 0
                        and splashed < a_tmpl["siege_splash"]
                    ):
                        t_hp[idx] -= damage
                        splashed += 1

            # Splash on hit
            if a_tmpl["splash_hit"] > 0:
                splashed = 0
                for idx in all_alive:
                    if (
                        idx != target_idx
                        and t_hp[idx] > 0
                        and splashed < a_tmpl["splash_hit"]
                    ):
                        t_hp[idx] -= damage
                        splashed += 1

            # Pass-through: 1 additional unit takes a fraction of the damage
            if a_tmpl["pass_through"] > 0:
                pt_dmg = max(1, int(damage * a_tmpl["pass_through"]))
                for idx in all_alive:
                    if idx != target_idx and t_hp[idx] > 0:
                        t_hp[idx] -= pt_dmg
                        break

        # --- HP regeneration ---
        for i in alive1:
            if t1["regen"][i] > 0 and hp1[i] < t1["max_hp"][i]:
                hp1[i] = min(t1["max_hp"][i], hp1[i] + t1["regen"][i])
        for i in alive2:
            if t2["regen"][i] > 0 and hp2[i] < t2["max_hp"][i]:
                hp2[i] = min(t2["max_hp"][i], hp2[i] + t2["regen"][i])

    # =========================================================
    # PHASE 3: Winner determination
    # =========================================================
    remaining1 = sum(1 for h in hp1 if h > 0)
    remaining2 = sum(1 for h in hp2 if h > 0)
    total_hp1 = sum(max(0, h) for h in hp1)
    total_hp2 = sum(max(0, h) for h in hp2)
    hp_pct1 = total_hp1 / start_total_hp1 if start_total_hp1 > 0 else 0.0
    hp_pct2 = total_hp2 / start_total_hp2 if start_total_hp2 > 0 else 0.0

    def _result(winner):
        if return_hp:
            return (winner, remaining1, remaining2, hp_pct1, hp_pct2)
        return (winner, remaining1, remaining2)

    if remaining1 > 0 and remaining2 == 0:
        return _result(1)
    elif remaining2 > 0 and remaining1 == 0:
        return _result(2)
    else:
        lost1 = count1 - remaining1
        lost2 = count2 - remaining2
        if lost1 > lost2:
            return _result(2)
        elif lost2 > lost1:
            return _result(1)
        else:
            if hp_pct1 < hp_pct2:
                return _result(2)
            elif hp_pct2 < hp_pct1:
                return _result(1)
            else:
                return _result(0)
