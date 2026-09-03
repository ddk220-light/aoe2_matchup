"""Decode and summarize the five-repeat current ranged golden matrix."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import statistics

import analyze_live_melee_group_variance as group


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations" / "ranged_matrix_5x_2026-08-29"
)
FORMATIONS = ROOT / "fixtures" / "current_ranged_golden_formations.json"
UNIT_FIXTURES = {
    "arbalester": (492, "arbalester_chinese_imperial.json"),
    "hand_cannoneer": (5, "hand_cannoneer_spanish_imperial.json"),
    "heavy_cav_archer": (474, "heavy_cav_archer_saracens_imperial.json"),
    "paladin": (569, "paladin_spanish_imperial.json"),
    "elite_steppe": (1372, "elite_steppe_lancer_cumans_imperial.json"),
    "hussar": (441, "hussar_spanish_imperial.json"),
    "champion": (567, "champion_chinese_imperial.json"),
}


def quantiles(values):
    values = [value for value in values if value is not None]
    return group.quantiles(values)


def first_damage_by_owner(run: dict, owner: int):
    values = [
        unit["first_damage_dealt_t"]
        for unit in run["units"]
        if unit["owner"] == owner and unit["first_damage_dealt_t"] is not None
    ]
    return min(values) if values else None


def matchup_summary(runs: list[dict], captures: list[dict]) -> dict:
    base = group.summarize_runs(runs)
    base.update({
        "winner_counts": dict(sorted(Counter(row["winner"] for row in captures).items())),
        "survivors": quantiles([row["survivors"] for row in captures]),
        "winner_hp": quantiles([row["winner_hp"] for row in captures]),
        "elimination_time_video_s": quantiles(
            [row["elimination_time_s"] for row in captures]
        ),
        "first_damage_dealt_game_s": {
            "side2": quantiles([first_damage_by_owner(run, 2) for run in runs]),
            "side3": quantiles([first_damage_by_owner(run, 3) for run in runs]),
        },
        "side2_unique_first_targets": quantiles([
            run["acquisition"]["side2"]["unique_first_targets"] for run in runs
        ]),
        "side3_unique_first_targets": quantiles([
            run["acquisition"]["side3"]["unique_first_targets"] for run in runs
        ]),
    })
    return base


def main() -> None:
    capture = json.loads((CAPTURE_ROOT / "capture_manifest.json").read_text(encoding="utf-8"))
    if capture.get("completed_runs") != 70:
        raise SystemExit(f"capture matrix is incomplete: {capture.get('completed_runs', 0)}/70")
    formations = json.loads(FORMATIONS.read_text(encoding="utf-8"))["families"]
    report = {
        "schema_version": 1,
        "capture_manifest": str((CAPTURE_ROOT / "capture_manifest.json").relative_to(ROOT)),
        "formation_fixture": str(FORMATIONS.relative_to(ROOT)),
        "clock": "raw gRPC game seconds",
        "matchups": {},
    }
    for matchup_key in capture["matchup_keys"]:
        matchup = capture["matchups"][matchup_key]
        slugs = (matchup["side1"]["slug"], matchup["side2"]["slug"])
        counts = (matchup["side1"]["count"], matchup["side2"]["count"])
        masters = (UNIT_FIXTURES[slugs[0]][0], UNIT_FIXTURES[slugs[1]][0])
        fixtures = [
            json.loads((ROOT / "fixtures" / "unit_stats" / UNIT_FIXTURES[slug][1])
                       .read_text(encoding="utf-8"))
            for slug in slugs
        ]
        group.EXPECTED = {2: (masters[0], counts[0]), 3: (masters[1], counts[1])}
        group.COLLISION_RADIUS = {
            2: float(fixtures[0]["collision_size_tiles"]["x"]),
            3: float(fixtures[1]["collision_size_tiles"]["x"]),
        }
        family = formations[matchup["family"]]
        slots = {
            owner: [
                (float(row["position"]["x"]), float(row["position"]["y"]))
                for row in family["sides"][str(owner)]
            ]
            for owner in (2, 3)
        }
        runs = []
        captures = []
        for repeat in range(1, 6):
            run_dir = CAPTURE_ROOT / matchup_key / f"run_{repeat:03d}"
            prefix = run_dir / "raw recordings" / matchup_key
            output = run_dir / "grpc_opening_variance.json"
            if output.exists():
                run = json.loads(output.read_text(encoding="utf-8"))
            else:
                damage = group.decode_damage_from_frames(prefix)
                run = {"repeat": repeat, **group.decode_frames(prefix, damage, slots)}
                output.write_text(
                    json.dumps(run, indent=2) + "\n", encoding="utf-8"
                )
            runs.append(run)
            run_manifest = json.loads(
                (run_dir / "capture_manifest.json").read_text(encoding="utf-8")
            )
            captures.append(run_manifest["capture"])
            print(
                f"{matchup_key} {repeat}/5: first damage "
                f"{run['first_damage']['t_game_s']:.2f}s",
                flush=True,
            )
        report["matchups"][matchup_key] = {
            "family": matchup["family"],
            "side2": {**matchup["side1"], "master": masters[0]},
            "side3": {**matchup["side2"], "master": masters[1]},
            "collision_radius_tiles": {
                "side2": group.COLLISION_RADIUS[2],
                "side3": group.COLLISION_RADIUS[3],
            },
            "summary": matchup_summary(runs, captures),
            "runs": runs,
        }
    (CAPTURE_ROOT / "grpc_matrix_analysis.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {CAPTURE_ROOT / 'grpc_matrix_analysis.json'}")


if __name__ == "__main__":
    main()
