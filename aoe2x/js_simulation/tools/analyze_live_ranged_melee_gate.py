"""Decode Player-4 gate targeting and defeat timing from live mixed tapes.

This forensics tool keeps Player 4 in the entity graph so the opening patrol's
actual target distribution can be compared with the simulator.  It never
feeds captured targets or timings into runtime behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_live_melee_group_variance as group


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations" / "ranged_matrix_5x_2026-08-29"
)
UNIT_MASTERS = {
    "arbalester": 492,
    "hand_cannoneer": 5,
    "heavy_cav_archer": 474,
    "paladin": 569,
    "elite_steppe": 1372,
    "hussar": 441,
    "champion": 567,
    "heavy_camel": 330,
}
PLAYER4_MASTER = 448
PLAYER4_COUNT = 9


def resolved_target(raw_target, selected, by_id):
    if raw_target in selected:
        return raw_target
    return by_id.get(raw_target)


def decode_run(prefix: Path, matchup: dict) -> dict:
    family = matchup["family"]
    if family == "ranged_vs_melee":
        gate_owner, principal_owner = 3, 2
    elif family == "melee_vs_ranged":
        gate_owner, principal_owner = 2, 3
    else:
        raise ValueError(f"{family!r} has no Player-4 melee gate")
    expected = {
        2: (UNIT_MASTERS[matchup["side1"]["slug"]], matchup["side1"]["count"]),
        3: (UNIT_MASTERS[matchup["side2"]["slug"]], matchup["side2"]["count"]),
    }
    path = Path(f"{prefix}.frames.bin")
    doc = entity_store = world_id = None
    first_frame_t = None
    identity = {}
    first_targets = {}
    target_sequences = {}
    target_seen_bounds = {}
    first_attack_state = {}
    attack_samples_by_second = {}
    target_load_samples_by_second = {}
    gate = None
    frames = 0
    observed_max = Counter()
    finished = False

    with path.open("rb") as stream:
        while not finished:
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
                    identity = {}
                    first_frame_t = None
                    continue
                if entity_store is None:
                    continue
                if patch:
                    group.D.apply_patch(doc, patch, entity_store, world_id)
                t = frame.time / 1000.0
                selected = {}
                observed_frame = Counter()
                for key, entity in group.merged_entities(doc, entity_store, world_id):
                    owner = entity.get(2)
                    master = entity.get(1)
                    if isinstance(owner, int) and isinstance(master, int):
                        observed_frame[(owner, master)] += 1
                    if owner not in expected:
                        continue
                    if master != expected[owner][0]:
                        continue
                    selected[key] = {
                        "key": key,
                        "id": entity.get(0),
                        "owner": owner,
                        "master": master,
                        "x": float(entity.get(3)),
                        "y": float(entity.get(4)),
                        "hp": float(entity.get(12)),
                        **group.action_of(doc, entity),
                    }
                for observed_key, count in observed_frame.items():
                    observed_max[observed_key] = max(observed_max[observed_key], count)
                if not identity:
                    counts = Counter(unit["owner"] for unit in selected.values())
                    if counts != Counter({owner: row[1] for owner, row in expected.items()}):
                        continue
                    first_frame_t = t
                    for owner in (2, 3):
                        units = sorted(
                            (unit for unit in selected.values() if unit["owner"] == owner),
                            key=lambda unit: (unit["x"], unit["y"], unit["id"]),
                        )
                        for slot, unit in enumerate(units, 1):
                            identity[unit["key"]] = {
                                "id": unit["id"], "owner": owner, "slot": slot,
                                "initial_x": unit["x"], "initial_y": unit["y"],
                            }
                if first_frame_t is None:
                    continue
                frames += 1
                by_id = {unit["id"]: key for key, unit in selected.items()}
                attacking_player4 = 0
                assigned_player4 = Counter()
                attacking_player4_by_target = Counter()
                for key, unit in selected.items():
                    if unit["owner"] != gate_owner or key not in identity:
                        continue
                    raw_target = unit.get("target_id")
                    target_key = resolved_target(raw_target, selected, by_id)
                    target = selected.get(target_key)
                    if (unit.get("action_state") == 7 and target is None
                            and isinstance(raw_target, int) and raw_target >= 0):
                        attacking_player4 += 1
                    # The live plugin omits Player-4 entities from the merged
                    # entity store, but gate-army action targets retain their
                    # raw entity IDs.  Before any owner-2 target resolves,
                    # those unresolved IDs are the authored Player-4 scouts.
                    if target and target["owner"] == principal_owner and gate is None:
                        state = {}
                        for owner in (2, 3):
                            alive = [
                                candidate for candidate in selected.values()
                                if candidate["owner"] == owner and candidate["hp"] > 0
                            ]
                            state[str(owner)] = {
                                "live": len(alive),
                                "hp": round(sum(candidate["hp"] for candidate in alive), 4),
                            }
                        gate = {
                            "time_game_seconds": round(t - first_frame_t, 4),
                            "state_by_owner": state,
                            "signal": (
                                f"first owner-{gate_owner} action target resolving "
                                f"to owner {principal_owner}"
                            ),
                        }
                    if (gate is None and target is None
                            and isinstance(raw_target, int) and raw_target >= 0
                            ):
                        assigned_player4[raw_target] += 1
                        if unit.get("action_state") == 7:
                            attacking_player4_by_target[raw_target] += 1
                        observed_at = round(t - first_frame_t, 4)
                        bounds = target_seen_bounds.setdefault(raw_target, {
                            "target_id": raw_target,
                            "first_seen_game_seconds": observed_at,
                            "last_seen_game_seconds": observed_at,
                            "actor_keys": set(),
                        })
                        bounds["last_seen_game_seconds"] = observed_at
                        bounds["actor_keys"].add(key)
                        if key not in first_targets:
                            first_targets[key] = {
                                "actor_slot": identity[key]["slot"],
                                "actor_id": identity[key]["id"],
                                "actor_initial_x": identity[key]["initial_x"],
                                "actor_initial_y": identity[key]["initial_y"],
                                "target_slot": raw_target,
                                "target_id": raw_target,
                                "time_game_seconds": observed_at,
                                "distance_tiles": None,
                            }
                        sequence_rows = target_sequences.setdefault(key, [])
                        if not sequence_rows or sequence_rows[-1]["target_id"] != raw_target:
                            sequence_rows.append({
                                "target_id": raw_target,
                                "time_game_seconds": observed_at,
                            })
                    if unit.get("action_state") == 7 and key not in first_attack_state:
                        first_attack_state[key] = round(t - first_frame_t, 4)
                second = int(t - first_frame_t)
                attack_samples_by_second.setdefault(second, []).append(attacking_player4)
                target_load_samples_by_second.setdefault(second, []).append({
                    "assigned_actors": sum(assigned_player4.values()),
                    "assigned_unique_targets": len(assigned_player4),
                    "assigned_maximum_load": max(assigned_player4.values(), default=0),
                    "attacking_actors": sum(attacking_player4_by_target.values()),
                    "attacking_unique_targets": len(attacking_player4_by_target),
                    "attacking_maximum_load": max(
                        attacking_player4_by_target.values(), default=0
                    ),
                })
                # The first principal-army target proves that Player 4 has
                # already been defeated and diplomacy has changed. Every
                # auxiliary opening edge necessarily precedes this frame, so
                # later tape frames cannot add evidence to this gate report.
                if gate is not None:
                    finished = True
                    break

    target_counts = Counter(
        row["target_id"] for row in first_targets.values()
    )
    sequence_rows = []
    for key, transitions in target_sequences.items():
        sequence_rows.append({
            "actor_slot": identity[key]["slot"],
            "actor_id": identity[key]["id"],
            "targets": transitions,
            "retargets": max(0, len(transitions) - 1),
            "unique_targets": len({row["target_id"] for row in transitions}),
        })
    return {
        "frames_bin": str(path.resolve()),
        "frames": frames,
        "observed_max_owner_master_counts": [
            {"owner": key[0], "master": key[1], "count": count}
            for key, count in sorted(observed_max.items())
        ],
        "player4": {
            "master": PLAYER4_MASTER,
            "initial_count": PLAYER4_COUNT,
            "defeat": gate,
            "visibility": "entities omitted; defeat proxied by owner-3 target switching to owner 2",
        },
        "gate_army_opening_player4_targets": {
            "owner": gate_owner,
            "principal_owner": principal_owner,
            "units": expected[gate_owner][1],
            "units_with_player4_target": len(first_targets),
            "unique_player4_targets": len(target_counts),
            "maximum_units_sharing_target": max(target_counts.values(), default=0),
            "target_id_counts": {
                str(slot): count for slot, count in sorted(target_counts.items())
            },
            "edges": sorted(first_targets.values(), key=lambda row: row["actor_slot"]),
            "target_sequences": sorted(sequence_rows, key=lambda row: row["actor_slot"]),
            "units_retargeting_before_defeat": sum(
                row["retargets"] > 0 for row in sequence_rows
            ),
            "retargets_before_defeat": sum(
                row["retargets"] for row in sequence_rows
            ),
            "target_seen_bounds": [
                {
                    key: value for key, value in bounds.items()
                    if key != "actor_keys"
                } | {"unique_actors": len(bounds["actor_keys"])}
                for _, bounds in sorted(target_seen_bounds.items())
            ],
        },
        "gate_army_first_attack_state_game_seconds": group.quantiles(
            list(first_attack_state.values())
        ),
        "gate_army_attacking_player4_by_second": [
            {
                "second": second,
                "mean": round(sum(values) / len(values), 4),
                "max": max(values),
                "samples": len(values),
            }
            for second, values in sorted(attack_samples_by_second.items())
        ],
        "gate_army_player4_target_load_by_second": [
            {
                "second": second,
                **{
                    key: round(sum(row[key] for row in values) / len(values), 4)
                    for key in values[0]
                },
                "samples": len(values),
            }
            for second, values in sorted(target_load_samples_by_second.items())
            if values
        ],
    }


def aggregate(runs: list[dict]) -> dict:
    targets = [run["gate_army_opening_player4_targets"] for run in runs]
    defeats = [run["player4"]["defeat"] for run in runs
               if run["player4"]["defeat"] is not None]
    return {
        "runs": len(runs),
        "runs_with_player4_defeat": len(defeats),
        "player4_defeat_game_seconds": group.quantiles([
            row["time_game_seconds"] for row in defeats
        ]),
        "gate_army_live_at_principal_acquisition": group.quantiles([
            row["state_by_owner"][str(targets[0]["owner"])]["live"]
            for row in defeats
        ]),
        "gate_army_hp_at_principal_acquisition": group.quantiles([
            row["state_by_owner"][str(targets[0]["owner"])]["hp"]
            for row in defeats
        ]),
        "unique_player4_targets": group.quantiles([
            row["unique_player4_targets"] for row in targets
        ]),
        "maximum_units_sharing_target": group.quantiles([
            row["maximum_units_sharing_target"] for row in targets
        ]),
        "units_retargeting_before_defeat": group.quantiles([
            row["units_retargeting_before_defeat"] for row in targets
        ]),
        "retargets_before_defeat": group.quantiles([
            row["retargets_before_defeat"] for row in targets
        ]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--matchup", action="append", default=[])
    parser.add_argument("--repeat", type=int, action="append", default=[])
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    capture_root = args.capture_root.resolve()
    manifest = json.loads(
        (capture_root / "capture_manifest.json").read_text(encoding="utf-8")
    )
    keys = args.matchup or manifest["matchup_keys"]
    if args.require_complete:
        expected = manifest["repeats"] * len(manifest["matchup_keys"])
        if manifest.get("completed_runs") != expected:
            raise SystemExit(
                f"capture batch incomplete: {manifest.get('completed_runs', 0)}/{expected}"
            )
    report = {
        "schema_version": 1,
        "capture_manifest": str((capture_root / "capture_manifest.json").resolve()),
        "matchups": {},
    }
    for key in keys:
        matchup = manifest["matchups"][key]
        if matchup["family"] not in {"ranged_vs_melee", "melee_vs_ranged"}:
            continue
        runs = []
        for manifest_row in sorted(
            manifest["runs"].get(key, []), key=lambda row: row["repeat"]
        ):
            repeat = int(manifest_row["repeat"])
            if args.repeat and repeat not in args.repeat:
                continue
            prefix = (
                capture_root / key / f"run_{repeat:03d}" / "raw recordings" / key
            )
            run = {"repeat": repeat, **decode_run(prefix, matchup)}
            runs.append(run)
            print(
                f"{key} {repeat}: P4 defeat "
                f"{run['player4']['defeat']['time_game_seconds'] if run['player4']['defeat'] else None}; "
                "targets="
                f"{run['gate_army_opening_player4_targets']['target_id_counts']}",
                flush=True,
            )
        report["matchups"][key] = {
            "family": matchup["family"],
            "side2": matchup["side1"],
            "side3": matchup["side2"],
            "summary": aggregate(runs),
            "runs": runs,
        }
    output = (args.output.resolve() if args.output
              else capture_root / "grpc_player4_gate_analysis.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
