"""R5c: the two ranged residuals R5b did not close, measured shot by shot.

Round 5b gave the engine a mechanistic ranged fire model (stop-to-fire,
ballistic lead, in-flight damage accounting with an arrival-order qualifier,
approach margin). Two residuals survived it, and this module measures ONLY
those two, from the tapes:

  Q1  The tape's hand cannoneer wastes exactly 0.0% of its shots on targets
      that die in flight, in all three of its recordings. The post-R5b engine
      HC still wastes 11.8-21.5%. What is the tape's HC doing per shot that
      the engine's is not?

  Q2  The tape hits MOVING targets 50-79% of the time; the engine's ballistic
      lead only manages 12-35%. Is the tape's aim model better, or are the
      tape's targets simply better behaved (they keep going) than the engine's
      (which halt mid-flight because of our own stop-to-fire)?

  Q0  (added mid-round, and it changes the answer to both) A MISSED shot in
      AoE2:DE is not a no-op: it still deals damage if it strikes a unit. The
      engine's R5b D2 grounds a failed accuracy roll at zero effect. Q0
      measures the rule off the tapes rather than assuming it -- the exact
      arithmetic, which units it applies to, whether the reduced hit lands on
      the intended target or on a neighbour -- because every Q1 and Q2 number
      that treats a landed damage event as "a hit on the unit I aimed at" is
      wrong by exactly that mechanism if it does not.

MEASUREMENT ONLY. Nothing under apps/website/static/js/engine/ is touched or
imported; the engine side is read from the shot dumps
(tools/simjs/ranged_shot_dump.mjs), the tape side from the recordings, and
every statistic is computed by ONE function over the normalised ``Fight``
object that tools/simjs/ranged_fire_forensics.py already builds from either
source. A tape number and an engine number here are the same code.

WHAT IS REUSED AND WHAT IS NEW
------------------------------
Reused verbatim from ranged_fire_forensics: Fight (frames/damage/shots/sides,
the wipe-time cut, interpolated positions), load_tape, load_engine, the
shot->damage pairing (residual 0.0000 s over 1,147 tape pairs) and the
aim-target inference (97.3% against tape hits, 99.3% against the engine's
recorded true target). New here: per-shot target CHOICE, volley structure
against two null models, in-flight coverage/lethality, a classification of
every wasted ENGINE shot, and the aim-model residual fit.

TARGET OF A SHOT. The engine dump records the true target, so the engine side
uses it. The tape has to infer, and uses exactly the inference above. Where a
tape statistic is sensitive to a wrong inference (the coverage counts) the
same statistic is also reported over the subset whose victim the damage
pairing NAMES, so the reader can see whether the inference is carrying it.

    node tools/simjs/ranged_shot_dump.mjs --tags <the six> --seeds 20 \
        --out-dir D:/AI/aoe2_golden/shots_r5c
    PYTHONPATH=. python tools/simjs/r5c_targeting_forensics.py \
        --sim-runs-dir D:/AI/aoe2_golden/shots_r5c
    ... --section q0|q1a|q1b|q1c|q1d|q2a|q2b|q2c|q2d|pool|all
    ... --seeds 20 --json out.json

Findings: docs/calibration/r5c_targeting_forensics.md.
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

import ranged_fire_forensics as rff          # noqa: E402
from ranged_fire_forensics import (          # noqa: E402
    CALIB, R5_TAGS, SHORT, TILE, med, q, r, pct, table,
    load_tape, load_engine, physics_radius_px,
)

# One engine tick. Two launches inside this are SIMULTANEOUS: neither could
# have seen the other's projectile, because both were created in the same
# sim.step() and the in-flight accounting reads sim.projectiles at the top of
# each unit's own update.
TICK = 1.0 / 60.0

# "Was the target moving?" -- tiles/s. The tape samples positions at ~9 Hz and
# the slowest unit here (imp_elite_skirm, 0.96 tiles/s) covers ~0.11 tiles per
# sample, so 0.30 tiles/s is a third of the slowest real walk and an order of
# magnitude above position quantisation. Same bar for tape and engine.
MOVING_TILES_PER_S = 0.30

# A shot "landed on" its target if it arrived this close -- the same
# ON_TARGET_TILES the R5 report validated (p99 of a genuine tape hit's
# landing distance is 0.421 tiles).
ON_TARGET = rff.ON_TARGET_TILES

# Heading change (degrees) between the target's launch-time velocity and its
# mid-flight velocity that makes the flight a TURN rather than a kept course.
TURN_DEG = 45.0


# ---------------------------------------------------------------------------
# small shared helpers over a Fight
# ---------------------------------------------------------------------------

def target_of(shot):
    """The victim this shot was aimed at: engine truth, else tape inference."""
    t = shot.get("true_target")
    return t if t is not None else shot.get("aim")


def hp_at(fight, uid, t):
    """Last recorded hp of `uid` at or before `t` (frames are not interpolable
    in hp: it is a step function)."""
    lo, hi = 0, len(fight.frames_all) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if fight.frames_all[mid][0] <= t + 1e-9:
            u = fight.frames_all[mid][1].get(uid)
            if u is not None:
                best = u[3]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def living_enemies(fight, owner, t):
    """[(uid, x, y, hp)] of the other side alive at `t`."""
    out = []
    for uid, (x, y, o, hp) in fight.frame_at(t).items():
        if o == owner:
            continue
        p = fight.pos(uid, t)
        out.append((uid, p[0] if p else x, p[1] if p else y, hp))
    return out


def velocity(fight, uid, t, win):
    """(vx, vy) tiles/s over the `win` seconds ending at `t`."""
    a = fight.pos(uid, t - win)
    b = fight.pos(uid, t)
    if a is None or b is None or win <= 0:
        return (0.0, 0.0)
    return ((b[0] - a[0]) / win, (b[1] - a[1]) / win)


def speed_at(fight, uid, t, win=0.25):
    vx, vy = velocity(fight, uid, t, win)
    return math.hypot(vx, vy)


def unit_dmg(fight, owner):
    """This side's FULL per-shot damage: the largest non-killing damage value.

    Killing blows are HP-clamped in BOTH streams (R5 methodology note), so
    they are excluded -- a kill's `damage` field is the victim's remaining hp,
    not the blow. `max` rather than `mode` because a side with an accuracy
    roll produces a SECOND, smaller cluster at exactly half (see
    damage_ledger); the full value is the upper one by construction, and every
    unit here is one projectile / one application so there is no third.
    """
    vals = [float(e.get("damage") or 0) for e in fight.damage_all
            if e.get("attacker_owner") == owner and not e.get("kill")]
    if not vals:
        vals = [float(e.get("damage") or 0) for e in fight.damage_all
                if e.get("attacker_owner") == owner]
    return max(vals) if vals else 0.0


# ---------------------------------------------------------------------------
# Q0 -- THE REDUCED-DAMAGE MISS, MEASURED
# ---------------------------------------------------------------------------

def damage_class(s, full):
    """FULL / HALF / KILL? / MISS for one shot, from its paired damage event.

    HALF is decided by the damage VALUE, not by any model: over the six tapes
    the only two non-killing values any side produces are `full` and exactly
    `full/2`. A killing blow is HP-clamped, so it can only be resolved when
    the clamped value exceeds `full/2` (a half-strength blow could not have
    killed): everything below that bar is reported as KILL? rather than
    guessed.
    """
    if s["hit"] is None:
        return "MISS"
    d = float(s["hit"].get("damage") or 0)
    if s["hit"].get("kill"):
        return "FULL" if d > full / 2 + 1e-6 else "KILL?"
    if abs(d - full) < 1e-6:
        return "FULL"
    if abs(d - full / 2) < 1e-6:
        return "HALF"
    return "OTHER"


def mark_strays(fight, owner, full):
    """Stamp `dclass` and `stray` on every shot of this side.

    A shot is a STRAY when the unit the damage stream says it hit is not the
    unit the aim inference says it was aimed at. Two kinds exist and are
    separated downstream by `dclass`: a HALF stray is the mechanic (a missed
    shot that struck somebody else); a FULL stray is an aim-inference error,
    since a full-damage application is by definition a direct hit on the unit
    it was aimed at.

    Strays are excluded from every target-CHOICE statistic: a damage event on
    a neighbour tells you where a projectile ended up, not who the shooter
    picked, and counting it as a choice would manufacture spread that the
    shooter never intended.
    """
    n_half = n_stray_half = n_stray_full = 0
    for s in fight.shots_all:
        if s["owner"] != owner:
            continue
        s["dclass"] = damage_class(s, full)
        s["stray"] = bool(s["hit"] is not None and s["aim"] is not None
                          and s["hit"]["victim"] != s["aim"])
        n_half += int(s["dclass"] == "HALF")
        if s["stray"]:
            n_stray_half += int(s["dclass"] == "HALF")
            n_stray_full += int(s["dclass"] != "HALF")
    return n_half, n_stray_half, n_stray_full


def damage_ledger(fight, owner, full, acc):
    """Full vs reduced applications, and where the shots that applied nothing
    ended up.

    `landed` is every shot the pairing attached a damage event to. `half%` is
    the share of RESOLVED landed shots (KILL? excluded, since a clamped kill
    cannot be classified) that applied exactly half. `nothing_d` quantiles are
    the distance from a non-applying shot's terminal position to the NEAREST
    living enemy at that instant -- the direct readout of how far a failed
    shot scatters, against a landed shot's 0.26-0.35 tile sprite-anchor
    offset.
    """
    ss = [s for s in fight.shots if s["owner"] == owner
          and s["outcome"] != "CENSORED"]
    cnt = Counter(s["dclass"] for s in ss)
    resolved = cnt["FULL"] + cnt["HALF"]
    landed = sum(1 for s in ss if s["hit"] is not None)
    nothing = []
    for s in ss:
        if s["hit"] is not None:
            continue
        best = None
        for uid, x, y, _hp in living_enemies(fight, owner, s["impact_t"]):
            d = math.hypot(s["ix"] - x, s["iy"] - y)
            if best is None or d < best:
                best = d
        if best is not None:
            nothing.append(best)
    # DISPERSION. `land_d` is the raw landing distance to the victim, which
    # includes the constant sprite-anchor offset a landed shot always carries.
    # `scatter` removes it: |landing - (victim + anchor)|, so a full-strength
    # hit reads ~0 by construction and a reduced hit reads the distance the
    # accuracy roll actually threw the projectile. Any claim about the
    # dispersion RADIUS has to be read off `scatter`, never off `land_d`.
    ox, oy, _n, _sp = anchor_offset(fight, owner)
    land_d = defaultdict(list)
    scatter = defaultdict(list)
    for s in ss:
        if s["hit"] is None:
            continue
        p = fight.pos(s["hit"]["victim"], s["impact_t"])
        if p:
            land_d[s["dclass"]].append(math.hypot(s["ix"] - p[0], s["iy"] - p[1]))
            scatter[s["dclass"]].append(
                math.hypot(s["ix"] - ox - p[0], s["iy"] - oy - p[1]))
    # CROWDING. Whether a scattered shot can find a SECOND body is a property
    # of the enemy formation, not of the shooter: it is the distance from the
    # unit a shot came down on to that unit's own nearest ally. If that is far
    # larger than the dispersion radius plus two body radii, a shot that
    # misses cannot hit anyone else no matter how the rule is written, so the
    # near-total absence of neighbour strikes in this corpus is a statement
    # about these six recordings and cannot be generalised to a packed blob.
    crowd = []
    for s in ss:
        if s["hit"] is None:
            continue
        v = s["hit"]["victim"]
        pv = fight.pos(v, s["impact_t"])
        if pv is None:
            continue
        best = None
        for uid, x, y, _hp in living_enemies(fight, owner, s["impact_t"]):
            if uid == v:
                continue
            d = math.hypot(x - pv[0], y - pv[1])
            if best is None or d < best:
                best = d
        if best is not None:
            crowd.append(best)
    return {
        "acc": acc, "full_dmg": r(full, 2), "shots": len(ss), "landed": landed,
        "crowd_med": r(med(crowd), 3), "crowd_p10": r(q(crowd, 0.1), 3),
        "full_n": cnt["FULL"], "half_n": cnt["HALF"], "killq_n": cnt["KILL?"],
        "other_n": cnt["OTHER"],
        "half%_resolved": r(pct(cnt["HALF"], resolved), 1) if resolved else None,
        "half%_shots": r(pct(cnt["HALF"], len(ss)), 1) if ss else None,
        "landed%": r(pct(landed, len(ss)), 1) if ss else None,
        "stray_half_n": sum(1 for s in ss if s["stray"] and s["dclass"] == "HALF"),
        "stray_full_n": sum(1 for s in ss if s["stray"] and s["dclass"] != "HALF"),
        "land_d_full": r(med(land_d["FULL"]), 3),
        "land_d_half": r(med(land_d["HALF"]), 3),
        "land_d_half_p90": r(q(land_d["HALF"], 0.9), 3),
        "scatter_full": r(med(scatter["FULL"]), 3),
        "scatter_half": r(med(scatter["HALF"]), 3),
        "scatter_half_p90": r(q(scatter["HALF"], 0.9), 3),
        "scatter_half_max": r(max(scatter["HALF"]), 3) if scatter["HALF"] else None,
        "nothing_n": len(nothing),
        "nothing_d_med": r(med(nothing), 3),
        "nothing_d_p90": r(q(nothing, 0.9), 3),
        "nothing_d_max": r(max(nothing), 3) if nothing else None,
        # damage actually applied per shot fired, relative to a full hit --
        # the single number the engine's missing mechanic costs.
        "dmg_per_shot_x": r((cnt["FULL"] + 0.5 * cnt["HALF"]
                             + cnt["KILL?"]) / len(ss), 3) if ss else None,
    }


def reach_tiles(att_dict, def_dict):
    """BattleUnit.canReach(): attackRange + both physics radii, in tiles.

    NOT inRange() -- canReach is the test pickShotTarget() uses to decide
    whether an alternative victim exists, and it omits inRange()'s
    MELEE_RANGE_BUFFER. Using the wrong one here would mis-count exactly the
    alternatives the redirect could have taken.
    """
    return (att_dict["attack_range"] * TILE
            + physics_radius_px(att_dict)
            + physics_radius_px(def_dict)) / TILE


# ---------------------------------------------------------------------------
# Q1a -- PER-SHOT TARGET CHOICE
# ---------------------------------------------------------------------------

def target_choice(fight, owner, cycle, reach):
    """For every shot of this side: was its victim (a) the shooter's nearest
    living enemy, (b) the shooter's own previous victim, (c) untouched by any
    OTHER friendly shot in the trailing `cycle` seconds?

    `rank` is the victim's position in the shooter's nearest-first ordering at
    launch -- 1 = nearest -- taken over the enemies actually WITHIN REACH,
    since those are the choices the shooter had. The engine's
    findTarget()/pickShotTarget() acquire strictly nearest-first, so rank is
    the direct readout of how far a choice sits from that rule.

    Two nulls are carried alongside so the numbers can be read against
    something: `near%_rand` and `rank_rand` are what a shooter picking
    UNIFORMLY AT RANDOM among its reachable enemies would score on the same
    shots (mean 1/k and mean (k+1)/2 over the same per-shot k). Nearest-first
    scores near% = 100 and rank = 1 by construction; the random null is the
    other end of the scale.
    """
    ss = sorted([s for s in fight.shots
                 if s["owner"] == owner and not s.get("stray")],
                key=lambda s: s["t"])
    prev_tgt = {}
    n = nearest = same = unshared = 0
    ranks, rand_near, rand_rank, ks = [], [], [], []
    n_named = named_nearest = 0
    for s in ss:
        v = target_of(s)
        if v is None:
            continue
        foes = [f for f in living_enemies(fight, owner, s["t"])
                if math.hypot(f[1] - s["sx"], f[2] - s["sy"]) <= reach]
        if not foes:
            continue
        order = sorted(foes, key=lambda f: math.hypot(f[1] - s["sx"],
                                                      f[2] - s["sy"]))
        ids = [f[0] for f in order]
        if v not in ids:
            continue
        n += 1
        k = len(ids)
        ks.append(k)
        rand_near.append(1.0 / k)
        rand_rank.append((k + 1) / 2.0)
        rk = ids.index(v) + 1
        ranks.append(rk)
        is_near = rk == 1
        nearest += is_near
        if s["hit"] is not None:        # victim NAMED by the damage pairing
            n_named += 1
            named_nearest += is_near
        same += int(prev_tgt.get(s["shooter"]) == v)
        others = [o for o in ss
                  if o is not s and s["t"] - cycle <= o["t"] <= s["t"]
                  and target_of(o) == v]
        unshared += int(not others)
        prev_tgt[s["shooter"]] = v
    return {
        "n": n,
        "nearest%": r(pct(nearest, n), 1),
        "nearest%_named": r(pct(named_nearest, n_named), 1),
        "same_as_prev%": r(pct(same, n), 1),
        "unshared%": r(pct(unshared, n), 1),
        "rank_med": r(med(ranks), 2),
        "rank_p90": r(q(ranks, 0.9), 1),
        "rank_mean": r(statistics.mean(ranks), 2) if ranks else None,
        "in_reach_med": r(med(ks), 1),
        "nearest%_rand": r(100.0 * statistics.mean(rand_near), 1) if rand_near else None,
        "rank_rand": r(statistics.mean(rand_rank), 2) if rand_rank else None,
    }


# ---------------------------------------------------------------------------
# Q1b -- VOLLEY STRUCTURE vs TWO NULL MODELS
# ---------------------------------------------------------------------------

def volley_structure(fight, owner, cycle):
    """Bin this side's shots into consecutive `cycle`-second windows and ask
    how widely each window's shots spread over victims, against two nulls:

      NEAREST  every shot goes to its own shooter's nearest living enemy at
               launch (what a pure nearest-first engine does)
      RR       perfect round-robin: min(shots_in_window, living enemies) --
               the maximum spread physically available

    `spread` = distinct victims / RR, so 1.00 is a perfect round-robin and the
    NEAREST column says how much spread you get for free from the shooters
    simply standing in different places.
    """
    ss = [s for s in fight.shots
          if s["owner"] == owner and not s.get("stray")]
    if not ss:
        return {}
    end = fight.end_t
    nb = max(1, int(math.ceil(end / cycle)))
    obs, nearest, rr, sizes, maxdup = [], [], [], [], []
    for b in range(nb):
        t0, t1 = b * cycle, (b + 1) * cycle
        win = [s for s in ss if t0 <= s["t"] < t1]
        if len(win) < 2:
            continue
        vs, nvs = [], []
        for s in win:
            v = target_of(s)
            if v is not None:
                vs.append(v)
            foes = living_enemies(fight, owner, s["t"])
            if foes:
                nvs.append(min(foes, key=lambda f: math.hypot(
                    f[1] - s["sx"], f[2] - s["sy"]))[0])
        if not vs:
            continue
        mid = 0.5 * (t0 + t1)
        alive = len(living_enemies(fight, owner, mid))
        obs.append(len(set(vs)))
        nearest.append(len(set(nvs)))
        rr.append(min(len(win), max(alive, 1)))
        sizes.append(len(win))
        maxdup.append(Counter(vs).most_common(1)[0][1])
    if not obs:
        return {}
    sp = [o / m for o, m in zip(obs, rr) if m]
    spn = [nn / m for nn, m in zip(nearest, rr) if m]
    return {
        "windows": len(obs),
        "shots/win": r(med(sizes), 1),
        "victims_obs": r(med(obs), 1),
        "victims_nearest": r(med(nearest), 1),
        "victims_rr": r(med(rr), 1),
        "spread_obs": r(med(sp), 3),
        "spread_nearest": r(med(spn), 3),
        "maxdup_obs": r(med(maxdup), 1),
        "fit_nearest": r(med([abs(o - nn) for o, nn in zip(obs, nearest)]), 2),
        "fit_rr": r(med([abs(o - m) for o, m in zip(obs, rr)]), 2),
    }


# ---------------------------------------------------------------------------
# Q1c -- IN-FLIGHT COVERAGE / LETHALITY AWARENESS
# ---------------------------------------------------------------------------

def coverage(fight, owner, dmg, reach):
    """At the instant each shot leaves, how covered was its victim already?

    `inbound` counts this side's OTHER projectiles already in the air toward
    the same victim that will LAND FIRST -- the exact quantity R5b's
    inboundDamageOn() sums, recomputed here from the shot list so the tape can
    be asked the same question. A shot is:

      covered   its victim already had >= its own hp of friendly damage
                inbound-and-arriving-first, i.e. the shot is dead on arrival
                by construction
      doubled   the victim needed ONE shot to die (hp <= dmg) and had at least
                one other friendly shot arriving first

    `redirect%` is the positive evidence for hold-fire/reassign: shots whose
    shooter's NEAREST living enemy was already lethally covered and that went
    somewhere else anyway. `stubborn%` is the same situation resolved the
    other way (fired at the covered nearest regardless).
    """
    ss = sorted([s for s in fight.shots
                 if s["owner"] == owner and not s.get("stray")],
                key=lambda s: s["t"])
    by_tgt = defaultdict(list)
    for s in ss:
        v = target_of(s)
        if v is not None:
            by_tgt[v].append(s)

    def inbound_first(v, t, impact_t, exclude):
        """Friendly shots at `v` airborne at `t` that land before `impact_t`."""
        out = []
        for o in by_tgt.get(v, ()):
            if o is exclude:
                continue
            if o["t"] < t - TICK and o["impact_t"] > t and o["impact_t"] < impact_t:
                out.append(o)
        return out

    n = any_in = cov = dbl = 0
    redirect = stubborn = 0
    onebang = 0
    for s in ss:
        v = target_of(s)
        if v is None:
            continue
        n += 1
        hp = hp_at(fight, v, s["t"]) or 0.0
        inb = inbound_first(v, s["t"], s["impact_t"], s)
        any_in += int(bool(inb))
        cov += int(sum(o.get("planned") or dmg for o in inb) >= hp > 0)
        if hp > 0 and hp <= dmg:
            onebang += 1
            dbl += int(bool(inb))
        # nearest-covered decision
        foes = living_enemies(fight, owner, s["t"])
        if not foes:
            continue
        nf = min(foes, key=lambda f: math.hypot(f[1] - s["sx"], f[2] - s["sy"]))
        if math.hypot(nf[1] - s["sx"], nf[2] - s["sy"]) > reach:
            continue
        nhp = hp_at(fight, nf[0], s["t"]) or 0.0
        ninb = inbound_first(nf[0], s["t"], s["t"] + math.hypot(
            nf[1] - s["sx"], nf[2] - s["sy"]) / max(s.get("speed", 7.0), 1e-6), None)
        if nhp > 0 and sum(o.get("planned") or dmg for o in ninb) >= nhp:
            if v == nf[0]:
                stubborn += 1
            else:
                redirect += 1
    return {
        "n": n,
        "dmg": r(dmg, 1),
        "any_inbound%": r(pct(any_in, n), 1),
        "covered%": r(pct(cov, n), 1),
        "1shot_kills": onebang,
        "1shot_doubled%": r(pct(dbl, onebang), 1) if onebang else None,
        "redirect_n": redirect, "stubborn_n": stubborn,
        "redirect%": r(pct(redirect, redirect + stubborn), 1)
        if (redirect + stubborn) else None,
    }


# ---------------------------------------------------------------------------
# Q1d -- WHERE THE ENGINE'S WASTED SHOTS COME FROM
# ---------------------------------------------------------------------------

def waste_classes(fight, owner, dmg, reach):
    """Every wasted shot of this side, attributed to a cause.

    A shot is WASTED when its true target dies strictly between launch and
    impact. R5b's rule should have prevented that whenever the damage already
    inbound-and-arriving-first was enough to kill; so each wasted shot is
    sorted by WHICH shots actually did the killing relative to this one:

      blind        the accounting's own test was already TRUE at launch
                   (inbound-arriving-first damage >= victim hp) and the shot
                   went out anyway -- either because nothing else was
                   reachable (the `best || primary` fallback) or as a genuine
                   edge case
      same-tick    the kill needed a shot launched in the SAME engine tick:
                   neither shooter could see the other's projectile
      overtaken    the kill needed a shot launched LATER than this one that
                   nevertheless arrived first (a closer shooter's shorter
                   flight)
      cumulative   the kill was completed by later-launched, later-arriving
                   damage; this shot was genuinely useful at launch and only
                   became waste because the victim's hp fell in the meantime

    Cross-tabulated with whether ANY other reachable, not-already-lethally-
    covered enemy existed at launch (`alt`), which is the question "was there
    anywhere else to send it".
    """
    deaths = {}
    for e in sorted(fight.damage_all, key=lambda e: e["t"]):
        if e.get("kill"):
            deaths.setdefault(e["victim"], e["t"])
    ss = sorted([s for s in fight.shots if s["owner"] == owner],
                key=lambda s: s["t"])
    by_tgt = defaultdict(list)
    for s in ss:
        v = target_of(s)
        if v is not None:
            by_tgt[v].append(s)

    cls = Counter()
    alt_yes = Counter()
    n_shots = len(ss)
    n_waste = 0
    for s in ss:
        v = target_of(s)
        if v is None:
            continue
        # A shot that produced a damage event is not wasted, whatever the
        # clock says. `impact_t` is analytic (launch + distance/speed) while
        # the engine resolves on the first TICK at or after that instant, so a
        # shot that delivers its own killing blow reports a death up to 1/60 s
        # "before" its own impact. Measured on the dumps: every such overlap
        # is inside one tick and every one of them is the shot's own kill.
        if s["hit"] is not None:
            continue
        dt = deaths.get(v)
        if dt is None or not (s["t"] < dt < s["impact_t"] - 1e-9):
            continue
        n_waste += 1
        sibs = by_tgt[v]
        prior_first = [o for o in sibs if o is not s and o["t"] < s["t"] - TICK
                       and o["impact_t"] < s["impact_t"]]
        hp0 = hp_at(fight, v, s["t"]) or 0.0
        contributors = [o for o in sibs if o is not s
                        and o["impact_t"] <= dt + 1e-6 and o["impact_t"] > s["t"]]
        same_tick = [o for o in contributors if abs(o["t"] - s["t"]) <= TICK]
        later_first = [o for o in contributors
                       if o["t"] > s["t"] + TICK and o["impact_t"] < s["impact_t"]]

        if hp0 > 0 and sum(o.get("planned") or dmg for o in prior_first) >= hp0:
            k = "blind"
        elif same_tick:
            k = "same-tick"
        elif later_first:
            k = "overtaken"
        else:
            k = "cumulative"
        cls[k] += 1

        # was there anywhere else to send it?
        alt = 0
        for uid, x, y, hp in living_enemies(fight, owner, s["t"]):
            if uid == v:
                continue
            d = math.hypot(x - s["sx"], y - s["sy"])
            if d > reach:
                continue
            inb = [o for o in by_tgt.get(uid, ())
                   if o["t"] < s["t"] - TICK and o["impact_t"] > s["t"]]
            if (hp or 0) > sum(o.get("planned") or dmg for o in inb):
                alt += 1
        if alt:
            alt_yes[k] += 1
    out = {"shots": n_shots, "waste": n_waste,
           "waste%": r(pct(n_waste, n_shots), 1)}
    for k in ("blind", "same-tick", "overtaken", "cumulative"):
        out[k] = cls[k]
        out[f"{k}%"] = r(pct(cls[k], n_waste), 1) if n_waste else None
        out[f"{k}_alt%"] = r(pct(alt_yes[k], cls[k]), 1) if cls[k] else None
    return out


# ---------------------------------------------------------------------------
# Q2a -- WHAT AIM MODEL DOES THE TAPE IMPLY?
# ---------------------------------------------------------------------------

def anchor_offset(fight, owner):
    """The constant sprite-anchor vector between a landed shot's terminal
    position and its victim's position at that instant.

    Measured on HITS at victims that did NOT move during the flight, so the
    victim's position at impact is unambiguous. Every aim-model residual below
    is taken against `predicted + offset`, otherwise all models would be
    charged the same ~0.28 tile bias and their comparison compressed.
    """
    dx, dy = [], []
    for s in fight.shots:
        if s["owner"] != owner or s["hit"] is None:
            continue
        if s.get("stray") or s.get("dclass") == "HALF":
            continue
        v = s["hit"]["victim"]
        if fight.moved_between(v, s["t"], s["impact_t"]):
            continue
        p = fight.pos(v, s["impact_t"])
        if p is None:
            continue
        dx.append(s["ix"] - p[0])
        dy.append(s["iy"] - p[1])
    if not dx:
        return (0.0, 0.0, 0, None)
    ox, oy = med(dx), med(dy)
    spread = med([math.hypot(a - ox, b - oy) for a, b in zip(dx, dy)])
    return (ox, oy, len(dx), spread)


def predict_aim(fight, s, v, speed, win, cap):
    """Intercept of `v`'s velocity (measured over the trailing `win` seconds,
    scaled by `cap`) with a projectile of `speed`, from this shot's launch.

    Two fixed-point passes, the same solver shape R5b's aimPointFor() uses --
    the flight time depends on the distance to the aim point which depends on
    the flight time -- so a residual difference between tape and engine is a
    difference of INPUTS (which velocity, how much of it), not of solvers.
    """
    p = fight.pos(v, s["t"])
    if p is None:
        return None
    if win <= 0 or cap == 0:
        return p
    vx, vy = velocity(fight, v, s["t"], win)
    ax, ay = p
    for _ in range(3):
        flight = math.hypot(ax - s["sx"], ay - s["sy"]) / speed
        ax = p[0] + vx * cap * flight
        ay = p[1] + vy * cap * flight
    return (ax, ay)


AIM_MODELS = [
    ("none", 0.0, 0.0),
    ("lead@0.11s", 0.11, 1.0),
    ("lead@0.3s", 0.30, 1.0),
    ("lead@0.5s", 0.50, 1.0),
    ("lead@1.0s", 1.00, 1.0),
    ("0.5x@0.3s", 0.30, 0.5),
    ("0.75x@0.3s", 0.30, 0.75),
    ("0.5x@0.5s", 0.50, 0.5),
]


def aim_fit(fight, owner, speed, moving_only=True, hits_only=True, sink=None):
    """Residual |predicted aim point - actual landing point| per model.

    Restricted by default to HITS at victims that MOVED during the flight --
    the only shots whose landing point discriminates between the models at
    all. `oracle` is the target's true position at impact: the floor any aim
    model could reach, and the check that the anchor offset was removed
    correctly.
    """
    ox, oy, n_off, off_spread = anchor_offset(fight, owner)
    res = defaultdict(list)
    lead_ratio = []
    n = 0
    for s in fight.shots:
        if s["owner"] != owner:
            continue
        # A stray landed on a neighbour and a half-strength application was
        # DELIBERATELY scattered by the accuracy roll: neither one's landing
        # point is an aim point, so neither can be used to fit an aim model.
        if s.get("stray") or s.get("dclass") == "HALF":
            continue
        if hits_only and s["hit"] is None:
            continue
        v = s["hit"]["victim"] if s["hit"] is not None else target_of(s)
        if v is None:
            continue
        p0 = fight.pos(v, s["t"])
        p1 = fight.pos(v, s["impact_t"])
        if p0 is None or p1 is None:
            continue
        disp = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if moving_only and disp <= rff.DODGE_TILES:
            continue
        n += 1
        tx, ty = s["ix"] - ox, s["iy"] - oy
        if disp > 1e-6:
            # how far along the target's own displacement the aim point sits
            lr = ((tx - p0[0]) * (p1[0] - p0[0])
                  + (ty - p0[1]) * (p1[1] - p0[1])) / (disp * disp)
            lead_ratio.append(lr)
            if sink is not None:
                sink["lead_ratio"].append((lr, disp))
        for name, win, cap in AIM_MODELS:
            pr = predict_aim(fight, s, v, speed, win, cap)
            if pr:
                d = math.hypot(pr[0] - tx, pr[1] - ty)
                res[name].append(d)
                if sink is not None:
                    sink[name].append(d)
        od = math.hypot(p1[0] - tx, p1[1] - ty)
        res["oracle"].append(od)
        if sink is not None:
            sink["oracle"].append(od)
    out = {"n": n, "anchor_dx": r(ox, 3), "anchor_dy": r(oy, 3),
           "anchor_n": n_off, "anchor_spread": r(off_spread, 3),
           "lead_ratio_med": r(med(lead_ratio), 2),
           "lead_ratio_p10": r(q(lead_ratio, 0.1), 2),
           "lead_ratio_p90": r(q(lead_ratio, 0.9), 2)}
    for name in [m[0] for m in AIM_MODELS] + ["oracle"]:
        vals = res.get(name, [])
        out[name] = r(med(vals), 3) if vals else None
        out[f"{name}_p90"] = r(q(vals, 0.9), 3) if vals else None
        out[f"{name}_win%"] = r(pct(sum(1 for x in vals if x <= ON_TARGET),
                                    len(vals)), 1) if vals else None
    return out


# ---------------------------------------------------------------------------
# Q2b/Q2c -- WHAT THE TARGET DID DURING THE FLIGHT
# ---------------------------------------------------------------------------

def flight_behaviour(fight, s, v):
    """Classify what `v` did between this shot's launch and its impact, and
    what fraction of that flight it spent moving.

    still        not moving at launch
    kept course  moving at launch, still moving through the flight, heading
                 held within TURN_DEG
    halted       moving at launch, moving for less than half the flight
    turned       moving throughout, heading swung by more than TURN_DEG

    The split exists to separate "our aim model is wrong" from "our targets
    behave differently": a lead that is correct for a target that keeps going
    is wrong for one that stops, so if the tape's hits concentrate on
    kept-course and its misses on halted/turned, the aim rule is the same on
    both sides and the difference is behavioural.
    """
    v0 = velocity(fight, v, s["t"], 0.25)
    sp0 = math.hypot(*v0)
    dur = max(s["impact_t"] - s["t"], 1e-6)
    steps = max(2, int(dur / 0.1))
    speeds = []
    for i in range(steps):
        t = s["t"] + dur * i / (steps - 1)
        speeds.append(speed_at(fight, v, t, 0.15))
    mov_frac = sum(1 for x in speeds if x > MOVING_TILES_PER_S) / len(speeds)
    if sp0 <= MOVING_TILES_PER_S:
        return "still", mov_frac
    vm = velocity(fight, v, s["t"] + dur, min(0.25, dur))
    if mov_frac < 0.5:
        return "halted", mov_frac
    if math.hypot(*vm) > MOVING_TILES_PER_S:
        cos = (v0[0] * vm[0] + v0[1] * vm[1]) / (sp0 * math.hypot(*vm))
        if math.degrees(math.acos(max(-1.0, min(1.0, cos)))) > TURN_DEG:
            return "turned", mov_frac
    return "kept", mov_frac


def applied_lead(fight, owner):
    """ENGINE ONLY: how big a lead the engine actually applied, on EVERY shot.

    R5b's aimPointFor() offsets the aim point by `target.vel * flight`, so the
    lead it applied is (landing point - target position at launch), both of
    which the dump records. Measuring it here rather than inferring it from
    hits removes the selection effect that makes the hit-only lead ratio
    unreadable: a shot whose lead was wrong MISSES, so the leads seen among
    hits are the small ones by construction.

    CONFOUND, stated rather than hidden: for a unit with accuracy < 100 the
    same difference also contains D2's miss displacement (up to the dat
    dispersion radius) on the shots whose roll failed, so its `lead>0.05%`
    cannot fall below its miss rate. The accuracy-100 units carry the clean
    reading.
    """
    leads = []
    for s in fight.shots:
        if s["owner"] != owner or s.get("launch_tx") is None:
            continue
        leads.append(math.hypot(s["ix"] - s["launch_tx"],
                                s["iy"] - s["launch_ty"]))
    if not leads:
        return {}
    return {
        "n": len(leads),
        "lead>0.05%": r(pct(sum(1 for x in leads if x > 0.05), len(leads)), 1),
        "lead>0.30%": r(pct(sum(1 for x in leads if x > 0.30), len(leads)), 1),
        "lead_med": r(med(leads), 3),
        "lead_p90": r(q(leads, 0.9), 3),
        "lead_p99": r(q(leads, 0.99), 3),
        "lead_max": r(max(leads), 3),
    }


def mover_split(fight, owner, sink=None):
    """Hit rate by what the target did during the flight, plus the share of
    flight time the target spent moving (Q2c).

    The landed column is split DIRECT / REDUCED. A half-strength application
    is a landed damage event and the shot/damage pairing counts it as a hit,
    so a raw "hit rate" mixes the two -- and since the engine has no reduced
    hit at all (R5b D2 grounds a failed roll at zero), the raw tape number and
    the raw engine number are not the same quantity. `direct%` is.
    """
    buckets = defaultdict(lambda: [0, 0, 0])
    fracs, fracs_mv = [], []
    for s in fight.shots:
        if s["owner"] != owner or s["outcome"] == "CENSORED":
            continue
        v = target_of(s)
        if v is None:
            continue
        kind, mf = flight_behaviour(fight, s, v)
        buckets[kind][0] += 1
        buckets[kind][1] += int(s["hit"] is not None)
        buckets[kind][2] += int(s.get("dclass") == "HALF")
        fracs.append(mf)
        if kind != "still":
            fracs_mv.append(mf)
        if sink is not None:
            b = sink.setdefault(kind, [0, 0, 0])
            b[0] += 1
            b[1] += int(s["hit"] is not None)
            b[2] += int(s.get("dclass") == "HALF")
            if kind != "still":
                sink.setdefault("_mvfrac", []).append(mf)
    out = {}
    tot = sum(b[0] for b in buckets.values())
    for k in ("still", "kept", "halted", "turned"):
        n, h, hf = buckets[k]
        out[f"{k}_n"] = n
        out[f"{k}_share"] = r(pct(n, tot), 1) if tot else None
        out[f"{k}_hit%"] = r(pct(h, n), 1) if n else None
        out[f"{k}_direct%"] = r(pct(h - hf, n), 1) if n else None
    mv = sum(buckets[k][0] for k in ("kept", "halted", "turned"))
    mvh = sum(buckets[k][1] for k in ("kept", "halted", "turned"))
    mvf = sum(buckets[k][2] for k in ("kept", "halted", "turned"))
    out["mover_n"] = mv
    out["mover_hit%"] = r(pct(mvh, mv), 1) if mv else None
    out["mover_direct%"] = r(pct(mvh - mvf, mv), 1) if mv else None
    out["mover_half%"] = r(pct(mvf, mv), 1) if mv else None
    out["movefrac_med"] = r(med(fracs), 3)
    out["movefrac_med_movers"] = r(med(fracs_mv), 3)
    return out


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def avg(rows, k, nd=2):
    v = [x[k] for x in rows if isinstance(x, dict) and x.get(k) is not None]
    return r(statistics.mean(v), nd) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-runs-dir", default="D:/AI/aoe2_golden/shots_r5c_b")
    ap.add_argument("--tags", default=",".join(R5_TAGS))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--section", default="all")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    sim_dir = Path(args.sim_runs_dir)
    manifest = json.loads((CALIB / "manifest.json").read_text())["fights"]
    dicts = json.loads((CALIB / "combat_dicts.json").read_text())
    want = args.tags.split(",")
    fights = [f for f in manifest if f["tag"] in want]
    fights.sort(key=lambda f: want.index(f["tag"]))

    out = {"fights": {}}
    sec = args.section
    # Pooled-by-shooter-unit accumulators. Per fight and side the mover-hit
    # populations are 0-21 shots -- these are ranged-vs-ranged fights in which
    # 77-100% of shots are at a stationary target -- so the per-fight cells of
    # Q2a/Q2b cannot carry a conclusion on their own. The pools collect the
    # same per-shot records across all six fights, keyed by the SHOOTER's
    # unit, which is the level at which an aim rule is a property of the game
    # rather than of one recording.
    aim_pool = defaultdict(lambda: defaultdict(list))
    mv_pool = defaultdict(dict)

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
            cycle = 1.0 / u["attack_speed"]
            reach = reach_tiles(u, ou)
            speed = u["projectile_speed"] or 7.0
            for sh in tape.shots_all:
                if sh["owner"] == o:
                    sh["speed"] = speed
            tfull = unit_dmg(tape, o)
            mark_strays(tape, o, tfull)

            rec["tape"].setdefault("ledger", {})[key] = damage_ledger(
                tape, o, tfull, u["accuracy"])
            rec["tape"].setdefault("choice", {})[key] = target_choice(
                tape, o, cycle, reach)
            rec["tape"].setdefault("volley", {})[key] = volley_structure(tape, o, cycle)
            rec["tape"].setdefault("cover", {})[key] = coverage(
                tape, o, tfull, reach)
            slug = s["slug"]
            rec["tape"].setdefault("aim", {})[key] = aim_fit(
                tape, o, speed, sink=aim_pool[("tape", slug)])
            rec["tape"].setdefault("mover", {})[key] = mover_split(
                tape, o, sink=mv_pool[("tape", slug)])
            rec["tape"].setdefault("waste", {})[key] = waste_classes(
                tape, o, tfull, reach)

            ech, evo, eco, eai, emo, ewa, ele, eld = ([], [], [], [], [],
                                                       [], [], [])
            for e in engines:
                for sh in e.shots_all:
                    if sh["owner"] == o:
                        sh["speed"] = speed
                d = unit_dmg(e, o)
                mark_strays(e, o, d)
                ele.append(damage_ledger(e, o, d, u["accuracy"]))
                ech.append(target_choice(e, o, cycle, reach))
                evo.append(volley_structure(e, o, cycle))
                eco.append(coverage(e, o, d, reach))
                eai.append(aim_fit(e, o, speed, sink=aim_pool[("engine", slug)]))
                emo.append(mover_split(e, o, sink=mv_pool[("engine", slug)]))
                ewa.append(waste_classes(e, o, d, reach))
                eld.append(applied_lead(e, o))
            for name, rows in (("choice", ech), ("volley", evo), ("cover", eco),
                               ("aim", eai), ("mover", emo), ("waste", ewa),
                               ("ledger", ele), ("lead", eld)):
                keys = set()
                for x in rows:
                    keys |= set(x)
                rec["engine"].setdefault(name, {})[key] = {
                    k: avg(rows, k, 3) for k in keys}

    def sides_of(tag):
        return list(out["fights"][tag]["tape"]["choice"].keys())

    def hc_first(tag):
        ks = sides_of(tag)
        return sorted(ks, key=lambda k: 0 if k.endswith("HC") else 1)

    # ---- Q0 -------------------------------------------------------------
    if sec in ("all", "q0"):
        rows = []
        for tag in want:
            for k in hc_first(tag):
                t = out["fights"][tag]["tape"]["ledger"][k]
                e = out["fights"][tag]["engine"]["ledger"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "acc": t["acc"], "full dmg": t["full_dmg"],
                    "half dmg": r(t["full_dmg"] / 2, 2),
                    "T shots": t["shots"], "T land%": t["landed%"],
                    "T full": t["full_n"], "T half": t["half_n"],
                    "T kill?": t["killq_n"], "T other": t["other_n"],
                    "T half%res": t["half%_resolved"],
                    "T half%shots": t["half%_shots"],
                    "T stray(half)": t["stray_half_n"],
                    "T stray(full)": t["stray_full_n"],
                    "T dmg/shot x": t["dmg_per_shot_x"],
                    "E half": e.get("half_n"), "E land%": e.get("landed%"),
                    "E dmg/shot x": e.get("dmg_per_shot_x"),
                    "T land_d full": t["land_d_full"],
                    "T land_d half": t["land_d_half"],
                    "T scat full": t["scatter_full"],
                    "T scat half": t["scatter_half"],
                    "T scat half p90": t["scatter_half_p90"],
                    "T scat half max": t["scatter_half_max"],
                    "T crowd med": t["crowd_med"], "T crowd p10": t["crowd_p10"],
                    "T nothing n": t["nothing_n"],
                    "T nothing_d med": t["nothing_d_med"],
                    "T nothing_d p90": t["nothing_d_p90"],
                    "T nothing_d max": t["nothing_d_max"],
                })
        table(rows, list(rows[0].keys()),
              "Q0 -- THE REDUCED-DAMAGE MISS. `full dmg` = this side's largest "
              "non-killing damage value; `half` counts events at exactly half "
              "of it. half%res = share of RESOLVED landed shots that applied "
              "half (clamped kills excluded). stray(half)/stray(full) = landed "
              "events whose victim is not the shot's inferred aim target -- "
              "half = the mechanic striking a neighbour, full = an aim-"
              "inference error. dmg/shot x = damage applied per shot fired as "
              "a fraction of a full hit. land_d = landing distance to the "
              "victim; nothing_d = distance from a NON-applying shot's landing "
              "point to the nearest living enemy (the dispersion readout).")

    # ---- Q1a ------------------------------------------------------------
    if sec in ("all", "q1a"):
        rows = []
        for tag in want:
            for k in hc_first(tag):
                t = out["fights"][tag]["tape"]["choice"][k]
                e = out["fights"][tag]["engine"]["choice"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T n": t["n"], "E n": e.get("n"),
                    "T near%": t["nearest%"], "E near%": e.get("nearest%"),
                    "T near%(named)": t["nearest%_named"],
                    "near% rand": t["nearest%_rand"],
                    "T inrch k": t["in_reach_med"], "E inrch k": e.get("in_reach_med"),
                    "rank rand": t["rank_rand"],
                    "T rankmed": t["rank_med"], "E rankmed": e.get("rank_med"),
                    "T rankmean": t["rank_mean"], "E rankmean": e.get("rank_mean"),
                    "T rankp90": t["rank_p90"], "E rankp90": e.get("rank_p90"),
                    "T same%": t["same_as_prev%"], "E same%": e.get("same_as_prev%"),
                    "T unshared%": t["unshared%"], "E unshared%": e.get("unshared%"),
                })
        table(rows, list(rows[0].keys()),
              "Q1a -- PER-SHOT TARGET CHOICE. near% = the victim was the "
              "shooter's nearest living enemy at launch (rank 1); rank = the "
              "victim's place in the shooter's nearest-first ordering; same% = "
              "same victim as that shooter's previous shot; unshared% = no "
              "OTHER friendly shot in the trailing reload window went to the "
              "same victim. near%(named) restricts to tape shots whose victim "
              "the damage pairing names, i.e. removes the aim inference.")

    # ---- Q1b ------------------------------------------------------------
    if sec in ("all", "q1b"):
        rows = []
        for tag in want:
            for k in hc_first(tag):
                t = out["fights"][tag]["tape"]["volley"][k]
                e = out["fights"][tag]["engine"]["volley"][k]
                if not t:
                    continue
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T win": t["windows"], "T shots/w": t["shots/win"],
                    "E shots/w": e.get("shots/win"),
                    "T vict": t["victims_obs"], "E vict": e.get("victims_obs"),
                    "T vict(near)": t["victims_nearest"],
                    "E vict(near)": e.get("victims_nearest"),
                    "T vict(RR)": t["victims_rr"], "E vict(RR)": e.get("victims_rr"),
                    "T spread": t["spread_obs"], "E spread": e.get("spread_obs"),
                    "T sprd(near)": t["spread_nearest"],
                    "E sprd(near)": e.get("spread_nearest"),
                    "T maxdup": t["maxdup_obs"], "E maxdup": e.get("maxdup_obs"),
                    "T |o-near|": t["fit_nearest"], "T |o-RR|": t["fit_rr"],
                    "E |o-near|": e.get("fit_nearest"), "E |o-RR|": e.get("fit_rr"),
                })
        table(rows, list(rows[0].keys()),
              "Q1b -- VOLLEY STRUCTURE, one reload-length window at a time. "
              "vict = distinct victims the window's shots went to; vict(near) "
              "= the same count under the every-shooter-fires-at-its-own-"
              "nearest null; vict(RR) = min(shots, living enemies), a perfect "
              "round-robin. spread = vict / vict(RR). maxdup = most shots on "
              "any one victim in the window. |o-near| / |o-RR| = median "
              "absolute distance from each null (smaller = better fit).")

    # ---- Q1c ------------------------------------------------------------
    if sec in ("all", "q1c"):
        rows = []
        for tag in want:
            for k in hc_first(tag):
                t = out["fights"][tag]["tape"]["cover"][k]
                e = out["fights"][tag]["engine"]["cover"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "dmg/shot": t["dmg"],
                    "T anyInb%": t["any_inbound%"], "E anyInb%": e.get("any_inbound%"),
                    "T cov%": t["covered%"], "E cov%": e.get("covered%"),
                    "T 1shot n": t["1shot_kills"], "E 1shot n": e.get("1shot_kills"),
                    "T 1shot dbl%": t["1shot_doubled%"],
                    "E 1shot dbl%": e.get("1shot_doubled%"),
                    "T redir n": t["redirect_n"], "T stub n": t["stubborn_n"],
                    "T redir%": t["redirect%"],
                    "E redir n": e.get("redirect_n"), "E stub n": e.get("stubborn_n"),
                    "E redir%": e.get("redirect%"),
                })
        table(rows, list(rows[0].keys()),
              "Q1c -- IN-FLIGHT COVERAGE AND LETHALITY AWARENESS. anyInb% = "
              "the victim already had a friendly projectile inbound that would "
              "land first; cov% = that inbound damage already exceeded its hp "
              "(the shot was dead on arrival at launch). 1shot n = shots whose "
              "victim needed only one hit to die; dbl% = the share of those "
              "that were nonetheless doubled up. redir/stub = the shooter's "
              "NEAREST enemy was already lethally covered and it shot "
              "elsewhere / shot it anyway.")

    # ---- Q1d ------------------------------------------------------------
    if sec in ("all", "q1d"):
        rows = []
        for tag in want:
            for k in hc_first(tag):
                t = out["fights"][tag]["tape"]["waste"][k]
                e = out["fights"][tag]["engine"]["waste"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T wst%": t["waste%"], "E wst%": e.get("waste%"),
                    "E wst n": e.get("waste"),
                    "blind%": e.get("blind%"), "blind alt%": e.get("blind_alt%"),
                    "same-tick%": e.get("same-tick%"),
                    "st alt%": e.get("same-tick_alt%"),
                    "overtaken%": e.get("overtaken%"),
                    "ov alt%": e.get("overtaken_alt%"),
                    "cumul%": e.get("cumulative%"),
                    "cum alt%": e.get("cumulative_alt%"),
                })
        table(rows, list(rows[0].keys()),
              "Q1d -- WHERE THE ENGINE'S WASTED SHOTS COME FROM (engine "
              "columns; T wst% is the tape's own waste rate under the same "
              "definition). blind = R5b's test was already true at launch; "
              "same-tick = the kill needed a shot fired in the same 1/60 s "
              "tick; overtaken = a LATER launch arrived FIRST; cumulative = "
              "the victim was genuinely alive-and-worth-shooting at launch. "
              "`alt%` = share of that bucket for which another reachable, "
              "not-already-lethally-covered enemy existed at launch.")

    # ---- Q2a ------------------------------------------------------------
    if sec in ("all", "q2a"):
        rows = []
        for tag in want:
            for k in sides_of(tag):
                t = out["fights"][tag]["tape"]["aim"][k]
                if not t["n"]:
                    continue
                row = {"fight": tag.replace("__vs__", " v "), "side": k,
                       "n": t["n"], "leadratio": t["lead_ratio_med"],
                       "lr p10-p90": f"{t['lead_ratio_p10']}-{t['lead_ratio_p90']}"}
                for name, _w, _c in AIM_MODELS:
                    row[name] = t[name]
                row["oracle"] = t["oracle"]
                rows.append(row)
        if rows:
            table(rows, list(rows[0].keys()),
                  "Q2a -- IMPLIED AIM MODEL, tape only. Median residual "
                  "|predicted aim point - actual landing point| in tiles, over "
                  "tape HITS whose victim MOVED during the flight, with the "
                  "sprite-anchor offset removed. leadratio = how far along the "
                  "victim's own launch->impact displacement the landing point "
                  "sits (0 = no lead, 1 = full intercept). `oracle` = the "
                  "victim's true position at impact, the achievable floor.")
        rows2 = []
        for tag in want:
            for k in sides_of(tag):
                t = out["fights"][tag]["tape"]["aim"][k]
                e = out["fights"][tag]["engine"]["aim"][k]
                rows2.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T anchor dx": t["anchor_dx"], "T anchor dy": t["anchor_dy"],
                    "T anchor n": t["anchor_n"], "T anchor spread": t["anchor_spread"],
                    "E anchor dx": e.get("anchor_dx"), "E anchor dy": e.get("anchor_dy"),
                    "E anchor spread": e.get("anchor_spread"),
                    "T best-win%": max(
                        [(t[f"{m[0]}_win%"] or 0, m[0]) for m in AIM_MODELS])[0],
                    "T best model": max(
                        [(t[f"{m[0]}_win%"] or 0, m[0]) for m in AIM_MODELS])[1],
                })
        table(rows2, list(rows2[0].keys()),
              "Q2a(b) -- ANCHOR OFFSET CALIBRATION. dx/dy = median vector from "
              "a landed shot's terminal position to its (stationary) victim's "
              "position; spread = median distance of individual offsets from "
              "that median, i.e. how constant the offset is. best-win% = the "
              "best model's share of mover-hits predicted within "
              f"{ON_TARGET} tiles.")

    # ---- Q2b / Q2c -------------------------------------------------------
    if sec in ("all", "q2b", "q2c"):
        rows = []
        for tag in want:
            for k in sides_of(tag):
                t = out["fights"][tag]["tape"]["mover"][k]
                e = out["fights"][tag]["engine"]["mover"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T still%": t["still_share"], "E still%": e.get("still_share"),
                    "T mover n": t["mover_n"], "E mover n": e.get("mover_n"),
                    "T mvhit%": t["mover_hit%"], "E mvhit%": e.get("mover_hit%"),
                    "T mvdirect%": t["mover_direct%"],
                    "E mvdirect%": e.get("mover_direct%"),
                    "T mvhalf%": t["mover_half%"],
                    "T still hit%": t["still_hit%"], "E still hit%": e.get("still_hit%"),
                    "T kept n": t["kept_n"], "T kept hit%": t["kept_hit%"],
                    "T kept dir%": t["kept_direct%"],
                    "E kept n": e.get("kept_n"), "E kept hit%": e.get("kept_hit%"),
                    "T halt n": t["halted_n"], "T halt hit%": t["halted_hit%"],
                    "T halt dir%": t["halted_direct%"],
                    "E halt n": e.get("halted_n"), "E halt hit%": e.get("halted_hit%"),
                    "T turn n": t["turned_n"], "T turn hit%": t["turned_hit%"],
                    "T turn dir%": t["turned_direct%"],
                    "E turn n": e.get("turned_n"), "E turn hit%": e.get("turned_hit%"),
                    "T mvfrac": t["movefrac_med_movers"],
                    "E mvfrac": e.get("movefrac_med_movers"),
                })
        table(rows, list(rows[0].keys()),
              "Q2b/Q2c -- WHAT THE TARGET DID DURING THE FLIGHT. Shots are "
              "classed by the victim's behaviour between launch and impact: "
              "still (not moving at launch), kept (moving throughout, heading "
              f"held within {TURN_DEG} deg), halted (moving at launch, moving "
              "for less than half the flight), turned. mvfrac = median share "
              "of the flight the victim spent moving, over shots at victims "
              "that were moving at launch.")

    # ---- pooled by shooter unit ------------------------------------------
    if sec in ("all", "q2a", "pool"):
        rows = []
        for slug in ("arbalester", "heavy_cav_archer", "imp_elite_skirm",
                     "hand_cannoneer"):
            for src in ("tape", "engine"):
                p = aim_pool[(src, slug)]
                lr = p.get("lead_ratio", [])
                if not lr:
                    continue
                big = [x for x, d in lr if d > 0.30]
                row = {"unit": SHORT[slug], "src": src, "n": len(lr),
                       "n(disp>0.3)": len(big),
                       "leadratio": r(med([x for x, _ in lr]), 2),
                       "lr(disp>0.3)": r(med(big), 2) if big else None,
                       "lr p25": r(q([x for x, _ in lr], 0.25), 2),
                       "lr p75": r(q([x for x, _ in lr], 0.75), 2)}
                for name, _w, _c in AIM_MODELS:
                    row[name] = r(med(p.get(name, [])), 3)
                row["oracle"] = r(med(p.get("oracle", [])), 3)
                rows.append(row)
        if rows:
            table(rows, list(rows[0].keys()),
                  "Q2a POOLED BY SHOOTER UNIT over all six fights. Same "
                  "statistic as Q2a, but the per-fight cells there run n=1-8 "
                  "and cannot carry a conclusion; this is the level at which "
                  "an aim rule is a property of the unit. lr(disp>0.3) drops "
                  "victims whose whole launch-to-impact displacement is under "
                  "0.3 tiles, where the ratio's denominator is comparable to "
                  "position noise.")

    if sec in ("all", "q2d", "pool"):
        rows = []
        for tag in want:
            for k in sides_of(tag):
                e = out["fights"][tag]["engine"].get("lead", {}).get(k, {})
                if not e:
                    continue
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "E shots": e.get("n"),
                    "E lead>0.05%": e.get("lead>0.05%"),
                    "E lead>0.30%": e.get("lead>0.30%"),
                    "E lead med": e.get("lead_med"),
                    "E lead p90": e.get("lead_p90"),
                    "E lead p99": e.get("lead_p99"),
                    "E lead max": e.get("lead_max"),
                })
        if rows:
            table(rows, list(rows[0].keys()),
                  "Q2d -- HOW OFTEN THE ENGINE ACTUALLY LEADS (engine only, "
                  "EVERY shot, no hit selection). Distance from the shot's "
                  "landing point to the target's position at launch: 0 means "
                  "R5b's ballistic lead resolved to no offset at all, i.e. "
                  "target.vel was zero on the launch tick. For a unit with "
                  "accuracy < 100 this difference also contains D2's miss "
                  "displacement, so its share cannot fall below its miss "
                  "rate; the accuracy-100 units are the clean reading.")

    if sec in ("all", "q2b", "q2c", "pool"):
        rows = []
        for slug in ("arbalester", "heavy_cav_archer", "imp_elite_skirm",
                     "hand_cannoneer"):
            row = {"unit": SHORT[slug]}
            for src, pre in (("tape", "T"), ("engine", "E")):
                p = mv_pool[(src, slug)]
                tot = sum(p[k][0] for k in ("still", "kept", "halted", "turned")
                          if k in p)
                mv = sum(p[k][0] for k in ("kept", "halted", "turned") if k in p)
                mvh = sum(p[k][1] for k in ("kept", "halted", "turned") if k in p)
                mvf = sum(p[k][2] for k in ("kept", "halted", "turned") if k in p)
                row[f"{pre} shots"] = tot
                row[f"{pre} still%"] = r(pct(p.get("still", [0])[0], tot), 1)
                row[f"{pre} still hit%"] = r(pct(
                    p["still"][1], p["still"][0]), 1) if p.get("still") else None
                row[f"{pre} mover n"] = mv
                row[f"{pre} mv hit%"] = r(pct(mvh, mv), 1) if mv else None
                row[f"{pre} mv direct%"] = r(pct(mvh - mvf, mv), 1) if mv else None
                for k, lab in (("kept", "kept"), ("halted", "halt"),
                               ("turned", "turn")):
                    b = p.get(k, [0, 0, 0])
                    row[f"{pre} {lab} n"] = b[0]
                    row[f"{pre} {lab} hit%"] = r(pct(b[1], b[0]), 1) if b[0] else None
                row[f"{pre} mvfrac"] = r(med(p.get("_mvfrac", [])), 3)
            rows.append(row)
        table(rows, list(rows[0].keys()),
              "Q2b/Q2c POOLED BY SHOOTER UNIT over all six fights. Hit rate "
              "and target behaviour, pooled to usable n. mvfrac = median share "
              "of the flight the victim spent moving, over shots at victims "
              "that were moving at launch -- the halt-frequency comparison.")

    if args.json:
        out["pool_aim"] = {f"{s}|{u}": {k: (v if k != "lead_ratio" else
                                            [x for x, _ in v])
                                        for k, v in p.items()}
                           for (s, u), p in aim_pool.items()}
        out["pool_mover"] = {f"{s}|{u}": p for (s, u), p in mv_pool.items()}
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
