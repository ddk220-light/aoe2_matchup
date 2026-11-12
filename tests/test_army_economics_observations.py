import hashlib
import json
from pathlib import Path

import pytest

from aoe2x.economy import observations as module


def fixture(tmp_path, rate=.5):
    # Synthetic test fixture only. Never used in the runtime database's evidence.
    capture = tmp_path / "run1" / "frames.bin"
    capture.parent.mkdir()
    capture.write_bytes(b"synthetic validation unit test")
    activity = {"id": "food", "scenarioSignature": "fixture", "outputs": {"food": .5, "wood": -.05, "gold": 0, "stone": 0}}
    civs = {"Test": {"activities": [activity]}}
    document = {"sourceSha256": "source", "windows": [{"modelKey": module.model_key(activity),
        "capturePath": "run1/frames.bin", "captureSha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
        "runNumber": 1, "startGameSecond": 60, "endGameSecond": 660, "villagerSeconds": 6000,
        "resourceDeltas": {"food": rate * 6000, "wood": -300}}]}
    manifest = tmp_path / "observations.json"
    manifest.write_text(json.dumps(document))
    return civs, manifest, document


def test_missing_measurements_cannot_release(tmp_path):
    civs, _, _ = fixture(tmp_path)
    report = module.validate_observations(civs, None, "source", tmp_path)
    assert report["blockers"][0]["code"] == "controlled_observations_missing"


def test_explicit_deferral_keeps_catalog_without_claiming_validation(tmp_path):
    civs, _, _ = fixture(tmp_path)
    report = module.validate_observations(civs, None, "source", tmp_path, require_measurements=False)
    assert report["status"] == "deferred_by_user"
    assert not report["requiredForRelease"]
    assert report["blockers"] == []
    assert report["comparisons"] == []
    assert len(report["required"]) == 1


def test_deferral_does_not_hide_a_supplied_failed_measurement(tmp_path):
    civs, manifest, _ = fixture(tmp_path, .6)
    report = module.validate_observations(civs, manifest, "source", tmp_path, require_measurements=False)
    assert report["status"] == "incomplete_or_failed"
    assert report["blockers"][0]["code"] == "gathering_measurement_mismatch"


@pytest.mark.parametrize("rate,passed", [(.5, True), (.504, True), (.506, False)])
def test_measurements_validate_without_fitting_model(tmp_path, rate, passed):
    civs, manifest, _ = fixture(tmp_path, rate)
    report = module.validate_observations(civs, manifest, "source", tmp_path)
    assert report["comparisons"][0]["passed"] == passed
    assert bool(report["blockers"]) != passed
    assert civs["Test"]["activities"][0]["outputs"]["food"] == .5


@pytest.mark.parametrize("invalid", ["source", "capture", "overlap", "window"])
def test_mismatched_or_duplicate_evidence_rejected(tmp_path, invalid):
    civs, manifest, doc = fixture(tmp_path)
    if invalid == "source": doc["sourceSha256"] = "other"
    if invalid == "capture": doc["windows"][0]["captureSha256"] = "other"
    if invalid == "overlap": doc["windows"].append(doc["windows"][0].copy())
    if invalid == "window": doc["windows"][0]["villagerSeconds"] = -1
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        module.validate_observations(civs, manifest, "source", tmp_path)
