"""_wf_desync_probe5.py — validate the STRUCTURAL re-anchor trigger:
   "op7/op9/op12 executed with f==1 and key in World.entities, while ctx != World"
   = stack-misalignment smoking gun.

Measures on the ground-truth dump:
  A. false-positive rate of the trigger on healthy patches (no exception, no skip,
     no lost army HP content),
  B. coverage: for every patch where raw army HP records were lost by the decoder,
     does the trigger fire at/before the first lost record,
  C. the unit-781 case: trigger position vs its op9 / hp<=0 record.

Uses apply_patch_trace (faithful semantics copy) and post-processes the op trace.
ASCII-only output. Run with cwd C:\\dev\\aoe2grpc.
"""
import struct
import sys

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D                              # noqa: E402
import cade_api_pb2 as pb                                # noqa: E402
from _wf_desync_probe import scan_07, derive_army        # noqa: E402
from _wf_desync_probe2 import extract_record             # noqa: E402
from _wf_desync_probe4 import apply_patch_trace          # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs).frames.bin")
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_seed_tmp5.bin"
F_HP = 12


def main():
    print("=" * 78)
    print("_wf_desync_probe5.py -- structural re-anchor trigger validation")
    print("=" * 78)

    doc = es = army = None
    world_id = None
    fight = False
    last_sec = None
    army_keys = set()
    key_type = {}
    n_patch = 0

    healthy_with_signal = 0          # A numerator (patch level)
    healthy_signal_events = 0
    healthy_patches = 0
    lost_rows = []                   # B
    sig_total_by_class = {"clean": 0, "skip": 0, "exc": 0}
    patches_by_class = {"clean": 0, "skip": 0, "exc": 0}
    covered = 0
    not_covered = 0

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

                world_keys = set(doc.models[world_id].get(1, {}).keys())

                # raw truth: army entity records carrying an HP assign, with positions
                raw_hp_pos = []
                for (pos, k) in scan_07(p, army_keys):
                    ok, endp, flds, ops, rsn = extract_record(p, pos, key_type.get(k))
                    if F_HP in flds:
                        raw_hp_pos.append((pos, k, flds[F_HP]))

                trace = apply_patch_trace(doc, p, es, world_id)

                n_exc = sum(1 for x in trace if x[1] == "EXC")
                n_skip = sum(1 for x in trace if x[1] == "SKIP")
                cls = "exc" if n_exc else ("skip" if n_skip else "clean")
                patches_by_class[cls] += 1

                # decoded army HP mirror writes (op2 f=12 inside army entity ctx)
                dec_hp_pos = [x[0] for x in trace
                              if x[1] == 2 and x[2] == F_HP
                              and isinstance(x[5], tuple) and x[5][0] == "entity"
                              and x[5][1] in army_keys]

                # structural trigger events
                signals = []
                for (pos, op, fld, k, depth, ctx) in trace:
                    if op == 7 and fld == 1 and k in world_keys:
                        # ctx recorded post-push: ('entity', k) when world-aligned
                        if not (isinstance(ctx, tuple) and ctx[0] == "entity"):
                            signals.append((pos, 7, k))
                    elif op in (9, 12) and fld == 1 and k in world_keys:
                        if ctx != ("world",):
                            signals.append((pos, op, k))
                sig_total_by_class[cls] += len(signals)

                lost = len(raw_hp_pos) - len(dec_hp_pos)
                if cls == "clean" and lost <= 0:
                    healthy_patches += 1
                    if signals:
                        healthy_with_signal += 1
                        healthy_signal_events += len(signals)
                        if healthy_with_signal <= 5:
                            print("  [A-fp] healthy patch t=%.2f size=%d signals=%s"
                                  % (t, len(p), signals[:6]))

                if lost > 0:
                    dec_set = set(dec_hp_pos)
                    lost_positions = []
                    for (pos, k, hp) in raw_hp_pos:
                        # decoded mirror write for this record would sit in (pos, pos+40)
                        if not any(pos < dp < pos + 60 for dp in dec_hp_pos):
                            lost_positions.append((pos, k, hp))
                    first_lost = lost_positions[0][0] if lost_positions else None
                    first_sig = signals[0][0] if signals else None
                    ok_cov = (first_sig is not None and first_lost is not None
                              and first_sig <= first_lost)
                    if ok_cov:
                        covered += 1
                    else:
                        not_covered += 1
                    lost_rows.append((t, cls, len(p), lost, lost_positions[:4],
                                      first_sig, len(signals), ok_cov))

    print("\n[A] TRIGGER FALSE-POSITIVE RATE (healthy patches: clean decode, no lost HP):")
    print("    healthy patches=%d  with >=1 trigger event: %d  total events: %d"
          % (healthy_patches, healthy_with_signal, healthy_signal_events))
    print("    patches by class: %s   trigger events by class: %s"
          % (patches_by_class, sig_total_by_class))

    print("\n[B] COVERAGE OF LOST-HP PATCHES (does trigger fire at/before first lost record):")
    print("        t  class   size  lost  first_sig  n_sig  covered  lost records (pos,key,hp)")
    for (t, cls, sz, lost, lp, fs, ns, okc) in lost_rows:
        print("   %6.2f  %-5s  %5d  %4d  %9s  %5d  %7s  %s"
              % (t, cls, sz, lost, fs if fs is not None else "-", ns,
                 "YES" if okc else "NO", lp))
    print("    covered=%d  not_covered=%d" % (covered, not_covered))

    print("\ndone.")


if __name__ == "__main__":
    main()
