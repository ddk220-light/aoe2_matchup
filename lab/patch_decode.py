"""Decode a CadeRemote state `patch` (the 14-instruction stack delta) into the
real game state, using the field schema auto-parsed from reference_model.rs.

Output: every Entity with (id, master_id=unit type, owner_id, world_x/y, hp) =
GROUND TRUTH. Run on first_patch.bin (the initial full-state snapshot).
"""
import re
import struct
import sys
from collections import Counter

# ---------- 1. parse the model schema from reference_model.rs ----------
SCALARS = {
    "u8": ("<B", 1), "i8": ("<b", 1), "u16": ("<H", 2), "i16": ("<h", 2),
    "u32": ("<I", 4), "i32": ("<i", 4), "f32": ("<f", 4), "f64": ("<d", 8),
    "u64": ("<Q", 8), "i64": ("<q", 8),
    "bool": ("<?", 1),
}


def classify(ty):
    """-> ('scalar', rust_type) | ('string',) | ('ref',) | ('list', elem) | ('map', valelem)"""
    ty = ty.strip()
    if ty in SCALARS:
        return ("scalar", ty)
    if ty == "String":
        return ("string",)
    m = re.match(r"(?:Model)?(?:Vec)<(.+)>$", ty) or re.match(r"Vec<(.+)>$", ty)
    if m:
        return ("list", m.group(1).strip())
    m = re.match(r"(?:Model)?(?:BTreeMap|HashMap)<\s*[^,]+,\s*(.+)>$", ty)
    if m:
        return ("map", m.group(1).strip())
    # Ref, ModelRef<T>, or any bare model name -> a model reference
    return ("ref",)


def parse_schema(path):
    txt = open(path).read()
    structs = {}          # name -> {'type':int, 'fields':{idx:type}, 'extends':parentName|None}
    name_to_type = {}
    for m in re.finditer(r"#\[uncage\(type = (\d+)\)\]\s*pub struct (\w+)\s*\{(.*?)\n\}", txt, re.S):
        ty, name, body = int(m.group(1)), m.group(2), m.group(3)
        name_to_type[name] = ty
        fields, parent = {}, None
        for fm in re.finditer(r"#\[uncage\(([^\]]*)\)\]\s*pub (\w+):\s*([^,\n]+)", body):
            attrs, fname, ftype = fm.group(1), fm.group(2), fm.group(3).strip().rstrip(",")
            idxm = re.search(r"index = (\d+)", attrs)
            if "extends" in attrs:
                parent = ftype  # the parent struct name
                continue
            if idxm:
                fields[int(idxm.group(1))] = ftype
        structs[name] = {"type": ty, "fields": fields, "extends": parent}

    # flatten via extends; build {model_type:int -> {field_idx -> classify(type)}}
    def flat(name, seen=None):
        seen = seen or set()
        if name in seen:
            return {}
        seen.add(name)
        s = structs[name]
        merged = {}
        if s["extends"]:
            merged.update(flat(s["extends"], seen))
        merged.update(s["fields"])
        return merged

    schema = {}
    for name, s in structs.items():
        schema[s["type"]] = {idx: classify(t) for idx, t in flat(name).items()}
    return schema, name_to_type


SCHEMA, NAME2TYPE = parse_schema("reference_model.rs")
TYPE2NAME = {v: k for k, v in NAME2TYPE.items()}


# ---------- 2. the patcher ----------
class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def scalar(self, rust):
        fmt, n = SCALARS[rust]
        v = struct.unpack_from(fmt, self.d, self.p)[0]
        self.p += n
        return v

    def string(self):
        n = self.i32()
        s = self.d[self.p:self.p + n].decode("utf-8", "replace")
        self.p += n
        return s


# fixed #bytes of args after a STRUCTURAL opcode (ops with no value payload)
_STRUCT_ARGS = {1: 0, 3: 1, 4: 2, 5: 1, 7: 5, 8: 6, 9: 5, 11: 6, 12: 5, 13: 9, 14: 5}


def _op_ok(d, p, depth=2):
    """Is position p a plausible op start? Validates `depth` ops forward through
    structural ops (value ops 2/6/10 can't be length-checked -> accepted)."""
    if p >= len(d):
        return False
    op = d[p]
    if not (1 <= op <= 14):
        return False
    if depth <= 1:
        return True
    if op in _STRUCT_ARGS:
        return _op_ok(d, p + 1 + _STRUCT_ARGS[op], depth - 1)
    return True  # value op: plausible, can't verify deeper


def guess_value(r):
    """Unknown field (new-patch model drift): determine the value width by
    lookahead. Try widths 1,2,4,8 and accept the first where the next bytes form
    a plausible op sequence (2-step). Small-int padding is 0x00 (=invalid op),
    so the correct width usually wins."""
    for w in (1, 2, 4, 8):
        if _op_ok(r.d, r.p + w, depth=2):
            v = r.d[r.p:r.p + w]
            r.p += w
            return ("g%d" % w, v.hex())
    r.p += 4  # fallback
    return ("g4?", None)


def read_value(r, kind):
    """Read a scalar/string value for AssignField / AssignKey / Insert."""
    if kind is None:
        return guess_value(r)
    if kind[0] == "scalar":
        return r.scalar(kind[1])
    if kind[0] == "string":
        return r.string()
    # element of a list/map that is itself scalar/string
    if kind[0] == "list" or kind[0] == "map":
        return read_value(r, classify(kind[1]))
    if kind[0] == "ref":
        # a bare model-id reference assigned as a value (rare); stored as i32
        return r.i32()
    raise ValueError(f"can't read value of kind {kind}")


def apply_patch(data):
    r = Reader(data)
    root = {"__type__": 0}
    stack = [root]
    ops = 0
    resyncs = 0
    while r.p < len(data):
        op_pos = r.p
        op = r.u8()
        if not (1 <= op <= 14):
            resyncs += 1
            continue  # garbage byte from a desync; skip and retry
        try:
            top = stack[-1]
            ty = top["__type__"]
            fields = SCHEMA.get(ty, {})
            ops += 1

            if op == 1:                                   # Pop
                if len(stack) > 1:
                    stack.pop()
            elif op == 2:                                 # AssignField
                f = r.u8()
                top[f] = read_value(r, fields.get(f))
            elif op == 3:                                 # PushField
                f = r.u8()
                stack.append(top.setdefault(f, {"__type__": -1}))
            elif op == 4:                                 # Push/Create/AssignField
                f = r.u8(); mt = r.u8()
                child = {"__type__": mt}
                top[f] = child
                stack.append(child)
            elif op == 5:                                 # ResetField
                f = r.u8()
                top.pop(f, None)
            elif op == 6:                                 # AssignKey
                f = r.u8(); k = r.i32()
                top.setdefault(f, {})[k] = read_value(r, fields.get(f))
            elif op == 7:                                 # PushKey (push existing)
                f = r.u8(); k = r.i32()
                stack.append(top.setdefault(f, {}).setdefault(k, {"__type__": -1}))
            elif op == 8:                                 # Push/Create/AssignKey
                f = r.u8(); mt = r.u8(); k = r.i32()
                child = {"__type__": mt}
                top.setdefault(f, {})[k] = child
                stack.append(child)
            elif op == 9:                                 # ResetKey
                f = r.u8(); k = r.i32()
                top.get(f, {}).pop(k, None)
            elif op == 10:                                # Insert
                f = r.u8(); k = r.i32()
                top.setdefault(f, {})[k] = read_value(r, fields.get(f))
            elif op == 11:                                # Push/Create/Insert
                f = r.u8(); mt = r.u8(); k = r.i32()
                child = {"__type__": mt}
                top.setdefault(f, {})[k] = child
                stack.append(child)
            elif op == 12:                                # Remove
                f = r.u8(); k = r.i32()
                top.get(f, {}).pop(k, None)
            elif op == 13:                                # Swap
                f = r.u8(); r.i32(); r.i32()
            elif op == 14:                                # Resize
                f = r.u8(); r.i32()
        except Exception:
            # arg read failed (out-of-range / drift) -> resync from just after
            # the opcode byte
            r.p = op_pos + 1
            resyncs += 1
            continue
    print(f"  decode: {ops} ops applied, {resyncs} resync skips")
    return root, ops, r.p


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "first_patch.bin"
    data = open(path, "rb").read()
    print(f"decoding {path} ({len(data)} bytes)...")
    root, ops, pos = apply_patch(data)
    print(f"applied {ops} instructions, consumed {pos}/{len(data)} bytes "
          f"({100*pos/len(data):.1f}%)")

    # walk World.entities. Root.world = field 0; World.entities = field 1.
    world = root.get(0, {})
    entities = world.get(1, {})
    print(f"World fields present: {sorted(k for k in world if isinstance(k,int))}")
    print(f"entities found: {len(entities)}")

    by_owner_type = Counter()
    sample = []
    for eid, e in entities.items():
        if not isinstance(e, dict):
            continue
        master = e.get(1)      # master_id = unit type
        owner = e.get(2)       # owner_id
        x, y = e.get(3), e.get(4)
        by_owner_type[(owner, master)] += 1
        if len(sample) < 8:
            sample.append((eid, master, owner, x, y, e.get("__type__")))
    print("\nsample entities (id, master_id, owner, x, y, modeltype):")
    for s in sample:
        print("  ", s)
    print("\nentity counts by (owner, master_id):")
    for (owner, master), n in by_owner_type.most_common(30):
        print(f"  owner={owner}  master_id={master}  count={n}")


if __name__ == "__main__":
    main()
