"""Repository locations used by the army-economics data pipeline.

Committed:
  data/army_economics/sources/army-context-2026-11-10/  reviewed source snapshot (.gz) and sidecar JSON
  data/army_economics/sources/handoff-data-2026-11-12/  upstream extraction inputs (.tar.gz) + manifest
  data/army_economics/army_context.db                   compiled runtime database (+ .validation.json)

Restored (git-ignored) by ``python -m aoe2x.economy.restore``:
  data/army_economics/sources/army-context-2026-11-10/army-context.sqlite
  data/local/army-economics/scratch/{production,research,economy}-review/   (with --include-sources)

The runtime database deliberately lives outside ``data/golden``: the release
builder packages every ``data/golden/*.db`` into the deployed backend.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "army_economics"
SOURCES_DIR = DATA_DIR / "sources"
SNAPSHOT_DIR = SOURCES_DIR / "army-context-2026-11-10"
REVIEW_DB = SNAPSHOT_DIR / "army-context.sqlite"
HANDOFF_DIR = SOURCES_DIR / "handoff-data-2026-11-12"
MANIFEST = HANDOFF_DIR / "manifest.json"
RUNTIME_DB = DATA_DIR / "army_context.db"
REFERENCE_DB = REPO_ROOT / "data" / "golden" / "aoe2_reference_simulation.db"
TOOLS_DIR = REPO_ROOT / "tools" / "economy"
CALIBRATION_ROOT = REPO_ROOT / "aoe2x" / "js_simulation" / "calibration"


def scratch_path(relative):
    """Restored upstream extraction inputs (``--include-sources``)."""
    base = Path(os.environ.get("ARMY_ECONOMY_SCRATCH", REPO_ROOT / "data/local/army-economics/scratch"))
    return base / relative


def dat_path(raw):
    """Use an explicit local DAT without rewriting the archived source metadata."""
    if os.environ.get("ARMY_ECONOMY_DAT"):
        return Path(os.environ["ARMY_ECONOMY_DAT"])
    original = Path(raw["source"]["path"])
    return original if original.exists() else scratch_path("production-review/current-input/dat/empires2_x2_p1.dat")
