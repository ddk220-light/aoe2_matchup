"""Phase B measurement report: WHERE and WHY the engine's outnumbered melee
side stops swinging.

Six measurements, all over ASYMMETRIC (count ratio >= 1.4) melee-vs-melee
fights. Sections 1, 3 and 4 are computed by ONE implementation fed either a
recording or an engine run, so every tape/engine pair is directly comparable.
Sections 2 and 5 are engine internals and come from
tools/simjs/melee_engagement_probe.mjs.

    node tools/simjs/calib_runner.mjs --tags <T> --seeds 20 --out-dir <clean>
    node tools/simjs/melee_engagement_probe.mjs --tags <T> --seeds 20 \
         --pos-seeds 5 --out-dir <probe> --verify <clean>
    python tools/simjs/melee_engagement_report.py --probe-dir <probe>

WHICH TAPES. The v2 melee corpus (drop aoe2_golden_melee_v2_palsteppe12.zip)
has a DEAD position channel -- every unit reports its spawn tile for the whole
recording (docs/calibration/v2_melee_rebaseline.md §1b). Sections 1, 3 and 4
therefore run on the OLD corpus only, where positions are live (89-208 distinct
positions per unit). Section 6 is the v2 cross-check and uses damage streams
alone, which are sound on both corpora. The six quarantined
paladin__vs__elite_steppe originals are dropped by loadManifest/filters and
never reach this script.
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
    load_manifest, load_dicts, tape_damage, TAPES, engine_reach, MELEE_SLUGS,
)

# The v2 doc's §6c concurrency window, reused verbatim so this report's numbers
# are checkable against the ones it is following up.
CONC_WINDOW_S = 2.5
V2_DROP = "aoe2_golden_melee_v2_palsteppe12.zip"
ASYM_MIN_RATIO = 1.4


# ---------------------------------------------------------------------------
# fight selection
# ---------------------------------------------------------------------------

def asymmetric_melee(fights):
    """(old_corpus, v2_corpus) asymmetric melee-vs-melee fights."""
    old, v2 = [], []
    for f in fights:
        s1, s2 = f["side1"], f["side2"]
        if s1["slug"] not in MELEE_SLUGS or s2["slug"] not in MELEE_SLUGS:
            continue
        if f.get("quarantined"):
            continue
        r = max(s1["count"], s2["count"]) / min(s1["count"], s2["count"])
        if r < ASYM_MIN_RATIO:
            continue
        (v2 if V2_DROP in f["drop"] else old).append(f)
    return old, v2


def sides_of(fight):
    """(outnumbered_side, superior_side) by start count."""
    s1, s2 = fight["side1"], fight["side2"]
    return (s1, s2) if s1["count"] < s2["count"] else (s2, s1)


def family(fight):
    return fight["matchup"]


# ---------------------------------------------------------------------------
# loading -- tape and engine, into the SAME two shapes
# ---------------------------------------------------------------------------

def tape_frames(tag):
    """[(t, {id: (x_tiles, y_tiles, owner, hp)})], time-sorted, 10 Hz."""
    frames = {}
    with gzip.open(TAPES / tag / f"{tag}.units.jsonl.gz", "rt") as fh:
        for line in fh:
            r = json.loads(line)
            frames.setdefault(round(r["t"], 3), {})[r["id"]] = (
                r["x"], r["y"], r["owner"], r.get("hp"))
    return sorted(frames.items())


def probe_record(probe_dir, run_id, seed):
    p = probe_dir / run_id / f"seed-{seed}.probe.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def probe_frames(probe_dir, run_id, seed):
    p = probe_dir / run_id / f"seed-{seed}.units.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [(f["t"], {u[0]: (u[1], u[2], u[3], u[4]) for u in f["u"]})
            for f in raw["frames"]]


def frame_at(frames, times, t):
    i = bisect.bisect_left(times, t)
    return frames[min(max(i, 0), len(frames) - 1)][1]


# ---------------------------------------------------------------------------
# 1. concurrent-swinger timeline
# ---------------------------------------------------------------------------

def engagement_stats(events, owner, start_count, window=CONC_WINDOW_S):
    """Decompose concurrency into the two things it multiplies together.

        concurrency = (living bodies) x (share of them swinging)

    Both factors come out of the damage stream alone -- deaths from `kill`
    events, swingers from attacker ids -- so this works on the v2 corpus too,
    where positions are dead. Without the split, "the engine gets fewer bodies
    swinging" is ambiguous between "its units die faster" and "its living units
    decline available fights", and those want opposite fixes.
    """
    hits = sorted((e["t"], e["attacker"]) for e in events
                  if e.get("attacker_owner") == owner)
    if not hits:
        return None
    wipe = max(e["t"] for e in events)
    if wipe <= 0:
        return None
    deaths = sorted(e["t"] for e in events
                    if e.get("kill") and e.get("victim_owner") == owner)
    ts = [h[0] for h in hits]
    conc, alive, share = [], [], []
    t = 0.0
    while t <= wipe:
        lo = bisect.bisect_left(ts, t - window)
        hi = bisect.bisect_right(ts, t)
        n = len({hits[i][1] for i in range(lo, hi)})
        a = start_count - bisect.bisect_right(deaths, t)
        conc.append(n)
        alive.append(a)
        if a > 0:
            share.append(n / a)
        t += 0.25
    return {
        "conc": statistics.mean(conc),
        "alive": statistics.mean(alive),
        "share": statistics.mean(share) if share else None,
        "wipe": wipe,
    }


def concurrency_curve(events, owner, nbins=10, window=CONC_WINDOW_S):
    """Distinct units of `owner` landing a hit inside a trailing `window`,
    sampled every 0.25 s over the fight and averaged per decile of NORMALISED
    fight time. Fight length is the stream's own last damage event -- the truth
    cards' duration_s is recorder segment length and runs ~1.6x long
    (v2_melee_rebaseline.md §5).

    Returns (per_bin_means, overall_mean) or (None, None) with no events.
    """
    hits = sorted((e["t"], e["attacker"]) for e in events
                  if e.get("attacker_owner") == owner)
    if not hits:
        return None, None
    wipe = max(e["t"] for e in events)
    if wipe <= 0:
        return None, None
    ts = [h[0] for h in hits]
    bins = [[] for _ in range(nbins)]
    allv = []
    step = 0.25
    t = 0.0
    while t <= wipe:
        lo = bisect.bisect_left(ts, t - window)
        hi = bisect.bisect_right(ts, t)
        n = len({hits[i][1] for i in range(lo, hi)})
        b = min(nbins - 1, int(nbins * t / wipe))
        bins[b].append(n)
        allv.append(n)
        t += step
    return ([statistics.mean(v) if v else None for v in bins],
            statistics.mean(allv))


# ---------------------------------------------------------------------------
# 3. retarget latency + attackers-per-victim (positions; tape or engine)
# ---------------------------------------------------------------------------

def retarget_latency(events, frames, owner, foe_owner, reach_self, reach_foe):
    """Effective retarget latency, inferred from the damage stream alone.

    A unit's LOCK at time t is the victim of its most recent landed hit. An
    OPPORTUNITY begins on the first 10 Hz frame at which that lock is alive but
    outside the unit's reach while some OTHER living enemy is inside it. The
    latency is the time from that frame to the unit's next landed hit, on
    anybody. Episodes whose unit never hits again (it died, or the fight ended)
    are censored, not counted as zero, and are reported separately.

    `reach_self` is this side's reach onto a foe body; `reach_foe` is unused
    here but kept in the signature so the caller passes the pair explicitly.
    """
    del reach_foe
    by_attacker = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            by_attacker[e["attacker"]].append((e["t"], e["victim"]))
    for v in by_attacker.values():
        v.sort()
    death_t = {}
    for e in sorted(events, key=lambda e: e["t"]):
        if e.get("kill"):
            death_t.setdefault(e["victim"], e["t"])

    times = [f[0] for f in frames]
    lats, censored, episodes = [], 0, 0
    for uid, hits in by_attacker.items():
        hts = [h[0] for h in hits]
        inside = False
        for ft, fr in frames:
            if ft < hts[0]:
                continue
            me = fr.get(uid)
            if me is None:
                break
            i = bisect.bisect_right(hts, ft) - 1
            if i < 0:
                continue
            lock = hits[i][1]
            lv = fr.get(lock)
            d_lock = death_t.get(lock)
            if lv is None or (d_lock is not None and d_lock <= ft):
                inside = False
                continue
            dl = ((me[0] - lv[0]) ** 2 + (me[1] - lv[1]) ** 2) ** 0.5
            if dl <= reach_self:
                inside = False
                continue
            other = False
            for oid, o in fr.items():
                if oid == lock or o[2] != foe_owner:
                    continue
                if o[3] is not None and o[3] <= 0:
                    continue
                if ((me[0] - o[0]) ** 2 + (me[1] - o[1]) ** 2) ** 0.5 <= reach_self:
                    other = True
                    break
            if not other:
                inside = False
                continue
            if inside:
                continue
            inside = True
            episodes += 1
            j = bisect.bisect_right(hts, ft)
            if j < len(hts):
                lats.append(hts[j] - ft)
            else:
                censored += 1
    del times
    return lats, censored, episodes


def attackers_per_victim_geom(frames, victim_owner, foe_owner, reach_foe):
    """At each 10 Hz frame, for each living unit of `victim_owner`: how many
    living enemies are inside THEIR reach of it. Pure geometry -- no target
    field is needed, so a recording and an engine run answer identically.
    """
    counts = []
    for _, fr in frames:
        for vid, v in fr.items():
            if v[2] != victim_owner:
                continue
            if v[3] is not None and v[3] <= 0:
                continue
            n = 0
            for aid, a in fr.items():
                if aid == vid or a[2] != foe_owner:
                    continue
                if a[3] is not None and a[3] <= 0:
                    continue
                if ((a[0] - v[0]) ** 2 + (a[1] - v[1]) ** 2) ** 0.5 <= reach_foe:
                    n += 1
            counts.append(n)
    return counts


def attackers_per_victim_dmg(events, attacker_owner, reload_s):
    """Distinct attackers of `attacker_owner` landing a hit on the same victim
    inside a trailing reload window. Damage-stream only, so it also works on
    the v2 corpus.
    """
    by_victim = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == attacker_owner:
            by_victim[e["victim"]].append(e)
    out = []
    for hits in by_victim.values():
        hits.sort(key=lambda e: e["t"])
        for i, e in enumerate(hits):
            lo = e["t"] - reload_s
            out.append(len({h["attacker"] for h in hits[:i + 1] if h["t"] >= lo}))
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def q(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    i = p * (len(s) - 1)
    lo = int(i)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def fmt(v, d=2):
    return "-" if v is None else f"{v:.{d}f}"


def ratio(sim, tape):
    if tape in (None, 0) or sim is None:
        return None
    return sim / tape


def merge_samples(entries):
    """Pool a list of probe `summariseSamples` dicts into one weighted mean and
    an n-weighted percentile approximation (the medians/p90s are averaged with
    n as the weight -- exact percentiles would need the raw samples, which the
    probe deliberately does not keep).
    """
    tot = sum(e.get("n", 0) for e in entries)
    if not tot:
        return {"n": 0}
    def w(key):
        s = sum(e[key] * e["n"] for e in entries
                if e.get("n") and e.get(key) is not None)
        d = sum(e["n"] for e in entries if e.get("n") and e.get(key) is not None)
        return s / d if d else None
    return {
        "n": tot, "mean": w("mean"), "median": w("median"),
        "p90": w("p90"),
        "max": max((e["max"] for e in entries if e.get("n")), default=None),
    }


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe-dir", type=Path, required=True)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--pos-seeds", type=int, default=5)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    dicts = load_dicts()
    old, v2 = asymmetric_melee(load_manifest())
    out = {}

    print(f"asymmetric melee (ratio >= {ASYM_MIN_RATIO}x): "
          f"{len(old)} old-corpus fights (live positions), "
          f"{len(v2)} v2 fights (damage only)\n")

    # ---- per-fight, per-side collection -----------------------------------
    # keyed (family, role) where role is "out" (outnumbered) or "sup"
    curves = defaultdict(lambda: {"tape": [], "sim": []})
    overall = defaultdict(lambda: {"tape": [], "sim": []})
    lat = defaultdict(lambda: {"tape": [], "sim": []})
    latcens = defaultdict(lambda: {"tape": [0, 0], "sim": [0, 0]})
    apv_geom = defaultdict(lambda: {"tape": [], "sim": []})
    apv_dmg = defaultdict(lambda: {"tape": [], "sim": []})
    decomp = defaultdict(lambda: {"tape": [], "sim": []})
    probe_side = defaultdict(list)      # role -> [side probe dicts]
    probe_fam = defaultdict(list)       # (family, role) -> [side probe dicts]

    for fight in old:
        tag, run_id = fight["tag"], fight["run_id"]
        low, high = sides_of(fight)
        try:
            tev = tape_damage(tag)
        except FileNotFoundError:
            continue
        tfr = None
        fam = family(fight)

        for side, foe, role in ((low, high, "out"), (high, low, "sup")):
            a = dicts[f"{side['civ']}|{side['slug']}"]
            b = dicts[f"{foe['civ']}|{foe['slug']}"]
            reach_self = engine_reach(a, b)
            reach_foe = engine_reach(b, a)
            reload_s = 1.0 / a["attack_speed"]
            reload_foe = 1.0 / b["attack_speed"]

            c, m = concurrency_curve(tev, side["owner"])
            if c:
                curves[(fam, role)]["tape"].append(c)
                overall[role]["tape"].append((m, side["count"]))
                overall[(fam, role)]["tape"].append((m, side["count"]))
            es = engagement_stats(tev, side["owner"], side["count"])
            if es:
                decomp[(fam, role)]["tape"].append(es)
                decomp[role]["tape"].append(es)

            # engine: every seed for the damage-only metrics
            sims_c, sims_m, sims_e = [], [], []
            for seed in range(1, args.seeds + 1):
                rec = probe_record(args.probe_dir, run_id, seed)
                if rec is None:
                    continue
                c2, m2 = concurrency_curve(rec["damage"], side["owner"])
                if c2:
                    sims_c.append(c2)
                    sims_m.append(m2)
                es2 = engagement_stats(rec["damage"], side["owner"], side["count"])
                if es2:
                    sims_e.append(es2)
                sp = rec["probe"].get(str(side["owner"]))
                if sp:
                    probe_side[role].append(sp)
                    probe_fam[(fam, role)].append(sp)
                apv_dmg[(fam, role)]["sim"] += attackers_per_victim_dmg(
                    rec["damage"], foe["owner"], reload_foe)
            if sims_c:
                nb = len(sims_c[0])
                curves[(fam, role)]["sim"].append(
                    [statistics.mean([s[i] for s in sims_c if s[i] is not None])
                     if any(s[i] is not None for s in sims_c) else None
                     for i in range(nb)])
                overall[role]["sim"].append(
                    (statistics.mean(sims_m), side["count"]))
                overall[(fam, role)]["sim"].append(
                    (statistics.mean(sims_m), side["count"]))
            if sims_e:
                avg = {k: statistics.mean([e[k] for e in sims_e if e[k] is not None])
                       for k in ("conc", "alive", "share", "wipe")}
                decomp[(fam, role)]["sim"].append(avg)
                decomp[role]["sim"].append(avg)

            apv_dmg[(fam, role)]["tape"] += attackers_per_victim_dmg(
                tev, foe["owner"], reload_foe)

            # position-based metrics
            if tfr is None:
                tfr = tape_frames(tag)
            l, cn, ep = retarget_latency(tev, tfr, side["owner"], foe["owner"],
                                         reach_self, reach_foe)
            lat[(fam, role)]["tape"] += l
            latcens[(fam, role)]["tape"][0] += cn
            latcens[(fam, role)]["tape"][1] += ep
            apv_geom[(fam, role)]["tape"] += attackers_per_victim_geom(
                tfr, side["owner"], foe["owner"], reach_foe)

            for seed in range(1, args.pos_seeds + 1):
                sfr = probe_frames(args.probe_dir, run_id, seed)
                rec = probe_record(args.probe_dir, run_id, seed)
                if sfr is None or rec is None:
                    continue
                l, cn, ep = retarget_latency(
                    rec["damage"], sfr, side["owner"], foe["owner"],
                    reach_self, reach_foe)
                lat[(fam, role)]["sim"] += l
                latcens[(fam, role)]["sim"][0] += cn
                latcens[(fam, role)]["sim"][1] += ep
                apv_geom[(fam, role)]["sim"] += attackers_per_victim_geom(
                    sfr, side["owner"], foe["owner"], reach_foe)
            del reload_s

    fams = sorted({k[0] for k in curves})

    # =======================================================================
    # 1. concurrent-swinger timeline
    # =======================================================================
    print("=" * 78)
    print("1. CONCURRENT-SWINGER TIMELINE — distinct units landing a hit inside a")
    print(f"   {CONC_WINDOW_S:.1f}s trailing window, by decile of normalised fight time.")
    print("   tape = the recording(s); eng = mean over 20 seeds.")
    print("=" * 78)
    for role, label in (("out", "OUTNUMBERED"), ("sup", "SUPERIOR")):
        print(f"\n--- {label} side ---")
        print(f"{'family':38s} {'n':>2s} " +
              " ".join(f"d{i + 1:<4d}" for i in range(10)) + "  overall")
        for fam in fams:
            tc = curves[(fam, role)]["tape"]
            sc = curves[(fam, role)]["sim"]
            if not tc or not sc:
                continue
            tm = [statistics.mean([c[i] for c in tc if c[i] is not None])
                  if any(c[i] is not None for c in tc) else None for i in range(10)]
            sm = [statistics.mean([c[i] for c in sc if c[i] is not None])
                  if any(c[i] is not None for c in sc) else None for i in range(10)]
            # A decile in which the tape barely swings at all (the armies are
            # still closing) makes a ratio that is all denominator noise --
            # 40.00 for one engine hit against a tape decile of 0.025. Those
            # cells are blanked rather than printed as if they meant something.
            rr = [ratio(sm[i], tm[i]) if (tm[i] or 0) >= 0.5 else None
                  for i in range(10)]
            to = statistics.mean([m for m, _ in overall[(fam, role)]["tape"]])
            so = statistics.mean([m for m, _ in overall[(fam, role)]["sim"]])
            print(f"{fam:38s} {len(tc):2d} " +
                  " ".join(f"{fmt(r, 2):>5s}" for r in rr) +
                  f"   {so / to:.2f}  ({to:.2f}->{so:.2f})")
        tv = [m for m, _ in overall[role]["tape"]]
        sv = [m for m, _ in overall[role]["sim"]]
        if tv and sv:
            print(f"{'ALL (mean of per-side ratios)':38s} {len(tv):2d} "
                  f"{'':60s}{statistics.mean(sv) / statistics.mean(tv):.2f}"
                  f"  ({statistics.mean(tv):.2f}->{statistics.mean(sv):.2f})")
    print("\n--- 1b. concurrency DECOMPOSED: living bodies x share of them")
    print("        swinging. Which factor is the engine missing?")
    print(f"\n{'family':38s} {'role':>4s} {'conc_t':>6s} {'conc_e':>6s} "
          f"{'cRat':>5s} {'live_t':>6s} {'live_e':>6s} {'lRat':>5s} "
          f"{'shr_t':>6s} {'shr_e':>6s} {'sRat':>5s}")
    for role in ("out", "sup"):
        for fam in fams:
            td, sd = decomp[(fam, role)]["tape"], decomp[(fam, role)]["sim"]
            if not td or not sd:
                continue
            def mm(rows, k):
                return statistics.mean([r[k] for r in rows if r[k] is not None])
            ct, ce = mm(td, "conc"), mm(sd, "conc")
            at, ae = mm(td, "alive"), mm(sd, "alive")
            st, se = mm(td, "share"), mm(sd, "share")
            print(f"{fam:38s} {role:>4s} {ct:>6.2f} {ce:>6.2f} {ce / ct:>5.2f} "
                  f"{at:>6.2f} {ae:>6.2f} {ae / at:>5.2f} "
                  f"{st:>6.3f} {se:>6.3f} {se / st:>5.2f}")
        td, sd = decomp[role]["tape"], decomp[role]["sim"]
        if td and sd:
            def mm2(rows, k):
                return statistics.mean([r[k] for r in rows if r[k] is not None])
            ct, ce = mm2(td, "conc"), mm2(sd, "conc")
            at, ae = mm2(td, "alive"), mm2(sd, "alive")
            st, se = mm2(td, "share"), mm2(sd, "share")
            print(f"{'ALL ' + role:38s} {role:>4s} {ct:>6.2f} {ce:>6.2f} "
                  f"{ce / ct:>5.2f} {at:>6.2f} {ae:>6.2f} {ae / at:>5.2f} "
                  f"{st:>6.3f} {se:>6.3f} {se / st:>5.2f}\n")
    out["concurrency"] = {
        f"{fam}|{role}": {
            "tape": statistics.mean([m for m, _ in overall[(fam, role)]["tape"]]),
            "sim": statistics.mean([m for m, _ in overall[(fam, role)]["sim"]]),
        }
        for fam in fams for role in ("out", "sup")
        if overall[(fam, role)]["tape"] and overall[(fam, role)]["sim"]}

    # =======================================================================
    # 2. non-swinging anatomy (engine internals)
    # =======================================================================
    print("\n" + "=" * 78)
    print("2. NON-SWINGING ANATOMY (engine only) — every living melee unit-tick,")
    print("   split three ways. ENGAGED = state attacking/committed (inside the")
    print("   swing loop). WASTED = an enemy is inside this unit's own reach and")
    print("   it is not engaged. OUT = nothing is inside its reach.")
    print("=" * 78)

    def pool(entries):
        t = {}
        for k in ("aliveTicks", "engagedTicks", "reachTicks", "wastedTicks",
                  "outTicks", "stalledTicks", "lockProtected", "bumpEligible",
                  "crowdedOut", "primeSuspect", "acquisitions", "reacquisitions",
                  "laneDiverts", "stuckTrips", "slotRelease", "lockHeld",
                  "bumpFires"):
            t[k] = sum(e.get(k, 0) for e in entries)
        for grp in ("wasted", "approach"):
            g = defaultdict(int)
            for e in entries:
                for k2, v2_ in e.get(grp, {}).items():
                    g[k2] += v2_
            t[grp] = dict(g)
        hist = defaultdict(int)
        for e in entries:
            for i, v in enumerate(e.get("apvHist", [])):
                hist[i] += v
        t["apvHist"] = [hist[i] for i in range(max(hist) + 1 if hist else 0)]
        for k in ("primeEpisodes", "laneExtraTiles", "laneJourneyS",
                  "plainJourneyS", "bumpGapTiles", "lockOverreachTiles",
                  "approachExtraTiles", "nearestDistTiles"):
            t[k] = merge_samples([e[k] for e in entries if k in e])
        t["episodes"] = {
            c: merge_samples([e["episodes"][c] for e in entries
                              if "episodes" in e and c in e["episodes"]])
            for c in ("lock_out_of_reach", "lane_journey", "no_target",
                      "no_target_blacklist", "other")}
        return t

    po, ps = pool(probe_side["out"]), pool(probe_side["sup"])
    print(f"\n{'':44s} {'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for label, key in (("unit-ticks (alive)", "aliveTicks"),):
        print(f"{label:44s} {po[key]:>13d} {ps[key]:>13d}")
    for label, key in (("  engaged (share of alive)", "engagedTicks"),
                       ("  WASTED  (share of alive)", "wastedTicks"),
                       ("  out of contact (share of alive)", "outTicks")):
        print(f"{label:44s} {po[key] / po['aliveTicks']:>13.3f} "
              f"{ps[key] / ps['aliveTicks']:>13.3f}")
    print(f"\n{'WASTED-tick breakdown (share of wasted)':44s} "
          f"{'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for c in ("lock_out_of_reach", "lane_journey", "no_target",
              "no_target_blacklist", "other"):
        print(f"  {c:42s} {po['wasted'].get(c, 0) / max(1, po['wastedTicks']):>13.3f} "
              f"{ps['wasted'].get(c, 0) / max(1, ps['wastedTicks']):>13.3f}")
    print(f"\n{'sub-flags (share of wasted ticks)':44s} "
          f"{'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for label, key in (("  lock protected (E14 forbids blacklist)", "lockProtected"),
                       ("  bump WAS eligible (rule 2 should fire)", "bumpEligible"),
                       ("  crowded out (all in-reach foes full)", "crowdedOut"),
                       ("  PRIME SUSPECT (locked, not crowded,", "primeSuspect")):
        print(f"{label:44s} {po[key] / max(1, po['wastedTicks']):>13.3f} "
              f"{ps[key] / max(1, ps['wastedTicks']):>13.3f}")
    print(f"{'                 no bump available)':44s}")
    print(f"\n{'episode durations, seconds':44s} "
          f"{'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for label, d in (("  lock_out_of_reach median / p90 / max",
                      (po["episodes"]["lock_out_of_reach"],
                       ps["episodes"]["lock_out_of_reach"])),
                     ("  PRIME SUSPECT   median / p90 / max",
                      (po["primeEpisodes"], ps["primeEpisodes"]))):
        a, b_ = d
        print(f"{label:44s} "
              f"{fmt(a.get('median')) + '/' + fmt(a.get('p90')) + '/' + fmt(a.get('max')):>13s} "
              f"{fmt(b_.get('median')) + '/' + fmt(b_.get('p90')) + '/' + fmt(b_.get('max')):>13s}")
    print(f"{'  (episode count)':44s} {po['primeEpisodes'].get('n', 0):>13d} "
          f"{ps['primeEpisodes'].get('n', 0):>13d}")
    print(f"\n{'geometry of the wasted tick, tiles':44s} "
          f"{'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for label, key in (("  lock is this far PAST its reach (med)", "lockOverreachTiles"),
                       ("  nearest hittable foe, gap past bump", "bumpGapTiles")):
        print(f"{label:44s} {fmt(po[key].get('median'), 3):>13s} "
              f"{fmt(ps[key].get('median'), 3):>13s}")

    print(f"\n{'OUT-OF-CONTACT breakdown (share of out)':44s} "
          f"{'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for c in ("approach_nearest", "approach_nonnearest", "approach_lane",
              "approach_no_target"):
        print(f"  {c:42s} {po['approach'].get(c, 0) / max(1, po['outTicks']):>13.3f} "
              f"{ps['approach'].get(c, 0) / max(1, ps['outTicks']):>13.3f}")
    print(f"  {'STALLED (nearest foe not getting closer)':42s} "
          f"{po['stalledTicks'] / max(1, po['outTicks']):>13.3f} "
          f"{ps['stalledTicks'] / max(1, ps['outTicks']):>13.3f}")
    print(f"  {'dist to nearest foe, tiles (median)':42s} "
          f"{fmt(po['nearestDistTiles'].get('median')):>13s} "
          f"{fmt(ps['nearestDistTiles'].get('median')):>13s}")
    out["anatomy"] = {"out": po, "sup": ps}

    # per-family, outnumbered only
    print("\n   `other` is a one-tick artifact of classifying AFTER update(): a")
    print("   unit whose own approach step carried it into reach is still")
    print("   state=moving on that tick and swings on the next. Its episode")
    print("   median is exactly one tick, which is the check on that reading.")
    print(f"\n{'per family, OUTNUMBERED side':34s} {'eng':>6s} {'wast':>6s} "
          f"{'out':>6s} {'lockOOR':>8s} {'prime':>7s} {'prime/':>7s} "
          f"{'crowd':>6s} {'stall':>6s} {'epiMed':>7s} {'epiP90':>7s} "
          f"{'ovrRch':>7s} {'bmpGap':>7s}")
    print(f"{'':34s} {'':6s} {'':6s} {'':6s} {'/wast':>8s} {'/wast':>7s} "
          f"{'alive':>7s}")
    for fam in fams:
        e = probe_fam[(fam, "out")]
        if not e:
            continue
        t = pool(e)
        a = t["aliveTicks"]
        pe = t["primeEpisodes"]
        print(f"{fam:34s} {t['engagedTicks'] / a:>6.3f} {t['wastedTicks'] / a:>6.3f} "
              f"{t['outTicks'] / a:>6.3f} "
              f"{t['wasted'].get('lock_out_of_reach', 0) / max(1, t['wastedTicks']):>8.3f} "
              f"{t['primeSuspect'] / max(1, t['wastedTicks']):>7.3f} "
              f"{t['primeSuspect'] / a:>7.3f} "
              f"{t['crowdedOut'] / max(1, t['wastedTicks']):>6.3f} "
              f"{t['stalledTicks'] / max(1, t['outTicks']):>6.3f} "
              f"{fmt(pe.get('median')):>7s} {fmt(pe.get('p90')):>7s} "
              f"{fmt(t['lockOverreachTiles'].get('median'), 3):>7s} "
              f"{fmt(t['bumpGapTiles'].get('median'), 3):>7s}")

    # =======================================================================
    # 3. tape counterpart -- retarget latency + attackers per victim
    # =======================================================================
    print("\n" + "=" * 78)
    print("3. TAPE COUNTERPART — when a unit's inferred lock is out of reach while")
    print("   another enemy is adjacent, how long until it lands a hit on SOMEBODY?")
    print("   Same inference on both streams; engine = seeds 1..%d." % args.pos_seeds)
    print("=" * 78)
    print(f"\n{'family / OUTNUMBERED side':38s} {'n_t':>5s} {'med_t':>6s} "
          f"{'p90_t':>6s} {'n_e':>6s} {'med_e':>6s} {'p90_e':>6s} {'ratio':>6s}")
    for role in ("out", "sup"):
        if role == "sup":
            print(f"\n{'family / SUPERIOR side':38s}")
        for fam in fams:
            tl, sl = lat[(fam, role)]["tape"], lat[(fam, role)]["sim"]
            if not tl or not sl:
                continue
            mt, ms = q(tl, 0.5), q(sl, 0.5)
            print(f"{fam:38s} {len(tl):>5d} {fmt(mt):>6s} {fmt(q(tl, 0.9)):>6s} "
                  f"{len(sl):>6d} {fmt(ms):>6s} {fmt(q(sl, 0.9)):>6s} "
                  f"{fmt(ratio(ms, mt)):>6s}")
    for role, label in (("out", "OUTNUMBERED"), ("sup", "SUPERIOR")):
        tl = [x for fam in fams for x in lat[(fam, role)]["tape"]]
        sl = [x for fam in fams for x in lat[(fam, role)]["sim"]]
        tc = sum(latcens[(fam, role)]["tape"][0] for fam in fams)
        te = sum(latcens[(fam, role)]["tape"][1] for fam in fams)
        sc = sum(latcens[(fam, role)]["sim"][0] for fam in fams)
        se = sum(latcens[(fam, role)]["sim"][1] for fam in fams)
        if tl and sl:
            print(f"{'ALL ' + label:38s} {len(tl):>5d} {fmt(q(tl, 0.5)):>6s} "
                  f"{fmt(q(tl, 0.9)):>6s} {len(sl):>6d} {fmt(q(sl, 0.5)):>6s} "
                  f"{fmt(q(sl, 0.9)):>6s} {fmt(ratio(q(sl, 0.5), q(tl, 0.5))):>6s}")
            print(f"{'    episodes / censored (never hit again)':38s} "
                  f"{te:>5d} {tc:>6d} {'':6s} {se:>6d} {sc:>6d}")

    print("\n   ATTACKERS PER VICTIM on the outnumbered side's own bodies")
    print("   geom = living enemies inside their reach of that body, at 10 Hz;")
    print("   dmg  = distinct attackers landing a hit inside a trailing reload.")
    print(f"\n{'family':38s} {'geom_t':>7s} {'geom_e':>7s} {'gmax_t':>7s} "
          f"{'gmax_e':>7s} {'dmg_t':>6s} {'dmg_e':>6s} {'dmax_t':>7s} {'dmax_e':>7s}")
    for fam in fams:
        gt, gs = apv_geom[(fam, "out")]["tape"], apv_geom[(fam, "out")]["sim"]
        dt_, ds = apv_dmg[(fam, "out")]["tape"], apv_dmg[(fam, "out")]["sim"]
        if not gt or not gs:
            continue
        print(f"{fam:38s} {statistics.mean(gt):>7.2f} {statistics.mean(gs):>7.2f} "
              f"{max(gt):>7d} {max(gs):>7d} "
              f"{statistics.mean(dt_) if dt_ else 0:>6.2f} "
              f"{statistics.mean(ds) if ds else 0:>6.2f} "
              f"{max(dt_) if dt_ else 0:>7d} {max(ds) if ds else 0:>7d}")

    # =======================================================================
    # 4. contact-slot audit
    # =======================================================================
    print("\n" + "=" * 78)
    print("4. CONTACT-SLOT AUDIT — does E14's slots-full release ever fire, and is")
    print(f"   MELEE_CONTACT_SLOTS=4 above or below what these fights actually show?")
    print("=" * 78)
    print(f"\n{'':44s} {'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for label, key in (("stuck bar reached 0.8s on a melee unit", "stuckTrips"),
                       ("  ... E14 lock HELD (bar re-armed)", "lockHeld"),
                       ("  ... slots-full RELEASE fired", "slotRelease"),
                       ("bump-retarget fired", "bumpFires")):
        print(f"{label:44s} {po[key]:>13d} {ps[key]:>13d}")
    print(f"{'release as share of stuck trips':44s} "
          f"{po['slotRelease'] / max(1, po['stuckTrips']):>13.3f} "
          f"{ps['slotRelease'] / max(1, ps['stuckTrips']):>13.3f}")
    print("\n   engine attackers-in-reach histogram on the OUTNUMBERED side's")
    print("   bodies (probe, target-aware — the exact count E14 caps at 4):")
    tot = sum(po["apvHist"]) or 1
    for i, v in enumerate(po["apvHist"]):
        print(f"     {i} attackers: {v:>9d}  {v / tot:>6.3f}")
    gt = [x for fam in fams for x in apv_geom[(fam, "out")]["tape"]]
    gs = [x for fam in fams for x in apv_geom[(fam, "out")]["sim"]]
    dt_ = [x for fam in fams for x in apv_dmg[(fam, "out")]["tape"]]
    ds = [x for fam in fams for x in apv_dmg[(fam, "out")]["sim"]]
    print(f"\n{'pooled, outnumbered side':38s} {'tape':>9s} {'engine':>9s}")
    for label, a, b_ in (("geometric mean attackers/body", gt, gs),
                         ("geometric p90", None, None),
                         ("geometric MAX simultaneous", None, None),
                         ("damage-window mean", dt_, ds),
                         ("damage-window p90", None, None),
                         ("damage-window MAX", None, None)):
        if a is not None:
            print(f"{label:38s} {statistics.mean(a):>9.2f} {statistics.mean(b_):>9.2f}")
        elif "geometric p90" == label:
            print(f"{label:38s} {fmt(q(gt, 0.9)):>9s} {fmt(q(gs, 0.9)):>9s}")
        elif "geometric MAX" in label:
            print(f"{label:38s} {max(gt):>9d} {max(gs):>9d}")
        elif "damage-window p90" == label:
            print(f"{label:38s} {fmt(q(dt_, 0.9)):>9s} {fmt(q(ds, 0.9)):>9s}")
        else:
            print(f"{label:38s} {max(dt_):>9d} {max(ds):>9d}")
    out["slots"] = {
        "geom_tape_max": max(gt), "geom_sim_max": max(gs),
        "geom_tape_p90": q(gt, 0.9), "geom_sim_p90": q(gs, 0.9),
        "dmg_tape_max": max(dt_), "dmg_sim_max": max(ds),
    }

    # =======================================================================
    # 5. lane-rule involvement
    # =======================================================================
    print("\n" + "=" * 78)
    print("5. LANE-RULE INVOLVEMENT — how often does E15b divert a re-acquisition")
    print("   to a farther enemy, and what does the walk cost?")
    print("=" * 78)
    print(f"\n{'':44s} {'OUTNUMBERED':>13s} {'SUPERIOR':>13s}")
    for label, key in (("target acquisitions", "acquisitions"),
                       ("  of which RE-acquisitions", "reacquisitions"),
                       ("  of which LANE-DIVERTED", "laneDiverts")):
        print(f"{label:44s} {po[key]:>13d} {ps[key]:>13d}")
    print(f"{'divert share of re-acquisitions':44s} "
          f"{po['laneDiverts'] / max(1, po['reacquisitions']):>13.3f} "
          f"{ps['laneDiverts'] / max(1, ps['reacquisitions']):>13.3f}")
    print(f"{'extra distance to the diverted pick (tiles)':44s} "
          f"{fmt(po['laneExtraTiles'].get('median')):>13s} "
          f"{fmt(ps['laneExtraTiles'].get('median')):>13s}")
    print(f"{'journey after a DIVERT, s (median)':44s} "
          f"{fmt(po['laneJourneyS'].get('median')):>13s} "
          f"{fmt(ps['laneJourneyS'].get('median')):>13s}")
    print(f"{'journey after a PLAIN pick, s (median)':44s} "
          f"{fmt(po['plainJourneyS'].get('median')):>13s} "
          f"{fmt(ps['plainJourneyS'].get('median')):>13s}")
    print(f"{'lane_journey share of WASTED ticks':44s} "
          f"{po['wasted'].get('lane_journey', 0) / max(1, po['wastedTicks']):>13.3f} "
          f"{ps['wasted'].get('lane_journey', 0) / max(1, ps['wastedTicks']):>13.3f}")
    print(f"{'approach_lane share of OUT ticks':44s} "
          f"{po['approach'].get('approach_lane', 0) / max(1, po['outTicks']):>13.3f} "
          f"{ps['approach'].get('approach_lane', 0) / max(1, ps['outTicks']):>13.3f}")

    # =======================================================================
    # 6. v2 outcome cross-check (damage streams only)
    # =======================================================================
    print("\n" + "=" * 78)
    print("6. V2 OUTCOME CROSS-CHECK — the two families the fix has to move,")
    print("   scored on the CURRENT engine. Damage streams only (v2 positions are")
    print("   dead), so this is the same concurrency metric as §1.")
    print("=" * 78)
    v2rows = defaultdict(lambda: defaultdict(lambda: {"tape": [], "sim": []}))
    for fight in v2:
        tag, run_id = fight["tag"], fight["run_id"]
        try:
            tev = tape_damage(tag)
        except FileNotFoundError:
            continue
        fam = family(fight)
        low, high = sides_of(fight)
        for side, role in ((low, "out"), (high, "sup")):
            es = engagement_stats(tev, side["owner"], side["count"])
            if es:
                v2rows[fam][side["slug"]]["tape"].append(es)
            sm = []
            for seed in range(1, args.seeds + 1):
                rec = probe_record(args.probe_dir, run_id, seed)
                if rec is None:
                    continue
                es2 = engagement_stats(rec["damage"], side["owner"], side["count"])
                if es2:
                    sm.append(es2)
            if sm:
                v2rows[fam][side["slug"]]["sim"].append(
                    {k: statistics.mean([e[k] for e in sm if e[k] is not None])
                     for k in ("conc", "alive", "share", "wipe")})
            v2rows[fam][side["slug"]]["role"] = role
            v2rows[fam][side["slug"]]["army"] = side["count"]
    print(f"\n{'family':30s} {'side':14s} {'army':>4s} {'role':>4s} "
          f"{'conc_t':>6s} {'conc_e':>6s} {'cRat':>5s} {'live_t':>6s} "
          f"{'live_e':>6s} {'shr_t':>6s} {'shr_e':>6s} {'sRat':>5s}")
    out["v2"] = {}
    for fam in sorted(v2rows):
        for slug in sorted(v2rows[fam], key=lambda s: -v2rows[fam][s]["army"]):
            d = v2rows[fam][slug]
            if not d["tape"] or not d["sim"]:
                continue
            def mm3(rows, k):
                return statistics.mean([r[k] for r in rows if r[k] is not None])
            ct, ce = mm3(d["tape"], "conc"), mm3(d["sim"], "conc")
            at, ae = mm3(d["tape"], "alive"), mm3(d["sim"], "alive")
            st, se = mm3(d["tape"], "share"), mm3(d["sim"], "share")
            print(f"{fam:30s} {slug:14s} {d['army']:>4d} {d['role']:>4s} "
                  f"{ct:>6.2f} {ce:>6.2f} {ce / ct:>5.2f} {at:>6.2f} "
                  f"{ae:>6.2f} {st:>6.3f} {se:>6.3f} {se / st:>5.2f}")
            out["v2"][f"{fam}|{slug}"] = {
                "conc_tape": ct, "conc_sim": ce, "conc_ratio": ce / ct,
                "alive_tape": at, "alive_sim": ae,
                "share_tape": st, "share_sim": se, "share_ratio": se / st,
                "role": d["role"], "army": d["army"]}

    # =======================================================================
    # 6b. same matchup, two spawn geometries -- is the engine or the tape the
    #     thing that moved between the corpora?
    # =======================================================================
    print("\n" + "=" * 78)
    print("6b. SAME MATCHUP, TWO CORPORA — champion__vs__paladin (21v9) is the")
    print("    only asymmetric melee matchup recorded in BOTH the old corpus and")
    print("    v2. The engine fights each from that recording's own first-frame")
    print("    spawns, so this isolates what the recorder change did.")
    print("=" * 78)
    spawns = json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "calibration"
         / "spawns.json").read_text(encoding="utf-8"))

    def geom(tag, f):
        e = spawns[tag]
        a = e[str(f["side1"]["owner"])]
        b = e[str(f["side2"]["owner"])]
        ca = (sum(p[0] for p in a) / len(a), sum(p[1] for p in a) / len(a))
        cb = (sum(p[0] for p in b) / len(b), sum(p[1] for p in b) / len(b))
        sep = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
        near = min(((p[0] - q2[0]) ** 2 + (p[1] - q2[1]) ** 2) ** 0.5
                   for p in a for q2 in b)
        return sep, near

    groups = {"old": [f for f in old if f["matchup"] == "champion__vs__paladin"],
              "v2": [f for f in v2 if f["matchup"] == "champion__vs__paladin"]}
    print(f"\n{'':40s} {'OLD corpus':>14s} {'V2 corpus':>14s}")
    cols = {}
    for name, fl in groups.items():
        fl = [f for f in fl
              if (args.probe_dir / f["run_id"] / "seed-1.probe.json").exists()]
        if not fl:
            continue
        seps = [geom(f["tag"], f) for f in fl]
        tstats, sstats, pr = [], [], []
        for f in fl:
            low, _ = sides_of(f)
            tev = tape_damage(f["tag"])
            es = engagement_stats(tev, low["owner"], low["count"])
            if es:
                tstats.append(es)
            sm = []
            for seed in range(1, args.seeds + 1):
                rec = probe_record(args.probe_dir, f["run_id"], seed)
                if rec is None:
                    continue
                es2 = engagement_stats(rec["damage"], low["owner"], low["count"])
                if es2:
                    sm.append(es2)
                sp = rec["probe"].get(str(low["owner"]))
                if sp:
                    pr.append(sp)
            if sm:
                sstats.append({
                    k: statistics.mean([e[k] for e in sm if e[k] is not None])
                    for k in ("conc", "alive", "share", "wipe")})
        def mn(rows, k):
            return (statistics.mean([r[k] for r in rows if r[k] is not None])
                    if rows else None)
        cols[name] = {
            "n": len(fl),
            "sep": statistics.mean([s for s, _ in seps]),
            "near": statistics.mean([n for _, n in seps]),
            "tape": mn(tstats, "conc"), "sim": mn(sstats, "conc"),
            "alive_t": mn(tstats, "alive"), "alive_e": mn(sstats, "alive"),
            "share_t": mn(tstats, "share"), "share_e": mn(sstats, "share"),
            "wipe_t": mn(tstats, "wipe"), "wipe_e": mn(sstats, "wipe"),
            "probe": pool(pr) if pr else None,
        }
    def row(label, fn, d=2):
        vals = []
        for name in ("old", "v2"):
            c = cols.get(name)
            vals.append("-" if c is None else fn(c))
        print(f"{label:40s} {vals[0]:>14s} {vals[1]:>14s}")
    row("recordings", lambda c: str(c["n"]))
    row("spawn: centroid separation (tiles)", lambda c: fmt(c["sep"]))
    row("spawn: nearest cross-army pair (tiles)", lambda c: fmt(c["near"]))
    row("TAPE paladin concurrency", lambda c: fmt(c["tape"]))
    row("ENGINE paladin concurrency", lambda c: fmt(c["sim"]))
    row("  ratio engine/tape", lambda c: fmt(ratio(c["sim"], c["tape"])))
    row("TAPE mean living paladins", lambda c: fmt(c["alive_t"]))
    row("ENGINE mean living paladins", lambda c: fmt(c["alive_e"]))
    row("TAPE swinging share of living", lambda c: fmt(c["share_t"], 3))
    row("ENGINE swinging share of living", lambda c: fmt(c["share_e"], 3))
    row("  ratio engine/tape", lambda c: fmt(ratio(c["share_e"], c["share_t"])))
    row("TAPE wipe / ENGINE wipe (s)",
        lambda c: f"{fmt(c['wipe_t'], 1)}/{fmt(c['wipe_e'], 1)}")
    for label, fn in (
        ("engine paladin: engaged share",
         lambda c: fmt(c["probe"]["engagedTicks"] / c["probe"]["aliveTicks"], 3)),
        ("engine paladin: WASTED share",
         lambda c: fmt(c["probe"]["wastedTicks"] / c["probe"]["aliveTicks"], 3)),
        ("engine paladin: out-of-contact share",
         lambda c: fmt(c["probe"]["outTicks"] / c["probe"]["aliveTicks"], 3)),
        ("engine paladin: prime-suspect / wasted",
         lambda c: fmt(c["probe"]["primeSuspect"]
                       / max(1, c["probe"]["wastedTicks"]), 3)),
        ("engine paladin: stalled / out",
         lambda c: fmt(c["probe"]["stalledTicks"]
                       / max(1, c["probe"]["outTicks"]), 3)),
    ):
        row(label, fn)
    out["corpus_ab"] = {k: {kk: vv for kk, vv in v.items() if kk != "probe"}
                        for k, v in cols.items()}

    if args.json:
        args.json.write_text(json.dumps(out, indent=1, default=str) + "\n",
                             encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
