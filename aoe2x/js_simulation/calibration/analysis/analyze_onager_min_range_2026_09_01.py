"""Measure live Siege Onager behavior after melee enters minimum range.

This is validation-only tape forensics.  It reads the exact project-local
``frames.bin`` captures and publishes source paths with every run; no observed
outcome is converted into a simulation parameter.
"""
from __future__ import annotations

from collections import Counter
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


CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31"
)
OUTPUT = (
    ROOT / "calibration" / "reports" / "onager_full_fix_2026-09-01"
    / "live_onager_min_range.json"
)
MATCHUPS = (
    "siege_onager_vs_champion",
    "siege_onager_vs_halberdier",
    "siege_onager_vs_paladin",
    "siege_onager_vs_elite_steppe",
    "siege_onager_vs_hussar",
    "siege_onager_vs_heavy_camel",
)

SNAP_RESEED = 400_000
F_ID, F_MASTER, F_OWNER, F_X, F_Y, F_HP, F_CUR_ACTION = 0, 1, 2, 3, 4, 12, 20
A_STATE, A_TARGET = 1, 2
ONAGER_MASTER = 588
MIN_RANGE = 3.0
MAX_RANGE = 9.0
ONAGER_OUTLINE = 0.5
TARGET_OUTLINE = {
    "siege_onager_vs_champion": 0.2,
    "siege_onager_vs_halberdier": 0.2,
    "siege_onager_vs_paladin": 0.4,
    "siege_onager_vs_elite_steppe": 0.4,
    "siege_onager_vs_hussar": 0.4,
    "siege_onager_vs_heavy_camel": 0.4,
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


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def round_or_none(value, digits=4):
    return None if value is None else round(value, digits)


def decode_run(matchup: str, repeat: int) -> dict:
    frames = (
        CAPTURE_ROOT / matchup / f"run_{repeat:03d}" / "raw recordings"
        / f"{matchup}.frames.bin"
    )
    doc = entities = world_id = None
    first_time = prior_time = None
    prior = {}
    target_before = {}
    auxiliary_first_targets = {}
    onager_first_targets = {}
    onager_first_attack_starts = {}
    pinned_samples = []
    target_switches_while_pinned = 0
    first_pinned_second = None
    first_melee_attack_on_onager_second = None
    action_histogram = Counter()

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
                    first_time = prior_time = None
                    prior = {}
                    target_before = {}
                    auxiliary_first_targets = {}
                    onager_first_targets = {}
                    onager_first_attack_starts = {}
                    pinned_samples = []
                    target_switches_while_pinned = 0
                    first_pinned_second = None
                    first_melee_attack_on_onager_second = None
                    action_histogram = Counter()
                    continue
                if entities is None:
                    continue
                if frame.patch:
                    D.apply_patch(doc, frame.patch, entities, world_id)
                if first_time is None:
                    first_time = frame.time
                second = (frame.time - first_time) / 1000.0
                units = {}
                for key, entity in merged(doc, entities, world_id):
                    owner = entity.get(F_OWNER)
                    hp = entity.get(F_HP)
                    if owner not in (2, 3, 4) or not finite(hp) or hp <= 0:
                        continue
                    if not finite(entity.get(F_X)) or not finite(entity.get(F_Y)):
                        continue
                    state, target_id = action(doc, entity)
                    units[key] = {
                        "key": key,
                        "id": entity.get(F_ID),
                        "master": entity.get(F_MASTER),
                        "owner": owner,
                        "x": float(entity.get(F_X)),
                        "y": float(entity.get(F_Y)),
                        "hp": float(hp),
                        "state": state,
                        "targetId": target_id,
                    }
                by_id = {
                    unit["id"]: unit for unit in units.values()
                    if isinstance(unit["id"], int)
                }
                onagers = [
                    unit for unit in units.values()
                    if unit["owner"] == 2 and unit["master"] == ONAGER_MASTER
                ]
                for actor in onagers:
                    target = by_id.get(actor["targetId"])
                    if (actor["id"] not in onager_first_targets
                            and target is not None and target["owner"] == 3):
                        onager_first_targets[actor["id"]] = {
                            "second": round(second, 6),
                            "actorId": actor["id"],
                            "actorX": round(actor["x"], 6),
                            "actorY": round(actor["y"], 6),
                            "targetId": target["id"],
                        }
                    previous = prior.get(actor["key"])
                    if (actor["id"] not in onager_first_attack_starts
                            and actor["state"] == 7
                            and (previous is None or previous["state"] != 7)):
                        onager_first_attack_starts[actor["id"]] = {
                            "second": round(second, 6),
                            "actorId": actor["id"],
                            "targetId": actor["targetId"],
                        }
                enemies = [unit for unit in units.values() if unit["owner"] == 3]
                for actor in enemies:
                    if actor["id"] in auxiliary_first_targets:
                        continue
                    target = by_id.get(actor["targetId"])
                    if target is not None and target["owner"] == 4:
                        auxiliary_first_targets[actor["id"]] = {
                            "second": round(second, 6),
                            "actorId": actor["id"],
                            "actorX": round(actor["x"], 6),
                            "actorY": round(actor["y"], 6),
                            "targetId": target["id"],
                            "targetX": round(target["x"], 6),
                            "targetY": round(target["y"], 6),
                        }
                onager_ids = {unit["id"] for unit in onagers}
                if first_melee_attack_on_onager_second is None:
                    for enemy in enemies:
                        if enemy["state"] == 7 and enemy["targetId"] in onager_ids:
                            first_melee_attack_on_onager_second = second
                            break
                dt = None if prior_time is None else (frame.time - prior_time) / 1000.0
                for actor in onagers:
                    action_histogram[str(actor["state"])] += 1
                    if not enemies:
                        continue
                    nearest = min(
                        enemies,
                        key=lambda enemy: math.hypot(
                            enemy["x"] - actor["x"], enemy["y"] - actor["y"]
                        ),
                    )
                    nearest_distance = math.hypot(
                        nearest["x"] - actor["x"], nearest["y"] - actor["y"]
                    )
                    if nearest_distance >= MIN_RANGE - 1e-9:
                        continue
                    if first_pinned_second is None:
                        first_pinned_second = second
                    previous = prior.get(actor["key"])
                    speed = 0.0
                    away_alignment = None
                    if previous and dt and dt > 0:
                        dx = actor["x"] - previous["x"]
                        dy = actor["y"] - previous["y"]
                        distance = math.hypot(dx, dy)
                        speed = distance / dt
                        if distance > 1e-9 and nearest_distance > 1e-9:
                            away_alignment = (
                                dx * (actor["x"] - nearest["x"])
                                + dy * (actor["y"] - nearest["y"])
                            ) / (distance * nearest_distance)
                    target = by_id.get(actor["targetId"])
                    target_distance = (
                        math.hypot(target["x"] - actor["x"], target["y"] - actor["y"])
                        if target else None
                    )
                    target_away_alignment = None
                    if (target and previous and dt and dt > 0):
                        move_x = actor["x"] - previous["x"]
                        move_y = actor["y"] - previous["y"]
                        move_distance = math.hypot(move_x, move_y)
                        if move_distance > 1e-9 and target_distance > 1e-9:
                            target_away_alignment = (
                                move_x * (actor["x"] - target["x"])
                                + move_y * (actor["y"] - target["y"])
                            ) / (move_distance * target_distance)
                    viable = sum(
                        MIN_RANGE - 1e-9 <= math.hypot(
                            enemy["x"] - actor["x"], enemy["y"] - actor["y"]
                        )
                        <= MAX_RANGE + 0.1 + ONAGER_OUTLINE + TARGET_OUTLINE[matchup]
                        for enemy in enemies
                    )
                    previous_target = target_before.get(actor["key"])
                    if (previous_target is not None
                            and actor["targetId"] != previous_target):
                        target_switches_while_pinned += 1
                    target_before[actor["key"]] = actor["targetId"]
                    pinned_samples.append({
                        "second": second,
                        "speed": speed,
                        "moving": speed > 0.05,
                        "awayAlignment": away_alignment,
                        "state": actor["state"],
                        "targetDistance": target_distance,
                        "targetAwayAlignment": target_away_alignment,
                        "viableTargets": viable,
                    })
                prior = {key: dict(unit) for key, unit in units.items()}
                prior_time = frame.time

    moving = [sample for sample in pinned_samples if sample["moving"]]
    alignments = [
        sample["awayAlignment"] for sample in moving
        if sample["awayAlignment"] is not None
    ]
    speeds = [sample["speed"] for sample in moving]
    with_alternative = [sample for sample in pinned_samples if sample["viableTargets"] > 0]
    firing = [sample for sample in pinned_samples if sample["state"] == 7]
    selected_pinned = [
        sample for sample in pinned_samples
        if sample["targetDistance"] is not None
        and sample["targetDistance"] < MIN_RANGE - 1e-9
    ]
    selected_shootable = [
        sample for sample in pinned_samples
        if sample["targetDistance"] is not None
        and MIN_RANGE - 1e-9 <= sample["targetDistance"]
        <= MAX_RANGE + 0.1 + ONAGER_OUTLINE + TARGET_OUTLINE[matchup]
    ]
    moving_selected_pinned = [sample for sample in selected_pinned if sample["moving"]]
    target_alignments = [
        sample["targetAwayAlignment"] for sample in moving_selected_pinned
        if sample["targetAwayAlignment"] is not None
    ]
    return {
        "repeat": repeat,
        "framesBin": str(frames.resolve()),
        "pinnedActorFrames": len(pinned_samples),
        "firstPinnedSecond": round_or_none(first_pinned_second, 3),
        "firstMeleeAttackOnOnagerSecond": round_or_none(
            first_melee_attack_on_onager_second, 3
        ),
        "movingShareWhilePinned": round_or_none(
            len(moving) / len(pinned_samples) if pinned_samples else None, 6
        ),
        "movingSpeed": {
            "p25": round_or_none(percentile(speeds, 0.25), 4),
            "median": round_or_none(percentile(speeds, 0.5), 4),
            "p75": round_or_none(percentile(speeds, 0.75), 4),
        },
        "awayAlignmentWhenMoving": {
            "p25": round_or_none(percentile(alignments, 0.25), 4),
            "median": round_or_none(percentile(alignments, 0.5), 4),
            "p75": round_or_none(percentile(alignments, 0.75), 4),
        },
        "shootableAlternativeShareWhilePinned": round_or_none(
            len(with_alternative) / len(pinned_samples) if pinned_samples else None, 6
        ),
        "firingShareWhilePinned": round_or_none(
            len(firing) / len(pinned_samples) if pinned_samples else None, 6
        ),
        "selectedTargetInsideMinRangeShare": round_or_none(
            len(selected_pinned) / len(pinned_samples) if pinned_samples else None, 6
        ),
        "selectedTargetShootableShare": round_or_none(
            len(selected_shootable) / len(pinned_samples) if pinned_samples else None, 6
        ),
        "movingShareWhenSelectedTargetPinned": round_or_none(
            len(moving_selected_pinned) / len(selected_pinned) if selected_pinned else None, 6
        ),
        "selectedTargetAwayAlignmentWhenMoving": {
            "p25": round_or_none(percentile(target_alignments, 0.25), 4),
            "median": round_or_none(percentile(target_alignments, 0.5), 4),
            "p75": round_or_none(percentile(target_alignments, 0.75), 4),
        },
        "targetSwitchesWhilePinned": target_switches_while_pinned,
        "auxiliaryOpeningTargets": {
            "actors": len(auxiliary_first_targets),
            "targetCounts": dict(Counter(
                str(row["targetId"])
                for row in auxiliary_first_targets.values()
            )),
            "details": sorted(
                auxiliary_first_targets.values(), key=lambda row: row["actorId"]
            ),
        },
        "onagerOpening": {
            "firstTargets": sorted(
                onager_first_targets.values(), key=lambda row: row["actorId"]
            ),
            "firstAttackStarts": sorted(
                onager_first_attack_starts.values(), key=lambda row: row["actorId"]
            ),
        },
        "actionStateHistogram": dict(sorted(action_histogram.items())),
    }


def main() -> None:
    rows = []
    for matchup in MATCHUPS:
        runs = [decode_run(matchup, repeat) for repeat in range(1, 6)]
        weighted_frames = sum(run["pinnedActorFrames"] for run in runs)
        rows.append({
            "matchup": matchup,
            "runs": runs,
            "aggregate": {
                "pinnedActorFrames": weighted_frames,
                "movingShareWhilePinned": round_or_none(
                    sum(
                        run["movingShareWhilePinned"] * run["pinnedActorFrames"]
                        for run in runs if run["movingShareWhilePinned"] is not None
                    ) / weighted_frames if weighted_frames else None,
                    6,
                ),
                "firingShareWhilePinned": round_or_none(
                    sum(
                        run["firingShareWhilePinned"] * run["pinnedActorFrames"]
                        for run in runs if run["firingShareWhilePinned"] is not None
                    ) / weighted_frames if weighted_frames else None,
                    6,
                ),
            },
        })
    report = {
        "schemaVersion": 1,
        "metric": (
            "Onager actor-frames with nearest principal melee centre inside "
            "the DAT 3.0-tile minimum range"
        ),
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
