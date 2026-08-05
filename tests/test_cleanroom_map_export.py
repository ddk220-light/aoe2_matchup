import hashlib
import json
from pathlib import Path

from aoe2x.js_simulation.tools.export_golden_map import extract_map


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "fixtures"
    / "source"
    / "golden_meleevsmelee.aoe2scenario"
)
EXPORTED = SCENARIO.parent.parent / "golden_map.json"
EXPECTED_SCENARIO_SHA256 = (
    "f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4"
)


def test_extracts_complete_golden_map_without_inferred_geometry():
    """Dropping a terrain tile or Gaia object must make Stage 0 fail."""
    payload = extract_map(SCENARIO)

    assert payload["schema_version"] == 1
    assert payload["source"]["sha256"] == EXPECTED_SCENARIO_SHA256
    assert payload["map"]["width"] == 16
    assert payload["map"]["height"] == 16
    assert len(payload["map"]["tiles"]) == 256
    assert len(payload["map"]["gaia_objects"]) == 101
    assert payload["terrain_counts"] == {
        "6:DIRT_1": 156,
        "10:FOREST_OAK": 7,
        "56:FOREST_RAINFOREST": 1,
        "128:FOREST_DRY_SOUTH_AMERICAN": 92,
    }
    assert payload["object_counts"] == {
        "411:TREE_OAK_FOREST": 7,
        "1053:BUSH_B": 7,
        "1063:TREE_ACACIA": 14,
        "1146:TREE_RAINFOREST": 1,
        "1348:TREE_ITALIAN_PINE": 32,
        "1349:TREE_OLIVE": 8,
        "2082:PANDA_ROCK": 1,
        "2567:TREE_OAK_GREEN": 12,
        "2570:TREE_MONKEY_PUZZLE": 19,
    }


def test_tiles_are_unique_and_sorted_in_scenario_row_order():
    """A transposed or duplicated map export must not pass unnoticed."""
    tiles = extract_map(SCENARIO)["map"]["tiles"]
    coordinates = [(tile["x"], tile["y"]) for tile in tiles]

    assert len(set(coordinates)) == 256
    assert coordinates == sorted(coordinates, key=lambda point: (point[1], point[0]))
    assert coordinates[0] == (0, 0)
    assert coordinates[-1] == (15, 15)


def test_checked_in_fixture_is_exact_export():
    """A stale hand-edited JSON fixture must differ from the parser output."""
    expected = extract_map(SCENARIO)
    actual = json.loads(EXPORTED.read_text(encoding="utf-8"))

    assert actual == expected


def test_source_binary_matches_recorded_repository_object():
    """Selecting a different golden scenario binary must be explicit."""
    assert hashlib.sha256(SCENARIO.read_bytes()).hexdigest() == EXPECTED_SCENARIO_SHA256
