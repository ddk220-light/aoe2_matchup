"""build_ai_arena.py — EXPERIMENTAL AI-controlled battle scenario generator.

Unlike build_run.py (which trigger-pins two adjacent armies that stand-and-fight),
this hands each army to a COMPUTER player running the default DE AI so the engine's
Extreme-difficulty "Group Micro" can kite/hit-and-run. Based on the 2026-06-28 deep
research:
  * AI adopts PRE-PLACED units it owns (spawning gives no extra control — myth).
  * AI only attacks what it has SEEN -> giant map-revealer on each enemy army.
  * AI goes passive / resigns without an economy -> hidden TC + villagers + resources
    in a corner, Victory = Conquest.
  * Trigger-tasking (Task Object) FIGHTS the AI's micro -> 'Contain strays' disabled,
    Setup's Stop/Stance on the armies disabled.
  * Kiting itself is an ENGINE feature gated to Extreme difficulty -> the launcher must
    pick Extreme in the editor Test menu (NOT stored in the scenario file).
  * Barbarian AI is NOT used: it can't run DE civs (Mapuche/Lithuanians) or reach Extreme.

  python build_ai_arena.py --side1 Mapuche:elite_bolas_rider:"Elite Bolas Rider" \
      --side2 Lithuanians:elite_leitis:"Elite Leitis" \
      --out templates/ai_arena_bolas_vs_leitis.aoe2scenario
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

# --- eco / vision object constants (from the dataset, verified 2026-06-28) ---
TOWN_CENTER, HOUSE, FARM, MILL = 109, 70, 50, 68
VILLAGER = 83
MAP_REVEALER_GIANT = 1775
FORAGE_BUSH, GOLD_MINE = 59, 66

# hidden eco-base centers (opposite, near-empty corners on the 60x60 map)
BASE_NW = (6, 6)     # P2 (side 1)
BASE_SE = (53, 53)   # P3 (side 2)

# effect type ids
STOP_OBJECT, CHANGE_OBJECT_STANCE = 29, 36


def _player(pm, pid):
    return next(p for p in pm.players if int(p.player_id) == pid)


def _clear_and_grass(um, mm, cx, cy, half=4):
    """Remove GAIA props and flatten terrain to grass in a box so the eco base fits."""
    for u in list(um.get_player_units(0)):
        if abs(u.x - cx) <= half and abs(u.y - cy) <= half:
            um.remove_unit(unit=u)
    for x in range(cx - half, cx + half + 1):
        for y in range(cy - half, cy + half + 1):
            if 0 <= x < mm.map_width and 0 <= y < mm.map_height:
                try:
                    mm.get_tile(x, y).terrain_id = 0   # grass
                except Exception:
                    pass


def _build_eco_base(um, mm, pid, center):
    """A real (but tucked-away) base so the AI stays alive + active and won't resign:
    Town Center + 4 villagers + 2 houses, plus gaia resources next to it to gather."""
    cx, cy = center
    _clear_and_grass(um, mm, cx, cy, half=4)
    um.add_unit(player=pid, unit_const=TOWN_CENTER, x=cx + 0.5, y=cy + 0.5)
    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
        um.add_unit(player=pid, unit_const=VILLAGER, x=cx + dx + 0.5, y=cy + dy + 0.5)
    um.add_unit(player=pid, unit_const=HOUSE, x=cx - 3.5, y=cy + 0.5)
    um.add_unit(player=pid, unit_const=HOUSE, x=cx + 3.5, y=cy + 0.5)
    # gaia resources for the villagers to work (keeps the AI "functioning")
    for dx, dy in [(-4, 0), (0, -4), (0, 4)]:
        um.add_unit(player=0, unit_const=FORAGE_BUSH, x=cx + dx + 0.5, y=cy + dy + 0.5)
    um.add_unit(player=0, unit_const=GOLD_MINE, x=cx + 4.5, y=cy + 0.5)


def make_ai_arena(side1, side2, out_path, counts=(30, 30), ranged=(True, False),
                  map_size=120):
    civ1, key1, label1 = side1
    civ2, key2, label2 = side2
    new1, new2 = BR.unit_const(key1), BR.unit_const(key2)

    # 1) base matchup via the tested builder (units swapped, triggers retargeted, camera)
    fd, base_tmp = tempfile.mkstemp(suffix=".aoe2scenario")
    os.close(fd); os.unlink(base_tmp)
    BR.build_run(side1, side2, base_tmp, counts=counts, ranged=ranged)

    # 2) layer the AI control changes on top
    scn = AoE2DEScenario.from_file(base_tmp)
    pm, um, tm, om, mm = (scn.player_manager, scn.unit_manager, scn.trigger_manager,
                          scn.option_manager, scn.map_manager)

    # GROW THE MAP to a standard size (Tiny=120) so the engine sets a map-size symbol
    # (TINY-MAP). Size-gated community AIs (Rehoboam, Illuminati) define HALF-MAP-SIZE /
    # FISHFACE etc. only inside #load-if-defined <SIZE>-MAP blocks; on the original 60x60
    # arena NO bucket matched -> those consts stayed undefined -> ERR2005 invalid
    # identifier at first use. The arena content stays put in the (0..60) quadrant; the
    # tree boundary (not the map edge) keeps it enclosed.
    if map_size and map_size != mm.map_size:
        prev = mm.map_size
        mm.map_size = map_size
        print(f"[ai_arena] map resized {prev}x{prev} -> {map_size}x{map_size} "
              f"(Tiny) so size-gated AIs (Rehoboam/Illuminati) load")

    # both fighting players -> COMPUTER (default DE AI); give resources + pop headroom
    for pid in (BR.P_SIDE1, BR.P_SIDE2):
        p = _player(pm, pid)
        p.human = False
        p.food, p.wood, p.gold, p.stone = 1500, 1500, 800, 800
        try:
            p.population_cap = max(int(getattr(p, "population_cap", 0) or 0), 200)
        except Exception:
            pass

    # hidden eco bases in opposite corners
    _build_eco_base(um, mm, BR.P_SIDE1, BASE_NW)
    _build_eco_base(um, mm, BR.P_SIDE2, BASE_SE)

    # vision: a giant map-revealer for each AI placed over the ENEMY army centroid
    c1 = BR._army_centroid(um, BR.P_SIDE1, new1)
    c2 = BR._army_centroid(um, BR.P_SIDE2, new2)
    if c1 and c2:
        um.add_unit(player=BR.P_SIDE1, unit_const=MAP_REVEALER_GIANT, x=c2[0], y=c2[1])
        um.add_unit(player=BR.P_SIDE2, unit_const=MAP_REVEALER_GIANT, x=c1[0], y=c1[1])

    # disable triggers/effects that FIGHT AI micro
    disabled = []
    for t in tm.triggers:
        nm = (getattr(t, "name", "") or "")
        if nm.strip().lower() == "contain strays":
            t.enabled = 0
            disabled.append("Contain strays (Task Object pins)")
        if nm.strip().lower() == "setup":
            for e in t.effects:
                if (int(e.effect_type) in (STOP_OBJECT, CHANGE_OBJECT_STANCE)
                        and int(getattr(e, "source_player", -1) or -1) in (BR.P_SIDE1, BR.P_SIDE2)):
                    try:
                        e.enabled = 0
                        disabled.append(f"Setup eff type{int(e.effect_type)} sp{int(e.source_player)}")
                    except Exception:
                        pass

    # anti-resign
    om.victory_condition = VictoryCondition.CONQUEST

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd); os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))
    try:
        os.unlink(base_tmp)
    except OSError:
        pass

    print(f"[ai_arena] {label1} ({civ1}) x{counts[0]}  vs  {label2} ({civ2}) x{counts[1]}")
    print(f"[ai_arena] P2/P3 -> Computer (default AI); resources 1500/1500/800/800; Victory=Conquest")
    print(f"[ai_arena] eco bases @ {BASE_NW} (P2) & {BASE_SE} (P3); giant revealers on enemy armies")
    print(f"[ai_arena] disabled: {disabled}")
    print(f"[ai_arena] wrote {out_path}")
    print(f"[ai_arena] >>> in the editor, set Test difficulty = EXTREME (kiting is Extreme-only)")
    return out_path


def _parse_side(s):
    civ, key, label = s.split(":", 2)
    return civ.strip(), key.strip(), label.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side1", required=True, type=_parse_side)
    ap.add_argument("--side2", required=True, type=_parse_side)
    ap.add_argument("--out", required=True)
    ap.add_argument("--r1", type=int, default=1, help="side1 ranged? (1/0)")
    ap.add_argument("--r2", type=int, default=0, help="side2 ranged? (1/0)")
    ap.add_argument("--map-size", type=int, default=120,
                    help="square map size; 120=Tiny (needed so size-gated AIs load)")
    a = ap.parse_args()
    make_ai_arena(a.side1, a.side2, a.out, ranged=(bool(a.r1), bool(a.r2)),
                  map_size=a.map_size)


if __name__ == "__main__":
    main()
