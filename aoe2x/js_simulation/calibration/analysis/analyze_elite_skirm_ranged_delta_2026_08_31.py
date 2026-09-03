"""Decode the two expanded-roster Elite Skirmisher ranged HP misses.

This is a read-only analysis of the live ``frames.bin`` captures.  It reuses
the full-rate action/HP decoder from ``tools/analyze_live_melee_group_variance``
but supplies the ranged-vs-ranged golden slots and the exact two rosters.
The only output is a traceable comparison report under ``calibration/reports``.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics
import struct
import sys


HERE = Path(__file__).resolve()
JS_SIMULATION = HERE.parents[2]
TOOLS = JS_SIMULATION / "tools"
sys.path.insert(0, str(TOOLS))

import analyze_live_melee_group_variance as group  # noqa: E402


CAPTURE_ROOT = (
    JS_SIMULATION
    / "calibration"
    / "live_observations"
    / "expanded_roster_5x_2026-08-31"
)
OUTPUT = (
    JS_SIMULATION
    / "calibration"
    / "reports"
    / "elite_skirm_diagnostics_2026-08-31"
    / "live_mechanics.json"
)
FORMATIONS = JS_SIMULATION / "fixtures" / "current_ranged_golden_formations.json"

MATCHUPS = (
    {
        "key": "imp_elite_skirm_vs_arbalester",
        "side2": {"slug": "imp_elite_skirm", "master": 6, "count": 27, "radius": 0.2},
        "side3": {"slug": "arbalester", "master": 492, "count": 23, "radius": 0.2},
    },
    {
        "key": "imp_elite_skirm_vs_hand_cannoneer",
        "side2": {"slug": "imp_elite_skirm", "master": 6, "count": 27, "radius": 0.2},
        "side3": {"slug": "hand_cannoneer", "master": 5, "count": 17, "radius": 0.2},
    },
)


def mean(values):
    return round(statistics.fmean(values), 4) if values else None


def damage_summary(events):
    by_owner = {}
    for owner in (2, 3):
        selected = [event for event in events if event["attacker_owner"] == owner]
        by_owner[str(owner)] = {
            "hits": len(selected),
            "damage": round(sum(event["damage"] for event in selected), 4),
            "unique_attackers": len({event["attacker"] for event in selected}),
            "unique_victims": len({event["victim"] for event in selected}),
            "first_damage_t_absolute_s": min(
                (event["t"] for event in selected), default=None
            ),
            "last_damage_t_absolute_s": max(
                (event["t"] for event in selected), default=None
            ),
            "damage_quanta": dict(sorted(Counter(
                round(event["damage"], 3) for event in selected
            ).items())),
        }
    return by_owner


def decode_combat_timeline(prefix, expected):
    """Count live firing states and exact HP loss directly from full-rate state."""
    path = Path(f"{prefix}.frames.bin")
    doc = entity_store = world_id = None
    first_t = None
    previous = {}
    previous_action_state = {}
    attack_starts = {2: [], 3: []}
    attack_start_samples = {2: [], 3: []}
    firing_units = {2: set(), 3: set()}
    received_damage = {2: 0.0, 3: 0.0}
    received_damage_by_second = {2: Counter(), 3: Counter()}
    first_damage_t = None
    last_damage_t = None
    bins = {}
    attack_target_switches = {2: [], 3: []}
    pending_reacquisition = {}
    reacquisitions_after_target_death = {2: [], 3: []}

    def selected_units():
        selected = {}
        for key, entity in group.merged_entities(doc, entity_store, world_id):
            owner = entity.get(2)
            master = entity.get(1)
            if owner not in expected or master != expected[owner][0]:
                continue
            selected[key] = {
                "id": entity.get(0),
                "owner": owner,
                "x": float(entity.get(3)),
                "y": float(entity.get(4)),
                "hp": max(0.0, float(entity.get(12))),
                **group.action_of(doc, entity),
            }
        return selected

    def finish(elimination_t):
        seconds = []
        for second, row in sorted(bins.items()):
            frames = row["frames"]
            seconds.append({
                "second": second,
                "frames": frames,
                "mean_alive": {
                    str(owner): round(row[f"alive_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_attacking": {
                    str(owner): round(row[f"attacking_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_targeting_live_enemy": {
                    str(owner): round(row[f"targeting_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_unique_live_targets": {
                    str(owner): round(row[f"unique_targets_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_maximum_live_target_load": {
                    str(owner): round(row[f"maximum_target_load_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_nearest_friendly_chebyshev_distance": {
                    str(owner): round(row[f"nearest_friendly_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_allied_overlap_pairs": {
                    str(owner): round(row[f"allied_overlap_pairs_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_x_span": {
                    str(owner): round(row[f"x_span_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "mean_y_span": {
                    str(owner): round(row[f"y_span_{owner}"] / frames, 4)
                    for owner in (2, 3)
                },
                "attack_starts": {
                    str(owner): sum(
                        int(math.floor(t - first_t)) == second
                        for t, _unit_id in attack_starts[owner]
                    )
                    for owner in (2, 3)
                },
                "received_damage": {
                    str(owner): round(received_damage_by_second[owner][second], 4)
                    for owner in (2, 3)
                },
            })
        cadence = {}
        for owner in (2, 3):
            starts_by_unit = {}
            for t, unit_id in attack_starts[owner]:
                starts_by_unit.setdefault(unit_id, []).append(t)
            intervals = [
                right - left
                for starts in starts_by_unit.values()
                for left, right in zip(starts, starts[1:])
            ]
            cadence[str(owner)] = {
                "intervals": len(intervals),
                "mean_attack_start_interval_s": mean(intervals),
                "median_attack_start_interval_s": (
                    round(statistics.median(intervals), 4) if intervals else None
                ),
            }
        return {
            "frames_bin": str(path),
            "first_frame_absolute_s": first_t,
            "first_damage_game_s": (
                round(first_damage_t - first_t, 4) if first_damage_t is not None else None
            ),
            "last_damage_game_s": (
                round(last_damage_t - first_t, 4) if last_damage_t is not None else None
            ),
            "elimination_game_s": round(elimination_t - first_t, 4),
            "received_damage": {
                str(owner): round(received_damage[owner], 4) for owner in (2, 3)
            },
            "attack_starts": {
                str(owner): len(attack_starts[owner]) for owner in (2, 3)
            },
            "attack_starts_first_20_game_s": {
                str(owner): sum(
                    t - first_t < 20.0 for t, _unit_id in attack_starts[owner]
                )
                for owner in (2, 3)
            },
            "attack_start_cadence": cadence,
            "attack_start_samples": {
                str(owner): attack_start_samples[owner] for owner in (2, 3)
            },
            "unique_units_entering_attack_state": {
                str(owner): len(firing_units[owner]) for owner in (2, 3)
            },
            "attack_target_switches_while_attacking": {
                str(owner): attack_target_switches[owner] for owner in (2, 3)
            },
            "reacquisitions_after_target_death": {
                str(owner): reacquisitions_after_target_death[owner]
                for owner in (2, 3)
            },
            "per_second": seconds,
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
            sequence = group.pb.FrameSequence()
            sequence.ParseFromString(payload)
            for frame in sequence.frame:
                patch = frame.patch
                if patch and len(patch) > group.SNAP_RESEED:
                    doc, entity_store, world_id = group.seed_snapshot(patch)
                    first_t = None
                    previous = {}
                    previous_action_state = {}
                    continue
                if entity_store is None:
                    continue
                if patch:
                    group.D.apply_patch(doc, patch, entity_store, world_id)
                selected = selected_units()
                live = {key: unit for key, unit in selected.items() if unit["hp"] > 0}
                if first_t is None:
                    counts = Counter(unit["owner"] for unit in live.values())
                    if counts != Counter({owner: row[1] for owner, row in expected.items()}):
                        continue
                    first_t = frame.time / 1000.0
                    previous = live
                    previous_action_state = {
                        key: unit.get("action_state") for key, unit in live.items()
                    }
                t = frame.time / 1000.0
                dropped = 0.0
                for key, before in previous.items():
                    after_hp = live.get(key, {}).get("hp", 0.0)
                    amount = max(0.0, before["hp"] - after_hp)
                    if amount <= 1e-9:
                        continue
                    received_damage[before["owner"]] += amount
                    received_damage_by_second[before["owner"]][
                        int(math.floor(t - first_t))
                    ] += amount
                    dropped += amount
                if dropped > 0:
                    if first_damage_t is None:
                        first_damage_t = t
                    last_damage_t = t

                by_id = {unit["id"]: key for key, unit in live.items()}
                previous_by_id = {
                    unit["id"]: key for key, unit in previous.items()
                }
                dead_keys = set(previous) - set(live)
                for actor_key, before in previous.items():
                    if actor_key not in live or actor_key in pending_reacquisition:
                        continue
                    old_raw = before.get("target_id")
                    old_key = (
                        old_raw if old_raw in previous else previous_by_id.get(old_raw)
                    )
                    if old_key not in dead_keys:
                        continue
                    old_target = previous.get(old_key)
                    if not old_target or old_target["owner"] == before["owner"]:
                        continue
                    pending_reacquisition[actor_key] = {
                        "death_t": t,
                        "actor_id": before["id"],
                        "owner": before["owner"],
                        "old_target_id": old_target["id"],
                    }
                for actor_key, pending in list(pending_reacquisition.items()):
                    unit = live.get(actor_key)
                    if unit is None:
                        del pending_reacquisition[actor_key]
                        continue
                    new_raw = unit.get("target_id")
                    new_key = new_raw if new_raw in live else by_id.get(new_raw)
                    new_target = live.get(new_key)
                    if not new_target or new_target["owner"] == unit["owner"] \
                            or new_target["id"] == pending["old_target_id"]:
                        continue
                    candidates = sorted(
                        (
                            math.hypot(
                                candidate["x"] - unit["x"],
                                candidate["y"] - unit["y"],
                            ),
                            candidate["id"],
                        )
                        for candidate in live.values()
                        if candidate["owner"] != unit["owner"]
                    )
                    chosen_distance = math.hypot(
                        new_target["x"] - unit["x"],
                        new_target["y"] - unit["y"],
                    )
                    chosen_rank = next(
                        index + 1
                        for index, (_distance, target_id) in enumerate(candidates)
                        if target_id == new_target["id"]
                    )
                    current_target_ids = []
                    for ally in live.values():
                        if ally["owner"] != unit["owner"]:
                            continue
                        ally_raw = ally.get("target_id")
                        ally_key = ally_raw if ally_raw in live else by_id.get(ally_raw)
                        ally_target = live.get(ally_key)
                        if ally_target and ally_target["owner"] != unit["owner"]:
                            current_target_ids.append(ally_target["id"])
                    target_loads = Counter(current_target_ids)
                    reacquisitions_after_target_death[pending["owner"]].append({
                        "actor_id": pending["actor_id"],
                        "from_target_id": pending["old_target_id"],
                        "to_target_id": new_target["id"],
                        "target_death_game_s": round(pending["death_t"] - first_t, 4),
                        "reacquisition_game_s": round(t - first_t, 4),
                        "delay_s": round(t - pending["death_t"], 4),
                        "chosen_center_distance": round(chosen_distance, 4),
                        "nearest_center_distance": (
                            round(candidates[0][0], 4) if candidates else None
                        ),
                        "chosen_distance_rank": chosen_rank,
                        "chosen_target_load_this_frame": target_loads[
                            new_target["id"]
                        ],
                    })
                    del pending_reacquisition[actor_key]
                for key, unit in live.items():
                    before = previous.get(key)
                    if not before or before.get("action_state") != 7 \
                            or unit.get("action_state") != 7:
                        continue
                    old_raw = before.get("target_id")
                    new_raw = unit.get("target_id")
                    old_key = (
                        old_raw if old_raw in previous else previous_by_id.get(old_raw)
                    )
                    new_key = new_raw if new_raw in live else by_id.get(new_raw)
                    if old_key is None or new_key is None or old_key == new_key:
                        continue
                    old_target = previous.get(old_key)
                    new_target = live.get(new_key)
                    if not old_target or not new_target \
                            or new_target["owner"] == unit["owner"]:
                        continue
                    attack_target_switches[unit["owner"]].append({
                        "game_s": round(t - first_t, 4),
                        "actor_id": unit["id"],
                        "from_target_id": old_target["id"],
                        "to_target_id": new_target["id"],
                        "from_target_died": old_key not in live,
                        "timer_before": before.get("action_timer"),
                        "timer_after": unit.get("action_timer"),
                    })
                for key, unit in live.items():
                    if unit.get("action_state") == 7 \
                            and previous_action_state.get(key) != 7:
                        attack_starts[unit["owner"]].append((t, unit["id"]))
                        firing_units[unit["owner"]].add(unit["id"])
                        raw_target = unit.get("target_id")
                        target_key = raw_target if raw_target in live else by_id.get(raw_target)
                        target = live.get(target_key)
                        attack_start_samples[unit["owner"]].append({
                            "game_s": round(t - first_t, 4),
                            "actor_id": unit["id"],
                            "target_id": target["id"] if target else None,
                            "center_distance": (
                                round(math.hypot(
                                    target["x"] - unit["x"],
                                    target["y"] - unit["y"],
                                ), 4)
                                if target else None
                            ),
                        })

                elapsed = max(0.0, t - first_t)
                second = int(math.floor(elapsed))
                row = bins.setdefault(second, {
                    "frames": 0,
                    "alive_2": 0,
                    "alive_3": 0,
                    "attacking_2": 0,
                    "attacking_3": 0,
                    "targeting_2": 0,
                    "targeting_3": 0,
                    "unique_targets_2": 0,
                    "unique_targets_3": 0,
                    "maximum_target_load_2": 0,
                    "maximum_target_load_3": 0,
                    "nearest_friendly_2": 0,
                    "nearest_friendly_3": 0,
                    "allied_overlap_pairs_2": 0,
                    "allied_overlap_pairs_3": 0,
                    "x_span_2": 0,
                    "x_span_3": 0,
                    "y_span_2": 0,
                    "y_span_3": 0,
                })
                row["frames"] += 1
                for owner in (2, 3):
                    own = [unit for unit in live.values() if unit["owner"] == owner]
                    row[f"alive_{owner}"] += len(own)
                    row[f"attacking_{owner}"] += sum(
                        unit.get("action_state") == 7 for unit in own
                    )
                    targeting = 0
                    target_ids = []
                    for unit in own:
                        raw_target = unit.get("target_id")
                        target_key = raw_target if raw_target in live else by_id.get(raw_target)
                        if target_key in live and live[target_key]["owner"] != owner:
                            targeting += 1
                            target_ids.append(live[target_key]["id"])
                    row[f"targeting_{owner}"] += targeting
                    target_counts = Counter(target_ids)
                    row[f"unique_targets_{owner}"] += len(target_counts)
                    row[f"maximum_target_load_{owner}"] += max(
                        target_counts.values(), default=0
                    )
                    if len(own) > 1:
                        nearest = []
                        overlap_pairs = 0
                        for left_index, left in enumerate(own):
                            distances = [
                                max(abs(right["x"] - left["x"]),
                                    abs(right["y"] - left["y"]))
                                for right_index, right in enumerate(own)
                                if right_index != left_index
                            ]
                            nearest.append(min(distances))
                            for right in own[left_index + 1:]:
                                if max(abs(right["x"] - left["x"]),
                                       abs(right["y"] - left["y"])) < 0.4 - 1e-9:
                                    overlap_pairs += 1
                        row[f"nearest_friendly_{owner}"] += statistics.fmean(nearest)
                        row[f"allied_overlap_pairs_{owner}"] += overlap_pairs
                    elif own:
                        row[f"nearest_friendly_{owner}"] += 0
                    if own:
                        row[f"x_span_{owner}"] += (
                            max(unit["x"] for unit in own)
                            - min(unit["x"] for unit in own)
                        )
                        row[f"y_span_{owner}"] += (
                            max(unit["y"] for unit in own)
                            - min(unit["y"] for unit in own)
                        )

                previous = live
                previous_action_state = {
                    key: unit.get("action_state") for key, unit in live.items()
                }
                counts = Counter(unit["owner"] for unit in live.values())
                if counts.get(2, 0) == 0 or counts.get(3, 0) == 0:
                    return finish(t)
    raise RuntimeError(f"{path}: combat did not reach elimination")


def summarize(matchup_runs):
    opening = group.summarize_runs(matchup_runs)
    by_owner = {}
    for owner in (2, 3):
        owner_key = str(owner)
        rows = [run["damage_by_owner"][owner_key] for run in matchup_runs]
        acquisitions = [run["acquisition"][f"side{owner}"] for run in matchup_runs]
        units = [
            unit
            for run in matchup_runs
            for unit in run["units"]
            if unit["owner"] == owner
        ]
        by_owner[owner_key] = {
            "mean_hits": mean([row["hits"] for row in rows]),
            "mean_damage": mean([row["damage"] for row in rows]),
            "mean_unique_attackers": mean([row["unique_attackers"] for row in rows]),
            "mean_unique_victims": mean([row["unique_victims"] for row in rows]),
            "mean_unique_first_targets": mean([
                row["unique_first_targets"] for row in acquisitions
            ]),
            "mean_maximum_first_target_load": mean([
                row["maximum_units_sharing_first_target"] for row in acquisitions
            ]),
            "mean_units_dealing_damage": mean([
                sum(unit["first_damage_dealt_t"] is not None
                    for unit in run["units"] if unit["owner"] == owner)
                for run in matchup_runs
            ]),
            "mean_first_attack_state_s": mean([
                unit["first_attack_state_t"]
                for unit in units
                if unit["first_attack_state_t"] is not None
            ]),
            "mean_first_damage_dealt_s": mean([
                unit["first_damage_dealt_t"]
                for unit in units
                if unit["first_damage_dealt_t"] is not None
            ]),
        }
    return {
        **opening,
        "mean_elimination_game_s": mean([
            run["elimination_t_game_s"] for run in matchup_runs
        ]),
        "by_owner": by_owner,
    }


def main():
    formations = json.loads(FORMATIONS.read_text(encoding="utf-8"))
    ranged = formations["families"]["ranged_vs_ranged"]
    slots = {
        owner: [
            (float(row["position"]["x"]), float(row["position"]["y"]))
            for row in ranged["sides"][str(owner)]
        ]
        for owner in (2, 3)
    }
    report = {
        "schema_version": 1,
        "capture_root": str(CAPTURE_ROOT),
        "formation_fixture": str(FORMATIONS),
        "formation_family": "ranged_vs_ranged",
        "clock": "raw gRPC game seconds",
        "damage_derivation": (
            "full-rate HP deltas attributed by adjacent action targets and kill events"
        ),
        "matchups": {},
    }
    for spec in MATCHUPS:
        group.EXPECTED = {
            2: (spec["side2"]["master"], spec["side2"]["count"]),
            3: (spec["side3"]["master"], spec["side3"]["count"]),
        }
        group.COLLISION_RADIUS = {
            2: spec["side2"]["radius"],
            3: spec["side3"]["radius"],
        }
        runs = []
        for repeat in range(1, 6):
            run_dir = CAPTURE_ROOT / spec["key"] / f"run_{repeat:03d}"
            prefix = run_dir / "raw recordings" / spec["key"]
            damage = group.decode_damage_from_frames(prefix)
            decoded = group.decode_frames(prefix, damage, slots)
            timeline = decode_combat_timeline(prefix, group.EXPECTED)
            run = {
                "repeat": repeat,
                **decoded,
                "damage_by_owner": damage_summary(damage),
                "combat_timeline": timeline,
            }
            runs.append(run)
            print(
                f"{spec['key']} run_{repeat:03d}: "
                f"{decoded['acquisition']['side2']['unique_first_targets']} "
                "P2 first targets, "
                f"{decoded['elimination_t_game_s']:.2f}s",
                flush=True,
            )
        report["matchups"][spec["key"]] = {
            "side2": spec["side2"],
            "side3": spec["side3"],
            "runs": runs,
            "summary": summarize(runs),
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


def refresh_timelines():
    """Refresh only full-rate timeline fields without redoing other decoders."""
    if not OUTPUT.exists():
        raise FileNotFoundError(f"timeline refresh requires existing {OUTPUT}")
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    for spec in MATCHUPS:
        group.EXPECTED = {
            2: (spec["side2"]["master"], spec["side2"]["count"]),
            3: (spec["side3"]["master"], spec["side3"]["count"]),
        }
        group.COLLISION_RADIUS = {
            2: spec["side2"]["radius"],
            3: spec["side3"]["radius"],
        }
        rows = report["matchups"][spec["key"]]["runs"]
        by_repeat = {row["repeat"]: row for row in rows}
        for repeat in range(1, 6):
            run_dir = CAPTURE_ROOT / spec["key"] / f"run_{repeat:03d}"
            prefix = run_dir / "raw recordings" / spec["key"]
            by_repeat[repeat]["combat_timeline"] = decode_combat_timeline(
                prefix, group.EXPECTED
            )
            print(f"{spec['key']} run_{repeat:03d}: timeline refreshed", flush=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    if "--timeline-only" in sys.argv:
        refresh_timelines()
    else:
        main()
