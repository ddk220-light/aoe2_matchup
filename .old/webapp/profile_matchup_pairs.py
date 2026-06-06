"""
Profile a real-sim civ-vs-civ matchup at the same fidelity that
generate_matchup_db_real.py uses (30v30 + 3k-resource for every power-unit
cross-product), but with per-sim timing instrumentation.

Reports:
- Total wall time per civ pair
- Slowest individual sims (game-time + wall-time + count)
- Distribution of game-time durations (so we can see how often the 60s cap fires)

Usage:
    cd webapp && python3 profile_matchup_pairs.py
"""

import os
import sqlite3
import time

from best_units import load_civ_power_units, _load_combat_unit, _calc_weighted_cost
from simulation_real import (
    BattleSimulation, DT, MAX_BATTLE_SECONDS, deterministic_seed,
)
import random

# Late-alphabet civ pairs that are still "remaining" in the running batch.
# Picked to exercise heavy unit pools (siege, unique units, mixed comp).
PAIRS_TO_PROFILE = [
    ("Sicilians", "Tatars"),
    ("Spanish", "Wei"),
    ("Vikings", "Wu"),
    ("Teutons", "Vietnamese"),
    ("Turks", "Slavs"),
]


def collect_units(power_units):
    units = []
    for col in ("cavalry", "ranged", "infantry"):
        for line, entries in power_units.get(col, {}).items():
            for e in entries or []:
                units.append(e)
    return units


def profile_pair(civ_a, civ_b, power_data, age="imperial"):
    db_age = "Imperial" if age == "imperial" else "Castle"
    pu_a = power_data[civ_a].get(age, {}).get("power_units", {})
    pu_b = power_data[civ_b].get(age, {}).get("power_units", {})
    units_a = collect_units(pu_a)
    units_b = collect_units(pu_b)

    # Load combat units
    cu_cache = {}
    for civ, units in ((civ_a, units_a), (civ_b, units_b)):
        for u in units:
            key = (civ, u["unit_slug"])
            if key not in cu_cache:
                cu = _load_combat_unit(civ, u["unit_slug"], db_age)
                if cu:
                    cu_cache[key] = cu

    def _calc_count(unit, fixed_count, cost):
        if fixed_count:
            pop = unit.get("pop_space") or 1.0
            return max(1, int(fixed_count / pop))
        return max(1, int(3000 / cost))

    sim_records = []   # (label, scenario, c1, c2, game_time_s, wall_ms, exit_reason)
    total_start = time.perf_counter()

    for u_a in units_a:
        cu_a = cu_cache.get((civ_a, u_a["unit_slug"]))
        if not cu_a:
            continue
        cost_a = _calc_weighted_cost(cu_a["cost_food"], cu_a["cost_wood"], cu_a["cost_gold"])
        for u_b in units_b:
            cu_b = cu_cache.get((civ_b, u_b["unit_slug"]))
            if not cu_b:
                continue
            cost_b = _calc_weighted_cost(cu_b["cost_food"], cu_b["cost_wood"], cu_b["cost_gold"])

            for scenario, fixed_count in (("pop", 30), ("eco", None)):
                c1 = _calc_count(cu_a, fixed_count, cost_a)
                c2 = _calc_count(cu_b, fixed_count, cost_b)
                random.seed(deterministic_seed(u_a["unit_slug"], u_b["unit_slug"], scenario))
                sim = BattleSimulation()
                sim.setup_team(1, cu_a, c1)
                sim.setup_team(2, cu_b, c2)
                t0 = time.perf_counter()
                ticks = sim.run()
                wall_ms = (time.perf_counter() - t0) * 1000
                game_time = ticks * DT
                # Determine exit reason
                if game_time >= MAX_BATTLE_SECONDS - DT:
                    reason = "60s_cap"
                elif sim.alive_count(1) == 0 or sim.alive_count(2) == 0:
                    reason = "natural"
                else:
                    reason = "decisive_lead"
                sim_records.append((
                    f"{u_a['unit_name']} vs {u_b['unit_name']}",
                    scenario, c1, c2, game_time, wall_ms, reason
                ))

    total_wall = time.perf_counter() - total_start
    return total_wall, sim_records


def main():
    print("Loading power data...")
    power_data = load_civ_power_units()

    for civ_a, civ_b in PAIRS_TO_PROFILE:
        print(f"\n=== {civ_a} vs {civ_b} ===")
        total_wall, records = profile_pair(civ_a, civ_b, power_data)
        print(f"Total: {total_wall:.1f}s wall, {len(records)} sims")

        # Distribution of game-time + exit reasons
        natural = sum(1 for r in records if r[6] == "natural")
        decisive = sum(1 for r in records if r[6] == "decisive_lead")
        capped = sum(1 for r in records if r[6] == "60s_cap")
        print(f"  Exit: natural={natural}  decisive_lead={decisive}  60s_cap={capped}")

        avg_gt = sum(r[4] for r in records) / len(records) if records else 0
        max_gt = max((r[4] for r in records), default=0)
        avg_wall = sum(r[5] for r in records) / len(records) if records else 0
        print(f"  Game time: avg={avg_gt:.1f}s, max={max_gt:.1f}s")
        print(f"  Wall time: avg={avg_wall:.0f}ms")

        # Top 5 slowest by wall time
        slowest = sorted(records, key=lambda r: -r[5])[:5]
        print(f"  Slowest sims by wall time:")
        for label, sc, c1, c2, gt, wms, reason in slowest:
            print(f"    {wms:>6.0f} ms  game={gt:>4.1f}s  {sc} {c1}v{c2:<3}  [{reason:<14}]  {label}")


if __name__ == "__main__":
    main()
