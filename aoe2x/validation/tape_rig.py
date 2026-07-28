"""Tape-validation rig for the position-based engine (simulation_real.py).

Measures how closely the batch engine reproduces recorded in-game fights. The
corpus (aoe2x/validation/tape_corpus.json) is ~40 arena fights recorded with
the ddkMatchupAI patrol rig; `tape_outcome` is ground truth.

    pypy3 -m aoe2x.validation.tape_rig --label baseline
    pypy3 -m aoe2x.validation.tape_rig --label after-armor-fix --seeds 5

Reporting and run-to-run comparison live in aoe2x.validation.report:

    python -m aoe2x.validation.report --list
    python -m aoe2x.validation.report --diff <before_tag> <after_tag>

Every fight is recorded at full granularity — one row per (matchup, scale,
seed) — into `data/validation/tape_runs.db`, using the same column set as
`matchup_battles` (counts, per-resource costs, winner, end_reason, game_time_s,
hp%, survivors, value lost) plus the tape verdict and wall-clock cost. Runs are
tagged with a unique `run_tag` so successive engine states stay comparable and
nothing is overwritten.

Scales
  tape           the exact counts the fight was RECORDED at (primary check)
  equal_resource counts re-derived from the recorder's own weighted-cost rule
                 (food 1.0, wood 1.0, gold 1.5, /batch; budget 3000, cap 21) --
                 should reproduce `tape`; a mismatch means the cost model drifted
  equal_count    N v N at N = n_subject, isolating raw strength from cost

IMPORTANT: this module must not import anything that mutates simulation_real.py.
It deliberately re-implements the outcome assembly from simulate_real_battle()
rather than editing that file, because simulation_real.py is byte-hashed into
sim_version -- even a comment there stales every matchup row.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from aoe2x.sim import simulation_real as SR                            # noqa: E402
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref    # noqa: E402

CORPUS = Path(__file__).resolve().parent / "tape_corpus.json"
REF_DB = REPO / "data" / "golden" / "aoe2_reference.db"
OUT_DB = REPO / "data" / "validation" / "tape_runs.db"

# Recorder's equal-resource sizing (build_v2_categorization.py). Kept in
# lockstep with that file and apps/video/overlay/overlay_data.COST_WEIGHT_*.
RES_BUDGET = 3000.0
UNIT_CAP = 21
COST_W_FOOD, COST_W_WOOD, COST_W_GOLD = 1.0, 1.0, 1.5
TRAIN_BATCH = {"blackwood_archer_tupi": 2, "elite_blackwood_archer_tupi": 2}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tape_runs (
    run_tag         TEXT PRIMARY KEY,
    run_label       TEXT NOT NULL,
    started_utc     TEXT NOT NULL,
    finished_utc    TEXT,
    sim_version     TEXT NOT NULL,
    engine          TEXT NOT NULL,
    python_impl     TEXT NOT NULL,
    git_commit      TEXT,
    git_branch      TEXT,
    git_dirty       INTEGER,
    seeds           INTEGER NOT NULL,
    max_seconds     REAL NOT NULL,
    scales          TEXT NOT NULL,
    n_matchups      INTEGER,
    n_fights        INTEGER,
    wall_s          REAL,
    notes           TEXT
);
CREATE TABLE IF NOT EXISTS tape_battles (
    id              INTEGER PRIMARY KEY,
    run_tag         TEXT NOT NULL,

    my_civ          TEXT NOT NULL,
    my_unit_slug    TEXT NOT NULL,
    opp_civ         TEXT NOT NULL,
    opp_unit_slug   TEXT NOT NULL,
    scale           TEXT NOT NULL,
    seed            INTEGER NOT NULL,
    my_count        INTEGER NOT NULL,
    opp_count       INTEGER NOT NULL,

    my_cost_food    REAL NOT NULL,
    my_cost_wood    REAL NOT NULL,
    my_cost_gold    REAL NOT NULL,
    opp_cost_food   REAL NOT NULL,
    opp_cost_wood   REAL NOT NULL,
    opp_cost_gold   REAL NOT NULL,

    winner          INTEGER NOT NULL,
    end_reason      TEXT NOT NULL,
    game_time_s     REAL NOT NULL,

    team1_hp_pct    REAL NOT NULL,
    team1_survivors INTEGER NOT NULL,
    team1_value_lost REAL NOT NULL,
    team2_hp_pct    REAL NOT NULL,
    team2_survivors INTEGER NOT NULL,
    team2_value_lost REAL NOT NULL,

    team1_start_count INTEGER NOT NULL,
    team2_start_count INTEGER NOT NULL,

    signed_score    REAL NOT NULL,
    tape_outcome    TEXT,
    sim_outcome     TEXT NOT NULL,
    agrees          INTEGER,
    wall_ms         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tb_run   ON tape_battles(run_tag);
CREATE INDEX IF NOT EXISTS idx_tb_match ON tape_battles(my_civ, my_unit_slug, opp_civ, opp_unit_slug);
CREATE INDEX IF NOT EXISTS idx_tb_scale ON tape_battles(run_tag, scale);
"""


# --------------------------------------------------------------------------- #
# unit loading / sizing
# --------------------------------------------------------------------------- #
def _batch(slug):
    return TRAIN_BATCH.get(slug, 1)


def weighted_cost(row):
    """Resource-weighted PER-UNIT cost for equal-resource sizing."""
    return (((row["final_cost_food"] or 0) * COST_W_FOOD
             + (row["final_cost_wood"] or 0) * COST_W_WOOD
             + (row["final_cost_gold"] or 0) * COST_W_GOLD)
            / _batch(row["unit_slug"]))


def arena_counts(subject_wc, opp_wc):
    """Recorder's equal_resource_counts: cheaper side gets min(cap, budget//cost),
    pricier side rescaled to the same spend."""
    if subject_wc <= opp_wc:
        n1 = max(1, min(UNIT_CAP, int(RES_BUDGET // subject_wc)))
        return n1, max(1, int(n1 * subject_wc // opp_wc))
    n2 = max(1, min(UNIT_CAP, int(RES_BUDGET // opp_wc)))
    return max(1, int(n2 * opp_wc // subject_wc)), n2


def load_unit(conn, civ, slug):
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()
    if row is None:
        return None, None
    cd = build_combat_dict_from_ref(row)
    cu = SR.prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]
    cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]
    cu["outline_size"] = cd.get("outline_size", 0.2)
    cu["cost"] = cd["cost_food"] + cd["cost_wood"] + cd["cost_gold"]
    return cu, row


# --------------------------------------------------------------------------- #
# one fight, explicit counts
# --------------------------------------------------------------------------- #
def run_fight(u1, n1, u2, n2, seed, max_seconds):
    """Mirror of simulate_real_battle() after _calc_counts, with explicit counts.

    Duplicated rather than imported because simulate_real_battle's `fixed_count`
    is symmetric and the tapes were recorded at asymmetric counts.
    """
    SR.random.seed(seed)
    sim = SR.BattleSimulation()
    sim.setup_team(1, u1, n1)
    sim.setup_team(2, u2, n2)
    t0 = time.perf_counter()
    ticks = sim.run(max_seconds=max_seconds, max_wallclock=1e9)
    wall_ms = (time.perf_counter() - t0) * 1000.0

    hp1 = sim.total_hp(1) / max(1.0, sim.total_max_hp(1))
    hp2 = sim.total_hp(2) / max(1.0, sim.total_max_hp(2))
    o = SR.BattleOutcome(
        winner=sim.winner if sim.winner is not None else 0,
        end_reason=sim.end_reason or "time_cap",
        game_time_s=round(ticks * SR.DT, 3),
        team1_hp_pct=round(hp1, 4), team2_hp_pct=round(hp2, 4),
        team1_survivors=sim.alive_count(1), team2_survivors=sim.alive_count(2),
        team1_resources_lost=sim.total_resources_lost(1),
        team2_resources_lost=sim.total_resources_lost(2),
        team1_start_count=n1, team2_start_count=n2,
        team1_value_lost=sim.total_value_lost(1),
        team2_value_lost=sim.total_value_lost(2),
        my_cost_food=float(u1.get("cost_food") or 0),
        my_cost_wood=float(u1.get("cost_wood") or 0),
        my_cost_gold=float(u1.get("cost_gold") or 0),
        opp_cost_food=float(u2.get("cost_food") or 0),
        opp_cost_wood=float(u2.get("cost_wood") or 0),
        opp_cost_gold=float(u2.get("cost_gold") or 0),
    )
    return o, wall_ms


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def _git(*args, default=None):
    try:
        return subprocess.run(["git", *args], capture_output=True, check=True,
                              cwd=str(REPO)).stdout.decode().strip()
    except Exception:
        return default


def make_run_tag(label, sim_version):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{label}-{stamp}-sv{sim_version[:8]}"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="run", help="human label for this run")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--max-seconds", type=float, default=180.0)
    ap.add_argument("--scales", default="tape,equal_count",
                    help="comma list: tape,equal_resource,equal_count")
    ap.add_argument("--subject", help="only this subject slug")
    ap.add_argument("--out", default=str(OUT_DB))
    ap.add_argument("--notes", default="")
    a = ap.parse_args()

    scales = [s.strip() for s in a.scales.split(",") if s.strip()]
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))["rows"]
    if a.subject:
        rows = [r for r in rows if r["subject_slug"] == a.subject]
    if not rows:
        sys.exit("no corpus rows selected")

    try:
        from aoe2x.sim.sim_version import compute_sim_version
        sim_version = compute_sim_version()
    except Exception as e:                                   # pragma: no cover
        sys.exit(f"cannot compute sim_version: {e}")

    run_tag = make_run_tag(a.label, sim_version)
    impl = ("PyPy" if hasattr(sys, "pypy_version_info") else "CPython")
    impl += " " + sys.version.split()[0]

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(out_path))
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO tape_runs (run_tag, run_label, started_utc, sim_version, engine,"
        " python_impl, git_commit, git_branch, git_dirty, seeds, max_seconds, scales, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_tag, a.label, datetime.now(timezone.utc).isoformat(), sim_version,
         "simulation_real.py", impl, _git("rev-parse", "HEAD"),
         _git("rev-parse", "--abbrev-ref", "HEAD"),
         1 if _git("status", "--porcelain", default="") else 0,
         a.seeds, a.max_seconds, ",".join(scales), a.notes))
    db.commit()

    print(f"run_tag      {run_tag}")
    print(f"engine       simulation_real.py   sim_version {sim_version[:12]}")
    print(f"runtime      {impl}")
    print(f"corpus       {len(rows)} matchups x {len(scales)} scales x {a.seeds} seeds")
    print()

    conn = sqlite3.connect(str(REF_DB))
    conn.row_factory = sqlite3.Row
    cache = {}

    def unit(civ, slug):
        if (civ, slug) not in cache:
            cache[(civ, slug)] = load_unit(conn, civ, slug)
        return cache[(civ, slug)]

    t_all = time.perf_counter()
    n_fights = 0
    agree = {s: [0, 0] for s in scales}          # scale -> [agreed, total]
    skipped = []

    for r in rows:
        u1, row1 = unit(r["subject_civ"], r["subject_slug"])
        u2, row2 = unit(r["opp_civ"], r["opp_slug"])
        if u1 is None or u2 is None:
            skipped.append(f"{r['subject_slug']} vs {r['opp_civ']}/{r['opp_slug']}")
            continue

        for scale in scales:
            if scale == "tape":
                n1, n2 = r["n_subject"], r["n_opp"]
            elif scale == "equal_resource":
                n1, n2 = arena_counts(weighted_cost(row1), weighted_cost(row2))
            elif scale == "equal_count":
                n1 = n2 = r["n_subject"]
            else:
                sys.exit(f"unknown scale {scale}")

            scores, wins = [], 0
            for seed in range(a.seeds):
                o, wall_ms = run_fight(u1, n1, u2, n2, seed, a.max_seconds)
                n_fights += 1
                score = SR.signed_score(o) if hasattr(SR, "signed_score") else \
                    (o.team1_hp_pct - o.team2_hp_pct) * 100.0
                scores.append(score)
                if o.winner == 1:
                    wins += 1
                sim_outcome = "win" if o.winner == 1 else "loss"
                agrees = (None if r["tape_outcome"] is None
                          else int(sim_outcome == r["tape_outcome"]))
                db.execute(
                    "INSERT INTO tape_battles (run_tag, my_civ, my_unit_slug, opp_civ,"
                    " opp_unit_slug, scale, seed, my_count, opp_count, my_cost_food,"
                    " my_cost_wood, my_cost_gold, opp_cost_food, opp_cost_wood,"
                    " opp_cost_gold, winner, end_reason, game_time_s, team1_hp_pct,"
                    " team1_survivors, team1_value_lost, team2_hp_pct, team2_survivors,"
                    " team2_value_lost, team1_start_count, team2_start_count,"
                    " signed_score, tape_outcome, sim_outcome, agrees, wall_ms)"
                    " VALUES (" + ",".join("?" * 31) + ")",
                    (run_tag, r["subject_civ"], r["subject_slug"], r["opp_civ"],
                     r["opp_slug"], scale, seed, n1, n2, o.my_cost_food, o.my_cost_wood,
                     o.my_cost_gold, o.opp_cost_food, o.opp_cost_wood, o.opp_cost_gold,
                     o.winner, o.end_reason, o.game_time_s, o.team1_hp_pct,
                     o.team1_survivors, o.team1_value_lost, o.team2_hp_pct,
                     o.team2_survivors, o.team2_value_lost, n1, n2,
                     round(score, 3), r["tape_outcome"], sim_outcome, agrees,
                     round(wall_ms, 2)))

            majority = "win" if wins * 2 >= a.seeds else "loss"
            ok = (majority == r["tape_outcome"])
            agree[scale][0] += int(ok)
            agree[scale][1] += 1
            if scale == scales[0]:
                print(f"  {'OK ' if ok else 'XX '}"
                      f"{r['subject_slug'][:26]:<26} vs {r['opp_slug'][:28]:<28}"
                      f" {n1:>3}v{n2:<3} tape={r['tape_outcome']:<4}"
                      f" sim={majority:<4} wr={wins}/{a.seeds}"
                      f" S={statistics.mean(scores):+7.1f}")
        db.commit()

    wall_s = time.perf_counter() - t_all
    db.execute("UPDATE tape_runs SET finished_utc=?, n_matchups=?, n_fights=?, wall_s=?"
               " WHERE run_tag=?",
               (datetime.now(timezone.utc).isoformat(), len(rows), n_fights,
                round(wall_s, 2), run_tag))
    db.commit()

    print()
    for s in scales:
        ok, tot = agree[s]
        pct = 100.0 * ok / tot if tot else 0.0
        print(f"AGREEMENT [{s:<14}] {ok}/{tot}  ({pct:.0f}%)")
    print(f"\n{n_fights} fights in {wall_s:.1f}s  ({1000*wall_s/max(1,n_fights):.0f} ms/fight)")
    if skipped:
        print(f"skipped {len(skipped)}: {skipped[:5]}")
    print(f"recorded -> {out_path}  (run_tag {run_tag})")


if __name__ == "__main__":
    main()
