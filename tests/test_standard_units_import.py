"""Regression tests for the authorized standard-units tape importer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "aoe2x" / "js_simulation" / "tools"
sys.path.insert(0, str(TOOLS))

from import_standard_units import (  # noqa: E402
    AUTHORIZED_ARCHIVE,
    REQUIRED_SHA256,
    import_archive,
)


def test_import_fails_closed_for_a_non_authorized_path(tmp_path):
    """Catch a fallback that accepts an archive outside the manifest lock."""
    with pytest.raises(ValueError, match="project-local authorized source"):
        import_archive(tmp_path / "standard-units-copy.zip")


def test_import_rebuilds_the_complete_authorized_standard_units_corpus():
    """Catch dropped recordings, manual truth, or an incomplete raw-tape inventory."""
    truth = import_archive(AUTHORIZED_ARCHIVE)

    assert truth["archive"]["zip_sha256"] == REQUIRED_SHA256
    assert len(truth["rows"]) == 101

    runs = [run for row in truth["rows"] for run in row["runs"]]
    assert len(runs) == 339
    assert sum(run["status"] == "scored" for run in runs) == 338
    assert sum(run["status"] == "timeout" for run in runs) == 1
    assert all(
        run["source_members"]["frames"].startswith("standard_units/raw recordings/")
        and run["source_members"]["frames"].endswith(".frames.bin")
        for run in runs
    )
    assert all(run["source_members"]["summary"].endswith(".summary.json") for run in runs)
    assert all(run["source_members"]["units"].endswith(".units.jsonl.gz") for run in runs)


def test_import_freezes_start_hp_from_tape_samples_when_summary_omits_it():
    """Catch a truth denominator that changes when engine mechanics later change."""
    truth = import_archive(AUTHORIZED_ARCHIVE)
    derived = [
        run
        for row in truth["rows"]
        for run in row["runs"]
        if run["status"] == "scored" and run["winner_starting_hp_source"] == "unit_samples"
    ]

    assert derived
    for run in derived:
        winner = str(run["winner_owner"])
        expected = 100 * run["winner_hp"] / run["starting_hp_by_owner"][winner]
        assert abs(abs(run["signed_score"]) - expected) < 1e-12


def test_import_keeps_one_canonical_start_geometry_per_comparison_row():
    """Catch grouping that silently mixes distinct tape-start formations."""
    truth = import_archive(AUTHORIZED_ARCHIVE)

    for row in truth["rows"]:
        assert len({run["starting_units_hash"] for run in row["runs"]}) == 1
