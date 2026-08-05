"""Who targets whom, and every retarget, tape vs sim -- champion_vs_paladin 6v3."""
import collections
import json
import sys

TAGS = ["6v3", "6v3_r2", "6v3_r3"]
CHAMPION, PALADIN = 567, 569
NAME = {CHAMPION: "C", PALADIN: "P"}


def load(path, tape):
    by = collections.defaultdict(list)
    for line in open(path):
        row = json.loads(line)
        if tape and row.get("master") not in (CHAMPION, PALADIN):
            continue
        by[row["id"]].append(row)
    for series in by.values():
        series.sort(key=lambda r: r["t_ms"])
    return by


def segments(series, tape):
    """Ordered [(t_start, target)] whenever the unit's target changes."""
    out = []
    for row in series:
        if tape:
            target = row.get("target_id")
            if target in (None, -1):
                target = None
        else:
            target = row.get("pursuit") if row.get("pursuit") is not None else row.get("engaged")
        if (row.get("hp") or 0) <= 0:
            break
        if not out or out[-1][1] != target:
            out.append((row["t_ms"] / 1000, target))
    return [(t, v) for t, v in out if v is not None]


def describe(by, tape):
    rows = {}
    for uid, series in sorted(by.items()):
        segs = segments(series, tape)
        rows[uid] = {
            "owner": series[0]["owner"],
            "segments": segs,
            "targets": [v for _, v in segs],
            "retargets": max(0, len(segs) - 1),
        }
    return rows


print("champion_vs_paladin 6v3 -- target assignment and retargets")
print("owner 2 = Champion (6), owner 3 = Paladin (3)\n")

sim = describe(load("cvp_trace/6v3.sim_trace.jsonl", False), False)
tapes = {t: describe(load(f"cvp_trace/{t}.tape_trace.jsonl", True), True) for t in TAGS}

units = sorted(sim)
print(f"{'unit':>6} {'side':4} {'source':8} {'retgt':>5}  target sequence (t=first acquire)")
for uid in units:
    for label, rows in [(t, tapes[t]) for t in TAGS] + [("SIM", sim)]:
        r = rows.get(uid)
        if not r:
            print(f"{uid:>6} {'':4} {label:8} {'-':>5}  (absent)")
            continue
        side = "C" if r["owner"] == 2 else "P"
        seq = " -> ".join(f"{v}@{t:.1f}" for t, v in r["segments"][:8])
        print(f"{uid:>6} {side:4} {label:8} {r['retargets']:5d}  {seq}")
    print()

print("\n=== retarget totals ===")
for label, rows in [(t, tapes[t]) for t in TAGS] + [("SIM", sim)]:
    champs = sum(v["retargets"] for v in rows.values() if v["owner"] == 2)
    pals = sum(v["retargets"] for v in rows.values() if v["owner"] == 3)
    print(f"  {label:8} champions {champs:3d}   paladins {pals:3d}")

print("\n=== how many champions ever attacked each paladin ===")
for label, rows in [(t, tapes[t]) for t in TAGS] + [("SIM", sim)]:
    counts = collections.Counter()
    for uid, r in rows.items():
        if r["owner"] != 2:
            continue
        for t in set(r["targets"]):
            counts[t] += 1
    print(f"  {label:8} {dict(sorted(counts.items()))}")

print("\n=== which paladin did each champion attack FIRST ===")
for label, rows in [(t, tapes[t]) for t in TAGS] + [("SIM", sim)]:
    first = {uid: (r["segments"][0][1] if r["segments"] else None)
             for uid, r in sorted(rows.items()) if r["owner"] == 2}
    print(f"  {label:8} {first}")
