"""R5: what the six ranged-vs-ranged recordings do that the engine does not.

Round 5's scope is the six ranged fights (arbalester / imp_elite_skirm /
heavy_cav_archer / hand_cannoneer, each pair once). Three of them are on
target after E15; three are not, and one of those three has the WRONG WINNER.
This module measures the firefight itself rather than its score, from the one
signal these recordings have that the melee corpus never had: a MISSILES
stream, one row per projectile per frame, so every shot is observable from
launch to impact whether or not it ever landed.

ONE IMPLEMENTATION, TWO SOURCES
-------------------------------
Everything below is computed by the same functions over a normalised
``Fight`` -- {frames (10 Hz positions), damage, shots, sides} -- built either
from a recording's three .jsonl.gz streams or from an engine run's
``seed-N.shots.json`` (tools/simjs/ranged_shot_dump.mjs). A tape number and an
engine number are therefore the same statistic, never two implementations that
happen to be named alike.

HOW A SHOT IS RECONSTRUCTED FROM A TAPE
---------------------------------------
Each missile id is one projectile. Its first row is the LAUNCH (t, shooter via
``fired_from``, launch x/y). Its last row with a position CHANGE is the
IMPACT: every flight ends with 1 or 3 stationary rows as the sprite is torn
down, and the flight itself is a straight line -- measured over the corpus,
the maximum perpendicular deviation of a track from its own launch->impact
chord is 0.001 tiles. The tape's arrows do NOT home: every flight is a straight
line to a point fixed at launch (which is not the same as aiming AT the
target -- that point is led ahead of a moving one). Implied speed from |impact-launch| / flight time reproduces
the dat's projectile_speed to three digits (arbalester 6.997 vs 7.0).

HIT OR NOT is then decided by pairing, not by guessing: a shot HIT iff the
damage stream has an event from that same shooter within PAIR_TOL of the
impact time. Over the six tapes this pairing consumes EVERY damage event with
a time residual of exactly 0.000 s -- there is no slack in it, and the shots
left over are exactly the shots that did nothing.

WHAT THE SHOT WAS AIMED AT is inferred identically on both sides: the enemy
that comes closest to the aim point at any instant of the flight. It is NOT
"nearest at launch", because the tape LEADS its shots -- see _classify. The
inference is validated, not trusted: 1,116/1,147 (97.3%) against the tape
hits whose victim the pairing already names, and 4,577/4,608 (99.3%) against
the TRUE target the engine dump's probe records.

Each shot then classifies into exactly one outcome:

    HIT        paired with a damage event
    WASTE      the aim target DIED between launch and impact (overkill paid
               through projectile travel time -- invisible in the damage
               stream, which is HP-clamped on both sides)
    WHIFF      the shot arrived within ON_TARGET_TILES of its living target
               and did nothing -- a genuine accuracy failure
    DODGE      it landed WIDE of a target that had moved during the flight
    SCATTER    it landed wide of a target that had not moved
    CENSORED   still airborne when the recording stopped

    PYTHONPATH=. python tools/simjs/ranged_fire_forensics.py \
        --sim-runs-dir D:/AI/aoe2_golden/simruns_r5_ranged
    ... --section cadence|e9|accuracy|geometry|focus|attrition|timeline|ledger|all
    ... --tags arbalester__vs__heavy_cav_archer
    ... --seeds 20          engine seeds to pool (default 20)
    ... --json out.json     machine-readable dump of every table
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import math
import statistics
from collections import defaultdict, Counter
from pathlib import Path

from aoe2x.paths import REPO_ROOT

CALIB = REPO_ROOT / "data" / "calibration"
TAPES = Path("D:/AI/aoe2_golden/tapes")
DEFAULT_SIMRUNS = Path("D:/AI/aoe2_golden/simruns_r5_ranged")

R5_TAGS = [
    "arbalester__vs__hand_cannoneer",
    "arbalester__vs__heavy_cav_archer",
    "arbalester__vs__imp_elite_skirm",
    "imp_elite_skirm__vs__hand_cannoneer",
    "imp_elite_skirm__vs__heavy_cav_archer",
    "heavy_cav_archer__vs__hand_cannoneer",
]

SLUG_BACK = {
    "arb": "arbalester", "skirm": "imp_elite_skirm",
    "HCA": "heavy_cav_archer", "HC": "hand_cannoneer",
}

SHORT = {
    "arbalester": "arb", "imp_elite_skirm": "skirm",
    "heavy_cav_archer": "HCA", "hand_cannoneer": "HC",
}

# A shot is paired to a damage event when the event lands within this of the
# reconstructed impact. Deliberately tight: on tape the residual is exactly
# 0.000 s for all 1,147 pairs (the damage row and the projectile's terminal
# row are written on the same frame), and in the engine the impact callback
# fires on the tick the projectile arrives, i.e. within one 1/60 s tick of the
# analytic launch + dist/speed. Anything wider would start stealing a
# shooter's NEXT shot, so the tolerance is checked (`pair_residual`) rather
# than assumed.
PAIR_TOL = 0.05

# Displacement (tiles) that makes a unit "moving" between two position
# samples. Same bar as melee_lock_forensics/melee_walk_forensics so the
# "moving" column means one thing across the campaign: the slowest unit here
# covers ~0.10 tiles per sample, so 0.02 is a fifth of a real step and far
# above position quantisation.
STEP_TILES = 0.02

# How far the aim target must have travelled between launch and impact for a
# non-landing shot to count as DODGED rather than WHIFFED. One tape sample of
# the slowest unit here is ~0.10 tiles, so 0.15 is "moved for more than a
# sample", not "jittered".
DODGE_TILES = 0.15

# How close to the living aim target a non-landing shot arrived. Landed tape
# hits sit 0.25-0.32 tiles from their victim (the projectile sprite's anchor
# offset; p90 0.39 over 1,147 pairs), so a shot inside this bar reached the
# unit and did nothing -- an accuracy failure -- while a wider one physically
# missed.
ON_TARGET_TILES = 0.45

# The engine's own ranged reach, BattleUnit.inRange(): attack_range * TILE +
# MELEE_RANGE_BUFFER + both physics radii, in pixels. Same formula
# melee_bout_forensics.engine_reach uses (validated there against the melee
# corpus to within 0.02 tiles of the observed contact distance); for ranged
# units the buffer and radii are a small correction on a large range, but it
# is the correction the engine actually applies, so range-utilisation numbers
# are quoted against it and not against the bare attack_range.
TILE = 30.0
MELEE_RANGE_BUFFER_PX = 5.0
MIN_PHYSICS_RADIUS_PX = 5.0

FIRE_CYCLE_QUANTUM = 2.0 / 3.0  # engine constant (E9), mirrored for prediction


def physics_radius_px(u) -> float:
    tiles = u.get("collision_size")
    if tiles is None:
        tiles = u.get("outline_size") or 0.2
    return max(MIN_PHYSICS_RADIUS_PX, tiles * TILE)


def engine_reach(attacker, defender) -> float:
    return (attacker["attack_range"] * TILE + MELEE_RANGE_BUFFER_PX
            + physics_radius_px(attacker) + physics_radius_px(defender)) / TILE


# ---------------------------------------------------------------------------
# normalised fight
# ---------------------------------------------------------------------------

class Fight:
    """{frames, damage, shots, sides} -- the only thing the measurements see."""

    def __init__(self, source, tag, duration_s, frames, damage, shots, sides,
                 end_t=None):
        self.source = source          # "tape" | "engine"
        self.tag = tag
        # END OF FIGHT. The engine stops the instant a side is wiped
        # (`while (sim.winner === null)`), so every tape statistic has to be
        # cut at the same event or the two are not the same measurement. They
        # were not: the recorder keeps streaming for a fixed ~17-20 s after
        # the last unit dies, and the manifest's `duration_s` is the STREAM
        # length, not the combat length. See load_tape.
        self.end_t = duration_s if end_t is None else end_t
        self.duration_s = self.end_t
        self.stream_end_s = duration_s
        # Full streams: lookups (a projectile in flight at the wipe still has
        # to resolve, and a death time may be needed either side of the cut).
        self.frames_all = frames
        self.damage_all = damage
        self.shots_all = shots
        # Truncated streams: every aggregate below iterates these.
        self.frames = [f for f in frames if f[0] <= self.end_t + 1e-9]
        self.damage = [e for e in damage if e["t"] <= self.end_t + 1e-9]
        self.shots = [x for x in shots if x["t"] <= self.end_t + 1e-9]
        self.sides = sides            # {owner: {slug, count, hp0, hp_left, survivors}}
        self._ts = [f[0] for f in self.frames_all]

    # -- position helpers ---------------------------------------------------
    def frame_at(self, t):
        i = bisect.bisect_left(self._ts, t)
        return self.frames_all[min(max(i, 0), len(self.frames_all) - 1)][1]

    def pos(self, uid, t):
        """Linearly interpolated position of `uid` at `t`, or None if unknown."""
        ts, fr = self._ts, self.frames_all
        i = bisect.bisect_left(ts, t)
        lo = max(0, min(i - 1, len(fr) - 1))
        hi = max(0, min(i, len(fr) - 1))
        a = fr[lo][1].get(uid)
        b = fr[hi][1].get(uid)
        if a is None and b is None:
            return None
        if a is None:
            return b[0], b[1]
        if b is None:
            return a[0], a[1]
        t0, t1 = fr[lo][0], fr[hi][0]
        if t1 <= t0:
            return a[0], a[1]
        w = max(0.0, min(1.0, (t - t0) / (t1 - t0)))
        return a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w

    def moved_between(self, uid, t0, t1):
        """Did `uid` change position at any sample inside (t0, t1]?"""
        ts, fr = self._ts, self.frames_all
        i = bisect.bisect_left(ts, t0)
        prev = None
        while i < len(fr) and fr[i][0] <= t1 + 1e-9:
            p = fr[i][1].get(uid)
            if p is not None:
                if prev is not None and math.hypot(p[0] - prev[0], p[1] - prev[1]) > STEP_TILES:
                    return True
                prev = (p[0], p[1])
            i += 1
        return False

    def lifetime(self, uid):
        """(first_seen, last_seen) for a unit, capped at the end of the fight."""
        first = last = None
        for t, fr in self.frames:
            if uid in fr:
                if first is None:
                    first = t
                last = t
        return first, last


def _tape_rows(tag, stream):
    p = TAPES / tag / f"{tag}.{stream}.jsonl.gz"
    with gzip.open(p, "rt") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _pair_shots(shots, damage, tol=PAIR_TOL):
    """Attach `hit` (the damage event) to each shot; returns time residuals.

    Greedy nearest-in-time within `tol`, each damage event consumed at most
    once, matched only against its own shooter's events.
    """
    by_att = defaultdict(list)
    for e in damage:
        by_att[e["attacker"]].append(e)
    for v in by_att.values():
        v.sort(key=lambda e: e["t"])
    used = set()
    residuals = []
    for s in sorted(shots, key=lambda s: s["impact_t"]):
        cands = by_att.get(s["shooter"], [])
        best = None
        for i, e in enumerate(cands):
            if (s["shooter"], i) in used:
                continue
            d = e["t"] - s["impact_t"]
            if abs(d) <= tol and (best is None or abs(d) < abs(best[1])):
                best = (i, d)
        if best is not None:
            used.add((s["shooter"], best[0]))
            s["hit"] = cands[best[0]]
            residuals.append(best[1])
        else:
            s["hit"] = None
    n_unpaired = sum(len(v) for v in by_att.values()) - len(used)
    return residuals, n_unpaired


def _classify(fight):
    """Stamp aim target + outcome on every shot. See the module docstring."""
    deaths = {}
    for e in sorted(fight.damage_all, key=lambda e: e["t"]):
        if e.get("kill"):
            deaths.setdefault(e["victim"], e["t"])
    t_end = fight.frames_all[-1][0] if fight.frames_all else fight.stream_end_s
    inf_ok = inf_n = 0
    for s in fight.shots_all:
        # AIM TARGET: the enemy that comes closest to the aim point at any
        # instant of the flight.
        #
        # NOT "nearest at launch": the tape LEADS its shots. Restricted to
        # tape hits whose victim is known from the pairing, |aim point -
        # victim| is 0.25-0.32 tiles when the victim stood still, but for a
        # victim that MOVED during the flight it is 0.50-0.88 at launch and
        # 0.22-0.38 at impact -- consistently, on all six sides that landed
        # such a shot. The arrow is fired at where the target WILL BE, which
        # is also why the tape's hand cannoneer flies shots out to 9.3 tiles
        # against a nominal 7-tile range. Minimising over the whole flight is
        # right for a led aim point AND for the engine's frozen one (whose
        # minimum falls at launch), so one rule serves both sources.
        best, bd = None, 1e9
        for uid, (_ux, _uy, uo, _hp) in fight.frame_at(s["t"]).items():
            if uo == s["owner"]:
                continue
            for j in range(7):
                tt = s["t"] + (s["impact_t"] - s["t"]) * j / 6.0
                p = fight.pos(uid, tt)
                if p is None:
                    continue
                d = math.hypot(p[0] - s["ix"], p[1] - s["iy"])
                if d < bd:
                    bd, best = d, uid
        s["aim"] = best if bd <= 0.9 else None
        s["aim_d"] = bd
        if s.get("true_target") is not None and s["hit"] is not None:
            inf_n += 1
            inf_ok += int(s["aim"] == s["true_target"])
        elif s["hit"] is not None:
            inf_n += 1
            inf_ok += int(s["aim"] == s["hit"]["victim"])

        if s["hit"] is not None:
            s["outcome"] = "HIT"
            continue
        if s.get("censored") or s["impact_t"] > t_end - 0.3:
            s["outcome"] = "CENSORED"
            continue
        tgt = s["aim"]
        if tgt is None:
            s["outcome"] = "UNRESOLVED"
            continue
        dt = deaths.get(tgt)
        if dt is not None and s["t"] <= dt <= s["impact_t"] + 0.06:
            s["outcome"] = "WASTE"
            continue
        pl = fight.pos(tgt, s["t"])
        pi = fight.pos(tgt, s["impact_t"])
        if pl is None or pi is None:
            s["outcome"] = "WASTE"
            continue
        s["tgt_move"] = math.hypot(pi[0] - pl[0], pi[1] - pl[1])
        # WHERE the shot landed relative to the still-living target it was
        # aimed at. Landed hits sit 0.25-0.32 tiles from their victim (the
        # projectile's sprite anchor offset, measured over 1,147 tape pairs,
        # p90 0.39), so ON_TARGET_TILES = 0.45 is "the arrow arrived on the
        # unit and did nothing" -- an accuracy failure -- while anything
        # wider physically missed.
        s["land_d"] = math.hypot(s["ix"] - pi[0], s["iy"] - pi[1])
        if s["land_d"] <= ON_TARGET_TILES:
            s["outcome"] = "WHIFF"
        else:
            s["outcome"] = "DODGE" if s["tgt_move"] > DODGE_TILES else "SCATTER"
    fight.inference = (inf_ok, inf_n)


def load_tape(fight_meta) -> Fight:
    tag = fight_meta["tag"]
    frames = {}
    for r in _tape_rows(tag, "units"):
        frames.setdefault(round(r["t"], 3), {})[r["id"]] = (
            r["x"], r["y"], r["owner"], r.get("hp"))
    frames = sorted(frames.items())
    damage = list(_tape_rows(tag, "damage"))

    tracks = defaultdict(list)
    for r in _tape_rows(tag, "missiles"):
        tracks[r["id"]].append(r)
    shots = []
    for mid, tr in tracks.items():
        tr.sort(key=lambda r: r["t"])
        last_move = 0
        for i in range(1, len(tr)):
            if (abs(tr[i]["x"] - tr[i - 1]["x"]) > 1e-6
                    or abs(tr[i]["y"] - tr[i - 1]["y"]) > 1e-6):
                last_move = i
        imp = tr[last_move]
        shots.append({
            "t": tr[0]["t"], "owner": tr[0]["owner"], "shooter": tr[0]["fired_from"],
            "sx": tr[0]["x"], "sy": tr[0]["y"], "ix": imp["x"], "iy": imp["y"],
            "impact_t": imp["t"],
            "dist": math.hypot(imp["x"] - tr[0]["x"], imp["y"] - tr[0]["y"]),
            # a flight whose sprite was never torn down was still airborne
            "censored": (len(tr) - 1 - last_move) == 0,
            "true_target": None,
        })
    shots.sort(key=lambda s: s["t"])

    summary = json.loads((TAPES / tag / f"{tag}.summary.json").read_text())
    sides = {}
    for key, sd in summary["sides"].items():
        sides[sd["owner"]] = {
            "slug": None, "count": sd["start_count"],
            "survivors": sd["survivors"], "hp_left": sd["hp_remaining"],
        }
    for side in (fight_meta["side1"], fight_meta["side2"]):
        sides[side["owner"]]["slug"] = side["slug"]
        sides[side["owner"]]["civ"] = side["civ"]

    # WHERE THE FIGHT ENDS. The manifest's duration_s is the recorder's
    # stream length: over these six recordings it runs 17.5-19.6 s PAST the
    # moment a side hits zero units (arbalester v hand_cannoneer: manifest
    # 34.69 s, last unit dies at 17.92 s). Everything after that is a
    # survivor standing in an empty box, which deflates every per-second and
    # per-army-second statistic and makes the engine look ~0.6x too fast when
    # in four of the six fights it is actually SLOWER than the tape. The
    # honest cut is the engine's own stop condition -- first frame at which a
    # side has no living unit -- and it is taken from the position stream, so
    # a fight that never wipes falls back to the stream end.
    wipe_t = None
    for t, fr in frames:
        counts = Counter(o for (_x, _y, o, _h) in fr.values())
        if any(counts.get(o, 0) == 0 for o in sides):
            wipe_t = t
            break
    stream_end = fight_meta.get("duration_s") or frames[-1][0]

    f = Fight("tape", tag, stream_end, frames, damage, shots, sides,
              end_t=wipe_t if wipe_t is not None else stream_end)
    f.residuals, f.unpaired = _pair_shots(shots, damage)
    _classify(f)
    return f


def load_engine(sim_dir: Path, fight_meta, seed: int) -> Fight | None:
    p = sim_dir / fight_meta["run_id"] / f"seed-{seed}.shots.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    frames = [(fr["t"], {u[0]: (u[1], u[2], u[3], u[4]) for u in fr["u"]})
              for fr in raw["frames"]]
    shots = []
    for m in raw["missiles"]:
        if "tx" not in m:      # a shot with no target snapshot: unusable
            continue
        # LANDING POINT. `tx, ty` is the target's position at launch -- the
        # point the PRE-R5b engine froze its impact at, which is why it was
        # the right field when this module was written. Since R5b the shot
        # flies to a ballistic intercept, displaced again on a failed accuracy
        # roll, and ranged_shot_dump.mjs now reads that true endpoint off the
        # projectile as `ax, ay` (with the flight time to match). Prefer it
        # when the dump carries it; a dump written before that change has no
        # `ax`, so those files reproduce exactly as before.
        ix, iy = (m["ax"], m["ay"]) if "ax" in m else (m["tx"], m["ty"])
        shots.append({
            "t": m["t"], "owner": m["owner"], "shooter": m["fired_from"],
            "sx": m["sx"], "sy": m["sy"], "ix": ix, "iy": iy,
            "impact_t": m["impact_t"],
            "dist": m.get("flight_tiles", m["dist_tiles"]),
            "censored": False, "true_target": m.get("target"),
            "planned": m.get("planned"),
            # The target's position at launch, kept alongside the landing
            # point so the LEAD the engine actually applied -- landing point
            # minus launch-time target position -- is observable on every
            # shot, not only on the ones that connected.
            "launch_tx": m["tx"], "launch_ty": m["ty"],
        })
    shots.sort(key=lambda s: s["t"])
    sides = {}
    for owner, sd in raw["sides"].items():
        sides[int(owner)] = {
            "slug": sd["slug"], "civ": sd["civ"], "count": sd["start_count"],
            "survivors": sd["survivors"], "hp_left": sd["hp_remaining"],
        }
    f = Fight("engine", fight_meta["tag"], raw["duration_s"],
              frames, raw["damage"], shots, sides)
    f.residuals, f.unpaired = _pair_shots(shots, raw["damage"])
    _classify(f)
    return f


# ---------------------------------------------------------------------------
# small stats helpers
# ---------------------------------------------------------------------------

def q(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    i = p * (len(s) - 1)
    lo = int(i)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def med(vals):
    return statistics.median(vals) if vals else None


def r(x, n=2):
    return None if x is None else round(x, n)


def pct(a, b):
    return None if not b else 100.0 * a / b


# ---------------------------------------------------------------------------
# 1. FIRE CADENCE
# ---------------------------------------------------------------------------

def reach_share(fight, owner, reach):
    """Per living-unit sample of this side, was ANY living enemy inside `reach`?

    Returns (unit_seconds, in_reach_seconds). This is the denominator the
    duty-cycle question actually needs: a unit with nothing in range is not
    idling, it is out of the fight, and the two have completely different
    fixes.
    """
    tot = inr = 0.0
    prev_t = None
    for t, fr in fight.frames:
        dt = (t - prev_t) if prev_t is not None else 0.0
        prev_t = t
        if dt <= 0:
            continue
        foes = [(x, y) for (x, y, o, _h) in fr.values() if o != owner]
        for uid, (x, y, o, _h) in fr.items():
            if o != owner:
                continue
            tot += dt
            for fx, fy in foes:
                if math.hypot(fx - x, fy - y) <= reach:
                    inr += dt
                    break
    return tot, inr


def cadence(fight, owner, reload_s, reach=None):
    """Launch-to-launch gaps for one side, split by whether the shooter moved
    during the cycle -- the E9 law's own two branches -- plus the same split
    for landed-HIT-to-landed-HIT gaps (the melee corpus's only observable).

    Also returns the two duration factors the ledger needs:
      shots        total launches by this side
      army_secs    summed unit lifetimes (a dead unit stops paying cadence)
      fire_frac    shots / (army_secs / predicted-cycle) -- 1.0 means every
                   unit fired on cooldown for its whole life.
    """
    by_shooter = defaultdict(list)
    for s in fight.shots:
        if s["owner"] == owner:
            by_shooter[s["shooter"]].append(s)
    moved, stood = [], []
    for lst in by_shooter.values():
        lst.sort(key=lambda s: s["t"])
        for a, b in zip(lst, lst[1:]):
            gap = b["t"] - a["t"]
            if gap > 12.0:      # not a cycle: the unit stopped fighting
                continue
            (moved if fight.moved_between(a["shooter"], a["t"], b["t"]) else
             stood).append(gap)

    hitgaps = []
    by_att = defaultdict(list)
    for e in fight.damage:
        if e.get("attacker_owner") == owner:
            by_att[e["attacker"]].append(e["t"])
    for v in by_att.values():
        v.sort()
        hitgaps += [b - a for a, b in zip(v, v[1:]) if b - a <= 12.0]

    ids = {uid for uid, (_x, _y, o, _h) in fight.frames[0][1].items() if o == owner}
    for _t, fr in fight.frames:
        ids |= {uid for uid, (_x, _y, o, _h) in fr.items() if o == owner}
    army_secs = 0.0
    for uid in ids:
        a, b = fight.lifetime(uid)
        if a is not None:
            army_secs += (b - a) + 0.1
    q_cycle = math.ceil(reload_s / FIRE_CYCLE_QUANTUM - 1e-9) * FIRE_CYCLE_QUANTUM
    n_shots = sum(1 for s in fight.shots if s["owner"] == owner)
    obs_cycle = med(moved + stood) or q_cycle
    tot_s, inr_s = reach_share(fight, owner, reach) if reach else (army_secs, army_secs)

    # DUTY DECOMPOSITION, boundary-free.
    #
    # Each unit's life splits into three parts: the time BEFORE its first
    # launch, its FIRING WINDOW (first launch -> last launch), and the time
    # after. Inside the window a unit with k launches paid (k-1) cycles, so
    #     duty_in_window = sum(k-1) * cycle / sum(window)
    # is 1.0 exactly when every unit fired on cooldown for the whole window,
    # with no +1 boundary term to inflate a short window (which is what made
    # the naive shots/in-reach-seconds version read >1 for hand cannoneer).
    # The other two parts are reported as shares of army-seconds, so
    # pre + window + post == 1 and the whole idle budget is accounted.
    by_sh = defaultdict(list)
    for s in fight.shots:
        if s["owner"] == owner:
            by_sh[s["shooter"]].append(s["t"])
    win_s = cyc_paid = pre_s = post_s = 0.0
    for uid, tl in by_sh.items():
        tl.sort()
        a, b = fight.lifetime(uid)
        if a is None:
            continue
        win_s += tl[-1] - tl[0]
        cyc_paid += len(tl) - 1
        pre_s += max(0.0, tl[0] - a)
        post_s += max(0.0, (b + 0.1) - tl[-1])
    silent_s = army_secs - (win_s + pre_s + post_s)   # units that never fired
    return {
        "shots": n_shots,
        "sec_per_shot": r(army_secs / n_shots, 3) if n_shots else None,
        "duty": r(obs_cycle / (army_secs / n_shots), 3) if n_shots else None,
        "duty_in_window": r(cyc_paid * obs_cycle / win_s, 3) if win_s else None,
        "window_share": r(pct(win_s, army_secs), 1) if army_secs else None,
        "pre_share": r(pct(pre_s, army_secs), 1) if army_secs else None,
        "post_share": r(pct(post_s + silent_s, army_secs), 1) if army_secs else None,
        "in_reach_share": r(pct(inr_s, tot_s), 1) if tot_s else None,
        "reload": round(reload_s, 3),
        "q_cycle": round(q_cycle, 3),
        "moved_n": len(moved), "moved_med": r(med(moved), 3),
        "stood_n": len(stood), "stood_med": r(med(stood), 3),
        "gap_p10": r(q(moved + stood, 0.10), 3),
        "gap_p90": r(q(moved + stood, 0.90), 3),
        "moved_share": r(pct(len(moved), len(moved) + len(stood)), 1),
        "hitgap_med": r(med(hitgaps), 3), "hitgap_n": len(hitgaps),
        "army_secs": r(army_secs, 1),
        "shots_per_army_sec": r(n_shots / army_secs, 4) if army_secs else None,
        "fire_frac": r(n_shots * q_cycle / army_secs, 3) if army_secs else None,
    }


def cycle_detail(fight, owner):
    """Every launch-to-launch gap of one side, tagged with HOW MUCH the
    shooter moved during it.

    E9's landed rule is binary -- "moved at any point in the cycle" quantises
    the whole cycle to ceil(reload/Q)*Q. This returns the raw material to test
    that on THIS corpus rather than re-assert it: for each gap, the fraction
    of its 10 Hz samples in which the shooter was displaced, and whether it
    was displaced in the last 0.5 s before the launch (i.e. it genuinely had
    to stop to shoot, which is the mechanism the rule is meant to price).
    """
    out = []
    by_shooter = defaultdict(list)
    for sh in fight.shots:
        if sh["owner"] == owner:
            by_shooter[sh["shooter"]].append(sh)
    for uid, lst in by_shooter.items():
        lst.sort(key=lambda x: x["t"])
        for a, b in zip(lst, lst[1:]):
            gap = b["t"] - a["t"]
            if gap > 12.0:
                continue
            i = bisect.bisect_left(fight._ts, a["t"])
            prev = None
            n = mv = 0
            while i < len(fight.frames_all) and fight.frames_all[i][0] <= b["t"] + 1e-9:
                pt = fight.frames_all[i][1].get(uid)
                if pt is not None:
                    if prev is not None:
                        n += 1
                        if math.hypot(pt[0] - prev[0], pt[1] - prev[1]) > STEP_TILES:
                            mv += 1
                    prev = (pt[0], pt[1])
                i += 1
            out.append({
                "gap": gap,
                "move_frac": (mv / n) if n else 0.0,
                "stopped_late": fight.moved_between(uid, b["t"] - 0.5, b["t"]),
            })
    return out


# ---------------------------------------------------------------------------
# 2. HIT RATE / MISSES / OVERKILL
# ---------------------------------------------------------------------------

def accuracy(fight, owner, max_range):
    ss = [s for s in fight.shots if s["owner"] == owner]
    cat = Counter(s["outcome"] for s in ss)
    n = len(ss)
    # Denominator = every shot that had time to land. UNRESOLVED (no enemy
    # within 0.9 tiles of the aim point at launch, i.e. a shot whose target
    # cannot be named) stays IN: it did not land, so excluding it would
    # flatter the hit rate. Only CENSORED (still airborne when the recording
    # stopped) is removed, because it is a truncation, not an outcome.
    live = n - cat["CENSORED"]

    def split_by(pred):
        a = [s for s in ss if s["outcome"] != "CENSORED" and pred(s)]
        return (len(a), r(pct(sum(1 for s in a if s["outcome"] == "HIT"), len(a)), 1))

    # was the aim target moving at launch? (same 10 Hz bar as everywhere else)
    def tgt_moving(s):
        if s["aim"] is None:
            return False
        return fight.moved_between(s["aim"], s["t"] - 0.25, s["t"] + 0.05)

    mv_n, mv_hit = split_by(tgt_moving)
    st_n, st_hit = split_by(lambda s: not tgt_moving(s))
    near_n, near_hit = split_by(lambda s: s["dist"] <= 0.6 * max_range)
    far_n, far_hit = split_by(lambda s: s["dist"] > 0.6 * max_range)

    kills = sum(1 for e in fight.damage
                if e.get("attacker_owner") == owner and e.get("kill"))
    return {
        "shots": n,
        "hit": cat["HIT"], "hit_pct": r(pct(cat["HIT"], live), 1),
        "waste": cat["WASTE"], "waste_pct": r(pct(cat["WASTE"], live), 1),
        "dodge": cat["DODGE"], "dodge_pct": r(pct(cat["DODGE"], live), 1),
        "scatter": cat["SCATTER"], "scatter_pct": r(pct(cat["SCATTER"], live), 1),
        "whiff": cat["WHIFF"], "whiff_pct": r(pct(cat["WHIFF"], live), 1),
        "censored": cat["CENSORED"], "unresolved": cat["UNRESOLVED"],
        "tgt_moving_n": mv_n, "tgt_moving_hit_pct": mv_hit,
        "tgt_still_n": st_n, "tgt_still_hit_pct": st_hit,
        "near_n": near_n, "near_hit_pct": near_hit,
        "far_n": far_n, "far_hit_pct": far_hit,
        "launch_range_med": r(med([s["dist"] for s in ss]), 2),
        "launch_range_p90": r(q([s["dist"] for s in ss], 0.9), 2),
        "kills": kills,
        "wasted_shots_per_kill": r(cat["WASTE"] / kills, 2) if kills else None,
    }


# ---------------------------------------------------------------------------
# 3. STANDOFF / CLOSURE GEOMETRY
# ---------------------------------------------------------------------------

def centroid(fr, owner):
    pts = [(x, y) for (x, y, o, _h) in fr.values() if o == owner]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def geometry(fight, o1, o2, reach):
    """Inter-centroid separation over time and each side's radial motion."""
    seps, t_axis, c1s, c2s = [], [], [], []
    for t, fr in fight.frames:
        a, b = centroid(fr, o1), centroid(fr, o2)
        if a is None or b is None:
            continue
        t_axis.append(t)
        seps.append(math.hypot(a[0] - b[0], a[1] - b[1]))
        c1s.append(a)
        c2s.append(b)
    if not seps:
        return {}
    # who moves: signed radial speed of each centroid toward the other
    rad = {o1: [], o2: []}
    for i in range(1, len(seps)):
        dt = t_axis[i] - t_axis[i - 1]
        if dt <= 0:
            continue
        for own, cs, other in ((o1, c1s, c2s), (o2, c2s, c1s)):
            ax, ay = cs[i - 1]
            bx, by = cs[i]
            ox, oy = other[i - 1]
            L = math.hypot(ox - ax, oy - ay) or 1.0
            ux, uy = (ox - ax) / L, (oy - ay) / L
            rad[own].append(((bx - ax) * ux + (by - ay) * uy) / dt)
    # standoff while both sides are shooting: separation over the middle half
    lo, hi = int(0.25 * len(seps)), int(0.75 * len(seps))
    return {
        "sep_start": r(seps[0]), "sep_min": r(min(seps)),
        "sep_med": r(med(seps)), "sep_mid_med": r(med(seps[lo:hi] or seps)),
        "sep_end": r(seps[-1]),
        "reach": r(reach),
        "t_first_in_reach": r(next((t_axis[i] for i in range(len(seps))
                                    if seps[i] <= reach), None), 2),
        f"radial_{o1}": r(statistics.mean(rad[o1]), 3) if rad[o1] else None,
        f"radial_{o2}": r(statistics.mean(rad[o2]), 3) if rad[o2] else None,
        "sep_trace": [(r(t, 1), r(s)) for t, s in zip(t_axis, seps)],
    }


def per_side_motion(fight, owner):
    """Fraction of unit-samples in which a unit of this side was moving, and
    the mean speed while moving."""
    n = mv = 0
    speeds = []
    prev = None
    for t, fr in fight.frames:
        if prev is not None:
            dt = t - prev[0]
            for uid, (x, y, o, _h) in fr.items():
                if o != owner:
                    continue
                p = prev[1].get(uid)
                if p is None:
                    continue
                d = math.hypot(x - p[0], y - p[1])
                n += 1
                if d > STEP_TILES:
                    mv += 1
                    if dt > 0:
                        speeds.append(d / dt)
        prev = (t, fr)
    return {"move_share": r(pct(mv, n), 1),
            "speed_while_moving": r(med(speeds), 3)}


# ---------------------------------------------------------------------------
# 4. FOCUS / TARGET SELECTION
# ---------------------------------------------------------------------------

def focus(fight, owner, window):
    """Concentration of this side's fire.

    - `victims_in_window`: distinct enemies this side damaged in each trailing
      `window` (one cycle), sampled at every hit -- how wide the fire is spread.
    - `hhi`: Herfindahl index of damage dealt per victim over the whole fight,
      normalised so 1/n_targets = perfectly even and 1.0 = one victim ate it all.
    - `attackers_per_victim`: distinct shooters that hit the same victim inside
      a trailing window -- how deep the pile-on is.
    """
    hits = sorted([e for e in fight.damage if e.get("attacker_owner") == owner],
                  key=lambda e: e["t"])
    if not hits:
        return {}
    victims_w, attackers_w = [], []
    for i, e in enumerate(hits):
        lo = e["t"] - window
        recent = [h for h in hits[:i + 1] if h["t"] >= lo]
        victims_w.append(len({h["victim"] for h in recent}))
        same = [h for h in recent if h["victim"] == e["victim"]]
        attackers_w.append(len({h["attacker"] for h in same}))
    dmg_by_victim = defaultdict(float)
    for e in hits:
        dmg_by_victim[e["victim"]] += float(e.get("damage") or 0)
    tot = sum(dmg_by_victim.values()) or 1.0
    hhi = sum((v / tot) ** 2 for v in dmg_by_victim.values())
    kills = sorted(e["t"] for e in hits if e.get("kill"))
    return {
        "victims_in_window_med": r(med(victims_w), 2),
        "attackers_per_victim_med": r(med(attackers_w), 2),
        "hhi": r(hhi, 4), "n_victims": len(dmg_by_victim),
        "even_hhi": r(1.0 / len(dmg_by_victim), 4),
        "first_blood_t": r(kills[0], 2) if kills else None,
        "kills": len(kills),
        "kill_times": [r(t, 1) for t in kills],
    }


# ---------------------------------------------------------------------------
# 5. ATTRITION SHAPE
# ---------------------------------------------------------------------------

def hp_curve(fight, owner, hp0, n=21):
    """This side's surviving HP as a fraction of its starting pool, sampled on
    a NORMALISED time axis (0 = start, 1 = end of this fight) so a 21 s sim and
    a 35 s recording are directly overlayable.

    Built from the damage stream, not from the position stream's hp column, so
    tape and engine use the identical construction.
    """
    ev = sorted(fight.damage, key=lambda e: e["t"])
    dur = fight.duration_s or (ev[-1]["t"] if ev else 1.0)
    out = []
    i = 0
    lost = 0.0
    for k in range(n):
        t = dur * k / (n - 1)
        while i < len(ev) and ev[i]["t"] <= t:
            if ev[i].get("victim_owner") == owner:
                lost += float(ev[i].get("damage") or 0)
            i += 1
        out.append(round(max(0.0, 1.0 - lost / hp0), 3))
    return out


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------

def timeline(fight, o1, o2, reach1, reach2, bucket=5.0):
    """Per `bucket` seconds: alive counts, launches, landed hits, in-reach
    share and centroid separation for each side. This is the "where does it
    diverge" instrument -- an aggregate can be right on average and wrong at
    every moment."""
    dur = fight.duration_s
    nb = max(1, int(math.ceil(dur / bucket)))
    rows = [{"t": f"{int(i*bucket)}-{int(min((i+1)*bucket, dur))}",
             "n1": 0, "n2": 0, "s1": 0, "s2": 0, "h1": 0, "h2": 0,
             "ir1": 0.0, "ir2": 0.0, "_w": 0.0, "sep": 0.0} for i in range(nb)]

    prev_t = None
    for t, fr in fight.frames:
        i = min(int(t / bucket), nb - 1)
        dt = (t - prev_t) if prev_t is not None else 0.0
        prev_t = t
        row = rows[i]
        row["_w"] += (dt or 0.1)
        a, b = centroid(fr, o1), centroid(fr, o2)
        if a and b:
            row["sep"] += math.hypot(a[0]-b[0], a[1]-b[1]) * (dt or 0.1)
            row["_sw"] = row.get("_sw", 0.0) + (dt or 0.1)
        u1 = [(x, y) for (x, y, o, _h) in fr.values() if o == o1]
        u2 = [(x, y) for (x, y, o, _h) in fr.values() if o == o2]
        row["n1"] += len(u1) * (dt or 0.1)
        row["n2"] += len(u2) * (dt or 0.1)
        for pts, foes, rch, key in ((u1, u2, reach1, "ir1"), (u2, u1, reach2, "ir2")):
            for (x, y) in pts:
                if any(math.hypot(fx-x, fy-y) <= rch for fx, fy in foes):
                    row[key] += (dt or 0.1)
    for s in fight.shots:
        rows[min(int(s["t"] / bucket), nb - 1)]["s1" if s["owner"] == o1 else "s2"] += 1
    for e in fight.damage:
        rows[min(int(e["t"] / bucket), nb - 1)][
            "h1" if e.get("attacker_owner") == o1 else "h2"] += 1
    out = []
    for row in rows:
        w = row["_w"] or 1.0
        out.append({
            "t": row["t"],
            "alive1": r(row["n1"] / w, 1), "alive2": r(row["n2"] / w, 1),
            "shots1": row["s1"], "shots2": row["s2"],
            "hits1": row["h1"], "hits2": row["h2"],
            "inrch1%": r(pct(row["ir1"], row["n1"]), 0),
            "inrch2%": r(pct(row["ir2"], row["n2"]), 0),
            "sep": r(row["sep"] / (row.get("_sw") or w)),
        })
    return out


def table(rows, cols, title):
    print()
    print(title)
    w = [max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in cols]
    print("  " + "  ".join(str(c).ljust(w[i]) for i, c in enumerate(cols)))
    print("  " + "  ".join("-" * w[i] for i in range(len(cols))))
    for row in rows:
        print("  " + "  ".join(str(row.get(c, "")).ljust(w[i]) for i, c in enumerate(cols)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-runs-dir", default=str(DEFAULT_SIMRUNS))
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

    for meta in fights:
        tag = meta["tag"]
        tape = load_tape(meta)
        engines = [e for e in (load_engine(sim_dir, meta, s)
                               for s in range(1, args.seeds + 1)) if e]
        rec = {"tag": tag, "tape": {}, "engine": {}}
        out["fights"][tag] = rec

        sides = [meta["side1"], meta["side2"]]
        du = {s["owner"]: dicts[f"{s['civ']}|{s['slug']}"] for s in sides}
        hp0 = {s["owner"]: du[s["owner"]]["hp"] * s["count"] for s in sides}
        rec["meta"] = {
            "sides": {s["owner"]: {"slug": s["slug"], "civ": s["civ"],
                                   "count": s["count"], "hp0": hp0[s["owner"]]}
                      for s in sides},
            "tape_duration": r(tape.duration_s),
            "tape_stream_len": r(tape.stream_end_s),
            "tape_post_wipe_tail": r(tape.stream_end_s - tape.duration_s),
            "engine_duration_med": r(med([e.duration_s for e in engines])),
            "tape_hp_left_pct": {s["owner"]: r(pct(tape.sides[s["owner"]]["hp_left"],
                                                   hp0[s["owner"]]), 1) for s in sides},
            "engine_hp_left_pct": {
                s["owner"]: r(med([pct(e.sides[s["owner"]]["hp_left"], hp0[s["owner"]])
                                   for e in engines]), 1) for s in sides},
            "tape_winner": max(sides, key=lambda s: tape.sides[s["owner"]]["hp_left"])["owner"],
            "engine_win_rate": {
                s["owner"]: r(pct(sum(1 for e in engines
                                      if e.sides[s["owner"]]["hp_left"] >
                                      e.sides[sides[1 - sides.index(s)]["owner"]]["hp_left"]),
                                  len(engines)), 0) for s in sides},
            "pair_residual_max": r(max((abs(x) for x in tape.residuals), default=0), 4),
            "unpaired_damage_events": tape.unpaired,
            "aim_inference": f"{tape.inference[0]}/{tape.inference[1]}",
        }

        for s in sides:
            o = s["owner"]
            u = du[o]
            reload_s = 1.0 / u["attack_speed"]
            other = sides[1 - sides.index(s)]["owner"]
            reach = engine_reach(u, du[other])
            key = f"{o}:{SHORT.get(s['slug'], s['slug'])}"
            rec["tape"].setdefault("cadence", {})[key] = cadence(tape, o, reload_s, reach)
            rec["tape"].setdefault("accuracy", {})[key] = accuracy(tape, o, reach)
            rec["tape"].setdefault("focus", {})[key] = focus(tape, o, reload_s)
            rec["tape"].setdefault("motion", {})[key] = per_side_motion(tape, o)
            rec["tape"].setdefault("cycles", {})[key] = cycle_detail(tape, o)
            rec["tape"].setdefault("hp_curve", {})[key] = hp_curve(tape, o, hp0[o])

            # engine: pool events over seeds by averaging each seed's table
            ec = [cadence(e, o, reload_s, reach) for e in engines]
            ea = [accuracy(e, o, reach) for e in engines]
            ef = [focus(e, o, reload_s) for e in engines]
            em = [per_side_motion(e, o) for e in engines]
            rec["engine"].setdefault("cycles", {})[key] = [
                c for e in engines for c in cycle_detail(e, o)]
            def avg(rows, k, nd=2):
                v = [x[k] for x in rows if x.get(k) is not None]
                return r(statistics.mean(v), nd) if v else None
            rec["engine"].setdefault("cadence", {})[key] = {
                k: avg(ec, k, 3) for k in ec[0]} if ec else {}
            rec["engine"].setdefault("accuracy", {})[key] = {
                k: avg(ea, k, 1) for k in ea[0]} if ea else {}
            rec["engine"].setdefault("focus", {})[key] = {
                k: avg(ef, k, 3) for k in ef[0] if k != "kill_times"} if ef else {}
            rec["engine"].setdefault("motion", {})[key] = {
                k: avg(em, k, 3) for k in em[0]} if em else {}
            if engines:
                mid = sorted(engines, key=lambda e: e.duration_s)[len(engines) // 2]
                rec["engine"].setdefault("hp_curve", {})[key] = hp_curve(mid, o, hp0[o])

        o1, o2 = sides[0]["owner"], sides[1]["owner"]
        reach12 = engine_reach(du[o1], du[o2])
        rch1, rch2 = engine_reach(du[o1], du[o2]), engine_reach(du[o2], du[o1])
        rec["tape"]["timeline"] = timeline(tape, o1, o2, rch1, rch2)
        rec["tape"]["geometry"] = geometry(tape, o1, o2, reach12)
        if engines:
            mid = sorted(engines, key=lambda e: e.duration_s)[len(engines) // 2]
            rec["engine"]["timeline"] = timeline(mid, o1, o2, rch1, rch2)
            rec["engine"]["geometry"] = geometry(mid, o1, o2, reach12)
            rec["engine"]["geometry"]["seed"] = mid.tag and sorted(
                engines, key=lambda e: e.duration_s)[len(engines) // 2].duration_s

    # -------- printing ----------------------------------------------------
    def sides_of(tag):
        return list(out["fights"][tag]["tape"]["cadence"].keys())

    if sec in ("all", "cadence"):
        rows = []
        for tag in want:
            f = out["fights"][tag]
            for k in sides_of(tag):
                t, e = f["tape"]["cadence"][k], f["engine"]["cadence"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "reload": t["reload"], "qcyc": t["q_cycle"],
                    "T shots": t["shots"], "E shots": e.get("shots"),
                    "T mv%": t["moved_share"], "E mv%": e.get("moved_share"),
                    "T mvgap": t["moved_med"], "E mvgap": e.get("moved_med"),
                    "T stgap": t["stood_med"], "E stgap": e.get("stood_med"),
                    "T armys": t["army_secs"], "E armys": e.get("army_secs"),
                    "T s/shot": t["sec_per_shot"], "E s/shot": e.get("sec_per_shot"),
                    "T duty": t["duty"], "E duty": e.get("duty"),
                    "T inrch%": t["in_reach_share"], "E inrch%": e.get("in_reach_share"),
                    "T dutyW": t["duty_in_window"], "E dutyW": e.get("duty_in_window"),
                    "T win%": t["window_share"], "E win%": e.get("window_share"),
                    "T pre%": t["pre_share"], "E pre%": e.get("pre_share"),
                    "T post%": t["post_share"], "E post%": e.get("post_share"),
                })
        table(rows, list(rows[0].keys()),
              "TABLE 1 -- FIRE CADENCE (T=tape, E=engine mean of seeds). "
              "mvgap/stgap = launch-to-launch median for cycles the shooter "
              "moved / stood; fire% = shots x quantised cycle / army-seconds "
              "(1.0 = every unit fired on cooldown its whole life).")

    if sec in ("all", "accuracy"):
        rows = []
        for tag in want:
            f = out["fights"][tag]
            for k in sides_of(tag):
                t, e = f["tape"]["accuracy"][k], f["engine"]["accuracy"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T hit%": t["hit_pct"], "E hit%": e.get("hit_pct"),
                    "T wst%": t["waste_pct"], "E wst%": e.get("waste_pct"),
                    "T ddg%": t["dodge_pct"], "E ddg%": e.get("dodge_pct"),
                    "T sct%": t["scatter_pct"], "E sct%": e.get("scatter_pct"),
                    "T whf%": t["whiff_pct"], "E whf%": e.get("whiff_pct"),
                    "T mvTgt%": t["tgt_moving_hit_pct"], "E mvTgt%": e.get("tgt_moving_hit_pct"),
                    "T stTgt%": t["tgt_still_hit_pct"], "E stTgt%": e.get("tgt_still_hit_pct"),
                    "T rng": t["launch_range_med"], "E rng": e.get("launch_range_med"),
                    "T wst/kill": t["wasted_shots_per_kill"],
                    "E wst/kill": e.get("wasted_shots_per_kill"),
                })
        table(rows, list(rows[0].keys()),
              "TABLE 2 -- SHOT OUTCOMES, % of shots that had time to land. "
              "wst = the target died in flight; whf = the shot reached the "
              "living target and did nothing (accuracy failure); ddg / sct = "
              "it landed wide of a target that had / had not moved. "
              "mvTgt%/stTgt% = hit rate when the aim target was moving / "
              "still at launch. rng = median launch range in tiles.")

    if sec in ("all", "geometry"):
        rows = []
        for tag in want:
            f = out["fights"][tag]
            t, e = f["tape"]["geometry"], f["engine"]["geometry"]
            ks = sides_of(tag)
            o1 = int(ks[0].split(":")[0]); o2 = int(ks[1].split(":")[0])
            rows.append({
                "fight": tag.replace("__vs__", " v "),
                "reach": t["reach"],
                "T sep0": t["sep_start"], "E sep0": e.get("sep_start"),
                "T sepmin": t["sep_min"], "E sepmin": e.get("sep_min"),
                "T sepmid": t["sep_mid_med"], "E sepmid": e.get("sep_mid_med"),
                "T sepend": t["sep_end"], "E sepend": e.get("sep_end"),
                f"T rad{o1}": t.get(f"radial_{o1}"), f"E rad{o1}": e.get(f"radial_{o1}"),
                f"T rad{o2}": t.get(f"radial_{o2}"), f"E rad{o2}": e.get(f"radial_{o2}"),
                "T mv%1": f["tape"]["motion"][ks[0]]["move_share"],
                "E mv%1": f["engine"]["motion"][ks[0]].get("move_share"),
                "T mv%2": f["tape"]["motion"][ks[1]]["move_share"],
                "E mv%2": f["engine"]["motion"][ks[1]].get("move_share"),
            })
        table(rows, list(rows[0].keys()),
              "TABLE 3 -- STANDOFF GEOMETRY. sep = inter-centroid separation "
              "(tiles); rad<owner> = that side's mean radial speed toward the "
              "enemy centroid (+ closing, - retreating, tiles/s); mv% = share "
              "of unit-samples in which a unit was moving.")

    if sec in ("all", "focus"):
        rows = []
        for tag in want:
            f = out["fights"][tag]
            for k in sides_of(tag):
                t, e = f["tape"]["focus"][k], f["engine"]["focus"][k]
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T vict/cyc": t.get("victims_in_window_med"),
                    "E vict/cyc": e.get("victims_in_window_med"),
                    "T att/vict": t.get("attackers_per_victim_med"),
                    "E att/vict": e.get("attackers_per_victim_med"),
                    "T hhi": t.get("hhi"), "E hhi": e.get("hhi"),
                    "T even": t.get("even_hhi"), "E even": e.get("even_hhi"),
                    "T 1stkill": t.get("first_blood_t"), "E 1stkill": e.get("first_blood_t"),
                    "T kills": t.get("kills"), "E kills": e.get("kills"),
                })
        table(rows, list(rows[0].keys()),
              "TABLE 4 -- FOCUS / TARGET SELECTION. vict/cyc = distinct enemies "
              "this side damaged in a trailing reload window; att/vict = "
              "distinct shooters on the same victim in that window; hhi = "
              "Herfindahl of damage per victim (even = 1/n_victims floor).")

    if sec in ("all", "attrition"):
        print()
        print("TABLE 5 -- ATTRITION SHAPE: surviving HP fraction on a NORMALISED "
              "time axis (0 = start, 1 = that fight's own end), 11 of 21 points.")
        for tag in want:
            f = out["fights"][tag]
            print(f"\n  {tag}")
            for k in sides_of(tag):
                tc = f["tape"]["hp_curve"][k][::2]
                ec = f["engine"]["hp_curve"].get(k, [])[::2]
                print(f"    {k:>18} tape   " + " ".join(f"{v:5.2f}" for v in tc))
                print(f"    {'':>18} engine " + " ".join(f"{v:5.2f}" for v in ec))

    if sec in ("all", "timeline"):
        cols = ["t", "alive1", "alive2", "shots1", "shots2", "hits1", "hits2",
                "inrch1%", "inrch2%", "sep"]
        for tag in want:
            f = out["fights"][tag]
            ks = sides_of(tag)
            for src in ("tape", "engine"):
                table(f[src]["timeline"], cols,
                      f"TIMELINE {src.upper()} -- {tag}  (1 = {ks[0]}, 2 = {ks[1]}); "
                      "5 s buckets: mean alive, launches, landed hits, share of "
                      "living units with an enemy inside their own reach, and "
                      "inter-centroid separation.")

    if sec in ("all", "e9"):
        # THE E9 LAW, RE-TESTED ON THIS CORPUS. The rule was derived over all
        # 140 recordings, where the ranged units are mostly running from
        # melee. These six are ranged-vs-ranged: the units barely move, and
        # the question is whether a cycle with a LITTLE movement in it still
        # pays the full quantum.
        buckets = [(0.0, 0.001, "still"), (0.001, 0.25, "mv<25%"),
                   (0.25, 0.60, "mv25-60%"), (0.60, 1.01, "mv>60%")]
        agg = defaultdict(lambda: defaultdict(list))
        for tag in want:
            f = out["fights"][tag]
            for k in sides_of(tag):
                slug = k.split(":")[1]
                for src in ("tape", "engine"):
                    for c in f[src]["cycles"][k]:
                        for lo, hi, name in buckets:
                            if lo <= c["move_frac"] < hi:
                                agg[(slug, src)][name].append(c["gap"])
                                break
                        agg[(slug, src)]["stopped_late" if c["stopped_late"]
                                         else "no_late_stop"].append(c["gap"])
        rows = []
        for slug in ["arb", "HCA", "skirm", "HC"]:
            u = next((d for kk, d in dicts.items() if d["slug"] == SLUG_BACK[slug]), None)
            rel = 1.0 / u["attack_speed"]
            row = {"unit": slug, "reload": r(rel, 3),
                   "qcyc": r(math.ceil(rel / FIRE_CYCLE_QUANTUM - 1e-9)
                             * FIRE_CYCLE_QUANTUM, 3)}
            for src, pre in (("tape", "T"), ("engine", "E")):
                d = agg[(slug, src)]
                for _lo, _hi, name in buckets:
                    v = d.get(name, [])
                    row[f"{pre} {name}"] = f"{r(med(v), 2)} n{len(v)}" if v else "-"
                v = d.get("stopped_late", [])
                row[f"{pre} late-stop"] = f"{r(med(v), 2)} n{len(v)}" if v else "-"
            rows.append(row)
        table(rows, list(rows[0].keys()),
              "TABLE 1b -- E9 RE-TEST on the six ranged fights: median "
              "launch-to-launch gap (and n) by how much of the cycle the "
              "SHOOTER spent displaced, plus the subset where it was still "
              "moving in the last 0.5 s before the launch. E9 predicts every "
              "non-'still' bucket sits at qcyc.")

    if sec in ("all", "ledger"):
        # THROUGHPUT LEDGER. A side's landed hits per second factorises
        # exactly:
        #     hits/s = A x F x H
        #       A = mean living units      (army-seconds / duration)
        #       F = launches per living-unit-second
        #       H = hit rate
        # so the engine/tape ratio of hits/s is the PRODUCT of three ratios
        # and the deficit can be ATTRIBUTED rather than described. F splits
        # again into 1/cycle x duty, and duty into in-reach share x in-window
        # duty (Table 1). The last column is the number that actually decides
        # the fight: how much the engine tilts the two sides' hits/s relative
        # to each other.
        rows = []
        for tag in want:
            f = out["fights"][tag]
            m = f["meta"]
            ks = sides_of(tag)
            ratios = {}
            for k in ks:
                o = int(k.split(":")[0])
                tc, ec = f["tape"]["cadence"][k], f["engine"]["cadence"][k]
                ta, ea = f["tape"]["accuracy"][k], f["engine"]["accuracy"][k]
                tdur, edur = m["tape_duration"], m["engine_duration_med"] or 1
                tA, eA = tc["army_secs"] / tdur, (ec.get("army_secs") or 0) / edur
                tF = tc["shots"] / tc["army_secs"] if tc["army_secs"] else 0
                eF = ((ec.get("shots") or 0) / ec["army_secs"]) if ec.get("army_secs") else 0
                tH = (ta["hit_pct"] or 0) / 100.0
                eH = (ea.get("hit_pct") or 0) / 100.0
                ratios[k] = (eA * eF * eH) / (tA * tF * tH) if (tA * tF * tH) else None
                rows.append({
                    "fight": tag.replace("__vs__", " v "), "side": k,
                    "T dur": m["tape_duration"], "E dur": m["engine_duration_med"],
                    "dur x": r(edur / tdur, 2),
                    "T A": r(tA, 2), "E A": r(eA, 2), "A x": r(eA / tA, 2) if tA else None,
                    "T F": r(tF, 3), "E F": r(eF, 3), "F x": r(eF / tF, 2) if tF else None,
                    "T H": r(tH, 3), "E H": r(eH, 3), "H x": r(eH / tH, 2) if tH else None,
                    "T hit/s": r(tA * tF * tH, 2), "E hit/s": r(eA * eF * eH, 2),
                    "hit/s x": r(ratios[k], 2),
                    "T hp%": m["tape_hp_left_pct"][o], "E hp%": m["engine_hp_left_pct"][o],
                })
            a, b = ratios[ks[0]], ratios[ks[1]]
            for row in rows[-2:]:
                row["tilt"] = r(a / b, 2) if (a and b) else None
        table(rows, list(rows[0].keys()),
              "TABLE 6 -- THROUGHPUT LEDGER. hits/s = A (mean living units) x "
              "F (launches per living-unit-second) x H (hit rate); 'x' columns "
              "are engine/tape. `tilt` = side1's hits/s ratio divided by "
              "side2's -- >1 means the engine hands side1 relatively more "
              "firepower than the tape gave it, which is what moves the HP "
              "score.")

    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
