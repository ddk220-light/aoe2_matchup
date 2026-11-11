"""Single source of truth for repo-anchored paths.

Every module that reads/writes a committed data artifact resolves it
through these constants instead of os.path.dirname(__file__) — so files
can move between layers without breaking readers.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = REPO_ROOT / "data"
# Committed golden artifacts (reference/derived/pool/patches DBs, civ power
# units, civ_top_units.json).
GOLDEN_DIR = DATA_DIR / "golden"
# Layer-1 external inputs (gitignored content + committed MANIFEST.md).
INPUTS_DIR = DATA_DIR / "inputs"
EXTRACTED_DIR = INPUTS_DIR / "extracted_data"
# Machine-local working artifacts (sim caches, patch-pipeline intermediates,
# local matchup DBs) — gitignored wholesale.
LOCAL_DIR = DATA_DIR / "local"

# Authoring copy of the site media (served from Blob in production), mirroring
# the old website static/ layout: img/, anim/ and the data/ media manifests
# (unit_sprites.json, unit_anims.json, anim_sheets.json).
MEDIA_DIR = DATA_DIR / "media"
# The retired legacy browser client (engine, simulate.js, renderer, lab harness,
# CSS): research/parity code only, never published by the live site.
LEGACY_CLIENT_DIR = REPO_ROOT / "legacy" / "client"
