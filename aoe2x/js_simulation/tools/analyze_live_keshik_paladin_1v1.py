"""Measure one live Elite Keshik-versus-Paladin gRPC capture.

The output is descriptive only. It reports the recorded target, motion, contact,
attack-state, and HP transitions without deriving simulation rules from them.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import struct
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VIDEO_SITE_PACKAGES = ROOT / "apps" / "video" / ".venv" / "Lib" / "site-packages"
GRPC_DIR = ROOT / "aoe2x" / "grpc"
sys.path.insert(0, str(VIDEO_SITE_PACKAGES))
sys.path.insert(0, str(GRPC_DIR))

import cade_api_pb2 as pb  # noqa: E402
import decode_state_v2 as decoder  # noqa: E402


SNAPSHOT_MIN_BYTES = 400_000
ARMY_MODEL_TYPES = {9, 11, 12}
# Depending on whether an upgraded unit is scenario/AI-created or directly
# player-controlled, the live layer can expose either its base-line or elite ID.
KESHIK_MASTERS = {1228, 1230}
OPPONENT_MASTERS = {38, 569}
KESHIK_LABEL = "Elite Keshik"
OPPONENT_LABEL = "Paladin"

F_ID, F_MASTER, F_OWNER, F_X, F_Y = 0, 1, 2, 3, 4
F_STATE, F_TYPE, F_HP, F_UNDER_ATTACK = 8, 11, 12, 13
F_CURRENT_ACTION = 20
A_TYPE, A_STATE, A_TARGET, A_TARGET_2 = 0, 1, 2, 3
A_TARGET_X, A_TARGET_Y, A_TIMER = 4, 5, 12

ACTION_STATE_LABELS = {
    1: "idle/complete",
    2: "target-lost",
    3: "fresh-order",
    4: "moving-to-target",
    6: "recovering/reload",
    7: "attack-animation",
}


def action_of(document, entity):
    reference = entity.get(F_CURRENT_ACTION)
    if not isinstance(reference, int):
        return {}
    action = document.models.get(reference)
    if not action:
        return {}
    return {
        "action_model_type": action.get("__type__"),
        "action_type": action.get(A_TYPE),
        "action_state": action.get(A_STATE),
        "target_id": action.get(A_TARGET),
        "target_2_id": action.get(A_TARGET_2),
        "target_x": action.get(A_TARGET_X),
        "target_y": action.get(A_TARGET_Y),
        "timer": action.get(A_TIMER),
    }


def decode_frames(frames_path, seed_path):
    document = entities = world_id = None
    rows = []
    kills = []
    sequence_count = total_frame_count = selected_frame_count = 0
    truncated_tail_bytes = 0
    snapshots = []
    selected_entities = {}

    def reseed(snapshot):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temporary:
            temporary.write(snapshot)
            temporary_path = Path(temporary.name)
        try:
            next_document = decoder.Doc()
            next_entities = {}
            _, next_world_id = decoder.seed_from_snapshot(
                str(temporary_path), next_document, next_entities,
            )
            return next_document, next_entities, next_world_id
        finally:
            temporary_path.unlink(missing_ok=True)

    with frames_path.open("rb") as stream:
        while True:
            header = stream.read(4)
            if len(header) < 4:
                break
            (length,) = struct.unpack("<I", header)
            payload = stream.read(length)
            if len(payload) != length:
                truncated_tail_bytes = len(header) + len(payload)
                break
            sequence = pb.FrameSequence()
            sequence.ParseFromString(payload)
            sequence_count += 1
            for frame in sequence.frame:
                if frame.patch and len(frame.patch) > SNAPSHOT_MIN_BYTES:
                    document, entities, world_id = reseed(frame.patch)
                    snapshots.append({
                        "segment": len(snapshots) + 1,
                        "t_ms": frame.time,
                        "snapshot_bytes": len(frame.patch),
                    })
                    # A new full snapshot starts a new game instance. This tool
                    # intentionally reports only the final instance in a capture.
                    rows.clear()
                    kills.clear()
                    selected_entities.clear()
                    selected_frame_count = 0
                    continue
                if entities is None:
                    continue
                if frame.patch:
                    decoder.apply_patch(document, frame.patch, entities, world_id)
                for event in frame.event:
                    if event.HasField("entityKilled"):
                        kills.append({
                            "t_ms": frame.time,
                            "id": event.entityKilled.id,
                            "killer_id": event.entityKilled.killerId,
                        })
                total_frame_count += 1
                selected_frame_count += 1
                world_entities = document.models.get(world_id, {}).get(1, {})
                for key, scalar_entity in entities.items():
                    if scalar_entity.get("__type__") not in ARMY_MODEL_TYPES:
                        continue
                    if scalar_entity.get(F_OWNER) in (1, 2, 3):
                        selected_entities[key] = {
                            "key": key,
                            "id": scalar_entity.get(F_ID),
                            "master": scalar_entity.get(F_MASTER),
                            "owner": scalar_entity.get(F_OWNER),
                            "hp": scalar_entity.get(F_HP),
                            "x": scalar_entity.get(F_X),
                            "y": scalar_entity.get(F_Y),
                        }
                    if (
                        scalar_entity.get(F_MASTER) not in KESHIK_MASTERS
                        and scalar_entity.get(F_MASTER) not in OPPONENT_MASTERS
                    ):
                        continue
                    document_id = world_entities.get(key)
                    entity = scalar_entity
                    if isinstance(document_id, int) and document_id in document.models:
                        entity = {**document.models[document_id], **scalar_entity}
                    row = {
                        "t_ms": frame.time,
                        "key": key,
                        "id": entity.get(F_ID),
                        "master": entity.get(F_MASTER),
                        "owner": entity.get(F_OWNER),
                        "x": entity.get(F_X),
                        "y": entity.get(F_Y),
                        "hp": entity.get(F_HP),
                        "entity_state": entity.get(F_STATE),
                        "entity_type": entity.get(F_TYPE),
                        "under_attack": entity.get(F_UNDER_ATTACK),
                    }
                    row.update(action_of(document, entity))
                    rows.append(row)

    return rows, kills, {
        "complete_sequences": sequence_count,
        "decoded_delta_frames_total": total_frame_count,
        "decoded_delta_frames_selected": selected_frame_count,
        "truncated_tail_bytes": truncated_tail_bytes,
        "snapshots": snapshots,
        "selected_segment": len(snapshots),
        "selected_entities": list(selected_entities.values()),
    }


def transition(series, predicate):
    for index in range(1, len(series)):
        if predicate(series[index - 1], series[index]):
            return series[index]
    return None


def position_changed(left, right, epsilon=1e-9):
    return math.hypot(right["x"] - left["x"], right["y"] - left["y"]) > epsilon


def geometry(left, right, radius_sum):
    dx = abs(left["x"] - right["x"])
    dy = abs(left["y"] - right["y"])
    chebyshev = max(dx, dy)
    euclidean = math.hypot(dx, dy)
    return {
        "dx": dx,
        "dy": dy,
        "chebyshev_center_distance": chebyshev,
        "euclidean_center_distance": euclidean,
        "body_gap": max(0.0, euclidean - radius_sum),
        "overlap_depth": max(0.0, radius_sum - euclidean),
        "axis_aligned_body_gap": max(0.0, chebyshev - radius_sum),
        "axis_aligned_overlap_depth": max(0.0, radius_sum - chebyshev),
    }


def rounded_geometry(value):
    if value is None:
        return None
    return {key: round(number, 6) for key, number in value.items()}


def measure_unit(label, series, opponent_id, frames_by_time, radius_sum):
    first_target = next(
        (row for row in series if row.get("target_id") == opponent_id), None,
    )
    first_move = transition(series, position_changed)
    first_swing = transition(
        series,
        lambda before, after: (
            after.get("action_state") == 7 and before.get("action_state") != 7
        ),
    )
    first_damage_taken = transition(
        series,
        lambda before, after: (
            isinstance(before.get("hp"), (int, float))
            and isinstance(after.get("hp"), (int, float))
            and after["hp"] < before["hp"]
        ),
    )

    def peer_at(row):
        if row is None:
            return None
        return frames_by_time.get(row["t_ms"], {}).get(opponent_id)

    moving_steps = []
    pursuit_steps = []
    closing_steps = 0
    aligned_cosines = []
    pursuit_start = first_target or first_move
    pursuit_end_ms = first_swing["t_ms"] if first_swing else series[-1]["t_ms"]
    for index in range(1, len(series)):
        before, after = series[index - 1], series[index]
        dt = (after["t_ms"] - before["t_ms"]) / 1000
        if dt <= 0:
            continue
        step_x = after["x"] - before["x"]
        step_y = after["y"] - before["y"]
        step = math.hypot(step_x, step_y)
        if step > 1e-9:
            moving_steps.append(step / dt)
        if not pursuit_start or not (pursuit_start["t_ms"] <= after["t_ms"] <= pursuit_end_ms):
            continue
        peer_before = frames_by_time.get(before["t_ms"], {}).get(opponent_id)
        peer_after = frames_by_time.get(after["t_ms"], {}).get(opponent_id)
        if not peer_before or not peer_after:
            continue
        pursuit_steps.append(step)
        distance_before = math.hypot(
            peer_before["x"] - before["x"], peer_before["y"] - before["y"],
        )
        distance_after = math.hypot(
            peer_after["x"] - after["x"], peer_after["y"] - after["y"],
        )
        if distance_after < distance_before - 1e-9:
            closing_steps += 1
        target_x = peer_before["x"] - before["x"]
        target_y = peer_before["y"] - before["y"]
        target_length = math.hypot(target_x, target_y)
        if step > 1e-9 and target_length > 1e-9:
            aligned_cosines.append(
                (step_x * target_x + step_y * target_y) / (step * target_length),
            )

    last_move_before_swing = None
    if first_swing:
        for index in range(1, len(series)):
            if series[index]["t_ms"] > first_swing["t_ms"]:
                break
            if position_changed(series[index - 1], series[index]):
                last_move_before_swing = series[index]

    target_transitions = []
    action_transitions = []
    for index in range(1, len(series)):
        before, after = series[index - 1], series[index]
        if after.get("target_id") != before.get("target_id"):
            target_transitions.append({
                "t_s": after["t_ms"] / 1000,
                "from": before.get("target_id"),
                "to": after.get("target_id"),
            })
        action_before = (before.get("action_type"), before.get("action_state"))
        action_after = (after.get("action_type"), after.get("action_state"))
        if action_after != action_before:
            action_transitions.append({
                "t_s": after["t_ms"] / 1000,
                "action_type": after.get("action_type"),
                "action_state": after.get("action_state"),
                "state_label": ACTION_STATE_LABELS.get(after.get("action_state"), "unknown"),
                "target_id": after.get("target_id"),
            })

    def event(row):
        peer = peer_at(row)
        return None if row is None else {
            "t_s": round(row["t_ms"] / 1000, 6),
            "position": [round(row["x"], 6), round(row["y"], 6)],
            "action_type": row.get("action_type"),
            "action_state": row.get("action_state"),
            "state_label": ACTION_STATE_LABELS.get(row.get("action_state"), "unknown"),
            "target_id": row.get("target_id"),
            "geometry": rounded_geometry(geometry(row, peer, radius_sum)) if peer else None,
        }

    pursuit_frame_count = max(1, len(pursuit_steps))
    return {
        "label": label,
        "id": series[0]["id"],
        "master": series[0]["master"],
        "owner": series[0]["owner"],
        "initial_hp": series[0]["hp"],
        "first_target": event(first_target),
        "first_movement": event(first_move),
        "first_attack_animation": event(first_swing),
        "first_damage_taken": event(first_damage_taken),
        "last_movement_before_first_attack_s": (
            round(last_move_before_swing["t_ms"] / 1000, 6)
            if last_move_before_swing else None
        ),
        "stationary_before_first_attack_s": (
            round((first_swing["t_ms"] - last_move_before_swing["t_ms"]) / 1000, 6)
            if first_swing and last_move_before_swing else None
        ),
        "median_moving_speed_tiles_s": (
            round(statistics.median(moving_steps), 6) if moving_steps else None
        ),
        "pursuit": {
            "sampled_steps": len(pursuit_steps),
            "path_length_tiles": round(sum(pursuit_steps), 6),
            "closing_step_fraction": round(closing_steps / pursuit_frame_count, 6),
            "median_heading_cosine_to_target": (
                round(statistics.median(aligned_cosines), 6)
                if aligned_cosines else None
            ),
        },
        "target_transitions": target_transitions,
        "action_transitions": action_transitions,
    }


def analyze(rows, kills, decode_meta, keshik_radius, opponent_radius):
    by_id = {}
    for row in rows:
        if row.get("id") is None or row.get("x") is None or row.get("y") is None:
            continue
        by_id.setdefault(row["id"], []).append(row)
    for series in by_id.values():
        series.sort(key=lambda row: row["t_ms"])

    keshik_ids = [
        uid for uid, series in by_id.items()
        if series[0]["master"] in KESHIK_MASTERS
    ]
    opponent_ids = [
        uid for uid, series in by_id.items()
        if series[0]["master"] in OPPONENT_MASTERS
    ]
    if len(keshik_ids) != 1 or len(opponent_ids) != 1:
        raise RuntimeError(
            f"expected one {KESHIK_LABEL} and one {OPPONENT_LABEL}, "
            f"found {keshik_ids=} {opponent_ids=}; "
            f"selected_entities={decode_meta['selected_entities']}",
        )
    keshik_id, opponent_id = keshik_ids[0], opponent_ids[0]
    keshik, opponent = by_id[keshik_id], by_id[opponent_id]
    frames_by_time = {}
    for row in rows:
        frames_by_time.setdefault(row["t_ms"], {})[row["id"]] = row

    radius_sum = keshik_radius + opponent_radius
    pair_frames = []
    for t_ms, frame in sorted(frames_by_time.items()):
        if keshik_id not in frame or opponent_id not in frame:
            continue
        left, right = frame[keshik_id], frame[opponent_id]
        pair_frames.append({
            "t_ms": t_ms,
            "left": left,
            "right": right,
            "geometry": geometry(left, right, radius_sum),
        })

    first_contact = next(
        (frame for frame in pair_frames if frame["geometry"]["body_gap"] <= 1e-6), None,
    )
    first_overlap = next(
        (frame for frame in pair_frames if frame["geometry"]["overlap_depth"] > 1e-6), None,
    )
    first_axis_contact = next(
        (
            frame for frame in pair_frames
            if frame["geometry"]["axis_aligned_body_gap"] <= 1e-6
        ),
        None,
    )
    first_axis_overlap = next(
        (
            frame for frame in pair_frames
            if frame["geometry"]["axis_aligned_overlap_depth"] > 1e-6
        ),
        None,
    )
    closest_approach = min(
        pair_frames,
        key=lambda frame: frame["geometry"]["euclidean_center_distance"],
    )
    overlap_frames = [
        frame for frame in pair_frames if frame["geometry"]["overlap_depth"] > 1e-6
    ]
    maximum_overlap = max(
        overlap_frames,
        key=lambda frame: frame["geometry"]["overlap_depth"],
        default=None,
    )
    axis_overlap_frames = [
        frame for frame in pair_frames
        if frame["geometry"]["axis_aligned_overlap_depth"] > 1e-6
    ]
    maximum_axis_overlap = max(
        axis_overlap_frames,
        key=lambda frame: frame["geometry"]["axis_aligned_overlap_depth"],
        default=None,
    )

    damage_events = []
    for victim_label, victim, attacker_id in (
        (KESHIK_LABEL, keshik, opponent_id),
        (OPPONENT_LABEL, opponent, keshik_id),
    ):
        for index in range(1, len(victim)):
            before, after = victim[index - 1], victim[index]
            if not all(isinstance(row.get("hp"), (int, float)) for row in (before, after)):
                continue
            if after["hp"] >= before["hp"]:
                continue
            peer = frames_by_time.get(after["t_ms"], {}).get(attacker_id)
            damage_events.append({
                "t_s": round(after["t_ms"] / 1000, 6),
                "attacker_id": attacker_id,
                "victim": victim_label,
                "victim_id": after["id"],
                "damage": round(before["hp"] - after["hp"], 6),
                "hp_after": after["hp"],
                "geometry": rounded_geometry(geometry(after, peer, radius_sum)) if peer else None,
            })

    def pair_event(frame):
        if frame is None:
            return None
        return {
            "t_s": round(frame["t_ms"] / 1000, 6),
            "keshik_position": [round(frame["left"]["x"], 6), round(frame["left"]["y"], 6)],
            "opponent_position": [round(frame["right"]["x"], 6), round(frame["right"]["y"], 6)],
            "geometry": rounded_geometry(frame["geometry"]),
        }

    pair_by_time = {frame["t_ms"]: frame for frame in pair_frames}
    manual_orders = []
    manual_engagements = []
    pending_order = None
    for index in range(1, len(keshik)):
        before, after = keshik[index - 1], keshik[index]
        before_action = (before.get("action_state"), before.get("target_id"))
        after_action = (after.get("action_state"), after.get("target_id"))
        if after_action == (4, -1) and before_action != after_action:
            pending_order = after
            manual_orders.append(after)
        if (
            pending_order is not None
            and after.get("action_state") == 7
            and before.get("action_state") != 7
        ):
            frame = pair_by_time.get(after["t_ms"])
            if frame:
                signed_dx = frame["right"]["x"] - frame["left"]["x"]
                signed_dy = frame["right"]["y"] - frame["left"]["y"]
                manual_engagements.append({
                    "order_t_ms": pending_order["t_ms"],
                    "attack_t_ms": after["t_ms"],
                    "approach_angle_degrees": (
                        math.degrees(math.atan2(signed_dy, signed_dx)) % 360
                    ),
                    "attack_frame": frame,
                })
            pending_order = None

    for index, engagement in enumerate(manual_engagements):
        end_ms = (
            manual_engagements[index + 1]["order_t_ms"]
            if index + 1 < len(manual_engagements)
            else pair_frames[-1]["t_ms"] + 1
        )
        window = [
            frame for frame in pair_frames
            if engagement["order_t_ms"] <= frame["t_ms"] < end_ms
        ]
        engagement["closest_in_episode"] = min(
            window,
            key=lambda frame: frame["geometry"]["euclidean_center_distance"],
        )

    manual_engagement_output = [
        {
            "sequence": index + 1,
            "ground_move_order_t_s": round(event["order_t_ms"] / 1000, 6),
            "attack_animation_t_s": round(event["attack_t_ms"] / 1000, 6),
            "order_to_attack_s": round(
                (event["attack_t_ms"] - event["order_t_ms"]) / 1000, 6,
            ),
            "approach_angle_degrees": round(event["approach_angle_degrees"], 6),
            "attack_start": pair_event(event["attack_frame"]),
            "closest_in_episode": pair_event(event["closest_in_episode"]),
        }
        for index, event in enumerate(manual_engagements)
    ]

    result = {
        "schema_version": 1,
        "measurement_scope": "observed live 1v1; no simulation rule inferred",
        "observed_matchup": f"{KESHIK_LABEL} vs {OPPONENT_LABEL}",
        "identity_note": (
            f"live gRPC exposed masters {keshik[0]['master']}/{opponent[0]['master']}; "
            "starting HP 165/180 confirms the Elite Keshik/Paladin units"
        ),
        "collision": {
            "keshik_radius_tiles": keshik_radius,
            "opponent_radius_tiles": opponent_radius,
            "contact_center_distance_euclidean_tiles": radius_sum,
            "radius_source": (
                "live AoE2 game DAT: selected masters "
                f"{keshik[0]['master']} and {opponent[0]['master']}"
            ),
        },
        "decode": decode_meta,
        "time_span_s": [
            round(pair_frames[0]["t_ms"] / 1000, 6),
            round(pair_frames[-1]["t_ms"] / 1000, 6),
        ],
        "units": {
            "keshik": measure_unit(
                KESHIK_LABEL, keshik, opponent_id, frames_by_time, radius_sum,
            ),
            "opponent": measure_unit(
                OPPONENT_LABEL, opponent, keshik_id, frames_by_time, radius_sum,
            ),
        },
        "pair": {
            "first_contact": pair_event(first_contact),
            "first_overlap": pair_event(first_overlap),
            "first_axis_aligned_contact": pair_event(first_axis_contact),
            "first_axis_aligned_overlap": pair_event(first_axis_overlap),
            "closest_approach": pair_event(closest_approach),
            "maximum_overlap": pair_event(maximum_overlap),
            "maximum_axis_aligned_overlap": pair_event(maximum_axis_overlap),
            "manual_keshik_engagements": manual_engagement_output,
            "damage_events": damage_events,
            "kill_events": kills,
        },
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    frames_path = args.frames.resolve()
    seed_path = (args.seed or Path(str(frames_path).replace(".frames.bin", ".seed_snap.bin"))).resolve()
    output_path = (args.output or Path(str(frames_path).replace(".frames.bin", ".analysis.json"))).resolve()
    rows, kills, decode_meta = decode_frames(frames_path, seed_path)
    result = analyze(
        rows,
        kills,
        decode_meta,
        0.25,
        0.25,
    )
    output_path.write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
