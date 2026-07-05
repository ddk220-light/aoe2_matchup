"""build_circle_test.py -- minimal NO-ENEMY arena to smoke-test ddkCircleTest.per.

One computer player (P2) gets a tight cluster of ranged units near map center; the
template's pinning triggers ('Contain strays' + Setup stop/stance) are disabled so the
AI can actually move them; a single lone P3 unit is parked in a far corner ONLY so the
match does not auto-end on a conquest victory. No real combat -- we just watch whether
ddkCircleTest walks the P2 cluster around a tight on-screen circle.

  python build_circle_test.py --out "<scenario folder>\\ddk Circle Test.aoe2scenario"
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from AoE2ScenarioParser import settings
    settings.PRINT_STATUS_UPDATES = False
except Exception:
    pass

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.trigger_lists import VictoryCondition

import build_run as BR

CAVALRY_ARCHER = 39
SCOUT = 448
STOP_OBJECT, CHANGE_OBJECT_STANCE = 29, 36


def build(out_path, count=12, unit=CAVALRY_ARCHER, map_size=80):
    scn = AoE2DEScenario.from_file(str(BR.TEMPLATE))
    pm, um, tm, om, mm = (scn.player_manager, scn.unit_manager, scn.trigger_manager,
                          scn.option_manager, scn.map_manager)

    if map_size and map_size != mm.map_size:
        prev = mm.map_size
        mm.map_size = map_size
        print(f"[circle] map resized {prev}x{prev} -> {map_size}x{map_size}")

    # wipe the template's two armies
    for pid in (BR.P_SIDE1, BR.P_SIDE2):
        for u in list(um.get_player_units(pid)):
            um.remove_unit(unit=u)

    # P2 cluster near center (4 cols), P2 -> computer
    cx = cy = mm.map_size // 2
    cols = 4
    for i in range(count):
        col, row = i % cols, i // cols
        x = cx - 1.5 + col
        y = cy - 1.0 + row
        um.add_unit(player=BR.P_SIDE1, unit_const=unit, x=x + 0.5, y=y + 0.5)
    p2 = next(p for p in pm.players if int(p.player_id) == BR.P_SIDE1)
    p2.human = False

    # lone faraway P3 unit so CONQUEST doesn't end the match instantly (no real fight)
    um.add_unit(player=BR.P_SIDE2, unit_const=SCOUT, x=5.5, y=5.5)
    p3 = next(p for p in pm.players if int(p.player_id) == BR.P_SIDE2)
    p3.human = False

    # disable the pinning triggers so ddkCircleTest can move units freely
    disabled = []
    for t in tm.triggers:
        nm = (getattr(t, "name", "") or "").strip().lower()
        if nm == "contain strays":
            t.enabled = 0
            disabled.append("Contain strays")
        if nm == "setup":
            for e in t.effects:
                if (int(getattr(e, "effect_type", -1)) in (STOP_OBJECT, CHANGE_OBJECT_STANCE)
                        and int(getattr(e, "source_player", -1) or -1) in (BR.P_SIDE1, BR.P_SIDE2)):
                    try:
                        e.enabled = 0
                        disabled.append(f"Setup eff{int(e.effect_type)}/sp{int(e.source_player)}")
                    except Exception:
                        pass

    om.victory_condition = VictoryCondition.CONQUEST

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd); os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))

    print(f"[circle] P2 = computer, {count}x unit {unit} clustered at ({cx},{cy})")
    print(f"[circle] lone P3 scout at (5,5) (anti-auto-win); disabled: {disabled}")
    print(f"[circle] wrote {out_path}")
    print(f"[circle] >>> in editor: load it, assign ddkCircleTest to P2, Test (any difficulty)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--unit", type=int, default=CAVALRY_ARCHER)
    ap.add_argument("--map-size", type=int, default=80)
    a = ap.parse_args()
    build(a.out, count=a.count, unit=a.unit, map_size=a.map_size)


if __name__ == "__main__":
    main()
