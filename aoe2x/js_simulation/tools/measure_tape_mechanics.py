"""Measure Paladin physics constants from the decoded tapes and test the five
predictions carried over from the Champion calibration."""
import collections
import json
import os
import statistics
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pal_trace")
RATIOS = ["1v1", "2v1", "2v3", "5v3", "6v3"]
TAGS = [t for r in RATIOS for t in (r, f"{r}_r2", f"{r}_r3")]
MASTER = 569
ST_MOVE, ST_RECOVER, ST_SWING = 4, 6, 7


def load(tag):
    by = collections.defaultdict(list)
    with open(f"{OUT}/{tag}.tape_trace.jsonl") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("master") != MASTER:
                continue
            by[row["id"]].append(row)
    for series in by.values():
        series.sort(key=lambda r: r["t_ms"])
    frames = collections.defaultdict(list)
    for series in by.values():
        for row in series:
            frames[row["t_ms"]].append(row)
    return by, dict(sorted(frames.items()))


def cheb(a, b):
    return max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]))


def euclid(a, b):
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def alive(row):
    return (row.get("hp") or 0) > 0


def measure(tag):
    by, frames = load(tag)
    res = {"tag": tag, "units": len(by)}

    # ---- speed: per-frame displacement / dt over sustained motion ---------
    speeds = []
    for series in by.values():
        for i in range(1, len(series)):
            a, b = series[i - 1], series[i]
            dt = (b["t_ms"] - a["t_ms"]) / 1000
            if dt <= 0:
                continue
            d = euclid(a, b)
            if d > 1e-6:
                speeds.append(d / dt)
    res["speed_max"] = max(speeds) if speeds else None
    res["speed_p99"] = (statistics.quantiles(speeds, n=100)[98]
                        if len(speeds) > 100 else None)

    # ---- separation: enemy vs ally, Chebyshev centre distance -------------
    enemy_sep, ally_sep = [], []
    for t, rows in frames.items():
        live = [r for r in rows if alive(r)]
        for i in range(len(live)):
            for j in range(i + 1, len(live)):
                a, b = live[i], live[j]
                (enemy_sep if a["owner"] != b["owner"] else ally_sep).append(
                    round(cheb(a, b), 4))
    res["enemy_sep_min"] = min(enemy_sep) if enemy_sep else None
    res["ally_sep_min"] = min(ally_sep) if ally_sep else None
    res["enemy_sep_hist"] = collections.Counter(
        round(v, 3) for v in enemy_sep if v < 0.75).most_common(8)
    res["ally_sep_hist"] = collections.Counter(
        round(v, 3) for v in ally_sep if v < 0.75).most_common(8)

    # ---- windup: swing start -> victim HP drop ----------------------------
    hp_drops = collections.defaultdict(list)
    for series in by.values():
        for i in range(1, len(series)):
            if (series[i].get("hp") or 0) < (series[i - 1].get("hp") or 0):
                hp_drops[series[i]["id"]].append(series[i]["t_ms"] / 1000)

    windups, cadence, reach = [], [], []
    for uid, series in by.items():
        swing_starts = []
        for i in range(1, len(series)):
            if (series[i].get("action_state") == ST_SWING
                    and series[i - 1].get("action_state") != ST_SWING):
                swing_starts.append((series[i]["t_ms"] / 1000,
                                     series[i].get("target_id")))
        for k in range(1, len(swing_starts)):
            cadence.append(round(swing_starts[k][0] - swing_starts[k - 1][0], 4))
        for t0, target in swing_starts:
            drops = hp_drops.get(target, [])
            after = [d for d in drops if t0 < d <= t0 + 2.5]
            if after:
                windups.append(round(after[0] - t0, 4))
        # attack envelope: separation at the moment of the swing
        for i in range(1, len(series)):
            if (series[i].get("action_state") == ST_SWING
                    and series[i - 1].get("action_state") != ST_SWING):
                tgt = series[i].get("target_id")
                peer = next((r for r in frames[series[i]["t_ms"]]
                             if r["id"] == tgt), None)
                if peer:
                    reach.append(round(cheb(series[i], peer), 4))
    res["windup"] = summarize(windups)
    res["cadence"] = summarize(cadence)
    res["swing_reach"] = summarize(reach)

    # ---- acquisition: first non-null target after the start command -------
    acquire = []
    for series in by.values():
        first = next((r for r in series
                      if r.get("target_id") not in (None, -1)), None)
        if first:
            acquire.append(round(first["t_ms"] / 1000, 4))
    res["first_target_t"] = summarize(acquire)

    # ---- fight span -------------------------------------------------------
    deaths = []
    for series in by.values():
        died = next((r["t_ms"] / 1000 for r in series
                     if (r.get("hp") or 0) <= 0), None)
        if died:
            deaths.append(died)
    res["deaths"] = sorted(round(d, 3) for d in deaths)
    res["path_len_max"] = round(max(
        sum(euclid(s[i - 1], s[i]) for i in range(1, len(s)))
        for s in by.values()), 3)
    return res


def summarize(values):
    if not values:
        return None
    return {"n": len(values), "min": min(values),
            "median": round(statistics.median(values), 4), "max": max(values)}


if __name__ == "__main__":
    tags = sys.argv[1:] or TAGS
    out = [measure(t) for t in tags]
    print(json.dumps(out, indent=1))
    with open(os.path.join(OUT, "pal_mechanics.json"), "w") as fh:
        json.dump(out, fh, indent=1)
