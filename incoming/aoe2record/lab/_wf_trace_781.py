"""_wf_trace_781.py — find why entity 781's op9 (ResetKey on World.entities) is missed
even by the re-anchor prototype. Locates fight-segment delta patches containing the
byte pattern 09 01 <781 le i32>, then replays them with a tracing apply_patch_fixed
that logs every executed op in a +/-80 byte window around the pattern, with stack
depth + ctx, plus all desync/re-anchor events in that patch.
"""
import struct
import sys

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402
import _wf_fix_proto as FX           # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_reseed.bin"
F_HP = 12
KEY = 781
PAT = bytes([9, 1]) + struct.pack("<i", KEY)


def traced_apply_fixed(doc, data, entity_store, world_id, win):
    """Same mechanics as FX.apply_patch_fixed but logs ops inside [win0,win1] and
    all reanchor events."""
    win0, win1 = win
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]
    log = []

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = D.SCHEMA.get(tty, {}).get(f)
        return fi if fi else ("value", False, None)

    def reanchor(from_pos, why):
        nonlocal stack, ctx_stack
        nxt = FX._next_delta_marker(data, from_pos, entity_store.keys())
        log.append(("REANCHOR", from_pos, why, nxt))
        if nxt is None:
            r.p = len(data)
            return
        r.p = nxt
        stack = [doc.root, world_id]
        ctx_stack = [None, ("world",)]

    while r.p < len(data):
        op_pos = r.p
        inwin = win0 <= op_pos <= win1
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                reanchor(op_pos + 1, f"invalid op byte {op}")
                continue
            top_id = stack[-1]
            top = doc.models[top_id]
            ctx = ctx_stack[-1]
            if inwin:
                log.append(("OP", op_pos, op, len(stack), ctx,
                            doc.models[top_id]["__type__"]))
            if op == 1:
                if len(stack) > 1:
                    stack.pop(); ctx_stack.pop()
            elif op == 2:
                f = r.u8()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top[f] = val
                if inwin:
                    log.append(("  assign", op_pos, f, val))
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    if ctx[1] in entity_store:
                        entity_store[ctx[1]][f] = val
            elif op == 3:
                f = r.u8()
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
                cid = doc.register(mt)
                top[f] = cid; stack.append(cid); ctx_stack.append(None)
            elif op == 5:
                f = r.u8(); top.pop(f, None)
            elif op == 6:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
            elif op == 7:
                f = r.u8(); k = r.i32()
                if inwin:
                    log.append(("  pushkey", op_pos, f, k))
                fmap = top.get(f)
                cid = fmap.get(k) if isinstance(fmap, dict) else None
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[cid]["__type__"]}
                    else:
                        ctx_stack.append(None)
                else:
                    new_id = doc.register(
                        entity_store.get(k, {}).get("__type__", -1)
                        if (ctx == ("world",) and f == 1) else -1)
                    if f not in top:
                        top[f] = {}
                    top.get(f, {})[k] = new_id
                    stack.append(new_id)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[new_id]["__type__"]}
                    else:
                        ctx_stack.append(None)
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32()
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
                if inwin or k == KEY:
                    log.append(("  resetkey", op_pos, f, k, len(stack), ctx,
                                doc.models[top_id]["__type__"]))
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
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid); ctx_stack.append(None)
            elif op == 12:
                f = r.u8(); k = r.i32()
                if inwin or k == KEY:
                    log.append(("  remove", op_pos, f, k, len(stack), ctx))
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
            elif op == 13:
                r.u8(); r.i32(); r.i32()
            elif op == 14:
                r.u8(); r.i32()
        except Exception as e:
            reanchor(op_pos + 1, f"exc {type(e).__name__} op@{op_pos}")
    return log


def main():
    doc = es = world_id = None
    fight = False
    found = 0
    with open(GT + ".frames.bin", "rb") as f:
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
                    fight = True
                    continue
                if not fight or not p:
                    continue
                hit = p.find(PAT)
                if hit >= 0:
                    found += 1
                    print(f"\n=== patch t={t:.2f} len={len(p)} "
                          f"pattern 09 01 <781> at byte {hit} ===")
                    print("hex around pattern:",
                          p[max(0, hit - 24):hit + 12].hex(" "))
                    log = traced_apply_fixed(doc, p, es, world_id,
                                             (hit - 80, hit + 12))
                    for entry in log:
                        print("   ", entry)
                    print(f"   781 in entity_store after: {781 in es}  "
                          f"hp={es.get(781, {}).get(F_HP)}")
                else:
                    FX.apply_patch_fixed(doc, p, es, world_id)
    print(f"\npatches containing the 781 death pattern: {found}")


if __name__ == "__main__":
    main()
