"""_wf_probe_markers.py — empirical probe of DELTA patch structure in the fight segment.

Answers:
 1. How is World entered in a delta patch (first bytes)?
 2. Which re-anchor marker patterns exist in deltas:
      07 01 <seeded key>      (PushKey into World.entities)
      08 01 <mt> <plaus key>  (snapshot-style create marker)
      09 01 <seeded key>      (ResetKey death)
      0c 01 <seeded key>      (Remove death)
 3. Current-code failure shape: exceptions vs silent invalid-op storms,
    per-patch desync position vs marker positions after it.
"""
import struct
import sys
from collections import Counter

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

PFX = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
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


def scan_markers(data, seeded_keys):
    """Raw byte scan for candidate marker patterns."""
    out = {"op7": [], "op8": [], "op9": [], "op12": [], "op7_unseeded_plaus": 0}
    n = len(data)
    i = 0
    while i < n - 6:
        b = data[i]
        if data[i + 1] == 1:
            if b == 7 and i + 6 <= n:
                k = struct.unpack_from("<i", data, i + 2)[0]
                if k in seeded_keys:
                    out["op7"].append((i, k))
                elif 0 < k < 1_000_000:
                    out["op7_unseeded_plaus"] += 1
            elif b == 8 and i + 7 <= n and data[i + 2] in D.ENTITY_TYPES:
                k = struct.unpack_from("<i", data, i + 3)[0]
                if 0 < k < 1_000_000:
                    out["op8"].append((i, data[i + 2], k))
            elif b == 9 and i + 6 <= n:
                k = struct.unpack_from("<i", data, i + 2)[0]
                if k in seeded_keys:
                    out["op9"].append((i, k))
            elif b == 12 and i + 6 <= n:
                k = struct.unpack_from("<i", data, i + 2)[0]
                if k in seeded_keys:
                    out["op12"].append((i, k))
        i += 1
    return out


def instrumented_apply(doc, data, entity_store, world_id):
    """Copy of apply_patch dispatch skeleton with desync instrumentation.
    Tracks: exceptions, invalid-op bytes (silent continue), first desync pos."""
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]
    stats = {"exc": 0, "invalid": 0, "first_bad": None, "max_invalid_run": 0,
             "ops": Counter(), "entity_pushes": 0, "ghost_creates": 0}
    run = 0

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = D.SCHEMA.get(tty, {}).get(f)
        return fi if fi else ("value", False, None)

    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                stats["invalid"] += 1
                run += 1
                stats["max_invalid_run"] = max(stats["max_invalid_run"], run)
                if stats["first_bad"] is None:
                    stats["first_bad"] = op_pos
                continue
            run = 0
            stats["ops"][op] += 1
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
                cid = top.get(f, {}).get(k) if isinstance(top.get(f), dict) else None
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        stats["entity_pushes"] += 1
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
                        stats["entity_pushes"] += 1
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[new_id]["__type__"]}
                            stats["ghost_creates"] += 1
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
            stats["exc"] += 1
            if stats["first_bad"] is None:
                stats["first_bad"] = op_pos
            r.p = op_pos + 1
            while len(stack) > len(ctx_stack):
                ctx_stack.append(None)
            while len(ctx_stack) > len(stack):
                ctx_stack.pop()
    return stats


def main():
    doc = es = army = world_id = None
    fight = False
    n_delta = 0
    agg = Counter()
    per_patch = []
    death_ops = []   # (game_s, op, key, byte_pos, patch_len)
    first_bytes = Counter()
    seeded_keys = set()
    key_range = None

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
                        allk = sorted(es.keys())
                        key_range = (allk[0], allk[-1], len(allk))
                    continue
                if not fight or es is None or not p:
                    continue
                n_delta += 1
                first_bytes[bytes(p[:4])] += 1
                mk = scan_markers(p, seeded_keys)
                agg["op7"] += len(mk["op7"])
                agg["op8"] += len(mk["op8"])
                agg["op9"] += len(mk["op9"])
                agg["op12"] += len(mk["op12"])
                agg["op7_unseeded_plaus"] += mk["op7_unseeded_plaus"]
                for pos, k in mk["op9"]:
                    death_ops.append((round(t, 2), 9, k, pos, len(p)))
                for pos, k in mk["op12"]:
                    death_ops.append((round(t, 2), 12, k, pos, len(p)))
                stats = instrumented_apply(doc, p, es, world_id)
                per_patch.append((round(t, 2), len(p), stats, mk))
                if n_delta >= 1200:   # enough for the fight (~30 game-s)
                    break
            if n_delta >= 1200:
                break

    print(f"fight deltas probed: {n_delta}")
    print(f"seeded entity keys: n={key_range[2]} range=[{key_range[0]}..{key_range[1]}]")
    print(f"army keys side1={len(army[2])} side2={len(army[3])}")
    print(f"first 4 bytes of delta patches: {dict(first_bytes)}")
    print(f"marker totals over {n_delta} deltas: {dict(agg)}")
    ak = army[2] | army[3]
    army_deaths = [(t, op, k) for (t, op, k, pos, pl) in death_ops if k in ak]
    print(f"raw-scan death ops on ARMY keys: {len(army_deaths)}")
    for t, op, k in army_deaths[:80]:
        side = 1 if k in army[2] else 2
        print(f"  t={t:6.2f}  op={op:2d}  key={k}  side{side}")

    # failure shape summary
    n_exc = sum(s["exc"] for _, _, s, _ in per_patch)
    n_inv = sum(s["invalid"] for _, _, s, _ in per_patch)
    bad_patches = [(t, ln, s, mk) for (t, ln, s, mk) in per_patch
                   if s["exc"] or s["invalid"]]
    print(f"\npatches with desync: {len(bad_patches)}/{len(per_patch)}  "
          f"total exceptions={n_exc}  total invalid-op bytes={n_inv}")
    print("sample desynced patches (t, len, first_bad, exc, invalid, maxrun, "
          "markers-after-first_bad op7/op8/op9/op12):")
    shown = 0
    for t, ln, s, mk in bad_patches:
        fb = s["first_bad"]
        after = {k2: sum(1 for e in mk[k2] if e[0] > fb)
                 for k2 in ("op7", "op8", "op9", "op12")}
        print(f"  t={t:6.2f} len={ln:6d} first_bad={fb:6d} exc={s['exc']:3d} "
              f"inv={s['invalid']:4d} maxrun={s['max_invalid_run']:3d} after={after} "
              f"ghosts={s['ghost_creates']}")
        shown += 1
        if shown >= 25:
            break
    clean = [(t, ln, s) for (t, ln, s, _) in per_patch if not (s["exc"] or s["invalid"])]
    print(f"\nclean patches: {len(clean)}; op histogram across ALL patches:")
    tot = Counter()
    for _, _, s, _ in per_patch:
        tot.update(s["ops"])
    print(" ", dict(sorted(tot.items())))


if __name__ == "__main__":
    main()
