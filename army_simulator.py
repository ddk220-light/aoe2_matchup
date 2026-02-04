#!/usr/bin/env python3
"""
AoE2 Army Combat Simulator

Simulates combat between armies of units (not just 1v1).
Uses resource budgets to determine army sizes.

Usage:
    python army_simulator.py --resources 5000
    python army_simulator.py --resources 5000 --output results.csv
"""

import argparse
import csv
import json
import random
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "webapp" / "aoe2_units.db"


@dataclass
class Unit:
    """A single unit in combat."""

    id: int
    name: str
    civ: str
    max_hp: int
    current_hp: float
    attack: int
    melee_armor: int
    pierce_armor: int
    reload_time: float
    attacks: dict
    armors: dict
    cost: int
    attack_range: float = 0.0  # 0 = melee
    speed: float = 1.0  # movement speed
    position: float = 0.0  # 1D position for simplified kiting
    target: Optional["Unit"] = None
    attack_cooldown: float = 0.0
    is_dead: bool = False

    def is_ranged(self) -> bool:
        """Check if this is a ranged unit."""
        return self.attack_range >= 1.0

    def get_damage_against(self, target: "Unit") -> int:
        """Calculate damage dealt to a target unit."""
        # Use pierce attack (class 3) for ranged, melee (class 4) for melee
        if self.is_ranged():
            base_damage = self.attacks.get(3, self.attacks.get(4, self.attack))
            target_armor = target.armors.get(3, target.pierce_armor)
        else:
            base_damage = self.attacks.get(4, self.attack)
            target_armor = target.armors.get(4, target.melee_armor)

        bonus_damage = 0
        for armor_class, armor_value in target.armors.items():
            if armor_class in self.attacks and armor_class not in (3, 4):
                attack_bonus = self.attacks[armor_class]
                if attack_bonus > 0:
                    effective_bonus = max(0, attack_bonus - armor_value)
                    bonus_damage += effective_bonus

        total_damage = max(1, base_damage + bonus_damage - target_armor)
        return total_damage

    def find_target(self, enemies: list["Unit"]) -> Optional["Unit"]:
        """Find closest living enemy."""
        alive_enemies = [e for e in enemies if not e.is_dead]
        if not alive_enemies:
            return None
        # Find closest by position
        return min(alive_enemies, key=lambda e: abs(e.position - self.position))

    def get_distance_to(self, other: "Unit") -> float:
        """Get distance to another unit."""
        return abs(self.position - other.position)

    def update(
        self, dt: float, enemies: list["Unit"], team_direction: int
    ) -> tuple[Optional["Unit"], int]:
        """Update unit state for one time step.

        Args:
            dt: Time delta
            enemies: List of enemy units
            team_direction: 1 for team moving right, -1 for team moving left

        Returns:
            Tuple of (target, damage) if an attack was made, (None, 0) otherwise.
            Damage is calculated but NOT applied - caller must apply damage after
            all units have calculated their attacks (for simultaneous combat).
        """
        if self.is_dead:
            return (None, 0)

        self.attack_cooldown = max(0, self.attack_cooldown - dt)

        # Find target if needed
        if self.target is None or self.target.is_dead:
            self.target = self.find_target(enemies)

        if self.target is None:
            return (None, 0)

        distance = self.get_distance_to(self.target)

        # Ranged unit behavior: kite (move back while reloading, attack when ready)
        if self.is_ranged():
            if self.attack_cooldown <= 0 and distance <= self.attack_range:
                # Ready to fire and in range - attack
                damage = self.get_damage_against(self.target)
                self.attack_cooldown = self.reload_time
                return (self.target, damage)
            elif self.attack_cooldown > 0:
                # Reloading - move backward (kite)
                self.position -= team_direction * self.speed * dt
            elif distance > self.attack_range:
                # Need to get in range - move toward enemy
                self.position += team_direction * self.speed * dt
            return (None, 0)
        else:
            # Melee unit behavior: close distance and attack
            melee_range = 0.5  # Melee range
            if distance <= melee_range:
                # In melee range - attack if ready
                if self.attack_cooldown <= 0:
                    damage = self.get_damage_against(self.target)
                    self.attack_cooldown = self.reload_time
                    return (self.target, damage)
            else:
                # Move toward target
                self.position += team_direction * self.speed * dt
            return (None, 0)


@dataclass
class UnitTemplate:
    """Template for creating units."""

    id: int
    name: str
    civ: str
    hp: int
    attack: int
    melee_armor: int
    pierce_armor: int
    reload_time: float
    attacks: dict
    armors: dict
    cost: int
    unit_slug: str
    age_id: int
    attack_range: float = 0.0  # 0 = melee
    speed: float = 1.0  # movement speed

    def create_unit(self, position: float = 0.0) -> Unit:
        """Create a new unit instance from this template."""
        return Unit(
            id=self.id,
            name=self.name,
            civ=self.civ,
            max_hp=self.hp,
            current_hp=float(self.hp),
            attack=self.attack,
            melee_armor=self.melee_armor,
            pierce_armor=self.pierce_armor,
            reload_time=self.reload_time,
            attacks=self.attacks.copy(),
            armors=self.armors.copy(),
            cost=self.cost,
            attack_range=self.attack_range,
            speed=self.speed,
            position=position,
        )


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_all_unit_templates() -> list[UnitTemplate]:
    """Load all available unit templates from database.

    Deduplicates by (civ, slug) - keeps only one entry per unit type per civ.
    When duplicates exist (same unit in multiple ages), keeps the one with highest age_id.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Order by age_id DESC so we see highest age first for each (civ, slug) pair
    cursor.execute("""
        SELECT us.id, us.unit_name, c.name as civ_name, us.hp, us.attack,
               us.melee_armor, us.pierce_armor, us.attack_speed,
               us.attack_range, us.movement_speed,
               us.attacks_json, us.armors_json,
               us.cost_food, us.cost_wood, us.cost_gold,
               u.slug, u.age_id, u.unit_type
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE us.has_unit = 1
        AND us.hp IS NOT NULL AND us.hp > 0
        ORDER BY u.age_id DESC, u.slug, c.name
    """)

    # Use dict to deduplicate by (civ, slug) - first seen wins (highest age due to ORDER BY)
    seen = {}
    templates = []

    for row in cursor.fetchall():
        key = (row["civ_name"], row["slug"])
        if key in seen:
            # Skip duplicate - we already have the higher age version
            continue
        seen[key] = True

        attacks = json.loads(row["attacks_json"]) if row["attacks_json"] else {}
        armors = json.loads(row["armors_json"]) if row["armors_json"] else {}
        attacks = {int(k): v for k, v in attacks.items()}
        armors = {int(k): v for k, v in armors.items()}

        attack_speed = row["attack_speed"] or 0.5
        reload_time = 1.0 / attack_speed if attack_speed > 0 else 2.0

        cost = (
            (row["cost_food"] or 0) + (row["cost_wood"] or 0) + (row["cost_gold"] or 0)
        )
        if cost == 0:
            cost = 100  # Default cost if missing

        # Get attack range (0 = melee) and movement speed
        attack_range = row["attack_range"] or 0.0
        movement_speed = row["movement_speed"] or 1.0

        templates.append(
            UnitTemplate(
                id=row["id"],
                name=row["unit_name"],
                civ=row["civ_name"],
                hp=row["hp"],
                attack=row["attack"],
                melee_armor=row["melee_armor"],
                pierce_armor=row["pierce_armor"],
                reload_time=reload_time,
                attacks=attacks,
                armors=armors,
                cost=cost,
                unit_slug=row["slug"],
                age_id=row["age_id"],
                attack_range=attack_range,
                speed=movement_speed,
            )
        )

    conn.close()
    return templates


def simulate_army_battle(
    team1_template: UnitTemplate,
    team2_template: UnitTemplate,
    resources: int,
    verbose: bool = False,
) -> dict:
    """
    Simulate a battle between two armies.

    Args:
        team1_template: Unit template for team 1
        team2_template: Unit template for team 2
        resources: Resource budget per team
        verbose: Print detailed output

    Returns:
        dict with battle results
    """
    # Calculate army sizes based on resource budget
    # No artificial cap - let resources determine army size
    team1_count = max(1, resources // team1_template.cost)
    team2_count = max(1, resources // team2_template.cost)

    # Create armies with initial positions
    # Team 1 starts at position 0 (left side), Team 2 at position 100 (right side)
    # Units are spread out slightly within each team
    team1 = [team1_template.create_unit(position=i * 0.5) for i in range(team1_count)]
    team2 = [
        team2_template.create_unit(position=100 - i * 0.5) for i in range(team2_count)
    ]

    if verbose:
        print(
            f"  {team1_template.civ} {team1_template.name} x{team1_count} vs "
            f"{team2_template.civ} {team2_template.name} x{team2_count}"
        )

    # Run simulation
    dt = 0.05  # 50ms time step
    time = 0.0
    max_time = 300.0  # 5 minute timeout

    while time < max_time:
        # Check for winner
        team1_alive = [u for u in team1 if not u.is_dead]
        team2_alive = [u for u in team2 if not u.is_dead]

        if len(team1_alive) == 0 or len(team2_alive) == 0:
            break

        # Collect all attacks first (simultaneous combat)
        pending_damage = []  # List of (target, damage) tuples

        # Team 1 moves right (direction=1), Team 2 moves left (direction=-1)
        for unit in team1_alive:
            target, damage = unit.update(dt, team2, team_direction=1)
            if target is not None:
                pending_damage.append((target, damage))

        for unit in team2_alive:
            target, damage = unit.update(dt, team1, team_direction=-1)
            if target is not None:
                pending_damage.append((target, damage))

        # Apply all damage simultaneously
        for target, damage in pending_damage:
            target.current_hp -= damage
            if target.current_hp <= 0:
                target.is_dead = True

        time += dt

    # Calculate results
    team1_remaining = len([u for u in team1 if not u.is_dead])
    team2_remaining = len([u for u in team2 if not u.is_dead])
    team1_hp_left = sum(u.current_hp for u in team1 if not u.is_dead)
    team2_hp_left = sum(u.current_hp for u in team2 if not u.is_dead)

    # Calculate starting HP for percentage comparison
    team1_start_hp = team1_count * team1_template.hp
    team2_start_hp = team2_count * team2_template.hp

    team1_res_spent = team1_count * team1_template.cost
    team2_res_spent = team2_count * team2_template.cost
    team1_res_lost = (team1_count - team1_remaining) * team1_template.cost
    team2_res_lost = (team2_count - team2_remaining) * team2_template.cost

    # Determine winner
    # If winner has less than 5% HP remaining, consider it a draw (very close battle)
    team1_hp_pct = team1_hp_left / team1_start_hp if team1_start_hp > 0 else 0
    team2_hp_pct = team2_hp_left / team2_start_hp if team2_start_hp > 0 else 0

    if team1_remaining > 0 and team2_remaining == 0:
        # Team 1 won, but check if it's a close battle
        if team1_hp_pct < 0.05:
            winner = 0  # Draw - pyrrhic victory
        else:
            winner = 1
    elif team2_remaining > 0 and team1_remaining == 0:
        # Team 2 won, but check if it's a close battle
        if team2_hp_pct < 0.05:
            winner = 0  # Draw - pyrrhic victory
        else:
            winner = 2
    elif team1_remaining > team2_remaining:
        winner = 1
    elif team2_remaining > team1_remaining:
        winner = 2
    elif team1_hp_left > team2_hp_left:
        winner = 1
    elif team2_hp_left > team1_hp_left:
        winner = 2
    else:
        winner = 0  # Draw

    return {
        "team1_civ": team1_template.civ,
        "team1_unit": team1_template.name,
        "team1_slug": team1_template.unit_slug,
        "team1_count": team1_count,
        "team1_remaining": team1_remaining,
        "team1_hp_left": int(team1_hp_left),
        "team1_res_spent": team1_res_spent,
        "team1_res_lost": team1_res_lost,
        "team2_civ": team2_template.civ,
        "team2_unit": team2_template.name,
        "team2_slug": team2_template.unit_slug,
        "team2_count": team2_count,
        "team2_remaining": team2_remaining,
        "team2_hp_left": int(team2_hp_left),
        "team2_res_spent": team2_res_spent,
        "team2_res_lost": team2_res_lost,
        "winner": winner,
        "battle_time": time,
    }


def run_all_simulations(
    resources: int, output_file: Optional[str] = None, verbose: bool = False
):
    """Run simulations for all unit matchups."""
    print(f"AoE2 Army Combat Simulator")
    print(f"Resources per team: {resources}")
    print("=" * 70)

    templates = load_all_unit_templates()
    print(f"Loaded {len(templates)} unit/civ combinations")

    # Group by unit slug for same-unit comparisons
    units_by_slug = {}
    for t in templates:
        if t.unit_slug not in units_by_slug:
            units_by_slug[t.unit_slug] = []
        units_by_slug[t.unit_slug].append(t)

    print(f"Found {len(units_by_slug)} distinct unit types")

    all_results = []

    # Run simulations within each unit type (same unit, different civs)
    print("\n" + "=" * 70)
    print("SAME-UNIT MATCHUPS (comparing civ bonuses)")
    print("=" * 70)

    NUM_RUNS = 5  # Run each matchup 5 times

    for unit_slug, civs in sorted(units_by_slug.items()):
        if len(civs) < 2:
            continue

        print(f"\n{civs[0].name} ({len(civs)} civs):")

        for i, t1 in enumerate(civs):
            for t2 in civs[i + 1 :]:
                # Run simulation NUM_RUNS times
                team1_wins = 0
                team2_wins = 0
                draws = 0

                for run in range(NUM_RUNS):
                    result = simulate_army_battle(t1, t2, resources, verbose=verbose)
                    if result["winner"] == 1:
                        team1_wins += 1
                    elif result["winner"] == 2:
                        team2_wins += 1
                    else:
                        draws += 1

                # Only count as win if ALL runs were won by the same side
                # Otherwise it's a draw (civs are considered equal)
                if team1_wins == NUM_RUNS:
                    final_winner = 1
                elif team2_wins == NUM_RUNS:
                    final_winner = 2
                else:
                    final_winner = 0  # Draw - civs are equal

                # Create aggregated result
                final_result = {
                    "team1_civ": t1.civ,
                    "team1_unit": t1.name,
                    "team1_slug": t1.unit_slug,
                    "team2_civ": t2.civ,
                    "team2_unit": t2.name,
                    "team2_slug": t2.unit_slug,
                    "winner": final_winner,
                    "team1_wins": team1_wins,
                    "team2_wins": team2_wins,
                    "draws": draws,
                }
                all_results.append(final_result)

    # Calculate win rates for each civ/unit combination
    print("\n" + "=" * 70)
    print("COMBAT EFFECTIVENESS BY UNIT")
    print("=" * 70)

    # Aggregate results by civ+unit
    stats = {}
    for r in all_results:
        key1 = (r["team1_civ"], r["team1_unit"], r["team1_slug"])
        key2 = (r["team2_civ"], r["team2_unit"], r["team2_slug"])

        if key1 not in stats:
            stats[key1] = {"wins": 0, "losses": 0, "draws": 0}
        if key2 not in stats:
            stats[key2] = {"wins": 0, "losses": 0, "draws": 0}

        if r["winner"] == 1:
            stats[key1]["wins"] += 1
            stats[key2]["losses"] += 1
        elif r["winner"] == 2:
            stats[key1]["losses"] += 1
            stats[key2]["wins"] += 1
        else:
            stats[key1]["draws"] += 1
            stats[key2]["draws"] += 1

    # Print results grouped by unit type
    results_by_unit = {}
    for (civ, unit, slug), s in stats.items():
        if slug not in results_by_unit:
            results_by_unit[slug] = []

        total = s["wins"] + s["losses"] + s["draws"]
        if total > 0:
            win_rate = (s["wins"] + 0.5 * s["draws"]) / total
        else:
            win_rate = 0.5

        results_by_unit[slug].append(
            {
                "civ": civ,
                "unit": unit,
                "wins": s["wins"],
                "losses": s["losses"],
                "draws": s["draws"],
                "win_rate": win_rate,
            }
        )

    # Sort each unit type by win rate and print
    for slug in sorted(results_by_unit.keys()):
        unit_results = sorted(results_by_unit[slug], key=lambda x: -x["win_rate"])
        if len(unit_results) < 2:
            continue

        print(f"\n{unit_results[0]['unit']}:")
        print(f"  {'Civilization':<20} {'W':>3} {'D':>3} {'L':>3} {'Win%':>7}")
        print(f"  {'-' * 40}")

        for r in unit_results:
            print(
                f"  {r['civ']:<20} {r['wins']:>3} {r['draws']:>3} {r['losses']:>3} "
                f"{r['win_rate'] * 100:>6.1f}%"
            )

    # Write CSV output if requested
    if output_file:
        print(f"\nWriting results to {output_file}...")
        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Unit",
                    "Civilization",
                    "Wins",
                    "Draws",
                    "Losses",
                    "Win Rate",
                ]
            )

            for slug in sorted(results_by_unit.keys()):
                unit_results = sorted(
                    results_by_unit[slug], key=lambda x: -x["win_rate"]
                )
                for r in unit_results:
                    writer.writerow(
                        [
                            r["unit"],
                            r["civ"],
                            r["wins"],
                            r["draws"],
                            r["losses"],
                            f"{r['win_rate']:.3f}",
                        ]
                    )

        print(f"Wrote {sum(len(v) for v in results_by_unit.values())} rows")

    # Also write detailed matchup results
    if output_file:
        matchup_file = output_file.replace(".csv", "_matchups.csv")
        print(f"Writing matchup details to {matchup_file}...")
        with open(matchup_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Team1_Civ",
                    "Team1_Unit",
                    "Team2_Civ",
                    "Team2_Unit",
                    "Team1_Wins",
                    "Team2_Wins",
                    "Draws",
                    "Final_Winner",
                ]
            )
            for r in all_results:
                winner_str = f"Team{r['winner']}" if r["winner"] > 0 else "Draw"
                writer.writerow(
                    [
                        r["team1_civ"],
                        r["team1_unit"],
                        r["team2_civ"],
                        r["team2_unit"],
                        r["team1_wins"],
                        r["team2_wins"],
                        r["draws"],
                        winner_str,
                    ]
                )
        print(f"Wrote {len(all_results)} matchup records")

    print(f"\n{'=' * 70}")
    print(f"SIMULATION COMPLETE")
    print(f"Total matchups: {len(all_results)}")
    print(f"{'=' * 70}")

    return all_results


def update_database_with_results(all_results: list, templates: list[UnitTemplate]):
    """Update the database with combat simulation results."""
    print("\nUpdating database with combat results...")

    conn = get_db()
    cursor = conn.cursor()

    # Reset all combat stats
    cursor.execute("""
        UPDATE unit_stats
        SET combat_wins = 0, combat_losses = 0, combat_draws = 0, combat_score = 0
    """)

    # Build a lookup from (civ, unit_name) to template id
    template_lookup = {(t.civ, t.name): t.id for t in templates}

    # Aggregate results by unit_stats.id
    stats = {}
    for r in all_results:
        key1 = (r["team1_civ"], r["team1_unit"])
        key2 = (r["team2_civ"], r["team2_unit"])

        id1 = template_lookup.get(key1)
        id2 = template_lookup.get(key2)

        if id1 is None or id2 is None:
            continue

        if id1 not in stats:
            stats[id1] = {"wins": 0, "losses": 0, "draws": 0}
        if id2 not in stats:
            stats[id2] = {"wins": 0, "losses": 0, "draws": 0}

        if r["winner"] == 1:
            stats[id1]["wins"] += 1
            stats[id2]["losses"] += 1
        elif r["winner"] == 2:
            stats[id1]["losses"] += 1
            stats[id2]["wins"] += 1
        else:
            stats[id1]["draws"] += 1
            stats[id2]["draws"] += 1

    # Update each unit's stats
    for unit_id, s in stats.items():
        total = s["wins"] + s["losses"] + s["draws"]
        if total > 0:
            # Score = (wins + 0.5 * draws) / total
            score = (s["wins"] + 0.5 * s["draws"]) / total
        else:
            score = 0.5

        cursor.execute(
            """
            UPDATE unit_stats
            SET combat_wins = ?, combat_losses = ?, combat_draws = ?, combat_score = ?
            WHERE id = ?
        """,
            (s["wins"], s["losses"], s["draws"], score, unit_id),
        )

    conn.commit()

    # Now normalize scores within each unit type
    # Get distinct unit slugs that have combat data
    cursor.execute("""
        SELECT DISTINCT u.slug, us.unit_name
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        WHERE (us.combat_wins + us.combat_losses + us.combat_draws) > 0
    """)
    unit_types = cursor.fetchall()

    for row in unit_types:
        unit_slug = row["slug"]

        # Get all scores for this unit type
        cursor.execute(
            """
            SELECT us.id, us.combat_score
            FROM unit_stats us
            JOIN units u ON us.unit_id = u.id
            WHERE u.slug = ? AND (us.combat_wins + us.combat_losses + us.combat_draws) > 0
        """,
            (unit_slug,),
        )
        scores = cursor.fetchall()

        if len(scores) < 2:
            continue

        # Find median score as baseline (represents "generic" performance)
        all_scores = sorted([r["combat_score"] for r in scores])
        mid = len(all_scores) // 2
        if len(all_scores) % 2 == 0:
            baseline = (all_scores[mid - 1] + all_scores[mid]) / 2
        else:
            baseline = all_scores[mid]

        # Normalize so baseline = 1.0
        if baseline > 0:
            for r in scores:
                normalized = r["combat_score"] / baseline
                cursor.execute(
                    "UPDATE unit_stats SET combat_score = ? WHERE id = ?",
                    (normalized, r["id"]),
                )

    conn.commit()
    conn.close()

    print(f"Updated {len(stats)} unit records in database")


def main():
    parser = argparse.ArgumentParser(description="AoE2 Army Combat Simulator")
    parser.add_argument(
        "--resources",
        "-r",
        type=int,
        default=1000,
        help="Resource budget per team (default: 1000)",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output CSV file for results"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Update database with combat results",
    )
    args = parser.parse_args()

    results = run_all_simulations(args.resources, args.output, args.verbose)

    if args.update_db:
        templates = load_all_unit_templates()
        update_database_with_results(results, templates)


if __name__ == "__main__":
    main()
