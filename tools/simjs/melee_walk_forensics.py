"""E15 step 1: WHERE does a melee unit's walking come from?

E14 established the last measured gap: over the 31 pure-melee recordings a
melee unit is MOVING for ~38-45% of the fight and is moving WHILE a living
foe sits inside its own reach for ~27-29% of it, while the engine after E14
moves 17% / 2.7%. "The engine's melee stands still" is the one-line summary.
This module decomposes that walking into CAUSES so the mechanism that has to
be built is chosen by measurement rather than by taste.

Everything is computed by ONE implementation fed either a tape's
(units.jsonl.gz + damage.jsonl.gz) or a sim run's (seed-N.units.json +
seed-N.json), so a tape number and an engine number are the same statistic.

THE LOCK TIMELINE (how "what was this unit doing at time t" is inferred)
-----------------------------------------------------------------------
The only shared ground truth is the damage stream, so a unit's intent is
read backwards off its landed hits. Run-length-encode each attacker's victim
sequence; run k (victim v_k, first hit f_k, last hit l_k) owns the whole
interval (l_{k-1}, l_k]:

    ACQUISITION  (l_{k-1}, f_k)   the unit is getting to v_k
    SUSTAINED    [f_k,     l_k]   the unit is landing hits on v_k

Attributing the pre-first-hit interval to the victim that is about to be hit
is the point: that interval IS the travel, and it is exactly what E13 faked
with a 5.8 s timer. Acquisition is sub-classified by what ended the previous
run -- the previous victim DIED (post-kill travel) or was still ALIVE (a
live break: contact was lost with a foe that could still be fought). The
interval before an attacker's first hit is the fight's opening approach; the
interval after its last hit is censored (the unit died or the fight ended)
and is excluded from every rate below.

THE FIVE CAUSES (step 1 of the E15 brief)
-----------------------------------------
1. PURSUIT      sustained, lock alive but OUT of reach. Split by the lock's
                own speed at that instant: the victim MOVED away (it is
                pursuing its own lock) vs the victim was standing still, in
                which case the gap was opened at this unit's end (shoved, or
                it never closed).
2. MICRO-FOLLOW sustained, lock IN reach, and the unit moves anyway -- i.e.
                it tracks its target's position between swings instead of
                planting. Measured with a sign: the displacement's component
                along (unit -> lock) is positive when following, negative
                when being pushed off.
3. SCRUM FLOW   is the whole line translating (everyone pursuing moving
                locks) or churning in place? Per side per frame: centroid
                speed vs mean individual speed. A high ratio is collective
                drift, a low one is internal shuffling.
4. POST-KILL    at every killing blow: how far is the attacker from the
                victim it hits NEXT, how long does it take, and how much
                longer is the path it walks than the straight line (a path
                that threads a scrum arcs; one through empty space does not).
5. SHOVE        sustained samples that go from in-reach to out-of-reach, and
                whether the attacker or the victim opened the gap. This is
                unit pushing, measured as the rate at which it breaks
                contact -- the suspected physical origin of both the walk and
                the tape's break rate.

    PYTHONPATH=. python tools/simjs/melee_walk_forensics.py \
        --sim-runs-dir calibration/runs/melee-walk
    ... --by-slug          per unit-class decomposition
    ... --fights paladin__vs__elite_steppe
"""
from __future__ import annotations

import argparse
import bisect
import json
import statistics
from collections import defaultdict
from pathlib import Path

from melee_bout_forensics import (
    load_dicts, tape_damage, sim_damage, pick_fights, engine_reach,
)
from melee_lock_forensics import tape_frames, sim_frames

# A unit counts as WALKING in a 10 Hz sample when it moved more than this many
# tiles between frames. Identical to melee_lock_forensics.walk_share's bar so
# the two scripts' "moving" columns are the same quantity: the slowest melee
# unit here covers 0.10 tiles per frame, so 0.02 is a fifth of a real step,
# comfortably above position quantisation and far below a walk.
STEP_TILES = 0.02


# ---------------------------------------------------------------------------
# lock timeline
# ---------------------------------------------------------------------------

def lock_timeline(events, owner):
    """{attacker_id: [segment, ...]} sorted by time.

    segment = dict(victim, t0, t1, phase, cause) where phase is
    "acquire" or "sustain" and cause (acquire only) is one of
    "open" (fight's first engagement), "postkill", "livebreak".
    """
    death_t = {}
    for e in sorted(events, key=lambda e: e["t"]):
        if e.get("kill"):
            death_t.setdefault(e["victim"], e["t"])

    by_attacker = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            by_attacker[e["attacker"]].append(e)

    out = {}
    for aid, hits in by_attacker.items():
        hits.sort(key=lambda e: e["t"])
        runs = []
        for e in hits:
            if runs and runs[-1]["victim"] == e["victim"]:
                runs[-1]["last"] = e["t"]
                runs[-1]["kill"] = runs[-1]["kill"] or bool(e.get("kill"))
            else:
                runs.append({"victim": e["victim"], "first": e["t"],
                             "last": e["t"], "kill": bool(e.get("kill"))})
        segs = []
        prev = None
        for r in runs:
            if prev is None:
                cause, t0 = "open", 0.0
            else:
                t0 = prev["last"]
                d = death_t.get(prev["victim"])
                cause = "postkill" if (d is not None and d <= r["first"]) \
                    else "livebreak"
            if r["first"] > t0:
                segs.append({"victim": r["victim"], "t0": t0, "t1": r["first"],
                             "phase": "acquire", "cause": cause})
            segs.append({"victim": r["victim"], "t0": r["first"],
                         "t1": r["last"], "phase": "sustain", "cause": None})
            prev = r
        out[aid] = segs
    return out


def seg_at(segs, t):
    """The segment covering t, or None (censored head/tail)."""
    lo, hi = 0, len(segs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s = segs[mid]
        if t < s["t0"]:
            hi = mid - 1
        elif t > s["t1"]:
            lo = mid + 1
        else:
            return s
    return None


# ---------------------------------------------------------------------------
# the walk decomposition
# ---------------------------------------------------------------------------

BUCKETS = ("pursue_victim_moved", "pursue_victim_still", "micro_follow",
           "travel_postkill", "travel_livebreak", "travel_open")


def decompose(frames, events, owner, foe_owner, reach_of, radius_pair):
    """Per-sample decomposition of one side's movement.

    frames     [(t, {id: (x, y, owner, hp)})]
    reach_of   (attacker_slug_reach) scalar: attack_range + rA + rB in tiles
    """
    tl = lock_timeline(events, owner)
    n_samples = 0
    n_moving = 0
    n_with_foe_in_reach = 0
    n_moving_with_foe_in_reach = 0
    bucket_samples = defaultdict(int)
    bucket_moving = defaultdict(int)
    radial = []                       # micro-follow signed radial step
    pursuit_gap = []                  # tiles beyond reach while pursuing
    breaks = 0                        # in-reach -> out-of-reach transitions
    breaks_attacker = 0               # ... opened at the attacker's end
    breaks_victim = 0
    in_reach_samples = 0
    centroid_speed = []
    indiv_speed = []
    rot_speed = []                    # rad/s about the side's own centroid
    engaged_step = []                 # |displacement| of an in-reach attacker
    engaged_cos = []                  # cos(attacker step, victim step)
    engaged_victim_moving = 0         # victim moved while I was in reach
    push_same = 0                     # shoved-off events with an ALLY behind
    push_enemy = 0                    # ... with an ENEMY behind
    push_none = 0

    for (t0, f0), (t1, f1) in zip(frames, frames[1:]):
        dt = max(t1 - t0, 1e-6)
        mine0 = [(uid, u) for uid, u in f0.items()
                 if u[2] == owner and (u[3] is None or u[3] > 0)]
        # --- scrum flow: centroid vs individual (cause 3) ---
        moved = []
        for uid, u in mine0:
            n = f1.get(uid)
            if n:
                moved.append((u, n))
        if len(moved) >= 2:
            cx0 = sum(m[0][0] for m in moved) / len(moved)
            cy0 = sum(m[0][1] for m in moved) / len(moved)
            cx1 = sum(m[1][0] for m in moved) / len(moved)
            cy1 = sum(m[1][1] for m in moved) / len(moved)
            centroid_speed.append(
                ((cx1 - cx0) ** 2 + (cy1 - cy0) ** 2) ** 0.5 / dt)
            indiv_speed.append(statistics.mean(
                ((m[1][0] - m[0][0]) ** 2 + (m[1][1] - m[0][1]) ** 2) ** 0.5 / dt
                for m in moved))
            # ROTATION of the body about its own centroid: the mean angular
            # velocity of each member's radius vector. Sign-preserving, so a
            # scrum that is genuinely wheeling gives a non-zero mean while one
            # that is only churning averages toward zero.
            om = []
            for a0, a1 in moved:
                rx, ry = a0[0] - cx0, a0[1] - cy0
                r2 = rx * rx + ry * ry
                if r2 < 0.25:                      # within half a tile of the
                    continue                       # centre: angle is noise
                vx = (a1[0] - cx1) - rx
                vy = (a1[1] - cy1) - ry
                om.append((rx * vy - ry * vx) / r2 / dt)
            if om:
                rot_speed.append(statistics.mean(om))

        foes0 = [v for v in f0.values()
                 if v[2] == foe_owner and (v[3] is None or v[3] > 0)]

        for uid, u in mine0:
            nxt = f1.get(uid)
            if not nxt:
                continue
            sx, sy = nxt[0] - u[0], nxt[1] - u[1]
            step = (sx * sx + sy * sy) ** 0.5
            walked = step > STEP_TILES
            n_samples += 1
            n_moving += walked
            if any(((u[0] - v[0]) ** 2 + (u[1] - v[1]) ** 2) ** 0.5 <= reach_of
                   for v in foes0):
                n_with_foe_in_reach += 1
                n_moving_with_foe_in_reach += walked

            segs = tl.get(uid)
            if not segs:
                continue
            s = seg_at(segs, t0)
            if s is None:
                continue
            v0 = f0.get(s["victim"])
            if s["phase"] == "acquire":
                b = {"open": "travel_open", "postkill": "travel_postkill",
                     "livebreak": "travel_livebreak"}[s["cause"]]
                bucket_samples[b] += 1
                bucket_moving[b] += walked
                continue
            # sustained: is the lock inside this unit's reach?
            if not v0:
                continue
            dx, dy = v0[0] - u[0], v0[1] - u[1]
            d0 = (dx * dx + dy * dy) ** 0.5
            if d0 <= reach_of:
                in_reach_samples += 1
                bucket_samples["micro_follow"] += 1
                bucket_moving["micro_follow"] += walked
                engaged_step.append(step)
                if walked and d0 > 1e-9:
                    radial.append((sx * dx + sy * dy) / d0)
                # --- micro-following (cause 2): does my step track my
                # victim's? Only meaningful when BOTH bodies actually moved.
                v1m = f1.get(s["victim"])
                if v1m:
                    vsx, vsy = v1m[0] - v0[0], v1m[1] - v0[1]
                    vstep = (vsx * vsx + vsy * vsy) ** 0.5
                    if vstep > STEP_TILES:
                        engaged_victim_moving += 1
                        if walked:
                            engaged_cos.append(
                                (sx * vsx + sy * vsy) / (step * vstep))
                    # --- who shoved me? A step whose radial component is
                    # NEGATIVE (away from the victim I am trying to hit) is not
                    # something the unit wanted; look for the body it is being
                    # driven off by, i.e. the nearest one within contact
                    # distance lying OPPOSITE the direction I moved.
                    if walked and d0 > 1e-9:
                        arad = (sx * dx + sy * dy) / d0
                        if arad < 0:
                            best, bteam = None, None
                            for oid, ou in f0.items():
                                if oid == uid:
                                    continue
                                if ou[3] is not None and ou[3] <= 0:
                                    continue
                                ox, oy = ou[0] - u[0], ou[1] - u[1]
                                od = (ox * ox + oy * oy) ** 0.5
                                if od > reach_of or od < 1e-9:
                                    continue
                                # behind me relative to my motion
                                if (ox * sx + oy * sy) / (od * step) > -0.5:
                                    continue
                                if best is None or od < best:
                                    best, bteam = od, ou[2]
                            if best is None:
                                push_none += 1
                            elif bteam == owner:
                                push_same += 1
                            else:
                                push_enemy += 1
                # --- shove / contact break (cause 5) ---
                v1 = f1.get(s["victim"])
                if v1:
                    d1 = ((v1[0] - nxt[0]) ** 2 + (v1[1] - nxt[1]) ** 2) ** 0.5
                    if d1 > reach_of:
                        breaks += 1
                        # who opened it? compare each body's radial motion
                        # along the ORIGINAL separation axis.
                        ux, uy = dx / max(d0, 1e-9), dy / max(d0, 1e-9)
                        a_rad = sx * ux + sy * uy          # + = attacker closed
                        v_rad = (v1[0] - v0[0]) * ux + (v1[1] - v0[1]) * uy
                        if v_rad > -a_rad:
                            breaks_victim += 1
                        else:
                            breaks_attacker += 1
            else:
                vnext = f1.get(s["victim"])
                vstep = 0.0
                if vnext:
                    vstep = ((vnext[0] - v0[0]) ** 2
                             + (vnext[1] - v0[1]) ** 2) ** 0.5
                b = ("pursue_victim_moved" if vstep > STEP_TILES
                     else "pursue_victim_still")
                bucket_samples[b] += 1
                bucket_moving[b] += walked
                if walked:
                    pursuit_gap.append(d0 - reach_of)

    void = radius_pair
    del void
    return {
        "samples": n_samples,
        "moving": n_moving,
        "with_foe_in_reach": n_with_foe_in_reach,
        "moving_with_foe_in_reach": n_moving_with_foe_in_reach,
        "bucket_samples": dict(bucket_samples),
        "bucket_moving": dict(bucket_moving),
        "radial": radial,
        "pursuit_gap": pursuit_gap,
        "breaks": breaks,
        "breaks_attacker": breaks_attacker,
        "breaks_victim": breaks_victim,
        "in_reach_samples": in_reach_samples,
        "centroid_speed": centroid_speed,
        "indiv_speed": indiv_speed,
        "rot_speed": rot_speed,
        "engaged_step": engaged_step,
        "engaged_cos": engaged_cos,
        "engaged_victim_moving": engaged_victim_moving,
        "push_same": push_same,
        "push_enemy": push_enemy,
        "push_none": push_none,
    }


# ---------------------------------------------------------------------------
# swing-phase profile (cause 6: WHEN does a unit move vs swing?)
# ---------------------------------------------------------------------------

def swing_phase(frames, events, owner, reload_s):
    """Moving-share as a function of position within the reload cycle.

    For every sample, phase = (t - this unit's last landed hit) / reload,
    binned into tenths. If a unit plants only for the swing animation the
    moving-share dips near phase 0 and recovers; if it plants for the whole
    cycle the profile is flat and low. Samples before a unit's first hit or
    more than one full reload after its last are excluded -- neither is inside
    a cycle.
    """
    hits = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            hits[e["attacker"]].append(e["t"])
    for v in hits.values():
        v.sort()
    bins_n = [0] * 10
    bins_m = [0] * 10
    for (t0, f0), (_t1, f1) in zip(frames, frames[1:]):
        for uid, u in f0.items():
            if u[2] != owner or (u[3] is not None and u[3] <= 0):
                continue
            hs = hits.get(uid)
            if not hs:
                continue
            i = bisect.bisect_right(hs, t0) - 1
            if i < 0:
                continue
            phase = (t0 - hs[i]) / reload_s
            if phase >= 1.0:
                continue
            n = f1.get(uid)
            if not n:
                continue
            step = ((n[0] - u[0]) ** 2 + (n[1] - u[1]) ** 2) ** 0.5
            b = min(9, int(phase * 10))
            bins_n[b] += 1
            bins_m[b] += step > STEP_TILES
    return bins_n, bins_m


# ---------------------------------------------------------------------------
# post-kill travel (cause 4)
# ---------------------------------------------------------------------------

def postkill_travel(frames, events, owner, reach_of):
    """At each killing blow: straight-line distance to the NEXT victim at the
    moment of the kill, the time to the next landed hit, and the ratio of the
    path actually walked to that straight line.
    """
    times = [f[0] for f in frames]
    by_attacker = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            by_attacker[e["attacker"]].append(e)
    dists, delays, arcs = [], [], []
    for aid, hits in by_attacker.items():
        hits.sort(key=lambda e: e["t"])
        for i, e in enumerate(hits):
            if not e.get("kill") or i + 1 >= len(hits):
                continue
            nxt = hits[i + 1]
            if nxt["victim"] == e["victim"]:
                continue
            i0 = min(range(len(times)), key=lambda k: abs(times[k] - e["t"]))
            i1 = min(range(len(times)), key=lambda k: abs(times[k] - nxt["t"]))
            if i1 <= i0:
                continue
            a0 = frames[i0][1].get(aid)
            v0 = frames[i0][1].get(nxt["victim"])
            if not a0 or not v0:
                continue
            d = ((a0[0] - v0[0]) ** 2 + (a0[1] - v0[1]) ** 2) ** 0.5
            dists.append(max(0.0, d - reach_of))
            delays.append(nxt["t"] - e["t"])
            path = 0.0
            prev = a0
            ok = True
            for k in range(i0 + 1, i1 + 1):
                cur = frames[k][1].get(aid)
                if not cur:
                    ok = False
                    break
                path += ((cur[0] - prev[0]) ** 2 + (cur[1] - prev[1]) ** 2) ** 0.5
                prev = cur
            if ok:
                straight = ((prev[0] - a0[0]) ** 2 + (prev[1] - a0[1]) ** 2) ** 0.5
                if straight > 0.25:
                    arcs.append(path / straight)
    return dists, delays, arcs


# ---------------------------------------------------------------------------
# lock birth: WHICH enemy does a freed unit pick? (cause 4, the choice half)
# ---------------------------------------------------------------------------

def lock_birth_choice(frames, events, owner, foe_owner, reach):
    """At every acquisition (the instant a unit is freed and starts on a new
    victim), rank the chosen victim among the living enemies by distance, and
    count how many same-team allies were already locked on each candidate.

    Two competing accounts of "why is the tape's next victim so much farther
    than the engine's" are separated here without either being assumed:

      NEAREST         the freed unit takes the geometrically closest body --
                      what the engine's findTarget does. Predicts rank 1
                      almost always.
      NEAREST-FREE    the freed unit takes the closest body that is not
                      already ringed by allies -- a purely geometric claim (a
                      corpse can only be reached from so many sides), and the
                      one MELEE_CONTACT_SLOTS already encodes. Predicts rank
                      > 1 exactly when the closer bodies are saturated.

    Returned: rank histogram, and for the rank>1 cases how many allies the
    SKIPPED closer enemies already had.
    """
    tl = lock_timeline(events, owner)
    times = [f[0] for f in frames]
    ranks = []
    excess = []
    skipped_load = []          # allies already on the closer enemies we passed
    chosen_load = []           # allies already on the one we took
    for aid, segs in tl.items():
        for s in segs:
            if s["phase"] != "acquire" or s["cause"] == "open":
                continue
            t = s["t0"]
            i = min(range(len(times)), key=lambda k: abs(times[k] - t))
            fr = frames[i][1]
            a = fr.get(aid)
            if not a:
                continue
            cands = []
            for uid, u in fr.items():
                if u[2] != foe_owner or (u[3] is not None and u[3] <= 0):
                    continue
                cands.append((((a[0] - u[0]) ** 2 + (a[1] - u[1]) ** 2) ** 0.5,
                              uid))
            if not cands:
                continue
            cands.sort()
            # how many allies are locked on each enemy right now
            load = defaultdict(int)
            for oid, osegs in tl.items():
                if oid == aid:
                    continue
                os_ = seg_at(osegs, t)
                if os_ is not None:
                    load[os_["victim"]] += 1
            rank = next((k for k, (_, uid) in enumerate(cands, 1)
                         if uid == s["victim"]), None)
            if rank is None:
                continue
            ranks.append(rank)
            # The physically meaningful version of "rank": how many EXTRA
            # tiles this choice costs over taking the nearest body. Rank alone
            # over-dramatises a scrum in which five enemies sit inside 1.5
            # tiles of each other.
            excess.append(cands[rank - 1][0] - cands[0][0])
            chosen_load.append(load[s["victim"]])
            if rank > 1:
                skipped_load += [load[uid] for _, uid in cands[:rank - 1]]
    void = reach
    del void
    return ranks, excess, chosen_load, skipped_load


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, list):
            dst.setdefault(k, []).extend(v)
        elif isinstance(v, dict):
            d = dst.setdefault(k, defaultdict(int))
            for kk, vv in v.items():
                d[kk] += vv
        else:
            dst[k] = dst.get(k, 0) + v
    return dst


def _pct(a, b):
    return f"{100.0 * a / b:6.2f}%" if b else "     -"


def report(label, tape, sim):
    print(f"\n=== {label} ===")
    print(f"{'':34s} {'tape':>10s} {'engine':>10s}")
    print(f"{'moving, any time':34s} "
          f"{_pct(tape['moving'], tape['samples']):>10s} "
          f"{_pct(sim['moving'], sim['samples']):>10s}")
    print(f"{'moving WITH a foe in reach':34s} "
          f"{_pct(tape['moving_with_foe_in_reach'], tape['with_foe_in_reach']):>10s} "
          f"{_pct(sim['moving_with_foe_in_reach'], sim['with_foe_in_reach']):>10s}")

    print(f"\n{'WALK DECOMPOSITION':30s} {'t occ':>8s} {'e occ':>8s}"
          f" {'t walk':>8s} {'e walk':>8s} {'t rate':>8s} {'e rate':>8s}")
    print("  occ  = % of ALL alive samples spent in this state\n"
          "  walk = % of ALL alive samples this state contributes to walking\n"
          "  rate = % of the state's OWN samples spent moving")
    for b in BUCKETS:
        ts, tm = tape["bucket_samples"].get(b, 0), tape["bucket_moving"].get(b, 0)
        ss, sm = sim["bucket_samples"].get(b, 0), sim["bucket_moving"].get(b, 0)
        print(f"{b:30s} {_pct(ts, tape['samples']):>8s} "
              f"{_pct(ss, sim['samples']):>8s} {_pct(tm, tape['samples']):>8s} "
              f"{_pct(sm, sim['samples']):>8s} {_pct(tm, ts):>8s} "
              f"{_pct(sm, ss):>8s}")
    tso = sum(tape["bucket_samples"].get(b, 0) for b in BUCKETS)
    sso = sum(sim["bucket_samples"].get(b, 0) for b in BUCKETS)
    tm = sum(tape["bucket_moving"].get(b, 0) for b in BUCKETS)
    sm = sum(sim["bucket_moving"].get(b, 0) for b in BUCKETS)
    print(f"{'TOTAL (classified)':30s} {_pct(tso, tape['samples']):>8s} "
          f"{_pct(sso, sim['samples']):>8s} {_pct(tm, tape['samples']):>8s} "
          f"{_pct(sm, sim['samples']):>8s}")
    print(f"{'alive samples (10 Hz)':30s} {tape['samples']:>8d} "
          f"{sim['samples']:>8d}")

    def q(v, p):
        v = sorted(v)
        return round(v[int(p * (len(v) - 1))], 3) if v else None

    print(f"\n{'MICRO-FOLLOW SIGN (tiles/step)':34s} {'tape':>10s} {'engine':>10s}")
    for lbl, p in (("radial p10 (- = pushed off)", 0.1), ("radial median", 0.5),
                   ("radial p90 (+ = following)", 0.9)):
        print(f"{lbl:34s} {q(tape['radial'], p)!s:>10s} "
              f"{q(sim['radial'], p)!s:>10s}")
    print(f"{'n micro-follow steps':34s} {len(tape['radial']):>10d} "
          f"{len(sim['radial']):>10d}")

    print(f"\n{'ENGAGED-UNIT STEP (in reach of lock)':34s} {'tape':>10s} {'engine':>10s}")
    for lbl, p in (("step p50 (tiles/0.1s)", 0.5), ("step p90", 0.9),
                   ("step p99", 0.99)):
        print(f"{lbl:34s} {q(tape['engaged_step'], p)!s:>10s} "
              f"{q(sim['engaged_step'], p)!s:>10s}")
    print(f"{'victim moving while I am in reach':34s} "
          f"{_pct(tape['engaged_victim_moving'], tape['in_reach_samples']):>10s} "
          f"{_pct(sim['engaged_victim_moving'], sim['in_reach_samples']):>10s}")
    t = round(statistics.mean(tape["engaged_cos"]), 3) if tape["engaged_cos"] else None
    s = round(statistics.mean(sim["engaged_cos"]), 3) if sim["engaged_cos"] else None
    print(f"{'cos(my step, victim step)':34s} {t!s:>10s} {s!s:>10s}")
    print(f"{'  n paired steps':34s} {len(tape['engaged_cos']):>10d} "
          f"{len(sim['engaged_cos']):>10d}")

    print(f"\n{'SHOVED-OFF EVENTS (who is behind me)':34s} {'tape':>10s} {'engine':>10s}")
    tt = tape["push_same"] + tape["push_enemy"] + tape["push_none"]
    ss = sim["push_same"] + sim["push_enemy"] + sim["push_none"]
    for lbl, k in (("pushed by an ALLY", "push_same"),
                   ("pushed by an ENEMY", "push_enemy"),
                   ("nobody behind (self-move)", "push_none")):
        print(f"{lbl:34s} {_pct(tape[k], tt):>10s} {_pct(sim[k], ss):>10s}")
    print(f"{'  n backward steps while engaged':34s} {tt:>10d} {ss:>10d}")

    print(f"\n{'PURSUIT GAP (tiles past reach)':34s} {'tape':>10s} {'engine':>10s}")
    for lbl, p in (("median", 0.5), ("p90", 0.9)):
        print(f"{lbl:34s} {q(tape['pursuit_gap'], p)!s:>10s} "
              f"{q(sim['pursuit_gap'], p)!s:>10s}")

    print(f"\n{'CONTACT BREAKS (shove)':34s} {'tape':>10s} {'engine':>10s}")
    print(f"{'breaks per in-reach sample':34s} "
          f"{_pct(tape['breaks'], tape['in_reach_samples']):>10s} "
          f"{_pct(sim['breaks'], sim['in_reach_samples']):>10s}")
    print(f"{'... opened by the VICTIM moving':34s} "
          f"{_pct(tape['breaks_victim'], tape['breaks']):>10s} "
          f"{_pct(sim['breaks_victim'], sim['breaks']):>10s}")
    print(f"{'... opened at the ATTACKER end':34s} "
          f"{_pct(tape['breaks_attacker'], tape['breaks']):>10s} "
          f"{_pct(sim['breaks_attacker'], sim['breaks']):>10s}")

    print(f"\n{'SCRUM FLOW (tiles/s)':34s} {'tape':>10s} {'engine':>10s}")
    for lbl, key in (("centroid speed (mean)", "centroid_speed"),
                     ("individual speed (mean)", "indiv_speed"),
                     ("rotation rad/s (signed mean)", "rot_speed")):
        t = round(statistics.mean(tape[key]), 4) if tape[key] else None
        s = round(statistics.mean(sim[key]), 4) if sim[key] else None
        print(f"{lbl:34s} {t!s:>10s} {s!s:>10s}")
    for lbl, key in (("rotation |rad/s| (mean)", "rot_speed"),):
        t = round(statistics.mean(abs(x) for x in tape[key]), 4) if tape[key] else None
        s = round(statistics.mean(abs(x) for x in sim[key]), 4) if sim[key] else None
        print(f"{lbl:34s} {t!s:>10s} {s!s:>10s}")
    if tape["indiv_speed"] and sim["indiv_speed"]:
        tr = statistics.mean(tape["centroid_speed"]) / statistics.mean(tape["indiv_speed"])
        sr = statistics.mean(sim["centroid_speed"]) / statistics.mean(sim["indiv_speed"])
        print(f"{'centroid/individual ratio':34s} {tr:10.3f} {sr:10.3f}")

    print(f"\n{'LOCK BIRTH: rank of chosen victim':34s} {'tape':>10s} {'engine':>10s}")
    for r in (1, 2, 3):
        print(f"{'  rank ' + str(r):34s} "
              f"{_pct(sum(1 for x in tape['ranks'] if x == r), len(tape['ranks'])):>10s} "
              f"{_pct(sum(1 for x in sim['ranks'] if x == r), len(sim['ranks'])):>10s}")
    print(f"{'  rank >3':34s} "
          f"{_pct(sum(1 for x in tape['ranks'] if x > 3), len(tape['ranks'])):>10s} "
          f"{_pct(sum(1 for x in sim['ranks'] if x > 3), len(sim['ranks'])):>10s}")
    print(f"{'  excess tiles over nearest, median':34s} "
          f"{q(tape['excess'], 0.5)!s:>10s} {q(sim['excess'], 0.5)!s:>10s}")
    print(f"{'  excess tiles over nearest, p90':34s} "
          f"{q(tape['excess'], 0.9)!s:>10s} {q(sim['excess'], 0.9)!s:>10s}")
    for lbl, key in (("allies already on the CHOSEN foe", "chosen_load"),
                     ("allies already on SKIPPED closer", "skipped_load")):
        t = round(statistics.mean(tape[key]), 3) if tape[key] else None
        s = round(statistics.mean(sim[key]), 3) if sim[key] else None
        print(f"{lbl:34s} {t!s:>10s} {s!s:>10s}")

    print(f"\n{'POST-KILL TRAVEL':34s} {'tape':>10s} {'engine':>10s}")
    for lbl, key, p in (("distance to next victim, median", "pk_dist", 0.5),
                        ("distance to next victim, p90", "pk_dist", 0.9),
                        ("seconds to next hit, median", "pk_delay", 0.5),
                        ("path/straight-line, median", "pk_arc", 0.5)):
        print(f"{lbl:34s} {q(tape[key], p)!s:>10s} {q(sim[key], p)!s:>10s}")

    print(f"\n{'SWING-PHASE PROFILE':34s} {'tape':>10s} {'engine':>10s}")
    print("  moving-share by tenth of the reload cycle since the last hit")
    for b in range(10):
        print(f"{'  phase ' + f'{b / 10:.1f}-{(b + 1) / 10:.1f}':34s} "
              f"{_pct(tape['phase_m'][b], tape['phase_n'][b]):>10s} "
              f"{_pct(sim['phase_m'][b], sim['phase_n'][b]):>10s}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fights", default="melee")
    ap.add_argument("--sim-runs-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--by-slug", action="store_true")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()

    dicts = load_dicts()
    tape_all, sim_all = {}, {}
    tape_slug, sim_slug = defaultdict(dict), defaultdict(dict)

    for fight in pick_fights(args.fights):
        try:
            tev = tape_damage(fight["tag"])
            sev = sim_damage(args.sim_runs_dir, fight["run_id"], args.seed)
        except FileNotFoundError:
            continue
        tfr = tape_frames(fight["tag"])
        sfr = sim_frames(args.sim_runs_dir, fight["run_id"], args.seed)
        if sfr is None:
            continue
        for side, foe in ((fight["side1"], fight["side2"]),
                          (fight["side2"], fight["side1"])):
            a = dicts[f"{side['civ']}|{side['slug']}"]
            b = dicts[f"{foe['civ']}|{foe['slug']}"]
            reach = engine_reach(a, b)
            for frames, ev, acc, sacc in (
                    (tfr, tev, tape_all, tape_slug[side["slug"]]),
                    (sfr, sev, sim_all, sim_slug[side["slug"]])):
                d = decompose(frames, ev, side["owner"], foe["owner"], reach,
                              (a["collision_size"], b["collision_size"]))
                dd, de, da = postkill_travel(frames, ev, side["owner"], reach)
                d["pk_dist"], d["pk_delay"], d["pk_arc"] = dd, de, da
                rk, ex, cl, sl = lock_birth_choice(
                    frames, ev, side["owner"], foe["owner"], reach)
                d["ranks"], d["excess"] = rk, ex
                d["chosen_load"], d["skipped_load"] = cl, sl
                pn, pm = swing_phase(frames, ev, side["owner"],
                                     1.0 / a["attack_speed"])
                d["phase_n"] = {i: v for i, v in enumerate(pn)}
                d["phase_m"] = {i: v for i, v in enumerate(pm)}
                merge(acc, d)
                merge(sacc, d)

    report(f"ALL MELEE  ({args.fights})  sim={args.sim_runs_dir}",
           tape_all, sim_all)
    if args.by_slug:
        for slug in sorted(tape_slug):
            if not sim_slug.get(slug):
                continue
            report(f"slug={slug}", tape_slug[slug], sim_slug[slug])
    if args.json_out:
        def strip(d):
            return {k: (len(v) if isinstance(v, list) else
                        dict(v) if isinstance(v, dict) else v)
                    for k, v in d.items()}
        args.json_out.write_text(json.dumps(
            {"tape": strip(tape_all), "sim": strip(sim_all)}, indent=1),
            encoding="utf-8")


if __name__ == "__main__":
    main()
