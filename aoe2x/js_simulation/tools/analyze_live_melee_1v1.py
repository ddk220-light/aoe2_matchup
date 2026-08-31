"""Analyze a live CadeRemote melee 1v1 capture.

The input is the prefix passed to ``aoe2x/grpc/grpc_hp_log.py``.  The analyzer
decodes the length-prefixed ``FrameSequence`` stream, selects the segment with
one live combat entity on owners 2 and 3, and reports movement, attack, HP, and
axis-aligned collision-box geometry.

Collision half-extents are explicit command-line inputs.  They must come from
the live DAT or a sourced unit fixture; the analyzer never derives or tunes
them from the observed positions.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import statistics
import struct
import sys
import tempfile


SCRIPT = Path(__file__).resolve()
JS_SIMULATION = SCRIPT.parents[1]
REPO_ROOT = JS_SIMULATION.parents[1]
GRPC_DIR = REPO_ROOT / "aoe2x" / "grpc"
sys.path.insert(0, str(GRPC_DIR))

import cade_api_pb2 as pb  # noqa: E402
import decode_state_v2 as D  # noqa: E402


SNAP_RESEED = 400_000
ARMY_MODEL_TYPES = {9, 11, 12}
SCOUT_MASTER = 448

F_ID, F_MASTER, F_OWNER, F_X, F_Y = 0, 1, 2, 3, 4
F_STATE, F_HP, F_CUR_ACTION = 8, 12, 20
A_TYPE, A_STATE, A_TARGET, A_TARGET_2 = 0, 1, 2, 3
A_TARGET_X, A_TARGET_Y, A_TIMER = 4, 5, 12


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def action_of(doc, entity):
    ref = entity.get(F_CUR_ACTION)
    if not isinstance(ref, int):
        return {}
    model = doc.models.get(ref)
    if not model:
        return {}
    return {
        "action_model_type": model.get("__type__"),
        "action_type": model.get(A_TYPE),
        "action_state": model.get(A_STATE),
        "target_id": model.get(A_TARGET),
        "target_2_id": model.get(A_TARGET_2),
        "target_x": model.get(A_TARGET_X),
        "target_y": model.get(A_TARGET_Y),
        "action_timer": model.get(A_TIMER),
    }


def merged_entities(doc, entity_store, world_id):
    world_entities = doc.models.get(world_id, {}).get(1, {})
    merged = []
    for key, scalar_entity in entity_store.items():
        if scalar_entity.get("__type__") not in ARMY_MODEL_TYPES:
            continue
        owner = scalar_entity.get(F_OWNER)
        master = scalar_entity.get(F_MASTER)
        hp = scalar_entity.get(F_HP)
        if not isinstance(owner, int) or owner <= 0 or master == SCOUT_MASTER:
            continue
        if not finite(hp) or hp <= 0:
            continue
        doc_id = world_entities.get(key)
        entity = scalar_entity
        if isinstance(doc_id, int) and doc_id in doc.models:
            entity = {**doc.models[doc_id], **scalar_entity}
        if not finite(entity.get(F_X)) or not finite(entity.get(F_Y)):
            continue
        merged.append((key, entity))
    return merged


def seed_snapshot(patch):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp:
            temp.write(patch)
            temp_path = temp.name
        doc = D.Doc()
        entity_store = {}
        _, world_id = D.seed_from_snapshot(temp_path, doc, entity_store)
        return doc, entity_store, world_id
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def decode(prefix, expected_masters, player_owners):
    path = Path(f"{prefix}.frames.bin")
    segments = []
    current = None
    sequence_count = 0
    frame_count = 0
    full_snapshots = 0
    incomplete_tail_bytes = 0
    incomplete_tail_declared_payload_bytes = None
    incomplete_tail_payload_bytes = 0
    kills = []
    observed_candidates = {}
    doc = entity_store = world_id = None

    def begin_segment(patch):
        nonlocal doc, entity_store, world_id, current, full_snapshots
        doc, entity_store, world_id = seed_snapshot(patch)
        full_snapshots += 1
        current = {"index": len(segments), "rows": []}
        segments.append(current)

    with path.open("rb") as stream:
        while True:
            header = stream.read(4)
            if not header:
                break
            if len(header) != 4:
                incomplete_tail_bytes = len(header)
                break
            (length,) = struct.unpack("<I", header)
            payload = stream.read(length)
            if len(payload) != length:
                incomplete_tail_bytes = 4 + len(payload)
                incomplete_tail_declared_payload_bytes = length
                incomplete_tail_payload_bytes = len(payload)
                break
            sequence_count += 1
            sequence = pb.FrameSequence()
            sequence.ParseFromString(payload)
            for frame in sequence.frame:
                frame_count += 1
                patch = frame.patch
                if patch and len(patch) > SNAP_RESEED:
                    begin_segment(patch)
                    continue
                if entity_store is None:
                    continue
                if patch:
                    D.apply_patch(doc, patch, entity_store, world_id)

                candidates = merged_entities(doc, entity_store, world_id)
                for key, entity in candidates:
                    actual_owner = entity.get(F_OWNER)
                    owner_candidates = observed_candidates.setdefault(actual_owner, {})
                    signature = (key, entity.get(F_MASTER))
                    owner_candidates[signature] = {
                        "key": key,
                        "id": entity.get(F_ID),
                        "master": entity.get(F_MASTER),
                        "maximum_hp": max(
                            entity.get(F_HP),
                            owner_candidates.get(signature, {}).get("maximum_hp", 0),
                        ),
                    }
                per_owner = {
                    owner: [(key, entity) for key, entity in candidates
                            if entity.get(F_OWNER) == player_owners[owner]]
                    for owner in (2, 3)
                }
                for owner in (2, 3):
                    expected_master = expected_masters.get(owner)
                    if expected_master is not None:
                        per_owner[owner] = [
                            pair for pair in per_owner[owner]
                            if pair[1].get(F_MASTER) == expected_master
                        ]
                if len(per_owner[2]) == 1 and len(per_owner[3]) == 1:
                    units = {}
                    for owner in (2, 3):
                        key, entity = per_owner[owner][0]
                        units[owner] = {
                            "key": key,
                            "id": entity.get(F_ID),
                            "master": entity.get(F_MASTER),
                            "owner": player_owners[owner],
                            "x": entity.get(F_X),
                            "y": entity.get(F_Y),
                            "hp": entity.get(F_HP),
                            "entity_state": entity.get(F_STATE),
                            **action_of(doc, entity),
                        }
                    current["rows"].append({"t_ms": frame.time, "units": units})

                for event in frame.event:
                    if event.HasField("entityKilled"):
                        kills.append({
                            "t_ms": frame.time,
                            "id": event.entityKilled.id,
                            "killer_id": event.entityKilled.killerId,
                        })
                        entity_store.pop(event.entityKilled.id, None)

    usable = [segment for segment in segments if segment["rows"]]
    if not usable:
        summary = {
            owner: sorted(candidates.values(), key=lambda item: (item["master"], item["key"]))
            for owner, candidates in observed_candidates.items()
        }
        raise RuntimeError(
            "capture contains no segment with exactly one selected live unit per side; "
            f"observed candidates: {json.dumps(summary, sort_keys=True)}"
        )
    selected = max(usable, key=lambda segment: len(segment["rows"]))
    return {
        "path": path,
        "sequence_count": sequence_count,
        "frame_count": frame_count,
        "full_snapshots": full_snapshots,
        "incomplete_tail_bytes": incomplete_tail_bytes,
        "incomplete_tail_declared_payload_bytes": incomplete_tail_declared_payload_bytes,
        "incomplete_tail_payload_bytes": incomplete_tail_payload_bytes,
        "segments": len(segments),
        "selected_segment": selected["index"],
        "rows": selected["rows"],
        "kills": kills,
    }


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_unit(rows, owner):
    speeds = []
    movement_steps = []
    attack_starts = []
    damage_events = []
    acquisition_time = None
    prior = None
    other_key = rows[0]["units"][3 if owner == 2 else 2]["key"]
    for row in rows:
        unit = row["units"][owner]
        if acquisition_time is None and unit.get("target_id") == other_key:
            acquisition_time = row["t_ms"]
        if unit.get("action_state") == 7 and prior is not None \
                and prior.get("action_state") != 7:
            attack_starts.append(row["t_ms"])
        if prior is not None:
            dt = (row["t_ms"] - prior["t_ms"]) / 1000
            distance = math.hypot(unit["x"] - prior["x"], unit["y"] - prior["y"])
            if dt > 0 and distance > 0:
                speeds.append(distance / dt)
                movement_steps.append({"t_ms": row["t_ms"], "distance": distance})
            if finite(prior.get("hp")) and finite(unit.get("hp")) \
                    and unit["hp"] < prior["hp"]:
                damage_events.append({
                    "t_ms": row["t_ms"],
                    "hp_before": prior["hp"],
                    "hp_after": unit["hp"],
                    "damage": prior["hp"] - unit["hp"],
                })
        prior = {"t_ms": row["t_ms"], **unit}
    first = rows[0]["units"][owner]
    first_attack_time = attack_starts[0] if attack_starts else None
    movement_before_first_attack = sum(
        step["distance"] for step in movement_steps
        if first_attack_time is not None and step["t_ms"] <= first_attack_time
    )
    total_movement = sum(step["distance"] for step in movement_steps)
    return {
        "key": first["key"],
        "id": first["id"],
        "master": first["master"],
        "owner": first["owner"],
        "initial_hp": max(row["units"][owner]["hp"] for row in rows),
        "final_observed_hp": rows[-1]["units"][owner]["hp"],
        "target_acquired_t_ms": acquisition_time,
        "first_attack_start_t_ms": first_attack_time,
        "attack_start_times_ms": attack_starts,
        "damage_events": damage_events,
        "moving_speed_tiles_per_second": {
            "samples": len(speeds),
            "median": statistics.median(speeds) if speeds else None,
            "p05": percentile(speeds, 0.05),
            "p95": percentile(speeds, 0.95),
        },
        "movement_distance_tiles": {
            "before_first_attack": movement_before_first_attack,
            "after_first_attack": total_movement - movement_before_first_attack,
            "total": total_movement,
        },
    }


def geometry(rows, extents, outlines):
    samples = []
    overlap_windows = []
    circular_overlap_windows = []
    outline_overlap_windows = []
    active_window = None
    circular_active_window = None
    outline_active_window = None
    attack_start_geometry = []
    prior_states = None
    for row in rows:
        left = row["units"][2]
        right = row["units"][3]
        dx = right["x"] - left["x"]
        dy = right["y"] - left["y"]
        gap_x = abs(dx) - extents["combined_x"]
        gap_y = abs(dy) - extents["combined_y"]
        signed_box_gap = max(gap_x, gap_y)
        center_distance = math.hypot(dx, dy)
        signed_circular_gap = center_distance - extents["combined_radius"]
        outline_gap_x = abs(dx) - outlines["combined_x"]
        outline_gap_y = abs(dy) - outlines["combined_y"]
        signed_outline_gap = max(outline_gap_x, outline_gap_y)
        sample = {
            "t_ms": row["t_ms"],
            "dx": dx,
            "dy": dy,
            "euclidean_center_distance": center_distance,
            "gap_x": gap_x,
            "gap_y": gap_y,
            "signed_box_gap": signed_box_gap,
            "penetration_depth": max(0, -signed_box_gap),
            "signed_circular_gap": signed_circular_gap,
            "circular_penetration_depth": max(0, -signed_circular_gap),
            "outline_gap_x": outline_gap_x,
            "outline_gap_y": outline_gap_y,
            "signed_outline_gap": signed_outline_gap,
            "outline_penetration_depth": max(0, -signed_outline_gap),
        }
        samples.append(sample)
        overlapping = signed_box_gap < -1e-12
        if overlapping and active_window is None:
            active_window = {"start_t_ms": row["t_ms"], "end_t_ms": row["t_ms"]}
        elif overlapping:
            active_window["end_t_ms"] = row["t_ms"]
        elif active_window is not None:
            active_window["duration_ms"] = (
                active_window["end_t_ms"] - active_window["start_t_ms"]
            )
            overlap_windows.append(active_window)
            active_window = None

        circular_overlapping = signed_circular_gap < -1e-12
        if circular_overlapping and circular_active_window is None:
            circular_active_window = {
                "start_t_ms": row["t_ms"],
                "end_t_ms": row["t_ms"],
            }
        elif circular_overlapping:
            circular_active_window["end_t_ms"] = row["t_ms"]
        elif circular_active_window is not None:
            circular_active_window["duration_ms"] = (
                circular_active_window["end_t_ms"]
                - circular_active_window["start_t_ms"]
            )
            circular_overlap_windows.append(circular_active_window)
            circular_active_window = None

        outline_overlapping = signed_outline_gap < -1e-12
        if outline_overlapping and outline_active_window is None:
            outline_active_window = {
                "start_t_ms": row["t_ms"],
                "end_t_ms": row["t_ms"],
            }
        elif outline_overlapping:
            outline_active_window["end_t_ms"] = row["t_ms"]
        elif outline_active_window is not None:
            outline_active_window["duration_ms"] = (
                outline_active_window["end_t_ms"]
                - outline_active_window["start_t_ms"]
            )
            outline_overlap_windows.append(outline_active_window)
            outline_active_window = None

        states = {owner: row["units"][owner].get("action_state") for owner in (2, 3)}
        for owner in (2, 3):
            if states[owner] == 7 and prior_states is not None and prior_states[owner] != 7:
                attack_start_geometry.append({"owner": owner, **sample})
        prior_states = states

    if active_window is not None:
        active_window["duration_ms"] = active_window["end_t_ms"] - active_window["start_t_ms"]
        overlap_windows.append(active_window)
    if circular_active_window is not None:
        circular_active_window["duration_ms"] = (
            circular_active_window["end_t_ms"]
            - circular_active_window["start_t_ms"]
        )
        circular_overlap_windows.append(circular_active_window)
    if outline_active_window is not None:
        outline_active_window["duration_ms"] = (
            outline_active_window["end_t_ms"] - outline_active_window["start_t_ms"]
        )
        outline_overlap_windows.append(outline_active_window)

    closest = min(samples, key=lambda sample: (
        sample["signed_box_gap"], sample["euclidean_center_distance"], sample["t_ms"]
    ))
    min_euclidean = min(samples, key=lambda sample: (
        sample["euclidean_center_distance"], sample["t_ms"]
    ))
    overlapping = [sample for sample in samples if sample["penetration_depth"] > 0]
    circular_overlapping = [
        sample for sample in samples
        if sample["circular_penetration_depth"] > 0
    ]
    outline_overlapping = [
        sample for sample in samples if sample["outline_penetration_depth"] > 0
    ]
    return {
        "first_observed": samples[0],
        "last_observed": samples[-1],
        "closest_box_approach": closest,
        "minimum_euclidean_approach": min_euclidean,
        "overlap": {
            "observed": bool(overlapping),
            "frames": len(overlapping),
            "frame_share": len(overlapping) / len(samples),
            "first_t_ms": overlapping[0]["t_ms"] if overlapping else None,
            "last_t_ms": overlapping[-1]["t_ms"] if overlapping else None,
            "maximum_penetration_depth": max(
                (sample["penetration_depth"] for sample in overlapping), default=0
            ),
            "windows": overlap_windows,
            "total_window_duration_ms": sum(
                window["duration_ms"] for window in overlap_windows
            ),
        },
        "circular_overlap": {
            "observed": bool(circular_overlapping),
            "frames": len(circular_overlapping),
            "frame_share": len(circular_overlapping) / len(samples),
            "first_t_ms": circular_overlapping[0]["t_ms"]
            if circular_overlapping else None,
            "last_t_ms": circular_overlapping[-1]["t_ms"]
            if circular_overlapping else None,
            "maximum_penetration_depth": max(
                (
                    sample["circular_penetration_depth"]
                    for sample in circular_overlapping
                ),
                default=0,
            ),
            "windows": circular_overlap_windows,
            "total_window_duration_ms": sum(
                window["duration_ms"] for window in circular_overlap_windows
            ),
        },
        "outline_overlap": {
            "observed": bool(outline_overlapping),
            "frames": len(outline_overlapping),
            "frame_share": len(outline_overlapping) / len(samples),
            "first_t_ms": outline_overlapping[0]["t_ms"]
            if outline_overlapping else None,
            "last_t_ms": outline_overlapping[-1]["t_ms"]
            if outline_overlapping else None,
            "maximum_penetration_depth": max(
                (
                    sample["outline_penetration_depth"]
                    for sample in outline_overlapping
                ),
                default=0,
            ),
            "windows": outline_overlap_windows,
            "total_window_duration_ms": sum(
                window["duration_ms"] for window in outline_overlap_windows
            ),
        },
        "attack_start_geometry": attack_start_geometry,
    }


def require_extent(value, name):
    if not finite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", help="capture prefix, without .frames.bin")
    parser.add_argument("--owner-2-half-x", type=float, required=True)
    parser.add_argument("--owner-2-half-y", type=float, required=True)
    parser.add_argument("--owner-3-half-x", type=float, required=True)
    parser.add_argument("--owner-3-half-y", type=float, required=True)
    parser.add_argument("--owner-2-radius", type=float)
    parser.add_argument("--owner-3-radius", type=float)
    parser.add_argument("--owner-2-outline-half-x", type=float)
    parser.add_argument("--owner-2-outline-half-y", type=float)
    parser.add_argument("--owner-3-outline-half-x", type=float)
    parser.add_argument("--owner-3-outline-half-y", type=float)
    parser.add_argument("--owner-2-master", type=int)
    parser.add_argument("--owner-3-master", type=int)
    parser.add_argument("--owner-2-player", type=int, default=2)
    parser.add_argument("--owner-3-player", type=int, default=3)
    parser.add_argument("--output", help="default: <prefix>.analysis.json")
    args = parser.parse_args()

    extents = {
        "owner_2": {
            "x": require_extent(args.owner_2_half_x, "owner 2 half-width"),
            "y": require_extent(args.owner_2_half_y, "owner 2 half-height"),
        },
        "owner_3": {
            "x": require_extent(args.owner_3_half_x, "owner 3 half-width"),
            "y": require_extent(args.owner_3_half_y, "owner 3 half-height"),
        },
    }
    extents["combined_x"] = extents["owner_2"]["x"] + extents["owner_3"]["x"]
    extents["combined_y"] = extents["owner_2"]["y"] + extents["owner_3"]["y"]
    owner_2_radius = args.owner_2_radius or extents["owner_2"]["x"]
    owner_3_radius = args.owner_3_radius or extents["owner_3"]["x"]
    extents["owner_2"]["radius"] = require_extent(
        owner_2_radius, "owner 2 radius"
    )
    extents["owner_3"]["radius"] = require_extent(
        owner_3_radius, "owner 3 radius"
    )
    extents["combined_radius"] = owner_2_radius + owner_3_radius
    outlines = {
        "owner_2": {
            "x": require_extent(
                args.owner_2_outline_half_x or extents["owner_2"]["x"],
                "owner 2 outline half-width",
            ),
            "y": require_extent(
                args.owner_2_outline_half_y or extents["owner_2"]["y"],
                "owner 2 outline half-height",
            ),
        },
        "owner_3": {
            "x": require_extent(
                args.owner_3_outline_half_x or extents["owner_3"]["x"],
                "owner 3 outline half-width",
            ),
            "y": require_extent(
                args.owner_3_outline_half_y or extents["owner_3"]["y"],
                "owner 3 outline half-height",
            ),
        },
    }
    outlines["combined_x"] = outlines["owner_2"]["x"] + outlines["owner_3"]["x"]
    outlines["combined_y"] = outlines["owner_2"]["y"] + outlines["owner_3"]["y"]

    decoded = decode(
        args.prefix,
        {2: args.owner_2_master, 3: args.owner_3_master},
        {2: args.owner_2_player, 3: args.owner_3_player},
    )
    rows = decoded.pop("rows")
    result = {
        "schema_version": 1,
        "capture_prefix": args.prefix,
        "capture_validation": {
            "frames_bin_bytes": decoded["path"].stat().st_size,
            "complete_frame_sequences": decoded["sequence_count"],
            "frames": decoded["frame_count"],
            "full_snapshots": decoded["full_snapshots"],
            "segments": decoded["segments"],
            "selected_segment": decoded["selected_segment"],
            "selected_pair_frames": len(rows),
            "t_ms_min": rows[0]["t_ms"],
            "t_ms_max": rows[-1]["t_ms"],
            "game_time_span_seconds": (rows[-1]["t_ms"] - rows[0]["t_ms"]) / 1000,
            "incomplete_tail_bytes": decoded["incomplete_tail_bytes"],
            "incomplete_tail_declared_payload_bytes": decoded[
                "incomplete_tail_declared_payload_bytes"
            ],
            "incomplete_tail_payload_bytes": decoded[
                "incomplete_tail_payload_bytes"
            ],
        },
        "collision_half_extents": extents,
        "outline_half_extents": outlines,
        "selected_player_owners": {
            "owner_2_slot": args.owner_2_player,
            "owner_3_slot": args.owner_3_player,
        },
        "combatants": {
            "owner_2": summarize_unit(rows, 2),
            "owner_3": summarize_unit(rows, 3),
        },
        "geometry": geometry(rows, extents, outlines),
        "kills": decoded["kills"],
    }
    output = Path(args.output or f"{args.prefix}.analysis.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
