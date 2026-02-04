#!/usr/bin/env python3
"""
AoE2 Combat Simulator

Simulates combat between two units, taking into account:
- Base attack and armor values
- Bonus damage against armor classes
- Attack speed (reload time)
- Hit points

Usage:
    python combat_simulator.py [--run-all]
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "webapp" / "aoe2_units.db"


@dataclass
class CombatUnit:
    """A unit in combat with all relevant stats."""

    id: int  # unit_stats.id in database
    name: str
    civ: str
    hp: int
    current_hp: float
    attack: int
    melee_armor: int
    pierce_armor: int
    reload_time: float  # seconds between attacks
    attacks: dict  # {armor_class: bonus_damage}
    armors: dict  # {armor_class: armor_value}
    age_id: int
    unit_slug: str

    def get_damage_against(self, target: "CombatUnit") -> int:
        """
        Calculate damage dealt to a target unit.

        Damage formula:
        damage = max(1, base_attack + sum(bonus_damage for matching armor classes) - target_armor)
        """
        # Base melee attack (class 4)
        base_damage = self.attacks.get(4, self.attack)

        # Calculate bonus damage against target's armor classes
        bonus_damage = 0
        for armor_class, armor_value in target.armors.items():
            if armor_class in self.attacks and armor_class != 4:  # Skip base melee
                attack_bonus = self.attacks[armor_class]
                if attack_bonus > 0:
                    # Bonus damage is reduced by armor in that class
                    effective_bonus = max(0, attack_bonus - armor_value)
                    bonus_damage += effective_bonus

        # Target's melee armor (class 4)
        target_armor = target.armors.get(4, target.melee_armor)

        # Total damage (minimum 1)
        total_damage = max(1, base_damage + bonus_damage - target_armor)

        return total_damage


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_unit_by_id(unit_stats_id: int) -> Optional[CombatUnit]:
    """Load a unit from the database by unit_stats.id."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT us.*, c.name as civ_name, u.display_name, u.slug, u.age_id
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE us.id = ? AND us.has_unit = 1
    """,
        (unit_stats_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return _row_to_combat_unit(row)


def load_unit(civ_name: str, unit_slug: str) -> Optional[CombatUnit]:
    """Load a unit from the database."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT us.*, c.name as civ_name, u.display_name, u.slug, u.age_id
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE c.name = ? AND u.slug = ? AND us.has_unit = 1
    """,
        (civ_name, unit_slug),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return _row_to_combat_unit(row)


def _row_to_combat_unit(row) -> CombatUnit:
    """Convert a database row to a CombatUnit."""
    # Parse attacks and armors JSON
    attacks = json.loads(row["attacks_json"]) if row["attacks_json"] else {}
    armors = json.loads(row["armors_json"]) if row["armors_json"] else {}

    # Convert string keys to integers
    attacks = {int(k): v for k, v in attacks.items()}
    armors = {int(k): v for k, v in armors.items()}

    # Calculate reload time from attack speed (attacks per second)
    attack_speed = row["attack_speed"] or 0.5
    reload_time = 1.0 / attack_speed if attack_speed > 0 else 2.0

    return CombatUnit(
        id=row["id"],
        name=row["unit_name"],
        civ=row["civ_name"],
        hp=row["hp"],
        current_hp=float(row["hp"]),
        attack=row["attack"],
        melee_armor=row["melee_armor"],
        pierce_armor=row["pierce_armor"],
        reload_time=reload_time,
        attacks=attacks,
        armors=armors,
        age_id=row["age_id"],
        unit_slug=row["slug"],
    )


def simulate_combat_one_direction(
    unit1: CombatUnit, unit2: CombatUnit, first_attacker: int = 1
) -> dict:
    """
    Simulate combat between two units with a specific first attacker.

    Args:
        unit1, unit2: The two units fighting
        first_attacker: 1 if unit1 attacks first, 2 if unit2 attacks first

    Returns dict with:
    - winner_id: unit_stats.id of winning unit (or None for draw)
    - winner_hp_remaining: HP left on winner
    """
    # Reset HP
    u1_hp = float(unit1.hp)
    u2_hp = float(unit2.hp)

    # Calculate damage per hit
    u1_damage = unit1.get_damage_against(unit2)
    u2_damage = unit2.get_damage_against(unit1)

    # Simulate combat tick by tick
    time = 0.0
    # First attacker starts at time 0, second attacker starts after a tiny delay
    if first_attacker == 1:
        u1_next_attack = 0.0
        u2_next_attack = 0.0001  # Tiny delay so unit1 hits first
    else:
        u1_next_attack = 0.0001  # Tiny delay so unit2 hits first
        u2_next_attack = 0.0

    dt = 0.001  # 1ms time step

    while u1_hp > 0 and u2_hp > 0:
        # Check if unit1 attacks
        if time >= u1_next_attack and u2_hp > 0:
            u2_hp -= u1_damage
            u1_next_attack = time + unit1.reload_time

        # Check if unit2 attacks
        if time >= u2_next_attack and u1_hp > 0 and u2_hp > 0:
            u1_hp -= u2_damage
            u2_next_attack = time + unit2.reload_time

        time += dt

        # Safety check
        if time > 300:
            break

    # Determine winner
    if u1_hp > 0 and u2_hp <= 0:
        return {"winner_id": unit1.id, "winner_hp_remaining": int(u1_hp)}
    elif u2_hp > 0 and u1_hp <= 0:
        return {"winner_id": unit2.id, "winner_hp_remaining": int(u2_hp)}
    else:
        return {"winner_id": None, "winner_hp_remaining": 0}


def simulate_combat(
    unit1: CombatUnit, unit2: CombatUnit, verbose: bool = False
) -> dict:
    """
    Simulate combat between two units, running both directions.

    Runs two simulations:
    1. Unit1 attacks first
    2. Unit2 attacks first

    If the same unit wins both times, they're the winner.
    If different units win depending on who starts, it's a draw.
    If units are identical (same stats), it's a draw.

    Returns dict with:
    - winner_id: unit_stats.id of winning unit (or None for draw)
    - is_draw: True if the result is a draw
    - unit1_id, unit2_id: IDs of the two units
    """
    # Calculate damage per hit for verbose output
    u1_damage = unit1.get_damage_against(unit2)
    u2_damage = unit2.get_damage_against(unit1)

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"COMBAT: {unit1.civ} {unit1.name} vs {unit2.civ} {unit2.name}")
        print(f"{'=' * 60}")
        print(f"\n{unit1.name} ({unit1.civ}):")
        print(
            f"  HP: {unit1.hp}, Attack: {unit1.attack}, Armor: {unit1.melee_armor}/{unit1.pierce_armor}"
        )
        print(f"  Reload time: {unit1.reload_time:.3f}s, Damage: {u1_damage}")
        print(f"\n{unit2.name} ({unit2.civ}):")
        print(
            f"  HP: {unit2.hp}, Attack: {unit2.attack}, Armor: {unit2.melee_armor}/{unit2.pierce_armor}"
        )
        print(f"  Reload time: {unit2.reload_time:.3f}s, Damage: {u2_damage}")

    # Run simulation both ways
    result1 = simulate_combat_one_direction(unit1, unit2, first_attacker=1)
    result2 = simulate_combat_one_direction(unit1, unit2, first_attacker=2)

    if verbose:
        print(f"\n  When {unit1.civ} attacks first: ", end="")
        if result1["winner_id"] == unit1.id:
            print(f"{unit1.civ} wins ({result1['winner_hp_remaining']} HP left)")
        elif result1["winner_id"] == unit2.id:
            print(f"{unit2.civ} wins ({result1['winner_hp_remaining']} HP left)")
        else:
            print("Draw")

        print(f"  When {unit2.civ} attacks first: ", end="")
        if result2["winner_id"] == unit1.id:
            print(f"{unit1.civ} wins ({result2['winner_hp_remaining']} HP left)")
        elif result2["winner_id"] == unit2.id:
            print(f"{unit2.civ} wins ({result2['winner_hp_remaining']} HP left)")
        else:
            print("Draw")

    # Determine final outcome
    # If same winner in both directions, that unit wins
    # Otherwise, it's a draw
    if (
        result1["winner_id"] == result2["winner_id"]
        and result1["winner_id"] is not None
    ):
        winner_id = result1["winner_id"]
        is_draw = False
        winner_hp = (
            result1["winner_hp_remaining"] + result2["winner_hp_remaining"]
        ) // 2
    else:
        # Different winners or both draws = draw
        winner_id = None
        is_draw = True
        winner_hp = 0

    if verbose:
        if is_draw:
            print(f"\n--- RESULT: DRAW ---")
        elif winner_id == unit1.id:
            print(f"\n--- RESULT: {unit1.civ} {unit1.name} WINS ---")
        else:
            print(f"\n--- RESULT: {unit2.civ} {unit2.name} WINS ---")

    return {
        "winner_id": winner_id,
        "winner_hp_remaining": winner_hp,
        "is_draw": is_draw,
        "unit1_id": unit1.id,
        "unit2_id": unit2.id,
    }


def get_all_units_for_age(age_id: int) -> list:
    """Get all unit_stats entries for a specific age."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT us.*, c.name as civ_name, u.display_name, u.slug, u.age_id, u.unit_type
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE u.age_id = ? AND us.has_unit = 1 AND u.unit_type = 'standard'
        AND us.hp IS NOT NULL AND us.hp > 0
        ORDER BY us.unit_name, c.name
    """,
        (age_id,),
    )

    units = []
    for row in cursor.fetchall():
        unit = _row_to_combat_unit(row)
        if unit:
            units.append(unit)

    conn.close()
    return units


def run_all_simulations():
    """Run combat simulations for all units and store results in database."""
    print("AoE2 Combat Simulator - Running All Simulations")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # Clear existing combat results
    cursor.execute("DELETE FROM combat_results")
    cursor.execute(
        "UPDATE unit_stats SET combat_wins = 0, combat_losses = 0, combat_draws = 0, combat_score = 0"
    )
    conn.commit()

    age_names = {2: "Feudal", 3: "Castle", 4: "Imperial"}
    total_results = []

    for age_id, age_name in age_names.items():
        print(f"\n{'=' * 60}")
        print(f"Processing {age_name} Age units...")
        print(f"{'=' * 60}")

        units = get_all_units_for_age(age_id)
        print(f"Found {len(units)} unit/civ combinations")

        if len(units) < 2:
            print("Not enough units to simulate")
            continue

        # Group units by actual unit name for intra-unit comparisons
        # This ensures Paladins are only compared to Paladins, not Cavaliers
        units_by_name = {}
        for unit in units:
            if unit.name not in units_by_name:
                units_by_name[unit.name] = []
            units_by_name[unit.name].append(unit)

        # Run simulations within each unit type
        results = []
        for unit_name, name_units in units_by_name.items():
            if len(name_units) < 2:
                continue

            print(
                f"  Simulating {unit_name} ({len(name_units)} civs)...",
                end=" ",
                flush=True,
            )
            matchup_count = 0

            for i, u1 in enumerate(name_units):
                for u2 in name_units[i + 1 :]:
                    result = simulate_combat(u1, u2)
                    results.append(result)
                    matchup_count += 1

                    # Store result in database
                    cursor.execute(
                        """
                        INSERT INTO combat_results
                        (unit_stats_id_1, unit_stats_id_2, winner_id, winner_hp_remaining,
                         combat_time, hits_by_unit1, hits_by_unit2)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            result["unit1_id"],
                            result["unit2_id"],
                            result["winner_id"],
                            result["winner_hp_remaining"],
                            0,  # combat_time no longer tracked
                            0,  # hits no longer tracked
                            0,
                        ),
                    )

                    # Update win/loss/draw counts
                    if result["is_draw"]:
                        cursor.execute(
                            "UPDATE unit_stats SET combat_draws = combat_draws + 1 WHERE id = ?",
                            (u1.id,),
                        )
                        cursor.execute(
                            "UPDATE unit_stats SET combat_draws = combat_draws + 1 WHERE id = ?",
                            (u2.id,),
                        )
                    elif result["winner_id"] == u1.id:
                        cursor.execute(
                            "UPDATE unit_stats SET combat_wins = combat_wins + 1 WHERE id = ?",
                            (u1.id,),
                        )
                        cursor.execute(
                            "UPDATE unit_stats SET combat_losses = combat_losses + 1 WHERE id = ?",
                            (u2.id,),
                        )
                    elif result["winner_id"] == u2.id:
                        cursor.execute(
                            "UPDATE unit_stats SET combat_wins = combat_wins + 1 WHERE id = ?",
                            (u2.id,),
                        )
                        cursor.execute(
                            "UPDATE unit_stats SET combat_losses = combat_losses + 1 WHERE id = ?",
                            (u1.id,),
                        )

            print(f"{matchup_count} matchups")

        total_results.extend(results)
        conn.commit()

    # Calculate raw combat score (wins count as 1, draws as 0.5, losses as 0)
    # Score = (wins + 0.5 * draws) / total_matches
    cursor.execute("""
        UPDATE unit_stats
        SET combat_score = CASE
            WHEN (combat_wins + combat_losses + combat_draws) > 0
            THEN (CAST(combat_wins AS REAL) + 0.5 * combat_draws) / (combat_wins + combat_losses + combat_draws)
            ELSE 0.5
        END
    """)
    conn.commit()

    # Normalize combat scores so generic civs (most common score) = 1.0
    # For each actual unit name, find the baseline and normalize
    for age_id in age_names.keys():
        # Get all distinct unit names for this age
        cursor.execute(
            """
            SELECT DISTINCT us.unit_name
            FROM unit_stats us
            JOIN units u ON us.unit_id = u.id
            WHERE u.age_id = ? AND u.unit_type = 'standard' AND us.has_unit = 1
            AND (us.combat_wins + us.combat_losses + us.combat_draws) > 0
        """,
            (age_id,),
        )
        unit_names = [row["unit_name"] for row in cursor.fetchall()]

        for unit_name in unit_names:
            # Get all scores for this actual unit
            cursor.execute(
                """
                SELECT us.id, us.combat_score, us.civ_bonuses
                FROM unit_stats us
                JOIN units u ON us.unit_id = u.id
                WHERE us.unit_name = ? AND u.age_id = ? AND us.has_unit = 1
                AND (us.combat_wins + us.combat_losses + us.combat_draws) > 0
            """,
                (unit_name, age_id),
            )
            scores = cursor.fetchall()

            if len(scores) < 2:
                # Not enough units to normalize, set to 1.0
                for row in scores:
                    cursor.execute(
                        "UPDATE unit_stats SET combat_score = 1.0 WHERE id = ?",
                        (row["id"],),
                    )
                continue

            # Find the baseline score (generic civs have no bonuses or '-')
            generic_scores = [
                row["combat_score"]
                for row in scores
                if not row["civ_bonuses"] or row["civ_bonuses"] == "-"
            ]

            if generic_scores:
                # Use median of generic civ scores as baseline (most representative)
                sorted_generic = sorted(generic_scores)
                mid = len(sorted_generic) // 2
                if len(sorted_generic) % 2 == 0:
                    baseline = (sorted_generic[mid - 1] + sorted_generic[mid]) / 2
                else:
                    baseline = sorted_generic[mid]
            else:
                # Fallback: use median of all scores
                all_scores = sorted([row["combat_score"] for row in scores])
                baseline = all_scores[len(all_scores) // 2]

            # Normalize all scores for this unit type (baseline = 1.0)
            if baseline > 0:
                for row in scores:
                    normalized_score = row["combat_score"] / baseline
                    cursor.execute(
                        "UPDATE unit_stats SET combat_score = ? WHERE id = ?",
                        (normalized_score, row["id"]),
                    )
            else:
                # If baseline is 0, set all to 1.0
                for row in scores:
                    cursor.execute(
                        "UPDATE unit_stats SET combat_score = 1.0 WHERE id = ?",
                        (row["id"],),
                    )

    conn.commit()

    print(f"\n{'=' * 60}")
    print(f"SIMULATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total matchups simulated: {len(total_results)}")

    # Print summary by age
    for age_id, age_name in age_names.items():
        cursor.execute(
            """
            SELECT u.slug, c.name, us.unit_name, us.combat_wins, us.combat_losses, us.combat_draws, us.combat_score
            FROM unit_stats us
            JOIN civilizations c ON us.civ_id = c.id
            JOIN units u ON us.unit_id = u.id
            WHERE u.age_id = ? AND us.has_unit = 1 AND u.unit_type = 'standard'
            AND (us.combat_wins + us.combat_losses + us.combat_draws) > 0
            ORDER BY us.combat_score DESC
            LIMIT 10
        """,
            (age_id,),
        )

        print(f"\n{age_name} Age - Top 10 Units by Combat Effectiveness:")
        print("-" * 60)
        for row in cursor.fetchall():
            print(
                f"  {row['name']:15} {row['unit_name']:20} {row['combat_wins']:2}W-{row['combat_draws']:2}D-{row['combat_losses']:2}L (Eff: {row['combat_score']:.2f})"
            )

    conn.close()
    return total_results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="AoE2 Combat Simulator")
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all simulations and store in database",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.run_all:
        run_all_simulations()
    else:
        # Example combat
        print("AoE2 Combat Simulator")
        print("=====================")
        print("\nExample: Franks vs Teutons Paladin")

        franks = load_unit("Franks", "paladin")
        teutons = load_unit("Teutons", "paladin")

        if franks and teutons:
            simulate_combat(franks, teutons, verbose=True)

        print("\nRun with --run-all to simulate all unit matchups")


if __name__ == "__main__":
    main()
