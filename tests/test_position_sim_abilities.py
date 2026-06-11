"""Unit tests for special abilities in the position-based engine (simulation_real.py).

These were ported from the position-less engine so the matchup table (which runs
on simulate_real_battle) models them. Each test isolates one ability.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from aoe2x.sim.simulation_real import BattleUnit  # noqa: E402


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


def test_urumi_trample_gated_to_charged_strike():
    """Charge-melee units (Urumi) splash only on the charged hit, not every hit."""
    sim = _Sim()
    a = _mk(_base(charge_attack_melee=12, charge_recharge_time=24,
                  trample_percent=0.5, trample_radius=0.5))
    t = _mk(_base(), 2, "t")
    b = _mk(_base(), 2, "b")
    sim.team1 = [a]
    sim.team2 = [t, b]
    a.x = a.y = 0.0
    t.x, t.y = 0.4, 0.0
    b.x, b.y = 0.7, 0.0
    hb = b.current_hp
    a.perform_attack_on(t, sim)            # charge ready -> trample fires
    charged = hb - b.current_hp
    b.current_hp = t.current_hp = 100.0
    hb = b.current_hp
    a.perform_attack_on(t, sim)            # recharging -> no trample
    uncharged = hb - b.current_hp
    assert charged > 0 and uncharged == 0


def test_ranged_charge_replaces_normal_when_every_attack():
    """Fire Archer (recharge<=0): charge fires every attack and replaces the shot."""
    sim = _Sim()
    fa = _mk(_base(attack_range=5, charge_projectile_count=2, charge_recharge_time=0,
                   charge_projectile_attacks_json='{"3":10}'))
    t = _mk(_base(), 2, "t")
    sim.team1 = [fa]
    sim.team2 = [t]
    fa.x = fa.y = 0.0
    t.x, t.y = 3.0, 0.0
    fa.target = t
    fa.perform_attack(sim)
    assert len(sim.projectiles) == 2       # 2 charge projectiles, no normal


def test_ranged_charge_adds_then_recharges():
    """Xianbei (recharge>0): charge burst adds to the normal shot, then recharges."""
    sim = _Sim()
    xb = _mk(_base(attack_range=5, charge_projectile_count=5, charge_recharge_time=30,
                   charge_projectile_attacks_json='{"3":5}'))
    t = _mk(_base(), 2, "t")
    sim.team1 = [xb]
    sim.team2 = [t]
    xb.x = xb.y = 0.0
    t.x, t.y = 3.0, 0.0
    xb.target = t
    xb.perform_attack(sim)                 # 5 charge + 1 normal
    first = len(sim.projectiles)
    assert first == 6 and xb.charge_timer == 30
    xb.perform_attack(sim)                 # recharging -> 1 normal only
    assert len(sim.projectiles) - first == 1


def test_konnik_dismounts_on_death_and_fights_on():
    """Konnik (Bulgarians elite): on death the unit is replaced in place by its
    dismounted form with the DERIVED teched stats (17 atk for the Bulgarians
    elite block), counts as alive for survivor/winner accounting, and only the
    second death is final. Stats mirror the committed ref DB row
    (Bulgarians / elite_konnik_bulgarians @ Imperial, derived:form_tech_chain).
    """
    from aoe2x.sim.simulation_real import BattleSimulation
    konnik = _base(
        hp=120, attack=18, melee_armor=5, pierce_armor=6,
        attacks_json='{"4":18}', armors_json='{"4":5,"3":6}',
        outline_size=0.4, cost_food=60, cost_gold=70,
        dismount_hp=50, dismount_attack=17, dismount_melee_armor=5,
        dismount_pierce_armor=6, dismount_attack_speed=0.4167,
        dismount_attack_delay=0, dismount_movement_speed=0.9,
        dismount_attacks_json='{"4":17,"21":6}',
        dismount_armors_json='{"1":0,"3":6,"4":5,"19":0,"31":0}',
    )
    enemy = dict(_base(hp=60), outline_size=0.2)
    sim = BattleSimulation()
    sim.setup_team(1, konnik, 1)
    sim.setup_team(2, enemy, 2)
    assert sim.has_dismount
    u = sim.team1[0]

    # First death: lethal hit, then one tick — the end-of-tick respawn swaps
    # in the dismounted form at FULL dismount HP.
    u.take_damage(9999, None)
    assert u.state == "dead"
    sim.step(1.0 / 30.0)
    assert u.is_dismounted and u.state != "dead"
    assert u.current_hp == 50 and u.max_hp == 50
    assert u.attack == 17 and u.attacks["4"] == 17
    assert u.melee_armor == 5 and u.pierce_armor == 6
    assert abs(u.reload_time - 1.0 / 0.4167) < 1e-9
    assert u.attack_cooldown == u.reload_time  # waits one full dismount reload
    assert abs(u.move_speed - 0.9) < 1e-9
    # Survivor accounting: the second life counts as alive, no winner yet.
    assert sim.alive_count(1) == 1 and u in sim.alive
    assert sim.winner is None

    # Second death is final — no third life.
    u.take_damage(9999, None)
    sim.step(1.0 / 30.0)
    assert u.state == "dead" and not sim.team1[0].current_hp
    assert sim.alive_count(1) == 0
    assert sim.winner == 2


def test_guecha_ally_death_heal():
    """Guecha heals over time when a nearby ally dies during a sim step."""
    from aoe2x.sim.simulation_real import BattleSimulation
    g = {"hp": 65, "attack": 10, "attack_speed": 0.5, "attack_delay": 0,
         "movement_speed": 1.0, "melee_armor": 0, "pierce_armor": 0,
         "attacks_json": '{"4":10}', "armors_json": "{}", "attack_range": 0,
         "accuracy": 100, "ally_death_heal": 5.0, "ally_death_heal_duration": 3.0,
         "outline_size": 0.5}
    enemy = dict(g, ally_death_heal=0, ally_death_heal_duration=0)
    sim = BattleSimulation()
    sim.setup_team(1, g, 2)
    sim.setup_team(2, enemy, 1)
    guecha, victim = sim.team1[0], sim.team1[1]
    guecha.x, guecha.y = 10.0, 10.0
    victim.x, victim.y = 10.6, 10.0
    guecha.current_hp = 40.0
    victim.bleed_effect = {"dps": 1000.0, "time_remaining": 1.0}
    for _ in range(40):
        sim.step(0.1)
    assert victim.state == "dead"
    assert abs(guecha.current_hp - 45.0) < 0.01   # +5 HP healed over 3s
