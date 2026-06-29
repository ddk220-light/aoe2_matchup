# tests/test_seo_phase0.py
import datetime


def test_sitemap_lastmod_reflects_data_build(client):
    import app
    body = client.get("/sitemap.xml").data.decode()
    expected = app._data_lastmod()
    # Every <lastmod> in the sitemap uses the data-build date, not "today".
    assert f"<lastmod>{expected}</lastmod>" in body
    # And it is a valid ISO date.
    datetime.date.fromisoformat(expected)


def test_fonts_preconnect_present(client):
    body = client.get("/").data.decode()
    assert '<link rel="preconnect" href="https://fonts.googleapis.com"' in body
    assert '<link rel="preconnect" href="https://fonts.gstatic.com"' in body
    assert 'crossorigin' in body  # gstatic preconnect must be crossorigin


def test_vs_page_has_breadcrumb_jsonld(client):
    import app
    pairs = app._unique_units_list()  # [(civ, slug, name), ...]
    (civ_a, slug_a, _), (civ_b, slug_b, _) = pairs[0], pairs[1]
    body = client.get(f"/vs/{civ_a}/{slug_a}/{civ_b}/{slug_b}").data.decode()
    assert '"@type": "BreadcrumbList"' in body
    assert '"name": "Matchups"' in body
    assert '/matchups' in body


def test_matchups_hub_renders(client):
    resp = client.get("/matchups")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "AoE2 Unit Matchups" in body
    assert "/vs/" in body  # links into landing pages


def test_matchups_hub_linked_from_footer(client):
    body = client.get("/").data.decode()
    assert 'href="/matchups"' in body


def test_matchups_hub_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/matchups</loc>" in body


def test_matchups_hub_loads_its_stylesheet(client):
    body = client.get("/matchups").data.decode()
    assert "css/matchups.css" in body
