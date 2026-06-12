"""Replay to the onset frame, then verbose-trace that patch to find the field whose wrong
width causes the resync."""
import struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
import cade_api_pb2 as pb

PFX = r"C:\dev\aoe2\aoe2record\lab\run1"; TARGET = 464
doc = D.Doc(); es = {}; _, world_id = D.seed_from_snapshot(PFX + ".seed_snap.bin", doc, es)
f = open(PFX + ".frames.bin", "rb"); fi = 0; patch = None
while patch is None:
    hdr = f.read(4)
    if len(hdr) < 4:
        break
    ln = struct.unpack("<I", hdr)[0]; buf = f.read(ln)
    if len(buf) < ln:
        break
    sq = pb.FrameSequence(); sq.ParseFromString(buf)
    for fr in sq.frame:
        p = fr.patch
        if not p or len(p) > 400_000:
            continue
        fi += 1
        if fi == TARGET:
            patch = p; break
        D.apply_patch(doc, p, es, world_id)
f.close()
print(f"replayed to frame {fi}; tracing patch ({len(patch)} B)")

SCHEMA = D.SCHEMA; ENT = D.ENTITY_TYPES
data = patch; r = D.Reader(data); stack = [doc.root]; ctx = [None]; log = []
while r.p < len(data):
    op_pos = r.p
    try:
        op = r.u8()
        if not (1 <= op <= 14):
            log.append((op_pos, "BADOP", f"byte={op:#x}")); continue
        tty = doc.models[stack[-1]]["__type__"]; c = ctx[-1]; top = doc.models[stack[-1]]
        if op == 2:
            fld = r.u8(); fi2 = SCHEMA.get(tty, {}).get(fld); b = r.p
            vt, ism, scal = fi2 if fi2 else ("value", False, None)
            val = D.read_value(r, vt, ism, scal); top[fld] = val
            isent = isinstance(c, tuple) and c[0] == "entity"
            if isent and c[1] in es:
                es[c[1]][fld] = val
            log.append((op_pos, "Assign", f"tty={tty} f={fld} known={fi2 is not None} "
                        f"w={r.p-b} val={val} ent={isent}"))
        elif op == 1:
            if len(stack) > 1: stack.pop(); ctx.pop()
            log.append((op_pos, "Pop", ""))
        elif op == 3:
            fld = r.u8(); cid = top.get(fld)
            if isinstance(cid, int) and cid in doc.models:
                stack.append(cid); ctx.append(("world",) if cid == world_id else None)
            else:
                nid = doc.register(-1); top[fld] = nid; stack.append(nid); ctx.append(None)
            log.append((op_pos, "Push", f"tty={tty} f={fld}"))
        elif op == 4:
            fld = r.u8(); mt = r.u8(); cid = doc.register(mt); top[fld] = cid; stack.append(cid)
            ctx.append(("world",) if (tty == 0 and fld == 0 and mt == 1) else None)
            log.append((op_pos, "PushCreate", f"f={fld} mt={mt}"))
        elif op == 7:
            fld = r.u8(); k = r.i32(); cid = top.get(fld, {}).get(k)
            if isinstance(cid, int) and cid in doc.models:
                stack.append(cid)
                ctx.append(("entity", k) if (c == ("world",) and fld == 1) else None)
                if c == ("world",) and fld == 1:
                    es.setdefault(k, {"__type__": doc.models[cid]["__type__"]})
            else:
                nid = doc.register(es.get(k, {}).get("__type__", -1) if (c == ("world",) and fld == 1) else -1)
                top.setdefault(fld, {})[k] = nid; stack.append(nid)
                ctx.append(("entity", k) if (c == ("world",) and fld == 1) else None)
            log.append((op_pos, "PushKey", f"tty={tty} f={fld} k={k} ent_type={doc.models[stack[-1]]['__type__']}"))
        elif op == 8:
            fld = r.u8(); mt = r.u8(); k = r.i32(); cid = doc.register(mt)
            top.setdefault(fld, {})[k] = cid; stack.append(cid)
            if c == ("world",) and fld == 1 and mt in ENT:
                ctx.append(("entity", k)); es[k] = {"__type__": mt}
            else:
                ctx.append(None)
            log.append((op_pos, "PushCreateKey", f"f={fld} mt={mt} k={k}"))
        elif op == 9:
            fld = r.u8(); k = r.i32(); m = top.get(fld)
            if isinstance(m, dict): m.pop(k, None)
            if c == ("world",) and fld == 1: es.pop(k, None)
            log.append((op_pos, "ResetKey/death", f"f={fld} k={k}"))
        elif op in (6, 10):
            fld = r.u8(); k = r.i32(); fi2 = SCHEMA.get(tty, {}).get(fld); b = r.p
            vt, ism, scal = fi2 if fi2 else ("value", False, None); D.read_value(r, vt, ism, scal)
            log.append((op_pos, "AssignKey/Insert", f"tty={tty} f={fld} k={k} known={fi2 is not None} w={r.p-b}"))
        elif op == 5:
            fld = r.u8(); top.pop(fld, None); log.append((op_pos, "Reset", f"f={fld}"))
        elif op == 11:
            fld = r.u8(); mt = r.u8(); k = r.i32(); cid = doc.register(mt)
            top.setdefault(fld, {})[k] = cid; stack.append(cid); ctx.append(None)
            log.append((op_pos, "PushCreateInsert", f"f={fld} mt={mt} k={k}"))
        elif op == 12:
            fld = r.u8(); k = r.i32(); m = top.get(fld)
            if isinstance(m, dict): m.pop(k, None)
            if c == ("world",) and fld == 1: es.pop(k, None)
            log.append((op_pos, "Remove", f"f={fld} k={k}"))
        elif op == 13:
            r.u8(); r.i32(); r.i32(); log.append((op_pos, "Swap", ""))
        elif op == 14:
            r.u8(); r.i32(); log.append((op_pos, "Resize", ""))
    except Exception as e:
        log.append((op_pos, "!!RESYNC!!", f"{type(e).__name__} {str(e)[:40]} byte={data[op_pos]:#x}"))
        r.p = op_pos + 1
        while len(stack) > len(ctx): ctx.append(None)
        while len(ctx) > len(stack): ctx.pop()

idxs = [i for i, L in enumerate(log) if L[1] == "!!RESYNC!!"]
print(f"{len(log)} ops, {len(idxs)} resyncs")
for ri in idxs[:5]:
    print(f"\n=== around resync (log#{ri}) ===")
    for L in log[max(0, ri - 7):ri + 2]:
        print(f"  @{L[0]:5} {L[1]:18} {L[2]}")
