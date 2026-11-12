# tests/test_seo_civ_pages.py — the civilization API behind the per-civ pages ("aoe2 <civ>" searches).
# Page heads, JSON-LD, sitemap dates and links are covered in tests/test_site_builders.py;
# the page markup belongs to the Astro components.


def test_new_civs_have_simulator_data_and_keep_legacy_advisor_scope(client):
    import aoe2_api.web as app
    from scripts.migration.site import pages, sources
    overview = {civ['name']: civ for civ in sources.civilization_overview()}
    for name in ('Danes', 'Saxons', 'Varangians'):
        # The published /civilizations/<civ> page exists (built from the same overview).
        assert pages.civilization_head(overview[name])['title'].startswith(name)
        assert client.get(f'/api/civilizations/{name}').status_code == 200
        assert client.get(f'/api/ref/civ/{name}').status_code == 200
        assert client.get(f'/api/civ-power-units/{name}').status_code == 400
        assert name not in app._get_ref_civs()
        assert name not in app._valid_civs()
        assert name not in app.site_catalog(app.REF_DB_PATH)['civilizations']


def test_new_civilizations_use_normal_unit_media(client):
    for name in ('Danes', 'Saxons', 'Varangians'):
        data = client.get(f'/api/civilizations/{name}').get_json()
        for lines in data['power_units'].values():
            for units in lines.values():
                assert all('media' not in unit for unit in units or [])


def test_new_civ_page_api_and_overview_share_reference_data(client):
    import aoe2_api.web as app
    row = client.get('/api/civilizations/Danes').get_json()
    assert row['emblem_url'] == '/static/img/civilizations/185872/danes.png'
    assert row['strategic_description'].startswith('Danes favor infantry-led attacks backed by siege.')
    assert row['power_units']['infantry']['jomsviking'][0]['unit_slug'] == 'elite_jomsviking'
    assert all(civ['emblem_url'] == row['emblem_url'] for civ in app.get_civ_overview_data()
               if civ['name'] == 'Danes')


def test_reference_tooltips_show_explained_technologies_only_once(client):
    for civ, line, effect, redundant in [
        ('Byzantines', 'varangian_guard', 'Logistica: trample damage.', 'Logistica: trample damage.'),
        ('Varangians', 'varangian_guard', 'Gothikon: periodically throws axes.', 'Gothikon'),
        ('Danes', 'mangonel', 'Northmen’s Fury: +1 range and +40% siege attack against buildings.', "Northmen's Fury"),
    ]:
        data = client.get(f'/api/civilizations/{civ}').get_json()
        unit = next(rows[line][0] for rows in data['power_units'].values() if line in rows)
        assert effect in unit['special_effects']
        assert redundant not in unit['bonus_abilities']


def test_ship_api_rows_use_shared_media(client):
    data = client.get('/api/civilizations/Vikings').get_json()
    ship = data['power_units']['navy']['longship'][0]
    assert 'media' not in ship


def test_resource_cost_images_are_published_media():
    # /static/img/ is published from the media authoring copy (data/media/img).
    import mimetypes
    from aoe2x.paths import MEDIA_DIR
    for resource in ('food', 'wood', 'gold'):
        image = MEDIA_DIR / 'img' / 'resources' / f'{resource}.png'
        assert image.is_file()
        assert mimetypes.guess_type(image.name)[0] == 'image/png'
        assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


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


def test_civ_analyzer_has_civilization_deep_links(client):
    from aoe2x.paths import LEGACY_CLIENT_DIR
    script = (LEGACY_CLIENT_DIR / "js" / "civilization-view.js").read_text(encoding="utf-8")
    assert 'https://aoe2techtree.net/#' in script
    assert 'https://ageofempires.fandom.com/wiki/' in script
    assert "Open Tech Tree" in script
    assert "Open Wiki" in script
