from aoe2x.grpc.redecode_hp import derive_army, refresh_army_membership, totals


def test_small_equal_resource_armies_are_valid_but_empty_sides_are_not():
    from aoe2x.grpc.redecode_hp import Segment
    for counts in ((27, 2), (1, 27), (27, 27)):
        segment = Segment()
        segment.add(0, {2: (counts[0], 675), 3: (counts[1], 180)})
        assert segment.plausible()
    for counts in ((27, 0), (0, 2), (81, 2)):
        segment = Segment()
        segment.add(0, {2: (counts[0], 675), 3: (counts[1], 180)})
        assert not segment.plausible()


def _entity(owner: int, master: int, hp: float) -> dict:
    return {"__type__": 9, 1: master, 2: owner, 12: hp}


def test_spawned_replacement_joins_live_army_totals() -> None:
    entities = {
        100: _entity(2, 1227, 140),
        200: _entity(3, 492, 40),
    }
    army = derive_army(entities)

    entities[100][12] = 0
    entities[101] = _entity(2, 1253, 50)
    refresh_army_membership(entities, army)

    assert totals(entities, army) == {2: (1, 50.0), 3: (1, 40.0)}


def test_army_refresh_does_not_admit_player_four_or_scouts() -> None:
    entities = {
        100: _entity(2, 1227, 140),
        200: _entity(3, 492, 40),
    }
    army = derive_army(entities)

    entities[300] = _entity(4, 1253, 50)
    entities[301] = _entity(2, 448, 95)
    refresh_army_membership(entities, army)

    assert totals(entities, army) == {2: (1, 140.0), 3: (1, 40.0)}


def test_conversion_moves_a_survivor_without_double_counting() -> None:
    entities = {100: _entity(2, 1947, 145), 200: _entity(3, 775, 65)}
    army = derive_army(entities)
    entities[100][2] = 3
    refresh_army_membership(entities, army)
    assert army == {2: set(), 3: {100, 200}}
    assert totals(entities, army) == {2: (0, 0), 3: (2, 210)}
    entities[100][2] = 4
    refresh_army_membership(entities, army)
    assert totals(entities, army) == {2: (0, 0), 3: (1, 65)}


def test_projectile_effect_hp_is_not_a_surviving_army():
    entities = {100: _entity(2, 1923, 0), 101: _entity(2, 1880, 10),
                200: _entity(3, 2564, 1), 201: _entity(3, 2565, 5)}
    army = derive_army(entities)
    assert totals(entities, army) == {2: (0, 0), 3: (1, 1.0)}
    entities[102] = _entity(2, 1880, 9)
    refresh_army_membership(entities, army)
    assert army == {2: set(), 3: {200}}


def test_live_end_counter_recognizes_defeat_by_conversion() -> None:
    import importlib
    from unittest.mock import patch
    with patch('sys.argv', ['grpc_hp_log.py']):
        LiveEnd = importlib.import_module('aoe2x.grpc.grpc_hp_log').LiveEnd
    live = LiveEnd('unused')
    live.es = {100: _entity(2, 1947, 145), 200: _entity(3, 775, 65)}
    live.army = live._derive_army()
    live.es[100][2] = 3
    live._refresh_army()
    assert live._alive(2) == 0
    assert live._alive(3) == 2


def test_live_end_writes_mutual_elimination_after_grace(tmp_path, monkeypatch):
    import importlib
    import json
    from types import SimpleNamespace
    from unittest.mock import patch
    with patch('sys.argv', ['grpc_hp_log.py']):
        module = importlib.import_module('aoe2x.grpc.grpc_hp_log')
    live = module.LiveEnd(str(tmp_path / 'explosion'))
    live.doc, live.world_id = object(), 1
    live.es = {100: _entity(2, 1263, 75), 200: _entity(3, 492, 40)}
    live.army = live._derive_army()
    monkeypatch.setattr(module.D, 'apply_patch', lambda *a: None)
    live.es[100][12] = live.es[200][12] = 0
    live.feed(SimpleNamespace(time=1000, patch=b'x'))
    end = tmp_path / 'explosion.END'
    assert not end.exists()
    live.feed(SimpleNamespace(time=4000, patch=b'x'))
    assert not end.exists()
    live.feed(SimpleNamespace(time=5000, patch=b'x'))
    result = json.loads(end.read_text())
    assert result['side1'] == result['side2'] == 0
    assert result['winner'] is None
    assert live.done and live.ok
