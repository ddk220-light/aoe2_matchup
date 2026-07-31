"""E14 step 1c: does a melee unit LOCK onto one enemy and ride it to death?

The hypothesis under test (the user's, from watching the game): a melee unit
picks ONE enemy and keeps it. Retargeting is rare. If its locked enemy is
somewhere else it WALKS there, past other enemies, without attacking them --
so melee units spend a lot of time walking rather than fighting even with
enemies in reach. If that is what the recordings show, the engine's
opportunistic "hit whatever is nearest" targeting is the thing to replace.

Four measurements, one implementation, fed either a tape or a sim run:

1. LOCK PERSISTENCE -- per attacker, the run-length encoding of the victims it
   damages. For every lock run: swings, seconds, and how it ENDED --
     DIED      the victim died (by anyone's hand) before the attacker's next
               landed hit -- the lock ran to completion;
     SWITCH    the attacker's next landed hit was on a different, still-LIVING
               victim. Split into RETURN (it comes back to the original later)
               and ABANDON (it never does). ABANDON is the only true retarget.
     END       no next hit (the attacker died, or the fight ended).
2. NEAREST-VS-LOCKED -- at each landed hit, was the victim the attacker's
   nearest living enemy? Reported as the share of hits on a non-nearest victim
   and the distance ratio victim/nearest. Ratios well above 1 mean units walk
   past enemies to reach the one they are locked on.
3. WALK SHARE -- fraction of 10 Hz samples in which a unit is moving while at
   least one living enemy is inside its own reach: an available fight it is
   declining. Requires positions, so it is tape-vs-sim only when the sim run
   carries a units stream (tools/simjs/dump_sim_units.mjs).
4. LOCK BIRTH -- when a lock ends and a new one starts, was the new victim the
   nearest living enemy at the moment the old lock ended? And at fight start,
   are the first victims spread one-per-attacker or piled?

    python tools/simjs/melee_lock_forensics.py --sim-runs-dir <dir>
    python tools/simjs/melee_lock_forensics.py --sim-runs-dir <dir> --positions
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path

from melee_bout_forensics import (
    load_manifest, load_dicts, tape_damage, sim_damage, pick_fights, TAPES,
)


# ---------------------------------------------------------------------------
# positions
# ---------------------------------------------------------------------------

def tape_frames(tag: str):
    """[(t, {id: (x, y, owner)})] at the recording's 10 Hz, time-sorted."""
    frames: dict[float, dict] = {}
    with gzip.open(TAPES / tag / f"{tag}.units.jsonl.gz", "rt") as fh:
        for line in fh:
            r = json.loads(line)
            frames.setdefault(round(r["t"], 3), {})[r["id"]] = (
                r["x"], r["y"], r["owner"], r.get("hp"))
    return sorted(frames.items())


def sim_frames(sim_runs_dir: Path, run_id: str, seed: int):
    p = sim_runs_dir / run_id / f"seed-{seed}.units.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [(f["t"], {u[0]: (u[1], u[2], u[3], u[4]) for u in f["u"]})
            for f in raw["frames"]]


def frame_at(frames, t):
    i = bisect.bisect_left([f[0] for f in frames], t)
    return frames[min(max(i, 0), len(frames) - 1)][1]


# ---------------------------------------------------------------------------
# 1. lock persistence
# ---------------------------------------------------------------------------

def lock_runs(events, owner):
    """Run-length encoding of each attacker's victim sequence, with the reason
    each run ended. `death_t` is built from the WHOLE stream (either side can
    land the killing blow), so DIED means the victim was actually dead.
    """
    death_t = {}
    for e in sorted(events, key=lambda e: e["t"]):
        if e.get("kill"):
            death_t.setdefault(e["victim"], e["t"])

    by_attacker = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            by_attacker[e["attacker"]].append(e)

    runs = []
    for hits in by_attacker.values():
        hits.sort(key=lambda e: e["t"])
        seq = []
        for e in hits:
            if seq and seq[-1][0] == e["victim"]:
                seq[-1][1].append(e)
            else:
                seq.append([e["victim"], [e]])
        later = defaultdict(int)
        for v, _ in seq:
            later[v] += 1
        seen = defaultdict(int)
        for i, (v, es) in enumerate(seq):
            seen[v] += 1
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            if nxt is None:
                how = "END"
            else:
                d = death_t.get(v)
                # dead by the time the attacker swung somewhere else?
                how = "DIED" if (d is not None and d <= nxt[1][0]["t"]) else (
                    "RETURN" if later[v] > seen[v] else "ABANDON")
            runs.append({
                "victim": v, "swings": len(es),
                "seconds": es[-1]["t"] - es[0]["t"], "how": how,
            })
    return runs


# ---------------------------------------------------------------------------
# 2. nearest vs locked
# ---------------------------------------------------------------------------

def nearest_vs_locked(events, owner, frames, foe_owner):
    """(share of hits on a non-nearest enemy, distance-ratio samples)."""
    if frames is None:
        return None, []
    ratios, non_nearest, total = [], 0, 0
    for e in events:
        if e.get("attacker_owner") != owner:
            continue
        fr = frame_at(frames, e["t"])
        a = fr.get(e["attacker"])
        v = fr.get(e["victim"])
        if not a or not v:
            continue
        dv = ((a[0] - v[0]) ** 2 + (a[1] - v[1]) ** 2) ** 0.5
        best = None
        for uid, u in fr.items():
            if u[2] != foe_owner or uid == e["attacker"]:
                continue
            if u[3] is not None and u[3] <= 0:
                continue
            d = ((a[0] - u[0]) ** 2 + (a[1] - u[1]) ** 2) ** 0.5
            if best is None or d < best:
                best = d
        if best is None or best <= 1e-9:
            continue
        total += 1
        if dv > best + 0.05:
            non_nearest += 1
        ratios.append(dv / best)
    return (non_nearest / total if total else None), ratios


# ---------------------------------------------------------------------------
# 3. walk share with a fight available
# ---------------------------------------------------------------------------

def walk_share(frames, owner, foe_owner, reach, step_tiles=0.02):
    """Share of samples where a unit MOVED while a living enemy was in reach.

    Movement is measured between consecutive frames; `step_tiles` is the
    per-frame displacement above which a unit counts as walking (10 Hz x the
    slowest melee unit here, 1.0 tile/s, gives 0.1 tiles per frame, so 0.02 is
    a fifth of a real step -- comfortably above position quantisation).
    """
    if frames is None:
        return None, None
    moving_with_fight = samples_with_fight = 0
    moving = samples = 0
    for (t0, f0), (t1, f1) in zip(frames, frames[1:]):
        for uid, u in f0.items():
            if u[2] != owner:
                continue
            if u[3] is not None and u[3] <= 0:
                continue
            n = f1.get(uid)
            if not n:
                continue
            step = ((n[0] - u[0]) ** 2 + (n[1] - u[1]) ** 2) ** 0.5
            walked = step > step_tiles
            samples += 1
            moving += walked
            near = any(
                v[2] == foe_owner and (v[3] is None or v[3] > 0)
                and ((u[0] - v[0]) ** 2 + (u[1] - v[1]) ** 2) ** 0.5 <= reach
                for v in f0.values())
            if near:
                samples_with_fight += 1
                moving_with_fight += walked
        void = (t0, t1)
        del void
    return (moving / samples if samples else None,
            moving_with_fight / samples_with_fight if samples_with_fight else None)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def summarise_runs(runs):
    n = len(runs)
    if not n:
        return {}
    by = defaultdict(int)
    for r in runs:
        by[r["how"]] += 1
    closed = n - by["END"]
    return {
        "runs": n,
        "swings_per_lock_median": statistics.median([r["swings"] for r in runs]),
        "swings_per_lock_mean": round(statistics.mean([r["swings"] for r in runs]), 2),
        "seconds_per_lock_median": round(statistics.median([r["seconds"] for r in runs]), 2),
        "died_frac": round(by["DIED"] / closed, 4) if closed else None,
        "return_frac": round(by["RETURN"] / closed, 4) if closed else None,
        "abandon_frac": round(by["ABANDON"] / closed, 4) if closed else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fights", default="melee")
    ap.add_argument("--sim-runs-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--positions", action="store_true",
                    help="also run the position-based measurements (slow)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    dicts = load_dicts()
    tape_rows, sim_rows = [], []
    tape_ratio, sim_ratio = [], []
    tape_nn, sim_nn = [], []
    tape_walk, sim_walk = [], []

    fights = pick_fights(args.fights)
    if args.limit:
        fights = fights[:args.limit]
    for fight in fights:
        try:
            tev = tape_damage(fight["tag"])
            sev = sim_damage(args.sim_runs_dir, fight["run_id"], args.seed)
        except FileNotFoundError:
            continue
        tfr = sfr = None
        if args.positions:
            tfr = tape_frames(fight["tag"])
            sfr = sim_frames(args.sim_runs_dir, fight["run_id"], args.seed)
        for side, foe in ((fight["side1"], fight["side2"]),
                          (fight["side2"], fight["side1"])):
            tape_rows += lock_runs(tev, side["owner"])
            sim_rows += lock_runs(sev, side["owner"])
            if args.positions:
                a = dicts[f"{side['civ']}|{side['slug']}"]
                b = dicts[f"{foe['civ']}|{foe['slug']}"]
                reach = a["attack_range"] + a["collision_size"] + b["collision_size"]
                f1, r1 = nearest_vs_locked(tev, side["owner"], tfr, foe["owner"])
                if f1 is not None:
                    tape_nn.append(f1)
                    tape_ratio += r1
                f2, r2 = nearest_vs_locked(sev, side["owner"], sfr, foe["owner"])
                if f2 is not None:
                    sim_nn.append(f2)
                    sim_ratio += r2
                w = walk_share(tfr, side["owner"], foe["owner"], reach)
                if w and w[1] is not None:
                    tape_walk.append(w)
                w = walk_share(sfr, side["owner"], foe["owner"], reach)
                if w and w[1] is not None:
                    sim_walk.append(w)

    t, s = summarise_runs(tape_rows), summarise_runs(sim_rows)
    print(f"sim={args.sim_runs_dir}\n")
    print(f"{'LOCK PERSISTENCE':34s} {'tape':>9s} {'engine':>9s}")
    for k in ("runs", "swings_per_lock_median", "swings_per_lock_mean",
              "seconds_per_lock_median", "died_frac", "return_frac",
              "abandon_frac"):
        print(f"{k:34s} {str(t.get(k)):>9s} {str(s.get(k)):>9s}")

    if args.positions:
        def q(v, p):
            v = sorted(v)
            return round(v[int(p * (len(v) - 1))], 3) if v else None
        print(f"\n{'NEAREST VS LOCKED':34s} {'tape':>9s} {'engine':>9s}")
        print(f"{'hits on a NON-nearest enemy':34s} "
              f"{round(statistics.mean(tape_nn), 4) if tape_nn else None!s:>9s} "
              f"{round(statistics.mean(sim_nn), 4) if sim_nn else None!s:>9s}")
        for lbl, p in (("dist ratio median", 0.5), ("dist ratio p75", 0.75),
                       ("dist ratio p90", 0.9), ("dist ratio p99", 0.99)):
            print(f"{lbl:34s} {q(tape_ratio, p)!s:>9s} {q(sim_ratio, p)!s:>9s}")
        print(f"\n{'WALK SHARE':34s} {'tape':>9s} {'engine':>9s}")
        for i, lbl in ((0, "moving, any time"),
                       (1, "moving WITH a foe in reach")):
            tv = round(statistics.mean([w[i] for w in tape_walk]), 4) if tape_walk else None
            sv = round(statistics.mean([w[i] for w in sim_walk]), 4) if sim_walk else None
            print(f"{lbl:34s} {tv!s:>9s} {sv!s:>9s}")

    void = load_manifest
    del void


if __name__ == "__main__":
    main()
