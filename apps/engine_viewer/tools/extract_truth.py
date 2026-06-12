"""gRPC capture -> data/<scenario>/truth.json (ground-truth economy timeline).

Generalized over scenarios. Reads the raw CadeRemote stream dump, segments it
on full snapshots / clock resets, picks the game segment, and extracts
frame-accurate economy events: owner-1 spawns (incl. buildings), deposits
(villager carry reset to ~0), and a 1 Hz wood-collected curve.

Usage: extract_truth.py <scenario>   (default: camp300)
Run with apps/video/.venv python (grpcio/protobuf; decoder is repo-local).
"""
import json
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:\AI\aoe2_matchup\aoe2x\grpc")
import decode_state_v2 as D  # noqa: E402
import cade_api_pb2 as pb  # noqa: E402

SCEN = sys.argv[1] if len(sys.argv) > 1 else "camp300"
ROOT = Path(__file__).resolve().parents[1]
FRAMES = Path(r"D:\AI\aoe2_matchup\lab\captures") / f"{SCEN}.frames.bin"
OUT = ROOT / "data" / SCEN / "truth.json"
SNAP_RESEED = 400_000
F_MASTER, F_OWNER, F_X, F_Y, F_CARRY, F_HP = 1, 2, 3, 4, 6, 12
# master ids: villagers carry a resource; buildings/dopples don't gather.
BUILDING_MASTERS = {562, 109, 70, 68, 79, 12, 87, 101, 49, 84}  # camp/tc/house...
DOPPLE_MASTER = 243


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
    tmp = Path(tempfile.gettempdir()) / f"{SCEN}_truth_seed.bin"
    tmp.write_bytes(seg["snap"])
    doc, es = D.Doc(), {}
    _, world_id = D.seed_from_snapshot(str(tmp), doc, es)

    known = set(es)
    owner1 = set(eid for eid, e in es.items() if e.get(F_OWNER) == 1)
    prev_carry = {}
    spawns, buildings, deposits, rows = [], [], [], []
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
                owner1.add(eid)
                m = e.get(F_MASTER)
                ts = round(t / 1000, 2)
                if m in BUILDING_MASTERS:
                    buildings.append({"t": ts, "eid": eid, "master": m})
                elif m != DOPPLE_MASTER and eid > 0:
                    spawns.append({"t": ts, "eid": eid, "master": m})
        known |= set(es)
        for eid in list(owner1):
            e = es.get(eid)
            c = e.get(F_CARRY) if e else None
            if not isinstance(c, float):
                continue
            p = prev_carry.get(eid)
            if p is not None and p > 5 and c < 1:
                deposits.append({"t": round(t / 1000, 2), "eid": eid,
                                 "amount": round(p, 2)})
            prev_carry[eid] = c
        if t and t >= next_row:
            next_row = (t // 1000 + 1) * 1000
            rows.append({"t": round(t / 1000, 1),
                         "collected": round(sum(d["amount"] for d in deposits), 1)})

    total = round(sum(d["amount"] for d in deposits), 2)
    out = {
        "scenario": SCEN,
        "capture": {"file": FRAMES.name, "game_version": 178524},
        "buildings": buildings,
        "spawns": spawns,
        "deposits": deposits,
        "total_collected": total,
        "rows": rows,
    }

    # ---- self-check ----
    assert buildings, "no owner-1 building (lumber camp) detected"
    assert len(spawns) >= 3, f"expected trained villagers, got {len(spawns)}"
    assert 250 <= total <= 320, f"collected wood {total} out of expected range"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"OK {OUT}")
    print(f"  buildings={len(buildings)} spawns={len(spawns)} "
          f"deposits={len(deposits)} total={total}")
    print(f"  camp t={buildings[0]['t']}  "
          f"spawn times={[s['t'] for s in spawns]}")


if __name__ == "__main__":
    main()
