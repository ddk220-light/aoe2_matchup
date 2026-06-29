# tests/test_seo_phase4.py
def test_get_patch_overview(client):
    import app
    data = app.get_patch_overview("177723")  # confirmed build with changes
    assert data is not None
    assert data["build_number"] == "177723"
    assert data["release_date"]
    assert data["title"]
    assert "<" in data["summary_html"]  # rendered HTML
    assert isinstance(data["unit_tables"], list) and data["unit_tables"]
    t = data["unit_tables"][0]
    assert {"civ", "slug", "title", "detail_url"}.issubset(t.keys())
    assert app.get_patch_overview("000000") is None


def test_patch_build_page_renders(client):
    import app
    data = app.get_patch_overview("177723")
    body = client.get("/patches/177723").data.decode()
    assert "177723" in body
    assert data["release_date"] in body
    assert data["unit_tables"][0]["title"].split()[-1] in body  # a changed-unit word


def test_patch_build_newsarticle_jsonld(client):
    import app
    data = app.get_patch_overview("177723")
    body = client.get("/patches/177723").data.decode()
    assert '"@type": "NewsArticle"' in body
    assert f'"datePublished": "{data["release_date"]}"' in body


def test_patch_build_404(client):
    assert client.get("/patches/000000").status_code == 404


def test_patches_hub_links_to_build_pages(client):
    body = client.get("/patches").data.decode()
    assert 'href="/patches/177723"' in body


def test_sitemap_includes_patch_pages(client):
    import app
    body = client.get("/sitemap.xml").data.decode()
    assert "/patches/177723</loc>" in body
    rd = app.get_patch_overview("177723")["release_date"]
    assert f"<loc>{app.SITE_URL}/patches/177723</loc><lastmod>{rd}</lastmod>" in body
