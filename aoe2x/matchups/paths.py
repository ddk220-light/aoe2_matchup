"""Locations used by the matchup rerun tooling."""
from __future__ import annotations

import os
from pathlib import Path

MATCHUPS_DIR = Path(__file__).resolve().parent
REPO_ROOT = MATCHUPS_DIR.parents[1]
ENGINES_DIR = MATCHUPS_DIR / "engines"
NODE_DIR = MATCHUPS_DIR / "node"
CONFIGS_DIR = MATCHUPS_DIR / "configs"
SCENARIOS_DIR = MATCHUPS_DIR / "scenarios"
BASELINES_DIR = MATCHUPS_DIR / "baselines"


def runs_store() -> Path:
    """Where bulky run records go by default: outside the repo.

    ``$MATCHUP_RUNS_STORE`` if set, else ``~/.cache/aoe2-matchup-runs``.
    """
    value = os.environ.get("MATCHUP_RUNS_STORE")
    return Path(value).expanduser() if value else Path.home() / ".cache" / "aoe2-matchup-runs"
