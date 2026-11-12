"""Focused checks of the committed 185872 civilization supplement, its API and page composition."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

def test_every_civilization_uses_the_same_editorial_description_in_pages_and_api(client):
    import aoe2_api.web as app
    from aoe2_api.services.civilizations import load_civilization_descriptions
    from scripts.migration.site import pages

    descriptions = load_civilization_descriptions()
    assert set(descriptions) == set(app._get_page_civs())
    assert len(set(descriptions.values())) == len(descriptions)
    overview = {row['name']: row for row in app.get_civ_overview_data()}
    for name, description in descriptions.items():
        # The published page renders the API's strategic description (apps/web reads the export).
        assert overview[name]['description'] == description, name
        assert client.get(f'/api/civilizations/{name}').get_json()['strategic_description'] == description, name
        head = pages.civilization_head(overview[name])
        assert description.split('. ', 1)[0] in next(
            tag['content'] for tag in head['meta'] if tag.get('name') == 'description'), name


@pytest.mark.parametrize('enabled', [False, True])
def test_civilization_emblems_use_configured_asset_bucket(monkeypatch, enabled):
    from aoe2x.assets import config
    from aoe2_api.services.civilizations import load_civilization_supplement
    monkeypatch.setattr(config, 'assets_enabled', lambda: enabled)
    release = load_civilization_supplement()
    prefix = '/assets' if enabled else '/static'
    assert release['civilizations']['Varangians']['emblem_url'] == prefix + '/img/civilizations/185872/varangians.png'
    assert release['media_inventory'][0]['output'].startswith('/static/')


def test_committed_frank_mounted_crossbow_row_explains_gold_discount():
    path = Path(__file__).resolve().parents[1] / 'apps/backend/aoe2_api/data/civilizations-185872.json'
    release = json.loads(path.read_text(encoding='utf-8'))
    row = next(row for row in release['civilizations']['Franks']['units']
               if row['unit_slug'] == 'heavy_mounted_crossbowman')
    assert row['stats']['cost_gold'] == 39
    assert 'Ordonnance Companies: Mounted Crossbowmen cost 40% less gold.' in row['bonus_abilities']


def test_page_composition_leaves_unaffected_civilization_and_input_unchanged():
    from aoe2_api.services.civilizations import compose_civilization_analysis, load_civilization_supplement
    baseline = {'civ_name': 'Aztecs', 'age': 'imperial', 'strategic_description': 'Original',
                'power_units': {'infantry': {'militia': [
                    {'unit_name': 'Elite Jaguar Warrior', 'unit_slug': 'elite_jaguar_warrior_aztecs',
                     'score': 85.4, 'rank': 5, 'tier': 'strong'}]}}}
    original = deepcopy(baseline)
    result = compose_civilization_analysis('Aztecs', 'imperial', baseline, load_civilization_supplement())
    assert result == original
    assert result is not baseline
    assert result['power_units'] is not baseline['power_units']
    assert baseline == original


def test_page_composition_replaces_affected_cavalry_archer_without_changing_other_rows():
    from aoe2_api.services.civilizations import compose_civilization_analysis, load_civilization_supplement
    paladin = {'unit_name': 'Paladin', 'unit_slug': 'paladin', 'score': 75.5,
               'rank': 8, 'tier': 'signature'}
    baseline = {'civ_name': 'Franks', 'age': 'imperial', 'strategic_description': 'Old description',
                'power_units': {'cavalry': {'knight': [paladin], 'camel': None}, 'ranged': {'cav_archer': [
                    {'unit_name': 'Heavy Cavalry Archer', 'unit_slug': 'heavy_cav_archer',
                     'score': 40.0, 'tier': 'weak'}]}}}
    original = deepcopy(baseline)
    result = compose_civilization_analysis('Franks', 'imperial', baseline, load_civilization_supplement())
    assert result['power_units']['cavalry']['knight'] == [paladin]
    assert result['power_units']['cavalry']['camel'] is None
    assert all(row['unit_slug'] != 'heavy_cav_archer'
               for lines in result['power_units'].values() for rows in lines.values() for row in rows or [])
    mounted = result['power_units']['ranged']['mounted_crossbowman'][0]
    assert mounted['unit_slug'] == 'heavy_mounted_crossbowman'
    assert mounted['building'] == 'archery_range'
    assert 'score' not in mounted and 'tier' not in mounted
    assert result['strategic_description'] == 'Old description'
    assert baseline == original


@pytest.mark.parametrize('name,unique_slug,unique_column', [
    ('Danes', 'elite_jomsviking', 'infantry'),
    ('Saxons', 'elite_hearth_troop', 'infantry'),
    ('Varangians', 'elite_jarl', 'cavalry'),
])
def test_new_civilization_composes_complete_roster_and_explicit_buildings(name, unique_slug, unique_column):
    from aoe2_api.services.civilizations import compose_civilization_analysis, load_civilization_supplement
    supplement = load_civilization_supplement()
    result = compose_civilization_analysis(name, 'imperial', {}, supplement)
    rows = [row for lines in result['power_units'].values() for units in lines.values() for row in units]
    assert len(rows) == 18
    assert result['strategic_description'] == supplement['civilizations'][name]['description']
    assert result['emblem_url'] == supplement['civilizations'][name]['emblem_url']
    guard = next(row for row in rows if row['unit_slug'] == 'elite_varangian_guard')
    mounted = next(row for row in rows if row['unit_slug'] == 'heavy_mounted_crossbowman')
    unique = result['power_units'][unique_column][unique_slug.removeprefix('elite_')][0]
    assert guard['building'] == 'barracks'
    assert mounted['building'] == 'archery_range'
    assert unique['unit_slug'] == unique_slug and unique['building'] == 'castle'
    assert all('score' not in row and 'tier' not in row for row in rows)


def test_new_civilization_keeps_actual_supplied_rank_fields():
    from aoe2_api.services.civilizations import compose_civilization_analysis, load_civilization_supplement
    scored = {'unit_slug': 'elite_jomsviking', 'unit_name': 'Old Jomsviking',
              'score': 91.2, 'rank': 2, 'percentile': 97.0, 'tier': 'signature',
              'median_delta': 34.5}
    baseline = {'civ_name': 'Danes', 'age': 'imperial', 'power_units': {
        'infantry': {'jomsviking': [scored], 'militia': [
            {'unit_slug': 'champion', 'score': 70.0, 'tier': 'strong'}]}}}
    original = deepcopy(baseline)
    result = compose_civilization_analysis('Danes', 'imperial', baseline, load_civilization_supplement())
    row = result['power_units']['infantry']['jomsviking'][0]
    assert (row['score'], row['rank'], row['percentile'], row['tier'], row['median_delta']) == (
        91.2, 2, 97.0, 'signature', 34.5)
    assert row['unit_name'] == 'Elite Jomsviking'
    assert len([u for lines in result['power_units'].values() for units in lines.values() for u in units]) == 18
    assert baseline == original


def test_viking_longship_alias_preserves_actual_longboat_rank():
    from aoe2_api.services.civilizations import compose_civilization_analysis, load_civilization_supplement
    baseline = {'civ_name': 'Vikings', 'age': 'imperial', 'power_units': {
        'navy': {'galleon': [{'unit_slug': 'elite_longboat_vikings', 'unit_name': 'Elite Longboat',
                             'score': 100.0, 'rank': 1, 'percentile': 100.0,
                             'tier': 'signature', 'median_delta': 22.5}]}}}
    result = compose_civilization_analysis('Vikings', 'imperial', baseline, load_civilization_supplement())
    row = result['power_units']['navy']['longship'][0]
    assert row['unit_slug'] == 'elite_longship'
    assert (row['score'], row['rank'], row['percentile'], row['tier'], row['median_delta']) == (
        100.0, 1, 100.0, 'signature', 22.5)
    assert baseline['power_units']['navy']['galleon'][0]['unit_slug'] == 'elite_longboat_vikings'


def test_page_names_add_only_supplement_civilizations():
    from aoe2_api.services.civilizations import civilization_page_names, load_civilization_supplement
    assert civilization_page_names(['Franks', 'Aztecs'], load_civilization_supplement())[:2] == [
        'Aztecs', 'Bohemians']
    names = civilization_page_names(['Franks', 'Aztecs'], load_civilization_supplement())
    assert names.count('Franks') == 1
    assert {'Danes', 'Saxons', 'Varangians'} <= set(names)


def test_explicit_building_overrides_unique_unit_default():
    from aoe2_api.services.catalog import building_for_unit
    assert building_for_unit({'unit_name': 'Varangian Guard', 'is_unique': True,
                              'building': 'barracks'}, 'infantry', 'varangian_guard') == 'barracks'


def test_cranequins_is_applied_despite_new_regional_availability_prerequisite(tmp_path):
    """A generic >1000 prerequisite exclusion previously omitted this real upgrade."""
    from aoe2x.dbgen.unit_analyzer import UnitAnalyzer
    fixture = {
        'units': [{'id': 2701, 'class': 36, 'hit_points': 55, 'range': 4,
                   'displayed_attack': 8, 'cost': {'wood': 40, 'gold': 65},
                   'attacks': [{'class': 3, 'amount': 8}, {'class': 1, 'amount': 0}]}],
        'technologies': [{'id': 1452, 'name': 'Cranequins', 'civ': -1,
                          'research_location': 87, 'required_techs': [103, 1450]}],
        'civilizations': [{'id': 62, 'name': 'Danes'}],
        'civ_tech_trees': [{'name': 'Danes', 'disabled_techs': []}], 'effects': [],
        'tech_effects': [{'tech_id': 1452, 'tech_name': 'Cranequins', 'commands': [
            {'type': 4, 'a': 2701, 'b': -1, 'c': 12, 'd': 1.0},
            {'type': 4, 'a': 2701, 'b': -1, 'c': 9, 'd': 258.0}]}],
    }
    for key, value in fixture.items():
        (tmp_path / (key + '.json')).write_text(json.dumps(value))
    analyzer = UnitAnalyzer(extracted_dir=tmp_path)
    result = analyzer.calculate_unit_stats_for_civ('Danes', {
        'base_id': 2701, 'display_name': 'Heavy Mounted Crossbowman',
        'unit_class': analyzer.get_unit(2701)['class'], 'upgrades': []}, max_age=4)
    assert result['stats'].range == 5
    assert result['stats'].attacks[1] == 2
    assert result['stats'].cost_gold == 65


def test_generated_release_contract_and_visible_longship_icons():
    path = Path(__file__).resolve().parents[1] / 'apps/backend/aoe2_api/data/civilizations-185872.json'
    assert path.exists(), 'Generated reference supplement is missing'
    release = json.loads(path.read_text())
    assert release['reference_build'] == 185872
    assert len(release['media_inventory']) == 43
    assert len(release['media']) == 10
    for media in release['media'].values():
        assert set(media) == {'icon', 'icon_transparent', 'idle', 'attack'}
    for civ in ('Danes', 'Saxons', 'Varangians', 'Vikings'):
        ship = next(u for u in release['civilizations'][civ]['units'] if u['unit_name'] == 'Elite Longship')
        from aoe2_api.services.catalog import presentation
        assert presentation()['icon_names'][ship['unit_name']] == 'Elite_Longboat'
    for civ, record in release['civilizations'].items():
        assert record['complete_roster'] == (civ in {'Danes', 'Saxons', 'Varangians'})
        for row in record['units']:
            assert 'media' not in row
            assert not {'tier', 'score', 'stat_baseline', 'ranking_status', 'simulation_available'} & row.keys()
            assert row['stats']['hp'] > 0
    assert next(u for u in release['civilizations']['Vikings']['units']
                if u['unit_slug'] == 'mounted_crossbowman')['stats']['range'] == 7
    assert next(u for u in release['civilizations']['Danes']['units']
                if u['unit_slug'] == 'heavy_mounted_crossbowman')['stats']['range'] == 8
