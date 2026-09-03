"""E14 Step 1: measure WHO melee units hit, tape vs engine.

E13 closed the time-domain gap (when units swing). What is left in the pure
melee gate is not the winner but the MARGIN: the winning side finishes too
weak. Two measured signatures point at target SELECTION rather than timing:

  * damage banked in survivors -- damage dealt to enemies that never die --
    is 2.1% of all damage on tape and 4.6% in the engine;
  * the wounded fraction of the foes still alive at the end is 0.704 on tape
    and 0.934 in the engine.

i.e. the engine SMEARS damage across the whole enemy line while the tape
concentrates it on a few victims and leaves the rest untouched. This module
measures the smear five ways, with ONE implementation fed either a tape's
``.damage.jsonl.gz`` or a sim run's ``seed-N.json`` ``damage`` array, so every
number is directly comparable (same discipline as melee_bout_forensics.py):

1. **concentration** -- distinct victims a side is actively damaging inside a
   trailing reload window; Herfindahl (HHI) and effective-victim-count of the
   damage share over the whole fight; Gini of that share.
2. **kill ordering** -- are victims finished in the order they were first
   touched? Spearman rho(first-touch rank, death rank), plus the number of
   OPEN WOUNDS (victims touched, still alive) standing at each kill. Strict
   "finish what you started" gives rho ~ 1 and few open wounds.
3. **damage-fate ledger** -- every enemy is killed / wounded-survivor /
   untouched. Counts, and the damage banked into each bucket, with the
   survivor bucket split by how much HP it has left (near-dead <25%, mid,
   lightly clipped >75%) so "banked" is not one undifferentiated number.
4. **retarget matrix** -- for consecutive landed hits by one attacker,
   classify the transition: SAME victim, or a SWITCH (after a kill or off a
   living victim), and for switches where the new victim came from: FRESH
   (nobody had touched it), ALLY (an ally hit it inside the trailing reload
   window -- a pile-on), or PRIOR (this attacker had hit it before).
5. **end-state wounding** -- of the enemies alive when the fight ends, what
   fraction carries damage (E13's 0.704 vs 0.934), and their mean HP fraction.

Usage:

    python tools/simjs/melee_target_forensics.py --sim-runs-dir <dir>
    python tools/simjs/melee_target_forensics.py --fights basic --detail
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aoe2x.calibration.paths import workspace_paths  # noqa: E402

PATHS = workspace_paths()
CALIB = PATHS.fixtures_dir
TAPES = PATHS.tapes_dir
DEFAULT_SIMRUNS = PATHS.runs_dir / "melee-target"

MELEE_SLUGS = {
    "champion", "halberdier", "paladin", "heavy_camel", "hussar",
    "elite_steppe", "elite_elephant",
}
BASIC_SLUGS = {"champion", "halberdier", "paladin", "heavy_camel", "hussar"}


# ---------------------------------------------------------------------------
# loading (same sources as melee_bout_forensics.py)
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
# measurements
# ---------------------------------------------------------------------------

def _side_events(events, owner):
    """Time-sorted damage events dealt BY `owner`."""
    return sorted((e for e in events if e.get("attacker_owner") == owner),
                  key=lambda e: e["t"])


def concentration(events, owner, reload_s):
    """How many distinct victims is this side working on at once?

    At every landed hit, count the distinct victims this side damaged in the
    trailing reload window. This is the exact dual of E13's
    attackers-per-victim: that one asked "how many hit this guy", this one
    asks "how many guys are being hit". A side that finishes what it starts
    keeps this number near (its own unit count / attackers-per-victim); a
    smearing side runs it much higher.
    """
    ev = _side_events(events, owner)
    counts = []
    lo = 0
    for i, e in enumerate(ev):
        t0 = e["t"] - reload_s
        while ev[lo]["t"] < t0:
            lo += 1
        counts.append(len({h["victim"] for h in ev[lo:i + 1]}))
    return counts


def damage_share(events, owner):
    """{victim: damage} for one side's whole output."""
    d = defaultdict(float)
    for e in events:
        if e.get("attacker_owner") == owner:
            d[e["victim"]] += float(e.get("damage") or 0.0)
    return d


def hhi_gini(share: dict):
    """Herfindahl and Gini of a damage-share distribution.

    HHI = sum of squared shares; 1/HHI is the EFFECTIVE number of victims the
    side spread its damage over. Reported alongside the raw victim count, so
    "hit 9 units but effectively 4" is visible directly.
    """
    tot = sum(share.values())
    if tot <= 0 or not share:
        return None, None, 0
    ss = sorted(share.values())
    n = len(ss)
    h = sum((v / tot) ** 2 for v in ss)
    # Gini over the victims actually touched (untouched enemies are counted in
    # the fate ledger instead -- mixing them in here would conflate "spread
    # thin" with "did not reach them").
    cum = 0.0
    for i, v in enumerate(ss, start=1):
        cum += i * v
    g = (2 * cum) / (n * tot) - (n + 1) / n if n > 1 else 0.0
    return h, g, n


def kill_ordering(events, owner):
    """Do victims die in the order they were first touched?

    Returns (spearman_rho, open_wounds_at_each_kill, n_kills). "Open wounds"
    are victims this side has damaged that are still alive at the moment of a
    kill -- the direct count of how many fights the side has going at once.
    """
    ev = _side_events(events, owner)
    first_touch, death_t = {}, {}
    for e in ev:
        first_touch.setdefault(e["victim"], e["t"])
        if e.get("kill"):
            death_t.setdefault(e["victim"], e["t"])
    killed = [v for v in death_t]
    if len(killed) < 2:
        return None, [], len(killed)
    touch_rank = {v: i for i, v in enumerate(
        sorted(killed, key=lambda v: first_touch[v]))}
    death_rank = {v: i for i, v in enumerate(
        sorted(killed, key=lambda v: death_t[v]))}
    n = len(killed)
    d2 = sum((touch_rank[v] - death_rank[v]) ** 2 for v in killed)
    rho = 1 - 6 * d2 / (n * (n * n - 1))

    open_counts = []
    for v, t in sorted(death_t.items(), key=lambda kv: kv[1]):
        open_ = sum(1 for w, ft in first_touch.items()
                    if w != v and ft <= t and death_t.get(w, 1e18) > t)
        open_counts.append(open_)
    return rho, open_counts, n


def fate_ledger(events, owner, enemy_count, enemy_maxhp):
    """Killed / wounded-survivor / untouched, in units AND in damage.

    The survivor bucket is split by the HP the survivor was left with (as a
    fraction of its own max): NEARDEAD <25%, MID, LIGHT >75%. That says
    WHERE the banked damage sits -- a near-dead survivor is one swing from
    being a kill (cheap smear), a lightly-clipped one is damage thrown away.
    """
    share = damage_share(events, owner)
    killed, last_hp = set(), {}
    for e in sorted(events, key=lambda e: e["t"]):
        if e.get("attacker_owner") != owner:
            continue
        after = e.get("victim_hp_after")
        last_hp[e["victim"]] = float(after) if after is not None else 0.0
        if e.get("kill"):
            killed.add(e["victim"])
    total = sum(share.values())
    surv = {v: d for v, d in share.items() if v not in killed}
    buckets = {"neardead": [0, 0.0], "mid": [0, 0.0], "light": [0, 0.0]}
    for v, d in surv.items():
        frac = max(0.0, last_hp.get(v, 0.0)) / enemy_maxhp if enemy_maxhp else 0.0
        key = "neardead" if frac < 0.25 else ("light" if frac > 0.75 else "mid")
        buckets[key][0] += 1
        buckets[key][1] += d
    return {
        "enemies": enemy_count,
        "killed": len(killed),
        "wounded_survivors": len(surv),
        "untouched": max(0, enemy_count - len(share)),
        "damage_total": round(total, 1),
        "banked_frac": round(sum(surv.values()) / total, 4) if total else None,
        "banked_neardead_frac": (round(buckets["neardead"][1] / total, 4)
                                 if total else None),
        "banked_mid_frac": round(buckets["mid"][1] / total, 4) if total else None,
        "banked_light_frac": (round(buckets["light"][1] / total, 4)
                              if total else None),
        # end-state wounding: of the enemies still standing, how many carry
        # damage (E13's headline 0.704 tape / 0.934 engine)
        "alive_end": max(0, enemy_count - len(killed)),
        "wounded_frac_of_alive": (round(len(surv) / (enemy_count - len(killed)), 4)
                                  if enemy_count - len(killed) > 0 else None),
    }


def retarget_matrix(events, owner, reload_s):
    """Consecutive-hit transitions for every attacker on this side.

    SAME                 -- the attacker hit the same victim twice running.
    SWITCH_AFTER_KILL/x  -- the previous hit killed; x is where it went next.
    SWITCH_LIVE/x        -- it left a living victim; x is where it went next.

    Destination class x:
      FRESH -- nobody on this side had touched the new victim before;
      ALLY  -- an ALLY hit the new victim inside the trailing reload window
               (the attacker piled onto a fight already in progress);
      PRIOR -- this attacker had hit that victim earlier in the fight (it
               came back to something it had started).
    ALLY wins over PRIOR when both hold: the pile-on is the stronger claim
    about selection and is the one the in-game hypothesis is about.
    """
    ev = _side_events(events, owner)
    by_victim = defaultdict(list)
    for e in ev:
        by_victim[e["victim"]].append(e)

    by_attacker = defaultdict(list)
    for e in ev:
        by_attacker[e["attacker"]].append(e)

    counts = defaultdict(int)
    for hits in by_attacker.values():
        seen_own = {hits[0]["victim"]}
        for a, b in zip(hits, hits[1:]):
            if a["victim"] == b["victim"]:
                counts["SAME"] += 1
                seen_own.add(b["victim"])
                continue
            prev = by_victim[b["victim"]]
            touched_before = any(h["t"] < b["t"] for h in prev)
            ally_recent = any(
                h["t"] < b["t"] and h["t"] >= b["t"] - reload_s
                and h["attacker"] != b["attacker"] for h in prev)
            if ally_recent:
                dest = "ALLY"
            elif b["victim"] in seen_own:
                dest = "PRIOR"
            elif touched_before:
                dest = "PRIOR"
            else:
                dest = "FRESH"
            kind = "KILL" if a.get("kill") else "LIVE"
            counts[f"SWITCH_{kind}/{dest}"] += 1
            seen_own.add(b["victim"])
    return dict(counts)


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
    return {"n": len(vals), "median": round(statistics.median(vals), 3),
            "mean": round(statistics.mean(vals), 3),
            "p90": round(_q(vals, 0.90), 3), "max": round(max(vals), 3)}


def measure(events, owner, reload_s, enemy_count, enemy_maxhp):
    conc = concentration(events, owner, reload_s)
    share = damage_share(events, owner)
    h, g, nvict = hhi_gini(share)
    rho, open_counts, nkills = kill_ordering(events, owner)
    out = {
        "concurrent_victims": stat(conc),
        "victims_touched": nvict,
        "hhi": round(h, 4) if h is not None else None,
        "eff_victims": round(1 / h, 2) if h else None,
        "gini": round(g, 4) if g is not None else None,
        "kill_order_rho": round(rho, 4) if rho is not None else None,
        "open_wounds": stat(open_counts),
        "kills": nkills,
        "retarget": retarget_matrix(events, owner, reload_s),
    }
    out.update(fate_ledger(events, owner, enemy_count, enemy_maxhp))
    return out


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
        for side, foe in ((fight["side1"], fight["side2"]),
                          (fight["side2"], fight["side1"])):
            u = dicts[f"{side['civ']}|{side['slug']}"]
            fu = dicts[f"{foe['civ']}|{foe['slug']}"]
            reload_s = 1.0 / u["attack_speed"]
            rows.append({
                "run_id": run_id, "side": side["owner"], "slug": side["slug"],
                "count": side["count"], "foe": foe["slug"],
                "foe_count": foe["count"], "reload": round(reload_s, 3),
                "tape": measure(tev, side["owner"], reload_s,
                                foe["count"], float(fu["hp"])),
                "sim": measure(sev, side["owner"], reload_s,
                               foe["count"], float(fu["hp"])),
            })
    if out_json:
        Path(out_json).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return rows


def _med(rows, stream, path):
    vals = []
    for r in rows:
        cur = r[stream]
        for k in path:
            if cur is None:
                break
            cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is not None:
            vals.append(cur)
    return round(statistics.median(vals), 4) if vals else None


def retarget_totals(rows, stream):
    tot = defaultdict(int)
    for r in rows:
        for k, v in r[stream]["retarget"].items():
            tot[k] += v
    n = sum(tot.values())
    return tot, n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fights", default="melee")
    ap.add_argument("--sim-runs-dir", type=Path, default=DEFAULT_SIMRUNS)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--json", default=None)
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    rows = run(args.fights, args.sim_runs_dir, args.seed, args.json)
    print(f"{len(rows)} melee sides   sim={args.sim_runs_dir}\n")

    print(f"{'measurement':34s} {'tape':>9s} {'engine':>9s}   ratio")
    for label, path in [
        ("concurrent victims median", ("concurrent_victims", "median")),
        ("concurrent victims p90", ("concurrent_victims", "p90")),
        ("concurrent victims max", ("concurrent_victims", "max")),
        ("victims touched", ("victims_touched",)),
        ("HHI of damage share", ("hhi",)),
        ("effective victims (1/HHI)", ("eff_victims",)),
        ("gini of damage share", ("gini",)),
        ("kill-order rho(touch,death)", ("kill_order_rho",)),
        ("open wounds at kill median", ("open_wounds", "median")),
        ("open wounds at kill p90", ("open_wounds", "p90")),
        ("killed", ("killed",)),
        ("wounded survivors", ("wounded_survivors",)),
        ("untouched enemies", ("untouched",)),
        ("banked damage frac", ("banked_frac",)),
        ("  banked in near-dead", ("banked_neardead_frac",)),
        ("  banked in mid", ("banked_mid_frac",)),
        ("  banked in light", ("banked_light_frac",)),
        ("wounded frac of alive foes", ("wounded_frac_of_alive",)),
    ]:
        tv, sv = _med(rows, "tape", path), _med(rows, "sim", path)
        ratio = round(sv / tv, 3) if tv not in (None, 0) and sv is not None else None
        print(f"{label:34s} {str(tv):>9s} {str(sv):>9s}   {ratio}")

    # corpus-wide banked fraction / wounded fraction (pooled, not median of
    # per-side numbers) -- this is the E13 headline definition.
    def pooled(stream):
        dmg = sum(r[stream]["damage_total"] for r in rows)
        banked = sum(r[stream]["damage_total"] * (r[stream]["banked_frac"] or 0)
                     for r in rows)
        alive = sum(r[stream]["alive_end"] for r in rows)
        wounded = sum(r[stream]["wounded_survivors"] for r in rows)
        return (round(banked / dmg, 4) if dmg else None,
                round(wounded / alive, 4) if alive else None)
    tb, tw = pooled("tape")
    sb, sw = pooled("sim")
    print(f"\nPOOLED  banked-damage  tape {tb}  engine {sb}")
    print(f"POOLED  wounded/alive   tape {tw}  engine {sw}")

    print("\nretarget transition matrix (share of all consecutive-hit pairs)")
    tt, tn = retarget_totals(rows, "tape")
    st, sn = retarget_totals(rows, "sim")
    keys = sorted(set(tt) | set(st))
    print(f"{'transition':28s} {'tape':>9s} {'engine':>9s}")
    for k in keys:
        print(f"{k:28s} {tt[k]/tn:>9.4f} {st[k]/sn:>9.4f}")
    print(f"{'(n pairs)':28s} {tn:>9d} {sn:>9d}")

    if args.detail:
        print(f"\n{'run_id':30s} {'side':13s} {'conc t/e':>11s} "
              f"{'effvic t/e':>12s} {'bank t/e':>13s} {'wnd/alive t/e':>15s}")
        for r in rows:
            t, s = r["tape"], r["sim"]
            def pair(a, b, f="{:.2f}"):
                return (f.format(a) if a is not None else "-") + "/" + \
                       (f.format(b) if b is not None else "-")
            print(f"{r['run_id']:30s} {r['slug']:13s} "
                  f"{pair(t['concurrent_victims'].get('median'), s['concurrent_victims'].get('median'), '{:.1f}'):>11s} "
                  f"{pair(t['eff_victims'], s['eff_victims'], '{:.1f}'):>12s} "
                  f"{pair(t['banked_frac'], s['banked_frac'], '{:.3f}'):>13s} "
                  f"{pair(t['wounded_frac_of_alive'], s['wounded_frac_of_alive'], '{:.2f}'):>15s}")


if __name__ == "__main__":
    main()
