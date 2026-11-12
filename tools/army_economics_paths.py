"""Portable locations for the archived army-economics research inputs."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scratch_path(relative):
    base = Path(os.environ.get("ARMY_ECONOMY_SCRATCH", ROOT / "data/local/army-economics/scratch"))
    return base / relative


def dat_path(raw):
    """Use an explicit local DAT without rewriting the archived source metadata."""
    if os.environ.get("ARMY_ECONOMY_DAT"):
        return Path(os.environ["ARMY_ECONOMY_DAT"])
    original = Path(raw["source"]["path"])
    return original if original.exists() else scratch_path("production-review/current-input/dat/empires2_x2_p1.dat")
