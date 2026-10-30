import pytest


def _find(rows, civ, slug):
    return next(
        row
        for row in rows
        if row["civ_name"] == civ and row["unit_slug"] == slug
    )


def test_land_scores_and_breakdowns_match_all_finalized_results(client):
    import json
    from collections import Counter
    from pathlib import Path
    from statistics import mean, median
    bundle = json.loads((Path(__file__).parents[1] / 'data/golden/unit_rankings_final.json').read_text())
    actual = []
    for group, count in [('infantry', 147), ('archery', 274), ('stable', 134)]:
        rows = client.get('/api/ref/unit-line/' + group).get_json()['imperial']
        assert len(rows) == count
        actual.extend(rows)
    keyed = {(r['civ_name'], r['unit_slug']): r for r in actual}
    assert len(keyed) == 555
    assert len({r['civ_name'] for r in actual}) == 56
    assert Counter(r['line_slug'] for r in actual) == {
        'militia': 91, 'spear': 56, 'archer': 65, 'skirmisher': 57, 'cav_archer': 59,
        'scorpion': 58, 'gunpowder': 35, 'knight': 70, 'light_cav': 51, 'camel': 13}
    matches = {}
    for r in bundle['matchups']:
        matches.setdefault((r['civilization'], r['slug']), []).append(r)
    for expected in bundle['scores']:
        key = expected['civilization'], expected['unitSlug']
        row = keyed[key]
        assert row['ranking_score'] == expected['score']
        assert row['ranking_rank'] == expected['categoryRank']
        assert row['unit_name'] == expected['unit']
        assert row['line_slug'] == expected['category']
        category_median = median(r['score'] for r in bundle['scores'] if r['category'] == expected['category'])
        assert row['ranking_median_delta'] == pytest.approx(expected['score'] - category_median)
        assert row['ranking_engine_runs'] == {'original': expected['originalEngineRuns'], 'corrected': expected['correctedEngineRuns']}
        assert row['stat_chain_source'] == 'rankings'
        assert row['ranking_breakdown']['roles'] == {}
        scores = row['ranking_breakdown']['yardsticks']
        assert len(scores) == expected['opponents']
        assert mean(r['score'] for r in scores) == pytest.approx(expected['score'])
        by_opponent = {r['key']: r['score'] for r in scores}
        for matchup in matches[key]:
            opponent = 'elite_skirmisher' if matchup['opponentKey'] == 'skirmisher' else matchup['opponentKey']
            assert by_opponent[opponent] == pytest.approx(50 + (matchup['meanUnitHpPercentDecided'] - matchup['meanOpponentHpPercentDecided']) / 2)


@pytest.mark.parametrize(('alias', 'count', 'category'), [('shock_infantry', 9, 'militia'), ('elephant', 7, 'knight'), ('steppe_lancer', 5, 'knight')])
def test_older_line_links_keep_their_units_and_use_merged_ranks(client, alias, count, category):
    rows = client.get('/api/ref/unit-line/' + alias).get_json()['imperial']
    assert len(rows) == count
    assert all(r['line_slug'] == category and 'ranking_score' in r for r in rows)


def test_ranking_stat_chain_uses_the_campaign_reference(client):
    import app
    rows = client.get('/api/ref/unit-line/archery').get_json()['imperial']
    row = next(r for r in rows if r['civ_name'] == 'Varangians' and 'jarl' in r['unit_slug'])
    chain = client.get(f"/api/ref/stat-chain/{row['id']}?source=rankings").get_json()
    conn = app.get_rankings_ref_db()
    expected = [r[0] for r in conn.execute('SELECT tech_name FROM ref_techs_applied WHERE ref_unit_id=?', (row['id'],))]
    conn.close()
    assert chain['stat_chain']
    assert sorted(t['tech_name'] for t in chain['techs_applied']) == sorted(expected)


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


def test_seo_line_page_describes_population_and_cost_balanced_scoring(client):
    body = client.get("/units/militia").get_data(as_text=True)
    assert "population- and cost-balanced" in body.lower()
    assert "equal numbers" not in body.lower()
