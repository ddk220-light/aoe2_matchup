"""gRPC capture -> data/4_lumber/truth.json (ground-truth economy timeline).

Reads the raw CadeRemote stream dump (lab/captures/4_lumber.frames.bin),
segments it on full snapshots / clock resets, picks the game segment, and
extracts frame-accurate economy events: spawns, deposits (carry reset),
tree felled/empty/removed, plus 1 Hz rows for charting.

Run: apps/video/.venv python (has grpcio/protobuf; decoder is repo-local).
"""
import json
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:\AI\aoe2_matchup\aoe2x\grpc")
import decode_state_v2 as D  # noqa: E402
import cade_api_pb2 as pb  # noqa: E402

FRAMES = Path(r"D:\AI\aoe2_matchup\lab\captures\4_lumber.frames.bin")
OUT = Path(__file__).resolve().parents[1] / "data" / "4_lumber" / "truth.json"
SNAP_RESEED = 400_000
F_MASTER, F_OWNER, F_X, F_Y, F_CARRY, F_HP = 1, 2, 3, 4, 6, 12
TREE_ID = 3662
START_TRACKED = [3652, 3654, 3656]


def read_seqs(path):
    with open(path, "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                return
            (n,) = struct.unpack("<I", hdr)
            buf = f.read(n)
            if len(buf) < n:
                return
            yield buf


def segment(path):
    segments, cur, last_t = [], {"snap": None, "frames": []}, None
    for raw in read_seqs(path):
        sq = pb.FrameSequence()
        try:
            sq.ParseFromString(raw)
        except Exception:
            continue
        for fr in sq.frame:
            t = fr.time
            events = [(ev.WhichOneof("event"), ev) for ev in fr.event]
            if fr.patch and len(fr.patch) > SNAP_RESEED:
                segments.append(cur)
                cur, last_t = {"snap": fr.patch, "frames": []}, t
                continue
            if last_t is not None and t and t < last_t - 2000:
                segments.append(cur)
                cur = {"snap": None, "frames": []}
            if t:
                last_t = t
            cur["frames"].append((t, fr.patch, events))
    segments.append(cur)
    best = None
    for s in segments:
        ts = [t for t, _, _ in s["frames"] if t]
        if s["snap"] and ts and (best is None or max(ts) > best[0]):
            best = (max(ts), s)
    if not best:
        raise SystemExit("no usable segment in capture")
    return best[1]


def main():
    seg = segment(FRAMES)
    tmp = Path(tempfile.gettempdir()) / "lumber_truth_seed.bin"
    tmp.write_bytes(seg["snap"])
    doc, es = D.Doc(), {}
    _, world_id = D.seed_from_snapshot(str(tmp), doc, es)

    tracked = list(START_TRACKED)
    deposits, spawns, rows = [], [], []
    prev_carry, known = {}, set(es)
    felled_t = empty_t = removed_t = None
    next_row = 0

    for t, patch, events in seg["frames"]:
        if patch:
            D.apply_patch(doc, patch, es, world_id)
        for which, ev in events:
            if which == "entityKilled":
                es.pop(ev.entityKilled.id, None)
        for eid in set(es) - known:
            e = es[eid]
            if e.get(F_OWNER) == 1:
                spawns.append({"eid": eid, "t": round(t / 1000, 2),
                               "master": e.get(F_MASTER)})
                tracked.append(eid)
        known |= set(es)
        for eid in tracked:
            e = es.get(eid)
            c = e.get(F_CARRY) if e else None
            p = prev_carry.get(eid)
            if p is not None and c is not None and p > 5 and c < 1:
                deposits.append({"t": round(t / 1000, 2), "eid": eid,
                                 "amount": round(p, 2)})
            if c is not None:
                prev_carry[eid] = c
        tree = es.get(TREE_ID)
        if tree:
            hp, w = tree.get(F_HP), tree.get(F_CARRY)
            if felled_t is None and hp is not None and hp <= 0:
                felled_t = round(t / 1000, 2)
            if empty_t is None and w is not None and w <= 0:
                empty_t = round(t / 1000, 2)
        elif removed_t is None and felled_t is not None:
            removed_t = round(t / 1000, 2)
        if t and t >= next_row:
            next_row = (t // 1000 + 1) * 1000
            rows.append({
                "t": round(t / 1000, 1),
                "vills": {str(eid): [round(es[eid][F_X], 2),
                                     round(es[eid][F_Y], 2),
                                     round(es[eid].get(F_CARRY) or 0, 2)]
                          for eid in tracked if eid in es},
                "tree_wood": round(tree.get(F_CARRY), 2) if tree else 0.0,
            })

    out = {
        "scenario": "4_lumber",
        "capture": {"file": FRAMES.name, "game_version": 178524},
        "spawn": spawns[0] if spawns else None,
        "spawns": spawns,
        "deposits": deposits,
        "tree": {"start_wood": 100.0, "hp": 20.0, "felled_t": felled_t,
                 "empty_t": empty_t, "removed_t": removed_t},
        "total_delivered": round(sum(d["amount"] for d in deposits), 2),
        "rows": rows,
    }

    # ---- self-check: the known shape of this capture ----
    assert len(deposits) == 11, f"expected 11 deposits, got {len(deposits)}"
    assert spawns and abs(spawns[0]["t"] - 35.26) < 0.1, spawns
    assert empty_t and 100 <= empty_t <= 104, empty_t
    assert abs(out["total_delivered"] - 100.3) < 1.0, out["total_delivered"]

    OUT.write_text(json.dumps(out, indent=1))
    print(f"OK {OUT}")
    print(f"  deposits={len(deposits)} spawn={spawns[0]['t']}"
          f" felled={felled_t} empty={empty_t} removed={removed_t}"
          f" total={out['total_delivered']}")
    for d in deposits:
        print(f"  deposit t={d['t']:7.2f} eid={d['eid']} amount={d['amount']}")


if __name__ == "__main__":
    main()
