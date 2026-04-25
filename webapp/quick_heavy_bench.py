"""Time the heaviest sim case to confirm bucketing helps where it matters."""
import os, sqlite3, time, random
from combat_unit_loader import build_combat_dict_from_ref
from simulation import prepare_combat_unit
from simulation_real import (
    BattleSimulation, DT, MAX_BATTLE_SECONDS, deterministic_seed
)

DB = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

def load(civ, slug):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()
    conn.close()
    if not row: return None
    cd = build_combat_dict_from_ref(row); cu = prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]; cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]; cu["outline_size"] = cd.get("outline_size", 0.2)
    return cu

cases = [
    ("Halberdier mirror", "Britons", "halberdier", "Britons", "halberdier", 54, 54),
    ("Skirm mirror",      "Britons", "imp_elite_skirm", "Britons", "imp_elite_skirm", 56, 56),
    ("Skirm vs Halb",     "Britons", "imp_elite_skirm", "Goths", "halberdier", 56, 54),
    ("Pal mirror 30v30",  "Franks", "paladin", "Britons", "paladin", 30, 30),
    ("Arb v Pal pop",     "Britons", "arbalester", "Franks", "paladin", 30, 30),
]

for label, ca, sa, cb, sb, c1, c2 in cases:
    cu_a = load(ca, sa); cu_b = load(cb, sb)
    if not cu_a or not cu_b: print(f"SKIP {label}"); continue
    times = []
    for trial in range(3):
        random.seed(deterministic_seed(label, trial))
        sim = BattleSimulation()
        sim.setup_team(1, cu_a, c1); sim.setup_team(2, cu_b, c2)
        t0 = time.perf_counter()
        ticks = sim.run()
        times.append((time.perf_counter() - t0) * 1000)
    avg = sum(times) / 3
    print(f"{label:<25}  {c1}v{c2:<3}  avg {avg:>6.0f} ms  trials {[f'{t:.0f}' for t in times]}")
