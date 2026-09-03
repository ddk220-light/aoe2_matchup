"""Measure Player 4's last live frame and the post-defeat target transition.

This reads only full-rate gRPC state.  It does not derive any simulator input;
the purpose is to distinguish real unit combat/trigger processing from the
retired per-matchup release clock.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import statistics
import sys


SCRIPT = Path(__file__).resolve()
REPO_ROOT = SCRIPT.parents[3]
sys.path.insert(0, str(REPO_ROOT / "aoe2x" / "grpc"))

import cade_api_pb2 as pb  # noqa: E402
import decode_state_v2 as D  # noqa: E402
from analyze_live_melee_1v1 import action_of, seed_snapshot  # noqa: E402


SNAP_RESEED = 400_000
ARMY_MODEL_TYPES = {9, 11, 12}


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def _entities(doc, entity_store, world_id):
    world_entities = doc.models.get(world_id, {}).get(1, {})
    merged = []
    for key, scalar in entity_store.items():
        if scalar.get("__type__") not in ARMY_MODEL_TYPES:
            continue
        doc_id = world_entities.get(key)
        entity = scalar
        if isinstance(doc_id, int) and doc_id in doc.models:
            entity = {**doc.models[doc_id], **scalar}
        owner = entity.get(2)
        hp = entity.get(12)
        if owner not in {2, 3, 4} or not _finite(hp) or hp <= 0:
            continue
        if not _finite(entity.get(3)) or not _finite(entity.get(4)):
            continue
        merged.append((key, entity))
    return merged


def analyze(path: Path) -> dict:
    doc = entity_store = world_id = None
    start_time = None
    first_p3_target_p4 = None
    first_p3_target_p2 = None
    last_p4_alive = None
    first_no_p4_after_live = None
    initial = {2: 0, 3: 0, 4: 0}
    initial_hp = {2: 0.0, 3: 0.0, 4: 0.0}
    initial_positions = {2: {}, 3: {}, 4: {}}
    prior_had_p4 = False
    first_p3_targets: dict[int, int] = {}
    first_targets_by_owner = {2: {}, 3: {}, 4: {}}
    first_target_times_by_owner = {2: {}, 3: {}, 4: {}}
    first_attack_times_by_owner = {2: {}, 3: {}, 4: {}}
    first_attack_targets_by_owner = {2: {}, 3: {}, 4: {}}
    first_target_changes_by_owner = {2: {}, 3: {}, 4: {}}
    first_target_geometry_by_owner = {2: {}, 3: {}, 4: {}}
    first_attack_geometry_by_owner = {2: {}, 3: {}, 4: {}}
    p4_last_seen: dict[int, float] = {}
    samples = []
    next_sample = 0
    last_frame_time = None
    principal_elimination_time = None

    with path.open("rb") as stream:
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
                patch = frame.patch
                if patch and len(patch) > SNAP_RESEED:
                    doc, entity_store, world_id = seed_snapshot(patch)
                    continue
                if entity_store is None:
                    continue
                if patch:
                    D.apply_patch(doc, patch, entity_store, world_id)
                selected = _entities(doc, entity_store, world_id)
                counts = {
                    owner: sum(entity.get(2) == owner for _, entity in selected)
                    for owner in (2, 3, 4)
                }
                if start_time is None:
                    if counts[2] == 0 or counts[3] == 0 or counts[4] != 9:
                        continue
                    start_time = frame.time / 1000.0
                    initial = counts
                    initial_hp = {
                        owner: sum(float(entity.get(12)) for _, entity in selected
                                   if entity.get(2) == owner)
                        for owner in (2, 3, 4)
                    }
                    initial_positions = {
                        owner: {
                            int(entity.get(0)): [round(float(entity.get(3)), 3),
                                                 round(float(entity.get(4)), 3)]
                            for _, entity in selected if entity.get(2) == owner
                        }
                        for owner in (2, 3, 4)
                    }
                game_time = frame.time / 1000.0 - start_time
                last_frame_time = game_time
                if (principal_elimination_time is None
                        and (counts[2] == 0 or counts[3] == 0)):
                    principal_elimination_time = game_time
                if counts[4] > 0:
                    prior_had_p4 = True
                    last_p4_alive = game_time
                elif prior_had_p4 and first_no_p4_after_live is None:
                    first_no_p4_after_live = game_time

                by_key = {key: entity for key, entity in selected}
                by_id = {entity.get(0): entity for _, entity in selected}
                p3_target_p4 = []
                p3_attacking_p4 = 0
                for _, entity in selected:
                    owner = entity.get(2)
                    action = action_of(doc, entity)
                    raw_target = action.get("target_id")
                    target = by_key.get(raw_target) or by_id.get(raw_target)
                    if not target:
                        continue
                    actor_id = int(entity.get(0))
                    target_id = int(target.get(0))
                    if owner in first_targets_by_owner and target.get(2) != owner:
                        original_target_id = first_targets_by_owner[owner].get(actor_id)
                        if (original_target_id is not None
                                and original_target_id != target_id
                                and actor_id not in first_target_changes_by_owner[owner]):
                            original_target = by_id.get(original_target_id)
                            first_target_changes_by_owner[owner][actor_id] = {
                                "game_s": game_time,
                                "from_target_id": original_target_id,
                                "to_target_id": target_id,
                                "original_target_alive": original_target is not None,
                                "action_state": action.get("action_state"),
                                "actor_position": [round(float(entity.get(3)), 3),
                                                   round(float(entity.get(4)), 3)],
                                "target_position": [round(float(target.get(3)), 3),
                                                    round(float(target.get(4)), 3)],
                                "center_distance": round(math.hypot(
                                    float(target.get(3)) - float(entity.get(3)),
                                    float(target.get(4)) - float(entity.get(4))), 3),
                            }
                        first_targets_by_owner[owner].setdefault(actor_id, target_id)
                        first_target_times_by_owner[owner].setdefault(actor_id, game_time)
                        first_target_geometry_by_owner[owner].setdefault(actor_id, {
                            "actor_position": [round(float(entity.get(3)), 3),
                                               round(float(entity.get(4)), 3)],
                            "target_position": [round(float(target.get(3)), 3),
                                                round(float(target.get(4)), 3)],
                            "center_distance": round(math.hypot(
                                float(target.get(3)) - float(entity.get(3)),
                                float(target.get(4)) - float(entity.get(4))), 3),
                        })
                        if action.get("action_state") == 7:
                            first_attack_times_by_owner[owner].setdefault(actor_id, game_time)
                            first_attack_targets_by_owner[owner].setdefault(actor_id, target_id)
                            first_attack_geometry_by_owner[owner].setdefault(actor_id, {
                                "actor_position": [round(float(entity.get(3)), 3),
                                                   round(float(entity.get(4)), 3)],
                                "target_position": [round(float(target.get(3)), 3),
                                                    round(float(target.get(4)), 3)],
                                "center_distance": round(math.hypot(
                                    float(target.get(3)) - float(entity.get(3)),
                                    float(target.get(4)) - float(entity.get(4))), 3),
                            })
                    if owner != 3:
                        continue
                    if target.get(2) == 4 and first_p3_target_p4 is None:
                        first_p3_target_p4 = game_time
                    if target.get(2) == 4:
                        p3_target_p4.append(target_id)
                        first_p3_targets.setdefault(actor_id, target_id)
                        if action.get("action_state") == 7:
                            p3_attacking_p4 += 1
                    if target.get(2) == 2 and first_p3_target_p2 is None:
                        first_p3_target_p2 = game_time
                for _, entity in selected:
                    if entity.get(2) == 4:
                        p4_last_seen[int(entity.get(0))] = game_time
                if game_time + 1e-9 >= next_sample:
                    p4 = [entity for _, entity in selected if entity.get(2) == 4]
                    samples.append({
                        "game_s": round(game_time, 3),
                        "p4_live": len(p4),
                        "p4_hp": round(sum(float(entity.get(12)) for entity in p4), 3),
                        "p3_targeting_p4": len(p3_target_p4),
                        "p3_attacking_p4": p3_attacking_p4,
                        "p3_unique_p4_targets": len(set(p3_target_p4)),
                    })
                    next_sample += 2

    transition_delay = None
    if first_no_p4_after_live is not None and first_p3_target_p2 is not None:
        transition_delay = first_p3_target_p2 - first_no_p4_after_live
    def owner_opening_summary(owner):
        targets = first_targets_by_owner[owner]
        attack_targets = first_attack_targets_by_owner[owner]
        target_changes = first_target_changes_by_owner[owner]
        target_times = sorted(first_target_times_by_owner[owner].values())
        attack_times = sorted(first_attack_times_by_owner[owner].values())
        target_change_times = sorted(change["game_s"] for change in target_changes.values())
        target_change_delays = sorted(
            change["game_s"] - first_target_times_by_owner[owner][actor_id]
            for actor_id, change in target_changes.items()
        )
        return {
            "target_distribution": {
                str(target_id): sum(value == target_id for value in targets.values())
                for target_id in sorted(set(targets.values()))
            },
            "first_attack_target_distribution": {
                str(target_id): sum(value == target_id for value in attack_targets.values())
                for target_id in sorted(set(attack_targets.values()))
            },
            "first_attack_target_changed": sum(
                attack_target != targets.get(actor_id)
                for actor_id, attack_target in attack_targets.items()
            ),
            "first_target_change_count": len(target_changes),
            "first_target_change_while_original_alive": sum(
                change["original_target_alive"] for change in target_changes.values()
            ),
            "first_target_change_game_s": [round(value, 3) for value in target_change_times],
            "first_target_change_delay_s": [round(value, 3) for value in target_change_delays],
            "first_target_change_target_distribution": {
                str(target_id): sum(
                    change["to_target_id"] == target_id for change in target_changes.values()
                )
                for target_id in sorted(set(
                    change["to_target_id"] for change in target_changes.values()
                ))
            },
            "first_target_game_s": [round(value, 3) for value in target_times],
            "first_attack_game_s": [round(value, 3) for value in attack_times],
            "actors": {
                str(actor_id): {
                    "target_id": targets[actor_id],
                    "target_game_s": round(first_target_times_by_owner[owner][actor_id], 3),
                    "attack_game_s": round(first_attack_times_by_owner[owner][actor_id], 3)
                    if actor_id in first_attack_times_by_owner[owner] else None,
                    "attack_target_id": attack_targets.get(actor_id),
                    "attack_target_changed": (
                        attack_targets[actor_id] != targets[actor_id]
                        if actor_id in attack_targets else None
                    ),
                    "first_target_change": target_changes.get(actor_id),
                    "initial_position": initial_positions[owner].get(actor_id),
                    "target_geometry": first_target_geometry_by_owner[owner].get(actor_id),
                    "attack_geometry": first_attack_geometry_by_owner[owner].get(actor_id),
                }
                for actor_id in sorted(targets)
            },
        }
    return {
        "frames": str(path),
        "duration_game_s": round(last_frame_time, 3) if last_frame_time is not None else None,
        "principal_elimination_game_s": (
            round(principal_elimination_time, 3)
            if principal_elimination_time is not None else None
        ),
        "initial_live_counts": initial,
        "initial_hp": initial_hp,
        "first_p3_target_distribution": {
            str(target_id): sum(value == target_id for value in first_p3_targets.values())
            for target_id in sorted(set(first_p3_targets.values()))
        },
        "opening_by_owner": {
            str(owner): owner_opening_summary(owner) for owner in (2, 3, 4)
        },
        "first_p3_target_p4_game_s": first_p3_target_p4,
        "last_p4_alive_game_s": last_p4_alive,
        "first_frame_without_p4_game_s": first_no_p4_after_live,
        "first_p3_target_p2_game_s": first_p3_target_p2,
        "post_death_transition_delay_s": transition_delay,
        "p4_death_times_game_s": sorted(round(value, 3) for value in p4_last_seen.values()),
        "two_second_samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path, nargs="+")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--actor", type=int, action="append", default=[])
    args = parser.parse_args()
    rows = [analyze(path) for path in args.frames]
    if args.summary:
        rows = [summarize(row) for row in rows]
    elif args.compact:
        rows = [{key: value for key, value in row.items() if key != "two_second_samples"}
                for row in rows]
    if args.actor:
        selected_actors = {str(value) for value in args.actor}
        for row in rows:
            for owner in row["opening_by_owner"].values():
                owner["actors"] = {
                    actor_id: value for actor_id, value in owner["actors"].items()
                    if actor_id in selected_actors
                }
    print(json.dumps(rows, indent=2))
    return 0


def summarize(row: dict) -> dict:
    def values(values):
        return {
            "min": min(values) if values else None,
            "mean": round(statistics.mean(values), 3) if values else None,
            "max": max(values) if values else None,
            "values": values,
        }

    return {
        "frames": row["frames"],
        "duration_game_s": row["duration_game_s"],
        "principal_elimination_game_s": row["principal_elimination_game_s"],
        "initial_live_counts": row["initial_live_counts"],
        "initial_hp": row["initial_hp"],
        "last_p4_alive_game_s": row["last_p4_alive_game_s"],
        "first_frame_without_p4_game_s": row["first_frame_without_p4_game_s"],
        "post_death_transition_delay_s": row["post_death_transition_delay_s"],
        "p4_death_times_game_s": row["p4_death_times_game_s"],
        "opening_by_owner": {
            owner: {
                "target_distribution": opening["target_distribution"],
                "first_attack_target_distribution": (
                    opening["first_attack_target_distribution"]
                ),
                "first_attack_target_changed": opening["first_attack_target_changed"],
                "first_target_change_count": opening["first_target_change_count"],
                "first_target_change_while_original_alive": (
                    opening["first_target_change_while_original_alive"]
                ),
                "first_target_change_target_distribution": (
                    opening["first_target_change_target_distribution"]
                ),
                "first_target_change_game_s": values(
                    opening["first_target_change_game_s"]
                ),
                "first_target_change_delay_s": values(
                    opening["first_target_change_delay_s"]
                ),
                "first_target_game_s": values(opening["first_target_game_s"]),
                "first_attack_game_s": values(opening["first_attack_game_s"]),
            }
            for owner, opening in row["opening_by_owner"].items()
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
