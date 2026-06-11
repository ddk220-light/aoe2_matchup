"""decode_lifecycle.py — extract the clean per-unit GROUND TRUTH from the capture.

For every entity that EVER existed in the game (cumulative, never deleted):
  instance_id, model_type, master_id(=unit type), owner, created_ms, died_ms,
  hp_max/hp_min/hp_last (so we see damage taken).

Reuses the cracked flat-document decoder (decode_state_v2) but RECORDS deaths
instead of dropping them. Streams the 993 MB capture; writes units_lifecycle.json
+ prints a per-type / per-player summary.
"""
import json
import struct
import sys
from collections import Counter

sys.path.insert(0, "C:/dev/aoe2/aoe2record/lab")
import decode_state_v2 as D
import cade_api_pb2 as pb

CAP = "GAME_munq_vs_ddk220_incas_frames_raw.bin"
SNAP = "first_patch_seg2.bin"
SCHEMA = D.SCHEMA
ENTITY_TYPES = D.ENTITY_TYPES
F_MASTER, F_OWNER, F_HP = 1, 2, 12
# Real gameplay units only: Entity(9), ActionEntity(11), CombatEntity(12),
# BuildingEntity(14). EXCLUDE DoppleEntity(10, fog shadows) and MissileEntity(13,
# projectiles) -- they flood the set and aren't units.
UNIT_TYPES = {9, 11, 12, 14}


def name_map():
    """Full master_id -> unit name from aocref dataset 100 (.dat object ids)."""
    import os
    import aocref
    p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
    raw = json.load(open(p, encoding="utf-8"))
    objs = raw.get("objects", raw) if isinstance(raw, dict) else raw
    m = {}
    if isinstance(objs, dict):
        for k, v in objs.items():
            try:
                m[int(k)] = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
            except Exception:
                pass
    return m


def _rec(units, k, mt, t):
    u = units.get(k)
    if u is None or (u.get("died_ms") is not None):   # new unit (or id reused after death)
        units[k] = {"model_type": mt, "master_id": None, "owner": None,
                    "created_ms": t, "died_ms": None,
                    "hp_max": None, "hp_min": None, "hp_last": None, "src": "delta"}
    return units[k]


def _hp(u, v):
    if not isinstance(v, (int, float)):
        return
    u["hp_last"] = v
    u["hp_max"] = v if u["hp_max"] is None else max(u["hp_max"], v)
    u["hp_min"] = v if u["hp_min"] is None else min(u["hp_min"], v)


def apply_lifecycle(doc, data, entity_store, world_id, units, t):
    """Mirror decode_state_v2.apply_patch, but record cumulative unit lifecycle."""
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]

    def finfo(top_id, f):
        return SCHEMA.get(doc.models[top_id]["__type__"], {}).get(f, ("value", False, None))

    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                continue
            top_id = stack[-1]; top = doc.models[top_id]; ctx = ctx_stack[-1]

            if op == 1:
                if len(stack) > 1:
                    stack.pop(); ctx_stack.pop()
            elif op == 2:
                f = r.u8(); vt, ism, scal = finfo(top_id, f); val = D.read_value(r, vt, ism, scal)
                top[f] = val
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    ek = ctx[1]
                    if ek in entity_store:
                        entity_store[ek][f] = val
                    u = units.get(ek)
                    if u is not None:
                        if f == F_MASTER: u["master_id"] = val
                        elif f == F_OWNER: u["owner"] = val
                        elif f == F_HP: _hp(u, val)
            elif op == 3:
                f = r.u8(); cid = top.get(f)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid); ctx_stack.append(("world",) if cid == world_id else None)
                else:
                    nid = doc.register(-1); top[f] = nid; stack.append(nid); ctx_stack.append(None)
            elif op == 4:
                f = r.u8(); mt = r.u8()
                old = top.get(f)
                if isinstance(old, int): doc.models.pop(old, None)
                cid = doc.register(mt); top[f] = cid; stack.append(cid)
                isw = doc.models[top_id]["__type__"] == 0 and f == 0 and mt == 1
                ctx_stack.append(("world",) if isw else None)
            elif op == 5:
                f = r.u8(); old = top.pop(f, None)
                if isinstance(old, int): doc.models.pop(old, None)
            elif op == 6:
                f = r.u8(); k = r.i32(); vt, ism, scal = finfo(top_id, f); D.read_value(r, vt, ism, scal)
            elif op == 7:
                f = r.u8(); k = r.i32(); cid = top.get(f, {}).get(k)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[cid]["__type__"]}
                    else:
                        ctx_stack.append(None)
                else:
                    nid = doc.register(entity_store.get(k, {}).get("__type__", -1) if (ctx == ("world",) and f == 1) else -1)
                    top.setdefault(f, {})[k] = nid; stack.append(nid)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        entity_store.setdefault(k, {"__type__": doc.models[nid]["__type__"]})
                    else:
                        ctx_stack.append(None)
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32()
                mp = top.setdefault(f, {})
                old = mp.get(k)
                if isinstance(old, int): doc.models.pop(old, None)
                cid = doc.register(mt); mp[k] = cid; stack.append(cid)
                if ctx == ("world",) and f == 1 and mt in ENTITY_TYPES:
                    ctx_stack.append(("entity", k)); entity_store[k] = {"__type__": mt}
                    if mt in UNIT_TYPES:
                        _rec(units, k, mt, t)        # CREATE (real units only)
                else:
                    ctx_stack.append(None)
            elif op == 9:
                f = r.u8(); k = r.i32(); m = top.get(f)
                if isinstance(m, dict):
                    old = m.pop(k, None)
                    if isinstance(old, int): doc.models.pop(old, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
                    if k in units and units[k]["died_ms"] is None:
                        units[k]["died_ms"] = t           # DEATH (recorded, not dropped)
            elif op == 10:
                f = r.u8(); k = r.i32(); vt, ism, scal = finfo(top_id, f); D.read_value(r, vt, ism, scal)
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32(); cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid; stack.append(cid); ctx_stack.append(None)
            elif op == 12:
                f = r.u8(); k = r.i32(); m = top.get(f)
                if isinstance(m, dict):
                    old = m.pop(k, None)
                    if isinstance(old, int): doc.models.pop(old, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
                    if k in units and units[k]["died_ms"] is None:
                        units[k]["died_ms"] = t
            elif op == 13:
                r.u8(); r.i32(); r.i32()
            elif op == 14:
                r.u8(); r.i32()
        except Exception:
            r.p = op_pos + 1
            while len(ctx_stack) > len(stack): ctx_stack.pop()
            while len(stack) > len(ctx_stack): ctx_stack.append(None)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    doc = D.Doc(); entity_store = {}
    n0, world_id = D.seed_from_snapshot(SNAP, doc, entity_store)
    units = {}
    for k, e in entity_store.items():
        if e.get("__type__") not in UNIT_TYPES:
            continue
        units[k] = {"model_type": e.get("__type__"), "master_id": e.get(F_MASTER),
                    "owner": e.get(F_OWNER), "created_ms": 0, "died_ms": None,
                    "hp_max": e.get(F_HP), "hp_min": e.get(F_HP), "hp_last": e.get(F_HP),
                    "src": "snapshot"}
    print(f"seeded {len(units)} entities from snapshot (world_id={world_id})", flush=True)

    f = open(CAP, "rb")
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
            if len(fr.patch) > 500_000:    # full-state snapshot -> skip
                continue
            apply_lifecycle(doc, fr.patch, entity_store, world_id, units, fr.time)
            frames += 1
        if limit and frames >= limit:
            break
    f.close()
    print(f"processed {frames} delta frames, final gametime {last_t}ms, "
          f"cumulative entities tracked: {len(units)}", flush=True)

    nm = name_map()
    # classify + summarize PLAYER units (owner 1/2), exclude gaia(0) and fog(model_type 10)
    players = {k: u for k, u in units.items()
               if u["owner"] in (1, 2) and u["model_type"] != 10 and u["master_id"] is not None}
    print(f"\nPLAYER units (owner 1/2, real): {len(players)}")
    by_owner = Counter(u["owner"] for u in players.values())
    print("by owner:", dict(by_owner))
    died = sum(1 for u in players.values() if u["died_ms"] is not None)
    dmg = sum(1 for u in players.values()
              if u["hp_max"] and u["hp_min"] is not None and u["hp_min"] < u["hp_max"])
    print(f"died during game: {died} | took damage (hp dropped): {dmg}")
    print("\ntop unit types (cumulative, per owner):")
    comp = Counter((u["owner"], nm.get(u["master_id"], f"id{u['master_id']}")) for u in players.values())
    for (own, nm2), c in comp.most_common(30):
        print(f"  P{own}  {nm2:24} {c}")

    out = {str(k): u for k, u in units.items()}
    json.dump(out, open("units_lifecycle.json", "w"))
    print(f"\nwrote units_lifecycle.json ({len(out)} entities)")


if __name__ == "__main__":
    main()
