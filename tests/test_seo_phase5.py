# tests/test_seo_phase5.py
def test_about_page_renders(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "How AoE2 Matchup works" in body
    assert ".dat" in body
    assert "30v30" in body and "3k" in body
    assert "53 civilizations" in body


def test_about_jsonld(client):
    body = client.get("/about").data.decode()
    assert '"@type": "AboutPage"' in body or '"@type": "FAQPage"' in body


def test_about_in_footer(client):
    body = client.get("/").data.decode()
    assert 'href="/about"' in body


def test_about_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/about</loc>" in body
