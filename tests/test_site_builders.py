"""SEO and content contracts of the build-side page builders (scripts/migration/site).

These carry over the meaningful assertions of the route-based SEO tests, which
go away with the Flask HTML routes; markup assertions (navigation, footer,
picker cards) now belong to the Astro components.
"""
import datetime
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

import pytest

from scripts.migration.site import config, content, data, metadata, pages, patches, sitemap, sources

ROOT = Path(__file__).resolve().parents[1]
FALLBACK_DESCRIPTION = 'Free Age of Empires II matchup simulator'


def meta(page, key):
    """The content of a meta tag by name or property."""
    for tag in page['meta']:
        if key in (tag.get('name'), tag.get('property')):
            return tag['content']
    return None


def link(page, rel):
    return next(item['href'] for item in page['links'] if item['rel'] == rel)


def schemas(page):
    return [json.loads(block) for block in page['structured']]


def schema(page, kind):
    return next(item for item in schemas(page) if item['@type'] == kind)


@pytest.fixture(scope='module')
def site_map():
    return ET.fromstring(sitemap.sitemap_xml().encode())


def sitemap_entries(root):
    return {node.find('{*}loc').text: getattr(node.find('{*}lastmod'), 'text', None)
            for node in root.findall('{*}url')}


@pytest.fixture
def seeded_patches(tmp_path):
    from aoe2x.batch import patches_db
    path = str(tmp_path / 'patches.db')
    conn = patches_db.create_db(path)
    pid = patches_db.insert_patch(conn, build_number='177723', release_date='2026-06-02',
                                  title='Update 177723', summary_md='**Tiger Cavalry** HP 130 -> 125.',
                                  source_url='https://example.com/177723', baseline_build='170934', is_current=1)
    conn.execute('INSERT INTO patch_unit_changes VALUES (?,?,?,?,?,?,?)',
                 (pid, 'Wei', 'tiger_cavalry_wei', 'base_hp', 130, 125, None))
    conn.execute('INSERT INTO patch_unit_ranking VALUES (?,?,?,?,?,?,?,?)',
                 (pid, 'Wei', 'tiger_cavalry_wei', 'stable_effectiveness', 90, 85, 1, 4))
    conn.execute('INSERT INTO patch_matchup_changes VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                 (pid, 'Wei', 'tiger_cavalry_wei', 'Franks', 'knight', '30v30', 1, 2, 60, -20, -80))
    conn.commit(); conn.close()
    return path


def all_pages():
    """Every page head the build publishes, keyed by path."""
    result = {'/about': pages.about(), '/civilizations': pages.civilizations_frame(), '/units': pages.rankings_frame(),
              '/': pages.simulator_frame(), '/matchups': pages.matchups()['frame'],
              '/matchup-advisor': pages.advisor()['frame'], '/patches': pages.patch_hub()['frame']}
    for civ in sources.civilization_overview():
        result['/civilizations/' + civ['slug']] = pages.civilization_head(civ)
    for page in content.UNIT_LINE_PAGES:
        result['/units/' + page['url']] = pages.unit_line_head(page)
    for patch in patches.patch_index():
        build = patch['build_number']
        result[f'/patches/{build}'] = pages.patch_build(build)['frame']
        conn = patches.connect()
        units = conn.execute('SELECT civ_name, unit_slug FROM patch_unit_changes c JOIN patches p ON p.id=c.patch_id '
                             'WHERE p.build_number=?', (build,)).fetchall()
        conn.close()
        for civ, unit in units:
            result[f'/patches/{build}/{civ}/{unit}'] = pages.patch_unit_page(build, civ, unit)['frame']
    result['/vs/Spanish/champion/Chinese/arbalester'] = pages.matchup_landing_frame('Spanish', 'champion', 'Chinese', 'arbalester')
    return result


@pytest.fixture(scope='module')
def every_page():
    return all_pages()


# ---- every page -----------------------------------------------------------

def test_every_page_has_its_own_title_description_canonical_and_valid_json_ld(every_page):
    descriptions = {}
    for path, page in every_page.items():
        assert page['title'], path
        description = meta(page, 'description')
        assert description and FALLBACK_DESCRIPTION not in description, path
        descriptions.setdefault(description, []).append(path)
        assert meta(page, 'og:title') == meta(page, 'twitter:title') == page['title'], path
        assert meta(page, 'og:description') == meta(page, 'twitter:description') == description, path
        canonical = link(page, 'canonical')
        assert canonical == 'https://aoe2matchup.com' + path and meta(page, 'og:url') == canonical, path
        assert meta(page, 'og:image') == 'https://aoe2matchup.com/static/img/og-default.png'
        assert link(page, 'icon') == '/static/img/favicon.png'
        assert page['structured'], path
        for item in schemas(page):
            assert item['@context'] == 'https://schema.org', path
    duplicated = {text: paths for text, paths in descriptions.items() if len(paths) > 1}
    assert not duplicated


def test_robots_meta_follows_indexing_policy(monkeypatch):
    monkeypatch.delenv('SEARCH_INDEXING', raising=False)
    monkeypatch.delenv('RAILWAY_ENVIRONMENT_NAME', raising=False)
    monkeypatch.delenv('SITE_URL', raising=False)
    assert meta(pages.simulator_frame(), 'robots') == metadata.DEFAULT_ROBOTS
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME', 'staging')
    assert meta(pages.simulator_frame(), 'robots') == 'noindex, nofollow'
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME', 'production')
    assert meta(pages.simulator_frame(), 'robots') == metadata.DEFAULT_ROBOTS
    # Built for another host than SITE_URL's: not indexable unless forced.
    assert not config.search_indexing('webapp-staging.up.railway.app')
    monkeypatch.setenv('SEARCH_INDEXING', 'true')
    assert config.search_indexing('webapp-staging.up.railway.app')
    monkeypatch.setenv('SEARCH_INDEXING', '0')
    assert meta(pages.matchups()['frame'], 'robots') == 'noindex, nofollow'


def test_site_url_and_verification_tokens_come_from_the_environment(monkeypatch):
    monkeypatch.setenv('SITE_URL', 'https://example.org/')
    monkeypatch.setenv('GOOGLE_SITE_VERIFICATION', 'google-token')
    monkeypatch.setenv('BING_SITE_VERIFICATION', 'bing-token')
    page = pages.matchups()['frame']
    assert link(page, 'canonical') == 'https://example.org/matchups'
    assert meta(page, 'og:image') == 'https://example.org/static/img/og-default.png'
    assert meta(page, 'google-site-verification') == 'google-token'
    assert meta(page, 'msvalidate.01') == 'bing-token'
    assert schema(page, 'WebApplication')['url'] == 'https://example.org'
    assert '<loc>https://example.org/matchups</loc>' in sitemap.sitemap_xml()
    monkeypatch.delenv('GOOGLE_SITE_VERIFICATION')
    monkeypatch.delenv('BING_SITE_VERIFICATION')
    names = {tag.get('name') for tag in pages.matchups()['frame']['meta']}
    assert not names & {'google-site-verification', 'msvalidate.01'}


def test_social_links_feed_json_ld_same_as(monkeypatch):
    for name in ('SOCIAL_DISCORD_URL', 'SOCIAL_YOUTUBE_URL', 'SOCIAL_INSTAGRAM_URL'):
        monkeypatch.delenv(name, raising=False)
    assert config.social_links() == {'discord': None, 'youtube': 'https://www.youtube.com/@AoE2Matchup', 'instagram': None}
    assert schema(pages.simulator_frame(), 'WebApplication')['sameAs'] == ['https://www.youtube.com/@AoE2Matchup']
    monkeypatch.setenv('SOCIAL_DISCORD_URL', 'https://discord.gg/example')
    monkeypatch.setenv('SOCIAL_YOUTUBE_URL', 'https://youtube.com/@example')
    monkeypatch.setenv('SOCIAL_INSTAGRAM_URL', 'https://instagram.com/example')
    assert schema(pages.simulator_frame(), 'WebApplication')['sameAs'] == [
        'https://discord.gg/example', 'https://youtube.com/@example', 'https://instagram.com/example']


def test_site_name_and_fonts_preconnect():
    page = pages.simulator_frame()
    assert meta(page, 'og:site_name') == 'AoE2 Matchup'
    preconnect = [item for item in page['links'] if item['rel'] == 'preconnect']
    assert [item['href'] for item in preconnect] == ['https://fonts.googleapis.com', 'https://fonts.gstatic.com']
    assert 'crossorigin' in preconnect[1]


def test_public_civilization_count_is_shared_across_pages_and_structured_data(monkeypatch):
    names = sources.page_civilizations() + ['Example']
    monkeypatch.setattr(pages, 'page_civilizations', lambda: names)
    for page in (pages.simulator_frame(), pages.rankings_frame(), pages.about()):
        description = next(item['description'] for item in schemas(page) if item['@type'] in ('WebApplication', 'AboutPage'))
        assert str(len(names)) in description
    assert f'all {len(names)} civilizations' in meta(pages.about(), 'description')


# ---- simulator, about, rankings -----------------------------------------

def test_homepage_has_flagship_content():
    about = pages.simulator_about()
    assert about.startswith('<section id="home-about"')
    count = len(sources.site_catalog(sources.SIM_REF_DB_PATH)['civilizations'])
    assert f'{count} civilizations' in about and f'{count} civilizations' in meta(pages.simulator_frame(), 'description')
    for href in ('/about', '/units', '/civilizations', '/matchup-advisor', '/matchups', '/patches'):
        assert f'href="{href}"' in about
    catalog = pages.simulator_catalog()
    assert catalog['civilizations'] == sources.site_catalog(sources.SIM_REF_DB_PATH)['civilizations']
    assert set(catalog['civilization_emblems']) >= {'Danes', 'Saxons', 'Varangians'}


def test_about_page_content_and_json_ld():
    about = pages.about()
    assert about['title'] == 'How AoE2 Matchup works — data & simulation methodology'
    body = about['body']
    assert 'How AoE2 Matchup works' in body and '.dat' in body
    assert '7,600' in body and '555' in body and '500,000' not in body
    assert f'{len(sources.page_civilizations())} civilizations' in body
    assert {item['@type'] for item in schemas(about)} == {'AboutPage', 'FAQPage'}
    assert '.about-page' in about['style']
    catalog = json.loads(re.fullmatch(r'window\.SITE_CATALOG = (.*);', about['catalog_script'], re.S).group(1))
    assert catalog['civilizations'] == sources.reference_civilizations()


def test_ranking_provenance_uses_published_metadata():
    release = json.loads((sources.GOLDEN_DIR / 'derived_data_v3.metadata.json').read_text())
    for text in (pages.rankings_overview_section(), pages.about()['body']):
        assert str(release['source_summary']['variants']) in text
        assert str(release['source_summary']['categories']) in text
        assert f"game build {release['game_build']}" not in text
        assert f"game build <strong>{release['game_build']}</strong>" not in text
        assert release['generated_at'][:10] in text
        assert 'historical' in text.lower()


def test_rankings_overview_shape_and_section():
    overview = data.rankings_overview(top_n=8)
    assert [group['label'] for group in overview] == ['Infantry', 'Archers & Gunpowder', 'Cavalry', 'Siege', 'Naval']
    for group in overview:
        assert group['units'] and len(group['units']) <= 8, group['label']
        scores = [unit['score'] for unit in group['units']]
        assert scores == sorted(scores, reverse=True)
        assert set(group['units'][0]) == {'civ', 'name', 'slug', 'score'}
    section = pages.rankings_overview_section(overview)
    assert section.startswith('<section id="rankings-ssr"')
    for phrase in ('Simulation V3', 'population- and cost-balanced', 'three seeded runs'):
        assert phrase in section
    for retired in ('scoreScaleToggle', 'Pop (30v30)', 'Cost (3k)'):
        assert retired not in section
    assert overview[0]['units'][0]['name'] in section
    for page in content.UNIT_LINE_PAGES:
        assert f'href="/units/{page["url"]}"' in section
    frame = pages.rankings_frame(overview)
    items = schema(frame, 'ItemList')['itemListElement']
    assert len(items) == sum(len(group['units']) for group in overview)
    assert link(frame, 'canonical') == 'https://aoe2matchup.com/units'


def test_ranking_methods_are_the_published_methodology():
    from aoe2x.rank.methodology import load_published_methods
    assert pages.ranking_methods() == json.loads(json.dumps(load_published_methods(sources.GOLDEN_DIR)))


def test_unit_line_pages():
    assert len(content.UNIT_LINE_PAGES) >= 20
    assert len({page['url'] for page in content.UNIT_LINE_PAGES}) == len(content.UNIT_LINE_PAGES)
    for page in content.UNIT_LINE_PAGES:
        assert page['line'] in sources.UNIT_LINES or sources.unit_line_data(page['line']), page['url']
        head = pages.unit_line_head(page)
        assert head['title'] == page['title'] and meta(head, 'description') == page['desc']
        crumbs = schema(head, 'BreadcrumbList')['itemListElement']
        assert crumbs[-1]['item'] == 'https://aoe2matchup.com/units/' + page['url']
    fire = pages.unit_line_head(next(p for p in content.UNIT_LINE_PAGES if p['url'] == 'shock-infantry'))
    assert 'Fire Lancer' in fire['title'] and 'Eagle Warrior' in fire['title']


# ---- civilizations --------------------------------------------------------

def test_civilization_pages_keep_owner_approved_copy():
    overview = {civ['name']: civ for civ in sources.civilization_overview()}
    assert len(overview) == 56
    for name in ('Danes', 'Saxons', 'Varangians', 'Franks', 'Byzantines'):
        head = pages.civilization_head(overview[name])
        assert head['title'] == f'{name} — AoE2 Civilization: Best Units & Strategy'
        assert meta(head, 'description').startswith(
            f'{name} in Age of Empires II — strongest fully-upgraded units by role, tiers, and strategy.')
        assert schema(head, 'BreadcrumbList')['itemListElement'][-1]['name'] == name
    for name, civ in overview.items():
        description = meta(pages.civilization_head(civ), 'description')
        assert len(description) <= 250
        assert civ['description'].split('. ', 1)[0][:150] in description, name
    frame = pages.civilizations_frame()
    assert frame['title'] == 'AoE2 Civilizations — Strengths, power units & strategic identity for all 56 civs'
    assert meta(frame, 'description') == (
        'Detailed Age of Empires II civilization breakdowns: power units, unique techs, civ bonuses, '
        'and the matchup-tested strengths of all 56 civilizations including Three Kingdoms.')
    items = schema(frame, 'ItemList')
    assert items['numberOfItems'] == 56
    assert [item['url'] for item in items['itemListElement']] == [
        'https://aoe2matchup.com/civilizations/' + civ['slug'] for civ in overview.values()]


def test_civilization_tiers_and_line_names():
    assert list(content.TIERS) == ['signature', 'good', 'generic', 'bad', 'situational', 'worst']
    assert all(set(value) == {'label', 'hint'} for value in content.TIERS.values())
    from aoe2_api.services.civilizations import civilization_page_analysis
    standard = {line for column in civilization_page_analysis('Franks')['power_units'].values() for line in column}
    # Lines without a display name (e.g. mounted_crossbowman) fall back to "unit" in Astro.
    assert standard - set(content.LINE_NAMES) == {'mounted_crossbowman'}


# ---- matchups and /vs/ ----------------------------------------------------

def test_matchups_hub_data():
    hub = pages.matchups()
    assert hub['frame']['title'] == 'AoE2 Unit Matchups — Every unique-unit battle, simulated'
    assert '/static/css/matchups.css' in [item['href'] for item in hub['frame']['links']]
    assert hub['groups'] and all(link['url'].startswith('/vs/') for group in hub['groups'] for link in group['links'])
    assert ('Knight vs Pikeman', '/vs/Franks/paladin/Bulgarians/halberdier') in hub['popular']


def test_popular_matchups_all_resolve():
    for label, url in data.popular_matchup_links():
        _, _, ca, ua, cb, ub = url.split('/')
        assert data.load_unit_for_landing(ca, ua) and data.load_unit_for_landing(cb, ub), label
        assert ca in sources.valid_civilizations() and cb in sources.valid_civilizations(), label


def test_vs_landing_frame_has_faq_and_breadcrumbs():
    (civ_a, slug_a, _), (civ_b, slug_b, _) = data.unique_units_list()[:2]
    frame = pages.matchup_landing_frame(civ_a, slug_a, civ_b, slug_b)
    assert meta(frame, 'og:type') == 'article'
    crumbs = schema(frame, 'BreadcrumbList')['itemListElement']
    assert crumbs[1] == {'@type': 'ListItem', 'position': 2, 'name': 'Matchups', 'item': 'https://aoe2matchup.com/matchups'}
    assert crumbs[2]['item'] == link(frame, 'canonical')
    assert len(schema(frame, 'FAQPage')['mainEntity']) == 3
    assert pages.matchup_landing_frame('Franks', 'not_a_unit', civ_b, slug_b) is None


# ---- patches --------------------------------------------------------------

def test_patch_overview_and_build_page():
    overview = patches.get_patch_overview('177723')
    assert overview['build_number'] == '177723' and overview['release_date'] and overview['title']
    assert '<' in overview['summary_html']
    assert {'civ', 'slug', 'title', 'detail_url'} <= set(overview['unit_tables'][0])
    assert patches.get_patch_overview('000000') is None and pages.patch_build('000000') is None
    page = pages.patch_build('177723')
    frame = page['frame']
    assert meta(frame, 'og:type') == 'article'
    assert overview['release_date'] in meta(frame, 'description')
    article = schema(frame, 'NewsArticle')
    assert article['datePublished'] == overview['release_date']
    assert article['mainEntityOfPage'] == 'https://aoe2matchup.com/patches/177723'
    assert '177723' in frame['title'] and 'BreadcrumbList' in {item['@type'] for item in schemas(frame)}


def test_patch_hub_metadata_and_links():
    hub = pages.patch_hub()
    assert hub['frame']['title'].startswith('AoE2 Patch Notes')
    assert 'patch notes' in meta(hub['frame'], 'description').lower()
    latest = hub['patches'][0]
    assert f"Latest: {latest['title']} ({latest['release_date']})." in meta(hub['frame'], 'description')
    urls = [item['url'] for item in schema(hub['frame'], 'ItemList')['itemListElement']]
    assert 'https://aoe2matchup.com/patches/177723' in urls


def test_patch_unit_page_has_specific_description_and_breadcrumbs():
    conn = patches.connect()
    build, civ, slug = conn.execute('SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_changes c '
                                    'JOIN patches p ON p.id = c.patch_id LIMIT 1').fetchone()
    conn.close()
    frame = pages.patch_unit_page(build, civ, slug)['frame']
    assert FALLBACK_DESCRIPTION not in meta(frame, 'description') and civ in meta(frame, 'description')
    assert schema(frame, 'BreadcrumbList')['itemListElement'][-1]['item'] == link(frame, 'canonical')
    empty = pages.patch_unit_page(build, 'Unknown', 'not_a_unit')
    assert empty['unit_title'] == 'Not A Unit' and empty['stat_changes'] == [] and empty['shifted'] == []


def test_seeded_patch_hub_and_unit_page(seeded_patches):
    hub = pages.patch_hub(seeded_patches)
    assert [(p['title'], p['source_url']) for p in hub['patches']] == [('Update 177723', 'https://example.com/177723')]
    unit = pages.patch_unit_page('177723', 'Wei', 'tiger_cavalry_wei', seeded_patches)
    assert 'tiger' in unit['unit_title'].lower()
    flipped = unit['now_loses'][0]['link']
    assert 'civ1=Wei' in flipped and 'unit2=knight' in flipped and 'autorun=1' in flipped
    assert [row['score_type'] for row in unit['ranking']] == ['stable_effectiveness']
    assert pages.patch_unit_page('000000', 'Wei', 'tiger_cavalry_wei', seeded_patches) is None
    assert pages.patch_hub(seeded_patches + '.missing')['patches'] == []


def test_render_patch_summary_basic():
    html = patches.render_patch_summary('**bold** and [link](http://x)\n- one\n- two')
    assert '<strong>bold</strong>' in html
    assert '<a href="http://x"' in html
    assert '<li>one</li>' in html
    assert '&lt;script&gt;' in patches.render_patch_summary('<script>')


def test_deep_link_builder():
    url = patches.battle_sim_deep_link('Wei', 'tiger_cavalry_wei', 'Franks', 'knight', '30v30')
    assert url.startswith('/?')
    assert 'civ1=Wei' in url and 'unit1=tiger_cavalry_wei' in url
    assert 'civ2=Franks' in url and 'unit2=knight' in url
    assert 'mode=count' in url and 'autorun=1' in url
    url3k = patches.battle_sim_deep_link('Wei', 'tiger_cavalry_wei', 'Franks', 'knight', '3k')
    assert 'mode=resources' in url3k and 'resources=3000' in url3k


# ---- sitemap --------------------------------------------------------------

def test_sitemap_urls_are_canonical_unique_and_published(site_map, every_page):
    urls = [node.text for node in site_map.findall('{*}url/{*}loc')]
    assert len(urls) == len(set(urls))
    conn = sqlite3.connect(f'file:{sources.REF_DB_PATH}?mode=ro', uri=True)
    try:
        units = set(conn.execute('SELECT civ_name, unit_slug FROM ref_units').fetchall())
    finally:
        conn.close()
    published = set(every_page)
    for url in urls:
        parsed = urlsplit(url)
        assert not parsed.query and parsed.hostname == 'aoe2matchup.com'
        path = unquote(parsed.path)
        assert not path.startswith('/api/')
        if path.startswith('/vs/'):
            _, _, ca, ua, cb, ub = path.split('/')
            assert (ca, ua) in units and (cb, ub) in units
        elif path.startswith('/patches/') and path.count('/') == 4:
            build, civ, unit = path.split('/', 2)[2].split('/', 2)
            assert pages.patch_unit_page(build, civ, unit) is not None, path
        else:
            assert path in published, path
    for path in ('/', '/matchup-advisor', '/units', '/civilizations', '/matchups', '/about', '/patches',
                 '/units/shock-infantry', '/units/knight', '/patches/177723', '/civilizations/bengalis',
                 '/vs/Franks/paladin/Bulgarians/halberdier'):
        assert 'https://aoe2matchup.com' + path in urls, path
    civilizations = {url for url in urls if '/civilizations/' in url}
    assert civilizations == {'https://aoe2matchup.com/civilizations/' + name.lower() for name in sources.page_civilizations()}


def test_sitemap_lastmod_dates(site_map):
    dates = sitemap_entries(site_map)
    data_date = sitemap.content_lastmod()
    datetime.date.fromisoformat(data_date)
    site = 'https://aoe2matchup.com'
    assert dates[site + '/'] == dates[site + '/matchup-advisor'] == dates[site + '/matchups'] == data_date
    assert dates[site + '/units'] == dates[site + '/about'] == sitemap.content_lastmod(rankings=True)
    assert dates[site + '/civilizations'] == '2026-09-23'
    for slug in ('danes', 'saxons', 'varangians', 'franks'):
        assert dates[f'{site}/civilizations/{slug}'] == '2026-09-23'
    assert dates[site + '/civilizations/bengalis'] == data_date
    release = patches.get_patch_overview('177723')['release_date']
    assert dates[site + '/patches/177723'] == release
    assert f'<loc>{site}/patches/177723</loc><lastmod>{release}</lastmod>' in sitemap.sitemap_xml()


def test_lastmod_uses_recorded_data_date_and_omits_unknown_dates(tmp_path):
    assert sitemap.content_lastmod(tmp_path) is None
    assert b'lastmod' not in sitemap.sitemap_document('https://example.com', [('/', None)])
    (tmp_path / 'derived_data_v3.metadata.json').write_text(json.dumps({'generated_at': '2026-09-04T01:46:57Z'}))
    assert sitemap.content_lastmod(tmp_path) == '2026-09-04'
    document = sitemap.sitemap_document('https://example.com', [('/a&b', None), ('/?q', None), ('/api/x', None), ('/b', 'x')])
    assert b'%26' in document and b'?q' not in document and b'/api/' not in document
    assert b'<loc>https://example.com/b</loc></url>' in document  # an invalid date is omitted


def test_sitemap_without_patches_db(tmp_path):
    document = sitemap.sitemap_xml(str(tmp_path / 'missing.db'))
    assert '/patches</loc>' in document and '/patches/177723' not in document


# ---- the build boundary ---------------------------------------------------

def test_build_never_renders_or_reads_the_flask_website():
    legacy = 'apps/' + 'website'  # the retired Flask site
    assert not (ROOT / legacy).exists()
    sources_of_build = [*(ROOT / 'scripts/migration').glob('*.py'), *(ROOT / 'scripts/migration/site').glob('*.py')]
    for path in sources_of_build:
        text = path.read_text()
        for forbidden in ('render_template', 'static/js/matchup.js', 'base_url=', 'HTMLParser',
                          legacy.replace('/', '.'), 'import app\n', 'import app as'):
            assert forbidden not in text, (path.name, forbidden)
        if path.name == 'export_data.py':
            # Only the simulator data version's legacy hash labels keep the old path.
            assert sorted(re.findall(legacy + r'/[\w/.]+', text)) == [
                legacy + '/services/', legacy + '/services/battles.py', legacy + '/services/mechanics.py']
        else:
            assert legacy not in text, path.name
    for path in (ROOT / 'scripts/migration/site/templates').glob('*.html'):
        assert '{% extends' not in path.read_text() and 'url_for' not in path.read_text(), path.name


def test_published_pages_use_the_current_site_name(every_page):
    texts = [json.dumps(page) for page in every_page.values()]
    texts += [pages.simulator_about(), pages.about()['body'], pages.rankings_overview_section()]
    for text in texts:
        assert 'AoE2 Unit Analyzer' not in text and 'AoE2 Analyzer' not in text
    assert meta(pages.simulator_frame(), 'og:site_name') == 'AoE2 Matchup'
