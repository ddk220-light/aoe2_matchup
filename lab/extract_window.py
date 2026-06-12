"""Data dump for a time window from the gRPC CAPTURE (not the .aoe2record).

For ddk220 (owner 2), window [START,END] minutes, lists every military unit
produced: entity_id, type, queued-time, spawn-time, spawn x/y, and the producing
building (nearest same-owner building by position) with its id + x/y. Plus the
MultiQueue commands (queue events) in the window.
"""
import json, os, struct, sys
from collections import defaultdict
import aocref, cade_api_pb2 as pb, decode_state_v2 as D

CAP = "GAME_munq_vs_ddk220_incas_frames_raw.bin"
SCH = D.SCHEMA
ENT = {9, 11, 12, 14}
UNIT = {9, 11, 12}          # mobile units
BUILDING = 14
START_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
END_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 22.0
OWNER = 2                    # ddk220

NAME = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(aocref.__file__),
        "data", "datasets", "100.json"), encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")

VILL = ("villager", "farmer", "lumberjack", "miner", "builder", "forager",
        "fisher", "shepherd", "repairer", "hunter", "gatherer")
def is_mil(name):
    n = name.lower()
    if name.startswith("id"):       # unmapped (wall pieces / effects) -> not a real unit
        return False
    return not (any(k in n for k in VILL) or "flare" in n or "dead" in n
                or "wall" in n or "gate" in n)


def decode_create(p, j, L):
    """At a create, read leading entity fields -> (mt, key, master, owner, x, y)."""
    mt = p[j + 2]
    key = struct.unpack_from("<i", p, j + 3)[0]
    if not (0 < key < 1_000_000) or j + 7 >= L or p[j + 7] != 2:
        return None
    r = D.Reader(p); r.p = j + 7
    f = {}
    for _ in range(10):
        if r.p >= L or p[r.p] != 2:
            break
        r.p += 1
        fld = r.u8()
        fi = SCH.get(mt, {}).get(fld, ("value", False, None))
        try:
            v = D.read_value(r, *fi)
        except Exception:
            break
        f[fld] = v
        if 1 in f and 2 in f and 3 in f and 4 in f:
            break
    if 1 not in f:
        return None
    return mt, key, f.get(1), f.get(2), f.get(3), f.get(4)


def main():
    units = {}        # eid -> dict (all military units, any time)
    buildings = {}    # eid -> (master, owner, x, y)
    mqs = []          # (time_ms, trainId, trainCount, [buildingIds]) for OWNER
    f = open(CAP, "rb")
    frames = 0
    while True:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        ln = struct.unpack("<I", hdr)[0]
        buf = f.read(ln)
        if len(buf) < ln:
            break
        sq = pb.FrameSequence(); sq.ParseFromString(buf)
        for fr in sq.frame:
            t = fr.time
            for c in fr.command:
                if c.WhichOneof("command") == "multiQueue":
                    mq = c.multiQueue
                    if mq.playerId == OWNER:
                        mqs.append((t, mq.trainId, mq.trainCount or 1, list(mq.buildingIds)))
            p = fr.patch
            if not p or len(p) > 500_000:
                continue
            frames += 1
            L = len(p); j = 0
            while j < L - 8:
                if p[j] == 8 and p[j + 1] == 1 and p[j + 2] in ENT:
                    res = decode_create(p, j, L)
                    if res:
                        mt, key, master, owner, x, y = res
                        if mt == BUILDING and owner == OWNER:
                            if key not in buildings:
                                buildings[key] = (master, owner, x, y)
                        elif mt in UNIT and owner == OWNER and master is not None:
                            nme = nm(master)
                            if key not in units and is_mil(nme):
                                units[key] = {"master": master, "name": nme, "x": x, "y": y,
                                              "spawn_ms": t}
                        j += 7; continue
                j += 1
    f.close()

    def nearest_building(x, y):
        if x is None or y is None:
            return None
        best, bd = None, 1e18
        for bid, (bm, bo, bx, by) in buildings.items():
            if bx is None or by is None:
                continue
            d = (bx - x) ** 2 + (by - y) ** 2
            if d < bd:
                bd = d; best = (bid, nm(bm), bx, by, d ** 0.5)
        return best

    lo, hi = START_MIN * 60000, END_MIN * 60000
    win = sorted([(u["spawn_ms"], eid, u) for eid, u in units.items() if lo <= u["spawn_ms"] <= hi])
    print(f"=== ddk220 MILITARY produced {START_MIN}-{END_MIN} min  ({len(win)} units) ===")
    for sms, eid, u in win:
        xy = f"({u['x']:.1f},{u['y']:.1f})" if u["x"] is not None else "?"
        # the queue command that trained it: same type, latest queue before spawn
        qt, qblds = None, []
        for (tt, tid, cnt, blds) in mqs:
            if tt <= sms and nm(tid) == u["name"]:
                qt, qblds = tt, blds
        # producing building = among the queued building set, nearest to spawn xy
        bld = None
        if qblds and u["x"] is not None:
            cand = [(bid, buildings.get(bid)) for bid in qblds if bid in buildings]
            cand = [(bid, b) for bid, b in cand if b and b[2] is not None]
            if cand:
                bid, b = min(cand, key=lambda kv: (kv[1][2]-u["x"])**2 + (kv[1][3]-u["y"])**2)
                bld = (bid, nm(b[0]), b[2], b[3])
        bs = f"{bld[1]} id={bld[0]} @({bld[2]:.1f},{bld[3]:.1f})" if bld else (f"buildings {qblds}" if qblds else "?")
        qd = f"queued {qt/60000:.2f}m, train {(sms-qt)/1000:.0f}s" if qt else "queue ?"
        print(f"  spawn {sms/60000:6.2f}m  id={eid:<6} {u['name']:13} at {xy:>13}  from {bs}   ({qd})")

    print(f"\n=== MultiQueue commands (player 2) in {START_MIN}-{END_MIN} min ===")
    for (tt, tid, cnt, blds) in mqs:
        if lo <= tt <= hi:
            print(f"  {tt/60000:6.2f}m  train={nm(tid):14} count={cnt}  buildings={blds}")
    print(f"\n(decoded {frames} delta frames; {len(buildings)} owner-2 buildings, {len(units)} owner-2 military total)")


if __name__ == "__main__":
    main()
