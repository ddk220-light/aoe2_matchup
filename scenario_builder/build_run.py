"""build_run.py — generate a per-run matchup scenario from the golden template.

The golden template (`templates/template_landscape_jungle.aoe2scenario`) is the
hand-decorated jungle battlefield: map, terrain, Gaia eye-candy, both player
slots, the two 30-unit armies in formation, the scout keep-alive, and the control
triggers (diplomacy / camera / title / 3-2-1 countdown / win conditions). It is
tech-free (post-imperial armies are already fully upgraded — see prepare_template.py).

For each run this loads that template and does the ONLY per-run changes:
  * set each fighting player's civilization,
  * swap each army's unit type (P2 = side 1, P3 = side 2),
  * retarget every trigger that referenced the old unit types,
  * refresh the on-screen title,
  * add a force-engage so the two armies cross the arena and collide,
and writes the result to /tmp for the automation to stage into the game folder.

No survivor readout / OCR machinery — the result video is a clean
intro-card -> real fight -> recap-card (counts are not extracted).

  python build_run.py \
      --side1 Muisca:elite_temple_guard:"Elite Temple Guard" \
      --side2 Aztecs:elite_jaguar_warrior:"Elite Jaguar Warrior" \
      --out /tmp/aoe2_matchup_runs/muisca_temple_guard_vs_aztec_jaguar.aoe2scenario
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.datasets.object_support import Civilization

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "templates" / "template_landscape_jungle.aoe2scenario"
RUN_DIR = Path("/tmp/aoe2_matchup_runs")        # generated scenarios live here

SCOUT_CONST = UnitInfo.SCOUT_CAVALRY.ID         # 448 — never swapped (it's the AI's explorer)
P_SPECTATOR, P_SIDE1, P_SIDE2 = 1, 2, 3         # player slots in the template


def unit_const(key: str) -> int:
    """Map a unit key like 'elite_temple_guard' -> its scenario unit id (2587)."""
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


def _retarget(scn, old1, new1, old2, new2):
    """Rewrite every trigger condition/effect that referenced an old army unit type."""
    swap = {old1: new1, old2: new2}
    for trig in scn.trigger_manager.triggers:
        for cond in trig.conditions:
            ol = getattr(cond, "object_list", None)
            if ol in swap:
                cond.object_list = swap[ol]
        for eff in trig.effects:
            uid = getattr(eff, "object_list_unit_id", None)
            if uid in swap:
                eff.object_list_unit_id = swap[uid]


def _set_title(scn, n1, label1, n2, label2):
    """Rewrite the Setup trigger's matchup title (the VS line), leaving the
    '3'/'2'/'1' countdown messages untouched."""
    new_title = f"{n1} {label1}  VS  {n2} {label2}"
    for trig in scn.trigger_manager.triggers:
        if trig.name != "Setup":
            continue
        for eff in trig.effects:
            msg = getattr(eff, "message", None)
            if msg and " VS " in msg:          # the matchup title, not the '3'/'2'/'1' countdown
                eff.message = new_title
                return


def _centroid(units, const):
    pts = [(u.x, u.y) for u in units if u.unit_const == const]
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))


def _add_engage(scn, new1, new2, c1, c2, engage_at=4):
    """The template freezes both armies for the countdown (stop_object) but never
    releases them — add an Engage trigger that PATROLs each army into the other's
    start position so they cross the arena and collide. (Patrol is steadier than a
    single attack-move, which can stall.)"""
    tm = scn.trigger_manager
    eng = tm.add_trigger("Engage", enabled=True, looping=False)
    eng.new_condition.timer(timer=engage_at)
    eng.new_effect.patrol(source_player=P_SIDE1, object_list_unit_id=new1,
                          location_x=int(round(c2[0])), location_y=int(round(c2[1])))
    eng.new_effect.patrol(source_player=P_SIDE2, object_list_unit_id=new2,
                          location_x=int(round(c1[0])), location_y=int(round(c1[1])))


def build_run(side1, side2, out_path, template=TEMPLATE):
    """side1/side2 = (civ_name, unit_key, label). Writes the run scenario; returns Path."""
    civ1, key1, label1 = side1
    civ2, key2, label2 = side2
    new1, new2 = unit_const(key1), unit_const(key2)

    scn = AoE2DEScenario.from_file(str(template))
    pm, um = scn.player_manager, scn.unit_manager

    def player(pid):
        return next(p for p in pm.players if p.player_id == pid)

    player(P_SIDE1).civilization = civ_enum(civ1)
    player(P_SIDE2).civilization = civ_enum(civ2)

    u1 = um.get_player_units(P_SIDE1)
    u2 = um.get_player_units(P_SIDE2)
    old1, old2 = _test_const(u1), _test_const(u2)

    n1 = n2 = 0
    for u in u1:
        if u.unit_const == old1:
            u.unit_const = new1
            n1 += 1
    for u in u2:
        if u.unit_const == old2:
            u.unit_const = new2
            n2 += 1

    _retarget(scn, old1, new1, old2, new2)
    _set_title(scn, n1, label1, n2, label2)
    c1 = _centroid(um.get_player_units(P_SIDE1), new1)
    c2 = _centroid(um.get_player_units(P_SIDE2), new2)
    _add_engage(scn, new1, new2, c1, c2)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # parser refuses to overwrite an existing file → write temp then move
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd)
    os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))
    print(f"[build_run] {label1} ({civ1}, {new1}) x{n1}  vs  {label2} ({civ2}, {new2}) x{n2}")
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
