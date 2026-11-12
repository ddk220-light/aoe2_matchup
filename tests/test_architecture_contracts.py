import json
from pathlib import Path
import sqlite3

import aoe2_api.web as app
from aoe2_api.services.database import connect_readonly
from scripts.migration.site.sitemap import content_lastmod, sitemap_document
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


def test_civilization_overview_loads_release_once(monkeypatch):
    from aoe2_api.services import civilizations
    calls = []
    def load(**kwargs):
        calls.append(kwargs)
        return {'Spanish': {'imperial': {}}, 'Chinese': {'imperial': {}}}
    monkeypatch.setattr(civilizations, 'load_civ_power_units', load)
    assert len(civilizations.civilization_overview(['Spanish', 'Chinese'])) == 2
    assert len(calls) == 1


def test_indexing_policy_distinguishes_staging_and_production(client, monkeypatch):
    # The API's crawler header; the pages' robots meta and robots.txt come from the
    # page builders (tests/test_site_builders.py) and the Astro app.
    monkeypatch.setitem(app.app.config, 'SEARCH_INDEXING', None)
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME', 'staging')
    response = client.get('/api/armor-classes', base_url='https://webapp-staging.up.railway.app')
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME', 'production')
    response = client.get('/api/armor-classes', base_url=app.SITE_URL)
    assert response.status_code == 200
    assert 'X-Robots-Tag' not in response.headers


def test_lastmod_uses_recorded_data_date_and_omits_unknown_dates(tmp_path):
    assert content_lastmod(tmp_path) is None
    assert b'lastmod' not in sitemap_document('https://example.com', [('/',None)])
    metadata = tmp_path / 'derived_data_v3.metadata.json'
    metadata.write_text(json.dumps({'generated_at':'2026-09-04T01:46:57Z'}))
    assert content_lastmod(tmp_path) == '2026-09-04'
    assert b'&amp;' in sitemap_document('https://example.com', [('/a&b',None)]) or b'%26' in sitemap_document('https://example.com', [('/a&b',None)])


def test_published_methodology_carries_source_identity():
    published = load_published_methods(Path(app._GOLDEN_DIR))
    assert published['schema_version'] == 2
    assert published['methods']['siege'] == load_methodology()['methods']['siege']
    assert published['methods']['naval'] == load_methodology()['methods']['naval']
    assert len(published['methods']['infantry']['formula']) == 5
    assert published['methods']['infantry']['source_engine'] == 'simulationv3'
    assert published['methods']['siege']['source_engine'] == 'retained_historical'
