"""Robust ground-truth from the gRPC COMMAND + EVENT streams (clean protobuf,
no fragile delta-patch decode).

  Make{unitId=type, unitPlayerId=owner, objId=producing building, uniqueId}
  Queue{buildingId, trainId=type, trainCount}
  Build{objId=building type, unitPlayerId, ...}
  Event.EntityKilled{id, killerId}   + frame.time

Produces, per player: units produced of each type with timestamps, buildings
built, and deaths over time. Cross-checks production vs the .aoe2record Queue log
to PROVE we parsed the 993 MB capture correctly.
"""
import json
import os
import struct
import sys
import types
from collections import Counter, defaultdict

import aocref
import cade_api_pb2 as pb

CAP = "GAME_munq_vs_ddk220_incas_frames_raw.bin"

# ---- name map ----
_p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
_raw = json.load(open(_p, encoding="utf-8"))
_objs = _raw.get("objects", _raw)
NAME = {}
for k, v in (_objs.items() if isinstance(_objs, dict) else []):
    try:
        NAME[int(k)] = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
    except Exception:
        pass
def nm(i): return NAME.get(i, f"id{i}")


def aoe2record_production():
    for m in ("flask", "flask_cors", "requests"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x"]
    import mgz.model
    mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
    prod = defaultdict(Counter)
    pmap = {}
    for p in mt.players:
        pmap[p.number] = p.name
    for a in mt.actions:
        if str(a.type).endswith("DE_QUEUE") and a.player and a.payload:
            prod[a.player.name][a.payload.get("unit")] += a.payload.get("amount", 1) or 1
    return prod, pmap


def main():
    f = open(CAP, "rb")
    make = defaultdict(Counter)        # player -> {type_name: count}
    make_first = {}                    # (player,type) -> first ms
    queue = Counter()                  # trainId type -> total trainCount
    build = defaultdict(Counter)       # player -> {building: count}
    kills = 0
    kill_times = []
    frames = 0
    last_t = 0
    n_cmd = Counter()
    n_evt = Counter()
    while True:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        ln = struct.unpack("<I", hdr)[0]
        buf = f.read(ln)
        if len(buf) < ln:
            break
        sq = pb.FrameSequence(); sq.ParseFromString(buf)
        for fr in sq.frame:
            frames += 1
            last_t = fr.time
            for ev in fr.event:
                w = ev.WhichOneof("event")
                n_evt[w] += 1
                if w == "entityKilled":
                    kills += 1
                    kill_times.append(fr.time)
            for c in fr.command:
                w = c.WhichOneof("command")
                n_cmd[w] += 1
                if w == "multiQueue":
                    m = c.multiQueue
                    p = m.playerId
                    t = nm(m.trainId)
                    cnt = m.trainCount or 1
                    make[p][t] += cnt
                    make_first.setdefault((p, t), fr.time)
                elif w == "make":
                    m = c.make
                    p = m.unitPlayerId
                    t = nm(m.unitId)
                    make[p][t] += 1
                    make_first.setdefault((p, t), fr.time)
                elif w == "queue":
                    q = c.queue
                    queue[nm(q.trainId)] += (q.trainCount or 1)
                elif w == "build":
                    b = c.build
                    build[b.unitPlayerId][nm(b.objId)] += 1
    f.close()
    print(f"frames={frames}  gametime={last_t}ms ({last_t/60000:.1f} min)")
    print(f"total kills (EntityKilled events): {kills}")
    print(f"ALL event types seen: {dict(n_evt.most_common())}")
    print(f"command types seen: {dict(n_cmd.most_common())}")

    print("\n==== MAKE commands (units produced) per player ====")
    for p in sorted(make):
        tot = sum(make[p].values())
        print(f"\n player {p}: {tot} units made")
        for t, c in make[p].most_common(40):
            fm = make_first.get((p, t), 0) / 60000
            print(f"    {t:24} {c:5}   first @ {fm:.1f} min")

    print("\n==== BUILD commands (buildings) per player ====")
    for p in sorted(build):
        print(f" player {p}: {dict(build[p].most_common(20))}")

    # cross-check vs .aoe2record (gRPC playerId == record player number)
    rec, pmap = aoe2record_production()
    print(f"\n==== CROSS-CHECK: gRPC MultiQueue vs .aoe2record DE_QUEUE ====")
    total_match = total_keys = 0
    for gp in sorted(make):
        rn = pmap.get(gp, f"player{gp}")
        rc = rec.get(rn, Counter())
        print(f"\n gRPC player {gp} == record '{rn}'")
        keys = sorted(set(make[gp]) | set(rc), key=lambda k: -(make[gp].get(k, 0) + rc.get(k, 0)))
        for k in keys:
            g = make[gp].get(k, 0); r = rc.get(k, 0)
            ok = (g == r)
            total_keys += 1; total_match += ok
            print(f"    {k:24} gRPC={g:5}  record={r:5}  {'OK' if ok else 'MISMATCH'}")
    print(f"\n  exact-match unit types: {total_match}/{total_keys}")

    out = {
        "frames": frames, "gametime_ms": last_t, "kills": kills,
        "make": {str(p): dict(c) for p, c in make.items()},
        "build": {str(p): dict(c) for p, c in build.items()},
        "queue": dict(queue),
        "kill_times": kill_times,
    }
    json.dump(out, open("events_summary.json", "w"))
    print("\nwrote events_summary.json")


if __name__ == "__main__":
    main()
