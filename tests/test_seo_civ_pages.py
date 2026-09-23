# tests/test_seo_civ_pages.py — per-civ landing pages (SEO: "aoe2 <civ>" searches).
_DEFAULT_DESC = "Free Age of Empires II matchup simulator"  # base.html fallback


def test_new_civ_is_page_only(client):
    import app
    for name in ('Danes', 'Saxons', 'Varangians'):
        assert client.get(f'/civilizations/{name.lower()}').status_code == 200
        assert client.get(f'/api/civilizations/{name}').status_code == 200
        assert client.get(f'/api/ref/civ/{name}').status_code == 400
        assert client.get(f'/api/civ-power-units/{name}').status_code == 400
        assert name not in app._get_ref_civs()
        assert name not in app._valid_civs()
        assert name not in app.site_catalog(app.REF_DB_PATH)['civilizations']


def test_new_civ_selector_overview_and_page_api_share_reference_data(client):
    import app
    overview = client.get('/civilizations').get_data(as_text=True)
    assert 'href="/civilizations/danes"' in overview
    assert 'href="/civilizations/saxons"' in overview
    assert 'href="/civilizations/varangians"' in overview
    detail = client.get('/civilizations/danes').get_data(as_text=True)
    assert 'window.PRESELECT_CIV = "Danes"' in detail
    assert 'data-civ="Saxons"' in detail
    row = client.get('/api/civilizations/Danes').get_json()
    assert row['emblem_url'] == '/static/img/civilizations/185872/danes.png'
    assert row['strategic_description'].startswith('Infantry and siege civilization.')
    assert row['power_units']['infantry']['jomsviking'][0]['unit_slug'] == 'elite_jomsviking'
    assert all(civ['emblem_url'] == row['emblem_url'] for civ in app.get_civ_overview_data()
               if civ['name'] == 'Danes')


def test_new_civ_server_html_uses_reference_emblems_media_buildings_and_costs(client):
    overview = client.get('/civilizations').get_data(as_text=True)
    detail = client.get('/civilizations/danes').get_data(as_text=True)
    assert '56 civs' in overview
    assert 'All 53 civs, fully upgraded.' not in overview
    assert 'src="/static/img/civilizations/185872/danes.png"' in overview
    assert 'src="/static/img/civilizations/185872/danes.png"' in detail
    assert 'src="/static/img/civilizations/185872/saxons.png"' in detail
    assert 'Elite Jomsviking' in detail
    assert 'Castle' in detail
    assert '/static/media/civilizations/185872/elite_jomsviking/idle.png' in detail
    assert '/static/media/civilizations/185872/elite_jomsviking/attack.webp' in detail
    assert 'Attack preview' in detail
    assert 'tt-cost-resource' in detail
    assert 'Coming soon' not in detail
    assert 'Unranked' not in detail


def test_server_html_shows_only_supplied_ship_media_and_real_tier(client):
    import app
    from flask import render_template

    data = client.get('/api/civilizations/Vikings').get_json()
    ship = data['power_units']['navy']['longship'][0]
    assert 'idle_blue' not in ship['media']
    with app.app.app_context():
        html = render_template('_civ_content.html', civ={'name': 'Vikings', 'slug': 'vikings'},
                               analysis=data, civ_buildings={'dock': [ship]},
                               site_catalog={'icon_names': {}})
    assert 'Elite Longship' in html
    assert ship['media']['icon'] in html
    assert 'Attack preview' not in html
    assert 'Blue' not in html
    assert 'idle_blue' not in html

    ranked = {'unit_name': 'Ranked Example', 'unit_slug': 'ranked_example',
              'tier': 'good', 'score': 63.0, 'stats': {'hp': 100},
              'bonus_abilities': [], 'special_effects': [], 'missing_techs': []}
    with app.app.app_context():
        ranked_html = render_template('_civ_content.html', civ={'name': 'Franks', 'slug': 'franks'},
                                      analysis={}, civ_buildings={'stable': [ranked]},
                                      site_catalog={'icon_names': {}})
    assert 'tier-good' in ranked_html
    assert '63.0' in ranked_html


def test_server_costs_use_resource_images_and_omit_zero(client):
    import app
    from flask import render_template

    unit = {'unit_name': 'Hearth Troop', 'unit_slug': 'hearth_troop',
            'stats': {'cost_food': 0, 'cost_wood': 80, 'cost_gold': 35}}
    with app.app.test_request_context():
        html = render_template('_civ_content.html', civ={'name': 'Saxons', 'slug': 'saxons'},
                               analysis={}, civ_buildings={'castle': [unit]},
                               site_catalog={'icon_names': {}})
    assert 'src="/static/img/resources/wood.png"' in html
    assert 'src="/static/img/resources/gold.png"' in html
    assert '/static/img/resources/food.png' not in html
    for resource in ('food', 'wood', 'gold'):
        response = client.get(f'/static/img/resources/{resource}.png')
        assert response.status_code == 200
        assert response.mimetype == 'image/png'


def test_page_api_keeps_imperial_age_policy_and_existing_ranks(client):
    assert client.get('/api/civilizations/Danes?age=castle').status_code == 400
    assert client.get('/api/civilizations/atlantis').status_code == 400
    page = client.get('/api/civilizations/Franks').get_json()
    old = client.get('/api/civ-power-units/Franks').get_json()
    old_paladin = old['power_units']['cavalry']['knight'][0]
    page_paladin = page['power_units']['cavalry']['knight'][0]
    assert (page_paladin['score'], page_paladin['rank'], page_paladin['tier']) == (
        old_paladin['score'], old_paladin['rank'], old_paladin['tier'])
    assert old['power_units']['ranged']['cav_archer'][0]['unit_slug'] == 'heavy_cav_archer'
    assert all(row['unit_slug'] != 'heavy_cav_archer'
               for lines in page['power_units'].values() for rows in lines.values() for row in rows or [])


def test_civilization_sitemap_dates_use_supplement_only_for_affected_pages(client):
    import app
    from xml.etree import ElementTree as ET
    root = ET.fromstring(client.get('/sitemap.xml').data)
    dates = {node.find('{*}loc').text.rsplit('/', 1)[-1]: node.find('{*}lastmod').text
             for node in root.findall('{*}url') if node.find('{*}lastmod') is not None}
    assert dates['danes'] == '2026-09-22'
    assert dates['franks'] == '2026-09-22'
    assert dates['bengalis'] == app._data_lastmod()
    assert dates['matchup-advisor'] == app._data_lastmod()


def test_all_civ_pages_resolve_with_own_title(client):
    import app
    import re
    from xml.etree import ElementTree as ET

    names = app._get_page_civs()
    assert len(names) == 56
    expected_paths = {f'/civilizations/{name.lower()}' for name in names}
    overview = client.get('/civilizations').get_data(as_text=True)
    assert set(re.findall(r'href="(/civilizations/[^"?#]+)"', overview)) == expected_paths
    sitemap = ET.fromstring(client.get('/sitemap.xml').data)
    sitemap_paths = {'/civilizations/' + node.find('{*}loc').text.rsplit('/', 1)[-1]
                     for node in sitemap.findall('{*}url')
                     if '/civilizations/' in node.find('{*}loc').text}
    assert sitemap_paths == expected_paths
    for name in names:
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


def test_civ_analyzer_has_civilization_deep_links(client):
    script = client.get("/static/js/civilization-view.js").data.decode()
    assert 'https://aoe2techtree.net/#' in script
    assert 'https://ageofempires.fandom.com/wiki/' in script
    assert "Open Tech Tree" in script
    assert "Open Wiki" in script


def test_civ_pages_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/civilizations/bengalis</loc>" in body


def test_legacy_civ_redirect_targets_detail_page(client):
    resp = client.get("/civ/Franks")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/civilizations/franks")
