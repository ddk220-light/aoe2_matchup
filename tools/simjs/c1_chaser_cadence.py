"""Phase C: the melee-chaser-vs-kiter cadence, measured tape vs engine.

MEASUREMENT ONLY. Nothing here proposes or makes an engine change.

E12 established, corpus-wide, that a melee unit's swing-interval ratio
tape/engine is 1.001 in melee-vs-melee but 1.29 when the melee unit is CHASING
a RANGED one (mean 1.493, p90 2.11). The tape's chasers keep losing and
re-winning contact with their kiting victims in a way the engine does not
model. That unmodelled cadence loss is the blocker under two tape-true
mechanics that are shipped OFF (R5D1.trailingWindowLead "P2" and
R5D1.reducedDamageHits "P1"), and it owns most of the remaining
ranged-vs-melee misses.

Six measurements, all computed by the SAME function for a recording and for an
engine run, from the streams both sources expose identically:

  1. CHASER SWING ANATOMY  per-chaser inter-hit intervals against the kiting
     side, and a decomposition of each interval into RELOAD + time out of
     reach while closing + time out of reach while NOT closing + time in
     reach without swinging. Plus the share of cycles that lose contact at
     all.
  2. CONTACT-LOSS MECHANISM  what happens in the reload window after a chaser
     lands a hit: how far the victim travels, how far the chaser travels, the
     radial split between the two (who opened the gap), when the victim's
     next kite step starts relative to the swing, and whether the chaser's
     hits land at the kiter's STOP moments. Plus the kiters' own stop/move
     rhythm measured independently of any hit.
  3. THE ENGINE'S EXCESS HITS  chaser landed hits per chaser-second, and
     every landed hit classified by the victim's and the chaser's movement
     state at the instant it landed, plus the attacker-victim distance at the
     hit against the engine's own reach.
  4. BLACKLIST / RETARGET  how often a chaser gives up a living victim,
     measured identically on both sources from the damage stream, plus the
     engine's own PURSUIT_BAR/blacklist ledger from the probe
     (tools/simjs/c1_chase_probe.mjs) which the tape cannot show.
  5. THE P2 COUNTERFACTUAL  champion__vs__heavy_cav_archer, three columns:
     tape, engine defaults, engine with R5D1.trailingWindowLead ON. Winner
     agreement, HP points, survival curves, kiter accuracy against the
     chaser, chaser output.
  6. HC LAND RATE  the hand cannoneer families under the current engine,
     with a shift-share decomposition of the land-rate gap into "the engine
     shoots at a different mix of targets" and "the engine hits that mix less
     often", plus an engine column with R5D1.reducedDamageHits ON.

Inputs
------
    node tools/simjs/c1_chase_probe.mjs --tags-file <86 chaser tags> \
         --seeds 20 --out-dir D:/AI/aoe2_golden/simruns_c1
    node tools/simjs/c1_chase_probe.mjs --tags-file <champion x9> --seeds 20 \
         --r5d1 trailingWindowLead --out-dir D:/AI/aoe2_golden/simruns_c1_p2
    node tools/simjs/c1_chase_probe.mjs --tags-file <hand cannoneer x29> \
         --seeds 20 --r5d1 reducedDamageHits --out-dir D:/AI/aoe2_golden/simruns_c1_p1

    PYTHONPATH=. python tools/simjs/c1_chaser_cadence.py --section all
    ... --section anatomy|contact|excess|retarget|p2|hc
    ... --seeds 20  --json out.json

Everything reuses tools/simjs/ranged_fire_forensics.py: its ``Fight`` (10 Hz
positions with interpolation, engine-equivalent wipe-time cut), its shot ->
damage pairing, its aim-target inference, and its ``engine_reach`` (the
engine's own inRange() expression, validated in E15 to within 0.02 tiles of
the observed contact distance on all 42 class pairs of the melee corpus). A
tape number and an engine number are therefore never two implementations that
happen to share a name.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tools.simjs.ranged_fire_forensics as rff  # noqa: E402
from aoe2x.paths import REPO_ROOT  # noqa: E402

CALIB = REPO_ROOT / "data" / "calibration"
DEFAULT_RUNS = Path("D:/AI/aoe2_golden/simruns_c1")
DEFAULT_P2_RUNS = Path("D:/AI/aoe2_golden/simruns_c1_p2")
DEFAULT_P1_RUNS = Path("D:/AI/aoe2_golden/simruns_c1_p1")

# The chaser corpus. RANGED excludes the two siege weapons deliberately: they
# have a minimum-range dead zone, their own repositioning path (tooClose) and
# are excluded from the group-kite gate, so a melee unit walking at a Siege
# Onager is a different mechanic from one chasing an archer.
RANGED = {"arbalester", "hand_cannoneer", "heavy_cav_archer", "imp_elite_skirm"}
MELEE = {"champion", "elite_elephant", "elite_fire_lancer", "elite_steppe",
         "halberdier", "heavy_camel", "hussar", "paladin"}

# Chasers whose "landed hit" is NOT a melee swing. The Elite Fire Lancer's
# damage comes from a charge PROJECTILE with a blast radius, so its damage
# events fire in bursts at up to 5-6 tiles (measured: median attacker-victim
# distance at a landed hit 5.06 tiles on tape against a 0.57-tile melee
# reach). Its rows are printed like every other family, but it is excluded
# from the pooled swing-interval headline, where a burst would read as a
# 0.12 s "swing cycle".
CHARGE_CHASERS = {"elite_fire_lancer"}

# A unit "moved" between two 10 Hz samples if it covered more than this.
# rff.STEP_TILES (0.02) is the campaign-wide bar and is reused rather than
# redeclared, so "moving" means one thing across every forensic.
STEP = rff.STEP_TILES

# Inter-hit gaps longer than this are not a swing cycle -- the unit stopped
# fighting entirely (its side was wiped out of reach, it was walking across
# the arena). Same cut rff.cadence() uses for launch-to-launch gaps.
MAX_CYCLE_S = 12.0

# A "stop" in a kiter's 10 Hz track has to last at least this long to be a
# stop rather than a sample of quantisation noise. One sample is ~0.102 s, so
# this is "stopped for two consecutive samples".
MIN_STOP_S = 0.15

# How near a still-living previous victim has to be, at the moment its
# attacker lands on somebody else, for that switch to count as ABANDONING it
# rather than as the natural consequence of it having run out of the fight.
ABANDON_NEAR_TILES = 3.0


def q(v, p):
    return rff.q(v, p)


def med(v):
    return rff.med(v)


def r(x, n=2):
    return None if x is None else round(x, n)


def pct(a, b):
    return None if not b else 100.0 * a / b


def ratio(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


# ---------------------------------------------------------------------------
# fight context
# ---------------------------------------------------------------------------

class Ctx:
    """Everything a measurement needs to know about WHO is chasing WHOM."""

    def __init__(self, fm, dicts):
        s1, s2 = fm["side1"], fm["side2"]
        if s1["slug"] in RANGED:
            kit, cha = s1, s2
        else:
            kit, cha = s2, s1
        self.fm = fm
        self.tag = fm["tag"]
        self.family = fm["matchup"]
        self.kiter_owner, self.chaser_owner = kit["owner"], cha["owner"]
        self.kiter, self.chaser = kit["slug"], cha["slug"]
        self.kd = dicts[f"{kit['civ']}|{kit['slug']}"]
        self.cd = dicts[f"{cha['civ']}|{cha['slug']}"]
        self.kiter_n, self.chaser_n = kit["count"], cha["count"]
        # 1 / attack_speed is exactly BattleUnit's own `reloadTime`.
        self.reload = 1.0 / (self.cd["attack_speed"] or 0.5)
        self.kiter_reload = 1.0 / (self.kd["attack_speed"] or 0.5)
        # BattleUnit.inRange(), in tiles, both directions.
        self.reach = rff.engine_reach(self.cd, self.kd)
        self.kiter_reach = rff.engine_reach(self.kd, self.cd)
        self.chaser_speed = self.cd["movement_speed"]
        self.kiter_speed = self.kd["movement_speed"]
        self.chaser_hp = self.cd["hp"]
        self.kiter_hp = self.kd["hp"]
        self.label = f"{self.chaser}->{self.kiter}"


def chaser_fights(fights):
    out = []
    for f in fights:
        if f.get("quarantined"):
            continue
        s = {f["side1"]["slug"], f["side2"]["slug"]}
        if (s & RANGED) and (s & MELEE) and len(s & RANGED) == 1:
            out.append(f)
    return out


def load_manifest():
    return json.loads((CALIB / "manifest.json").read_text(encoding="utf-8"))["fights"]


def load_dicts():
    return json.loads((CALIB / "combat_dicts.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# shared position helpers (identical for tape and engine)
# ---------------------------------------------------------------------------

def army_seconds(fight, owner):
    """Summed living-unit seconds for `owner`, cut at the end of the fight."""
    tot = 0.0
    prev = None
    for t, fr in fight.frames:
        if prev is not None:
            n = sum(1 for (_x, _y, o, _h) in fr.values() if o == owner)
            tot += n * (t - prev)
        prev = t
    return tot


def nearest_enemy_dist(fr, ax, ay, owner):
    best = None
    for (x, y, o, _h) in fr.values():
        if o != owner:
            continue
        d = math.hypot(x - ax, y - ay)
        if best is None or d < best:
            best = d
    return best


def moving_at(fight, uid, t, back=0.25, fwd=0.05):
    """Was `uid` moving around `t`? rff's own predicate and bar."""
    return fight.moved_between(uid, t - back, t + fwd)


def hits_by(fight, att_owner, vic_owner):
    return [e for e in fight.damage
            if e.get("attacker_owner") == att_owner
            and e.get("victim_owner") == vic_owner]


# ---------------------------------------------------------------------------
# 1. CHASER SWING ANATOMY
# ---------------------------------------------------------------------------

def anatomy(fight, ctx):
    """Inter-hit intervals of every chaser, each decomposed in time.

    Decomposition, over the 10 Hz samples strictly inside the interval:

      in_reach   at least one living kiter inside `ctx.reach` of the chaser.
                 This is the engine's OWN reach predicate, and it is taken
                 against ANY living kiter, not against the specific victim:
                 "could have swung at somebody" is what a cadence is made of,
                 and using the named victim would score an honest switch to a
                 nearer body as lost contact.
      oor_close  nothing in reach AND the distance to the nearest kiter fell
                 since the previous sample -- the chaser is closing.
      oor_far    nothing in reach and the distance did NOT fall -- the chaser
                 is being outrun, blocked, or walking the wrong way.

    An interval is `reload` seconds of unavoidable cooldown plus EXCESS. The
    excess is attributed to contact loss up to the amount of contact actually
    lost, and the remainder to standing in reach without swinging.
    """
    ts = fight._ts
    frames = fight.frames_all
    out = {
        "intervals": [], "oor_close": [], "oor_far": [], "in_reach": [],
        "lost_contact": 0, "n": 0,
        "excess_to_contact": [], "excess_to_idle": [],
    }
    by_att = defaultdict(list)
    for e in hits_by(fight, ctx.chaser_owner, ctx.kiter_owner):
        by_att[e["attacker"]].append(e["t"])
    for att, times in by_att.items():
        times.sort()
        for t0, t1 in zip(times, times[1:]):
            gap = t1 - t0
            if gap > MAX_CYCLE_S or gap <= 0:
                continue
            i0 = bisect.bisect_right(ts, t0)
            i1 = bisect.bisect_right(ts, t1)
            oor_c = oor_f = inr = 0.0
            prev_t, prev_d = t0, None
            ok = False
            for i in range(i0, i1):
                t, fr = frames[i]
                a = fr.get(att)
                dt = t - prev_t
                prev_t = t
                if a is None:
                    break
                d = nearest_enemy_dist(fr, a[0], a[1], ctx.kiter_owner)
                if d is None:
                    break
                ok = True
                if d <= ctx.reach:
                    inr += dt
                elif prev_d is not None and d < prev_d - 1e-9:
                    oor_c += dt
                else:
                    oor_f += dt
                prev_d = d
            if not ok:
                continue
            span = oor_c + oor_f + inr
            if span <= 0:
                continue
            # renormalise to the true interval (the sample grid clips the ends)
            k = gap / span
            oor_c, oor_f, inr = oor_c * k, oor_f * k, inr * k
            out["n"] += 1
            out["intervals"].append(gap)
            out["oor_close"].append(oor_c)
            out["oor_far"].append(oor_f)
            out["in_reach"].append(inr)
            oor = oor_c + oor_f
            if oor > 0.10:                 # one 10 Hz sample
                out["lost_contact"] += 1
            excess = max(0.0, gap - ctx.reload)
            out["excess_to_contact"].append(min(oor, excess))
            out["excess_to_idle"].append(max(0.0, excess - oor))
    return out


# ---------------------------------------------------------------------------
# 2. CONTACT-LOSS MECHANISM + KITER RHYTHM
# ---------------------------------------------------------------------------

def contact_mechanism(fight, ctx):
    """The reload window that FOLLOWS every chaser hit.

    For a hit at `th` by chaser A on kiter V, over [th, th + reload]:

      vic_disp / cha_disp   straight-line displacement of each (tiles).
      vic_radial            the victim's displacement projected on the
                            A->V direction at `th`: how much of the gap the
                            VICTIM opened.
      cha_radial            the same projection of the chaser's displacement:
                            how much of the gap the CHASER closed (positive)
                            or opened (negative).
      d_gap                 dist(A,V) at th+reload minus at th.
      t_lose                seconds from the hit until V first leaves A's
                            reach (None if it never does).
      onset                 seconds from the hit until V's next MOVEMENT
                            starts, for hits landed on a stopped victim.

    plus the movement state of the victim AT the hit, which is measurement
    3's classifier and is the direct test of "does the tape chaser land its
    hit predominantly at the kiter's STOP moments".
    """
    R = ctx.reload
    ts, frames = fight._ts, fight.frames_all
    out = {
        "n": 0, "vic_disp": [], "cha_disp": [], "vic_radial": [],
        "cha_radial": [], "d_gap": [], "t_lose": [], "lost": 0,
        "onset": [], "hit_on_stopped": 0, "hit_on_moving": 0,
        "victim_opened": 0, "chaser_opened": 0, "both_static": 0,
        "align_att": [], "align_cen": [],
    }
    for e in hits_by(fight, ctx.chaser_owner, ctx.kiter_owner):
        th, A, V = e["t"], e["attacker"], e["victim"]
        pa0, pv0 = fight.pos(A, th), fight.pos(V, th)
        pa1, pv1 = fight.pos(A, th + R), fight.pos(V, th + R)
        if None in (pa0, pv0, pa1, pv1):
            continue
        out["n"] += 1
        ux, uy = pv0[0] - pa0[0], pv0[1] - pa0[1]
        d0 = math.hypot(ux, uy)
        if d0 > 1e-9:
            ux, uy = ux / d0, uy / d0
        vr = (pv1[0] - pv0[0]) * ux + (pv1[1] - pv0[1]) * uy
        ar = (pa1[0] - pa0[0]) * ux + (pa1[1] - pa0[1]) * uy
        out["vic_disp"].append(math.hypot(pv1[0] - pv0[0], pv1[1] - pv0[1]))
        out["cha_disp"].append(math.hypot(pa1[0] - pa0[0], pa1[1] - pa0[1]))
        out["vic_radial"].append(vr)
        out["cha_radial"].append(ar)
        out["d_gap"].append(math.hypot(pv1[0] - pa1[0], pv1[1] - pa1[1]) - d0)
        # WHICH WAY the victim runs. Two candidate flee bases, both unit
        # vectors from the victim's position at the hit:
        #   align_att  away from the unit that just hit it;
        #   align_cen  away from the CENTROID of the whole chasing side --
        #              which is what a radial-flee-from-target plus a group
        #              cohesion term produces, and is NOT the same direction
        #              once the chaser side has spread out.
        # Reported as cosines of the victim's actual displacement, so 1.0 =
        # ran exactly along that basis and 0.0 = ran across it.
        mvx, mvy = pv1[0] - pv0[0], pv1[1] - pv0[1]
        mlen = math.hypot(mvx, mvy)
        if mlen > 0.05 and d0 > 1e-9:
            out["align_att"].append((mvx * ux + mvy * uy) / mlen)
            fr = fight.frame_at(th)
            cx = [p for p in fr.values() if p[2] == ctx.chaser_owner]
            if cx:
                gx = sum(p[0] for p in cx) / len(cx)
                gy = sum(p[1] for p in cx) / len(cx)
                ex, ey = pv0[0] - gx, pv0[1] - gy
                el = math.hypot(ex, ey)
                if el > 1e-9:
                    out["align_cen"].append((mvx * ex / el + mvy * ey / el) / mlen)
        # WHO opened the gap: the victim's away-motion vs the chaser's
        # failure to follow. Only asked of windows that actually opened one.
        if out["d_gap"][-1] > 0.10:
            if vr > 0.10 and vr >= abs(ar):
                out["victim_opened"] += 1
            elif ar < -0.10:
                out["chaser_opened"] += 1
            else:
                out["both_static"] += 1
        # when contact is first lost
        i0 = bisect.bisect_right(ts, th)
        i1 = bisect.bisect_right(ts, th + R)
        t_lose = None
        for i in range(i0, i1):
            t, fr = frames[i]
            a, v = fr.get(A), fr.get(V)
            if a is None or v is None:
                break
            if math.hypot(v[0] - a[0], v[1] - a[1]) > ctx.reach:
                t_lose = t - th
                break
        if t_lose is not None:
            out["lost"] += 1
            out["t_lose"].append(t_lose)
        # victim movement state at the hit, and the kite-step onset
        if moving_at(fight, V, th):
            out["hit_on_moving"] += 1
        else:
            out["hit_on_stopped"] += 1
            prev = None
            for i in range(bisect.bisect_left(ts, th),
                           bisect.bisect_right(ts, th + 2.5 * R)):
                p = frames[i][1].get(V)
                if p is None:
                    break
                if prev is not None and math.hypot(p[0] - prev[0],
                                                   p[1] - prev[1]) > STEP:
                    out["onset"].append(frames[i][0] - th)
                    break
                prev = (p[0], p[1])
    return out


def kiter_rhythm(fight, ctx):
    """The kiting side's stop/move rhythm, measured with no reference to any
    hit: every kiter's 10 Hz track segmented into STOPPED and MOVING runs.

    This is the control for measurement 2. If the tape chaser lands its hits
    at the kiter's stop moments, then a correct chaser cadence is EMERGENT
    from a correct kiter rhythm, and the question becomes whether the engine's
    kiters stop as long and as often as the tape's.
    """
    ts, frames = fight._ts, fight.frames_all
    end = fight.end_t
    tracks = defaultdict(list)
    for t, fr in frames:
        if t > end + 1e-9:
            break
        for uid, (x, y, o, _h) in fr.items():
            if o == ctx.kiter_owner:
                tracks[uid].append((t, x, y))
    stops, moves = [], []
    stopped_s = total_s = 0.0
    for uid, tr in tracks.items():
        run_state = None
        run_t0 = None
        for (t0, x0, y0), (t1, x1, y1) in zip(tr, tr[1:]):
            dt = t1 - t0
            if dt <= 0 or dt > 0.5:      # a gap in the track: cut the run
                run_state = None
                continue
            total_s += dt
            st = math.hypot(x1 - x0, y1 - y0) > STEP
            if not st:
                stopped_s += dt
            if run_state is None:
                run_state, run_t0 = st, t0
            elif st != run_state:
                (moves if run_state else stops).append(t0 - run_t0)
                run_state, run_t0 = st, t0
        if run_state is not None and tr:
            (moves if run_state else stops).append(tr[-1][0] - run_t0)
    stops = [s for s in stops if s >= MIN_STOP_S]
    return {
        "stops": stops, "moves": moves,
        "stopped_s": stopped_s, "total_s": total_s,
        "n_units": len(tracks),
    }


# ---------------------------------------------------------------------------
# 3. THE ENGINE'S EXCESS HITS
# ---------------------------------------------------------------------------

def hit_states(fight, ctx):
    """Every chaser landed hit, classified by both parties' movement state at
    the instant it landed, plus the attacker-victim distance at that instant."""
    out = {"n": 0, "cells": Counter(), "dist": [], "army_s": 0.0,
           "kills": 0, "cstep": [], "vstep": []}
    for e in hits_by(fight, ctx.chaser_owner, ctx.kiter_owner):
        th, A, V = e["t"], e["attacker"], e["victim"]
        out["n"] += 1
        if e.get("kill"):
            out["kills"] += 1
        vm = moving_at(fight, V, th)
        am = moving_at(fight, A, th)
        out["cells"][("mov" if vm else "stop", "mov" if am else "stop")] += 1
        pa, pv = fight.pos(A, th), fight.pos(V, th)
        if pa and pv:
            out["dist"].append(math.hypot(pv[0] - pa[0], pv[1] - pa[1]))
        # HOW FAR each party actually travelled across the same window the
        # moving/stopped flag is decided over. A melee unit that is being
        # shoved by resolveCollisions while it stands and swings registers as
        # "moving" under a 0.02-tile bar, so the flag alone cannot separate
        # walking from body jitter -- these two medians can.
        for uid, key in ((A, "cstep"), (V, "vstep")):
            p0, p1 = fight.pos(uid, th - 0.25), fight.pos(uid, th + 0.05)
            if p0 and p1:
                out[key].append(math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
    out["army_s"] = army_seconds(fight, ctx.chaser_owner)
    return out


# ---------------------------------------------------------------------------
# 4. BLACKLIST / RETARGET, tape-observable half
# ---------------------------------------------------------------------------

def switching(fight, ctx):
    """Victim switching between a chaser's consecutive landed hits.

    ABANDON = the next hit is on a DIFFERENT enemy while the previous victim
    was still alive AND still within ABANDON_NEAR_TILES of the chaser at that
    moment. That is the only "gave up a reachable victim" event both sources
    can produce: the tape has no target field, and this one is decided purely
    from the damage stream plus positions.
    """
    deaths = {}
    for e in sorted(fight.damage_all, key=lambda e: e["t"]):
        if e.get("kill"):
            deaths.setdefault(e["victim"], e["t"])
    by_att = defaultdict(list)
    for e in hits_by(fight, ctx.chaser_owner, ctx.kiter_owner):
        by_att[e["attacker"]].append(e)
    out = {"pairs": 0, "same": 0, "switch": 0, "abandon": 0,
           "distinct_per_chaser": [], "run_len": [], "hits": 0}
    for att, evs in by_att.items():
        evs.sort(key=lambda e: e["t"])
        out["hits"] += len(evs)
        out["distinct_per_chaser"].append(len({e["victim"] for e in evs}))
        run = 1
        for a, b in zip(evs, evs[1:]):
            if b["t"] - a["t"] > MAX_CYCLE_S:
                out["run_len"].append(run)
                run = 1
                continue
            out["pairs"] += 1
            if a["victim"] == b["victim"]:
                out["same"] += 1
                run += 1
                continue
            out["switch"] += 1
            out["run_len"].append(run)
            run = 1
            dt = deaths.get(a["victim"])
            if dt is not None and dt <= b["t"]:
                continue          # the old victim was dead: not an abandon
            pa, pv = fight.pos(b["attacker"], b["t"]), fight.pos(a["victim"], b["t"])
            if pa and pv and math.hypot(pv[0] - pa[0], pv[1] - pa[1]) <= ABANDON_NEAR_TILES:
                out["abandon"] += 1
        out["run_len"].append(run)
    return out


def winner_of(fight, ctx):
    """"chaser" / "kiter" / "draw", by (survivors, hp remaining).

    The same ordering aoe2x.calibration's own scorer and melee_hp_report use,
    so a winner here is the winner the campaign's scoreboard means.
    """
    def rank(o):
        s = fight.sides[o]
        return ((s["survivors"] or 0), (s["hp_left"] or 0.0))
    a, b = rank(ctx.chaser_owner), rank(ctx.kiter_owner)
    if a == b:
        return "draw"
    return "chaser" if a > b else "kiter"


def agreement(fs, dicts, rundir, seeds):
    """Per-recording and pooled seed agreement of an engine run set with the
    tape's winner."""
    per, ok, tot = {}, 0, 0
    for fm in fs:
        ctx = Ctx(fm, dicts)
        w = winner_of(rff.load_tape(fm, classify=False), ctx)
        a = b = 0
        for fight in iter_engine(rundir, fm, seeds):
            b += 1
            if winner_of(fight, ctx) == w:
                a += 1
        per[fm["tag"]] = (a, b, w)
        ok += a
        tot += b
    return {"pct": pct(ok, tot), "per": per,
            "recordings_majority": sum(1 for (a, b, _w) in per.values()
                                       if b and a > b / 2)}


def load_chase(sim_dir: Path, fm, seed):
    p = sim_dir / fm["run_id"] / f"seed-{seed}.chase.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 6. HC LAND RATE (needs the classified shot stream)
# ---------------------------------------------------------------------------

def land_rate(fight, owner, max_range):
    """Landed share of every shot that had time to land, plus the two splits
    the shortfall decomposes over. Same denominator rule as rff.accuracy():
    only CENSORED is removed."""
    ss = [s for s in fight.shots if s["owner"] == owner]
    live = [s for s in ss if s["outcome"] != "CENSORED"]
    cat = Counter(s["outcome"] for s in live)

    def mv(s):
        return s["aim"] is not None and fight.moved_between(
            s["aim"], s["t"] - 0.25, s["t"] + 0.05)

    cells = {}
    # 0.6 * max_range is rff.accuracy()'s own near/far cut, reused so the two
    # modules' "near" means one thing.
    cut = 0.6 * max_range
    for name, pred in (("mover", mv), ("stander", lambda s: not mv(s)),
                       ("near", lambda s: s["dist"] <= cut),
                       ("far", lambda s: s["dist"] > cut)):
        sub = [s for s in live if pred(s)]
        cells[name] = {
            "n": len(sub),
            "hit": sum(1 for s in sub if s["outcome"] == "HIT"),
        }
    return {
        "shots": len(ss), "live": len(live), "cat": cat,
        "cells": cells,
        "range_med": med([s["dist"] for s in ss]),
        "land_d": [s["land_d"] for s in live
                   if s["outcome"] in ("WHIFF", "DODGE", "SCATTER")
                   and "land_d" in s],
    }


# ---------------------------------------------------------------------------
# pooling
# ---------------------------------------------------------------------------

class Pool:
    """Accumulates the per-fight dicts above across a family."""

    def __init__(self):
        self.lists = defaultdict(list)
        self.nums = Counter()
        self.cells = Counter()
        self.cat = Counter()

    def add(self, d, keys_list=(), keys_num=()):
        for k in keys_list:
            self.lists[k].extend(d.get(k) or [])
        for k in keys_num:
            v = d.get(k)
            if v:
                self.nums[k] += v


def fmt(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def iter_engine(runs, fm, seeds, classify=False):
    for seed in range(1, seeds + 1):
        f = rff.load_engine(runs, fm, seed, classify=classify)
        if f is not None:
            yield f


def family_groups(fights):
    g = defaultdict(list)
    for f in fights:
        g[f["matchup"]].append(f)
    return dict(sorted(g.items(), key=lambda kv: -len(kv[1])))


def section_anatomy(mf, dicts, runs, seeds, out):
    print("\n" + "=" * 118)
    print("TABLE 1 -- CHASER SWING ANATOMY. Inter-hit intervals of the melee "
          "side against the kiting side, and where the")
    print("time in each interval goes. `T/E` is the tape/engine ratio of the "
          "MEDIAN interval (E12's 1.29 headline, per family).")
    print("Decomposition columns are MEAN SECONDS PER INTERVAL: rl = the "
          "unit's own reload, oorC/oorF = out of reach while")
    print("closing / while not closing, inR = in reach and not swinging. "
          "`lost%` = intervals that left reach at all.")
    print("=" * 118)
    hdr = (f"{'family':<38} {'src':<4} {'n':>6} {'med':>6} {'mean':>6} "
           f"{'p90':>6} {'/rl':>5} {'T/E':>5} {'lost%':>6} "
           f"{'oorC':>6} {'oorF':>6} {'inR':>6}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for fam, fs in family_groups(mf).items():
        ctx0 = Ctx(fs[0], dicts)
        cols = {}
        for src in ("T", "E"):
            P = Pool()
            for fm in fs:
                ctx = Ctx(fm, dicts)
                gen = ([rff.load_tape(fm, classify=False)] if src == "T"
                       else iter_engine(runs, fm, seeds))
                for fight in gen:
                    d = anatomy(fight, ctx)
                    P.add(d, ("intervals", "oor_close", "oor_far", "in_reach",
                              "excess_to_contact", "excess_to_idle"),
                          ("n", "lost_contact"))
            iv = P.lists["intervals"]
            cols[src] = {
                "n": len(iv), "med": med(iv),
                "mean": statistics.fmean(iv) if iv else None,
                "p90": q(iv, 0.9),
                "lost": pct(P.nums["lost_contact"], len(iv)),
                "oorC": statistics.fmean(P.lists["oor_close"]) if iv else None,
                "oorF": statistics.fmean(P.lists["oor_far"]) if iv else None,
                "inR": statistics.fmean(P.lists["in_reach"]) if iv else None,
                "exc_contact": statistics.fmean(P.lists["excess_to_contact"]) if iv else None,
                "exc_idle": statistics.fmean(P.lists["excess_to_idle"]) if iv else None,
            }
        te = ratio(cols["T"]["med"], cols["E"]["med"])
        for src in ("T", "E"):
            c = cols[src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<4} {c['n']:>6} "
                  f"{fmt(c['med']):>6} {fmt(c['mean']):>6} {fmt(c['p90']):>6} "
                  f"{fmt(ratio(c['med'], ctx0.reload)):>5} "
                  f"{(fmt(te) if src == 'T' else ''):>5} "
                  f"{fmt(c['lost'], 1):>6} {fmt(c['oorC']):>6} "
                  f"{fmt(c['oorF']):>6} {fmt(c['inR']):>6}")
        rows[fam] = {"reload": ctx0.reload, "T": cols["T"], "E": cols["E"],
                     "T_over_E": te, "n_fights": len(fs),
                     "charge": ctx0.chaser in CHARGE_CHASERS}
    out["anatomy"] = rows
    # pooled headline, over melee-swing chasers only (see CHARGE_CHASERS)
    keep = {k: v for k, v in rows.items() if not v["charge"]}
    tv = [v["T"]["med"] for v in keep.values() if v["T"]["med"]]
    ev = [v["E"]["med"] for v in keep.values() if v["E"]["med"]]
    rr = [v["T_over_E"] for v in keep.values() if v["T_over_E"]]
    lostT = [v["T"]["lost"] for v in keep.values() if v["T"]["lost"] is not None]
    lostE = [v["E"]["lost"] for v in keep.values() if v["E"]["lost"] is not None]
    inrT = [v["T"]["inR"] for v in keep.values() if v["T"]["inR"] is not None]
    inrE = [v["E"]["inR"] for v in keep.values() if v["E"]["inR"] is not None]
    print("-" * len(hdr))
    print(f"{len(keep)} melee-swing families ({len(rows) - len(keep)} "
          f"charge-attack families excluded from the headline: "
          f"{', '.join(sorted(k for k, v in rows.items() if v['charge']))})")
    print(f"  median-of-family-medians  T {fmt(med(tv))}s  E {fmt(med(ev))}s   "
          f"median T/E {fmt(med(rr))}  (min {fmt(min(rr))} max {fmt(max(rr))})")
    print(f"  cycles that lose contact  T {fmt(med(lostT), 1)}%  "
          f"E {fmt(med(lostE), 1)}%     mean seconds IN REACH per cycle  "
          f"T {fmt(med(inrT))}s  E {fmt(med(inrE))}s")
    out["anatomy_headline"] = {
        "median_T_over_E": med(rr), "min": min(rr), "max": max(rr),
        "lost_T": med(lostT), "lost_E": med(lostE),
        "inreach_T": med(inrT), "inreach_E": med(inrE),
        "families": len(keep),
    }


def section_contact(mf, dicts, runs, seeds, out):
    print("\n" + "=" * 122)
    print("TABLE 2a -- THE RELOAD WINDOW AFTER A CHASER HIT. Displacement in "
          "TILES over [hit, hit+reload]; `vRad`/`cRad` are the")
    print("victim's and the chaser's displacement PROJECTED on the "
          "attacker->victim line (positive = away from / toward the victim).")
    print("`dGap` = change in separation. `lose%` = windows in which the "
          "victim left reach, `tLose` = median seconds until it did.")
    print("`vOpen/cOpen/static` = of the windows that opened a gap, the share "
          "the VICTIM opened / the CHASER opened / neither.")
    print("=" * 122)
    hdr = (f"{'family':<38} {'src':<4} {'n':>6} {'vDisp':>6} {'cDisp':>6} "
           f"{'vRad':>6} {'cRad':>6} {'dGap':>6} {'lose%':>6} {'tLose':>6} "
           f"{'vOpen%':>7} {'cOpen%':>7} {'stat%':>6}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    stop_rows = {}
    for fam, fs in family_groups(mf).items():
        cols, scols = {}, {}
        for src in ("T", "E"):
            P = Pool()
            RH = Pool()
            n = lost = hs = hm = vo = co = bs = 0
            for fm in fs:
                ctx = Ctx(fm, dicts)
                gen = ([rff.load_tape(fm, classify=False)] if src == "T"
                       else iter_engine(runs, fm, seeds))
                for fight in gen:
                    d = contact_mechanism(fight, ctx)
                    P.add(d, ("vic_disp", "cha_disp", "vic_radial",
                              "cha_radial", "d_gap", "t_lose", "onset",
                              "align_att", "align_cen"))
                    n += d["n"]; lost += d["lost"]
                    hs += d["hit_on_stopped"]; hm += d["hit_on_moving"]
                    vo += d["victim_opened"]; co += d["chaser_opened"]
                    bs += d["both_static"]
                    k = kiter_rhythm(fight, ctx)
                    RH.add(k, ("stops", "moves"), ("stopped_s", "total_s"))
            opened = vo + co + bs
            cols[src] = {
                "n": n,
                "vDisp": med(P.lists["vic_disp"]), "cDisp": med(P.lists["cha_disp"]),
                "vRad": med(P.lists["vic_radial"]), "cRad": med(P.lists["cha_radial"]),
                "dGap": med(P.lists["d_gap"]),
                "lose": pct(lost, n), "tLose": med(P.lists["t_lose"]),
                "vOpen": pct(vo, opened), "cOpen": pct(co, opened),
                "static": pct(bs, opened),
                "hit_stopped_pct": pct(hs, hs + hm),
                "onset_med": med(P.lists["onset"]),
                "align_att": med(P.lists["align_att"]),
                "align_cen": med(P.lists["align_cen"]),
            }
            scols[src] = {
                "stop_med": med(RH.lists["stops"]),
                "stop_p90": q(RH.lists["stops"], 0.9),
                "move_med": med(RH.lists["moves"]),
                "stops": len(RH.lists["stops"]),
                "stopped_frac": (RH.nums["stopped_s"] / RH.nums["total_s"]
                                 if RH.nums["total_s"] else None),
                "stops_per_min": (60.0 * len(RH.lists["stops"]) / RH.nums["total_s"]
                                  if RH.nums["total_s"] else None),
            }
        for src in ("T", "E"):
            c = cols[src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<4} {c['n']:>6} "
                  f"{fmt(c['vDisp']):>6} {fmt(c['cDisp']):>6} {fmt(c['vRad']):>6} "
                  f"{fmt(c['cRad']):>6} {fmt(c['dGap']):>6} {fmt(c['lose'], 1):>6} "
                  f"{fmt(c['tLose']):>6} {fmt(c['vOpen'], 1):>7} "
                  f"{fmt(c['cOpen'], 1):>7} {fmt(c['static'], 1):>6}")
        rows[fam] = cols
        stop_rows[fam] = scols
    out["contact"] = rows

    print("\n" + "=" * 104)
    print("TABLE 2b -- THE PHASE RACE. `hitStop%` = chaser hits landed on a "
          "victim that was NOT moving; `onset` = median")
    print("seconds from such a hit to the victim's next step. Then the "
          "KITERS' OWN rhythm, measured with no reference to")
    print("any hit: stop-run and move-run durations, stopped duty cycle, "
          "stops per kiter-minute.")
    print("=" * 104)
    print("`cosAtt`/`cosCen` = cosine of the just-hit victim's displacement "
          "with 'away from the unit that hit it' and with")
    print("'away from the chasing side's centroid' -- WHICH WAY the kiter "
          "runs, not how often.")
    hdr = (f"{'family':<38} {'src':<4} {'hitStop%':>9} {'onset':>6} "
           f"{'stopMed':>8} {'stopP90':>8} {'moveMed':>8} {'stopFrac':>9} "
           f"{'stops/min':>10} {'cosAtt':>7} {'cosCen':>7}")
    print(hdr)
    print("-" * len(hdr))
    for fam in rows:
        for src in ("T", "E"):
            c, s = rows[fam][src], stop_rows[fam][src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<4} "
                  f"{fmt(c['hit_stopped_pct'], 1):>9} {fmt(c['onset_med']):>6} "
                  f"{fmt(s['stop_med']):>8} {fmt(s['stop_p90']):>8} "
                  f"{fmt(s['move_med']):>8} {fmt(s['stopped_frac'], 3):>9} "
                  f"{fmt(s['stops_per_min'], 1):>10} "
                  f"{fmt(c['align_att']):>7} {fmt(c['align_cen']):>7}")
    out["rhythm"] = stop_rows


def section_excess(mf, dicts, runs, seeds, out):
    print("\n" + "=" * 118)
    print("TABLE 3 -- WHERE THE ENGINE'S EXTRA CHASER HITS COME FROM. "
          "`hits/cs` = chaser landed hits per chaser-ALIVE-second")
    print("(a dead chaser stops paying cadence). The four cells are every "
          "landed hit by (victim moving?, chaser moving?) at the")
    print("instant it landed, as a RATE per chaser-second, so the excess is "
          "attributable rather than merely redistributed.")
    print("`dHit` = attacker-victim distance at the landed hit; `reach` = the "
          "engine's own inRange() for the pair.")
    print("=" * 118)
    hdr = (f"{'family':<38} {'src':<4} {'hits':>7} {'armyS':>8} {'hits/cs':>8} "
           f"{'E/T':>5} {'V.mov':>6} {'V.stop':>7} {'both.mov':>9} "
           f"{'cStep':>6} {'vStep':>6} {'dHit':>6} {'p90':>6} {'reach':>6}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for fam, fs in family_groups(mf).items():
        ctx0 = Ctx(fs[0], dicts)
        cols = {}
        for src in ("T", "E"):
            cells = Counter()
            n = 0
            army = 0.0
            dist, cstep, vstep = [], [], []
            kills = 0
            for fm in fs:
                ctx = Ctx(fm, dicts)
                gen = ([rff.load_tape(fm, classify=False)] if src == "T"
                       else iter_engine(runs, fm, seeds))
                for fight in gen:
                    d = hit_states(fight, ctx)
                    cells += d["cells"]
                    n += d["n"]; army += d["army_s"]; dist += d["dist"]
                    kills += d["kills"]
                    cstep += d["cstep"]; vstep += d["vstep"]
            rate = (n / army) if army else None
            cols[src] = {
                "hits": n, "army": army, "rate": rate, "kills": kills,
                "cells": {f"{a}/{b}": c for (a, b), c in cells.items()},
                "vmov_rate": (sum(c for (a, _b), c in cells.items() if a == "mov") / army) if army else None,
                "vstop_rate": (sum(c for (a, _b), c in cells.items() if a == "stop") / army) if army else None,
                "bothmov_rate": (cells[("mov", "mov")] / army) if army else None,
                "dmed": med(dist), "dp90": q(dist, 0.9),
                "cstep": med(cstep), "vstep": med(vstep),
            }
        et = ratio(cols["E"]["rate"], cols["T"]["rate"])
        for src in ("T", "E"):
            c = cols[src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<4} {c['hits']:>7} "
                  f"{fmt(c['army'], 0):>8} {fmt(c['rate'], 4):>8} "
                  f"{(fmt(et) if src == 'E' else ''):>5} "
                  f"{fmt(c['vmov_rate'], 4):>6} {fmt(c['vstop_rate'], 4):>7} "
                  f"{fmt(c['bothmov_rate'], 4):>9} "
                  f"{fmt(c['cstep'], 3):>6} {fmt(c['vstep'], 3):>6} "
                  f"{fmt(c['dmed']):>6} {fmt(c['dp90']):>6} "
                  f"{(fmt(ctx0.reach) if src == 'T' else ''):>6}")
        rows[fam] = {"T": cols["T"], "E": cols["E"], "E_over_T": et,
                     "reach": ctx0.reach}
    out["excess"] = rows


def section_retarget(mf, dicts, runs, seeds, out):
    print("\n" + "=" * 120)
    print("TABLE 4a -- DOES THE CHASER STICK? Both columns from the DAMAGE "
          "stream alone, so tape and engine are the same statistic.")
    print("`switch%` = consecutive landed hits by one chaser that changed "
          "victim. `abandon%` = of those, the ones where the old")
    print("victim was still ALIVE and still within "
          f"{ABANDON_NEAR_TILES:.1f} tiles. `run` = median consecutive hits on one victim.")
    print("=" * 120)
    hdr = (f"{'family':<38} {'src':<4} {'hits':>7} {'pairs':>7} {'switch%':>8} "
           f"{'abandon%':>9} {'runMed':>7} {'distinct':>9}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for fam, fs in family_groups(mf).items():
        cols = {}
        for src in ("T", "E"):
            agg = Counter()
            runs_l, dist_l = [], []
            for fm in fs:
                ctx = Ctx(fm, dicts)
                gen = ([rff.load_tape(fm, classify=False)] if src == "T"
                       else iter_engine(runs, fm, seeds))
                for fight in gen:
                    d = switching(fight, ctx)
                    for k in ("pairs", "same", "switch", "abandon", "hits"):
                        agg[k] += d[k]
                    runs_l += d["run_len"]
                    dist_l += d["distinct_per_chaser"]
            cols[src] = {
                "hits": agg["hits"], "pairs": agg["pairs"],
                "switch_pct": pct(agg["switch"], agg["pairs"]),
                "abandon_pct": pct(agg["abandon"], agg["pairs"]),
                "run_med": med(runs_l),
                "distinct_med": med(dist_l),
            }
        for src in ("T", "E"):
            c = cols[src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<4} {c['hits']:>7} "
                  f"{c['pairs']:>7} {fmt(c['switch_pct'], 1):>8} "
                  f"{fmt(c['abandon_pct'], 1):>9} {fmt(c['run_med'], 1):>7} "
                  f"{fmt(c['distinct_med'], 1):>9}")
        rows[fam] = cols
    out["retarget_tape"] = rows

    print("\n" + "=" * 116)
    print("TABLE 4b -- THE ENGINE'S OWN PURSUIT-BAR LEDGER (probe-only; the "
          "tape has no target field). Rates per CHASER-MINUTE.")
    print("A melee unit chasing a RANGED target can never be lock-protected "
          "(meleeTargetLock returns false when target.isRanged()),")
    print("so every stuck-bar trip blacklists. `null%` = share of chaser-time "
          "with no target at all; `gap` = median seconds to")
    print("re-acquire; `dAband` = median distance to the victim at the moment "
          "it was blacklisted; `span` = median seconds held.")
    print("=" * 116)
    hdr = (f"{'family':<38} {'blk/min':>8} {'stuck/min':>10} {'lockHeld':>9} "
           f"{'clr/min':>8} {'bump/min':>9} {'null%':>6} {'gap':>6} "
           f"{'dAband':>7} {'span':>6}")
    print(hdr)
    print("-" * len(hdr))
    lrows = {}
    for fam, fs in family_groups(mf).items():
        agg = Counter()
        gaps, dab, spans = [], [], []
        chaser_min = 0.0
        for fm in fs:
            ctx = Ctx(fm, dicts)
            for seed in range(1, seeds + 1):
                ch = load_chase(runs, fm, seed)
                if not ch:
                    continue
                acc = ch["sides"].get(str(ctx.chaser_owner))
                if not acc or not acc["aliveTicks"]:
                    continue
                tick = ch["tick_s"]
                chaser_min += acc["aliveTicks"] * tick / 60.0
                for k in ("blacklistAdds", "stuckTrips", "lockHeld",
                          "blacklistClears", "bumpFires", "nullTargetTicks",
                          "aliveTicks", "switchedToDifferentLiving"):
                    agg[k] += acc[k]
                gaps += acc["gapToReacquireS"]
                dab += acc["distAtAbandonTiles"]
                spans += acc["chaseSpanS"]
        if not chaser_min:
            continue
        row = {
            "blk_min": agg["blacklistAdds"] / chaser_min,
            "stuck_min": agg["stuckTrips"] / chaser_min,
            "lock_held": agg["lockHeld"],
            "clr_min": agg["blacklistClears"] / chaser_min,
            "bump_min": agg["bumpFires"] / chaser_min,
            "null_pct": pct(agg["nullTargetTicks"], agg["aliveTicks"]),
            "gap_med": med(gaps), "dab_med": med(dab), "span_med": med(spans),
            "chaser_min": chaser_min,
        }
        print(f"{fam:<38} {fmt(row['blk_min'], 1):>8} {fmt(row['stuck_min'], 1):>10} "
              f"{row['lock_held']:>9} {fmt(row['clr_min'], 1):>8} "
              f"{fmt(row['bump_min'], 1):>9} {fmt(row['null_pct'], 1):>6} "
              f"{fmt(row['gap_med']):>6} {fmt(row['dab_med']):>7} "
              f"{fmt(row['span_med']):>6}")
        lrows[fam] = row
    out["retarget_engine"] = lrows


# ---------------------------------------------------------------------------
# 5. THE P2 COUNTERFACTUAL
# ---------------------------------------------------------------------------

def p2_column(fs, dicts, src, runs, seeds):
    """One column of the P2 ledger, computed identically for every source."""
    acc = {
        "fights": 0, "dur": [], "chaser_hits": 0, "chaser_army": 0.0,
        "intervals": [], "kiter_shots": 0, "kiter_live": 0, "kiter_hit": 0,
        "kiter_hit_mov": 0, "kiter_mov_n": 0, "kiter_army": 0.0,
        "chaser_hp_pts": [], "kiter_hp_pts": [], "winner_chaser": 0,
        "runs": 0, "surv": defaultdict(list),
        "chaser_dmg": 0.0, "kiter_dmg": 0.0, "kiter_hits": 0,
    }
    tape_winner = {}
    for fm in fs:
        ctx = Ctx(fm, dicts)
        gen = ([rff.load_tape(fm)] if src == "T"
               else iter_engine(runs, fm, seeds, classify=True))
        for fight in gen:
            acc["runs"] += 1
            acc["dur"].append(fight.end_t)
            a = anatomy(fight, ctx)
            acc["intervals"] += a["intervals"]
            h = hit_states(fight, ctx)
            acc["chaser_hits"] += h["n"]
            acc["chaser_army"] += h["army_s"]
            acc["kiter_army"] += army_seconds(fight, ctx.kiter_owner)
            lr = land_rate(fight, ctx.kiter_owner, ctx.kd["attack_range"])
            acc["kiter_shots"] += lr["shots"]
            acc["kiter_live"] += lr["live"]
            acc["kiter_hit"] += lr["cat"]["HIT"]
            acc["kiter_hit_mov"] += lr["cells"]["mover"]["hit"]
            acc["kiter_mov_n"] += lr["cells"]["mover"]["n"]
            # Damage LANDED, not HP removed: the damage stream is HP-clamped
            # on both sources, so this is the honest common quantity.
            for e in hits_by(fight, ctx.chaser_owner, ctx.kiter_owner):
                acc["chaser_dmg"] += e["damage"]
            for e in hits_by(fight, ctx.kiter_owner, ctx.chaser_owner):
                acc["kiter_dmg"] += e["damage"]
                acc["kiter_hits"] += 1
            cs = fight.sides[ctx.chaser_owner]
            ks = fight.sides[ctx.kiter_owner]
            acc["chaser_hp_pts"].append(
                100.0 * (cs["hp_left"] or 0) / (ctx.chaser_n * ctx.chaser_hp))
            acc["kiter_hp_pts"].append(
                100.0 * (ks["hp_left"] or 0) / (ctx.kiter_n * ctx.kiter_hp))
            win_chaser = (cs["survivors"] or 0) > 0 and (ks["survivors"] or 0) == 0
            if win_chaser:
                acc["winner_chaser"] += 1
            if src == "T":
                tape_winner[fm["tag"]] = win_chaser
            # survival curve at absolute times
            for tt in (10, 20, 30, 40, 50):
                fr = fight.frame_at(tt)
                if fight.end_t + 0.5 < tt:
                    n = sum(1 for (_x, _y, o, _h) in fr.values()
                            if o == ctx.chaser_owner)
                    # after the fight ended the frame is the last one
                    acc["surv"][tt].append(100.0 * n / ctx.chaser_n)
                else:
                    n = sum(1 for (_x, _y, o, _h) in fr.values()
                            if o == ctx.chaser_owner)
                    acc["surv"][tt].append(100.0 * n / ctx.chaser_n)
            acc["fights"] += 1
    acc["tape_winner"] = tape_winner
    return acc


def section_ledger(mf, dicts, runs, alt_runs, seeds, out, *, family, alt,
                   table, blurb):
    """The full outcome ledger for ONE family, three columns: tape, engine
    defaults, engine with one shipped-OFF rule turned on. This is the object
    the enable decision needs -- who wins, by how much, and which side's
    output is wrong."""
    fs = [f for f in mf if f["matchup"] == family]
    if not fs:
        print(f"\n(no {family} fights in scope -- skipping {alt})")
        return
    ctx0 = Ctx(fs[0], dicts)
    ALT = f"ENG+{alt}"
    cols = {
        "TAPE": p2_column(fs, dicts, "T", None, seeds),
        "ENG": p2_column(fs, dicts, "E", runs, seeds),
        ALT: p2_column(fs, dicts, "E", alt_runs, seeds),
    }
    # per-recording winner agreement against the tape, by (survivors, HP) rank
    agree = {name: agreement(fs, dicts, rundir, seeds)
             for name, rundir in (("ENG", runs), (ALT, alt_runs))}

    print("\n" + "=" * 108)
    print(f"TABLE {table} -- {family} "
          f"({len(fs)} recordings x {seeds} seeds).")
    print(blurb)
    print("=" * 108)
    C, K = ctx0.chaser, ctx0.kiter
    hdr = f"{'metric':<48} {'TAPE':>13} {'ENG':>13} {ALT:>13}"
    print(hdr)
    print("-" * len(hdr))

    def line(label, f):
        vals = []
        for k in ("TAPE", "ENG", ALT):
            try:
                vals.append(f(cols[k], k))
            except Exception:
                vals.append(None)
        print(f"{label:<44} " + " ".join(f"{('-' if v is None else v):>13}"
                                         for v in vals))

    line("runs pooled", lambda c, k: f"{c['runs']}")
    line("fight duration, median s",
         lambda c, k: fmt(med(c["dur"])))
    line(f"{C} wipes the {K} side, % of runs",
         lambda c, k: fmt(pct(c["winner_chaser"], c["runs"]), 1))
    line("winner agreement vs tape, % of seeds",
         lambda c, k: "-" if k == "TAPE" else fmt(agree[k]["pct"], 1))
    line(f"  ... recordings won on a seed majority (of {len(fs)})",
         lambda c, k: "-" if k == "TAPE" else str(agree[k]["recordings_majority"]))
    line(f"{C} HP points left (median)",
         lambda c, k: fmt(med(c["chaser_hp_pts"]), 1))
    line(f"{K} HP points left (median)",
         lambda c, k: fmt(med(c["kiter_hp_pts"]), 1))
    line(f"{C} swing interval, median s",
         lambda c, k: fmt(med(c["intervals"])))
    line(f"{C} landed hits PER RUN",
         lambda c, k: fmt(c["chaser_hits"] / c["runs"], 1))
    line(f"{C} damage landed per run",
         lambda c, k: fmt(c["chaser_dmg"] / c["runs"], 0))
    line(f"  ... vs {K} army max HP ({ctx0.kiter_n * ctx0.kiter_hp:.0f})",
         lambda c, k: fmt(100.0 * c["chaser_dmg"] / c["runs"]
                          / (ctx0.kiter_n * ctx0.kiter_hp), 1) + "%")
    line(f"{C} hits per chaser-second",
         lambda c, k: fmt(c["chaser_hits"] / c["chaser_army"], 4))
    line(f"{K} damage landed per run",
         lambda c, k: fmt(c["kiter_dmg"] / c["runs"], 0))
    line(f"  ... vs {C} army max HP ({ctx0.chaser_n * ctx0.chaser_hp:.0f})",
         lambda c, k: fmt(100.0 * c["kiter_dmg"] / c["runs"]
                          / (ctx0.chaser_n * ctx0.chaser_hp), 1) + "%")
    line(f"{K} shots (total)", lambda c, k: f"{c['kiter_shots']}")
    line(f"{K} land rate, % of resolvable shots",
         lambda c, k: fmt(pct(c["kiter_hit"], c["kiter_live"]), 1))
    line(f"{K} land rate vs a MOVING {C}, %",
         lambda c, k: fmt(pct(c["kiter_hit_mov"], c["kiter_mov_n"]), 1))
    line(f"{K} landed hits per kiter-second",
         lambda c, k: fmt(c["kiter_hit"] / c["kiter_army"], 4))
    line(f"{K} damage per resolvable shot",
         lambda c, k: fmt(c["kiter_dmg"] / c["kiter_live"]))
    for tt in (10, 20, 30, 40, 50):
        line(f"{C}s alive at t={tt}s, % of start",
             lambda c, k, tt=tt: fmt(statistics.fmean(c["surv"][tt]), 1)
             if c["surv"][tt] else None)

    print("\nper-recording winner (tape) and seed agreement:")
    print(f"{'tag':<40} {'tape winner':>14} {'ENG agree':>10} {ALT + ' agree':>14}")
    for fm in fs:
        a1 = agree["ENG"]["per"][fm["tag"]]
        a2 = agree[ALT]["per"][fm["tag"]]
        print(f"{fm['tag']:<40} {a1[2]:>14} {a1[0]:>4}/{a1[1]:<5} {a2[0]:>6}/{a2[1]:<6}")
    key = f"ledger_{alt}"
    out[key] = {k: {kk: vv for kk, vv in v.items()
                    if kk not in ("surv", "tape_winner")}
                for k, v in cols.items()}
    out[key]["agree"] = {k: v["pct"] for k, v in agree.items()}
    out[key]["surv"] = {k: {str(tt): statistics.fmean(v["surv"][tt])
                            for tt in (10, 20, 30, 40, 50) if v["surv"][tt]}
                        for k, v in cols.items()}


# ---------------------------------------------------------------------------
# 6. HC LAND RATE
# ---------------------------------------------------------------------------

def section_hc(mf, dicts, runs, p1runs, seeds, out):
    fs_all = [f for f in mf
              if "hand_cannoneer" in (f["side1"]["slug"], f["side2"]["slug"])]
    if not fs_all:
        print("\n(no hand cannoneer fights in scope -- skipping)")
        return
    print("\n" + "=" * 124)
    print("TABLE 6 -- HAND CANNONEER LAND RATE under the CURRENT engine "
          "(post R5d/B2). `land%` = HIT / every shot that had time")
    print("to land. `mov%` = share of those shots whose aim target was moving "
          "at launch; `hitMov`/`hitStd` = land rate within each.")
    print("The gap is decomposed shift-share: MIX = the engine aiming at a "
          "different moving/standing mix at the tape's own")
    print("per-cell rates; RATE = the engine hitting the tape's mix less "
          "often. `+P1` is --r5d1 reducedDamageHits.")
    print("=" * 124)
    hdr = (f"{'family':<38} {'src':<6} {'shots':>7} {'land%':>7} {'whiff%':>7} "
           f"{'dodge%':>7} {'scat%':>6} {'wast%':>6} {'mov%':>6} {'hitMov':>7} "
           f"{'hitStd':>7} {'rng':>5} {'MIX':>6} {'RATE':>6}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for fam, fs in family_groups(fs_all).items():
        cols = {}
        srcs = [("T", None), ("E", runs), ("E+P1", p1runs)]
        for src, rundir in srcs:
            cat = Counter()
            live = shots = 0
            cells = {k: Counter() for k in ("mover", "stander", "near", "far")}
            rngs, land_ds = [], []
            hcdmg = [0.0, 0, 0]   # [damage, resolvable shots, runs]
            for fm in fs:
                s1, s2 = fm["side1"], fm["side2"]
                hc_owner = s1["owner"] if s1["slug"] == "hand_cannoneer" else s2["owner"]
                mr = (s1 if s1["slug"] == "hand_cannoneer" else s2)
                gen = ([rff.load_tape(fm)] if src == "T"
                       else iter_engine(rundir, fm, seeds, classify=True))
                for fight in gen:
                    d = land_rate(fight, hc_owner,
                                  dicts[f"{mr['civ']}|hand_cannoneer"]["attack_range"])
                    cat += d["cat"]; live += d["live"]; shots += d["shots"]
                    for k in cells:
                        cells[k]["n"] += d["cells"][k]["n"]
                        cells[k]["hit"] += d["cells"][k]["hit"]
                    if d["range_med"] is not None:
                        rngs.append(d["range_med"])
                    land_ds += d["land_d"]
                    # DAMAGE, not just land rate. P1 turns a failed accuracy
                    # roll from "pays full" into "pays half if the displaced
                    # landing point still overlaps a body", so it raises the
                    # land rate and LOWERS the damage per shot at the same
                    # time; the land rate alone cannot say whether the engine
                    # HC's output matches the tape's.
                    dmg = sum(e["damage"] for e in fight.damage
                              if e.get("attacker_owner") == hc_owner)
                    hcdmg[0] += dmg
                    hcdmg[1] += d["live"]
                    hcdmg[2] += 1
            denom = cells["mover"]["n"] + cells["stander"]["n"]
            cols[src] = {
                "shots": shots, "live": live,
                "land": pct(cat["HIT"], live),
                "whiff": pct(cat["WHIFF"], live), "dodge": pct(cat["DODGE"], live),
                "scat": pct(cat["SCATTER"], live), "waste": pct(cat["WASTE"], live),
                "unres": pct(cat["UNRESOLVED"], live),
                "mov_share": pct(cells["mover"]["n"], denom),
                "hit_mov": pct(cells["mover"]["hit"], cells["mover"]["n"]),
                "hit_std": pct(cells["stander"]["hit"], cells["stander"]["n"]),
                "near_share": pct(cells["near"]["n"],
                                  cells["near"]["n"] + cells["far"]["n"]),
                "hit_near": pct(cells["near"]["hit"], cells["near"]["n"]),
                "hit_far": pct(cells["far"]["hit"], cells["far"]["n"]),
                "rng": med(rngs), "land_d": med(land_ds),
                "dmg_per_shot": (hcdmg[0] / hcdmg[1]) if hcdmg[1] else None,
                "dmg_per_run": (hcdmg[0] / hcdmg[2]) if hcdmg[2] else None,
            }
        # shift-share against the tape
        T = cols["T"]
        for src in ("E", "E+P1"):
            E = cols[src]
            mix = rate = None
            if None not in (T["mov_share"], E["mov_share"], T["hit_mov"],
                            T["hit_std"], E["hit_mov"], E["hit_std"]):
                sT, sE = T["mov_share"] / 100.0, E["mov_share"] / 100.0
                mix = ((sE - sT) * T["hit_mov"] + ((1 - sE) - (1 - sT)) * T["hit_std"])
                rate = (sE * (E["hit_mov"] - T["hit_mov"])
                        + (1 - sE) * (E["hit_std"] - T["hit_std"]))
            E["mix"], E["rate"] = mix, rate
        T["mix"] = T["rate"] = None
        for src, _ in srcs:
            c = cols[src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<6} {c['shots']:>7} "
                  f"{fmt(c['land'], 1):>7} {fmt(c['whiff'], 1):>7} "
                  f"{fmt(c['dodge'], 1):>7} {fmt(c['scat'], 1):>6} "
                  f"{fmt(c['waste'], 1):>6} {fmt(c['mov_share'], 1):>6} "
                  f"{fmt(c['hit_mov'], 1):>7} {fmt(c['hit_std'], 1):>7} "
                  f"{fmt(c['rng'], 1):>5} {fmt(c['mix'], 1):>6} "
                  f"{fmt(c['rate'], 1):>6}")
        rows[fam] = cols

    print("\n" + "=" * 96)
    print("TABLE 6b -- the same shots split by LAUNCH RANGE instead "
          "(`near` = within 0.6 x attack_range, rff.accuracy()'s own cut),")
    print("plus `landD` = median distance from the victim at which a "
          "NON-landing shot arrived (the arrival resolution).")
    print("=" * 96)
    hdr = (f"{'family':<38} {'src':<6} {'near%':>7} {'hitNear':>8} "
           f"{'hitFar':>7} {'landD':>7}")
    print(hdr)
    print("-" * len(hdr))
    for fam, cols in rows.items():
        for src in ("T", "E", "E+P1"):
            c = cols[src]
            print(f"{(fam if src == 'T' else ''):<38} {src:<6} "
                  f"{fmt(c['near_share'], 1):>7} {fmt(c['hit_near'], 1):>8} "
                  f"{fmt(c['hit_far'], 1):>7} {fmt(c['land_d'], 2):>7}")
    out["hc"] = rows

    print("\n" + "=" * 112)
    print("TABLE 6c -- THE P1 FLIP CRITERION. Land rate is not the quantity "
          "P1 moves: P1 turns a failed accuracy roll from")
    print("'pays full' into 'pays half if the displaced landing point still "
          "overlaps a body', so it raises land% and lowers")
    print("DAMAGE PER SHOT at once. `d/shot` is HC damage landed per "
          "resolvable shot; `agree` is winner agreement with the tape")
    print("(seeds, and recordings won on a majority of seeds).")
    print("=" * 112)
    hdr = (f"{'family':<38} {'n_rec':>6} {'d/shot T':>9} {'d/shot E':>9} "
           f"{'d/shot E+P1':>12} {'agree E':>16} {'agree E+P1':>16}")
    print(hdr)
    print("-" * len(hdr))
    crit = {}
    for fam, fs in family_groups(fs_all).items():
        aE = agreement(fs, dicts, runs, seeds)
        aP = agreement(fs, dicts, p1runs, seeds)
        c = rows[fam]
        print(f"{fam:<38} {len(fs):>6} "
              f"{fmt(c['T']['dmg_per_shot']):>9} "
              f"{fmt(c['E']['dmg_per_shot']):>9} "
              f"{fmt(c['E+P1']['dmg_per_shot']):>12} "
              f"{(fmt(aE['pct'], 1) + '%  ' + str(aE['recordings_majority']) + '/' + str(len(fs))):>16} "
              f"{(fmt(aP['pct'], 1) + '%  ' + str(aP['recordings_majority']) + '/' + str(len(fs))):>16}")
        crit[fam] = {"agree_E": aE["pct"], "agree_P1": aP["pct"],
                     "rec_E": aE["recordings_majority"],
                     "rec_P1": aP["recordings_majority"],
                     "n_rec": len(fs),
                     "dps_T": c["T"]["dmg_per_shot"],
                     "dps_E": c["E"]["dmg_per_shot"],
                     "dps_P1": c["E+P1"]["dmg_per_shot"]}
    out["hc_criterion"] = crit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-runs-dir", type=Path, default=DEFAULT_RUNS)
    ap.add_argument("--p2-runs-dir", type=Path, default=DEFAULT_P2_RUNS)
    ap.add_argument("--p1-runs-dir", type=Path, default=DEFAULT_P1_RUNS)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--section", default="all",
                    choices=["all", "anatomy", "contact", "excess",
                             "retarget", "p2", "hc"])
    ap.add_argument("--families", default=None,
                    help="comma-separated matchup filter")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--print-tags", action="store_true",
                    help="print the corpus as a comma-separated tag list and "
                         "exit -- feed straight to c1_chase_probe.mjs "
                         "--tags-file so the two tools cannot drift")
    a = ap.parse_args()

    dicts = load_dicts()
    mf = chaser_fights(load_manifest())
    if a.families:
        want = set(a.families.split(","))
        mf = [f for f in mf if f["matchup"] in want]
    if a.print_tags:
        print(",".join(f["tag"] for f in mf))
        return
    print(f"chaser corpus: {len(mf)} recordings, "
          f"{len(family_groups(mf))} families, {a.seeds} engine seeds each")
    print(f"engine runs: {a.sim_runs_dir}")

    out = {}
    S = a.section
    if S in ("all", "anatomy"):
        section_anatomy(mf, dicts, a.sim_runs_dir, a.seeds, out)
    if S in ("all", "contact"):
        section_contact(mf, dicts, a.sim_runs_dir, a.seeds, out)
    if S in ("all", "excess"):
        section_excess(mf, dicts, a.sim_runs_dir, a.seeds, out)
    if S in ("all", "retarget"):
        section_retarget(mf, dicts, a.sim_runs_dir, a.seeds, out)
    if S in ("all", "p2"):
        section_ledger(
            mf, dicts, a.sim_runs_dir, a.p2_runs_dir, a.seeds, out,
            family="champion__vs__heavy_cav_archer", alt="P2", table="5",
            blurb=("P2 = R5D1.trailingWindowLead, shipped OFF. TAPE is the "
                   "recording; ENG is HEAD defaults; ENG+P2 is "
                   "--r5d1 trailingWindowLead."))
    if S in ("all", "hc"):
        section_hc(mf, dicts, a.sim_runs_dir, a.p1_runs_dir, a.seeds, out)
        section_ledger(
            mf, dicts, a.sim_runs_dir, a.p1_runs_dir, a.seeds, out,
            family="hand_cannoneer__vs__heavy_camel", alt="P1", table="6d",
            blurb=("P1 = R5D1.reducedDamageHits, shipped OFF because enabling "
                   "it flips this family. TAPE is the recording; ENG is HEAD "
                   "defaults; ENG+P1 is --r5d1 reducedDamageHits."))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str),
                          encoding="utf-8")
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
