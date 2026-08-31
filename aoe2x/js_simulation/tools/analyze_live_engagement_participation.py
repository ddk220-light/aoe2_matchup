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
SNAP_RESEED = 400_000
EXPECTED = {2: (492, 27), 3: (474, 18)}
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
        nearest = {unit["id"]: math.inf for unit in units}
        overlap_pairs = 0
        overlap_depth_sum = 0.0
        max_overlap_depth = 0.0
        overlapped = set()
        for left_index, left in enumerate(units):
            for right in units[left_index + 1:]:
                distance = math.hypot(right["x"] - left["x"], right["y"] - left["y"])
                nearest[left["id"]] = min(nearest[left["id"]], distance)
                nearest[right["id"]] = min(nearest[right["id"]], distance)
                overlap_depth = (
                    MECHANICS[left["owner"]]["collision"]
                    + MECHANICS[right["owner"]]["collision"] - distance
                )
                if overlap_depth > 1e-12:
                    overlap_pairs += 1
                    overlap_depth_sum += overlap_depth
                    max_overlap_depth = max(max_overlap_depth, overlap_depth)
                    overlapped.add(left["id"])
                    overlapped.add(right["id"])
        nearest_values = [value for value in nearest.values() if math.isfinite(value)]
        output[owner] = {
            "alive": len(units),
            "possiblePairs": len(units) * (len(units) - 1) / 2,
            "overlapPairs": overlap_pairs,
            "overlapDepthSum": overlap_depth_sum,
            "maxOverlapDepth": max_overlap_depth,
            "overlappedUnits": len(overlapped),
            "nearestDistanceSum": sum(nearest_values),
            "nearestDistanceCount": len(nearest_values),
        }
    return output


def integrate_seconds(samples: list[dict], shot_starts: list[dict], damage: list[dict]):
    totals = [empty_counts() for _ in range(WINDOW_SECONDS)]
    pair_fields = (
        "alive", "possiblePairs", "overlapPairs", "overlapDepthSum",
        "overlappedUnits", "nearestDistanceSum", "nearestDistanceCount",
    )
    pair_totals = [
        {owner: {field: 0.0 for field in pair_fields} for owner in (2, 3)}
        for _ in range(WINDOW_SECONDS)
    ]
    pair_max = [{owner: 0.0 for owner in (2, 3)} for _ in range(WINDOW_SECONDS)]
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
                    prior = {}
                    prior_t = None
                    first_frame_t = None
                    action_histogram = {2: Counter(), 3: Counter()}
                    continue
                if entity_store is None:
                    continue
                if patch:
                    group.D.apply_patch(doc, patch, entity_store, world_id)
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
                if first_frame_t is None:
                    roster = Counter(unit["owner"] for unit in selected.values())
                    if roster != Counter({owner: value[1] for owner, value in EXPECTED.items()}):
                        continue
                    first_frame_t = frame.time / 1000.0
                t = frame.time / 1000.0 - first_frame_t
                if t > WINDOW_SECONDS + 0.25:
                    continue
                dt = (frame.time / 1000.0 - prior_t) if prior_t is not None else 1 / 60
                counts = classify_frame(selected, prior, dt)
                samples.append({"t": t, "counts": counts, "pairs": classify_pairs(selected)})
                for key, unit in selected.items():
                    state = unit.get("action_state")
                    action_histogram[unit["owner"]][str(state)] += 1
                    if state == 7 and prior.get(key, {}).get("action_state") != 7:
                        event = {"t": t, "owner": unit["owner"], "id": unit["id"]}
                        raw_target = unit.get("target_id")
                        target_key = raw_target if raw_target in selected else by_id.get(raw_target)
                        target = selected.get(target_key)
                        if target and target["owner"] != unit["owner"]:
                            mechanics = MECHANICS[unit["owner"]]
                            target_mechanics = MECHANICS[target["owner"]]
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
                                "edgeDistance": rounded(edge_distance, 6),
                                "nominalRange": mechanics["range"],
                                "rangeUtilization": rounded(
                                    edge_distance / mechanics["range"], 6
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
    return {
        "repeat": repeat,
        "framesBin": str(frames_path),
        "framesBinBytes": frames_path.stat().st_size,
        "firstFrameGameSeconds": rounded(first_frame_t),
        "samples": len(samples),
        "firstDamageSeconds": rounded(min(event["t"] for event in damage)),
        "actionStateHistogram": {
            str(owner): dict(sorted(histogram.items()))
            for owner, histogram in action_histogram.items()
        },
        "attackStartRanges": shot_starts,
        "perSecond": per_second,
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
