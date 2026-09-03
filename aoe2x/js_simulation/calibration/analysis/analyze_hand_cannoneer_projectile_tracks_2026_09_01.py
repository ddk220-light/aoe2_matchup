"""Trace live Hand Cannoneer projectile headings for the Scorpion matchup."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_scorpion_bolt_tracks_2026_08_31 as tracks  # noqa: E402


MATCHUP = "heavy_scorpion_vs_hand_cannoneer"
CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31"
)
OUTPUT_ROOT = (
    ROOT / "calibration" / "reports"
    / "scorpion_hca_hc_deep_dive_2026-09-01"
)


def main() -> None:
    # The shared tracker is geometry-generic despite its historical names.
    tracks.SCORPION_MASTER = 5
    tracks.BOLT_MASTER = 380
    for repeat in range(1, 6):
        run_name = f"run_{repeat:03d}"
        tracks.main({
            "captureManifest": CAPTURE_ROOT / "capture_manifest.json",
            "frames": (
                CAPTURE_ROOT / MATCHUP / run_name / "raw recordings"
                / f"{MATCHUP}.frames.bin"
            ),
            "matchup": MATCHUP,
            "output": OUTPUT_ROOT / f"live_hc_projectiles_{run_name}.json",
            "scorpionOwner": 3,
            "expected": Counter({2: 17, 3: 27}),
        })


if __name__ == "__main__":
    main()
