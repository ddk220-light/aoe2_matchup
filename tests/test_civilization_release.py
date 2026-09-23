"""Focused release checks; node fields transcribed from shipped 185872 trees."""
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE = 'aoe2x.assets.build_civilization_release'


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
