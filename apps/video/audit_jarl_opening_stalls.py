"""Read-only archive audit for long frozen Jarl clusters during opening combat.

Writes compact evidence locally, never edits archived media or starts the game.
Movement plus animation are checked together: stationary ranged attackers are
not idle merely because they stand still. Candidates still require review.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import struct
import tempfile
from pathlib import Path

from overlay.unit_timeline import D, pb, SNAP_RESEED
from redecode_hp import derive_army, refresh_army_membership


def read_samples(source, expected):
    segments, rows = [], []
    es = None
    last_ms = next_ms = None
    trailing_bytes = 0
    with tempfile.TemporaryDirectory(prefix="jarl-stall-audit-") as tmp:
        snapshot = Path(tmp) / "snapshot.bin"
        with source.open("rb") as stream:
            while header := stream.read(4):
                if len(header) != 4:
                    trailing_bytes = len(header)
                    break
                size = struct.unpack("<I", header)[0]
                payload = stream.read(size)
                if len(payload) != size:
                    # Recorder shutdown may leave a trailing partial sequence;
                    # audit only complete snapshots, as unit_timeline does.
                    trailing_bytes = len(payload) + 4
                    break
                for frame in pb.FrameSequence.FromString(payload).frame:
                    if len(frame.patch) > SNAP_RESEED:
                        if rows:
                            segments.append(rows)
                        rows = []
                        snapshot.write_bytes(frame.patch)
                        doc, es = D.Doc(), {}
                        with contextlib.redirect_stdout(io.StringIO()):
                            _, world = D.seed_from_snapshot(str(snapshot), doc, es)
                        army = derive_army(es)
                        last_ms = next_ms = None
                        continue
                    if es is None:
                        continue
                    if last_ms is not None and frame.time < last_ms - 2000:
                        if rows:
                            segments.append(rows)
                        rows, es = [], None
                        continue
                    last_ms = frame.time
                    if frame.patch:
                        D.apply_patch(doc, frame.patch, es, world)
                        refresh_army_membership(es, army)
                    for event in frame.event:
                        if event.HasField("entityKilled"):
                            es.pop(event.entityKilled.id, None)
                    if next_ms is not None and frame.time < next_ms:
                        continue
                    next_ms = frame.time + 200
                    sides = {}
                    for owner in (2, 3):
                        units = []
                        for eid in sorted(army[owner]):
                            e = es.get(eid, {})
                            if e.get(12, 0) <= 0 or e.get(2) != owner:
                                continue
                            model = doc.models.get(doc.models[world].get(1, {}).get(eid), {})
                            animation = tuple((doc.models.get(ref, {}).get(0),
                                               doc.models.get(ref, {}).get(3))
                                              for ref in model.get(17, {}).values())
                            units.append(dict(id=eid, x=e.get(3), y=e.get(4), hp=e[12],
                                              sprite=e.get(15), animation=animation))
                        sides[str(owner)] = units
                    rows.append(dict(gameSeconds=frame.time / 1000, sides=sides))
    if rows:
        segments.append(rows)
    valid = [s for s in segments if [len(s[0]["sides"][o]) for o in ("2", "3")] == expected]
    fights = [s for s in valid if any(len(s[-1]["sides"][o]) < expected[i] for i, o in enumerate(("2", "3")))]
    if not valid:
        raise ValueError(f"No recorded segment matches {expected}")
    return (fights or valid)[-1], trailing_bytes


def find_stalls(rows):
    initial = {u["id"]: u for u in rows[0]["sides"]["2"]}
    starting_hp = sum(u["hp"] for u in initial.values())
    blocks, findings = {}, []

    def finish(eid):
        b = blocks.pop(eid, None)
        if not b:
            return
        # Eight game seconds is much longer than a normal Jarl attack cycle.
        # Focus on clusters that freeze during the opening, not post-victory rest.
        if (b["end"] - b["start"] >= 8 and b["start"] <= 10
                and b["armyHpFractionEnd"] < 0.85 and b["nearestEnemyEnd"] > 4.5):
            findings.append(dict(entityId=eid, startSeconds=round(b["start"], 3),
                                 endSeconds=round(b["end"], 3),
                                 durationSeconds=round(b["end"] - b["start"], 3),
                                 position=[b["x"], b["y"]],
                                 nearestEnemyAtEnd=b["nearestEnemyEnd"],
                                 alliedSurvivorsAtEnd=b["aliveEnd"],
                                 armyHpFractionAtEnd=b["armyHpFractionEnd"]))

    for r in rows:
        enemies = r["sides"]["3"]
        own = {u["id"]: u for u in r["sides"]["2"]}
        for eid in list(blocks):
            if eid not in own or not enemies:
                finish(eid)
        if not enemies:
            continue
        for eid, u in own.items():
            if eid not in initial or u["x"] is None or u["y"] is None:
                continue
            signature = (u["sprite"], u["animation"])
            b = blocks.get(eid)
            same = (b and b["signature"] == signature and b["hp"] == u["hp"]
                    and math.hypot(u["x"]-b["x"], u["y"]-b["y"]) <= 0.08)
            if not same:
                finish(eid)
                b = dict(start=r["gameSeconds"], x=u["x"], y=u["y"], hp=u["hp"], signature=signature)
                blocks[eid] = b
            b.update(end=r["gameSeconds"], aliveEnd=len(own),
                     armyHpFractionEnd=sum(v["hp"] for v in own.values()) / starting_hp,
                     nearestEnemyEnd=min(math.hypot(u["x"]-v["x"], u["y"]-v["y"]) for v in enemies))
    for eid in list(blocks):
        finish(eid)
    return findings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--job")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    entries = json.loads(a.index.read_text())["matchups"]
    results = []
    for entry in entries:
        if a.job and a.job not in entry["jobId"]:
            continue
        dest = a.out / (entry["jobId"] + ".json")
        media = entry["files"]["frames.bin"]
        if dest.exists():
            cached = json.loads(dest.read_text())
            if cached.get("framesSha256") == media["sha256"]:
                results.append(cached)
                continue
        source = (a.index.parent / media["path"]).resolve()
        if not source.is_relative_to(a.index.parent.resolve()):
            raise ValueError("Archive path escape")
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if source.stat().st_size != media["bytes"] or actual_hash != media["sha256"]:
            raise ValueError(f"Archive checksum mismatch: {entry['jobId']}")
        rows, trailing_bytes = read_samples(source, entry["capture"]["capture"]["startCounts"])
        stalls = find_stalls(rows)
        result = dict(jobId=entry["jobId"], opponent=entry["plan"]["side3"]["label"],
                      counts=entry["capture"]["capture"]["startCounts"],
                      family=entry["plan"]["scenario"]["family"],
                      framesSha256=actual_hash, sampledFrames=len(rows), trailingPartialBytes=trailing_bytes,
                      candidateUnits=len({s["entityId"] for s in stalls}), stalls=stalls)
        dest.write_text(json.dumps(result, indent=2))
        results.append(result)
        print(f"{len(results)}/{len(entries)} {entry['jobId']}: {result['candidateUnits']} frozen units", flush=True)
        (a.out / "status.json").write_text(json.dumps(dict(checked=len(results), total=len(entries))))
    (a.out / "audit.json").write_text(json.dumps(dict(index=str(a.index), checked=len(results),
        criteria="Opening freeze >=8 game seconds: same position within 0.08 tiles, unchanged HP and animation; starts <=10s; army HP falls below85%; closest enemy >4.5tiles. Candidates require review.",
        results=results), indent=2))


if __name__ == "__main__":
    main()
