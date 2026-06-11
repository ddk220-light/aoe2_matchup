"""munq (player 1) MILITARY, minutes 0-20: queue -> per-building FIFO production
simulation -> does the PREDICTED creation time match the ACTUAL spawn time (gRPC)?

  (A) .aoe2record: DE_QUEUE (military) + Unqueue commands -> per-building queues
  (B) FIFO sim:   load-balance multiqueue, serial completion = max(queue,prev)+train,
                  apply unqueue (remove slot)  -> predicted spawn time per unit
  (C) gRPC capture: actual entity creates (type, spawn_ms, x/y -> building)
  -> match predicted vs actual creation time, per unit.
"""
import json, os, re, struct, sys, types
from collections import defaultdict
sys.path.insert(0, "C:/dev/aoe2/aoe2record/lab")
import aocref, cade_api_pb2 as pb, decode_state_v2 as D

CAP = "GAME_persp1_munqonly.bin"     # munq is complete here
OWNER = 1
PLAYER = "munq"
LIMIT = 20 * 60000
NAME = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(aocref.__file__),
        "data", "datasets", "100.json"), encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")
def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
VILL = ("villager", "farmer", "lumberjack", "miner", "builder", "forager",
        "fisher", "shepherd", "repairer", "hunter")
def is_mil(name):
    n = name.lower()
    return not (name.startswith("id") or any(k in n for k in VILL)
                or "flare" in n or "dead" in n or "wall" in n or "gate" in n)

# train times (DB base)
TT = json.load(open("C:/dev/aoe2/aoe2record/visualizer/train_times.json"))["base"]
def train(name):
    return TT.get(norm(name)) or {"skirmisher": 22, "archer": 35, "militia": 21,
        "knight": 30, "hussitewagon": 30, "trebuchet": 50, "monk": 51}.get(norm(name), 30)


def record_cmds():
    for m in ("flask", "flask_cors", "requests"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.path.insert(0, "C:/dev/aoe2/aoc-mgz-67x")
    import mgz.model
    mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
    queues, unqs = [], []
    for a in mt.actions:
        if not a.player or a.player.name != PLAYER:
            continue
        p = a.payload or {}
        t = a.timestamp.total_seconds()
        if t > 1200:
            continue
        at = str(a.type).replace("Action.", "")
        if at.endswith("DE_QUEUE"):
            u = p.get("unit", "?")
            if u and "Villager" not in u:
                for _ in range(p.get("amount", 1) or 1):
                    queues.append((t, u, list(p.get("object_ids", []))))
        elif p.get("order") == "Unqueue":
            b = [(o >> 8 if o >= 1_000_000 else o) for o in p.get("object_ids", [])]
            unqs.append((t, b[0] if b else None, p.get("slot_id")))
    return sorted(queues), sorted(unqs)


def fifo_sim(queues, unqs):
    """Per-building FIFO with multiqueue load-balancing + unqueue. Returns
    predicted [(spawn_t, type, building)] sorted by spawn time."""
    free = defaultdict(float)         # building -> time queue goes idle
    pending = defaultdict(list)       # building -> [(complete_t, type)] not yet spawned
    # interleave queue + unqueue by time
    events = sorted([(t, "q", u, b) for t, u, b in queues] +
                    [(t, "x", bld, slot) for t, bld, slot in unqs])
    out = []
    for ev in events:
        if ev[1] == "q":
            _, _, u, blds = ev; t = ev[0]
            if not blds:
                continue
            b = min(blds, key=lambda bb: max(free[bb], t))    # least-loaded
            start = max(free[b], t)
            done = start + train(u)
            free[b] = done
            pending[b].append([done, u])
            out.append((done, u, b))
        else:  # unqueue: remove slot-th pending unit from that building
            _, _, bld, slot = ev
            if bld in pending and pending[bld]:
                idx = slot if (isinstance(slot, int) and slot < len(pending[bld])) else -1
                rm = pending[bld].pop(idx)
                # remove from out (the matching predicted spawn)
                for k in range(len(out) - 1, -1, -1):
                    if out[k][2] == bld and out[k][0] == rm[0] and out[k][1] == rm[1]:
                        out.pop(k); break
    return sorted(out)


def grpc_spawns():
    spawns = {}; buildings = {}
    fh = open(CAP, "rb")
    while True:
        hdr = fh.read(4)
        if len(hdr) < 4: break
        ln = struct.unpack("<I", hdr)[0]; buf = fh.read(ln)
        if len(buf) < ln: break
        sq = pb.FrameSequence(); sq.ParseFromString(buf)
        for fr in sq.frame:
            t = fr.time; p = fr.patch
            if not p or len(p) > 500_000: continue
            L = len(p); j = 0
            while j < L - 8:
                if p[j] == 8 and p[j + 1] == 1 and p[j + 2] in (9, 11, 12, 14):
                    mt = p[j + 2]; key = struct.unpack_from("<i", p, j + 3)[0]
                    if 0 < key < 1_000_000 and p[j + 7] == 2:
                        r = D.Reader(p); r.p = j + 7; f = {}
                        for _ in range(6):
                            if r.p >= L or p[r.p] != 2: break
                            r.p += 1; fld = r.u8()
                            try: v = D.read_value(r, *D.SCHEMA.get(mt, {}).get(fld, ("value", False, None)))
                            except Exception: break
                            f[fld] = v
                            if all(k in f for k in (1, 2, 3, 4)): break
                        ow = f.get(2)
                        if mt == 14 and ow == OWNER and key not in buildings:
                            buildings[key] = (nm(f.get(1)), f.get(3), f.get(4))
                        elif mt in (9, 11, 12) and ow == OWNER and 1 in f and t <= LIMIT:
                            if key not in spawns and is_mil(nm(f[1])):
                                spawns[key] = (t, nm(f[1]), f.get(3), f.get(4))
                        j += 7; continue
                j += 1
    fh.close()
    return spawns, buildings


def main():
    queues, unqs = record_cmds()
    print(f"{PLAYER} military, 0-20min: {len(queues)} DE_QUEUE, {len(unqs)} Unqueue")
    pred = fifo_sim(queues, unqs)
    pred = [x for x in pred if x[0] <= 1200]
    spawns, buildings = grpc_spawns()
    print(f"FIFO predicts {len(pred)} spawns <=20min | gRPC actual creates: {len(spawns)}")

    # actual spawns sorted, attribute to building by nearest pos
    def bld_of(x, y):
        if x is None: return None
        c = [(bid, b) for bid, b in buildings.items() if b[1] is not None]
        if not c: return None
        bid, b = min(c, key=lambda kv: (kv[1][1]-x)**2 + (kv[1][2]-y)**2)
        return bid, b[0]
    actual = sorted((t / 1000.0, nm_, bld_of(x, y)) for t, nm_, x, y in spawns.values())

    # match predicted vs actual per TYPE in time order
    print(f"\n{'#':>3} {'type':13} | {'pred_spawn':>10} | {'actual_spawn':>12} | {'diff':>6} | building")
    from collections import defaultdict as dd
    pa = dd(list); aa = dd(list)
    for t, u, b in pred: pa[norm(u)].append((t, b))
    for t, u, bb in actual: aa[norm(u)].append((t, bb))
    diffs = []
    for ty in sorted(set(pa) | set(aa), key=lambda k: -(len(pa.get(k, []))+len(aa.get(k, [])))):
        P = sorted(pa.get(ty, [])); A = sorted(aa.get(ty, []))
        for i in range(max(len(P), len(A))):
            ps = P[i][0] if i < len(P) else None
            as_ = A[i][0] if i < len(A) else None
            d = f"{as_-ps:+.0f}s" if (ps is not None and as_ is not None) else "-"  # seconds
            if ps is not None and as_ is not None: diffs.append(abs(as_-ps))
            bld = (A[i][1] if i < len(A) and A[i][1] else (P[i][1] if i < len(P) else "?"))
            bn = buildings.get(bld[0] if isinstance(bld, tuple) else bld, ("?",))[0] if bld else "?"
            pss = f"{ps/60:.2f}m" if ps is not None else "-"
            ass = f"{as_/60:.2f}m" if as_ is not None else "-"
            print(f"{i:3} {ty:13.13} | {pss:>10} | {ass:>12} | {d:>6} | {bn}")
    if diffs:
        diffs.sort()
        print(f"\nmatched {len(diffs)} units | median |diff|={diffs[len(diffs)//2]:.1f}s | "
              f"within 5s: {100*sum(d<5 for d in diffs)/len(diffs):.0f}% | within 15s: {100*sum(d<15 for d in diffs)/len(diffs):.0f}%")


if __name__ == "__main__":
    main()
