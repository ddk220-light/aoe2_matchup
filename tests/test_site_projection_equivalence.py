"""TEMPORARY equivalence proof for Stage 3 of the apps/website removal.

The export scripts used to render every page through Flask's HTML routes and
templates and scrape the result. They now use the build-side builders in
scripts/migration/site. While the templates and routes still exist, this file
renders each page exactly the way the old exports did and asserts the builders
publish identical values: head metadata, JSON-LD, HTML fragments, captured page
data and the sitemap, for every page.

Delete this file in Stage 4, together with apps/website/templates and the HTML
routes it compares against; tests/test_site_builders.py keeps the coverage.
"""
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

import app as website
from scripts.migration.site import content, data, pages, patches, sitemap

ROOT = Path(__file__).resolve().parents[1]
BUILD_URL = 'https://aoe2matchup.com'
JSON_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


class Head(HTMLParser):
    """The parser prepare_release.py used for the rendered <head>."""
    def __init__(self):
        super().__init__()
        self.meta = []; self.links = []; self.title = ''; self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta': self.meta.append(attrs)
        if tag == 'link': self.links.append(attrs)
        if tag == 'title': self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False

    def handle_data(self, value):
        if self.in_title: self.title += value


def scraped(html, drop=None):
    head = Head()
    head.feed(html.split('<head>', 1)[1].split('</head>', 1)[0])
    return {'title': head.title, 'meta': head.meta,
            'links': [link for link in head.links if link.get('href') != drop],
            'structured': JSON_LD.findall(html)}


@pytest.fixture(scope='module')
def http():
    with website.app.test_client() as client:
        def get(path, base_url=BUILD_URL):
            response = client.get(path, base_url=base_url)
            assert response.status_code == 200, path
            return response.get_data(as_text=True)
        yield get


@pytest.fixture
def captured(monkeypatch):
    """render_template kwargs of the last HTML route, as export_remaining_pages captured them."""
    contexts = {}
    render = website.render_template
    def capture(name, **kwargs):
        contexts['value'] = kwargs
        return render(name, **kwargs)
    monkeypatch.setattr(website, 'render_template', capture)
    def page(get, path):
        html = get(path, base_url=website.SITE_URL)
        value = {**contexts['value'], 'frame': scraped(html)}
        value.pop('active_nav', None)
        return value
    return page


def plain(value):
    return json.loads(json.dumps(value))


def patch_unit_keys():
    conn = website._patches_conn()
    try:
        return [f'{b}/{c}/{u}' for b, c, u in conn.execute(
            'SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_changes c JOIN patches p ON p.id=c.patch_id '
            'UNION SELECT p.build_number, c.my_civ, c.my_unit_slug FROM patch_matchup_changes c JOIN patches p ON p.id=c.patch_id '
            'UNION SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_ranking c JOIN patches p ON p.id=c.patch_id')]
    finally:
        conn.close()


CIVILIZATIONS = website.get_civ_overview_data()
PATCH_BUILDS = [str(p['build_number']) for p in patches.patch_index()]
PATCH_UNITS = patch_unit_keys()


def test_about_page(http):
    html = http('/about')
    head_html = html.split('<head>', 1)[1].split('</head>', 1)[0]
    plain_scripts = [s for s in re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S)
                     if s.strip() and not s.lstrip().startswith('{')]
    expected = {**scraped(html),
                'style': re.search(r'<style>(.*?)</style>', head_html, re.S).group(1),
                'body': html.split('</nav>', 1)[1].split('</script>', 1)[1].split('<footer', 1)[0].strip(),
                'catalog_script': next(s for s in plain_scripts if 'window.SITE_CATALOG =' in s)}
    assert pages.about() == expected


def test_civilization_overview_frame(http):
    assert pages.civilizations_frame() == scraped(http('/civilizations'), '/static/css/matchup.css')


@pytest.mark.parametrize('civ', CIVILIZATIONS, ids=[c['slug'] for c in CIVILIZATIONS])
def test_civilization_page(http, civ):
    expected = scraped(http('/civilizations/' + civ['slug']), '/static/css/matchup.css')
    # The export reads the overview back from its JSON file.
    assert pages.civilization_head(plain(civ)) == expected


def test_civilization_tiers_and_line_names_match_the_retired_script():
    logic = (ROOT / 'apps/website/static/js/matchup.js').read_text()
    tiers = {key: {'label': label, 'hint': hint} for key, label, hint in
             re.findall(r'(\w+):\s*\{ label: "([^"]+)",\s*hint: "([^"]+)"', logic)}
    lines = dict(re.findall(r'(\w+): "([^"]+)"', logic.split('const LINE_NAMES = {', 1)[1].split('};', 1)[0]))
    assert content.TIERS == tiers and list(content.TIERS) == list(tiers)
    assert content.LINE_NAMES == lines and list(content.LINE_NAMES) == list(lines)


def test_rankings_page(http):
    html = http('/units')
    assert pages.rankings_frame() == scraped(html, '/static/css/rankings.css')
    assert pages.rankings_overview_section() == re.search(r'<section id="rankings-ssr".*?</section>', html, re.S).group()
    assert pages.ranking_methods() == json.loads(re.search(r'window.RANKING_METHODS = (.*?);</script>', html).group(1))
    assert data.rankings_overview() == website.get_rankings_overview_data()


def test_unit_line_pages_list_is_unchanged():
    assert content.UNIT_LINE_PAGES == website._UNIT_LINE_PAGES


@pytest.mark.parametrize('page', content.UNIT_LINE_PAGES, ids=[p['url'] for p in content.UNIT_LINE_PAGES])
def test_unit_line_page(http, page):
    assert pages.unit_line_head(page) == scraped(http('/units/' + page['url']), '/static/css/rankings.css')


def test_simulator_page(http):
    html = http('/')
    assert pages.simulator_frame() == scraped(html, '/static/css/simulate.css')
    assert pages.simulator_about() == re.search(r'<section id="home-about".*?</section>', html, re.S).group()
    assert pages.simulator_catalog() == json.loads(
        re.search(r'window.SITE_CATALOG = (.*?);\s*</script>', html, re.S).group(1))


def test_matchups_page(http, captured):
    assert pages.matchups() == captured(http, '/matchups')
    assert content.POPULAR_MATCHUPS == website._POPULAR_MATCHUPS
    assert data.unique_units_list() == website._unique_units_list()


def test_advisor_page(http, captured):
    assert pages.advisor() == captured(http, '/matchup-advisor')


def test_patch_hub(http, captured):
    assert pages.patch_hub() == captured(http, '/patches')


@pytest.mark.parametrize('build', PATCH_BUILDS)
def test_patch_build_page(http, captured, build):
    assert pages.patch_build(build) == captured(http, '/patches/' + build)


@pytest.mark.parametrize('key', PATCH_UNITS)
def test_patch_unit_page(http, captured, key):
    assert pages.patch_unit_page(*key.split('/', 2)) == captured(http, '/patches/' + key)


def test_empty_patch_frame(http, captured):
    build = PATCH_BUILDS[0]
    assert pages.patch_unit_page(build, 'Unknown', 'not_a_unit') == captured(http, f'/patches/{build}/Unknown/not_a_unit')


@pytest.mark.parametrize('path', ['/vs/Spanish/champion/Chinese/arbalester',
                                  '/vs/Franks/paladin/Bulgarians/halberdier',
                                  '/vs/Mongols/elite_mangudai_mongols/Britons/elite_longbowman_britons'])
def test_matchup_landing_frame(http, captured, path):
    assert pages.matchup_landing_frame(*path.split('/')[2:]) == captured(http, path)['frame']


def test_landing_and_patch_unit_helpers_match_for_every_unit():
    conn = website.get_ref_db()
    try:
        keys = conn.execute('SELECT DISTINCT civ_name, unit_slug FROM ref_units').fetchall()
    finally:
        conn.close()
    for civ, slug in keys:
        assert data.load_unit_for_landing(civ, slug) == website._load_unit_for_landing(civ, slug)
        assert patches.ref_unit_name(civ, slug) == website._ref_unit_name(civ, slug)
    assert patches.ref_unit_name('Unknown', 'not_a_unit') == website._ref_unit_name('Unknown', 'not_a_unit')


def test_patch_helpers_match():
    for build in PATCH_BUILDS + ['000000']:
        assert patches.get_patch_overview(build) == website.get_patch_overview(build)
    for md in ['**bold** and [link](http://x)\n- one\n- two', '', '# A\n## Franks\n- **Paladin** +1\n### x <y>']:
        assert patches.render_patch_summary(md) == website.render_patch_summary(md)
    for scale in ['30v30', '3k']:
        assert patches.battle_sim_deep_link('Wei', 'tiger_cavalry_wei', 'Franks', 'knight', scale) == \
            website.battle_sim_deep_link('Wei', 'tiger_cavalry_wei', 'Franks', 'knight', scale)


def test_sitemap(http):
    # The export fetched it with the test client's default host.
    assert sitemap.sitemap_xml() == http('/sitemap.xml', base_url='http://localhost')
    assert sitemap.content_lastmod() == website._data_lastmod()


def test_patch_pages_without_patches_db(tmp_path, monkeypatch):
    missing = str(tmp_path / 'missing.db')
    monkeypatch.setattr(website, 'PATCHES_DB_PATH', missing)
    client = website.app.test_client()
    assert client.get('/patches/177723').status_code == 404
    assert pages.patch_build('177723', missing) is None
    assert pages.patch_unit_page('177723', 'Franks', 'paladin', missing) is None
    expected = sitemap.sitemap_xml(missing)
    assert expected == client.get('/sitemap.xml').get_data(as_text=True)
    assert pages.patch_hub(missing)['patches'] == []


ENVIRONMENTS = {
    'socials-verification-noindex': {
        'SOCIAL_DISCORD_URL': 'https://discord.gg/example', 'SOCIAL_YOUTUBE_URL': 'https://youtube.com/@example',
        'SOCIAL_INSTAGRAM_URL': 'https://instagram.com/example', 'GOOGLE_SITE_VERIFICATION': 'google-token',
        'BING_SITE_VERIFICATION': 'bing-token', 'SEARCH_INDEXING': '0'},
    'staging-site-url': {'SITE_URL': 'https://staging.example.org/', 'RAILWAY_ENVIRONMENT_NAME': 'staging',
                         'SOCIAL_YOUTUBE_URL': ''},
    'forced-indexing-other-host': {'SITE_URL': 'http://localhost:5000', 'SEARCH_INDEXING': 'true'},
}


@pytest.mark.skipif(os.environ.get('SITE_EQUIVALENCE_CHILD') == '1', reason='already inside an environment variant')
@pytest.mark.parametrize('name', ENVIRONMENTS)
def test_environment_handling_is_equivalent(name):
    """The API reads some settings at import time, so each variant runs in a fresh interpreter."""
    env = {**os.environ, **ENVIRONMENTS[name], 'SITE_EQUIVALENCE_CHILD': '1'}
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', __file__,
                             '-k', 'about or frame or simulator or rankings_page or matchups_page or advisor '
                                   'or patch_hub or patch_build_page or empty_patch or sitemap or '
                                   'civilization_page and franks or unit_line_page and knight or '
                                   'patch_unit_page and Armenians'],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    assert ' passed' in result.stdout and 'failed' not in result.stdout
