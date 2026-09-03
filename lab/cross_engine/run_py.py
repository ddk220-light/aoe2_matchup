"""Task 11 — Python side of the cross-engine comparison. READ-ONLY experiment.

Runs the 16-unit roster (roster.json) as an unordered round-robin — 120 pairs,
10 v 10, seeds 1..5 = 600 fights — through the LEGACY position-based engine
`aoe2x/sim/simulation_real.py`, and writes `py_results.json`.

It also dumps the roster's combat dicts to `combat_dicts.json` (same payload
shape `tools/simjs/dump_combat_dicts.py` freezes for the JS parity golden), so
that `run_js.mjs` feeds the JS engine byte-identical unit stats. Both engines
therefore start from ONE source of truth: data/golden/aoe2_reference.db.

    python lab/cross_engine/run_py.py            # dicts + 600 fights
    python lab/cross_engine/run_py.py --dicts-only

Nothing in aoe2x/ is imported for anything but reading — no engine, golden or
production file is written by this script.

CONSTRUCTION PATTERN (mirrors aoe2x/batch/run_matchup_battles.py::_load_unit
and simulate_real_battle's body, lines 2029-2045):
  * ref_units row -> build_combat_dict_from_ref -> prepare_combat_unit,
    then the four cost keys + outline_size copied over exactly as the batch
    runner does (outline_size drives collision_radius in setup_team);
  * `random.seed(seed)` on the module-global RNG immediately before the sim is
    built, exactly where simulate_real_battle does it;
  * BattleSimulation() + setup_team(1, u, 10) + setup_team(2, u, 10) directly
    rather than simulate_real_battle(fixed_count=10), because that helper runs
    counts through `_calc_count` (fixed_count / pop_space). Every roster unit
    has pop_space 1.0 today so the two agree, but calling setup_team keeps the
    "exactly 10 v 10 in both engines" guarantee independent of pop data.

CAP / TIMEOUT BEHAVIOUR (documented for the report):
  * game-time cap = MAX_BATTLE_SECONDS 600.0 s = 18000 ticks at DT 1/30
    (`BattleSimulation.run`). On reaching it the Python declares a winner by
    HP% (`hp1_pct > hp2_pct`), i.e. it BREAKS the tie the JS refuses to break
    (JS leaves sim.winner === null). Both the raw winner and the raw
    end_reason are recorded; the normalised `winner` field discards the
    HP%-tiebreak so the two engines' categories line up (see NORMALISATION).
  * wall-clock backstop = max_wallclock, default 180 s. Passed as None here:
    a wall-clock exit would make results depend on the host machine, and the
    tick budget already bounds the work.
  * `_decide_kited_fight` can end a fight EARLY (from 120 s, KITE_DECISION_TIME)
    with end_reason "kite_win" (decisive) or "stalemate" (winner 0, both sides
    still alive). The JS has no such exit.

NORMALISATION (identical mapping applied on both sides; run_js.mjs mirrors it):
    "a"                    team 1 won
    "b"                    team 2 won
    "draw"                 mutual annihilation — both teams wiped
    "timeout_both_alive"   the fight never resolved by elimination and BOTH
                           sides still had living units when the engine stopped
  Python reaches "timeout_both_alive" via end_reason "time_cap" (600 s) or
  "stalemate" (kite decision); JS reaches it via winner === null at 600 s.
  Python "kite_win" is decisive -> "a"/"b" (raw fields keep the distinction).
"""

import argparse
import json
import random
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402
from aoe2x.sim import simulation_real as SR  # noqa: E402

REF_DB = ROOT / "data/golden/aoe2_reference.db"
COUNT = 10
SEEDS = (1, 2, 3, 4, 5)
MAX_SECONDS = 600.0


def load_roster():
    return json.loads((HERE / "roster.json").read_text(encoding="utf-8"))


def dump_combat_dicts(roster):
    """ref_units -> {"<civ>|<slug>": combat_dict} -> combat_dicts.json.

    Same logic as tools/simjs/dump_combat_dicts.py, driven by roster.json
    instead of panel_spec.json. Fails loudly on any slug not in the DB.
    """
    con = sqlite3.connect(REF_DB)
    con.row_factory = sqlite3.Row
    out, missing = {}, []
    for u in roster["units"]:
        row = con.execute(
            "select * from ref_units where civ_name=? and unit_slug=? and age='Imperial'",
            (u["civ"], u["slug"]),
        ).fetchone()
        if row is None:
            missing.append(f"{u['civ']}/{u['slug']}")
            continue
        out[f"{u['civ']}|{u['slug']}"] = build_combat_dict_from_ref(row)
        print(f"  {u['civ']:12s} {u['slug']:38s} -> {row['unit_name']}")
    con.close()
    if missing:
        sys.exit("NOT IN DB: " + ", ".join(missing))
    dest = HERE / "combat_dicts.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(out)} dicts -> {dest}")
    return out


def prepare_units(roster, dicts):
    """combat dict -> the prepared stats dict BattleSimulation.setup_team wants."""
    units = {}
    for u in roster["units"]:
        cd = dicts[f"{u['civ']}|{u['slug']}"]
        cu = SR.prepare_combat_unit(cd)
        cu["cost_food"] = cd["cost_food"]
        cu["cost_wood"] = cd["cost_wood"]
        cu["cost_gold"] = cd["cost_gold"]
        cu["outline_size"] = cd.get("outline_size", 0.2)
        cu["cost"] = cd["cost_food"] + cd["cost_wood"] + cd["cost_gold"]
        units[u["key"]] = cu
    return units


def normalise(raw_winner, end_reason, alive_a, alive_b):
    """Python raw result -> the shared 4-value winner vocabulary (see module doc)."""
    if end_reason in ("time_cap", "stalemate") and alive_a > 0 and alive_b > 0:
        return "timeout_both_alive"
    if raw_winner == 1:
        return "a"
    if raw_winner == 2:
        return "b"
    if raw_winner == 0 and alive_a == 0 and alive_b == 0:
        return "draw"
    # winner 0 with survivors on at least one side: no elimination, no decision.
    return "timeout_both_alive"


def living_hp(sim, team_num):
    """Sum currentHp over LIVING units only — the JS headless runner's rule.

    (BattleSimulation.total_hp sums the whole team including corpses.)
    """
    team = sim.team1 if team_num == 1 else sim.team2
    return sum(u.current_hp for u in team if u.state != "dead")


def run_fight(unit_a, unit_b, seed):
    random.seed(seed)
    sim = SR.BattleSimulation()
    sim.setup_team(1, unit_a, COUNT)
    sim.setup_team(2, unit_b, COUNT)
    t0 = time.perf_counter()
    ticks = sim.run(max_seconds=MAX_SECONDS, max_wallclock=None)
    wall = time.perf_counter() - t0
    alive_a = sim.alive_count(1)
    alive_b = sim.alive_count(2)
    raw_winner = sim.winner if sim.winner is not None else 0
    end_reason = sim.end_reason or "time_cap"
    return {
        "winner": normalise(raw_winner, end_reason, alive_a, alive_b),
        "time": round(ticks * SR.DT, 4),
        "alive_a": alive_a,
        "alive_b": alive_b,
        "hp_a": living_hp(sim, 1),
        "hp_b": living_hp(sim, 2),
        "raw_winner": raw_winner,
        "end_reason": end_reason,
        "ticks": ticks,
        "wall_s": round(wall, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dicts-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0,
                    help="debug: only run the first N pairs")
    args = ap.parse_args()

    roster = load_roster()
    dicts = dump_combat_dicts(roster)
    if args.dicts_only:
        return

    units = prepare_units(roster, dicts)
    keys = [u["key"] for u in roster["units"]]
    pairs = [(keys[i], keys[j])
             for i in range(len(keys)) for j in range(i + 1, len(keys))]
    if args.limit:
        pairs = pairs[:args.limit]
    print(f"{len(pairs)} pairs x {len(SEEDS)} seeds = {len(pairs) * len(SEEDS)} fights")

    rows = []
    t0 = time.perf_counter()
    for n, (a, b) in enumerate(pairs, start=1):
        for seed in SEEDS:
            r = run_fight(units[a], units[b], seed)
            r["a"], r["b"], r["seed"] = a, b, seed
            rows.append(r)
            if r["wall_s"] > 300:
                print(f"  !! slow fight {a} vs {b} seed {seed}: {r['wall_s']:.0f}s wall")
        if n % 10 == 0 or n == len(pairs):
            print(f"[{n}/{len(pairs)}] {a} vs {b}  ({time.perf_counter() - t0:.0f}s)")

    order = ["a", "b", "seed", "winner", "time", "alive_a", "alive_b", "hp_a",
             "hp_b", "raw_winner", "end_reason", "ticks", "wall_s"]
    rows = [{k: r[k] for k in order} for r in rows]
    payload = {
        "engine": "python simulation_real.py",
        "count_per_side": COUNT,
        "seeds": list(SEEDS),
        "max_seconds": MAX_SECONDS,
        "max_wallclock": None,
        "sim_dt": SR.DT,
        "kite_decision_time": SR.KITE_DECISION_TIME,
        "wall_seconds_total": round(time.perf_counter() - t0, 1),
        "rows": rows,
    }
    (HERE / "py_results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> py_results.json "
          f"({payload['wall_seconds_total']}s)")


if __name__ == "__main__":
    main()
