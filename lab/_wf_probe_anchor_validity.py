"""_wf_probe_anchor_validity.py — validate the 07-01-<seeded-key> marker as a re-anchor
target inside DELTA patches.

For CLEAN patches (no exception, no invalid-op byte) in the fight segment:
  - TRUE positions: byte offsets where the decoder actually executed op7 f=1 with
    top==World (a genuine World.entities push).
  - CAND positions: raw-scan offsets of pattern 07 01 <i32 key in seeded set>.
  - Classify CAND \\ TRUE: executed-op-start at other ctx? or inside payload bytes?
  - Check ascending-key ordering of TRUE pushes within each patch.
  - Distribution of the op byte following a TRUE push (lookahead validation design).
Also: per-army-unit HP trajectory from deltas (does HP reach <=0, and when?).
"""
import struct
import sys
import math
from collections import Counter

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

PFX = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
       r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
F_MASTER, F_OWNER, F_HP = 1, 2, 12
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_reseed.bin"


def derive_army(es):
    a = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in (9, 11, 12) and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != 448
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            a[e.get(F_OWNER)].add(k)
    return a


def traced_apply(doc, data, entity_store, world_id):
    """apply_patch copy that records every executed op's start offset + kind."""
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]
    trace = []           # (pos, op, f_or_None, key_or_None, is_world_entity_push)
    exc = inval = 0

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = D.SCHEMA.get(tty, {}).get(f)
        return fi if fi else ("value", False, None)

    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                inval += 1
                continue
            top_id = stack[-1]
            top = doc.models[top_id]
            ctx = ctx_stack[-1]
            if op == 1:
                trace.append((op_pos, 1, None, None, False))
                if len(stack) > 1:
                    stack.pop(); ctx_stack.pop()
            elif op == 2:
                f = r.u8()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top[f] = val
                trace.append((op_pos, 2, f, None, False))
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    ekey = ctx[1]
                    if ekey in entity_store:
                        entity_store[ekey][f] = val
            elif op == 3:
                f = r.u8()
                trace.append((op_pos, 3, f, None, False))
                cid = top.get(f)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    ctx_stack.append(("world",) if cid == world_id else None)
                else:
                    new_id = doc.register(-1)
                    top[f] = new_id
                    stack.append(new_id); ctx_stack.append(None)
            elif op == 4:
                f = r.u8(); mt = r.u8()
                trace.append((op_pos, 4, f, None, False))
                cid = doc.register(mt)
                top[f] = cid; stack.append(cid); ctx_stack.append(None)
            elif op == 5:
                f = r.u8(); top.pop(f, None)
                trace.append((op_pos, 5, f, None, False))
            elif op == 6:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
                trace.append((op_pos, 6, f, k, False))
            elif op == 7:
                f = r.u8(); k = r.i32()
                is_we = (ctx == ("world",) and f == 1)
                trace.append((op_pos, 7, f, k, is_we))
                cid = top.get(f, {}).get(k) if isinstance(top.get(f), dict) else None
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    ctx_stack.append(("entity", k) if is_we else None)
                    if is_we and k not in entity_store:
                        entity_store[k] = {"__type__": doc.models[cid]["__type__"]}
                else:
                    new_id = doc.register(
                        entity_store.get(k, {}).get("__type__", -1) if is_we else -1)
                    if f not in top:
                        top[f] = {}
                    top.get(f, {})[k] = new_id
                    stack.append(new_id)
                    if is_we:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[new_id]["__type__"]}
                    else:
                        ctx_stack.append(None)
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32()
                trace.append((op_pos, 8, f, k, False))
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid)
                if ctx == ("world",) and f == 1 and mt in D.ENTITY_TYPES:
                    ctx_stack.append(("entity", k))
                    entity_store[k] = {"__type__": mt}
                else:
                    ctx_stack.append(None)
            elif op == 9:
                f = r.u8(); k = r.i32()
                trace.append((op_pos, 9, f, k, ctx == ("world",) and f == 1))
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
            elif op == 10:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
                trace.append((op_pos, 10, f, k, False))
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid); ctx_stack.append(None)
                trace.append((op_pos, 11, f, k, False))
            elif op == 12:
                f = r.u8(); k = r.i32()
                trace.append((op_pos, 12, f, k, ctx == ("world",) and f == 1))
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
            elif op == 13:
                r.u8(); r.i32(); r.i32()
                trace.append((op_pos, 13, None, None, False))
            elif op == 14:
                r.u8(); r.i32()
                trace.append((op_pos, 14, None, None, False))
        except Exception:
            exc += 1
            r.p = op_pos + 1
            while len(stack) > len(ctx_stack):
                ctx_stack.append(None)
            while len(ctx_stack) > len(stack):
                ctx_stack.pop()
    return trace, exc, inval


def main():
    doc = es = army = world_id = None
    fight = False
    n_delta = 0
    seeded_keys = set()

    cand_true = cand_other_op7 = cand_other_opstart = cand_payload = 0
    asc_ok = asc_bad = 0
    next_op_after_true = Counter()
    hp_traj = {}          # army key -> list of (t, hp)
    n_clean = 0

    with open(PFX + ".frames.bin", "rb") as f:
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
                p = fr.patch
                t = fr.time / 1000.0
                if p and len(p) > 400_000:
                    with open(TMP, "wb") as sf:
                        sf.write(p)
                    doc = D.Doc()
                    es2 = {}
                    _, world_id = D.seed_from_snapshot(TMP, doc, es2)
                    es = es2
                    a = derive_army(es)
                    if len(a[2]) == 24 and len(a[3]) == 30:
                        fight = True
                        army = a
                        seeded_keys = set(es.keys())
                    continue
                if not fight or es is None or not p:
                    continue
                n_delta += 1
                allk = army[2] | army[3]
                pre = {k: (es.get(k) or {}).get(F_HP) for k in allk}
                trace, exc, inval = traced_apply(doc, p, es, world_id)
                for k in allk:
                    post = (es.get(k) or {}).get(F_HP)
                    if post != pre[k]:
                        hp_traj.setdefault(k, []).append((round(t, 2), post))
                if exc or inval:
                    continue  # only validate markers against CLEAN ground truth
                n_clean += 1
                # raw-scan candidates
                cands = []
                i, n = 0, len(p)
                while i < n - 6:
                    if p[i] == 7 and p[i + 1] == 1:
                        k = struct.unpack_from("<i", p, i + 2)[0]
                        if k in seeded_keys:
                            cands.append((i, k))
                    i += 1
                pos2op = {pos: (op, fld, key, iswe) for pos, op, fld, key, iswe in trace}
                true_pushes = [(pos, key) for pos, op, fld, key, iswe in trace
                               if op == 7 and iswe]
                true_pos = {pos for pos, _ in true_pushes}
                for pos, k in cands:
                    if pos in true_pos:
                        cand_true += 1
                        # next executed op byte after the 6-byte marker
                        nxt = pos2op.get(pos + 6)
                        next_op_after_true[nxt[0] if nxt else p[pos + 6]] += 1
                    elif pos in pos2op:
                        if pos2op[pos][0] == 7:
                            cand_other_op7 += 1
                        else:
                            cand_other_opstart += 1
                    else:
                        cand_payload += 1
                keys_seq = [key for _, key in true_pushes]
                if keys_seq == sorted(keys_seq):
                    asc_ok += 1
                else:
                    asc_bad += 1
                if n_delta >= 2400:
                    break
            if n_delta >= 2400:
                break

    print(f"deltas={n_delta} clean={n_clean}")
    print(f"CAND(07 01 seeded-key) classification over clean patches:")
    print(f"  true World.entities push : {cand_true}")
    print(f"  op7 at other ctx/depth   : {cand_other_op7}")
    print(f"  other-op start position  : {cand_other_opstart}")
    print(f"  inside payload bytes     : {cand_payload}")
    print(f"ascending-key order of true pushes: ok={asc_ok} violated={asc_bad}")
    print(f"op following a true entity push: {dict(next_op_after_true)}")

    # HP trajectories for army units
    print(f"\narmy units with delta HP changes: {len(hp_traj)}/54")
    zero_times = []
    for k in sorted(army[2] | army[3]):
        tr = hp_traj.get(k, [])
        side = 1 if k in army[2] else 2
        z = next((tt for tt, v in tr
                  if isinstance(v, (int, float)) and v <= 0), None)
        last = tr[-1] if tr else None
        zero_times.append((k, side, z))
        print(f"  key={k} side{side} events={len(tr)} "
              f"first<=0 at t={z} last={last}")
    s1z = sorted(z for k, s, z in zero_times if s == 1 and z is not None)
    print(f"\nside1 HP<=0 times ({len(s1z)}/24): {s1z}")


if __name__ == "__main__":
    main()
