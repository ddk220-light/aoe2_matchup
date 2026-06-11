"""combat_math.py — the duel numbers the detail cards show: damage per hit vs THIS
opponent, effective DPS, hits-to-kill and time-to-kill, charge attacks included.

Pure functions over the raw attack/armor dicts that overlay_data.get_unit_card exposes
(parsed from the reference DB's final_attacks_json / final_armors_json), so the cards
don't re-implement combat rules ad hoc.

AoE2 damage rules implemented here:
  * per attack class: max(0, attack - armor), counted ONLY when the defender belongs
    to that armor class (base melee/pierce always apply; bonus classes need membership);
  * the total per hit is never below 1;
  * the unit's PRIMARY damage type is whichever base class (3=pierce, 4=melee) carries
    the bigger attack — NOT is_ranged (e.g. the Guecha Warrior is a melee unit dealing
    pierce damage);
  * charge attacks (charge_attack_melee) add onto the primary base attack for one hit
    when charged — armor applies unless charge_ignores_armor — and armies enter the
    fight charged, so the FIRST hit carries it;
  * effective DPS folds in the attacker's accuracy when it's a ranged unit.
"""
from __future__ import annotations

import math

BASE_PIERCE, BASE_MELEE = 3, 4
BASE_CLASSES = (BASE_PIERCE, BASE_MELEE)


def _ints(d: dict) -> dict:
    return {int(k): float(v) for k, v in (d or {}).items()}


def primary_damage_class(attacks: dict) -> int:
    """3 (pierce) or 4 (melee) — whichever base class carries the bigger attack."""
    atk = _ints(attacks)
    return max(BASE_CLASSES, key=lambda c: atk.get(c, 0.0))


def damage_per_hit(attacks: dict, armors: dict, extra_base: float = 0.0,
                   ignore_armor: bool = False) -> float:
    """One hit's damage vs this defender. `extra_base` is charge damage folded onto
    the attacker's primary base class (reduced by that armor unless ignore_armor)."""
    atk, arm = _ints(attacks), _ints(armors)
    primary = max(BASE_CLASSES, key=lambda c: atk.get(c, 0.0))
    total = 0.0
    for c, a in atk.items():
        if a <= 0 and c != primary:
            continue
        if c in BASE_CLASSES:
            bonus = extra_base if (c == primary and not ignore_armor) else 0.0
            total += max(0.0, a + bonus - arm.get(c, 0.0))
        elif c in arm:                       # bonus damage needs armor-class membership
            total += max(0.0, a - arm.get(c, 0.0))
    if ignore_armor:
        total += extra_base
    return max(1.0, total)


def duel(attacker: dict, defender: dict) -> dict | None:
    """Card-level duel summary for attacker vs ONE defender unit. Both args are
    get_unit_card dicts (raw fields: attacks/armors/hp/reload_s/accuracy_pct/charge).

    Returns {dmg, first_hit, hits, dps, ttk_s, charge} or None when data is missing.
      dmg       damage per (regular) hit
      first_hit damage of the opening hit (charge included, if any)
      hits      hits to kill one defender (first hit charged)
      dps       effective damage/second = dmg x accuracy / reload
      ttk_s     time to kill one defender = (hits-1) x reload (first hit immediate)
      charge    the charge attack amount, or None
    """
    atk_j, arm_j = attacker.get("attacks"), defender.get("armors")
    hp = float(defender.get("hp") or 0)
    reload_s = float(attacker.get("reload_s") or 0)
    if not atk_j or arm_j is None or hp <= 0:
        return None
    dmg = damage_per_hit(atk_j, arm_j)
    ch = attacker.get("charge") or {}
    charge_amt = float(ch.get("melee") or 0)
    first = (damage_per_hit(atk_j, arm_j, extra_base=charge_amt,
                            ignore_armor=bool(ch.get("ignores_armor")))
             if charge_amt else dmg)
    hits = 1 + max(0, math.ceil((hp - first) / dmg))
    acc = attacker.get("accuracy_pct")
    eff = dmg * (acc / 100.0 if attacker.get("is_ranged") and acc else 1.0)
    dps = round(eff / reload_s, 1) if reload_s else None
    ttk = round((hits - 1) * reload_s, 1) if reload_s else None
    return {"dmg": dmg, "first_hit": first, "hits": hits, "dps": dps,
            "ttk_s": ttk, "charge": charge_amt or None}
