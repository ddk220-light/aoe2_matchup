"""Decode the live entity state from captured per-frame patches (path C).

Skips the big full-state snapshots (which desync on the drifted master-entity
defs) and applies the small per-frame DELTAS, which navigate World.entities and
the stable Entity model directly. Reconstructs every unit: type (master_id),
owner, position (world_x/y), hp, action -- the ground truth.
"""
import struct
import sys
from collections import Counter

import patch_decode as P
import cade_api_pb2 as pb

# Entity model types and the stable field indices we care about.
ENTITY_TYPES = {9, 10, 11, 12, 13, 14}
F_MASTER, F_OWNER, F_X, F_Y, F_HP, F_STATE = 1, 2, 3, 4, 12, 8


def apply_delta(root, data):
    """Apply one patch to the persistent root (resync-tolerant)."""
    r = P.Reader(data)
    stack = [root]
    while r.p < len(data):
        op_pos = r.p
        op = r.u8()
        if not (1 <= op <= 14):
            continue
        try:
            top = stack[-1]
            fields = P.SCHEMA.get(top["__type__"], {})
            if op == 1:
                if len(stack) > 1:
                    stack.pop()
            elif op == 2:
                f = r.u8(); top[f] = P.read_value(r, fields.get(f))
            elif op == 3:
                f = r.u8(); stack.append(top.setdefault(f, {"__type__": -1}))
            elif op == 4:
                f = r.u8(); mt = r.u8(); c = {"__type__": mt}; top[f] = c; stack.append(c)
            elif op == 5:
                f = r.u8(); top.pop(f, None)
            elif op == 6:
                f = r.u8(); k = r.i32(); top.setdefault(f, {})[k] = P.read_value(r, fields.get(f))
            elif op == 7:
                f = r.u8(); k = r.i32(); stack.append(top.setdefault(f, {}).setdefault(k, {"__type__": -1}))
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32(); c = {"__type__": mt}; top.setdefault(f, {})[k] = c; stack.append(c)
            elif op == 9:
                f = r.u8(); k = r.i32(); top.get(f, {}).pop(k, None)
            elif op == 10:
                f = r.u8(); k = r.i32(); top.setdefault(f, {})[k] = P.read_value(r, fields.get(f))
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32(); c = {"__type__": mt}; top.setdefault(f, {})[k] = c; stack.append(c)
            elif op == 12:
                f = r.u8(); k = r.i32(); top.get(f, {}).pop(k, None)
            elif op == 13:
                f = r.u8(); r.i32(); r.i32()
            elif op == 14:
                f = r.u8(); r.i32()
        except Exception:
            r.p = op_pos + 1
            continue


def read_seqs(path):
    data = open(path, "rb").read()
    pos = 0
    out = []
    while pos + 4 <= len(data):
        n = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if pos + n > len(data):
            break  # incomplete tail (capture still writing)
        out.append(data[pos:pos + n])
        pos += n
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "frames_raw.bin"
    max_seqs = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    seqs = read_seqs(path)
    if max_seqs:
        seqs = seqs[:max_seqs]
    print(f"{len(seqs)} sequences in {path}")

    # pre-seed Root -> World(type1) -> entities(field1, empty map)
    root = {"__type__": 0, 0: {"__type__": 1, 1: {}}}
    applied = skipped_big = kills = 0
    last_time = None
    for raw in seqs:
        sq = pb.FrameSequence()
        sq.ParseFromString(raw)
        for fr in sq.frame:
            last_time = fr.time
            if fr.patch:
                if len(fr.patch) > 500_000:      # full-state snapshot -> skip (drift)
                    skipped_big += 1
                else:
                    apply_delta(root, fr.patch)
                    applied += 1
            for e in fr.event:
                if e.WhichOneof("event") == "entityKilled":
                    kills += 1
                    P  # (could remove from entities; left in for now)

    world = root.get(0, {})
    ents = world.get(1, {})
    print(f"applied {applied} delta patches, skipped {skipped_big} snapshots, "
          f"{kills} kill events, gametime~{last_time}ms")
    print(f"entities tracked: {len(ents)}")

    # only real entities (have a master_id and an entity model type)
    real = {k: e for k, e in ents.items()
            if isinstance(e, dict) and e.get(F_MASTER) is not None}
    print(f"entities with a unit type (master_id): {len(real)}")
    by_owner_master = Counter((e.get(F_OWNER), e.get(F_MASTER)) for e in real.values())
    print("\ntop (owner, master_id, count):")
    for (owner, master), n in by_owner_master.most_common(25):
        print(f"  owner={owner}  type_id={master}  count={n}")

    print("\nsample entities (id, type_id, owner, x, y, hp):")
    for k, e in list(real.items())[:12]:
        print(f"  id={k} type={e.get(F_MASTER)} owner={e.get(F_OWNER)} "
              f"x={e.get(F_X)} y={e.get(F_Y)} hp={e.get(F_HP)}")


if __name__ == "__main__":
    main()
