"""Single source of truth for repo-anchored paths.

Every module that reads/writes a committed data artifact resolves it
through these constants instead of os.path.dirname(__file__) — so files
can move between layers without breaking readers.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = REPO_ROOT / "data"
# Committed golden artifacts (reference/derived/pool/patches DBs, civ power
# units...). Populated in migration Stage 4; until then artifacts live in
# webapp/ (see WEBAPP_DIR users).
GOLDEN_DIR = DATA_DIR / "golden"
# Layer-1 external inputs (gitignored content + committed MANIFEST.md).
INPUTS_DIR = DATA_DIR / "inputs"
EXTRACTED_DIR = INPUTS_DIR / "extracted_data"
# Machine-local working artifacts (sim caches, patch-pipeline intermediates,
# local matchup DBs) — gitignored wholesale.
LOCAL_DIR = DATA_DIR / "local"

# Transitional anchor while the Flask app still lives in webapp/
# (removed at the end of the migration).
WEBAPP_DIR = REPO_ROOT / "webapp"
