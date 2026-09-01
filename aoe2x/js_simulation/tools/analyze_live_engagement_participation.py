"""Compare first-20-second live and simulated ranged engagement participation.

The live side reads the five exact 27 Chinese Arbalester vs 18 Saracen Heavy
Cavalry Archer gRPC streams. The simulation side reads a fresh export from the
current engine. This is validation-only analysis: no observed matchup outcome
is converted into a runtime parameter.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics
import struct
import sys

import analyze_live_melee_group_variance as group
from analyze_live_melee_1v1 import action_of, merged_entities, seed_snapshot


ROOT = Path(__file__).resolve().parents[1]
MATCHUP_KEY = "arbalester_vs_heavy_cav_archer"
CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations" / "ranged_matrix_5x_2026-08-29"
    / MATCHUP_KEY
)
OUTPUT_ROOT = (
    ROOT / "calibration" / "reports" / "arbalester_hca_participation_2026-08-30"
)
SIMULATION_SOURCE = OUTPUT_ROOT / "simulation_participation.json"
WINDOW_SECONDS = 20
OPENING_SNAPSHOT_SECONDS = (1.6, 1.8, 2.5, 2.6, 3.3, 3.4)
SNAP_RESEED = 400_000
EXPECTED = {2: (492, 27), 3: (474, 18)}
# Optional scenario auxiliaries used only to resolve action targets. They are
# deliberately excluded from the principal-army participation aggregates.
AUXILIARY_EXPECTED = {}
MECHANICS = {
    2: {"range": 8.0, "min_range": 0.0, "outline": 0.2, "collision": 0.2},
    3: {"range": 7.0, "min_range": 0.0, "outline": 0.4, "collision": 0.25},
}
STATE_FIELDS = (
    "alive", "active", "firing", "notFiring", "windup", "reload", "inRangeNotFiring",
    "seekingMoving", "seekingStationary", "untargetedMoving",
    "untargetedStationary", "staleTarget",
)

# The shared raw HP-delta decoder is parameterized through these module-level
# roster selectors. Pin them before any run is decoded.
group.EXPECTED = EXPECTED


def rounded(value: float, digits: int = 4):
    return round(value, digits)


def within_reach(actor: dict, target: dict) -> bool:
    mechanics = MECHANICS[actor["owner"]]
    distance = math.hypot(target["x"] - actor["x"], target["y"] - actor["y"])
    if mechanics["min_range"] > 0 and distance < mechanics["min_range"] - 1e-12:
        return False
    gap = distance - mechanics["outline"] - MECHANICS[target["owner"]]["outline"]
    return gap <= mechanics["range"] + 0.1 + 1e-12


def empty_counts():
    return {owner: {field: 0 for field in STATE_FIELDS} for owner in (2, 3)}


def classify_frame(selected: dict, prior: dict, dt: float):
    counts = empty_counts()
    by_id = {unit["id"]: key for key, unit in selected.items()}
    for key, unit in selected.items():
        owner = unit["owner"]
        row = counts[owner]
        row["alive"] += 1
        raw_target = unit.get("target_id")
        target_key = raw_target if raw_target in selected else by_id.get(raw_target)
        target = selected.get(target_key)
        if target and target["owner"] == owner:
            target = None
        in_range = bool(target and within_reach(unit, target))
        state = unit.get("action_state")
        if target and in_range and state == 7:
            row["active"] += 1
            row["firing"] += 1
            row["windup"] += 1
            continue
        row["notFiring"] += 1
        if state == 6:
            row["reload"] += 1
            if target and in_range:
                row["active"] += 1
            continue
        previous = prior.get(key)
        speed = (
            math.hypot(unit["x"] - previous["x"], unit["y"] - previous["y"])
            / max(dt, 1e-9)
            if previous else 0.0
        )
        moving = speed > 0.05
        if raw_target is not None and target is None:
            row["staleTarget"] += 1
        if target and in_range:
            row["inRangeNotFiring"] += 1
        elif target:
            row["seekingMoving" if moving else "seekingStationary"] += 1
        else:
            row["untargetedMoving" if moving else "untargetedStationary"] += 1
    return counts


def classify_pairs(selected: dict):
    output = {}
    for owner in (2, 3):
        units = [unit for unit in selected.values() if unit["owner"] == owner]
        units_by_id = {unit["id"]: unit for unit in units}
        nearest = {unit["id"]: math.inf for unit in units}
        overlap_pairs = 0
        overlap_depth_sum = 0.0
        max_overlap_depth = 0.0
        overlapped = set()
        box_overlap_pairs = 0
        box_overlap_depth_sum = 0.0
        max_box_overlap_depth = 0.0
        box_overlapped = set()
        box_overlap_by_commitment = {
            "committedCommitted": {"pairs": 0, "depth": 0.0},
            "mixed": {"pairs": 0, "depth": 0.0},
            "uncommittedUncommitted": {"pairs": 0, "depth": 0.0},
        }
        box_neighbors = {unit["id"]: set() for unit in units}
        for left_index, left in enumerate(units):
            for right in units[left_index + 1:]:
                dx = abs(right["x"] - left["x"])
                dy = abs(right["y"] - left["y"])
                distance = math.hypot(dx, dy)
                nearest[left["id"]] = min(nearest[left["id"]], distance)
                nearest[right["id"]] = min(nearest[right["id"]], distance)
                extent = (MECHANICS[left["owner"]]["collision"]
                          + MECHANICS[right["owner"]]["collision"])
                overlap_depth = extent - distance
                if overlap_depth > 1e-12:
                    overlap_pairs += 1
                    overlap_depth_sum += overlap_depth
                    max_overlap_depth = max(max_overlap_depth, overlap_depth)
                    overlapped.add(left["id"])
                    overlapped.add(right["id"])
                # DAT collision_size x/y is an axis-aligned obstruction box.
                # Preserve the historical Euclidean metric above, but publish
                # this box metric for direct comparison with the engine's
                # Chebyshev collision solver.
                box_overlap_depth = extent - max(dx, dy)
                if box_overlap_depth > 1e-12:
                    box_overlap_pairs += 1
                    box_overlap_depth_sum += box_overlap_depth
                    max_box_overlap_depth = max(
                        max_box_overlap_depth, box_overlap_depth)
                    box_overlapped.add(left["id"])
                    box_overlapped.add(right["id"])
                    box_neighbors[left["id"]].add(right["id"])
                    box_neighbors[right["id"]].add(left["id"])
                    committed = [
                        unit.get("action_state") in (6, 7)
                        for unit in (left, right)
                    ]
                    commitment = (
                        "committedCommitted" if all(committed)
                        else "uncommittedUncommitted" if not any(committed)
                        else "mixed"
                    )
                    box_overlap_by_commitment[commitment]["pairs"] += 1
                    box_overlap_by_commitment[commitment]["depth"] += box_overlap_depth
        def shared_box_fraction(member_ids: tuple[int, ...]) -> float:
            members = [units_by_id[member_id] for member_id in member_ids]
            radii = [MECHANICS[member["owner"]]["collision"] for member in members]
            width = max(0.0, min(
                member["x"] + radius for member, radius in zip(members, radii)
            ) - max(
                member["x"] - radius for member, radius in zip(members, radii)
            ))
            height = max(0.0, min(
                member["y"] + radius for member, radius in zip(members, radii)
            ) - max(
                member["y"] - radius for member, radius in zip(members, radii)
            ))
            smallest_area = min((2 * radius) ** 2 for radius in radii)
            return width * height / smallest_area

        triple_stacks = 0
        four_stacks = 0
        max_shared_triple_fraction = 0.0
        max_shared_four_fraction = 0.0
        ordered_ids = sorted(units_by_id)
        for a_index, a_id in enumerate(ordered_ids):
            for b_id in sorted(member_id for member_id in box_neighbors[a_id]
                               if member_id > a_id):
                common_c = box_neighbors[a_id] & box_neighbors[b_id]
                for c_id in sorted(member_id for member_id in common_c
                                   if member_id > b_id):
                    triple_fraction = shared_box_fraction((a_id, b_id, c_id))
                    if triple_fraction <= 1e-12:
                        continue
                    triple_stacks += 1
                    max_shared_triple_fraction = max(
                        max_shared_triple_fraction, triple_fraction
                    )
                    common_d = common_c & box_neighbors[c_id]
                    for d_id in sorted(member_id for member_id in common_d
                                       if member_id > c_id):
                        four_fraction = shared_box_fraction((a_id, b_id, c_id, d_id))
                        if four_fraction <= 1e-12:
                            continue
                        four_stacks += 1
                        max_shared_four_fraction = max(
                            max_shared_four_fraction, four_fraction
                        )
        nearest_values = [value for value in nearest.values() if math.isfinite(value)]
        output[owner] = {
            "alive": len(units),
            "possiblePairs": len(units) * (len(units) - 1) / 2,
            "overlapPairs": overlap_pairs,
            "overlapDepthSum": overlap_depth_sum,
            "maxOverlapDepth": max_overlap_depth,
            "overlappedUnits": len(overlapped),
            "boxOverlapPairs": box_overlap_pairs,
            "boxOverlapDepthSum": box_overlap_depth_sum,
            "maxBoxOverlapDepth": max_box_overlap_depth,
            "boxOverlappedUnits": len(box_overlapped),
            **{
                f"box{key[0].upper()}{key[1:]}OverlapPairs": value["pairs"]
                for key, value in box_overlap_by_commitment.items()
            },
            **{
                f"box{key[0].upper()}{key[1:]}OverlapDepthSum": value["depth"]
                for key, value in box_overlap_by_commitment.items()
            },
            "tripleStacks": triple_stacks,
            "fourStacks": four_stacks,
            "maxSharedTripleFraction": max_shared_triple_fraction,
            "maxSharedFourFraction": max_shared_four_fraction,
            "nearestDistanceSum": sum(nearest_values),
            "nearestDistanceCount": len(nearest_values),
        }
    return output


def classify_formation(selected: dict):
    """Compact geometry for diagnostics without publishing every entity frame."""
    by_id = {unit["id"]: key for key, unit in selected.items()}
    output = {}
    for owner in (2, 3):
        units = [unit for unit in selected.values() if unit["owner"] == owner]
        hostiles = [unit for unit in selected.values() if unit["owner"] != owner]
        nearest = [
            min((math.hypot(enemy["x"] - unit["x"], enemy["y"] - unit["y"])
                 for enemy in hostiles), default=math.inf)
            for unit in units
        ]
        target_distances = []
        for unit in units:
            raw_target = unit.get("target_id")
            target_key = raw_target if raw_target in selected else by_id.get(raw_target)
            target = selected.get(target_key)
            if target and target["owner"] != owner:
                target_distances.append(math.hypot(
                    target["x"] - unit["x"], target["y"] - unit["y"]
                ))
        finite_nearest = [value for value in nearest if math.isfinite(value)]
        output[str(owner)] = {
            "alive": len(units),
            "meanX": rounded(statistics.fmean(unit["x"] for unit in units))
                if units else None,
            "meanY": rounded(statistics.fmean(unit["y"] for unit in units))
                if units else None,
            "minX": rounded(min(unit["x"] for unit in units)) if units else None,
            "maxX": rounded(max(unit["x"] for unit in units)) if units else None,
            "minY": rounded(min(unit["y"] for unit in units)) if units else None,
            "maxY": rounded(max(unit["y"] for unit in units)) if units else None,
            "meanNearestHostileDistance": rounded(statistics.fmean(finite_nearest))
                if finite_nearest else None,
            "minNearestHostileDistance": rounded(min(finite_nearest))
                if finite_nearest else None,
            "meanTargetDistance": rounded(statistics.fmean(target_distances))
                if target_distances else None,
        }
    return output


def classify_target_load(selected: dict):
    """Describe current principal-army target concentration.

    Player 4 is absent from the plugin entity graph, so its raw target IDs are
    unresolved before the diplomacy gate.  Once the two principal armies are
    hostile, both sides resolve normally and this directly measures how many
    actors share each live target.  It is forensic output only.
    """
    by_id = {
        unit["id"]: key for key, unit in selected.items()
        if unit.get("id") is not None
    }
    output = {}
    for owner in (2, 3):
        assigned = []
        attacking = []
        for unit in selected.values():
            if unit["owner"] != owner or unit["hp"] <= 0:
                continue
            raw_target = unit.get("target_id")
            target_key = raw_target if raw_target in selected else by_id.get(raw_target)
            target = selected.get(target_key)
            if not target or target["owner"] == owner or target["hp"] <= 0:
                continue
            assigned.append(target["id"])
            if unit.get("action_state") == 7:
                attacking.append(target["id"])

        def load_summary(targets: list[int]) -> dict:
            counts = Counter(targets)
            histogram = Counter(counts.values())
            return {
                "actors": len(targets),
                "uniqueTargets": len(counts),
                "maximumLoad": max(counts.values(), default=0),
                "loadHistogram": {
                    str(load): count for load, count in sorted(histogram.items())
                },
                "targetCounts": {
                    str(target): count for target, count in sorted(counts.items())
                },
            }

        output[str(owner)] = {
            "assigned": load_summary(assigned),
            "attacking": load_summary(attacking),
        }
    return output


def integrate_seconds(samples: list[dict], shot_starts: list[dict], damage: list[dict]):
    totals = [empty_counts() for _ in range(WINDOW_SECONDS)]
    pair_fields = (
        "alive", "possiblePairs", "overlapPairs", "overlapDepthSum",
        "overlappedUnits", "boxOverlapPairs", "boxOverlapDepthSum",
        "boxOverlappedUnits", "tripleStacks", "fourStacks",
        "boxCommittedCommittedOverlapPairs", "boxCommittedCommittedOverlapDepthSum",
        "boxMixedOverlapPairs", "boxMixedOverlapDepthSum",
        "boxUncommittedUncommittedOverlapPairs",
        "boxUncommittedUncommittedOverlapDepthSum",
        "nearestDistanceSum", "nearestDistanceCount",
    )
    pair_totals = [
        {owner: {field: 0.0 for field in pair_fields} for owner in (2, 3)}
        for _ in range(WINDOW_SECONDS)
    ]
    pair_max = [{owner: 0.0 for owner in (2, 3)} for _ in range(WINDOW_SECONDS)]
    pair_box_max = [
        {owner: 0.0 for owner in (2, 3)} for _ in range(WINDOW_SECONDS)
    ]
    pair_shared_triple_max = [
        {owner: 0.0 for owner in (2, 3)} for _ in range(WINDOW_SECONDS)
    ]
    pair_shared_four_max = [
        {owner: 0.0 for owner in (2, 3)} for _ in range(WINDOW_SECONDS)
    ]
    covered = [0.0 for _ in range(WINDOW_SECONDS)]
    if not samples:
        raise RuntimeError("no live samples to integrate")
    frame_deltas = [
        samples[index + 1]["t"] - samples[index]["t"]
        for index in range(len(samples) - 1)
        if 0 < samples[index + 1]["t"] - samples[index]["t"] < 0.2
    ]
    fallback_dt = statistics.median(frame_deltas) if frame_deltas else 1 / 60
    for index, sample in enumerate(samples):
        start = max(0.0, sample["t"])
        end = samples[index + 1]["t"] if index + 1 < len(samples) else start + fallback_dt
        end = min(float(WINDOW_SECONDS), end)
        if end <= start or start >= WINDOW_SECONDS:
            continue
        first_second = max(0, int(math.floor(start)))
        last_second = min(WINDOW_SECONDS - 1, int(math.floor(max(start, end - 1e-12))))
        for second in range(first_second, last_second + 1):
            duration = max(0.0, min(end, second + 1) - max(start, second))
            if duration <= 0:
                continue
            covered[second] += duration
            for owner in (2, 3):
                for field in STATE_FIELDS:
                    totals[second][owner][field] += sample["counts"][owner][field] * duration
                for field in pair_fields:
                    pair_totals[second][owner][field] += (
                        sample["pairs"][owner][field] * duration
                    )
                pair_max[second][owner] = max(
                    pair_max[second][owner], sample["pairs"][owner]["maxOverlapDepth"]
                )
                pair_box_max[second][owner] = max(
                    pair_box_max[second][owner],
                    sample["pairs"][owner]["maxBoxOverlapDepth"],
                )
                pair_shared_triple_max[second][owner] = max(
                    pair_shared_triple_max[second][owner],
                    sample["pairs"][owner]["maxSharedTripleFraction"],
                )
                pair_shared_four_max[second][owner] = max(
                    pair_shared_four_max[second][owner],
                    sample["pairs"][owner]["maxSharedFourFraction"],
                )
    rows = []
    for second in range(WINDOW_SECONDS):
        row = {"second": second}
        for owner in (2, 3):
            metrics = {
                field: rounded(totals[second][owner][field] / max(covered[second], 1e-9))
                for field in STATE_FIELDS
            }
            shots = [event for event in shot_starts
                     if event["owner"] == owner and second <= event["t"] < second + 1]
            hits = [event for event in damage
                    if event["attacker_owner"] == owner and second <= event["t"] < second + 1]
            row[str(owner)] = {
                **metrics,
                "meanOverlapPairs": rounded(
                    pair_totals[second][owner]["overlapPairs"]
                    / max(covered[second], 1e-9)
                ),
                "meanPossiblePairs": rounded(
                    pair_totals[second][owner]["possiblePairs"]
                    / max(covered[second], 1e-9)
                ),
                "overlapPairShare": rounded(
                    pair_totals[second][owner]["overlapPairs"]
                    / max(pair_totals[second][owner]["possiblePairs"], 1e-9), 6
                ),
                "meanOverlappedUnits": rounded(
                    pair_totals[second][owner]["overlappedUnits"]
                    / max(covered[second], 1e-9)
                ),
                "overlappedUnitShare": rounded(
                    pair_totals[second][owner]["overlappedUnits"]
                    / max(pair_totals[second][owner]["alive"], 1e-9), 6
                ),
                "meanOverlapDepth": rounded(
                    pair_totals[second][owner]["overlapDepthSum"]
                    / max(pair_totals[second][owner]["overlapPairs"], 1e-9), 6
                ),
                "maxOverlapDepth": rounded(pair_max[second][owner], 6),
                "meanBoxOverlapPairs": rounded(
                    pair_totals[second][owner]["boxOverlapPairs"]
                    / max(covered[second], 1e-9)
                ),
                "meanBoxOverlappedUnits": rounded(
                    pair_totals[second][owner]["boxOverlappedUnits"]
                    / max(covered[second], 1e-9)
                ),
                "meanBoxOverlapDepth": rounded(
                    pair_totals[second][owner]["boxOverlapDepthSum"]
                    / max(pair_totals[second][owner]["boxOverlapPairs"], 1e-9), 6
                ),
                "meanBoxCommittedCommittedOverlapPairs": rounded(
                    pair_totals[second][owner]["boxCommittedCommittedOverlapPairs"]
                    / max(covered[second], 1e-9)
                ),
                "meanBoxCommittedCommittedOverlapDepth": rounded(
                    pair_totals[second][owner]["boxCommittedCommittedOverlapDepthSum"]
                    / max(pair_totals[second][owner]["boxCommittedCommittedOverlapPairs"], 1e-9), 6
                ),
                "meanBoxMixedOverlapPairs": rounded(
                    pair_totals[second][owner]["boxMixedOverlapPairs"]
                    / max(covered[second], 1e-9)
                ),
                "meanBoxMixedOverlapDepth": rounded(
                    pair_totals[second][owner]["boxMixedOverlapDepthSum"]
                    / max(pair_totals[second][owner]["boxMixedOverlapPairs"], 1e-9), 6
                ),
                "meanBoxUncommittedUncommittedOverlapPairs": rounded(
                    pair_totals[second][owner]["boxUncommittedUncommittedOverlapPairs"]
                    / max(covered[second], 1e-9)
                ),
                "meanBoxUncommittedUncommittedOverlapDepth": rounded(
                    pair_totals[second][owner]["boxUncommittedUncommittedOverlapDepthSum"]
                    / max(
                        pair_totals[second][owner]["boxUncommittedUncommittedOverlapPairs"],
                        1e-9,
                    ), 6
                ),
                "maxBoxOverlapDepth": rounded(pair_box_max[second][owner], 6),
                "meanTripleStacks": rounded(
                    pair_totals[second][owner]["tripleStacks"]
                    / max(covered[second], 1e-9)
                ),
                "meanFourStacks": rounded(
                    pair_totals[second][owner]["fourStacks"]
                    / max(covered[second], 1e-9)
                ),
                "maxSharedTripleFraction": rounded(
                    pair_shared_triple_max[second][owner], 6
                ),
                "maxSharedFourFraction": rounded(
                    pair_shared_four_max[second][owner], 6
                ),
                "meanNearestFriendlyDistance": rounded(
                    pair_totals[second][owner]["nearestDistanceSum"]
                    / max(pair_totals[second][owner]["nearestDistanceCount"], 1e-9), 6
                ),
                "shotStarts": len(shots),
                "uniqueShotStarters": len({event["id"] for event in shots}),
                "damageHits": len(hits),
                "uniqueDamageDealers": len({event["attacker"] for event in hits}),
            }
        rows.append(row)
    return rows


def decode_run(repeat: int):
    prefix = (
        CAPTURE_ROOT / f"run_{repeat:03d}" / "raw recordings" / MATCHUP_KEY
    )
    frames_path = Path(f"{prefix}.frames.bin")
    decoded_damage = group.decode_damage_from_frames(prefix)
    doc = entity_store = world_id = None
    samples = []
    shot_starts = []
    first_targets = {}
    windup_started_at = {}
    windup_target_changes = []
    pending_target_losses = {}
    target_reacquisitions = []
    opening_snapshots = {}
    prior = {}
    prior_t = None
    first_frame_t = None
    action_histogram = {2: Counter(), 3: Counter()}

    with frames_path.open("rb") as stream:
        while True:
            header = stream.read(4)
            if len(header) < 4:
                break
            (length,) = struct.unpack("<I", header)
            payload = stream.read(length)
            if len(payload) != length:
                break
            sequence = group.pb.FrameSequence()
            sequence.ParseFromString(payload)
            for frame in sequence.frame:
                patch = frame.patch
                if patch and len(patch) > SNAP_RESEED:
                    doc, entity_store, world_id = seed_snapshot(patch)
                    samples = []
                    shot_starts = []
                    first_targets = {}
                    windup_started_at = {}
                    windup_target_changes = []
                    pending_target_losses = {}
                    target_reacquisitions = []
                    opening_snapshots = {}
                    prior = {}
                    prior_t = None
                    first_frame_t = None
                    action_histogram = {2: Counter(), 3: Counter()}
                    continue
                if entity_store is None:
                    continue
                if patch:
                    group.D.apply_patch(doc, patch, entity_store, world_id)
                selected_all = {}
                all_expected = {**EXPECTED, **AUXILIARY_EXPECTED}
                for key, entity in merged_entities(doc, entity_store, world_id):
                    owner = entity.get(2)
                    master = entity.get(1)
                    if owner not in all_expected or master != all_expected[owner][0]:
                        continue
                    selected_all[key] = {
                        "key": key,
                        "id": entity.get(0),
                        "owner": owner,
                        "x": float(entity.get(3)),
                        "y": float(entity.get(4)),
                        "hp": float(entity.get(12)),
                        **action_of(doc, entity),
                    }
                selected = {
                    key: unit for key, unit in selected_all.items()
                    if unit["owner"] in EXPECTED
                }
                by_id = {
                    unit["id"]: key for key, unit in selected_all.items()
                    if unit.get("id") is not None
                }
                prior_by_id = {
                    unit["id"]: key for key, unit in prior.items()
                    if unit.get("id") is not None
                }
                if first_frame_t is None:
                    roster = Counter(unit["owner"] for unit in selected.values())
                    if roster != Counter({owner: value[1] for owner, value in EXPECTED.items()}):
                        continue
                    first_frame_t = frame.time / 1000.0
                t = frame.time / 1000.0 - first_frame_t
                if t > WINDOW_SECONDS + 0.25:
                    continue
                for marker in OPENING_SNAPSHOT_SECONDS:
                    if marker not in opening_snapshots and t >= marker:
                        opening_snapshots[marker] = {
                            "t": rounded(t, 6),
                            "units": sorted(({
                                "owner": unit["owner"],
                                "id": unit["id"],
                                "x": rounded(unit["x"], 6),
                                "y": rounded(unit["y"], 6),
                                "targetId": unit.get("target_id"),
                                "actionState": unit.get("action_state"),
                            } for unit in selected.values()),
                            key=lambda row: (row["owner"], row["id"])),
                        }
                dt = (frame.time / 1000.0 - prior_t) if prior_t is not None else 1 / 60
                counts = classify_frame(selected, prior, dt)
                samples.append({
                    "t": t,
                    "counts": counts,
                    "pairs": classify_pairs(selected),
                    "formation": classify_formation(selected),
                    "targetLoad": classify_target_load(selected),
                })
                for key, unit in selected.items():
                    state = unit.get("action_state")
                    action_histogram[unit["owner"]][str(state)] += 1
                    raw_target = unit.get("target_id")
                    target_key = raw_target if raw_target in selected else by_id.get(raw_target)
                    target = selected_all.get(target_key)
                    previous = prior.get(key)
                    previous_state = previous.get("action_state") if previous else None
                    previous_raw_target = previous.get("target_id") if previous else None
                    previous_target_key = (
                        previous_raw_target if previous_raw_target in prior
                        else prior_by_id.get(previous_raw_target)
                    )
                    previous_target = prior.get(previous_target_key)
                    previous_target_id = (
                        previous_target.get("id") if previous_target else None
                    )
                    current_target_id = target.get("id") if target else None
                    current_hostile_target_id = (
                        current_target_id
                        if target and target["owner"] != unit["owner"] else None
                    )
                    if (previous_target_id is not None
                            and previous_target_id != current_hostile_target_id):
                        old_target_key = (
                            previous_target_id if previous_target_id in selected_all
                            else by_id.get(previous_target_id)
                        )
                        old_target = selected_all.get(old_target_key)
                        target_died = old_target is None or old_target.get("hp", 0) <= 0
                        if target_died:
                            row = {
                                "owner": unit["owner"],
                                "id": unit["id"],
                                "fromTargetId": previous_target_id,
                                "lossSeconds": rounded(t, 6),
                                "stateBeforeLoss": previous_state,
                                "stateAtLoss": state,
                                "targetId": current_hostile_target_id,
                                "reacquireSeconds": (
                                    rounded(t, 6)
                                    if current_hostile_target_id is not None else None
                                ),
                                "delaySeconds": (
                                    0.0 if current_hostile_target_id is not None else None
                                ),
                                "stateAtReacquisition": (
                                    state if current_hostile_target_id is not None else None
                                ),
                            }
                            target_reacquisitions.append(row)
                            if current_hostile_target_id is None:
                                pending_target_losses[key] = row
                    pending = pending_target_losses.get(key)
                    if pending is not None and current_hostile_target_id is not None:
                        pending["targetId"] = current_hostile_target_id
                        pending["reacquireSeconds"] = rounded(t, 6)
                        pending["delaySeconds"] = rounded(t - pending["lossSeconds"], 6)
                        pending["stateAtReacquisition"] = state
                        pending_target_losses.pop(key, None)
                    if state == 7 and previous_state != 7:
                        windup_started_at[key] = t
                    elif state == 7 and previous_state == 7:
                        if (previous_target_id is not None
                                and current_target_id is not None
                                and previous_target_id != current_target_id
                                and target["owner"] != unit["owner"]):
                            windup_target_changes.append({
                                "owner": unit["owner"],
                                "id": unit["id"],
                                "fromTargetId": previous_target_id,
                                "targetId": current_target_id,
                                "changeSeconds": rounded(t, 6),
                                "elapsedWindupSeconds": rounded(
                                    t - windup_started_at.get(key, t), 6
                                ),
                                "releaseSeconds": None,
                                "remainingWindupSeconds": None,
                            })
                    if previous_state == 7 and state != 7:
                        started = windup_started_at.pop(key, None)
                        if started is not None:
                            for change in reversed(windup_target_changes):
                                if change["id"] != unit["id"]:
                                    continue
                                if change["releaseSeconds"] is not None:
                                    continue
                                if change["changeSeconds"] < started - 1e-9:
                                    break
                                change["releaseSeconds"] = rounded(t, 6)
                                change["remainingWindupSeconds"] = rounded(
                                    t - change["changeSeconds"], 6
                                )
                    if (key not in first_targets and target
                            and target["owner"] != unit["owner"]):
                        first_targets[key] = {
                            "t": rounded(t, 6),
                            "owner": unit["owner"],
                            "id": unit["id"],
                            "x": rounded(unit["x"], 6),
                            "y": rounded(unit["y"], 6),
                            "targetOwner": target["owner"],
                            "targetId": target["id"],
                            "targetX": rounded(target["x"], 6),
                            "targetY": rounded(target["y"], 6),
                        }
                    if state == 7 and prior.get(key, {}).get("action_state") != 7:
                        event = {
                            "t": t,
                            "owner": unit["owner"],
                            "id": unit["id"],
                            "rawTargetId": raw_target,
                        }
                        if target and target["owner"] != unit["owner"]:
                            mechanics = MECHANICS[unit["owner"]]
                            target_mechanics = MECHANICS[target["owner"]]
                            hostile_distances = [
                                math.hypot(candidate["x"] - unit["x"],
                                           candidate["y"] - unit["y"])
                                for candidate in selected_all.values()
                                if candidate["owner"] != unit["owner"]
                            ]
                            center_distance = math.hypot(
                                target["x"] - unit["x"], target["y"] - unit["y"]
                            )
                            edge_distance = (
                                center_distance - mechanics["outline"]
                                - target_mechanics["outline"]
                            )
                            event.update({
                                "targetId": target["id"],
                                "centerDistance": rounded(center_distance, 6),
                                "nearestHostileCenterDistance": rounded(
                                    min(hostile_distances), 6
                                ) if hostile_distances else None,
                                "hostilesInsideMinimumRange": sum(
                                    distance < mechanics.get("min_range", 0.0) - 1e-12
                                    for distance in hostile_distances
                                ),
                                "edgeDistance": rounded(edge_distance, 6),
                                "nominalRange": mechanics["range"],
                                "rangeUtilization": (
                                    rounded(edge_distance / mechanics["range"], 6)
                                    if mechanics["range"] > 0 else None
                                ),
                                "nominalHeadroom": rounded(
                                    mechanics["range"] - edge_distance, 6
                                ),
                            })
                        shot_starts.append(event)
                prior = selected
                prior_t = frame.time / 1000.0

    if first_frame_t is None or not samples:
        raise RuntimeError(f"{frames_path}: exact roster was not decoded")
    damage = [{**event, "t": event["t"] - first_frame_t} for event in decoded_damage]
    per_second = integrate_seconds(samples, shot_starts, damage)
    damage_by_owner = {}
    for owner in (2, 3):
        owner_rows = [event for event in damage if event["attacker_owner"] == owner]
        amounts = Counter(round(event["damage"], 4) for event in owner_rows)
        damage_by_owner[str(owner)] = {
            "hits": len(owner_rows),
            "damage": rounded(sum(event["damage"] for event in owner_rows)),
            "byAmount": {
                str(amount): count for amount, count in sorted(amounts.items())
            },
        }
    formation_per_second = []
    target_load_per_second = []
    for second in range(WINDOW_SECONDS):
        nearest_sample = min(samples, key=lambda sample: abs(sample["t"] - second))
        formation_per_second.append({
            "second": second,
            "sampleTime": rounded(nearest_sample["t"]),
            **nearest_sample["formation"],
        })
        target_load_per_second.append({
            "second": second,
            "sampleTime": rounded(nearest_sample["t"]),
            **nearest_sample["targetLoad"],
        })
    return {
        "repeat": repeat,
        "framesBin": str(frames_path),
        "framesBinBytes": frames_path.stat().st_size,
        "firstFrameGameSeconds": rounded(first_frame_t),
        "samples": len(samples),
        "firstDamageSeconds": rounded(min(event["t"] for event in damage)),
        "damageByOwner": damage_by_owner,
        "actionStateHistogram": {
            str(owner): dict(sorted(histogram.items()))
            for owner, histogram in action_histogram.items()
        },
        "firstTargets": sorted(
            first_targets.values(), key=lambda row: (row["owner"], row["id"])
        ),
        "openingSnapshots": [
            opening_snapshots[marker]
            for marker in OPENING_SNAPSHOT_SECONDS
            if marker in opening_snapshots
        ],
        "attackStartRanges": shot_starts,
        "windupTargetChanges": windup_target_changes,
        "targetReacquisitions": target_reacquisitions,
        "perSecond": per_second,
        "formationPerSecond": formation_per_second,
        "targetLoadPerSecond": target_load_per_second,
    }


def mean_per_second(runs: list[dict]):
    output = []
    for second in range(WINDOW_SECONDS):
        row = {"second": second}
        for owner in (2, 3):
            source_rows = [run["perSecond"][second][str(owner)] for run in runs]
            row[str(owner)] = {
                field: rounded(statistics.fmean(source[field] for source in source_rows))
                for field in source_rows[0]
            }
        output.append(row)
    return output


def window_summary(rows: list[dict], seconds: int):
    summary = {}
    for owner in (2, 3):
        selected = [row[str(owner)] for row in rows[:seconds]]
        alive_seconds = sum(row["alive"] for row in selected)
        summary[str(owner)] = {
            "meanAlive": rounded(statistics.fmean(row["alive"] for row in selected)),
            "meanActive": rounded(statistics.fmean(row["active"] for row in selected)),
            "meanFiring": rounded(statistics.fmean(row["firing"] for row in selected)),
            "meanNotFiring": rounded(
                statistics.fmean(row["notFiring"] for row in selected)
            ),
            "firingShareOfAlive": rounded(
                sum(row["firing"] for row in selected) / max(alive_seconds, 1e-9)
            ),
            "activeShareOfAlive": rounded(
                sum(row["active"] for row in selected) / max(alive_seconds, 1e-9)
            ),
            "meanInRangeNotFiring": rounded(
                statistics.fmean(row["inRangeNotFiring"] for row in selected)
            ),
            "meanSeekingMoving": rounded(
                statistics.fmean(row["seekingMoving"] for row in selected)
            ),
            "meanSeekingStationary": rounded(
                statistics.fmean(row["seekingStationary"] for row in selected)
            ),
            "seekingStationaryShareOfAlive": rounded(
                sum(row["seekingStationary"] for row in selected)
                / max(alive_seconds, 1e-9)
            ),
            "meanUntargetedStationary": rounded(
                statistics.fmean(row["untargetedStationary"] for row in selected)
            ),
            "shotStarts": rounded(sum(row["shotStarts"] for row in selected)),
            "damageHits": rounded(sum(row["damageHits"] for row in selected)),
        }
    return summary


def tidy_rows(live: list[dict], simulation: list[dict]):
    rows = []
    labels = {2: "Chinese Arbalesters", 3: "Saracen Heavy Cavalry Archers"}
    for source_name, source_rows in (("Live game", live), ("Simulation", simulation)):
        for second_row in source_rows:
            for owner in (2, 3):
                rows.append({
                    "second": second_row["second"],
                    "interval": f"{second_row['second']}-{second_row['second'] + 1}s",
                    "source": source_name,
                    "owner": owner,
                    "army": labels[owner],
                    **second_row[str(owner)],
                })
    return rows


def percentile(values: list[float], fraction: float):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_range_events(events: list[dict]):
    output = {}
    for owner in (2, 3):
        starts = [event for event in events if event["owner"] == owner]
        resolved = [event for event in starts if "edgeDistance" in event]
        edges = [event["edgeDistance"] for event in resolved]
        centers = [event["centerDistance"] for event in resolved]
        utilizations = [event["rangeUtilization"] for event in resolved]
        headrooms = [event["nominalHeadroom"] for event in resolved]
        output[str(owner)] = {
            "shotStarts": len(starts),
            "resolvedRangeSamples": len(resolved),
            "resolvedShare": rounded(len(resolved) / max(len(starts), 1)),
            "meanCenterDistance": rounded(statistics.fmean(centers)) if centers else None,
            "meanEdgeDistance": rounded(statistics.fmean(edges)) if edges else None,
            "medianEdgeDistance": rounded(statistics.median(edges)) if edges else None,
            "p10EdgeDistance": rounded(percentile(edges, 0.10)) if edges else None,
            "p90EdgeDistance": rounded(percentile(edges, 0.90)) if edges else None,
            "meanRangeUtilization": (
                rounded(statistics.fmean(utilizations)) if utilizations else None
            ),
            "meanNominalHeadroom": (
                rounded(statistics.fmean(headrooms)) if headrooms else None
            ),
            "beyondNominalShare": rounded(
                sum(value < 0 for value in headrooms) / max(len(headrooms), 1)
            ),
        }
    return output


def range_rows(live_runs: list[dict], simulation_runs: list[dict]):
    labels = {2: "Chinese Arbalesters", 3: "Saracen Heavy Cavalry Archers"}
    live_events = [
        {**event, "run": run["repeat"]}
        for run in live_runs for event in run["attackStartRanges"]
    ]
    simulation_events = [
        {**event, "run": run["openingSeed"]}
        for run in simulation_runs for event in run["attackStartRanges"]
    ]
    per_second = []
    for source, events in (("Live game", live_events), ("Simulation", simulation_events)):
        for second in range(WINDOW_SECONDS):
            for owner in (2, 3):
                selected = [
                    event for event in events
                    if event["owner"] == owner and second <= event.get("t", event.get("second")) < second + 1
                    and "edgeDistance" in event
                ]
                edges = [event["edgeDistance"] for event in selected]
                per_second.append({
                    "second": second,
                    "interval": f"{second}-{second + 1}s",
                    "source": source,
                    "owner": owner,
                    "army": labels[owner],
                    "rangeSamples": len(selected),
                    "meanCenterDistance": (
                        rounded(statistics.fmean(event["centerDistance"] for event in selected))
                        if selected else None
                    ),
                    "meanEdgeDistance": (
                        rounded(statistics.fmean(edges)) if edges else None
                    ),
                    "p10EdgeDistance": rounded(percentile(edges, 0.10)) if edges else None,
                    "p90EdgeDistance": rounded(percentile(edges, 0.90)) if edges else None,
                    "nominalRange": MECHANICS[owner]["range"],
                })
    return {
        "definition": (
            "Distance at transition into attack windup/attack-start. Center distance is "
            "actor center to target center; edge distance subtracts both outline radii."
        ),
        "live": summarize_range_events(live_events),
        "simulation": summarize_range_events(simulation_events),
        "perSecond": per_second,
        "events": [
            {**event, "source": source}
            for source, events in (("Live game", live_events), ("Simulation", simulation_events))
            for event in events
        ],
    }


def main():
    if not SIMULATION_SOURCE.exists():
        raise SystemExit(f"missing fresh simulation export: {SIMULATION_SOURCE}")
    single_run = "--single-run" in sys.argv
    run_numbers = [1] if single_run else list(range(1, 6))
    simulation = json.loads(SIMULATION_SOURCE.read_text(encoding="utf-8"))
    simulation_runs = simulation["runs"][:1] if single_run else simulation["runs"]
    live_runs = [decode_run(repeat) for repeat in run_numbers]
    live_mean = mean_per_second(live_runs)
    sim_mean = (
        simulation_runs[0]["perSecond"] if single_run else simulation["meanPerSecond"]
    )
    comparison = {
        "schemaVersion": 2,
        "generatedAt": simulation["generatedAt"],
        "matchup": simulation["matchup"],
        "timeAlignment": (
            "second 0 begins at the first full exact-roster gRPC frame in live runs "
            "and engine tick 0 in simulation"
        ),
        "metricDefinition": {
            **simulation["metricDefinition"],
            "liveActionMapping": "Action.state 7=windup/fire; 6=reload; both require a live hostile target inside the DAT attack envelope",
            "strictlyFiring": "living unit in Action.state 7 / simulation attacking state with a resolved hostile target inside the attack envelope",
            "notFiring": "living units minus strictlyFiring; reload, pursuit, in-range idle, and no-target states are retained as reasons",
            "engagementRange": "distance at the transition into Action.state 7 / attack-start; edge distance subtracts both units' outline radii",
            "movementThreshold": "speed > 0.05 tiles/s between adjacent full-rate states",
            "aggregation": (
                "time-weighted mean concurrent living-unit count per one-second interval; "
                + ("single live run 1 versus simulation seed 0" if single_run else "mean across five runs/seeds")
            ),
        },
        "sources": {
            "liveFrames": [
                {
                    "run": repeat,
                    "path": str(
                        CAPTURE_ROOT / f"run_{repeat:03d}" / "raw recordings"
                        / f"{MATCHUP_KEY}.frames.bin"
                    ),
                }
                for repeat in run_numbers
            ],
            "simulation": str(SIMULATION_SOURCE),
        },
        "liveRuns": live_runs,
        "simulationRuns": simulation_runs,
        "liveMeanPerSecond": live_mean,
        "simulationMeanPerSecond": sim_mean,
        "tidyRows": tidy_rows(live_mean, sim_mean),
        "windowSummary": {
            str(seconds): {
                "live": window_summary(live_mean, seconds),
                "simulation": window_summary(sim_mean, seconds),
            }
            for seconds in (5, 10, 20)
        },
        "engagementRange": range_rows(live_runs, simulation_runs),
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / "engagement_participation_comparison.json"
    output.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
