"""D1 (siege round): what the 25 scorpion/onager recordings do that the engine does not.

Scope: every manifest fight in which EITHER side is `heavy_scorpion` or
`siege_onager` (25 of them; no mangonel-line recordings exist). Both units are
AREA weapons, and both are area weapons of a KIND the engine models with a
single scalar:

    heavy_scorpion   dat blast_attack_level 3, blast_width 0  -> PASS-THROUGH
                     engine: `passThroughPercent` = one extra victim, floor()
    siege_onager     dat blast_attack_level 1, blast_width 1.5 -> BLAST
                     engine: `splashRadius`, linear falloff (E4)

so the measurement that matters is not the score but the ANATOMY OF ONE SHOT:
how many bodies it touches, which bodies, and how much each one takes.

WHY THE SCORPION NEEDS ITS OWN RECONSTRUCTION
---------------------------------------------
ranged_fire_forensics reconstructs a shot as launch -> impact, because an
arbalester's arrow resolves once. A scorpion bolt does not: on tape its
missile track flies its FULL length (past the target, out to the edge of the
box) while damage events fire at DIFFERENT TIMES along the way -- e.g.

    missile -2, launched t=1.026 at (4.5, 6.808), last moves t=2.864 at (4.5, 15.89)
      damage t=1.488 victim 1607  9.0     <- primary
      damage t=1.902 victim 1605  4.5     <- passed through
      damage t=2.016 victim 1622  4.5     <- passed through

Pairing a shot to "the damage event nearest its impact" therefore throws away
two thirds of what a bolt does. This module pairs instead by FLIGHT WINDOW +
GEOMETRY: a damage event belongs to the missile whose straight-line track is
closest to the victim's interpolated position at the instant of the event,
among that shooter's missiles that were airborne then. The pairing is checked,
not assumed -- `--section pair` reports the residual (tiles off the bolt line)
for every matched event and the count that no missile can explain.

Engine runs are reconstructed by the same functions from
tools/simjs/ranged_shot_dump.mjs output (`--out-dir D:/AI/aoe2_golden/shots_d1_siege`),
where a shot is a launch point, a landing point and an impact time, so its
"track" is that segment. A tape number and an engine number in every table
below are the same statistic computed by the same code.

    D:/miniconda3/python.exe tools/simjs/d1_siege_forensics.py \
        --sim-runs-dir D:/AI/aoe2_golden/shots_d1_siege --section all
    ... --section board|pair|passthrough|blast|friendly|minrange|opponent|duration
    ... --tags heavy_scorpion__vs__hussar
    ... --seeds 20        engine seeds to pool (default 20)
    ... --json out.json
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALIB = ROOT / "data" / "calibration"
TAPES = Path("D:/AI/aoe2_golden/tapes")
DEFAULT_SIMRUNS = Path("D:/AI/aoe2_golden/shots_d1_siege")

SIEGE_SLUGS = {"heavy_scorpion", "siege_onager"}

# ---------------------------------------------------------------------------
# tolerances -- every one of them is reported, not trusted
# ---------------------------------------------------------------------------

# How far off the bolt's straight-line track a victim may be and still be
# attributed to it. Tape positions are sampled at 10 Hz and interpolated, and a
# hussar covers ~0.15 tiles between samples, so a genuine pass-through victim
# sits a fraction of a tile off the line. 1.0 tile is deliberately generous:
# the point of the tolerance is to *measure* the residual distribution
# (--section pair), and a tight bar would hide the misses instead of showing
# them.
TRACK_TOL_TILES = 1.0

# Grace either side of a missile's own [launch, last-move] window, to cover the
# 10 Hz position sampling and the frame the damage row is written on.
WINDOW_PAD_S = 0.12

# A track row counts as "moving" when it differs from the previous row by more
# than this; the last row that moved is the end of the flight (the sprite is
# torn down over 1-3 stationary rows). Same rule ranged_fire_forensics uses.
MOVE_EPS = 1e-6

# Engine damage from one projectile all lands on the same tick, so an engine
# shot's events are gathered by |t - impact_t| instead of by geometry.
ENGINE_PAIR_TOL = 0.05

TILE = 30.0


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_manifest():
    return json.loads((CALIB / "manifest.json").read_text(encoding="utf-8"))["fights"]


def load_dicts():
    return json.loads((CALIB / "combat_dicts.json").read_text(encoding="utf-8"))


def siege_fights(fights, tags=None):
    out = []
    for f in fights:
        if f.get("quarantined"):
            continue
        slugs = {f["side1"]["slug"], f["side2"]["slug"]}
        if not (slugs & SIEGE_SLUGS):
            continue
        if tags and f["tag"] not in tags:
            continue
        out.append(f)
    return out


def _tape_rows(tag, stream):
    p = TAPES / tag / f"{tag}.{stream}.jsonl.gz"
    with gzip.open(p, "rt") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


class Fight:
    """{frames, damage, shots, sides} -- everything below reads only this.

    `shots` carry a TRACK (list of (t, x, y)) rather than only launch/impact,
    because a pass-through weapon's victims are spread along it.
    """

    def __init__(self, source, tag, frames, damage, shots, sides,
                 stream_end, end_t):
        self.source = source
        self.tag = tag
        self.stream_end_s = stream_end
        self.end_t = end_t
        self.duration_s = end_t
        self.frames_all = frames
        self.damage_all = damage
        self.shots_all = shots
        self.frames = [f for f in frames if f[0] <= end_t + 1e-9]
        self.damage = [e for e in damage if e["t"] <= end_t + 1e-9]
        self.shots = [s for s in shots if s["t"] <= end_t + 1e-9]
        self.sides = sides
        self._ts = [f[0] for f in frames]

    def pos(self, uid, t):
        ts, fr = self._ts, self.frames_all
        if not fr:
            return None
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

    def owner_of(self, uid, t=None):
        for _t, fr in self.frames_all:
            if uid in fr:
                return fr[uid][2]
        return None


def _shot_from_track(rows):
    """One missile id -> {t, shooter, owner, track, sx..iy, end_t}."""
    rows.sort(key=lambda r: r["t"])
    last_move = 0
    for i in range(1, len(rows)):
        if (abs(rows[i]["x"] - rows[i - 1]["x"]) > MOVE_EPS
                or abs(rows[i]["y"] - rows[i - 1]["y"]) > MOVE_EPS):
            last_move = i
    imp = rows[last_move]
    return {
        "t": rows[0]["t"], "owner": rows[0]["owner"],
        "shooter": rows[0]["fired_from"],
        "sx": rows[0]["x"], "sy": rows[0]["y"],
        "ix": imp["x"], "iy": imp["y"], "impact_t": imp["t"],
        "end_t": imp["t"],
        "flight_tiles": math.hypot(imp["x"] - rows[0]["x"],
                                   imp["y"] - rows[0]["y"]),
        "censored": (len(rows) - 1 - last_move) == 0,
        "track": [(r["t"], r["x"], r["y"]) for r in rows[:last_move + 1]],
        "master": rows[0].get("master"),
        "events": [],
        "target": None,
    }


def load_tape(fm) -> Fight:
    tag = fm["tag"]
    frames = {}
    for r in _tape_rows(tag, "units"):
        frames.setdefault(round(r["t"], 3), {})[r["id"]] = (
            r["x"], r["y"], r["owner"], r.get("hp"))
    frames = sorted(frames.items())
    damage = list(_tape_rows(tag, "damage"))

    tracks = defaultdict(list)
    for r in _tape_rows(tag, "missiles"):
        tracks[r["id"]].append(r)
    shots = sorted((_shot_from_track(v) for v in tracks.values()),
                   key=lambda s: s["t"])

    summary = json.loads((TAPES / tag / f"{tag}.summary.json").read_text())
    sides = {}
    for sd in summary["sides"].values():
        sides[sd["owner"]] = {
            "slug": None, "count": sd["start_count"],
            "survivors": sd["survivors"], "hp_left": sd["hp_remaining"],
        }
    for side in (fm["side1"], fm["side2"]):
        sides[side["owner"]]["slug"] = side["slug"]
        sides[side["owner"]]["civ"] = side["civ"]
        sides[side["owner"]]["unit_name"] = side["unit_name"]

    # END OF FIGHT: the recorder keeps streaming ~17-20 s past the wipe (see
    # ranged_fire_forensics). Cut at the first frame where a side has no living
    # unit, exactly where the engine's `while (sim.winner === null)` stops.
    wipe_t = None
    for t, fr in frames:
        counts = Counter(o for (_x, _y, o, _h) in fr.values())
        if any(counts.get(o, 0) == 0 for o in sides):
            wipe_t = t
            break
    stream_end = fm.get("duration_s") or (frames[-1][0] if frames else 0.0)
    f = Fight("tape", tag, frames, damage, shots, sides, stream_end,
              wipe_t if wipe_t is not None else stream_end)
    f.wipe_t = wipe_t
    attribute_tape(f)
    return f


def load_engine(sim_dir: Path, fm, seed: int) -> Fight | None:
    p = sim_dir / fm["run_id"] / f"seed-{seed}.shots.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    frames = [(fr["t"], {u[0]: (u[1], u[2], u[3], u[4]) for u in fr["u"]})
              for fr in raw["frames"]]
    shots = []
    for m in raw["missiles"]:
        if "ax" not in m:
            continue
        # D2-S1: a pass-through bolt's track runs launch -> END OF FLIGHT, not
        # launch -> aim point, and its damage events are spread along it instead
        # of piled on the impact tick. When the dump carries `ex/ey` (i.e. the
        # engine attached a corridor to this projectile) the shot is modelled
        # exactly the way a TAPE bolt already is, which is what keeps the two
        # columns of every table below commensurable. Without those keys every
        # value this file prints is byte-identical to what it printed before D2.
        has_end = "ex" in m
        ix, iy = (m["ex"], m["ey"]) if has_end else (m["ax"], m["ay"])
        end_t = m["end_t"] if has_end else m["impact_t"]
        flight = (m["end_flight_tiles"] if has_end
                  else m.get("flight_tiles", m["dist_tiles"]))
        shots.append({
            "t": m["t"], "owner": m["owner"], "shooter": m["fired_from"],
            "sx": m["sx"], "sy": m["sy"], "ix": ix, "iy": iy,
            "impact_t": m["impact_t"], "end_t": end_t,
            "flight_tiles": flight,
            "censored": False,
            "track": [(m["t"], m["sx"], m["sy"]), (end_t, ix, iy)],
            "master": None, "events": [], "target": m.get("target"),
            "planned": m.get("planned"), "launch_dist": m["dist_tiles"],
            "swept": has_end,
        })
    shots.sort(key=lambda s: s["t"])
    sides = {}
    for owner, sd in raw["sides"].items():
        sides[int(owner)] = {
            "slug": sd["slug"], "civ": sd["civ"], "unit_name": sd["unit_name"],
            "count": sd["start_count"], "survivors": sd["survivors"],
            "hp_left": sd["hp_remaining"],
        }
    f = Fight("engine", fm["tag"], frames, raw["damage"], shots, sides,
              raw["duration_s"], raw["duration_s"])
    f.seed = seed
    f.winner_owner = raw.get("winner_owner")
    f.wipe_t = raw["duration_s"]
    attribute_engine(f)
    return f


# ---------------------------------------------------------------------------
# attribution: which shot caused which damage event
# ---------------------------------------------------------------------------

def _seg_dist(px, py, ax, ay, bx, by):
    """Distance from point to segment, and the parametric position along it."""
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 <= 1e-12:
        return math.hypot(px - ax, py - ay), 0.0
    u = ((px - ax) * vx + (py - ay) * vy) / L2
    uc = max(0.0, min(1.0, u))
    return math.hypot(px - (ax + uc * vx), py - (ay + uc * vy)), u


def _track_pos(shot, t):
    """Interpolated bolt position at `t` (clamped to the flight)."""
    tr = shot["track"]
    if not tr:
        return shot["sx"], shot["sy"]
    if t <= tr[0][0]:
        return tr[0][1], tr[0][2]
    if t >= tr[-1][0]:
        return tr[-1][1], tr[-1][2]
    lo, hi = 0, len(tr) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if tr[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, x0, y0 = tr[lo]
    t1, x1, y1 = tr[hi]
    if t1 <= t0:
        return x0, y0
    w = (t - t0) / (t1 - t0)
    return x0 + (x1 - x0) * w, y0 + (y1 - y0) * w


def attribute_tape(f: Fight):
    """Attach each damage event to the missile that plausibly caused it.

    A candidate missile is one from the SAME attacker that was airborne at the
    event time. Among candidates the winner is the one whose bolt position at
    that instant is nearest the victim -- which is the physical statement
    "this bolt was at that unit when that unit took damage". `resid` (tiles) is
    kept on every event so the pairing can be audited rather than believed.
    """
    by_shooter = defaultdict(list)
    for s in f.shots_all:
        by_shooter[s["shooter"]].append(s)
    f.unattributed = []
    for e in f.damage_all:
        cands = [
            s for s in by_shooter.get(e["attacker"], [])
            if s["t"] - WINDOW_PAD_S <= e["t"] <= s["end_t"] + WINDOW_PAD_S
        ]
        if not cands:
            e["shot"] = None
            f.unattributed.append(e)
            continue
        vp = f.pos(e["victim"], e["t"])
        best, bestd = None, None
        for s in cands:
            bx, by = _track_pos(s, e["t"])
            d = (math.hypot(vp[0] - bx, vp[1] - by) if vp else 0.0)
            if bestd is None or d < bestd:
                best, bestd = s, d
        e["shot"] = best
        e["resid"] = bestd
        best["events"].append(e)
    # order-of-arrival on each shot
    for s in f.shots_all:
        s["events"].sort(key=lambda e: (e["t"], e["victim"]))


def attribute_engine(f: Fight):
    """Engine: every consequence of a projectile lands on the impact tick."""
    by_shooter = defaultdict(list)
    for s in f.shots_all:
        by_shooter[s["shooter"]].append(s)
    f.unattributed = []
    # A shooter whose bolts SWEEP (D2-S1) spreads one shot's consequences over
    # the whole flight, exactly as the tape's do, so the impact-tick pairing
    # below is structurally unable to see them -- it would read the engine as
    # having FEWER victims per bolt the moment the corridor is switched on.
    # Those shooters get the tape's own geometric attribution; every other
    # shooter keeps the original branch verbatim, so a pre-D2 dump reproduces
    # the pre-D2 numbers to the digit.
    swept_shooters = {s["shooter"] for s in f.shots_all if s.get("swept")}
    for e in f.damage_all:
        if e["attacker"] in swept_shooters:
            cands = [
                s for s in by_shooter.get(e["attacker"], [])
                if s["t"] - WINDOW_PAD_S <= e["t"] <= s["end_t"] + WINDOW_PAD_S
            ]
            if not cands:
                e["shot"] = None
                f.unattributed.append(e)
                continue
            vp = f.pos(e["victim"], e["t"])
            best, bestd = None, None
            for s in cands:
                bx, by = _track_pos(s, e["t"])
                d = (math.hypot(vp[0] - bx, vp[1] - by) if vp else 0.0)
                if bestd is None or d < bestd:
                    best, bestd = s, d
            e["shot"] = best
            e["resid"] = bestd
            best["events"].append(e)
            continue
        cands = [s for s in by_shooter.get(e["attacker"], [])
                 if abs(e["t"] - s["impact_t"]) <= ENGINE_PAIR_TOL]
        if not cands:
            e["shot"] = None
            f.unattributed.append(e)
            continue
        best = min(cands, key=lambda s: abs(e["t"] - s["impact_t"]))
        e["shot"] = best
        e["resid"] = 0.0
        best["events"].append(e)
    for s in f.shots_all:
        s["events"].sort(key=lambda e: (e["t"], str(e["victim"])))


# ---------------------------------------------------------------------------
# stats helpers
# ---------------------------------------------------------------------------

def med(v):
    return statistics.median(v) if v else None


def mean(v):
    return statistics.fmean(v) if v else None


def q(v, p):
    if not v:
        return None
    s = sorted(v)
    if len(s) == 1:
        return s[0]
    i = p * (len(s) - 1)
    lo = int(i)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def r(x, n=2):
    return None if x is None else round(x, n)


def table(rows, cols, title):
    print(f"\n{title}")
    if not rows:
        print("  (no rows)")
        return
    w = [max(len(str(c)), *(len(str(row.get(c, ""))) for row in rows)) for c in cols]
    print("  " + "  ".join(str(c).ljust(w[i]) for i, c in enumerate(cols)))
    print("  " + "  ".join("-" * w[i] for i in range(len(cols))))
    for row in rows:
        print("  " + "  ".join(str(row.get(c, "")).ljust(w[i])
                               for i, c in enumerate(cols)))


def siege_side(fm):
    """(siege owner, siege slug, opponent owner, opponent slug) or None."""
    s1, s2 = fm["side1"], fm["side2"]
    a = s1["slug"] in SIEGE_SLUGS
    b = s2["slug"] in SIEGE_SLUGS
    if a and b:
        return None          # scorpion vs onager -- both sides are siege
    sg, op = (s1, s2) if a else (s2, s1)
    return sg["owner"], sg["slug"], op["owner"], op["slug"]


# ---------------------------------------------------------------------------
# 1. THE BOARD
# ---------------------------------------------------------------------------

def hp_pct(side):
    # hp0 is unavailable from the tape summary alone, so hp% uses the dict.
    return side


def board(fights, sim_dir, seeds, dicts):
    rows = []
    for fm in fights:
        tape = load_tape(fm)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        if not engs:
            continue
        owners = sorted(tape.sides)
        hp0 = {}
        for side in (fm["side1"], fm["side2"]):
            d = dicts.get(f"{side['civ']}|{side['slug']}")
            hp0[side["owner"]] = (d["hp"] if d else 0) * side["count"]

        # tape winner = the side with a survivor at the wipe; if neither side
        # was wiped, the higher HP% (the same rule the engine's cap uses).
        tape_hp = {o: tape.sides[o]["hp_left"] / hp0[o] if hp0[o] else 0
                   for o in owners}
        tape_win = None
        for o in owners:
            if tape.sides[o]["survivors"] == 0:
                tape_win = [x for x in owners if x != o][0]
        if tape_win is None:
            tape_win = max(owners, key=lambda o: tape_hp[o])

        eng_wins = Counter(e.winner_owner for e in engs)
        eng_hp = {o: mean([e.sides[o]["hp_left"] / hp0[o] if hp0[o] else 0
                           for e in engs]) for o in owners}
        sg = siege_side(fm)
        row = {
            "tag": fm["tag"],
            "tape_win": tape_win,
            "eng_win%": r(100 * eng_wins.get(tape_win, 0) / len(engs), 1),
            "agree": "OK" if eng_wins.get(tape_win, 0) > len(engs) / 2 else "FLIP",
            "tape_dur": r(tape.end_t, 1),
            "stream_dur": r(tape.stream_end_s, 1),
            "eng_dur": r(mean([e.duration_s for e in engs]), 1),
        }
        for i, o in enumerate(owners):
            lab = tape.sides[o]["slug"][:12]
            row[f"side{i+1}"] = lab
            row[f"tapeHP{i+1}"] = r(100 * tape_hp[o], 1)
            row[f"engHP{i+1}"] = r(100 * eng_hp[o], 1)
            row[f"errHP{i+1}"] = r(100 * (eng_hp[o] - tape_hp[o]), 1)
        row["absErr"] = r(mean([abs(row[f"errHP{i+1}"]) for i in range(len(owners))]), 1)
        if sg:
            sg_owner = sg[0]
            i = owners.index(sg_owner) + 1
            row["siege_err"] = row[f"errHP{i}"]
            row["opp_err"] = row[f"errHP{2 if i == 1 else 1}"]
            row["siege"] = sg[1][:13]
        else:
            row["siege_err"] = row["opp_err"] = ""
            row["siege"] = "both"
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# 1b. ONE ONAGER SHOT = 10 PROJECTILES
# ---------------------------------------------------------------------------
# The recordings show the siege onager launching TEN missiles per shot, all on
# the same frame from the same unit: one master 656 ("Projectile Mangonel
# (Primary)", the unit's own projectile_unit_id) and NINE master 369
# ("Projectile Mangonel (Secondary)"), each with its own slightly different
# landing point scattered around the primary's. Naively counting missiles
# therefore counts every onager shot ten times. `shot_groups` folds them back
# into one shot, keyed by (shooter, launch frame).
PRIMARY_MASTERS = {656, 658}          # mangonel-line primary stone (+fire)
SECONDARY_MASTERS = {369, 468}        # its debris

def shot_groups(f: Fight, owner):
    """[(primary_shot, [secondary_shots]), ...] for one side.

    On an engine fight there are no secondaries, so every shot is its own
    group and every table below reads the same on both sources.
    """
    by = defaultdict(list)
    for s in f.shots:
        if s["owner"] != owner:
            continue
        by[(s["shooter"], round(s["t"], 2))].append(s)
    out = []
    for _k, g in sorted(by.items(), key=lambda kv: kv[1][0]["t"]):
        prim = [s for s in g if s["master"] in PRIMARY_MASTERS]
        secs = [s for s in g if s["master"] in SECONDARY_MASTERS]
        if not prim:
            # scorpion / engine: no primary/secondary split at all
            for s in g:
                out.append((s, []))
        else:
            out.append((prim[0], secs))
    return out


# ---------------------------------------------------------------------------
# 2. PASS-THROUGH ANATOMY (scorpion)
# ---------------------------------------------------------------------------
# MEASURED FACT the tables below are built on: a scorpion bolt's damage events
# take exactly TWO values, one of them exactly half the other, and across the
# whole 13-recording scorpion corpus (1,510 events, 0 exceptions) NO BOLT EVER
# HAS MORE THAN ONE full-value event. So a bolt pays FULL to (at most) one body
# -- its aim target -- and exactly 50% to every other body it passes through.
# `damage_tier` labels an event on that basis. Killing blows are HP-clamped in
# the damage stream, so they are classified by which tier they are nearer.

def full_damage_scale(f: Fight, owner):
    """The un-clamped full-hit damage per (attacker slug, victim id-class)."""
    ev = [e for e in f.damage if e.get("attacker_owner") == owner]
    clean = [e["damage"] for e in ev if not e.get("kill")]
    return max(clean) if clean else (max((e["damage"] for e in ev), default=0.0))


def tier_of(dmg, kill, full):
    """'full' | 'half' -- for a kill, whichever tier the clamped value is near."""
    if full <= 0:
        return "full"
    if not kill:
        return "full" if abs(dmg - full) < abs(dmg - full * 0.5) else "half"
    return "full" if dmg > full * 0.5 + 1e-9 else "half"

def passthrough(f: Fight, owner):
    """Anatomy of every scorpion bolt fired by `owner`."""
    shots = [s for s in f.shots if s["owner"] == owner and not s["censored"]]
    full = full_damage_scale(f, owner)
    per_shot, geom = [], []
    tot = fullD = halfD = 0.0
    nfull = nhalf = 0
    full_per_bolt = Counter()
    victims_hist = Counter()
    for s in shots:
        ev = s["events"]
        victims_hist[len(ev)] += 1
        per_shot.append(len(ev))
        if not ev:
            continue
        nf = 0
        for i, e in enumerate(ev):
            tier = tier_of(e["damage"], e.get("kill"), full)
            tot += e["damage"]
            if tier == "full":
                nf += 1
                nfull += 1
                fullD += e["damage"]
            else:
                nhalf += 1
                halfD += e["damage"]
            vp = f.pos(e["victim"], e["t"])
            if vp:
                d, u = _seg_dist(vp[0], vp[1], s["sx"], s["sy"],
                                 s["ix"], s["iy"])
                geom.append({
                    "rank": i, "tier": tier, "perp": d,
                    "along": u * s["flight_tiles"], "u": u,
                    "dmg": e["damage"], "ratio": e["damage"] / full if full else 0,
                })
        full_per_bolt[nf] += 1
    hit = [n for n in per_shot if n > 0]
    return {
        "shots": len(shots), "shots_with_dmg": len(hit),
        "victims_hist": dict(sorted(victims_hist.items())),
        "victims_mean": mean(per_shot), "victims_mean_hit": mean(hit),
        "victims_max": max(per_shot) if per_shot else 0,
        "multi_rate": sum(1 for n in hit if n > 1) / max(1, len(hit)),
        "full_scale": full,
        "n_full": nfull, "n_half": nhalf,
        "full_per_bolt": dict(sorted(full_per_bolt.items())),
        "total_dmg": tot, "full_dmg": fullD, "half_dmg": halfD,
        "nonprimary_frac": halfD / tot if tot else 0.0,
        "nonprimary_events_frac": nhalf / max(1, nfull + nhalf),
        "geom": geom,
        "flight_tiles": [s["flight_tiles"] for s in shots],
        "reach_first": [g["along"] for g in geom if g["rank"] == 0],
    }


# ---------------------------------------------------------------------------
# 3. BLAST ANATOMY (onager)
# ---------------------------------------------------------------------------

def blast(f: Fight, owner, full_scale=None):
    """Victims-per-STONE and damage-vs-distance-from-impact for `owner`.

    Everything is keyed off the PRIMARY stone's landing point: on tape the
    damage-vs-distance curve is monotone in the distance to the primary's
    landing point and NOT in the distance to the nearest debris fragment, so
    the blast is one disc centred on the stone, not ten little ones. The nine
    fragments contribute their own events, and every one of them is exactly
    1.0 damage -- the engine-wide minimum-damage floor -- so they are counted
    separately as `chip` events rather than folded into the blast profile.
    """
    groups = shot_groups(f, owner)
    if full_scale is None:
        full_scale = full_damage_scale(f, owner)
    profile, hist, per_shot, chips = [], Counter(), [], []
    frag_geom = []
    ff = []
    for prim, secs in groups:
        ev = list(prim["events"]) + [e for s in secs for e in s["events"]]
        blast_ev = [e for e in ev if not (e["damage"] == 1.0 and not e.get("kill"))]
        chip_ev = [e for e in ev if e["damage"] == 1.0 and not e.get("kill")]
        chips.append(len(chip_ev))
        vic = len({e["victim"] for e in blast_ev})
        hist[vic] += 1
        per_shot.append(vic)
        for s in secs:
            frag_geom.append({
                "off": math.hypot(s["ix"] - prim["ix"], s["iy"] - prim["iy"]),
                # signed offset along the firing direction (forward positive)
                "fwd": _fwd_offset(prim, s),
                "lat": _lat_offset(prim, s),
                "dt": s["impact_t"] - prim["impact_t"],
            })
        for e in blast_ev:
            vp = f.pos(e["victim"], e["t"])
            if vp is None:
                continue
            d = math.hypot(vp[0] - prim["ix"], vp[1] - prim["iy"])
            profile.append({"dist": d, "dmg": e["damage"],
                            "frac": e["damage"] / full_scale if full_scale else 0,
                            "kill": bool(e.get("kill"))})
    for e in f.damage:
        if (e.get("attacker_owner") == e.get("victim_owner")
                and e.get("attacker_owner") == owner):
            ff.append(e)
    return {
        "shots": len(groups), "victims_hist": dict(sorted(hist.items())),
        "victims_mean": mean(per_shot),
        "victims_mean_hit": mean([n for n in per_shot if n > 0]),
        "victims_max": max(per_shot) if per_shot else 0,
        "chips_mean": mean(chips), "profile": profile, "frag_geom": frag_geom,
        "full_scale": full_scale,
        "friendly_events": len(ff),
        "friendly_damage": sum(e["damage"] for e in ff),
        "flight_times": [p["impact_t"] - p["t"] for p, _ in groups],
        "launch_dists": [p.get("launch_dist", p["flight_tiles"])
                         for p, _ in groups],
    }


def _fwd_offset(prim, sec):
    vx, vy = prim["ix"] - prim["sx"], prim["iy"] - prim["sy"]
    L = math.hypot(vx, vy)
    if L <= 1e-9:
        return 0.0
    return ((sec["ix"] - prim["ix"]) * vx + (sec["iy"] - prim["iy"]) * vy) / L


def _lat_offset(prim, sec):
    vx, vy = prim["ix"] - prim["sx"], prim["iy"] - prim["sy"]
    L = math.hypot(vx, vy)
    if L <= 1e-9:
        return 0.0
    return ((sec["ix"] - prim["ix"]) * (-vy) + (sec["iy"] - prim["iy"]) * vx) / L


def bucket_profile(profile, edges):
    out = []
    for lo, hi in zip(edges, edges[1:]):
        sel = [p for p in profile if lo <= p["dist"] < hi]
        if not sel:
            out.append({"band": f"{lo:.2f}-{hi:.2f}", "n": 0})
            continue
        out.append({
            "band": f"{lo:.2f}-{hi:.2f}", "n": len(sel),
            "dmg_mean": r(mean([p["dmg"] for p in sel])),
            "dmg_med": r(med([p["dmg"] for p in sel])),
            "frac_mean": r(mean([p["frac"] for p in sel]), 3),
        })
    return out


# ---------------------------------------------------------------------------
# 4. OPPONENT-SIDE DECOMPOSITION (cadence / contact / damage-per-hit)
# ---------------------------------------------------------------------------

def side_melee_stats(f: Fight, owner, dict_row):
    """C1-style decomposition of one side's OUTPUT: how often it swung, how
    much each swing paid, and how long it took to land the first one."""
    ev = [e for e in f.damage if e.get("attacker_owner") == owner]
    per_att = defaultdict(list)
    for e in ev:
        per_att[e["attacker"]].append(e["t"])
    gaps = []
    for ts in per_att.values():
        ts.sort()
        gaps += [b - a for a, b in zip(ts, ts[1:]) if 0.05 < b - a < 30]
    dmgs = [e["damage"] for e in ev]
    n_units = f.sides[owner]["count"]
    dur = max(1e-6, f.end_t)
    firsts = [min(ts) for ts in per_att.values() if ts]
    return {
        "hits": len(ev),
        "dmg": sum(dmgs),
        "dmg_per_hit": mean(dmgs),
        "hits_per_unit_min": 60.0 * len(ev) / (n_units * dur),
        "swing_gap_med": med(gaps),
        "first_blood": min(firsts) if firsts else None,
        "attackers": len(per_att),
        "attackers_frac": len(per_att) / max(1, n_units),
        "dps_per_unit": sum(dmgs) / (n_units * dur),
    }


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def sec_board(fights, sim_dir, seeds, dicts, out):
    rows = board(fights, sim_dir, seeds, dicts)
    out["board"] = rows
    cols = ["tag", "siege", "tape_win", "eng_win%", "agree",
            "side1", "tapeHP1", "engHP1", "errHP1",
            "side2", "tapeHP2", "engHP2", "errHP2", "absErr"]
    table(sorted(rows, key=lambda x: -(x["absErr"] or 0)), cols,
          "BOARD -- 25 siege recordings vs engine (%d seeds), ranked by |HP err|" % seeds)
    flips = [x for x in rows if x["agree"] == "FLIP"]
    print(f"\n  winners: {len(rows) - len(flips)}/{len(rows)} agree; "
          f"flips: {', '.join(x['tag'] for x in flips) or 'none'}")
    sg_err = [abs(x["siege_err"]) for x in rows if x["siege_err"] != ""]
    op_err = [abs(x["opp_err"]) for x in rows if x["opp_err"] != ""]
    print(f"  mean |err| on the SIEGE side:    {r(mean(sg_err),2)}  (n={len(sg_err)})")
    print(f"  mean |err| on the OPPONENT side: {r(mean(op_err),2)}  (n={len(op_err)})")
    for slug in ("heavy_scorpion", "siege_onager"):
        sel = [x for x in rows if x["siege"].startswith(slug[:13])]
        if sel:
            print(f"  {slug:15s} n={len(sel):2d}  "
                  f"mean|err| siege {r(mean([abs(x['siege_err']) for x in sel]),2)}  "
                  f"opp {r(mean([abs(x['opp_err']) for x in sel]),2)}  "
                  f"winners {sum(1 for x in sel if x['agree']=='OK')}/{len(sel)}")


def sec_duration(fights, sim_dir, seeds, out):
    rows = []
    for fm in fights:
        t = load_tape(fm)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        last_dmg = max((e["t"] for e in t.damage_all), default=0.0)
        rows.append({
            "tag": fm["tag"],
            "stream": r(t.stream_end_s, 1),
            "wipe": r(t.wipe_t, 1) if t.wipe_t else "no-wipe",
            "last_dmg": r(last_dmg, 1),
            "tail": r(t.stream_end_s - (t.wipe_t or t.stream_end_s), 1),
            "eng": r(mean([e.duration_s for e in engs]), 1) if engs else None,
            "eng/wipe": r(mean([e.duration_s for e in engs]) / t.end_t, 2) if engs and t.end_t else None,
            "eng/stream": r(mean([e.duration_s for e in engs]) / t.stream_end_s, 2) if engs else None,
        })
    out["duration"] = rows
    table(sorted(rows, key=lambda x: x["tag"]),
          ["tag", "stream", "wipe", "last_dmg", "tail", "eng", "eng/wipe", "eng/stream"],
          "DURATION -- recorder tail vs true wipe vs engine")
    rr = [x["eng/wipe"] for x in rows if x["eng/wipe"]]
    print(f"\n  engine/wipe ratio: mean {r(mean(rr))}  median {r(med(rr))}  "
          f"min {r(min(rr))}  max {r(max(rr))}")
    nw = [x["tag"] for x in rows if x["wipe"] == "no-wipe"]
    print(f"  recordings that never wipe: {len(nw)}  {', '.join(nw) or '-'}")


def sec_pair(fights, sim_dir, seeds, out):
    rows = []
    for fm in fights:
        t = load_tape(fm)
        res = [e["resid"] for e in t.damage_all if e.get("shot") is not None]
        rows.append({
            "tag": fm["tag"], "dmg_events": len(t.damage_all),
            "attributed": len(res),
            "unattr": len(t.unattributed),
            "resid_med": r(med(res), 3), "resid_p90": r(q(res, 0.9), 3),
            "resid_max": r(max(res), 3) if res else None,
        })
    out["pair"] = rows
    table(rows, ["tag", "dmg_events", "attributed", "unattr",
                 "resid_med", "resid_p90", "resid_max"],
          "PAIRING AUDIT -- damage events attributed to a missile track (tape)")
    tot = sum(x["dmg_events"] for x in rows)
    ua = sum(x["unattr"] for x in rows)
    print(f"\n  {tot - ua}/{tot} events attributed ({100*(tot-ua)/max(1,tot):.1f}%); "
          f"unattributed are melee swings (no missile) + censored flights")


def sec_passthrough(fights, sim_dir, seeds, out):
    rows, geom_all_t, geom_all_e = [], [], []
    lad_t, lad_e = defaultdict(list), defaultdict(list)
    for fm in fights:
        slugs = {fm["side1"]["slug"], fm["side2"]["slug"]}
        if "heavy_scorpion" not in slugs:
            continue
        owner = next(s["owner"] for s in (fm["side1"], fm["side2"])
                     if s["slug"] == "heavy_scorpion")
        t = load_tape(fm)
        pt = passthrough(t, owner)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        pes = [passthrough(e, owner) for e in engs]
        geom_all_t += pt["geom"]
        for p in pes:
            geom_all_e += p["geom"]
        rows.append({
            "tag": fm["tag"],
            "T_shots": pt["shots"], "T_vic/shot": r(pt["victims_mean"]),
            "T_vic/hit": r(pt["victims_mean_hit"]), "T_max": pt["victims_max"],
            "T_multi%": r(100 * pt["multi_rate"], 1),
            "T_np%dmg": r(100 * pt["nonprimary_frac"], 1),
            "T_np%ev": r(100 * pt["nonprimary_events_frac"], 1),
            "T_fpb": str(pt["full_per_bolt"]),
            "E_shots": r(mean([p["shots"] for p in pes]), 1),
            "E_vic/shot": r(mean([p["victims_mean"] for p in pes])),
            "E_vic/hit": r(mean([p["victims_mean_hit"] or 0 for p in pes])),
            "E_max": max(p["victims_max"] for p in pes),
            "E_multi%": r(100 * mean([p["multi_rate"] for p in pes]), 1),
            "E_np%dmg": r(100 * mean([p["nonprimary_frac"] for p in pes]), 1),
            "T_flight": r(med(pt["flight_tiles"])),
            "E_flight": r(med([x for p in pes for x in p["flight_tiles"]])),
        })
    out["passthrough"] = rows
    table(rows, ["tag", "T_shots", "T_vic/shot", "T_vic/hit", "T_max",
                 "T_multi%", "T_np%dmg", "T_np%ev", "T_fpb",
                 "E_shots", "E_vic/shot", "E_vic/hit", "E_max",
                 "E_multi%", "E_np%dmg", "T_flight", "E_flight"],
          "PASS-THROUGH -- victims per scorpion bolt, tape (T) vs engine (E). "
          "T_fpb = how many FULL-damage victims a bolt had")
    tot_np = sum(x["T_np%dmg"] * 1 for x in rows)
    print(f"\n  corpus: mean non-primary share of scorpion DAMAGE "
          f"tape {r(mean([x['T_np%dmg'] for x in rows]),1)}%  "
          f"engine {r(mean([x['E_np%dmg'] for x in rows]),1)}%")
    print(f"  corpus: victims per bolt that landed  "
          f"tape {r(mean([x['T_vic/hit'] for x in rows]),2)}  "
          f"engine {r(mean([x['E_vic/hit'] for x in rows]),2)}")

    print("\n  DAMAGE TIER (damage / this fight's full-hit value) -- tape only.")
    print("  Two values and nothing between them is the whole distribution.")
    tr = []
    for lab, g in (("tape", geom_all_t), ("engine", geom_all_e)):
        c = Counter(round(x["ratio"], 3) for x in g)
        for v, n in sorted(c.items(), reverse=True)[:8]:
            tr.append({"src": lab, "dmg/full": v, "n": n,
                       "share%": r(100 * n / len(g), 1)})
    table(tr, ["src", "dmg/full", "n", "share%"], "")
    out["tiers"] = tr

    print("\n  CORRIDOR -- how far off the bolt's own launch->end line a victim")
    print("  may sit (perp), and where along the line it sits (along).")
    gr = []
    for lab, g in (("tape", geom_all_t), ("engine", geom_all_e)):
        for tier in ("full", "half"):
            sel = [x for x in g if x["tier"] == tier]
            if not sel:
                continue
            gr.append({"src": lab, "tier": tier, "n": len(sel),
                       "perp_med": r(med([x["perp"] for x in sel]), 3),
                       "perp_p90": r(q([x["perp"] for x in sel], 0.9), 3),
                       "perp_p99": r(q([x["perp"] for x in sel], 0.99), 3),
                       "perp_max": r(max(x["perp"] for x in sel), 3),
                       "along_med": r(med([x["along"] for x in sel]), 2),
                       "along_max": r(max(x["along"] for x in sel), 2),
                       "u_med": r(med([x["u"] for x in sel]), 3)})
    table(gr, ["src", "tier", "n", "perp_med", "perp_p90", "perp_p99",
               "perp_max", "along_med", "along_max", "u_med"], "")
    out["geometry"] = gr

    print("\n  OVERSHOOT -- the bolt does not stop at the body it pays FULL")
    print("  damage to. Per bolt that had a full-damage victim:")
    ovr = []
    for src, mk in (("tape", lambda fm: [load_tape(fm)]),
                    ("engine", lambda fm: [e for e in
                                           (load_engine(sim_dir, fm, s)
                                            for s in range(1, seeds + 1))
                                           if e is not None])):
        past_tiles, n_past, share = [], [], []
        for fm in fights:
            slugs = {fm["side1"]["slug"], fm["side2"]["slug"]}
            if "heavy_scorpion" not in slugs:
                continue
            owner = next(s["owner"] for s in (fm["side1"], fm["side2"])
                         if s["slug"] == "heavy_scorpion")
            for fg in mk(fm):
                full = full_damage_scale(fg, owner)
                for s in fg.shots:
                    if s["owner"] != owner or not s["events"]:
                        continue
                    rec = []
                    for e in s["events"]:
                        vp = fg.pos(e["victim"], e["t"])
                        if vp is None:
                            continue
                        _d, u = _seg_dist(vp[0], vp[1], s["sx"], s["sy"],
                                          s["ix"], s["iy"])
                        rec.append((u * s["flight_tiles"],
                                    tier_of(e["damage"], e.get("kill"), full)))
                    pf = [a for a, t in rec if t == "full"]
                    if not pf:
                        continue
                    a0 = pf[0]
                    past_tiles.append(s["flight_tiles"] - a0)
                    n_past.append(sum(1 for a, t in rec if a > a0 + 1e-6))
                    share.append(1 if any(a > a0 + 1e-6 for a, _t in rec) else 0)
        ovr.append({"src": src, "bolts": len(past_tiles),
                    "past_med": r(med(past_tiles), 2),
                    "past_p90": r(q(past_tiles, 0.9), 2),
                    "victims_past_mean": r(mean(n_past), 2),
                    "bolts_with_a_victim_past%": r(100 * mean(share), 1)})
    table(ovr, ["src", "bolts", "past_med", "past_p90",
                "victims_past_mean", "bolts_with_a_victim_past%"], "")
    out["overshoot"] = ovr

    # spacing between consecutive victims along the bolt
    print("\n  SPACING between consecutive victims of the same bolt (tape)")
    sp = []
    for fm in fights:
        slugs = {fm["side1"]["slug"], fm["side2"]["slug"]}
        if "heavy_scorpion" not in slugs:
            continue
        owner = next(s["owner"] for s in (fm["side1"], fm["side2"])
                     if s["slug"] == "heavy_scorpion")
        t = load_tape(fm)
        for s in t.shots:
            if s["owner"] != owner or len(s["events"]) < 2:
                continue
            alongs = []
            for e in s["events"]:
                vp = t.pos(e["victim"], e["t"])
                if vp:
                    d, u = _seg_dist(vp[0], vp[1], s["sx"], s["sy"], s["ix"], s["iy"])
                    alongs.append(u * s["flight_tiles"])
            alongs.sort()
            sp += [b - a for a, b in zip(alongs, alongs[1:])]
    print(f"    n={len(sp)}  median {r(med(sp))}  p10 {r(q(sp,0.1))}  "
          f"p90 {r(q(sp,0.9))}  min {r(min(sp)) if sp else None}")
    out["spacing"] = {"n": len(sp), "median": med(sp), "p10": q(sp, 0.1),
                      "p90": q(sp, 0.9)}


def sec_blast(fights, sim_dir, seeds, out):
    rows = []
    prof_t, prof_e, frag = [], [], []
    for fm in fights:
        slugs = {fm["side1"]["slug"], fm["side2"]["slug"]}
        if "siege_onager" not in slugs:
            continue
        owner = next(s["owner"] for s in (fm["side1"], fm["side2"])
                     if s["slug"] == "siege_onager")
        t = load_tape(fm)
        bt = blast(t, owner)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        # The engine's damage scale is its OWN full hit, so the frac column is
        # comparable even where the two disagree about armour.
        bes = [blast(e, owner) for e in engs]
        prof_t += bt["profile"]
        frag += bt["frag_geom"]
        for b in bes:
            prof_e += b["profile"]
        rows.append({
            "tag": fm["tag"],
            "T_stones": bt["shots"], "T_vic/shot": r(bt["victims_mean"]),
            "T_vic/hit": r(bt["victims_mean_hit"]), "T_max": bt["victims_max"],
            "T_chip": r(bt["chips_mean"], 2),
            "T_full": r(bt["full_scale"], 1),
            "E_stones": r(mean([b["shots"] for b in bes]), 1),
            "E_vic/shot": r(mean([b["victims_mean"] for b in bes])),
            "E_vic/hit": r(mean([b["victims_mean_hit"] or 0 for b in bes])),
            "E_max": max(b["victims_max"] for b in bes),
            "E_full": r(mean([b["full_scale"] for b in bes]), 1),
            "T_ff": bt["friendly_events"], "T_ffdmg": r(bt["friendly_damage"], 1),
            "E_ff": r(mean([b["friendly_events"] for b in bes]), 2),
            "T_flt_s": r(med(bt["flight_times"]), 2),
            "E_flt_s": r(med([x for b in bes for x in b["flight_times"]]), 2),
            "T_range": r(med(bt["launch_dists"]), 2),
            "E_range": r(med([x for b in bes for x in b["launch_dists"]]), 2),
        })
    out["blast"] = rows
    table(rows, ["tag", "T_stones", "T_vic/shot", "T_vic/hit", "T_max", "T_chip",
                 "T_full", "E_stones", "E_vic/shot", "E_vic/hit", "E_max",
                 "E_full", "T_ff", "T_ffdmg", "E_ff", "T_flt_s", "E_flt_s",
                 "T_range", "E_range"],
          "BLAST -- victims per siege-onager STONE (the 9 debris fragments "
          "folded in), tape (T) vs engine (E)")
    print(f"\n  corpus: victims per landed stone  "
          f"tape {r(mean([x['T_vic/hit'] for x in rows]),2)}  "
          f"engine {r(mean([x['E_vic/hit'] for x in rows]),2)}")

    print("\n  DEBRIS -- the nine master-369 fragments launched with every stone.")
    print("  Offsets are relative to the primary stone's landing point, along")
    print("  the firing direction (fwd) and across it (lat).")
    if frag:
        table([{"n": len(frag),
                "off_med": r(med([x["off"] for x in frag]), 3),
                "off_p90": r(q([x["off"] for x in frag], 0.9), 3),
                "off_max": r(max(x["off"] for x in frag), 3),
                "fwd_med": r(med([x["fwd"] for x in frag]), 3),
                "fwd_min": r(min(x["fwd"] for x in frag), 3),
                "fwd_max": r(max(x["fwd"] for x in frag), 3),
                "lat_med": r(med([x["lat"] for x in frag]), 3),
                "lat_p90": r(q([abs(x["lat"]) for x in frag], 0.9), 3),
                "dt_med": r(med([x["dt"] for x in frag]), 3)}],
              ["n", "off_med", "off_p90", "off_max", "fwd_med", "fwd_min",
               "fwd_max", "lat_med", "lat_p90", "dt_med"], "")
    out["fragments"] = {"n": len(frag),
                        "off_med": med([x["off"] for x in frag]) if frag else None,
                        "off_max": max((x["off"] for x in frag), default=None)}

    edges = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
    print("\n  DAMAGE vs DISTANCE from the STONE's landing point.")
    print("  frac = damage / that side's full-hit damage. E4's shipped rule is")
    print("  frac = 1 - (dist - victim_radius)/1.5, floored at 1 damage.")
    bt = bucket_profile(prof_t, edges)
    be = bucket_profile(prof_e, edges)
    merged = []
    for a, b in zip(bt, be):
        merged.append({"band": a["band"], "T_n": a["n"],
                       "T_dmg": a.get("dmg_mean"), "T_frac": a.get("frac_mean"),
                       "E_n": b["n"], "E_dmg": b.get("dmg_mean"),
                       "E_frac": b.get("frac_mean")})
    table(merged, ["band", "T_n", "T_dmg", "T_frac", "E_n", "E_dmg", "E_frac"], "")
    out["blast_profile"] = merged

    # least-squares line through the un-floored tape points: frac = 1 - (d-a)/b
    pts = [p for p in prof_t if not p["kill"] and p["frac"] > 0.03]
    if len(pts) > 8:
        xs = [p["dist"] for p in pts]
        ys = [p["frac"] for p in pts]
        n = len(xs)
        mx, my = mean(xs), mean(ys)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sxy / sxx if sxx else 0
        icpt = my - slope * mx
        zero = -icpt / slope if slope else None
        one = (1 - icpt) / slope if slope else None
        print(f"\n  fitted tape falloff (n={n}, un-floored points): "
              f"frac = {icpt:.3f} {slope:+.3f}*d")
        print(f"    -> full damage out to d = {one:.3f} tiles, "
              f"zero at d = {zero:.3f} tiles, width = {zero - one:.3f}")
        print(f"    E4's shipped rule with a 0.2-tile victim radius: full to "
              f"0.200, zero at 1.700, width 1.500")
        out["blast_fit"] = {"n": n, "slope": slope, "intercept": icpt,
                            "full_to": one, "zero_at": zero}


def sec_friendly(fights, sim_dir, seeds, out):
    rows = []
    for fm in fights:
        t = load_tape(fm)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        tff = [e for e in t.damage if e.get("attacker_owner") == e.get("victim_owner")]
        eff = mean([sum(1 for e2 in e.damage
                        if e2.get("attacker_owner") == e2.get("victim_owner"))
                    for e in engs]) if engs else None
        rows.append({
            "tag": fm["tag"], "T_events": len(t.damage), "T_ff": len(tff),
            "T_ff%": r(100 * len(tff) / max(1, len(t.damage)), 2),
            "T_ff_dmg": r(sum(e["damage"] for e in tff), 1),
            "T_ff_kills": sum(1 for e in tff if e.get("kill")),
            "E_ff": r(eff, 2),
        })
    out["friendly"] = rows
    table(rows, ["tag", "T_events", "T_ff", "T_ff%", "T_ff_dmg", "T_ff_kills", "E_ff"],
          "FRIENDLY FIRE -- damage events whose attacker and victim share an owner")


def sec_minrange(fights, sim_dir, seeds, dicts, out):
    """Shots taken from inside the unit's dat minimum range, both sides.

    The tape's "range of this shot" is the distance from the muzzle to the
    body that took FULL damage -- i.e. the shot's aim target. It is NOT the
    distance to the first body damaged: a pass-through bolt aimed at something
    8 tiles away routinely damages a unit 1 tile away first, and scoring that
    as a 1-tile shot would invent a min-range violation that never happened.
    """
    rows = []
    for fm in fights:
        sg = siege_side(fm)
        t = load_tape(fm)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        for side in (fm["side1"], fm["side2"]):
            if side["slug"] not in SIEGE_SLUGS:
                continue
            d = dicts.get(f"{side['civ']}|{side['slug']}")
            minr = d["min_attack_range"] if d else 0
            maxr = d["attack_range"] if d else 0
            o = side["owner"]
            full = full_damage_scale(t, o)
            tl = []
            for prim, secs in shot_groups(t, o):
                ev = list(prim["events"]) + [e for s in secs for e in s["events"]]
                aim = [e for e in ev
                       if tier_of(e["damage"], e.get("kill"), full) == "full"]
                if not aim:
                    continue
                vp = t.pos(aim[0]["victim"], aim[0]["t"])
                if vp:
                    tl.append(math.hypot(vp[0] - prim["sx"], vp[1] - prim["sy"]))
            el = [x.get("launch_dist", x["flight_tiles"])
                  for e in engs for x in e.shots if x["owner"] == o]
            rows.append({
                "tag": fm["tag"], "slug": side["slug"], "min_r": minr, "max_r": maxr,
                "T_n": len(tl), "T_med": r(med(tl)), "T_min": r(min(tl)) if tl else None,
                "T_<min%": r(100 * sum(1 for x in tl if x < minr) / max(1, len(tl)), 1),
                "E_n": len(el), "E_med": r(med(el)), "E_min": r(min(el)) if el else None,
                "E_<min%": r(100 * sum(1 for x in el if x < minr) / max(1, len(el)), 1),
                "E_>max%": r(100 * sum(1 for x in el if x > maxr + 0.6) / max(1, len(el)), 1),
            })
    out["minrange"] = rows
    table(rows, ["tag", "slug", "min_r", "max_r", "T_n", "T_med", "T_min", "T_<min%",
                 "E_n", "E_med", "E_min", "E_<min%", "E_>max%"],
          "RANGE DISCIPLINE -- shot distances vs the dat min/max range")


def sec_siegeout(fights, sim_dir, seeds, dicts, out):
    """The SIEGE side's own output, decomposed into shots x damage-per-shot.

    dps_x = shots_x * dmg-per-shot_x, so the table says whether the engine's
    siege unit is firing at the wrong RATE or paying the wrong PRICE per shot
    -- the two have completely different fixes.
    """
    rows = []
    for fm in fights:
        for side in (fm["side1"], fm["side2"]):
            if side["slug"] not in SIEGE_SLUGS:
                continue
            o = side["owner"]
            t = load_tape(fm)
            engs = [e for e in (load_engine(sim_dir, fm, s)
                                for s in range(1, seeds + 1)) if e is not None]
            if not engs:
                continue

            def stats(f):
                g = shot_groups(f, o)
                dmg = sum(e["damage"] for e in f.damage
                          if e.get("attacker_owner") == o)
                n = f.sides[o]["count"]
                dur = max(1e-6, f.end_t)
                return {
                    "shots": len(g),
                    "shots_per_unit_min": 60.0 * len(g) / (n * dur),
                    "dmg": dmg, "dmg_per_shot": dmg / max(1, len(g)),
                    "dps_per_unit": dmg / (n * dur),
                    "kills": sum(1 for e in f.damage
                                 if e.get("attacker_owner") == o and e.get("kill")),
                }
            ts = stats(t)
            es = [stats(e) for e in engs]

            def em(k):
                return mean([x[k] for x in es])
            rows.append({
                "tag": fm["tag"], "siege": side["slug"][:14],
                "T_shot/u/m": r(ts["shots_per_unit_min"], 2),
                "E_shot/u/m": r(em("shots_per_unit_min"), 2),
                "rate_x": r(em("shots_per_unit_min") / ts["shots_per_unit_min"], 2)
                if ts["shots_per_unit_min"] else None,
                "T_dmg/shot": r(ts["dmg_per_shot"], 1),
                "E_dmg/shot": r(em("dmg_per_shot"), 1),
                "shot_x": r(em("dmg_per_shot") / ts["dmg_per_shot"], 2)
                if ts["dmg_per_shot"] else None,
                "T_dps/u": r(ts["dps_per_unit"], 2),
                "E_dps/u": r(em("dps_per_unit"), 2),
                "dps_x": r(em("dps_per_unit") / ts["dps_per_unit"], 2)
                if ts["dps_per_unit"] else None,
                "T_kills": ts["kills"], "E_kills": r(em("kills"), 1),
            })
    out["siegeout"] = rows
    table(sorted(rows, key=lambda x: (x["siege"], -(x["dps_x"] or 0))),
          ["tag", "siege", "T_shot/u/m", "E_shot/u/m", "rate_x",
           "T_dmg/shot", "E_dmg/shot", "shot_x", "T_dps/u", "E_dps/u", "dps_x",
           "T_kills", "E_kills"],
          "SIEGE SIDE OUTPUT -- fire rate x damage-per-shot (engine / tape)")
    for slug in ("heavy_scorpion", "siege_onager"):
        sel = [x for x in rows if x["siege"].startswith(slug[:14])]
        if sel:
            print(f"  {slug:15s} mean rate_x {r(mean([x['rate_x'] for x in sel if x['rate_x']]),2)}  "
                  f"shot_x {r(mean([x['shot_x'] for x in sel if x['shot_x']]),2)}  "
                  f"dps_x {r(mean([x['dps_x'] for x in sel if x['dps_x']]),2)}")


def sec_opponent(fights, sim_dir, seeds, dicts, out):
    rows = []
    for fm in fights:
        sg = siege_side(fm)
        if sg is None:
            continue
        sg_owner, sg_slug, op_owner, op_slug = sg
        t = load_tape(fm)
        engs = [e for e in (load_engine(sim_dir, fm, s) for s in range(1, seeds + 1))
                if e is not None]
        if not engs:
            continue
        d = dicts.get(f"{[s for s in (fm['side1'], fm['side2']) if s['owner']==op_owner][0]['civ']}|{op_slug}")
        ts = side_melee_stats(t, op_owner, d)
        es = [side_melee_stats(e, op_owner, d) for e in engs]

        def em(k):
            v = [x[k] for x in es if x[k] is not None]
            return mean(v)
        rows.append({
            "tag": fm["tag"], "opp": op_slug[:14],
            "T_dps/u": r(ts["dps_per_unit"], 2), "E_dps/u": r(em("dps_per_unit"), 2),
            "dps_x": r(em("dps_per_unit") / ts["dps_per_unit"], 2) if ts["dps_per_unit"] else None,
            "T_hpm": r(ts["hits_per_unit_min"], 2), "E_hpm": r(em("hits_per_unit_min"), 2),
            "cad_x": r(em("hits_per_unit_min") / ts["hits_per_unit_min"], 2) if ts["hits_per_unit_min"] else None,
            "T_dmg/hit": r(ts["dmg_per_hit"], 2), "E_dmg/hit": r(em("dmg_per_hit"), 2),
            "dph_x": r(em("dmg_per_hit") / ts["dmg_per_hit"], 2) if ts["dmg_per_hit"] else None,
            "T_fb": r(ts["first_blood"], 2), "E_fb": r(em("first_blood"), 2),
            "T_actv": r(ts["attackers_frac"], 2), "E_actv": r(em("attackers_frac"), 2),
        })
    out["opponent"] = rows
    table(sorted(rows, key=lambda x: -(x["dps_x"] or 0)),
          ["tag", "opp", "T_dps/u", "E_dps/u", "dps_x", "T_hpm", "E_hpm", "cad_x",
           "T_dmg/hit", "E_dmg/hit", "dph_x", "T_fb", "E_fb", "T_actv", "E_actv"],
          "OPPONENT SIDE -- is the non-siege side's error cadence, contact or damage-per-hit?")
    print("\n  dps_x = engine / tape.  dps_x ~= cad_x * dph_x, so whichever of the")
    print("  two is further from 1.0 is the term that carries the error.")


def sec_dictgap(fights, dicts, dat_json, out):
    """Every dat field for the two siege units next to what the dict carries."""
    dat = json.loads(Path(dat_json).read_text(encoding="utf-8")) if dat_json else None
    if dat is None:
        print("\n(no --dat-json; run tools/simjs/d1_dat_audit.py first)")
        return
    ids = {"heavy_scorpion": "542", "siege_onager": "588"}
    rows = []
    for slug, uid in ids.items():
        rec = dat["units"].get(uid)
        if not rec:
            continue
        key = next((k for k in dicts if k.endswith("|" + slug)), None)
        dd = dicts.get(key, {})
        t50 = rec["type_50"] or {}
        proj = rec.get("projectile") or {}
        pblk = proj.get("projectile_block") or {}
        pairs = [
            ("max_range", t50.get("max_range"), dd.get("attack_range")),
            ("min_range", t50.get("min_range"), dd.get("min_attack_range")),
            ("reload_time", t50.get("reload_time"), 1 / dd["attack_speed"] if dd.get("attack_speed") else None),
            ("frame_delay/60", (t50.get("frame_delay") or 0) / 60.0, dd.get("attack_delay")),
            ("accuracy_percent", t50.get("accuracy_percent"), dd.get("accuracy")),
            ("accuracy_dispersion", t50.get("accuracy_dispersion"), "(no column)"),
            ("blast_width", t50.get("blast_width"), dd.get("splash_radius")),
            ("blast_attack_level", t50.get("blast_attack_level"), "(no column)"),
            ("blast_damage", t50.get("blast_damage"), dd.get("splash_on_hit_fraction")),
            ("projectile_speed", proj.get("speed"), dd.get("projectile_speed")),
            ("projectile_arc", pblk.get("projectile_arc"), "(no column)"),
            ("proj hit_mode", pblk.get("hit_mode"), "(no column)"),
            ("proj vanish_mode", pblk.get("vanish_mode"), "(no column)"),
            ("proj smart_mode", pblk.get("smart_mode"), "(no column)"),
            ("proj area_effect_specials", pblk.get("area_effect_specials"), "(no column)"),
            ("proj collision_x", proj.get("collision_x"), "(no column)"),
            ("proj attacks", str((proj.get("type_50") or {}).get("attacks")),
             f"pass_through_percent={dd.get('pass_through_percent')}"),
            ("pass_through_count", "(not a dat field)", dd.get("pass_through_count")),
        ]
        for name, datv, dictv in pairs:
            rows.append({"unit": slug, "dat field": name, "dat": datv, "dict": dictv})
    out["dictgap"] = rows
    table(rows, ["unit", "dat field", "dat", "dict"],
          "DAT vs COMBAT DICT -- what the pipeline carries and what it drops")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-runs-dir", default=str(DEFAULT_SIMRUNS))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--tags")
    ap.add_argument("--section", default="all")
    ap.add_argument("--json")
    ap.add_argument("--dat-json", default="D:/AI/aoe2_golden/d1_dat_audit.json")
    args = ap.parse_args()

    sim_dir = Path(args.sim_runs_dir)
    tags = set(args.tags.split(",")) if args.tags else None
    fights = siege_fights(load_manifest(), tags)
    dicts = load_dicts()
    print(f"D1 siege forensics: {len(fights)} fights, {args.seeds} engine seeds, "
          f"sim dir {sim_dir}")
    out = {}
    S = args.section
    if S in ("all", "board"):
        sec_board(fights, sim_dir, args.seeds, dicts, out)
    if S in ("all", "duration"):
        sec_duration(fights, sim_dir, args.seeds, out)
    if S in ("all", "pair"):
        sec_pair(fights, sim_dir, args.seeds, out)
    if S in ("all", "passthrough"):
        sec_passthrough(fights, sim_dir, args.seeds, out)
    if S in ("all", "blast"):
        sec_blast(fights, sim_dir, args.seeds, out)
    if S in ("all", "friendly"):
        sec_friendly(fights, sim_dir, args.seeds, out)
    if S in ("all", "minrange"):
        sec_minrange(fights, sim_dir, args.seeds, dicts, out)
    if S in ("all", "siegeout"):
        sec_siegeout(fights, sim_dir, args.seeds, dicts, out)
    if S in ("all", "opponent"):
        sec_opponent(fights, sim_dir, args.seeds, dicts, out)
    if S in ("all", "dictgap"):
        sec_dictgap(fights, dicts, args.dat_json, out)
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, default=str),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
