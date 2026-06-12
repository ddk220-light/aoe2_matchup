"""_wf_review_fuzz.py - termination + exception-safety of the fixed apply_patch.

Cases:
  P1  400KB of crafted adversarial blocks: a VALID op7 marker immediately
      followed by an op that forces reanchor (worst case: re-anchor density).
  P2  400KB pseudo-random bytes (seed 42).
  P3  400KB of 0x00 (invalid op everywhere, no marker anywhere).
  P4  a real delta patch from the ground-truth dump truncated at 300 positions.
  P5  the same real patch with 300 random single-byte corruptions.
  P6  empty patch; 1-6 byte stubs; world_id=None with garbage.
Asserts: returns without exception; wall time bounded; reports doc.models
growth (placeholder churn). Also checks ENTITY_TYPES are decodable per SCHEMA.
ASCII only.
"""
import contextlib
import io
import os
import random
import struct
import sys
import time

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
import decode_state_v2 as D  # noqa: E402
import cade_api_pb2 as pb    # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      "\\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
TMP = os.path.join(D_DIR, "_wf_review_fuzz.reseed.bin")


def fresh_state():
    """Seed doc/es from the GT snapshot (realistic known_keys)."""
    for t, p in frames():
        if p is not None and len(p) > 400_000:
            with open(TMP, "wb") as f:
                f.write(p)
            doc, es = D.Doc(), {}
            with contextlib.redirect_stdout(io.StringIO()):
                _, wid = D.seed_from_snapshot(TMP, doc, es)
            return doc, es, wid
    raise RuntimeError("no snapshot")


def frames():
    with open(GT + ".frames.bin", "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                return
            ln = struct.unpack("<I", hdr)[0]
            buf = f.read(ln)
            if len(buf) < ln:
                return
            sq = pb.FrameSequence()
            sq.ParseFromString(buf)
            for fr in sq.frame:
                yield fr.time / 1000.0, (fr.patch if fr.patch else None)


def first_real_delta(min_len=2000):
    for t, p in frames():
        if p is not None and len(p) <= 400_000 and len(p) >= min_len:
            return bytes(p)
    raise RuntimeError("no delta")


def timed(tag, doc, es, wid, payload, budget_s):
    t0 = time.perf_counter()
    rs = D.apply_patch(doc, payload, es, wid)
    dt = time.perf_counter() - t0
    ok = dt <= budget_s
    print(f"{tag}: len={len(payload):,} resyncs={rs} time={dt:.3f}s "
          f"models={len(doc.models):,} {'OK' if ok else 'TOO SLOW'}")
    return ok


def main():
    print("ENTITY_TYPES in SCHEMA:",
          {mt: (mt in D.SCHEMA) for mt in sorted(D.ENTITY_TYPES)})
    all_ok = True

    doc, es, wid = fresh_state()
    key = sorted(es.keys())[len(es) // 2]
    kb = struct.pack("<i", key)

    # P1: valid op7 marker then forced reanchor (op3 on unknown field 99)
    block = b"\x07\x01" + kb + b"\x03\x63"
    p1 = block * (400_000 // len(block))
    all_ok &= timed("P1 marker+desync blocks", doc, es, wid, p1, 30)

    doc, es, wid = fresh_state()
    rnd = random.Random(42)
    p2 = bytes(rnd.randrange(256) for _ in range(400_000))
    all_ok &= timed("P2 random 400KB", doc, es, wid, p2, 30)

    doc, es, wid = fresh_state()
    all_ok &= timed("P3 zeros 400KB", doc, es, wid, b"\x00" * 400_000, 30)

    real = first_real_delta()
    print(f"P4/P5 base real delta: {len(real):,} bytes")
    doc, es, wid = fresh_state()
    rnd = random.Random(7)
    t0 = time.perf_counter()
    n_exc = 0
    for _ in range(300):
        cut = rnd.randrange(1, len(real))
        try:
            D.apply_patch(doc, real[:cut], es, wid)
        except Exception as e:
            n_exc += 1
            print("  P4 EXCEPTION:", type(e).__name__, e)
    print(f"P4 truncations x300: exceptions={n_exc} time={time.perf_counter()-t0:.2f}s "
          f"models={len(doc.models):,}")
    all_ok &= (n_exc == 0)

    doc, es, wid = fresh_state()
    t0 = time.perf_counter()
    n_exc = 0
    for _ in range(300):
        b = bytearray(real)
        for _ in range(rnd.randrange(1, 8)):
            b[rnd.randrange(len(b))] = rnd.randrange(256)
        try:
            D.apply_patch(doc, bytes(b), es, wid)
        except Exception as e:
            n_exc += 1
            print("  P5 EXCEPTION:", type(e).__name__, e)
    print(f"P5 corruptions x300: exceptions={n_exc} time={time.perf_counter()-t0:.2f}s "
          f"models={len(doc.models):,}")
    all_ok &= (n_exc == 0)

    doc, es, wid = fresh_state()
    stubs = [b"", b"\x07", b"\x07\x01", b"\x07\x01\x01", b"\x08\x01\x09",
             b"\x02", b"\x09\x01\xff", b"\x0c\x01\x01\x02", b"\xff" * 6]
    n_exc = 0
    for s in stubs:
        try:
            D.apply_patch(doc, s, es, wid)
        except Exception as e:
            n_exc += 1
            print("  P6 stub EXCEPTION:", s.hex(), type(e).__name__, e)
    try:
        D.apply_patch(D.Doc(), p2[:50_000], {}, None)   # world_id=None + garbage
        print("P6 stubs + world_id=None garbage: exceptions=", n_exc)
    except Exception as e:
        n_exc += 1
        print("  P6 None-world EXCEPTION:", type(e).__name__, e)
    all_ok &= (n_exc == 0)

    print("RESULT:", "ALL OK" if all_ok else "PROBLEM FOUND")


if __name__ == "__main__":
    main()
