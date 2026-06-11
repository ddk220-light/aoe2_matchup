"""Cross-check ddk220 MILITARY production in the first 20 min across 3 sources:
  (A) .aoe2record DE_QUEUE commands  (queue time, type, building set)
  (B) gRPC MultiQueue commands       (queue time, type, building set)
  (C) gRPC entity spawns             (spawn time, entity_id, type, building@xy)
Skips villagers. Verifies the queue command matches between record and capture,
and lines each queue up with the unit that actually came out.
"""
import json, os, struct, sys, types
from collections import defaultdict, Counter

# ---- gRPC side ----
sys.path.insert(0, "C:/dev/aoe2/aoe2record/lab")
import aocref, cade_api_pb2 as pb, decode_state_v2 as D
SCH = D.SCHEMA
ENT = {9, 11, 12, 14}; UNIT = {9, 11, 12}; BUILDING = 14
OWNER = 2
LIMIT = 20 * 60000
NAME = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(aocref.__file__),
        "data", "datasets", "100.json"), encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")
VILL = ("villager", "farmer", "lumberjack", "miner", "builder", "forager",
        "fisher", "shepherd", "repairer", "hunter", "gatherer")
def is_mil(name):
    n = name.lower()
    if name.startswith("id"):
        return False
    return not (any(k in n for k in VILL) or "flare" in n or "dead" in n
                or "wall" in n or "gate" in n)

def decode_create(p, j, L):
    mt = p[j + 2]; key = struct.unpack_from("<i", p, j + 3)[0]
    if not (0 < key < 1_000_000) or j + 7 >= L or p[j + 7] != 2:
        return None
    r = D.Reader(p); r.p = j + 7; f = {}
    for _ in range(10):
        if r.p >= L or p[r.p] != 2:
            break
        r.p += 1; fld = r.u8()
        try:
            v = D.read_value(r, *SCH.get(mt, {}).get(fld, ("value", False, None)))
        except Exception:
            break
        f[fld] = v
        if all(k in f for k in (1, 2, 3, 4)):
            break
    return (mt, key, f.get(1), f.get(2), f.get(3), f.get(4)) if 1 in f else None

def grpc_data():
    mq = []; spawns = {}; buildings = {}
    fh = open("GAME_munq_vs_ddk220_incas_frames_raw.bin", "rb")
    while True:
        hdr = fh.read(4)
        if len(hdr) < 4: break
        ln = struct.unpack("<I", hdr)[0]; buf = fh.read(ln)
        if len(buf) < ln: break
        sq = pb.FrameSequence(); sq.ParseFromString(buf)
        for fr in sq.frame:
            t = fr.time
            for c in fr.command:
                if c.WhichOneof("command") == "multiQueue":
                    m = c.multiQueue
                    if m.playerId == OWNER and t <= LIMIT and is_mil(nm(m.trainId)):
                        mq.append((t, nm(m.trainId), list(m.buildingIds)))
            p = fr.patch
            if not p or len(p) > 500_000: continue
            L = len(p); j = 0
            while j < L - 8:
                if p[j] == 8 and p[j + 1] == 1 and p[j + 2] in ENT:
                    res = decode_create(p, j, L)
                    if res:
                        mt, key, master, owner, x, y = res
                        if mt == BUILDING and owner == OWNER and key not in buildings:
                            buildings[key] = (nm(master), x, y)
                        elif mt in UNIT and owner == OWNER and master is not None and t <= LIMIT:
                            if key not in spawns and is_mil(nm(master)):
                                spawns[key] = (t, nm(master), x, y)
                        j += 7; continue
                j += 1
    fh.close()
    return mq, spawns, buildings

# ---- .aoe2record side ----
def record_queues():
    for m in ("flask", "flask_cors", "requests"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.path.insert(0, "C:/dev/aoe2/aoc-mgz-67x")
    import mgz.model
    mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
    out = []
    for a in mt.actions:
        if str(a.type).endswith("DE_QUEUE") and a.player and a.player.name == "ddk220":
            pl = a.payload or {}
            u = pl.get("unit", "?")
            if u and "Villager" not in u:
                ts = a.timestamp.total_seconds()
                if ts <= 1200:
                    for _ in range(pl.get("amount", 1) or 1):
                        out.append((ts, u, pl.get("object_ids", [])))
    return out


def main():
    print("parsing .aoe2record + streaming gRPC capture (first 20 min)...")
    rec = record_queues()
    mq, spawns, buildings = grpc_data()

    print(f"\n=== COUNTS (ddk220 military queued, first 20 min) ===")
    print(f"  .aoe2record DE_QUEUE: {len(rec)}   |  gRPC MultiQueue: {len(mq)}   |  gRPC spawns: {len(spawns)}")
    print(f"  by type  record: {dict(Counter(u for _,u,_ in rec))}")
    print(f"  by type  gRPC  : {dict(Counter(u for _,u,_ in mq))}")
    print(f"  by type  spawns: {dict(Counter(s[1] for s in spawns.values()))}")

    # align record vs gRPC queue commands by sorted (time,type)
    print(f"\n=== QUEUE TIMELINE: .aoe2record  vs  gRPC MultiQueue ===")
    print(f"{'#':>3} {'rec_t':>7} {'rec_type':13} {'rec_bldgs':>16} | {'grpc_t':>7} {'grpc_type':13} {'grpc_bldgs':>16}  match")
    R = sorted(rec); G = sorted(mq)
    n = max(len(R), len(G))
    ok = 0
    for i in range(n):
        r = R[i] if i < len(R) else None
        g = G[i] if i < len(G) else None
        rs = f"{r[0]/60:6.2f}m {r[1]:13} {str(r[2]):>16}" if r else f"{'-':>34}"
        gs = f"{g[0]/60000:6.2f}m {g[1]:13} {str(g[2]):>16}" if g else f"{'-':>34}"
        m = "OK" if (r and g and abs(r[0]-g[0]/1000) < 1.0 and r[1] == g[1] and set(r[2]) == set(g[2])) else "<<"
        if m == "OK": ok += 1
        print(f"{i:3} {rs} | {gs}  {m}")
    print(f"\n  exact-matching queue rows: {ok}/{n}")

    # spawns with building (queue->spawn)
    print(f"\n=== gRPC SPAWNS (when each queued unit came out), first 20 min ===")
    for sms, eid, _x in sorted((s[0], k, s) for k, s in spawns.items()):
        t, name, x, y = spawns[eid]
        qt, qb = None, []
        for (mt_, u, b) in sorted(mq):
            if mt_ <= t and u == name:
                qt, qb = mt_, b
        bld = None
        if qb and x is not None:
            cand = [(bid, buildings[bid]) for bid in qb if bid in buildings and buildings[bid][1] is not None]
            if cand:
                bid, b = min(cand, key=lambda kv: (kv[1][1]-x)**2 + (kv[1][2]-y)**2)
                bld = f"{b[0]} id={bid}"
        qd = f"queued {qt/60000:.2f}m train {(t-qt)/1000:.0f}s" if qt else "queue?"
        print(f"  {t/60000:6.2f}m id={eid:<6} {name:13} @({x:.1f},{y:.1f}) from {bld or qb}  ({qd})")


if __name__ == "__main__":
    main()
