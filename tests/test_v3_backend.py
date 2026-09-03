import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

from aoe2x.dbgen.v3_mechanics import (
    MECHANICS_SCHEMA_VERSION,
    canonical_json,
    validate_runtime_profile,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DB = ROOT / "data" / "golden" / "aoe2_reference.db"


def test_every_reference_unit_has_one_default_valid_v3_profile():
    connection = sqlite3.connect(REFERENCE_DB)
    connection.row_factory = sqlite3.Row
    units = connection.execute("SELECT COUNT(*) FROM ref_units").fetchone()[0]
    covered, defaults = connection.execute(
        """
        SELECT COUNT(DISTINCT ref_unit_id), SUM(is_default)
        FROM ref_unit_mechanics
        """
    ).fetchone()
    assert covered == units
    assert defaults == units
    assert not connection.execute(
        """
        SELECT ref_unit_id FROM ref_unit_mechanics
        GROUP BY ref_unit_id HAVING SUM(is_default) != 1
        """
    ).fetchall()
    for row in connection.execute(
        "SELECT schema_version, mechanics_json, mechanics_hash FROM ref_unit_mechanics"
    ):
        assert row["schema_version"] == MECHANICS_SCHEMA_VERSION
        profile = json.loads(row["mechanics_json"])
        validate_runtime_profile(profile)
        assert canonical_json(profile) == row["mechanics_json"]
        assert hashlib.sha256(row["mechanics_json"].encode()).hexdigest() == row["mechanics_hash"]
    connection.close()


def test_database_owns_valid_auxiliary_actor_mechanics():
    connection = sqlite3.connect(REFERENCE_DB)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM ref_auxiliary_mechanics WHERE actor_slug='scout_cavalry'"
    ).fetchone()
    connection.close()
    assert row is not None
    profile = json.loads(row["mechanics_json"])
    validate_runtime_profile(profile)
    assert profile["unit_slug"] == "scout_cavalry"
    assert profile["unit_master"] == 448


def test_existing_combat_endpoint_adds_valid_v3_contract(client):
    response = client.get("/api/ref/combat-unit/Spanish/champion?age=Imperial")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["name"] == "Champion"
    assert payload["mechanics_schema_version"] == MECHANICS_SCHEMA_VERSION
    assert payload["mechanics_mode"] == "default"
    assert payload["mechanics_modes"] == ["default"]
    validate_runtime_profile(payload["mechanics"])
    assert response.get_etag()[0] == payload["mechanics_hash"]


def test_combat_endpoint_exposes_each_weapon_mode(client):
    default = client.get("/api/ref/combat-unit/Shu/war_chariot_shu?age=Imperial")
    barrage = client.get(
        "/api/ref/combat-unit/Shu/war_chariot_shu?age=Imperial&mode=barrage"
    )
    assert default.status_code == barrage.status_code == 200
    default_payload = default.get_json()
    barrage_payload = barrage.get_json()
    assert default_payload["mechanics_mode"] == "focus_fire"
    assert default_payload["mechanics_modes"] == ["focus_fire", "barrage"]
    assert barrage_payload["mechanics_mode"] == "barrage"
    assert default_payload["mechanics_hash"] != barrage_payload["mechanics_hash"]
    assert barrage_payload["mechanics"]["ranged"]["extra_projectile_count"] == 10


def test_battle_config_resolves_direct_scenario_and_counts(client):
    response = client.post(
        "/api/v3/battle-config",
        json={
            "teams": [
                {"civ": "Spanish", "unit_slug": "champion"},
                {"civ": "Spanish", "unit_slug": "paladin"},
            ],
            "army": {"mode": "equal_resources", "budget": 3000},
            "seed": 42,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["seed"] == 42
    assert payload["engagementMode"] == "direct"
    assert payload["scenario"]["family"] == "melee_vs_melee"
    assert payload["scenario"]["hasRangedBuffer"] is False
    assert len(payload["scenario"]["mapFixture"]["map"]["tiles"]) == 256
    assert len(payload["scenario"]["placementByOwner"]["2"]) == 27
    assert all(1 <= team["count"] <= 27 for team in payload["teams"])


def test_battle_config_includes_database_owned_ranged_buffer(client):
    response = client.post(
        "/api/v3/battle-config",
        json={
            "teams": [
                {"civ": "Chinese", "unit_slug": "arbalester", "count": 20},
                {"civ": "Spanish", "unit_slug": "paladin", "count": 20},
            ],
            "army": {"mode": "explicit"},
            "engagement_mode": "ranged_buffer",
            "seed": 7,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    scenario = payload["scenario"]
    assert scenario["family"] == "ranged_vs_melee"
    assert scenario["hasRangedBuffer"] is True
    auxiliary = scenario["auxiliaryArmiesByOwner"]["4"]
    assert len(auxiliary["cells"]) == 9
    assert auxiliary["mechanics"]["unit_master"] == 448
    validate_runtime_profile(auxiliary["mechanics"])
    assert scenario["victoryTeams"] == [
        {"winnerOwner": 2, "owners": [2, 4]},
        {"winnerOwner": 3, "owners": [3]},
    ]


def test_battle_config_accepts_zero_weight_but_rejects_all_zero(client):
    base = {
        "teams": [
            {"civ": "Spanish", "unit_slug": "champion"},
            {"civ": "Spanish", "unit_slug": "paladin"},
        ],
        "army": {
            "mode": "equal_resources",
            "weights": {"food": 1, "wood": 0, "gold": 1.5},
        },
    }
    assert client.post("/api/v3/battle-config", json=base).status_code == 200
    base["army"]["weights"] = {"food": 0, "wood": 0, "gold": 0}
    response = client.post("/api/v3/battle-config", json=base)
    assert response.status_code == 400
    assert "at least one resource weight" in response.get_json()["error"]


def _run_headless(config, workers=2):
    node = shutil.which("node")
    assert node, "Node.js is required for the V3 backend integration test"
    completed = subprocess.run(
        [
            node,
            str(ROOT / "aoe2x" / "js_simulation" / "node" / "headless-runner.mjs"),
            "--workers",
            str(workers),
        ],
        input=json.dumps(config),
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=True,
        timeout=30,
    )
    return json.loads(completed.stdout)["results"]


def test_database_profiles_run_direct_and_buffered_headless_smokes(client):
    direct = client.post(
        "/api/v3/battle-config",
        json={
            "teams": [
                {"civ": "Shu", "unit_slug": "war_chariot_shu", "count": 2},
                {"civ": "Spanish", "unit_slug": "paladin", "count": 2},
            ],
            "army": {"mode": "explicit"},
            "seed": 11,
        },
    ).get_json()
    buffered = client.post(
        "/api/v3/battle-config",
        json={
            "teams": [
                {"civ": "Chinese", "unit_slug": "arbalester", "count": 2},
                {"civ": "Spanish", "unit_slug": "paladin", "count": 2},
            ],
            "army": {"mode": "explicit"},
            "engagement_mode": "ranged_buffer",
            "seed": 12,
        },
    ).get_json()
    results = _run_headless([direct, buffered])
    assert len(results) == 2
    assert all("error" not in result for result in results), results
    assert [result["seed"] for result in results] == [11, 12]
    assert all(result["winnerOwner"] in (2, 3) for result in results)
