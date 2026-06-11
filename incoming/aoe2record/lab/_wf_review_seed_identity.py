"""_wf_review_seed_identity.py - prove seed_from_snapshot is behaviorally unchanged.

Loads BOTH decoder modules (current decode_state_v2.py and the pre-fix backup)
and runs seed_from_snapshot from each on:
  1. the ground-truth .seed_snap.bin
  2. every >400KB snapshot patch inside the ground-truth .frames.bin
  3. the first 3 and last 3 >400KB snapshot patches inside run1.frames.bin
Compares (entity_store deep-equal, world_id, doc.models deep-equal, return count).
ASCII output only.
"""
import importlib.util
import io
import contextlib
import os
import struct
import sys

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
import decode_state_v2 as NEW  # noqa: E402
import cade_api_pb2 as pb      # noqa: E402

spec = importlib.util.spec_from_file_location(
    "decode_state_v2_old", os.path.join(D_DIR, "decode_state_v2.pre_fix.bak.py"))
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      "\\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
RUN1 = os.path.join(D_DIR, "run1")
TMP = os.path.join(D_DIR, "_wf_review_seed_tmp.bin")


def snapshots_of(pfx, limit_head=None, limit_tail=None):
    out = []
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
                if fr.patch and len(fr.patch) > 400_000:
                    out.append(bytes(fr.patch))
    if limit_head is not None and len(out) > limit_head + limit_tail:
        out = out[:limit_head] + out[-limit_tail:]
    return out


def seed_with(mod, snap_bytes):
    with open(TMP, "wb") as f:
        f.write(snap_bytes)
    doc, es = mod.Doc(), {}
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        cnt, wid = mod.seed_from_snapshot(TMP, doc, es)
    return cnt, wid, es, doc.models


def compare(tag, snap_bytes):
    c_new = seed_with(NEW, snap_bytes)
    c_old = seed_with(OLD, snap_bytes)
    same = (c_new[0] == c_old[0] and c_new[1] == c_old[1]
            and c_new[2] == c_old[2] and c_new[3] == c_old[3])
    print(f"{tag}: bytes={len(snap_bytes):,} count_new={c_new[0]} count_old={c_old[0]} "
          f"world_id new={c_new[1]} old={c_old[1]} entities new={len(c_new[2])} "
          f"old={len(c_old[2])} IDENTICAL={same}")
    if not same:
        ks_new, ks_old = set(c_new[2]), set(c_old[2])
        print("  key diff new-old:", sorted(ks_new - ks_old)[:10])
        print("  key diff old-new:", sorted(ks_old - ks_new)[:10])
        for k in sorted(ks_new & ks_old):
            if c_new[2][k] != c_old[2][k]:
                print(f"  first differing entity {k}: new={c_new[2][k]} old={c_old[2][k]}")
                break
        if c_new[3] != c_old[3]:
            print("  doc.models differ")
    return same


def main():
    all_ok = True
    seed_snap = GT + ".seed_snap.bin"
    if os.path.exists(seed_snap):
        all_ok &= compare("GT .seed_snap.bin", open(seed_snap, "rb").read())
    gt_snaps = snapshots_of(GT)
    for i, s in enumerate(gt_snaps):
        all_ok &= compare(f"GT inline snapshot #{i}", s)
    r1 = snapshots_of(RUN1, limit_head=3, limit_tail=3)
    for i, s in enumerate(r1):
        all_ok &= compare(f"run1 snapshot sample #{i}", s)
    print("RESULT:", "ALL IDENTICAL" if all_ok else "MISMATCH FOUND")


if __name__ == "__main__":
    main()
