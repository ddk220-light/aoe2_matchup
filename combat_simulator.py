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


def simulate_combat(
    unit1: CombatUnit, unit2: CombatUnit, verbose: bool = False
) -> dict:
    """
    Simulate combat between two units.

    Returns dict with:
    - winner_id: unit_stats.id of winning unit (or None for draw)
    - winner_hp_remaining: HP left on winner
    - time: total combat time in seconds
    - hits_unit1: number of hits by unit1
    - hits_unit2: number of hits by unit2
    """
    # Reset HP
    u1_hp = float(unit1.hp)
    u2_hp = float(unit2.hp)

    # Calculate damage per hit
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

    # Simulate combat tick by tick
    time = 0.0
    u1_next_attack = 0.0
    u2_next_attack = 0.0
    u1_hits = 0
    u2_hits = 0

    dt = 0.001  # 1ms time step

    while u1_hp > 0 and u2_hp > 0:
        # Check if unit1 attacks
        if time >= u1_next_attack and u2_hp > 0:
            u2_hp -= u1_damage
            u1_hits += 1
            u1_next_attack = time + unit1.reload_time

        # Check if unit2 attacks
        if time >= u2_next_attack and u1_hp > 0 and u2_hp > 0:
            u1_hp -= u2_damage
            u2_hits += 1
            u2_next_attack = time + unit2.reload_time

        time += dt

        # Safety check
        if time > 300:
            break

    # Determine winner
    if u1_hp > 0 and u2_hp <= 0:
        winner_id = unit1.id
        winner_hp = int(u1_hp)
    elif u2_hp > 0 and u1_hp <= 0:
        winner_id = unit2.id
        winner_hp = int(u2_hp)
    else:
        # Draw (both died at same time or timeout)
        winner_id = None
        winner_hp = 0

    if verbose:
        if winner_id == unit1.id:
            print(
                f"\n--- WINNER: {unit1.civ} {unit1.name} ({winner_hp} HP remaining) ---"
            )
        elif winner_id == unit2.id:
            print(
                f"\n--- WINNER: {unit2.civ} {unit2.name} ({winner_hp} HP remaining) ---"
            )
        else:
            print(f"\n--- DRAW ---")

    return {
        "winner_id": winner_id,
        "winner_hp_remaining": winner_hp,
        "time": round(time, 3),
        "hits_unit1": u1_hits,
        "hits_unit2": u2_hits,
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
        ORDER BY u.slug, c.name
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

        # Group units by unit type (slug) for intra-unit comparisons
        units_by_slug = {}
        for unit in units:
            if unit.unit_slug not in units_by_slug:
                units_by_slug[unit.unit_slug] = []
            units_by_slug[unit.unit_slug].append(unit)

        # Run simulations within each unit type
        results = []
        for slug, slug_units in units_by_slug.items():
            if len(slug_units) < 2:
                continue

            print(
                f"  Simulating {slug} ({len(slug_units)} civs)...", end=" ", flush=True
            )
            matchup_count = 0

            for i, u1 in enumerate(slug_units):
                for u2 in slug_units[i + 1 :]:
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
                            result["time"],
                            result["hits_unit1"],
                            result["hits_unit2"],
                        ),
                    )

                    # Update win/loss counts
                    if result["winner_id"] == u1.id:
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
                    else:
                        cursor.execute(
                            "UPDATE unit_stats SET combat_draws = combat_draws + 1 WHERE id = ?",
                            (u1.id,),
                        )
                        cursor.execute(
                            "UPDATE unit_stats SET combat_draws = combat_draws + 1 WHERE id = ?",
                            (u2.id,),
                        )

            print(f"{matchup_count} matchups")

        total_results.extend(results)
        conn.commit()

    # Calculate combat score (win rate)
    cursor.execute("""
        UPDATE unit_stats
        SET combat_score = CASE
            WHEN (combat_wins + combat_losses + combat_draws) > 0
            THEN CAST(combat_wins AS REAL) / (combat_wins + combat_losses + combat_draws) * 100
            ELSE 0
        END
    """)
    conn.commit()

    print(f"\n{'=' * 60}")
    print(f"SIMULATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total matchups simulated: {len(total_results)}")

    # Print summary by age
    for age_id, age_name in age_names.items():
        cursor.execute(
            """
            SELECT u.slug, c.name, us.unit_name, us.combat_wins, us.combat_losses, us.combat_score
            FROM unit_stats us
            JOIN civilizations c ON us.civ_id = c.id
            JOIN units u ON us.unit_id = u.id
            WHERE u.age_id = ? AND us.has_unit = 1 AND u.unit_type = 'standard'
            AND (us.combat_wins + us.combat_losses) > 0
            ORDER BY us.combat_score DESC
            LIMIT 10
        """,
            (age_id,),
        )

        print(f"\n{age_name} Age - Top 10 Units by Win Rate:")
        print("-" * 50)
        for row in cursor.fetchall():
            total = row["combat_wins"] + row["combat_losses"]
            print(
                f"  {row['name']:15} {row['unit_name']:20} {row['combat_wins']:2}W-{row['combat_losses']:2}L ({row['combat_score']:.1f}%)"
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
