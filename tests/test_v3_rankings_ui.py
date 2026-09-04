"""Rendered-page contracts for the single-score V3 rankings experience."""


def test_rankings_page_describes_the_v3_equal_resource_method(client):
    response = client.get("/units")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Simulation V3" in html
    assert "equal-resource" in html
    assert "five seeded runs" in html
    assert "scoreScaleToggle" not in html
    assert "Pop (30v30)" not in html
    assert "Cost (3k)" not in html
    assert "rankings_v3_model.js" in html
