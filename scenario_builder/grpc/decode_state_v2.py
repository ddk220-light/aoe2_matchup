"""decode_state_v2.py — ground-truth entity state decoder for AoE2:DE gRPC capture.

Architecture:
  - Flat Document model (mirrors uncage-model's document.rs / patcher.rs exactly).
  - Seeds from first_patch_seg2.bin by seeking to the World.entities band (bytes
    ~4.547M-4.775M) to avoid the per-player master-entity definition drift zone
    (gameVersion 177723 added new model types 47/49 and new fields 76/77/81 on
    MasterCombatEntity that break the 2024 schema's String-field width guessing).
  - Applies per-frame delta patches from GAME_munq_vs_ddk220_incas_frames_raw.bin
    (length-delimited stream: [u32-LE length][FrameSequence protobuf]).
  - Tracks entity creates/updates/deletions and EntityKilled events.
  - Reports entity composition at several game-time checkpoints.

Run:
  python decode_state_v2.py [max_sequences]
  # max_sequences: 0 = all (196k), default = 10000 for a quick check
"""

import re
import struct
import sys
import json
import os
from collections import Counter, defaultdict

import cade_api_pb2 as pb

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCALARS = {
    "u8":   ("<B", 1),  "i8":   ("<b", 1),
    "u16":  ("<H", 2),  "i16":  ("<h", 2),
    "u32":  ("<I", 4),  "i32":  ("<i", 4),
    "u64":  ("<Q", 8),  "i64":  ("<q", 8),
    "f32":  ("<f", 4),  "f64":  ("<d", 8),
    "bool": ("<?", 1),
    "u128": ("16s", 16), "i128": ("16s", 16),
}

def parse_schema(path):
    txt = open(path).read()
    structs = {}
    name_to_type = {}
    for m in re.finditer(
        r"#\[uncage\(type = (\d+)\)\]\s*pub struct (\w+)\s*\{(.*?)\n\}",
        txt, re.S
    ):
        ty, name, body = int(m.group(1)), m.group(2), m.group(3)
        name_to_type[name] = ty
        fields, parent = {}, None
        for fm in re.finditer(
            r"#\[uncage\(([^\]]*)\)\]\s*pub (\w+):\s*([^,\n]+)", body
        ):
            attrs, _, ftype = fm.group(1), fm.group(2), fm.group(3).strip().rstrip(",")
            if "extends" in attrs:
                parent = ftype
                continue
            idxm = re.search(r"index = (\d+)", attrs)
            if idxm:
                fields[int(idxm.group(1))] = ftype
        structs[name] = {"type": ty, "fields": fields, "extends": parent}

    type2struct = {s["type"]: s for s in structs.values()}

    def flat_fields(ty, seen=None):
        seen = seen or set()
        if ty not in type2struct or ty in seen:
            return {}
        seen.add(ty)
        s = type2struct[ty]
        merged = {}
        if s["extends"] and s["extends"] in name_to_type:
            merged.update(flat_fields(name_to_type[s["extends"]], seen))
        merged.update(s["fields"])
        return merged

    def field_info(rust_ty):
        """Returns (value_type, is_model, scalar_rust_or_None).
        value_type in {'value', 'map', 'list'}.
        is_model=True means the slot holds a child document id (Ref), not a scalar.
        """
        t = rust_ty.strip()
        # Map
        m = re.match(r"(?:Model)?(?:BTreeMap|HashMap)<\s*([^,]+),\s*(.+)>$", t)
        if m:
            val = m.group(2).strip()
            is_model = (t.startswith("Model") or val == "Ref"
                        or val.startswith("ModelRef")
                        or (val not in SCALARS and val != "String"))
            scal = val if val in SCALARS else ("String" if val == "String" else None)
            return ("map", is_model, scal)
        # Vec
        m = re.match(r"(?:Model)?Vec<(.+)>$", t)
        if m:
            val = m.group(1).strip()
            is_model = (t.startswith("ModelVec") or val == "Ref"
                        or val.startswith("ModelRef")
                        or (val not in SCALARS and val != "String"))
            scal = val if val in SCALARS else ("String" if val == "String" else None)
            return ("list", is_model, scal)
        # Ref / ModelRef
        if t == "Ref" or t.startswith("ModelRef"):
            return ("value", True, None)
        if t in SCALARS:
            return ("value", False, t)
        if t == "String":
            return ("value", False, "String")
        if t in name_to_type:
            return ("value", True, None)
        return ("value", False, None)  # unknown

    # Build schema: type_id -> {field_idx -> (vt, is_model, scalar)}
    schema = {}
    for s in structs.values():
        ff = flat_fields(s["type"])
        schema[s["type"]] = {
            idx: field_info(rust) for idx, rust in ff.items()
        }

    # Apply known patches for gameVersion 177723
    patches = {
        35: {  # GameOptions
            48: ("value", False, "f32"),
            50: ("value", False, "u8"),
            51: ("value", False, "i32"),
        },
        36: {  # PlayerGameOptions
            18: ("value", False, "i32"),
            19: ("value", False, "u64"),
        },
        1: {   # World
            29: ("value", False, "i32"),
        },
    }
    for ty, fields in patches.items():
        schema.setdefault(ty, {}).update(fields)

    return schema, name_to_type, type2struct

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA, NAME2TYPE, TYPE2STRUCT = parse_schema(
    os.path.join(_SCRIPT_DIR, "reference_model.rs")
)

# Entity model types (live instances, NOT master-entity definitions)
ENTITY_TYPES = {9, 10, 11, 12, 13, 14}


def _next_entity_marker(data, pos, limit=200_000):
    """Find the next live-entity create marker (08 01 <entity_mt> <valid key>) at/after
    `pos`. Used to RE-ANCHOR the snapshot decode after a resync inside a drifting master-
    entity definition, so the corruption can't cascade into losing the next live entity."""
    end = min(len(data) - 6, pos + limit)
    i = pos
    while i < end:
        if data[i] == 8 and data[i + 1] == 1 and data[i + 2] in ENTITY_TYPES:
            k = struct.unpack_from("<i", data, i + 3)[0]
            if 0 < k < 1_000_000:
                return i
        i += 1
    return None


def _next_delta_marker(data, pos, known_keys):
    """Nearest re-anchor target at/after pos inside a DELTA patch."""
    n = len(data)
    i = pos
    while i < n - 6:
        b = data[i]
        if data[i + 1] == 1:
            if b == 7 and i + 7 <= n:
                k = struct.unpack_from("<i", data, i + 2)[0]
                if k in known_keys and (i + 6 >= n or 1 <= data[i + 6] <= 14):
                    return i
            elif b in (9, 12):
                k = struct.unpack_from("<i", data, i + 2)[0]
                if k in known_keys:
                    return i
            elif b == 8 and i + 8 <= n and data[i + 2] in ENTITY_TYPES:
                k = struct.unpack_from("<i", data, i + 3)[0]
                if 0 < k < 1_000_000 and 1 <= data[i + 7] <= 14:
                    return i
        i += 1
    return None


# ---------------------------------------------------------------------------
# Byte reader helpers
# ---------------------------------------------------------------------------
class Reader:
    __slots__ = ("d", "p")

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
        if n < 0 or n > 65536:
            raise ValueError(f"suspicious string length {n}")
        s = self.d[self.p:self.p + n].decode("utf-8", "replace")
        self.p += n
        return s


# ---------------------------------------------------------------------------
# Lookahead guesser for unknown (drift) fields
# ---------------------------------------------------------------------------
_STRUCT_ARGS = {
    1: 0, 3: 1, 4: 2, 5: 1,
    7: 5, 8: 6, 9: 5, 11: 6,
    12: 5, 13: 9, 14: 5,
}


def _op_ok(d, p, depth=2):
    if p >= len(d):
        return False
    op = d[p]
    if not (1 <= op <= 14):
        return False
    if depth <= 1:
        return True
    if op in _STRUCT_ARGS:
        return _op_ok(d, p + 1 + _STRUCT_ARGS[op], depth - 1)
    return True  # value op: accept


def guess_value(r):
    for w in (1, 2, 4, 8):
        if _op_ok(r.d, r.p + w, 2):
            r.p += w
            return None
    r.p += 4
    return None


def read_value(r, vt, is_model, scal):
    """Read a scalar or string value payload.  Model refs don't appear as value payloads."""
    if is_model:
        # Shouldn't be a value assign on a model ref field, but handle gracefully
        guess_value(r)
        return None
    if scal is None:
        guess_value(r)
        return None
    if scal == "String":
        return r.string()
    return r.scalar(scal)


# ---------------------------------------------------------------------------
# Flat Document
# ---------------------------------------------------------------------------
class Doc:
    """Mirrors uncage-model's InnerDocument: a flat id -> model store.
    model = {'__type__': int, field_idx -> value, ...}
    Map/list fields that are model-ref containers hold {key -> child_id}.
    Model-ref scalar fields hold the child_id directly.
    """

    __slots__ = ("models", "next", "root")

    def __init__(self):
        self.models = {}
        self.next = 0
        self.root = self._alloc(0)  # Root = type 0, id 0

    def _alloc(self, mtype):
        i = self.next
        self.next += 1
        self.models[i] = {"__type__": mtype}
        return i

    def register(self, mtype):
        return self._alloc(mtype)


# ---------------------------------------------------------------------------
# Patch applier
# ---------------------------------------------------------------------------
def apply_patch(doc, data, entity_store, world_id):
    """Apply one patch buffer to doc.  Updates entity_store in-place.

    entity_store: {entity_key (i32) -> {'__type__', field_idx -> value}}
      Mirrors World.entities[key], maintained separately for fast access.
    world_id: document id of the World model (or None if not yet discovered).

    Re-anchor recovery: any desync signal — an exception, an invalid op byte,
    or an attempted descent into an undecodable model (the silent guess_value
    ctx-depth drift) — jumps to the next valid delta marker found by
    _next_delta_marker (op7/9/12 on a known entity key, or an op8 entity
    create) and resets the parse stack to [Root, World].  If no marker
    remains, the rest of the patch is abandoned.  Return value = number of
    re-anchors (was: number of one-byte resync steps).
    """
    r = Reader(data)
    stack = [doc.root]       # stack of document ids
    # Parallel "path" stack to know when we're inside World.entities[key].
    # Each element: None | ('world',) | ('entity', key)
    ctx_stack = [None]
    resyncs = 0

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = SCHEMA.get(tty, {}).get(f)
        return fi if fi else ("value", False, None)

    def reanchor(from_pos):
        nonlocal stack, ctx_stack, resyncs
        resyncs += 1
        if world_id is None:
            # No World context to anchor to; abandon the rest of the patch.
            r.p = len(data)
            return
        nxt = _next_delta_marker(data, from_pos, entity_store.keys())
        if nxt is None:
            r.p = len(data)            # nothing decodable left
            return
        r.p = nxt
        stack = [doc.root, world_id]
        ctx_stack = [None, ("world",)]

    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                reanchor(op_pos + 1)   # silent desync detected
                continue
            top_id = stack[-1]
            top = doc.models[top_id]
            ctx = ctx_stack[-1]

            if op == 1:
                if len(stack) > 1:
                    stack.pop(); ctx_stack.pop()
            elif op == 2:
                f = r.u8()
                vt, ism, scal = finfo_for(top_id, f)
                val = read_value(r, vt, ism, scal)
                top[f] = val
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    ekey = ctx[1]
                    if ekey in entity_store:
                        entity_store[ekey][f] = val
            elif op == 3:
                f = r.u8()
                cid = top.get(f)
                if (isinstance(cid, int) and cid in doc.models
                        and doc.models[cid]["__type__"] in SCHEMA):
                    stack.append(cid)
                    ctx_stack.append(("world",) if cid == world_id else None)
                else:
                    reanchor(op_pos + 1)   # unknown child model: undecodable subtree
            elif op == 4:
                f = r.u8(); mt = r.u8()
                if mt not in SCHEMA:
                    reanchor(op_pos + 1)
                    continue
                cid = doc.register(mt)
                top[f] = cid; stack.append(cid); ctx_stack.append(None)
            elif op == 5:
                f = r.u8(); top.pop(f, None)
            elif op == 6:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
            elif op == 7:
                f = r.u8(); k = r.i32()
                is_we = (ctx == ("world",) and f == 1)
                fmap = top.get(f)
                cid = fmap.get(k) if isinstance(fmap, dict) else None
                if (isinstance(cid, int) and cid in doc.models
                        and doc.models[cid]["__type__"] in SCHEMA):
                    stack.append(cid)
                    if is_we:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[cid]["__type__"]}
                    else:
                        ctx_stack.append(None)
                elif is_we and k in entity_store:
                    # entity known from seed but absent in doc: placeholder w/ real type
                    new_id = doc.register(entity_store[k].get("__type__", 9))
                    top.setdefault(f, {})[k] = new_id
                    stack.append(new_id)
                    ctx_stack.append(("entity", k))
                else:
                    reanchor(op_pos + 1)   # unknown child / ghost entity key
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32()
                if ctx == ("world",) and f == 1 and mt in ENTITY_TYPES:
                    cid = doc.register(mt)
                    top.setdefault(f, {})[k] = cid
                    stack.append(cid)
                    ctx_stack.append(("entity", k))
                    entity_store[k] = {"__type__": mt}
                elif mt in SCHEMA:
                    cid = doc.register(mt)
                    top.setdefault(f, {})[k] = cid
                    stack.append(cid)
                    ctx_stack.append(None)
                else:
                    reanchor(op_pos + 1)
            elif op == 9:
                f = r.u8(); k = r.i32()
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
            elif op == 10:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32()
                if mt not in SCHEMA:
                    reanchor(op_pos + 1)
                    continue
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid); ctx_stack.append(None)
            elif op == 12:
                f = r.u8(); k = r.i32()
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
            elif op == 13:
                r.u8(); r.i32(); r.i32()
            elif op == 14:
                r.u8(); r.i32()
        except Exception:
            reanchor(op_pos + 1)
    return resyncs


# ---------------------------------------------------------------------------
# Snapshot seeder: locate World.entities band in first_patch_seg2.bin
# and decode only that section into entity_store + doc with correct entity ids.
# ---------------------------------------------------------------------------
def seed_from_snapshot(snap_path, doc, entity_store):
    """Scan snap_path for the entity-creation band (op8 field=1 Entity types)
    and decode it into entity_store.  Returns (count, world_id).
    """
    data = open(snap_path, "rb").read()
    print(f"  snapshot: {len(data):,} bytes")

    # The World model is at Root.field0. We need to register it in the Doc
    # so that deltas can PushField(0) -> World correctly.
    # Register a synthetic World at doc and store its id in Root.
    world_id = doc.register(1)
    doc.models[doc.root][0] = world_id

    # Locate the entity band: first occurrence of op8 field=1 modeltype in ENTITY_TYPES
    # Pattern: 0x08 0x01 <mt> where mt in {9,10,11,12,13,14}
    entity_mt_bytes = bytes(ENTITY_TYPES)
    band_start = None
    for i in range(len(data) - 3):
        if data[i] == 8 and data[i + 1] == 1 and data[i + 2] in entity_mt_bytes:
            # Validate: following 4 bytes = plausible i32 entity key (positive, < 1_000_000)
            if i + 6 < len(data):
                key = struct.unpack_from("<i", data, i + 3)[0]
                if 0 < key < 1_000_000:
                    band_start = i
                    print(f"  entity band start: byte {band_start:,} (key={key})")
                    break

    if band_start is None:
        print("  ERROR: could not locate entity band in snapshot!")
        return 0, world_id

    # Set up a synthetic World model in the doc stack so the entity creates land under it
    # Stack: [root_id, world_id]  -> entities are being assigned into World.field1
    r = Reader(data)
    r.p = band_start
    stack = [world_id]
    ctx_stack = [("world",)]
    entity_creates = 0
    resyncs = 0

    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                # Once we exit the entity band we get garbage; stop cleanly
                if entity_creates > 100:
                    break
                continue

            top_id = stack[-1]
            top = doc.models[top_id]
            ctx = ctx_stack[-1]

            if op == 1:
                if len(stack) > 1:
                    stack.pop()
                    ctx_stack.pop()

            elif op == 2:
                f = r.u8()
                tty = top["__type__"]
                fi = SCHEMA.get(tty, {}).get(f)
                if fi:
                    vt, ism, scal = fi
                    val = read_value(r, vt, ism, scal)
                else:
                    val = None
                    guess_value(r)
                top[f] = val
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    ekey = ctx[1]
                    if ekey in entity_store:
                        entity_store[ekey][f] = val

            elif op == 3:
                f = r.u8()
                cid = top.get(f)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    ctx_stack.append(None)
                else:
                    stack.append(top_id)
                    ctx_stack.append(ctx)

            elif op == 4:
                f = r.u8()
                mt = r.u8()
                cid = doc.register(mt)
                top[f] = cid
                stack.append(cid)
                ctx_stack.append(None)

            elif op == 5:
                f = r.u8()
                top.pop(f, None)

            elif op == 6:
                f = r.u8(); k = r.i32()
                tty = top["__type__"]
                fi = SCHEMA.get(tty, {}).get(f)
                if fi:
                    vt, ism, scal = fi
                    val = read_value(r, vt, ism, scal)
                else:
                    guess_value(r); val = None
                top.setdefault(f, {})[k] = val

            elif op == 7:
                f = r.u8(); k = r.i32()
                cid = top.get(f, {}).get(k)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                    else:
                        ctx_stack.append(None)
                else:
                    stack.append(top_id)
                    ctx_stack.append(ctx)

            elif op == 8:   # PushCreateAndAssignKey — entity create
                f = r.u8()
                mt = r.u8()
                k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid)
                if ctx == ("world",) and f == 1 and mt in ENTITY_TYPES:
                    ctx_stack.append(("entity", k))
                    entity_store[k] = {"__type__": mt}
                    entity_creates += 1
                else:
                    ctx_stack.append(None)

            elif op == 9:
                f = r.u8(); k = r.i32()
                m = top.get(f)
                if isinstance(m, dict): m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)

            elif op == 10:
                f = r.u8(); k = r.i32()
                tty = top["__type__"]
                fi = SCHEMA.get(tty, {}).get(f)
                if fi:
                    vt, ism, scal = fi
                    val = read_value(r, vt, ism, scal)
                else:
                    guess_value(r); val = None
                top.setdefault(f, {})[k] = val

            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid)
                ctx_stack.append(None)

            elif op == 12:
                f = r.u8(); k = r.i32()
                m = top.get(f)
                if isinstance(m, dict): m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)

            elif op == 13:
                r.u8(); r.i32(); r.i32()

            elif op == 14:
                r.u8(); r.i32()

        except Exception:
            resyncs += 1
            # A resync almost always means we drifted inside a master-entity DEFINITION (the
            # 178524 drift zone) that a live entity inlines AFTER its own fields (incl. HP).
            # Byte-skipping cascades into losing the next entity, so instead RE-ANCHOR to the
            # next live-entity marker and reset to the World context.
            nxt = _next_entity_marker(data, op_pos + 1)
            if nxt is not None:
                r.p = nxt
                stack = [world_id]
                ctx_stack = [("world",)]
            else:
                r.p = op_pos + 1
                while len(stack) > len(ctx_stack):
                    ctx_stack.append(None)
                while len(ctx_stack) > len(stack):
                    ctx_stack.pop()

    print(f"  snapshot decode: {entity_creates} entities created, {resyncs} resyncs")
    return entity_creates, world_id


# ---------------------------------------------------------------------------
# Load aocref unit name table
# ---------------------------------------------------------------------------
def load_unit_names():
    try:
        import aocref
        pkg_dir = os.path.dirname(aocref.__file__)
        dataset_path = os.path.join(pkg_dir, "data", "datasets", "100.json")
        with open(dataset_path) as f:
            ds = json.load(f)
        return {int(k): v for k, v in ds.get("objects", {}).items()}
    except Exception as e:
        print(f"  (aocref not available: {e}; unit names will show as ids)")
        return {}


# ---------------------------------------------------------------------------
# Frame sequence reader
# ---------------------------------------------------------------------------
def read_frame_sequences(path):
    data = open(path, "rb").read()
    pos = 0
    while pos + 4 <= len(data):
        n = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if pos + n > len(data):
            break
        yield data[pos:pos + n]
        pos += n


# ---------------------------------------------------------------------------
# Entity snapshot helper
# ---------------------------------------------------------------------------
def snapshot_entity_store(entity_store):
    """Return {owner -> Counter(master_id -> count)} for live entities."""
    by_owner = defaultdict(Counter)
    for ekey, e in entity_store.items():
        master = e.get(1)
        owner = e.get(2, 0)  # default 0 = Gaia
        if master is not None:
            by_owner[owner][master] += 1
    return by_owner


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    max_seqs = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    snap_path = os.path.join(_SCRIPT_DIR, "first_patch_seg2.bin")
    frames_path = os.path.join(_SCRIPT_DIR, "GAME_munq_vs_ddk220_incas_frames_raw.bin")

    unit_names = load_unit_names()

    def uname(mid):
        if mid is None:
            return "?"
        return unit_names.get(mid, f"id{mid}")

    print("=" * 70)
    print("decode_state_v2.py — AoE2:DE gRPC ground-truth entity decoder")
    print("=" * 70)

    # Step 1: Build flat document and seed from snapshot entity band
    doc = Doc()
    entity_store = {}   # {entity_key (i32) -> {field_idx -> value, '__type__' -> mt}}
    world_id = None

    if os.path.exists(snap_path):
        print(f"\n[1] Seeding from snapshot: {snap_path}")
        _, world_id = seed_from_snapshot(snap_path, doc, entity_store)
        print(f"    Entities seeded: {len(entity_store)}")

        # Validate snapshot
        real = {k: e for k, e in entity_store.items() if e.get(1) is not None}
        owned = {k: e for k, e in real.items() if e.get(2, 0) != 0}
        print(f"    With master_id: {len(real)}   Player-owned (non-gaia): {len(owned)}")

        # Print position range check
        xs = [e.get(3) for e in real.values() if e.get(3) is not None]
        ys = [e.get(4) for e in real.values() if e.get(4) is not None]
        if xs:
            print(f"    Position range x=[{min(xs):.1f}..{max(xs):.1f}] y=[{min(ys):.1f}..{max(ys):.1f}]")
    else:
        print(f"\n[1] Snapshot not found at {snap_path}; starting empty (deltas only).")
        world_id = doc.register(1)
        doc.models[doc.root][0] = world_id
        print("    WARNING: Without snapshot seed, ~71+ pre-existing entities won't be typed.")

    # Store the entity map in the World model as well (for reference)
    # The doc's World model will accumulate entity ids via op8 in the deltas too.
    world_model = doc.models[world_id]
    # Sync existing entity_store keys into doc's World.entities (field 1) map
    # so that op7 PushKey can find them.
    world_ents_in_doc = world_model.setdefault(1, {})
    for ekey, e in entity_store.items():
        if ekey not in world_ents_in_doc:
            # Register a doc model for this entity
            cid = doc.register(e.get("__type__", 9))
            world_ents_in_doc[ekey] = cid
            # Copy all known fields into that doc model
            dm = doc.models[cid]
            for fk, fv in e.items():
                dm[fk] = fv

    print(f"\n[2] Applying delta frames from: {frames_path}")
    print(f"    max_sequences={max_seqs if max_seqs else 'all'}")

    # Checkpoint times (ms) at which to record population snapshots
    checkpoint_targets = [5_000, 30_000, 120_000, 300_000, 600_000,
                          900_000, 1_200_000, 1_800_000, 2_400_000]
    checkpoints = {}   # gametime_ms -> snapshot

    seq_count = 0
    frame_count = 0
    delta_count = 0
    snapshot_count = 0
    kill_count = 0
    total_resyncs = 0
    last_time_ms = 520

    # For end-to-end entity creation tracking from deltas
    delta_creates = 0
    delta_kills = 0

    for raw_seq in read_frame_sequences(frames_path):
        if max_seqs and seq_count >= max_seqs:
            break
        seq_count += 1

        try:
            sq = pb.FrameSequence()
            sq.ParseFromString(raw_seq)
        except Exception as e:
            continue

        for fr in sq.frame:
            frame_count += 1
            t = fr.time

            if fr.patch:
                plen = len(fr.patch)
                if plen > 500_000:
                    # Full-state snapshot (the drift zone) — skip to avoid desync
                    snapshot_count += 1
                    # Don't update last_time_ms for skipped snapshots
                    continue
                else:
                    before_creates = len(entity_store)
                    rs = apply_patch(doc, fr.patch, entity_store, world_id)
                    total_resyncs += rs
                    delta_creates += max(0, len(entity_store) - before_creates)
                    delta_count += 1

            for ev in fr.event:
                which = ev.WhichOneof("event")
                if which == "entityKilled":
                    ek = ev.entityKilled
                    kill_count += 1
                    delta_kills += 1
                    # Remove entity from store
                    entity_store.pop(ek.id, None)

            # Update time and record checkpoints AFTER applying the patch
            if t:
                last_time_ms = t
            # Record checkpoint snapshots (only for real delta frames)
            for cp in checkpoint_targets:
                if cp not in checkpoints and last_time_ms >= cp:
                    checkpoints[cp] = (last_time_ms, snapshot_entity_store(entity_store))

    print(f"\n    Processed: {seq_count} sequences, {frame_count} frames")
    print(f"    Deltas applied: {delta_count}, snapshots skipped: {snapshot_count}")
    print(f"    EntityKilled events: {kill_count}")
    print(f"    Total patch resyncs: {total_resyncs}")
    print(f"    Entities created via deltas: {delta_creates}")
    print(f"    Final game time: {last_time_ms/1000:.1f}s ({last_time_ms/60000:.1f}min)")

    # ---- Final entity analysis ----
    print("\n" + "=" * 70)
    print("FINAL ENTITY STATE")
    print("=" * 70)
    real = {k: e for k, e in entity_store.items() if e.get(1) is not None}
    print(f"Total live entities: {len(entity_store)}")
    print(f"Entities with master_id (typed): {len(real)}")

    # Sanity: position bounds
    xs = [e.get(3) for e in real.values() if e.get(3) is not None]
    ys = [e.get(4) for e in real.values() if e.get(4) is not None]
    if xs:
        print(f"Position range x=[{min(xs):.1f}..{max(xs):.1f}] y=[{min(ys):.1f}..{max(ys):.1f}]")
        oob = sum(1 for x in xs if not (0 <= x <= 240))
        print(f"Out-of-bounds positions (x outside 0-240): {oob}")

    # Per-owner, per-type breakdown
    by_owner = defaultdict(Counter)
    for e in real.values():
        owner = e.get(2, 0)
        by_owner[owner][e.get(1)] += 1

    owner_labels = {0: "Gaia", 1: "P1(munq)", 2: "P2(ddk220)"}
    for owner in sorted(by_owner.keys()):
        label = owner_labels.get(owner, f"owner{owner}")
        total = sum(by_owner[owner].values())
        print(f"\n  {label}: {total} units/buildings")
        for mid, cnt in by_owner[owner].most_common(20):
            print(f"    {uname(mid):30s} (id={mid:5d})  x{cnt}")

    # ---- Sample entities ----
    print("\nSAMPLE ENTITIES (first 15 player-owned):")
    print(f"{'id':>8}  {'type_name':30s}  {'mid':>6}  {'owner':>5}  {'x':>7}  {'y':>7}  {'hp':>7}  {'state':>5}")
    shown = 0
    for ekey, e in entity_store.items():
        owner = e.get(2, 0)
        if owner == 0:
            continue
        mid = e.get(1)
        x = e.get(3)
        y = e.get(4)
        hp = e.get(12)
        state = e.get(8)
        print(f"  {ekey:8d}  {uname(mid):30s}  {str(mid):>6}  {owner:>5}  "
              f"{str(round(x,1)) if x is not None else '?':>7}  "
              f"{str(round(y,1)) if y is not None else '?':>7}  "
              f"{str(round(hp,1)) if hp is not None else '?':>7}  "
              f"{str(state) if state is not None else '?':>5}")
        shown += 1
        if shown >= 15:
            break

    # ---- Checkpoint timeline ----
    print("\nPOPULATION OVER TIME:")
    print(f"{'time':>12}  {'P1_units':>10}  {'P2_units':>10}  {'Gaia':>8}")

    # Add initial snapshot (t=520ms)
    init_snap = snapshot_entity_store(entity_store)
    # We'll show checkpoints + final
    show_checkpoints = []
    for cp in sorted(checkpoints.keys()):
        show_checkpoints.append(checkpoints[cp])
    show_checkpoints.append((last_time_ms, snapshot_entity_store(entity_store)))

    # Rebuild initial from entity_store at snapshot time isn't possible (we've overwritten it)
    # Just show what we have
    for t, snap in show_checkpoints:
        p1 = sum(snap.get(1, {}).values())
        p2 = sum(snap.get(2, {}).values())
        g  = sum(snap.get(0, {}).values())
        print(f"  {t/1000:8.1f}s    {p1:10d}  {p2:10d}  {g:8d}")

    print("\nVALIDATION CHECKS:")
    # 1. Player-owned entities
    p1_total = sum(by_owner.get(1, {}).values())
    p2_total = sum(by_owner.get(2, {}).values())
    print(f"  P1 entities: {p1_total}  P2 entities: {p2_total}")
    if p1_total > 5 and p2_total > 5:
        print("  PASS: both players have entities")
    else:
        print("  WARN: one or both players have very few entities")

    # 2. Check for TCs (master_id=109)
    tc_owners = [(e.get(2, 0), e.get(1)) for e in real.values() if e.get(1) == 109]
    print(f"  Town Centers (id=109): {len(tc_owners)}  owners={[o for o,_ in tc_owners]}")

    # 3. Check for villagers (83 or 293)
    vills = sum(1 for e in real.values() if e.get(1) in (83, 293))
    print(f"  Villagers (83/293): {vills}")

    # 4. Position sanity
    if xs:
        in_bounds = sum(1 for x, y in zip(xs, ys) if 0 <= x <= 240 and 0 <= y <= 240)
        pct = 100 * in_bounds / len(xs)
        print(f"  Positions in 0-240: {in_bounds}/{len(xs)} ({pct:.1f}%)")
        if pct >= 95:
            print("  PASS: positions look valid")
        else:
            print("  WARN: many out-of-bounds positions")

    print("\nDone.")


if __name__ == "__main__":
    main()
