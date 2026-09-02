"""Inspect the preserved War Chariot and Chu Ko Nu ranged-vs-ranged tapes.

This is validation-only tape forensics.  It records the exact project-local
``frames.bin`` path and scenario unit constants, and never feeds an observed
outcome back into the simulator.  The useful observables are attack-windup
entries, raw HP drops, and projectile-entity births at full recorder cadence.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics
import struct
import sys


SCRIPT = Path(__file__).resolve()
JS_SIMULATION = SCRIPT.parents[2]
TOOLS = JS_SIMULATION / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import analyze_live_engagement_participation as participation  # noqa: E402
import analyze_live_melee_group_variance as group  # noqa: E402
from analyze_live_melee_1v1 import action_of, seed_snapshot  # noqa: E402


CAPTURE_ROOT = (
    JS_SIMULATION / "calibration" / "live_observations"
    / "requested_roster_vs_arb_paladin_1x_2026-08-31"
)
OUTPUT = (
    JS_SIMULATION / "calibration" / "reports"
    / "requested_unique_effects_2026-09-01" / "ranged_volley_live_forensics.json"
)
SNAP_RESEED = 400_000
ARMY_MODEL_TYPES = {9, 11, 12}

MATCHUPS = (
    {
        "key": "xianbei_raider_wei_vs_arbalester",
        "scenario_unit_constants": {"2": 1952, "3": 492},
        "expected": {2: (1952, 21), 3: (492, 27)},
        "projectile_masters": (1982, 1983),
        "mechanics": {
            2: {"range": 7.0, "min_range": 0.0, "outline": 0.4,
                "collision": 0.25},
            3: {"range": 8.0, "min_range": 0.0, "outline": 0.2,
                "collision": 0.2},
        },
        "mode": "charge_volley",
    },
    {
        "key": "elite_kipchak_cumans_vs_arbalester",
        "scenario_unit_constants": {"2": 1233, "3": 492},
        "expected": {2: (1233, 19), 3: (492, 27)},
        "projectile_masters": (510,),
        "mechanics": {
            2: {"range": 6.0, "min_range": 0.0, "outline": 0.4,
                "collision": 0.25},
            3: {"range": 8.0, "min_range": 0.0, "outline": 0.2,
                "collision": 0.2},
        },
        "mode": "multi_arrow",
    },
    {
        "key": "war_chariot_shu_vs_arbalester",
        "scenario_unit_constants": {"2": 1962, "3": 492},
        "expected": {2: (1962, 12), 3: (492, 27)},
        "projectile_masters": (1964,),
        "mechanics": {
            2: {"range": 6.0, "min_range": 1.0, "outline": 0.8,
                "collision": 0.5},
            3: {"range": 8.0, "min_range": 0.0, "outline": 0.2,
                "collision": 0.2},
        },
        "mode": "focus_fire",
        "alternate_mode": {
            "name": "barrage",
            "unit_constant": 1980,
            "projectile_master": 1957,
            "live_capture": None,
        },
    },
    {
        "key": "elite_chu_ko_nu_chinese_vs_arbalester",
        "scenario_unit_constants": {"2": 559, "3": 492},
        "expected": {2: (559, 25), 3: (492, 27)},
        "projectile_masters": (510,),
        "mechanics": {
            2: {"range": 7.0, "min_range": 0.0, "outline": 0.2,
                "collision": 0.2},
            3: {"range": 8.0, "min_range": 0.0, "outline": 0.2,
                "collision": 0.2},
        },
        "mode": "repeating_volley",
    },
)


def finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def entity_rows(doc, entity_store, world_id):
    """Merge scalar/entity-document rows without filtering out missiles."""
    world_entities = doc.models.get(world_id, {}).get(1, {})
    for key, scalar in entity_store.items():
        doc_id = world_entities.get(key)
        entity = scalar
        if isinstance(doc_id, int) and doc_id in doc.models:
            entity = {**doc.models[doc_id], **scalar}
        yield key, entity


def percentile(values: list[float], fraction: float):
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    left = math.floor(position)
    right = math.ceil(position)
    if left == right:
        return ordered[left]
    weight = position - left
    return ordered[left] * (1 - weight) + ordered[right] * weight


def distribution(values: list[float], digits: int = 4):
    if not values:
        return {"count": 0, "min": None, "median": None, "p90": None,
                "mean": None, "max": None}
    return {
        "count": len(values),
        "min": round(min(values), digits),
        "median": round(statistics.median(values), digits),
        "p90": round(percentile(values, 0.9), digits),
        "mean": round(statistics.fmean(values), digits),
        "max": round(max(values), digits),
    }


def summarize_volleys(births: list[dict]):
    """Group one actor's projectile births; inter-volley gaps exceed 1 s."""
    by_actor: dict[int, list[dict]] = {}
    for birth in births:
        source = birth.get("sourceActorId")
        if not isinstance(source, int):
            continue
        by_actor.setdefault(source, []).append(birth)
    volleys = []
    for actor_id, rows in by_actor.items():
        rows.sort(key=lambda current: current["t"])
        cluster = []
        for birth in rows:
            if cluster and birth["t"] - cluster[-1]["t"] > 1.0:
                volleys.append((actor_id, cluster))
                cluster = []
            cluster.append(birth)
        if cluster:
            volleys.append((actor_id, cluster))
    counts = [len(cluster) for _, cluster in volleys]
    spans = [cluster[-1]["t"] - cluster[0]["t"]
             for _, cluster in volleys if len(cluster) > 1]
    intra = [right["t"] - left["t"]
             for _, cluster in volleys
             for left, right in zip(cluster, cluster[1:])]
    return {
        "sourceActors": len(by_actor),
        "volleyCount": len(volleys),
        "projectilesPerVolley": {
            str(count): occurrences
            for count, occurrences in sorted(Counter(counts).items())
        },
        "volleySpanSeconds": distribution(spans, 6),
        "intraVolleyIntervalSeconds": distribution(intra, 6),
        "firstVolleys": [
            {
                "actorId": actor_id,
                "start": round(cluster[0]["t"], 6),
                "count": len(cluster),
                "times": [birth["t"] for birth in cluster],
            }
            for actor_id, cluster in sorted(
                volleys, key=lambda current: current[1][0]["t"]
            )[:20]
        ],
    }


def decode_projectile_births(row: dict):
    key = row["key"]
    expected = row["expected"]
    projectile_masters = set(row["projectile_masters"])
    prefix = CAPTURE_ROOT / key / "run_001" / "raw recordings" / key
    frames_path = Path(f"{prefix}.frames.bin")
    doc = entity_store = world_id = None
    prior_projectiles: set[int] = set()
    prior_projectile_rows: dict[int, dict] = {}
    prior_units: dict[int, dict] = {}
    first_frame_time = None
    spawn_frames = []
    hp_drop_frames = []
    windup_starts = []
    projectile_samples = []
    projectile_births = []
    projectile_deaths = []
    action_timeline = []
    sampled_second = -1
    model_types_by_master: dict[int, Counter] = {
        master: Counter() for master in projectile_masters
    }

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
                    prior_projectiles = set()
                    prior_projectile_rows = {}
                    prior_units = {}
                    first_frame_time = None
                    spawn_frames = []
                    hp_drop_frames = []
                    windup_starts = []
                    projectile_samples = []
                    projectile_births = []
                    projectile_deaths = []
                    action_timeline = []
                    sampled_second = -1
                    model_types_by_master = {
                        master: Counter() for master in projectile_masters
                    }
                    continue
                if entity_store is None:
                    continue
                if patch:
                    group.D.apply_patch(doc, patch, entity_store, world_id)

                all_rows = list(entity_rows(doc, entity_store, world_id))
                selected = {}
                for state_key, entity in all_rows:
                    owner = entity.get(2)
                    master = entity.get(1)
                    if owner not in expected or master != expected[owner][0]:
                        continue
                    hp = entity.get(12)
                    if not finite(hp) or hp <= 0:
                        continue
                    selected[state_key] = {
                        "id": entity.get(0),
                        "owner": owner,
                        "master": master,
                        "x": float(entity.get(3)),
                        "y": float(entity.get(4)),
                        "hp": float(hp),
                        **action_of(doc, entity),
                    }
                if first_frame_time is None:
                    roster = Counter(unit["owner"] for unit in selected.values())
                    required = Counter({owner: value[1] for owner, value in expected.items()})
                    if roster != required:
                        continue
                    first_frame_time = frame.time / 1000.0
                t = frame.time / 1000.0 - first_frame_time
                second = math.floor(t)
                if second > sampled_second:
                    sampled_second = second
                    action_timeline.append({
                        "second": second,
                        "byOwner": {
                            str(owner): {
                                "alive": sum(
                                    unit["owner"] == owner
                                    for unit in selected.values()
                                ),
                                "actionStates": {
                                    str(state): count
                                    for state, count in sorted(Counter(
                                        unit.get("action_state")
                                        for unit in selected.values()
                                        if unit["owner"] == owner
                                    ).items(), key=lambda item: str(item[0]))
                                },
                            }
                            for owner in sorted(expected)
                        },
                    })

                projectiles = {}
                projectile_entities = {}
                for state_key, entity in all_rows:
                    master = entity.get(1)
                    if master not in projectile_masters:
                        continue
                    model_types_by_master[master][entity.get("__type__")] += 1
                    projectile_id = entity.get(0)
                    if not isinstance(projectile_id, int):
                        projectile_id = state_key
                    projectiles[projectile_id] = master
                    projectile_entities[projectile_id] = entity
                    if len(projectile_samples) < 5 and projectile_id not in prior_projectiles:
                        projectile_samples.append({
                            "t": round(t, 6),
                            "stateKey": state_key,
                            "fields": {
                                str(field): value
                                for field, value in entity.items()
                                if isinstance(value, (str, int, float, bool))
                                   or value is None
                            },
                        })
                new_ids = sorted(set(projectiles) - prior_projectiles)
                dead_ids = sorted(prior_projectiles - set(projectiles))
                for projectile_id in dead_ids:
                    prior = prior_projectile_rows.get(projectile_id, {})
                    px = prior.get("x")
                    py = prior.get("y")
                    hostile = [unit for unit in prior_units.values()
                               if unit.get("owner") == 3]
                    nearest = min(
                        hostile,
                        key=lambda unit: max(
                            abs(unit["x"] - px), abs(unit["y"] - py)
                        ),
                        default=None,
                    ) if finite(px) and finite(py) else None
                    projectile_deaths.append({
                        "t": round(t, 6),
                        "projectileId": projectile_id,
                        **prior,
                        "nearestEnemy": ({
                            "id": nearest.get("id"),
                            "distance": round(max(
                                abs(nearest["x"] - px),
                                abs(nearest["y"] - py),
                            ), 6),
                        } if nearest else None),
                    })
                if new_ids:
                    for projectile_id in new_ids:
                        entity = projectile_entities[projectile_id]
                        source_id = entity.get(22)
                        source = next((unit for unit in selected.values()
                                       if unit.get("id") == source_id), None)
                        projectile_births.append({
                            "t": round(t, 6),
                            "projectileId": projectile_id,
                            "projectileMaster": projectiles[projectile_id],
                            "sourceActorId": source_id,
                            "sourceTargetId": (
                                source.get("target_id") if source else None
                            ),
                            "sourceActionState": (
                                source.get("action_state") if source else None
                            ),
                            "x": round(float(entity.get(3)), 6)
                                 if finite(entity.get(3)) else None,
                            "y": round(float(entity.get(4)), 6)
                                 if finite(entity.get(4)) else None,
                            "sourceX": round(float(source.get("x")), 6)
                                       if source and finite(source.get("x")) else None,
                            "sourceY": round(float(source.get("y")), 6)
                                       if source and finite(source.get("y")) else None,
                            "projectileAction": action_of(doc, entity),
                            "primaryMarker": entity.get(23) is True,
                        })
                    counts = Counter(projectiles[projectile_id] for projectile_id in new_ids)
                    spawn_frames.append({
                        "t": round(t, 6),
                        "count": len(new_ids),
                        "byMaster": {str(master): count
                                     for master, count in sorted(counts.items())},
                    })

                current_by_id = {
                    unit["id"]: unit for unit in selected.values()
                    if isinstance(unit.get("id"), int)
                }
                drops = []
                for unit_id, before in prior_units.items():
                    after = current_by_id.get(unit_id)
                    after_hp = after["hp"] if after else 0.0
                    if after_hp < before["hp"] - 1e-9:
                        drops.append({
                            "victimId": unit_id,
                            "victimOwner": before["owner"],
                            "amount": round(before["hp"] - after_hp, 6),
                        })
                if drops:
                    hp_drop_frames.append({"t": round(t, 6), "drops": drops})

                for state_key, unit in selected.items():
                    unit_id = unit.get("id")
                    before = prior_units.get(unit_id)
                    if unit.get("action_state") == 7 and (
                        before is None or before.get("action_state") != 7
                    ):
                        target = current_by_id.get(unit.get("target_id"))
                        windup_starts.append({
                            "t": round(t, 6),
                            "owner": unit["owner"],
                            "actorId": unit_id,
                            "targetId": unit.get("target_id"),
                            "actorX": round(unit["x"], 6),
                            "actorY": round(unit["y"], 6),
                            "targetX": round(target["x"], 6) if target else None,
                            "targetY": round(target["y"], 6) if target else None,
                            "centerDistance": (
                                round(math.hypot(
                                    target["x"] - unit["x"],
                                    target["y"] - unit["y"],
                                ), 6)
                                if target else None
                            ),
                        })

                prior_projectiles = set(projectiles)
                prior_projectile_rows = {
                    projectile_id: {
                        "projectileMaster": projectiles[projectile_id],
                        "sourceActorId": entity.get(22),
                        "x": round(float(entity.get(3)), 6)
                             if finite(entity.get(3)) else None,
                        "y": round(float(entity.get(4)), 6)
                             if finite(entity.get(4)) else None,
                        "projectileAction": (
                            action_of(doc, entity)
                            or prior_projectile_rows.get(projectile_id, {}).get(
                                "projectileAction", {}
                            )
                        ),
                        "primaryMarker": entity.get(23) is True,
                    }
                    for projectile_id, entity in projectile_entities.items()
                }
                prior_units = current_by_id

    spawn_times = [frame["t"] for frame in spawn_frames]
    spawn_gaps = [right - left for left, right in zip(spawn_times, spawn_times[1:])]
    return {
        "framesBin": str(frames_path.resolve()),
        "framesBinBytes": frames_path.stat().st_size,
        "projectileMasters": sorted(projectile_masters),
        "projectileModelTypes": {
            str(master): {str(kind): count for kind, count in counts.items()}
            for master, counts in model_types_by_master.items()
        },
        "projectileSamples": projectile_samples,
        "projectileBirths": projectile_births,
        "projectileDeaths": projectile_deaths,
        "volleySummary": summarize_volleys(projectile_births),
        "projectileSpawnFrames": spawn_frames,
        "projectileSpawnFrameCount": len(spawn_frames),
        "projectileBirthCount": sum(frame["count"] for frame in spawn_frames),
        "projectilesPerSpawnFrame": distribution(
            [float(frame["count"]) for frame in spawn_frames]),
        "interSpawnFrameSeconds": distribution(spawn_gaps, 6),
        "windupStarts": windup_starts,
        "actionTimeline": action_timeline,
        "hpDropFrames": hp_drop_frames,
    }


def decode_participation(row: dict):
    participation.MATCHUP_KEY = row["key"]
    participation.CAPTURE_ROOT = CAPTURE_ROOT / row["key"]
    participation.EXPECTED = row["expected"]
    participation.AUXILIARY_EXPECTED = {}
    participation.MECHANICS = row["mechanics"]
    participation.WINDOW_SECONDS = 20
    participation.OPENING_SNAPSHOT_SECONDS = ()
    group.EXPECTED = row["expected"]
    decoded = participation.decode_run(1)
    summary = {}
    for owner in (2, 3):
        shots = [event for event in decoded["attackStartRanges"]
                 if event["owner"] == owner]
        per_second = [second[str(owner)] for second in decoded["perSecond"]]
        summary[str(owner)] = {
            "attackWindupStartsFirst20Seconds": len(shots),
            "uniqueAttackersFirst20Seconds": len({event["id"] for event in shots}),
            "meanAliveFirst20Seconds": round(statistics.fmean(
                second["alive"] for second in per_second), 4),
            "meanFiringFirst20Seconds": round(statistics.fmean(
                second["firing"] for second in per_second), 4),
            "meanActiveFirst20Seconds": round(statistics.fmean(
                second["active"] for second in per_second), 4),
            "meanBoxOverlapPairsFirst20Seconds": round(statistics.fmean(
                second["meanBoxOverlapPairs"] for second in per_second), 4),
            "meanTripleStacksFirst20Seconds": round(statistics.fmean(
                second["meanTripleStacks"] for second in per_second), 4),
            "meanOverlapDepthFirst20Seconds": round(statistics.fmean(
                second["meanBoxOverlapDepth"] for second in per_second), 6),
            "decodedDamage": decoded["damageByOwner"][str(owner)],
        }
    return summary


def main() -> None:
    output = {
        "schemaVersion": 1,
        "scope": "one preserved live run per ranged-vs-ranged matchup",
        "captureRoot": str(CAPTURE_ROOT.resolve()),
        "notes": [
            "Scenario constants establish that the War Chariot tape uses Focus Fire (1962).",
            "Barrage (1980 / projectile 1957) has no preserved live capture in this batch.",
            "Action state 7 is the full-rate live proxy for an attack windup.",
            "Projectile births are observational only; some projectile entities may share a recorder frame.",
        ],
        "matchups": [],
    }
    for row in MATCHUPS:
        output["matchups"].append({
            "key": row["key"],
            "mode": row["mode"],
            "scenarioUnitConstants": row["scenario_unit_constants"],
            **({"alternateMode": row["alternate_mode"]}
               if row.get("alternate_mode") else {}),
            "participation": decode_participation(row),
            "fullRate": decode_projectile_births(row),
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    for row in output["matchups"]:
        side = row["participation"]["2"]
        rate = row["fullRate"]
        print(
            f"{row['key']}: P2 windups={side['attackWindupStartsFirst20Seconds']}, "
            f"damage={side['decodedDamage']['damage']}, "
            f"projectile births={rate['projectileBirthCount']} in "
            f"{rate['projectileSpawnFrameCount']} frames"
        )


if __name__ == "__main__":
    main()
