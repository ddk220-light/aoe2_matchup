"""_wf_fix_proto.py — PROTOTYPE of the apply_patch re-anchor port (decode_state_v2.py
is NOT modified; this file carries a patched copy) + acceptance + regression harness.

Fix mechanics under test:
  F1. Exception recovery -> re-anchor to nearest valid delta marker (was: pos+1 step).
  F2. Invalid op byte (not 1..14) -> same re-anchor (was: silent continue).
  F3. Descent into an UNKNOWN model (placeholder type -1 / mt not in SCHEMA) via
      op3/op4/op7/op8/op11 -> re-anchor instead of pushing, EXCEPT the
      World.entities op7/op8 entity paths. Kills the guess_value silent
      ctx-depth drift (the missed 781 death at t=26.00).
  Markers (nearest wins), all requiring field byte 01:
     07 01 <key in known-entity set> with next byte a valid op
     09 01 <key in known-entity set>
     0c 01 <key in known-entity set>
     08 01 <mt in ENTITY_TYPES> <0<key<1e6> with next byte a valid op
  Reset: r.p = marker; stack = [doc.root, world_id]; ctx_stack = [None, ('world',)].
  No marker after desync point -> abort rest of patch.

Usage:
  python _wf_fix_proto.py accept   # ground-truth dump: acceptance rmse (scales 1.0/1.7)
  python _wf_fix_proto.py run1     # regression: run1.frames.bin decode summary
"""
import json
import math
import struct
import sys

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

F_MASTER, F_OWNER, F_HP = 1, 2, 12
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_reseed.bin"
GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
OCR_S1 = [(0.5, 24), (6.5, 21), (7.5, 18), (8.5, 17), (9.5, 14), (10.5, 11),
          (11.5, 10), (12.5, 8), (13.5, 5), (15.5, 2), (16.5, 0)]


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
            elif b == 8 and i + 8 <= n and data[i + 2] in D.ENTITY_TYPES:
                k = struct.unpack_from("<i", data, i + 3)[0]
                if 0 < k < 1_000_000 and 1 <= data[i + 7] <= 14:
                    return i
        i += 1
    return None


def apply_patch_fixed(doc, data, entity_store, world_id):
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]
    resyncs = 0

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = D.SCHEMA.get(tty, {}).get(f)
        return fi if fi else ("value", False, None)

    def reanchor(from_pos):
        nonlocal stack, ctx_stack, resyncs
        resyncs += 1
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
                val = D.read_value(r, vt, ism, scal)
                top[f] = val
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    ekey = ctx[1]
                    if ekey in entity_store:
                        entity_store[ekey][f] = val
            elif op == 3:
                f = r.u8()
                cid = top.get(f)
                if (isinstance(cid, int) and cid in doc.models
                        and doc.models[cid]["__type__"] in D.SCHEMA):
                    stack.append(cid)
                    ctx_stack.append(("world",) if cid == world_id else None)
                else:
                    reanchor(op_pos + 1)   # unknown child model: undecodable subtree
            elif op == 4:
                f = r.u8(); mt = r.u8()
                if mt not in D.SCHEMA:
                    reanchor(op_pos + 1)
                    continue
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
                is_we = (ctx == ("world",) and f == 1)
                fmap = top.get(f)
                cid = fmap.get(k) if isinstance(fmap, dict) else None
                if (isinstance(cid, int) and cid in doc.models
                        and doc.models[cid]["__type__"] in D.SCHEMA):
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
                if ctx == ("world",) and f == 1 and mt in D.ENTITY_TYPES:
                    cid = doc.register(mt)
                    top.setdefault(f, {})[k] = cid
                    stack.append(cid)
                    ctx_stack.append(("entity", k))
                    entity_store[k] = {"__type__": mt}
                elif mt in D.SCHEMA:
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
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32()
                if mt not in D.SCHEMA:
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


def derive_army(es):
    a = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in (9, 11, 12) and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != 448
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            a[e.get(F_OWNER)].add(k)
    return a


def totals(es, army):
    out = {}
    for o in (2, 3):
        cnt, hp = 0, 0.0
        for k in army[o]:
            e = es.get(k)
            v = e.get(F_HP) if e else None
            if isinstance(v, (int, float)) and v > 0:
                cnt += 1
                hp += v
        out[o] = (cnt, round(hp, 1))
    return out


APPLY = None   # set in __main__: apply_patch_fixed or D.apply_patch


def decode(pfx, want=None):
    """Replay <pfx>.frames.bin with apply_patch_fixed. Returns the fight segment data:
    (army, death_times {key: stream_s}, rows, total_resyncs).
    want=(n1, n2) selects the fight snapshot; None = use redecode-style plausibility."""
    doc = es = army = world_id = None
    fight = False
    deaths = {}
    rows = []
    last_sec = None
    total_rs = 0
    alive_prev = set()

    with open(pfx + ".frames.bin", "rb") as f:
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
                    ok = ((want and (len(a[2]), len(a[3])) == want)
                          or (not want and 3 <= len(a[2]) <= 80
                              and 3 <= len(a[3]) <= 80))
                    if ok and not fight:
                        fight = True
                        army = a
                        alive_prev = set(a[2]) | set(a[3])
                        deaths = {}
                        rows = []
                        last_sec = None
                    continue
                if not fight or es is None:
                    continue
                if p:
                    total_rs += APPLY(doc, p, es, world_id)
                    alive_now = set()
                    for k in alive_prev:
                        e = es.get(k)
                        v = e.get(F_HP) if e else None
                        if isinstance(v, (int, float)) and v > 0:
                            alive_now.add(k)
                    for k in alive_prev - alive_now:
                        deaths[k] = t
                    alive_prev = alive_now
                sec = int(t)
                if last_sec is None or sec > last_sec:
                    last_sec = sec
                    tt = totals(es, army)
                    rows.append({"game_s": sec,
                                 "side1": {"count": tt[2][0], "hp": tt[2][1]},
                                 "side2": {"count": tt[3][0], "hp": tt[3][1]}})
    return army, deaths, rows, total_rs


def accept():
    army, deaths, rows, rs = decode(GT, want=(24, 30))
    d1 = sorted(deaths[k] for k in deaths if k in army[2])
    d2 = sorted(deaths[k] for k in deaths if k in army[3])
    print(f"total apply_patch resyncs (re-anchors): {rs}")
    print(f"side1 deaths decoded: {len(d1)}/24  stream_s: {[round(x,2) for x in d1]}")
    print(f"side2 deaths decoded: {len(d2)}/30  stream_s: {[round(x,2) for x in d2]}")
    end = next((r0["game_s"] for r0 in rows
                if min(r0["side1"]["count"], r0["side2"]["count"]) == 0), None)
    print(f"battle_end stream_s: {end}")
    fin = rows[-1]
    print(f"final row: t={fin['game_s']} side1={fin['side1']} side2={fin['side2']}")

    def fit(scale):
        best = (None, 1e9)
        off = -2.0
        while off <= 2.0001:
            sse = 0.0
            for v, cnt in OCR_S1:
                pred = 24 - sum(1 for d in d1 if d / scale + off <= v)
                sse += (pred - cnt) ** 2
            r0 = math.sqrt(sse / len(OCR_S1))
            if r0 < best[1]:
                best = (off, r0)
            off += 0.01
        return best

    for sc in (1.0, 1.7):
        off, r0 = fit(sc)
        verdict = "PASS" if r0 <= 1.0 else "FAIL"
        print(f"ACCEPTANCE scale={sc}: best_off={off:+.2f} rmse={r0:.3f}  [{verdict}]")
        if sc == 1.7:
            for v, cnt in OCR_S1:
                pred = 24 - sum(1 for d in d1 if d / sc + off <= v)
                print(f"    t={v:5.1f}  ocr={cnt:2d}  pred={pred:2d}")


def run1():
    pfx = r"C:\dev\aoe2\aoe2record\lab\run1"
    army, deaths, rows, rs = decode(pfx)
    print(f"resyncs: {rs}")
    print(f"start counts: side1={len(army[2])} side2={len(army[3])}")
    end = next((r0["game_s"] for r0 in rows
                if min(r0["side1"]["count"], r0["side2"]["count"]) == 0), None)
    print(f"side1-zero / battle_end stream_s: {end}")
    fin = rows[-1]
    print(f"final row: t={fin['game_s']} side1={fin['side1']} side2={fin['side2']}")
    d1 = sorted(deaths[k] for k in deaths if k in army[2])
    print(f"side1 deaths: {len(d1)} times={[round(x,1) for x in d1]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "accept"
    APPLY = D.apply_patch if mode.endswith("old") else apply_patch_fixed
    print(f"mode={mode}  APPLY={'OLD D.apply_patch' if mode.endswith('old') else 'FIXED'}")
    if mode.startswith("accept"):
        accept()
    else:
        run1()
