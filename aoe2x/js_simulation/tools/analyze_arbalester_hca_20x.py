"""Decode completed runs from the 20x Arbalester-vs-HCA live batch.

This is tape forensics only. It records each exact ``frames.bin`` source and
does not feed observations back into simulation runtime parameters.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_live_melee_group_variance as group
import analyze_live_engagement_participation as participation


ROOT = Path(__file__).resolve().parents[1]
MATCHUP_KEY = "arbalester_vs_heavy_cav_archer"
DEFAULT_CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "arbalester_hca_20x_2026-08-30"
)
FORMATIONS = ROOT / "fixtures" / "current_ranged_golden_formations.json"


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def compact_run(run: dict, capture: dict) -> dict:
    return {
        "repeat": run["repeat"],
        "frames_bin": run["frames_bin"],
        "winner": capture["winner"],
        "survivors": capture["survivors"],
        "winner_hp": capture["winner_hp"],
        "elimination_time_s": capture["elimination_time_s"],
        "grpc_elimination_game_seconds": run["elimination_t_game_s"],
        "first_damage": run["first_damage"],
        "first_two_game_seconds": run["first_two_game_seconds"],
        "acquisition": run["acquisition"],
        "overlap": run["overlap"],
    }


def winner_summary(rows: list[dict], winner: str) -> dict:
    selected = [row for row in rows if row["winner"] == winner]
    return {
        "runs": len(selected),
        "winner_hp_mean": mean([row["winner_hp"] for row in selected]),
        "survivors_mean": mean([row["survivors"] for row in selected]),
        "side2_unique_first_targets_mean": mean([
            row["acquisition"]["side2"]["unique_first_targets"]
            for row in selected
        ]),
        "side2_maximum_shared_first_target_mean": mean([
            row["acquisition"]["side2"]["maximum_units_sharing_first_target"]
            for row in selected
        ]),
        "side3_unique_first_targets_mean": mean([
            row["acquisition"]["side3"]["unique_first_targets"]
            for row in selected
        ]),
        "opening_side2_hits_mean": mean([
            row["first_two_game_seconds"]["hits_by_side"].get("2", 0)
            for row in selected
        ]),
        "opening_side3_hits_mean": mean([
            row["first_two_game_seconds"]["hits_by_side"].get("3", 0)
            for row in selected
        ]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--include-participation", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    capture_root = args.capture_root.resolve()
    batch = json.loads(
        (capture_root / "capture_manifest.json").read_text(encoding="utf-8")
    )
    if batch.get("matchup_keys") != [MATCHUP_KEY]:
        raise SystemExit("capture manifest is not the single Arbalester-vs-HCA batch")
    if args.require_complete and batch.get("completed_runs") != 20:
        raise SystemExit(
            f"capture batch is incomplete: {batch.get('completed_runs', 0)}/20"
        )

    family = json.loads(FORMATIONS.read_text(encoding="utf-8"))["families"][
        "ranged_vs_ranged"
    ]
    slots = {
        owner: [
            (float(row["position"]["x"]), float(row["position"]["y"]))
            for row in family["sides"][str(owner)]
        ]
        for owner in (2, 3)
    }
    group.EXPECTED = {2: (492, 27), 3: (474, 18)}
    group.COLLISION_RADIUS = {2: 0.2, 3: 0.25}

    rows = []
    decoded_runs = []
    for manifest_row in sorted(
        batch.get("runs", {}).get(MATCHUP_KEY, []),
        key=lambda row: row["repeat"],
    ):
        repeat = int(manifest_row["repeat"])
        run_dir = capture_root / MATCHUP_KEY / f"run_{repeat:03d}"
        prefix = run_dir / "raw recordings" / MATCHUP_KEY
        decoded_path = run_dir / "grpc_opening_variance.json"
        if decoded_path.exists() and not args.refresh:
            run = json.loads(decoded_path.read_text(encoding="utf-8"))
        else:
            damage = group.decode_damage_from_frames(prefix)
            run = {"repeat": repeat, **group.decode_frames(prefix, damage, slots)}
            decoded_path.write_text(
                json.dumps(run, indent=2) + "\n", encoding="utf-8"
            )
        run["frames_bin"] = str(Path(f"{prefix}.frames.bin").resolve())
        decoded_runs.append(run)
        rows.append(compact_run(run, manifest_row["capture"]))
        print(
            f"run {repeat:02d}: {manifest_row['capture']['winner']} "
            f"{manifest_row['capture']['winner_hp']} HP",
            flush=True,
        )

    winners = Counter(row["winner"] for row in rows)
    report = {
        "schema_version": 1,
        "generated_from_completed_runs": len(rows),
        "capture_manifest": str((capture_root / "capture_manifest.json").resolve()),
        "matchup": MATCHUP_KEY,
        "winner_counts": dict(sorted(winners.items())),
        "by_winner": {
            winner: winner_summary(rows, winner)
            for winner in ("arbalester", "heavy_cav_archer")
        },
        "runs": rows,
    }
    if args.include_participation:
        participation.CAPTURE_ROOT = capture_root / MATCHUP_KEY
        participation_runs = []
        by_repeat = {row["repeat"]: row for row in rows}
        for repeat in sorted(by_repeat):
            decoded = participation.decode_run(repeat)
            participation_runs.append({
                "repeat": repeat,
                "frames_bin": decoded["framesBin"],
                "winner": by_repeat[repeat]["winner"],
                "winner_hp": by_repeat[repeat]["winner_hp"],
                "first_damage_seconds": decoded["firstDamageSeconds"],
                "window_5s": participation.window_summary(decoded["perSecond"], 5),
                "window_10s": participation.window_summary(decoded["perSecond"], 10),
                "window_20s": participation.window_summary(decoded["perSecond"], 20),
                "engagement_ranges": participation.summarize_range_events(
                    decoded["attackStartRanges"]
                ),
                "per_second": decoded["perSecond"],
            })
            print(f"participation {repeat:02d}", flush=True)
        report["participation"] = participation_runs
    output = capture_root / "grpc_20x_analysis.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}", flush=True)


if __name__ == "__main__":
    main()
