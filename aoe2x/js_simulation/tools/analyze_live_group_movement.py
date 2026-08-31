"""Analyze a live CadeRemote capture of a player-issued group movement test.

The input is the prefix passed to ``aoe2x/grpc/grpc_hp_log.py``. The analyzer
selects the largest same-owner/same-master combat cohort (or the cohort matching
``--expected-count``), reconstructs every position and action destination, and
reports move-order episodes, per-unit motion, and formation geometry.
"""

from __future__ import annotations

import argparse
import bisect
from collections import Counter, defaultdict
import hashlib
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


def distribution(values):
    values = [value for value in values if finite(value)]
    return {
        "samples": len(values),
        "minimum": min(values) if values else None,
        "p05": percentile(values, 0.05),
        "median": statistics.median(values) if values else None,
        "p95": percentile(values, 0.95),
        "maximum": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def action_of(doc, entity):
    ref = entity.get(F_CUR_ACTION)
    if not isinstance(ref, int):
        return {
            "action_model_type": None,
            "action_type": None,
            "action_state": None,
            "target_id": None,
            "target_2_id": None,
            "target_x": None,
            "target_y": None,
            "action_timer": None,
            "action_ref": None,
            "action_raw_scalar_fields": None,
        }
    model = doc.models.get(ref)
    if not model:
        return {
            "action_model_type": None,
            "action_type": None,
            "action_state": None,
            "target_id": None,
            "target_2_id": None,
            "target_x": None,
            "target_y": None,
            "action_timer": None,
            "action_ref": ref,
            "action_raw_scalar_fields": None,
        }
    return {
        "action_model_type": model.get("__type__"),
        "action_type": model.get(A_TYPE),
        "action_state": model.get(A_STATE),
        "target_id": model.get(A_TARGET),
        "target_2_id": model.get(A_TARGET_2),
        "target_x": model.get(A_TARGET_X),
        "target_y": model.get(A_TARGET_Y),
        "action_timer": model.get(A_TIMER),
        "action_ref": ref,
        "action_raw_scalar_fields": {
            str(key): value
            for key, value in model.items()
            if isinstance(value, (type(None), bool, int, float, str))
        },
    }


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


def candidate_entities(doc, entity_store, world_id):
    world_entities = doc.models.get(world_id, {}).get(1, {})
    candidates = []
    for key, scalar_entity in entity_store.items():
        if scalar_entity.get("__type__") not in ARMY_MODEL_TYPES:
            continue
        owner = scalar_entity.get(F_OWNER)
        master = scalar_entity.get(F_MASTER)
        hp = scalar_entity.get(F_HP)
        if (
            not isinstance(owner, int)
            or owner <= 0
            or master == SCOUT_MASTER
            or not finite(hp)
            or hp <= 1
        ):
            continue
        doc_id = world_entities.get(key)
        entity = scalar_entity
        if isinstance(doc_id, int) and doc_id in doc.models:
            entity = {**doc.models[doc_id], **scalar_entity}
        if not finite(entity.get(F_X)) or not finite(entity.get(F_Y)):
            continue
        candidates.append((key, entity))
    return candidates


def unit_row(doc, key, entity):
    return {
        "key": key,
        "id": entity.get(F_ID),
        "master": entity.get(F_MASTER),
        "owner": entity.get(F_OWNER),
        "x": entity.get(F_X),
        "y": entity.get(F_Y),
        "hp": entity.get(F_HP),
        "entity_state": entity.get(F_STATE),
        **action_of(doc, entity),
    }


def decode(prefix, expected_count):
    path = Path(f"{prefix}.frames.bin")
    sequence_count = 0
    frame_count = 0
    full_snapshots = 0
    incomplete_tail_bytes = 0
    incomplete_tail_declared_payload_bytes = None
    incomplete_tail_payload_bytes = 0
    segments = []
    commands = []
    current = None
    doc = entity_store = world_id = None

    def begin_segment(patch):
        nonlocal doc, entity_store, world_id, current, full_snapshots
        doc, entity_store, world_id = seed_snapshot(patch)
        full_snapshots += 1
        current = {"index": len(segments), "frames": [], "peak_groups": Counter()}
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
                for command in frame.command:
                    kind = command.WhichOneof("command")
                    if kind == "move":
                        move = command.move
                        commands.append({
                            "t_ms": frame.time,
                            "kind": kind,
                            "comm_player_id": move.commPlayerId,
                            "target_id": move.targetId,
                            "location": {
                                "x": move.location.x,
                                "y": move.location.y,
                            },
                            "extend": move.extend,
                            "instant": move.instant,
                            "human_order": move.humanOrder,
                            "control_held": move.controlHeld,
                            "unit_ids": list(move.unitIds),
                        })
                    elif kind == "interact":
                        interact = command.interact
                        commands.append({
                            "t_ms": frame.time,
                            "kind": kind,
                            "comm_player_id": interact.commPlayerId,
                            "target_id": interact.targetId,
                            "location": {
                                "x": interact.location.x,
                                "y": interact.location.y,
                            },
                            "extend": interact.extend,
                            "instant": interact.instant,
                            "human_order": interact.humanOrder,
                            "control_held": interact.controlHeld,
                            "unit_ids": list(interact.unitIds),
                        })
                    else:
                        commands.append({"t_ms": frame.time, "kind": kind})
                patch = frame.patch
                if patch and len(patch) > SNAP_RESEED:
                    begin_segment(patch)
                    continue
                if entity_store is None:
                    continue
                if patch:
                    D.apply_patch(doc, patch, entity_store, world_id)
                candidates = candidate_entities(doc, entity_store, world_id)
                groups = defaultdict(list)
                for key, entity in candidates:
                    groups[(entity.get(F_OWNER), entity.get(F_MASTER))].append(
                        unit_row(doc, key, entity)
                    )
                if current is not None:
                    for group, units in groups.items():
                        current["peak_groups"][group] = max(
                            current["peak_groups"][group], len(units)
                        )
                    current["frames"].append({
                        "t_ms": frame.time,
                        "groups": dict(groups),
                    })

    choices = []
    for segment in segments:
        for group, peak in segment["peak_groups"].items():
            matching_frames = sum(
                1 for frame in segment["frames"]
                if len(frame["groups"].get(group, [])) == peak
            )
            choices.append({
                "segment": segment,
                "group": group,
                "peak": peak,
                "matching_frames": matching_frames,
            })
    if not choices:
        raise RuntimeError("capture contains no live combat-unit cohort")
    exact = [choice for choice in choices if choice["peak"] == expected_count]
    selected = max(
        exact or choices,
        key=lambda choice: (choice["peak"], choice["matching_frames"]),
    )
    owner, master = selected["group"]
    cohort_frames = []
    keys = None
    for frame in selected["segment"]["frames"]:
        units = frame["groups"].get(selected["group"], [])
        if len(units) != selected["peak"]:
            continue
        frame_keys = {unit["key"] for unit in units}
        if keys is None:
            keys = frame_keys
        if frame_keys != keys:
            continue
        cohort_frames.append({
            "t_ms": frame["t_ms"],
            "units": {unit["key"]: unit for unit in units},
            "context_units": {
                unit["key"]: unit
                for group, context_units in frame["groups"].items()
                if group != selected["group"]
                for unit in context_units
            },
        })
    if len(cohort_frames) < 2:
        raise RuntimeError("selected cohort has fewer than two complete frames")
    return {
        "path": path,
        "sequence_count": sequence_count,
        "frame_count": frame_count,
        "full_snapshots": full_snapshots,
        "segments": len(segments),
        "selected_segment": selected["segment"]["index"],
        "selected_owner": owner,
        "selected_master": master,
        "selected_count": selected["peak"],
        "candidate_groups": [
            {
                "segment": choice["segment"]["index"],
                "owner": choice["group"][0],
                "master": choice["group"][1],
                "peak_count": choice["peak"],
                "matching_frames": choice["matching_frames"],
            }
            for choice in sorted(
                choices,
                key=lambda item: (-item["peak"], item["group"]),
            )
        ],
        "rows": cohort_frames,
        "commands": commands,
        "incomplete_tail_bytes": incomplete_tail_bytes,
        "incomplete_tail_declared_payload_bytes": incomplete_tail_declared_payload_bytes,
        "incomplete_tail_payload_bytes": incomplete_tail_payload_bytes,
    }


def formation_metrics(units):
    points = [(unit["x"], unit["y"]) for unit in units.values()]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    cx = statistics.fmean(xs)
    cy = statistics.fmean(ys)
    radii = [math.hypot(x - cx, y - cy) for x, y in points]
    nearest = []
    for index, (x, y) in enumerate(points):
        nearest.append(min(
            math.hypot(x - ox, y - oy)
            for other_index, (ox, oy) in enumerate(points)
            if other_index != index
        ))
    cov_xx = statistics.fmean((x - cx) ** 2 for x in xs)
    cov_yy = statistics.fmean((y - cy) ** 2 for y in ys)
    cov_xy = statistics.fmean(
        (x - cx) * (y - cy) for x, y in points
    )
    orientation = math.degrees(0.5 * math.atan2(2 * cov_xy, cov_xx - cov_yy))
    if orientation < 0:
        orientation += 180
    return {
        "centroid": {"x": cx, "y": cy},
        "bounds": {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        },
        "radius_tiles": distribution(radii),
        "nearest_neighbor_tiles": distribution(nearest),
        "principal_axis_degrees_mod_180": orientation,
    }


def destination_summary(units):
    destinations = {
        key: (unit.get("target_x"), unit.get("target_y"))
        for key, unit in units.items()
        if (
            finite(unit.get("target_x"))
            and finite(unit.get("target_y"))
            and (unit.get("target_x"), unit.get("target_y")) != (-1, -1)
        )
    }
    if not destinations:
        return None
    xs = [point[0] for point in destinations.values()]
    ys = [point[1] for point in destinations.values()]
    return {
        "count": len(destinations),
        "center_x": statistics.fmean(xs),
        "center_y": statistics.fmean(ys),
        "points": destinations,
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def movement_trace(rows):
    trace = []
    unit_speed_samples = defaultdict(list)
    action_state_counts = Counter()
    action_type_counts = Counter()
    action_model_samples = {}
    previous = None
    for row in rows:
        formation = formation_metrics(row["units"])
        destination = destination_summary(row["units"])
        moved = {}
        if previous is not None:
            dt = (row["t_ms"] - previous["t_ms"]) / 1000
            for key, unit in row["units"].items():
                prior = previous["units"][key]
                distance = math.hypot(unit["x"] - prior["x"], unit["y"] - prior["y"])
                if distance > 1e-9:
                    moved[key] = distance
                    if dt > 0:
                        unit_speed_samples[key].append(distance / dt)
        for unit in row["units"].values():
            action_state_counts[str(unit.get("action_state"))] += 1
            action_type_counts[str(unit.get("action_type"))] += 1
            raw = unit.get("action_raw_scalar_fields")
            if raw:
                signature = json.dumps(raw, sort_keys=True)
                action_model_samples.setdefault(signature, {
                    "first_t_ms": row["t_ms"],
                    "entity_id": unit["id"],
                    "fields": raw,
                })
        trace.append({
            "t_ms": row["t_ms"],
            "units": row["units"],
            "context_units": row.get("context_units", {}),
            "formation": formation,
            "destination": destination,
            "moving_keys": list(moved),
            "step_distances": moved,
        })
        previous = row
    return (
        trace,
        unit_speed_samples,
        action_state_counts,
        action_type_counts,
        list(action_model_samples.values())[:100],
    )


def detect_destination_events(trace, cohort_count):
    events = []
    prior_points = {}
    minimum_changed = max(2, math.ceil(cohort_count * 0.5))
    for row in trace:
        destination = row["destination"]
        if not destination or destination["count"] < minimum_changed:
            continue
        points = destination["points"]
        changed = []
        for key, point in points.items():
            prior = prior_points.get(key)
            if prior is None or math.hypot(point[0] - prior[0], point[1] - prior[1]) > 0.05:
                changed.append(key)
        if len(changed) >= minimum_changed:
            event = {
                "t_ms": row["t_ms"],
                "changed_units": len(changed),
                "destination_units": destination["count"],
                "destination_center": {
                    "x": destination["center_x"],
                    "y": destination["center_y"],
                },
                "destination_bounds": {
                    "width": destination["width"],
                    "height": destination["height"],
                },
                "destinations": {
                    str(key): {"x": point[0], "y": point[1]}
                    for key, point in points.items()
                },
            }
            if events and event["t_ms"] - events[-1]["t_ms"] <= 150:
                events[-1] = event
            else:
                events.append(event)
        prior_points.update(points)
    return events


def detect_active_windows(trace, cohort_count):
    threshold = max(1, math.ceil(cohort_count * 0.05))
    active_indices = [
        index for index, row in enumerate(trace)
        if len(row["moving_keys"]) >= threshold
    ]
    if not active_indices:
        return []
    windows = []
    start = prior = active_indices[0]
    for index in active_indices[1:]:
        if trace[index]["t_ms"] - trace[prior]["t_ms"] > 300:
            windows.append((start, prior))
            start = index
        prior = index
    windows.append((start, prior))
    return [window for window in windows if (
        trace[window[1]]["t_ms"] - trace[window[0]]["t_ms"] >= 100
    )]


def summarize_episode(trace, start_index, end_index, event=None):
    start_index = max(0, start_index - 1)
    start = trace[start_index]
    end = trace[end_index]
    keys = sorted(start["units"])
    paths = {key: 0.0 for key in keys}
    speed_samples = []
    heading_cosines = []
    last_move_t = {key: None for key in keys}
    destination_points = event.get("destinations", {}) if event else {}
    for index in range(start_index + 1, end_index + 1):
        row = trace[index]
        previous = trace[index - 1]
        dt = (row["t_ms"] - previous["t_ms"]) / 1000
        for key in keys:
            unit = row["units"][key]
            prior = previous["units"][key]
            vx = unit["x"] - prior["x"]
            vy = unit["y"] - prior["y"]
            distance = math.hypot(vx, vy)
            paths[key] += distance
            if distance <= 1e-9:
                continue
            last_move_t[key] = row["t_ms"]
            if dt > 0:
                speed_samples.append(distance / dt)
            destination = destination_points.get(str(key))
            if destination:
                tx = destination["x"] - prior["x"]
                ty = destination["y"] - prior["y"]
                target_distance = math.hypot(tx, ty)
                if target_distance > 1e-9:
                    heading_cosines.append(
                        (vx * tx + vy * ty) / (distance * target_distance)
                    )
    displacements = {}
    straightness = []
    final_destination_error = []
    for key in keys:
        first = start["units"][key]
        last = end["units"][key]
        displacement = math.hypot(last["x"] - first["x"], last["y"] - first["y"])
        displacements[key] = displacement
        if paths[key] > 1e-9:
            straightness.append(displacement / paths[key])
        destination = destination_points.get(str(key))
        if destination:
            final_destination_error.append(math.hypot(
                last["x"] - destination["x"],
                last["y"] - destination["y"],
            ))
    start_centroid = start["formation"]["centroid"]
    end_centroid = end["formation"]["centroid"]
    centroid_displacement = math.hypot(
        end_centroid["x"] - start_centroid["x"],
        end_centroid["y"] - start_centroid["y"],
    )
    arrivals = [value for value in last_move_t.values() if value is not None]
    return {
        "start_t_ms": start["t_ms"],
        "last_motion_t_ms": end["t_ms"],
        "duration_seconds": (end["t_ms"] - start["t_ms"]) / 1000,
        "destination_event": event,
        "centroid_displacement_tiles": centroid_displacement,
        "start_formation": start["formation"],
        "end_formation": end["formation"],
        "unit_path_distance_tiles": distribution(list(paths.values())),
        "unit_net_displacement_tiles": distribution(list(displacements.values())),
        "unit_path_straightness": distribution(straightness),
        "moving_speed_tiles_per_second": distribution(speed_samples),
        "heading_cosine_to_assigned_destination": distribution(heading_cosines),
        "final_assigned_destination_error_tiles": distribution(final_destination_error),
        "arrival_last_motion_t_ms": distribution(arrivals),
        "arrival_spread_ms": max(arrivals) - min(arrivals) if arrivals else None,
    }


def match_events_to_windows(trace, events, windows):
    episodes = []
    for start, end in windows:
        start_t = trace[start]["t_ms"]
        event = None
        eligible = [candidate for candidate in events if candidate["t_ms"] <= start_t + 250]
        if eligible:
            event = max(eligible, key=lambda candidate: candidate["t_ms"])
        episodes.append(summarize_episode(trace, start, end, event))
    return episodes


def compact_formation(formation):
    return {
        "centroid": formation["centroid"],
        "width": formation["bounds"]["width"],
        "height": formation["bounds"]["height"],
        "median_radius": formation["radius_tiles"]["median"],
        "median_nearest_neighbor": formation["nearest_neighbor_tiles"]["median"],
        "principal_axis_degrees_mod_180": formation[
            "principal_axis_degrees_mod_180"
        ],
    }


def vector_cosine(ax, ay, bx, by):
    left = math.hypot(ax, ay)
    right = math.hypot(bx, by)
    if left <= 1e-12 or right <= 1e-12:
        return None
    return (ax * bx + ay * by) / (left * right)


def analyze_move_commands(trace, commands, cohort_keys):
    minimum_selected = max(2, math.ceil(len(cohort_keys) * 0.5))
    relevant_commands = [
        command for command in commands
        if command["kind"] in {"move", "interact"}
        and len(set(command.get("unit_ids", ())) & cohort_keys) >= minimum_selected
    ]
    moves = [command for command in relevant_commands if command["kind"] == "move"]
    times = [row["t_ms"] for row in trace]
    records = []
    all_heading_cosines = []
    all_speeds = []
    all_progress_steps = []
    for move_index, command in enumerate(moves):
        command_t = command["t_ms"]
        later_commands = [
            candidate for candidate in relevant_commands
            if candidate["t_ms"] > command_t
        ]
        next_command = later_commands[0] if later_commands else None
        next_t = next_command["t_ms"] if next_command else trace[-1]["t_ms"] + 1
        start_index = min(bisect.bisect_left(times, command_t), len(trace) - 1)
        end_index = min(
            max(start_index, bisect.bisect_left(times, next_t) - 1),
            len(trace) - 1,
        )
        start = trace[start_index]
        end = trace[end_index]
        target_x = command["location"]["x"]
        target_y = command["location"]["y"]
        start_centroid = start["formation"]["centroid"]
        end_centroid = end["formation"]["centroid"]
        start_distance = math.hypot(
            target_x - start_centroid["x"], target_y - start_centroid["y"]
        )
        end_distance = math.hypot(
            target_x - end_centroid["x"], target_y - end_centroid["y"]
        )
        centroid_path = 0.0
        speed_samples = []
        heading_cosines = []
        progress_steps = []
        response_t = None
        centroid_response_t = None
        for index in range(start_index + 1, end_index + 1):
            row = trace[index]
            previous = trace[index - 1]
            dt = (row["t_ms"] - previous["t_ms"]) / 1000
            prior_centroid = previous["formation"]["centroid"]
            centroid = row["formation"]["centroid"]
            centroid_path += math.hypot(
                centroid["x"] - prior_centroid["x"],
                centroid["y"] - prior_centroid["y"],
            )
            centroid_step_cosine = vector_cosine(
                centroid["x"] - prior_centroid["x"],
                centroid["y"] - prior_centroid["y"],
                target_x - prior_centroid["x"],
                target_y - prior_centroid["y"],
            )
            if (
                centroid_response_t is None
                and centroid_step_cosine is not None
                and centroid_step_cosine >= 0.8
            ):
                centroid_response_t = row["t_ms"]
            aligned = 0
            moving = 0
            for key in cohort_keys:
                unit = row["units"][key]
                prior = previous["units"][key]
                vx = unit["x"] - prior["x"]
                vy = unit["y"] - prior["y"]
                distance = math.hypot(vx, vy)
                if distance <= 1e-9:
                    continue
                moving += 1
                if dt > 0:
                    speed_samples.append(distance / dt)
                before = math.hypot(target_x - prior["x"], target_y - prior["y"])
                after = math.hypot(target_x - unit["x"], target_y - unit["y"])
                progress_steps.append(after < before)
                cosine = vector_cosine(
                    vx,
                    vy,
                    target_x - prior["x"],
                    target_y - prior["y"],
                )
                if cosine is not None:
                    heading_cosines.append(cosine)
                    if cosine >= 0.9:
                        aligned += 1
            if (
                response_t is None
                and moving >= minimum_selected
                and aligned >= minimum_selected
            ):
                response_t = row["t_ms"]
        centroid_displacement = math.hypot(
            end_centroid["x"] - start_centroid["x"],
            end_centroid["y"] - start_centroid["y"],
        )
        centroid_cosine = vector_cosine(
            end_centroid["x"] - start_centroid["x"],
            end_centroid["y"] - start_centroid["y"],
            target_x - start_centroid["x"],
            target_y - start_centroid["y"],
        )
        selected_count = len(set(command.get("unit_ids", ())) & cohort_keys)
        record = {
            "index": move_index + 1,
            "t_ms": command_t,
            "next_move_t_ms": next_t if move_index + 1 < len(moves) else None,
            "next_cohort_command_kind": next_command["kind"] if next_command else None,
            "next_cohort_command_t_ms": next_command["t_ms"] if next_command else None,
            "available_motion_ms": max(0, end["t_ms"] - start["t_ms"]),
            "selected_cohort_units": selected_count,
            "location": command["location"],
            "target_id": command.get("target_id"),
            "human_order": command.get("human_order"),
            "start_centroid_distance_to_click": start_distance,
            "end_centroid_distance_to_click": end_distance,
            "centroid_progress_to_click": start_distance - end_distance,
            "centroid_displacement_tiles": centroid_displacement,
            "centroid_path_tiles": centroid_path,
            "centroid_path_straightness": (
                centroid_displacement / centroid_path if centroid_path > 1e-12 else None
            ),
            "centroid_heading_cosine_to_click": centroid_cosine,
            "unit_step_heading_cosine_to_click": distribution(heading_cosines),
            "unit_step_share_reducing_click_distance": (
                sum(progress_steps) / len(progress_steps) if progress_steps else None
            ),
            "moving_speed_tiles_per_second": distribution(speed_samples),
            "majority_aligned_response_t_ms": response_t,
            "majority_aligned_response_latency_ms": (
                response_t - command_t if response_t is not None else None
            ),
            "centroid_aligned_response_t_ms": centroid_response_t,
            "centroid_aligned_response_latency_ms": (
                centroid_response_t - command_t
                if centroid_response_t is not None else None
            ),
            "start_formation": compact_formation(start["formation"]),
            "end_formation": compact_formation(end["formation"]),
        }
        records.append(record)
        all_heading_cosines.extend(heading_cosines)
        all_speeds.extend(speed_samples)
        all_progress_steps.extend(progress_steps)
    intervals = [
        moves[index + 1]["t_ms"] - moves[index]["t_ms"]
        for index in range(len(moves) - 1)
    ]
    target_steps = [
        math.hypot(
            moves[index + 1]["location"]["x"] - moves[index]["location"]["x"],
            moves[index + 1]["location"]["y"] - moves[index]["location"]["y"],
        )
        for index in range(len(moves) - 1)
    ]
    return {
        "count": len(moves),
        "full_cohort_command_count": sum(
            1 for move in moves
            if len(set(move.get("unit_ids", ())) & cohort_keys) == len(cohort_keys)
        ),
        "selected_unit_count": distribution([
            len(set(move.get("unit_ids", ())) & cohort_keys) for move in moves
        ]),
        "intercommand_interval_ms": distribution(intervals),
        "clicked_target_step_tiles": distribution(target_steps),
        "clicked_target_path_tiles": sum(target_steps),
        "unit_step_heading_cosine_to_click": distribution(all_heading_cosines),
        "unit_step_share_reducing_click_distance": (
            sum(all_progress_steps) / len(all_progress_steps)
            if all_progress_steps else None
        ),
        "moving_speed_tiles_per_second": distribution(all_speeds),
        "majority_aligned_response_latency_ms": distribution([
            record["majority_aligned_response_latency_ms"]
            for record in records
        ]),
        "centroid_heading_cosine_to_click": distribution([
            record["centroid_heading_cosine_to_click"] for record in records
        ]),
        "centroid_path_straightness": distribution([
            record["centroid_path_straightness"] for record in records
        ]),
        "centroid_path_tiles": sum(record["centroid_path_tiles"] for record in records),
        "centroid_progress_to_click_tiles": distribution([
            record["centroid_progress_to_click"] for record in records
        ]),
        "commands_with_positive_centroid_progress": sum(
            1 for record in records if record["centroid_progress_to_click"] > 0
        ),
        "commands_with_majority_unit_steps_reducing_click_distance": sum(
            1 for record in records
            if (
                record["unit_step_share_reducing_click_distance"] is not None
                and record["unit_step_share_reducing_click_distance"] > 0.5
            )
        ),
        "centroid_aligned_response_latency_ms": distribution([
            record["centroid_aligned_response_latency_ms"] for record in records
        ]),
        "records": records,
    }


def analyze_ally_spacing(trace, half_x, half_y, multiplier):
    combined_x = 2 * half_x
    combined_y = 2 * half_y
    shrunk_x = combined_x * multiplier
    shrunk_y = combined_y * multiplier
    frames_with_nominal_overlap = 0
    frames_below_shrunk_extent = 0
    frames_with_exact_stack = 0
    maximum_nominal = {"depth": 0, "t_ms": None, "left": None, "right": None}
    maximum_shrunk = {"depth": 0, "t_ms": None, "left": None, "right": None}
    maximum_stack = {"count": 1, "t_ms": None, "x": None, "y": None}
    nearest_axis_by_frame = []
    nominal_pair_counts = []
    shrunk_pair_counts = []
    pair_count = (
        len(trace[0]["units"]) * (len(trace[0]["units"]) - 1) // 2
        if trace else 0
    )
    for row in trace:
        units = list(row["units"].items())
        nominal_pairs = 0
        shrunk_pairs = 0
        nearest_axis = math.inf
        buckets = Counter((round(unit["x"], 6), round(unit["y"], 6)) for _, unit in units)
        (stack_point, stack_count) = max(buckets.items(), key=lambda item: item[1])
        if stack_count > maximum_stack["count"]:
            maximum_stack = {
                "count": stack_count,
                "t_ms": row["t_ms"],
                "x": stack_point[0],
                "y": stack_point[1],
            }
        if stack_count > 1:
            frames_with_exact_stack += 1
        for left_index, (left_key, left) in enumerate(units):
            for right_key, right in units[left_index + 1:]:
                dx = abs(right["x"] - left["x"])
                dy = abs(right["y"] - left["y"])
                nearest_axis = min(nearest_axis, max(dx, dy))
                nominal_gap = max(dx - combined_x, dy - combined_y)
                shrunk_gap = max(dx - shrunk_x, dy - shrunk_y)
                if nominal_gap < -1e-12:
                    nominal_pairs += 1
                    depth = -nominal_gap
                    if depth > maximum_nominal["depth"]:
                        maximum_nominal = {
                            "depth": depth,
                            "t_ms": row["t_ms"],
                            "left": left_key,
                            "right": right_key,
                            "dx": dx,
                            "dy": dy,
                        }
                if shrunk_gap < -1e-12:
                    shrunk_pairs += 1
                    depth = -shrunk_gap
                    if depth > maximum_shrunk["depth"]:
                        maximum_shrunk = {
                            "depth": depth,
                            "t_ms": row["t_ms"],
                            "left": left_key,
                            "right": right_key,
                            "dx": dx,
                            "dy": dy,
                        }
        nearest_axis_by_frame.append(nearest_axis)
        nominal_pair_counts.append(nominal_pairs)
        shrunk_pair_counts.append(shrunk_pairs)
        if nominal_pairs:
            frames_with_nominal_overlap += 1
        if shrunk_pairs:
            frames_below_shrunk_extent += 1
    frame_count = len(trace)
    return {
        "collision_half_extents": {"x": half_x, "y": half_y},
        "minimum_collision_multiplier": multiplier,
        "nominal_combined_extents": {"x": combined_x, "y": combined_y},
        "minimum_shrunk_combined_extents": {"x": shrunk_x, "y": shrunk_y},
        "possible_pairs_per_frame": pair_count,
        "nearest_pair_max_axis_separation_by_frame": distribution(nearest_axis_by_frame),
        "nominally_overlapping_pair_count_by_frame": distribution(nominal_pair_counts),
        "nominally_overlapping_pair_share_by_frame": distribution([
            count / pair_count for count in nominal_pair_counts
        ] if pair_count else []),
        "below_minimum_shrunk_pair_count_by_frame": distribution(shrunk_pair_counts),
        "below_minimum_shrunk_pair_share_by_frame": distribution([
            count / pair_count for count in shrunk_pair_counts
        ] if pair_count else []),
        "frames_with_nominal_overlap": frames_with_nominal_overlap,
        "nominal_overlap_frame_share": frames_with_nominal_overlap / frame_count,
        "frames_below_minimum_shrunk_extent": frames_below_shrunk_extent,
        "below_minimum_shrunk_extent_frame_share": (
            frames_below_shrunk_extent / frame_count
        ),
        "frames_with_exact_coordinate_stack": frames_with_exact_stack,
        "exact_coordinate_stack_frame_share": frames_with_exact_stack / frame_count,
        "maximum_nominal_penetration": maximum_nominal,
        "maximum_penetration_below_minimum_shrunk_extent": maximum_shrunk,
        "maximum_exact_coordinate_stack": maximum_stack,
    }


def speed_factor_summary(speeds, reference_speed):
    usable = [
        speed for speed in speeds
        if finite(speed) and reference_speed * 0.5 <= speed <= reference_speed * 2
    ]
    buckets = Counter(round(speed / reference_speed, 2) for speed in usable)
    canonical = (5 / 6, 1.0, 1.2, 1.5)
    return {
        "reference_speed_tiles_per_second": reference_speed,
        "normalized_factor": distribution([
            speed / reference_speed for speed in usable
        ]),
        "most_common_rounded_factors": [
            {"factor": factor, "samples": count, "share": count / len(usable)}
            for factor, count in buckets.most_common(12)
        ],
        "canonical_factor_shares_within_0_01": {
            str(round(factor, 4)): sum(
                1 for speed in usable
                if abs(speed / reference_speed - factor) <= 0.01
            ) / len(usable)
            for factor in canonical
        },
    }


def movement_phase_dynamics(trace):
    keys = sorted(trace[0]["units"])
    unit_paths = {key: 0.0 for key in keys}
    centroid_path = 0.0
    widths = []
    heights = []
    median_radii = []
    median_nearest = []
    moving_counts = []
    previous = None
    for row in trace:
        formation = row["formation"]
        widths.append(formation["bounds"]["width"])
        heights.append(formation["bounds"]["height"])
        median_radii.append(formation["radius_tiles"]["median"])
        median_nearest.append(formation["nearest_neighbor_tiles"]["median"])
        moving_counts.append(len(row["moving_keys"]))
        if previous is not None:
            left = previous["formation"]["centroid"]
            right = formation["centroid"]
            centroid_path += math.hypot(right["x"] - left["x"], right["y"] - left["y"])
            for key in keys:
                unit = row["units"][key]
                prior = previous["units"][key]
                unit_paths[key] += math.hypot(
                    unit["x"] - prior["x"], unit["y"] - prior["y"]
                )
        previous = row
    start_centroid = trace[0]["formation"]["centroid"]
    end_centroid = trace[-1]["formation"]["centroid"]
    centroid_displacement = math.hypot(
        end_centroid["x"] - start_centroid["x"],
        end_centroid["y"] - start_centroid["y"],
    )
    extrema = lambda values, fn: {
        "value": fn(values),
        "t_ms": trace[values.index(fn(values))]["t_ms"],
    }
    return {
        "start_t_ms": trace[0]["t_ms"],
        "end_t_ms": trace[-1]["t_ms"],
        "duration_seconds": (trace[-1]["t_ms"] - trace[0]["t_ms"]) / 1000,
        "centroid_path_tiles": centroid_path,
        "centroid_net_displacement_tiles": centroid_displacement,
        "centroid_path_straightness": (
            centroid_displacement / centroid_path if centroid_path > 1e-12 else None
        ),
        "unit_path_distance_tiles": distribution(list(unit_paths.values())),
        "moving_unit_count_by_frame": distribution(moving_counts),
        "formation_width_tiles": distribution(widths),
        "formation_height_tiles": distribution(heights),
        "formation_median_radius_tiles": distribution(median_radii),
        "formation_median_nearest_neighbor_tiles": distribution(median_nearest),
        "minimum_width": extrema(widths, min),
        "maximum_width": extrema(widths, max),
        "minimum_height": extrema(heights, min),
        "maximum_height": extrema(heights, max),
        "minimum_median_radius": extrema(median_radii, min),
        "maximum_median_radius": extrema(median_radii, max),
        "minimum_median_nearest_neighbor": extrema(median_nearest, min),
    }


def trace_speed_samples(trace):
    by_unit = defaultdict(list)
    for index in range(1, len(trace)):
        row = trace[index]
        previous = trace[index - 1]
        dt = (row["t_ms"] - previous["t_ms"]) / 1000
        if dt <= 0:
            continue
        for key, unit in row["units"].items():
            prior = previous["units"][key]
            distance = math.hypot(unit["x"] - prior["x"], unit["y"] - prior["y"])
            if distance > 1e-9:
                by_unit[key].append(distance / dt)
    return by_unit


def combat_state_contamination(trace):
    """Separate ordinary group motion from known melee swing/reload frames."""
    combat_states = {6, 7}
    contaminated = []
    clean = []
    combat_unit_counts = []
    for row in trace:
        combat_units = [
            unit for unit in row["units"].values()
            if unit.get("action_state") in combat_states
        ]
        combat_unit_counts.append(len(combat_units))
        if combat_units:
            contaminated.append(row)
        else:
            clean.append(row)
    return {
        "known_combat_action_states": sorted(combat_states),
        "frames_with_known_combat_action": len(contaminated),
        "known_combat_action_frame_share": (
            len(contaminated) / len(trace) if trace else None
        ),
        "combat_unit_count_by_frame": distribution(combat_unit_counts),
        "first_known_combat_action_t_ms": (
            contaminated[0]["t_ms"] if contaminated else None
        ),
        "last_known_combat_action_t_ms": (
            contaminated[-1]["t_ms"] if contaminated else None
        ),
        "clean_trace": clean,
    }


def context_proximity(trace, exclusion_distance=2.0):
    """Measure and filter cohort frames near any other live combat unit."""
    nearest_euclidean = []
    nearest_max_axis = []
    near = []
    far = []
    closest = {
        "euclidean_distance": None,
        "max_axis_distance": None,
        "t_ms": None,
        "cohort_unit": None,
        "context_unit": None,
    }
    for row in trace:
        pairs = []
        for key, unit in row["units"].items():
            for context_key, context_unit in row.get("context_units", {}).items():
                dx = abs(unit["x"] - context_unit["x"])
                dy = abs(unit["y"] - context_unit["y"])
                pairs.append((math.hypot(dx, dy), max(dx, dy), key, context_key))
        if not pairs:
            far.append(row)
            continue
        frame_closest = min(pairs)
        nearest_euclidean.append(frame_closest[0])
        nearest_max_axis.append(frame_closest[1])
        if (
            closest["euclidean_distance"] is None
            or frame_closest[0] < closest["euclidean_distance"]
        ):
            closest = {
                "euclidean_distance": frame_closest[0],
                "max_axis_distance": frame_closest[1],
                "t_ms": row["t_ms"],
                "cohort_unit": frame_closest[2],
                "context_unit": frame_closest[3],
            }
        if frame_closest[0] < exclusion_distance:
            near.append(row)
        else:
            far.append(row)
    return {
        "exclusion_distance_tiles": exclusion_distance,
        "nearest_context_euclidean_distance_by_frame": distribution(
            nearest_euclidean
        ),
        "nearest_context_max_axis_distance_by_frame": distribution(
            nearest_max_axis
        ),
        "frames_near_context_unit": len(near),
        "near_context_frame_share": len(near) / len(trace) if trace else None,
        "closest_observation": closest,
        "far_trace": far,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", help="capture prefix, without .frames.bin")
    parser.add_argument("--expected-count", type=int, default=20)
    parser.add_argument("--collision-half-x", type=float, default=0.25)
    parser.add_argument("--collision-half-y", type=float, default=0.25)
    parser.add_argument("--minimum-collision-multiplier", type=float, default=0.5)
    parser.add_argument("--output", help="default: <prefix>.movement.analysis.json")
    args = parser.parse_args()
    if args.expected_count < 1:
        raise ValueError("expected count must be positive")
    if args.collision_half_x <= 0 or args.collision_half_y <= 0:
        raise ValueError("collision half-extents must be positive")
    if not 0 < args.minimum_collision_multiplier <= 1:
        raise ValueError("minimum collision multiplier must be within (0, 1]")

    decoded = decode(args.prefix, args.expected_count)
    rows = decoded.pop("rows")
    commands = decoded.pop("commands")
    trace, unit_speeds, action_states, action_types, action_model_samples = movement_trace(rows)
    events = detect_destination_events(trace, decoded["selected_count"])
    windows = detect_active_windows(trace, decoded["selected_count"])
    episodes = match_events_to_windows(trace, events, windows)
    cohort_keys = set(rows[0]["units"])
    move_command_analysis = analyze_move_commands(trace, commands, cohort_keys)
    ally_spacing = analyze_ally_spacing(
        trace,
        args.collision_half_x,
        args.collision_half_y,
        args.minimum_collision_multiplier,
    )
    cohort_commands = [
        command for command in commands
        if command["kind"] in {"move", "interact"}
        and len(set(command.get("unit_ids", ())) & cohort_keys)
        >= max(2, math.ceil(len(cohort_keys) * 0.5))
    ]
    first_move_t = min(
        command["t_ms"] for command in cohort_commands if command["kind"] == "move"
    )
    later_non_move = [
        command for command in cohort_commands
        if command["kind"] != "move" and command["t_ms"] > first_move_t
    ]
    movement_end_t = (
        min(command["t_ms"] for command in later_non_move)
        if later_non_move else trace[-1]["t_ms"] + 1
    )
    movement_phase_trace = [
        row for row in trace if first_move_t <= row["t_ms"] < movement_end_t
    ]
    movement_phase_speeds_by_unit = trace_speed_samples(movement_phase_trace)
    movement_phase_speeds = [
        speed for speeds in movement_phase_speeds_by_unit.values() for speed in speeds
    ]
    reference_speed = statistics.median([
        statistics.median(speeds)
        for speeds in movement_phase_speeds_by_unit.values()
        if speeds
    ])
    combat_contamination = combat_state_contamination(movement_phase_trace)
    pure_move_trace = combat_contamination.pop("clean_trace")
    proximity = context_proximity(movement_phase_trace)
    far_from_context_trace = proximity.pop("far_trace")
    movement_phase = {
        "terminating_command": later_non_move[0] if later_non_move else None,
        "dynamics": movement_phase_dynamics(movement_phase_trace),
        "moving_speed_tiles_per_second": distribution(movement_phase_speeds),
        "per_unit_speed_medians": distribution([
            statistics.median(speeds)
            for speeds in movement_phase_speeds_by_unit.values()
            if speeds
        ]),
        "speed_factors": speed_factor_summary(
            movement_phase_speeds, reference_speed
        ),
        "ally_spacing": analyze_ally_spacing(
            movement_phase_trace,
            args.collision_half_x,
            args.collision_half_y,
            args.minimum_collision_multiplier,
        ),
        "combat_state_contamination": combat_contamination,
        "combat_state_filtered_ally_spacing": analyze_ally_spacing(
            pure_move_trace,
            args.collision_half_x,
            args.collision_half_y,
            args.minimum_collision_multiplier,
        ),
        "context_unit_proximity": proximity,
        "far_from_context_ally_spacing": analyze_ally_spacing(
            far_from_context_trace,
            args.collision_half_x,
            args.collision_half_y,
            args.minimum_collision_multiplier,
        ),
    }
    all_speeds = [speed for speeds in unit_speeds.values() for speed in speeds]
    first_units = rows[0]["units"]
    result = {
        "schema_version": 1,
        "capture_prefix": args.prefix,
        "capture_validation": {
            "frames_bin_bytes": decoded["path"].stat().st_size,
            "frames_bin_sha256": sha256(decoded["path"]),
            "complete_frame_sequences": decoded["sequence_count"],
            "frames": decoded["frame_count"],
            "full_snapshots": decoded["full_snapshots"],
            "segments": decoded["segments"],
            "selected_segment": decoded["selected_segment"],
            "selected_cohort_frames": len(rows),
            "t_ms_min": rows[0]["t_ms"],
            "t_ms_max": rows[-1]["t_ms"],
            "game_time_span_seconds": (rows[-1]["t_ms"] - rows[0]["t_ms"]) / 1000,
            "incomplete_tail_bytes": decoded["incomplete_tail_bytes"],
            "incomplete_tail_declared_payload_bytes": decoded[
                "incomplete_tail_declared_payload_bytes"
            ],
            "incomplete_tail_payload_bytes": decoded["incomplete_tail_payload_bytes"],
        },
        "selected_cohort": {
            "owner": decoded["selected_owner"],
            "master": decoded["selected_master"],
            "count": decoded["selected_count"],
            "entity_ids": sorted(first_units),
            "initial_hp": distribution([unit["hp"] for unit in first_units.values()]),
        },
        "candidate_groups": decoded["candidate_groups"],
        "action_state_sample_counts": dict(sorted(action_states.items())),
        "action_type_sample_counts": dict(sorted(action_types.items())),
        "action_model_samples": action_model_samples,
        "command_kind_counts": dict(sorted(Counter(
            command["kind"] for command in commands
        ).items())),
        "move_command_analysis": move_command_analysis,
        "movement_phase": movement_phase,
        "decoded_action_destination_change_events": events,
        "movement_windows": [
            {
                "start_t_ms": trace[start]["t_ms"],
                "end_t_ms": trace[end]["t_ms"],
                "duration_seconds": (trace[end]["t_ms"] - trace[start]["t_ms"]) / 1000,
            }
            for start, end in windows
        ],
        "movement_episodes": episodes,
        "whole_capture": {
            "initial_formation": trace[0]["formation"],
            "final_formation": trace[-1]["formation"],
            "moving_speed_tiles_per_second": distribution(all_speeds),
            "per_unit_speed_medians": distribution([
                statistics.median(speeds) for speeds in unit_speeds.values() if speeds
            ]),
            "ally_spacing": ally_spacing,
        },
    }
    output = Path(args.output or f"{args.prefix}.movement.analysis.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
