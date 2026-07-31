"""R5c: WHAT MECHANISM puts tape ranged units INSIDE their reach lip.

Measurement only. Nothing here writes to the engine; the engine is imported for
nothing at all -- its geometry constants are mirrored from
``ranged_fire_forensics`` (which mirrors ``battle_unit.js``) so a tape number
and an engine number are the same statistic computed by the same code.

THE PREMISE, AND WHY IT HAD TO BE RE-MEASURED FIRST
---------------------------------------------------
R5b's D4 approach margin was fitted against "the tape fires from 0.9-1.4 tiles
inside its reach", a figure taken from ``accuracy()``'s ``launch_range_med``,
which is ``shot["dist"]`` -- the length of the reconstructed FLIGHT, i.e.
|impact point - launch point|. On a tape neither endpoint is a unit centre:

    launch point = shooter centre + 0.615 tiles TOWARD the target
    impact point = victim  centre - 0.24..0.32 tiles toward the shooter

Both offsets are purely radial: measured over the 1,147 tape shots whose victim
the damage pairing names outright, the PERPENDICULAR component of each is
0.000 tiles on all twelve sides, so they are not a coordinate-frame skew
between the units stream and the missiles stream -- they are insets along the
shot line, and they are the same size whatever direction the shot is fired in.
The launch inset is also not a sampling lag: it would then scale with
projectile speed, and the hand cannoneer's bullet is 7% faster than the
arbalester's arrow while its inset is 1.3% larger.

So the recorded flight is ~0.86-0.93 tiles SHORTER than the shooter-to-target
distance, and the whole of the "0.9-1.4 tiles inside reach" residual is that
bookkeeping. Section 0 below quantifies it per side. Everything after Section 0
measures range CENTRE-TO-CENTRE off the 10 Hz position stream, on both sources,
which is the frame the melee corpus already validated ``engine_reach`` against
to within 0.02 tiles of observed contact distance.

WHAT IS THEN MEASURED
---------------------
  0  RECONCILIATION  flight-distance depth vs true centre-to-centre depth.
  1  STANDOFF        two different questions, kept apart:
                       (a) where units STAND -- reach - (distance to the
                           NEAREST living enemy), over every unit-frame, no
                           shot bookkeeping involved;
                       (b) where units SHOOT FROM -- reach - (distance to the
                           unit they actually fired at).
                     (a) is positioning. (b) is positioning + target choice.
  2  H4 PREDICATE    the stopping distribution against four range predicates
                     differing only in which radii they count:
                       C  = attack_range                     (centre->centre)
                       SE = attack_range + r_self            (own edge->centre)
                       TE = attack_range + r_target          (centre->target edge)
                       EE = attack_range + r_self + r_target (edge->edge)
                     plus ENG = EE + MELEE_RANGE_BUFFER, what inRange() uses.
  3  H1 ARMY DEPTH   launch depth by the shooter's RANK (distance-order within
                     its own army toward the enemy centroid), and the army's
                     own depth along the threat axis.
  4  H2 TARGET MOTION  launch depth by the TARGET's speed and its radial
                     component over the preceding 1 s / 2 s.
  5  H3 RE-APPROACH  launch depth on the first shot after a retarget vs the
                     2nd/3rd/4th+ at the same target, and vs the shooter's own
                     launch gap.
  6  H5 HCA v HC     30-bucket closure timeline of the one failing fight.
  7  TARGET CHOICE   how much further than the nearest enemy the chosen target
                     was, and the chosen target's distance-rank among enemies.

DEFINITIONS
-----------
target    engine: the shot probe's recorded ``true_target`` (ground truth).
          tape: the victim named by the damage pairing when the shot HIT
          ("certain"), else ranged_fire_forensics' inferred aim target.
          ``--certain-only`` restricts every table to the certain subset.
depth     reach - range, tiles, positive = inside the lip. reach = the
          engine's own inRange() reach for that ordered (shooter, target)
          pair.
rank      0-based index of a unit among its own side's LIVING units sorted
          ascending by distance to the enemy centroid. 0 = frontmost.
army depth  (max - min) of own-army projections onto the unit vector from own
          centroid to enemy centroid, tiles.

    PYTHONPATH=. python tools/simjs/ranged_depth_forensics.py \
        --sim-runs-dir D:/AI/aoe2_golden/shots_r5c --seeds 20 --section all
    ... --section recon|standoff|predicate|rank|motion|retarget|timeline|choice
    ... --certain-only     tape shots restricted to paired hits
    ... --json out.json
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ranged_fire_forensics import (          # noqa: E402
    CALIB, R5_TAGS, SHORT, TILE, MELEE_RANGE_BUFFER_PX,
    load_tape, load_engine, physics_radius_px,
    centroid, med, q, r, pct, table,
)

# A shooter counts as SETTLED when it has not moved for this long before the
# launch (same 0.02-tile step bar the rest of the campaign uses). A settled
# unit's range IS its stopping distance, which is the quantity every approach
# predicate makes a claim about; a unit mid-walk says nothing about where it
# meant to stop.
SETTLED_S = 0.6
MOVING_S = 0.35

# Frame stride for the occupancy tables (Section 1a). 10 Hz positions are far
# finer than any standoff statistic needs and the sweep is O(units x enemies).
OCC_STRIDE = 5


# ---------------------------------------------------------------------------
# per-frame army geometry, cached
# ---------------------------------------------------------------------------

class Geo:
    def __init__(self, fight, owners):
        self.f = fight
        self.owners = tuple(owners)
        self.ts = [t for t, _ in fight.frames]
        self._cent, self._rank, self._adepth = {}, {}, {}

    def idx(self, t):
        if not self.ts:
            return None
        i = bisect.bisect_left(self.ts, t)
        return min(max(i, 0), len(self.ts) - 1)

    def frame(self, i):
        return self.f.frames[i][1]

    def other(self, owner):
        return self.owners[0] if owner == self.owners[1] else self.owners[1]

    def cent(self, i, owner):
        k = (i, owner)
        if k not in self._cent:
            self._cent[k] = centroid(self.frame(i), owner)
        return self._cent[k]

    def _axis(self, i, owner):
        a, b = self.cent(i, owner), self.cent(i, self.other(owner))
        if a is None or b is None:
            return None, None
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0:
            return None, None
        return a, ((b[0] - a[0]) / L, (b[1] - a[1]) / L)

    def ranks(self, i, owner):
        k = (i, owner)
        if k in self._rank:
            return self._rank[k]
        ec = self.cent(i, self.other(owner))
        out = {}
        if ec is not None:
            mine = sorted((math.hypot(x - ec[0], y - ec[1]), uid)
                          for uid, (x, y, o, _h) in self.frame(i).items() if o == owner)
            out = {uid: n for n, (_d, uid) in enumerate(mine)}
        self._rank[k] = out
        return out

    def army_depth(self, i, owner):
        """(depth along the threat axis, front offset, width across it, n)."""
        k = (i, owner)
        if k in self._adepth:
            return self._adepth[k]
        c, u = self._axis(i, owner)
        out = (None, None, None, 0)
        if c is not None:
            pts = [(x, y) for _uid, (x, y, o, _h) in self.frame(i).items()
                   if o == owner]
            pr = [(x - c[0]) * u[0] + (y - c[1]) * u[1] for x, y in pts]
            pp = [-(x - c[0]) * u[1] + (y - c[1]) * u[0] for x, y in pts]
            if pr:
                out = (max(pr) - min(pr), max(pr), max(pp) - min(pp), len(pr))
        self._adepth[k] = out
        return out

    def nearest_enemy(self, i, owner):
        """[distance to nearest living enemy] for each living unit of `owner`."""
        fr = self.frame(i)
        mine = [(x, y) for (x, y, o, _h) in fr.values() if o == owner]
        foes = [(x, y) for (x, y, o, _h) in fr.values() if o != owner]
        if not mine or not foes:
            return None
        return [min(math.hypot(x - fx, y - fy) for fx, fy in foes) for (x, y) in mine]

    def enemy_dists(self, i, owner, ux, uy):
        fr = self.frame(i)
        return sorted(math.hypot(x - ux, y - uy)
                      for (x, y, o, _h) in fr.values() if o != owner)

    def in_reach_share(self, i, owner, reach):
        ne = self.nearest_enemy(i, owner)
        if not ne:
            return None
        return 100.0 * sum(1 for d in ne if d <= reach) / len(ne)

    def radial_speed(self, i, owner, dt_frames=5):
        j = max(0, i - dt_frames)
        if j == i:
            return None
        a0, a1 = self.cent(j, owner), self.cent(i, owner)
        _c, u = self._axis(j, owner)
        if a0 is None or a1 is None or u is None:
            return None
        dt = self.ts[i] - self.ts[j]
        if dt <= 0:
            return None
        return ((a1[0] - a0[0]) * u[0] + (a1[1] - a0[1]) * u[1]) / dt


# ---------------------------------------------------------------------------
# range predicates
# ---------------------------------------------------------------------------

def reach_variants(att, dfn):
    ar = att["attack_range"]
    ra = physics_radius_px(att) / TILE
    rb = physics_radius_px(dfn) / TILE
    buf = MELEE_RANGE_BUFFER_PX / TILE
    return {"C": ar, "SE": ar + ra, "TE": ar + rb, "EE": ar + ra + rb,
            "ENG": ar + buf + ra + rb,
            "r_self": ra, "r_target": rb, "buf": buf, "ar": ar}


# ---------------------------------------------------------------------------
# per-shot record
# ---------------------------------------------------------------------------

def shot_records(fight, meta, du, geo, seed=None):
    owners = [meta["side1"]["owner"], meta["side2"]["owner"]]
    rv = {o: reach_variants(du[o], du[geo.other(o)]) for o in owners}

    prev_tgt, prev_t, run_i = {}, {}, {}
    rows = []
    for s in sorted(fight.shots, key=lambda s: s["t"]):
        # TARGET IDENTITY. Engine: ground truth from the probe. Tape: the
        # damage pairing's victim when the shot landed (certain), else the
        # inferred aim target.
        certain = False
        tgt = s.get("true_target")
        if tgt is not None:
            certain = True
        elif s.get("hit") is not None:
            tgt, certain = s["hit"]["victim"], True
        else:
            tgt = s.get("aim")
        if tgt is None:
            continue
        t = s["t"]
        i = geo.idx(t)
        if i is None:
            continue
        ps, pt = fight.pos(s["shooter"], t), fight.pos(tgt, t)
        if ps is None or pt is None:
            continue
        d = math.hypot(pt[0] - ps[0], pt[1] - ps[1])
        o = s["owner"]
        R = rv[o]

        # nearest enemy to the SHOOTER at launch, and where the chosen target
        # sits in that ordering
        ed = geo.enemy_dists(i, o, ps[0], ps[1])
        d_near = ed[0] if ed else None
        t_rank = sum(1 for x in ed if x < d - 1e-9) if ed else None

        sh = s["shooter"]
        new_tgt = prev_tgt.get(sh) != tgt
        run_i[sh] = 0 if new_tgt else run_i.get(sh, 0) + 1
        gap = None if prev_t.get(sh) is None else t - prev_t[sh]
        prev_tgt[sh], prev_t[sh] = tgt, t

        ux, uy = ((pt[0] - ps[0]) / d, (pt[1] - ps[1]) / d) if d > 0 else (0.0, 0.0)
        mot = {}
        for w in (1.0, 2.0):
            t0 = max(0.0, t - w)
            p0 = fight.pos(tgt, t0)
            span = t - t0
            if p0 is None or span <= 0:
                mot[w] = (None, None)
                continue
            dx, dy = pt[0] - p0[0], pt[1] - p0[1]
            mot[w] = (math.hypot(dx, dy) / span, (dx * ux + dy * uy) / span)

        ranks = geo.ranks(i, o)
        rank = ranks.get(sh)
        nside = len(ranks)
        adepth, afront, awidth, _n = geo.army_depth(i, o)

        rows.append({
            "tag": fight.tag, "src": fight.source, "seed": seed, "t": t,
            "owner": o, "shooter": sh, "target": tgt, "certain": certain,
            "d": d, "depth": R["ENG"] - d, "reach": R["ENG"],
            "d_near": d_near,
            "depth_near": (R["ENG"] - d_near) if d_near is not None else None,
            "excess": (d - d_near) if d_near is not None else None,
            "t_rank": t_rank,
            "flight": s["dist"], "outcome": s.get("outcome"),
            "rank": rank, "n_side": nside,
            "army_depth": adepth, "army_front": afront, "army_width": awidth,
            "tv1": mot[1.0][0], "tvr1": mot[1.0][1],
            "tv2": mot[2.0][0], "tvr2": mot[2.0][1],
            "retarget": new_tgt, "run_i": run_i[sh], "gap": gap,
            "moving": fight.moved_between(sh, t - MOVING_S, t + 0.05),
            "settled": not fight.moved_between(sh, t - SETTLED_S, t + 0.05),
        })
    return rows, rv


def occupancy(fight, geo, owner, reach, stride=OCC_STRIDE):
    """reach - (distance to nearest living enemy), every `stride`-th frame."""
    out = []
    for i in range(0, len(fight.frames), stride):
        ne = geo.nearest_enemy(i, owner)
        if not ne:
            continue
        out.extend(reach - d for d in ne)
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def key_of(meta, owner):
    s = meta["side1"] if meta["side1"]["owner"] == owner else meta["side2"]
    return f"{owner}:{SHORT.get(s['slug'], s['slug'])}"


def tag_short(tag):
    a, b = tag.split("__vs__")
    return f"{SHORT.get(a, a)} v {SHORT.get(b, b)}"


def bucket(rows, keyfn, names):
    out = defaultdict(list)
    for x in rows:
        k = keyfn(x)
        if k is not None:
            out[k].append(x)
    return [(n, out.get(n, [])) for n in names]


def cell(b, key="depth"):
    return f"{r(med([x[key] for x in b]))} ({len(b)})" if b else "-"


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-runs-dir", default="D:/AI/aoe2_golden/shots_r5c")
    ap.add_argument("--tags", default=",".join(R5_TAGS))
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--section", default="all")
    ap.add_argument("--certain-only", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    sim_dir = Path(args.sim_runs_dir)
    manifest = json.loads((CALIB / "manifest.json").read_text())["fights"]
    dicts = json.loads((CALIB / "combat_dicts.json").read_text())
    want = args.tags.split(",")
    fights = [f for f in manifest if f["tag"] in want]
    fights.sort(key=lambda f: want.index(f["tag"]))
    sec, out, PER = args.section, {}, {}
    ALL = {"tape": [], "engine": []}
    order = [f["tag"] for f in fights]

    def sel(rows, o):
        return [x for x in rows
                if x["owner"] == o and (x["certain"] or not args.certain_only)]

    for meta in fights:
        tag = meta["tag"]
        owners = [meta["side1"]["owner"], meta["side2"]["owner"]]
        du = {s["owner"]: dicts[f"{s['civ']}|{s['slug']}"]
              for s in (meta["side1"], meta["side2"])}

        tape = load_tape(meta)
        gt = Geo(tape, owners)
        trows, rv = shot_records(tape, meta, du, gt)
        tocc = {o: occupancy(tape, gt, o, rv[o]["ENG"]) for o in owners}

        engines, erows, eocc = [], [], {o: [] for o in owners}
        for s in range(1, args.seeds + 1):
            e = load_engine(sim_dir, meta, s)
            if e is None:
                continue
            ge = Geo(e, owners)
            rr, _ = shot_records(e, meta, du, ge, seed=s)
            erows.extend(rr)
            for o in owners:
                eocc[o].extend(occupancy(e, ge, o, rv[o]["ENG"]))
            engines.append((s, e, ge))

        PER[tag] = {"meta": meta, "owners": owners, "du": du, "rv": rv,
                    "tape": tape, "geo": gt, "engines": engines,
                    "trows": trows, "erows": erows, "tocc": tocc, "eocc": eocc}
        ALL["tape"].extend(trows)
        ALL["engine"].extend(erows)
        print(f"# {tag}: tape {len(trows)} shots "
              f"({sum(1 for x in trows if x['certain'])} certain), "
              f"engine {len(erows)} shots / {len(engines)} seeds", file=sys.stderr)

    # ---- 0. reconciliation -------------------------------------------------
    if sec in ("all", "recon"):
        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                T = [x for x in P["trows"] if x["owner"] == o and x["certain"]]
                E = [x for x in P["erows"] if x["owner"] == o]
                if not T:
                    continue
                R = P["rv"][o]["ENG"]
                rows.append({
                    "fight": tag_short(tag), "side": key_of(P["meta"], o),
                    "reach": r(R), "n(T)": len(T),
                    "T flight p50": r(med([x["flight"] for x in T])),
                    "T range p50": r(med([x["d"] for x in T])),
                    "inset": r(med([x["d"] - x["flight"] for x in T])),
                    "T depth (flight)": r(R - med([x["flight"] for x in T])),
                    "T depth (true)": r(R - med([x["d"] for x in T])),
                    "E depth (true)": r(R - med([x["d"] for x in E])) if E else None,
                })
        table(rows, list(rows[0]),
              "0. RECONCILIATION -- the R5b premise used flight length, not range")
        out["recon"] = rows

    # ---- 0b. the anchor insets themselves ----------------------------------
    # The evidence that the launch/impact insets are geometry and not a
    # coordinate-frame skew between the units stream and the missiles stream:
    # decomposed onto the shot line, the PERPENDICULAR component of both is
    # zero. A constant frame offset would instead show a fixed WORLD vector,
    # whose perpendicular component swings with the firing direction.
    # Restricted to paired hits, so the victim is named by the damage stream
    # and no aim inference enters.
    if sec in ("all", "anchor"):
        rows = []
        for tag in order:
            P = PER[tag]
            f = P["tape"]
            for o in P["owners"]:
                lr, lp, ir, ip = [], [], [], []
                for s in f.shots:
                    if s["owner"] != o or s["hit"] is None:
                        continue
                    v = s["hit"]["victim"]
                    ps, pt = f.pos(s["shooter"], s["t"]), f.pos(v, s["t"])
                    pi = f.pos(v, s["impact_t"])
                    if ps is None or pt is None or pi is None:
                        continue
                    d = math.hypot(pt[0] - ps[0], pt[1] - ps[1])
                    if d <= 0:
                        continue
                    ux, uy = (pt[0] - ps[0]) / d, (pt[1] - ps[1]) / d
                    ox, oy = s["sx"] - ps[0], s["sy"] - ps[1]
                    jx, jy = s["ix"] - pi[0], s["iy"] - pi[1]
                    lr.append(ox * ux + oy * uy)
                    lp.append(-ox * uy + oy * ux)
                    ir.append(jx * ux + jy * uy)
                    ip.append(-jx * uy + jy * ux)
                if not lr:
                    continue
                rows.append({
                    "fight": tag_short(tag), "side": key_of(P["meta"], o),
                    "n": len(lr),
                    "launch radial": r(med(lr), 3),
                    "launch p10": r(q(lr, .1), 3), "launch p90": r(q(lr, .9), 3),
                    "launch PERP": r(med(lp), 3),
                    "impact radial": r(med(ir), 3),
                    "impact PERP": r(med(ip), 3),
                    "total inset": r(med(lr) - med(ir), 3),
                })
        table(rows, list(rows[0]),
              "0b. THE ANCHOR INSETS -- tape launch/impact offsets decomposed "
              "onto the shot line (tiles, paired hits only). PERP == 0 means "
              "these are insets along the shot, not a frame skew.")
        out["anchor"] = rows

    # ---- 1. standoff -------------------------------------------------------
    if sec in ("all", "standoff"):
        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                T, E = P["tocc"][o], P["eocc"][o]
                rows.append({
                    "fight": tag_short(tag), "side": key_of(P["meta"], o),
                    "reach": r(P["rv"][o]["ENG"]), "2r": r(2 * P["rv"][o]["r_self"]),
                    "T n": len(T), "T p25": r(q(T, .25)), "T p50": r(med(T)),
                    "T p75": r(q(T, .75)), "T p90": r(q(T, .90)),
                    "T in%": r(pct(sum(1 for x in T if x >= 0), len(T)), 0),
                    "E n": len(E), "E p25": r(q(E, .25)), "E p50": r(med(E)),
                    "E p75": r(q(E, .75)), "E p90": r(q(E, .90)),
                    "E in%": r(pct(sum(1 for x in E if x >= 0), len(E)), 0),
                    "T-E p50": r(med(T) - med(E)),
                })
        table(rows, list(rows[0]),
              "1a. STANDOFF OCCUPANCY -- reach - dist(nearest living enemy), "
              "every unit-frame (stride 0.5 s), tiles")
        out["standoff"] = rows

        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                T, E = sel(P["trows"], o), sel(P["erows"], o)
                Ts = [x for x in T if x["settled"]]
                Es = [x for x in E if x["settled"]]
                rows.append({
                    "fight": tag_short(tag), "side": key_of(P["meta"], o),
                    "reach": r(P["rv"][o]["ENG"]),
                    "T n": len(T), "T p10": r(q([x["depth"] for x in T], .1)),
                    "T p50": r(med([x["depth"] for x in T])),
                    "T p90": r(q([x["depth"] for x in T], .9)),
                    "T sd": r(statistics.pstdev([x["depth"] for x in T])) if len(T) > 1 else None,
                    "T settled p50": r(med([x["depth"] for x in Ts])) if Ts else None,
                    "E n": len(E), "E p10": r(q([x["depth"] for x in E], .1)),
                    "E p50": r(med([x["depth"] for x in E])),
                    "E p90": r(q([x["depth"] for x in E], .9)),
                    "E sd": r(statistics.pstdev([x["depth"] for x in E])) if len(E) > 1 else None,
                    "E settled p50": r(med([x["depth"] for x in Es])) if Es else None,
                    "T-E p50": r(med([x["depth"] for x in T]) - med([x["depth"] for x in E])),
                })
        table(rows, list(rows[0]),
              "1b. LAUNCH DEPTH -- reach - dist(the unit actually fired at), tiles")
        out["launch_depth"] = rows

    # ---- 2. H4 predicate ---------------------------------------------------
    if sec in ("all", "predicate"):
        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                R = P["rv"][o]
                T = [x["d"] for x in P["trows"] if x["owner"] == o and x["certain"]]
                E = [x["d"] for x in P["erows"] if x["owner"] == o]
                if not T:
                    continue
                pcT = lambda k: r(pct(sum(1 for d in T if d > R[k] + 1e-9), len(T)), 1)
                rows.append({
                    "fight": tag_short(tag), "side": key_of(P["meta"], o),
                    "C": r(R["C"]), "SE": r(R["SE"]), "TE": r(R["TE"]),
                    "EE": r(R["EE"]), "ENG": r(R["ENG"]),
                    "n": len(T), "p50": r(med(T)), "p90": r(q(T, .9)),
                    "p99": r(q(T, .99)), "max": r(max(T)),
                    ">C%": pcT("C"), ">SE%": pcT("SE"), ">TE%": pcT("TE"),
                    ">EE%": pcT("EE"), ">ENG%": pcT("ENG"),
                    "E max": r(max(E)) if E else None,
                })
        table(rows, list(rows[0]),
              "2. H4 -- tape stopping distribution vs the four range predicates "
              "(certain-victim shots)")
        out["predicate"] = rows

    # ---- 3. H1 rank --------------------------------------------------------
    if sec in ("all", "rank"):
        names = ["0", "1-2", "3-5", "6+"]
        rk = lambda x: (None if x["rank"] is None else
                        names[0] if x["rank"] == 0 else names[1] if x["rank"] <= 2
                        else names[2] if x["rank"] <= 5 else names[3])
        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o)}
                for src, rr in (("T", sel(P["trows"], o)), ("E", sel(P["erows"], o))):
                    for n, b in bucket(rr, rk, names):
                        row[f"{src} r{n}"] = cell(b)
                rows.append(row)
        table(rows, list(rows[0]),
              "3a. H1 -- median launch DEPTH by shooter rank (0 = frontmost) (n)")
        out["rank"] = rows

        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o),
                       "reach": r(P["rv"][o]["ENG"])}
                for src, rr in (("T", sel(P["trows"], o)), ("E", sel(P["erows"], o))):
                    fr0 = [x["depth"] for x in rr if x["rank"] == 0]
                    bk = [x["depth"] for x in rr if x["rank"] is not None
                          and x["n_side"] > 2 and x["rank"] >= x["n_side"] - 2]
                    ad = [x["army_depth"] for x in rr if x["army_depth"] is not None]
                    row[f"{src} armydep"] = r(med(ad)) if ad else None
                    row[f"{src} front"] = r(med(fr0)) if fr0 else None
                    row[f"{src} rear"] = r(med(bk)) if bk else None
                    row[f"{src} f-r"] = r(med(fr0) - med(bk)) if fr0 and bk else None
                rows.append(row)
        table(rows, list(rows[0]),
              "3b. H1 -- army depth along the threat axis vs front/rear launch depth")
        out["army_depth"] = rows

        # 3c: is the tape's extra burial CLOSURE (the whole army walks in) or
        # SPREAD (the army fans out so its leading units are far ahead of its
        # centroid)? Measured on positions only, over the last third.
        def shape(f, g, o):
            nf = len(f.frames)
            dep, wid, sp = [], [], []
            for i in range(2 * nf // 3, nf, OCC_STRIDE):
                d, _fr, w, n = g.army_depth(i, o)
                if d is None or n < 2:
                    continue
                dep.append(d)
                wid.append(w)
                c0, c1 = g.cent(i, o), g.cent(i, g.other(o))
                if c0 and c1:
                    sp.append(math.hypot(c0[0] - c1[0], c0[1] - c1[1]))
            return dep, wid, sp

        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o),
                       "reach": r(P["rv"][o]["ENG"])}
                d, w, s = shape(P["tape"], P["geo"], o)
                row.update({"T sep": r(med(s)) if s else None,
                            "T depth": r(med(d)) if d else None,
                            "T width": r(med(w)) if w else None})
                ad, aw, asp = [], [], []
                for _s, e, g in P["engines"]:
                    d2, w2, s2 = shape(e, g, o)
                    ad += d2
                    aw += w2
                    asp += s2
                row.update({"E sep": r(med(asp)) if asp else None,
                            "E depth": r(med(ad)) if ad else None,
                            "E width": r(med(aw)) if aw else None})
                row["sep T-E"] = (r(row["T sep"] - row["E sep"])
                                  if row["T sep"] is not None and row["E sep"] is not None else None)
                row["depth T-E"] = (r(row["T depth"] - row["E depth"])
                                    if row["T depth"] is not None and row["E depth"] is not None else None)
                rows.append(row)
        table(rows, list(rows[0]),
              "3c. H1 -- army SHAPE over the last third: inter-centroid "
              "separation vs the army's own depth (along the threat axis) and "
              "width (across it), tiles")
        out["army_shape"] = rows

    # ---- 4. H2 target motion ----------------------------------------------
    if sec in ("all", "motion"):
        names = ["still", "lateral", "fleeing", "closing"]

        def mv(x):
            v, rr = x["tv1"], x["tvr1"]
            if v is None or rr is None:
                return None
            if v <= 0.05:
                return "still"
            return "fleeing" if rr > 0.15 else "closing" if rr < -0.15 else "lateral"

        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o)}
                for src, rr in (("T", sel(P["trows"], o)), ("E", sel(P["erows"], o))):
                    for n, b in bucket(rr, mv, names):
                        row[f"{src} {n}"] = cell(b)
                rows.append(row)
        table(rows, list(rows[0]),
              "4a. H2 -- median launch DEPTH by the TARGET's motion over the "
              "preceding 1 s (n)")
        out["motion"] = rows

        rows = []
        for src in ("tape", "engine"):
            pool = [x for x in ALL[src] if x["certain"] or not args.certain_only]
            for lo, hi, nm in ((None, .05, "|v| <= 0.05"), (.05, .4, "0.05-0.4"),
                               (.4, .9, "0.4-0.9"), (.9, None, "> 0.9")):
                b = [x for x in pool if x["tv1"] is not None
                     and (lo is None or x["tv1"] > lo)
                     and (hi is None or x["tv1"] <= hi)]
                rows.append({"src": src, "target |v| tiles/s": nm, "n": len(b),
                             "depth p50": r(med([x["depth"] for x in b])) if b else None,
                             "depth p90": r(q([x["depth"] for x in b], .9)) if b else None})
            for lo, hi, nm in ((None, -.3, "radial < -0.3 (closing)"),
                               (-.3, .3, "-0.3..0.3"), (.3, None, "> 0.3 (fleeing)")):
                b = [x for x in pool if x["tvr1"] is not None
                     and (lo is None or x["tvr1"] > lo)
                     and (hi is None or x["tvr1"] <= hi)]
                rows.append({"src": src, "target |v| tiles/s": nm, "n": len(b),
                             "depth p50": r(med([x["depth"] for x in b])) if b else None,
                             "depth p90": r(q([x["depth"] for x in b], .9)) if b else None})
        table(rows, list(rows[0]),
              "4b. H2 -- pooled depth vs target speed and radial velocity "
              "(all six fights, both sides)")
        out["motion_pooled"] = rows

    # ---- 5. H3 re-approach -------------------------------------------------
    if sec in ("all", "retarget"):
        names = ["1st", "2nd", "3rd", "4th+"]
        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o)}
                for src, rr in (("T", sel(P["trows"], o)), ("E", sel(P["erows"], o))):
                    for n, b in bucket(rr, lambda x: names[min(x["run_i"], 3)], names):
                        row[f"{src} {n}"] = cell(b)
                rows.append(row)
        table(rows, list(rows[0]),
              "5a. H3 -- median launch DEPTH by shot index since retarget (n)")
        out["retarget"] = rows

        rows = []
        for src in ("tape", "engine"):
            pool = [x for x in ALL[src] if x["certain"] or not args.certain_only]
            for lo, hi, nm in ((None, None, "first launch of the unit"),
                               (0, 2.5, "gap <= 2.5 s"), (2.5, 5.0, "gap 2.5-5 s"),
                               (5.0, None, "gap > 5 s")):
                if hi is None and lo is None:
                    b = [x for x in pool if x["gap"] is None]
                else:
                    b = [x for x in pool if x["gap"] is not None
                         and (lo is None or x["gap"] > lo)
                         and (hi is None or x["gap"] <= hi)]
                rows.append({"src": src, "bucket": nm, "n": len(b),
                             "depth p50": r(med([x["depth"] for x in b])) if b else None,
                             "moving%": r(pct(sum(1 for x in b if x["moving"]), len(b)), 0) if b else None})
        table(rows, list(rows[0]),
              "5b. H3 -- pooled depth vs the shooter's own launch gap")
        out["retarget_pooled"] = rows

    # ---- 6. H5 HCA v HC timeline ------------------------------------------
    if sec in ("all", "timeline"):
        tag = "heavy_cav_archer__vs__hand_cannoneer"
        if tag in PER:
            P = PER[tag]
            owners = P["owners"]
            reach = {o: P["rv"][o]["ENG"] for o in owners}
            srcs = [("T", P["tape"], P["geo"], P["trows"])]
            if P["engines"]:
                mid = sorted(P["engines"], key=lambda x: x[1].duration_s)[len(P["engines"]) // 2]
                srcs.append(("E", mid[1], mid[2],
                             [x for x in P["erows"] if x["seed"] == mid[0]]))
            nm = {o: SHORT.get((P["meta"]["side1"] if P["meta"]["side1"]["owner"] == o
                                else P["meta"]["side2"])["slug"], str(o)) for o in owners}
            rows = []
            for label, f, g, rr in srcs:
                T, nb = f.duration_s, 30
                for b in range(nb):
                    t0, t1 = T * b / nb, T * (b + 1) / nb
                    i = (g.idx(t0) + g.idx(t1)) // 2
                    row = {"src": label, "t": r((t0 + t1) / 2, 1)}
                    c0, c1 = g.cent(i, owners[0]), g.cent(i, owners[1])
                    row["sep"] = (r(math.hypot(c0[0] - c1[0], c0[1] - c1[1]))
                                  if c0 and c1 else None)
                    for o in owners:
                        k, fr = nm[o], g.frame(i)
                        alive = sum(1 for (_x, _y, oo, _h) in fr.values() if oo == o)
                        ne = g.nearest_enemy(i, o)
                        sh = [x for x in rr if x["owner"] == o and t0 <= x["t"] < t1]
                        row[f"{k} n"] = alive
                        row[f"{k} dmin"] = r(min(ne)) if ne else None
                        row[f"{k} dmed"] = r(med(ne)) if ne else None
                        row[f"{k} rch%"] = r(g.in_reach_share(i, o, reach[o]), 0)
                        row[f"{k} rad"] = r(g.radial_speed(i, o), 2)
                        row[f"{k} sh/us"] = r(len(sh) / (max(1, alive) * max(1e-6, t1 - t0)), 3)
                        row[f"{k} dep"] = r(med([x["depth"] for x in sh])) if sh else None
                    rows.append(row)
            table(rows, list(rows[0]),
                  "6a. H5 -- heavy_cav_archer vs hand_cannoneer closure timeline "
                  "(30 buckets; T = tape, E = median-duration engine seed). "
                  "dmin/dmed = distance to nearest enemy; rad = centroid radial "
                  "speed (+ closing); sh/us = launches per living-unit-second")
            out["timeline"] = rows

            rows = []
            for label, f, g, rr in srcs:
                for o in owners:
                    t_in = next((t for i, (t, _fr) in enumerate(f.frames)
                                 if (lambda ne: ne and min(ne) <= reach[o])(g.nearest_enemy(i, o))),
                                None)
                    t_all = next((t for i, (t, _fr) in enumerate(f.frames)
                                  if (g.in_reach_share(i, o, reach[o]) or 0) >= 90.0), None)
                    rows.append({
                        "src": label, "side": key_of(P["meta"], o),
                        "reach": r(reach[o]),
                        "t first unit in reach": r(t_in, 2),
                        "t 90% of side in reach": r(t_all, 2),
                        "t first launch": r(min((x["t"] for x in rr if x["owner"] == o),
                                                default=None), 2),
                        "wipe": r(f.duration_s),
                    })
            table(rows, list(rows[0]), "6b. H5 -- who crosses into reach first")
            out["timeline_entry"] = rows

    # ---- 7. target choice --------------------------------------------------
    if sec in ("all", "choice"):
        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o)}
                for src, rr in (("T", sel(P["trows"], o)), ("E", sel(P["erows"], o))):
                    ex = [x["excess"] for x in rr if x["excess"] is not None]
                    tr = [x["t_rank"] for x in rr if x["t_rank"] is not None]
                    dn = [x["depth_near"] for x in rr if x["depth_near"] is not None]
                    row[f"{src} n"] = len(rr)
                    row[f"{src} excess p50"] = r(med(ex)) if ex else None
                    row[f"{src} excess p90"] = r(q(ex, .9)) if ex else None
                    row[f"{src} nearest%"] = r(pct(sum(1 for x in tr if x == 0), len(tr)), 0) if tr else None
                    row[f"{src} depth(near) p50"] = r(med(dn)) if dn else None
                rows.append(row)
        table(rows, list(rows[0]),
              "7. TARGET CHOICE -- how much further than the nearest enemy the "
              "chosen target was, at launch")
        out["choice"] = rows

    # ---- 8. closure budget -------------------------------------------------
    # A one-shot approach margin and a sustained walk-in look the same in a
    # median and different here: does the side keep closing all fight, and does
    # its standoff keep deepening?
    if sec in ("all", "closure"):
        def budget(f, g, o):
            close = hold = back = n = 0
            net = 0.0
            for i in range(1, len(f.frames)):
                v = g.radial_speed(i, o, dt_frames=1)
                if v is None:
                    continue
                n += 1
                dt = g.ts[i] - g.ts[i - 1]
                net += v * dt
                if v > 0.05:
                    close += 1
                elif v < -0.05:
                    back += 1
                else:
                    hold += 1
            if not n:
                return None
            return (net, 100.0 * close / n, 100.0 * hold / n, 100.0 * back / n)

        def thirds(f, g, o, reach):
            nf = len(f.frames)
            out = []
            for a, b in ((0, nf // 3), (nf // 3, 2 * nf // 3), (2 * nf // 3, nf)):
                v = []
                for i in range(a, b, OCC_STRIDE):
                    ne = g.nearest_enemy(i, o)
                    if ne:
                        v.extend(reach - d for d in ne)
                out.append(med(v) if v else None)
            return out

        rows = []
        for tag in order:
            P = PER[tag]
            for o in P["owners"]:
                reach = P["rv"][o]["ENG"]
                row = {"fight": tag_short(tag), "side": key_of(P["meta"], o)}
                tb = budget(P["tape"], P["geo"], o)
                tt = thirds(P["tape"], P["geo"], o, reach)
                row.update({"T net": r(tb[0]) if tb else None,
                            "T close%": r(tb[1], 0) if tb else None,
                            "T hold%": r(tb[2], 0) if tb else None,
                            "T back%": r(tb[3], 0) if tb else None,
                            "T d1": r(tt[0]), "T d2": r(tt[1]), "T d3": r(tt[2])})
                eb = [budget(e, g, o) for _s, e, g in P["engines"]]
                eb = [x for x in eb if x]
                et = [thirds(e, g, o, reach) for _s, e, g in P["engines"]]
                avg = lambda k: (r(statistics.mean([x[k] for x in eb]),
                                   0 if k else 2) if eb else None)
                row.update({"E net": avg(0), "E close%": avg(1),
                            "E hold%": avg(2), "E back%": avg(3)})
                for j, nm in enumerate(("E d1", "E d2", "E d3")):
                    v = [x[j] for x in et if x[j] is not None]
                    row[nm] = r(statistics.mean(v)) if v else None
                rows.append(row)
        table(rows, list(rows[0]),
              "8. CLOSURE BUDGET -- 'net' = cumulative centroid displacement "
              "toward the enemy over the whole fight (tiles, + = closed in); "
              "close/hold/back% = share of 0.1 s steps with radial speed "
              "above +0.05 / within +-0.05 / below -0.05 tiles/s; "
              "d1/d2/d3 = median standoff depth in the first/middle/last third")
        out["closure"] = rows

    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
