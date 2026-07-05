"""build_immortal_test.py -- a BOUNDED arena for the UNMODIFIED Immortal AI.

The goal (user, 2026-06-29): keep Immortal's kiting (which is the best of any AI we
tried) but stop it fleeing OFF-SCREEN and getting STUCK on the arena's wall/tree edges.

Why this works WITHOUT touching Immortal (it's 115k lines of compiled bytecode):
  * Immortal's kite is a scored position search that clamps its chosen retreat point to
    the MAP edge (up-bound-precise-point ... c: 13). So a SMALL map edge bounds the kite
    on-screen automatically -- no AI edit needed.
  * It got STUCK because the production template (default3) confines units with ~566 GAIA
    boundary TREES + a 'Contain strays' trigger; Immortal's retreat-scoring jams units into
    those trees. So here we DELETE all Gaia boundary objects and disable Contain strays --
    the clean map edge is the only boundary, and there's nothing to stick on.

Result: a small, flat, obstacle-free box. Melee ball at the centre; ranged kiters next to
it; assign Immortal to the ranged player. Immortal kites the kiters around the box, bounded
to the visible area, never hitting an obstacle.

  python build_immortal_test.py --out "<scenario folder>\\ddk Immortal Bound.aoe2scenario"

TUNING: --map-size is THE knob. Smaller = tighter on-screen bound but more cramped kite;
larger = more room but more off-screen drift. Try 24 / 32 / 40 and keep the smallest size
where the kite never leaves the frame. (Default 32.)
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
from AoE2ScenarioParser.datasets.terrains import TerrainId
from AoE2ScenarioParser.datasets.trigger_lists import VictoryCondition

import build_run as BR

CAVALRY_ARCHER = 39
KNIGHT = 38
TREE_OAK = 349          # Gaia tree (blocks pathing; the classic stick hazard)
PALISADE_WALL = 72      # placed as P1 (spectator, allied) so nobody fights it
GAIA_PLAYER = 0
STOP_OBJECT, CHANGE_OBJECT_STANCE, CHANGE_VIEW = 29, 36, 16


def _trees(um, x0, y0, w, h):
    """Solid w x h Gaia tree block (impassable; obj-detectable as tree=915)."""
    for dx in range(w):
        for dy in range(h):
            um.add_unit(player=GAIA_PLAYER, unit_const=TREE_OAK,
                        x=x0 + dx + 0.5, y=y0 + dy + 0.5)


def _wall(um, pid, tiles):
    """Palisade run owned by the spectator (obj-detectable as wall=927)."""
    for x, y in tiles:
        um.add_unit(player=pid, unit_const=PALISADE_WALL, x=x + 0.5, y=y + 0.5)


def _add_obstacles(um, spectator_pid, cx, cy, layout):
    """Obstacle courses for wall/corner-handling tests. Spawn boxes stay clear
    (kiters ~x 14-19 / y 9-12, melee ~x 14-19 / y 15-18 on a 32 map); every layout
    puts something across or beside the NORTHWARD kite path so the ball must dodge
    behind / navigate around it. Coordinates are center-relative, so layouts scale
    with --map-size.

      line    -- palisade line across the kite path + tree clumps on the south flanks
      block   -- two solid tree blocks NW/NE: cover to dodge behind
      pillars -- seven 2x2 tree pillars ringing the arena: a slalom course
      choke   -- a wall spanning the map with one gap: kite must funnel through
      pocket  -- an L-wall around the NE corner: the classic trap to escape from
    """
    placed = []
    if layout == "line":
        _wall(um, spectator_pid, [(cx + i, cy - 9) for i in range(-4, 5)])
        _trees(um, cx - 7, cy + 3, 3, 2)
        _trees(um, cx + 5, cy + 3, 3, 2)
        placed = ["palisade x9 @ y=cy-9", "2 tree clumps 3x2 @ y=cy+3"]
    elif layout == "block":
        _trees(um, cx - 9, cy - 10, 4, 4)
        _trees(um, cx + 6, cy - 10, 4, 4)
        placed = ["2 solid 4x4 tree blocks NW+NE @ y=cy-10 (dodge-behind cover)"]
    elif layout == "pillars":
        for px, py in ((cx - 10, cy - 9), (cx + 8, cy - 9), (cx - 12, cy),
                       (cx + 10, cy), (cx - 8, cy + 9), (cx + 6, cy + 9),
                       (cx - 1, cy - 12)):
            _trees(um, px, py, 2, 2)
        placed = ["7 tree pillars 2x2 ringing the arena (slalom)"]
    elif layout == "choke":
        _wall(um, spectator_pid,
              [(x, cy - 8) for x in range(cx - 13, cx - 2)] +
              [(x, cy - 8) for x in range(cx + 3, cx + 13)])
        placed = ["wall across y=cy-8 with a 5-tile gap at centre (funnel)"]
    elif layout == "pocket":
        _wall(um, spectator_pid,
              [(cx + 9, y) for y in range(cy - 12, cy - 1)] +
              [(x, cy - 12) for x in range(cx + 1, cx + 9)])
        placed = ["L-wall pocket around the NE corner (trap/escape)"]
    else:
        raise SystemExit(f"unknown obstacle layout: {layout}")
    return placed


def _set_player_ai(scn, pid, ai_name):
    """Pre-pick a CUSTOM AI for a player inside the scenario file itself, exactly as the
    editor's per-player AI dropdown would: PlayerDataTwo.ai_names[pid-1] = the .per/.ai
    base name (must exist in resources/_common/ai/), ai_type[pid-1] = 0 (custom; the
    template ships 1=standard 'PromiDE' for P1 and 2=none 'NoneAi' for P2/P3). The script
    is NOT embedded -- the game loads it from the ai dir by name, so iterating on the
    .per keeps flowing into existing scenarios."""
    pd2 = scn.sections["PlayerDataTwo"]
    pd2.ai_names[pid - 1] = ai_name
    pd2.ai_type[pid - 1] = 0


def build(out_path, map_size=32, ranged_const=CAVALRY_ARCHER, melee_const=KNIGHT,
          ranged_count=12, melee_count=8, civ=None, obstacles=None, ai=None, blank=False):
    scn = AoE2DEScenario.from_file(str(BR.TEMPLATE))
    pm, um, tm, om, mm = (scn.player_manager, scn.unit_manager, scn.trigger_manager,
                          scn.option_manager, scn.map_manager)

    if map_size and map_size != mm.map_size:
        mm.map_size = map_size

    # PAINT THE ARENA: shrinking keeps the template's TOP-LEFT corner, and default3 is a
    # 60x60 jungle map whose corner holds its LAKE (203 water + beach tiles at 32x32) --
    # knights were literally standing on water. Flat uniform DIRT everywhere: no water,
    # no beach layering, no forest ground art, nothing to mistake for an obstacle.
    for t in mm.terrain:
        t.terrain_id = TerrainId.DIRT_1
        t.elevation = 0
        t.layer = -1

    cx = cy = mm.map_size // 2

    # 1) CLEAR THE BOX. Drop the two fighting armies (we re-place them) AND every Gaia
    #    object -- the ~566 boundary trees Immortal jams into. Clean grass, map edge = the
    #    only boundary.
    for u in list(um.get_player_units(BR.P_SIDE1)):
        um.remove_unit(unit=u)
    for u in list(um.get_player_units(BR.P_SIDE2)):
        um.remove_unit(unit=u)
    gaia_removed = 0
    for u in list(um.get_player_units(GAIA_PLAYER)):
        um.remove_unit(unit=u)
        gaia_removed += 1

    # 2) RANGED kiters (P2 = side 1) -- a tight block a few tiles NORTH of centre, so they
    #    open fire immediately and Immortal starts kiting them back into the box.
    #    (--blank: place NOTHING; the user paints armies in the editor and hits Test --
    #    the civ + AI assignments below still apply.)
    cols = 4
    if not blank:
        for i in range(ranged_count):
            col, row = i % cols, i // cols
            um.add_unit(player=BR.P_SIDE1, unit_const=ranged_const,
                        x=cx - 1.5 + col + 0.5, y=cy - 5 - 1.0 + row + 0.5)

        # 3) MELEE ball (P3 = side 2) AT centre -- the thing they kite around. With no AI
        #    it stands until shot, then chases; on this small map it can't be out-run, so
        #    the chase (and the kite) is continuous. (Assign an AI to P3 too if you want a
        #    harder chaser.)
        for i in range(melee_count):
            col, row = i % cols, i // cols
            um.add_unit(player=BR.P_SIDE2, unit_const=melee_const,
                        x=cx - 1.5 + col + 0.5, y=cy - 1.0 + row + 0.5)

    for pid in (BR.P_SIDE1, BR.P_SIDE2):
        next(p for p in pm.players if int(p.player_id) == pid).human = False

    # Set the KITER player's civ to the unit's owning civ: gives the unit its real stats
    # and lets Immortal's `my-unique-unit` find resolve to it (a bonus on top of the
    # class-based find in ddkTesterAI2). Harmless for generic units (any civ has them).
    if civ:
        next(p for p in pm.players if int(p.player_id) == BR.P_SIDE1).civilization = BR.civ_enum(civ)

    placed = _add_obstacles(um, BR.P_SPECTATOR, cx, cy, obstacles) if obstacles else []

    # 4) Drop the template's containment: 'Contain strays' (the trigger half of the
    #    tree-wall cage) and the Setup stop/stance pins on the fighters. Recenter the
    #    spectator camera on the new (small-map) centre so the editor opens on the box.
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
    for t in tm.triggers:
        for e in t.effects:
            if int(getattr(e, "effect_type", -1)) == CHANGE_VIEW:
                e.location_x, e.location_y = cx, cy

    om.victory_condition = VictoryCondition.CONQUEST

    if ai:
        _set_player_ai(scn, BR.P_SIDE1, ai)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd)
    os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))

    print(f"[immortal] map {mm.map_size}x{mm.map_size}, painted flat DIRT; stripped {gaia_removed} Gaia objects (the tree boundary)")
    if placed:
        print(f"[immortal] obstacles ({obstacles}): {placed}")
    if blank:
        print(f"[immortal] BLANK arena: no armies placed -- paint P2 (kiters) + P3 (melee) in the editor, then Test")
    else:
        print(f"[immortal] P2 = {ranged_count} ranged kiters north of ({cx},{cy}); P3 = {melee_count} melee AT ({cx},{cy})")
    print(f"[immortal] disabled: {disabled}")
    print(f"[immortal] kiter civ: {civ or '(template default)'}")
    print(f"[immortal] wrote {out_path}")
    if ai:
        print(f"[immortal] P2 AI pre-picked in the scenario: '{ai}' -- just load it in the editor and hit Test")
    else:
        print(f"[immortal] >>> editor: load it, assign your kite AI (e.g. ddkImmortalCoreG) to P2, Test")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--map-size", type=int, default=32, help="THE knob: smaller = tighter on-screen bound")
    ap.add_argument("--ranged", type=int, default=CAVALRY_ARCHER, help="ranged kiter unit const (default cav archer 39)")
    ap.add_argument("--melee", type=int, default=KNIGHT, help="melee chaser unit const (default knight 38)")
    ap.add_argument("--civ", default=None, help="kiter player's civ (e.g. Burmese for Arambai); enables my-unique-unit")
    ap.add_argument("--obstacles", default=None,
                    choices=["line", "block", "pillars", "choke", "pocket"],
                    help="obstacle layout for wall/corner-handling tests (see _add_obstacles)")
    ap.add_argument("--ranged-count", type=int, default=12, help="P2 army size (default 12)")
    ap.add_argument("--melee-count", type=int, default=8, help="P3 army size (default 8)")
    ap.add_argument("--ai", default=None,
                    help="pre-pick this CUSTOM AI for P2 inside the scenario (base name of a "
                         ".per/.ai pair in resources/_common/ai, e.g. ddkImmortalCoreG)")
    ap.add_argument("--blank", action="store_true",
                    help="place NO armies -- paint units in the editor; civ/AI assignments still apply")
    a = ap.parse_args()
    build(a.out, map_size=a.map_size, ranged_const=a.ranged, melee_const=a.melee, civ=a.civ,
          ranged_count=a.ranged_count, melee_count=a.melee_count,
          obstacles=a.obstacles, ai=a.ai, blank=a.blank)


if __name__ == "__main__":
    main()
