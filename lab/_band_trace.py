"""Replicate seed_from_snapshot's band decode with a rolling op-trail; dump the trail at
the first resync to find the ROOT divergence (the field whose width drifted on 178524)."""
import os, struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
SCHEMA, ENT = D.SCHEMA, D.ENTITY_TYPES
TYPE = {0: "Root", 1: "World", 9: "Entity", 11: "ActionEntity", 12: "CombatEntity",
        14: "Building", 18: "MasterCombatEntity", 29: "Sprite", -1: "?"}
data = open(os.path.join(r"C:\dev\aoe2\aoe2record\lab", "val_latest_snap.bin"), "rb").read()

# locate band start (same as seed_from_snapshot)
bs = None
for i in range(len(data) - 6):
    if data[i] == 8 and data[i + 1] == 1 and data[i + 2] in ENT:
        k = struct.unpack_from("<i", data, i + 3)[0]
        if 0 < k < 1_000_000:
            bs = i; break

doc = D.Doc(); world_id = doc.register(1); doc.models[doc.root][0] = world_id
r = D.Reader(data); r.p = bs
stack = [world_id]; trail = []


def tname():
    return TYPE.get(doc.models[stack[-1]]["__type__"], doc.models[stack[-1]]["__type__"])


resyncs = 0
while r.p < len(data) and resyncs < 1:
    op_pos = r.p
    try:
        op = r.u8()
        if not (1 <= op <= 14):
            continue
        top = doc.models[stack[-1]]; tty = top["__type__"]
        rec = f"@{op_pos} {tname()} op{op}"
        if op == 1:
            if len(stack) > 1: stack.pop()
        elif op == 2:
            f = r.u8(); fi = SCHEMA.get(tty, {}).get(f); b = r.p
            if fi:
                v = D.read_value(r, *fi)
            else:
                D.guess_value(r); v = "?"
            rec += f" f{f}={v}(w{r.p-b}{'' if fi else '*GUESS'})"
        elif op == 3:
            f = r.u8(); cid = top.get(f)
            if isinstance(cid, int) and cid in doc.models: stack.append(cid)
            else:
                nid = doc.register(-1); top[f] = nid; stack.append(nid)
            rec += f" f{f}->push({tname()})"
        elif op == 4:
            f = r.u8(); mt = r.u8(); cid = doc.register(mt); top[f] = cid; stack.append(cid)
            rec += f" f{f} create+push mt={TYPE.get(mt,mt)}"
        elif op == 5:
            f = r.u8(); top.pop(f, None); rec += f" reset f{f}"
        elif op == 6:
            f = r.u8(); k = r.i32(); fi = SCHEMA.get(tty, {}).get(f); b = r.p
            if fi: D.read_value(r, *fi)
            else: D.guess_value(r)
            rec += f" f{f}[{k}]=val(w{r.p-b}{'' if fi else '*GUESS'})"
        elif op == 7:
            f = r.u8(); k = r.i32(); cid = top.get(f, {}).get(k) if isinstance(top.get(f), dict) else None
            if isinstance(cid, int) and cid in doc.models: stack.append(cid)
            else: stack.append(stack[-1])
            rec += f" f{f}[{k}]->push({tname()})"
        elif op == 8:
            f = r.u8(); mt = r.u8(); k = r.i32(); cid = doc.register(mt)
            top.setdefault(f, {})[k] = cid; stack.append(cid)
            rec += f" f{f}[{k}] create+push mt={TYPE.get(mt,mt)}"
        elif op == 9:
            f = r.u8(); k = r.i32(); rec += f" resetkey f{f}[{k}]"
        elif op == 10:
            f = r.u8(); k = r.i32(); fi = SCHEMA.get(tty, {}).get(f); b = r.p
            if fi: D.read_value(r, *fi)
            else: D.guess_value(r)
            rec += f" insert f{f}[{k}](w{r.p-b}{'' if fi else '*GUESS'})"
        elif op == 11:
            f = r.u8(); mt = r.u8(); k = r.i32(); cid = doc.register(mt)
            top.setdefault(f, {})[k] = cid; stack.append(cid)
            rec += f" f{f}[{k}] create+insert mt={TYPE.get(mt,mt)}"
        elif op == 12:
            f = r.u8(); k = r.i32(); rec += f" remove f{f}[{k}]"
        elif op == 13:
            r.u8(); r.i32(); r.i32(); rec += " swap"
        elif op == 14:
            r.u8(); r.i32(); rec += " resize"
        trail.append(rec)
    except Exception as e:
        trail.append(f"@{op_pos} {tname()} op{data[op_pos]} !!RESYNC!! {type(e).__name__} "
                     f"bytes={data[op_pos-2:op_pos+10].hex()}")
        resyncs += 1
        r.p = op_pos + 1

print(f"band start @{bs}; first resync after {len(trail)} ops\n--- last 30 ops ---")
for t in trail[-30:]:
    print("  " + t)
