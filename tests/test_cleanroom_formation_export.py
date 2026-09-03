import json
from pathlib import Path

from aoe2x.js_simulation.tools.export_golden_formation import extract_formation


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "fixtures"
    / "source"
    / "golden_meleevsmelee.aoe2scenario"
)
EXPORTED = SCENARIO.parent.parent / "golden_formation_21v21.json"
EXPECTED_SHA256 = "f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4"


def test_extracts_the_exact_units_retained_by_the_golden_builder():
    payload = extract_formation(SCENARIO)

    assert payload["schema_version"] == 1
    assert payload["source"]["sha256"] == EXPECTED_SHA256
    assert [unit["reference_id"] for unit in payload["sides"]["2"]] == [
        *range(1628, 1643),
        *range(1739, 1745),
    ]
    assert [unit["reference_id"] for unit in payload["sides"]["3"]] == list(
        range(1699, 1720)
    )
    assert {unit["unit_const"] for unit in payload["sides"]["2"]} == {38, 569}
    assert {unit["unit_const"] for unit in payload["sides"]["3"]} == {1372}
    assert payload["sides"]["2"][0]["position"] == {"x": 3.5, "y": 6.5, "z": 0.0}
    assert payload["sides"]["2"][-1]["position"] == {"x": 6.5, "y": 3.5, "z": 0.0}
    assert payload["sides"]["3"][0]["position"] == {"x": 5.5, "y": 8.5, "z": 0.0}
    assert payload["sides"]["3"][-1]["position"] == {"x": 1.5, "y": 10.5, "z": 0.0}


def test_initial_21v21_layout_has_no_blocked_or_duplicate_cells():
    payload = extract_formation(SCENARIO)

    assert payload["validation"] == {"valid": True, "conflicts": []}
    cells = {
        (int(unit["position"]["x"]), int(unit["position"]["y"]))
        for side in payload["sides"].values()
        for unit in side
    }
    assert len(cells) == 42


def test_checked_in_formation_fixture_is_an_exact_parser_export():
    assert json.loads(EXPORTED.read_text(encoding="utf-8")) == extract_formation(SCENARIO)
