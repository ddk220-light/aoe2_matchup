"""build_ground_truth.py — the consolidated, verified ground-truth dataset.

Combines three RELIABLE sources from the 993 MB gRPC capture:
  1. PRODUCTION  (MultiQueue commands) -> units of each type per player + when
     first trained. 100% verified against the .aoe2record (13/13 types).
  2. INITIAL     (start snapshot, 0.5 min) -> entities present at game start.
  3. SURVIVORS   (end snapshot, 42.6 min) -> entities alive at game end.
  -> DEATHS by difference = produced - survived (approximate; ignores transforms).

Filters survivors to real unit model-types {9,11,12,14} (drops MissileEntity 13,
DoppleEntity 10 fog-shadows) and excludes Flare pings. Villager task-variants
(Farmer/Lumberjack/Miner/Builder/...) collapse to "Villager".

Writes ground_truth.json + prints the report. This is the simple, trustworthy
dataset the file decode was meant to produce.
"""
import json
import os
import struct
from collections import Counter, defaultdict

import aocref
import decode_state_v2 as D

# ---- names ----
_p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
NAME = {int(k): v for k, v in json.load(open(_p, encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")

REAL_UNIT_MT = {9, 11, 12, 14}     # Entity/Action/Combat/Building (no Missile/Dopple)
BUILDING_MT = 14
VILLAGER_KW = ("villager", "hunter", "lumberjack", "miner", "builder", "forager",
               "farmer", "fisher", "shepherd", "repairer", "gatherer", "berry")
SKIP_KW = ("flare",)


def collapse(name):
    n = name.lower()
    if any(k in n for k in VILLAGER_KW):
        return "Villager"
    return name


def decode_snapshot_entities(path):
    """Robust full-file entity scan of a snapshot. Returns {key: {'__type__', fields}}."""
    data = open(path, "rb").read()
    ENT = D.ENTITY_TYPES
    bs = None
    for i in range(len(data) - 6):
        if data[i] == 8 and data[i + 1] == 1 and data[i + 2] in ENT:
            k = struct.unpack_from("<i", data, i + 3)[0]
            if 0 < k < 1_000_000:
                bs = i; break
    r = D.Reader(data); r.p = bs
    es = {}; cur = None; SCH = D.SCHEMA
    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                cur = None; continue
            if op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32()
                if f == 1 and mt in ENT:
                    es[k] = {"__type__": mt}; cur = k
                else:
                    cur = None
            elif op == 2:
                f = r.u8()
                fi = SCH.get(es[cur]["__type__"], {}).get(f) if (cur in es) else None
                if fi:
                    vt, ism, scal = fi; val = D.read_value(r, vt, ism, scal)
                else:
                    D.guess_value(r); val = None
                if cur in es:
                    es[cur][f] = val
            elif op == 1:
                cur = None
            elif op in (3, 5, 14):
                r.u8()
            elif op == 4:
                r.u8(); r.u8()
            elif op in (7, 9, 12):
                r.u8(); r.i32()
            elif op in (6, 10):
                r.u8(); r.i32(); D.guess_value(r)
            elif op == 11:
                r.u8(); r.u8(); r.i32()
            elif op == 13:
                r.u8(); r.i32(); r.i32()
        except Exception:
            r.p = op_pos + 1; cur = None
    return es


def units_by_player(es):
    """{owner: Counter(collapsed_name -> count)} for real, non-flare, non-gaia units."""
    out = defaultdict(Counter)
    bld = defaultdict(Counter)
    for e in es.values():
        mt = e.get("__type__")
        if mt not in REAL_UNIT_MT:
            continue
        owner = e.get(2, 0)
        if owner not in (1, 2):
            continue
        name = nm(e.get(1))
        if any(k in name.lower() for k in SKIP_KW):
            continue
        if mt == BUILDING_MT:
            bld[owner][name] += 1
        else:
            out[owner][collapse(name)] += 1
    return out, bld


def main():
    ev = json.load(open("events_summary.json"))
    make = {int(p): Counter(c) for p, c in ev["make"].items()}

    print("decoding start + end snapshots...")
    start_es = decode_snapshot_entities("first_patch_seg2.bin")
    end_es = decode_snapshot_entities("end_snapshot.bin")
    start_u, start_b = units_by_player(start_es)
    surv_u, surv_b = units_by_player(end_es)

    pname = {1: "munq (Bohemians)", 2: "ddk220 (Incas)"}
    gt = {}
    for o in (1, 2):
        print("\n" + "=" * 64)
        print(f"  PLAYER {o} - {pname[o]}")
        print("=" * 64)
        prod = make.get(o, Counter())
        surv = surv_u.get(o, Counter())
        print(f"  produced total: {sum(prod.values())}   alive at end: {sum(surv.values())}")
        print(f"\n  {'unit type':22} {'produced':>9} {'alive@end':>10} {'died~':>7}")
        rows = {}
        for t in sorted(set(prod) | set(surv), key=lambda k: -prod.get(k, 0)):
            p = prod.get(t, 0); s = surv.get(t, 0); d = max(0, p - s)
            rows[t] = {"produced": p, "alive_end": s, "died_approx": d}
            print(f"  {t:22} {p:9} {s:10} {d:7}")
        print(f"\n  buildings built (alive@end): "
              f"{dict(surv_b.get(o, Counter()).most_common(15))}")
        gt[str(o)] = {"player": pname[o], "units": rows,
                      "buildings_alive": dict(surv_b.get(o, Counter()))}

    json.dump({"players": gt, "gametime_ms": ev["gametime_ms"],
               "frames": ev["frames"]}, open("ground_truth.json", "w"), indent=2)
    print("\nwrote ground_truth.json")
    print("\nNOTE: 'died~' = produced - alive@end (approximate; ignores garrison/"
          "transform). Exact per-unit death TIME + hp needs the delta-state decode "
          "(plateaus mid-game due to model drift) or a re-capture with EntityKilled "
          "events enabled. Production counts are 100% verified vs the .aoe2record.")


if __name__ == "__main__":
    main()
