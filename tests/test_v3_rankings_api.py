import pytest


def _find(rows, civ, slug):
    return next(
        row
        for row in rows
        if row["civ_name"] == civ and row["unit_slug"] == slug
    )


@pytest.mark.parametrize(
    ("line", "civ", "slug", "score_type", "score", "rank", "median_delta"),
    [
        ("militia", "Aztecs", "elite_jaguar_warrior_aztecs", "militia_value", 85.4, 5, 32.1),
        ("knight", "Franks", "paladin", "stable_effectiveness", 75.5, 8, 33.7),
        ("archer", "Britons", "arbalester", "ranged_effectiveness", 54.8, 10, 22.7),
    ],
)
def test_land_rows_expose_the_v3_final_score(
    client, line, civ, slug, score_type, score, rank, median_delta
):
    response = client.get(f"/api/ref/unit-line/{line}")
    assert response.status_code == 200
    row = _find(response.get_json()["imperial"], civ, slug)
    assert row["ranking_score_type"] == score_type
    assert row["ranking_score"] == score
    assert row["ranking_rank"] == rank
    assert row["ranking_median_delta"] == median_delta
    assert "pool_scores" not in row


def test_jaguar_breakdown_comes_from_the_same_v3_campaign(client):
    payload = client.get("/api/ref/unit-line/militia").get_json()
    jaguar = _find(
        payload["imperial"], "Aztecs", "elite_jaguar_warrior_aztecs"
    )
    assert jaguar["ranking_breakdown"]["roles"] == {
        "GC": 86.4,
        "AC": 64.3,
        "AT": 90.6,
        "AA": 60.8,
    }
    assert jaguar["ranking_breakdown"]["yardsticks"] == [
        {"key": "champion", "label": "Champion", "score": 86.5},
        {"key": "paladin", "label": "Paladin", "score": 64.3},
        {"key": "arbalester", "label": "Arbalester", "score": 60.8},
        {"key": "halberdier", "label": "Halberdier", "score": 95.6},
        {"key": "elite_skirmisher", "label": "Elite Skirmisher", "score": 94.0},
        {"key": "hussar", "label": "Hussar", "score": 79.2},
    ]


@pytest.mark.parametrize(
    ("line", "civ", "slug", "score_type", "score"),
    [
        ("trebuchet", "Britons", "trebuchet", "anti_building_score", 95.5),
        ("galleon", "Britons", "galleon", "naval_effectiveness", 60.3),
    ],
)
def test_retained_retail_rows_use_the_uniform_ranking_contract(
    client, line, civ, slug, score_type, score
):
    response = client.get(f"/api/ref/unit-line/{line}")
    assert response.status_code == 200
    row = _find(response.get_json()["imperial"], civ, slug)
    assert row["ranking_score_type"] == score_type
    assert row["ranking_score"] == score
    assert "ranking_breakdown" not in row


def test_mangonel_remains_stat_only(client):
    response = client.get("/api/ref/unit-line/mangonel")
    assert response.status_code == 200
    rows = response.get_json()["imperial"]
    assert rows
    assert all("ranking_score" not in row for row in rows)


def test_unit_row_keeps_missing_tech_details(client):
    payload = client.get("/api/ref/unit-line/militia").get_json()
    champion = _find(payload["imperial"], "Aztecs", "champion")
    assert isinstance(champion["missing_techs"], list)


def test_seo_line_page_describes_only_equal_resource_scoring(client):
    body = client.get("/units/militia").get_data(as_text=True)
    assert "equal-resource" in body.lower()
    assert "equal numbers" not in body.lower()
