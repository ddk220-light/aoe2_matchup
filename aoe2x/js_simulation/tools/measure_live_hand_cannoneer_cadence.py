"""Measure Spanish Hand Cannoneer damage-wave cadence in current live captures."""
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
OUTPUT = (
    ROOT / "calibration" / "reports" / "ranged_matrix_current_engine_2026-08-29"
    / "spanish_hand_cannoneer_live_cadence.json"
)
MELEE_MASTERS = {
    "paladin": 569,
    "elite_steppe": 1372,
    "hussar": 441,
    "champion": 567,
}


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def reload_band(values: list[float]) -> list[float]:
    """Keep clean adjacent waves around the independently documented reload."""
    return [value for value in values if 2.5 <= value <= 3.5]


def damage_waves(events: list[dict], gap_seconds: float = 1.0) -> list[list[float]]:
    times = sorted({row["t"] for row in events if row["victim_owner"] == 3})
    waves: list[list[float]] = []
    for timestamp in times:
        if not waves or timestamp - waves[-1][-1] > gap_seconds:
            waves.append([timestamp])
        else:
            waves[-1].append(timestamp)
    return waves


def main() -> None:
    capture = json.loads(
        (CAPTURE_ROOT / "capture_manifest.json").read_text(encoding="utf-8")
    )
    report = {
        "schema_version": 1,
        "source": str((CAPTURE_ROOT / "capture_manifest.json").relative_to(ROOT)),
        "clock": "raw gRPC game seconds",
        "wave_rule": "unique damage timestamps joined while adjacent gaps are <= 1.0s",
        "matchups": {},
    }
    all_intervals: list[float] = []
    for key in capture["matchup_keys"]:
        if not key.startswith("hand_cannoneer_vs_"):
            continue
        matchup = capture["matchups"][key]
        melee_slug = matchup["side2"]["slug"]
        group.EXPECTED = {
            2: (5, matchup["side1"]["count"]),
            3: (MELEE_MASTERS[melee_slug], matchup["side2"]["count"]),
        }
        rows = []
        for repeat in range(1, 6):
            prefix = (
                CAPTURE_ROOT / key / f"run_{repeat:03d}" / "raw recordings" / key
            )
            events = group.decode_damage_from_frames(prefix)
            waves = damage_waves(events)
            centers = [statistics.median(wave) for wave in waves]
            intervals = [round(right - left, 4)
                         for left, right in zip(centers, centers[1:])]
            all_intervals.extend(intervals)
            rows.append({
                "repeat": repeat,
                "damage_wave_centers": [round(value, 4) for value in centers],
                "damage_wave_sizes": [len(wave) for wave in waves],
                "adjacent_wave_intervals": intervals,
                "median_interval": median(intervals),
            })
            print(f"{key} {repeat}/5: {len(waves)} waves", flush=True)
        intervals = [value for row in rows for value in row["adjacent_wave_intervals"]]
        report["matchups"][key] = {
            "runs": rows,
            "median_adjacent_wave_interval": median(intervals),
            "median_reload_band_interval": median(reload_band(intervals)),
            "reload_band_interval_count": len(reload_band(intervals)),
            "interval_count": len(intervals),
        }
    report["all_matchups_median_adjacent_wave_interval"] = median(all_intervals)
    report["all_matchups_median_reload_band_interval"] = median(
        reload_band(all_intervals)
    )
    report["reload_band_seconds"] = [2.5, 3.5]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
