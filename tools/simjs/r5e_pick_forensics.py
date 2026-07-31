"""R5e: is the tape's per-shot victim choice POSITIONAL, and is that the same
thing as the heavy-cavalry-archer army stringing out along the threat axis?

MEASUREMENT ONLY. Nothing under apps/website/static/js/engine/ is imported or
changed. The engine side is read from tools/simjs/ranged_shot_dump.mjs dumps,
the tape side from the recordings, and every statistic is computed by ONE
function over the normalised ``Fight`` that tools/simjs/ranged_fire_forensics.py
builds from either source -- so a tape number and an engine number here are the
same code, never two implementations that happen to share a column name.

THE QUESTION THIS ROUND INHERITS
--------------------------------
R5c measured that tape ranged units pick their per-shot victim at rank 2-3.5
among the enemies in reach (34-65% nearest) with low persistence (6-26% of
consecutive shots re-pick the same victim). R5d shipped T1, the
coverage-filtered nearest-first rule, and its emergent near% moved the WRONG
way (63-95%). Separately, in `heavy_cav_archer__vs__hand_cannoneer` the tape's
archer army strings out 6.25 tiles deep along the threat axis -- individual
riders close to 1.45 tiles while the median holds ~6.5-7 -- where the engine
holds a 1.62-tile flat line. That fight carries the last ranged-vs-ranged HP
error.

The hypothesis under test is that these are ONE phenomenon: the deep riders are
the units whose TARGETS sit deep in the enemy formation, i.e. selection is
positional (shoot the enemy across from me) rather than metric (shoot the
nearest), and the ride-in is the consequence of the assignment rather than its
cause.

    node tools/simjs/ranged_shot_dump.mjs --tags <the six> --seeds 20 \
        --out-dir D:/AI/aoe2_golden/shots_r5e
    PYTHONPATH=. python tools/simjs/r5e_pick_forensics.py \
        --sim-runs-dir D:/AI/aoe2_golden/shots_r5e --seeds 20 --section all
    ... --section m1|m2|m3|m4|m5|m6|all

Findings: docs/calibration/r5e_pick_forensics.md.

GEOMETRY, AND WHY IT IS THE R5c GEOMETRY
----------------------------------------
Every distance is centre-to-centre off the 10 Hz position stream, interpolated,
on both sources -- never the reconstructed flight length, which R5c §0 showed
is inset 0.61 tiles at the launch end and 0.24-0.32 at the impact end.

The CHOICE SET is the enemies inside `reach_tiles` = canReach() =
`attack_range + both physics radii`, NOT inRange()'s reach: canReach is the
predicate the engine's own selectShotTarget() uses to decide which alternatives
exist, so it is the set the shooter picked from. `engine_reach` (canReach plus
MELEE_RANGE_BUFFER) is used only where a "reach lip" is quoted, matching
r5c_depth_forensics.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ranged_fire_forensics as rff              # noqa: E402
from ranged_fire_forensics import (              # noqa: E402
    CALIB, R5_TAGS, SHORT, med, q, r, pct, table,
    load_tape, load_engine, engine_reach,
)
from r5c_targeting_forensics import (            # noqa: E402
    TICK, target_of, hp_at, living_enemies, unit_dmg, mark_strays, reach_tiles,
)

HCA_HC = "heavy_cav_archer__vs__hand_cannoneer"

# An "excess" pick -- the shot went at least this much further than the
# shooter's nearest reachable enemy. 0.5 tiles is above the ~0.1-tile position
# noise of the 10 Hz stream and above the 0.2-0.25 tile body radii, so a shot
# over the bar passed a genuinely closer body. Same bar on both sources.
FAR_EXCESS = 0.5

# Two candidates are TIED on a metric inside this. Ties are given the mid-rank
# rather than being broken arbitrarily, so a pool of identical candidates
# scores 0.5 (the random null) on every metric instead of 0 or 1.
TIE = 1e-9


# ---------------------------------------------------------------------------
# small stats helpers
# ---------------------------------------------------------------------------

def mean(v):
    return statistics.mean(v) if v else None


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx < 1e-12 or sy < 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(v[order[j + 1]] - v[order[i]]) <= TIE:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    return pearson(_ranks(xs), _ranks(ys))


def pctile_of(vals, chosen):
    """Where `chosen` sits in `vals`, 0 = the minimum, 1 = the maximum.

    Mid-rank on ties, so a pool whose candidates are all equal on this metric
    scores 0.5 -- the random null -- rather than crediting the rule with a
    minimum it did not have to find. Returns None for a pool of one, where the
    metric carries no information at all.
    """
    k = len(vals)
    if k < 2:
        return None
    less = sum(1 for x in vals if x < chosen - TIE)
    ties = sum(1 for x in vals if abs(x - chosen) <= TIE)
    return (less + (ties - 1) / 2.0) / (k - 1)


def is_min(vals, chosen):
    return chosen <= min(vals) + TIE


# ---------------------------------------------------------------------------
# geometry over a Fight
# ---------------------------------------------------------------------------

def centroids(fight, owner, t):
    """(own centroid, enemy centroid) over the units alive at `t`."""
    mine, theirs = [], []
    for uid, (x, y, o, _hp) in fight.frame_at(t).items():
        p = fight.pos(uid, t) or (x, y)
        (mine if o == owner else theirs).append(p)
    if not mine or not theirs:
        return None, None
    return ((mean([p[0] for p in mine]), mean([p[1] for p in mine])),
            (mean([p[0] for p in theirs]), mean([p[1] for p in theirs])))


def unit_vec(ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    return None if n < 1e-9 else (dx / n, dy / n)


def threat_axis(fight, owner, t):
    """Unit vector from this side's centroid toward the enemy's, at `t`.

    THE axis for every "along / across" statement below. Army-level rather than
    per-shooter, because the thing being tested is whether a shooter fires at
    the enemy DIRECTLY ACROSS THE LINE from it -- which only means something
    against a line the whole army shares. The per-shooter variant (shooter ->
    enemy centroid) is carried alongside as `perpS`, since it is the other
    reasonable reading of "straight ahead" and the two can disagree.
    """
    a, b = centroids(fight, owner, t)
    return None if a is None else unit_vec(a[0], a[1], b[0], b[1])


# ---------------------------------------------------------------------------
# committed-damage reconstruction (shared by M2, M5's T1 rule and M6)
# ---------------------------------------------------------------------------

class Cover:
    """The friendly damage already COMMITTED to a victim when a shot leaves.

    This is R5b's `inboundDamageOn` (in flight, arriving strictly before mine)
    plus, when `claims` is set, R5d-T2's same-tick ledger (a shot fired earlier
    in the same tick counts regardless of arrival order). It is rebuilt from
    the shot list rather than read off the engine so the TAPE can be asked the
    same question -- and, on the engine, so the same arithmetic can be re-run
    with a different weight per projectile, which is the whole of M6.

    `weight(shot)` is what one in-flight projectile is worth. The engine books
    `plannedDamage` = the FULL post-armor damage on every projectile including
    one whose accuracy roll already failed; M6 re-runs this with those shots at
    half and at zero.
    """

    def __init__(self, shots, dmg, weight=None, claims=False):
        self.dmg = dmg
        self.claims = claims
        self.w = weight or (lambda s: s.get("planned") or dmg)
        self.by_tgt = defaultdict(list)
        for i, s in enumerate(shots):
            s["_i"] = i
            v = target_of(s)
            if v is not None:
                self.by_tgt[v].append(s)

    def on(self, v, t, idx, my_impact_t):
        tot = 0.0
        for o in self.by_tgt.get(v, ()):
            if o["_i"] >= idx:
                continue                      # not fired yet
            if abs(o["t"] - t) <= TICK:
                if self.claims:               # T2: same tick, no eta test
                    tot += self.w(o)
                continue
            if o["impact_t"] > t and o["impact_t"] < my_impact_t:
                tot += self.w(o)
        return tot


def failed_roll(s):
    """Did this ENGINE shot's accuracy roll fail? Exact, not inferred.

    fireProjectile computes the undisplaced aim point and throws it by up to
    the dat dispersion IF AND ONLY IF the roll failed. The probe records both
    the aim point (`aimx/aimy`) and the projectile's real endpoint (`ix/iy`),
    so a non-zero difference is the roll's own signature -- no rate is assumed
    and no rng is replayed. Tape shots have no aim point recorded and always
    return False; they are never fed to M6, which is an engine-only question.
    """
    if s.get("aimx") is None:
        return False
    return math.hypot(s["ix"] - s["aimx"], s["iy"] - s["aimy"]) > 1e-9


# ---------------------------------------------------------------------------
# THE PER-SHOT RECORD -- one builder, both sources, every measurement below
# ---------------------------------------------------------------------------

def shot_records(fight, owner, reach, dmg, claims):
    """Every shot of `owner` with its full choice set, scored three ways.

    For each shot: the enemies inside `reach` at launch (the set the shooter
    picked from), and for each of them the three quantities the positional
    hypothesis and the metric hypothesis disagree about --

        d      centre-to-centre distance from the shooter
        perp   |offset across the ARMY threat axis| from the shooter's own
               position: 0 means the candidate is directly across the line
        perpS  the same against the shooter -> enemy-centroid axis
        ang    |angle| between the candidate and the shooter's FACING, where
               facing is taken as the direction of that shooter's PREVIOUS
               launch. The engine has no facing angle (only a sprite bool), so
               this proxy is the only definition available identically on both
               sources; it is a swing angle, and because a repeat pick scores
               0 by construction the angular table is reported only over
               shots that CHANGED victim.

    plus the state the conditional chains (M2) need: whether the shooter's
    previous victim is dead, alive-and-covered, alive-and-uncovered, or has
    left reach.
    """
    ss = sorted([s for s in fight.shots
                 if s["owner"] == owner and not s.get("stray")],
                key=lambda s: s["t"])
    cov = Cover(ss, dmg, claims=claims)
    prev_v, prev_face = {}, {}
    recs = []
    # A shot whose own victim is outside the pool cannot be scored against it,
    # so it is dropped -- and the drop is REPORTED (`drop%` in M1) rather than
    # silently absorbed, because R5c section 2 measured that the tape fires
    # from beyond the bare centre-to-centre range on 21-92% of shots and the
    # pool's reach predicate is exactly what decides how many of those survive.
    # `--pool-reach inrange` re-runs everything with the 5 px
    # MELEE_RANGE_BUFFER added -- the tape's own measured ceiling -- as the
    # sensitivity check on that choice.
    n_seen = n_drop = 0
    for idx, s in enumerate(ss):
        v = target_of(s)
        if v is None:
            continue
        n_seen += 1
        sx, sy = s["sx"], s["sy"]
        foes = living_enemies(fight, owner, s["t"])
        pool = [f for f in foes if math.hypot(f[1] - sx, f[2] - sy) <= reach]
        ids = [f[0] for f in pool]
        if v not in ids:
            n_drop += 1
            continue
        u = threat_axis(fight, owner, s["t"])
        _a, ec = centroids(fight, owner, s["t"])
        us = unit_vec(sx, sy, ec[0], ec[1]) if ec else None
        face = prev_face.get(s["shooter"])

        cands = {}
        for uid, x, y, hp in pool:
            dx, dy = x - sx, y - sy
            d = math.hypot(dx, dy)
            c = {"id": uid, "x": x, "y": y, "hp": hp or 0.0, "d": d}
            c["perp"] = abs(dx * -u[1] + dy * u[0]) if u else None
            c["perpS"] = abs(dx * -us[1] + dy * us[0]) if us else None
            if face and d > 1e-9:
                dot = max(-1.0, min(1.0, (dx * face[0] + dy * face[1]) / d))
                c["ang"] = math.degrees(math.acos(dot))
            else:
                c["ang"] = None
            c["cov"] = cov.on(uid, s["t"], idx, s["t"] + d / max(s.get("speed", 7.0), 1e-6))
            c["covered"] = c["hp"] > 0 and c["cov"] >= c["hp"]
            cands[uid] = c

        pv = prev_v.get(s["shooter"])
        if pv is None:
            pstate = "first"
        elif pv not in cands:
            pstate = "dead_or_gone"
            phpv = hp_at(fight, pv, s["t"])
            if phpv is not None and phpv > 0:
                pstate = "left_reach"
        elif cands[pv]["covered"]:
            pstate = "covered"
        else:
            pstate = "open"

        recs.append({
            "t": s["t"], "shooter": s["shooter"], "victim": v,
            "sx": sx, "sy": sy, "shot": s, "cands": cands, "k": len(cands),
            "prev": pv, "pstate": pstate, "axis": u,
        })
        prev_v[s["shooter"]] = v
        f = unit_vec(sx, sy, cands[v]["x"], cands[v]["y"])
        if f:
            prev_face[s["shooter"]] = f
    for rec in recs:
        rec["drop%"] = pct(n_drop, n_seen)
    return recs


def metric_summary(recs, key, changed_only=False):
    """Where the CHOSEN victim sits on `key` against the pool it came from."""
    pcts, mins, n = [], 0, 0
    for rec in recs:
        if changed_only and rec["prev"] == rec["victim"]:
            continue
        vals = [c[key] for c in rec["cands"].values() if c[key] is not None]
        ch = rec["cands"][rec["victim"]][key]
        if ch is None or len(vals) < 2:
            continue
        n += 1
        pcts.append(pctile_of(vals, ch))
        mins += int(is_min(vals, ch))
    return {"n": n, "pctile": r(mean(pcts), 3), "min%": r(pct(mins, n), 1)}


# ---------------------------------------------------------------------------
# M1 -- ANGULAR / POSITIONAL PICK STRUCTURE
# ---------------------------------------------------------------------------

def m1(recs):
    """Chosen-victim percentile on distance vs across-the-line offset vs swing.

    The random null is 0.500 on every column by construction (pctile_of gives
    ties the mid-rank), and a strict nearest-first rule scores d.pctile = 0.000
    / d.min% = 100. So the comparison the hypothesis needs is direct: if the
    tape's `perp` percentile is materially below its `d` percentile, the pick
    is positional; if `d` is the low one, it is metric.

    `rho(d,perp)` is the mean Spearman correlation between the two metrics
    INSIDE each pool. It is the caveat column: when it is high the two rules
    are nearly the same rule on this geometry and the comparison above cannot
    separate them.
    """
    out = {"n": len(recs), "k_med": r(med([x["k"] for x in recs]), 1),
           "drop%": r(recs[0]["drop%"], 1) if recs else None}
    for key, lbl in (("d", "dist"), ("perp", "perp"), ("perpS", "perpS")):
        s = metric_summary(recs, key)
        out[f"{lbl}.pct"] = s["pctile"]
        out[f"{lbl}.min%"] = s["min%"]
    s = metric_summary(recs, "ang", changed_only=True)
    out["ang.n"] = s["n"]
    out["ang.pct"] = s["pctile"]
    out["ang.min%"] = s["min%"]
    rhos = []
    for rec in recs:
        ds = [c["d"] for c in rec["cands"].values()]
        ps = [c["perp"] for c in rec["cands"].values() if c["perp"] is not None]
        if len(ds) >= 4 and len(ps) == len(ds):
            rr = spearman(ds, ps)
            if rr is not None:
                rhos.append(rr)
    out["rho(d,perp)"] = r(mean(rhos), 2)
    # The min% columns need their own null: a shooter picking uniformly at
    # random lands on a given pool's minimum with probability 1/k, so the
    # random null for `min%` is the mean of 1/k over the same shots -- not
    # zero, and not the same number in two fights with different pool sizes.
    out["min%_rand"] = r(100.0 * mean([1.0 / x["k"] for x in recs]), 1) \
        if recs else None
    ex = [rec["cands"][rec["victim"]]["d"] - min(c["d"] for c in rec["cands"].values())
          for rec in recs]
    out["excess p50"] = r(med(ex), 2)
    out["excess p90"] = r(q(ex, 0.9), 2)
    out["far%"] = r(pct(sum(1 for e in ex if e > FAR_EXCESS), len(ex)), 1)
    return out


# ---------------------------------------------------------------------------
# M2 -- CONDITIONAL PICK CHAINS
# ---------------------------------------------------------------------------

def m2(recs):
    """Split the rank-2-3.5 aggregate by what happened to the PREVIOUS victim.

    Four regimes: the previous victim died (or vanished from the frame), it is
    alive but out of reach, it is alive in reach and already lethally covered,
    or it is alive in reach and open. If the pick is nearest at re-acquisition
    and drifts positionally in between (or the reverse), it shows here and
    nowhere else.
    """
    out = {}
    for st in ("first", "dead_or_gone", "left_reach", "covered", "open"):
        sub = [x for x in recs if x["pstate"] == st]
        if not sub:
            continue
        same = sum(1 for x in sub if x["prev"] == x["victim"])
        d = metric_summary(sub, "d")
        p = metric_summary(sub, "perp")
        ex = [x["cands"][x["victim"]]["d"]
              - min(c["d"] for c in x["cands"].values()) for x in sub]
        out[st] = {
            "n": len(sub), "share%": r(pct(len(sub), len(recs)), 1),
            "same%": r(pct(same, len(sub)), 1),
            "near%": d["min%"], "dist.pct": d["pctile"],
            "perp.min%": p["min%"], "perp.pct": p["pctile"],
            "excess p50": r(med(ex), 2), "far%": r(pct(
                sum(1 for e in ex if e > FAR_EXCESS), len(ex)), 1),
        }
    return out


# ---------------------------------------------------------------------------
# M3 -- ASSIGNMENT vs ADVANCE, CAUSE AND EFFECT
# ---------------------------------------------------------------------------

def depth_pct_in_army(fight, owner, t, victim, axis):
    """Where the victim sits in ITS OWN army along the threat axis.

    0 = the frontmost enemy (closest to the shooting side), 1 = the deepest.
    Projected on the same army-level axis the pick metrics use, so "deep
    target" and "across the line" are measured in one frame of reference.
    """
    proj = []
    vp = None
    for uid, (x, y, o, _hp) in fight.frame_at(t).items():
        if o == owner:
            continue
        p = fight.pos(uid, t) or (x, y)
        s = p[0] * axis[0] + p[1] * axis[1]
        proj.append(s)
        if uid == victim:
            vp = s
    if vp is None or len(proj) < 2:
        return None
    return pctile_of(proj, vp)


def m3(fight, owner, reach, recs, lags):
    """Do deep riders target deep enemies, and which one leads?

    Two per-rider signals, sampled at the rider's own shots:
      assign  the victim's depth percentile in the enemy army (above)
      adv     how far the rider is AHEAD OF ITS OWN ARMY along the axis
      pen     how far inside its own reach lip its nearest enemy is

    The cause question is settled by lag: correlate `assign` at the shot with
    `adv` measured `lag` seconds later. A peak at POSITIVE lag means the
    assignment came first and the ride-in followed (assignment drives depth);
    a peak at NEGATIVE lag means the rider was already deep when it picked
    (depth drives assignment). Reported over the whole lag sweep rather than
    at one lag, because a single correlation cannot distinguish the two.
    """
    lip = reach          # canReach; the lip statements below use it as given
    pairs = []           # (t, rider, assign, adv, pen)
    for rec in recs:
        if rec["axis"] is None:
            continue
        a = depth_pct_in_army(fight, owner, rec["t"], rec["victim"], rec["axis"])
        if a is None:
            continue
        c0, _ec = centroids(fight, owner, rec["t"])
        adv = ((rec["sx"] - c0[0]) * rec["axis"][0]
               + (rec["sy"] - c0[1]) * rec["axis"][1])
        pen = lip - min(c["d"] for c in rec["cands"].values())
        pairs.append((rec["t"], rec["shooter"], a, adv, pen))
    if len(pairs) < 8:
        return {}

    def adv_at(rider, t):
        p = fight.pos(rider, t)
        if p is None:
            return None
        ax = threat_axis(fight, owner, t)
        c0, _ = centroids(fight, owner, t)
        if ax is None or c0 is None:
            return None
        return (p[0] - c0[0]) * ax[0] + (p[1] - c0[1]) * ax[1]

    lagrow = {}
    for lag in lags:
        xs, ys = [], []
        for t, rider, a, _adv, _pen in pairs:
            tt = t + lag
            if tt < 0 or tt > fight.end_t:
                continue
            av = adv_at(rider, tt)
            if av is None:
                continue
            xs.append(a)
            ys.append(av)
        lagrow[lag] = (r(spearman(xs, ys), 3), len(xs))

    # Per-rider aggregate: is a rider that rides deep a rider that was given
    # deep targets? One point per rider, so a single very active unit cannot
    # carry the shot-level correlation.
    byr = defaultdict(list)
    for _t, rider, a, adv, pen in pairs:
        byr[rider].append((a, adv, pen))
    ra = [mean([x[0] for x in v]) for v in byr.values() if len(v) >= 3]
    rd = [max(x[1] for x in v) for v in byr.values() if len(v) >= 3]
    rp = [max(x[2] for x in v) for v in byr.values() if len(v) >= 3]
    return {
        "n_shots": len(pairs), "n_riders": len(ra),
        "assign.p50": r(med([p[2] for p in pairs]), 3),
        "assign.p90": r(q([p[2] for p in pairs], 0.9), 3),
        "same_shot_rho(assign,adv)": r(spearman([p[2] for p in pairs],
                                                [p[3] for p in pairs]), 3),
        "same_shot_rho(assign,pen)": r(spearman([p[2] for p in pairs],
                                                [p[4] for p in pairs]), 3),
        "rider_rho(mean assign, max adv)": r(spearman(ra, rd), 3),
        "rider_rho(mean assign, max pen)": r(spearman(ra, rp), 3),
        "lags": {str(k): v for k, v in lagrow.items()},
    }


# ---------------------------------------------------------------------------
# M4 -- RIDE-IN ANATOMY
# ---------------------------------------------------------------------------

def m4(fight, owner, reach, recs, cycle, walk, top=5):
    """The deepest individual units of one side, one row each.

    `pen_max` is how far inside its own reach lip the unit's nearest enemy ever
    got -- the ride-in, in the units the depth report uses. Everything else on
    the row is what was happening around that instant, and each column exists
    to kill one explanation of the ride:

      fire10 / exp10   launches in the 10 s BEFORE the peak against the number
                       the unit's own reload would produce. A rider that is
                       firing on cooldown while it advances is doing something
                       different from one that has gone quiet and walked.
      gap_pre          seconds since its last launch at the peak.
      k@peak           enemies inside reach at the peak -- whether it had
                       anything to shoot at all.
      spd/walk         its own mean speed over the 3 s before the peak against
                       its dat walk speed: is it walking, or being shoved?
      aim(near/vic/cen) median angle, degrees, between its velocity and the
                       direction to its nearest enemy / its current victim /
                       the enemy centroid, over the moving frames of that
                       window. This is the cause test at the individual level:
                       a rider closing ON ITS ASSIGNED TARGET has aim(vic)
                       near zero and aim(near) larger.
      assign@peak      its victim's depth percentile in the enemy army.
      recede           pen at its last frame minus pen_max: negative means it
                       came back out.

    Launch bookkeeping uses the side's RAW shot list, not the resolved records,
    so a shot whose victim could not be resolved still counts as the unit
    having fired -- otherwise a quiet rider and an unresolvable one look alike.
    """
    raw = defaultdict(list)
    for s in fight.shots:
        if s["owner"] == owner:
            raw[s["shooter"]].append(s["t"])
    for v in raw.values():
        v.sort()
    shots_by = defaultdict(list)
    for rec in recs:
        shots_by[rec["shooter"]].append(rec)
    deaths = {}
    for e in sorted(fight.damage_all, key=lambda e: e["t"]):
        if e.get("kill"):
            deaths.setdefault(e["victim"], e["t"])

    prof = defaultdict(list)
    for t, fr in fight.frames:
        foes = [(x, y) for (x, y, o, _h) in fr.values() if o != owner]
        if not foes:
            continue
        for uid, (x, y, o, _h) in fr.items():
            if o != owner:
                continue
            dmin = min(math.hypot(fx - x, fy - y) for fx, fy in foes)
            prof[uid].append((t, reach - dmin, dmin))
    best = {uid: max(v, key=lambda z: z[1]) for uid, v in prof.items() if v}
    order = sorted(best.items(), key=lambda kv: -kv[1][1])[:top]

    rows = []
    for uid, (tpk, pen, dmin) in order:
        mine = sorted(shots_by.get(uid, []), key=lambda x: x["t"])
        allt = raw.get(uid, [])
        before = [x for x in mine if x["t"] <= tpk]
        near = min(mine, key=lambda x: abs(x["t"] - tpk)) if mine else None
        assign = None
        if near and near["axis"] is not None:
            assign = depth_pct_in_army(fight, owner, near["t"],
                                       near["victim"], near["axis"])
        vic = before[-1]["victim"] if before else None

        # motion over the 3 s run-up: speed, and what it was aimed at
        # The assignment it was actually carrying while it walked: its last
        # victim before the peak if that unit is still alive at the peak,
        # otherwise the victim of its first shot AFTER it (a rider whose target
        # died mid-ride is not walking toward a corpse).
        if vic is not None and (hp_at(fight, vic, tpk) or 0) <= 0:
            after = [x for x in mine if x["t"] > tpk]
            vic = after[0]["victim"] if after else None
        seg, prev = [], None
        an, av, ac = [], [], []
        for t, fr in fight.frames:
            if t < tpk - 3.0 or t > tpk + 1e-9 or uid not in fr:
                continue
            p = (fr[uid][0], fr[uid][1])
            if prev is not None:
                dt = t - prev[0]
                step = math.hypot(p[0] - prev[1][0], p[1] - prev[1][1])
                if dt > 0:
                    seg.append(step / dt)
                if step > rff.STEP_TILES:
                    hv = unit_vec(prev[1][0], prev[1][1], p[0], p[1])
                    foes = [(u2, fr[u2][0], fr[u2][1])
                            for u2 in fr if fr[u2][2] != owner]
                    if hv and foes:
                        nf = min(foes, key=lambda f: math.hypot(
                            f[1] - p[0], f[2] - p[1]))
                        for tgt, sink in (((nf[1], nf[2]), an),
                                          (fight.pos(vic, t) if vic else None, av),
                                          (centroids(fight, owner, t)[1], ac)):
                            if not tgt:
                                continue
                            d = unit_vec(p[0], p[1], tgt[0], tgt[1])
                            if d:
                                sink.append(math.degrees(math.acos(max(
                                    -1.0, min(1.0, hv[0] * d[0] + hv[1] * d[1])))))
            prev = (t, p)

        my_death = deaths.get(uid)
        last_pen = prof[uid][-1][1]
        rows.append({
            "unit": uid, "t_peak": r(tpk, 1), "pen_max": r(pen, 2),
            "dmin": r(dmin, 2), "shots": len(allt),
            "fire10": sum(1 for t in allt if tpk - 10 <= t <= tpk),
            "exp10": r(10.0 / cycle, 1),
            "gap_pre": r(tpk - max([t for t in allt if t <= tpk], default=0.0), 2)
            if allt and min(allt) <= tpk else None,
            "k@peak": sum(1 for f in living_enemies(fight, owner, tpk)
                          if math.hypot(f[1] - (fight.pos(uid, tpk) or (0, 0))[0],
                                        f[2] - (fight.pos(uid, tpk) or (0, 0))[1])
                          <= reach),
            "spd": r(mean(seg), 2), "walk": r(walk, 2),
            "aim(near)": r(med(an), 0), "aim(vic)": r(med(av), 0),
            "aim(cen)": r(med(ac), 0), "aim n": len(an),
            "assign@peak": r(assign, 2),
            "recede": r(last_pen - pen, 2),
            "died_at": r(my_death - tpk, 1) if my_death else None,
        })
    return rows


def m4b(fight, owner, cycle, recs):
    """WHEN a side closes, binned by where each unit is in its own fire cycle.

    One row per bucket over every 0.1 s unit-step of the side. `rad` is the
    unit's own closing speed along the threat axis, + = toward the enemy.

    The bucket is the unit's launch gap at that instant -- how long since it
    last fired, in units of its own reload -- crossed with whether the victim
    of its most recent shot is dead. Between them these separate the two
    stories the ride-in could be: a unit that advances WHILE trading (closure
    concentrated in the on-cooldown buckets) is executing an approach; a unit
    that advances only after its target died or after it has gone quiet for
    several cycles is walking because it has nothing to shoot, which is a
    re-acquisition behaviour and not a targeting one.
    """
    last_shot, last_vic = {}, {}
    ev = defaultdict(list)
    for rec in recs:
        ev[rec["shooter"]].append((rec["t"], rec["victim"]))
    for v in ev.values():
        v.sort()
    deaths = {}
    for e in sorted(fight.damage_all, key=lambda e: e["t"]):
        if e.get("kill"):
            deaths.setdefault(e["victim"], e["t"])

    buckets = defaultdict(list)
    prev = None
    for t, fr in fight.frames:
        ax = threat_axis(fight, owner, t)
        if ax is None:
            prev = (t, fr)
            continue
        if prev is not None:
            dt = t - prev[0]
            for uid, (x, y, o, _h) in fr.items():
                if o != owner or uid not in prev[1] or dt <= 0:
                    continue
                px, py = prev[1][uid][0], prev[1][uid][1]
                rad = ((x - px) * ax[0] + (y - py) * ax[1]) / dt
                fired = [z for z in ev.get(uid, ()) if z[0] <= t]
                if not fired:
                    key = "never fired"
                    vd = False
                else:
                    gap = t - fired[-1][0]
                    dt_v = deaths.get(fired[-1][1])
                    vd = dt_v is not None and dt_v <= t
                    key = ("<=1 cycle" if gap <= cycle else
                           "1-2 cycles" if gap <= 2 * cycle else ">2 cycles")
                buckets[(key, vd)].append(rad)
        prev = (t, fr)
    out = {}
    order = ["never fired", "<=1 cycle", "1-2 cycles", ">2 cycles"]
    for key in order:
        for vd in (False, True):
            v = buckets.get((key, vd))
            if not v:
                continue
            out[f"{key} / victim {'dead' if vd else 'alive'}"] = {
                "n": len(v), "rad p50": r(med(v), 3),
                "close%": r(pct(sum(1 for x in v if x > 0.05), len(v)), 1),
                "back%": r(pct(sum(1 for x in v if x < -0.05), len(v)), 1),
            }
    return out


# ---------------------------------------------------------------------------
# M5 -- NULL MODELS
# ---------------------------------------------------------------------------

def _argmin(cands, key, among=None):
    pool = [c for c in (among if among is not None else cands.values())
            if c.get(key) is not None]
    return min(pool, key=lambda c: (c[key], c["id"]))["id"] if pool else None


def _point(cid):
    return {cid: 1.0} if cid is not None else {}


def _uniform(ids):
    return {i: 1.0 / len(ids) for i in ids} if ids else {}


def rule_distributions(recs):
    """Each rule as a PROBABILITY over the shot's candidates, TEACHER-FORCED.

    A distribution rather than a single prediction, so a deterministic rule and
    a stochastic one are scored by the same two numbers: the mass the rule puts
    on the victim the shot actually went to (its expected accuracy), and the
    excess distribution its own picks would produce (the candidate excesses,
    weighted by the rule's own probabilities). The stochastic family is in here
    because every deterministic rule tested caps out near the observed nearest%
    -- if the tape's choice carries real dispersion, only a rule that carries
    dispersion can reproduce it, and one that does must be measured on the same
    scale as one that does not.

    Persistence rules are given the shooter's REAL previous victim rather than
    their own previous prediction. Free-running would compound a rule's errors
    and measure error accumulation as much as the rule; teacher forcing asks
    the question that matters -- given the state the shooter was actually in,
    does the rule reproduce this pick? -- and makes the accuracy and the excess
    distribution two readings of the same object.

    No rule here carries a fitted constant. K = 2, 3 is a sweep, not a fit, and
    both are reported.
    """
    out = defaultdict(list)
    for rec in recs:
        C = rec["cands"]
        ids = list(C)
        nearest = _argmin(C, "d")
        openc = [c for c in C.values() if not c["covered"]]
        near_open = _argmin(C, "d", among=openc) or nearest
        minperp = _argmin(C, "perp") or nearest
        minang = _argmin(C, "ang") or nearest
        by_d = sorted(ids, key=lambda i: (C[i]["d"], i))
        pv = rec["prev"]

        d = {
            "nearest": _point(nearest),
            "nearest-uncovered (T1)": _point(near_open),
            "min-perp": _point(minperp),
            "min-ang": _point(minang),
            "persist->nearest": _point(pv if pv in C else nearest),
            "persist->perp": _point(pv if pv in C else minperp),
            "persist(open)->perp": _point(
                pv if (pv in C and not C[pv]["covered"]) else minperp),
            "rand: uniform in reach": _uniform(ids),
            "rand: uniform uncovered": _uniform(
                [c["id"] for c in openc] or ids),
            "rand: 1/rank": {i: 1.0 / (n + 1) for n, i in enumerate(by_d)},
            "rand: 1/dist": {i: 1.0 / max(C[i]["d"], 1e-6) for i in ids},
        }
        for K in (2, 3):
            byperp = sorted([c for c in C.values() if c["perp"] is not None],
                            key=lambda c: (c["perp"], c["id"]))[:K]
            d[f"nearest of {K} across"] = _point(
                _argmin(C, "d", among=byperp) or nearest)
            d[f"rand: {K} nearest"] = _uniform(by_d[:K])
        for name, dist in d.items():
            tot = sum(dist.values())
            out[name].append((rec, {k: v / tot for k, v in dist.items()}
                              if tot else {}))
    return out


def m5(recs):
    """Accuracy AND the excess distribution each rule produces.

    The E15c lesson is that a rule can score well per pick and still generate
    the wrong population, so every rule is reported both ways: the mass it puts
    on the victim the shot actually went to, and what its own picks look like
    as a distribution of `excess` -- how much further than the nearest
    reachable enemy it shoots. A rule that matches the tape has to reproduce
    the OBSERVED row's excess p50 / p90 / far%, not just its accuracy.

    `acc far%` is the same accuracy restricted to the shots the tape itself
    fired past a nearer body (excess > 0.5). It is the column a nearest-first
    rule cannot win by construction, and the one a positional rule was supposed
    to.
    """
    obs_ex = [rec["cands"][rec["victim"]]["d"]
              - min(c["d"] for c in rec["cands"].values()) for rec in recs]
    far_idx = [i for i, e in enumerate(obs_ex) if e > FAR_EXCESS]
    rows = [{
        "rule": "OBSERVED", "n": len(recs), "acc%": 100.0,
        "acc far%": 100.0, "near%": r(pct(sum(1 for e in obs_ex if e <= TIE),
                                          len(obs_ex)), 1),
        "ex p50": r(med(obs_ex), 2), "ex p90": r(q(obs_ex, 0.9), 2),
        "ex mean": r(mean(obs_ex), 2),
        "far%": r(pct(len(far_idx), len(obs_ex)), 1),
    }]
    for name, preds in rule_distributions(recs).items():
        acc = mean([dist.get(rec["victim"], 0.0) for rec, dist in preds])
        accf = mean([preds[i][1].get(recs[i]["victim"], 0.0) for i in far_idx]) \
            if far_idx else None
        wex, wnear, wfar, tot = [], 0.0, 0.0, 0.0
        for rec, dist in preds:
            dmin = min(c["d"] for c in rec["cands"].values())
            for cid, p in dist.items():
                e = rec["cands"][cid]["d"] - dmin
                wex.append((e, p))
                wnear += p * (e <= TIE)
                wfar += p * (e > FAR_EXCESS)
                tot += p
        wex.sort()
        cum, p50, p90 = 0.0, None, None
        for e, p in wex:
            cum += p
            if p50 is None and cum >= 0.5 * tot:
                p50 = e
            if p90 is None and cum >= 0.9 * tot:
                p90 = e
        rows.append({
            "rule": name, "n": len(preds),
            "acc%": r(100 * acc, 1),
            "acc far%": r(100 * accf, 1) if accf is not None else None,
            "near%": r(100 * wnear / tot, 1) if tot else None,
            "ex p50": r(p50, 2), "ex p90": r(p90, 2),
            "ex mean": r(sum(e * p for e, p in wex) / tot, 2) if tot else None,
            "far%": r(100 * wfar / tot, 1) if tot else None,
        })
    return rows


# ---------------------------------------------------------------------------
# M6 -- plannedDamage SENSITIVITY (engine only)
# ---------------------------------------------------------------------------

def m6(fight, owner, reach, dmg, claims):
    """What the all-covered fallback costs to the failed-roll over-count.

    The engine books `plannedDamage` = the full post-armor damage on EVERY
    projectile, including one whose accuracy roll has already failed and which
    (with R5D1.reducedDamageHits off) will apply nothing. Coverage is therefore
    over-counted on any side with accuracy < 100. This re-runs exactly the
    engine's own arithmetic three times, changing only what a failed-roll
    projectile is worth -- full (what ships), half (what the tape's mechanic
    would make it worth) and zero (what it actually applies today) -- and
    reports the two rates that decide whether the fix matters:

      fallback%  every reachable enemy is covered, so T1's `best || primary`
                 fires and the shot goes to a victim it believes is dead
      divert%    the nearest reachable enemy is covered but some other is not,
                 so T1 sends the shot elsewhere

    `probe fallback%` is the engine's OWN answer for the same shots, read off
    `coveredDamageOn` at launch. It validates the reconstruction: the two
    disagree only where the rebuild's shot list differs from sim.projectiles.
    """
    ss = sorted([s for s in fight.shots if s["owner"] == owner],
                key=lambda s: s["t"])
    if not ss:
        return {}
    nfail = sum(1 for s in ss if failed_roll(s))
    probe_n = probe_fb = 0
    for s in ss:
        if s.get("covered") is None or s.get("target_hp") is None:
            continue
        probe_n += 1
        probe_fb += int(s["target_hp"] > 0 and s["covered"] >= s["target_hp"])

    out = {"shots": len(ss), "failed_roll%": r(pct(nfail, len(ss)), 1),
           "probe fallback%": r(pct(probe_fb, probe_n), 1) if probe_n else None}

    # PROBE-ANCHORED re-weighting. The rebuild below runs on hp read from the
    # 10 Hz stream, which is stale-HIGH and so makes coverage harder to
    # trigger: its absolute rates are a LOWER BOUND on the engine's own (the
    # `probe fallback%` column, which is exact). The delta the question asks
    # for does not have to inherit that bias. For each shot the rebuild is run
    # twice -- every projectile at full weight, and failed-roll projectiles at
    # `w` -- and only the DIFFERENCE is subtracted from the engine's exact
    # `covered`. The baseline is then the engine's own arithmetic and the
    # correction is the exactly identified failed-roll contribution, with the
    # stale-hp bias cancelling between the two rebuilds.
    cov_full = Cover(ss, dmg, claims=claims)
    for lbl, mult in (("half", 0.5), ("zero", 0.0)):
        def wz(s2, m=mult):
            base = s2.get("planned") or dmg
            return base * m if failed_roll(s2) else base
        cov_w = Cover(ss, dmg, weight=wz, claims=claims)
        n2 = fb2 = 0
        for idx, s in enumerate(ss):
            v = target_of(s)
            if v is None or s.get("covered") is None or s.get("target_hp") is None:
                continue
            n2 += 1
            imp = s["impact_t"]
            delta = cov_full.on(v, s["t"], idx, imp) - cov_w.on(v, s["t"], idx, imp)
            fb2 += int(s["target_hp"] > 0
                       and (s["covered"] - delta) >= s["target_hp"])
        out[f"probe fallback% ({lbl})"] = r(pct(fb2, n2), 1) if n2 else None
    for lbl, mult in (("full", 1.0), ("half", 0.5), ("zero", 0.0)):
        def w(s, m=mult):
            base = s.get("planned") or dmg
            return base * m if failed_roll(s) else base
        cov = Cover(ss, dmg, weight=w, claims=claims)
        n = fb = dv = vc = 0
        for idx, s in enumerate(ss):
            v = target_of(s)
            if v is None:
                continue
            sx, sy = s["sx"], s["sy"]
            pool = [f for f in living_enemies(fight, owner, s["t"])
                    if math.hypot(f[1] - sx, f[2] - sy) <= reach]
            if not pool or v not in [f[0] for f in pool]:
                continue
            n += 1
            openn, nearest, nd = [], None, 1e9
            for uid, x, y, hp in pool:
                d = math.hypot(x - sx, y - sy)
                c = cov.on(uid, s["t"], idx,
                           s["t"] + d / max(s.get("speed", 7.0), 1e-6))
                covd = (hp or 0) > 0 and c >= (hp or 0)
                if not covd:
                    openn.append(uid)
                if d < nd:
                    nd, nearest = d, (uid, covd)
                if uid == v:
                    vc += int(covd)
            fb += int(not openn)
            dv += int(bool(openn) and nearest[1])
        out[f"{lbl}: n"] = n
        out[f"{lbl}: fallback%"] = r(pct(fb, n), 1) if n else None
        out[f"{lbl}: divert%"] = r(pct(dv, n), 1) if n else None
        out[f"{lbl}: victim-covered%"] = r(pct(vc, n), 1) if n else None
    return out


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def avg(rows, k, nd=3):
    v = [x[k] for x in rows if isinstance(x, dict) and x.get(k) is not None]
    return r(statistics.mean(v), nd) if v else None


def prep(fight, owner):
    full = unit_dmg(fight, owner)
    mark_strays(fight, owner, full)
    return full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-runs-dir", default="D:/AI/aoe2_golden/shots_r5e")
    ap.add_argument("--tags", default=",".join(R5_TAGS))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--m5-seeds", type=int, default=5,
                    help="engine seeds for the null-model control (M5 only)")
    ap.add_argument("--pool-reach", default="canreach",
                    choices=("canreach", "inrange"),
                    help="reach predicate defining the candidate pool")
    ap.add_argument("--section", default="all")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    sim_dir = Path(args.sim_runs_dir)
    manifest = json.loads((CALIB / "manifest.json").read_text())["fights"]
    dicts = json.loads((CALIB / "combat_dicts.json").read_text())
    want = args.tags.split(",")
    fights = [f for f in manifest if f["tag"] in want]
    fights.sort(key=lambda f: want.index(f["tag"]))
    sec = args.section
    lags = [-6.0, -4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0, 6.0, 8.0]

    out = {"fights": {}}
    for meta in fights:
        tag = meta["tag"]
        tape = load_tape(meta)
        engines = [e for e in (load_engine(sim_dir, meta, s)
                               for s in range(1, args.seeds + 1)) if e]
        rec = {"tape": {}, "engine": {}}
        out["fights"][tag] = rec
        sides = [meta["side1"], meta["side2"]]
        du = {s["owner"]: dicts[f"{s['civ']}|{s['slug']}"] for s in sides}

        for s in sides:
            o = s["owner"]
            other = sides[1 - sides.index(s)]["owner"]
            u, ou = du[o], du[other]
            key = f"{o}:{SHORT.get(s['slug'], s['slug'])}"
            lipr = engine_reach(u, ou)
            reach = lipr if args.pool_reach == "inrange" else reach_tiles(u, ou)
            speed = u["projectile_speed"] or 7.0
            cycle = 1.0 / u["attack_speed"]
            walk = u.get("movement_speed") or 0.0

            for sh in tape.shots_all:
                if sh["owner"] == o:
                    sh["speed"] = speed
            tfull = prep(tape, o)
            trecs = shot_records(tape, o, reach, tfull, claims=False)
            rec["tape"].setdefault("m1", {})[key] = m1(trecs)
            rec["tape"].setdefault("m2", {})[key] = m2(trecs)
            if tag == HCA_HC:
                rec["tape"].setdefault("m3", {})[key] = m3(
                    tape, o, lipr, trecs, lags)
                rec["tape"].setdefault("m4", {})[key] = m4(
                    tape, o, lipr, trecs, cycle, walk)
                rec["tape"].setdefault("m4b", {})[key] = m4b(
                    tape, o, cycle, trecs)
            rec["tape"].setdefault("m5", {})[key] = m5(trecs)

            em1, em2, em3, em6, em4b = [], [], [], [], []
            em4, em5 = None, None
            for i, e in enumerate(engines):
                for sh in e.shots_all:
                    if sh["owner"] == o:
                        sh["speed"] = speed
                d = prep(e, o)
                er = shot_records(e, o, reach, d, claims=True)
                em1.append(m1(er))
                em2.append(m2(er))
                em6.append(m6(e, o, reach, d, claims=True))
                if tag == HCA_HC:
                    em3.append(m3(e, o, lipr, er, lags))
                    if em4 is None:
                        em4 = m4(e, o, lipr, er, cycle, walk)
                    em4b.append(m4b(e, o, cycle, er))
                if i < args.m5_seeds:
                    em5 = m5(er) if em5 is None else em5
            def pool(rows):
                ks = set()
                for x in rows:
                    ks |= set(x)
                return {k: avg(rows, k) for k in ks if k != "lags"}
            rec["engine"]["m1"] = rec["engine"].get("m1", {})
            rec["engine"]["m1"][key] = pool(em1)
            rec["engine"]["m6"] = rec["engine"].get("m6", {})
            rec["engine"]["m6"][key] = pool(em6)
            sub = {}
            for st in ("first", "dead_or_gone", "left_reach", "covered", "open"):
                rows = [x[st] for x in em2 if st in x]
                if rows:
                    sub[st] = pool(rows)
            rec["engine"].setdefault("m2", {})[key] = sub
            if tag == HCA_HC:
                lg = {}
                for L in lags:
                    vs = [x["lags"][str(L)][0] for x in em3
                          if x.get("lags") and x["lags"][str(L)][0] is not None]
                    lg[str(L)] = (r(mean(vs), 3), len(vs))
                base = pool(em3)
                base["lags"] = lg
                rec["engine"].setdefault("m3", {})[key] = base
                rec["engine"].setdefault("m4", {})[key] = em4 or []
                sub4 = {}
                for bk in set().union(*[set(x) for x in em4b]) if em4b else []:
                    rows4 = [x[bk] for x in em4b if bk in x]
                    sub4[bk] = pool(rows4)
                rec["engine"].setdefault("m4b", {})[key] = sub4
            if em5:
                rec["engine"].setdefault("m5", {})[key] = em5

    def keys_of(tag):
        return list(out["fights"][tag]["tape"]["m1"].keys())

    # ---- M1 ---------------------------------------------------------------
    if sec in ("all", "m1"):
        rows = []
        for tag in want:
            for k in keys_of(tag):
                for src in ("tape", "engine"):
                    x = out["fights"][tag][src]["m1"][k]
                    rows.append({
                        "fight": tag.replace("__vs__", " v "), "side": k,
                        "src": "T" if src == "tape" else "E",
                        "n": x["n"], "k": x["k_med"], "drop%": x["drop%"],
                        "dist.pct": x["dist.pct"], "near%": x["dist.min%"],
                        "perp.pct": x["perp.pct"], "perp.min%": x["perp.min%"],
                        "perpS.pct": x["perpS.pct"],
                        "min%rand": x["min%_rand"],
                        "ang.n": x["ang.n"], "ang.pct": x["ang.pct"],
                        "rho(d,perp)": x["rho(d,perp)"],
                        "ex p50": x["excess p50"], "ex p90": x["excess p90"],
                        "far%": x["far%"],
                    })
        table(rows, list(rows[0].keys()),
              "M1. Chosen victim's percentile in the reachable pool "
              "(0 = the minimum, 0.5 = random null)")

    # ---- M2 ---------------------------------------------------------------
    if sec in ("all", "m2"):
        rows = []
        for tag in want:
            for k in keys_of(tag):
                for src in ("tape", "engine"):
                    for st, x in out["fights"][tag][src]["m2"][k].items():
                        rows.append({
                            "fight": tag.replace("__vs__", " v "), "side": k,
                            "src": "T" if src == "tape" else "E",
                            "prev victim": st, "n": x["n"],
                            "share%": x["share%"], "same%": x["same%"],
                            "near%": x["near%"], "dist.pct": x["dist.pct"],
                            "perp.min%": x["perp.min%"],
                            "perp.pct": x["perp.pct"],
                            "ex p50": x["excess p50"], "far%": x["far%"],
                        })
        table(rows, list(rows[0].keys()),
              "M2. Pick structure conditioned on the previous victim's state")

    # ---- M3 ---------------------------------------------------------------
    if sec in ("all", "m3") and HCA_HC in want:
        rows = []
        for k in keys_of(HCA_HC):
            for src in ("tape", "engine"):
                x = out["fights"][HCA_HC][src].get("m3", {}).get(k)
                if not x:
                    continue
                row = {"side": k, "src": "T" if src == "tape" else "E",
                       "shots": x["n_shots"], "riders": x["n_riders"],
                       "rho(a,adv)": x["same_shot_rho(assign,adv)"],
                       "rho(a,pen)": x["same_shot_rho(assign,pen)"],
                       "rider rho(a,adv)": x["rider_rho(mean assign, max adv)"],
                       "rider rho(a,pen)": x["rider_rho(mean assign, max pen)"]}
                for L in lags:
                    row[f"L{L:+.0f}"] = x["lags"][str(L)][0]
                rows.append(row)
        if rows:
            table(rows, list(rows[0].keys()),
                  "M3. HCA v HC -- assignment depth vs the shooter's own "
                  "advance. L+x = corr(assign now, advance x s LATER)")

    # ---- M4 ---------------------------------------------------------------
    if sec in ("all", "m4") and HCA_HC in want:
        rows = []
        for k in keys_of(HCA_HC):
            for src in ("tape", "engine"):
                for x in out["fights"][HCA_HC][src].get("m4", {}).get(k, []):
                    rows.append({"side": k,
                                 "src": "T" if src == "tape" else "E", **x})
        if rows:
            table(rows, list(rows[0].keys()),
                  "M4. The five deepest units of each side in HCA v HC "
                  "(engine = seed 1)")

    # ---- M4b --------------------------------------------------------------
    if sec in ("all", "m4") and HCA_HC in want:
        rows = []
        for k in keys_of(HCA_HC):
            for src in ("tape", "engine"):
                for bk, x in out["fights"][HCA_HC][src].get(
                        "m4b", {}).get(k, {}).items():
                    rows.append({"side": k,
                                 "src": "T" if src == "tape" else "E",
                                 "bucket": bk, **x})
        if rows:
            table(rows, list(rows[0].keys()),
                  "M4b. HCA v HC -- closing speed along the threat axis, by "
                  "where the unit is in its own fire cycle")

    # ---- M5 ---------------------------------------------------------------
    if sec in ("all", "m5"):
        for tag in want:
            for k in keys_of(tag):
                for src in ("tape", "engine"):
                    rr = out["fights"][tag][src].get("m5", {}).get(k)
                    if not rr:
                        continue
                    table(rr, list(rr[0].keys()),
                          f"M5. {tag.replace('__vs__', ' v ')} {k} "
                          f"[{'tape' if src == 'tape' else 'engine seed 1'}] "
                          "-- null models: accuracy AND excess distribution")

    # ---- M6 ---------------------------------------------------------------
    if sec in ("all", "m6"):
        rows = []
        for tag in want:
            for k in keys_of(tag):
                x = out["fights"][tag]["engine"]["m6"][k]
                if not x:
                    continue
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "shots": x.get("shots"),
                    "fail%": x.get("failed_roll%"),
                    "probe fb%": x.get("probe fallback%"),
                    "probe fb% half": x.get("probe fallback% (half)"),
                    "probe fb% zero": x.get("probe fallback% (zero)"),
                    "fb% full": x.get("full: fallback%"),
                    "fb% half": x.get("half: fallback%"),
                    "fb% zero": x.get("zero: fallback%"),
                    "div% full": x.get("full: divert%"),
                    "div% half": x.get("half: divert%"),
                    "div% zero": x.get("zero: divert%"),
                    "vcov% full": x.get("full: victim-covered%"),
                    "vcov% zero": x.get("zero: victim-covered%"),
                })
        table(rows, list(rows[0].keys()),
              "M6. plannedDamage sensitivity -- the same engine arithmetic "
              "with a failed-roll projectile worth full / half / zero")

    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, default=str))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
