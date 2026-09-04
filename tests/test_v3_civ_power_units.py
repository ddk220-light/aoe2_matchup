"""Contracts for the staged V3 civ power-unit data source split."""

import json

from aoe2x.advisor import best_units


def _jaguar_entry(data):
    entries = data["Aztecs"]["imperial"]["power_units"]["infantry"]["militia"]
    return next(
        entry
        for entry in entries
        if entry["unit_slug"] == "elite_jaguar_warrior_aztecs"
    )


def test_civ_power_units_use_v3_ranking_scores():
    data = best_units.compute_civ_power_units(build_number="177723")

    jaguar = _jaguar_entry(data)
    assert jaguar["score"] == 85.4
    assert jaguar["rank"] == 5
    assert jaguar["median_delta"] == 32.1


def test_advisor_and_rankings_open_separate_databases():
    rankings = best_units._get_rankings_derived_db()
    advisor = best_units._get_advisor_derived_db()
    try:
        rankings_score = rankings.execute(
            """SELECT score_value FROM battle_scores
               WHERE civ_name = 'Aztecs'
                 AND unit_slug = 'elite_jaguar_warrior_aztecs'
                 AND score_type = 'militia_value'
                 AND age = 'imperial'
                 AND build_number = '177723'"""
        ).fetchone()[0]
        advisor_score = advisor.execute(
            """SELECT score_value FROM battle_scores
               WHERE civ_name = 'Aztecs'
                 AND unit_slug = 'elite_jaguar_warrior_aztecs'
                 AND score_type = 'militia_value'
                 AND age = 'imperial'
                 AND build_number = '177723'"""
        ).fetchone()[0]
    finally:
        rankings.close()
        advisor.close()

    assert rankings_score == 85.4
    assert advisor_score == 86.9


def test_committed_power_units_match_the_hybrid_rankings_database():
    with open(best_units.power_units_path("177723"), encoding="utf-8") as handle:
        data = json.load(handle)

    samples = (
        ("Aztecs", "infantry", "militia", "elite_jaguar_warrior_aztecs"),
        ("Franks", "cavalry", "knight", "paladin"),
        ("Britons", "ranged", "archer", "arbalester"),
        ("Britons", "siege", "trebuchet", "trebuchet"),
        ("Britons", "navy", "galleon", "galleon"),
    )
    rankings = best_units._get_rankings_derived_db()
    try:
        for civ, column, line, slug in samples:
            entry = next(
                item
                for item in data[civ]["imperial"]["power_units"][column][line]
                if item["unit_slug"] == slug
            )
            row = rankings.execute(
                """SELECT score_value, rank, median_delta FROM battle_scores
                   WHERE civ_name = ? AND unit_slug = ? AND line_slug = ?
                     AND age = 'imperial' AND build_number = '177723'
                     AND score_type = ?""",
                (civ, slug, line, best_units.LINE_SCORE_TYPE[line]),
            ).fetchone()
            assert entry["score"] == round(row["score_value"], 1)
            assert entry["rank"] == row["rank"]
            if "median_delta" in entry:
                assert entry["median_delta"] == round(row["median_delta"], 1)
    finally:
        rankings.close()


def test_live_advisor_candidate_query_uses_retail_connector(monkeypatch):
    calls = []
    real_connector = best_units._get_advisor_derived_db

    def tracked_connector():
        calls.append("retail")
        return real_connector()

    def reject_rankings_connector():
        raise AssertionError("live advisor opened the partial rankings database")

    monkeypatch.setattr(best_units, "_get_advisor_derived_db", tracked_connector)
    monkeypatch.setattr(best_units, "_get_rankings_derived_db", reject_rankings_connector)

    result = best_units.get_matchup_recommendations("Aztecs", "Byzantines")

    assert "error" not in result
    assert calls == ["retail"]
