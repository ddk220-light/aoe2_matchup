"""Regression tests for /api/matchup-recommendations.

Guards the KeyError('median_delta') 500 found 2026-06-10: siege entries in
civ_power_units/<build>.json are stripped to a minimal payload (no median_delta
key) by _strip_minimal_entries, but get_matchup_recommendations indexed
best_entry["median_delta"] directly when the opponent's best siege unit was
strong/signature (e.g. Franks vs Britons, Aztecs vs Franks at imperial).
"""


def test_matchup_recommendations_siege_strength_pair(client):
    # Franks vs Britons imperial 500'd before the .get() fix.
    resp = client.get("/api/matchup-recommendations/Franks/Britons?age=imperial")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    data = resp.get_json()
    assert "error" not in data
    assert data.get("recommended_compositions"), "expected at least one composition"
    # the crash was on the stripped siege entry — assert it survives with a default
    siege = [s for s in data.get("opponent_strengths", []) if s["role"] == "siege"]
    for entry in siege:
        assert "median_delta" in entry


def test_matchup_recommendations_known_good_pair(client):
    resp = client.get("/api/matchup-recommendations/Aztecs/Byzantines?age=imperial")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "error" not in data
