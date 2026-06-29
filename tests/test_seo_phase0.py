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
