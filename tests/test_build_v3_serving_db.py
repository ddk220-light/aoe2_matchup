import json
import sqlite3

import pytest

from aoe2x.rank.build_v3_serving_db import build_serving_db
from aoe2x.rank.derived_db import create_db as create_derived_db


COMMON_SCORE_TYPES = {
    "general_combat",
    "anti_cav",
    "anti_archer",
    "anti_trash",
    "aa_v3_27_vs_arb",
    "aa_v3_27_vs_arb_raw",
    "ac_v3_27_vs_paladin",
    "ac_v3_27_vs_paladin_raw",
    "at_v3_27_vs_elite_skirm",
    "at_v3_27_vs_elite_skirm_raw",
    "at_v3_27_vs_halb",
    "at_v3_27_vs_halb_raw",
    "at_v3_27_vs_hussar",
    "at_v3_27_vs_hussar_raw",
    "gc_v3_27_vs_arb",
    "gc_v3_27_vs_arb_raw",
    "gc_v3_27_vs_champ",
    "gc_v3_27_vs_champ_raw",
    "gc_v3_27_vs_paladin",
    "gc_v3_27_vs_paladin_raw",
}

VARIANTS = [
    ("militia", "infantry", "Aztecs", "elite_jaguar_warrior_aztecs", "Jaguar Warrior", "militia_value", 80.0),
    ("militia", "infantry", "Vikings", "champion", "Champion", "militia_value", 60.0),
    ("archer", "archery", "Britons", "arbalester", "Arbalester", "ranged_effectiveness", 70.0),
    ("knight", "cavalry", "Franks", "paladin", "Paladin", "stable_effectiveness", 90.0),
    ("mangonel", "siege", "Celts", "siege_onager", "Siege Onager", "v3_combat_effectiveness", 75.0),
]

YARDSTICKS = [
    ("Vikings", "champion", "Champion"),
    ("Spanish", "paladin", "Paladin"),
    ("Chinese", "arbalester", "Arbalester"),
    ("Spanish", "halberdier", "Halberdier"),
    ("Spanish", "imp_elite_skirm", "Elite Skirmisher"),
    ("Spanish", "hussar", "Hussar"),
]


def _summary(failures=0):
    return {
        "failures": failures,
        "matchups": len(VARIANTS) * len(YARDSTICKS),
        "runs": len(VARIANTS) * len(YARDSTICKS) * 5,
        "scores": len(VARIANTS) * 21,
    }


def _create_v3(path, *, failures=0, resource_weights=None, incomplete_matchup=False):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE battle_scores (
            line_slug TEXT, stage_name TEXT, age TEXT, civ_name TEXT,
            unit_slug TEXT, unit_name TEXT, score_type TEXT, score_value REAL,
            rank INTEGER, median_delta REAL, source_engine TEXT
        );
        CREATE TABLE campaign_failures (
            civ_name TEXT, unit_slug TEXT, line_slug TEXT, stage_name TEXT,
            opponent_civ TEXT, opponent_slug TEXT, seed INTEGER,
            error_name TEXT, error_message TEXT, attempts INTEGER,
            task_json TEXT, updated_at TEXT
        );
        CREATE TABLE campaign_metadata (
            key TEXT PRIMARY KEY, value_json TEXT, updated_at TEXT
        );
        CREATE TABLE ranking_matchups (
            civ_name TEXT, unit_slug TEXT, unit_name TEXT, line_slug TEXT,
            stage_name TEXT, opponent_civ TEXT, opponent_slug TEXT,
            opponent_name TEXT, count2 INTEGER, count3 INTEGER,
            engagement_mode TEXT, used_player4 INTEGER, resolved_seeds INTEGER,
            failed_seeds INTEGER, winner_owners_observed TEXT,
            winner_flipped INTEGER, mean_signed_hp_pct REAL,
            min_signed_hp_pct REAL, max_signed_hp_pct REAL,
            mean_winner_hp REAL, min_winner_hp REAL, max_winner_hp REAL,
            mean_duration_seconds REAL, min_duration_seconds REAL,
            max_duration_seconds REAL, mean_winner_survivors REAL,
            min_winner_survivors INTEGER, max_winner_survivors INTEGER,
            updated_at TEXT
        );
        CREATE TABLE ranking_runs (
            civ_name TEXT, unit_slug TEXT, unit_name TEXT, line_slug TEXT,
            stage_name TEXT, opponent_civ TEXT, opponent_slug TEXT,
            opponent_name TEXT, seed INTEGER, count2 INTEGER, count3 INTEGER,
            engagement_mode TEXT, used_player4 INTEGER, family TEXT,
            winner_owner INTEGER, winner_hp REAL, starting_hp_owner2 REAL,
            starting_hp_owner3 REAL, signed_hp_pct REAL, ticks INTEGER,
            duration_seconds REAL, survivors_owner2 INTEGER,
            survivors_owner3 INTEGER, survivors_owner4 INTEGER,
            winner_survivors INTEGER, final_state_hash TEXT,
            event_log_hash TEXT, unit_mechanics_hash TEXT,
            opponent_mechanics_hash TEXT, completed_at TEXT, outcome TEXT,
            timed_out INTEGER, remaining_hp_owner2 REAL,
            remaining_hp_owner3 REAL, remaining_hp_owner4 REAL
        );
        """
    )
    metadata = {
        "engine_revision": "engine-test-revision",
        "last_summary": _summary(failures),
        "resource_weights": resource_weights or {"food": 1, "wood": 1, "gold": 1},
        "seed_count": 5,
        "seeds": [0, 1, 2, 3, 4],
        "source_mechanics_build": "mechanics-test-hash",
        "stage_order": ["infantry", "archery", "cavalry", "siege"],
        "unit_cap": 27,
        "unit_filter": None,
    }
    conn.executemany(
        "INSERT INTO campaign_metadata VALUES (?, ?, '2026-09-03T00:00:00Z')",
        [(key, json.dumps(value, separators=(",", ":"))) for key, value in metadata.items()],
    )

    for line, stage, civ, slug, name, final_type, final_value in VARIANTS:
        for index, score_type in enumerate(sorted(COMMON_SCORE_TYPES | {final_type})):
            value = final_value if score_type == final_type else float(index)
            conn.execute(
                "INSERT INTO battle_scores VALUES (?, ?, 'imperial', ?, ?, ?, ?, ?, 99, 99, 'simulationv3')",
                (line, stage, civ, slug, name, score_type, value),
            )
        for opponent_index, (opp_civ, opp_slug, opp_name) in enumerate(YARDSTICKS):
            resolved = 4 if incomplete_matchup and civ == "Aztecs" and opponent_index == 0 else 5
            conn.execute(
                """INSERT INTO ranking_matchups VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, 27, 27, 'cohesive', 0, ?, 0,
                    '[2]', 0, 0.5, 0.4, 0.6, 100, 90, 110,
                    30, 25, 35, 2, 1, 3, '2026-09-03T00:00:00Z'
                )""",
                (civ, slug, name, line, stage, opp_civ, opp_slug, opp_name, resolved),
            )
            for seed in range(5):
                conn.execute(
                    """INSERT INTO ranking_runs VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, 27, 27, 'cohesive', 0, ?,
                        2, 100, 2700, 2700, 0.5, 600, 30, 2, 0, 2, 2,
                        'final-hash', 'event-hash', 'unit-hash', 'opponent-hash',
                        '2026-09-03T00:00:00Z', 'complete', 0, 0, 100, 0
                    )""",
                    (civ, slug, name, line, stage, opp_civ, opp_slug, opp_name, seed, stage),
                )

    for index in range(failures):
        conn.execute(
            "INSERT INTO campaign_failures VALUES ('Aztecs','champion','militia','infantry','Vikings','champion',?,'Error','boom',1,'{}','2026-09-03T00:00:00Z')",
            (index,),
        )
    conn.commit()
    conn.close()
    return path


def _create_retail(path):
    conn = create_derived_db(str(path))
    rows = [
        ("ram", "Spanish", "siege_ram", "anti_building_score", 44.0, "177723"),
        ("ram", "Spanish", "siege_ram", "ab_persian_5k_dmg", 55.0, "177723"),
        ("galleon", "Britons", "galleon", "naval_effectiveness", 66.0, "177723"),
        ("galleon", "Britons", "galleon", "vs_fire", 77.0, "177723"),
        ("militia", "Aztecs", "champion", "militia_value", 1.0, "177723"),
        ("galleon", "Britons", "galleon", "naval_effectiveness", 99.0, "170934"),
    ]
    conn.executemany(
        """INSERT INTO battle_scores
           (line_slug, age, civ_name, unit_slug, score_type, score_value,
            rank, median_delta, build_number)
           VALUES (?, 'imperial', ?, ?, ?, ?, 9, 9, ?)""",
        rows,
    )
    conn.commit()
    conn.close()
    return path


def test_builds_only_v3_land_and_allowlisted_retail_rows(tmp_path):
    v3 = _create_v3(tmp_path / "v3.db")
    retail = _create_retail(tmp_path / "retail.db")
    output = tmp_path / "derived_data_v3.db"
    metadata = tmp_path / "derived_data_v3.metadata.json"

    manifest = build_serving_db(
        str(v3), str(retail), str(output), str(metadata),
        expected_summary=_summary(),
    )

    conn = sqlite3.connect(output)
    rows = conn.execute(
        "SELECT line_slug, civ_name, unit_slug, score_type, score_value, rank, median_delta, build_number "
        "FROM battle_scores"
    ).fetchall()
    assert len(rows) == 88
    assert {row[7] for row in rows} == {"177723"}
    assert not any(row[0] == "mangonel" for row in rows)
    assert not any(
        row[0] == "militia"
        and row[2] == "champion"
        and row[3] == "militia_value"
        and row[4] == 1.0
        for row in rows
    )
    assert not any(row[4] == 99.0 for row in rows)

    militia = {
        row[1]: row
        for row in rows
        if row[0] == "militia" and row[3] == "militia_value"
    }
    assert militia["Aztecs"][5:7] == (1, 0.0)
    assert militia["Vikings"][5:7] == (2, -20.0)
    assert conn.execute("SELECT COUNT(*) FROM advisor_recommendations").fetchone()[0] == 0
    conn.close()

    saved_manifest = json.loads(metadata.read_text(encoding="utf-8"))
    assert saved_manifest == manifest
    assert manifest["game_build"] == "177723"
    assert manifest["engine_revision"] == "engine-test-revision"
    assert manifest["mechanics_build"] == "mechanics-test-hash"
    assert manifest["published_rows"] == 88


def test_rejects_campaign_failures_without_replacing_outputs(tmp_path):
    v3 = _create_v3(tmp_path / "v3.db", failures=1)
    retail = _create_retail(tmp_path / "retail.db")
    output = tmp_path / "derived_data_v3.db"
    metadata = tmp_path / "derived_data_v3.metadata.json"
    output.write_bytes(b"existing-db")
    metadata.write_text('{"existing":true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="campaign failures"):
        build_serving_db(
            str(v3), str(retail), str(output), str(metadata),
            expected_summary=_summary(failures=1),
        )

    assert output.read_bytes() == b"existing-db"
    assert metadata.read_text(encoding="utf-8") == '{"existing":true}\n'


def test_rejects_non_equal_resource_weights(tmp_path):
    v3 = _create_v3(
        tmp_path / "v3.db",
        resource_weights={"food": 1, "wood": 1, "gold": 1.5},
    )
    retail = _create_retail(tmp_path / "retail.db")

    with pytest.raises(ValueError, match="resource_weights"):
        build_serving_db(
            str(v3), str(retail), str(tmp_path / "out.db"),
            str(tmp_path / "out.metadata.json"), expected_summary=_summary(),
        )


def test_rejects_matchups_without_five_resolved_seeds(tmp_path):
    v3 = _create_v3(tmp_path / "v3.db", incomplete_matchup=True)
    retail = _create_retail(tmp_path / "retail.db")

    with pytest.raises(ValueError, match="five resolved seeds"):
        build_serving_db(
            str(v3), str(retail), str(tmp_path / "out.db"),
            str(tmp_path / "out.metadata.json"), expected_summary=_summary(),
        )
