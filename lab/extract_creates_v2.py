"""extract_creates_v2.py — capture EVERY entity create, desync-immune.

Each unit create has a fixed local signature:
  08 01 <mt>  <key:i32>            # op8 create World.entities[key], entity type mt
  02 08 <state:i8>                 # (units; buildings skip this)
  02 01 <master_id:i16>            # the unit type
  02 02 <owner:i8>
We ANCHOR on each `08 01 <entity-type> <plausible-key>` occurrence and decode only
the entity's own leading fields from the Entity schema. Because each create is its
own clean start point, a desync ANYWHERE else in the frame cannot drop it. This is
the 100%-capture baseline of {entity_id (= instance_id) -> unit type}.
"""
import json
import os
import struct
from collections import Counter, defaultdict

import aocref
import cade_api_pb2 as pb
import decode_state_v2 as D

CAP = "GAME_munq_vs_ddk220_incas_frames_raw.bin"
SCH = D.SCHEMA
ENT = {9, 11, 12, 14}
UNIT_MT = {9, 11, 12, 14}
BUILDING_MT = 14

_p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
NAME = {int(k): v for k, v in json.load(open(_p, encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")


def decode_create(p, j, L):
    """At a candidate create `08 01 mt key`, decode the entity's leading op2
    assigns to extract (master_id, owner). Returns (mt, key, master, owner) or None."""
    mt = p[j + 2]
    key = struct.unpack_from("<i", p, j + 3)[0]
    if not (0 < key < 1_000_000):
        return None
    # must be followed by an op2 field assign (state f8 for units, master f1 for bldgs)
    if j + 7 >= L or p[j + 7] != 2:
        return None
    r = D.Reader(p)
    r.p = j + 7
    master = owner = None
    for _ in range(8):
        if r.p >= L or p[r.p] != 2:
            break
        r.p += 1
        f = r.u8()
        fi = SCH.get(mt, {}).get(f, ("value", False, None))
        try:
            v = D.read_value(r, *fi)
        except Exception:
            break
        if f == 1:
            master = v
        elif f == 2:
            owner = v
        if master is not None and owner is not None:
            break
    if master is None or master < 0:
        return None
    return mt, key, master, owner


def main():
    f = open(CAP, "rb")
    units = {}        # key -> {mt, master, owner, created_ms}
    deaths = {}       # key -> died_ms (from EntityKilled + op9/op12 best-effort)
    frames = 0; last_t = 0; cand = 0
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
            last_t = fr.time
            for ev in fr.event:
                if ev.WhichOneof("event") == "entityKilled":
                    deaths.setdefault(ev.entityKilled.id, fr.time)
            p = fr.patch; L = len(p)
            if L > 500_000:
                continue
            frames += 1
            j = 0
            while j < L - 8:
                if p[j] == 8 and p[j + 1] == 1 and p[j + 2] in ENT:
                    res = decode_create(p, j, L)
                    if res:
                        cand += 1
                        mt, key, master, owner = res
                        if key not in units:      # first create wins
                            units[key] = {"mt": mt, "master": master,
                                          "owner": owner, "created_ms": fr.time}
                        j += 7
                        continue
                j += 1
    f.close()

    # seed start-snapshot units that may never be re-created in deltas
    start = __import__("build_ground_truth").decode_snapshot_entities("first_patch_seg2.bin")
    seeded = 0
    for k, e in start.items():
        if e.get("__type__") in UNIT_MT and e.get(1) is not None and k not in units:
            units[k] = {"mt": e["__type__"], "master": e.get(1),
                        "owner": e.get(2), "created_ms": 0}
            seeded += 1

    print(f"frames={frames}  gametime={last_t/60000:.1f}min  create-candidates={cand}  "
          f"unique entities={len(units)}  seeded_from_start={seeded}")

    # classify
    def is_villager(name):
        n = name.lower()
        return any(k in n for k in ("villager", "farmer", "lumberjack", "miner",
                   "builder", "forager", "fisher", "shepherd", "repairer", "hunter", "gatherer"))
    def is_skip(name):
        return "flare" in name.lower()

    prod = json.load(open("events_summary.json"))["make"]   # verified production
    pname = {1: "munq (Bohemians)", 2: "ddk220 (Incas)"}
    for o in (1, 2):
        # collapse villager-variants; keep military by name; separate buildings
        mil = Counter(); vil = 0; bld = Counter()
        for u in units.values():
            if u["owner"] != o:
                continue
            name = nm(u["master"])
            if is_skip(name):
                continue
            if u["mt"] == BUILDING_MT:
                bld[name] += 1
            elif is_villager(name):
                vil += 1
            else:
                mil[name] += 1
        print(f"\n==== PLAYER {o} - {pname[o]} ====")
        print(f"  Villagers: {vil}")
        print(f"  Military: {sum(mil.values())}")
        # compare military vs production
        rec = Counter(prod.get(str(o), {}))
        print(f"  {'type':22} {'captured':>9} {'produced':>9}  match")
        keys = sorted(set(mil) | {k for k in rec if k != 'Villager'},
                      key=lambda k: -rec.get(k, 0))
        cap_v = vil; rec_v = rec.get("Villager", 0)
        print(f"  {'Villager':22} {cap_v:9} {rec_v:9}  {'OK' if cap_v==rec_v else 'diff '+str(cap_v-rec_v)}")
        for k in keys:
            c = mil.get(k, 0); rc = rec.get(k, 0)
            print(f"  {k:22} {c:9} {rc:9}  {'OK' if c==rc else 'diff '+str(c-rc)}")

    out = {str(k): {"type": nm(u["master"]), "master_id": u["master"],
                    "owner": u["owner"], "model_type": u["mt"],
                    "created_ms": u["created_ms"],
                    "died_ms": deaths.get(k)} for k, u in units.items()}
    json.dump(out, open("labels.json", "w"))
    print(f"\nwrote labels.json ({len(out)} instance_id -> type)")


if __name__ == "__main__":
    main()
