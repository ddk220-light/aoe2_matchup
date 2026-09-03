"""Inspect live Siege Onager projectile motion and Player-4 HP loss.

The analysis reads the newest project-local run directly.  It records the
exact frames.bin path and never supplies observations to the simulation.
"""
from __future__ import annotations

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


MATCHUP_CONFIG = {
    "siege_onager_vs_champion": (567, "champion", 6, 27, 0.20),
    "siege_onager_vs_halberdier": (359, "halberdier", 5, 27, 0.20),
    "siege_onager_vs_paladin": (569, "paladin", 12, 27, 0.25),
    "siege_onager_vs_elite_steppe": (1372, "elite_steppe", 10, 27, 0.25),
    "siege_onager_vs_hussar": (441, "hussar", 7, 27, 0.25),
    "siege_onager_vs_heavy_camel": (330, "heavy_camel", 10, 27, 0.25),
}
MATCHUP = os.environ.get("AOE2X_ONAGER_PROJECTILE_MATCHUP", "siege_onager_vs_hussar")
if MATCHUP not in MATCHUP_CONFIG:
    raise ValueError(f"unsupported Onager projectile matchup: {MATCHUP}")
RUN_NUMBER = int(os.environ.get("AOE2X_ONAGER_PROJECTILE_RUN", "1"))
if RUN_NUMBER < 1 or RUN_NUMBER > 5:
    raise ValueError("Onager projectile run must be between 1 and 5")
TARGET_MASTER, TARGET_KIND, ONAGER_COUNT, TARGET_COUNT, TARGET_COLLISION = (
    MATCHUP_CONFIG[MATCHUP]
)
FRAMES = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31" / MATCHUP / f"run_{RUN_NUMBER:03d}"
    / "raw recordings" / f"{MATCHUP}.frames.bin"
)
OUTPUT = (
    ROOT / "calibration" / "reports" / "onager_full_fix_2026-09-01"
    / f"{MATCHUP}_projectiles_run_{RUN_NUMBER:03d}.json"
)

SNAP_RESEED = 400_000
F_ID, F_MASTER, F_OWNER, F_X, F_Y, F_HP, F_CUR_ACTION = 0, 1, 2, 3, 4, 12, 20
A_STATE, A_TARGET = 1, 2
UNIT_MASTERS = {
    588: "siege_onager",
    TARGET_MASTER: TARGET_KIND,
    448: "player4_scout",
}
PROJECTILE_MASTERS = {656: "primary_shell", 369: "secondary_debris"}
EXPECTED = Counter({2: ONAGER_COUNT, 3: TARGET_COUNT, 4: 9})
COLLISION_RADIUS = {588: 0.5, TARGET_MASTER: TARGET_COLLISION, 448: 0.25}


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


def formation_summary(units, owner):
    selected = [unit for unit in units.values()
                if unit["owner"] == owner and unit["hp"] > 0]
    overlap_pairs = 0
    for index, left in enumerate(selected):
        for right in selected[index + 1:]:
            extent = (COLLISION_RADIUS[left["master"]]
                      + COLLISION_RADIUS[right["master"]])
            if max(abs(left["x"] - right["x"]),
                   abs(left["y"] - right["y"])) < extent:
                overlap_pairs += 1
    return {
        "alive": len(selected),
        "xSpan": round(max((unit["x"] for unit in selected), default=0)
                       - min((unit["x"] for unit in selected), default=0), 6),
        "ySpan": round(max((unit["y"] for unit in selected), default=0)
                       - min((unit["y"] for unit in selected), default=0), 6),
        "overlapPairs": overlap_pairs,
        "units": sorted(({
            "id": unit["id"],
            "x": round(unit["x"], 6),
            "y": round(unit["y"], 6),
            "targetId": unit["targetId"],
            "actionState": unit["actionState"],
        } for unit in selected), key=lambda row: row["id"]),
    }


def main() -> None:
    doc = entities = world_id = None
    first_time = None
    prior_units = {}
    prior_actions = {}
    hp_drops = []
    attack_starts = []
    target_changes = []
    projectile_tracks = []
    active_projectiles = {}
    model_types_by_master = {}
    first_targets = {}
    last_valid_targets = {}
    formation_samples = {}

    with FRAMES.open("rb") as stream:
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
                    hp_drops = []
                    attack_starts = []
                    target_changes = []
                    projectile_tracks = []
                    active_projectiles = {}
                    model_types_by_master = {}
                    first_targets = {}
                    last_valid_targets = {}
                    formation_samples = {}
                    continue
                if entities is None:
                    continue
                if frame.patch:
                    D.apply_patch(doc, frame.patch, entities, world_id)
                current_units = {}
                current_projectiles = set()
                for key, entity in merged(doc, entities, world_id):
                    master = entity.get(F_MASTER)
                    if master in PROJECTILE_MASTERS:
                        model_types_by_master.setdefault(str(master), set()).add(
                            entity.get("__type__")
                        )
                        if finite(entity.get(F_X)) and finite(entity.get(F_Y)):
                            current_projectiles.add(key)
                            x = float(entity.get(F_X))
                            y = float(entity.get(F_Y))
                            track = active_projectiles.get(key)
                            if track is not None:
                                elapsed = max(0.0, (frame.time - track["lastMs"]) / 1000)
                                step = math.hypot(x - track["lastX"], y - track["lastY"])
                                # Decoded projectile entities remain addressable after
                                # landing and their negative keys are later reused.  A
                                # fresh launch therefore appears either as a physical
                                # teleport or as motion resuming after a stationary
                                # landing.  Split that reuse into a new generation.
                                if (step > 5.0 * elapsed + 0.25
                                        or (elapsed > 0.25 and step > 0.05)):
                                    track = None
                            if track is None:
                                track = {
                                "key": key,
                                "generation": sum(
                                    previous["key"] == key
                                    for previous in projectile_tracks
                                ),
                                "master": master,
                                "kind": PROJECTILE_MASTERS[master],
                                "owner": entity.get(F_OWNER),
                                "spawnMs": frame.time,
                                "lastMs": frame.time,
                                "startX": x,
                                "startY": y,
                                "lastX": x,
                                "lastY": y,
                                "samples": 0,
                                }
                                active_projectiles[key] = track
                                projectile_tracks.append(track)
                            moved = (x != track["lastX"] or y != track["lastY"])
                            if moved or track["samples"] == 0:
                                track.update({
                                    "lastMs": frame.time,
                                    "lastX": x,
                                    "lastY": y,
                                    "samples": track["samples"] + 1,
                                })
                    if master not in UNIT_MASTERS:
                        continue
                    owner = entity.get(F_OWNER)
                    if owner not in (2, 3, 4) or not finite(entity.get(F_HP)):
                        continue
                    state, target_id = action(doc, entity)
                    current_units[key] = {
                        "key": key,
                        "id": entity.get(F_ID),
                        "master": master,
                        "owner": owner,
                        "x": float(entity.get(F_X)),
                        "y": float(entity.get(F_Y)),
                        "hp": float(entity.get(F_HP)),
                        "actionState": state,
                        "targetId": target_id,
                    }
                roster = Counter(unit["owner"] for unit in current_units.values()
                                 if unit["hp"] > 0)
                if first_time is None:
                    if roster != EXPECTED:
                        continue
                    first_time = frame.time
                t = (frame.time - first_time) / 1000
                second = math.floor(t)
                if 0 <= second <= 20 and second not in formation_samples:
                    formation_samples[second] = {
                        "second": second,
                        **{
                            str(owner): formation_summary(current_units, owner)
                            for owner in (2, 3, 4)
                        },
                    }
                for key, unit in current_units.items():
                    before = prior_units.get(key)
                    if before and unit["hp"] < before["hp"] - 1e-9:
                        hp_drops.append({
                            "second": round(t, 6),
                            "victimId": unit["id"],
                            "victimOwner": unit["owner"],
                            "victimKind": UNIT_MASTERS[unit["master"]],
                            "amount": round(before["hp"] - unit["hp"], 6),
                            "x": round(unit["x"], 6),
                            "y": round(unit["y"], 6),
                        })
                    if (unit["owner"] == 2 and unit["master"] == 588
                            and unit["actionState"] == 7
                            and prior_actions.get(key) != 7):
                        target = next((candidate for candidate in current_units.values()
                                       if candidate["id"] == unit["targetId"]), None)
                        attack_starts.append({
                            "second": round(t, 6),
                            "actorId": unit["id"],
                            "actorX": round(unit["x"], 6),
                            "actorY": round(unit["y"], 6),
                            "targetId": unit["targetId"],
                            "targetOwner": target["owner"] if target else None,
                            "targetX": round(target["x"], 6) if target else None,
                            "targetY": round(target["y"], 6) if target else None,
                        })
                    if unit["owner"] == 2 and unit["master"] == 588:
                        target = next((candidate for candidate in current_units.values()
                                       if candidate["id"] == unit["targetId"]), None)
                        previous_target_id = last_valid_targets.get(key)
                        if (target is not None and previous_target_id is not None
                                and target["id"] != previous_target_id):
                            previous = next((candidate for candidate in current_units.values()
                                             if candidate["id"] == previous_target_id), None)
                            if previous is None:
                                previous = next((candidate for candidate in prior_units.values()
                                                 if candidate["id"] == previous_target_id), None)
                            target_changes.append({
                                "second": round(t, 6),
                                "actorId": unit["id"],
                                "actorActionState": unit["actionState"],
                                "previousTargetId": previous_target_id,
                                "previousTargetOwner": previous["owner"] if previous else None,
                                "previousTargetAlive": (
                                    previous is not None and previous["hp"] > 0
                                ),
                                "previousTargetHp": (
                                    round(previous["hp"], 6) if previous else None
                                ),
                                "newTargetId": target["id"],
                                "newTargetOwner": target["owner"],
                                "distanceToPrevious": (
                                    round(math.hypot(unit["x"] - previous["x"],
                                                     unit["y"] - previous["y"]), 6)
                                    if previous else None
                                ),
                                "distanceToNew": round(math.hypot(
                                    unit["x"] - target["x"], unit["y"] - target["y"]
                                ), 6),
                            })
                        if target is not None:
                            last_valid_targets[key] = target["id"]
                    prior_actions[key] = unit["actionState"]
                    if key not in first_targets and finite(unit["targetId"]):
                        target = next((candidate for candidate in current_units.values()
                                       if candidate["id"] == unit["targetId"]), None)
                        if target is not None:
                            first_targets[key] = {
                                "second": round(t, 6),
                                "actorId": unit["id"],
                                "actorOwner": unit["owner"],
                                "actorX": round(unit["x"], 6),
                                "actorY": round(unit["y"], 6),
                                "targetId": target["id"],
                                "targetOwner": target["owner"],
                            }
                for key in tuple(active_projectiles):
                    if key not in current_projectiles:
                        del active_projectiles[key]
                prior_units = current_units

    tracks = []
    for track in projectile_tracks:
        track["spawnSecond"] = round((track.pop("spawnMs") - first_time) / 1000, 6)
        track["lastSecond"] = round((track.pop("lastMs") - first_time) / 1000, 6)
        track["durationSeconds"] = round(track["lastSecond"] - track["spawnSecond"], 6)
        track["groundDistance"] = round(math.hypot(
            track["lastX"] - track["startX"], track["lastY"] - track["startY"]
        ), 6)
        tracks.append(track)
    primary = [track for track in tracks if track["master"] == 656]
    player4_drops = [drop for drop in hp_drops if drop["victimOwner"] == 4]
    report = {
        "schemaVersion": 1,
        "matchup": MATCHUP,
        "runNumber": RUN_NUMBER,
        "sourceFramesBin": str(FRAMES),
        "modelTypesByProjectileMaster": {
            master: sorted(value for value in values if value is not None)
            for master, values in model_types_by_master.items()
        },
        "onagerAttackStarts": attack_starts,
        "onagerTargetChanges": target_changes,
        "firstTargets": sorted(first_targets.values(), key=lambda row: (
            row["second"], row["actorOwner"], row["actorId"]
        )),
        "formationPerSecond": [formation_samples[second]
                               for second in sorted(formation_samples)],
        "primaryProjectileTracks": sorted(primary, key=lambda row: (row["spawnSecond"], row["key"])),
        "secondaryProjectileTrackCount": sum(track["master"] == 369 for track in tracks),
        "hpDrops": hp_drops,
        "player4HpDrops": player4_drops,
        "player4HpLost": round(sum(drop["amount"] for drop in player4_drops), 6),
        "player4DamageQuanta": dict(sorted(Counter(
            str(drop["amount"]) for drop in player4_drops
        ).items())),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
