"""Full-roster consistency and atomic refresh; behavior is tested in Node."""
import json
from pathlib import Path
import shutil
import sqlite3
import pytest

from aoe2x.dbgen.audit_v3_units import audit
from aoe2x.dbgen.refresh_v3_effects import refresh
from aoe2x.dbgen.v3_mechanics import canonical_json, mechanics_hash, validate_runtime_profile

REFERENCE = Path(__file__).parents[1] / "data/golden/aoe2_reference_simulation.db"


def mutate_profile(connection, civ, slug, update):
    ref_id, mode, encoded = connection.execute(
        "SELECT u.id,m.mode,m.mechanics_json FROM ref_units u JOIN ref_unit_mechanics m "
        "ON m.ref_unit_id=u.id WHERE u.civ_name=? AND u.unit_slug=? AND m.is_default=1",
        (civ, slug)).fetchone()
    profile = json.loads(encoded)
    update(profile)
    connection.execute("UPDATE ref_unit_mechanics SET mechanics_json=?,mechanics_hash=? "
                       "WHERE ref_unit_id=? AND mode=?",
                       (canonical_json(profile), mechanics_hash(profile), ref_id, mode))


def test_every_unit_matches_reference_and_records_source_limitations():
    report = audit(REFERENCE)
    assert report["errors"] == []
    assert report["summary"]["reference_units"] == 1030
    assert report["summary"]["runtime_profiles"] == 1031
    assert report["summary"]["civilizations"] == 56
    assert report["summary"]["auxiliary_profiles"] == 1
    assert report["raw_source_verified"] is False
    assert report["summary"]["profiles_with_followups"] > 0
    assert len(report["source_builds"]) == 1
    assert len(report["abilities"]) == 33


def test_jarl_is_ranged_melee_without_armor_stripping():
    with sqlite3.connect(REFERENCE) as connection:
        row = connection.execute(
            "SELECT m.mechanics_json FROM ref_unit_mechanics m JOIN ref_units u ON u.id=m.ref_unit_id "
            "WHERE u.civ_name='Varangians' AND u.unit_slug='elite_jarl_varangians' AND m.is_default=1"
        ).fetchone()
    profile = json.loads(row[0])
    assert profile["ranged"] is not None
    assert profile["attack_classes"]["4"] > 0
    assert profile["effects"].get("armor_strip_per_hit", 0) == 0
    from aoe2x.dbgen.audit_v3_units import UNIT_FOLLOWUPS
    assert "elite_jarl_varangians" not in UNIT_FOLLOWUPS


def test_audit_detects_stats_armor_and_dropped_effect_even_with_valid_hashes(tmp_path):
    candidate = tmp_path / "candidate.db"
    shutil.copyfile(REFERENCE, candidate)
    with sqlite3.connect(candidate) as connection:
        mutate_profile(connection, "Spanish", "champion", lambda p: p.update(hp=p["hp"] + 1))
        mutate_profile(connection, "Spanish", "siege_ram", lambda p: p["armor_classes"].update({"4": 0}))
        mutate_profile(connection, "Gurjaras", "elite_shrivamsha_rider_gurjaras",
                       lambda p: p["effects"].pop("dodge_shield_max"))
    report = audit(candidate)
    assert any("Spanish/champion" in e and "hp:" in e for e in report["errors"])
    assert any("Spanish/siege_ram" in e and "armor_classes" in e for e in report["errors"])
    assert any("Gurjaras/elite_shrivamsha" in e and "effects missing/stale" in e for e in report["errors"])


def test_effect_refresh_is_idempotent_preserves_other_fields_and_is_atomic(tmp_path):
    candidate = tmp_path / "candidate.db"
    shutil.copyfile(REFERENCE, candidate)
    assert refresh(candidate, write=True)["changed_profiles"] == 0
    with sqlite3.connect(candidate) as connection:
        before = dict(connection.execute("SELECT ref_unit_id,mechanics_json FROM ref_unit_mechanics WHERE is_default=1"))
        mutate_profile(connection, "Gurjaras", "elite_shrivamsha_rider_gurjaras",
                       lambda p: p["effects"].pop("dodge_shield_max"))
    assert refresh(candidate)["changed_profiles"] == 1
    assert refresh(candidate, write=True)["changed_profiles"] == 1
    with sqlite3.connect(candidate) as connection:
        after = dict(connection.execute("SELECT ref_unit_id,mechanics_json FROM ref_unit_mechanics WHERE is_default=1"))
    assert before == after
    assert refresh(candidate, write=True)["changed_profiles"] == 0
    with sqlite3.connect(candidate) as connection:
        mutate_profile(connection, "Gurjaras", "elite_shrivamsha_rider_gurjaras",
                       lambda p: p["effects"].pop("dodge_shield_max"))
        connection.execute("UPDATE ref_unit_mechanics SET mechanics_hash='invalid' WHERE ref_unit_id="
                           "(SELECT MAX(ref_unit_id) FROM ref_unit_mechanics)")
    before_failure = candidate.read_bytes()
    with pytest.raises(ValueError, match="hash mismatch"):
        refresh(candidate, write=True)
    assert candidate.read_bytes() == before_failure


def test_invalid_defensive_parameters_fail_the_server_boundary():
    with sqlite3.connect(REFERENCE) as connection:
        profile = json.loads(connection.execute("SELECT mechanics_json FROM ref_unit_mechanics LIMIT 1").fetchone()[0])
    profile["effects"]["bonus_damage_reduction"] = 2
    with pytest.raises(ValueError, match="bonus_damage_reduction"):
        validate_runtime_profile(profile)


def test_web_serves_the_audited_profiles_without_losing_defensive_effects(client):
    for civ, slug, effect, expected in [
        ("Gurjaras", "elite_shrivamsha_rider_gurjaras", "dodge_shield_max", 7),
        ("Jurchens", "elite_iron_pagoda_jurchens", "melee_block_recharge_seconds", 30),
        ("Sicilians", "hussar", "bonus_damage_reduction", 0.4),
    ]:
        response = client.get(f"/api/ref/combat-unit/{civ}/{slug}")
        assert response.status_code == 200
        mechanics = response.json["mechanics"]
        assert mechanics["effects"][effect] == expected
        assert response.json["mechanics_hash"] == mechanics_hash(mechanics)
