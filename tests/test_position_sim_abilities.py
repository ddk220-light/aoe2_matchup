"""Unit tests for special abilities in the position-based engine (simulation_real.py).

These were ported from the position-less engine so the matchup table (which runs
on simulate_real_battle) models them. Each test isolates one ability.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from simulation_real import BattleUnit  # noqa: E402


def _base(**kw):
    s = {
        "hp": 100, "attack": 10, "attack_speed": 0.5, "attack_delay": 0,
        "movement_speed": 1.0, "melee_armor": 2, "pierce_armor": 1,
        "attacks_json": '{"4":10}', "armors_json": '{"4":2,"3":1}',
        "attack_range": 0, "accuracy": 100,
    }
    s.update(kw)
    return s


class _Sim:
    def __init__(self):
        self.team1 = []
        self.team2 = []
        self.projectiles = []
        self.battle_time = 0
        for a in ("team1_food_gained", "team1_wood_gained", "team1_gold_gained",
                  "team2_food_gained", "team2_wood_gained", "team2_gold_gained"):
            setattr(self, a, 0)


def _mk(stats, team=1, uid="u"):
    return BattleUnit(uid, team, stats)


def _melee_pair(attacker_stats, defender_stats=None):
    sim = _Sim()
    a = _mk(attacker_stats, 1, "a")
    d = _mk(defender_stats or _base(), 2, "d")
    sim.team1 = [a]
    sim.team2 = [d]
    a.x = a.y = 0.0
    d.x, d.y = 0.4, 0.0
    return sim, a, d


def test_charge_attack_melee_then_recharge():
    sim, a, d = _melee_pair(_base(charge_attack_melee=10, charge_recharge_time=20))
    h0 = d.current_hp
    a.perform_attack_on(d, sim)
    charged = h0 - d.current_hp           # (10-2) + max(0,10-2) = 16
    h1 = d.current_hp
    a.perform_attack_on(d, sim)
    normal = h1 - d.current_hp            # 8 (charge on cooldown)
    assert charged == 16 and normal == 8
    assert a.charge_timer == 20


def test_execute_scales_with_missing_hp():
    a = _mk(_base(execute_damage_per_step=1, execute_hp_step=0.15))
    t = _mk(_base(), 2)
    t.current_hp = 50  # 50% missing -> int(0.5/0.15)=3 bonus
    assert a.get_damage_against(t) == 11


def test_damage_reflect():
    sim, a, d = _melee_pair(_base(), _base(damage_reflect_percent=0.25))
    ah = a.current_hp
    a.perform_attack_on(d, sim)           # melee 8 -> reflect 2
    assert abs(a.current_hp - (ah - 2)) < 1e-6


def test_armor_strip():
    sim, a, d = _melee_pair(_base(armor_strip_per_hit=1))
    a.perform_attack_on(d, sim)
    assert d.melee_armor == 1 and d.pierce_armor == 0
    assert d.armors["4"] == 1 and d.armors["3"] == 0


def test_hp_per_kill_capped():
    sim, a, d = _melee_pair(_base(hp_per_kill=10, hp_per_kill_max=40), _base(hp=5))
    a.current_hp = 50
    a.perform_attack_on(d, sim)
    assert a.current_hp == 60 and a.hp_gained_from_kills == 10


def test_attack_speed_ramp():
    sim, a, d = _melee_pair(_base(attack_speed_ramp=0.2, attack_speed_min=1.0))
    a.perform_attack_on(d, sim)
    assert abs(a.reload_time - 1.8) < 1e-6


def test_transform_swaps_stats():
    a = _mk(_base(hp_transform_threshold=0.5, transform_hp=70, transform_attack=11,
                  transform_attacks_json='{"4":11}'))
    a.current_hp = 40
    a._apply_transform()
    assert a.is_transformed and a.attack == 11


def test_attack_bonus_aura_capped():
    sim = _Sim()
    a = _mk(_base(attack_bonus_nearby=1, nearby_bonus_count=4))
    allies = [_mk(_base(), 1, "x%d" % i) for i in range(3)]
    sim.team1 = [a] + allies
    a.x = a.y = 0.0
    for i, al in enumerate(allies):
        al.x, al.y = 1.0 + i, 0.0
    a._update_auras(sim)
    assert a.aura_attack_bonus == 3  # 3 allies, under the cap of 4


def test_hp_nearby_aura():
    sim = _Sim()
    a = _mk(_base(hp_nearby_percent_per_unit=0.5, hp_nearby_max_units=30))
    allies = [_mk(_base(), 1, "x%d" % i) for i in range(4)]
    sim.team1 = [a] + allies
    a.x = a.y = 0.0
    for i, al in enumerate(allies):
        al.x, al.y = 1.0 + i * 0.5, 0.0
    base_max = a.max_hp
    a._update_auras(sim)
    # +0.5% per ally x 4 = +2% of 100 = +2 HP
    assert abs(a.max_hp - (base_max + 2.0)) < 1e-6
