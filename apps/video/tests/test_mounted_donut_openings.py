"""An idle sprite transition must not hide a rear melee unit's delayed move."""
from audit_mounted_donut_openings import inspect


def test_melee_sprite_change_does_not_count_as_opening_movement():
    rows = [dict(gameSeconds=t, sides={'3': [dict(
        id=1, x=2.5 if t < 22 else 3.0, y=12.5, hp=140,
        sprite=2610 if t < 3 else 2611)]}) for t in range(26)]
    result = inspect(rows, '3')
    assert result['units'][0]['firstActivitySeconds'] == 3
    assert result['units'][0]['firstMoveSeconds'] == 22
    assert result['delayedUnits'][0]['id'] == 1


def test_melee_unit_that_moves_at_opening_is_clean():
    rows = [dict(gameSeconds=t, sides={'3': [dict(
        id=1, x=2.5 + min(t, 1), y=12.5, hp=140, sprite=2610)]}) for t in range(26)]
    assert inspect(rows, '3')['delayedUnits'] == []
