import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as ET

import app
from apps.website.services.database import connect_readonly
from apps.website.services.seo import content_lastmod, sitemap_document
from aoe2x.rank.methodology import load_methodology, load_published_methods


def test_serving_database_is_readonly():
    conn = connect_readonly(app.REF_DB_PATH)
    try:
        assert conn.execute('PRAGMA query_only').fetchone()[0] == 1
        try:
            conn.execute('CREATE TABLE architecture_should_never_exist (id INTEGER)')
        except sqlite3.OperationalError:
            pass
        else:
            raise AssertionError('serving connection permits writes')
    finally:
        conn.close()


def test_all_civilizations_have_html_content_and_links_without_javascript(client):
    for name in app._get_ref_civs():
        response = client.get('/civilizations/' + name.lower())
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        content = body.split('id="results"', 1)[1].split('<div class="civ-selector">', 1)[0]
        assert 'analysis-civ-name' in content and name in content
        assert 'building-unit-grid' in content
        assert 'Open Tech Tree' in content and 'Open Wiki' in content
        assert 'unit-badge-name' in content
        assert 'window.CIV_ANALYSIS' in body


def test_sitemap_urls_are_canonical_unique_and_valid(client):
    root = ET.fromstring(client.get('/sitemap.xml').data)
    urls = [node.text for node in root.findall('{*}url/{*}loc')]
    assert len(urls) == len(set(urls))
    conn = connect_readonly(app.REF_DB_PATH)
    try:
        units = {(r[0], r[1]) for r in conn.execute('SELECT civ_name, unit_slug FROM ref_units')}
    finally:
        conn.close()
    for url in urls:
        parsed = urlsplit(url)
        assert not parsed.query
        assert parsed.hostname == urlsplit(app.SITE_URL).hostname
        path = unquote(parsed.path)
        assert not path.startswith('/api/')
        if path.startswith('/vs/'):
            _, _, ca, ua, cb, ub = path.split('/')
            assert (ca,ua) in units and (cb,ub) in units
        else:
            assert client.get(path).status_code == 200, path
    for name in app._get_ref_civs():
        assert app.SITE_URL + '/civilizations/' + name.lower() in urls


def test_indexing_policy_distinguishes_staging_and_production(client, monkeypatch):
    monkeypatch.setitem(app.app.config, 'SEARCH_INDEXING', None)
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME', 'staging')
    response = client.get('/', base_url='https://webapp-staging.up.railway.app')
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert 'content="noindex, nofollow"' in response.get_data(as_text=True)
    assert client.get('/static/js/simulate.js').status_code == 200
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME', 'production')
    response = client.get('/', base_url=app.SITE_URL)
    assert 'X-Robots-Tag' not in response.headers
    assert 'index, follow' in response.get_data(as_text=True)
    assert 'Allow: /' in client.get('/robots.txt', base_url=app.SITE_URL).get_data(as_text=True)


def test_lastmod_uses_recorded_data_date_and_omits_unknown_dates(tmp_path):
    assert content_lastmod(tmp_path) is None
    assert b'lastmod' not in sitemap_document('https://example.com', [('/',None)])
    metadata = tmp_path / 'derived_data_v3.metadata.json'
    metadata.write_text(json.dumps({'generated_at':'2026-09-04T01:46:57Z'}))
    assert content_lastmod(tmp_path) == '2026-09-04'
    assert b'&amp;' in sitemap_document('https://example.com', [('/a&b',None)]) or b'%26' in sitemap_document('https://example.com', [('/a&b',None)])


def test_published_methodology_carries_source_identity():
    published = load_published_methods(Path(app._GOLDEN_DIR))
    assert published == load_methodology()
    assert published['methods']['infantry']['source_engine'] == 'simulationv3'
    assert published['methods']['siege']['source_engine'] == 'retained_historical'
