"""build_kite_test.py -- arena to test ddkKiteV1 (orbit + reload-gated volley).

P2 (computer, ddkKiteV1) = a cluster of Cavalry Archers placed NORTH of center.
P3 (computer) = a cluster of Knights at the exact center tile (40,40) -- the
orbit center the AI is hardcoded to. The cav archers should circle the knights
at ~4-tile radius and volley them when reloaded. Leave P3 with NO ai (or the
default) for the first test so the knights are a roughly-stationary target;
we'll add a chasing enemy once the kite mechanic is confirmed. Triggers that
pin/stop units are disabled.

  python build_kite_test.py --out "<scenario folder>\\ddk Kite Test.aoe2scenario"
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
KNIGHT = 38
STOP_OBJECT, CHANGE_OBJECT_STANCE = 29, 36


def build(out_path, map_size=80):
    scn = AoE2DEScenario.from_file(str(BR.TEMPLATE))
    pm, um, tm, om, mm = (scn.player_manager, scn.unit_manager, scn.trigger_manager,
                          scn.option_manager, scn.map_manager)

    if map_size and map_size != mm.map_size:
        mm.map_size = map_size

    for pid in (BR.P_SIDE1, BR.P_SIDE2):
        for u in list(um.get_player_units(pid)):
            um.remove_unit(unit=u)

    cx = cy = mm.map_size // 2          # 40 on an 80 map = the AI's hardcoded center

    # P2: 12 cavalry archers clustered NORTH of center (they orbit in)
    cols = 4
    for i in range(12):
        col, row = i % cols, i // cols
        um.add_unit(player=BR.P_SIDE1, unit_const=CAVALRY_ARCHER,
                    x=cx - 1.5 + col + 0.5, y=cy + 8 - 1.0 + row + 0.5)

    # P3: 8 knights at the center (the orbit target)
    for i in range(8):
        col, row = i % cols, i // cols
        um.add_unit(player=BR.P_SIDE2, unit_const=KNIGHT,
                    x=cx - 1.5 + col + 0.5, y=cy - 1.0 + row + 0.5)

    for pid in (BR.P_SIDE1, BR.P_SIDE2):
        next(p for p in pm.players if int(p.player_id) == pid).human = False

    disabled = []
    for t in tm.triggers:
        nm = (getattr(t, "name", "") or "").strip().lower()
        if nm == "contain strays":
            t.enabled = 0; disabled.append("Contain strays")
        if nm == "setup":
            for e in t.effects:
                if (int(getattr(e, "effect_type", -1)) in (STOP_OBJECT, CHANGE_OBJECT_STANCE)
                        and int(getattr(e, "source_player", -1) or -1) in (BR.P_SIDE1, BR.P_SIDE2)):
                    try:
                        e.enabled = 0; disabled.append(f"Setup eff{int(e.effect_type)}/sp{int(e.source_player)}")
                    except Exception:
                        pass

    om.victory_condition = VictoryCondition.CONQUEST

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd); os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))

    print(f"[kite] P2 = 12 cav archers north of ({cx},{cy}); P3 = 8 knights AT ({cx},{cy})")
    print(f"[kite] disabled: {disabled}")
    print(f"[kite] wrote {out_path}")
    print(f"[kite] >>> assign ddkKiteV1 to P2; leave P3 default/no-AI; Test")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--map-size", type=int, default=80)
    a = ap.parse_args()
    build(a.out, map_size=a.map_size)


if __name__ == "__main__":
    main()
