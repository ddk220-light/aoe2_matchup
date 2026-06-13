"""gRPC capture -> data/<scenario>/truth.json (ground-truth economy timeline).

Generalized over scenarios. Reads the raw CadeRemote stream dump, segments it
on full snapshots / clock resets, picks the game segment, and extracts
frame-accurate economy events: owner-1 spawns, building foundations AND their
construction-complete times (HP ramp reaching its final max), deposits
(villager carry reset to ~0), per-resource-node depletion (trees & bushes),
and a 1 Hz collected curve.

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
BUILDING_MASTERS = {562, 109, 70, 68, 79, 12, 87, 101, 49, 84}  # camp/tc/house/mill...
# Villagers mutate master by profession (forager/lumberjack/builder/...):
# include all task variants so trained-villager spawns are caught.
UNIT_MASTERS = {83, 293, 448, 118, 212, 120, 354, 123, 218, 122, 216,
                124, 220, 579, 581, 259, 214, 156, 222}
DOPPLE_MASTER = 243
BUSH_MASTER = 1059


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
    bldg_hp = {}        # eid -> [(t, hp)] sparse hp ramp for new owner-1 buildings
    # resource nodes present in the seed: trees handled per-scenario before;
    # now track ANY gaia node with a pool (bushes, straggler trees...).
    node0 = {eid: e.get(F_CARRY) for eid, e in es.items()
             if e.get(F_OWNER) is None and isinstance(e.get(F_CARRY), float)
             and e.get(F_CARRY) > 0}
    node_seen = {}      # eid -> {"first_drop": t, "empty": t|None, "last": pool}
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
                    buildings.append({"t": ts, "eid": eid, "master": m,
                                      "x": e.get(F_X), "y": e.get(F_Y)})
                    bldg_hp[eid] = []
                elif m in UNIT_MASTERS and eid > 0:
                    spawns.append({"t": ts, "eid": eid, "master": m})
        known |= set(es)
        ts = round(t / 1000, 2) if t else None
        # building construction ramps (sparse: record hp changes only)
        for eid, ramp in bldg_hp.items():
            e = es.get(eid)
            hp = e.get(F_HP) if e else None
            if isinstance(hp, float) and (not ramp or ramp[-1][1] != hp) and ts:
                ramp.append((ts, hp))
        # resource node depletion
        for eid, p0 in node0.items():
            e = es.get(eid)
            pool = e.get(F_CARRY) if e else None
            if not isinstance(pool, float) or ts is None:
                continue
            st = node_seen.setdefault(eid, {"first_drop": None, "empty": None,
                                            "last": p0})
            if pool < st["last"] - 1e-6 and st["first_drop"] is None:
                st["first_drop"] = ts
            if pool < 1e-6 and st["last"] > 1e-6:
                st["empty"] = ts
            st["last"] = pool
        # deposits
        for eid in list(owner1):
            e = es.get(eid)
            c = e.get(F_CARRY) if e else None
            if not isinstance(c, float):
                continue
            p = prev_carry.get(eid)
            if p is not None and p > 5 and c < 1 and ts:
                deposits.append({"t": ts, "eid": eid, "amount": round(p, 2)})
            prev_carry[eid] = c
        if t and t >= next_row:
            next_row = (t // 1000 + 1) * 1000
            rows.append({"t": round(t / 1000, 1),
                         "collected": round(sum(d["amount"] for d in deposits), 1)})

    # building completion: first time the hp ramp hits its final (max) value
    for b in buildings:
        ramp = bldg_hp.get(b["eid"]) or []
        if ramp:
            final = ramp[-1][1]
            b["hp_final"] = final
            b["completed_t"] = next(t for t, hp in ramp if hp >= final - 1e-6)
            b["hp_ramp_n"] = len(ramp)

    nodes = [{"eid": eid, "pool0": round(p0, 1),
              "taken": round(p0 - node_seen[eid]["last"], 2),
              "first_drop": node_seen[eid]["first_drop"],
              "empty": node_seen[eid]["empty"]}
             for eid, p0 in sorted(node0.items())
             if eid in node_seen and node_seen[eid]["first_drop"] is not None]

    total = round(sum(d["amount"] for d in deposits), 2)
    out = {
        "scenario": SCEN,
        "capture": {"file": FRAMES.name, "game_version": 178524},
        "buildings": buildings,
        "spawns": spawns,
        "deposits": deposits,
        "nodes": nodes,
        "total_collected": total,
        "rows": rows,
    }

    # ---- self-check ----
    assert buildings, "no owner-1 building detected"
    assert spawns, "no trained units detected"
    assert total > 50, f"implausibly low collected total {total}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"OK {OUT}")
    print(f"  buildings={len(buildings)} spawns={len(spawns)} "
          f"deposits={len(deposits)} total={total}")
    for b in buildings:
        print(f"  building m={b['master']} eid={b['eid']} found t={b['t']} "
              f"completed t={b.get('completed_t')} hp={b.get('hp_final')} "
              f"pos=({b.get('x')},{b.get('y')})")
    print(f"  spawn times={[s['t'] for s in spawns]}")
    print(f"  nodes touched={[(n['eid'], n['pool0'], n['taken'], n['empty']) for n in nodes]}")


if __name__ == "__main__":
    main()
