"""Tape-validation rig for the JAVASCRIPT engine (apps/website/static/js/engine/).

Sibling of tape_rig.py, which scores simulation_real.py. Same corpus, same
tape_runs.db, same 31-column tape_battles INSERT -- so
`python -m aoe2x.validation.report --diff <py_tag> <js_tag>` works unchanged.

    python tools/simjs/dump_tape_dicts.py          # refresh dicts + plan first
    python -m aoe2x.validation.tape_rig_js --label js-before

Division of labour: Python owns the army counts (tape_rig.arena_counts, the only
rule proven to reproduce all 38 recorded counts) and the SQLite write; Node owns
the fights. Python does the DB write because this repo has no node_modules and no
better-sqlite3 -- a native dependency for ~380 inserts is not worth it.
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from aoe2x.sim.sim_version import compute_sim_version                  # noqa: E402
from aoe2x.validation.tape_rig import SCHEMA, _git, make_run_tag       # noqa: E402

ENGINE_GLOB = str(REPO / "apps" / "website" / "static" / "js" / "engine" / "*.js")
ENGINE_LABEL = "js apps/website/static/js/engine"
PLAN = REPO / "data" / "validation" / "tape_plan.json"
OUT_DB = REPO / "data" / "validation" / "tape_runs.db"
RUNNER = REPO / "tools" / "simjs" / "tape_runner.mjs"


def js_sim_version() -> str:
    """Hash the extracted engine's sources -- the JS analogue of sim_version."""
    files = sorted(glob.glob(ENGINE_GLOB))
    if not files:
        sys.exit(f"no engine files matched {ENGINE_GLOB}")
    return compute_sim_version(file_paths=files)


def node_version() -> str:
    out = subprocess.run(["node", "--version"], capture_output=True, check=True)
    return "Node " + out.stdout.decode().strip()


def run_node(scales, seeds, max_seconds):
    proc = subprocess.run(
        ["node", str(RUNNER), "--scales", ",".join(scales),
         "--seeds", str(seeds), "--max-seconds", str(max_seconds)],
        cwd=str(REPO), capture_output=True)
    if proc.returncode != 0:
        sys.exit("tape_runner.mjs failed:\n" + proc.stderr.decode()[-4000:])
    return json.loads(proc.stdout.decode())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="js-run")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--max-seconds", type=float, default=600.0)
    ap.add_argument("--scales", default="tape,equal_count")
    ap.add_argument("--out", default=str(OUT_DB))
    ap.add_argument("--notes", default="")
    a = ap.parse_args()

    if not PLAN.exists():
        sys.exit(f"{PLAN} missing -- run: python tools/simjs/dump_tape_dicts.py")

    scales = [s.strip() for s in a.scales.split(",") if s.strip()]
    plan = {r["plan_id"]: r for r in
            json.loads(PLAN.read_text(encoding="utf-8"))["rows"]}

    sim_version = js_sim_version()
    run_tag = make_run_tag(a.label, sim_version)
    impl = node_version()
    notes = (a.notes + " | " if a.notes else "") + (
        "JS engine run. seeds are 1..N (rng.js aliases seed 0 to 1). "
        "winner===null at the cap is adjudicated by HP% with end_reason='time_cap'. "
        "python_impl holds the NODE version. team*_value_lost is approximated from "
        "hp_pct (the JS engine keeps no resource bookkeeping; kill-bonus gains omitted). "
        "At tape counts the spawn column overflows the 600px map and some units start "
        "clamped to the bottom edge -- production-faithful and parity-locked."
    )

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(out_path))
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO tape_runs (run_tag, run_label, started_utc, sim_version, engine,"
        " python_impl, git_commit, git_branch, git_dirty, seeds, max_seconds, scales, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_tag, a.label, datetime.now(timezone.utc).isoformat(), sim_version,
         ENGINE_LABEL, impl, _git("rev-parse", "HEAD"),
         _git("rev-parse", "--abbrev-ref", "HEAD"),
         1 if _git("status", "--porcelain", default="") else 0,
         a.seeds, a.max_seconds, ",".join(scales), notes))
    db.commit()

    print(f"run_tag      {run_tag}")
    print(f"engine       {ENGINE_LABEL}   sim_version {sim_version[:12]}")
    print(f"runtime      {impl}")
    print(f"corpus       {len(plan)} matchups x {len(scales)} scales x {a.seeds} seeds")
    print()

    t0 = time.perf_counter()
    fights = run_node(scales, a.seeds, a.max_seconds)
    wall_s = time.perf_counter() - t0

    agree = {s: [0, 0] for s in scales}
    wins = {}
    for f in fights:
        pr = plan[f["plan_id"]]
        c = pr["cost"]
        my_value = (c["my_food"] + c["my_wood"] + c["my_gold"]) * f["n1"]
        opp_value = (c["opp_food"] + c["opp_wood"] + c["opp_gold"]) * f["n2"]
        sim_outcome = "win" if f["winner"] == 1 else "loss"
        agrees = (None if pr["tape_outcome"] is None
                  else int(sim_outcome == pr["tape_outcome"]))
        db.execute(
            "INSERT INTO tape_battles (run_tag, my_civ, my_unit_slug, opp_civ,"
            " opp_unit_slug, scale, seed, my_count, opp_count, my_cost_food,"
            " my_cost_wood, my_cost_gold, opp_cost_food, opp_cost_wood,"
            " opp_cost_gold, winner, end_reason, game_time_s, team1_hp_pct,"
            " team1_survivors, team1_value_lost, team2_hp_pct, team2_survivors,"
            " team2_value_lost, team1_start_count, team2_start_count,"
            " signed_score, tape_outcome, sim_outcome, agrees, wall_ms)"
            " VALUES (" + ",".join("?" * 31) + ")",
            (run_tag, pr["subject_civ"], pr["subject_slug"], pr["opp_civ"],
             pr["opp_slug"], f["scale"], f["seed"], f["n1"], f["n2"],
             c["my_food"], c["my_wood"], c["my_gold"],
             c["opp_food"], c["opp_wood"], c["opp_gold"],
             f["winner"], f["end_reason"], round(f["game_time_s"], 3),
             round(f["team1_hp_pct"], 4), f["team1_survivors"],
             round(my_value * (1.0 - f["team1_hp_pct"]), 2),
             round(f["team2_hp_pct"], 4), f["team2_survivors"],
             round(opp_value * (1.0 - f["team2_hp_pct"]), 2),
             f["n1"], f["n2"], round(f["signed_score"], 3),
             pr["tape_outcome"], sim_outcome, agrees, round(f["wall_ms"], 2)))
        key = (f["plan_id"], f["scale"])
        wins[key] = wins.get(key, 0) + (1 if f["winner"] == 1 else 0)
    db.commit()

    for (plan_id, scale), w in sorted(wins.items()):
        pr = plan[plan_id]
        majority = "win" if w * 2 >= a.seeds else "loss"
        ok = (majority == pr["tape_outcome"])
        agree[scale][0] += int(ok)
        agree[scale][1] += 1
        if scale == scales[0]:
            print(f"  {'OK ' if ok else 'XX '}{pr['subject_slug'][:26]:<26}"
                  f" vs {pr['opp_slug'][:28]:<28} tape={pr['tape_outcome']:<4}"
                  f" sim={majority:<4} wr={w}/{a.seeds}")

    db.execute("UPDATE tape_runs SET finished_utc=?, n_matchups=?, n_fights=?, wall_s=?"
               " WHERE run_tag=?",
               (datetime.now(timezone.utc).isoformat(), len(plan), len(fights),
                round(wall_s, 2), run_tag))
    db.commit()

    print()
    for s in scales:
        ok, tot = agree[s]
        print(f"AGREEMENT [{s:<14}] {ok}/{tot}  ({100.0*ok/max(1,tot):.0f}%)")
    print(f"\n{len(fights)} fights in {wall_s:.1f}s"
          f"  ({1000*wall_s/max(1,len(fights)):.0f} ms/fight)")
    print(f"recorded -> {out_path}  (run_tag {run_tag})")


if __name__ == "__main__":
    main()
