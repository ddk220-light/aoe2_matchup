"""Role: batch-runner — hash sim source files into a 16-char version string.

Used as a row-level cache key in matchup_db: rows with a different
sim_version are re-simulated on the next run, others are skipped.

Hashes simulation_real.py + analysis/config_combat.py BYTE content — never
edit those two files (even a comment) outside a planned full re-sim.
simulation.py (the abstract engine) is deliberately NOT hashed; its only
regression guard is the golden-baseline test (tests/test_simulations.py).
"""

import hashlib
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DEFAULT_FILES = [
    os.path.join(os.path.dirname(__file__), "simulation_real.py"),
    os.path.join(_REPO_ROOT, "analysis", "config_combat.py"),
]


def compute_sim_version(file_paths=None):
    """Return 16-char hex SHA-256 prefix of the concatenated file contents.

    If `file_paths` is None, hashes the canonical sim files (simulation_real.py
    + config_combat.py).
    """
    if file_paths is None:
        file_paths = DEFAULT_FILES
    h = hashlib.sha256()
    for p in file_paths:
        with open(p, "rb") as f:
            h.update(f.read())
        h.update(b"\0")  # separator so concatenation can't collide
    return h.hexdigest()[:16]
