# tests/test_seo_unit_line_pages.py — per-unit-line landing pages ("aoe2 fire lancer").
_DEFAULT_DESC = "Free Age of Empires II matchup simulator"


def test_all_unit_line_pages_resolve(client):
    import app
    assert len(app._UNIT_LINE_PAGES) >= 20
    for p in app._UNIT_LINE_PAGES:
        resp = client.get(f"/units/{p['url']}")
        assert resp.status_code == 200, p["url"]
        body = resp.data.decode()
        title_html = p["title"].replace("&", "&amp;")  # Jinja autoescapes titles
        assert f"<title>{title_html}" in body, p["url"]
        assert _DEFAULT_DESC not in body.split("</head>")[0], p["url"]


def test_fire_lancer_page_content(client):
    body = client.get("/units/shock-infantry").data.decode()
    assert "Fire Lancer" in body
    assert "Eagle Warrior" in body
    assert '"@type": "BreadcrumbList"' in body
    assert "?line=shock_infantry" in body       # CTA deep link into /units
    assert 'href="/civilizations/' in body      # rows cross-link civ pages


def test_knight_page_has_full_table(client):
    body = client.get("/units/knight").data.decode()
    assert body.count("<tr") > 30  # one row per civ (53 civs, some unique extras)


def test_unknown_line_404s(client):
    assert client.get("/units/wololo").status_code == 404


def test_unit_line_pages_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/units/shock-infantry</loc>" in body
    assert "/units/knight</loc>" in body


def test_units_page_links_line_guides(client):
    body = client.get("/units").data.decode()
    assert 'href="/units/shock-infantry"' in body


def test_units_deeplink_params_dont_break_page(client):
    resp = client.get("/units?line=shock_infantry&unit=fire_lancer")
    assert resp.status_code == 200
    # canonical must stay the clean URL (query variants must not index separately)
    assert 'rel="canonical" href="' in resp.data.decode()
