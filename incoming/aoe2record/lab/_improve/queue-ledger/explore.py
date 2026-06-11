"""Explore raw actions relevant to the production ledger."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger"
sys.path[:0] = [WS, "C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
from collections import Counter, defaultdict
import mgz.model

key = sys.argv[1] if len(sys.argv) > 1 else "g0"
REPLAYS = {
    "g0": "C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
    "train": r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
}
mt = mgz.model.parse_match(open(REPLAYS[key], "rb"))

print("PLAYERS:", [(p.number, p.name, p.civilization) for p in mt.players])
print("multiqueue flag:", mt.multiqueue)

# All RESEARCH actions with payload
print("\n--- RESEARCH actions ---")
for a in mt.actions:
    at = str(a.type).replace("Action.", "")
    if at == "RESEARCH":
        pl = a.payload or {}
        print(f"{a.timestamp.total_seconds():8.1f} {a.player.name if a.player else '?':12} "
              f"tech={pl.get('technology')!r} ids={pl.get('object_ids')} extra={ {k:v for k,v in pl.items() if k not in ('technology','object_ids')} }")

print("\n--- DE_QUEUE unit token counts ---")
cnt = Counter()
amt_dist = Counter()
for a in mt.actions:
    at = str(a.type).replace("Action.", "")
    if at == "DE_QUEUE":
        pl = a.payload or {}
        cnt[(a.player.name, (pl.get('unit') or '').lower().replace(' ', ''))] += pl.get('amount', 1) or 1
        amt_dist[pl.get('amount')] += 1
        if len(pl.get('object_ids') or []) > 1:
            pass
for k, v in sorted(cnt.items()):
    print(f"  {k[0]:12} {k[1]:22} {v}")
print("amount distribution:", dict(amt_dist))

print("\n--- Unqueue orders ---")
uq = Counter()
for a in mt.actions:
    pl = a.payload or {}
    if pl.get("order") == "Unqueue":
        uq[a.player.name] += 1
print(dict(uq))

# orders present
print("\n--- payload 'order' values ---")
print(Counter(pl.get('order') for a in mt.actions if (pl := a.payload or {}).get('order')))

# GAME COMMANDS that might matter (DE_QUEUE multi-building)
print("\n--- DE_QUEUE with multiple buildings ---")
nmulti = 0
for a in mt.actions:
    at = str(a.type).replace("Action.", "")
    if at == "DE_QUEUE":
        pl = a.payload or {}
        ids = pl.get('object_ids') or []
        if len(ids) > 1:
            nmulti += 1
            if nmulti <= 12:
                print(f"{a.timestamp.total_seconds():8.1f} {a.player.name:12} unit={pl.get('unit')} amount={pl.get('amount')} ids={ids}")
print("total multi-building DE_QUEUE:", nmulti)
