"""_wf_desync_probe4.py — targeted diagnosis of the decoder misses that survive the
time-base fix, plus re-anchor feasibility metrics.

  1. Unit 781: its op9 removal AND its hp<=0 write were both missed by the broken
     decoder (the only side1 unit with NO decoded death  ->  redecode end-detection
     never fires). Find the patches, verbose-trace ops around the markers, explain.
  2. Unit 779: raw hp<=0 at t=12.69 sits in a patch NOT flagged desynced -> silent
     misalignment. Trace it.
  3. Re-anchor feasibility: per desynced patch, byte distance first_exc -> next valid
     marker; does every desynced patch have one; what content sits in the skipped gap.
  4. Skip-only patches (silent byte skips, no exception): how much army content do
     they carry / lose; do skipped bytes precede the missed content?
  5. op9-vs-hp<=0 delay stats (corpse-removal lag) for death-channel choice.

ASCII-only output. Run with cwd C:\\dev\\aoe2grpc.
"""
import struct
import sys
from collections import Counter

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D                              # noqa: E402
import cade_api_pb2 as pb                                # noqa: E402
from _wf_desync_probe import (apply_patch_probe, scan_07, derive_army,  # noqa: E402
                              hexdump)
from _wf_desync_probe2 import extract_record, scan_deaths               # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs).frames.bin")
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_seed_tmp4.bin"
F_HP = 12
TARGETS = {781, 779}


# ---------------------------------------------------------------------------
# Verbose-trace copy of apply_patch: records every executed op (pos, op, f, k,
# depth, ctx-kind) WITHOUT changing semantics. Used only on targeted patches.
# ---------------------------------------------------------------------------
def apply_patch_trace(doc, data, entity_store, world_id):
    r = D.Reader(data)
    stack = [doc.root]
    ctx_stack = [None]
    trace = []

    def finfo_for(top_id, f):
        tty = doc.models[top_id]["__type__"]
        fi = D.SCHEMA.get(tty, {}).get(f)
        if fi:
            return fi
        return ("value", False, None)

    while r.p < len(data):
        op_pos = r.p
        try:
            op = r.u8()
            if not (1 <= op <= 14):
                trace.append((op_pos, "SKIP", op, None, len(stack), ctx_stack[-1]))
                continue
            top_id = stack[-1]
            top = doc.models[top_id]
            ctx = ctx_stack[-1]
            if op == 1:
                trace.append((op_pos, 1, None, None, len(stack), ctx))
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
                trace.append((op_pos, 2, f, val if isinstance(val, (int, float)) else None,
                              len(stack), ctx))
            elif op == 3:
                f = r.u8()
                cid = top.get(f)
                if isinstance(cid, int) and cid in doc.models:
                    stack.append(cid)
                    ctx_stack.append(("world",) if cid == world_id else None)
                else:
                    new_id = doc.register(-1)
                    top[f] = new_id
                    stack.append(new_id)
                    ctx_stack.append(None)
                trace.append((op_pos, 3, f, None, len(stack), ctx_stack[-1]))
            elif op == 4:
                f = r.u8(); mt = r.u8()
                cid = doc.register(mt)
                top[f] = cid
                stack.append(cid)
                nlw = None
                if doc.models[top_id]["__type__"] == 0 and f == 0 and mt == 1:
                    nlw = cid
                ctx_stack.append(("world",) if nlw else None)
                trace.append((op_pos, 4, f, mt, len(stack), ctx_stack[-1]))
            elif op == 5:
                f = r.u8()
                top.pop(f, None)
                trace.append((op_pos, 5, f, None, len(stack), ctx))
            elif op == 6:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
                trace.append((op_pos, 6, f, k, len(stack), ctx))
            elif op == 7:
                f = r.u8(); k = r.i32()
                cid = top.get(f, {}).get(k) if isinstance(top.get(f, {}), dict) else None
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
                trace.append((op_pos, 7, f, k, len(stack), ctx_stack[-1]))
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
                trace.append((op_pos, 8, f, k, len(stack), ctx_stack[-1]))
            elif op == 9:
                f = r.u8(); k = r.i32()
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
                trace.append((op_pos, 9, f, k, len(stack), ctx))
            elif op == 10:
                f = r.u8(); k = r.i32()
                vt, ism, scal = finfo_for(top_id, f)
                val = D.read_value(r, vt, ism, scal)
                top.setdefault(f, {})[k] = val
                trace.append((op_pos, 10, f, k, len(stack), ctx))
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32()
                cid = doc.register(mt)
                top.setdefault(f, {})[k] = cid
                stack.append(cid)
                ctx_stack.append(None)
                trace.append((op_pos, 11, f, k, len(stack), None))
            elif op == 12:
                f = r.u8(); k = r.i32()
                m = top.get(f)
                if isinstance(m, dict):
                    m.pop(k, None)
                if ctx == ("world",) and f == 1:
                    entity_store.pop(k, None)
                trace.append((op_pos, 12, f, k, len(stack), ctx))
            elif op == 13:
                r.u8(); r.i32(); r.i32()
                trace.append((op_pos, 13, None, None, len(stack), ctx))
            elif op == 14:
                r.u8(); r.i32()
                trace.append((op_pos, 14, None, None, len(stack), ctx))
        except Exception as e:
            trace.append((op_pos, "EXC", type(e).__name__, str(e)[:40],
                          len(stack), ctx_stack[-1]))
            r.p = op_pos + 1
            while len(stack) > len(ctx_stack):
                ctx_stack.append(None)
            while len(ctx_stack) > len(stack):
                ctx_stack.pop()
    return trace


def fmt_trace_window(trace, lo, hi):
    out = []
    for tr in trace:
        if lo <= tr[0] <= hi:
            pos, op, f, k, depth, ctx = tr
            cs = ("W" if ctx == ("world",) else
                  ("E%s" % ctx[1] if isinstance(ctx, tuple) and ctx[0] == "entity"
                   else "-"))
            out.append("    pos=%6d  op=%-4s f=%-4s k/v=%-12s depth=%d ctx=%s"
                       % (pos, op, f, k, depth, cs))
    return "\n".join(out) if out else "    (no executed ops in window)"


def main():
    print("=" * 78)
    print("_wf_desync_probe4.py -- targeted miss diagnosis + re-anchor feasibility")
    print("=" * 78)

    doc = es = army = None
    world_id = None
    fight = False
    last_sec = None
    army_keys = set()
    known_keys = set()
    key_type = {}
    raw_hp0 = {}
    dec_removed = {}
    n_patch = 0
    gap_stats = []           # (t, size, first_exc, next_marker_pos, gap, n_raw_hp_in_gap)
    skiponly_info = []       # (t, size, skip_bytes, raw_hp, dec_hp, raw_deaths, run_positions)
    traced = []

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
                        known_keys = set(es.keys())
                        key_type = {k: e.get("__type__") for k, e in es.items()}
                    continue
                if not fight or es is None:
                    continue
                if last_sec is not None and t < last_sec - 2:
                    continue
                last_sec = t
                if not p:
                    continue
                n_patch += 1

                # does this patch contain a TARGET event? (op9 of 781, or an
                # hp<=0-carrying record of a target key)
                want_trace = False
                tgt_positions = []
                for (pos, op, k) in scan_deaths(p, TARGETS):
                    want_trace = True
                    tgt_positions.append(("op%d k=%d" % (op, k), pos))
                for (pos, k) in scan_07(p, TARGETS):
                    ok, endp, flds, ops, rsn = extract_record(p, pos, key_type.get(k))
                    if F_HP in flds and flds[F_HP] <= 0 and k not in raw_hp0:
                        want_trace = True
                        tgt_positions.append(("hp0rec k=%d hp=%.1f" % (k, flds[F_HP]),
                                              pos))

                pre_in = {k: (k in es) for k in TARGETS}
                if want_trace:
                    trace = apply_patch_trace(doc, p, es, world_id)
                    nexc = sum(1 for x in trace if x[1] == "EXC")
                    nskip = sum(1 for x in trace if x[1] == "SKIP")
                    first_exc = next((x[0] for x in trace if x[1] == "EXC"), None)
                    first_skip = next((x[0] for x in trace if x[1] == "SKIP"), None)
                    print("\n[TRACE] patch t=%.2fs size=%d exc=%d (first@%s) "
                          "skips=%d (first@%s) targets=%s"
                          % (t, len(p), nexc, first_exc, nskip, first_skip,
                             tgt_positions))
                    for label, pos in tgt_positions:
                        print("  -- around %s at pos %d:" % (label, pos))
                        print(fmt_trace_window(trace, pos - 60, pos + 40))
                        print(hexdump(p, pos, 32, mark=pos))
                    traced.append(t)
                    rec = None
                else:
                    rec = apply_patch_probe(doc, p, es, world_id, army_keys)

                # track raw hp0 / dec removal for the delay stats
                for (pos, k) in scan_07(p, army_keys):
                    if k in raw_hp0:
                        continue
                    ok, endp, flds, ops, rsn = extract_record(p, pos, key_type.get(k))
                    if F_HP in flds and flds[F_HP] <= 0:
                        raw_hp0[k] = t
                for k in TARGETS:
                    if pre_in[k] and k not in es and k not in dec_removed:
                        dec_removed[k] = t
                for k in army_keys:
                    if k in dec_removed or k in TARGETS:
                        continue
                    # cheap: only fill on the patch where an op9 marker exists
                for (pos, op, k) in scan_deaths(p, army_keys):
                    if k not in es and k not in dec_removed:
                        dec_removed[k] = t

                if rec is None:
                    continue
                # creates -> growing keyset
                for (pos, k, mt, after) in rec["creates"]:
                    if not after:
                        known_keys.add(k)
                        key_type.setdefault(k, mt)

                # re-anchor feasibility on desynced patches
                if rec["exc"]:
                    fe = rec["exc"][0]["op_pos"]
                    h = [pos for (pos, k) in scan_07(p, known_keys) if pos > fe]
                    hd = [pos for (pos, op, k) in scan_deaths(p, army_keys) if pos > fe]
                    nxt = min(h + hd) if (h or hd) else None
                    n_hp_gap = 0
                    if nxt is not None:
                        for (pos, k) in scan_07(p, army_keys):
                            if fe < pos < nxt:
                                ok, endp, flds, ops, rsn = extract_record(
                                    p, pos, key_type.get(k))
                                if F_HP in flds:
                                    n_hp_gap += 1
                    gap_stats.append((t, len(p), fe, nxt,
                                      (nxt - fe) if nxt is not None else None,
                                      n_hp_gap))
                elif rec["skip_before"] > 0:
                    raw_hp = 0
                    for (pos, k) in scan_07(p, army_keys):
                        ok, endp, flds, ops, rsn = extract_record(p, pos,
                                                                  key_type.get(k))
                        if F_HP in flds:
                            raw_hp += 1
                    dec_hp = len(rec["hp_writes"])
                    rdeaths = len(scan_deaths(p, army_keys))
                    runs = rec["skip_runs"][:4]
                    skiponly_info.append((t, len(p), rec["skip_before"], raw_hp,
                                          dec_hp, rdeaths, runs))

    print("\n[3] RE-ANCHOR FEASIBILITY (desynced patches): first_exc -> next marker")
    print("        t   size  first_exc  next_marker   gap_bytes  army_hp_in_gap")
    no_marker = 0
    for (t, sz, fe, nxt, gap, nhp) in gap_stats:
        print("   %6.2f  %5d  %9d  %11s  %10s  %14d"
              % (t, sz, fe, nxt if nxt is not None else "NONE",
                 gap if gap is not None else "-", nhp))
        if nxt is None:
            no_marker += 1
    gaps = [g for (_, _, _, _, g, _) in gap_stats if g is not None]
    if gaps:
        gaps.sort()
        print("  patches with NO marker after exc: %d/%d   gap bytes: min=%d "
              "median=%d max=%d" % (no_marker, len(gap_stats), gaps[0],
                                    gaps[len(gaps) // 2], gaps[-1]))

    print("\n[4] SKIP-ONLY PATCHES (silent desync, no exception):")
    print("        t   size  skipped  raw_hp  dec_hp  death_marks  first_runs")
    lost_in_skip = 0
    for (t, sz, sk, rhp, dhp, rd, runs) in skiponly_info:
        lost_in_skip += max(0, rhp - dhp)
        print("   %6.2f  %5d  %7d  %6d  %6d  %11d  %s"
              % (t, sz, sk, rhp, dhp, rd, runs))
    print("  army HP writes lost in skip-only patches: %d" % lost_in_skip)

    print("\n[5] op9 (corpse removal) vs raw hp<=0 delay:")
    # dec_removed here was filled from op9-marker patches
    deltas = []
    for k, t0 in raw_hp0.items():
        t9 = dec_removed.get(k)
        if t9 is not None and t9 >= t0:
            deltas.append(t9 - t0)
    if deltas:
        deltas.sort()
        print("  n=%d  min=%.2f  median=%.2f  max=%.2f  (fr.time seconds)"
              % (len(deltas), deltas[0], deltas[len(deltas) // 2], deltas[-1]))
    print("\ntraced patches at t=%s" % traced)
    print("done.")


if __name__ == "__main__":
    main()
