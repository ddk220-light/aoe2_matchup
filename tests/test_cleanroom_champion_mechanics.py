import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "fixtures"
    / "unit_stats"
    / "champion_chinese_imperial.json"
)
EXPORTER = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "tools"
    / "export_champion_mechanics.py"
)
REFERENCE_DB = REPO_ROOT / "data" / "golden" / "aoe2_reference.db"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_chinese_champion_core_mechanics_are_source_backed():
    """Catches exporting a wrong unit/civ row or hard-coding the self damage."""
    fixture = load_fixture()
    assert fixture["unit_master"] == 567
    assert fixture["civilization"] == "Chinese"
    assert fixture["hp"] == 70
    assert fixture["speed_tiles_per_second"] == 1.06
    assert fixture["attack_range_tiles"] == 0.0
    assert fixture["reload_seconds"] == 2.0
    assert fixture["attack_delay_seconds"] == 0.0
    assert fixture["line_of_sight_tiles"] == 5.0
    assert fixture["outline_size_tiles"]["x"] == 0.2
    assert fixture["attack_classes"] == {
        "4": 18,
        "8": 0,
        "15": 0,
        "21": 6,
        "29": 8,
        "30": 0,
    }
    assert fixture["armor_classes"] == {"1": 0, "3": 5, "4": 4, "31": 0}
    assert fixture["derived"]["damage_vs_self"] == 14


def test_collision_fields_have_raw_dat_provenance():
    """Catches substituting outline/viewer markers for raw movement geometry."""
    fixture = load_fixture()
    assert fixture["collision_size_tiles"] == {"x": 0.2, "y": 0.2, "z": 2.0}
    assert fixture["clearance_size_tiles"] == {"x": 0.2, "y": 0.2}
    assert fixture["obstruction"] == {"type": 5, "class": 2}
    assert fixture["movement_blocks"] == {
        "terrain_restriction": 7,
        "fly_mode": 0,
        "hill_mode": 0,
    }
    assert fixture["attack_graphic"] == 2896
    assert fixture["frame_delay"] == 0
    assert fixture["provenance"]["reference_db_sha256"]
    assert fixture["provenance"]["dat_sha256"]
    fields = fixture["provenance"]["fields"]
    assert fields["age"] == "ref_units.age"
    assert fields["collision_size_tiles.x"] == "unit.collision_size_x"
    assert fields["clearance_size_tiles.x"] == "unit.clearance_size[0]"
    assert fields["obstruction.type"] == "unit.obstruction_type"
    assert fields["attack_graphic"] == "unit.type_50.attack_graphic"
    assert fields["frame_delay"] == "unit.type_50.frame_delay"


def test_exporter_requires_an_explicit_dat_argument():
    """Catches silently guessing an installed or legacy .dat path."""
    result = subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--reference-db",
            str(REFERENCE_DB),
            "--output",
            str(EXPORTER.with_name("_unused.json")),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "the following arguments are required: --dat" in result.stderr


def test_exporter_rejects_a_non_dat_file_clearly():
    """Catches accepting arbitrary input or leaking a raw parser traceback."""
    not_a_dat = EXPORTER.with_name("_not_a_genie_test.dat")
    try:
        not_a_dat.write_bytes(b"not a Genie data file")
        result = subprocess.run(
            [
                sys.executable,
                str(EXPORTER),
                "--reference-db",
                str(REFERENCE_DB),
                "--dat",
                str(not_a_dat),
                "--output",
                str(EXPORTER.with_name("_unused.json")),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        not_a_dat.unlink(missing_ok=True)
    assert result.returncode != 0
    assert "failed to parse Genie .dat" in result.stderr
    assert "Traceback" not in result.stderr
