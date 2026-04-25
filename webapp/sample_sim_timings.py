"""
Sample real-sim battles and log:
- Game-time at natural winner
- HP-delta progression every 15s game time

Used to pick a meaningful early-exit threshold.

Usage:
    cd webapp && python3 sample_sim_timings.py
"""

import os
import sqlite3

from combat_unit_loader import build_combat_dict_from_ref
from simulation import prepare_combat_unit
from simulation_real import (
    BattleSimulation, DT, MAX_BATTLE_SECONDS, deterministic_seed,
)
import random

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

PAIRINGS = [
    ("Franks", "paladin", "Britons", "paladin", "Pal mirror"),
    ("Britons", "arbalester", "Franks", "paladin", "Arb v Pal"),
    ("Britons", "siege_onager", "Goths", "halberdier", "Onager v Halb"),
    ("Byzantines", "elite_cataphract_byzantines", "Britons", "champion", "Cata v Champ"),
    ("Chinese", "elite_chu_ko_nu_chinese", "Britons", "arbalester", "CKN v Arb"),
    ("Saracens", "elite_mameluke_saracens", "Persians", "paladin", "Mam v Pal"),
    # potential stalemates
    ("Mongols", "mangonel", "Britons", "siege_onager", "Mang v Onager"),
    ("Vikings", "berserk_vikings", "Goths", "huskarl_goths", "Berserk v Huskarl"),
]


def _load(civ, slug, age="Imperial"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ, slug, age),
    ).fetchone()
    conn.close()
    if not row:
        return None
    cd = build_combat_dict_from_ref(row)
    cu = prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]
    cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]
    cu["outline_size"] = cd.get("outline_size", 0.2)
    return cu


def run_with_hp_trace(unit1, unit2, scenario, label):
    """Run sim manually, sampling HP every 15s of game time."""
    if scenario == "pop":
        c1, c2 = 30, 30
    else:
        cost1 = unit1["cost_food"] + unit1["cost_wood"] + unit1["cost_gold"] * 1.25
        cost2 = unit2["cost_food"] + unit2["cost_wood"] + unit2["cost_gold"] * 1.25
        c1 = max(1, int(3000 / cost1))
        c2 = max(1, int(3000 / cost2))

    random.seed(deterministic_seed(label, scenario))
    sim = BattleSimulation()
    sim.setup_team(1, unit1, c1)
    sim.setup_team(2, unit2, c2)

    samples = []  # list of (game_time, hp1_pct, hp2_pct, alive1, alive2)
    sample_interval_ticks = int(15.0 / DT)
    next_sample = sample_interval_ticks
    max_ticks = int(MAX_BATTLE_SECONDS / DT)

    natural_winner = None
    natural_tick = None

    for tick in range(max_ticks):
        sim.step(DT)
        if sim.winner is not None and natural_winner is None:
            natural_winner = sim.winner
            natural_tick = tick + 1
            # capture final HP at winner moment
            hp1 = sim.total_hp(1) / max(1.0, sim.total_max_hp(1))
            hp2 = sim.total_hp(2) / max(1.0, sim.total_max_hp(2))
            samples.append(((tick + 1) * DT, hp1, hp2, sim.alive_count(1), sim.alive_count(2)))
            break
        if tick + 1 >= next_sample:
            hp1 = sim.total_hp(1) / max(1.0, sim.total_max_hp(1))
            hp2 = sim.total_hp(2) / max(1.0, sim.total_max_hp(2))
            samples.append(((tick + 1) * DT, hp1, hp2, sim.alive_count(1), sim.alive_count(2)))
            next_sample += sample_interval_ticks

    return {
        "label": f"{label} ({scenario})",
        "count1": c1, "count2": c2,
        "natural_winner": natural_winner,
        "natural_game_time": natural_tick * DT if natural_tick else None,
        "samples": samples,
    }


def main():
    print(f"{'Pairing':<28} {'cnt':<7} {'Win@s':<8} {'Sampling at 15s intervals (game time)':<50}")
    print(f"{'':<28} {'':<7} {'':<8} {'time:hp1/hp2  (delta)':<50}")
    print("-" * 130)

    for civ_a, slug_a, civ_b, slug_b, label in PAIRINGS:
        cu_a = _load(civ_a, slug_a)
        cu_b = _load(civ_b, slug_b)
        if cu_a is None or cu_b is None:
            print(f"  SKIP {label}")
            continue

        for scenario in ("pop", "eco"):
            res = run_with_hp_trace(cu_a, cu_b, scenario, label)
            cnt = f"{res['count1']}v{res['count2']}"
            win_s = f"{res['natural_game_time']:.1f}s" if res['natural_game_time'] else "TIMEOUT"
            samples_str = "  ".join(
                f"{t:.0f}:{h1:.2f}/{h2:.2f}({(h1-h2)*100:+.0f})"
                for (t, h1, h2, _, _) in res['samples']
            )
            print(f"{res['label']:<28} {cnt:<7} {win_s:<8} {samples_str}")

    print()
    print("Now project: how many sims would early-exit at 90s game time with |delta|>10pp?")
    print("(Implement and re-test once cap is in place.)")


if __name__ == "__main__":
    main()
