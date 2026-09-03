from aoe2x.grpc.redecode_hp import derive_army, refresh_army_membership, totals


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
