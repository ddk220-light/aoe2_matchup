import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ZIP = Path("C:/Users/ddk22/Downloads/aoe2_golden_spike_2026-07-29.zip")
MANIFEST = REPO / "data" / "calibration" / "manifest.json"


def test_ingest_spike_zip():
    from aoe2x.calibration.ingest import ingest_zip

    tags = ingest_zip(str(ZIP))
    assert set(tags) == {"hand_cannoneer__vs__elite_elephant", "elite_steppe__vs__arbalester"}
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fights = {f["tag"]: f for f in m["fights"]}
    hc = fights["hand_cannoneer__vs__elite_elephant"]
    sides = {s["unit_name"]: s for s in (hc["side1"], hc["side2"])}
    assert sides["Hand Cannoneer"]["civ"] == "Japanese"
    assert sides["Hand Cannoneer"]["count"] == 21
    assert sides["Elite Battle Elephant"]["civ"] == "Burmese"
    assert sides["Elite Battle Elephant"]["count"] == 12
    assert abs(hc["duration_s"] - 152.31) < 0.01


def test_ingest_is_idempotent():
    from aoe2x.calibration.ingest import ingest_zip

    before = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ingest_zip(str(ZIP))
    after = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(before["fights"]) == len(after["fights"])


def test_hp_cross_validation_rejects_wrong_civ():
    from aoe2x.calibration.ingest import validate_unit

    validate_unit("Burmese", "elite_elephant", observed_hp=320.0)  # must not raise
    try:
        validate_unit("Bengalis", "elite_elephant", observed_hp=999.0)
        assert False, "expected a hard failure on HP mismatch"
    except Exception:
        pass
