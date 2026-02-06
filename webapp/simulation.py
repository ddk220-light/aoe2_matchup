"""
Data-driven battle simulation engine.

All unit-specific behaviors (siege projectiles, trample, armor-ignoring, etc.)
are read from unit dict fields populated from the database — no hardcoded slug lookups.

Used by both the matchup API (headless, many simulations) and can serve as the
reference implementation for the frontend JS simulator.
"""

import json

import numpy as np

# Simulation constants
DT = 0.05  # 50ms time step
MAX_TICKS = 5000  # 250 seconds max battle time
MELEE_RANGE = 0.5
MAP_MIN = 0.0
MAP_MAX = 100.0
HIT_RADIUS = 1.0  # Projectile dodge check radius


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
        "ignores_pierce_armor": row["ignores_pierce_armor"] or 0,
        "ignores_melee_armor": row["ignores_melee_armor"] or 0,
        "trample_percent": row["trample_percent"] or 0,
        "trample_radius": row["trample_radius"] or 0,
        "trample_flat_damage": row["trample_flat_damage"] or 0,
        "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
        # Unique unit mechanics
        "extra_projectiles": row["extra_projectiles"] or 0,
        "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
        "dodge_shield_max": row["dodge_shield_max"] or 0,
        "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
        "bleed_dps": row["bleed_dps"] or 0,
        "bleed_duration": row["bleed_duration"] or 0,
        "block_first_melee": row["block_first_melee"] or 0,
        "attack_bonus_per_kill": row["attack_bonus_per_kill"] or 0,
        "first_attack_extra_projectiles": row["first_attack_extra_projectiles"] or 0,
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


def simulate_battle(unit1, unit2, resources, fixed_count=None):
    """
    Tick-based battle simulation with kiting, siege projectiles, and trample.

    All unit-specific behaviors are read from unit dict fields — no slug lookups.

    Args:
        unit1/unit2: dicts from prepare_combat_unit() with pre-parsed attacks/armors
            and combat properties (min_attack_range, is_siege_projectile, etc.)
        resources: total resource pool for army sizing (ignored if fixed_count set)
        fixed_count: if set, both sides get this many units

    Returns: (winner, unit1_remaining, unit2_remaining)
        winner: 1 if unit1 wins, 2 if unit2 wins, 0 if draw
    """
    # Army sizes
    if fixed_count is not None:
        count1 = fixed_count
        count2 = fixed_count
    else:
        cost1 = unit1["cost"] if unit1["cost"] > 0 else 100
        cost2 = unit2["cost"] if unit2["cost"] > 0 else 100
        count1 = max(1, resources // cost1)
        count2 = max(1, resources // cost2)

    # Pre-parsed attacks/armors (already dicts with int keys from prepare_combat_unit)
    attacks1 = unit1["attacks"]
    armors1 = unit1["armors"]
    attacks2 = unit2["attacks"]
    armors2 = unit2["armors"]

    # Unit properties
    range1 = unit1["attack_range"]
    range2 = unit2["attack_range"]
    move_speed1 = unit1["movement_speed"]
    move_speed2 = unit2["movement_speed"]
    is_ranged1 = range1 >= 1.0
    is_ranged2 = range2 >= 1.0

    # Data-driven combat properties (from DB, no slug lookups)
    min_range1 = unit1["min_attack_range"]
    min_range2 = unit2["min_attack_range"]
    is_siege1 = unit1["is_siege_projectile"] == 1
    is_siege2 = unit2["is_siege_projectile"] == 1
    splash_radius1 = unit1["splash_radius"]
    splash_radius2 = unit2["splash_radius"]
    proj_speed1 = unit1["projectile_speed"]
    proj_speed2 = unit2["projectile_speed"]

    # Trample info
    tp1 = unit1["trample_percent"]
    tr1 = unit1["trample_radius"]
    tf1 = unit1["trample_flat_damage"]
    has_trample1 = (tp1 > 0 or tf1 > 0) and not is_ranged1
    tp2 = unit2["trample_percent"]
    tr2 = unit2["trample_radius"]
    tf2 = unit2["trample_flat_damage"]
    has_trample2 = (tp2 > 0 or tf2 > 0) and not is_ranged2

    # Pre-compute damage (deterministic, no RNG)
    dmg1 = _calc_damage(
        attacks1,
        unit1["attack"],
        armors2,
        unit2["melee_armor"],
        unit2["pierce_armor"],
        is_ranged1,
        ignores_pierce=unit1["ignores_pierce_armor"],
        ignores_melee=unit1["ignores_melee_armor"],
        bonus_damage_reduction=unit2["bonus_damage_reduction"],
    )
    dmg2 = _calc_damage(
        attacks2,
        unit2["attack"],
        armors1,
        unit1["melee_armor"],
        unit1["pierce_armor"],
        is_ranged2,
        ignores_pierce=unit2["ignores_pierce_armor"],
        ignores_melee=unit2["ignores_melee_armor"],
        bonus_damage_reduction=unit1["bonus_damage_reduction"],
    )

    # Pre-compute trample damage
    trample_dmg1 = int(dmg1 * tp1) + tf1 if has_trample1 else 0
    trample_dmg2 = int(dmg2 * tp2) + tf2 if has_trample2 else 0

    # Attack timing
    speed1 = unit1["attack_speed"] or 0.5
    speed2 = unit2["attack_speed"] or 0.5
    reload1 = 1.0 / speed1 if speed1 > 0 else 2.0
    reload2 = 1.0 / speed2 if speed2 > 0 else 2.0
    attack_delay1 = unit1["attack_delay"]
    attack_delay2 = unit2["attack_delay"]

    # Kiting: ranged vs melee only
    should_kite1 = is_ranged1 and not is_ranged2
    should_kite2 = is_ranged2 and not is_ranged1

    # Unique mechanic properties
    extra_proj1 = unit1["extra_projectiles"]
    extra_proj2 = unit2["extra_projectiles"]
    splash_hit_r1 = unit1["splash_on_hit_radius"]
    splash_hit_r2 = unit2["splash_on_hit_radius"]
    dodge_max1 = unit1["dodge_shield_max"]
    dodge_max2 = unit2["dodge_shield_max"]
    dodge_recharge1 = unit1["dodge_shield_recharge"]
    dodge_recharge2 = unit2["dodge_shield_recharge"]
    bleed_dps1 = unit1["bleed_dps"]
    bleed_dur1 = unit1["bleed_duration"]
    bleed_dps2 = unit2["bleed_dps"]
    bleed_dur2 = unit2["bleed_duration"]
    block_melee1 = unit1["block_first_melee"]
    block_melee2 = unit2["block_first_melee"]
    kill_bonus1 = unit1["attack_bonus_per_kill"]
    kill_bonus2 = unit2["attack_bonus_per_kill"]
    first_burst1 = unit1["first_attack_extra_projectiles"]
    first_burst2 = unit2["first_attack_extra_projectiles"]
    transform_thresh1 = unit1["hp_transform_threshold"]
    transform_thresh2 = unit2["hp_transform_threshold"]

    # Army state — numpy arrays for speed
    hp1 = np.full(count1, float(unit1["hp"]))
    hp2 = np.full(count2, float(unit2["hp"]))
    pos1 = np.arange(count1, dtype=np.float64) * 0.5
    pos2 = MAP_MAX - np.arange(count2, dtype=np.float64) * 0.5
    cooldown1 = np.zeros(count1)
    cooldown2 = np.zeros(count2)
    was_moving1 = np.ones(count1, dtype=bool)
    was_moving2 = np.ones(count2, dtype=bool)

    # Committed melee attacks (sparse, use dicts)
    committed1 = {}  # attacker_idx -> (target_idx, time_remaining)
    committed2 = {}

    # Unique mechanic state arrays
    # Dodge shield
    shield1 = np.full(count1, float(dodge_max1))
    shield2 = np.full(count2, float(dodge_max2))
    shield_timer1 = np.zeros(count1)
    shield_timer2 = np.zeros(count2)
    # Block first melee
    has_blocked1 = np.zeros(count1, dtype=bool)
    has_blocked2 = np.zeros(count2, dtype=bool)
    # Kill bonus
    bonus_atk1 = np.zeros(count1)
    bonus_atk2 = np.zeros(count2)
    # First attack burst
    used_first1 = np.zeros(count1, dtype=bool)
    used_first2 = np.zeros(count2, dtype=bool)
    # HP transform (Jian Swordsman)
    transformed1 = np.zeros(count1, dtype=bool)
    transformed2 = np.zeros(count2, dtype=bool)
    # Bleed effects (sparse: target_idx -> (dps, remaining_time))
    bleed_on1 = {}  # bleeds on team 1 units (applied by team 2)
    bleed_on2 = {}  # bleeds on team 2 units (applied by team 1)

    start_hp1 = float(hp1.sum())
    start_hp2 = float(hp2.sum())

    # Siege projectiles in flight
    projectiles = []

    for tick in range(MAX_TICKS):
        alive1 = np.where(hp1 > 0)[0]
        alive2 = np.where(hp2 > 0)[0]

        if len(alive1) == 0 or len(alive2) == 0:
            break

        # Early termination
        a1_pct = len(alive1) / count1
        a2_pct = len(alive2) / count2
        if a1_pct < 0.5 and a2_pct > 0.6:
            return (2, int(len(alive1)), int(len(alive2)))
        if a2_pct < 0.5 and a1_pct > 0.6:
            return (1, int(len(alive1)), int(len(alive2)))

        # Update cooldowns (vectorized)
        cooldown1[alive1] = np.maximum(0, cooldown1[alive1] - DT)
        cooldown2[alive2] = np.maximum(0, cooldown2[alive2] - DT)

        # Update siege projectiles
        new_projectiles = []
        for proj in projectiles:
            target_team, impact_pos, proj_pos, damage, splash_r, positions_at_fire = (
                proj
            )
            if proj_pos < impact_pos:
                proj_pos += proj_speed1 * DT if target_team == 2 else proj_speed2 * DT
                arrived = proj_pos >= impact_pos
            else:
                proj_pos -= proj_speed1 * DT if target_team == 2 else proj_speed2 * DT
                arrived = proj_pos <= impact_pos

            if arrived:
                if target_team == 1:
                    for idx in alive1:
                        if idx in positions_at_fire:
                            pos_at_fire = positions_at_fire[idx]
                            if abs(pos_at_fire - impact_pos) <= splash_r:
                                if abs(pos1[idx] - pos_at_fire) <= HIT_RADIUS:
                                    hp1[idx] -= damage
                else:
                    for idx in alive2:
                        if idx in positions_at_fire:
                            pos_at_fire = positions_at_fire[idx]
                            if abs(pos_at_fire - impact_pos) <= splash_r:
                                if abs(pos2[idx] - pos_at_fire) <= HIT_RADIUS:
                                    hp2[idx] -= damage
            else:
                new_projectiles.append(
                    (
                        target_team,
                        impact_pos,
                        proj_pos,
                        damage,
                        splash_r,
                        positions_at_fire,
                    )
                )
        projectiles = new_projectiles

        # Collect pending damage
        pending_damage = []

        # --- Team 1 actions ---
        pos2_alive = pos2[alive2]
        for i in alive1:
            # Find closest enemy
            dists = np.abs(pos2_alive - pos1[i])
            closest_local = np.argmin(dists)
            closest = alive2[closest_local]
            distance = dists[closest_local]
            attack_range = range1 if is_ranged1 else MELEE_RANGE

            if is_ranged1:
                in_range = distance <= attack_range
                too_close = min_range1 > 0 and distance < min_range1

                if too_close:
                    # Inside min range - retreat
                    pos1[i] = max(MAP_MIN, pos1[i] - move_speed1 * DT)
                    was_moving1[i] = True
                elif not was_moving1[i] and cooldown1[i] <= 0:
                    # Stopped and delay elapsed - fire!
                    num_proj = 1 + extra_proj1
                    if first_burst1 > 0 and not used_first1[i]:
                        num_proj += first_burst1
                        used_first1[i] = True
                    if is_siege1:
                        enemy_positions = {int(idx): float(pos2[idx]) for idx in alive2}
                        projectiles.append(
                            (
                                2,
                                float(pos2[closest]),
                                float(pos1[i]),
                                dmg1,
                                splash_radius1,
                                enemy_positions,
                            )
                        )
                    else:
                        hit_dmg = dmg1 + int(bonus_atk1[i])
                        for _ in range(num_proj):
                            pending_damage.append(
                                (2, int(closest), hit_dmg, int(i), float(pos1[i]))
                            )
                    cooldown1[i] = reload1
                    was_moving1[i] = True  # Start kiting next tick
                elif not was_moving1[i]:
                    # Stopped, waiting for attack delay - hold position
                    pass
                elif cooldown1[i] > 0 and should_kite1:
                    # On cooldown vs melee - kite away
                    pos1[i] = max(MAP_MIN, pos1[i] - move_speed1 * DT)
                elif cooldown1[i] > 0:
                    # On cooldown vs ranged - stand
                    pass
                elif in_range:
                    # In range, ready to fire, was moving - stop and apply delay
                    cooldown1[i] = attack_delay1
                    was_moving1[i] = False
                else:
                    # Ready to fire, not in range - move toward target
                    pos1[i] += move_speed1 * DT
            else:
                # Melee
                if i in committed1:
                    target_idx, time_left = committed1[i]
                    time_left -= DT
                    if time_left <= 0:
                        if hp2[target_idx] > 0:
                            hit_dmg = dmg1 + int(bonus_atk1[i])
                            pending_damage.append(
                                (2, target_idx, hit_dmg, int(i), float(pos1[i]))
                            )
                        del committed1[i]
                        cooldown1[i] = reload1
                        was_moving1[i] = False
                    else:
                        committed1[i] = (target_idx, time_left)
                elif distance <= attack_range:
                    if cooldown1[i] <= 0:
                        if attack_delay1 > 0:
                            committed1[i] = (int(closest), attack_delay1)
                            was_moving1[i] = False
                        else:
                            hit_dmg = dmg1 + int(bonus_atk1[i])
                            pending_damage.append(
                                (2, int(closest), hit_dmg, int(i), float(pos1[i]))
                            )
                            cooldown1[i] = reload1
                else:
                    pos1[i] += move_speed1 * DT
                    was_moving1[i] = True

        # --- Team 2 actions ---
        pos1_alive = pos1[alive1]
        for i in alive2:
            dists = np.abs(pos1_alive - pos2[i])
            closest_local = np.argmin(dists)
            closest = alive1[closest_local]
            distance = dists[closest_local]
            attack_range = range2 if is_ranged2 else MELEE_RANGE

            if is_ranged2:
                in_range = distance <= attack_range
                too_close = min_range2 > 0 and distance < min_range2

                if too_close:
                    # Inside min range - retreat
                    pos2[i] = min(MAP_MAX, pos2[i] + move_speed2 * DT)
                    was_moving2[i] = True
                elif not was_moving2[i] and cooldown2[i] <= 0:
                    # Stopped and delay elapsed - fire!
                    num_proj = 1 + extra_proj2
                    if first_burst2 > 0 and not used_first2[i]:
                        num_proj += first_burst2
                        used_first2[i] = True
                    if is_siege2:
                        enemy_positions = {int(idx): float(pos1[idx]) for idx in alive1}
                        projectiles.append(
                            (
                                1,
                                float(pos1[closest]),
                                float(pos2[i]),
                                dmg2,
                                splash_radius2,
                                enemy_positions,
                            )
                        )
                    else:
                        hit_dmg = dmg2 + int(bonus_atk2[i])
                        for _ in range(num_proj):
                            pending_damage.append(
                                (1, int(closest), hit_dmg, int(i), float(pos2[i]))
                            )
                    cooldown2[i] = reload2
                    was_moving2[i] = True  # Start kiting next tick
                elif not was_moving2[i]:
                    # Stopped, waiting for attack delay - hold position
                    pass
                elif cooldown2[i] > 0 and should_kite2:
                    # On cooldown vs melee - kite away
                    pos2[i] = min(MAP_MAX, pos2[i] + move_speed2 * DT)
                elif cooldown2[i] > 0:
                    # On cooldown vs ranged - stand
                    pass
                elif in_range:
                    # In range, ready to fire, was moving - stop and apply delay
                    cooldown2[i] = attack_delay2
                    was_moving2[i] = False
                else:
                    # Ready to fire, not in range - move toward target
                    pos2[i] -= move_speed2 * DT
            else:
                if i in committed2:
                    target_idx, time_left = committed2[i]
                    time_left -= DT
                    if time_left <= 0:
                        if hp1[target_idx] > 0:
                            hit_dmg = dmg2 + int(bonus_atk2[i])
                            pending_damage.append(
                                (1, target_idx, hit_dmg, int(i), float(pos2[i]))
                            )
                        del committed2[i]
                        cooldown2[i] = reload2
                        was_moving2[i] = False
                    else:
                        committed2[i] = (target_idx, time_left)
                elif distance <= attack_range:
                    if cooldown2[i] <= 0:
                        if attack_delay2 > 0:
                            committed2[i] = (int(closest), attack_delay2)
                            was_moving2[i] = False
                        else:
                            hit_dmg = dmg2 + int(bonus_atk2[i])
                            pending_damage.append(
                                (1, int(closest), hit_dmg, int(i), float(pos2[i]))
                            )
                            cooldown2[i] = reload2
                else:
                    pos2[i] -= move_speed2 * DT
                    was_moving2[i] = True

        # Update dodge shield recharge timers
        if dodge_max1 > 0:
            recharging1 = shield_timer1[alive1] > 0
            shield_timer1[alive1[recharging1]] -= DT
            recharged = alive1[recharging1][shield_timer1[alive1[recharging1]] <= 0]
            for idx in recharged:
                if shield1[idx] < dodge_max1:
                    shield1[idx] += 1
                    if shield1[idx] < dodge_max1:
                        shield_timer1[idx] = dodge_recharge1
                    else:
                        shield_timer1[idx] = 0
        if dodge_max2 > 0:
            recharging2 = shield_timer2[alive2] > 0
            shield_timer2[alive2[recharging2]] -= DT
            recharged = alive2[recharging2][shield_timer2[alive2[recharging2]] <= 0]
            for idx in recharged:
                if shield2[idx] < dodge_max2:
                    shield2[idx] += 1
                    if shield2[idx] < dodge_max2:
                        shield_timer2[idx] = dodge_recharge2
                    else:
                        shield_timer2[idx] = 0

        # Apply bleed damage
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

        # Apply damage (including trample, dodge shield, block, splash, bleed, kill bonus)
        for team, target, damage, attacker_idx, attacker_pos in pending_damage:
            if team == 1:
                # Attacker is team 2, target is team 1
                # Dodge shield check (team 1 unit dodging team 2 ranged attack)
                if dodge_max1 > 0 and is_ranged2 and shield1[target] > 0:
                    shield1[target] -= 1
                    shield_timer1[target] = dodge_recharge1
                    continue
                # Block first melee check
                if block_melee1 and not is_ranged2 and not has_blocked1[target]:
                    has_blocked1[target] = True
                    continue
                target_was_alive = hp1[target] > 0
                hp1[target] -= damage
                # Kill bonus for attacker (team 2)
                if kill_bonus2 > 0 and target_was_alive and hp1[target] <= 0:
                    bonus_atk2[attacker_idx] += kill_bonus2
                # Trample
                if trample_dmg2 > 0:
                    for idx in alive1:
                        if idx != target and abs(pos1[idx] - attacker_pos) <= tr2:
                            hp1[idx] -= trample_dmg2
                # Splash on hit (centered on target, not attacker)
                if splash_hit_r2 > 0:
                    for idx in alive1:
                        if (
                            idx != target
                            and abs(pos1[idx] - pos1[target]) <= splash_hit_r2
                        ):
                            hp1[idx] -= damage
                # Bleed application
                if bleed_dps2 > 0 and target_was_alive:
                    bleed_on1[target] = (bleed_dps2, bleed_dur2)
            else:
                # Attacker is team 1, target is team 2
                # Dodge shield check (team 2 unit dodging team 1 ranged attack)
                if dodge_max2 > 0 and is_ranged1 and shield2[target] > 0:
                    shield2[target] -= 1
                    shield_timer2[target] = dodge_recharge2
                    continue
                # Block first melee check
                if block_melee2 and not is_ranged1 and not has_blocked2[target]:
                    has_blocked2[target] = True
                    continue
                target_was_alive = hp2[target] > 0
                hp2[target] -= damage
                # Kill bonus for attacker (team 1)
                if kill_bonus1 > 0 and target_was_alive and hp2[target] <= 0:
                    bonus_atk1[attacker_idx] += kill_bonus1
                # Trample
                if trample_dmg1 > 0:
                    for idx in alive2:
                        if idx != target and abs(pos2[idx] - attacker_pos) <= tr1:
                            hp2[idx] -= trample_dmg1
                # Splash on hit (centered on target, not attacker)
                if splash_hit_r1 > 0:
                    for idx in alive2:
                        if (
                            idx != target
                            and abs(pos2[idx] - pos2[target]) <= splash_hit_r1
                        ):
                            hp2[idx] -= damage
                # Bleed application
                if bleed_dps1 > 0 and target_was_alive:
                    bleed_on2[target] = (bleed_dps1, bleed_dur1)

        # HP transformation check (Jian Swordsman)
        if transform_thresh1 > 0:
            threshold_hp = unit1["hp"] * transform_thresh1
            for idx in alive1:
                if not transformed1[idx] and hp1[idx] <= threshold_hp and hp1[idx] > 0:
                    transformed1[idx] = True
                    # Jian Swordsman: +3 attack, +0.15 speed, -2 melee armor
                    # Applied as permanent bonus_atk increase; speed/armor
                    # changes are hard to apply per-unit in this model,
                    # so we approximate with attack bonus only
                    bonus_atk1[idx] += 3
        if transform_thresh2 > 0:
            threshold_hp = unit2["hp"] * transform_thresh2
            for idx in alive2:
                if not transformed2[idx] and hp2[idx] <= threshold_hp and hp2[idx] > 0:
                    transformed2[idx] = True
                    bonus_atk2[idx] += 3

    # Determine winner
    remaining1 = int(np.sum(hp1 > 0))
    remaining2 = int(np.sum(hp2 > 0))

    if remaining1 > 0 and remaining2 == 0:
        return (1, remaining1, 0)
    elif remaining2 > 0 and remaining1 == 0:
        return (2, 0, remaining2)
    else:
        lost1 = count1 - remaining1
        lost2 = count2 - remaining2
        if lost1 > lost2:
            return (2, remaining1, remaining2)
        elif lost2 > lost1:
            return (1, remaining1, remaining2)
        else:
            total_hp1 = float(np.sum(np.maximum(0, hp1)))
            total_hp2 = float(np.sum(np.maximum(0, hp2)))
            hp_lost_pct1 = (start_hp1 - total_hp1) / start_hp1 if start_hp1 > 0 else 0
            hp_lost_pct2 = (start_hp2 - total_hp2) / start_hp2 if start_hp2 > 0 else 0
            if hp_lost_pct1 > hp_lost_pct2:
                return (2, remaining1, remaining2)
            elif hp_lost_pct2 > hp_lost_pct1:
                return (1, remaining1, remaining2)
            else:
                return (0, remaining1, remaining2)
