"""extract_creates.py — STEP 1 done right.

Scan EVERY frame of the 993 MB capture and capture EVERY entity create:
  entity_id (= .aoe2record instance_id), master_id (unit type), owner, created_ms,
  and (best-effort) died_ms + hp.

Robust to mid-game model drift: each frame is decoded with a FRESH local stack
(no cross-frame persistent document to corrupt), and a create is detected by its
unmistakable local pattern (op8, field=1, entity model-type, plausible key) WITHOUT
depending on whole-document World navigation. So a desync in one frame can't stop
creates in later frames.
"""
import json
import os
import struct
from collections import Counter, defaultdict

import aocref
import cade_api_pb2 as pb
import decode_state_v2 as D

CAP = "GAME_munq_vs_ddk220_incas_frames_raw.bin"
SCHEMA = D.SCHEMA
ENTITY_TYPES = D.ENTITY_TYPES          # {9,10,11,12,13,14}
UNIT_TYPES = {9, 11, 12, 14}           # real units (no Missile13 / Dopple10)
F_MASTER, F_OWNER, F_HP = 1, 2, 12

_p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
NAME = {int(k): v for k, v in json.load(open(_p, encoding="utf-8"))["objects"].items()}
def nm(i): return NAME.get(i, f"id{i}")


def scan_frame(data, units, t):
    """Decode one patch with a fresh local stack; record creates/updates/deaths.
    stack elements: [model_type, entity_key_or_None]."""
    r = D.Reader(data)
    stack = [[0, None]]                  # Root
    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                continue
            top = stack[-1]
            tty, ekey = top

            if op == 1:                                  # Pop
                if len(stack) > 1:
                    stack.pop()
            elif op == 2:                                # AssignField
                f = r.u8()
                fi = SCHEMA.get(tty, {}).get(f, ("value", False, None))
                val = D.read_value(r, *fi)
                if ekey is not None:
                    u = units.get(ekey)
                    if u is not None:
                        if f == F_MASTER and isinstance(val, int):
                            u["master_id"] = val
                        elif f == F_OWNER and isinstance(val, int):
                            u["owner"] = val
                        elif f == F_HP and isinstance(val, (int, float)):
                            u["hp_last"] = val
                            u["hp_max"] = val if u["hp_max"] is None else max(u["hp_max"], val)
                            u["hp_min"] = val if u["hp_min"] is None else min(u["hp_min"], val)
            elif op == 3:                                # PushField
                r.u8(); stack.append([-1, None])
            elif op == 4:                                # PushCreateAssignField
                r.u8(); mt = r.u8(); stack.append([mt, None])
            elif op == 5:                                # ResetField
                r.u8()
            elif op == 6:                                # AssignKey
                f = r.u8(); r.i32()
                D.read_value(r, *SCHEMA.get(tty, {}).get(f, ("value", False, None)))
            elif op == 7:                                # PushKey (existing)
                f = r.u8(); k = r.i32()
                if f == 1 and (k in units):              # re-entering a known entity
                    stack.append([units[k]["model_type"], k])
                else:
                    stack.append([-1, None])
            elif op == 8:                                # PushCreateAssignKey == CREATE
                f = r.u8(); mt = r.u8(); k = r.i32()
                if f == 1 and mt in ENTITY_TYPES and 0 < k < 1_000_000:
                    if mt in UNIT_TYPES:
                        u = units.get(k)
                        if u is None or u.get("died_ms") is not None:
                            units[k] = {"model_type": mt, "master_id": None, "owner": None,
                                        "created_ms": t, "died_ms": None,
                                        "hp_max": None, "hp_min": None, "hp_last": None}
                    stack.append([mt, k])
                else:
                    stack.append([mt, None])
            elif op == 9:                                # ResetKey == DEATH (World.entities)
                f = r.u8(); k = r.i32()
                if f == 1 and k in units and units[k]["died_ms"] is None:
                    units[k]["died_ms"] = t
            elif op == 10:                               # Insert
                f = r.u8(); r.i32()
                D.read_value(r, *SCHEMA.get(tty, {}).get(f, ("value", False, None)))
            elif op == 11:                               # PushCreateInsert
                r.u8(); mt = r.u8(); r.i32(); stack.append([mt, None])
            elif op == 12:                               # Remove == DEATH
                f = r.u8(); k = r.i32()
                if f == 1 and k in units and units[k]["died_ms"] is None:
                    units[k]["died_ms"] = t
            elif op == 13:                               # Swap
                r.u8(); r.i32(); r.i32()
            elif op == 14:                               # Resize
                r.u8(); r.i32()
        except Exception:
            r.p = op_pos + 1
            # keep stack; a local misread shouldn't nuke the whole frame


def main():
    f = open(CAP, "rb")
    units = {}
    frames = 0; last_t = 0
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
            if len(fr.patch) > 500_000:        # snapshot -> handled separately
                continue
            scan_frame(fr.patch, units, fr.time)
            frames += 1
            # deaths also come as EntityKilled events
            for ev in fr.event:
                if ev.WhichOneof("event") == "entityKilled":
                    k = ev.entityKilled.id
                    if k in units and units[k]["died_ms"] is None:
                        units[k]["died_ms"] = fr.time
    f.close()

    # also seed from the start snapshot (units alive at t=0 that may never be re-created)
    snap = D.__dict__  # noqa
    start = __import__("build_ground_truth").decode_snapshot_entities("first_patch_seg2.bin")
    seeded = 0
    for k, e in start.items():
        mt = e.get("__type__")
        if mt in UNIT_TYPES and k not in units:
            units[k] = {"model_type": mt, "master_id": e.get(1), "owner": e.get(2),
                        "created_ms": 0, "died_ms": None,
                        "hp_max": e.get(12), "hp_min": e.get(12), "hp_last": e.get(12)}
            seeded += 1

    print(f"frames={frames}  gametime={last_t/60000:.1f}min  seeded_from_start={seeded}")
    players = {k: u for k, u in units.items()
               if u["owner"] in (1, 2) and u["master_id"] is not None}
    print(f"TOTAL entities created (all): {len(units)}")
    print(f"PLAYER units (owner 1/2, typed): {len(players)}")
    print("by owner:", dict(Counter(u["owner"] for u in players.values())))
    died = sum(1 for u in players.values() if u["died_ms"] is not None)
    print(f"died (recorded): {died}")

    for o in (1, 2):
        c = Counter(nm(u["master_id"]) for u in players.values() if u["owner"] == o)
        print(f"\n owner {o}: {sum(c.values())} units created")
        for t, n in c.most_common(30):
            print(f"    {t:24} {n}")

    json.dump({str(k): u for k, u in units.items()}, open("all_creates.json", "w"))
    print("\nwrote all_creates.json")


if __name__ == "__main__":
    main()
