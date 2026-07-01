# tests/test_seo_civ_pages.py — per-civ landing pages (SEO: "aoe2 <civ>" searches).
_DEFAULT_DESC = "Free Age of Empires II matchup simulator"  # base.html fallback


def test_all_civ_pages_resolve_with_own_title(client):
    import app
    for name in app._get_ref_civs():
        resp = client.get(f"/civilizations/{name.lower()}")
        assert resp.status_code == 200, name
        body = resp.data.decode()
        assert f"<title>{name}" in body, name
        assert _DEFAULT_DESC not in body.split("</head>")[0], name


def test_titlecase_url_redirects_to_lowercase(client):
    resp = client.get("/civilizations/Bengalis")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/civilizations/bengalis")


def test_unknown_civ_404s(client):
    assert client.get("/civilizations/atlantis").status_code == 404


def test_civ_page_preselects_and_has_breadcrumbs(client):
    body = client.get("/civilizations/bengalis").data.decode()
    assert "PRESELECT_CIV" in body and "Bengalis" in body
    assert '"@type": "BreadcrumbList"' in body
    assert 'id="civ-grid"' in body  # interactive analyzer present


def test_index_links_to_detail_pages(client):
    body = client.get("/civilizations").data.decode()
    assert 'href="/civilizations/bengalis"' in body


def test_civ_pages_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/civilizations/bengalis</loc>" in body


def test_legacy_civ_redirect_targets_detail_page(client):
    resp = client.get("/civ/Franks")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/civilizations/franks")
