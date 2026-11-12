"""Committed inputs of the 2026 baseline (small files; the bulky records stay on RB)."""
from __future__ import annotations

from aoe2x.matchups.paths import BASELINES_DIR, MATCHUPS_DIR, SCENARIOS_DIR

BUNDLES_DIR = MATCHUPS_DIR / "bundles"
CAMPAIGN_2026_BUNDLE = BUNDLES_DIR / "campaign-2026-185872-188329.json.gz"
FROZEN_SCENARIOS = SCENARIOS_DIR / "frozen-ranking-scenarios-v1.json.gz"
BASELINE_2026 = BASELINES_DIR / "campaign-2026"
ADAPTIVE_ORIENTATION = BASELINE_2026 / "orientation-adaptive-inventory.json.gz"
RESULT_INDEX_RECEIPT = BASELINE_2026 / "result-index.json"
INVENTORY_RECEIPT = BASELINE_2026 / "adaptive-inventory-reproduction.json"


def rel(path) -> str:
    from aoe2x.matchups.paths import REPO_ROOT
    return path.relative_to(REPO_ROOT).as_posix()
