"""build_run.py — generate a per-run matchup scenario from the golden template.

The golden template (`templates/new_template.aoe2scenario`) is the hand-decorated
battlefield: map, terrain, Gaia eye-candy, both player slots, the two armies placed
**adjacent** (so they auto-engage on contact — no patrol trigger needed), the scout
keep-alive, and the control triggers (diplomacy / camera / title / 3-2-1 countdown /
live readout / win conditions). It is tech-free (armies start Post-Imperial, already
fully upgraded).

The template already carries all those triggers, authored for one specific matchup.
For each run this loads it and does only the per-run changes:
  * set each fighting player's civilization (P2 = side 1, P3 = side 2),
  * set the SPECTATOR (P1) civ to side 2's civ, so the game plays that civ's music,
  * swap each army's unit type while KEEPING the template's hand-placed positions,
  * retarget the existing triggers (count/win/readout/title) to this run's units+counts,
and writes the result for the automation to stage into the game folder.

  python build_run.py \
      --side1 Muisca:elite_temple_guard:"Elite Temple Guard" \
      --side2 Aztecs:elite_jaguar_warrior:"Elite Jaguar Warrior" \
      --out /tmp/aoe2_matchup_runs/temple_guard_vs_jaguar.aoe2scenario
"""
from __future__ import annotations

import argparse
import math
import os
import tempfile
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.datasets.object_support import Civilization

WIN_MARKER = "WINS"   # the automation watches the center band for this word

# Clean footage by DEFAULT: the on-screen TITLE + live COUNT READOUT texts are blanked
# (the WINS hold stays — it's the recording stop signal). The overlay gets its counts
# from the gRPC data stream (decoder fixed + live-validated 2026-06-10); there is no
# OCR count fallback for these runs by deliberate choice — if a game patch drifts the
# decoder, fix it against the archived frames.bin and re-render. Set AOE2_NO_READOUT=0
# to put the readout back (e.g. for a one-off decoder cross-check run).
NO_READOUT = os.environ.get("AOE2_NO_READOUT", "1").lower() not in ("0", "", "false", "no")

HERE = Path(__file__).resolve().parent
# the GOLDEN template every run is generated from. default1 (2026-06-10) = the
# default3 (2026-06-11): the user's hand-tuned arena — boundary objects close every
# retreat path (566 GAIA) and the template CARRIES ITS OWN looping 'Contain strays'
# trigger, so the build must neither move trees nor add containment triggers; it only
# retargets the template trigger's unit filters to each matchup's army types.
TEMPLATE = HERE / "templates" / "default3.aoe2scenario"
RUN_DIR = Path("/tmp/aoe2_matchup_runs")        # (legacy; the auto path passes its own out)

SCOUT_CONST = UnitInfo.SCOUT_CAVALRY.ID         # 448 — never swapped (it's the AI's explorer)
P_SPECTATOR, P_SIDE1, P_SIDE2 = 1, 2, 3         # player slots in the template


# Unit keys whose scenario id can't be derived from the slug by a simple suffix-strip
# + UnitInfo[KEY] lookup (e.g. the Bengali Ratha's slug carries a "(melee)"/"(ranged)"
# mode tag the dataset spells without parentheses).
_KEY_CONST_OVERRIDE = {
    "elite_ratha_(melee)": int(UnitInfo.ELITE_RATHA_MELEE.ID),
    "elite_ratha_(ranged)": int(UnitInfo.ELITE_RATHA_RANGED.ID),
    "ratha_(melee)": int(UnitInfo.RATHA_MELEE.ID),
    "ratha_(ranged)": int(UnitInfo.RATHA_RANGED.ID),
    # the Shu War Chariot is a mode-switch unit (Focus Fire / Barrage); place its
    # default Focus Fire form
    "war_chariot": int(UnitInfo.WAR_CHARIOT_FOCUS_FIRE.ID),
}


def unit_const(key: str) -> int:
    """Map a unit key like 'elite_temple_guard' -> its scenario unit id (2587)."""
    if key in _KEY_CONST_OVERRIDE:
        return _KEY_CONST_OVERRIDE[key]
    return int(UnitInfo[key.upper()].ID)


def civ_enum(name: str) -> Civilization:
    """Map a civ name like 'Muisca' -> Civilization.MUISCA."""
    return Civilization[name.upper()]


def _test_const(units) -> int:
    """The army's test-unit const = the most common non-scout type the player owns."""
    from collections import Counter
    c = Counter(u.unit_const for u in units if u.unit_const != SCOUT_CONST)
    if not c:
        raise ValueError("no test units found for player")
    return c.most_common(1)[0][0]


def _grid_positions(count, cx, cy, spacing=1.0):
    """`count` positions in a centered ~square grid around (cx, cy)."""
    cols = max(1, int(math.ceil(math.sqrt(count))))
    rows = int(math.ceil(count / cols))
    x0 = cx - (cols - 1) * spacing / 2.0
    y0 = cy - (rows - 1) * spacing / 2.0
    return [(x0 + (i % cols) * spacing, y0 + (i // cols) * spacing) for i in range(count)]


def _choose_positions(positions, count, spacing=1.0):
    """Pick `count` placement points, PRESERVING the template's hand-placed formation.
    count == len -> use as-is; count < len -> keep the `count` closest to the formation
    centroid (a compact core); count > len -> keep all and add a small grid of extras at
    the centroid."""
    positions = list(positions)
    if count <= 0 or not positions:
        return positions[:max(0, count)]
    if count == len(positions):
        return positions
    cx = sum(x for x, _ in positions) / len(positions)
    cy = sum(y for _, y in positions) / len(positions)
    if count < len(positions):
        return sorted(positions, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)[:count]
    return positions + _grid_positions(count - len(positions), cx, cy, spacing)


def _swap_army_inplace(um, pid, old_const, new_const, count):
    """Replace player `pid`'s army (units of `old_const`) with `count` units of
    `new_const`, KEEPING the template's positions — the user hand-placed the formation,
    so we only swap the unit TYPE. See _choose_positions for count != template-size."""
    army = [u for u in um.get_player_units(pid) if u.unit_const == old_const]
    positions = [(u.x, u.y) for u in army]
    for u in army:
        um.remove_unit(unit=u)
    for (px, py) in _choose_positions(positions, count):
        um.add_unit(player=pid, unit_const=new_const, x=px, y=py)


def _strip_camp(um, pid, keep_const):
    """Remove every object player `pid` owns that ISN'T its army (`keep_const`) or the
    keep-alive scout. The template decorates each side with buildings/camp props (a yurt,
    army tents, a bonfire, supplies). After one army is wiped, the victors path over and
    ATTACK the loser's building, which looks wrong in the recap. Stripping them leaves only
    the army + scout, so the winners just stand. The scout stays so neither player ever hits
    0 objects (no defeat banner — the win trigger holds the result on screen instead)."""
    removed = 0
    for u in list(um.get_player_units(pid)):
        if u.unit_const != keep_const and u.unit_const != SCOUT_CONST:
            um.remove_unit(unit=u)
            removed += 1
    return removed


def _retarget_new_template(scn, new1, label1, n1, new2, label2, n2):
    """The golden template already carries the control triggers (title / countdown /
    win / live readout), authored for one specific matchup. Retarget them to THIS run,
    anchored on source_player (P2 = side 1, P3 = side 2) so it's robust to any unit-id
    drift in the template (e.g. it counts Elite Temple Guard while placing the non-elite):
      * COUNT_UNITS_INTO_VARIABLE -> count the ACTUAL army (P2->new1, P3->new2)
      * OWN_FEWER_OBJECTS         -> fire on ARMY wipe (object_list = that army), not on
                                     'any object' (a kept-alive scout would never let it
                                     reach zero, hanging the watch loop)
      * title / readout / WINS messages -> this run's labels and counts
    """
    from AoE2ScenarioParser.datasets.conditions import ConditionId
    from AoE2ScenarioParser.datasets.effects import EffectId
    COUNT = int(EffectId.COUNT_UNITS_INTO_VARIABLE)
    DISPLAY = int(EffectId.DISPLAY_INSTRUCTIONS)
    OWN_FEWER = int(ConditionId.OWN_FEWER_OBJECTS)
    by_src = {P_SIDE1: new1, P_SIDE2: new2}

    def _sp(obj):
        sp = getattr(obj, "source_player", None)
        try:
            return int(sp)
        except (TypeError, ValueError):
            return None

    TASK = 12                                          # EffectId.TASK_OBJECT
    for trig in scn.trigger_manager.triggers:
        wiped_src = None
        for cond in trig.conditions:
            if int(cond.condition_type) == OWN_FEWER and _sp(cond) in by_src:
                cond.object_list = by_src[_sp(cond)]   # fire when THIS army is gone
                cond.quantity = 1
                wiped_src = _sp(cond)
        for eff in trig.effects:
            et = int(eff.effect_type)
            if et == COUNT and _sp(eff) in by_src:
                eff.object_list_unit_id = by_src[_sp(eff)]
            elif et == TASK and _sp(eff) in by_src:
                # the template's own 'Contain strays' trigger (user-authored areas &
                # cadence): point its unit filter at THIS matchup's army types
                eff.object_list_unit_id = by_src[_sp(eff)]
            elif et == DISPLAY:
                msg = getattr(eff, "message", None) or ""
                if " VS " in msg:                              # the matchup title
                    eff.message = "" if NO_READOUT else f"{n1} {label1}  VS  {n2} {label2}"
                elif "<left1>" in msg or "<left2>" in msg:     # the live readout
                    eff.message = ("" if NO_READOUT
                                   else f"{label1}: <left1>   vs   {label2}: <left2>")
                elif "WINS" in msg.upper():                    # the result banner
                    winner = label2 if wiped_src == P_SIDE1 else label1
                    eff.message = f"{winner} {WIN_MARKER}!"
                    eff.display_time = 90                      # hold for OCR + viewer


def _army_centroid(um, pid, const):
    """Centroid (x, y) of player `pid`'s units of type `const`, or None."""
    pts = [(u.x, u.y) for u in um.get_player_units(pid) if u.unit_const == const]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


# NOTE: the template (default3) owns BOTH the boundary-tree layout and the looping
# 'Contain strays' trigger — per the user, the build must not move trees or add
# containment triggers; _retarget_new_template points the template trigger's unit
# filters at each matchup's army types instead.


def _set_camera(scn, ranged, c1, c2):
    """Recenter the spectator (P1) camera. In a RANGED-vs-MELEE fight the action collects
    around the ranged army (it kites back while the melee piles in), so center the view
    on THAT army's centroid. In a SAME-KIND fight (ranged-vs-ranged stands off between
    the spawns; melee-vs-melee collapses centrally) center on the MIDPOINT of the two
    armies — the template's authored view is tuned for the template's own matchup and
    can miss this one's fight entirely (seen live: Guecha vs Blackwood, both ranged)."""
    from AoE2ScenarioParser.datasets.effects import EffectId
    r1, r2 = ranged
    if c1 is None or c2 is None:
        return None
    if r1 == r2:
        target = ((c1[0] + c2[0]) / 2.0, (c1[1] + c2[1]) / 2.0)   # the clash midpoint
    else:
        target = c1 if r1 else c2                        # the ranged army
    vx, vy = int(round(target[0])), int(round(target[1]))
    CHANGE_VIEW = int(EffectId.CHANGE_VIEW)
    for trig in scn.trigger_manager.triggers:
        for eff in trig.effects:
            if int(eff.effect_type) == CHANGE_VIEW:
                eff.location_x = vx
                eff.location_y = vy
    return (vx, vy)


def build_run(side1, side2, out_path, counts=(30, 30), template=TEMPLATE,
              ranged=(False, False)):
    """side1/side2 = (civ_name, unit_key, label). `counts` = (n1, n2) units per side
    (equal-count is (30, 30); resource-capped runs pass uneven counts). `ranged` = (r1, r2)
    flags whether each side is a ranged unit — used to aim the spectator camera at the
    ranged army in a ranged-vs-melee fight. Writes the run scenario; returns Path."""
    civ1, key1, label1 = side1
    civ2, key2, label2 = side2
    new1, new2 = unit_const(key1), unit_const(key2)
    n1, n2 = counts

    scn = AoE2DEScenario.from_file(str(template))
    pm, um = scn.player_manager, scn.unit_manager

    def player(pid):
        return next(p for p in pm.players if p.player_id == pid)

    player(P_SIDE1).civilization = civ_enum(civ1)
    player(P_SIDE2).civilization = civ_enum(civ2)
    player(P_SPECTATOR).civilization = civ_enum(civ2)    # P1 spectator hears side-2 music

    old1 = _test_const(um.get_player_units(P_SIDE1))
    old2 = _test_const(um.get_player_units(P_SIDE2))
    _swap_army_inplace(um, P_SIDE1, old1, new1, n1)      # keep the template formation
    _swap_army_inplace(um, P_SIDE2, old2, new2, n2)
    # strip the decorative buildings/camp props off both fighting players so the victors
    # don't run off and attack them once the enemy army is gone
    r1 = _strip_camp(um, P_SIDE1, new1)
    r2 = _strip_camp(um, P_SIDE2, new2)
    if r1 or r2:
        print(f"[build_run] removed {r1 + r2} P2/P3 buildings/camp props")

    _retarget_new_template(scn, new1, label1, n1, new2, label2, n2)
    cam = _set_camera(scn, ranged, _army_centroid(um, P_SIDE1, new1),
                      _army_centroid(um, P_SIDE2, new2))
    if cam:
        kind = "midpoint" if ranged[0] == ranged[1] else "ranged army"
        print(f"[build_run] camera on the {kind} at {cam} "
              f"(trees and containment are the template's own — not touched)")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # parser refuses to overwrite an existing file → write temp then move
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd)
    os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))
    print(f"[build_run] {label1} ({civ1}, {new1}) x{n1}  vs  {label2} ({civ2}, {new2}) x{n2}")
    print(f"[build_run] P1 spectator civ = {civ2} (plays its music)")
    print(f"[build_run] wrote {out_path}")
    return out_path


def _parse_side(s: str):
    """'Muisca:elite_temple_guard:Elite Temple Guard' -> (civ, key, label)."""
    civ, key, label = s.split(":", 2)
    return civ.strip(), key.strip(), label.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side1", required=True, type=_parse_side,
                    help='CIV:unit_key:Display Label  (e.g. Muisca:elite_temple_guard:"Elite Temple Guard")')
    ap.add_argument("--side2", required=True, type=_parse_side)
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default=str(TEMPLATE))
    a = ap.parse_args()
    build_run(a.side1, a.side2, a.out, template=Path(a.template))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
