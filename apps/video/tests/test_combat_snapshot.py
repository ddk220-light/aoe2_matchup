from overlay.unit_timeline import combat_snapshot, D


def test_combat_snapshots_do_not_change_with_later_model_patches():
    action = {0: 9, 2: 123}
    sprite = {0: 2860, 3: 12}
    entity = {3: 1.0, 4: 2.0, 20: 8, 17: {0: 9}}
    captured = combat_snapshot(entity, {8: action, 9: sprite})
    action[2] = 456
    sprite[3] = 25
    entity[3] = 3.0
    assert captured['action'][2] == 123
    assert captured['spriteModels'][0][3] == 12
    assert captured['x'] == 1.0


def test_rust_raw_identifiers_keep_their_scalar_schema_types():
    assert D.SCHEMA[22][0] == ('value', False, 'i16')
    assert D.SCHEMA[9][11] == ('value', False, 'i8')
