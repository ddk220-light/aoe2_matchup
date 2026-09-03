"""Measure opening target, movement, engagement, and overlap variance in live melee tapes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import statistics
import struct
import sys


SCRIPT = Path(__file__).resolve()
JS_SIMULATION = SCRIPT.parents[1]
REPO_ROOT = JS_SIMULATION.parents[1]
GRPC_DIR = REPO_ROOT / "aoe2x" / "grpc"
sys.path.insert(0, str(GRPC_DIR))

import cade_api_pb2 as pb  # noqa: E402
import decode_state_v2 as D  # noqa: E402

from analyze_live_melee_1v1 import action_of, merged_entities, seed_snapshot  # noqa: E402


SNAP_RESEED = 400_000
EXPECTED = {2: (567, 23), 3: (359, 27)}
COLLISION_RADIUS = {2: 0.2, 3: 0.2}


def read_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def quantiles(values):
    if not values:
        return {"min": None, "median": None, "mean": None, "max": None}
    return {
        "min": round(min(values), 4),
        "median": round(statistics.median(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "max": round(max(values), 4),
    }


def load_slots():
    fixture = json.loads((JS_SIMULATION / "fixtures" / "golden_formation_27v27.json")
                         .read_text(encoding="utf-8"))
    return {
        owner: [(float(row["position"]["x"]), float(row["position"]["y"]))
                for row in fixture["sides"][str(owner)]]
        for owner in (2, 3)
    }


def nearest_slot(position, slots, limit):
    ranked = sorted(
        ((math.hypot(position[0] - x, position[1] - y), index + 1)
         for index, (x, y) in enumerate(slots[:limit])),
        key=lambda row: row[0],
    )
    if not ranked or ranked[0][0] > 1e-4:
        raise RuntimeError(f"initial position {position} does not match a golden slot")
    return ranked[0][1]


def decode_damage_from_frames(prefix: Path):
    """Reconstruct melee hit rows from full-rate HP deltas and action targets.

    Fresh live captures do not have the archive-era decoded damage sidecar. The
    raw stream remains authoritative: each HP drop supplies the victim, amount,
    and time, while the current/recent action target (or EntityKilled event)
    identifies the attacker. Simultaneous deltas are expanded using the modal
    per-hit damage for that victim side.
    """
    path = Path(f"{prefix}.frames.bin")
    doc = entity_store = world_id = None
    prior = {}
    raw_drops = []

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
                    prior = {}
                    continue
                if entity_store is None:
                    continue
                if patch:
                    D.apply_patch(doc, patch, entity_store, world_id)
                selected = {}
                for key, entity in merged_entities(doc, entity_store, world_id):
                    owner = entity.get(2)
                    master = entity.get(1)
                    if owner not in EXPECTED or master != EXPECTED[owner][0]:
                        continue
                    selected[key] = {
                        "key": key,
                        "id": entity.get(0),
                        "owner": owner,
                        "x": float(entity.get(3)),
                        "y": float(entity.get(4)),
                        "hp": float(entity.get(12)),
                        **action_of(doc, entity),
                    }
                expected_counts = Counter({owner: row[1] for owner, row in EXPECTED.items()})
                if not prior and Counter(unit["owner"] for unit in selected.values()) \
                        != expected_counts:
                    continue
                by_id = {unit["id"]: key for key, unit in selected.items()}
                prior_by_id = {unit["id"]: key for key, unit in prior.items()}
                killed = {
                    event.entityKilled.id: event.entityKilled.killerId
                    for event in frame.event if event.HasField("entityKilled")
                }
                recorded_victims = set()
                for key, unit in selected.items():
                    before = prior.get(key)
                    if not before or unit["hp"] >= before["hp"] - 1e-9:
                        continue
                    recorded_victims.add(unit["id"])
                    candidates = []
                    for attacker_key, attacker in selected.items():
                        if attacker["owner"] == unit["owner"]:
                            continue
                        raw_target = attacker.get("target_id")
                        target_key = raw_target if raw_target in selected else by_id.get(raw_target)
                        previous = prior.get(attacker_key, {})
                        previous_raw_target = previous.get("target_id")
                        previous_target_key = (previous_raw_target if previous_raw_target in prior
                                               else prior_by_id.get(previous_raw_target))
                        if target_key != key and previous_target_key != key:
                            continue
                        score = (
                            int(previous.get("action_state") == 7),
                            int(attacker.get("action_state") == 7),
                            -math.hypot(attacker["x"] - unit["x"], attacker["y"] - unit["y"]),
                            -int(attacker["id"]),
                        )
                        candidates.append((score, attacker["id"]))
                    candidates.sort(reverse=True)
                    killer_id = killed.get(unit["id"])
                    attacker_ids = [candidate[1] for candidate in candidates]
                    if killer_id is not None:
                        attacker_ids = [killer_id, *[value for value in attacker_ids
                                                    if value != killer_id]]
                    if not attacker_ids:
                        enemies = [attacker for attacker in selected.values()
                                   if attacker["owner"] != unit["owner"]]
                        # A lethal projectile can resolve on the same frame
                        # that its firing side's last live entity disappears
                        # from the merged state. The previous frame is still
                        # authoritative for nearest-enemy attribution.
                        if not enemies:
                            enemies = [attacker for attacker in prior.values()
                                       if attacker["owner"] != unit["owner"]]
                        enemies.sort(key=lambda attacker: math.hypot(
                            attacker["x"] - unit["x"], attacker["y"] - unit["y"]))
                        attacker_ids = [attacker["id"] for attacker in enemies[:1]]
                    if not attacker_ids:
                        # Retain the HP drop in the raw outcome timeline but
                        # omit an event whose attacker cannot be supported by
                        # either adjacent full-rate state.
                        continue
                    raw_drops.append({
                        "t": frame.time / 1000.0,
                        "attacker_ids": attacker_ids,
                        "victim": unit["id"],
                        "victim_owner": unit["owner"],
                        "damage": before["hp"] - unit["hp"],
                        "kill": unit["id"] in killed,
                    })
                for victim_id, killer_id in killed.items():
                    if victim_id in recorded_victims:
                        continue
                    victim_key = prior_by_id.get(victim_id)
                    victim = prior.get(victim_key)
                    if not victim:
                        continue
                    raw_drops.append({
                        "t": frame.time / 1000.0,
                        "attacker_ids": [killer_id],
                        "victim": victim_id,
                        "victim_owner": victim["owner"],
                        "damage": victim["hp"],
                        "kill": True,
                    })
                prior = selected

    if not raw_drops:
        raise RuntimeError(f"{prefix}: no HP drops decoded")
    modal_damage = {}
    for owner in (2, 3):
        values = Counter(round(row["damage"], 3) for row in raw_drops
                         if row["victim_owner"] == owner and row["damage"] > 0)
        modal_damage[owner] = values.most_common(1)[0][0] if values else None
    events = []
    for row in raw_drops:
        base = modal_damage[row["victim_owner"]]
        hits = max(1, int(round(row["damage"] / base))) if base and base > 0 else 1
        if abs(row["damage"] - hits * base) > max(0.25, base * 0.15):
            hits = 1
        for index in range(hits):
            events.append({
                "t": row["t"],
                "attacker": row["attacker_ids"][index % len(row["attacker_ids"])],
                "attacker_owner": 3 if row["victim_owner"] == 2 else 2,
                "victim": row["victim"],
                "victim_owner": row["victim_owner"],
                "damage": round(row["damage"] / hits, 4),
                "kill": row["kill"] and index == hits - 1,
            })
    events.sort(key=lambda row: (row["t"], row["victim"], row["attacker"]))
    return events


def decode_frames(prefix: Path, damage, slots):
    first_damage_t = damage[0]["t"] if damage else math.inf
    first_outgoing = {}
    for event in damage:
        first_outgoing.setdefault(event["attacker"], event["t"])

    path = Path(f"{prefix}.frames.bin")
    doc = entity_store = world_id = None
    identity = {}
    units_state = {}
    first_frame_t = None
    last_frame_t = None
    frames = 0
    frame_hz_times = []
    prior_t = None
    full_snapshots = 0
    stats = {}
    first_ai_order_t = None
    target_presence_frames = 0
    target_unit_frames = 0
    overlap = {
        phase: {
            "frames": 0,
            "allied_pair_sum": 0,
            "cross_pair_sum": 0,
            "frames_with_allied_overlap": 0,
            "frames_with_cross_overlap": 0,
            "peak_allied_pairs": 0,
            "peak_cross_pairs": 0,
            "maximum_allied_penetration": 0.0,
            "maximum_cross_penetration": 0.0,
            "allied_units": set(),
            "cross_units": set(),
        }
        for phase in ("pre_damage", "opening_2s", "whole_fight")
    }

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
                if first_ai_order_t is None and any(
                        command.WhichOneof("command") == "aiOrder"
                        for command in frame.command):
                    first_ai_order_t = frame.time / 1000.0
                patch = frame.patch
                if patch and len(patch) > SNAP_RESEED:
                    doc, entity_store, world_id = seed_snapshot(patch)
                    identity = {}
                    units_state = {}
                    stats = {}
                    first_frame_t = None
                    prior_t = None
                    full_snapshots += 1
                    continue
                if entity_store is None:
                    continue
                if patch:
                    D.apply_patch(doc, patch, entity_store, world_id)
                t = frame.time / 1000.0
                if first_frame_t is None:
                    first_frame_t = t
                last_frame_t = t
                if prior_t is not None and 0 < t - prior_t < 1:
                    frame_hz_times.append(t - prior_t)
                prior_t = t

                selected = {}
                for key, entity in merged_entities(doc, entity_store, world_id):
                    owner = entity.get(2)
                    master = entity.get(1)
                    if owner not in EXPECTED or master != EXPECTED[owner][0]:
                        continue
                    selected[key] = {
                        "key": key,
                        "id": entity.get(0),
                        "owner": owner,
                        "master": master,
                        "x": float(entity.get(3)),
                        "y": float(entity.get(4)),
                        "hp": float(entity.get(12)),
                        **action_of(doc, entity),
                    }
                if not selected:
                    continue
                frames += 1

                if not identity:
                    counts = Counter(unit["owner"] for unit in selected.values())
                    if counts != Counter({owner: row[1] for owner, row in EXPECTED.items()}):
                        continue
                    for key, unit in selected.items():
                        slot = nearest_slot(
                            (unit["x"], unit["y"]), slots[unit["owner"]],
                            EXPECTED[unit["owner"]][1],
                        )
                        identity[key] = {
                            "id": unit["id"], "owner": unit["owner"], "slot": slot,
                        }
                        stats[key] = {
                            **identity[key],
                            "initial": [unit["x"], unit["y"]],
                            "last": [unit["x"], unit["y"]],
                            "path_total": 0.0,
                            "path_before_first_damage": 0.0,
                            "first_target_t": None,
                            "first_target_key": None,
                            "first_target_distance": None,
                            "target_changes_before_damage": 0,
                            "last_enemy_target_key": None,
                            "contact_target_key": None,
                            "contact_target_t": None,
                            "first_attack_state_t": None,
                            "movement_start_t": None,
                            "waypoint_3s": None,
                            "waypoint_4_5s": None,
                        }

                by_id = {unit["id"]: key for key, unit in selected.items()}
                for key, unit in selected.items():
                    if key not in stats:
                        continue
                    record = stats[key]
                    step = math.hypot(unit["x"] - record["last"][0],
                                      unit["y"] - record["last"][1])
                    record["path_total"] += step
                    if t <= first_outgoing.get(unit["id"], first_damage_t):
                        record["path_before_first_damage"] += step
                    record["last"] = [unit["x"], unit["y"]]
                    elapsed = t - first_frame_t
                    if record["movement_start_t"] is None and math.hypot(
                            unit["x"] - record["initial"][0],
                            unit["y"] - record["initial"][1]) > 0.01:
                        record["movement_start_t"] = elapsed
                    if record["waypoint_3s"] is None and elapsed >= 3.0:
                        record["waypoint_3s"] = [unit["x"], unit["y"]]
                    if record["waypoint_4_5s"] is None and elapsed >= 4.5:
                        record["waypoint_4_5s"] = [unit["x"], unit["y"]]
                    if record["first_attack_state_t"] is None \
                            and unit.get("action_state") == 7:
                        record["first_attack_state_t"] = t

                    raw_target = unit.get("target_id")
                    target_key = raw_target if raw_target in selected else by_id.get(raw_target)
                    if raw_target is not None:
                        target_presence_frames += 1
                    if target_key in selected:
                        target_unit_frames += 1
                    if target_key in selected \
                            and selected[target_key]["owner"] != unit["owner"]:
                        if record["first_target_t"] is None:
                            target = selected[target_key]
                            record["first_target_t"] = t
                            record["first_target_key"] = target_key
                            record["first_target_distance"] = math.hypot(
                                unit["x"] - target["x"], unit["y"] - target["y"])
                        if t <= first_damage_t and record["last_enemy_target_key"] is not None \
                                and record["last_enemy_target_key"] != target_key:
                            record["target_changes_before_damage"] += 1
                        if t <= first_damage_t and record["contact_target_key"] != target_key:
                            record["contact_target_key"] = target_key
                            record["contact_target_t"] = t
                        record["last_enemy_target_key"] = target_key

                live = list(selected.values())
                allied_pairs = cross_pairs = 0
                allied_penetration = cross_penetration = 0.0
                allied_units = set()
                cross_units = set()
                for left_index, left in enumerate(live):
                    for right in live[left_index + 1:]:
                        threshold = COLLISION_RADIUS[left["owner"]] + COLLISION_RADIUS[right["owner"]]
                        penetration = threshold - math.hypot(
                            left["x"] - right["x"], left["y"] - right["y"])
                        if penetration <= 1e-9:
                            continue
                        if left["owner"] == right["owner"]:
                            allied_pairs += 1
                            allied_penetration = max(allied_penetration, penetration)
                            allied_units.update((left["key"], right["key"]))
                        else:
                            cross_pairs += 1
                            cross_penetration = max(cross_penetration, penetration)
                            cross_units.update((left["key"], right["key"]))
                phases = ["whole_fight"]
                if t <= first_damage_t:
                    phases.append("pre_damage")
                if t <= first_damage_t + 2.0:
                    phases.append("opening_2s")
                for phase in phases:
                    row = overlap[phase]
                    row["frames"] += 1
                    row["allied_pair_sum"] += allied_pairs
                    row["cross_pair_sum"] += cross_pairs
                    row["frames_with_allied_overlap"] += int(allied_pairs > 0)
                    row["frames_with_cross_overlap"] += int(cross_pairs > 0)
                    row["peak_allied_pairs"] = max(row["peak_allied_pairs"], allied_pairs)
                    row["peak_cross_pairs"] = max(row["peak_cross_pairs"], cross_pairs)
                    row["maximum_allied_penetration"] = max(
                        row["maximum_allied_penetration"], allied_penetration)
                    row["maximum_cross_penetration"] = max(
                        row["maximum_cross_penetration"], cross_penetration)
                    row["allied_units"].update(allied_units)
                    row["cross_units"].update(cross_units)

    expected_counts = Counter({owner: row[1] for owner, row in EXPECTED.items()})
    if not identity or Counter(row["owner"] for row in identity.values()) != expected_counts:
        raise RuntimeError(f"{prefix}: did not decode the expected roster {dict(expected_counts)}")

    output_units = []
    for key, record in sorted(stats.items(), key=lambda item: (item[1]["owner"], item[1]["slot"])):
        target = identity.get(record["first_target_key"])
        contact_target = identity.get(record["contact_target_key"])
        first_out = first_outgoing.get(record["id"])
        output_units.append({
            "owner": record["owner"],
            "slot": record["slot"],
            "id": record["id"],
            "first_target_owner": target["owner"] if target else None,
            "first_target_slot": target["slot"] if target else None,
            "first_target_t": (round(record["first_target_t"] - first_frame_t, 4)
                               if record["first_target_t"] is not None else None),
            "first_target_distance": (round(record["first_target_distance"], 4)
                                      if record["first_target_distance"] is not None else None),
            "contact_target_owner": contact_target["owner"] if contact_target else None,
            "contact_target_slot": contact_target["slot"] if contact_target else None,
            "contact_target_t": (round(record["contact_target_t"] - first_frame_t, 4)
                                 if record["contact_target_t"] is not None else None),
            "target_changes_before_first_damage": record["target_changes_before_damage"],
            "first_attack_state_t": (round(record["first_attack_state_t"] - first_frame_t, 4)
                                     if record["first_attack_state_t"] is not None else None),
            "first_damage_dealt_t": (round(first_out - first_frame_t, 4)
                                     if first_out is not None else None),
            "path_before_first_damage_dealt": round(record["path_before_first_damage"], 4),
            "path_total": round(record["path_total"], 4),
            "movement_start_t": (round(record["movement_start_t"], 4)
                                 if record["movement_start_t"] is not None else None),
            "waypoint_3s": ({"x": round(record["waypoint_3s"][0], 4),
                              "y": round(record["waypoint_3s"][1], 4)}
                             if record["waypoint_3s"] is not None else None),
            "waypoint_4_5s": ({"x": round(record["waypoint_4_5s"][0], 4),
                                "y": round(record["waypoint_4_5s"][1], 4)}
                               if record["waypoint_4_5s"] is not None else None),
        })

    def overlap_output(row):
        frames_count = row["frames"] or 1
        return {
            "frames": row["frames"],
            "mean_allied_pairs": round(row["allied_pair_sum"] / frames_count, 4),
            "mean_cross_pairs": round(row["cross_pair_sum"] / frames_count, 4),
            "allied_overlap_frame_share": round(
                row["frames_with_allied_overlap"] / frames_count, 4),
            "cross_overlap_frame_share": round(
                row["frames_with_cross_overlap"] / frames_count, 4),
            "peak_allied_pairs": row["peak_allied_pairs"],
            "peak_cross_pairs": row["peak_cross_pairs"],
            "maximum_allied_penetration": round(row["maximum_allied_penetration"], 4),
            "maximum_cross_penetration": round(row["maximum_cross_penetration"], 4),
            "allied_units_ever_overlapping": len(row["allied_units"]),
            "cross_units_ever_overlapping": len(row["cross_units"]),
        }

    acquisition = {}
    for owner in (2, 3):
        rows = [row for row in output_units if row["owner"] == owner]
        targets = Counter(row["first_target_slot"] for row in rows
                          if row["first_target_slot"] is not None)
        acquisition[f"side{owner}"] = {
            "units": len(rows),
            "units_with_enemy_target": sum(targets.values()),
            "unique_first_targets": len(targets),
            "maximum_units_sharing_first_target": max(targets.values(), default=0),
            "first_target_times": quantiles(
                [row["first_target_t"] for row in rows if row["first_target_t"] is not None]),
            "first_target_distances": quantiles(
                [row["first_target_distance"] for row in rows
                 if row["first_target_distance"] is not None]),
            "target_changes_before_first_damage": sum(
                row["target_changes_before_first_damage"] for row in rows),
            "target_slot_counts": {str(slot): count for slot, count in sorted(targets.items())},
        }

    first = damage[0]
    identities_by_id = {row["id"]: row for row in identity.values()}
    first_attacker = identities_by_id.get(first["attacker"])
    first_victim = identities_by_id.get(first["victim"])
    opening_damage = [row for row in damage if row["t"] <= first["t"] + 2.0]
    engagement_edges = Counter()
    for event in opening_damage:
        attacker = identities_by_id.get(event["attacker"])
        victim = identities_by_id.get(event["victim"])
        if attacker and victim:
            engagement_edges[(attacker["owner"], attacker["slot"],
                              victim["owner"], victim["slot"])] += 1

    hz = 1.0 / statistics.fmean(frame_hz_times) if frame_hz_times else None
    return {
        "frames_bin": str(path),
        "frames_bin_bytes": path.stat().st_size,
        "full_snapshots": full_snapshots,
        "frames": frames,
        "stream_hz": round(hz, 2) if hz else None,
        "duration_game_s": round((last_frame_t or 0) - (first_frame_t or 0), 4),
        "elimination_t_game_s": round(damage[-1]["t"] - first_frame_t, 4),
        "damage_events": len(damage),
        "first_ai_order_t_game_s": (round(first_ai_order_t, 4)
                                    if first_ai_order_t is not None else None),
        "first_damage": {
            "t_game_s": round(first["t"] - first_frame_t, 4),
            "attacker_owner": first_attacker["owner"],
            "attacker_slot": first_attacker["slot"],
            "victim_owner": first_victim["owner"],
            "victim_slot": first_victim["slot"],
            "damage": first["damage"],
        },
        "first_two_game_seconds": {
            "hits": len(opening_damage),
            "unique_attackers": len({row["attacker"] for row in opening_damage}),
            "unique_victims": len({row["victim"] for row in opening_damage}),
            "unique_engagement_pairs": len(engagement_edges),
            "hits_by_side": {
                str(owner): sum(row["attacker_owner"] == owner for row in opening_damage)
                for owner in (2, 3)
            },
            "engagement_edges": [
                {"attacker_owner": edge[0], "attacker_slot": edge[1],
                 "victim_owner": edge[2], "victim_slot": edge[3], "hits": count}
                for edge, count in sorted(engagement_edges.items())
            ],
        },
        "target_signal": {
            "frames_with_any_action_target": target_presence_frames,
            "frames_resolved_to_a_live_unit": target_unit_frames,
        },
        "acquisition": acquisition,
        "overlap": {phase: overlap_output(row) for phase, row in overlap.items()},
        "units": output_units,
    }


def summarize_runs(runs):
    first_target_by_unit = defaultdict(set)
    edge_counts = Counter()
    for run in runs:
        for unit in run["units"]:
            key = (unit["owner"], unit["slot"])
            target = unit["first_target_slot"]
            if target is not None:
                first_target_by_unit[key].add(target)
                edge_counts[(unit["owner"], unit["slot"], target)] += 1
    stable = sum(len(targets) == 1 for targets in first_target_by_unit.values())
    observed = len(first_target_by_unit)
    return {
        "runs": len(runs),
        "first_damage_attacker_slots": [run["first_damage"]["attacker_slot"] for run in runs],
        "first_damage_victim_slots": [run["first_damage"]["victim_slot"] for run in runs],
        "first_damage_times_game_s": quantiles(
            [run["first_damage"]["t_game_s"] for run in runs]),
        "opening_hits": quantiles([run["first_two_game_seconds"]["hits"] for run in runs]),
        "opening_unique_engagement_pairs": quantiles(
            [run["first_two_game_seconds"]["unique_engagement_pairs"] for run in runs]),
        "pre_damage_peak_allied_overlap_pairs": quantiles(
            [run["overlap"]["pre_damage"]["peak_allied_pairs"] for run in runs]),
        "opening_peak_allied_overlap_pairs": quantiles(
            [run["overlap"]["opening_2s"]["peak_allied_pairs"] for run in runs]),
        "opening_peak_cross_overlap_pairs": quantiles(
            [run["overlap"]["opening_2s"]["peak_cross_pairs"] for run in runs]),
        "first_target_stability": {
            "unit_slots_with_resolved_target": observed,
            "same_target_in_all_observed_runs": stable,
            "varied_target_across_runs": observed - stable,
            "stable_share": round(stable / observed, 4) if observed else None,
        },
        "most_repeated_first_target_edges": [
            {"owner": edge[0], "slot": edge[1], "target_slot": edge[2], "runs": count}
            for edge, count in edge_counts.most_common(15)
        ],
    }


def main():
    global EXPECTED, COLLISION_RADIUS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--stem", default="spanish_champion_vs_halberdier")
    parser.add_argument("--matchup", default="23 Spanish Champions vs 27 Spanish Halberdiers")
    parser.add_argument("--side2-master", type=int, default=567)
    parser.add_argument("--side2-count", type=int, default=23)
    parser.add_argument("--side2-slug", default="champion")
    parser.add_argument("--side2-radius", type=float, default=0.2)
    parser.add_argument("--side3-master", type=int, default=359)
    parser.add_argument("--side3-count", type=int, default=27)
    parser.add_argument("--side3-slug", default="halberdier")
    parser.add_argument("--side3-radius", type=float, default=0.2)
    args = parser.parse_args()
    EXPECTED = {
        2: (args.side2_master, args.side2_count),
        3: (args.side3_master, args.side3_count),
    }
    COLLISION_RADIUS = {2: args.side2_radius, 3: args.side3_radius}
    slots = load_slots()
    runs = []
    for index in range(1, 6):
        run_dir = args.capture_root / f"run_{index:03d}"
        prefix = run_dir / "raw recordings" / args.stem
        decoded_damage = run_dir / "decoded" / f"{args.stem}.damage.jsonl.gz"
        damage = (read_jsonl_gz(decoded_damage) if decoded_damage.exists()
                  else decode_damage_from_frames(prefix))
        run = {"repeat": index, **decode_frames(prefix, damage, slots)}
        output = run_dir / "grpc_opening_variance.json"
        output.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        runs.append(run)
        print(json.dumps({
            "repeat": index,
            "first_damage": run["first_damage"],
            "side2_acquisition": run["acquisition"]["side2"],
            "pre_damage_overlap": run["overlap"]["pre_damage"],
        }, sort_keys=True))
    report = {
        "schema_version": 1,
        "matchup": args.matchup,
        "collision_radius_tiles": {
            args.side2_slug: args.side2_radius,
            args.side3_slug: args.side3_radius,
        },
        "damage_derivation": ("decoded damage sidecars when present; otherwise full-rate "
                              "HP deltas attributed by action target and kill events"),
        "clock": "raw gRPC game seconds",
        "runs": runs,
        "summary": summarize_runs(runs),
    }
    (args.capture_root / "grpc_opening_variance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
