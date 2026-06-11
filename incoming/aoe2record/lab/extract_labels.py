"""extract_labels.py CAP OUT -- build ground-truth labels from a gRPC capture .bin.

Parameterized version of extract_creates_v2: anchors on every op8 entity-create
signature (desync-immune), records {instance_id -> type, owner, created_ms}, and
seeds the initial entities from the capture's OWN first full-state patch (record_games
does not save a separate first_patch file). Writes OUT as the labels.json schema the
classifier scorer expects.
"""
import json
import os
import struct
import sys
from collections import Counter

import aocref
import cade_api_pb2 as pb
import decode_state_v2 as D
import build_ground_truth as BGT

CAP = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "labels.json"
SCH = D.SCHEMA
ENT = {9, 11, 12, 14}
UNIT_MT = {9, 11, 12, 14}
BUILDING_MT = 14
_p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
NAME = {int(k): v for k, v in json.load(open(_p, encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")


def decode_create(p, j, L):
    mt = p[j + 2]
    key = struct.unpack_from("<i", p, j + 3)[0]
    if not (0 < key < 1_000_000):
        return None
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
    units = {}
    deaths = {}
    frames = 0
    last_t = 0
    cand = 0
    snap_path = None
    while True:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        ln = struct.unpack("<I", hdr)[0]
        buf = f.read(ln)
        if len(buf) < ln:
            break
        sq = pb.FrameSequence()
        sq.ParseFromString(buf)
        for fr in sq.frame:
            last_t = fr.time
            for ev in fr.event:
                if ev.WhichOneof("event") == "entityKilled":
                    deaths.setdefault(ev.entityKilled.id, fr.time)
            p = fr.patch
            L = len(p)
            # first big patch = the full-state snapshot (initial entities)
            if snap_path is None and L > 50_000:
                snap_path = OUT + ".snap.bin"
                open(snap_path, "wb").write(p)
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
                        if key not in units:
                            units[key] = {"mt": mt, "master": master,
                                          "owner": owner, "created_ms": fr.time}
                        j += 7
                        continue
                j += 1
    f.close()

    seeded = 0
    if snap_path and os.path.exists(snap_path):
        try:
            start = BGT.decode_snapshot_entities(snap_path)
            for k, e in start.items():
                if e.get("__type__") in UNIT_MT and e.get(1) is not None and k not in units:
                    units[k] = {"mt": e["__type__"], "master": e.get(1),
                                "owner": e.get(2), "created_ms": 0}
                    seeded += 1
        except Exception as ex:
            print("snapshot seed failed:", ex)

    out = {str(k): {"type": nm(u["master"]), "master_id": u["master"],
                    "owner": u["owner"], "model_type": u["mt"],
                    "created_ms": u["created_ms"],
                    "died_ms": deaths.get(k)} for k, u in units.items()}
    json.dump(out, open(OUT, "w"))
    print(f"frames={frames} gametime={last_t/60000:.1f}min candidates={cand} "
          f"entities={len(units)} seeded={seeded} -> {OUT}")
    for o in sorted(set(u["owner"] for u in units.values() if u["owner"])):
        c = Counter(nm(u["master"]) for u in units.values()
                    if u["owner"] == o and u["mt"] != BUILDING_MT)
        print(f"  owner {o}: {sum(c.values())} non-building, top: {dict(c.most_common(6))}")


if __name__ == "__main__":
    main()
