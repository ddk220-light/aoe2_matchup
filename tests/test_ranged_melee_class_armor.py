"""Damage class, not delivery range, decides which armor resists a hit.

A ranged unit whose base attack is class 4 (melee) and which has no class-3
entry is resisted by MELEE armor. That covers 19 units in the current dat:
thrown-melee (Gbeto, Mameluke, Throwing Axeman, Chakram Thrower), the
mangonel/onager line, bombards and houfnice, trebuchet variants, and most
warships.

These matter because the tape corpus in aoe2x/validation/ contains none of
those 19 units, so the fidelity rig cannot catch a regression here.

Numbers below mirror real dat rows (checked 2026-07-27):
    Elite Gbeto     attacks {"4": 15, ...}   -- no class-3 entry
    Elite Huskarl   armors  {"4": 2, "3": 10} -- the anti-archer unit
Resolving the Gbeto against pierce armor gives 15-10 = 5; against melee armor,
which is what the game does, it gives 15-2 = 13. The bug cost 62% of the hit.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aoe2x.sim.simulation_real import BattleUnit  # noqa: E402


def _unit(**kw):
    s = {
        "hp": 100, "attack": 10, "attack_speed": 0.5, "attack_delay": 0,
        "movement_speed": 1.0, "melee_armor": 0, "pierce_armor": 0,
        "attacks_json": '{"4":10}', "armors_json": '{"4":0,"3":0}',
        "attack_range": 0, "accuracy": 100,
    }
    s.update(kw)
    return BattleUnit("u", 1, s)


# Elite Huskarl: thin melee armor, very thick pierce armor.
HUSKARL = dict(armors_json='{"4":2,"3":10}', melee_armor=2, pierce_armor=10)


def test_thrown_melee_attack_resolves_against_melee_armor():
    """Elite Gbeto: ranged delivery, class-4 damage -> melee armor applies."""
    gbeto = _unit(attack_range=6.0, attack=15, attacks_json='{"4":15}')
    huskarl = _unit(**HUSKARL)
    # 15 - 2 (melee armor), NOT 15 - 10 (pierce armor)
    assert gbeto.get_damage_against(huskarl) == 13


def test_normal_archer_still_resolves_against_pierce_armor():
    """Regression guard: a real class-3 attack must keep using pierce armor."""
    arbalest = _unit(attack_range=11.0, attack=10, attacks_json='{"3":10}')
    huskarl = _unit(**HUSKARL)
    # 10 attack - 10 pierce armor = 0, raised to the AoE2 minimum of 1.
    # That floor IS the Huskarl's identity: arbalest fire barely scratches it.
    assert arbalest.get_damage_against(huskarl) == 1


def test_melee_unit_unchanged():
    """Regression guard: melee units were always correct; keep them that way."""
    champion = _unit(attack=22, attacks_json='{"4":22}')
    huskarl = _unit(**HUSKARL)
    assert champion.get_damage_against(huskarl) == 20  # 22 - 2


def test_zero_class3_entry_counts_as_melee_class():
    """An explicit "3": 0 is not a pierce attack -- it must fall through to 4."""
    u = _unit(attack_range=6.0, attack=15, attacks_json='{"3":0,"4":15}')
    huskarl = _unit(**HUSKARL)
    assert u.get_damage_against(huskarl) == 13


def test_ignores_armor_flag_follows_damage_class_not_delivery():
    """A thrown-melee unit that ignores MELEE armor must have it honoured.

    Before the fix the ignores_* branch keyed off is_ranged(), so a ranged
    unit could only ever consume ignores_pierce_armor -- meaning a thrown-melee
    armor-ignoring attack silently paid full melee armor.
    """
    ignore_melee = _unit(attack_range=6.0, attack=15, attacks_json='{"4":15}',
                         ignores_melee_armor=True)
    huskarl = _unit(**HUSKARL)
    assert ignore_melee.get_damage_against(huskarl) == 15   # armor zeroed

    # ...and the pierce-ignoring flag must NOT fire for a melee-class attack.
    ignore_pierce = _unit(attack_range=6.0, attack=15, attacks_json='{"4":15}',
                          ignores_pierce_armor=True)
    assert ignore_pierce.get_damage_against(huskarl) == 13   # melee armor still applies


def test_bonus_damage_unaffected_by_the_class_rule():
    """The base-class rule must not disturb per-class bonus accumulation."""
    # class 8 = cavalry-ish bonus; target carries a class-8 armor entry of 1.
    u = _unit(attack_range=6.0, attack=15, attacks_json='{"4":15,"8":6}')
    target = _unit(armors_json='{"4":2,"3":10,"8":1}', melee_armor=2, pierce_armor=10)
    # base 15-2 = 13, bonus 6-1 = 5
    assert u.get_damage_against(target) == 18
