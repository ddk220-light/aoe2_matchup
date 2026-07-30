"""E13 Step 1: measure the TIME-DOMAIN structure of melee combat, tape vs engine.

E12 established that an *engaged* melee unit's per-swing cadence is already
exactly right (tape/engine swing-interval median 1.001) but that its DUTY
CYCLE is not: tape 0.28 vs engine 0.52 of the fight spent swinging. That
means tape units repeatedly stop hitting things and engine units do not.
This module measures WHAT that idle time is made of, from the one signal
both sides expose identically -- the damage stream (t, attacker, victim,
damage, kill).

Five measurements, computed by the SAME functions for a tape's
``.damage.jsonl.gz`` and a sim run's ``seed-N.json`` ``damage`` array, so
every number is directly comparable:

1. **gaps** -- consecutive landed-hit intervals per attacker, split into
   SAME-target (should be ~reload) and SWITCH-target (the attacker's victim
   changed between the two hits). A switch gap far above reload is
   re-acquisition cost the engine may not be paying.
2. **post-kill latency** -- for the unit that lands a killing blow, how long
   until its NEXT landed hit. This is retarget cost measured at its purest.
3. **bouts** -- per attacker, contiguous runs of swings spaced
   <= reload + BOUT_SLACK apart. Reports swings-per-bout and the duration
   of the IDLE GAPS between bouts. A bounded bout length on tape and an
   unbounded one in the engine is the "units cycle in and out of contact"
   signature.
4. **attackers-per-victim** -- at each landed hit, how many DISTINCT enemies
   hit that same victim within the trailing reload window. Says whether the
   tape's rear ranks queue or pile on.
5. **overkill** -- damage delivered to a victim in excess of the HP it had
   left, summed over kills, as a fraction of all damage dealt. Tape lancers
   reportedly waste ~0; the engine reportedly wastes ~15%.

Duty cycle is recomputed here too (swings x reload / (side lifetime)) so the
E12 headline number is reproducible from this one script.

Usage:

    python tools/simjs/melee_bout_forensics.py --fights basic
    python tools/simjs/melee_bout_forensics.py --fights paladin__vs__elite_steppe --detail
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path

from aoe2x.paths import REPO_ROOT

CALIB = REPO_ROOT / "data" / "calibration"
TAPES = Path("D:/AI/aoe2_golden/tapes")
DEFAULT_SIMRUNS = Path("D:/AI/aoe2_golden/simruns_e12_tapebox")

MELEE_SLUGS = {
    "champion", "halberdier", "paladin", "heavy_camel", "hussar",
    "elite_steppe", "elite_elephant",
}
BASIC_SLUGS = {"champion", "halberdier", "paladin", "heavy_camel", "hussar"}

# A swing that lands within reload + this much of the previous one is "the
# same bout" -- the unit never stopped fighting. 0.5s is wide enough to
# absorb attack-delay/projectile flight and the 60Hz sampling of the tape,
# narrow enough that a genuine walk-away shows up as a gap. Sensitivity to
# this choice is reported (BOUT_SLACK_ALT) rather than assumed away.
BOUT_SLACK = 0.5
BOUT_SLACK_ALT = 0.25


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_manifest():
    return json.loads((CALIB / "manifest.json").read_text(encoding="utf-8"))["fights"]


def load_dicts():
    return json.loads((CALIB / "combat_dicts.json").read_text(encoding="utf-8"))


def tape_damage(tag: str) -> list[dict]:
    p = TAPES / tag / f"{tag}.damage.jsonl.gz"
    out = []
    with gzip.open(p, "rt") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def sim_damage(sim_runs_dir: Path, run_id: str, seed: int = 1) -> list[dict]:
    p = sim_runs_dir / run_id / f"seed-{seed}.json"
    return json.loads(p.read_text(encoding="utf-8"))["damage"]


# ---------------------------------------------------------------------------
# measurements -- one implementation, fed tape events or sim events
# ---------------------------------------------------------------------------

def _by_attacker(events, owner):
    """{attacker_id: [event, ...]} for one owner, each list time-sorted."""
    d = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            d[e["attacker"]].append(e)
    for lst in d.values():
        lst.sort(key=lambda e: e["t"])
    return d


def gaps_split(events, owner):
    """SAME-target vs SWITCH-target consecutive-hit gaps for one side."""
    same, switch = [], []
    for hits in _by_attacker(events, owner).values():
        for a, b in zip(hits, hits[1:]):
            gap = b["t"] - a["t"]
            (same if a["victim"] == b["victim"] else switch).append(gap)
    return same, switch


def post_kill_latency(events, owner):
    """For every killing blow this side lands: seconds until that same
    attacker's next landed hit. Attackers that never hit again (fight ended,
    or they died) contribute nothing -- a censored sample, not a zero.
    """
    out = []
    for hits in _by_attacker(events, owner).values():
        for i, e in enumerate(hits):
            if not e.get("kill"):
                continue
            if i + 1 < len(hits):
                out.append(hits[i + 1]["t"] - e["t"])
    return out


def bouts(events, owner, reload_s, slack=BOUT_SLACK):
    """Contiguous swing runs and the idle gaps separating them.

    Returns (bout_lengths_in_swings, idle_gap_seconds, bout_durations).
    """
    lengths, idles, durs = [], [], []
    thresh = reload_s + slack
    for hits in _by_attacker(events, owner).values():
        run_len, run_t0 = 1, hits[0]["t"]
        for a, b in zip(hits, hits[1:]):
            gap = b["t"] - a["t"]
            if gap <= thresh:
                run_len += 1
            else:
                lengths.append(run_len)
                durs.append(a["t"] - run_t0)
                idles.append(gap)
                run_len, run_t0 = 1, b["t"]
        lengths.append(run_len)
        durs.append(hits[-1]["t"] - run_t0)
    return lengths, idles, durs


def attackers_per_victim(events, owner, reload_s):
    """At each landed hit BY this side, the number of distinct attackers from
    this side that hit the same victim within the trailing reload window
    (the hit itself included, so the minimum is 1).
    """
    by_victim = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            by_victim[e["victim"]].append(e)
    counts = []
    for hits in by_victim.values():
        hits.sort(key=lambda e: e["t"])
        for i, e in enumerate(hits):
            lo = e["t"] - reload_s
            seen = {h["attacker"] for h in hits[:i + 1] if h["t"] >= lo}
            counts.append(len(seen))
    return counts


def overkill(events, owner):
    """(wasted_damage, total_damage) for this side.

    Waste is measured per killing blow: a hit that leaves the victim at 0
    but carried more damage than the victim's remaining HP wasted the
    excess. Both streams carry ``victim_hp_after``, so remaining HP before
    the blow is (hp_after + damage) -- and for a kill hp_after is 0 (or
    negative in a stream that does not clamp), so the waste is exactly
    ``damage - hp_before_the_blow``. Computed from hp_after directly to stay
    agnostic about clamping:

        hp_before = hp_after + damage   (always true)
        waste     = damage - hp_before  if kill else 0   -> = -hp_after

    i.e. an unclamped stream reports the overkill in its own hp_after, and a
    clamped one reports 0. Both are handled: we track the victim's last
    known HP ourselves and use that when hp_after is clamped.
    """
    last_hp = {}
    waste = total = 0.0
    for e in sorted(events, key=lambda e: e["t"]):
        dmg = float(e.get("damage") or 0.0)
        v = e["victim"]
        hp_before = last_hp.get(v)
        if e.get("attacker_owner") == owner:
            total += dmg
            if e.get("kill") and hp_before is not None:
                waste += max(0.0, dmg - hp_before)
        after = e.get("victim_hp_after")
        last_hp[v] = float(after) if after is not None else 0.0
    return waste, total


def duty_cycle(events, owner, reload_s, n_units, duration_s):
    """Fraction of unit-seconds this side spent mid-swing: swings x reload
    over (n_units x fight duration). This is E12's number, recomputed here
    so the whole account comes out of one script.
    """
    swings = sum(1 for e in events if e.get("attacker_owner") == owner)
    denom = n_units * duration_s
    return (swings * reload_s / denom) if denom else None


def _q(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    i = q * (len(s) - 1)
    lo = int(i)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def stat(vals):
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "median": round(statistics.median(vals), 3),
        "mean": round(statistics.mean(vals), 3),
        "p90": round(_q(vals, 0.90), 3),
        "max": round(max(vals), 3),
    }


def measure(events, owner, reload_s, n_units, duration_s):
    same, switch = gaps_split(events, owner)
    lens, idles, durs = bouts(events, owner, reload_s)
    lens_alt, idles_alt, _ = bouts(events, owner, reload_s, BOUT_SLACK_ALT)
    w, tot = overkill(events, owner)
    return {
        "swings": sum(1 for e in events if e.get("attacker_owner") == owner),
        "duty_cycle": (round(duty_cycle(events, owner, reload_s, n_units, duration_s), 4)
                       if duration_s else None),
        "gap_same": stat(same),
        "gap_switch": stat(switch),
        "switch_frac": (round(len(switch) / (len(same) + len(switch)), 3)
                        if (same or switch) else None),
        "post_kill": stat(post_kill_latency(events, owner)),
        "bout_len": stat(lens),
        "bout_len_alt": stat(lens_alt),
        "idle_gap": stat(idles),
        "idle_gap_alt": stat(idles_alt),
        "bout_dur": stat(durs),
        "attackers_per_victim": stat(attackers_per_victim(events, owner, reload_s)),
        "overkill_frac": round(w / tot, 4) if tot else None,
        "damage_total": round(tot, 1),
    }


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def pick_fights(which: str):
    fights = load_manifest()
    mel = [f for f in fights
           if f["side1"]["slug"] in MELEE_SLUGS and f["side2"]["slug"] in MELEE_SLUGS]
    if which == "melee":
        return mel
    if which == "basic":
        return [f for f in mel
                if f["side1"]["slug"] in BASIC_SLUGS and f["side2"]["slug"] in BASIC_SLUGS]
    return [f for f in fights if f["run_id"] in which.split(",")]


def run(which, sim_runs_dir, seed, out_json=None):
    dicts = load_dicts()
    rows = []
    for fight in pick_fights(which):
        tag, run_id = fight["tag"], fight["run_id"]
        try:
            tev = tape_damage(tag)
            sev = sim_damage(sim_runs_dir, run_id, seed)
        except FileNotFoundError:
            continue
        tape_dur = fight.get("duration_s") or (max(e["t"] for e in tev) if tev else 0)
        sim_dur = max((e["t"] for e in sev), default=0.0)
        for side in (fight["side1"], fight["side2"]):
            u = dicts[f"{side['civ']}|{side['slug']}"]
            reload_s = 1.0 / u["attack_speed"]
            rows.append({
                "run_id": run_id, "side": side["owner"], "slug": side["slug"],
                "count": side["count"], "reload": round(reload_s, 3),
                "tape": measure(tev, side["owner"], reload_s, side["count"], tape_dur),
                "sim": measure(sev, side["owner"], reload_s, side["count"], sim_dur),
            })
    if out_json:
        Path(out_json).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return rows


def aggregate(rows, key, sub="median"):
    t = [r["tape"][key][sub] for r in rows if r["tape"][key].get(sub) is not None]
    s = [r["sim"][key][sub] for r in rows if r["sim"][key].get(sub) is not None]
    return (round(statistics.median(t), 3) if t else None,
            round(statistics.median(s), 3) if s else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fights", default="basic",
                    help="'basic', 'melee', or a comma-separated run_id list")
    ap.add_argument("--sim-runs-dir", type=Path, default=DEFAULT_SIMRUNS)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--json", default=None)
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    rows = run(args.fights, args.sim_runs_dir, args.seed, args.json)
    print(f"{len(rows)} melee sides   sim={args.sim_runs_dir}\n")

    print(f"{'measurement':28s} {'tape':>9s} {'engine':>9s}   ratio")
    for label, key, sub in [
        ("duty cycle", None, None),
        ("gap SAME-target median", "gap_same", "median"),
        ("gap SWITCH-target median", "gap_switch", "median"),
        ("gap SWITCH-target p90", "gap_switch", "p90"),
        ("switch fraction of gaps", None, "switch_frac"),
        ("post-kill latency median", "post_kill", "median"),
        ("post-kill latency p90", "post_kill", "p90"),
        ("bout length (swings) med", "bout_len", "median"),
        ("bout length p90", "bout_len", "p90"),
        ("bout length max", "bout_len", "max"),
        ("idle gap median", "idle_gap", "median"),
        ("idle gap p90", "idle_gap", "p90"),
        ("attackers/victim median", "attackers_per_victim", "median"),
        ("attackers/victim p90", "attackers_per_victim", "p90"),
        ("attackers/victim max", "attackers_per_victim", "max"),
        ("overkill fraction", None, "overkill_frac"),
    ]:
        if key is None:
            fld = sub if sub else "duty_cycle"
            t = [r["tape"][fld] for r in rows if r["tape"].get(fld) is not None]
            s = [r["sim"][fld] for r in rows if r["sim"].get(fld) is not None]
            tv = round(statistics.median(t), 4) if t else None
            sv = round(statistics.median(s), 4) if s else None
        else:
            tv, sv = aggregate(rows, key, sub)
        ratio = (round(sv / tv, 3) if tv not in (None, 0) and sv is not None else None)
        print(f"{label:28s} {str(tv):>9s} {str(sv):>9s}   {ratio}")

    if args.detail:
        print(f"\n{'run_id':30s} {'side':13s} "
              f"{'duty t/e':>13s} {'boutlen t/e':>13s} {'idle t/e':>13s} "
              f"{'postkill t/e':>14s} {'ovk t/e':>13s}")
        for r in rows:
            t, s = r["tape"], r["sim"]
            def pair(a, b, f="{:.2f}"):
                fa = f.format(a) if a is not None else "-"
                fb = f.format(b) if b is not None else "-"
                return f"{fa}/{fb}"
            print(f"{r['run_id']:30s} {r['slug']:13s} "
                  f"{pair(t['duty_cycle'], s['duty_cycle']):>13s} "
                  f"{pair(t['bout_len'].get('median'), s['bout_len'].get('median'), '{:.1f}'):>13s} "
                  f"{pair(t['idle_gap'].get('median'), s['idle_gap'].get('median')):>13s} "
                  f"{pair(t['post_kill'].get('median'), s['post_kill'].get('median')):>14s} "
                  f"{pair(t['overkill_frac'], s['overkill_frac'], '{:.3f}'):>13s}")


if __name__ == "__main__":
    main()
