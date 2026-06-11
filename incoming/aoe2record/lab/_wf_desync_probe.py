"""_wf_desync_probe.py — empirically characterize apply_patch desyncs in REAL delta patches.

Seeds from the Guecha-vs-Jaguar ground-truth dump exactly like _diag_delta_deaths.py
(>400KB patch via seed_from_snapshot; fight instance = 24 vs 30 army), then runs an
INSTRUMENTED faithful copy of decode_state_v2.apply_patch over the fight delta frames.

Measures:
  1. every decode exception (op byte, field id, reader pos, ctx depth, top model type),
     runs of silently-skipped bytes, per-patch army-entity HP mirror writes.
  2. which raw-scan marker reliably indicates the next REAL entity record inside a DELTA
     (07 01 <known key> vs 01 07 01 <known key> vs snapshot-style 08 01 <mt> <key>),
     with false-positive rates measured against decoder-truth positions in CLEAN patches.
  3. how many fight delta patches desync, at what byte-fraction the first desync lands,
     and how many army HP updates are lost per desynced patch.

No existing files are modified. ASCII-only output (cp1252 console).
Run:  python _wf_desync_probe.py   (cwd C:\\dev\\aoe2grpc)
"""
import struct
import sys
from collections import Counter

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs).frames.bin")
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_seed_tmp.bin"
F_MASTER, F_OWNER, F_HP = 1, 2, 12
ENTITY_TYPES = D.ENTITY_TYPES        # {9,10,11,12,13,14}


def derive_army(es):
    a = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in (9, 11, 12) and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != 448
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            a[e.get(F_OWNER)].add(k)
    return a


# ---------------------------------------------------------------------------
# Instrumented FAITHFUL copy of decode_state_v2.apply_patch (semantics identical;
# only adds logging). Copied rather than editing the module.
# ---------------------------------------------------------------------------
def apply_patch_probe(doc, data, entity_store, world_id, army_keys):
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]
    rec = {
        "size": len(data),
        "exc": [],                  # list of dicts per exception
        "skip_before": 0,           # bytes skipped (op not in 1..14) before 1st exception
        "skip_after": 0,
        "skip_runs": [],            # [start_pos, length] runs (capped)
        "ops_before": 0,
        "ops_after": 0,
        "op_hist_before": Counter(),
        "op_hist_after": Counter(),
        "f_hist_before": Counter(),
        "f_hist_after": Counter(),
        "hp_writes": [],            # (op_pos, ekey, val, after_desync_bool)
        "visits": [],               # (op_pos, key, depth_after_push, after_desync_bool)
        "creates": [],              # (op_pos, key, mt, after_desync_bool)
        "head_ops": [],             # first 8 (op_pos, op, extra) for structure check
        "max_depth": 1,
    }
    desynced = False
    cur_run = None

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = D.SCHEMA.get(tty, {}).get(f)
        if fi:
            return fi
        return ("value", False, None)

    while r.p < len(data):
        op_pos = r.p
        op = None
        f_local = None
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                if desynced:
                    rec["skip_after"] += 1
                else:
                    rec["skip_before"] += 1
                if cur_run is not None and cur_run[0] + cur_run[1] == op_pos:
                    cur_run[1] += 1
                else:
                    cur_run = [op_pos, 1]
                    if len(rec["skip_runs"]) < 200:
                        rec["skip_runs"].append(cur_run)
                continue
            if desynced:
                rec["ops_after"] += 1
                rec["op_hist_after"][op] += 1
            else:
                rec["ops_before"] += 1
                rec["op_hist_before"][op] += 1
            top_id = stack[-1]
            top = doc.models[top_id]
            ctx = ctx_stack[-1]

            if op == 1:
                if len(stack) > 1:
                    stack.pop()
                    ctx_stack.pop()
                if len(rec["head_ops"]) < 8:
                    rec["head_ops"].append((op_pos, 1, None))

            elif op == 2:
                f = r.u8(); f_local = f
                (rec["f_hist_after"] if desynced else rec["f_hist_before"])[f] += 1
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top[f] = val
                if isinstance(ctx, tuple) and ctx[0] == "entity":
                    ekey = ctx[1]
                    if ekey in entity_store:
                        entity_store[ekey][f] = val
                    if f == F_HP and ekey in army_keys:
                        rec["hp_writes"].append(
                            (op_pos, ekey,
                             val if isinstance(val, (int, float)) else None,
                             desynced))
                if len(rec["head_ops"]) < 8:
                    rec["head_ops"].append((op_pos, 2, f))

            elif op == 3:
                f = r.u8(); f_local = f
                (rec["f_hist_after"] if desynced else rec["f_hist_before"])[f] += 1
                cid = top.get(f)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    if cid == world_id:
                        ctx_stack.append(("world",))
                    else:
                        ctx_stack.append(None)
                else:
                    new_id = doc.register(-1)
                    top[f] = new_id
                    stack.append(new_id)
                    ctx_stack.append(None)
                if len(rec["head_ops"]) < 8:
                    rec["head_ops"].append((op_pos, 3, f))

            elif op == 4:
                f = r.u8(); f_local = f
                mt = r.u8()
                cid = doc.register(mt)
                top[f] = cid
                stack.append(cid)
                nonlocal_world = None
                if doc.models[top_id]["__type__"] == 0 and f == 0 and mt == 1:
                    nonlocal_world = cid
                ctx_stack.append(("world",) if nonlocal_world else None)
                if len(rec["head_ops"]) < 8:
                    rec["head_ops"].append((op_pos, 4, (f, mt)))

            elif op == 5:
                f = r.u8(); f_local = f
                top.pop(f, None)

            elif op == 6:
                f = r.u8(); f_local = f
                k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val

            elif op == 7:
                f = r.u8(); f_local = f
                k = r.i32()
                (rec["f_hist_after"] if desynced else rec["f_hist_before"])[f] += 1
                cid = top.get(f, {}).get(k) if isinstance(top.get(f, {}), dict) else None
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[cid]["__type__"]}
                        rec["visits"].append((op_pos, k, len(stack), desynced))
                    else:
                        ctx_stack.append(None)
                else:
                    new_id = doc.register(
                        entity_store.get(k, {}).get("__type__", -1)
                        if (ctx == ("world",) and f == 1) else -1
                    )
                    if f not in top:
                        top[f] = {}
                    top.get(f, {})[k] = new_id
                    stack.append(new_id)
                    if ctx == ("world",) and f == 1:
                        ctx_stack.append(("entity", k))
                        if k not in entity_store:
                            entity_store[k] = {"__type__": doc.models[new_id]["__type__"]}
                        rec["visits"].append((op_pos, k, len(stack), desynced))
                    else:
                        ctx_stack.append(None)
                if len(rec["head_ops"]) < 8:
                    rec["head_ops"].append((op_pos, 7, (f, k)))

            elif op == 8:
                f = r.u8(); f_local = f
                mt = r.u8()
                k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid)
                if ctx == ("world",) and f == 1 and mt in ENTITY_TYPES:
                    ctx_stack.append(("entity", k))
                    entity_store[k] = {"__type__": mt}
                    rec["creates"].append((op_pos, k, mt, desynced))
                else:
                    ctx_stack.append(None)
                if len(rec["head_ops"]) < 8:
                    rec["head_ops"].append((op_pos, 8, (f, mt, k)))

            elif op == 9:
                f = r.u8(); f_local = f
                k = r.i32()
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)

            elif op == 10:
                f = r.u8(); f_local = f
                k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val

            elif op == 11:
                f = r.u8(); f_local = f
                mt = r.u8()
                k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid)
                ctx_stack.append(None)

            elif op == 12:
                f = r.u8(); f_local = f
                k = r.i32()
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)

            elif op == 13:
                r.u8(); r.i32(); r.i32()

            elif op == 14:
                r.u8(); r.i32()

            if len(stack) > rec["max_depth"]:
                rec["max_depth"] = len(stack)

        except Exception as e:
            try:
                top_type = doc.models[stack[-1]]["__type__"]
            except Exception:
                top_type = None
            rec["exc"].append({
                "op_pos": op_pos, "op": op, "field": f_local, "rp": r.p,
                "depth": len(stack), "ctx": repr(ctx_stack[-1]),
                "top_type": top_type,
                "err": type(e).__name__, "msg": str(e)[:80],
            })
            desynced = True
            r.p = op_pos + 1
            while len(stack) > len(ctx_stack):
                ctx_stack.append(None)
            while len(ctx_stack) > len(stack):
                ctx_stack.pop()

    rec["final_depth"] = len(stack)
    return rec


# ---------------------------------------------------------------------------
# Raw byte scanners for candidate re-anchor markers
# ---------------------------------------------------------------------------
def scan_07(data, keys, start=0):
    """07 01 <i32 key in keys> -> list of (pos, key)."""
    hits = []
    n = len(data)
    i = start
    while i + 6 <= n:
        if data[i] == 7 and data[i + 1] == 1:
            k = struct.unpack_from("<i", data, i + 2)[0]
            if k in keys:
                hits.append((i, k))
        i += 1
    return hits


def scan_0107(data, keys, start=0):
    """01 07 01 <i32 key in keys> (pop, then push entity) -> (pos_of_07, key)."""
    hits = []
    n = len(data)
    i = start
    while i + 7 <= n:
        if data[i] == 1 and data[i + 1] == 7 and data[i + 2] == 1:
            k = struct.unpack_from("<i", data, i + 3)[0]
            if k in keys:
                hits.append((i + 1, k))
        i += 1
    return hits


def scan_08(data, start=0):
    """Snapshot-style 08 01 <mt in 9..14> <plausible key> -> (pos, key, mt)."""
    hits = []
    n = len(data)
    i = start
    while i + 7 <= n:
        if data[i] == 8 and data[i + 1] == 1 and data[i + 2] in ENTITY_TYPES:
            k = struct.unpack_from("<i", data, i + 3)[0]
            if 0 < k < 1_000_000:
                hits.append((i, k, data[i + 2]))
        i += 1
    return hits


# ---------------------------------------------------------------------------
# Non-mutating structural dry-parse for marker-coherence checking
# ---------------------------------------------------------------------------
def _guess_width(data, p):
    for w in (1, 2, 4, 8):
        if D._op_ok(data, p + w, 2):
            return p + w
    return p + 4


def dry_parse_after_marker(data, pos, ent_type, max_ops=40):
    """Start AT a 07 01 <key> marker (pos). Consume the push, then structurally parse
    ops with a type stack, no mutation. Returns (ok, ops_parsed, clean_pop, reason).
    clean_pop=True when the entity record's matching Pop returns us to World depth and
    the following byte is a valid op (or end-of-buffer)."""
    n = len(data)
    p = pos + 6                       # consume 07 01 <i32 key>
    tstack = [None, ent_type]         # [world(unknown enough), entity]
    ops = 0
    while p < n and ops < max_ops:
        op = data[p]
        p += 1
        if not (1 <= op <= 14):
            return False, ops, False, "nonop 0x%02x at +%d" % (op, p - 1 - pos)
        ops += 1
        try:
            if op == 1:
                if len(tstack) > 1:
                    tstack.pop()
                if len(tstack) == 1:
                    if p >= n or (1 <= data[p] <= 14):
                        return True, ops, True, "clean pop"
                    return False, ops, False, "pop then nonop 0x%02x" % data[p]
            elif op in (2, 6, 10):
                if p >= n:
                    return False, ops, False, "eof field"
                f = data[p]; p += 1
                if op in (6, 10):
                    p += 4            # i32 key
                tty = tstack[-1]
                fi = D.SCHEMA.get(tty, {}).get(f) if tty is not None else None
                if fi:
                    vt, ism, scal = fi
                    if ism or scal is None:
                        p = _guess_width(data, p)
                    elif scal == "String":
                        if p + 4 > n:
                            return False, ops, False, "eof strlen"
                        ln = struct.unpack_from("<i", data, p)[0]
                        if ln < 0 or ln > 65536:
                            return False, ops, False, "bad strlen %d" % ln
                        p += 4 + ln
                    else:
                        p += D.SCALARS[scal][1]
                else:
                    p = _guess_width(data, p)
            elif op == 3:
                p += 1
                tstack.append(None)
            elif op == 4:
                if p + 2 > n:
                    return False, ops, False, "eof"
                mt = data[p + 1]
                p += 2
                tstack.append(mt)
            elif op == 5:
                p += 1
            elif op == 7:
                p += 5
                tstack.append(None)
            elif op == 8:
                if p + 6 > n:
                    return False, ops, False, "eof"
                mt = data[p + 1]
                p += 6
                tstack.append(mt)
            elif op == 9 or op == 12:
                p += 5
            elif op == 11:
                if p + 6 > n:
                    return False, ops, False, "eof"
                mt = data[p + 1]
                p += 6
                tstack.append(mt)
            elif op == 13:
                p += 9
            elif op == 14:
                p += 5
        except Exception as e:
            return False, ops, False, type(e).__name__
        if p > n:
            return False, ops, False, "ran past eof"
    return True, ops, False, "max ops without failure"


def hexdump(data, center, span=32, mark=None):
    lo = max(0, center - span)
    hi = min(len(data), center + span)
    out = []
    p = lo - (lo % 16)
    while p < hi:
        row = data[p:min(p + 16, len(data))]
        hx = []
        for j, b in enumerate(row):
            tag = ">" if (mark is not None and p + j == mark) else " "
            hx.append("%s%02x" % (tag, b))
        out.append("  %8d: %s" % (p, "".join(hx)))
        p += 16
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("_wf_desync_probe.py  --  delta-patch desync characterization")
    print("ground truth: %s" % GT)
    print("=" * 78)

    doc = es = army = None
    world_id = None
    fight = False
    last_sec = None
    snap_times = []
    army_keys = set()
    seed_keys = set()
    key_type = {}

    records = []          # per fight delta patch
    hp_changed_units = {} # diag-style pre/post per-patch change events
    hp_change_events = 0

    with open(GT, "rb") as f:
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
                    if len(a[2]) == 24 and len(a[3]) == 30 and not fight:
                        fight = True
                        army = a
                        army_keys = a[2] | a[3]
                        seed_keys = set(es.keys())
                        key_type = {k: e.get("__type__") for k, e in es.items()}
                        print("\n[seed] FIGHT snapshot at t=%.2fs  entities=%d  "
                              "army side1=%d side2=%d" % (t, len(es), len(a[2]), len(a[3])))
                    if fight:
                        snap_times.append(round(t, 2))
                    continue
                if not fight or es is None:
                    continue
                if last_sec is not None and t < last_sec - 2:
                    continue
                last_sec = t
                if p:
                    allk = army[2] | army[3]
                    pre = {k: (es.get(k) or {}).get(F_HP) for k in allk}
                    rec = apply_patch_probe(doc, p, es, world_id, army_keys)
                    nchg = 0
                    for k in allk:
                        post = (es.get(k) or {}).get(F_HP)
                        if post != pre[k]:
                            nchg += 1
                            hp_changed_units.setdefault(k, 0)
                            hp_changed_units[k] += 1
                            hp_change_events += 1
                    # raw scans with the SEEDED keyset (a realistic re-anchor would use this)
                    h07 = scan_07(p, seed_keys)
                    h0107 = scan_0107(p, seed_keys)
                    h08 = scan_08(p)
                    for c in (ck for ck in rec["creates"]):
                        key_type.setdefault(c[1], None)
                    records.append({
                        "t": round(t, 3), "p": p, "rec": rec,
                        "hp_changed_units": nchg,
                        "h07": h07, "h0107": h0107, "h08": h08,
                    })

    print("[seed] fight snapshots at game_s: %s" % snap_times)
    print("[run ] fight delta patches: %d   t range %.2f..%.2f s"
          % (len(records), records[0]["t"] if records else -1,
             records[-1]["t"] if records else -1))
    print("[diag-parity] army units with delta HP changes: %d/54   "
          "total delta hp change events: %d"
          % (len(hp_changed_units), hp_change_events))

    # ---- classification ----
    desync = [r for r in records if r["rec"]["exc"]]
    skiponly = [r for r in records if not r["rec"]["exc"] and r["rec"]["skip_before"] > 0]
    clean = [r for r in records if not r["rec"]["exc"] and r["rec"]["skip_before"] == 0]
    print("\n" + "=" * 78)
    print("[1] PER-PATCH DESYNC CENSUS  (fight segment, all post-snapshot delta frames)")
    print("=" * 78)
    print("  total delta patches : %d" % len(records))
    print("  CLEAN  (0 exceptions, 0 skipped bytes)        : %d" % len(clean))
    print("  SKIP-ONLY (0 exceptions, >0 skipped bytes)    : %d" % len(skiponly))
    print("  DESYNCED (>=1 decode exception)               : %d  (%.1f%%)"
          % (len(desync), 100.0 * len(desync) / max(1, len(records))))

    in_fight = [r for r in records if r["t"] <= 20.0]
    in_fight_desync = [r for r in in_fight if r["rec"]["exc"]]
    print("  within fight window t<=20s: %d patches, %d desynced (%.1f%%)"
          % (len(in_fight), len(in_fight_desync),
             100.0 * len(in_fight_desync) / max(1, len(in_fight))))

    if desync:
        fracs = sorted(r["rec"]["exc"][0]["op_pos"] / max(1, r["rec"]["size"])
                       for r in desync)
        import statistics
        print("  first-desync byte-fraction of patch: min=%.3f  p25=%.3f  median=%.3f  "
              "p75=%.3f  max=%.3f"
              % (fracs[0], fracs[len(fracs) // 4], statistics.median(fracs),
                 fracs[3 * len(fracs) // 4], fracs[-1]))
        nexc = sorted(len(r["rec"]["exc"]) for r in desync)
        print("  exceptions per desynced patch: median=%d  max=%d  total=%d"
              % (nexc[len(nexc) // 2], nexc[-1], sum(nexc)))
        szs = sorted(r["rec"]["size"] for r in desync)
        szc = sorted(r["rec"]["size"] for r in clean) or [0]
        print("  desynced patch sizes: median=%d  max=%d   clean patch sizes: median=%d  max=%d"
              % (szs[len(szs) // 2], szs[-1], szc[len(szc) // 2], szc[-1]))

    # exception detail histograms
    err_kinds = Counter()
    fail_ops = Counter()
    fail_depth = Counter()
    fail_toptype = Counter()
    fail_ctx = Counter()
    for r in desync:
        for e in r["rec"]["exc"]:
            err_kinds["%s:%s" % (e["err"], e["msg"][:40])] += 1
            fail_ops[e["op"]] += 1
            fail_depth[e["depth"]] += 1
            fail_toptype[e["top_type"]] += 1
            fail_ctx[e["ctx"]] += 1
    print("\n  exception kinds (top 8):")
    for k, c in err_kinds.most_common(8):
        print("    %6d  %s" % (c, k))
    print("  op byte at failure   : %s" % dict(fail_ops.most_common(10)))
    print("  stack depth at failure: %s" % dict(sorted(fail_depth.items())))
    print("  top model __type__ at failure: %s" % dict(fail_toptype.most_common(10)))
    print("  ctx at failure: %s" % dict(fail_ctx.most_common(6)))

    # silently-executed garbage after first failure
    print("\n  post-desync garbage execution (ops the dispatcher ran AFTER 1st exception):")
    tot_ops_after = sum(r["rec"]["ops_after"] for r in desync)
    tot_skip_after = sum(r["rec"]["skip_after"] for r in desync)
    tot_ops_before = sum(r["rec"]["ops_before"] for r in desync)
    tot_skip_before = sum(r["rec"]["skip_before"] for r in desync)
    print("    desynced patches: ops before 1st exc=%d (skipped bytes=%d), "
          "ops AFTER=%d (skipped bytes=%d)"
          % (tot_ops_before, tot_skip_before, tot_ops_after, tot_skip_after))
    ophb = Counter(); opha = Counter()
    for r in desync:
        ophb.update(r["rec"]["op_hist_before"])
        opha.update(r["rec"]["op_hist_after"])
    ophc = Counter()
    for r in clean:
        ophc.update(r["rec"]["op_hist_before"])
    def fmt_hist(h):
        tot = sum(h.values()) or 1
        return "  ".join("op%d:%.1f%%" % (o, 100.0 * h[o] / tot) for o in sorted(h))
    print("    op mix CLEAN patches     : %s" % fmt_hist(ophc))
    print("    op mix desynced pre-exc  : %s" % fmt_hist(ophb))
    print("    op mix desynced post-exc : %s" % fmt_hist(opha))
    fhc = Counter(); fha = Counter()
    for r in clean:
        fhc.update(r["rec"]["f_hist_before"])
    for r in desync:
        fha.update(r["rec"]["f_hist_after"])
    big_f_clean = sum(c for f, c in fhc.items() if f > 60)
    big_f_post = sum(c for f, c in fha.items() if f > 60)
    print("    field ids > 60: clean=%d/%d (%.2f%%)   post-desync=%d/%d (%.2f%%)"
          % (big_f_clean, sum(fhc.values()), 100.0 * big_f_clean / max(1, sum(fhc.values())),
             big_f_post, sum(fha.values()), 100.0 * big_f_post / max(1, sum(fha.values()))))

    # ---- HP-update loss quantification ----
    print("\n" + "=" * 78)
    print("[2] ARMY HP-UPDATE LOSS PER DESYNCED PATCH")
    print("=" * 78)
    hdr = ("      t   size  1stexc@  nexc  hpW_pre  hpW_post  visits  vis_post  "
           "raw07(army)  raw07(all)")
    print(hdr)
    tot_lost_est_extrap = 0.0
    tot_raw_minus_dec = 0
    rows_shown = 0
    for r in records:
        rc = r["rec"]
        if not rc["exc"]:
            continue
        first = rc["exc"][0]["op_pos"]
        hw_pre = sum(1 for w in rc["hp_writes"] if not w[3])
        hw_post = sum(1 for w in rc["hp_writes"] if w[3])
        vis = len(rc["visits"])
        vis_post = sum(1 for v in rc["visits"] if v[3])
        raw07_army = sum(1 for (pos, k) in r["h07"] if k in army_keys)
        raw07_all = len(r["h07"])
        frac = first / max(1, rc["size"])
        if frac > 0:
            est_total = hw_pre / max(frac, 1e-9)
            tot_lost_est_extrap += max(0.0, est_total - hw_pre - hw_post)
        dec_army_vis = sum(1 for v in rc["visits"] if v[1] in army_keys)
        tot_raw_minus_dec += max(0, raw07_army - dec_army_vis)
        if rows_shown < 25 and r["t"] <= 30:
            print("  %6.2f %6d  %6.3f  %4d  %7d  %8d  %6d  %8d  %11d  %10d"
                  % (r["t"], rc["size"], frac, len(rc["exc"]),
                     hw_pre, hw_post, vis, vis_post, raw07_army, raw07_all))
            rows_shown += 1
    print("  (table: first 25 desynced patches with t<=30s)")
    # totals across ALL patches
    tot_hp_writes = sum(len(r["rec"]["hp_writes"]) for r in records)
    tot_hp_pre = sum(sum(1 for w in r["rec"]["hp_writes"] if not w[3]) for r in records)
    tot_raw07_army = sum(sum(1 for (pos, k) in r["h07"] if k in army_keys) for r in records)
    tot_dec_army_vis = sum(sum(1 for v in r["rec"]["visits"] if v[1] in army_keys)
                           for r in records)
    print("\n  TOTALS (all fight deltas):")
    print("    decoded army HP mirror writes: %d (pre-desync %d, post-desync %d)"
          % (tot_hp_writes, tot_hp_pre, tot_hp_writes - tot_hp_pre))
    print("    raw 07-01-<armykey> scan occurrences : %d" % tot_raw07_army)
    print("    decoded army entity visits (op7 ctx) : %d" % tot_dec_army_vis)
    print("    visits lost (raw - decoded)          : %d" % (tot_raw07_army - tot_dec_army_vis))
    print("    clean-prefix extrapolation of lost HP writes: %.0f" % tot_lost_est_extrap)
    if desync:
        nd = len(desync)
        print("    => per desynced patch: raw-vs-decoded army-visit loss = %.2f, "
              "extrapolated HP-write loss = %.2f"
              % (tot_raw_minus_dec / nd, tot_lost_est_extrap / nd))

    # ---- marker analysis on CLEAN patches (labeled ground truth) ----
    print("\n" + "=" * 78)
    print("[3] RE-ANCHOR MARKER EVALUATION")
    print("=" * 78)
    print("  Truth = op positions where the decoder actually entered World.entities[k]")
    print("  (a) measured on CLEAN patches (decoder positions are trustworthy labels):")

    def eval_marker(patches, scan_key, truth_from):
        tp = fp = 0
        truth_total = 0
        fp_coherent = 0
        tp_coherent = 0
        for r in patches:
            rc = r["rec"]
            truth = set(v[0] for v in rc["visits"])
            truth_total += len(truth)
            for hit in r[scan_key]:
                pos, k = hit[0], hit[1]
                ok, ops, cleanpop, reason = dry_parse_after_marker(
                    r["p"], pos, key_type.get(k))
                if pos in truth:
                    tp += 1
                    if ok:
                        tp_coherent += 1
                else:
                    fp += 1
                    if ok:
                        fp_coherent += 1
        return tp, fp, truth_total, tp_coherent, fp_coherent

    for name, key in (("07 01 <key in seeded store>", "h07"),
                      ("01 07 01 <key in seeded store>", "h0107")):
        tp, fp, truth_total, tpc, fpc = eval_marker(clean, key, "visits")
        prec = 100.0 * tp / max(1, tp + fp)
        rec_ = 100.0 * tp / max(1, truth_total)
        prec_c = 100.0 * tpc / max(1, tpc + fpc)
        print("    %-32s hits=%5d  TP=%5d  FP=%5d  precision=%6.2f%%  "
              "recall=%6.2f%%  | after dry-parse filter: TP=%d FP=%d prec=%.2f%%"
              % (name, tp + fp, tp, fp, prec, rec_, prec_c, fpc, prec_c))

    # 08 marker in deltas: truth = op8 creates
    tp = fp = 0
    truth_total = 0
    for r in clean:
        truth = set(c[0] for c in r["rec"]["creates"])
        truth_total += len(truth)
        for (pos, k, mt) in r["h08"]:
            if pos in truth:
                tp += 1
            else:
                fp += 1
    print("    %-32s hits=%5d  TP=%5d  FP=%5d  precision=%6.2f%%  "
          "(truth=op8 entity creates, n=%d)"
          % ("08 01 <mt 9-14> <plausible key>", tp + fp, tp, fp,
             100.0 * tp / max(1, tp + fp), truth_total))

    # entity-visit depth and patch head structure (what stack must re-anchor TO)
    dvis = Counter()
    for r in clean:
        for v in r["rec"]["visits"]:
            dvis[v[2]] += 1
    print("\n    stack depth AFTER entity push (clean patches): %s" % dict(sorted(dvis.items())))
    heads = Counter()
    for r in records[:400]:
        h = tuple((o, fk if not isinstance(fk, tuple) else fk[0])
                  for (pp, o, fk) in r["rec"]["head_ops"][:3])
        heads[h] += 1
    print("    patch head op-structure (first 3 ops, first 400 patches): %s"
          % dict(heads.most_common(5)))

    # (b) desynced patches: how many marker hits exist after the first failure,
    #     and do they pass the coherence dry-parse?
    print("\n  (b) on DESYNCED patches, after the first exception position:")
    tot_after = tot_after_coh = 0
    tot_after_army = tot_after_army_coh = 0
    for r in desync:
        first = r["rec"]["exc"][0]["op_pos"]
        for (pos, k) in r["h07"]:
            if pos <= first:
                continue
            tot_after += 1
            ok, ops, cleanpop, reason = dry_parse_after_marker(r["p"], pos, key_type.get(k))
            if ok:
                tot_after_coh += 1
            if k in army_keys:
                tot_after_army += 1
                if ok:
                    tot_after_army_coh += 1
    print("    07-marker hits after 1st exc: %d (army keys: %d)" % (tot_after, tot_after_army))
    print("    passing dry-parse coherence : %d (army keys: %d)"
          % (tot_after_coh, tot_after_army_coh))

    # ---- hexdumps around failures ----
    print("\n" + "=" * 78)
    print("[4] HEXDUMPS AROUND FIRST FAILURES (sample of desynced patches)")
    print("=" * 78)
    shown = 0
    for r in desync:
        if shown >= 4:
            break
        rc = r["rec"]
        e = rc["exc"][0]
        print("\n  patch t=%.2fs size=%d  first exc: op=%s field=%s pos=%d rp=%d depth=%d "
              "ctx=%s top_type=%s err=%s:%s"
              % (r["t"], rc["size"], e["op"], e["field"], e["op_pos"], e["rp"],
                 e["depth"], e["ctx"], e["top_type"], e["err"], e["msg"][:50]))
        print(hexdump(r["p"], e["op_pos"], 40, mark=e["op_pos"]))
        nxt = [(pos, k) for (pos, k) in r["h07"] if pos > e["op_pos"]]
        if nxt:
            pos, k = nxt[0]
            ok, ops, cleanpop, reason = dry_parse_after_marker(r["p"], pos, key_type.get(k))
            print("  next 07-marker after failure: pos=%d key=%d (army=%s) "
                  "dry-parse ok=%s ops=%d cleanpop=%s (%s)"
                  % (pos, k, k in army_keys, ok, ops, cleanpop, reason))
            print(hexdump(r["p"], pos, 24, mark=pos))
        shown += 1

    # ---- HP write timeline (delta HP events per game second, parity with diag) ----
    print("\n" + "=" * 78)
    print("[5] DELTA HP-WRITE TIMELINE (army mirror writes per game second)")
    print("=" * 78)
    hist = Counter()
    for r in records:
        for w in r["rec"]["hp_writes"]:
            hist[int(r["t"])] += 1
    print("  " + str(dict(sorted(hist.items()))))

    print("\ndone.")


if __name__ == "__main__":
    main()
