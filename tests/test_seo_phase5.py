# tests/test_seo_phase5.py
def test_about_page_renders(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "How AoE2 Matchup works" in body
    assert ".dat" in body
    assert "7,600" in body and "555" in body
    import app
    assert f"{len(app._get_page_civs())} civilizations" in body
    assert "500,000" not in body


def test_about_jsonld(client):
    body = client.get("/about").data.decode()
    assert '"@type": "AboutPage"' in body or '"@type": "FAQPage"' in body


def test_about_in_footer(client):
    body = client.get("/").data.decode()
    assert 'href="/about"' in body


def test_about_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/about</loc>" in body


def test_homepage_has_flagship_content(client):
    body = client.get("/").data.decode()
    assert 'id="home-about"' in body
    import app
    count = len(app.site_catalog(app.SIM_REF_DB_PATH)['civilizations'])
    assert f"{count} civilizations" in body
    assert 'href="/about"' in body
    assert 'href="/units"' in body and 'href="/civilizations"' in body


def test_public_count_is_shared_across_pages_and_structured_data(client, monkeypatch):
    import app
    import json
    import re
    names = app._get_page_civs() + ['Example']
    monkeypatch.setattr(app, '_get_page_civs', lambda: names)
    for path in ('/', '/units', '/about', '/civilizations'):
        body = client.get(path).get_data(as_text=True)
        assert f'All {len(names)} civs, fully upgraded.' in body
        schemas = [json.loads(text) for text in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]
        description = next(schema['description'] for schema in schemas
                           if schema['@type'] in ('WebApplication', 'AboutPage'))
        assert str(len(names)) in description


def test_ranking_provenance_uses_published_metadata(client):
    import app
    import json
    from pathlib import Path
    release = json.loads((Path(app._GOLDEN_DIR) / 'derived_data_v3.metadata.json').read_text())
    for path in ('/units', '/about'):
        body = client.get(path).get_data(as_text=True)
        assert str(release['source_summary']['variants']) in body
        assert str(release['source_summary']['categories']) in body
        assert f"game build {release['game_build']}" not in body
        assert f"game build <strong>{release['game_build']}</strong>" not in body
        assert release['generated_at'][:10] in body
        assert 'historical' in body.lower()
