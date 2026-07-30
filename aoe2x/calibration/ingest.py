"""Ingest recorded-fight "drop" zips into the calibration manifest.

A drop contains one or more decoded fight tapes (10 Hz unit positions, damage
events, ~60 Hz missile positions, in-game commands) plus a `matchups_91.json`
civ authority. This module unpacks a drop, resolves which civilization each
side actually was (tapes only carry unit *names*, not civs), cross-validates
that resolution against the tape's observed spawn HP, and records everything
in `data/calibration/manifest.json` so downstream calibration stages
(truth-card extraction, engine replay, scoring) never have to re-derive it.

Large decoded tapes and raw drop archives live OUTSIDE the repo under
``D:/AI/aoe2_golden/`` — only the manifest and the `matchups.json` civ
authority are committed.

Do not import this module's callers into ``aoe2x/sim/simulation_real.py`` or
``aoe2x/dbgen/config_combat.py`` territory: those files are byte-hashed into
the matchup-row cache key and this pipeline must never touch them.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aoe2x.paths import GOLDEN_DIR, REPO_ROOT

# Large decoded tapes + raw drop archives live outside the repo (never committed).
EXTERNAL_ROOT = Path("D:/AI/aoe2_golden")
TAPES_DIR = EXTERNAL_ROOT / "tapes"
DROPS_DIR = EXTERNAL_ROOT / "drops"

# Committed calibration artifacts.
CALIBRATION_DIR = REPO_ROOT / "data" / "calibration"
MANIFEST_PATH = CALIBRATION_DIR / "manifest.json"
MATCHUPS_PATH = CALIBRATION_DIR / "matchups.json"

REFERENCE_DB_PATH = GOLDEN_DIR / "aoe2_reference.db"

_HP_TOLERANCE = 1e-6


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_matchups(matchups_path: Path) -> list[dict[str, Any]]:
    return json.loads(matchups_path.read_text(encoding="utf-8"))


def resolve_civ(unit_name: str, matchups: list[dict[str, Any]]) -> tuple[str, str]:
    """Resolve a tape's unit display name to (civ, slug) via the matchups authority.

    Each `matchups_91.json` entry carries {civ1, slug1, label1, civ2, slug2,
    label2} for both sides of a matchup; a unit's display name (`label1` /
    `label2`) must map to exactly one (civ, slug) pair across the authority.
    Raises if the name is unknown, or ambiguous (maps to >1 distinct pair —
    would mean the authority list itself is inconsistent). Never guesses.
    """
    found: set[tuple[str, str]] = set()
    for entry in matchups:
        if entry.get("label1") == unit_name:
            found.add((entry["civ1"], entry["slug1"]))
        if entry.get("label2") == unit_name:
            found.add((entry["civ2"], entry["slug2"]))
    if not found:
        raise ValueError(
            f"resolve_civ: no (civ, slug) found for unit_name={unit_name!r} in matchups authority"
        )
    if len(found) > 1:
        raise ValueError(
            f"resolve_civ: ambiguous unit_name={unit_name!r} maps to multiple "
            f"(civ, slug) pairs: {sorted(found)}"
        )
    return next(iter(found))


def validate_unit(civ: str, slug: str, observed_hp: float) -> None:
    """Cross-validate a resolved (civ, slug) against `ref_units.final_hp`.

    Hard-fails (raises ValueError, printing both values) if the row is
    missing or the DB's Imperial-age `final_hp` doesn't match the tape's
    observed spawn HP. Called for every side of every fight during ingest —
    this is the guard against silently mis-resolving a civ.
    """
    conn = sqlite3.connect(str(REFERENCE_DB_PATH))
    try:
        cur = conn.execute(
            "SELECT final_hp FROM ref_units WHERE civ_name = ? AND unit_slug = ? AND age = 'Imperial'",
            (civ, slug),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise ValueError(
            f"validate_unit: no ref_units row for civ_name={civ!r} unit_slug={slug!r} "
            f"age='Imperial' (observed tape hp={observed_hp!r})"
        )
    final_hp = row[0]
    if final_hp is None or abs(final_hp - observed_hp) > _HP_TOLERANCE:
        raise ValueError(
            f"validate_unit: HP mismatch for civ_name={civ!r} unit_slug={slug!r}: "
            f"ref_units.final_hp={final_hp!r} vs tape observed_hp={observed_hp!r}"
        )


def _owner_from_composition_key(key: str) -> int:
    # meta.json composition keys are the in-game owner numbers, e.g. "side2"
    # means owner==2 — NOT a "first side / second side" label. Preserve the
    # real owner number; it goes in each side's "owner" field below.
    if not key.startswith("side") or not key[len("side"):].isdigit():
        raise ValueError(f"ingest_zip: unexpected composition key (expected 'sideN'): {key!r}")
    return int(key[len("side"):])


def _read_units_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _observed_spawn_hp(units_rows: list[dict[str, Any]], owner: int) -> float:
    """Max hp seen for `owner`'s units at the earliest `t` in the tape."""
    owner_rows = [r for r in units_rows if r["owner"] == owner]
    if not owner_rows:
        raise ValueError(f"_observed_spawn_hp: no unit samples for owner={owner}")
    t_min = min(r["t"] for r in owner_rows)
    return max(r["hp"] for r in owner_rows if r["t"] == t_min)


def _load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"fights": []}


def _save_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def ingest_zip(zip_path: str) -> list[str]:
    """Unpack a recorded-fight drop zip and register it in the calibration manifest.

    Extracts the zip to a temp dir, copies each fight's decoded tape files to
    ``D:/AI/aoe2_golden/tapes/<tag>/``, archives the raw zip under
    ``D:/AI/aoe2_golden/drops/``, and copies the drop's `matchups_91.json`
    civ authority into the repo as `data/calibration/matchups.json`.

    For each fight, resolves both sides' (civ, slug) from `meta.json`
    composition unit names via `resolve_civ`, cross-validates each against
    `ref_units.final_hp` via `validate_unit` (hard-fails on mismatch), and
    appends an entry to `data/calibration/manifest.json` keyed by tag.

    Idempotent: re-running on the same zip (same sha256) leaves tags already
    present in the manifest with that sha256 untouched — no duplicates.

    Returns the list of fight tags found in the drop.
    """
    zip_path = Path(zip_path)
    zip_sha256 = _sha256_file(zip_path)

    manifest = _load_manifest()
    fights_by_tag: dict[str, dict[str, Any]] = {f["tag"]: f for f in manifest["fights"]}

    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory(prefix="aoe2_calib_") as tmp:
        tmp_path = Path(tmp)
        zf.extractall(tmp_path)

        decoded_dir = tmp_path / "decoded"
        meta_files = sorted(decoded_dir.glob("*.meta.json"))
        tags = [p.name[: -len(".meta.json")] for p in meta_files]

        matchups_src = tmp_path / "matchups_91.json"
        matchups = _load_matchups(matchups_src)

        for tag in tags:
            existing = fights_by_tag.get(tag)
            if existing is not None and existing.get("zip_sha256") == zip_sha256:
                continue  # already ingested from this exact drop

            meta = json.loads((decoded_dir / f"{tag}.meta.json").read_text(encoding="utf-8"))
            units_rows = _read_units_jsonl_gz(decoded_dir / f"{tag}.units.jsonl.gz")

            composition = meta["composition"]
            side_keys = sorted(composition.keys(), key=_owner_from_composition_key)
            if len(side_keys) != 2:
                raise ValueError(
                    f"ingest_zip: expected exactly 2 sides in composition for tag={tag!r}, "
                    f"got {list(composition)}"
                )

            sides = []
            for side_key in side_keys:
                owner = _owner_from_composition_key(side_key)
                unit_counts = composition[side_key]
                if len(unit_counts) != 1:
                    raise ValueError(
                        f"ingest_zip: expected exactly 1 unit type per side for tag={tag!r} "
                        f"side={side_key!r}, got {unit_counts}"
                    )
                unit_name, count = next(iter(unit_counts.items()))

                civ, slug = resolve_civ(unit_name, matchups)
                observed_hp = _observed_spawn_hp(units_rows, owner)
                validate_unit(civ, slug, observed_hp=observed_hp)

                sides.append(
                    {
                        "owner": owner,
                        "unit_name": unit_name,
                        "civ": civ,
                        "slug": slug,
                        "count": count,
                    }
                )

            # Copy this fight's decoded tape files into the external store.
            tag_dir = TAPES_DIR / tag
            tag_dir.mkdir(parents=True, exist_ok=True)
            for src in decoded_dir.glob(f"{tag}.*"):
                shutil.copy2(src, tag_dir / src.name)

            fights_by_tag[tag] = {
                "tag": tag,
                "zip_sha256": zip_sha256,
                "drop": str(DROPS_DIR / zip_path.name),
                "side1": sides[0],
                "side2": sides[1],
                "duration_s": meta["duration_s"],
                "stream_hz": meta["stream_hz"],
                "ingested_utc": datetime.now(timezone.utc).isoformat(),
            }

        # Archive the raw drop and the civ authority alongside the manifest.
        DROPS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, DROPS_DIR / zip_path.name)

        CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(matchups_src, MATCHUPS_PATH)

    manifest["fights"] = list(fights_by_tag.values())
    _save_manifest(manifest)
    return tags
