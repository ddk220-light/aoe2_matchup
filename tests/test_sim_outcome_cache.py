from webapp.battle_outcome import BattleOutcome
from webapp.sim_outcome_cache import OutcomeCache, unit_fingerprint


def _outcome(winner=1):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=20.0,
        team1_hp_pct=0.5, team2_hp_pct=0.0,
        team1_survivors=15, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )


def _unit(**overrides):
    base = dict(
        hp=70, attack=11, melee_armor=0, pierce_armor=1,
        speed=1.0, max_range=0, reload_time=2.0, projectile_count=0,
        cost_food=60, cost_wood=0, cost_gold=20,
        outline_size=0.4,
        attacks={"4": 6}, special_properties={},
    )
    base.update(overrides)
    return base


def test_fingerprint_same_for_identical_units():
    a = _unit()
    b = _unit()
    assert unit_fingerprint(a) == unit_fingerprint(b)


def test_fingerprint_differs_when_attack_differs():
    a = _unit(attack=11)
    b = _unit(attack=12)
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_fingerprint_differs_when_attacks_table_differs():
    a = _unit(attacks={"4": 6})
    b = _unit(attacks={"4": 8})
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_fingerprint_unchanged_by_empty_form_fields():
    # None / 0 / "" form fields must NOT alter the fingerprint — units
    # without alternate forms keep their exact historical fingerprints
    # (and thus their dedup-group hashes in existing baselines).
    a = _unit()
    b = _unit(dismount_hp=None, transform_hp=0, hp_transform_threshold=0.0,
              dismount_attacks_json="", transform_armors_json=None)
    assert unit_fingerprint(a) == unit_fingerprint(b)


def test_fingerprint_differs_when_dismount_block_present():
    a = _unit()
    b = _unit(dismount_hp=50, dismount_attack=17,
              dismount_attacks_json='{"4": 17}')
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_fingerprint_differs_when_transform_block_present():
    a = _unit()
    b = _unit(hp_transform_threshold=0.6429, transform_hp=70)
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_fingerprint_differs_between_distinct_form_blocks():
    a = _unit(dismount_hp=50)
    b = _unit(dismount_hp=45)
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_cache_returns_same_outcome_for_matching_keys():
    cache = OutcomeCache()
    fp1, fp2 = ("a",), ("b",)
    o = _outcome()
    cache.put(fp1, fp2, 30, 30, "30v30", 0, o)
    assert cache.get(fp1, fp2, 30, 30, "30v30", 0) is o


def test_cache_miss_returns_none():
    cache = OutcomeCache()
    assert cache.get(("a",), ("b",), 30, 30, "30v30", 0) is None
