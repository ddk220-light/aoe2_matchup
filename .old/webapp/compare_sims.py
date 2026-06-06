"""
Side-by-side validation: fast sim (simulation.py) vs real sim (simulation_real.py).

Runs a handful of canonical pairings under the same battle scenarios used by
get_matchup_sims (30v30 fixed-count + 3000-resource), and prints results so we
can sanity-check the position-aware port before running the full batch.

Usage:
    cd webapp && python3 compare_sims.py
"""

import os
import sqlite3
import time

from combat_unit_loader import build_combat_dict_from_ref
from simulation import prepare_combat_unit, simulate_battle
from simulation_real import simulate_real_battle, deterministic_seed

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

# Canonical pairings: (civA, slugA, civB, slugB, label)
# Chosen to exercise melee mirror, kiting, splash, anti-infantry bonus,
# extra projectiles, and ranged-melee.
PAIRINGS = [
    ("Franks", "paladin", "Britons", "paladin", "Paladin mirror (melee)"),
    ("Britons", "arbalester", "Franks", "paladin", "Arb vs Paladin (kite)"),
    ("Britons", "siege_onager", "Goths", "halberdier", "Siege Onager vs Halb (splash)"),
    ("Byzantines", "elite_cataphract_byzantines", "Britons", "champion",
     "Elite Cataphract vs Champ"),
    ("Chinese", "elite_chu_ko_nu_chinese", "Britons", "arbalester",
     "Elite CKN vs Arb (extras)"),
    ("Saracens", "elite_mameluke_saracens", "Persians", "paladin",
     "Elite Mameluke vs Paladin"),
]


def _calc_weighted_cost(food, wood, gold):
    """Match best_units.py / fast-sim cost weighting (food+wood, gold heavier)."""
    return food + wood + gold * 1.25


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
    # carry through outline_size for the real sim
    cu["outline_size"] = cd.get("outline_size", 0.2)
    return cu


def _battle_pair(cu_a, cu_b, scenario):
    """scenario = 'pop' (30v30 fixed) or 'eco' (3000 resources)."""
    cost_a = _calc_weighted_cost(cu_a["cost_food"], cu_a["cost_wood"], cu_a["cost_gold"])
    cost_b = _calc_weighted_cost(cu_b["cost_food"], cu_b["cost_wood"], cu_b["cost_gold"])

    if scenario == "pop":
        kwargs = dict(fixed_count=30, return_hp=True)
    else:
        kwargs = dict(cost1_override=cost_a, cost2_override=cost_b, return_hp=True)
        kwargs_resources = 3000

    if scenario == "pop":
        # ---- Fast sim ----
        t0 = time.perf_counter()
        fw, _, _, fhp1, fhp2 = simulate_battle(cu_a, cu_b, 0, **kwargs)
        ft = time.perf_counter() - t0

        # ---- Real sim ----
        t0 = time.perf_counter()
        rw, _, _, rhp1, rhp2 = simulate_real_battle(
            cu_a, cu_b, 0,
            seed=deterministic_seed(cu_a.get("slug"), cu_b.get("slug"), "pop"),
            _legacy_tuple=True,
            **kwargs,
        )
        rt = time.perf_counter() - t0
    else:
        t0 = time.perf_counter()
        fw, _, _, fhp1, fhp2 = simulate_battle(cu_a, cu_b, 3000, **kwargs)
        ft = time.perf_counter() - t0

        t0 = time.perf_counter()
        rw, _, _, rhp1, rhp2 = simulate_real_battle(
            cu_a, cu_b, 3000,
            seed=deterministic_seed(cu_a.get("slug"), cu_b.get("slug"), "eco"),
            _legacy_tuple=True,
            **kwargs,
        )
        rt = time.perf_counter() - t0

    return {
        "fast": {"winner": fw, "hp1": fhp1, "hp2": fhp2, "time": ft},
        "real": {"winner": rw, "hp1": rhp1, "hp2": rhp2, "time": rt},
    }


def main():
    print(f"{'Pairing':<35} {'Scenario':<6} "
          f"{'Fast W':>6} {'F-HP1':>6} {'F-HP2':>6} {'F-ms':>7}   "
          f"{'Real W':>6} {'R-HP1':>6} {'R-HP2':>6} {'R-ms':>7}")
    print("-" * 130)

    fast_total_ms = 0.0
    real_total_ms = 0.0
    sims = 0

    for civ_a, slug_a, civ_b, slug_b, label in PAIRINGS:
        cu_a = _load(civ_a, slug_a)
        cu_b = _load(civ_b, slug_b)
        if cu_a is None:
            print(f"  SKIP {label}: cannot load {civ_a} {slug_a}")
            continue
        if cu_b is None:
            print(f"  SKIP {label}: cannot load {civ_b} {slug_b}")
            continue

        for scenario in ("pop", "eco"):
            res = _battle_pair(cu_a, cu_b, scenario)
            f, r = res["fast"], res["real"]
            print(
                f"{label:<35} {scenario:<6} "
                f"{f['winner']:>6} {f['hp1']:>6.2f} {f['hp2']:>6.2f} {f['time']*1000:>7.2f}   "
                f"{r['winner']:>6} {r['hp1']:>6.2f} {r['hp2']:>6.2f} {r['time']*1000:>7.2f}"
            )
            fast_total_ms += f["time"] * 1000
            real_total_ms += r["time"] * 1000
            sims += 1

    print("-" * 130)
    if sims:
        print(f"\nSummary: {sims} sims each")
        print(f"  Fast avg: {fast_total_ms/sims:.2f} ms/sim")
        print(f"  Real avg: {real_total_ms/sims:.2f} ms/sim "
              f"({real_total_ms/fast_total_ms:.0f}x slower)")

        # Project full-batch ETA: 1225 civ-pairs * ~30 unit-pairs * 2 sims
        proj_sims = 1225 * 30 * 2
        proj_min = (real_total_ms / sims * proj_sims) / 1000 / 60
        print(f"  Full matchup batch projection: ~{proj_sims} sims "
              f"~ {proj_min:.0f} min")


if __name__ == "__main__":
    main()
