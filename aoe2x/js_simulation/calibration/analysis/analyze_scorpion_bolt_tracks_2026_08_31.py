"""Trace live Heavy Scorpion bolt headings against their designated targets.

This is validation-only tape forensics.  It reads one project-local frames.bin
capture and records the exact source path in the derived report.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
GRPC = ROOT.parent / "grpc"
sys.path.insert(0, str(GRPC))

from google.protobuf import runtime_version as _rtv  # noqa: E402
_rtv.ValidateProtobufRuntimeVersion = lambda *args, **kwargs: None
import cade_api_pb2 as pb  # noqa: E402
import decode_state_v2 as D  # noqa: E402


SNAP_RESEED = 400_000
F_ID, F_MASTER, F_OWNER, F_X, F_Y, F_HP, F_CUR_ACTION = 0, 1, 2, 3, 4, 12, 20
A_STATE, A_TARGET = 1, 2
SCORPION_MASTER = 542
BOLT_MASTER = 627


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", default="expanded_roster_5x_2026-08-31")
    parser.add_argument("--matchup", default="heavy_scorpion_vs_hand_cannoneer")
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--output")
    return parser.parse_args()


def configuration(args):
    capture_root = (
        ROOT / "calibration" / "live_observations" / args.capture_root
    )
    manifest_path = capture_root / "capture_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    matchup = manifest["matchups"].get(args.matchup)
    if matchup is None:
        raise KeyError(f"capture manifest has no matchup {args.matchup}")
    side1 = matchup["side1"]
    side2 = matchup["side2"]
    if side1["slug"] == "heavy_scorpion":
        scorpion_owner = 2
    elif side2["slug"] == "heavy_scorpion":
        scorpion_owner = 3
    else:
        raise ValueError(f"{args.matchup} has no Heavy Scorpion side")
    run_name = f"run_{args.run:03d}"
    frames = (
        capture_root / args.matchup / run_name / "raw recordings"
        / f"{args.matchup}.frames.bin"
    )
    output = Path(args.output) if args.output else (
        ROOT / "calibration" / "reports"
        / "scorpion_onager_diagnostics_2026-08-31"
        / f"scorpion_bolt_tracks_{args.matchup}_{run_name}.json"
    )
    return {
        "captureManifest": manifest_path,
        "frames": frames,
        "matchup": args.matchup,
        "output": output,
        "scorpionOwner": scorpion_owner,
        "expected": Counter({2: side1["count"], 3: side2["count"]}),
    }


def finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def seed_snapshot(patch: bytes):
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as stream:
            stream.write(patch)
            path = stream.name
        doc = D.Doc()
        entities = {}
        _, world_id = D.seed_from_snapshot(path, doc, entities)
        return doc, entities, world_id
    finally:
        if path is not None:
            try:
                os.unlink(path)
            except OSError:
                pass


def merged(doc, entities, world_id):
    world_entities = doc.models.get(world_id, {}).get(1, {})
    for key, scalar in entities.items():
        doc_id = world_entities.get(key)
        entity = scalar
        if isinstance(doc_id, int) and doc_id in doc.models:
            entity = {**doc.models[doc_id], **scalar}
        yield key, entity


def action(doc, entity):
    action_id = entity.get(F_CUR_ACTION)
    model = doc.models.get(action_id) if isinstance(action_id, int) else None
    if not model:
        return None, None
    return model.get(A_STATE), model.get(A_TARGET)


def rounded(value):
    return None if value is None else round(value, 6)


def main(config) -> None:
    frames = config["frames"]
    matchup = config["matchup"]
    output = config["output"]
    scorpion_owner = config["scorpionOwner"]
    expected = config["expected"]
    doc = entities = world_id = None
    first_time = None
    prior_units = {}
    prior_actions = {}
    projectile_tracks = {}
    active_projectile_keys = set()
    attack_starts = []
    hp_drops = []

    with frames.open("rb") as stream:
        while True:
            header = stream.read(4)
            if len(header) < 4:
                break
            (length,) = struct.unpack("<I", header)
            payload = stream.read(length)
            if len(payload) != length:
                break
            sequence = pb.FrameSequence()
            sequence.ParseFromString(payload)
            for frame in sequence.frame:
                if frame.patch and len(frame.patch) > SNAP_RESEED:
                    doc, entities, world_id = seed_snapshot(frame.patch)
                    first_time = None
                    prior_units = {}
                    prior_actions = {}
                    projectile_tracks = {}
                    active_projectile_keys = set()
                    attack_starts = []
                    hp_drops = []
                    continue
                if entities is None:
                    continue
                if frame.patch:
                    D.apply_patch(doc, frame.patch, entities, world_id)

                units = {}
                projectiles = {}
                for key, entity in merged(doc, entities, world_id):
                    master = entity.get(F_MASTER)
                    if master == BOLT_MASTER and finite(entity.get(F_X)) and finite(entity.get(F_Y)):
                        projectiles[key] = {
                            "key": key,
                            "x": float(entity.get(F_X)),
                            "y": float(entity.get(F_Y)),
                            "owner": entity.get(F_OWNER),
                        }
                    owner = entity.get(F_OWNER)
                    if owner not in (2, 3, 4) or master == BOLT_MASTER:
                        continue
                    if not all(finite(entity.get(field)) for field in (F_X, F_Y, F_HP)):
                        continue
                    state, target_id = action(doc, entity)
                    units[key] = {
                        "key": key,
                        "id": entity.get(F_ID),
                        "master": master,
                        "owner": owner,
                        "x": float(entity.get(F_X)),
                        "y": float(entity.get(F_Y)),
                        "hp": float(entity.get(F_HP)),
                        "state": state,
                        "targetId": target_id,
                    }

                roster = Counter(
                    unit["owner"] for unit in units.values()
                    if unit["owner"] in (2, 3) and unit["hp"] > 0
                )
                if first_time is None:
                    if roster != expected:
                        continue
                    first_time = frame.time
                second = (frame.time - first_time) / 1000
                by_public_id = {unit["id"]: unit for unit in units.values()}

                for key, unit in units.items():
                    before = prior_units.get(key)
                    prior_state = prior_actions.get(key)
                    if (unit["owner"] == scorpion_owner
                            and unit["master"] == SCORPION_MASTER
                            and unit["state"] == 7 and prior_state != 7):
                        target = by_public_id.get(unit["targetId"])
                        target_before = prior_units.get(target["key"]) if target else None
                        attack_starts.append({
                            "second": rounded(second),
                            "actorId": unit["id"],
                            "actorX": rounded(unit["x"]),
                            "actorY": rounded(unit["y"]),
                            "targetId": unit["targetId"],
                            "targetX": rounded(target["x"] if target else None),
                            "targetY": rounded(target["y"] if target else None),
                            "targetDxPerFrame": rounded(
                                target["x"] - target_before["x"]
                                if target and target_before else None
                            ),
                            "targetDyPerFrame": rounded(
                                target["y"] - target_before["y"]
                                if target and target_before else None
                            ),
                        })
                    if before and unit["hp"] < before["hp"] - 1e-9:
                        hp_drops.append({
                            "second": rounded(second),
                            "victimId": unit["id"],
                            "victimOwner": unit["owner"],
                            "amount": rounded(before["hp"] - unit["hp"]),
                            "x": rounded(unit["x"]),
                            "y": rounded(unit["y"]),
                        })
                    prior_actions[key] = unit["state"]

                current_projectile_keys = set(projectiles)
                for key, projectile in projectiles.items():
                    track = projectile_tracks.get(key)
                    if track is None:
                        # The bolt starts at the Scorpion projectile-spawn offset;
                        # nearest live Scorpion is the unambiguous shooter here.
                        shooters = [
                            unit for unit in units.values()
                            if unit["owner"] == scorpion_owner
                            and unit["master"] == SCORPION_MASTER
                            and unit["hp"] > 0
                        ]
                        shooter = min(shooters, key=lambda unit: (
                            math.hypot(unit["x"] - projectile["x"], unit["y"] - projectile["y"]),
                            unit["id"],
                        )) if shooters else None
                        target = by_public_id.get(shooter["targetId"]) if shooter else None
                        target_before = prior_units.get(target["key"]) if target else None
                        track = {
                            "key": key,
                            "spawnSecond": rounded(second),
                            "lastSecond": rounded(second),
                            "startX": rounded(projectile["x"]),
                            "startY": rounded(projectile["y"]),
                            "lastX": rounded(projectile["x"]),
                            "lastY": rounded(projectile["y"]),
                            "samples": 0,
                            "shooterId": shooter["id"] if shooter else None,
                            "shooterX": rounded(shooter["x"] if shooter else None),
                            "shooterY": rounded(shooter["y"] if shooter else None),
                            "targetIdAtSpawn": shooter["targetId"] if shooter else None,
                            "targetXAtSpawn": rounded(target["x"] if target else None),
                            "targetYAtSpawn": rounded(target["y"] if target else None),
                            "targetDxPerFrameAtSpawn": rounded(
                                target["x"] - target_before["x"]
                                if target and target_before else None
                            ),
                            "targetDyPerFrameAtSpawn": rounded(
                                target["y"] - target_before["y"]
                                if target and target_before else None
                            ),
                        }
                        projectile_tracks[key] = track
                    track.update({
                        "lastSecond": rounded(second),
                        "lastX": rounded(projectile["x"]),
                        "lastY": rounded(projectile["y"]),
                        "samples": track["samples"] + 1,
                    })
                active_projectile_keys = current_projectile_keys
                prior_units = units

    tracks = []
    for track in projectile_tracks.values():
        dx = track["lastX"] - track["startX"]
        dy = track["lastY"] - track["startY"]
        distance = math.hypot(dx, dy)
        target_dx = (track["targetXAtSpawn"] - track["startX"]
                     if track["targetXAtSpawn"] is not None else None)
        target_dy = (track["targetYAtSpawn"] - track["startY"]
                     if track["targetYAtSpawn"] is not None else None)
        along = None
        lateral = None
        if distance > 1e-9 and target_dx is not None:
            ux, uy = dx / distance, dy / distance
            along = target_dx * ux + target_dy * uy
            lateral = abs(target_dx * uy - target_dy * ux)
        track["groundDistance"] = rounded(distance)
        track["targetAlongTrackAtSpawn"] = rounded(along)
        track["targetLateralFromTrackAtSpawn"] = rounded(lateral)
        tracks.append(track)

    report = {
        "schemaVersion": 1,
        "matchup": matchup,
        "sourceCaptureManifest": str(config["captureManifest"]),
        "sourceFramesBin": str(frames),
        "scorpionOwner": scorpion_owner,
        "expectedRoster": dict(sorted(expected.items())),
        "attackStarts": attack_starts,
        "boltTracks": sorted(tracks, key=lambda row: (row["spawnSecond"], str(row["key"]))),
        "hpDrops": hp_drops,
        "damageQuantaByVictimOwner": {
            str(owner): dict(sorted(Counter(
                str(drop["amount"]) for drop in hp_drops if drop["victimOwner"] == owner
            ).items()))
            for owner in (2, 3, 4)
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(output)


if __name__ == "__main__":
    main(configuration(arguments()))
