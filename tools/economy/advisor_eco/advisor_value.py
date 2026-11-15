"""Matchup value of one advisor cell (owner design 2026-11-15, "Revision 5").

For a decided cell, from the winner's side:

    value = hp x R**X_REPLENISH x P**Y_PRODUCTION x S**z

- ``hp``  = min(1, winner HP left / HP_FULL). Winner HP left is the seed mean with seeds the
            winner did not win counted as 0 (split seeds therefore pull it down).
- ``R``   = loser's army cost / winner's army cost: the units' purchase in villager-minutes
            (civ eco bonuses and discounts included, no buildings, no research).
- ``P``   = loser's / winner's 60-second production buildings in villager-minutes
            (fractional buildings, stone weighted 1.5).
- ``S``   = winner's / loser's movement speed. ``z = Z_SPEED``, doubled when exactly one of
            the two units is ranged (a faster ranged unit can avoid, kite or pick fights).

The loser's value is the same number, negative. "Close" cells (the campaign's label for seeds
that disagree, from 9-1 to 5-5) are scored by their seeds (owner 2026-11-15): the side that won
more seeds is the winner, with the same HP rule. Exact seed ties and identical units are 0.
Cells without seed HP (first-pass records not in git) use ``NO_HP_ASSUMED``.
"""
from __future__ import annotations

HP_FULL = 0.75
X_REPLENISH = 0.5
Y_PRODUCTION = 0.25
Z_SPEED = 0.5
MIXED_SPEED_FACTOR = 2.0
SPEED_FLOOR = 0.3      # tiles/s; guards stationary units
VM_FLOOR = 1.0         # villager-minutes; guards a zero building bill
NO_HP_ASSUMED = 0.5

CONSTANTS = {"hpFull": HP_FULL, "replenishExponent": X_REPLENISH, "productionExponent": Y_PRODUCTION,
             "speedExponent": Z_SPEED, "mixedSpeedFactor": MIXED_SPEED_FACTOR, "speedFloor": SPEED_FLOOR,
             "villagerMinuteFloor": VM_FLOOR, "noHpAssumed": NO_HP_ASSUMED}


def winner_hp(cell, w):
    """Seed-mean HP fraction of winner ``w`` ('a'/'b'); lost/drawn seeds count 0. None without seeds."""
    seeds = cell["seeds"]
    if not seeds:
        return None
    return (cell["hp_avg_won"] or 0.0) * cell["seeds_won_" + w] / seeds


def cell_value(cell, motion):
    """Signed value from side a (0 for draws) and its components. ``motion``: unit id -> motion()."""
    outcome = cell["outcome"]
    if outcome == "close_uncertain":
        won_a, won_b = cell["seeds_won_a"] or 0, cell["seeds_won_b"] or 0
        outcome = "a_win" if won_a > won_b else "b_win" if won_b > won_a else "draw"
    if outcome not in ("a_win", "b_win"):
        return 0.0, None
    w, l = ("a", "b") if outcome == "a_win" else ("b", "a")
    hp = winner_hp(cell, w)
    hp_known = hp is not None
    h = min(1.0, (hp if hp_known else NO_HP_ASSUMED) / HP_FULL)
    replenish = max(VM_FLOOR, cell["army_vm_" + l]) / max(VM_FLOOR, cell["army_vm_" + w])
    production = max(VM_FLOOR, cell["bld_vm_" + l]) / max(VM_FLOOR, cell["bld_vm_" + w])
    mw, ml = motion[cell[w]], motion[cell[l]]
    speed = max(SPEED_FLOOR, mw["speed"]) / max(SPEED_FLOOR, ml["speed"])
    mixed = mw["ranged"] != ml["ranged"]
    z = Z_SPEED * (MIXED_SPEED_FACTOR if mixed else 1.0)
    value = h * replenish ** X_REPLENISH * production ** Y_PRODUCTION * speed ** z
    parts = {"winner": w, "hp": hp, "hpKnown": hp_known, "R": replenish, "P": production, "S": speed, "mixed": mixed}
    return (value if w == "a" else -value), parts
