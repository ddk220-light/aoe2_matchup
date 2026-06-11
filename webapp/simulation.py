"""Role: engine — Engine 1 of 3: ABSTRACT tick-based sim (damage-only, no positions).

Used by the live Matchup Advisor (/api/matchup-sims via best_units) — NOT by
the batch matchup data, which runs simulation_real.py (Engine 2, position-based);
the interactive Battle Sim page runs static/js/simulate.js (Engine 3) client-side.
This file is NOT hashed into sim_version; the golden-baseline test
(tests/test_simulations.py) is its only regression guard.

All unit-specific behaviors (siege projectiles, trample, armor-ignoring, etc.)
are read from unit dict fields populated from the database — no hardcoded slug lookups.

Uses a tick-based damage loop with pre-calculated opening volleys for
range/kiting advantages. No XY positions or unit movement.
"""

import json
import random

try:
    from analysis.ability_registry import combat_dict_defaults
except ImportError:  # pragma: no cover - webapp/ on sys.path, repo root not
    import sys
    from pathlib import Path

    _ROOT = str(Path(__file__).resolve().parents[1])
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from analysis.ability_registry import combat_dict_defaults

# Simulation constants
DT = 0.1  # 100ms time step
MAX_TICKS = 2500  # 250 seconds max battle time
MELEE_RANGE = 0.5
MAP_SPACE = 22.0  # ~tiles of combat space (MAP_MAX - 2*start_offset)
RETARGET_DIST = 1.5  # tiles to walk when switching to a new melee target
UNIT_SPACING = 0.75  # approximate unit spacing in melee clump
RETREAT_MAX = 10.0  # max tiles ranged retreats before standing to fight
TRAMPLE_HIT_CHANCE = 0.25  # fraction of trample attacks that hit a nearby unit
MELEE_ENGAGE_START = 0.3    # initial fraction of ranged engageable when melee arrives
MELEE_ENGAGE_STEP = 0.1    # increase per attack round (every ~2 seconds)
MELEE_ENGAGE_ROUND_TICKS = 20  # ticks per "attack round" for ramp (~2 seconds)
MELEE_MAX_PER_TARGET = 1   # max melee attackers per ranged target
MELEE_VS_MELEE_MAX = 2     # soft cap for melee-vs-melee targeting
MELEE_VS_MELEE_RAMP_TICKS = 20  # ticks before next attacker can engage (~2.0s, one attack cycle)
INF_VS_CAV_INITIAL_CAP = 2  # infantry can stack 2-wide on large cavalry hitboxes immediately
INF_VS_CAV_MAX_CAP = 3      # infantry can stack 3-wide on cavalry after pathing delay


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


# Neutral defaults for every ability key, declared once in the registry
# (analysis/ability_registry.py) — Phase B of data-model-review §3.2.
_ABILITY_DEFAULTS = combat_dict_defaults()

# Scalar ability keys prepare_combat_unit emits, in the legacy emission order.
# The KEY LIST stays pinned here because the abstract engine consumes a
# deliberate SUBSET of the registry (it parses charge_projectile_speed /
# hp_regen_in_combat without acting on them, and skips position/JS-only params
# like charge_attack_range and the resources_per_kill trio); the DEFAULTS come
# from the registry. JSON-carrying params (extra/charge projectile attacks)
# and the transform/dismount blocks are parsed separately below.
_PREPARE_SCALAR_KEYS = (
    "min_attack_range",
    "is_siege_projectile",
    "splash_radius",
    "projectile_speed",
    "ignores_pierce_armor",
    "ignores_melee_armor",
    "trample_percent",
    "trample_radius",
    "trample_flat_damage",
    "bonus_damage_reduction",
    "extra_projectiles",
    "splash_on_hit_radius",
    "splash_on_hit_fraction",
    "dodge_shield_max",
    "dodge_shield_recharge",
    "bleed_dps",
    "bleed_duration",
    "block_first_melee",
    "attack_bonus_per_kill",
    "first_attack_extra_projectiles",
    "hp_regen",
    "hp_regen_in_combat",
    "pass_through_percent",
    "pass_through_count",
    "extra_proj_scatter",
    "miss_damage_percent",
    "hp_per_kill",
    "hp_per_kill_max",
    "hp_transform_threshold",
    "pop_space",
    "armor_strip_per_hit",
    "charge_attack_melee",
    "charge_recharge_time",
    "charge_projectile_count",
    "charge_projectile_speed",
    "attack_bonus_nearby",
    "nearby_bonus_count",
    "damage_reflect_percent",
    "attack_speed_ramp",
    "attack_speed_min",
    "hp_nearby_percent_per_unit",
    "hp_nearby_max_units",
    "execute_damage_per_step",
    "execute_hp_step",
    "charge_slow_percent",
    "charge_slow_duration",
    "ally_death_heal",
    "ally_death_heal_duration",
)

_unknown = [k for k in _PREPARE_SCALAR_KEYS if k not in _ABILITY_DEFAULTS]
if _unknown:
    raise RuntimeError(
        f"prepare_combat_unit keys not declared in the ability registry: {_unknown}"
    )
del _unknown


def prepare_combat_unit(row):
    """Convert a DB row (sqlite3.Row or dict) into a combat-ready unit dict.

    Parses JSON fields once so simulate_battle() never has to.
    Call this ONCE per unit before running simulations.

    Scalar ability keys are filled from _PREPARE_SCALAR_KEYS with neutral
    defaults from the ability registry; in practice `row` is a dict from
    combat_unit_loader.build_combat_dict_from_ref (the pre-registry version
    already relied on dict-only .get() for half of these keys).
    """
    attacks = json.loads(row["attacks_json"]) if row["attacks_json"] else {}
    armors = json.loads(row["armors_json"]) if row["armors_json"] else {}
    attacks = {int(k): v for k, v in attacks.items()}
    armors = {int(k): v for k, v in armors.items()}
    cost = (row["cost_food"] or 0) + (row["cost_wood"] or 0) + (row["cost_gold"] or 0)

    unit = {
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
        "accuracy": row.get("accuracy", 100) if hasattr(row, "get") else 100,
        "base_accuracy": (row.get("base_accuracy", 100) if hasattr(row, "get") else 100) or 100,
    }

    # Scalar ability keys: null-coalesce to the registry default.
    for key in _PREPARE_SCALAR_KEYS:
        default = _ABILITY_DEFAULTS[key]
        unit[key] = row.get(key, default) or default

    unit.update({
        # Volley damage profiles, parsed once (None = reuse primary profile)
        "extra_projectile_attacks": {
            int(k): v
            for k, v in json.loads(row["extra_projectile_attacks_json"]).items()
        }
        if row["extra_projectile_attacks_json"]
        else None,
        "charge_projectile_attacks": {
            int(k): v
            for k, v in json.loads(row["charge_projectile_attacks_json"]).items()
        }
        if row.get("charge_projectile_attacks_json")
        else None,
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
        # Form-change blocks (Jian transform, Konnik dismount)
        "transform": _parse_transform(row),
        "dismount": _parse_dismount(row),
        # Outline size — passed through for position-aware simulation_real.py.
        # The fast (tick-based) sim does not use it.
        "outline_size": row.get("outline_size", 0.2) if hasattr(row, "get") else (
            row["outline_size"] if "outline_size" in (row.keys() if hasattr(row, "keys") else row) else 0.2
        ),
    })
    return unit


def _does_melee_damage(attacks):
    """True if unit's primary damage type is melee (class 4), not pierce (class 3).
    Units like Mameluke, Throwing Axeman, Kamayuk do melee damage at range."""
    has_pierce = attacks.get(3, 0) > 0
    has_melee = attacks.get(4, 0) > 0
    if has_melee and not has_pierce:
        return True
    if has_pierce and not has_melee:
        return False
    # Both or neither: default to melee
    return True


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
    melee_damage=False,
):
    """Calculate damage per hit between two unit types.
    melee_damage=True means attacker does melee damage (use melee armor) even at range."""
    if is_ranged and not melee_damage:
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
        # Skip base damage classes (3=pierce, 4=melee)
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


def _assign_targets_melee_capped(my_alive, enemy_alive, tick):
    """Assign melee attackers to ranged targets with rolling engagement limits.

    Rules:
    - Engagement ratio ramps from MELEE_ENGAGE_START (30%) up by MELEE_ENGAGE_STEP
      (10%) each attack round (~2 seconds), capping at 100%
    - Each engageable target gets exactly MELEE_MAX_PER_TARGET attacker
    - Surplus melee units get no target (they idle that tick)
    - Melee units lock onto targets until they die; no rotation needed.
      As enemies die, new ones naturally enter the engageable pool.
    """
    if not enemy_alive:
        return {}
    n_enemy = len(enemy_alive)
    # Rolling engagement ratio: starts at 30%, increases 10% every ~2 seconds
    attack_round = tick // MELEE_ENGAGE_ROUND_TICKS
    engage_ratio = min(1.0, MELEE_ENGAGE_START + attack_round * MELEE_ENGAGE_STEP)
    engageable_count = max(1, int(n_enemy * engage_ratio))
    # Always target the first N enemies in the alive list (no rotation).
    # When targets die they leave alive list, naturally exposing new targets.
    engageable = enemy_alive[:engageable_count]
    # Assign 1 melee per engageable target, up to MELEE_MAX_PER_TARGET
    assignments = {}
    slots_used = {}
    slot_idx = 0
    for i in my_alive:
        if slot_idx >= len(engageable):
            break
        target = engageable[slot_idx]
        assignments[i] = target
        slots_used[target] = slots_used.get(target, 0) + 1
        if slots_used[target] >= MELEE_MAX_PER_TARGET:
            slot_idx += 1
    return assignments


def _assign_targets_spread_capped(my_alive, enemy_alive, tick=0,
                                   initial_cap=1, max_cap=MELEE_VS_MELEE_MAX):
    """Assign melee attackers spread across enemies with a per-target cap.

    Same as _assign_targets_spread but limits each enemy to a cap that ramps
    from initial_cap to max_cap after pathing delay. Infantry vs cavalry uses
    higher caps (2→3) since cavalry hitboxes allow more surrounding.
    Surplus melee units beyond the total cap get no target.
    """
    if not enemy_alive:
        return {}
    # Ramp: initial_cap at start, max_cap after pathing delay
    cap = initial_cap if tick < MELEE_VS_MELEE_RAMP_TICKS else max_cap
    assignments = {}
    slots_used = {}
    total_slots = len(enemy_alive) * cap
    n_en = len(enemy_alive)
    assigned = 0
    for li, i in enumerate(my_alive):
        if assigned >= total_slots:
            break
        target_pos = li % n_en
        target = enemy_alive[target_pos]
        if slots_used.get(target, 0) >= cap:
            found = False
            for offset in range(1, n_en):
                alt = enemy_alive[(target_pos + offset) % n_en]
                if slots_used.get(alt, 0) < cap:
                    target = alt
                    found = True
                    break
            if not found:
                break
        assignments[i] = target
        slots_used[target] = slots_used.get(target, 0) + 1
        assigned += 1
    return assignments


def _assign_targets_focus(
    my_alive,
    enemy_alive,
    enemy_hp,
    dmg_per_hit,
    num_proj,
    extra_dmg=None,
    extra_accuracy=1.0,
):
    """Focus-fire targeting: group just enough attackers to kill each enemy.

    Assigns attackers to the first enemy until enough are assigned to kill it
    (based on expected damage per shot), then moves to the next enemy.

    `dmg_per_hit` is the main projectile's damage. When a unit fires extra
    projectiles whose damage differs from main (e.g. Shu Bolt Magazine adds a
    1-pierce arrow alongside a 10-pierce main, or Chu Ko Nu's secondary arrows
    deal less than the primary), pass `extra_dmg` so the assignment reflects
    expected per-shot damage = main + extra * (num_proj - 1) * extra_accuracy.
    Without this, units with weak extras get OVER-estimated and the sim
    under-assigns attackers, leaving targets alive longer than they should.
    """
    if not enemy_alive:
        return {}
    if extra_dmg is None:
        per_shot = dmg_per_hit * num_proj
    else:
        per_shot = dmg_per_hit + extra_dmg * (num_proj - 1) * extra_accuracy
    assignments = {}
    e_idx = 0  # current enemy target index
    assigned_dmg = 0.0  # damage assigned to current target so far
    for i in my_alive:
        if e_idx >= len(enemy_alive):
            e_idx = 0  # wrap around if more attackers than needed
            assigned_dmg = 0.0
        assignments[i] = enemy_alive[e_idx]
        assigned_dmg += per_shot
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


class BattleState:
    """Mutable state bundle for simulate_battle().

    Holds all per-unit arrays, pre-computed damage values, and combat
    constants so that phase functions can read/write them without 30+
    argument signatures.  Created by _init_battle_state().
    """
    pass


def _init_battle_state(unit1, unit2, resources, fixed_count, cost1_override, cost2_override):
    """Set up all pre-computed values and per-unit arrays for a battle.

    Returns a populated BattleState with every variable the tick loop needs.
    """
    s = BattleState()
    s.unit1 = unit1
    s.unit2 = unit2

    # --- Army sizes ---
    if fixed_count is not None:
        pop1 = unit1.get("pop_space", 1.0)
        pop2 = unit2.get("pop_space", 1.0)
        s.count1 = int(fixed_count / pop1)
        s.count2 = int(fixed_count / pop2)
    else:
        cost1 = cost1_override or (unit1["cost"] if unit1["cost"] > 0 else 100)
        cost2 = cost2_override or (unit2["cost"] if unit2["cost"] > 0 else 100)
        s.count1 = int(max(1, resources // cost1))
        s.count2 = int(max(1, resources // cost2))

    count1 = s.count1
    count2 = s.count2

    # --- Unit properties ---
    s.range1 = unit1["attack_range"]
    s.range2 = unit2["attack_range"]
    s.melee_dmg1 = _does_melee_damage(unit1["attacks"])
    s.melee_dmg2 = _does_melee_damage(unit2["attacks"])
    # Melee-at-range units with short range (Steppe Lancer, Kamayuk) are treated as melee
    s.is_ranged1 = s.range1 >= 1.0 and not (s.melee_dmg1 and s.range1 < 2.0)
    s.is_ranged2 = s.range2 >= 1.0 and not (s.melee_dmg2 and s.range2 < 2.0)
    s.speed1 = unit1["movement_speed"]
    s.speed2 = unit2["movement_speed"]
    # Accuracy: primary projectiles always hit (distance reduces miss chance to ~0).
    # Primary projectile uses the unit's `accuracy` (post-Thumb-Ring final
    # value, e.g. 100% for arbalester / Chu Ko Nu first arrow with TR).
    # Extra projectiles use `base_accuracy` (Thumb Ring is a primary-only
    # bonus per Fandom, e.g. CKN extras stay at 85% even with TR).
    s.accuracy1 = (unit1.get("accuracy", 100) or 100) / 100.0
    s.accuracy2 = (unit2.get("accuracy", 100) or 100) / 100.0
    s.extra_accuracy1 = (unit1.get("base_accuracy", 100) or 100) / 100.0
    s.extra_accuracy2 = (unit2.get("base_accuracy", 100) or 100) / 100.0
    # Default extra-projectile accuracy, read by the damage phases (via
    # `s.EXTRA_PROJ_ACCURACY`) when a side has no per-side extra accuracy.
    s.EXTRA_PROJ_ACCURACY = 0.85

    # Attack timing
    aspeed1 = unit1["attack_speed"] or 0.5
    aspeed2 = unit2["attack_speed"] or 0.5
    s.reload1 = 1.0 / aspeed1 if aspeed1 > 0 else 2.0
    s.reload2 = 1.0 / aspeed2 if aspeed2 > 0 else 2.0
    s.delay1 = unit1["attack_delay"]
    s.delay2 = unit2["attack_delay"]
    s.min_range1 = unit1["min_attack_range"]
    s.min_range2 = unit2["min_attack_range"]

    # Pre-compute damage
    s.dmg1 = _calc_damage(
        unit1["attacks"],
        unit1["attack"],
        unit2["armors"],
        unit2["melee_armor"],
        unit2["pierce_armor"],
        s.is_ranged1,
        ignores_pierce=unit1["ignores_pierce_armor"],
        ignores_melee=unit1["ignores_melee_armor"],
        bonus_damage_reduction=unit2["bonus_damage_reduction"],
        melee_damage=s.melee_dmg1,
    )
    s.dmg2 = _calc_damage(
        unit2["attacks"],
        unit2["attack"],
        unit1["armors"],
        unit1["melee_armor"],
        unit1["pierce_armor"],
        s.is_ranged2,
        ignores_pierce=unit2["ignores_pierce_armor"],
        ignores_melee=unit2["ignores_melee_armor"],
        bonus_damage_reduction=unit1["bonus_damage_reduction"],
        melee_damage=s.melee_dmg2,
    )

    # Nearby ally attack bonus (Monaspa): pre-compute as flat damage addition
    nearby_bonus1 = unit1.get("attack_bonus_nearby", 0)
    if nearby_bonus1 > 0:
        max_nearby1 = unit1.get("nearby_bonus_count", 4)
        effective_nearby1 = min(max_nearby1, count1 - 1)
        s.dmg1 += nearby_bonus1 * effective_nearby1

    nearby_bonus2 = unit2.get("attack_bonus_nearby", 0)
    if nearby_bonus2 > 0:
        max_nearby2 = unit2.get("nearby_bonus_count", 4)
        effective_nearby2 = min(max_nearby2, count2 - 1)
        s.dmg2 += nearby_bonus2 * effective_nearby2

    # Trample (melee only)
    tp1, tr1, tf1 = (
        unit1["trample_percent"],
        unit1["trample_radius"],
        unit1["trample_flat_damage"],
    )
    s.has_trample1 = (tp1 > 0 or tf1 > 0) and not s.is_ranged1
    s.trample_dmg1 = (int(s.dmg1 * tp1) + tf1) if s.has_trample1 else 0
    s.trample_extra1 = _splash_targets(tr1) if s.has_trample1 else 0

    tp2, tr2, tf2 = (
        unit2["trample_percent"],
        unit2["trample_radius"],
        unit2["trample_flat_damage"],
    )
    s.has_trample2 = (tp2 > 0 or tf2 > 0) and not s.is_ranged2
    s.trample_dmg2 = (int(s.dmg2 * tp2) + tf2) if s.has_trample2 else 0
    s.trample_extra2 = _splash_targets(tr2) if s.has_trample2 else 0

    # Siege splash
    s.is_siege1 = unit1["is_siege_projectile"] == 1
    s.is_siege2 = unit2["is_siege_projectile"] == 1
    s.siege_splash1 = _splash_targets(unit1["splash_radius"]) if s.is_siege1 else 0
    s.siege_splash2 = _splash_targets(unit2["splash_radius"]) if s.is_siege2 else 0

    # Splash on hit
    s.splash_hit1 = _splash_targets(unit1["splash_on_hit_radius"])
    s.splash_hit2 = _splash_targets(unit2["splash_on_hit_radius"])
    s.splash_hit_frac1 = unit1["splash_on_hit_fraction"]
    s.splash_hit_frac2 = unit2["splash_on_hit_fraction"]

    # Pass-through damage (Scorpion bolts, Pirotecnia)
    s.pass_through1 = unit1["pass_through_percent"]
    s.pass_through2 = unit2["pass_through_percent"]
    s.pass_through_count1 = unit1["pass_through_count"]
    s.pass_through_count2 = unit2["pass_through_count"]

    # Extra projectile scatter (Organ Gun)
    s.extra_proj_scatter1 = unit1["extra_proj_scatter"]
    s.extra_proj_scatter2 = unit2["extra_proj_scatter"]

    # Extra projectiles
    s.extra_proj1 = unit1["extra_projectiles"]
    s.extra_proj2 = unit2["extra_projectiles"]
    s.first_burst1 = unit1["first_attack_extra_projectiles"]
    s.first_burst2 = unit2["first_attack_extra_projectiles"]

    # Extra projectile damage (secondary projectile has different attacks)
    # e.g. Chu Ko Nu extra arrows: 3 pierce only, vs main: 8 pierce + anti-spearman
    extra_proj_attacks1 = unit1.get("extra_projectile_attacks")
    extra_proj_attacks2 = unit2.get("extra_projectile_attacks")

    if extra_proj_attacks1 and (s.extra_proj1 > 0 or s.first_burst1 > 0):
        sec_base1 = extra_proj_attacks1.get(3, extra_proj_attacks1.get(4, 0))
        s.extra_proj_dmg1 = _calc_damage(
            extra_proj_attacks1,
            sec_base1,
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            s.is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
            melee_damage=_does_melee_damage(extra_proj_attacks1),
        )
    else:
        s.extra_proj_dmg1 = s.dmg1  # No secondary attacks: extra proj same as main

    if extra_proj_attacks2 and (s.extra_proj2 > 0 or s.first_burst2 > 0):
        sec_base2 = extra_proj_attacks2.get(3, extra_proj_attacks2.get(4, 0))
        s.extra_proj_dmg2 = _calc_damage(
            extra_proj_attacks2,
            sec_base2,
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            s.is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
            melee_damage=_does_melee_damage(extra_proj_attacks2),
        )
    else:
        s.extra_proj_dmg2 = s.dmg2

    # Unique mechanics
    s.dodge_max1 = unit1["dodge_shield_max"]
    s.dodge_max2 = unit2["dodge_shield_max"]
    s.dodge_recharge1 = unit1["dodge_shield_recharge"]
    s.dodge_recharge2 = unit2["dodge_shield_recharge"]
    s.bleed_dps1, s.bleed_dur1 = unit1["bleed_dps"], unit1["bleed_duration"]
    s.bleed_dps2, s.bleed_dur2 = unit2["bleed_dps"], unit2["bleed_duration"]
    # HP regen: stored as HP/minute, convert to HP/tick
    s.regen_per_tick1 = unit1["hp_regen"] / 60.0 * DT if unit1["hp_regen"] > 0 else 0.0
    s.regen_per_tick2 = unit2["hp_regen"] / 60.0 * DT if unit2["hp_regen"] > 0 else 0.0
    s.max_hp1 = float(unit1["hp"])
    s.max_hp2 = float(unit2["hp"])
    s.block_melee1 = unit1["block_first_melee"]
    s.block_melee2 = unit2["block_first_melee"]
    s.kill_bonus1 = unit1["attack_bonus_per_kill"]
    s.kill_bonus2 = unit2["attack_bonus_per_kill"]
    s.hp_per_kill1 = unit1.get("hp_per_kill", 0)
    s.hp_per_kill2 = unit2.get("hp_per_kill", 0)
    s.hp_per_kill_max1 = unit1.get("hp_per_kill_max", 0)
    s.hp_per_kill_max2 = unit2.get("hp_per_kill_max", 0)
    s.miss_dmg_pct1 = unit1.get("miss_damage_percent", 0)
    s.miss_dmg_pct2 = unit2.get("miss_damage_percent", 0)
    s.transform_thresh1 = unit1["hp_transform_threshold"]
    s.transform_thresh2 = unit2["hp_transform_threshold"]

    # Kiting: ranged vs melee only
    s.should_kite1 = s.is_ranged1 and not s.is_ranged2
    s.should_kite2 = s.is_ranged2 and not s.is_ranged1

    # Min range: units with high min_range can't attack in melee phase
    # (e.g. mangonels min_range=3, can't hit units at melee range)
    s.cant_attack_melee1 = s.is_ranged1 and s.min_range1 >= 2.0 and not s.is_ranged2
    s.cant_attack_melee2 = s.is_ranged2 and s.min_range2 >= 2.0 and not s.is_ranged1

    # --- Per-unit state (plain Python lists) ---
    s.hp1 = [float(unit1["hp"])] * count1
    s.hp2 = [float(unit2["hp"])] * count2

    # Percentage-based HP bonus from nearby allies (Shu Coiled Serpent Array)
    # +X% HP per nearby qualifying unit, capped at max_units
    pct1 = unit1.get("hp_nearby_percent_per_unit", 0)
    if pct1 > 0:
        max_n1 = unit1.get("hp_nearby_max_units", 30)
        eff1 = min(max_n1, count1 - 1)
        hp_mult1 = 1.0 + (pct1 * eff1 / 100.0)
        for i in range(count1):
            s.hp1[i] = s.hp1[i] * hp_mult1
    pct2 = unit2.get("hp_nearby_percent_per_unit", 0)
    if pct2 > 0:
        max_n2 = unit2.get("hp_nearby_max_units", 30)
        eff2 = min(max_n2, count2 - 1)
        hp_mult2 = 1.0 + (pct2 * eff2 / 100.0)
        for i in range(count2):
            s.hp2[i] = s.hp2[i] * hp_mult2

    s.cooldown1 = [0.0] * count1
    s.cooldown2 = [0.0] * count2
    s.bonus_atk1 = [0.0] * count1
    s.bonus_atk2 = [0.0] * count2
    s.hp_gained1 = [0] * count1  # Track cumulative HP gained from kills (for cap)
    s.hp_gained2 = [0] * count2
    s.used_first1 = [False] * count1
    s.used_first2 = [False] * count2
    s.transformed1 = [False] * count1
    s.transformed2 = [False] * count2
    s.shield1 = [float(s.dodge_max1)] * count1
    s.shield2 = [float(s.dodge_max2)] * count2
    s.shield_timer1 = [0.0] * count1
    s.shield_timer2 = [0.0] * count2
    s.has_blocked1 = [False] * count1
    s.has_blocked2 = [False] * count2
    s.bleed_on1 = {}  # idx -> (dps, remaining)
    s.bleed_on2 = {}
    s.committed1 = {}  # idx -> (target, time_remaining)
    s.committed2 = {}
    s.prev_target1 = [-1] * count1  # last attacked target per unit (for retarget delay)
    s.prev_target2 = [-1] * count2

    # Dismount on death (Konnik): pre-compute dismount damage
    s.dismount1 = unit1.get("dismount")
    s.dismount2 = unit2.get("dismount")
    s.dismounted1 = [False] * count1 if s.dismount1 else None
    s.dismounted2 = [False] * count2 if s.dismount2 else None

    s.dmg1_dismount = 0
    s.dmg2_vs_dismount1 = 0
    s.reload1_dismount = 0
    s.delay1_dismount = 0
    s.dmg2_dismount = 0
    s.dmg1_vs_dismount2 = 0
    s.reload2_dismount = 0
    s.delay2_dismount = 0

    if s.dismount1:
        # Dismounted team1 attacking team2
        s.dmg1_dismount = _calc_damage(
            s.dismount1["attacks"],
            s.dismount1["attack"],
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            False,  # dismounted is always melee
        )
        # Team2 attacking dismounted team1 (different armor classes!)
        s.dmg2_vs_dismount1 = _calc_damage(
            unit2["attacks"],
            unit2["attack"],
            s.dismount1["armors"],
            s.dismount1["melee_armor"],
            s.dismount1["pierce_armor"],
            s.is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            melee_damage=s.melee_dmg2,
        )
        s.reload1_dismount = (
            1.0 / s.dismount1["attack_speed"] if s.dismount1["attack_speed"] > 0 else 2.0
        )
        s.delay1_dismount = s.dismount1["attack_delay"]
    if s.dismount2:
        # Dismounted team2 attacking team1
        s.dmg2_dismount = _calc_damage(
            s.dismount2["attacks"],
            s.dismount2["attack"],
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            False,
        )
        # Team1 attacking dismounted team2 (different armor classes!)
        s.dmg1_vs_dismount2 = _calc_damage(
            unit1["attacks"],
            unit1["attack"],
            s.dismount2["armors"],
            s.dismount2["melee_armor"],
            s.dismount2["pierce_armor"],
            s.is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            melee_damage=s.melee_dmg1,
        )
        s.reload2_dismount = (
            1.0 / s.dismount2["attack_speed"] if s.dismount2["attack_speed"] > 0 else 2.0
        )
        s.delay2_dismount = s.dismount2["attack_delay"]

    # HP transform (Jian Swordsman): pre-compute transformed damage
    s.transform1 = unit1.get("transform")
    s.transform2 = unit2.get("transform")

    s.dmg1_transform = s.dmg1
    s.dmg2_vs_transform1 = s.dmg2
    s.dmg2_transform = s.dmg2
    s.dmg1_vs_transform2 = s.dmg1

    if s.transform1:
        # Transformed team1 attacking team2
        s.dmg1_transform = _calc_damage(
            s.transform1["attacks"],
            s.transform1["attack"],
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            s.is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
            melee_damage=_does_melee_damage(s.transform1["attacks"]),
        )
        # Team2 attacking transformed team1 (different armor!)
        s.dmg2_vs_transform1 = _calc_damage(
            unit2["attacks"],
            unit2["attack"],
            s.transform1["armors"],
            s.transform1["melee_armor"],
            s.transform1["pierce_armor"],
            s.is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
            melee_damage=s.melee_dmg2,
        )
    if s.transform2:
        s.dmg2_transform = _calc_damage(
            s.transform2["attacks"],
            s.transform2["attack"],
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            s.is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
            melee_damage=_does_melee_damage(s.transform2["attacks"]),
        )
        s.dmg1_vs_transform2 = _calc_damage(
            unit1["attacks"],
            unit1["attack"],
            s.transform2["armors"],
            s.transform2["melee_armor"],
            s.transform2["pierce_armor"],
            s.is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
            melee_damage=s.melee_dmg1,
        )

    # Charge attack (Coustillier): extra melee damage on first hit, then recharges
    s.charge_melee1 = unit1.get("charge_attack_melee", 0) or 0
    s.charge_melee2 = unit2.get("charge_attack_melee", 0) or 0
    s.charge_recharge1 = unit1.get("charge_recharge_time", 0) or 0
    s.charge_recharge2 = unit2.get("charge_recharge_time", 0) or 0

    # Charge projectile (Bolas Rider): ranged units fire stronger projectile on charge
    s.charge_proj_count1 = unit1.get("charge_projectile_count", 0) or 0
    s.charge_proj_count2 = unit2.get("charge_projectile_count", 0) or 0

    # Pre-compute charge projectile damage
    charge_proj_attacks1 = unit1.get("charge_projectile_attacks")
    if charge_proj_attacks1 and s.charge_proj_count1 > 0:
        cp_base1 = charge_proj_attacks1.get(3, charge_proj_attacks1.get(4, 0))
        s.charge_proj_dmg1 = _calc_damage(
            charge_proj_attacks1,
            cp_base1,
            unit2["armors"],
            unit2["melee_armor"],
            unit2["pierce_armor"],
            s.is_ranged1,
            ignores_pierce=unit1["ignores_pierce_armor"],
            ignores_melee=unit1["ignores_melee_armor"],
            bonus_damage_reduction=unit2["bonus_damage_reduction"],
            melee_damage=_does_melee_damage(charge_proj_attacks1),
        )
    else:
        s.charge_proj_dmg1 = 0

    charge_proj_attacks2 = unit2.get("charge_projectile_attacks")
    if charge_proj_attacks2 and s.charge_proj_count2 > 0:
        cp_base2 = charge_proj_attacks2.get(3, charge_proj_attacks2.get(4, 0))
        s.charge_proj_dmg2 = _calc_damage(
            charge_proj_attacks2,
            cp_base2,
            unit1["armors"],
            unit1["melee_armor"],
            unit1["pierce_armor"],
            s.is_ranged2,
            ignores_pierce=unit2["ignores_pierce_armor"],
            ignores_melee=unit2["ignores_melee_armor"],
            bonus_damage_reduction=unit1["bonus_damage_reduction"],
            melee_damage=_does_melee_damage(charge_proj_attacks2),
        )
    else:
        s.charge_proj_dmg2 = 0

    # Initialize charge ready/timer arrays for either melee charge or projectile charge
    has_charge1 = s.charge_melee1 > 0 or s.charge_proj_count1 > 0
    has_charge2 = s.charge_melee2 > 0 or s.charge_proj_count2 > 0
    s.charge_ready1 = [True] * count1 if has_charge1 else None
    s.charge_ready2 = [True] * count2 if has_charge2 else None
    s.charge_timer1 = [0.0] * count1 if has_charge1 else None
    s.charge_timer2 = [0.0] * count2 if has_charge2 else None

    # Armor stripping (Obuch): each hit reduces enemy melee + pierce armor by N
    s.armor_strip1 = unit1.get("armor_strip_per_hit", 0) or 0
    s.armor_strip2 = unit2.get("armor_strip_per_hit", 0) or 0
    # Per-unit armor tracking when armor stripping is in play
    if s.armor_strip1 or s.armor_strip2:
        s.current_ma2 = [unit2["melee_armor"]] * count2
        s.current_pa2 = [unit2["pierce_armor"]] * count2
        s.current_ma1 = [unit1["melee_armor"]] * count1
        s.current_pa1 = [unit1["pierce_armor"]] * count1
    else:
        s.current_ma1 = s.current_pa1 = s.current_ma2 = s.current_pa2 = None

    # Damage reflection (Khitan Lamellar Armor): melee attackers take % damage back
    s.reflect1 = unit1.get("damage_reflect_percent", 0) or 0
    s.reflect2 = unit2.get("damage_reflect_percent", 0) or 0

    # Attack speed ramp (Temple Guard): each hit reduces reload by N seconds, down to minimum
    s.attack_speed_ramp1 = unit1.get("attack_speed_ramp", 0) or 0
    s.attack_speed_ramp2 = unit2.get("attack_speed_ramp", 0) or 0
    s.attack_speed_min1 = unit1.get("attack_speed_min", 0) or 0
    s.attack_speed_min2 = unit2.get("attack_speed_min", 0) or 0
    # Per-unit cumulative reload reduction (increases by attack_speed_ramp each hit)
    s.ramp_reduction1 = [0.0] * count1 if s.attack_speed_ramp1 > 0 else None
    s.ramp_reduction2 = [0.0] * count2 if s.attack_speed_ramp2 > 0 else None

    # Execute damage (Kona): flat bonus damage per % of target HP missing
    s.execute_per_step1 = unit1.get("execute_damage_per_step", 0) or 0
    s.execute_per_step2 = unit2.get("execute_damage_per_step", 0) or 0
    s.execute_hp_step1 = unit1.get("execute_hp_step", 0) or 0
    s.execute_hp_step2 = unit2.get("execute_hp_step", 0) or 0

    # Charge slow (Bolas Rider): charge projectile slows target's movement speed
    s.charge_slow_pct1 = unit1.get("charge_slow_percent", 0) or 0
    s.charge_slow_pct2 = unit2.get("charge_slow_percent", 0) or 0
    s.charge_slow_dur1 = unit1.get("charge_slow_duration", 0) or 0
    s.charge_slow_dur2 = unit2.get("charge_slow_duration", 0) or 0
    # Per-unit slow timers on TARGETS (team1 slows team2's units, and vice versa)
    # slow_timer2 = remaining slow duration on each team2 unit (applied by team1's charge)
    has_slow1 = s.charge_slow_pct1 > 0 and s.charge_slow_dur1 > 0
    has_slow2 = s.charge_slow_pct2 > 0 and s.charge_slow_dur2 > 0
    s.slow_timer1 = [0.0] * count1 if has_slow2 else None  # team2 slows team1
    s.slow_timer2 = [0.0] * count2 if has_slow1 else None  # team1 slows team2
    # Store slow percent applied TO each team (from the opposing team's charge)
    s.slow_pct_on1 = s.charge_slow_pct2  # team2's slow % applied to team1 units
    s.slow_pct_on2 = s.charge_slow_pct1  # team1's slow % applied to team2 units

    # Ally death heal (Guecha Warrior): when a same-team unit dies, surviving
    # allies gain a heal-over-time that refreshes (does not stack).
    s.ally_death_heal1 = unit1.get("ally_death_heal", 0) or 0
    s.ally_death_heal_dur1 = unit1.get("ally_death_heal_duration", 0) or 0
    s.ally_death_heal2 = unit2.get("ally_death_heal", 0) or 0
    s.ally_death_heal_dur2 = unit2.get("ally_death_heal_duration", 0) or 0
    # Per-unit timers: remaining duration of current heal-over-time (0 = not healing)
    s.death_heal_timer1 = (
        [0.0] * count1 if s.ally_death_heal1 > 0 else None
    )
    s.death_heal_timer2 = (
        [0.0] * count2 if s.ally_death_heal2 > 0 else None
    )
    # Pre-compute heal per tick: (total_heal / duration) * DT
    s.death_heal_per_tick1 = (
        (s.ally_death_heal1 / s.ally_death_heal_dur1 * DT)
        if s.ally_death_heal_dur1 > 0
        else 0.0
    )
    s.death_heal_per_tick2 = (
        (s.ally_death_heal2 / s.ally_death_heal_dur2 * DT)
        if s.ally_death_heal_dur2 > 0
        else 0.0
    )

    s.start_total_hp1 = float(unit1["hp"]) * count1
    s.start_total_hp2 = float(unit2["hp"]) * count2

    return s


def _run_opening_volley(s):
    """Phase 1: Calculate and apply opening shots for range/kiting advantage.

    Modifies s.hp1, s.hp2, s.cooldown1, s.cooldown2, and related arrays in-place.
    """
    # Local aliases (these reference the same mutable lists/dicts in s)
    count1, count2 = s.count1, s.count2
    is_ranged1, is_ranged2 = s.is_ranged1, s.is_ranged2
    speed1, speed2 = s.speed1, s.speed2
    accuracy1, accuracy2 = s.accuracy1, s.accuracy2
    extra_accuracy1, extra_accuracy2 = s.extra_accuracy1, s.extra_accuracy2
    EXTRA_PROJ_ACCURACY = s.EXTRA_PROJ_ACCURACY
    reload1, reload2 = s.reload1, s.reload2
    delay1, delay2 = s.delay1, s.delay2
    min_range1, min_range2 = s.min_range1, s.min_range2
    range1, range2 = s.range1, s.range2
    dmg1, dmg2 = s.dmg1, s.dmg2
    is_siege1, is_siege2 = s.is_siege1, s.is_siege2
    siege_splash1, siege_splash2 = s.siege_splash1, s.siege_splash2
    splash_hit1, splash_hit2 = s.splash_hit1, s.splash_hit2
    splash_hit_frac1, splash_hit_frac2 = s.splash_hit_frac1, s.splash_hit_frac2
    pass_through1, pass_through2 = s.pass_through1, s.pass_through2
    pass_through_count1, pass_through_count2 = s.pass_through_count1, s.pass_through_count2
    extra_proj_scatter1, extra_proj_scatter2 = s.extra_proj_scatter1, s.extra_proj_scatter2
    extra_proj1, extra_proj2 = s.extra_proj1, s.extra_proj2
    first_burst1, first_burst2 = s.first_burst1, s.first_burst2
    extra_proj_dmg1, extra_proj_dmg2 = s.extra_proj_dmg1, s.extra_proj_dmg2
    dodge_max1, dodge_max2 = s.dodge_max1, s.dodge_max2
    dodge_recharge1, dodge_recharge2 = s.dodge_recharge1, s.dodge_recharge2
    bleed_dps1, bleed_dur1 = s.bleed_dps1, s.bleed_dur1
    bleed_dps2, bleed_dur2 = s.bleed_dps2, s.bleed_dur2
    max_hp1, max_hp2 = s.max_hp1, s.max_hp2
    block_melee1, block_melee2 = s.block_melee1, s.block_melee2
    kill_bonus1, kill_bonus2 = s.kill_bonus1, s.kill_bonus2
    hp_per_kill1, hp_per_kill2 = s.hp_per_kill1, s.hp_per_kill2
    hp_per_kill_max1, hp_per_kill_max2 = s.hp_per_kill_max1, s.hp_per_kill_max2
    miss_dmg_pct1, miss_dmg_pct2 = s.miss_dmg_pct1, s.miss_dmg_pct2
    hp1, hp2 = s.hp1, s.hp2
    cooldown1, cooldown2 = s.cooldown1, s.cooldown2
    bonus_atk1, bonus_atk2 = s.bonus_atk1, s.bonus_atk2
    hp_gained1, hp_gained2 = s.hp_gained1, s.hp_gained2
    used_first1, used_first2 = s.used_first1, s.used_first2
    shield1, shield2 = s.shield1, s.shield2
    shield_timer1, shield_timer2 = s.shield_timer1, s.shield_timer2
    has_blocked1, has_blocked2 = s.has_blocked1, s.has_blocked2
    bleed_on1, bleed_on2 = s.bleed_on1, s.bleed_on2

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
            a_hp_per_kill, a_hp_per_kill_max = hp_per_kill1, hp_per_kill_max1
            a_hp_gained, a_hp_arr = hp_gained1, hp1
            a_max_hp = max_hp1
            a_bleed_dps, a_bleed_dur = bleed_dps1, bleed_dur1
            a_splash_hit = splash_hit1
            a_splash_hit_frac = splash_hit_frac1
            a_siege_splash = siege_splash1
            a_is_siege = is_siege1
            a_pass_through = pass_through1
            a_pass_through_count = pass_through_count1
            t_alive_fn = lambda: _get_alive_targets(hp2, count2)
        else:
            t_hp, t_shield, t_shield_timer = hp1, shield1, shield_timer1
            t_blocked, t_bleed = has_blocked1, bleed_on1
            a_bonus, a_used_first = bonus_atk2, used_first2
            a_is_ranged = is_ranged2
            d_dodge_max, d_recharge = dodge_max1, dodge_recharge1
            d_block = block_melee1
            a_kill_bonus = kill_bonus2
            a_hp_per_kill, a_hp_per_kill_max = hp_per_kill2, hp_per_kill_max2
            a_hp_gained, a_hp_arr = hp_gained2, hp2
            a_max_hp = max_hp2
            a_bleed_dps, a_bleed_dur = bleed_dps2, bleed_dur2
            a_splash_hit = splash_hit2
            a_splash_hit_frac = splash_hit_frac2
            a_siege_splash = siege_splash2
            a_is_siege = is_siege2
            a_pass_through = pass_through2
            a_pass_through_count = pass_through_count2
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

        if was_alive and t_hp[target_idx] <= 0:
            if a_kill_bonus > 0 and a_bonus[attacker_idx] < a_kill_bonus:
                a_bonus[attacker_idx] = min(a_bonus[attacker_idx] + 1, a_kill_bonus)
            if a_hp_per_kill > 0 and a_hp_gained[attacker_idx] < a_hp_per_kill_max:
                heal = min(a_hp_per_kill, a_hp_per_kill_max - a_hp_gained[attacker_idx])
                a_hp_arr[attacker_idx] = min(a_hp_arr[attacker_idx] + heal, a_max_hp + a_hp_per_kill_max)
                a_hp_gained[attacker_idx] += heal

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
            splash_dmg = max(1, hit_dmg * a_splash_hit_frac)
            splashed = 0
            for idx in alive:
                if idx != target_idx and splashed < a_splash_hit:
                    t_hp[idx] -= splash_dmg
                    splashed += 1

        # Pass-through: up to N additional units take a fraction of the damage
        if a_pass_through > 0:
            alive = t_alive_fn()
            pt_dmg = max(1, int(hit_dmg * a_pass_through))
            pt_hit = 0
            for idx in alive:
                if idx != target_idx:
                    t_hp[idx] -= pt_dmg
                    pt_hit += 1
                    if pt_hit >= a_pass_through_count:
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
        a_miss_dmg_pct=0,
        a_scatter=0,
        a_pass_through=0,
        a_extra_accuracy=0.85,
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
                a_alive, t_alive, target_hp_arr, damage, 1 + a_extra_proj,
                extra_dmg=extra_proj_damage, extra_accuracy=a_extra_accuracy,
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
                else:
                    # Missed shot — may hit random enemy in formation
                    alive = [i for i in range(target_count) if target_hp_arr[i] > 0]
                    if a_miss_dmg_pct > 0:
                        stray_chance = a_miss_dmg_pct
                    else:
                        stray_chance = min(0.5, len(alive) * 0.05)
                    if alive and random.random() < stray_chance:
                        stray = random.choice(alive)
                        _apply_opening_hit(attacker_team, stray, damage, a_idx)
                # Extra projectiles: pass-through bolts always hit; scatter
                # multi-barrel projectiles (Organ Gun) also always land on
                # SOME target; ordinary secondary projectiles (Chu Ko Nu,
                # Bolt Magazine, Hul'che extras) roll the unit's BASE accuracy
                # — Thumb Ring is a primary-only bonus per Fandom, so extras
                # don't get the +15% lift that a_accuracy carries.
                for _ in range(num_proj - 1):
                    if a_pass_through > 0 or a_scatter or random.random() < a_extra_accuracy:
                        if a_scatter:
                            t_alive_scat = [i for i in range(target_count) if target_hp_arr[i] > 0]
                            if t_alive_scat:
                                scat_target = random.choice(t_alive_scat)
                                _apply_opening_hit(attacker_team, scat_target, extra_proj_damage, a_idx)
                        else:
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
        # Both ranged: longer-ranged unit retreats while firing.
        # Shorter-ranged unit closes the gap at full speed (can't fire yet).
        # Same physics model as ranged-vs-melee kiting.
        range_diff = range1 - range2
        if range_diff > 0:
            # Unit 1 has longer range — retreats while firing
            fire_dist = range1 - max(min_range1, range2)
            if fire_dist > 0 and speed2 > 0:
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
                stand_time = remaining_dist / speed2 if remaining_dist > 0 else 0
                closing_time = retreat_time + stand_time + delay2
                closing_time1 = closing_time
                if closing_time > delay1:
                    opening1 = 1 + int((closing_time - delay1) / reload1)
            # Kiting bonus: if unit 1 effective retreat > unit 2 speed
            eff_spd1 = eff_retreat_speed1 if fire_dist > 0 and speed2 > 0 else speed1
            if eff_spd1 > speed2 and speed2 > 0:
                speed_diff = eff_spd1 - speed2
                kite_dist = MAP_SPACE * 0.4 - RETREAT_MAX
                if kite_dist > 0:
                    kite_time = kite_dist / speed_diff
                    opening1 += max(0, int(kite_time / reload1))
        elif range_diff < 0:
            # Unit 2 has longer range — retreats while firing (mirror)
            fire_dist = range2 - max(min_range2, range1)
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
            a_miss_dmg_pct=miss_dmg_pct1,
            a_scatter=extra_proj_scatter1,
            a_pass_through=pass_through1,
            a_extra_accuracy=extra_accuracy1,
        )
        # Set cooldowns to reflect time elapsed since last opening shot
        if is_ranged1 and closing_time1 > 0:
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
            a_miss_dmg_pct=miss_dmg_pct2,
            a_scatter=extra_proj_scatter2,
            a_pass_through=pass_through2,
            a_extra_accuracy=extra_accuracy2,
        )
        if is_ranged2 and closing_time2 > 0:
            last_shot_t = delay2 + (opening2 - 1) * reload2
            remaining_cd = max(0.0, reload2 - (closing_time2 - last_shot_t))
            for i in range(count2):
                cooldown2[i] = remaining_cd


def _apply_tick_damage(s, pending_damage, alive1, alive2):
    """Apply all pending damage from attack generation atomically.

    Handles dodge shields, block-first-melee, armor stripping, damage
    reflection, kill bonuses, trample, siege splash, splash-on-hit,
    pass-through, and bleed application.

    Modifies s.hp1, s.hp2, and related per-unit arrays in-place.
    """
    # Local aliases (mutable references into state)
    hp1, hp2 = s.hp1, s.hp2
    shield1, shield2 = s.shield1, s.shield2
    shield_timer1, shield_timer2 = s.shield_timer1, s.shield_timer2
    has_blocked1, has_blocked2 = s.has_blocked1, s.has_blocked2
    bleed_on1, bleed_on2 = s.bleed_on1, s.bleed_on2
    bonus_atk1, bonus_atk2 = s.bonus_atk1, s.bonus_atk2
    hp_gained1, hp_gained2 = s.hp_gained1, s.hp_gained2
    is_ranged1, is_ranged2 = s.is_ranged1, s.is_ranged2
    dodge_max1, dodge_max2 = s.dodge_max1, s.dodge_max2
    dodge_recharge1, dodge_recharge2 = s.dodge_recharge1, s.dodge_recharge2
    block_melee1, block_melee2 = s.block_melee1, s.block_melee2
    kill_bonus1, kill_bonus2 = s.kill_bonus1, s.kill_bonus2
    hp_per_kill1, hp_per_kill2 = s.hp_per_kill1, s.hp_per_kill2
    hp_per_kill_max1, hp_per_kill_max2 = s.hp_per_kill_max1, s.hp_per_kill_max2
    max_hp1, max_hp2 = s.max_hp1, s.max_hp2
    bleed_dps1, bleed_dur1 = s.bleed_dps1, s.bleed_dur1
    bleed_dps2, bleed_dur2 = s.bleed_dps2, s.bleed_dur2
    trample_dmg1, trample_extra1 = s.trample_dmg1, s.trample_extra1
    trample_dmg2, trample_extra2 = s.trample_dmg2, s.trample_extra2
    splash_hit1, splash_hit2 = s.splash_hit1, s.splash_hit2
    splash_hit_frac1, splash_hit_frac2 = s.splash_hit_frac1, s.splash_hit_frac2
    siege_splash1, siege_splash2 = s.siege_splash1, s.siege_splash2
    is_siege1, is_siege2 = s.is_siege1, s.is_siege2
    pass_through1, pass_through2 = s.pass_through1, s.pass_through2
    pass_through_count1, pass_through_count2 = s.pass_through_count1, s.pass_through_count2
    armor_strip1, armor_strip2 = s.armor_strip1, s.armor_strip2
    current_ma1, current_pa1 = s.current_ma1, s.current_pa1
    current_ma2, current_pa2 = s.current_ma2, s.current_pa2
    reflect1, reflect2 = s.reflect1, s.reflect2
    execute_per_step1, execute_per_step2 = s.execute_per_step1, s.execute_per_step2
    execute_hp_step1, execute_hp_step2 = s.execute_hp_step1, s.execute_hp_step2
    unit1, unit2 = s.unit1, s.unit2

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
            a_hp_per_kill, a_hp_per_kill_max = hp_per_kill2, hp_per_kill_max2
            a_hp_gained, a_hp_arr = hp_gained2, hp2
            a_max_hp = max_hp2
            a_bleed_dps, a_bleed_dur = bleed_dps2, bleed_dur2
            a_trample_dmg, a_trample_extra = trample_dmg2, trample_extra2
            a_splash_hit = splash_hit2
            a_splash_hit_frac = splash_hit_frac2
            a_siege_splash = siege_splash2
            a_is_siege = is_siege2
            a_pass_through = pass_through2
            a_pass_through_count = pass_through_count2
            a_armor_strip = armor_strip2
            t_current_ma, t_current_pa = current_ma1, current_pa1
            all_alive = alive1
            a_execute_per_step = execute_per_step2
            a_execute_hp_step = execute_hp_step2
            t_max_hp = max_hp1
        else:
            t_hp = hp2
            t_shield, t_shield_timer = shield2, shield_timer2
            t_blocked, t_bleed = has_blocked2, bleed_on2
            a_bonus = bonus_atk1
            a_is_ranged = is_ranged1
            d_dodge_max, d_recharge = dodge_max2, dodge_recharge2
            d_block = block_melee2
            a_kill_bonus = kill_bonus1
            a_hp_per_kill, a_hp_per_kill_max = hp_per_kill1, hp_per_kill_max1
            a_hp_gained, a_hp_arr = hp_gained1, hp1
            a_max_hp = max_hp1
            a_bleed_dps, a_bleed_dur = bleed_dps1, bleed_dur1
            a_trample_dmg, a_trample_extra = trample_dmg1, trample_extra1
            a_splash_hit = splash_hit1
            a_splash_hit_frac = splash_hit_frac1
            a_siege_splash = siege_splash1
            a_is_siege = is_siege1
            a_pass_through = pass_through1
            a_pass_through_count = pass_through_count1
            a_armor_strip = armor_strip1
            t_current_ma, t_current_pa = current_ma2, current_pa2
            all_alive = alive2
            a_execute_per_step = execute_per_step1
            a_execute_hp_step = execute_hp_step1
            t_max_hp = max_hp2

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

        # Armor stripping (Obuch): adjust damage for stripped armor on target
        if t_current_ma is not None:
            if a_is_ranged:
                orig_armor = (
                    unit1["pierce_armor"]
                    if target_team == 1
                    else unit2["pierce_armor"]
                )
                cur_armor = t_current_pa[target_idx]
            else:
                orig_armor = (
                    unit1["melee_armor"]
                    if target_team == 1
                    else unit2["melee_armor"]
                )
                cur_armor = t_current_ma[target_idx]
            armor_lost = orig_armor - cur_armor
            if armor_lost > 0:
                damage += armor_lost

        # Execute damage (Kona): flat bonus per 15% missing HP on target
        if a_execute_per_step > 0 and a_execute_hp_step > 0 and t_max_hp > 0:
            missing_frac = 1.0 - (t_hp[target_idx] / t_max_hp)
            if missing_frac > 0:
                damage += int(missing_frac / a_execute_hp_step) * a_execute_per_step

        t_hp[target_idx] -= damage

        # Damage reflection (Khitan Lamellar Armor): melee attackers take % back
        if not a_is_ranged:
            t_reflect = reflect1 if target_team == 1 else reflect2
            if t_reflect > 0:
                reflect_dmg = max(1, int(damage * t_reflect))
                a_hp = hp2 if target_team == 1 else hp1
                a_hp[attacker_idx] -= reflect_dmg

        # Armor stripping (Obuch): reduce target armor after hit
        if a_armor_strip > 0 and t_current_ma is not None:
            t_current_ma[target_idx] = max(
                -99, t_current_ma[target_idx] - a_armor_strip
            )
            t_current_pa[target_idx] = max(
                -99, t_current_pa[target_idx] - a_armor_strip
            )

        # Kill bonus (attack + HP)
        if was_alive and t_hp[target_idx] <= 0:
            if a_kill_bonus > 0 and a_bonus[attacker_idx] < a_kill_bonus:
                a_bonus[attacker_idx] = min(a_bonus[attacker_idx] + 1, a_kill_bonus)
            if a_hp_per_kill > 0 and a_hp_gained[attacker_idx] < a_hp_per_kill_max:
                heal = min(a_hp_per_kill, a_hp_per_kill_max - a_hp_gained[attacker_idx])
                a_hp_arr[attacker_idx] = min(a_hp_arr[attacker_idx] + heal, a_max_hp + a_hp_per_kill_max)
                a_hp_gained[attacker_idx] += heal

        # Trample: 25% chance to damage a nearby alive enemy
        if (
            a_trample_dmg > 0
            and a_trample_extra > 0
            and random.random() < TRAMPLE_HIT_CHANCE
        ):
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
            splash_dmg = max(1, damage * a_splash_hit_frac)
            splashed = 0
            for idx in all_alive:
                if idx != target_idx and t_hp[idx] > 0 and splashed < a_splash_hit:
                    t_hp[idx] -= splash_dmg
                    splashed += 1

        # Pass-through: up to N additional units take a fraction of the damage
        if a_pass_through > 0:
            pt_dmg = max(1, int(damage * a_pass_through))
            pt_hit = 0
            for idx in all_alive:
                if idx != target_idx and t_hp[idx] > 0:
                    t_hp[idx] -= pt_dmg
                    pt_hit += 1
                    if pt_hit >= a_pass_through_count:
                        break

        # Bleed
        if a_bleed_dps > 0 and was_alive:
            t_bleed[target_idx] = (a_bleed_dps, a_bleed_dur)


def _apply_tick_effects(s, alive1, alive2):
    """Apply per-tick effects: dodge recharge, charge recharge, bleed, HP regen,
    HP transform, and dismount-on-death.

    Modifies s.hp1, s.hp2, and related per-unit arrays in-place.
    """
    # Local aliases (mutable references into state)
    count1, count2 = s.count1, s.count2
    hp1, hp2 = s.hp1, s.hp2
    cooldown1, cooldown2 = s.cooldown1, s.cooldown2
    shield1, shield2 = s.shield1, s.shield2
    shield_timer1, shield_timer2 = s.shield_timer1, s.shield_timer2
    dodge_max1, dodge_max2 = s.dodge_max1, s.dodge_max2
    dodge_recharge1, dodge_recharge2 = s.dodge_recharge1, s.dodge_recharge2
    charge_ready1, charge_ready2 = s.charge_ready1, s.charge_ready2
    charge_timer1, charge_timer2 = s.charge_timer1, s.charge_timer2
    bleed_on1, bleed_on2 = s.bleed_on1, s.bleed_on2
    regen_per_tick1, regen_per_tick2 = s.regen_per_tick1, s.regen_per_tick2
    max_hp1, max_hp2 = s.max_hp1, s.max_hp2
    transform_thresh1, transform_thresh2 = s.transform_thresh1, s.transform_thresh2
    transformed1, transformed2 = s.transformed1, s.transformed2
    dismount1, dismount2 = s.dismount1, s.dismount2
    dismounted1, dismounted2 = s.dismounted1, s.dismounted2
    committed1, committed2 = s.committed1, s.committed2
    reload1_dismount, reload2_dismount = s.reload1_dismount, s.reload2_dismount
    unit1, unit2 = s.unit1, s.unit2

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

    # Charge attack recharge (melee charge: Coustillier; projectile charge: Bolas Rider)
    if charge_timer1 is not None:
        for i in alive1:
            if not charge_ready1[i] and charge_timer1[i] > 0:
                charge_timer1[i] -= DT
                if charge_timer1[i] <= 0:
                    charge_ready1[i] = True
    if charge_timer2 is not None:
        for i in alive2:
            if not charge_ready2[i] and charge_timer2[i] > 0:
                charge_timer2[i] -= DT
                if charge_timer2[i] <= 0:
                    charge_ready2[i] = True

    # Slow timer tick-down (Bolas Rider charge slow)
    slow_timer1, slow_timer2 = s.slow_timer1, s.slow_timer2
    if slow_timer1 is not None:
        for i in alive1:
            if slow_timer1[i] > 0:
                slow_timer1[i] = max(0.0, slow_timer1[i] - DT)
    if slow_timer2 is not None:
        for i in alive2:
            if slow_timer2[i] > 0:
                slow_timer2[i] = max(0.0, slow_timer2[i] - DT)

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

    # Ally death heal-over-time (Guecha Warrior)
    death_heal_timer1, death_heal_timer2 = s.death_heal_timer1, s.death_heal_timer2
    if death_heal_timer1 is not None:
        heal_per_tick = s.death_heal_per_tick1
        for idx in alive1:
            if death_heal_timer1[idx] > 0:
                if hp1[idx] < max_hp1:
                    hp1[idx] = min(max_hp1, hp1[idx] + heal_per_tick)
                death_heal_timer1[idx] = max(0.0, death_heal_timer1[idx] - DT)
    if death_heal_timer2 is not None:
        heal_per_tick = s.death_heal_per_tick2
        for idx in alive2:
            if death_heal_timer2[idx] > 0:
                if hp2[idx] < max_hp2:
                    hp2[idx] = min(max_hp2, hp2[idx] + heal_per_tick)
                death_heal_timer2[idx] = max(0.0, death_heal_timer2[idx] - DT)

    # HP transform (e.g. Jian Swordsman — switch to unshielded form, revert when healed)
    if transform_thresh1 > 0:
        threshold_hp = unit1["hp"] * transform_thresh1
        for idx in alive1:
            if not transformed1[idx] and hp1[idx] <= threshold_hp and hp1[idx] > 0:
                transformed1[idx] = True
            elif transformed1[idx] and hp1[idx] > threshold_hp:
                transformed1[idx] = False
    if transform_thresh2 > 0:
        threshold_hp = unit2["hp"] * transform_thresh2
        for idx in alive2:
            if not transformed2[idx] and hp2[idx] <= threshold_hp and hp2[idx] > 0:
                transformed2[idx] = True
            elif transformed2[idx] and hp2[idx] > threshold_hp:
                transformed2[idx] = False

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


def _determine_winner(s, tick, return_hp, return_ticks):
    """Phase 3: Determine the battle winner from remaining HP arrays.

    Returns the appropriate result tuple based on return_hp/return_ticks flags.
    """
    hp1, hp2 = s.hp1, s.hp2
    count1, count2 = s.count1, s.count2
    start_total_hp1, start_total_hp2 = s.start_total_hp1, s.start_total_hp2

    remaining1 = sum(1 for h in hp1 if h > 0)
    remaining2 = sum(1 for h in hp2 if h > 0)
    total_hp1 = sum(max(0, h) for h in hp1)
    total_hp2 = sum(max(0, h) for h in hp2)
    hp_pct1 = total_hp1 / start_total_hp1 if start_total_hp1 > 0 else 0.0
    hp_pct2 = total_hp2 / start_total_hp2 if start_total_hp2 > 0 else 0.0
    elapsed_ticks = tick + 1  # tick is 0-indexed from the for loop

    def _result(winner):
        if return_ticks:
            return (winner, remaining1, remaining2, hp_pct1, hp_pct2, elapsed_ticks)
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


def simulate_battle(
    unit1,
    unit2,
    resources,
    fixed_count=None,
    cost1_override=None,
    cost2_override=None,
    return_hp=False,
    return_ticks=False,
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
        return_ticks: if True, returns 6-tuple with HP totals + elapsed ticks

    Returns: (winner, unit1_remaining, unit2_remaining) or
             (winner, unit1_remaining, unit2_remaining, hp_pct1, hp_pct2) if return_hp
             (winner, remaining1, remaining2, hp_pct1, hp_pct2, elapsed_ticks) if return_ticks
        winner: 1 if unit1 wins, 2 if unit2 wins, 0 if draw
        hp_pct1/hp_pct2: remaining HP as fraction of starting total (0.0-1.0)
        elapsed_ticks: number of ticks the battle lasted (multiply by DT for seconds)
    """
    # --- Initialize all battle state ---
    s = _init_battle_state(unit1, unit2, resources, fixed_count, cost1_override, cost2_override)

    # Local aliases for hot-path variables (avoids s.attr lookups in tight loops)
    count1, count2 = s.count1, s.count2
    range1, range2 = s.range1, s.range2
    is_ranged1, is_ranged2 = s.is_ranged1, s.is_ranged2
    speed1, speed2 = s.speed1, s.speed2
    accuracy1, accuracy2 = s.accuracy1, s.accuracy2
    extra_accuracy1, extra_accuracy2 = s.extra_accuracy1, s.extra_accuracy2
    EXTRA_PROJ_ACCURACY = s.EXTRA_PROJ_ACCURACY
    reload1, reload2 = s.reload1, s.reload2
    delay1, delay2 = s.delay1, s.delay2
    min_range1, min_range2 = s.min_range1, s.min_range2
    dmg1, dmg2 = s.dmg1, s.dmg2
    trample_dmg1, trample_extra1 = s.trample_dmg1, s.trample_extra1
    trample_dmg2, trample_extra2 = s.trample_dmg2, s.trample_extra2
    is_siege1, is_siege2 = s.is_siege1, s.is_siege2
    siege_splash1, siege_splash2 = s.siege_splash1, s.siege_splash2
    splash_hit1, splash_hit2 = s.splash_hit1, s.splash_hit2
    splash_hit_frac1, splash_hit_frac2 = s.splash_hit_frac1, s.splash_hit_frac2
    pass_through1, pass_through2 = s.pass_through1, s.pass_through2
    pass_through_count1, pass_through_count2 = s.pass_through_count1, s.pass_through_count2
    extra_proj_scatter1, extra_proj_scatter2 = s.extra_proj_scatter1, s.extra_proj_scatter2
    extra_proj1, extra_proj2 = s.extra_proj1, s.extra_proj2
    first_burst1, first_burst2 = s.first_burst1, s.first_burst2
    extra_proj_dmg1, extra_proj_dmg2 = s.extra_proj_dmg1, s.extra_proj_dmg2
    dodge_max1, dodge_max2 = s.dodge_max1, s.dodge_max2
    dodge_recharge1, dodge_recharge2 = s.dodge_recharge1, s.dodge_recharge2
    bleed_dps1, bleed_dur1 = s.bleed_dps1, s.bleed_dur1
    bleed_dps2, bleed_dur2 = s.bleed_dps2, s.bleed_dur2
    regen_per_tick1, regen_per_tick2 = s.regen_per_tick1, s.regen_per_tick2
    max_hp1, max_hp2 = s.max_hp1, s.max_hp2
    block_melee1, block_melee2 = s.block_melee1, s.block_melee2
    kill_bonus1, kill_bonus2 = s.kill_bonus1, s.kill_bonus2
    hp_per_kill1, hp_per_kill2 = s.hp_per_kill1, s.hp_per_kill2
    hp_per_kill_max1, hp_per_kill_max2 = s.hp_per_kill_max1, s.hp_per_kill_max2
    miss_dmg_pct1, miss_dmg_pct2 = s.miss_dmg_pct1, s.miss_dmg_pct2
    transform_thresh1, transform_thresh2 = s.transform_thresh1, s.transform_thresh2
    cant_attack_melee1, cant_attack_melee2 = s.cant_attack_melee1, s.cant_attack_melee2
    hp1, hp2 = s.hp1, s.hp2
    cooldown1, cooldown2 = s.cooldown1, s.cooldown2
    bonus_atk1, bonus_atk2 = s.bonus_atk1, s.bonus_atk2
    hp_gained1, hp_gained2 = s.hp_gained1, s.hp_gained2
    used_first1, used_first2 = s.used_first1, s.used_first2
    transformed1, transformed2 = s.transformed1, s.transformed2
    shield1, shield2 = s.shield1, s.shield2
    shield_timer1, shield_timer2 = s.shield_timer1, s.shield_timer2
    has_blocked1, has_blocked2 = s.has_blocked1, s.has_blocked2
    bleed_on1, bleed_on2 = s.bleed_on1, s.bleed_on2
    committed1, committed2 = s.committed1, s.committed2
    prev_target1, prev_target2 = s.prev_target1, s.prev_target2
    dismount1, dismount2 = s.dismount1, s.dismount2
    dismounted1, dismounted2 = s.dismounted1, s.dismounted2
    dmg1_dismount, dmg2_vs_dismount1 = s.dmg1_dismount, s.dmg2_vs_dismount1
    reload1_dismount, delay1_dismount = s.reload1_dismount, s.delay1_dismount
    dmg2_dismount, dmg1_vs_dismount2 = s.dmg2_dismount, s.dmg1_vs_dismount2
    reload2_dismount, delay2_dismount = s.reload2_dismount, s.delay2_dismount
    transform1, transform2 = s.transform1, s.transform2
    dmg1_transform = s.dmg1_transform
    dmg2_vs_transform1 = s.dmg2_vs_transform1
    dmg2_transform = s.dmg2_transform
    dmg1_vs_transform2 = s.dmg1_vs_transform2
    charge_melee1, charge_melee2 = s.charge_melee1, s.charge_melee2
    charge_recharge1, charge_recharge2 = s.charge_recharge1, s.charge_recharge2
    charge_ready1, charge_ready2 = s.charge_ready1, s.charge_ready2
    charge_timer1, charge_timer2 = s.charge_timer1, s.charge_timer2
    charge_proj_count1, charge_proj_count2 = s.charge_proj_count1, s.charge_proj_count2
    charge_proj_dmg1, charge_proj_dmg2 = s.charge_proj_dmg1, s.charge_proj_dmg2
    armor_strip1, armor_strip2 = s.armor_strip1, s.armor_strip2
    current_ma1, current_pa1 = s.current_ma1, s.current_pa1
    current_ma2, current_pa2 = s.current_ma2, s.current_pa2
    reflect1, reflect2 = s.reflect1, s.reflect2
    attack_speed_ramp1 = s.attack_speed_ramp1
    attack_speed_ramp2 = s.attack_speed_ramp2
    attack_speed_min1 = s.attack_speed_min1
    attack_speed_min2 = s.attack_speed_min2
    ramp_reduction1 = s.ramp_reduction1
    ramp_reduction2 = s.ramp_reduction2
    slow_timer1, slow_timer2 = s.slow_timer1, s.slow_timer2
    charge_slow_dur1, charge_slow_dur2 = s.charge_slow_dur1, s.charge_slow_dur2
    slow_pct_on1, slow_pct_on2 = s.slow_pct_on1, s.slow_pct_on2
    start_total_hp1, start_total_hp2 = s.start_total_hp1, s.start_total_hp2

    # =========================================================
    # PHASE 1: Opening volley (range/kiting advantage)
    # =========================================================
    _run_opening_volley(s)

    # =========================================================
    # PHASE 2: Tick-based combat loop
    # =========================================================

    # Infantry vs cavalry: infantry can stack more around large cavalry hitboxes
    is_inf1 = 1 in unit1["armors"]  # armor class 1 = Infantry
    is_inf2 = 1 in unit2["armors"]
    is_cav1 = 8 in unit1["armors"]  # armor class 8 = Cavalry
    is_cav2 = 8 in unit2["armors"]
    # Team 1 attacking team 2: if infantry attacking cavalry, use higher caps
    if is_inf1 and is_cav2:
        spread_initial1, spread_max1 = INF_VS_CAV_INITIAL_CAP, INF_VS_CAV_MAX_CAP
    else:
        spread_initial1, spread_max1 = 1, MELEE_VS_MELEE_MAX
    # Team 2 attacking team 1
    if is_inf2 and is_cav1:
        spread_initial2, spread_max2 = INF_VS_CAV_INITIAL_CAP, INF_VS_CAV_MAX_CAP
    else:
        spread_initial2, spread_max2 = 1, MELEE_VS_MELEE_MAX

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

        # Assign targets: ranged focus fire, melee capped vs ranged, spread capped vs melee
        if is_ranged1:
            targets1 = _assign_targets_focus(
                alive1, alive2, hp2, dmg1, 1 + extra_proj1,
                extra_dmg=extra_proj_dmg1, extra_accuracy=extra_accuracy1,
            )
        elif is_ranged2:
            targets1 = _assign_targets_melee_capped(alive1, alive2, tick)
        else:
            targets1 = _assign_targets_spread_capped(alive1, alive2, tick,
                                                      spread_initial1, spread_max1)
        if is_ranged2:
            targets2 = _assign_targets_focus(
                alive2, alive1, hp1, dmg2, 1 + extra_proj2,
                extra_dmg=extra_proj_dmg2, extra_accuracy=extra_accuracy2,
            )
        elif is_ranged1:
            targets2 = _assign_targets_melee_capped(alive2, alive1, tick)
        else:
            targets2 = _assign_targets_spread_capped(alive2, alive1, tick,
                                                      spread_initial2, spread_max2)

        # Reverse maps: who is targeting each unit (for retarget-on-attacked)
        # targeted_by1[i] = first enemy (team2) unit targeting team1 unit i
        # targeted_by2[i] = first enemy (team1) unit targeting team2 unit i
        targeted_by1 = {}
        for attacker, target in targets2.items():
            if target not in targeted_by1:
                targeted_by1[target] = attacker
        targeted_by2 = {}
        for attacker, target in targets1.items():
            if target not in targeted_by2:
                targeted_by2[target] = attacker

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
                t_extra_accuracy = extra_accuracy1
                t_miss_dmg_pct = miss_dmg_pct1
                t_reload, t_delay = reload1, delay1
                t_extra_proj, t_first_burst = extra_proj1, first_burst1
                t_scatter = extra_proj_scatter1
                t_pass_through = pass_through1
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
                my_charge_ready = charge_ready1
                my_charge_timer = charge_timer1
                t_charge_melee = charge_melee1
                t_charge_recharge = charge_recharge1
                t_charge_proj_count = charge_proj_count1
                t_charge_proj_dmg = charge_proj_dmg1
                my_ramp_reduction = ramp_reduction1
                t_attack_speed_ramp = attack_speed_ramp1
                t_attack_speed_min = attack_speed_min1
                enemy_hp = hp2
                enemy_alive = alive2
                enemy_team = 2
                my_targeted_by = targeted_by1  # who (team2) is attacking me (team1)
                enemy_slow_timer = slow_timer2  # team1 slows team2
                t_charge_slow_dur = charge_slow_dur1
                my_slow_timer = slow_timer1  # team2 may have slowed team1 units
                my_slow_pct = slow_pct_on1  # slow % applied to my units
            else:
                my_alive = alive2
                my_targets = targets2
                my_cooldown, my_committed = cooldown2, committed2
                my_bonus_atk, my_used_first = bonus_atk2, used_first2
                t_is_ranged, t_is_siege = is_ranged2, is_siege2
                t_speed = speed2
                t_accuracy = accuracy2
                t_extra_accuracy = extra_accuracy2
                t_miss_dmg_pct = miss_dmg_pct2
                t_reload, t_delay = reload2, delay2
                t_extra_proj, t_first_burst = extra_proj2, first_burst2
                t_scatter = extra_proj_scatter2
                t_pass_through = pass_through2
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
                my_charge_ready = charge_ready2
                my_charge_timer = charge_timer2
                t_charge_melee = charge_melee2
                t_charge_recharge = charge_recharge2
                t_charge_proj_count = charge_proj_count2
                t_charge_proj_dmg = charge_proj_dmg2
                my_ramp_reduction = ramp_reduction2
                t_attack_speed_ramp = attack_speed_ramp2
                t_attack_speed_min = attack_speed_min2
                enemy_hp = hp1
                enemy_alive = alive1
                enemy_team = 1
                my_targeted_by = targeted_by2  # who (team1) is attacking me (team2)
                enemy_slow_timer = slow_timer1  # team2 slows team1
                t_charge_slow_dur = charge_slow_dur2
                my_slow_timer = slow_timer2  # team1 may have slowed team2 units
                my_slow_pct = slow_pct_on2  # slow % applied to my units

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
                            # Charge attack bonus (Coustillier)
                            if my_charge_ready and my_charge_ready[i]:
                                hit_dmg += t_charge_melee
                                my_charge_ready[i] = False
                                my_charge_timer[i] = t_charge_recharge
                            pending_damage.append(
                                (enemy_team, target_idx, hit_dmg, i, team_id)
                            )
                        del my_committed[i]
                        if i_dismounted:
                            my_cooldown[i] = (
                                reload1_dismount if team_id == 1 else reload2_dismount
                            )
                        else:
                            # Attack speed ramp: each hit reduces reload time
                            if my_ramp_reduction is not None and t_attack_speed_ramp > 0:
                                my_ramp_reduction[i] += t_attack_speed_ramp
                                my_cooldown[i] = max(
                                    t_attack_speed_min,
                                    t_reload - my_ramp_reduction[i],
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
                # Exception: if an enemy is already attacking this unit, switch
                # to that enemy instantly (they're already in melee range)
                prev = my_prev_target[i]
                if prev >= 0 and target_idx != prev and not t_is_ranged:
                    attacker = my_targeted_by.get(i)
                    if attacker is not None and enemy_hp[attacker] > 0:
                        # Switch to the enemy attacking us — no walk needed
                        target_idx = attacker
                    else:
                        eff_speed = t_speed
                        if my_slow_timer and my_slow_timer[i] > 0 and my_slow_pct > 0:
                            eff_speed = t_speed * (1.0 - my_slow_pct)
                        retarget_time = RETARGET_DIST / eff_speed if eff_speed > 0 else 2.0
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
                    # Charge projectile: use stronger damage when charge is ready
                    use_charge_proj = (
                        t_charge_proj_count > 0
                        and my_charge_ready
                        and my_charge_ready[i]
                    )
                    if use_charge_proj:
                        base = t_charge_proj_dmg
                    elif t_enemy_dismounted and t_enemy_dismounted[target_idx]:
                        base = t_dmg_vs_dismount
                    elif t_enemy_transformed and t_enemy_transformed[target_idx]:
                        base = t_dmg_vs_transform
                    else:
                        base = t_dmg
                    # Main projectile: hit chance = unit accuracy
                    charge_hit_target = -1  # track which target got hit by charge proj
                    if t_accuracy >= 1.0 or random.random() < t_accuracy:
                        hit_dmg = base + int(my_bonus_atk[i])
                        pending_damage.append(
                            (enemy_team, target_idx, hit_dmg, i, team_id)
                        )
                        if use_charge_proj:
                            charge_hit_target = target_idx
                    else:
                        # Missed shot — may hit random enemy in formation
                        if t_miss_dmg_pct > 0:
                            stray_chance = t_miss_dmg_pct
                        else:
                            stray_chance = min(0.5, len(enemy_alive) * 0.05)
                        if enemy_alive and random.random() < stray_chance:
                            stray = random.choice(enemy_alive)
                            hit_dmg = base + int(my_bonus_atk[i])
                            pending_damage.append(
                                (enemy_team, stray, hit_dmg, i, team_id)
                            )
                            if use_charge_proj:
                                charge_hit_target = stray
                    # Reset charge after firing (whether hit or miss)
                    if use_charge_proj:
                        my_charge_ready[i] = False
                        my_charge_timer[i] = t_charge_recharge
                        # Charge slow: apply slow debuff to the hit target
                        if charge_hit_target >= 0 and enemy_slow_timer is not None:
                            enemy_slow_timer[charge_hit_target] = t_charge_slow_dur
                    # Extra projectiles: pass-through bolts always hit; others ~50%
                    if num_extra > 0:
                        extra_base = t_extra_proj_dmg
                        extra_hit = extra_base + int(my_bonus_atk[i])
                        # Scatter multi-barrel extras (Organ Gun) always land
                        # on SOME target; pass-through extras pierce. Ordinary
                        # secondary projectiles (Chu Ko Nu, Bolt Magazine,
                        # Hul'che) roll the unit's BASE accuracy — Thumb Ring
                        # is a primary-only bonus per Fandom.
                        for _ in range(num_extra):
                            if t_pass_through > 0 or t_scatter or random.random() < t_extra_accuracy:
                                if t_scatter and enemy_alive:
                                    scat_target = random.choice(enemy_alive)
                                    pending_damage.append(
                                        (enemy_team, scat_target, extra_hit, i, team_id)
                                    )
                                else:
                                    pending_damage.append(
                                        (enemy_team, target_idx, extra_hit, i, team_id)
                                    )
                    # Attack speed ramp: each hit reduces reload time
                    if my_ramp_reduction is not None and t_attack_speed_ramp > 0:
                        my_ramp_reduction[i] += t_attack_speed_ramp
                        my_cooldown[i] = max(
                            t_attack_speed_min,
                            t_reload - my_ramp_reduction[i],
                        )
                    else:
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
                        # Charge attack bonus (Coustillier)
                        if my_charge_ready and my_charge_ready[i]:
                            hit_dmg += t_charge_melee
                            my_charge_ready[i] = False
                            my_charge_timer[i] = t_charge_recharge
                        pending_damage.append(
                            (enemy_team, target_idx, hit_dmg, i, team_id)
                        )
                        # Attack speed ramp: each hit reduces reload time
                        if my_ramp_reduction is not None and t_attack_speed_ramp > 0:
                            my_ramp_reduction[i] += t_attack_speed_ramp
                            my_cooldown[i] = max(
                                t_attack_speed_min,
                                t_reload - my_ramp_reduction[i],
                            )
                        else:
                            my_cooldown[i] = t_reload

        # Snapshot alive counts before damage (for ally-death-heal detection)
        pre_alive1 = len(alive1) if s.death_heal_timer1 is not None else 0
        pre_alive2 = len(alive2) if s.death_heal_timer2 is not None else 0

        # --- Apply all pending damage atomically ---
        _apply_tick_damage(s, pending_damage, alive1, alive2)

        # --- Tick-based effects ---
        _apply_tick_effects(s, alive1, alive2)

        # --- Ally death heal trigger (Guecha Warrior) ---
        # If any allied Guecha died this tick, refresh heal timer on all survivors.
        if s.death_heal_timer1 is not None:
            post_alive1 = sum(1 for i in range(count1) if hp1[i] > 0)
            if post_alive1 < pre_alive1 and post_alive1 > 0:
                for i in range(count1):
                    if hp1[i] > 0:
                        s.death_heal_timer1[i] = s.ally_death_heal_dur1
        if s.death_heal_timer2 is not None:
            post_alive2 = sum(1 for i in range(count2) if hp2[i] > 0)
            if post_alive2 < pre_alive2 and post_alive2 > 0:
                for i in range(count2):
                    if hp2[i] > 0:
                        s.death_heal_timer2[i] = s.ally_death_heal_dur2

    # =========================================================
    # PHASE 3: Winner determination
    # =========================================================
    return _determine_winner(s, tick, return_hp, return_ticks)
