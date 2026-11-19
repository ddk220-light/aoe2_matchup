from copy import deepcopy

from audit_jarl_opening_stalls import find_stalls


def samples(*, animate=False, fighting=True):
    rows = []
    for second in range(16):
        rows.append({"gameSeconds": second, "sides": {
            "2": [dict(id=1, x=12., y=3., hp=105., sprite=4428,
                       animation=((4428, second % 5 if animate else 0),)),
                  dict(id=2, x=8.-second/20, y=6., hp=50. if fighting and second > 5 else 105.,
                       sprite=4423, animation=((4423, second),))],
            "3": [dict(id=3, x=4., y=10., hp=80.)]}})
    return rows


def test_opening_frozen_unit_is_flagged():
    hits = find_stalls(samples())
    assert len(hits) == 1
    assert hits[0]["entityId"] == 1
    assert hits[0]["durationSeconds"] == 15


def test_stationary_attacker_is_not_flagged():
    assert find_stalls(samples(animate=True)) == []


def test_no_combat_or_post_victory_rest_is_not_flagged():
    assert find_stalls(samples(fighting=False)) == []
    rows = deepcopy(samples())
    for r in rows[3:]:
        r["sides"]["3"] = []
    assert find_stalls(rows) == []


def test_late_freeze_is_outside_opening_audit():
    rows = samples()
    for r in rows:
        r["gameSeconds"] += 11
    assert find_stalls(rows) == []
