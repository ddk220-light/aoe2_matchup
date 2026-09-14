"""Verify the actual early-game P4 Hussars in archived gRPC frames."""
import struct
import tempfile
from pathlib import Path

from aoe2x.lab.io import read_json, write_json
from overlay.unit_timeline import D, pb, SNAP_RESEED


def verify(run, expected=5):
    run = Path(run)
    recording = read_json(run / "recording.json")
    plan = read_json(run.parent.parent / "plan.json")
    frames = run / recording["files"]["frames"]["path"]
    doc, entities, world = None, None, None
    with tempfile.TemporaryDirectory(prefix="screen-proof-") as tmp:
        snapshot = Path(tmp) / "snapshot.bin"
        with frames.open("rb") as stream:
            while header := stream.read(4):
                if len(header) != 4:
                    break
                size = struct.unpack("<I", header)[0]
                payload = stream.read(size)
                if len(payload) != size:
                    break
                for frame in pb.FrameSequence.FromString(payload).frame:
                    if len(frame.patch) > SNAP_RESEED:
                        snapshot.write_bytes(frame.patch)
                        doc, entities = D.Doc(), {}
                        _, world = D.seed_from_snapshot(str(snapshot), doc, entities)
                        continue
                    if entities is None:
                        continue
                    if frame.patch:
                        D.apply_patch(doc, frame.patch, entities, world)
                    if not 0 <= frame.time <= 3000:
                        continue
                    main = {o: [e for e in entities.values() if e.get(2) == o and e.get("__type__") in (9, 11, 12)
                                and e.get(1) != 448 and e.get(12, 0) > 0] for o in (2, 3)}
                    if [len(main[o]) for o in (2, 3)] != [plan[s]["count"] for s in ("side2", "side3")]:
                        continue
                    screen = [{"id": i, "master": e.get(1), "hp": e.get(12), "x": e.get(3), "y": e.get(4)}
                              for i, e in entities.items() if e.get(2) == 4 and e.get("__type__") in (9, 11, 12) and e.get(12, 0) > 0]
                    # gRPC retains the authored Scout master (448) even though
                    # Post-Imperial upgrades give these Spanish screen units the
                    # Golden's 95 HP. Do not expect the entity master to change.
                    if screen and all(e["master"] in (448, 441) and e["hp"] == 95 for e in screen):
                        if len(screen) != expected:
                            raise ValueError(f"Expected {expected} starting Hussars, observed {len(screen)}")
                        result = {"passed": True, "expected": expected, "actual": len(screen),
                                  "gameMs": frame.time, "framesSha256": recording["files"]["frames"]["sha256"],
                                  "units": screen}
                        write_json(run / "screen-verification.json", result)
                        return result
    raise ValueError("No early-game upgraded Hussar snapshot with both planned armies; inspect the raw frames")


if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--expected", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(verify(args.run, args.expected)))
