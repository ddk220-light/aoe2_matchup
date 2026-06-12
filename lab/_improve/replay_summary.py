"""replay_summary.py REPLAY OUT.json -- parse a replay with mgz and dump pairing facts:
player count/names/civs, duration, max action time, DE_QUEUE production counts per unit.
"""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter
import mgz.model

REPLAY = sys.argv[1]
OUT = sys.argv[2]

mt = mgz.model.parse_match(open(REPLAY, "rb"))

players = [{"number": getattr(p, "number", None), "name": p.name,
            "civ": getattr(p, "civilization", None)} for p in mt.players]
dur = getattr(mt, "duration", None)
dur_s = dur.total_seconds() if dur is not None else None

queue = Counter()
queue_by_player = {}
last_action = 0.0
n_actions = 0
for a in mt.actions:
    n_actions += 1
    t = a.timestamp.total_seconds()
    if t > last_action:
        last_action = t
    at = getattr(getattr(a, "type", None), "name", None) or str(getattr(a, "type", ""))
    if at == "DE_QUEUE" and a.player:
        payload = a.payload or {}
        u = payload.get("unit")
        amt = payload.get("amount", 1) or 1
        queue[u] += amt
        queue_by_player.setdefault(a.player.name, Counter())[u] = \
            queue_by_player.setdefault(a.player.name, Counter()).get(u, 0) + amt

out = {
    "replay": REPLAY,
    "n_players": len(players),
    "players": players,
    "duration_s": dur_s,
    "duration_min": (dur_s / 60.0) if dur_s else None,
    "last_action_s": last_action,
    "last_action_min": last_action / 60.0,
    "n_actions": n_actions,
    "queue_total": dict(queue),
    "queue_by_player": {k: dict(v) for k, v in queue_by_player.items()},
}
json.dump(out, open(OUT, "w"), indent=1)
print(json.dumps({k: out[k] for k in ("n_players", "duration_min", "last_action_min")}, indent=1))
print("players:", [(p["name"], p["civ"]) for p in players])
print("queue totals:", queue.most_common(20))
