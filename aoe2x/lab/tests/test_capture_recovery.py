import pytest

from aoe2x.lab.capture_recovery import mutual_elimination_evidence
from aoe2x.lab.errors import LiveCaptureError


def row(t, left, right):
    return {'gameMs': t, 'sides': {
        '2': [{'hp': hp} for hp in left],
        '3': [{'hp': hp} for hp in right],
    }}


def test_terminal_explosion_requires_repeated_zero_observations():
    rows = [row(0, [100, 100], [75, 75]),
            row(1000, [26, 25], [0, 75]),
            row(1018, [26, 25], [0, 0]),
            row(1036, [0, 0], [0, 0]),
            row(1200, [0, 0], [0, 0]),
            row(1400, [0, 0], [0, 0])]
    result = mutual_elimination_evidence({'rows': rows}, (2, 2))
    assert result['terminalGameMs'] == 1036
    assert result['winnerOwner'] is None
    assert result['finalHp'] == [0, 0]


@pytest.mark.parametrize('rows,expected', [
    ([row(0, [100, 100], [75, 75]), row(1000, [0, 0], [0, 0])], (2, 2)),
    ([row(0, [100, 100], [75, 75]), row(1000, [0, 0], [0, 1])], (2, 2)),
    ([row(0, [100, 100], [75, 75]), row(1000, [0, 0], [0, 0]),
      row(1300, [0, 0], [0, 0]), row(1400, [10, 0], [0, 0])], (2, 2)),
    ([row(0, [100, 100], [75, 75])], (3, 2)),
])
def test_incomplete_replaced_or_wrong_armies_are_not_recovered(rows, expected):
    with pytest.raises(LiveCaptureError):
        mutual_elimination_evidence({'rows': rows}, expected)
