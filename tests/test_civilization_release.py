"""Focused release checks; node fields transcribed from shipped 185872 trees."""
import importlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE = 'aoe2x.assets.build_civilization_release'


def test_idle_sprite_uses_selected_dat_image_and_shared_web_size(tmp_path):
    from PIL import Image
    source = tmp_path / 'selected_idle_dat4x.png'
    frame = Image.new('RGBA', (500, 600))
    frame.paste((210, 40, 25, 255), (100, 100, 400, 500))
    frame.save(source)
    target = tmp_path / 'idle.png'
    builder().write_idle_sprite(source, target)
    with Image.open(target) as sprite:
        assert sprite.size == (320, 384)
        assert sprite.getpixel((0, 0)) == (0, 0, 0, 0)
        assert sprite.getpixel((160, 192)) == (210, 40, 25, 255)


def test_builder_explains_frank_mounted_crossbow_gold_discount():
    class Analyzer:
        def get_unit(self, unit_id):
            assert unit_id == 2701
            return {'class': 36}

        def calculate_unit_stats_for_civ(self, civ, config, max_age):
            assert civ == 'Franks'
            assert config['base_id'] == 2701
            assert max_age == 4
            stats = SimpleNamespace(hp=66, attack=11, reload_time=2.5, range=7,
                                    melee_armor=4, pierce_armor=2, cost_food=0,
                                    cost_wood=40, cost_gold=39)
            return {'stats': stats, 'applied_bonuses': ['Ordonnance Companies']}

    row = builder().reference_row('Franks', {'Node ID': 2701,
        'Name': 'Heavy Mounted Crossbowman', 'Building ID': 87}, Analyzer())
    assert row['stats']['cost_gold'] == 39
    assert 'Ordonnance Companies: Mounted Crossbowmen cost 40% less gold.' in row['bonus_abilities']


def test_committed_frank_mounted_crossbow_row_explains_gold_discount():
    path = Path(__file__).resolve().parents[1] / 'apps/website/static/data/civilizations-185872.json'
    release = json.loads(path.read_text(encoding='utf-8'))
    row = next(row for row in release['civilizations']['Franks']['units']
               if row['unit_slug'] == 'heavy_mounted_crossbowman')
    assert row['stats']['cost_gold'] == 39
    assert 'Ordonnance Companies: Mounted Crossbowmen cost 40% less gold.' in row['bonus_abilities']


def test_page_composition_leaves_unaffected_civilization_and_input_unchanged():
    from apps.website.services.civilizations import compose_civilization_analysis, load_civilization_supplement
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
    from apps.website.services.civilizations import compose_civilization_analysis, load_civilization_supplement
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
    from apps.website.services.civilizations import compose_civilization_analysis, load_civilization_supplement
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
    from apps.website.services.civilizations import compose_civilization_analysis, load_civilization_supplement
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
    from apps.website.services.civilizations import compose_civilization_analysis, load_civilization_supplement
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
    from apps.website.services.civilizations import civilization_page_names, load_civilization_supplement
    assert civilization_page_names(['Franks', 'Aztecs'], load_civilization_supplement())[:2] == [
        'Aztecs', 'Bohemians']
    names = civilization_page_names(['Franks', 'Aztecs'], load_civilization_supplement())
    assert names.count('Franks') == 1
    assert {'Danes', 'Saxons', 'Varangians'} <= set(names)


def test_explicit_building_overrides_unique_unit_default():
    from apps.website.services.catalog import building_for_unit
    assert building_for_unit({'unit_name': 'Varangian Guard', 'is_unique': True,
                              'building': 'barracks'}, 'infantry', 'varangian_guard') == 'barracks'


def builder():
    assert importlib.util.find_spec(MODULE), 'Scoped civilization release builder is missing'
    return importlib.import_module(MODULE)


def node(name, uid, *, parent=None, status='ResearchedCompleted', building=87,
         kind='RegionalUnit', link_kind=None):
    result = {'Name': name, 'Node ID': uid, 'Use Type': 'Unit',
              'Node Status': status, 'Building ID': building, 'Node Type': kind,
              'Link Node Type': link_kind or (kind if parent else 'BuildingTech'),
              'Age ID': 4 if parent else 3}
    if parent:
        result['Link ID'] = parent
    return result


@pytest.mark.parametrize('civ,heavy', [
    ('Britons', True), ('Celts', True), ('Franks', True), ('Poles', True),
    ('Sicilians', True), ('Spanish', True), ('Teutons', True), ('Danes', True),
    ('Saxons', True), ('Varangians', True), ('Bohemians', False),
    ('Burgundians', False), ('Italians', False), ('Portuguese', False), ('Vikings', False),
])
def test_mounted_crossbow_grants_keep_highest_available_tier(civ, heavy):
    nodes = [node('Mounted Crossbowman', 2700),
             node('Heavy Mounted Crossbowman', 2701, parent=2700,
                  status='ResearchedCompleted' if heavy else 'NotAvailable'),
             node('Cavalry Archer', 39, status='NotAvailable', kind='Unit')]
    selected = builder().select_roster(civ, {'civ_techs_units': nodes})
    assert [n['Node ID'] for n in selected] == [2701 if heavy else 2700]
    removed = builder().removed_slugs(civ)
    assert ('cavalry_archer' in removed) == (civ not in {'Bohemians', 'Danes', 'Saxons', 'Varangians'})


@pytest.mark.parametrize('civ', ['Byzantines', 'Vikings', 'Danes', 'Saxons', 'Varangians'])
def test_five_elite_guard_grants_are_regional_barracks_units(civ):
    nodes = [node('Varangian Guard', 2703, building=12),
             node('Elite Varangian Guard', 2704, parent=2703, building=12)]
    selected = builder().select_roster(civ, {'civ_techs_units': nodes})
    assert [n['Node ID'] for n in selected] == [2704]
    assert builder().identity(selected[0]) == ('elite_varangian_guard', 'varangian_guard', 'infantry', 'barracks', False)


@pytest.mark.parametrize('civ,name,base,elite,column', [
    ('Saxons', 'Hearth Troop', 2705, 2706, 'infantry'),
    ('Varangians', 'Jarl', 2708, 2709, 'cavalry'),
    ('Danes', 'Jomsviking', 2711, 2712, 'infantry'),
])
def test_new_unique_units_use_castle(civ, name, base, elite, column):
    nodes = [node(name, base, kind='UniqueUnit', building=82),
             node('Elite '+name, elite, parent=base, kind='UniqueUnit', building=82)]
    selected = builder().select_roster(civ, {'civ_techs_units': nodes})
    assert [n['Node ID'] for n in selected] == [elite]
    assert builder().identity(selected[0])[2:] == (column, 'castle', True)


def test_catapult_galleon_building_link_does_not_replace_fire_ship():
    nodes = [node('Fast Fire Ship', 532, building=45, kind='UnitUpgrade'),
             node('Catapult Galleon', 2633, parent=532, building=45, link_kind='BuildingTech'),
             node('Villager', 83, building=109, kind='Unit')]
    assert [n['Node ID'] for n in builder().select_roster('Danes', {'civ_techs_units': nodes})] == [532, 2633]


def test_standard_units_retain_existing_page_columns_and_lines():
    assert builder().identity(node('Heavy Scorpion', 542, building=49))[1:4] == ('scorpion', 'ranged', 'siege_workshop')
    assert builder().identity(node('Hussar', 441, building=101))[1] == 'light_cav'
    assert builder().identity(node('Galleon', 442, building=45))[1] == 'galleon'


@pytest.mark.parametrize('name,legacy', [('Longship', 'Longboat'), ('Elite Longship', 'Elite_Longboat')])
def test_longship_media_is_explicit_legacy_alias(name, legacy):
    media = builder().media_for(name)
    assert media['icon'] == '/static/img/units/' + legacy + '.png'
    assert (Path(__file__).resolve().parents[1] / 'apps/website' / media['icon'].lstrip('/')).is_file()


def test_release_selected_missing_unit_is_a_build_error():
    from aoe2x.dbgen.unit_analyzer import UnitAnalyzer
    analyzer = object.__new__(UnitAnalyzer)
    analyzer.units = {}
    with pytest.raises(ValueError, match='2701'):
        builder().reference_row('Danes', node('Heavy Mounted Crossbowman', 2701), analyzer)


@pytest.mark.parametrize('civ', ['Danes', 'Saxons', 'Varangians'])
def test_emblem_copies_finished_menu_shield_instead_of_ingame_mask(tmp_path, civ):
    game = tmp_path / 'game'
    static = tmp_path / 'static'
    textures = game / 'widgetui' / 'textures'
    shield = textures / 'menu' / 'civs' / (civ.lower() + '.png')
    mask = textures / 'ingame' / 'emblems' / shield.name
    for path, content in ((shield, b'finished shield'), (mask, b'ingame mask')):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    record = builder().copy_emblem(game, static, civ)
    assert (static / record['output'].removeprefix('/static/')).read_bytes() == b'finished shield'
    assert Path(record['source']) == shield
    assert record['source_sha256'] == builder().digest(shield)


@pytest.mark.parametrize('available,expected_range,infantry_bonus', [(True, 5, 2), (False, 4, 0)])
def test_cranequins_is_applied_despite_new_regional_availability_prerequisite(tmp_path, available, expected_range, infantry_bonus):
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
    if not available:
        builder().apply_tree_availability(analyzer, {'Danes': {'civ_techs_units': [
            {'Name': 'Cranequins', 'Node ID': 1452, 'Use Type': 'Tech', 'Node Status': 'NotAvailable'}]}})
    result = analyzer.calculate_unit_stats_for_civ('Danes', {
        'base_id': 2701, 'display_name': 'Heavy Mounted Crossbowman',
        'unit_class': analyzer.get_unit(2701)['class'], 'upgrades': []}, max_age=4)
    assert result['stats'].range == expected_range
    assert result['stats'].attacks[1] == infantry_bonus
    assert result['stats'].cost_gold == 65


def test_generated_release_contract_and_visible_longship_icons():
    path = Path(__file__).resolve().parents[1] / 'apps/website/static/data/civilizations-185872.json'
    assert path.exists(), 'Generated reference supplement is missing'
    release = json.loads(path.read_text())
    assert release['reference_build'] == 185872
    assert len(release['media_inventory']) == 43
    assert len(release['media']) == 10
    for media in release['media'].values():
        assert set(media) == {'icon', 'icon_transparent', 'idle', 'attack'}
    for civ in ('Danes', 'Saxons', 'Varangians', 'Vikings'):
        ship = next(u for u in release['civilizations'][civ]['units'] if u['unit_name'] == 'Elite Longship')
        assert ship['media']['icon'].endswith('Elite_Longboat.png')
    for civ, record in release['civilizations'].items():
        assert record['complete_roster'] == (civ in {'Danes', 'Saxons', 'Varangians'})
        for row in record['units']:
            assert not {'tier', 'score', 'stat_baseline', 'ranking_status', 'simulation_available'} & row.keys()
            assert row['stats']['hp'] > 0
    assert next(u for u in release['civilizations']['Vikings']['units']
                if u['unit_slug'] == 'mounted_crossbowman')['stats']['range'] == 7
    assert next(u for u in release['civilizations']['Danes']['units']
                if u['unit_slug'] == 'heavy_mounted_crossbowman')['stats']['range'] == 8
