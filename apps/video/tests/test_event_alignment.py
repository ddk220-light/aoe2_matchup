import pytest
from overlay.event_alignment import fit


def events():
    return [dict(gameSeconds=g, videoMinSeconds=g / 2 - .71, videoMaxSeconds=g / 2 - .68)
            for g in (3.5, 6.7, 11.3)]


def test_distinct_events_identify_speed_and_bounded_offset():
    speed, offset, interval = fit(events())
    assert speed == 2
    assert offset == pytest.approx(-.695)
    assert interval == pytest.approx([-.71, -.68])


def test_inconsistent_event_rejected():
    a = events()
    a[-1]['videoMinSeconds'] += .3
    a[-1]['videoMaxSeconds'] += .3
    with pytest.raises(ValueError, match='consistent'):
        fit(a)


def test_insufficient_or_loose_evidence_rejected():
    with pytest.raises(ValueError, match='three'):
        fit(events()[:2])
    a = events()
    a[0]['videoMaxSeconds'] += .2
    with pytest.raises(ValueError, match='100 milliseconds'):
        fit(a)
