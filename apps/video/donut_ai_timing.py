"""Unit-specific Donut firing windows, without changing numbered AI jumps.

The legacy reference attack_delay is frame_delay / 60, not game animation
time. Use the installed attack graphic's frame duration for release timing.
Keep application explicit: changing timing does not authorize recapturing a
frozen campaign or silently replacing its embedded AI.

Units fixed this way so far: Slinger (Incas 185), Bolas Rider (Mapuche
2569/2571, whose 0.76 s windup was cut at the table's 377 ms and released
almost nothing) and War Wagon (Koreans 827/829, ~1.0 s release vs 593 ms).
"""
from __future__ import annotations

import math
from pathlib import Path

from aoe2x.js_simulation.tools.export_unit_mechanics import _animation_seconds, _raw_unit


def unit_timing(dat: Path, civ: str, master: int, label: str) -> dict:
    """Release time of one unit's attack, read from the installed DAT animation."""
    data, unit = _raw_unit(dat, civ, master)
    animation = _animation_seconds(data, int(unit.type_50.attack_graphic), 'attack')
    release = int(unit.type_50.frame_delay) * animation['frame_duration_seconds']
    return dict(master=master, civilization=civ, label=label, frameDelay=int(unit.type_50.frame_delay),
                animation=animation, releaseSeconds=release,
                releaseMs=math.ceil(release * 1000), marginMs=60,
                firingWindowMs=math.ceil(release * 1000) + 60)


def slinger_timing(dat: Path) -> dict:
    timing = unit_timing(dat, 'Incas', 185, 'Slinger')
    del timing['label']  # keep the frozen Slinger receipts byte-identical
    return timing


def bolas_timing(dat: Path) -> list[dict]:
    return [unit_timing(dat, 'Mapuche', master, label)
            for master, label in ((2569, 'Bolas Rider'), (2571, 'Elite Bolas Rider'))]


def war_wagon_timing(dat: Path) -> list[dict]:
    return [unit_timing(dat, 'Koreans', master, label)
            for master, label in ((827, 'War Wagon'), (829, 'Elite War Wagon'))]


# Unique units whose table window is far below their installed release
# (Arambai 310 vs 600 ms, Gbeto 560 vs 1001, Elite Jarl 343 vs 737, Mameluke
# 260 vs 401); Guecha (477 vs 501) is included so every new unit uses the
# installed timing. Each entry: civ, ((master, label), ...).
UNIQUE_TIMINGS = {
    'arambai': ('Burmese', ((1126, 'Arambai'), (1128, 'Elite Arambai'))),
    'gbeto': ('Malians', ((1013, 'Gbeto'), (1015, 'Elite Gbeto'))),
    'guecha': ('Muisca', ((2562, 'Guecha Warrior'), (2564, 'Elite Guecha Warrior'))),
    'jarl': ('Varangians', ((2708, 'Jarl'), (2709, 'Elite Jarl'))),
    'mameluke': ('Saracens', ((282, 'Mameluke'), (556, 'Elite Mameluke'))),
    # Infantry class: the AI's class searches miss it entirely (needs discovery).
    'chakram': ('Gurjaras', ((1741, 'Chakram Thrower'), (1743, 'Elite Chakram Thrower'))),
}


def unique_timing(dat: Path, key: str) -> list[dict]:
    civ, units = UNIQUE_TIMINGS[key]
    return [unit_timing(dat, civ, master, label) for master, label in units]


def add_discovery(ai: str, master: int, after: int) -> str:
    """Let the AI find a ranged unit its class searches miss (e.g. Jarl is Cavalry class).

    Adds a search action next to each existing one for `after`; no rule is added,
    so the numbered jumps stay valid."""
    marker = f'\t(up-find-local c: {after} c: 240)'
    if ai.count(marker) != 3 or f'(up-find-local c: {master} c: 240)' in ai:
        raise ValueError(f'Unexpected discovery pipeline for {master}; review before editing')
    before = ai.count('(defrule')
    ai = ai.replace(marker, marker + f'\n\t(up-find-local c: {master} c: 240)')
    assert ai.count('(defrule') == before
    return ai


def protect_volley(ai: str, timings: list[dict]) -> str:
    """Give each listed unit type its installed firing window and volley hold.

    All other units retain their existing transitions. Rules 0..77 contain
    absolute jumps: add actions/conditions inside those rules, never insert a
    rule there. The type overrides must precede the gWset=2 latch; putting
    them at EOF makes them unreachable.
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
    overrides = ''
    for timing in timings:
        window = int(timing['firingWindowMs'])
        overrides += (f'; {timing["label"]}: installed animation release {timing["releaseMs"]} ms + '
                      f'{timing["marginMs"]} ms margin. Protect windup before any retreat.\n'
                      '(defrule\n\t(up-compare-goal gWset c:== 1)\n'
                      f'\t(up-compare-goal gUType c:== {timing["master"]})\n\t=>\n'
                      f'\t(up-modify-goal gWfire c:= {window})\n'
                      f'\t(up-modify-goal gVolleyHold c:= {window})\n)\n')
    ai = ai.replace(latch, overrides + latch)
    assert ai.split(core_end)[0].count('(defrule') == original_core_rules
    return ai


DWELL_CLAMP = '\t(up-modify-goal gDwell c:min 2200)\n'


def min_retreat(ai: str, ms: int) -> str:
    """Make every kite retreat last at least `ms` before the ball may turn and fire.

    Rule 46 (18->22) waits for gStateAge >= gDwell. The appendix sets gDwell =
    clamp(reload - 1400, 400, 2200), i.e. 400 ms for cavalry archers, so they
    turn the moment ~91% have reloaded. Adds one action after that clamp: no
    rule is added, so the numbered jumps stay valid."""
    if ai.count(DWELL_CLAMP) != 1 or 'gDwell c:max' in ai.replace('gDwell c:max 400', ''):
        raise ValueError('Unexpected kite dwell rule; review before editing')
    before = ai.count('(defrule')
    ai = ai.replace(DWELL_CLAMP, DWELL_CLAMP + f'\t(up-modify-goal gDwell c:max {int(ms)})\t; minimum retreat\n')
    assert ai.count('(defrule') == before
    return ai


VOLLEY_STATE = '\t(up-compare-goal gState c:== 22)\n'


def _volley_exits(ai: str, numbers=(44, 45)):
    """Yield (start, end) of the VOLLEY->KITE transition rules, checked to be unique."""
    for number in numbers:
        start = ai.index(f';--- Rule {number} --')
        end = ai.index(f';--- Rule {number + 1} --', start)
        if ai[start:end].count(VOLLEY_STATE) != 1:
            raise ValueError(f'Unexpected volley transition {number}')
        yield start, end


def hold_volley(ai: str, hold_ms: int) -> str:
    """Stand and fire for at least `hold_ms` before any retreat (e.g. 2-3 shots).

    Gates both VOLLEY exits (rules 44 and 45) on gStateAge >= gVolleyHold, the
    same mechanism protect_volley uses; give hold_ms = (shots - 1) x reload +
    fire window + margin. Conditions are added inside existing rules only."""
    if '(defconst gVolleyHold ' in ai:
        raise ValueError('A volley hold is already applied; do not patch twice')
    rules = ai.count('(defrule')
    ai = ai.replace('(defconst gWset 192)', '(defconst gVolleyHold 214)\n(defconst gWset 192)', 1)
    ai = ai.replace('\t(up-modify-goal gWset c:= 0)\n',
                    f'\t(up-modify-goal gVolleyHold c:= {int(hold_ms)})\n\t(up-modify-goal gWset c:= 0)\n', 1)
    for start, end in reversed(list(_volley_exits(ai))):
        ai = ai[:start] + ai[start:end].replace(
            VOLLEY_STATE, VOLLEY_STATE + '\t(up-compare-goal gStateAge g:>= gVolleyHold)\n') + ai[end:]
    assert ai.count('(defrule') == rules
    return ai


def threat_gate(ai: str, distance: int) -> str:
    """Keep firing until an enemy is within `distance` (precise units, 100 = 1 tile).

    Rule 44 (the not-close VOLLEY exit) gets gDistClosE < distance; rule 45
    (enemy within 2.5 tiles) is unchanged, so the ball still runs when caught."""
    if 'gDistClosE c:< ' + str(int(distance)) in ai:
        raise ValueError('Threat gate already applied')
    rules = ai.count('(defrule')
    (start, end), = _volley_exits(ai, (44,))
    ai = ai[:start] + ai[start:end].replace(
        VOLLEY_STATE, VOLLEY_STATE + f'\t(up-compare-goal gDistClosE c:< {int(distance)})\n') + ai[end:]
    assert ai.count('(defrule') == rules
    return ai


VOLLEY_TIMEOUT = '\t\t(up-compare-goal gStateAge c:>= 3000))\n'


def cap_volley(ai: str, margin_ms: int = 100, after_fire_ms: int | None = None) -> str:
    """Stop fast-reload units firing twice per volley.

    Rule 44 leaves VOLLEY when most of the ball has finished its shot and most
    are still reloading, or after 3000 ms. With a short reload (Mongol cavalry
    archers, 1.43 s) the units are ready again before that ever holds, so the
    ball fires a second time and only leaves on the 3000 ms timeout. Replace
    the timeout with min(3000, reload - margin_ms), never below the fire window
    + 200 (first shots always complete). Quick-windup units (Mangudai, 0.38 s)
    start their second shot before the next AI pass, so need a larger margin.
    `after_fire_ms` additionally caps the volley at fire window + after_fire_ms,
    independent of the live reload read (the Mangudai's civ fire-rate bonus is
    not reflected in the reload the AI reads, so reload - margin is too late). The literal is swapped in place and the cap
    is computed in the appendix dwell rule: no rule is added.
    """
    if '(defconst gVolleyCap ' in ai:
        raise ValueError('Volley cap already applied; do not patch twice')
    start = ai.index(';--- Rule 44 --')
    end = ai.index(';--- Rule 45 --', start)
    if ai[start:end].count(VOLLEY_TIMEOUT) != 1 or ai.count(DWELL_CLAMP) != 1:
        raise ValueError('Unexpected volley exit rule; review before editing')
    rules = ai.count('(defrule')
    ai = ai[:start] + ai[start:end].replace(
        VOLLEY_TIMEOUT, '\t\t(up-compare-goal gStateAge g:>= gVolleyCap))\n') + ai[end:]
    ai = ai.replace('(defconst gWset 192)',
                    '(defconst gVolleyCap 215)\n(defconst gVolleyMin 216)\n(defconst gWset 192)', 1)
    ai = ai.replace('\t(up-modify-goal gWset c:= 0)\n',
                    '\t(up-modify-goal gVolleyCap c:= 3000)\n\t(up-modify-goal gWset c:= 0)\n', 1)
    ai = ai.replace(DWELL_CLAMP, DWELL_CLAMP +
                    '\t(up-modify-goal gVolleyCap g:= gReload)\t; volley cap: one shot per volley\n'
                    f'\t(up-modify-goal gVolleyCap c:- {int(margin_ms)})\n'
                    '\t(up-modify-goal gVolleyCap c:min 3000)\n' +
                    ('' if after_fire_ms is None else
                     '\t(up-modify-goal gVolleyMin g:= gWfire)\n'
                     f'\t(up-modify-goal gVolleyMin c:+ {int(after_fire_ms)})\n'
                     '\t(up-modify-goal gVolleyCap g:min gVolleyMin)\n') +
                    '\t(up-modify-goal gVolleyMin g:= gWfire)\n'
                    '\t(up-modify-goal gVolleyMin c:+ 200)\n'
                    '\t(up-modify-goal gVolleyCap g:max gVolleyMin)\n', 1)
    assert ai.count('(defrule') == rules
    init = ai[:ai.index('(up-modify-goal gVolleyCap c:= 3000)')]
    init_rule = ai[init.rindex('(defrule'):ai.index('\n)', len(init))]
    assert sum(1 for line in init_rule.splitlines() if line.startswith('\t(')) <= 32, 'init rule too long'
    return ai


def protect_slinger_volley(ai: str, timing: dict) -> str:
    """Patch Slinger only (frozen behaviour of the Slinger timing probe)."""
    return protect_volley(ai, [dict(timing, label='Slinger')])
