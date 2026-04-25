"""
Position-aware battle simulation — Python port of the JS canvas sim in
static/js/simulate.js.

Differences from simulation.py (the fast tick-based sim):
- Real 2D positions, distance-based range checks.
- Movement toward target at unit speed.
- Projectiles travel in flight; damage applied on impact.
- Kiting: ranged-vs-melee units back away during reload.
- Hard collision resolution (units push apart when overlapping).

Coordinate system: tiles (1.0 = 1 tile). The JS sim uses pixels with
TILE_SIZE=30; we skip the scaling and work in tiles directly. The 5px
melee buffer becomes 0.17 tiles. Map is 30x20 tiles (= 900x600 px).

Public entry point matches simulate_battle()'s signature:

    simulate_real_battle(unit1, unit2, resources,
                         fixed_count=None,
                         cost1_override=None, cost2_override=None,
                         return_hp=False, return_ticks=False)

so it's a drop-in replacement in callers that pass the same args.
"""

import json
import math
import random
import time as _time

try:
    from webapp.battle_outcome import BattleOutcome
except ImportError:
    from battle_outcome import BattleOutcome

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tick rate: 30 Hz fixed.  JS uses variable RAF; we use a fixed dt for
# determinism and reproducibility.
DT = 1.0 / 30.0

# Match the JS sim's pixel-space buffer (5 px / 30 px-per-tile = 0.167 tiles)
MELEE_RANGE_BUFFER = 5.0 / 30.0

# Map size in tiles (matches 900x600 canvas / TILE_SIZE 30)
MAP_W = 30.0
MAP_H = 20.0

# Default projectile speed when stat is 0 (JS fallback: 7 * TILE_SIZE px/s)
DEFAULT_PROJECTILE_SPEED = 7.0  # tiles/s

# Battle timeout (game-time seconds).  Hard cap — at this point the leader
# (by raw HP diff) is declared winner.  Calibrated from sample_sim_timings.py:
# typical battles end naturally in 20-65s of game time, so 60s catches the
# tail without sacrificing accuracy on the cases that mattered.
MAX_BATTLE_SECONDS = 60.0

# Wall-clock cap (seconds): if a single sim takes longer than this in real
# time, abort and award winner by HP%.  Backstop only — with the 60s game-time
# cap, sims now have a bounded tick budget and rarely hit this.
DEFAULT_MAX_WALLCLOCK_SECONDS = 90.0

# Decisive-lead early exit:
#   Every DECISIVE_CHECK_INTERVAL_S of game time (starting at t = interval),
#   if |hp1_pct - hp2_pct| >= DECISIVE_HP_DELTA, declare the leader.
#   Calibrated from sample_sim_timings.py: most battles develop a clear
#   20pp+ lead by 15-30s game time, so this clips them off as soon as the
#   outcome is decided rather than running to last-unit-standing.
DECISIVE_CHECK_INTERVAL_S = 15.0
DECISIVE_HP_DELTA = 0.20

# Movement smoothing factor (matches JS: 0.3 means blend 30% old + 70% new).
MOVE_SMOOTHING = 0.3

# Stuck detection threshold (matches JS: 0.5 px in pixel-space → 0.5/30 tiles)
STUCK_PROGRESS_THRESHOLD = 0.5 / 30.0
STUCK_TIMER_LIMIT = 0.8  # seconds

# Spatial-grid cell size (tiles).  Must be >= the max relevant interaction
# distance (avoidance ~3 tiles, collision ~2 tiles) so that a unit's cell + 8
# adjacent cells cover everything that could matter.  3.5 tiles is comfortable
# headroom for the largest unit radii (~1 tile) plus avoidance multiplier.
GRID_CELL_SIZE = 3.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_int(v):
    return int(v) if v is not None else 0


def _to_float(v, default=0.0):
    return float(v) if v is not None else default


def _parse_attacks_armors(s):
    """Accept either a JSON string, a pre-parsed dict (post prepare_combat_unit),
    or None.  Return {str_class_id: float_value}.  Internal keys are strings to
    match the JS sim's JSON.parse behavior.
    """
    if not s:
        return {}
    if isinstance(s, dict):
        return {str(k): float(v) for k, v in s.items()}
    try:
        d = json.loads(s)
        return {str(k): float(v) for k, v in d.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def _stat_attacks(stats):
    """Pull the attacks dict from a combat-unit dict.

    Handles both forms:
    - Raw `build_combat_dict_from_ref` output: stats["attacks_json"] is a JSON string
    - Post `prepare_combat_unit`: stats["attacks"] is an int-keyed dict
    """
    if "attacks" in stats and isinstance(stats["attacks"], dict):
        return _parse_attacks_armors(stats["attacks"])
    return _parse_attacks_armors(stats.get("attacks_json"))


def _stat_armors(stats):
    if "armors" in stats and isinstance(stats["armors"], dict):
        return _parse_attacks_armors(stats["armors"])
    return _parse_attacks_armors(stats.get("armors_json"))


def _stat_extra_proj_attacks(stats):
    v = stats.get("extra_projectile_attacks")
    if isinstance(v, dict):
        return _parse_attacks_armors(v)
    return _parse_attacks_armors(stats.get("extra_projectile_attacks_json"))


def _stat_charge_proj_attacks(stats):
    v = stats.get("charge_projectile_attacks")
    if isinstance(v, dict):
        return _parse_attacks_armors(v)
    return _parse_attacks_armors(stats.get("charge_projectile_attacks_json"))


# ---------------------------------------------------------------------------
# Spatial grid (uniform-bucket) for O(N) collision/avoidance queries
# ---------------------------------------------------------------------------


class SpatialGrid:
    """Uniform-grid spatial index.  Rebuilt every tick.

    Cell size is chosen so that all relevant pairwise interactions
    (avoidance, collision) for any unit lie inside the unit's own cell or
    one of the 8 adjacent cells.  This is exact for our use case — same
    forces and collisions resolve as the O(N²) version, just faster.
    """

    __slots__ = ("cell_size", "inv", "cells")

    def __init__(self, cell_size=GRID_CELL_SIZE):
        self.cell_size = cell_size
        self.inv = 1.0 / cell_size
        self.cells = {}

    def rebuild(self, units):
        cells = {}
        inv = self.inv
        for u in units:
            if u.state == "dead":
                continue
            key = (int(u.x * inv), int(u.y * inv))
            bucket = cells.get(key)
            if bucket is None:
                cells[key] = [u]
            else:
                bucket.append(u)
        self.cells = cells

    def neighbors(self, unit):
        """Iterate all units in the 3x3 block of cells around `unit`.
        Includes `unit` itself; callers should skip it.
        """
        cx = int(unit.x * self.inv)
        cy = int(unit.y * self.inv)
        cells = self.cells
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                bucket = cells.get((cx + dx, cy + dy))
                if bucket:
                    for n in bucket:
                        yield n


# ---------------------------------------------------------------------------
# Projectile
# ---------------------------------------------------------------------------


class Projectile:
    __slots__ = ("x", "y", "tx", "ty", "speed", "team", "is_siege",
                 "on_hit", "done")

    def __init__(self, x, y, tx, ty, speed, team, is_siege, on_hit):
        self.x = x
        self.y = y
        self.tx = tx
        self.ty = ty
        self.speed = speed if speed > 0 else DEFAULT_PROJECTILE_SPEED
        self.team = team
        self.is_siege = is_siege
        self.on_hit = on_hit
        self.done = False

    def update(self, dt):
        if self.done:
            return
        dx = self.tx - self.x
        dy = self.ty - self.y
        dist = math.hypot(dx, dy)
        move = self.speed * dt
        if dist <= move:
            self.x = self.tx
            self.y = self.ty
            self.done = True
            if self.on_hit:
                self.on_hit()
        else:
            self.x += (dx / dist) * move
            self.y += (dy / dist) * move


# ---------------------------------------------------------------------------
# BattleUnit
# ---------------------------------------------------------------------------


class BattleUnit:
    __slots__ = (
        "id", "team", "stats",
        "cost_food", "cost_wood", "cost_gold",
        "max_hp", "current_hp", "attack",
        "raw_attack_range", "attack_range",
        "attack_speed", "reload_time", "attack_delay",
        "move_speed",
        "melee_armor", "pierce_armor", "attacks", "armors",
        "accuracy", "base_accuracy",
        "min_attack_range", "is_siege_projectile", "splash_radius",
        "projectile_speed", "ignores_pierce_armor", "ignores_melee_armor",
        "trample_percent", "trample_radius", "trample_flat_damage",
        "bonus_damage_reduction",
        "extra_projectiles", "extra_proj_attacks",
        "splash_on_hit_radius", "splash_on_hit_fraction",
        "dodge_shield_max", "dodge_shield_recharge",
        "bleed_dps", "bleed_duration",
        "block_first_melee", "attack_bonus_per_kill",
        "first_attack_extra_projectiles",
        "hp_transform_threshold", "hp_regen",
        "pass_through_percent", "pass_through_count",
        "charge_projectile_count", "charge_projectile_speed",
        "charge_attack_range", "charge_ignores_armor", "charge_projectile_attacks",
        "shield_charges", "shield_recharge_timer",
        "has_blocked_first_melee", "kill_bonus_attack",
        "has_used_first_attack", "is_transformed",
        "bleed_effect", "has_used_charge",
        "x", "y", "radius",
        "target", "state", "attack_cooldown",
        "was_moving", "committed_attack",
        "vx", "vy",
        "stuck_timer", "last_dist_to_target", "blocked_targets",
    )

    def __init__(self, uid, team, stats):
        self.id = uid
        self.team = team
        self.stats = stats

        self.cost_food = float(stats.get("cost_food") or 0)
        self.cost_wood = float(stats.get("cost_wood") or 0)
        self.cost_gold = float(stats.get("cost_gold") or 0)

        self.max_hp = float(stats["hp"])
        self.current_hp = float(stats["hp"])
        self.attack = float(stats["attack"])

        # Range: JS adds MELEE_RANGE_BUFFER even for ranged units.
        self.raw_attack_range = float(stats.get("attack_range") or 0.0)
        self.attack_range = self.raw_attack_range + MELEE_RANGE_BUFFER

        self.attack_speed = float(stats.get("attack_speed") or 0.5)
        self.reload_time = 1.0 / self.attack_speed if self.attack_speed > 0 else 2.0
        self.attack_delay = float(stats.get("attack_delay") or 0)

        # Movement speed: stats.movement_speed is already in tiles/sec.
        self.move_speed = float(stats.get("movement_speed") or 1.0)

        self.melee_armor = float(stats.get("melee_armor") or 0)
        self.pierce_armor = float(stats.get("pierce_armor") or 0)
        self.attacks = _stat_attacks(stats)
        self.armors = _stat_armors(stats)

        # Accuracy
        self.accuracy = float(stats.get("accuracy") or 100) / 100.0
        self.base_accuracy = float(stats.get("base_accuracy") or 100) / 100.0

        # Combat properties
        self.min_attack_range = float(stats.get("min_attack_range") or 0)
        self.is_siege_projectile = _to_int(stats.get("is_siege_projectile"))
        self.splash_radius = float(stats.get("splash_radius") or 0)
        self.projectile_speed = float(stats.get("projectile_speed") or 0)
        self.ignores_pierce_armor = _to_int(stats.get("ignores_pierce_armor"))
        self.ignores_melee_armor = _to_int(stats.get("ignores_melee_armor"))
        self.trample_percent = float(stats.get("trample_percent") or 0)
        self.trample_radius = float(stats.get("trample_radius") or 0)
        self.trample_flat_damage = float(stats.get("trample_flat_damage") or 0)
        self.bonus_damage_reduction = float(stats.get("bonus_damage_reduction") or 0)

        # Unique mechanics
        self.extra_projectiles = _to_int(stats.get("extra_projectiles"))
        self.extra_proj_attacks = _stat_extra_proj_attacks(stats)
        self.splash_on_hit_radius = float(stats.get("splash_on_hit_radius") or 0)
        self.splash_on_hit_fraction = float(stats.get("splash_on_hit_fraction") or 1.0)
        self.dodge_shield_max = _to_int(stats.get("dodge_shield_max"))
        self.dodge_shield_recharge = float(stats.get("dodge_shield_recharge") or 0)
        self.bleed_dps = float(stats.get("bleed_dps") or 0)
        self.bleed_duration = float(stats.get("bleed_duration") or 0)
        self.block_first_melee = _to_int(stats.get("block_first_melee"))
        self.attack_bonus_per_kill = _to_int(stats.get("attack_bonus_per_kill"))
        self.first_attack_extra_projectiles = _to_int(
            stats.get("first_attack_extra_projectiles")
        )
        self.hp_transform_threshold = float(stats.get("hp_transform_threshold") or 0)
        self.hp_regen = float(stats.get("hp_regen") or 0)
        self.pass_through_percent = float(stats.get("pass_through_percent") or 0)
        self.pass_through_count = max(1, _to_int(stats.get("pass_through_count")) or 1)

        # Charge projectiles (Fire Lancer)
        self.charge_projectile_count = _to_int(stats.get("charge_projectile_count"))
        self.charge_projectile_speed = float(stats.get("charge_projectile_speed") or 0)
        self.charge_attack_range = float(stats.get("charge_attack_range") or 0)
        self.charge_ignores_armor = _to_int(stats.get("charge_ignores_armor"))
        self.charge_projectile_attacks = _stat_charge_proj_attacks(stats)

        # State
        self.shield_charges = float(self.dodge_shield_max)
        self.shield_recharge_timer = 0.0
        self.has_blocked_first_melee = False
        self.kill_bonus_attack = 0.0
        self.has_used_first_attack = False
        self.is_transformed = False
        self.bleed_effect = None  # {"dps": float, "time_remaining": float}
        self.has_used_charge = False

        self.x = 0.0
        self.y = 0.0
        # Outline-size scaling matches JS: 0.2->14 px, 0.5->20 px, 1.0->30 px.
        # Convert to tiles by dividing by TILE_SIZE=30.
        outline = float(stats.get("outline_size") or 0.2)
        self.radius = (10.0 + min(outline, 1.0) * 20.0) / 30.0

        self.target = None
        self.state = "idle"
        self.attack_cooldown = 0.0
        self.was_moving = True
        self.committed_attack = None  # {"target": unit, "time_left": float}

        # Movement smoothing
        self.vx = 0.0
        self.vy = 0.0
        # Stuck detection
        self.stuck_timer = 0.0
        self.last_dist_to_target = float("inf")
        self.blocked_targets = set()

    # ---- Predicates -------------------------------------------------------

    def is_ranged(self):
        return self.raw_attack_range >= 1.0

    def is_dead(self):
        return self.state == "dead"

    def distance_to(self, other):
        return math.hypot(other.x - self.x, other.y - self.y)

    def in_range(self):
        if not self.target:
            return False
        d = self.distance_to(self.target)
        eff_range = self.attack_range + self.radius + self.target.radius
        if d > eff_range:
            return False
        if self.min_attack_range > 0 and d < self.min_attack_range:
            return False
        return True

    def too_close(self):
        if not self.target or self.min_attack_range <= 0:
            return False
        return self.distance_to(self.target) < self.min_attack_range

    # ---- Damage calc ------------------------------------------------------

    def get_damage_against(self, target, attacks_override=None,
                           ignores_armor_override=None):
        is_ranged = self.is_ranged()
        attacks = attacks_override if attacks_override is not None else self.attacks
        base_class = "3" if is_ranged else "4"
        base_attack = attacks.get(base_class, attacks.get("4", self.attack))

        if ignores_armor_override is not None:
            ignore = ignores_armor_override
        else:
            ignore = (is_ranged and self.ignores_pierce_armor) or \
                     (not is_ranged and self.ignores_melee_armor)

        if ignore:
            target_base_armor = 0.0
        elif is_ranged:
            target_base_armor = target.armors.get("3", target.pierce_armor)
        else:
            target_base_armor = target.armors.get("4", target.melee_armor)

        base_dmg = max(0, base_attack - target_base_armor)

        bonus_damage = 0.0
        for armor_class, attack_value in attacks.items():
            if armor_class in ("3", "4"):
                continue
            if attack_value <= 0:
                continue
            if armor_class in target.armors:
                target_armor = target.armors[armor_class]
                bonus_damage += max(0, attack_value - target_armor)

        if target.bonus_damage_reduction > 0:
            bonus_damage = math.floor(bonus_damage * (1 - target.bonus_damage_reduction))

        return max(1, base_dmg + bonus_damage)

    # ---- Targeting --------------------------------------------------------

    def find_target(self, enemies):
        closest = None
        closest_dist = float("inf")
        fallback = None
        fallback_dist = float("inf")
        for enemy in enemies:
            if enemy.state == "dead":
                continue
            d = self.distance_to(enemy)
            if enemy not in self.blocked_targets:
                if d < closest_dist:
                    closest_dist = d
                    closest = enemy
            if d < fallback_dist:
                fallback_dist = d
                fallback = enemy
        self.target = closest or fallback
        self.stuck_timer = 0.0
        self.last_dist_to_target = self.distance_to(self.target) if self.target else float("inf")
        return self.target

    # ---- Update -----------------------------------------------------------

    def update(self, dt, grid, enemies, sim):
        if self.state == "dead":
            return

        # Alias hot attributes to locals for the duration of this tick
        cooldown = max(0.0, self.attack_cooldown - dt)
        self.attack_cooldown = cooldown

        if self.hp_regen > 0 and 0 < self.current_hp < self.max_hp:
            self.current_hp = min(self.max_hp, self.current_hp + (self.hp_regen / 60.0) * dt)

        if self.bleed_effect:
            self.current_hp -= self.bleed_effect["dps"] * dt
            self.bleed_effect["time_remaining"] -= dt
            if self.bleed_effect["time_remaining"] <= 0:
                self.bleed_effect = None
            if self.current_hp <= 0:
                self.current_hp = 0
                self.state = "dead"
                self.target = None
                return

        if self.shield_recharge_timer > 0:
            self.shield_recharge_timer -= dt
            if self.shield_recharge_timer <= 0:
                self.shield_charges = min(self.shield_charges + 1, self.dodge_shield_max)
                if self.shield_charges < self.dodge_shield_max:
                    self.shield_recharge_timer = self.dodge_shield_recharge
                else:
                    self.shield_recharge_timer = 0

        if self.hp_transform_threshold > 0 and not self.is_transformed:
            if self.current_hp <= self.max_hp * self.hp_transform_threshold and self.current_hp > 0:
                self.is_transformed = True
                self.kill_bonus_attack += 3

        # Clean blocked targets
        dead_blocked = [bt for bt in self.blocked_targets if bt.state == "dead"]
        for bt in dead_blocked:
            self.blocked_targets.discard(bt)
        alive_count = sum(1 for e in enemies if e.state != "dead")
        if self.blocked_targets and len(self.blocked_targets) >= alive_count:
            self.blocked_targets.clear()

        if not self.target or self.target.state == "dead":
            self.find_target(enemies)
        if not self.target:
            self.state = "idle"
            return

        was_moving = self.was_moving
        if self.is_ranged():
            should_kite = not self.target.is_ranged()
            if self.too_close():
                self.state = "kiting"
                self.move_away_from_target(dt, grid)
                self.was_moving = True
            elif not was_moving and cooldown <= 0:
                self.state = "attacking"
                self.perform_attack(sim)
                self.was_moving = True
            elif not was_moving:
                self.state = "attacking"
            elif cooldown > 0 and should_kite:
                self.state = "kiting"
                self.move_away_from_target(dt, grid)
            elif cooldown > 0:
                self.state = "attacking"
            elif self.in_range():
                self.attack_cooldown = self.attack_delay
                self.was_moving = False
                self.state = "attacking"
            else:
                self.state = "moving"
                self.move_toward_target(dt, grid)
        else:
            # Charge projectile attack (Fire Lancer)
            if (self.charge_projectile_count > 0 and not self.has_used_charge
                    and self.target):
                d = self.distance_to(self.target)
                charge_range = self.charge_attack_range + self.radius + self.target.radius
                if d <= charge_range:
                    self.has_used_charge = True
                    self.state = "attacking"
                    for _ in range(self.charge_projectile_count):
                        self.fire_charge_projectile(self.target, sim)
                    self.attack_cooldown = self.reload_time
                else:
                    self.state = "moving"
                    self.move_toward_target(dt, grid)
                    self.was_moving = True
            elif self.committed_attack:
                self.committed_attack["time_left"] -= dt
                self.state = "committed"
                if self.committed_attack["time_left"] <= 0:
                    target = self.committed_attack["target"]
                    if target.state != "dead":
                        self.perform_attack_on(target, sim)
                    self.committed_attack = None
                    self.attack_cooldown = self.reload_time
                    self.was_moving = False
            elif self.in_range():
                if self.attack_cooldown <= 0:
                    if self.attack_delay > 0:
                        self.committed_attack = {
                            "target": self.target,
                            "time_left": self.attack_delay,
                        }
                        self.state = "committed"
                        self.was_moving = False
                    else:
                        self.state = "attacking"
                        self.perform_attack(sim)
                else:
                    self.state = "attacking"
            else:
                self.state = "moving"
                self.move_toward_target(dt, grid)
                self.was_moving = True

    # ---- Attacks ----------------------------------------------------------

    def perform_attack(self, sim):
        if not self.target or self.target.state == "dead":
            return
        num_proj = 1 + self.extra_projectiles
        if self.first_attack_extra_projectiles > 0 and not self.has_used_first_attack:
            num_proj += self.first_attack_extra_projectiles
            self.has_used_first_attack = True
        for p_idx in range(num_proj):
            if not self.target or self.target.state == "dead":
                break
            if self.is_ranged():
                # Primary uses unit accuracy; extras use base_accuracy (Thumb Ring
                # is primary-only).  This mirrors the modeling fix in
                # simulation.py / commit 756705e.
                is_extra = (p_idx > 0)
                if is_extra and self.extra_proj_attacks:
                    # Some extras (e.g. Bolt Magazine) use a different attack profile.
                    self.fire_projectile(self.target, sim,
                                         attacks_override=self.extra_proj_attacks,
                                         is_extra=True)
                else:
                    self.fire_projectile(self.target, sim, is_extra=is_extra)
            else:
                self.perform_attack_on(self.target, sim)
        self.attack_cooldown = self.reload_time

    def fire_projectile(self, target, sim, attacks_override=None, is_extra=False):
        damage = self.get_damage_against(target, attacks_override=attacks_override) \
            + math.floor(self.kill_bonus_attack)

        # Accuracy roll: misses still spawn a projectile but apply 0 damage on hit
        accuracy = self.base_accuracy if is_extra else self.accuracy
        will_hit = random.random() < accuracy if accuracy < 1.0 else True

        speed = self.projectile_speed if self.projectile_speed > 0 else DEFAULT_PROJECTILE_SPEED
        # Mangonel-style splash: scale up if too small (matches JS heuristic)
        splash_r = max(self.splash_radius, 2.5) if self.splash_radius > 0 else 0
        impact_x = target.x
        impact_y = target.y
        attacker = self
        team = self.team

        def on_hit():
            target_was_alive = target.state != "dead"
            if target.state != "dead" and will_hit:
                target.take_damage(damage, attacker)

            if (attacker.attack_bonus_per_kill > 0 and target_was_alive
                    and target.state == "dead"):
                attacker.kill_bonus_attack += attacker.attack_bonus_per_kill

            if splash_r > 0 and will_hit:
                enemies = sim.team2 if team == 1 else sim.team1
                for enemy in enemies:
                    if enemy is target or enemy.state == "dead":
                        continue
                    dx = enemy.x - impact_x
                    dy = enemy.y - impact_y
                    d = math.hypot(dx, dy)
                    if d <= splash_r + enemy.radius:
                        ratio = min(1.0, d / splash_r)
                        falloff = 1.0 - 0.75 * ratio
                        splash_dmg = max(1, round(damage * falloff))
                        enemy.take_damage(splash_dmg, attacker)

            if attacker.splash_on_hit_radius > 0 and splash_r == 0 and will_hit:
                enemies = sim.team2 if team == 1 else sim.team1
                for enemy in enemies:
                    if enemy is target or enemy.state == "dead":
                        continue
                    dx = enemy.x - impact_x
                    dy = enemy.y - impact_y
                    _r = attacker.splash_on_hit_radius + enemy.radius
                    if dx * dx + dy * dy <= _r * _r:
                        s_dmg = max(1, math.floor(damage * attacker.splash_on_hit_fraction))
                        enemy.take_damage(s_dmg, attacker)

            if attacker.pass_through_percent > 0 and will_hit:
                pt_dmg = max(1, math.floor(damage * attacker.pass_through_percent))
                enemies = sim.team2 if team == 1 else sim.team1
                # Find up to pass_through_count closest alive non-target enemies
                candidates = []
                for enemy in enemies:
                    if enemy is target or enemy.state == "dead":
                        continue
                    dx = enemy.x - target.x
                    dy = enemy.y - target.y
                    candidates.append((math.hypot(dx, dy), enemy))
                candidates.sort(key=lambda c: c[0])
                for _, enemy in candidates[:max(1, attacker.pass_through_count - 1) or 1]:
                    enemy.take_damage(pt_dmg, attacker)

            if attacker.bleed_dps > 0 and target_was_alive and will_hit:
                target.bleed_effect = {
                    "dps": attacker.bleed_dps,
                    "time_remaining": attacker.bleed_duration,
                }

        proj = Projectile(self.x, self.y, target.x, target.y, speed, team,
                          self.is_siege_projectile, on_hit)
        sim.projectiles.append(proj)

    def fire_charge_projectile(self, target, sim):
        if not target or target.state == "dead":
            return
        charge_dmg = 0.0
        if self.charge_projectile_attacks:
            for cls, atk_val in self.charge_projectile_attacks.items():
                if atk_val <= 0:
                    continue
                if self.charge_ignores_armor:
                    charge_dmg += atk_val
                else:
                    armor = target.armors.get(cls, 0)
                    charge_dmg += max(0, atk_val - armor)
        charge_dmg = max(1, charge_dmg)
        speed = self.charge_projectile_speed if self.charge_projectile_speed > 0 else DEFAULT_PROJECTILE_SPEED
        attacker = self

        def on_hit():
            if target.state == "dead":
                return
            target.take_damage(charge_dmg, attacker)

        proj = Projectile(self.x, self.y, target.x, target.y, speed, self.team,
                          False, on_hit)
        sim.projectiles.append(proj)

    def perform_attack_on(self, target, sim):
        if not target or target.state == "dead":
            return
        damage = self.get_damage_against(target) + math.floor(self.kill_bonus_attack)
        target_was_alive = target.state != "dead"
        target.take_damage(damage, self)

        if (self.attack_bonus_per_kill > 0 and target_was_alive
                and target.state == "dead"):
            self.kill_bonus_attack += self.attack_bonus_per_kill

        # Trample (melee)
        if not self.is_ranged():
            if self.trample_percent > 0 or self.trample_flat_damage > 0:
                trample_dmg = math.floor(damage * self.trample_percent) + self.trample_flat_damage
                if trample_dmg > 0:
                    enemies = sim.team2 if self.team == 1 else sim.team1
                    for enemy in enemies:
                        if enemy is target or enemy.state == "dead":
                            continue
                        if self.distance_to(enemy) <= self.trample_radius + enemy.radius:
                            enemy.take_damage(trample_dmg, self)

        if self.splash_on_hit_radius > 0:
            enemies = sim.team2 if self.team == 1 else sim.team1
            for enemy in enemies:
                if enemy is target or enemy.state == "dead":
                    continue
                dx = enemy.x - target.x
                dy = enemy.y - target.y
                _r = self.splash_on_hit_radius + enemy.radius
                if dx * dx + dy * dy <= _r * _r:
                    s_dmg = max(1, math.floor(damage * self.splash_on_hit_fraction))
                    enemy.take_damage(s_dmg, self)

        if self.pass_through_percent > 0:
            pt_dmg = max(1, math.floor(damage * self.pass_through_percent))
            enemies = sim.team2 if self.team == 1 else sim.team1
            best, best_dist_sq = None, float("inf")
            for enemy in enemies:
                if enemy is target or enemy.state == "dead":
                    continue
                dx = enemy.x - target.x
                dy = enemy.y - target.y
                d_sq = dx * dx + dy * dy
                if d_sq < best_dist_sq:
                    best_dist_sq, best = d_sq, enemy
            if best:
                best.take_damage(pt_dmg, self)

        if self.bleed_dps > 0 and target_was_alive:
            target.bleed_effect = {
                "dps": self.bleed_dps,
                "time_remaining": self.bleed_duration,
            }

    # ---- Damage receipt ---------------------------------------------------

    def take_damage(self, amount, attacker):
        if (self.dodge_shield_max > 0 and attacker is not None
                and attacker.is_ranged() and self.shield_charges > 0):
            self.shield_charges -= 1
            self.shield_recharge_timer = self.dodge_shield_recharge
            return
        if (self.block_first_melee and attacker is not None
                and not attacker.is_ranged() and not self.has_blocked_first_melee):
            self.has_blocked_first_melee = True
            return
        self.current_hp -= amount
        if self.current_hp <= 0:
            self.current_hp = 0
            self.state = "dead"
            self.target = None

    # ---- Movement ---------------------------------------------------------

    def _calculate_avoidance(self, neighbor_iter):
        """Compute avoidance forces from nearby units.

        `neighbor_iter` is an iterable that yields candidate units (typically
        the spatial grid's 3x3 cell neighborhood — same set the O(N²) version
        would have inspected after distance culling, just delivered faster).
        """
        avoid_x, avoid_y = 0.0, 0.0
        sx, sy = self.x, self.y
        sqrt = math.sqrt
        for other in neighbor_iter:
            if other is self or other.state == "dead":
                continue
            dx = sx - other.x
            dy = sy - other.y
            d_sq = dx * dx + dy * dy
            if d_sq <= 0:
                continue
            min_d = self.radius + other.radius + 0.067
            if d_sq >= (min_d * 1.5) ** 2:
                continue
            d = sqrt(d_sq)
            overlap = max(0, min_d - d) / min_d
            force = 3 + overlap * 5 if overlap > 0 else 0.5
            avoid_x += (dx / d) * force
            avoid_y += (dy / d) * force
        return avoid_x, avoid_y

    def move_toward_target(self, dt, grid):
        if not self.target:
            return
        dx = self.target.x - self.x
        dy = self.target.y - self.y
        dist = math.hypot(dx, dy)
        if dist < 1.0 / 30.0:
            return
        dx /= dist
        dy /= dist
        ax, ay = self._calculate_avoidance(grid.neighbors(self))
        avoid_mag = math.hypot(ax, ay)
        if avoid_mag > 2:
            dx = ax + dx * 0.2
            dy = ay + dy * 0.2
        else:
            dx += ax
            dy += ay
        ln = math.hypot(dx, dy)
        if ln > 0:
            dx /= ln
            dy /= ln

        self.vx = self.vx * MOVE_SMOOTHING + dx * (1 - MOVE_SMOOTHING)
        self.vy = self.vy * MOVE_SMOOTHING + dy * (1 - MOVE_SMOOTHING)
        v_ln = math.hypot(self.vx, self.vy)
        if v_ln > 0:
            self.vx /= v_ln
            self.vy /= v_ln

        move = self.move_speed * dt
        self.x += self.vx * move
        self.y += self.vy * move
        self.x = max(self.radius, min(MAP_W - self.radius, self.x))
        self.y = max(self.radius, min(MAP_H - self.radius, self.y))

        new_dist = self.distance_to(self.target)
        if new_dist >= self.last_dist_to_target - STUCK_PROGRESS_THRESHOLD:
            self.stuck_timer += dt
        else:
            self.stuck_timer = max(0, self.stuck_timer - dt * 2)
        self.last_dist_to_target = new_dist
        if self.stuck_timer > STUCK_TIMER_LIMIT:
            self.blocked_targets.add(self.target)
            self.target = None
            self.stuck_timer = 0

    def move_away_from_target(self, dt, grid):
        if not self.target:
            return
        dx = self.x - self.target.x
        dy = self.y - self.target.y
        dist = math.hypot(dx, dy)
        if dist < 1.0 / 30.0:
            dx = -1.0 if self.team == 1 else 1.0
            dy = 0.0
        else:
            dx /= dist
            dy /= dist
        ax, ay = self._calculate_avoidance(grid.neighbors(self))
        dx += ax
        dy += ay
        ln = math.hypot(dx, dy)
        if ln > 0:
            dx /= ln
            dy /= ln
        self.vx = self.vx * MOVE_SMOOTHING + dx * (1 - MOVE_SMOOTHING)
        self.vy = self.vy * MOVE_SMOOTHING + dy * (1 - MOVE_SMOOTHING)
        v_ln = math.hypot(self.vx, self.vy)
        if v_ln > 0:
            self.vx /= v_ln
            self.vy /= v_ln
        move = self.move_speed * dt
        self.x += self.vx * move
        self.y += self.vy * move
        self.x = max(self.radius, min(MAP_W - self.radius, self.x))
        self.y = max(self.radius, min(MAP_H - self.radius, self.y))


# ---------------------------------------------------------------------------
# Battle simulation
# ---------------------------------------------------------------------------


class BattleSimulation:
    def __init__(self):
        self.team1 = []
        self.team2 = []
        self.projectiles = []
        self.battle_time = 0.0
        self.winner = None  # 1, 2, or 0 (draw)
        self.end_reason = None  # set when run() exits
        self.grid = SpatialGrid()
        self.alive = []  # maintained across ticks; populated on first step

    def setup_team(self, team_num, stats, count):
        team = []
        # Place units in a vertical line on the appropriate side.
        # Match JS layout but in tile coordinates.
        outline = float(stats.get("outline_size") or 0.2)
        radius = (10.0 + min(outline, 1.0) * 20.0) / 30.0
        start_x = (1.0 + radius) if team_num == 1 else (MAP_W - 1.0 - radius)
        min_spacing = radius * 2.2
        if count > 1:
            natural_spacing = (MAP_H - 2 * radius) / (count - 1)
        else:
            natural_spacing = 0.0
        spacing = max(natural_spacing, min_spacing)
        total_h = (count - 1) * spacing
        start_y = max(radius, (MAP_H - total_h) / 2) if count > 1 else MAP_H / 2

        for i in range(count):
            unit = BattleUnit(f"{team_num}-{i}", team_num, stats)
            # Tiny deterministic-ish jitter (no RNG: keep sim mostly deterministic).
            unit.x = start_x
            unit.y = start_y + i * spacing
            team.append(unit)

        if team_num == 1:
            self.team1 = team
        else:
            self.team2 = team

    def alive_count(self, team_num):
        team = self.team1 if team_num == 1 else self.team2
        return sum(1 for u in team if u.state != "dead")

    def total_hp(self, team_num):
        team = self.team1 if team_num == 1 else self.team2
        return sum(u.current_hp for u in team)

    def total_max_hp(self, team_num):
        team = self.team1 if team_num == 1 else self.team2
        return sum(u.max_hp for u in team)

    def total_resources_lost(self, team_num):
        team = self.team1 if team_num == 1 else self.team2
        # cost_food/wood/gold attached during prepare_combat_unit; default 0.
        total = 0
        for u in team:
            if u.state == "dead":
                total += int(u.cost_food + u.cost_wood + u.cost_gold)
        return total

    def step(self, dt):
        self.battle_time += dt

        # Maintain self.alive: on first step populate from both teams;
        # on subsequent steps prune units that died last tick.
        if not self.alive:
            self.alive = [u for u in self.team1 + self.team2 if u.state != "dead"]
        else:
            self.alive = [u for u in self.alive if u.state != "dead"]
        alive = self.alive

        # Rebuild spatial grid once per tick before unit updates (avoidance
        # queries the grid).
        self.grid.rebuild(alive)

        for u in self.team1:
            u.update(dt, self.grid, self.team2, self)
        for u in self.team2:
            u.update(dt, self.grid, self.team1, self)

        # Hard collision resolution using the grid.  Each unit checks only
        # its 3x3 cell neighborhood — same relevant pairs as O(N²) after
        # culling, just discovered faster.  We dedupe by id ordering (process
        # the pair only when a's id < b's id) to avoid a per-tick set.
        # Prune any units that died during this tick's update pass.
        self.alive = [u for u in alive if u.state != "dead"]
        alive = self.alive
        sqrt = math.sqrt
        EPS = 0.01 / 30.0
        EPS_NUDGE = 2.0 / 30.0
        # The grid was just rebuilt before unit updates and unit positions
        # shifted only by a fraction of a tile during update.  Rebuild once
        # here so collision sees fresh positions; skip rebuild between the
        # 2 collision passes since pass 1 only nudges units by tiny amounts.
        self.grid.rebuild(alive)
        for _ in range(2):
            for a in alive:
                ax, ay, ar = a.x, a.y, a.radius
                a_id = id(a)
                for b in self.grid.neighbors(a):
                    if b is a or b.state == "dead" or id(b) <= a_id:
                        continue
                    dx = b.x - ax
                    dy = b.y - ay
                    d_sq = dx * dx + dy * dy
                    min_d = ar + b.radius + 1.0 / 30.0
                    if d_sq >= min_d * min_d:
                        continue
                    if d_sq > EPS * EPS:
                        d = sqrt(d_sq)
                        overlap = (min_d - d) / 2
                        nx = dx / d
                        ny = dy / d
                        a.x -= nx * overlap
                        a.y -= ny * overlap
                        b.x += nx * overlap
                        b.y += ny * overlap
                        ax, ay = a.x, a.y
                    else:
                        a.x -= EPS_NUDGE
                        b.x += EPS_NUDGE
                        ax = a.x
        for u in alive:
            u.x = max(u.radius, min(MAP_W - u.radius, u.x))
            u.y = max(u.radius, min(MAP_H - u.radius, u.y))

        # Projectiles
        for p in self.projectiles:
            p.update(dt)
        self.projectiles = [p for p in self.projectiles if not p.done]

        a1 = self.alive_count(1)
        a2 = self.alive_count(2)
        if a1 == 0 and a2 > 0:
            self.winner = 2
            self.end_reason = "eliminated"
        elif a2 == 0 and a1 > 0:
            self.winner = 1
            self.end_reason = "eliminated"
        elif a1 == 0 and a2 == 0:
            self.winner = 0
            self.end_reason = "eliminated"

    def run(self, max_seconds=MAX_BATTLE_SECONDS,
            max_wallclock=DEFAULT_MAX_WALLCLOCK_SECONDS,
            decisive_interval_s=DECISIVE_CHECK_INTERVAL_S,
            decisive_delta=DECISIVE_HP_DELTA):
        """Run the sim until one of:
        1. One team wins naturally (last opposing unit dies)
        2. Decisive-lead early exit: every decisive_interval_s of game time,
           if |hp1_pct - hp2_pct| >= decisive_delta the leader wins.
        3. Game-time cap (max_seconds): winner is whichever side has more HP%
           remaining (any positive diff = win; equal = draw).
        4. Wall-clock cap (max_wallclock): backstop — winner by HP%.

        Returns the number of ticks elapsed.
        """
        max_ticks = int(max_seconds / DT)
        wall_start = _time.perf_counter()
        # Wall-clock check every 30 ticks (~1s of game time).
        wall_check_interval = 30

        # Decisive-lead checkpoints — first check at t = decisive_interval_s.
        decisive_step = max(1, int(decisive_interval_s / DT))
        next_decisive_tick = decisive_step

        for tick in range(max_ticks):
            self.step(DT)
            if self.winner is not None:
                return tick + 1

            # Decisive-lead check at scheduled tick milestones
            if tick + 1 >= next_decisive_tick:
                hp1_pct = self.total_hp(1) / max(1.0, self.total_max_hp(1))
                hp2_pct = self.total_hp(2) / max(1.0, self.total_max_hp(2))
                if abs(hp1_pct - hp2_pct) >= decisive_delta:
                    self.winner = 1 if hp1_pct > hp2_pct else 2
                    self.end_reason = "decisive_lead"
                    return tick + 1
                next_decisive_tick += decisive_step

            # Wall-clock backstop
            if max_wallclock and (tick + 1) % wall_check_interval == 0:
                if _time.perf_counter() - wall_start >= max_wallclock:
                    break

        # Game-time cap (60s) or wall-clock backstop reached
        hp1_pct = self.total_hp(1) / max(1.0, self.total_max_hp(1))
        hp2_pct = self.total_hp(2) / max(1.0, self.total_max_hp(2))
        if hp1_pct > hp2_pct:
            self.winner = 1
        elif hp2_pct > hp1_pct:
            self.winner = 2
        else:
            self.winner = 0
        self.end_reason = "time_cap"
        return tick + 1


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _calc_count(unit, resources, fixed_count, cost_override):
    if fixed_count is not None:
        pop = float(unit.get("pop_space") or 1.0)
        return max(1, int(fixed_count / pop))
    cost = cost_override
    if cost is None:
        cost = unit["cost"] if unit.get("cost") and unit["cost"] > 0 else 100
    return int(max(1, resources // cost))


def simulate_real_battle(
    unit1,
    unit2,
    resources,
    fixed_count=None,
    cost1_override=None,
    cost2_override=None,
    return_hp=False,             # legacy param, ignored by default new return
    return_ticks=False,          # legacy param, ignored by default new return
    max_seconds=MAX_BATTLE_SECONDS,
    max_wallclock=DEFAULT_MAX_WALLCLOCK_SECONDS,
    seed=None,
    _legacy_tuple=False,         # set True for old tuple return shape
):
    """Position-aware battle simulation. Returns BattleOutcome.

    For backwards compatibility, callers that still want the old (winner,
    remaining1, remaining2, [hp1, hp2, [ticks]]) tuple shape can pass
    `_legacy_tuple=True` along with `return_hp` / `return_ticks`.
    """
    if seed is not None:
        random.seed(seed)

    count1 = _calc_count(unit1, resources, fixed_count, cost1_override)
    count2 = _calc_count(unit2, resources, fixed_count, cost2_override)

    sim = BattleSimulation()
    sim.setup_team(1, unit1, count1)
    sim.setup_team(2, unit2, count2)
    elapsed_ticks = sim.run(max_seconds=max_seconds, max_wallclock=max_wallclock)

    winner = sim.winner if sim.winner is not None else 0
    remaining1 = sim.alive_count(1)
    remaining2 = sim.alive_count(2)
    hp1_pct = sim.total_hp(1) / max(1.0, sim.total_max_hp(1))
    hp2_pct = sim.total_hp(2) / max(1.0, sim.total_max_hp(2))

    if _legacy_tuple:
        if return_ticks:
            return winner, remaining1, remaining2, hp1_pct, hp2_pct, elapsed_ticks
        if return_hp:
            return winner, remaining1, remaining2, hp1_pct, hp2_pct
        return winner, remaining1, remaining2

    return BattleOutcome(
        winner=winner,
        end_reason=sim.end_reason or "time_cap",
        game_time_s=round(elapsed_ticks * DT, 3),
        team1_hp_pct=round(hp1_pct, 4),
        team2_hp_pct=round(hp2_pct, 4),
        team1_survivors=remaining1,
        team2_survivors=remaining2,
        team1_resources_lost=sim.total_resources_lost(1),
        team2_resources_lost=sim.total_resources_lost(2),
        team1_start_count=count1,
        team2_start_count=count2,
    )


# Convenience: build a deterministic seed from civ/slug pair so the same
# matchup always produces the same result.  Callers can pass this as `seed=`.
def deterministic_seed(*parts):
    return abs(hash("|".join(str(p) for p in parts))) & 0xFFFFFFFF
