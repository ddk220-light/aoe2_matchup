"""Per-run mechanic extraction from the full-rate tape traces.

Emits one JSON per run plus an aggregated min/median/max view per ratio.
Read-only; writes only into the scratchpad.
"""
import collections
import json
import math
import os
import statistics
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
TRUTH = (r"D:\AI\aoe2_matchup\aoe2x\js_simulation\calibration\fixtures"
         r"\champion_basics.json")
COMMAND_T = 0.2          # both "game" commands land here in every run
RATIOS = ["1v1", "2v1", "2v3", "5v3", "6v3"]
TAGS = {r: [r, f"{r}_r2", f"{r}_r3"] for r in RATIOS}

# Tape Action.state values, inferred from the 1v1 lifecycle and confirmed on
# every ratio: 4 = moving to an acquired target, 7 = attack animation playing,
# 6 = animation finished / waiting out the reload, 2/1/3 = target lost, idle,
# fresh move order.
ST_MOVE, ST_SWING, ST_RECOVER = 4, 7, 6


def load(tag):
    rows = [json.loads(line) for line in open(f"{OUT}/{tag}.tape_trace.jsonl")]
    by = collections.defaultdict(list)
    for row in rows:
        by[row["id"]].append(row)
    for series in by.values():
        series.sort(key=lambda r: r["t_ms"])
    frames = collections.defaultdict(list)
    for row in rows:
        frames[row["t_ms"]].append(row)
    return by, dict(sorted(frames.items()))


def truth_run(tag):
    truth = json.load(open(TRUTH))
    ratio = tag.split("_")[0]
    for run in truth["ratios"][ratio]["runs"]:
        if run["tag"] == tag:
            return run
    raise KeyError(tag)


def transitions(series, key):
    out = []
    for i in range(1, len(series)):
        if series[i].get(key) != series[i - 1].get(key):
            out.append((series[i]["t_ms"] / 1000, series[i].get(key)))
    return out


def alive(row):
    return (row.get("hp") or 0) > 0


def analyse(tag):
    by, frames = load(tag)
    run = truth_run(tag)
    damage = run["damage_events"]
    result = {"tag": tag, "units": {}, "geometry": {}, "fight": {}}

    # ---- per unit ---------------------------------------------------------
    for uid, series in by.items():
        first_target = next(
            (r for r in series if r.get("target_id") not in (None, -1)), None)
        moving = [i for i in range(1, len(series))
                  if (series[i]["x"], series[i]["y"])
                  != (series[i - 1]["x"], series[i - 1]["y"])]
        swings = [series[i]["t_ms"] / 1000 for i in range(1, len(series))
                  if series[i].get("action_state") == ST_SWING
                  and series[i - 1].get("action_state") != ST_SWING]
        recovers = [series[i]["t_ms"] / 1000 for i in range(1, len(series))
                    if series[i].get("action_state") == ST_RECOVER
                    and series[i - 1].get("action_state") != ST_RECOVER]
        # animation length: each swing start paired with the next recover
        animation = []
        for start in swings:
            end = next((r for r in recovers if r > start), None)
            if end is not None:
                animation.append(round(end - start, 4))
        # windup: swing start -> this unit's next landed hit
        my_hits = [d["t"] for d in damage if d["attacker"] == uid]
        windup = []
        for start in swings:
            hit = next((h for h in my_hits if h > start), None)
            if hit is not None and hit - start < 1.2:
                windup.append(round(hit - start, 4))
        # path length and speed samples
        path = 0.0
        steps = []
        for i in range(1, len(series)):
            step = math.hypot(series[i]["x"] - series[i - 1]["x"],
                              series[i]["y"] - series[i - 1]["y"])
            dt = (series[i]["t_ms"] - series[i - 1]["t_ms"]) / 1000
            path += step
            if step > 1e-9 and dt > 0:
                steps.append(step / dt)
        target_timeline = [(t, v) for t, v in transitions(series, "target_id")
                           if v not in (None,)]
        # blocked frames: has a move-state action but did not move
        blocked = 0
        for i in range(1, len(series)):
            if series[i].get("action_state") == ST_MOVE and alive(series[i]):
                if (series[i]["x"], series[i]["y"]) == (
                        series[i - 1]["x"], series[i - 1]["y"]):
                    blocked += 1
        death = next((r["t_ms"] / 1000 for r in series if not alive(r)), None)
        result["units"][uid] = {
            "owner": series[0]["owner"],
            "order_latency": (round(first_target["t_ms"] / 1000 - COMMAND_T, 4)
                              if first_target else None),
            "move_start": (round(series[moving[0] - 1]["t_ms"] / 1000, 4)
                           if moving else None),
            "move_end": (round(series[moving[-1]]["t_ms"] / 1000, 4)
                         if moving else None),
            "path_len": round(path, 4),
            "speed_samples": [round(s, 6) for s in steps[:4]],
            "speed_median": round(statistics.median(steps), 6) if steps else None,
            "swings": [round(s, 4) for s in swings],
            "cadence": [round(swings[i] - swings[i - 1], 4)
                        for i in range(1, len(swings))],
            "animation": animation,
            "windup": windup,
            "targets": [(round(t, 4), v) for t, v in target_timeline],
            "retargets": max(0, len({v for _, v in target_timeline
                                     if v not in (None, -1)}) - 1),
            "blocked_frames": blocked,
            "hits_landed": len(my_hits),
            "death": death,
        }

    # ---- geometry ---------------------------------------------------------
    enemy_cheb, enemy_euclid, ally_cheb, ally_euclid, swing_reach = [], [], [], [], []
    for t, rows in frames.items():
        live = [r for r in rows if alive(r)]
        pos = {r["id"]: r for r in live}
        for i in range(len(live)):
            for j in range(i + 1, len(live)):
                p, q = live[i], live[j]
                dx, dy = abs(p["x"] - q["x"]), abs(p["y"] - q["y"])
                if p["owner"] == q["owner"]:
                    ally_cheb.append(max(dx, dy))
                    ally_euclid.append(math.hypot(dx, dy))
                else:
                    enemy_cheb.append(max(dx, dy))
                    enemy_euclid.append(math.hypot(dx, dy))
        for r in live:
            if r.get("action_state") != ST_SWING:
                continue
            target = pos.get(r.get("target_id"))
            if target:
                swing_reach.append(max(abs(target["x"] - r["x"]),
                                       abs(target["y"] - r["y"])))

    def band(values):
        if not values:
            return None
        values = sorted(values)
        return {
            "min": round(values[0], 4),
            "p01": round(values[len(values) // 100], 4),
            "median": round(statistics.median(values), 4),
            "max": round(values[-1], 4),
            "n": len(values),
        }

    result["geometry"] = {
        "enemy_chebyshev": band(enemy_cheb),
        "enemy_euclid": band(enemy_euclid),
        "ally_chebyshev": band(ally_cheb),
        "ally_euclid": band(ally_euclid),
        "swing_reach_chebyshev": band(swing_reach),
    }

    # ---- fight ------------------------------------------------------------
    kills = [d["t"] for d in damage if d.get("kill")]
    summary = run["summary"]
    result["fight"] = {
        "first_damage": damage[0]["t"] - COMMAND_T if damage else None,
        "last_kill": (max(kills) - COMMAND_T) if kills else None,
        "combat_span": (max(kills) - damage[0]["t"]) if kills and damage else None,
        "damage_events": len(damage),
        "winner": summary["outcome"],
        "winner_hp": max(summary["sides"]["side2"]["hp_remaining"],
                         summary["sides"]["side3"]["hp_remaining"]),
        "survivors": {k: v["survivors"] for k, v in summary["sides"].items()},
    }
    return result


def main():
    everything = {}
    for ratio, tags in TAGS.items():
        everything[ratio] = [analyse(tag) for tag in tags]
    with open(f"{OUT}/tape_mechanics.json", "w") as out:
        json.dump(everything, out, indent=1)

    def pool(ratio, extract):
        vals = []
        for run in everything[ratio]:
            vals.extend(extract(run))
        return vals

    def show(name, values, unit=""):
        if not values:
            print(f"  {name:26s} n/a")
            return
        values = sorted(values)
        print(f"  {name:26s} min {values[0]:8.4f}  median "
              f"{statistics.median(values):8.4f}  max {values[-1]:8.4f}  "
              f"n={len(values)}{unit}")

    for ratio in RATIOS:
        print(f"\n================ {ratio} (3 runs) ================")
        show("order latency (s)", pool(ratio, lambda r: [
            u["order_latency"] for u in r["units"].values()
            if u["order_latency"] is not None]))
        show("speed (tiles/s)", pool(ratio, lambda r: [
            u["speed_median"] for u in r["units"].values()
            if u["speed_median"]]))
        show("swing cadence (s)", pool(ratio, lambda r: [
            c for u in r["units"].values() for c in u["cadence"]]))
        show("animation length (s)", pool(ratio, lambda r: [
            a for u in r["units"].values() for a in u["animation"]]))
        show("windup swing->hit (s)", pool(ratio, lambda r: [
            w for u in r["units"].values() for w in u["windup"]]))
        show("retargets per unit", pool(ratio, lambda r: [
            u["retargets"] for u in r["units"].values()]))
        show("first damage (s)", pool(ratio, lambda r: [r["fight"]["first_damage"]]))
        show("last kill (s)", pool(ratio, lambda r: [r["fight"]["last_kill"]]))
        show("combat span (s)", pool(ratio, lambda r: [r["fight"]["combat_span"]]))
        show("enemy min chebyshev", pool(ratio, lambda r: [
            r["geometry"]["enemy_chebyshev"]["min"]]))
        show("ally min chebyshev", pool(ratio, lambda r: [
            r["geometry"]["ally_chebyshev"]["min"]]
            if r["geometry"]["ally_chebyshev"] else []))
        show("ally min euclid", pool(ratio, lambda r: [
            r["geometry"]["ally_euclid"]["min"]]
            if r["geometry"]["ally_euclid"] else []))
        show("swing reach cheb max", pool(ratio, lambda r: [
            r["geometry"]["swing_reach_chebyshev"]["max"]]
            if r["geometry"]["swing_reach_chebyshev"] else []))
        print("  winners:", [r["fight"]["winner"] for r in everything[ratio]],
              " winner HP:", [r["fight"]["winner_hp"] for r in everything[ratio]],
              " damage events:", [r["fight"]["damage_events"]
                                  for r in everything[ratio]])


if __name__ == "__main__":
    main()
