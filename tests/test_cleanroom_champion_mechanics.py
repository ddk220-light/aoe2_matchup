import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from aoe2x.js_simulation.tools.export_champion_mechanics import (
    export_champion_mechanics,
)
from genieutils.datfile import DatFile


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


def make_reference_db(tmp_path, attack_classes, armor_classes):
    reference_db = tmp_path / "reference.db"
    with sqlite3.connect(reference_db) as connection:
        connection.execute(
            """
            CREATE TABLE ref_units (
                unit_slug TEXT,
                civ_name TEXT,
                age TEXT,
                final_hp REAL,
                final_speed REAL,
                final_range REAL,
                final_reload_time REAL,
                final_attack_delay REAL,
                final_los REAL,
                final_attacks_json TEXT,
                final_armors_json TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ref_units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "champion",
                "Chinese",
                "Imperial",
                70,
                1.06,
                0,
                2,
                0,
                5,
                json.dumps(attack_classes),
                json.dumps(armor_classes),
            ),
        )
    return reference_db


def controlled_dat():
    champion = SimpleNamespace(
        id=567,
        collision_size_x=0.2,
        collision_size_y=0.25,
        collision_size_z=2.0,
        clearance_size=(0.3, 0.35),
        outline_size_x=0.4,
        outline_size_y=0.45,
        outline_size_z=2.5,
        obstruction_type=5,
        obstruction_class=2,
        terrain_restriction=7,
        fly_mode=0,
        hill_mode=1,
        type_50=SimpleNamespace(attack_graphic=2896, frame_delay=3),
    )
    decoy = SimpleNamespace(id=567, collision_size_x=99)
    chinese_units = [None] * 568
    chinese_units[567] = champion
    decoy_units = [None] * 568
    decoy_units[567] = decoy
    return SimpleNamespace(
        civs=[
            SimpleNamespace(name="British", units=decoy_units),
            SimpleNamespace(name="Chinese", units=chinese_units),
        ]
    )


def install_controlled_dat(monkeypatch):
    parsed_paths = []

    def parse(dat_path):
        parsed_paths.append(dat_path)
        return controlled_dat()

    monkeypatch.setattr(DatFile, "parse", staticmethod(parse))
    return parsed_paths


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


def test_exporter_maps_controlled_sources_reproducibly(monkeypatch, tmp_path):
    """Catches bypassing either source, selecting a decoy civ/unit, or nondeterminism."""
    reference_db = make_reference_db(
        tmp_path,
        {"4": 18, "21": 6},
        {"4": 4, "1": 0},
    )
    dat_path = tmp_path / "controlled.dat"
    dat_path.write_bytes(b"controlled complete raw Genie object")
    parsed_paths = install_controlled_dat(monkeypatch)
    reference_before = reference_db.read_bytes()

    first = export_champion_mechanics(reference_db, dat_path)
    second = export_champion_mechanics(reference_db, dat_path)

    assert first == second
    assert parsed_paths == [dat_path, dat_path]
    assert reference_db.read_bytes() == reference_before
    assert first["unit_master"] == 567
    assert first["civilization"] == "Chinese"
    assert first["attack_classes"] == {"4": 18, "21": 6}
    assert first["armor_classes"] == {"1": 0, "4": 4}
    assert first["collision_size_tiles"] == {"x": 0.2, "y": 0.25, "z": 2.0}
    assert first["clearance_size_tiles"] == {"x": 0.3, "y": 0.35}
    assert first["outline_size_tiles"] == {"x": 0.4, "y": 0.45, "z": 2.5}
    assert first["obstruction"] == {"type": 5, "class": 2}
    assert first["movement_blocks"] == {
        "terrain_restriction": 7,
        "fly_mode": 0,
        "hill_mode": 1,
    }
    assert first["attack_graphic"] == 2896
    assert first["frame_delay"] == 3
    assert first["derived"]["damage_vs_self"] == 14
    assert first["provenance"]["reference_db_sha256"] == hashlib.sha256(
        reference_before
    ).hexdigest().upper()
    assert first["provenance"]["dat_sha256"] == hashlib.sha256(
        dat_path.read_bytes()
    ).hexdigest().upper()
    assert first["provenance"]["dat_selector"] == "dat.civs[name='Chinese'].units[567]"
    assert (
        first["provenance"]["fields"]["collision_size_tiles.x"]
        == "unit.collision_size_x"
    )


@pytest.mark.parametrize(
    ("attack_classes", "armor_classes", "message"),
    [
        ({"3": 18}, {"4": 4}, "missing required attack class 4"),
        ({"4": 18}, {"3": 4}, "missing required armor class 4"),
        ({"4": "18"}, {"4": 4}, "attack class 4 must be numeric"),
        ({"4": 18}, {"4": None}, "armor class 4 must be numeric"),
        ({"4": 0}, {"4": 4}, "attack class 4 must be positive"),
    ],
)
def test_exporter_rejects_missing_or_malformed_class_4(
    monkeypatch, tmp_path, attack_classes, armor_classes, message
):
    """Catches substituting a damage class or publishing incomplete mechanics."""
    reference_db = make_reference_db(tmp_path, attack_classes, armor_classes)
    dat_path = tmp_path / "controlled.dat"
    dat_path.write_bytes(b"controlled complete raw Genie object")
    install_controlled_dat(monkeypatch)

    with pytest.raises(ValueError, match=message):
        export_champion_mechanics(reference_db, dat_path)


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


def test_exporter_rejects_a_non_dat_file_clearly(tmp_path):
    """Catches accepting arbitrary input or leaking a raw parser traceback."""
    not_a_dat = tmp_path / "not-a-genie.dat"
    output = tmp_path / "must-not-exist.json"
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
            str(output),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "failed to parse Genie .dat" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()
