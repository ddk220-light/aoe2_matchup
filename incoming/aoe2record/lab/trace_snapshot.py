"""Trace decoder for the full-state snapshot. Runs a STRICT pass (no resync):
stop at the first op whose arg-read is impossible OR whose value type is unknown,
and dump the surrounding bytes + the live stack path. This finds the EXACT desync.
"""
import struct
import sys
from collections import Counter
import patch_decode as P

SCHEMA = P.SCHEMA
TYPE2NAME = P.TYPE2NAME

# field-name lookup for nicer traces: rebuild flat field -> name per model type
import re
def parse_field_names(path):
    txt = open(path).read()
    structs = {}
    for m in re.finditer(r"#\[uncage\(type = (\d+)\)\]\s*pub struct (\w+)\s*\{(.*?)\n\}", txt, re.S):
        ty, name, body = int(m.group(1)), m.group(2), m.group(3)
        fields, parent = {}, None
        for fm in re.finditer(r"#\[uncage\(([^\]]*)\)\]\s*pub (\w+):\s*([^,\n]+)", body):
            attrs, fname, ftype = fm.group(1), fm.group(2), fm.group(3).strip().rstrip(",")
            if "extends" in attrs:
                parent = ftype; continue
            idxm = re.search(r"index = (\d+)", attrs)
            if idxm:
                fields[int(idxm.group(1))] = (fname, ftype)
        structs[name] = {"type": ty, "fields": fields, "extends": parent}
    def flat(name, seen=None):
        seen = seen or set();
        if name in seen: return {}
        seen.add(name); s = structs[name]; merged = {}
        if s["extends"]: merged.update(flat(s["extends"], seen))
        merged.update(s["fields"]); return merged
    out = {}
    for name, s in structs.items():
        out[s["type"]] = flat(name)
    return out

FIELD_NAMES = parse_field_names("reference_model.rs")

def tname(ty):
    return TYPE2NAME.get(ty, f"type{ty}")

def fname(ty, f):
    return FIELD_NAMES.get(ty, {}).get(f, (f"f{f}", "?"))[0]

OPNAMES = {1:"Pop",2:"AssignField",3:"PushField",4:"PushCreateAssignField",
    5:"ResetField",6:"AssignKey",7:"PushKey",8:"PushCreateAssignKey",
    9:"ResetKey",10:"Insert",11:"PushCreateInsert",12:"Remove",13:"Swap",14:"Resize"}


def trace(data, stop_after=None, verbose_from=None):
    r = P.Reader(data)
    root = {"__type__": 0}
    # stack holds (model_dict, label)
    stack = [(root, "Root")]
    ops = 0
    op_history = []   # (pos, op, detail) ring
    entities_seen = set()
    first_entity_op = None
    player_master_op = None

    def path_str():
        return " > ".join(l for _, l in stack)

    while r.p < len(data):
        op_pos = r.p
        op = r.u8()
        if not (1 <= op <= 14):
            print(f"\n*** INVALID OPCODE {op} at byte {op_pos} (op #{ops}) ***")
            print(f"path: {path_str()}")
            ctx = data[max(0,op_pos-24):op_pos+24]
            print(f"bytes around: {ctx.hex()}")
            print(f"  (^ desync at offset {op_pos}, byte={op:#x})")
            return root, ops, op_pos, "invalid_op"
        top, label = stack[-1]
        ty = top["__type__"]
        fields = SCHEMA.get(ty, {})
        detail = ""
        try:
            if op == 1:
                if len(stack) > 1: stack.pop()
                detail = "Pop"
            elif op == 2:
                f = r.u8(); kind = fields.get(f)
                if kind is None:
                    # UNKNOWN FIELD - this is the drift point
                    print(f"\n*** UNKNOWN FIELD {f} on {tname(ty)} at byte {op_pos} (op #{ops}) ***")
                    print(f"path: {path_str()}")
                    print(f"  op=AssignField field={f} -> not in schema for {tname(ty)} (type {ty})")
                    print(f"  known fields: {sorted(fields.keys())}")
                    ctx = data[max(0,op_pos-32):op_pos+32]
                    print(f"  bytes around: {ctx.hex()}")
                    return root, ops, op_pos, f"unknown_field {tname(ty)}.{f}"
                v = P.read_value(r, kind)
                top[f] = v
                detail = f"AssignField {tname(ty)}.{fname(ty,f)}={v}"
            elif op == 3:
                f = r.u8(); child = top.setdefault(f, {"__type__": -1})
                stack.append((child, f"{fname(ty,f)}"))
                detail = f"PushField {tname(ty)}.{fname(ty,f)}"
            elif op == 4:
                f = r.u8(); mt = r.u8(); child = {"__type__": mt}; top[f] = child
                stack.append((child, f"{fname(ty,f)}:{tname(mt)}"))
                detail = f"PushCreateAssignField {tname(ty)}.{fname(ty,f)} = new {tname(mt)}"
            elif op == 5:
                f = r.u8(); top.pop(f, None); detail = f"ResetField {tname(ty)}.{fname(ty,f)}"
            elif op == 6:
                f = r.u8(); k = r.i32(); kind = fields.get(f)
                if kind is None:
                    print(f"\n*** UNKNOWN MAP FIELD {f} on {tname(ty)} at byte {op_pos} (op #{ops}) ***")
                    print(f"path: {path_str()}")
                    ctx = data[max(0,op_pos-32):op_pos+32]
                    print(f"  bytes around: {ctx.hex()}")
                    return root, ops, op_pos, f"unknown_mapfield {tname(ty)}.{f}"
                v = P.read_value(r, kind)
                top.setdefault(f, {})[k] = v
                detail = f"AssignKey {tname(ty)}.{fname(ty,f)}[{k}]={v}"
            elif op == 7:
                f = r.u8(); k = r.i32(); child = top.setdefault(f, {}).setdefault(k, {"__type__": -1})
                stack.append((child, f"{fname(ty,f)}[{k}]"))
                detail = f"PushKey {tname(ty)}.{fname(ty,f)}[{k}]"
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32(); child = {"__type__": mt}
                top.setdefault(f, {})[k] = child
                stack.append((child, f"{fname(ty,f)}[{k}]:{tname(mt)}"))
                detail = f"PushCreateAssignKey {tname(ty)}.{fname(ty,f)}[{k}] = new {tname(mt)}"
                if ty == 1 and f == 1:   # World.entities
                    entities_seen.add(k)
                    if first_entity_op is None:
                        first_entity_op = ops
                if ty == 5 and f == 4:   # Player.master_entities
                    if player_master_op is None:
                        player_master_op = ops
            elif op == 9:
                f = r.u8(); k = r.i32(); top.get(f, {}).pop(k, None); detail="ResetKey"
            elif op == 10:
                f = r.u8(); k = r.i32(); kind = fields.get(f)
                v = P.read_value(r, kind)
                top.setdefault(f, {})[k] = v
                detail = f"Insert {tname(ty)}.{fname(ty,f)}[{k}]={v}"
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32(); child = {"__type__": mt}
                top.setdefault(f, {})[k] = child
                stack.append((child, f"{fname(ty,f)}[{k}]:{tname(mt)}"))
                detail = f"PushCreateInsert {tname(ty)}.{fname(ty,f)}[{k}] = new {tname(mt)}"
            elif op == 12:
                f = r.u8(); k = r.i32(); detail="Remove"
            elif op == 13:
                f = r.u8(); r.i32(); r.i32(); detail="Swap"
            elif op == 14:
                f = r.u8(); n = r.i32(); detail=f"Resize {tname(ty)}.{fname(ty,f)} -> {n}"
        except Exception as ex:
            print(f"\n*** READ EXCEPTION at byte {op_pos} (op #{ops}) op={OPNAMES[op]}: {ex} ***")
            print(f"path: {path_str()}")
            return root, ops, op_pos, f"exception {ex}"
        ops += 1
        op_history.append((op_pos, op, detail))
        if verbose_from is not None and ops >= verbose_from:
            print(f"#{ops} @{op_pos}: {detail}")
        if stop_after and ops >= stop_after:
            break

    print(f"\nreached end cleanly: {ops} ops, consumed {r.p}/{len(data)}")
    return root, ops, r.p, "clean"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "first_patch_seg2.bin"
    data = open(path, "rb").read()
    print(f"tracing {path} ({len(data)} bytes)")
    root, ops, pos, reason = trace(data)
    print(f"\nSTOPPED: reason={reason}, after {ops} ops, at byte {pos} ({100*pos/len(data):.2f}%)")

    # report structure reached
    world = root.get(0, {})
    if isinstance(world, dict):
        ents = world.get(1, {})
        print(f"World present: {0 in root}, World fields: {sorted(k for k in world if isinstance(k,int))}")
        if isinstance(ents, dict):
            real = {k:v for k,v in ents.items() if isinstance(v,dict)}
            print(f"World.entities reached: {len(real)} entries")
            mt = Counter(v.get('__type__') for v in real.values())
            print(f"  entity model types: {dict(mt)}")
        players = world.get(2, {})
        if isinstance(players, dict):
            print(f"World.players reached: {len([k for k,v in players.items() if isinstance(v,dict)])}")


if __name__ == "__main__":
    main()
