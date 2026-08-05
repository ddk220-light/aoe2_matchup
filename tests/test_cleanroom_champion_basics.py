import json
from pathlib import Path

import pytest

from aoe2x.js_simulation.tools.import_champion_basics import import_archive


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SHA = "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE"
ARCHIVE = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "calibration"
    / "source"
    / "aoe2_golden_basics_championvschampion_2026-08-04.zip"
)
SOURCE_OF_TRUTH = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "calibration"
    / "source"
    / "source_of_truth.json"
)
TRUTH_FIXTURE = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "calibration"
    / "fixtures"
    / "champion_basics.json"
)


def test_source_authority_names_only_the_champion_basics_archive():
    authority = json.loads(SOURCE_OF_TRUTH.read_text(encoding="utf-8"))
    assert authority == {
        "archive": "aoe2_golden_basics_championvschampion_2026-08-04.zip",
        "sha256": "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE",
        "recordings": 15,
        "ratios": {"1v1": 3, "2v1": 3, "2v3": 3, "5v3": 3, "6v3": 3},
    }


def test_importer_finds_three_repeats_for_every_ratio():
    manifest, truth = import_archive(ARCHIVE)
    assert len(manifest["runs"]) == 15
    assert {key: len(value["runs"]) for key, value in truth["ratios"].items()} == {
        "1v1": 3,
        "2v1": 3,
        "2v3": 3,
        "5v3": 3,
        "6v3": 3,
    }
    assert all(row["zip_sha256"] == REQUIRED_SHA for row in manifest["runs"])


def test_generated_fixture_matches_checked_in_fixture():
    _, regenerated = import_archive(ARCHIVE)
    checked_in = json.loads(TRUTH_FIXTURE.read_text(encoding="utf-8"))
    assert regenerated == checked_in


def test_authorized_ratio_medians_are_locked():
    truth = json.loads(TRUTH_FIXTURE.read_text(encoding="utf-8"))
    assert {ratio: row["median_winner_hp_pct"] for ratio, row in truth["ratios"].items()} == {
        "1v1": 20.0,
        "2v1": 80.0,
        "2v3": 60.0,
        "5v3": 72.0,
        "6v3": 80.0,
    }


def test_importer_rejects_same_named_archive_outside_project_local_source():
    outside_archive = REPO_ROOT / "outside-source" / ARCHIVE.name
    with pytest.raises(ValueError, match="project-local"):
        import_archive(outside_archive)
