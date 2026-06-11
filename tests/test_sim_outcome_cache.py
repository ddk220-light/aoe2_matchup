"""Outcome cache + unit fingerprinting (aoe2x/sim/sim_outcome_cache.py).

Includes the regression suite for the 2026-06-11 dedup bug: the old
unit_fingerprint read keys ('speed', 'reload_time', 'max_range', 'min_range',
'projectile_count', 'special_properties') that exist in NEITHER prepared
combat-dict shape, so movement/attack speed, range, and every special ability
were invisible to dedup — all 33 generic champions (Celts speed, Japanese
attack speed, Dravidians Wootz Steel, Slavs trample included) collapsed into
one sim group.  The contract test below is the one that would have caught it.
"""

import os
import sqlite3

import pytest

from aoe2x.sim.battle_outcome import BattleOutcome
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
from aoe2x.sim.sim_outcome_cache import (
    _ABILITY_PARAMS, _CORE_STATS, _FORM_PREFIXES, OutcomeCache, unit_fingerprint,
)
from aoe2x.sim.simulation import prepare_combat_unit as prep_abstract
from aoe2x.sim.simulation_real import prepare_combat_unit as prep_position

REF_DB = os.path.join(os.path.dirname(__file__), "..", "webapp", "aoe2_reference.db")


def _ref_unit(civ, slug):
    conn = sqlite3.connect(REF_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name = ? AND unit_slug = ?",
        (civ, slug),
    ).fetchone()
    conn.close()
    assert row is not None, f"{civ} {slug} missing from ref_units"
    return build_combat_dict_from_ref(row)


def _outcome(winner=1):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=20.0,
        team1_hp_pct=0.5, team2_hp_pct=0.0,
        team1_survivors=15, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )


def _unit(**overrides):
    """Minimal PREPARED-shape combat dict (real contract key names)."""
    base = dict(
        hp=70, attack=11, melee_armor=0, pierce_armor=1,
        attack_range=0, attack_speed=0.5, attack_delay=0,
        movement_speed=1.0, accuracy=100, base_accuracy=100,
        cost_food=60, cost_wood=0, cost_gold=20,
        outline_size=0.4,
        attacks={4: 6}, armors={4: 0, 1: 0},
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Synthetic-dict behavior
# ---------------------------------------------------------------------------

def test_fingerprint_same_for_identical_units():
    assert unit_fingerprint(_unit()) == unit_fingerprint(_unit())


def test_fingerprint_differs_when_attack_differs():
    assert unit_fingerprint(_unit(attack=11)) != unit_fingerprint(_unit(attack=12))


def test_fingerprint_differs_when_attacks_table_differs():
    a = _unit(attacks={4: 6})
    b = _unit(attacks={4: 8})
    assert unit_fingerprint(a) != unit_fingerprint(b)


@pytest.mark.parametrize("key,val", [
    ("movement_speed", 1.15),     # Celts champion (old fp read dead 'speed')
    ("attack_speed", 1 / 1.5),    # Japanese champion (old fp read 'reload_time')
    ("attack_range", 5),          # old fp read 'max_range'
    ("min_attack_range", 2.0),    # old fp read 'min_range'
    ("extra_projectiles", 2),     # old fp read 'projectile_count'
    ("ignores_melee_armor", 1),   # Dravidians (old fp read 'special_properties')
    ("trample_percent", 0.5),     # Slavs
    ("attack_delay", 0.35),       # not fingerprinted at all before
])
def test_fingerprint_differs_on_real_contract_keys(key, val):
    assert unit_fingerprint(_unit()) != unit_fingerprint(_unit(**{key: val}))


def test_fingerprint_unchanged_by_empty_form_fields():
    # None / 0 / "" form fields must NOT alter the fingerprint — units
    # without alternate forms keep compact fingerprints.
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


def test_form_block_same_for_flat_and_nested_shapes():
    # sim_real keeps flat dismount_* keys; simulation.py nests a 'dismount'
    # dict — the same unit must fingerprint identically through both.
    flat = _unit(dismount_hp=50, dismount_attack=17, dismount_melee_armor=1,
                 dismount_pierce_armor=1, dismount_attack_speed=0.4167,
                 dismount_attack_delay=0, dismount_movement_speed=0.9,
                 dismount_attacks_json='{"4": 17}', dismount_armors_json='{"4": 1}')
    nested = _unit(dismount={
        "hp": 50, "attack": 17, "melee_armor": 1, "pierce_armor": 1,
        "attack_speed": 0.4167, "attack_delay": 0, "movement_speed": 0.9,
        "attacks": {4: 17}, "armors": {4: 1},
    })
    assert unit_fingerprint(flat) == unit_fingerprint(nested)


# ---------------------------------------------------------------------------
# Real-unit regression: the five champions that collided pre-fix
# ---------------------------------------------------------------------------

CHAMPION_CIVS = ("Britons", "Celts", "Japanese", "Dravidians", "Slavs")


@pytest.mark.parametrize("prep", [prep_abstract, prep_position],
                         ids=["abstract", "position"])
def test_five_champions_get_five_distinct_fingerprints(prep):
    # Pre-fix: all five identical (Celts movement_speed 1.15, Japanese reload
    # 1.5 vs 2.0, Dravidians ignores_melee_armor, Slavs trample all invisible).
    fps = {civ: unit_fingerprint(prep(_ref_unit(civ, "champion")))
           for civ in CHAMPION_CIVS}
    assert len(set(fps.values())) == 5, fps


def test_true_clone_champions_still_collide():
    # Berbers and Bohemians champions are genuinely stat-identical
    # (verified against the committed reference DB) — dedup must still
    # collapse them after the fix.
    a = prep_position(_ref_unit("Berbers", "champion"))
    b = prep_position(_ref_unit("Bohemians", "champion"))
    assert unit_fingerprint(a) == unit_fingerprint(b)


# ---------------------------------------------------------------------------
# CONTRACT: every key unit_fingerprint reads must exist in the prepared dicts
# (this is the test that would have caught the dead-key bug).
# ---------------------------------------------------------------------------

# Registry params the abstract engine deliberately does not emit (position/JS
# only); unit_fingerprint falls back to the registry default for them there.
_ABSTRACT_SKIPPED = {
    "charge_attack_range", "charge_ignores_armor",
    "food_per_kill", "wood_per_kill", "gold_per_kill",
}


def _contract_units():
    # A unit with abilities + form blocks exercises every read path.
    cds = [_ref_unit("Britons", "champion"),
           _ref_unit("Bulgarians", "elite_konnik_bulgarians")]
    return [(cd, prep_position(dict(cd)), prep_abstract(dict(cd))) for cd in cds]


def test_contract_every_fingerprint_key_exists_in_position_prepared_dict():
    for _cd, pos, _abs in _contract_units():
        for key, _nd in _CORE_STATS:
            assert key in pos, f"core stat '{key}' missing from sim_real-prepared dict"
        for key in ("cost_food", "cost_wood", "cost_gold", "outline_size"):
            assert key in pos, f"'{key}' missing from sim_real-prepared dict"
        assert "attacks" in pos or "attacks_json" in pos
        assert "armors" in pos or "armors_json" in pos
        for name, _default in _ABILITY_PARAMS:
            if name.endswith("_json"):
                assert name in pos or name[:-5] in pos, f"json param '{name}' dead"
            else:
                assert name in pos, f"ability param '{name}' dead in sim_real shape"
        for prefix in _FORM_PREFIXES:
            assert prefix in pos or f"{prefix}_hp" in pos, f"form block '{prefix}' dead"


def test_contract_every_fingerprint_key_exists_in_abstract_prepared_dict():
    for _cd, _pos, abst in _contract_units():
        for key, _nd in _CORE_STATS:
            assert key in abst, f"core stat '{key}' missing from simulation-prepared dict"
        for key in ("cost_food", "cost_wood", "cost_gold", "outline_size"):
            assert key in abst, f"'{key}' missing from simulation-prepared dict"
        assert "attacks" in abst and "armors" in abst
        for name, _default in _ABILITY_PARAMS:
            if name in _ABSTRACT_SKIPPED:
                continue
            if name.endswith("_json"):
                assert name in abst or name[:-5] in abst, f"json param '{name}' dead"
            else:
                assert name in abst, f"ability param '{name}' dead in abstract shape"
        for prefix in _FORM_PREFIXES:
            assert prefix in abst or f"{prefix}_hp" in abst, f"form block '{prefix}' dead"


def test_fingerprint_shape_agnostic_for_konnik():
    # The same loader dict through either prepare path must dedup identically
    # (Konnik exercises the form-block flat-vs-nested normalization). The
    # abstract path lacks the five position-only params, but Konnik carries
    # none of them, so the fingerprints must match exactly.
    cd = _ref_unit("Bulgarians", "elite_konnik_bulgarians")
    assert unit_fingerprint(prep_position(dict(cd))) == \
        unit_fingerprint(prep_abstract(dict(cd)))


# ---------------------------------------------------------------------------
# OutcomeCache
# ---------------------------------------------------------------------------

def test_cache_returns_same_outcome_for_matching_keys():
    cache = OutcomeCache()
    fp1, fp2 = ("a",), ("b",)
    o = _outcome()
    cache.put(fp1, fp2, 30, 30, "30v30", 0, o)
    assert cache.get(fp1, fp2, 30, 30, "30v30", 0) is o


def test_cache_miss_returns_none():
    cache = OutcomeCache()
    assert cache.get(("a",), ("b",), 30, 30, "30v30", 0) is None
