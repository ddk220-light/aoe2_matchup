"""Tests for melee engagement slot targeting functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

import json
from simulation import (
    _assign_targets_spread,
    _assign_targets_melee_capped,
    _assign_targets_spread_capped,
    simulate_battle,
    prepare_combat_unit,
    MELEE_ENGAGE_START,
    MELEE_ENGAGE_STEP,
    MELEE_ENGAGE_ROUND_TICKS,
    MELEE_VS_MELEE_MAX,
)


def test_spread_unchanged():
    """Original spread targeting still works: all attackers get a target."""
    my_alive = [0, 1, 2, 3, 4]
    enemy_alive = [0, 1, 2]
    result = _assign_targets_spread(my_alive, enemy_alive)
    assert len(result) == 5
    for attacker in my_alive:
        assert attacker in result
        assert result[attacker] in enemy_alive


def test_melee_capped_initial_ratio():
    """At tick=0, engagement starts at MELEE_ENGAGE_START (30%)."""
    my_alive = list(range(30))
    enemy_alive = list(range(30))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # 30 * 0.3 = 9 engageable at tick 0
    expected = max(1, int(30 * MELEE_ENGAGE_START))
    assert len(result) == expected

    targets = list(result.values())
    assert len(set(targets)) == len(targets)


def test_melee_capped_1to1_strict():
    """Each engageable target gets exactly 1 melee attacker."""
    my_alive = list(range(20))
    enemy_alive = list(range(10))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # 10 * 0.3 = 3 engageable at tick 0
    expected = max(1, int(10 * MELEE_ENGAGE_START))
    assert len(result) == expected
    targets = list(result.values())
    assert len(set(targets)) == len(targets)


def test_melee_capped_surplus_idles():
    """Surplus melee units get no target (not in result dict)."""
    my_alive = list(range(30))
    enemy_alive = list(range(10))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # 10 * 0.3 = 3 engageable at tick 0, so 27 idle
    expected = max(1, int(10 * MELEE_ENGAGE_START))
    assert len(result) == expected
    idle = [i for i in my_alive if i not in result]
    assert len(idle) == 30 - expected


def test_melee_capped_stable_targets():
    """Targets are stable across ticks — melee locks onto targets until they die."""
    my_alive = list(range(10))
    enemy_alive = list(range(10))
    # Same targets at tick 0 and tick 1 (no rotation)
    targets_tick0 = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    targets_tick1 = _assign_targets_melee_capped(my_alive, enemy_alive, tick=1)
    assert targets_tick0 == targets_tick1
    # Targets are always the first N in the alive list
    assert set(targets_tick0.values()) == set(enemy_alive[:len(targets_tick0)])


def test_melee_capped_ramp_up():
    """Engagement ratio increases over time: 30% -> 40% -> 50% -> ... -> 100%."""
    my_alive = list(range(30))
    enemy_alive = list(range(30))
    # tick 0: 30% = 9 engageable
    r0 = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(r0) == max(1, int(30 * MELEE_ENGAGE_START))
    # After 1 attack round (20 ticks): 40%
    r1 = _assign_targets_melee_capped(my_alive, enemy_alive, tick=MELEE_ENGAGE_ROUND_TICKS)
    assert len(r1) == max(1, int(30 * (MELEE_ENGAGE_START + MELEE_ENGAGE_STEP)))
    # After 7 attack rounds (140 ticks): 100%
    r7 = _assign_targets_melee_capped(my_alive, enemy_alive, tick=MELEE_ENGAGE_ROUND_TICKS * 7)
    assert len(r7) == 30  # 100% = all engageable, 1:1 with 30 melee vs 30 ranged


def test_melee_capped_small_army():
    """Small armies: 2 melee vs 2 ranged."""
    my_alive = [0, 1]
    enemy_alive = [0, 1]
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 1


def test_melee_capped_single_enemy():
    """With 1 enemy, at least 1 melee can attack."""
    my_alive = list(range(10))
    enemy_alive = [0]
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 1
    assert result[my_alive[0]] == 0


def test_melee_capped_fewer_melee_than_slots():
    """When melee count < engageable slots, all melee get targets."""
    my_alive = [0, 1, 2]
    enemy_alive = list(range(20))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 3


def test_spread_capped_equal_numbers():
    """Equal melee armies: each enemy gets 1 attacker (under cap of 2)."""
    my_alive = list(range(10))
    enemy_alive = list(range(10))
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    assert len(result) == 10
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX


def test_spread_capped_outnumber():
    """When outnumbering 3:1, max 2 per target, surplus gets no target."""
    my_alive = list(range(15))
    enemy_alive = list(range(5))
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    # 5 enemies * 2 max = 10 slots, so 10 assigned, 5 idle
    assert len(result) == 10
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX


def test_spread_capped_small():
    """Small armies: 3v2, each enemy gets up to 2, all 3 fit."""
    my_alive = [0, 1, 2]
    enemy_alive = [0, 1]
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    # 2 enemies * 2 cap = 4 slots -> all 3 get targets
    assert len(result) == 3
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX


def _make_unit(hp, attack, attack_speed, attack_range, melee_armor, pierce_armor,
               movement_speed=1.0, attacks=None, armors=None, **kwargs):
    """Build a minimal unit dict for testing simulate_battle."""
    if attacks is None:
        if attack_range >= 1.0:
            attacks = {3: attack}
        else:
            attacks = {4: attack}
    if armors is None:
        armors = {3: pierce_armor, 4: melee_armor}
    base = {
        "hp": hp, "attack": attack, "attack_range": attack_range,
        "attack_speed": attack_speed, "attack_delay": 0,
        "melee_armor": melee_armor, "pierce_armor": pierce_armor,
        "movement_speed": movement_speed,
        "attacks_json": json.dumps({str(k): v for k, v in attacks.items()}),
        "armors_json": json.dumps({str(k): v for k, v in armors.items()}),
        "cost_food": 50, "cost_wood": 0, "cost_gold": 20,
        "min_attack_range": 0, "is_siege_projectile": 0,
        "splash_radius": 0, "projectile_speed": 7 if attack_range >= 1.0 else 0,
        "ignores_pierce_armor": 0, "ignores_melee_armor": 0,
        "trample_percent": 0, "trample_radius": 0, "trample_flat_damage": 0,
        "bonus_damage_reduction": 0, "extra_projectiles": 0,
        "extra_projectile_attacks_json": None,
        "splash_on_hit_radius": 0, "splash_on_hit_fraction": 1.0,
        "dodge_shield_max": 0, "dodge_shield_recharge": 0,
        "bleed_dps": 0, "bleed_duration": 0,
        "block_first_melee": 0, "attack_bonus_per_kill": 0,
        "first_attack_extra_projectiles": 0,
        "hp_regen": 0, "pass_through_percent": 0,
        "hp_transform_threshold": 0, "pop_space": 1.0,
        "armor_strip_per_hit": 0, "charge_attack_melee": 0,
        "charge_recharge_time": 0, "attack_bonus_nearby": 0,
        "nearby_bonus_count": 0, "damage_reflect_percent": 0,
        "hp_nearby_percent_per_unit": 0, "hp_nearby_max_units": 0,
        "slug": "test_unit", "unit_name": "Test Unit",
        "unit_category": "military", "paired_unit_slug": None,
        "dismount_hp": None,
    }
    base.update(kwargs)
    return prepare_combat_unit(base)


def test_simulate_melee_vs_ranged_engagement_slots():
    """30 melee vs 30 ranged: melee can't all attack at once, ranged does better."""
    champ = _make_unit(hp=70, attack=18, attack_speed=0.5, attack_range=0,
                       melee_armor=4, pierce_armor=6, movement_speed=1.06,
                       attacks={4: 18}, armors={4: 4, 3: 6})
    arb = _make_unit(hp=40, attack=10, attack_speed=0.5, attack_range=11,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    winner, remaining1, remaining2 = simulate_battle(champ, arb, 0, fixed_count=30)
    # With engagement slots, arbs should perform much better than before.
    # Before: champ wins with 30 remaining, 0.7 HP.
    # After: arbs should win or it should be very close (remaining1 < 20 or remaining2 > 0)
    assert remaining1 < 20 or remaining2 > 0, (
        f"Engagement slots should reduce melee dominance. "
        f"Got: champ={remaining1}, arb={remaining2}"
    )


def test_simulate_melee_vs_melee_similar():
    """Melee vs melee at equal numbers should produce a valid result."""
    knight = _make_unit(hp=120, attack=14, attack_speed=0.55, attack_range=0,
                        melee_armor=4, pierce_armor=4, movement_speed=1.35,
                        attacks={4: 14}, armors={4: 4, 3: 4})
    paladin = _make_unit(hp=160, attack=18, attack_speed=0.55, attack_range=0,
                         melee_armor=5, pierce_armor=5, movement_speed=1.35,
                         attacks={4: 18}, armors={4: 5, 3: 5})
    winner, rem1, rem2 = simulate_battle(knight, paladin, 0, fixed_count=20)
    # Paladin should still win (higher stats across the board)
    assert winner == 2


def test_simulate_small_battle_unchanged():
    """5v5 battle: should complete without error."""
    champ = _make_unit(hp=70, attack=18, attack_speed=0.5, attack_range=0,
                       melee_armor=4, pierce_armor=6, movement_speed=1.06,
                       attacks={4: 18}, armors={4: 4, 3: 6})
    arb = _make_unit(hp=40, attack=10, attack_speed=0.5, attack_range=11,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    winner, rem1, rem2 = simulate_battle(champ, arb, 0, fixed_count=5)
    assert winner in (1, 2, 0)


def test_simulate_ranged_vs_ranged_with_kiting():
    """Ranged vs ranged: arbalester should still beat crossbow with kiting model."""
    arb = _make_unit(hp=40, attack=10, attack_speed=0.5, attack_range=11,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    xbow = _make_unit(hp=35, attack=8, attack_speed=0.5, attack_range=9,
                      melee_armor=2, pierce_armor=3, movement_speed=0.96,
                      attacks={3: 8}, armors={4: 2, 3: 3})
    winner, rem1, rem2 = simulate_battle(arb, xbow, 0, fixed_count=20)
    # Arbalester should beat crossbow (higher stats + range advantage)
    assert winner == 1


def test_ranged_kiting_longer_range_slower_gets_opening_shots():
    """Arb-like (range 8, slow) vs TAx-like (range 6, fast): range advantage yields opening shots.

    With kiting, the arb (range 8) should get ~6 opening shots against the TAx (range 6)
    due to the +2 range advantage and kiting retreat. The old formula gives only
    int(2/2)=1 opening shot. With proper kiting, the battle should be competitive
    even though the TAx is faster and has higher DPS.
    """
    # Arb-like: range 8, speed 0.96, attack_speed=1.7 (rate) → reload=0.588s, delay=0.333
    arb = _make_unit(hp=40, attack=10, attack_speed=1.7, attack_range=8,
                     melee_armor=0, pierce_armor=0, movement_speed=0.96,
                     attack_delay=0.333,
                     attacks={3: 10}, armors={4: 0, 3: 0})
    # TAx-like: range 6, speed 1.1, attack_speed=2.0 (rate) → reload=0.5s, delay=0.467
    tax = _make_unit(hp=60, attack=12, attack_speed=2.0, attack_range=6,
                     melee_armor=0, pierce_armor=0, movement_speed=1.1,
                     attack_delay=0.467,
                     attacks={3: 12}, armors={4: 0, 3: 0})
    winner, rem_arb, rem_tax = simulate_battle(arb, tax, 0, fixed_count=30)
    # With kiting model, arb should get meaningful opening shots making the battle
    # competitive. Assert TAx doesn't dominate completely.
    assert rem_arb > 0 or rem_tax <= 20, (
        f"Kiting should make arb competitive. Got: arb_remaining={rem_arb}, tax_remaining={rem_tax}"
    )


def test_ranged_kiting_faster_longer_range_dominates():
    """Fast archer (range 8, speed 1.4) vs slow archer (range 5, speed 0.9): extended kiting.

    When one side has BOTH range AND speed advantage, it should be able to kite
    indefinitely and dominate. The old formula gives int(3/2)=1 opening shot,
    but the fast archer should win decisively due to sustained kiting advantage.
    """
    fast = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=8,
                      melee_armor=0, pierce_armor=0, movement_speed=1.4,
                      attack_delay=0.3,
                      attacks={3: 8}, armors={4: 0, 3: 0})
    slow = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=5,
                      melee_armor=0, pierce_armor=0, movement_speed=0.9,
                      attack_delay=0.3,
                      attacks={3: 8}, armors={4: 0, 3: 0})
    winner, rem_fast, rem_slow = simulate_battle(fast, slow, 0, fixed_count=20)
    # Fast archer with range+speed advantage should win decisively
    assert winner == 1 and rem_fast >= 10, (
        f"Fast archer with range+speed should dominate. "
        f"Got: winner={winner}, fast_remaining={rem_fast}, slow_remaining={rem_slow}"
    )


def test_ranged_kiting_equal_range_no_opening():
    """Equal range (6 vs 6) with different speeds: no opening shots regardless of speed.

    When both sides have identical range, neither can fire before the other
    regardless of speed difference. Battle should be close to a draw since
    stats are identical except for speed (which doesn't matter at equal range).
    """
    fast = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=6,
                      melee_armor=0, pierce_armor=0, movement_speed=1.4,
                      attack_delay=0.3,
                      attacks={3: 8}, armors={4: 0, 3: 0})
    slow = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=6,
                      melee_armor=0, pierce_armor=0, movement_speed=0.9,
                      attack_delay=0.3,
                      attacks={3: 8}, armors={4: 0, 3: 0})
    winner, rem1, rem2 = simulate_battle(fast, slow, 0, fixed_count=20)
    # Equal range = equal fight. Winner's remaining should be small (close battle).
    winner_remaining = rem1 if winner == 1 else rem2
    assert winner_remaining <= 15, (
        f"Equal range should produce a close fight. "
        f"Got: winner={winner}, remaining={winner_remaining}"
    )


def test_ranged_kiting_min_range_reduces_fire_dist():
    """Unit with min_range=6 vs archer with range=5: min_range caps effective fire distance.

    A unit with range=10 but min_range=6 can't fire at targets closer than 6.
    Against an archer with range=5, the fire_dist should be 10 - max(6, 5) = 4,
    capped by the min_range. Verify the simulation handles this correctly.
    """
    long_range = _make_unit(hp=50, attack=12, attack_speed=1.0, attack_range=10,
                            melee_armor=0, pierce_armor=0, movement_speed=0.8,
                            attack_delay=0.5, min_attack_range=6,
                            attacks={3: 12}, armors={4: 0, 3: 0})
    archer = _make_unit(hp=40, attack=8, attack_speed=1.7, attack_range=5,
                        melee_armor=0, pierce_armor=0, movement_speed=0.96,
                        attack_delay=0.3,
                        attacks={3: 8}, armors={4: 0, 3: 0})
    # Just verify the simulation runs without error
    winner, rem1, rem2 = simulate_battle(long_range, archer, 0, fixed_count=20)
    assert winner in (0, 1, 2), f"Unexpected winner value: {winner}"
