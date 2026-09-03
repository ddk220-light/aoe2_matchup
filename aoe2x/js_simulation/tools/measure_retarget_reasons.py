"""WHY does a unit voluntarily change target?

Community/engine sources say a unit that cannot reach its target looks for
another one. That is a physics rule, not a timer -- so test it directly.

For every voluntary switch (old target still alive), look back over the span
the unit held that target and ask:

  * did it EVER get to attack it (action_state 6 reload / 7 swing)?
  * if it did, how long since the last attack frame?
  * was it closing the distance, or stalled?

If voluntary switches are dominated by "never reached it" and "stalled a long
time", the rule is reachability, and any per-second rate is a CONSEQUENCE of
how often units get stuck -- which is what we want to model.
"""
import collections
import glob
import json
import os
import statistics
import sys

CH, PA = 567, 569
HALF = {CH: 0.20, PA: 0.25}
ST_MOVE, ST_RELOAD, ST_SWING = 4, 6, 7
REACH = 0.1


def gap(a, b):
    return (max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]))
            - HALF[a["master"]] - HALF[b["master"]])


def analyse(path):
    by = collections.defaultdict(list)
    frames = collections.defaultdict(dict)
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("master") in (CH, PA):
                by[r["id"]].append(r)
                frames[r["t_ms"]][r["id"]] = r
    for s in by.values():
        s.sort(key=lambda r: r["t_ms"])

    death = {}
    for uid, s in by.items():
        for r in s:
            if r.get("hp") is not None and r["hp"] <= 0:
                death[uid] = r["t_ms"]
                break

    events = []
    for uid, s in by.items():
        cur = None
        held_from = None
        last_attack = None
        min_gap = None
        for r in s:
            if r.get("hp") is not None and r["hp"] <= 0:
                break
            t = r.get("target_id")
            if t in (None, -1, 0):
                t = None
            if t == cur and cur is not None:
                if r.get("action_state") in (ST_RELOAD, ST_SWING):
                    last_attack = r["t_ms"]
                tgt = frames.get(r["t_ms"], {}).get(cur)
                if tgt is not None:
                    g = gap(r, tgt)
                    min_gap = g if min_gap is None else min(min_gap, g)
            elif t is not None and t != cur:
                if cur is not None:
                    d = death.get(cur)
                    voluntary = d is None or r["t_ms"] < d - 100
                    if voluntary and held_from is not None:
                        events.append({
                            "held": (r["t_ms"] - held_from) / 1000.0,
                            "ever_attacked": last_attack is not None,
                            "since_attack": ((r["t_ms"] - last_attack) / 1000.0
                                             if last_attack else None),
                            "min_gap": min_gap,
                        })
                cur = t
                held_from = r["t_ms"]
                last_attack = None
                min_gap = None
    return events


def main():
    paths = sorted(glob.glob(os.path.join(sys.argv[1], "*.tape_trace.jsonl")))
    allev = []
    for p in paths:
        allev += analyse(p)
    n = len(allev)
    never = [e for e in allev if not e["ever_attacked"]]
    ever = [e for e in allev if e["ever_attacked"]]
    print(f"{len(paths)} fights, {n} voluntary target switches\n")
    print(f"  NEVER got to attack the target it abandoned : "
          f"{len(never):5d}  ({len(never)/n*100:.0f}%)")
    print(f"  had attacked it at least once              : "
          f"{len(ever):5d}  ({len(ever)/n*100:.0f}%)")
    print()
    if never:
        held = [e["held"] for e in never]
        gaps = [e["min_gap"] for e in never if e["min_gap"] is not None]
        print("  of those that NEVER attacked it:")
        print(f"     median time spent holding that target : {statistics.median(held):5.2f} s")
        print(f"     median CLOSEST it ever got            : {statistics.median(gaps):5.2f} tiles"
              f"   (contact is <= {REACH})")
        reached = sum(1 for g in gaps if g <= REACH + 1e-9)
        print(f"     got within contact range anyway       : {reached}/{len(gaps)}"
              f"  ({reached/len(gaps)*100:.0f}%)")
    print()
    if ever:
        since = [e["since_attack"] for e in ever]
        print("  of those that HAD attacked it:")
        print(f"     median time since its last swing      : {statistics.median(since):5.2f} s")
        print(f"     switched within 2 s of last swing     : "
              f"{sum(1 for s in since if s <= 2)}/{len(since)}"
              f"  ({sum(1 for s in since if s <= 2)/len(since)*100:.0f}%)")
        print(f"     stalled > 4 s before switching        : "
              f"{sum(1 for s in since if s > 4)}/{len(since)}"
              f"  ({sum(1 for s in since if s > 4)/len(since)*100:.0f}%)")


if __name__ == "__main__":
    main()
