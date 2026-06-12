"""Test: were ddk220's missing units lost because their production BUILDING was
destroyed while units were still queued?

From the gRPC capture: track each owner-2 production building's CREATE and DEATH
(op9/op12 removal from World.entities). Then run the per-building FIFO sim from the
.aoe2record and count, per building, how many queued units would complete AFTER the
building died (= lost) vs before (= produced).
"""
import json, os, re, struct, sys, types
from collections import defaultdict, Counter
sys.path.insert(0, "C:/dev/aoe2/aoe2record/lab")
import aocref, cade_api_pb2 as pb, decode_state_v2 as D

CAP = "GAME_fogoff_raw.bin"
OWNER = 2
NAME = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(aocref.__file__),
        "data", "datasets", "100.json"), encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")
def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
TT = json.load(open("C:/dev/aoe2/aoe2record/visualizer/train_times.json"))["base"]
def train(name):
    return TT.get(norm(name)) or {"skirmisher": 22, "slinger": 25, "spearman": 22,
        "archer": 35, "champiscout": 26, "villager": 25}.get(norm(name), 30)


def grpc_buildings():
    """Return {bid: (name, create_ms, death_ms or None)} for owner-2 buildings."""
    created = {}; died = {}
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
                b = p[j]
                # building create: op8 field1 model14
                if b == 8 and p[j + 1] == 1 and p[j + 2] == 14 and p[j + 7] == 2:
                    key = struct.unpack_from("<i", p, j + 3)[0]
                    if 0 < key < 1_000_000:
                        r = D.Reader(p); r.p = j + 7; f = {}
                        for _ in range(4):
                            if r.p >= L or p[r.p] != 2: break
                            r.p += 1; fld = r.u8()
                            try: v = D.read_value(r, *D.SCHEMA.get(14, {}).get(fld, ("value", False, None)))
                            except Exception: break
                            f[fld] = v
                            if 1 in f and 2 in f: break
                        if f.get(2) == OWNER and key not in created:
                            created[key] = (nm(f.get(1)), t)
                    j += 7; continue
                # removal: op9/op12 field1 key  (ResetKey / Remove from World.entities)
                if b in (9, 12) and p[j + 1] == 1:
                    key = struct.unpack_from("<i", p, j + 2)[0]
                    if 0 < key < 1_000_000 and key not in died:
                        died[key] = t
                    j += 6; continue
                j += 1
    fh.close()
    out = {}
    for bid, (name, ct) in created.items():
        out[bid] = (name, ct, died.get(bid))
    return out


def record_queues_unqs():
    for m in ("flask", "flask_cors", "requests"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.path.insert(0, "C:/dev/aoe2/aoc-mgz-67x")
    import mgz.model
    mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
    q, u = [], []
    for a in mt.actions:
        if not a.player or a.player.name != "ddk220": continue
        p = a.payload or {}; t = a.timestamp.total_seconds() * 1000.0
        at = str(a.type).replace("Action.", "")
        if at.endswith("DE_QUEUE"):
            un = p.get("unit", "?")
            if un and "Villager" not in un:
                for _ in range(p.get("amount", 1) or 1):
                    q.append((t, un, list(p.get("object_ids", []))))
        elif p.get("order") == "Unqueue":
            b = [(o >> 8 if o >= 1_000_000 else o) for o in p.get("object_ids", [])]
            u.append((t, b[0] if b else None, p.get("slot_id")))
    return sorted(q), sorted(u)


def main():
    print("scanning gRPC for owner-2 building create/death...")
    blds = grpc_buildings()
    q, unqs = record_queues_unqs()

    # FIFO sim with multiqueue load-balancing -> (building, completion_ms, type)
    free = defaultdict(float)
    units = []
    for t, un, bset in q:
        if not bset: continue
        b = min(bset, key=lambda bb: max(free[bb], t))
        done = max(free[b], t) + train(un) * 1000.0
        free[b] = done
        units.append((b, done, un))

    # account: for each unit, is its building alive at completion?
    GAME_END = 2553544
    lost_dead = Counter(); lost_endgame = Counter(); produced = Counter()
    bld_loss = defaultdict(lambda: [0, 0])   # bid -> [produced, lost]
    for b, done, un in units:
        death = blds.get(b, (None, None, None))[2]
        if death is not None and done > death:
            lost_dead[norm(un)] += 1; bld_loss[b][1] += 1
        elif done > GAME_END:
            lost_endgame[norm(un)] += 1
        else:
            produced[norm(un)] += 1; bld_loss[b][0] += 1

    print("\n=== ddk220 production buildings: create -> death ===")
    prod_bids = set(b for u in units for b in [u[0]])
    for bid in sorted(prod_bids, key=lambda b: -(bld_loss[b][0] + bld_loss[b][1])):
        name, ct, dt = blds.get(bid, (f"?id{bid}", None, None))
        dstr = f"DIED @{dt/60000:.1f}m" if dt else "survived"
        print(f"  bldg {bid} {name:16} created @{(ct or 0)/60000:5.1f}m  {dstr:14}  produced={bld_loss[bid][0]} lost={bld_loss[bid][1]}")

    print("\n=== accounting (FIFO vs building death) ===")
    for ty in ("skirmisher", "slinger", "spearman", "archer", "champiscout"):
        qn = sum(1 for _, un, _ in q if norm(un) == ty)
        print(f"  {ty:12}: queued={qn:3}  produced={produced.get(ty,0):3}  "
              f"lost-to-building-death={lost_dead.get(ty,0):3}  still-in-queue-at-end={lost_endgame.get(ty,0):3}")


if __name__ == "__main__":
    main()
