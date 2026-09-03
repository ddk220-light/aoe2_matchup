"""Measure Heavy Scorpion pass-through damage and live hit geometry.

Validation-only tape forensics.  Every report records the exact project-local
capture manifest and frames.bin used.  No measured outcome is consumed by the
runtime simulator.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import statistics
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
BOLT_HALF_WIDTH = 0.1


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", default="expanded_roster_5x_2026-08-31")
    parser.add_argument("--matchup", default="heavy_scorpion_vs_hand_cannoneer")
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--output")
    return parser.parse_args()


def configuration(args):
    capture_root = ROOT / "calibration" / "live_observations" / args.capture_root
    manifest_path = capture_root / "capture_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    matchup = manifest["matchups"].get(args.matchup)
    if matchup is None:
        raise KeyError(f"capture manifest has no matchup {args.matchup}")
    side1 = matchup["side1"]
    side2 = matchup["side2"]
    if side1["slug"] == "heavy_scorpion":
        scorpion_owner = 2
        victim_owner = 3
    elif side2["slug"] == "heavy_scorpion":
        scorpion_owner = 3
        victim_owner = 2
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
        / f"scorpion_damage_geometry_{args.matchup}_{run_name}.json"
    )
    return {
        "captureManifest": manifest_path,
        "frames": frames,
        "matchup": args.matchup,
        "run": args.run,
        "output": output,
        "scorpionOwner": scorpion_owner,
        "victimOwner": victim_owner,
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


def fixture_geometry():
    """Return collision half-extents indexed by master ID."""
    observed = defaultdict(set)
    for path in (ROOT / "fixtures" / "unit_stats").glob("*.json"):
        try:
            fixture = json.loads(path.read_text(encoding="utf8"))
            master = int(fixture["unit_master"])
            collision = fixture["collision_size_tiles"]
            observed[master].add((float(collision["x"]), float(collision["y"])))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    result = {}
    for master, sizes in observed.items():
        # Geometry is a base-unit property.  Keep the largest record if a
        # historical fixture disagrees so a reported hit is never made to look
        # artificially farther outside the victim body.
        result[master] = max(sizes, key=lambda size: (size[0] * size[1], size))
    return result


def closest_on_segment(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy
    if length2 <= 1e-18:
        return x0, y0, 0.0
    fraction = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / length2))
    return x0 + fraction * dx, y0 + fraction * dy, fraction


def geometry_to_segment(victim, before, after, radius_x, radius_y):
    qx, qy, fraction = closest_on_segment(
        victim["x"], victim["y"], before["x"], before["y"], after["x"], after["y"])
    dx = abs(victim["x"] - qx)
    dy = abs(victim["y"] - qy)
    expanded_x = radius_x + BOLT_HALF_WIDTH
    expanded_y = radius_y + BOLT_HALF_WIDTH
    outside_x = max(0.0, dx - expanded_x)
    outside_y = max(0.0, dy - expanded_y)
    return {
        "closestX": qx,
        "closestY": qy,
        "segmentFraction": fraction,
        "centerDistance": math.hypot(dx, dy),
        "centerChebyshev": max(dx, dy),
        "axisDx": dx,
        "axisDy": dy,
        "expandedBoxOutsideDistance": math.hypot(outside_x, outside_y),
        "expandedBoxMargin": max(dx - expanded_x, dy - expanded_y),
    }


def rounded(value):
    return None if value is None else round(value, 6)


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * fraction
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def summary(values):
    finite_values = [float(value) for value in values if finite(value)]
    if not finite_values:
        return {"count": 0}
    return {
        "count": len(finite_values),
        "min": rounded(min(finite_values)),
        "p05": rounded(percentile(finite_values, 0.05)),
        "median": rounded(statistics.median(finite_values)),
        "mean": rounded(statistics.fmean(finite_values)),
        "p95": rounded(percentile(finite_values, 0.95)),
        "max": rounded(max(finite_values)),
    }


def main(config):
    geometry = fixture_geometry()
    doc = entities = world_id = None
    first_time = None
    prior_units = {}
    prior_projectiles = {}
    tracks = {}
    hits = []
    frame_intervals_ms = []
    prior_frame_time = None

    with config["frames"].open("rb") as stream:
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
                    prior_projectiles = {}
                    tracks = {}
                    hits = []
                    frame_intervals_ms = []
                    prior_frame_time = None
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
                            "id": entity.get(F_ID),
                            "owner": entity.get(F_OWNER),
                            "x": float(entity.get(F_X)),
                            "y": float(entity.get(F_Y)),
                        }
                        continue
                    owner = entity.get(F_OWNER)
                    # Missiles are ordinary Genie entities with 1 HP and
                    # negative public IDs.  Do not mistake the opponent's
                    # disappearing projectiles for damaged combat units.
                    public_id = entity.get(F_ID)
                    if not isinstance(public_id, int) or public_id <= 0:
                        continue
                    if owner not in (2, 3, 4):
                        continue
                    if not all(finite(entity.get(field)) for field in (F_X, F_Y, F_HP)):
                        continue
                    state, target_id = action(doc, entity)
                    units[key] = {
                        "key": key,
                        "id": public_id,
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
                    if roster != config["expected"]:
                        continue
                    first_time = frame.time
                second = (frame.time - first_time) / 1000
                if prior_frame_time is not None and frame.time > prior_frame_time:
                    frame_intervals_ms.append(frame.time - prior_frame_time)
                prior_frame_time = frame.time
                by_public_id = {unit["id"]: unit for unit in units.values()}

                # Bind a newly visible bolt to the nearest live Scorpion and
                # its current action target.  Its projectile-spawn offset is
                # much smaller than formation spacing, making this unique in
                # all captures inspected here.
                for key, projectile in projectiles.items():
                    if key not in tracks:
                        shooters = [
                            unit for unit in units.values()
                            if unit["owner"] == config["scorpionOwner"]
                            and unit["master"] == SCORPION_MASTER
                            and unit["hp"] > 0
                        ]
                        shooter = min(shooters, key=lambda unit: (
                            math.hypot(unit["x"] - projectile["x"], unit["y"] - projectile["y"]),
                            unit["id"],
                        )) if shooters else None
                        tracks[key] = {
                            "key": str(key),
                            "projectileId": projectile["id"],
                            "shooterId": shooter["id"] if shooter else None,
                            "targetIdAtSpawn": shooter["targetId"] if shooter else None,
                            "spawnSecond": rounded(second),
                            "startX": rounded(projectile["x"]),
                            "startY": rounded(projectile["y"]),
                            "lastSecond": rounded(second),
                            "lastX": rounded(projectile["x"]),
                            "lastY": rounded(projectile["y"]),
                            "samples": 0,
                        }
                    tracks[key].update({
                        "lastSecond": rounded(second),
                        "lastX": rounded(projectile["x"]),
                        "lastY": rounded(projectile["y"]),
                        "samples": tracks[key]["samples"] + 1,
                    })

                # A hit can share a patch with the bolt's movement or expiry.
                # Consider the union of current and immediately prior bolts;
                # rank candidates by distance from the swept frame segment to
                # the victim's collision box.
                projectile_union = set(projectiles) | set(prior_projectiles)
                for key, victim in units.items():
                    before_victim = prior_units.get(key)
                    if (not before_victim
                            or victim["owner"] != config["victimOwner"]
                            or victim["hp"] >= before_victim["hp"] - 1e-9):
                        continue
                    radius_x, radius_y = geometry.get(victim["master"], (0.0, 0.0))
                    candidates = []
                    for projectile_key in projectile_union:
                        track = tracks.get(projectile_key)
                        if track is None:
                            continue
                        current = projectiles.get(projectile_key)
                        previous = prior_projectiles.get(projectile_key)
                        if current is None and previous is None:
                            continue
                        if current is None:
                            current = previous
                        if previous is None:
                            previous = current
                        if current.get("owner") != config["scorpionOwner"]:
                            continue
                        measure = geometry_to_segment(
                            victim, previous, current, radius_x, radius_y)
                        target_now = by_public_id.get(track["targetIdAtSpawn"])
                        target_dx = abs(victim["x"] - target_now["x"]) if target_now else None
                        target_dy = abs(victim["y"] - target_now["y"]) if target_now else None
                        candidates.append({
                            "projectileKey": str(projectile_key),
                            "projectileId": current.get("id"),
                            "shooterId": track["shooterId"],
                            "targetIdAtSpawn": track["targetIdAtSpawn"],
                            "isDesignatedTarget": victim["id"] == track["targetIdAtSpawn"],
                            "targetXNow": rounded(target_now["x"] if target_now else None),
                            "targetYNow": rounded(target_now["y"] if target_now else None),
                            "victimDistanceToDesignatedTarget": rounded(
                                math.hypot(target_dx, target_dy)
                                if target_dx is not None else None
                            ),
                            "victimChebyshevToDesignatedTarget": rounded(
                                max(target_dx, target_dy)
                                if target_dx is not None else None
                            ),
                            "previousX": rounded(previous["x"]),
                            "previousY": rounded(previous["y"]),
                            "currentX": rounded(current["x"]),
                            "currentY": rounded(current["y"]),
                            **{name: rounded(value) for name, value in measure.items()},
                        })
                    candidates.sort(key=lambda row: (
                        row["expandedBoxOutsideDistance"],
                        row["centerDistance"],
                        row["projectileKey"],
                    ))
                    nearest = candidates[0] if candidates else None
                    hits.append({
                        "second": rounded(second),
                        "victimId": victim["id"],
                        "victimMaster": victim["master"],
                        "amount": rounded(before_victim["hp"] - victim["hp"]),
                        "hpBefore": rounded(before_victim["hp"]),
                        "hpAfter": rounded(victim["hp"]),
                        "victimX": rounded(victim["x"]),
                        "victimY": rounded(victim["y"]),
                        "collisionHalfX": radius_x,
                        "collisionHalfY": radius_y,
                        "nearestBolt": nearest,
                        "plausibleBoltCount": sum(
                            candidate["expandedBoxOutsideDistance"] <= 1e-6
                            for candidate in candidates
                        ),
                        "nearbyCandidates": candidates[:4],
                    })

                prior_units = units
                prior_projectiles = projectiles

    # Distance from each victim to its attributed bolt's complete travel line.
    # This is the cleanest test for a radial splash outside the swept bolt body.
    tracks_by_string_key = {str(key): value for key, value in tracks.items()}
    for hit in hits:
        nearest = hit["nearestBolt"]
        if nearest is None:
            continue
        track = tracks_by_string_key.get(nearest["projectileKey"])
        if track is None:
            continue
        dx = track["lastX"] - track["startX"]
        dy = track["lastY"] - track["startY"]
        distance = math.hypot(dx, dy)
        if distance <= 1e-12:
            continue
        ux, uy = dx / distance, dy / distance
        victim_dx = hit["victimX"] - track["startX"]
        victim_dy = hit["victimY"] - track["startY"]
        along = victim_dx * ux + victim_dy * uy
        lateral = abs(victim_dx * uy - victim_dy * ux)
        nearest["victimAlongFullTrack"] = rounded(along)
        nearest["victimLateralFromFullTrack"] = rounded(lateral)
        nearest["lateralBeyondCollisionAndBolt"] = rounded(max(
            0.0,
            lateral - max(hit["collisionHalfX"], hit["collisionHalfY"])
            - BOLT_HALF_WIDTH,
        ))

    attributed = [hit for hit in hits if hit["nearestBolt"] is not None]
    designated = [hit for hit in attributed if hit["nearestBolt"]["isDesignatedTarget"]]
    passthrough = [hit for hit in attributed if not hit["nearestBolt"]["isDesignatedTarget"]]
    unambiguous = [hit for hit in attributed if hit["plausibleBoltCount"] == 1]

    def amount_counts(rows):
        return dict(sorted(Counter(str(row["amount"]) for row in rows).items()))

    report = {
        "schemaVersion": 1,
        "matchup": config["matchup"],
        "run": config["run"],
        "sourceCaptureManifest": str(config["captureManifest"]),
        "sourceFramesBin": str(config["frames"]),
        "scorpionOwner": config["scorpionOwner"],
        "victimOwner": config["victimOwner"],
        "expectedRoster": dict(sorted(config["expected"].items())),
        "datProjectileEvidence": {
            "projectileUnit": BOLT_MASTER,
            "collisionHalfWidthTiles": BOLT_HALF_WIDTH,
            "blastWidthTiles": 0.0,
            "hitMode": 1,
            "vanishMode": 1,
            "note": "Values independently read from installed build-180059 Genie DAT unit 627.",
        },
        "summary": {
            "frameIntervalMs": summary(frame_intervals_ms),
            "visibleBoltTracks": len(tracks),
            "enemyHpDrops": len(hits),
            "attributedDrops": len(attributed),
            "unambiguousSweptBoxDrops": len(unambiguous),
            "designatedTargetDrops": len(designated),
            "passThroughDrops": len(passthrough),
            "damageQuanta": {
                "all": amount_counts(attributed),
                "designatedTarget": amount_counts(designated),
                "passThrough": amount_counts(passthrough),
            },
            "nearestBoltGeometry": {
                "centerDistanceToFrameSegment": summary(
                    hit["nearestBolt"]["centerDistance"] for hit in attributed),
                "expandedBoxMargin": summary(
                    hit["nearestBolt"]["expandedBoxMargin"] for hit in attributed),
                "expandedBoxOutsideDistance": summary(
                    hit["nearestBolt"]["expandedBoxOutsideDistance"] for hit in attributed),
                "victimLateralFromFullTrack": summary(
                    hit["nearestBolt"].get("victimLateralFromFullTrack")
                    for hit in attributed),
                "lateralBeyondCollisionAndBolt": summary(
                    hit["nearestBolt"].get("lateralBeyondCollisionAndBolt")
                    for hit in attributed),
            },
        },
        "boltTracks": sorted(tracks.values(), key=lambda row: (row["spawnSecond"], row["key"])),
        "hits": hits,
    }
    config["output"].parent.mkdir(parents=True, exist_ok=True)
    config["output"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(config["output"])


if __name__ == "__main__":
    main(configuration(arguments()))
