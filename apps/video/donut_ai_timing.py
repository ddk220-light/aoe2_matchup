"""Unit-specific Donut firing windows, without changing numbered AI jumps.

The legacy reference attack_delay is frame_delay / 60, not game animation
time. Use the installed attack graphic's frame duration for release timing.
Keep application explicit: changing timing does not authorize recapturing a
frozen campaign or silently replacing its embedded AI.
"""
from __future__ import annotations

import math
from pathlib import Path

from aoe2x.js_simulation.tools.export_unit_mechanics import _animation_seconds, _raw_unit


def slinger_timing(dat: Path) -> dict:
    data, unit = _raw_unit(dat, 'Incas', 185)
    animation = _animation_seconds(data, int(unit.type_50.attack_graphic), 'attack')
    release = int(unit.type_50.frame_delay) * animation['frame_duration_seconds']
    return dict(master=185, civilization='Incas', frameDelay=int(unit.type_50.frame_delay),
                animation=animation, releaseSeconds=release,
                releaseMs=math.ceil(release * 1000), marginMs=60,
                firingWindowMs=math.ceil(release * 1000) + 60)


def protect_slinger_volley(ai: str, timing: dict) -> str:
    """Patch Slinger only; all other units retain their existing transitions.

    Rules 0..77 contain absolute jumps. Add actions/conditions inside those
    rules, never insert a rule there. The type override must precede the
    gWset=2 latch; putting it at EOF makes it unreachable.
    """
    if '(defconst gVolleyHold ' in ai:
        raise ValueError('Firing protection already applied; do not patch twice')
    core_end = ';=== DIAGNOSTIC TRACE'
    original_core_rules = ai.split(core_end)[0].count('(defrule')
    if original_core_rules != 78:
        raise ValueError('Unexpected AI rule numbering; inspect before modifying')
    ai = ai.replace('(defconst gWset 192)', '(defconst gVolleyHold 214)\n(defconst gWset 192)', 1)
    ai = ai.replace('(up-modify-goal gWset c:= 0)',
                    '(up-modify-goal gVolleyHold c:= 0)\n\t(up-modify-goal gWset c:= 0)', 1)
    for number in (44, 45):
        start = ai.index(f';--- Rule {number} --')
        end = ai.index(f';--- Rule {number + 1} --', start)
        block = ai[start:end]
        marker = '\t(up-compare-goal gState c:== 22)\n'
        if block.count(marker) != 1:
            raise ValueError(f'Unexpected volley transition {number}')
        block = block.replace(marker, marker + '\t(up-compare-goal gStateAge g:>= gVolleyHold)\n')
        ai = ai[:start] + block + ai[end:]
    latch = '(defrule\n\t(up-compare-goal gWset c:== 1)\n\t=>\n\t(up-modify-goal gWset c:= 2)\n)'
    if ai.count(latch) != 1:
        raise ValueError('Cannot find unique unit timing latch')
    window = int(timing['firingWindowMs'])
    override = (f'; Slinger: installed animation release {timing["releaseMs"]} ms + '
                f'{timing["marginMs"]} ms margin. Protect windup before any retreat.\n'
                '(defrule\n\t(up-compare-goal gWset c:== 1)\n'
                '\t(up-compare-goal gUType c:== 185)\n\t=>\n'
                f'\t(up-modify-goal gWfire c:= {window})\n'
                f'\t(up-modify-goal gVolleyHold c:= {window})\n)\n')
    ai = ai.replace(latch, override + latch)
    assert ai.split(core_end)[0].count('(defrule') == original_core_rules
    return ai
