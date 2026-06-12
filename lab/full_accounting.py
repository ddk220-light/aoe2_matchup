"""Full production accounting for ddk220: of everything queued, how many were
PRODUCED vs LOST, and of the lost, how many to BUILDING DESTRUCTION vs RESIGN.

Sources:
  gRPC capture  -> building create/death times; actual military spawns (ground truth)
  .aoe2record   -> DE_QUEUE (per-building sets) + Unqueue + resign time
FIFO sim with multiqueue load-balancing, building death (drop in-progress queue),
and resign cutoff. Cross-checked against the captured (real) spawn counts.
"""
import json, os, re, struct, sys, types
from collections import defaultdict, Counter
sys.path.insert(0, "C:/dev/aoe2/aoe2record/lab")
import aocref, cade_api_pb2 as pb, decode_state_v2 as D

CAP = "GAME_fogoff_raw.bin"
OWNER = 2
RESIGN_MS = 2555000          # ddk220 resigned @42.59m
CLEANUP_MS = 2545000         # removals after ~42.4m = end-of-game cleanup, not destruction
NAME = {int(k): v for k, v in json.load(open(os.path.join(os.path.dirname(aocref.__file__),
        "data", "datasets", "100.json"), encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")
def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
TT = json.load(open("C:/dev/aoe2/aoe2record/visualizer/train_times.json"))["base"]
def train(name):
    return TT.get(norm(name)) or {"skirmisher": 22, "slinger": 25, "spearman": 22,
        "archer": 35, "champiscout": 26}.get(norm(name), 30)
MIL = ("skirmisher", "slinger", "spearman", "archer", "champiscout")


def grpc_scan():
    created = {}; died = {}; spawns = Counter(); spawn_bld = defaultdict(Counter)
    buildings_pos = {}
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
                if b == 8 and p[j + 1] == 1 and p[j + 2] in (11, 12, 14) and p[j + 7] == 2:
                    mt = p[j + 2]; key = struct.unpack_from("<i", p, j + 3)[0]
                    if 0 < key < 1_000_000:
                        r = D.Reader(p); r.p = j + 7; f = {}
                        for _ in range(6):
                            if r.p >= L or p[r.p] != 2: break
                            r.p += 1; fld = r.u8()
                            try: v = D.read_value(r, *D.SCHEMA.get(mt, {}).get(fld, ("value", False, None)))
                            except Exception: break
                            f[fld] = v
                            if all(k in f for k in (1, 2, 3, 4)): break
                        ow = f.get(2)
                        if mt == 14 and ow == OWNER and key not in created:
                            created[key] = (nm(f.get(1)), t, f.get(3), f.get(4))
                            buildings_pos[key] = (f.get(3), f.get(4))
                        elif mt in (11, 12) and ow == OWNER and 1 in f:
                            ty = norm(nm(f[1]))
                            if ty in MIL:
                                spawns[ty] += 1
                                spawn_bld[ty][(round(f.get(3) or 0), round(f.get(4) or 0))] += 1
                    j += 7; continue
                if b in (9, 12) and p[j + 1] == 1:
                    key = struct.unpack_from("<i", p, j + 2)[0]
                    if 0 < key < 1_000_000 and key not in died:
                        died[key] = t
                    j += 6; continue
                j += 1
    fh.close()
    return created, died, spawns


def record():
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
    print("scanning gRPC capture...")
    created, died_raw, captured = grpc_scan()
    q, unqs = record()

    # real building death = removal before cleanup window; else survived
    bdeath = {}
    for bid in created:
        d = died_raw.get(bid)
        bdeath[bid] = d if (d is not None and d < CLEANUP_MS) else None

    # FIFO with multiqueue load-balancing, building death, resign cutoff + unqueue
    free = defaultdict(float)
    pending = defaultdict(list)
    events = sorted([(t, "q", un, bs) for t, un, bs in q] +
                    [(t, "x", bld, sl) for t, bld, sl in unqs])
    produced = Counter(); lost_death = Counter(); lost_resign = Counter()
    death_by_bld = Counter()
    for ev in events:
        if ev[1] == "q":
            t, _, un, bs = ev
            alive = [b for b in bs if bdeath.get(b) is None or bdeath[b] > t]
            cand = alive or bs
            if not cand:
                continue
            b = min(cand, key=lambda bb: max(free[bb], t))
            done = max(free[b], t) + train(un) * 1000.0
            free[b] = done
            pending[b].append((done, un))
            ty = norm(un)
            d = bdeath.get(b)
            if d is not None and done > d:
                lost_death[ty] += 1; death_by_bld[b] += 1
            elif done > RESIGN_MS:
                lost_resign[ty] += 1
            else:
                produced[ty] += 1
        else:
            t, _, bld, sl = ev
            if bld in pending and pending[bld]:
                idx = sl if (isinstance(sl, int) and sl < len(pending[bld])) else -1
                pending[bld].pop(idx)

    # report
    print("\n=== BUILDINGS DESTROYED before resign (real, not end cleanup) ===")
    for bid, d in sorted(bdeath.items(), key=lambda kv: (kv[1] is None, kv[1] or 0)):
        if d is not None and death_by_bld.get(bid, 0) >= 0 and created[bid][0] in ("Archery Range", "Barracks", "Stable", "Castle", "Siege Workshop", "Monastery"):
            print(f"  {created[bid][0]:15} id={bid}  built @{created[bid][1]/60000:5.1f}m  DESTROYED @{d/60000:5.1f}m  -> lost {death_by_bld.get(bid,0)} in-queue units")

    print(f"\n=== ddk220 MILITARY accounting (resign @ {RESIGN_MS/60000:.1f}m) ===")
    print(f"{'type':12} {'queued':>7} {'produced':>9} {'lost:bldg':>10} {'lost:resign':>12} | {'captured(gRPC)':>14}")
    tq = tp = tld = tlr = tc = 0
    for ty in MIL:
        qn = sum(1 for _, un, _ in q if norm(un) == ty)
        pr, ld, lr, cp = produced[ty], lost_death[ty], lost_resign[ty], captured[ty]
        tq += qn; tp += pr; tld += ld; tlr += lr; tc += cp
        print(f"{ty:12} {qn:7} {pr:9} {ld:10} {lr:12} | {cp:14}")
    print(f"{'TOTAL':12} {tq:7} {tp:9} {tld:10} {tlr:12} | {tc:14}")
    print(f"\n  queued {tq} = produced {tp} + lost-to-building-death {tld} + lost-to-resign {tlr}  ({tq-tp-tld-tlr} unaccounted/cancelled)")
    print(f"  sim-produced {tp} vs captured {tc}  (diff {tp-tc})")


if __name__ == "__main__":
    main()
