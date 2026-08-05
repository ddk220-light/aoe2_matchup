"""Side-by-side tape-vs-sim mechanic comparison for one or all ratios.

Both sides go through the same metric extractor so the numbers are comparable.
Tape column shows min/median/max over the ratio's three authorized runs.
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
COMMAND_T = 0.2
RATIOS = ["1v1", "2v1", "2v3", "5v3", "6v3"]
ST_SWING, ST_RECOVER = 7, 6


def series_of(path, time_key, sort_key):
    rows = [json.loads(line) for line in open(path)]
    by = collections.defaultdict(list)
    for row in rows:
        by[row["id"]].append(row)
    for value in by.values():
        value.sort(key=lambda r: r[sort_key])
    frames = collections.defaultdict(list)
    for row in rows:
        frames[row[time_key]].append(row)
    return by, dict(sorted(frames.items()))


def is_alive(row):
    if "alive" in row:
        return bool(row["alive"])
    return (row.get("hp") or 0) > 0


def swinging(row):
    """True while the unit's attack animation is playing."""
    if "action_state" in row:                 # tape
        return row.get("action_state") == ST_SWING
    return row.get("action") == "attacking"    # sim


def metrics(by, frames, damage_events, time_scale):
    """damage_events: list of dicts with t (seconds), attacker, victim, kill."""
    out = collections.defaultdict(list)
    deaths = {}
    for uid, rows in by.items():
        dead = next((r for r in rows if not is_alive(r)), None)
        if dead:
            deaths[uid] = dead[time_scale[0]] * time_scale[1]

    for uid, rows in by.items():
        def t(row):
            return row[time_scale[0]] * time_scale[1]

        first_target = next(
            (r for r in rows if (r.get("target_id") if "target_id" in r
                                 else r.get("pursuit")) not in (None, -1)), None)
        if first_target is not None:
            out["order_latency"].append(t(first_target) - (
                COMMAND_T if "action_state" in rows[0] else 0.0))

        moving = [i for i in range(1, len(rows))
                  if (rows[i]["x"], rows[i]["y"]) != (rows[i - 1]["x"], rows[i - 1]["y"])]
        if moving:
            out["move_start"].append(t(rows[moving[0] - 1]))
            out["move_end"].append(t(rows[moving[-1]]))
            path = sum(math.hypot(rows[i]["x"] - rows[i - 1]["x"],
                                  rows[i]["y"] - rows[i - 1]["y"])
                       for i in range(1, len(rows)))
            out["path_len"].append(path)
            speeds = []
            for i in moving:
                step = math.hypot(rows[i]["x"] - rows[i - 1]["x"],
                                  rows[i]["y"] - rows[i - 1]["y"])
                dt = t(rows[i]) - t(rows[i - 1])
                if dt > 0:
                    speeds.append(step / dt)
            if speeds:
                out["speed"].append(statistics.median(speeds))

        swings = [t(rows[i]) for i in range(1, len(rows))
                  if swinging(rows[i]) and not swinging(rows[i - 1])]
        ends = [t(rows[i]) for i in range(1, len(rows))
                if not swinging(rows[i]) and swinging(rows[i - 1])]
        for i in range(1, len(swings)):
            out["cadence"].append(swings[i] - swings[i - 1])
        for start in swings:
            end = next((e for e in ends if e > start), None)
            if end is not None and end - start < 3.0:
                out["animation"].append(end - start)
        my_hits = [d["t"] for d in damage_events if d["attacker"] == uid]
        for start in swings:
            hit = next((h for h in my_hits if h > start - 1e-9), None)
            if hit is not None and hit - start < 1.2:
                out["windup"].append(hit - start)
        out["hits"].append(len(my_hits))

    enemy_cheb, ally_cheb, ally_euclid, reach = [], [], [], []
    for _, rows in frames.items():
        live = [r for r in rows if is_alive(r)]
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
        for r in live:
            if not swinging(r):
                continue
            tid = r.get("target_id") if "target_id" in r else r.get("attack")
            target = pos.get(tid)
            if target:
                reach.append(max(abs(target["x"] - r["x"]),
                                 abs(target["y"] - r["y"])))
    if enemy_cheb:
        out["enemy_min_cheb"].append(min(enemy_cheb))
    if ally_cheb:
        out["ally_min_cheb"].append(min(ally_cheb))
        out["ally_min_euclid"].append(min(ally_euclid))
    if reach:
        out["reach_max_cheb"].append(max(reach))

    if damage_events:
        base = COMMAND_T if "action_state" in next(iter(by.values()))[0] else 0.0
        out["first_damage"].append(damage_events[0]["t"] - base)
        kills = [d["t"] for d in damage_events if d.get("kill")]
        if kills:
            out["last_kill"].append(max(kills) - base)
            out["combat_span"].append(max(kills) - damage_events[0]["t"])
    return out


def tape_metrics(ratio):
    truth = json.load(open(TRUTH))
    pooled = collections.defaultdict(list)
    per_run = []
    for run in truth["ratios"][ratio]["runs"]:
        tag = run["tag"]
        by, frames = series_of(f"{OUT}/{tag}.tape_trace.jsonl", "t_ms", "t_ms")
        damage = [{"t": d["t"], "attacker": d["attacker"], "victim": d["victim"],
                   "kill": d.get("kill", False)} for d in run["damage_events"]]
        m = metrics(by, frames, damage, ("t_ms", 0.001))
        per_run.append((tag, run))
        for k, v in m.items():
            pooled[k].extend(v)
    return pooled, per_run


def sim_metrics(ratio):
    path = f"{OUT}/{ratio}.sim_trace.jsonl"
    if not os.path.exists(path):
        return None
    by, frames = series_of(path, "t_ms", "tick")
    events = json.load(open(f"{OUT}/{ratio}.sim_events.json"))
    damage = [{"t": e["tick"] / 60.0, "attacker": e["actorId"],
               "victim": e["targetId"], "kill": e.get("hpAfter") == 0}
              for e in events if e["type"] == "damage"]
    return metrics(by, frames, damage, ("tick", 1 / 60.0)), damage


def band(values):
    if not values:
        return "        --                  "
    values = sorted(values)
    return (f"{values[0]:8.3f} /{statistics.median(values):8.3f} /"
            f"{values[-1]:8.3f}")


def one(values):
    if not values:
        return "     --   "
    values = sorted(values)
    if len(values) == 1:
        return f"{values[0]:10.3f}"
    return f"{values[0]:.3f}/{statistics.median(values):.3f}/{values[-1]:.3f}"


ROWS = [
    ("order latency (s)", "order_latency"),
    ("move start (s)", "move_start"),
    ("move end (s)", "move_end"),
    ("path length (tiles)", "path_len"),
    ("speed (tiles/s)", "speed"),
    ("swing cadence (s)", "cadence"),
    ("animation length (s)", "animation"),
    ("windup swing->hit (s)", "windup"),
    ("first damage (s)", "first_damage"),
    ("last kill (s)", "last_kill"),
    ("combat span (s)", "combat_span"),
    ("enemy min chebyshev", "enemy_min_cheb"),
    ("ally min chebyshev", "ally_min_cheb"),
    ("ally min euclid", "ally_min_euclid"),
    ("reach max chebyshev", "reach_max_cheb"),
]


def report(ratio):
    tape, per_run = tape_metrics(ratio)
    sim = sim_metrics(ratio)
    print(f"\n=========== {ratio} ===========")
    print(f"{'metric':24s} | {'TAPE  min / median / max':28s} | "
          f"{'SIM  min / median / max':28s}")
    print("-" * 90)
    for label, key in ROWS:
        s = band(sim[0][key]) if sim else "   (no sim trace)   "
        print(f"{label:24s} | {band(tape[key]):28s} | {s:28s}")
    tw = [r["summary"]["outcome"] for _, r in per_run]
    th = [max(r["summary"]["sides"]["side2"]["hp_remaining"],
              r["summary"]["sides"]["side3"]["hp_remaining"]) for _, r in per_run]
    print(f"{'winner':24s} | {str(tw):28s} | ", end="")
    if sim:
        print(f"owner-based (see runner)")
    else:
        print("--")
    print(f"{'winner HP':24s} | {str(th):28s} |")


if __name__ == "__main__":
    for ratio in (sys.argv[1:] or RATIOS):
        report(ratio)
