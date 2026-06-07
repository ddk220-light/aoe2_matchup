"""
make_scenario.py — parameterized AoE2:DE matchup-arena scenario generator.

Produces a `.aoe2scenario` for a 1-army-vs-1-army test fight inside a walled
arena, with triggers that make the pipeline (run -> record -> read results)
work cleanly. One `MatchupSpec` -> one scenario file.

Design (agreed with user):
  * Centered square stone-walled arena (Gaia-owned walls so they block movement
    but never count toward either player's "alive" status and are never attacked).
  * Both armies in a grid formation at opposite ends; one Scout Cavalry per player
    parked OUTSIDE the arena so an AI uses the scout to explore instead of peeling
    a test unit off the line. The scout is a different unit type, so it never
    affects the win/loss check.
  * Triggers (tiered):
      CORE        - "P<n> defeated" when that player owns 0 of its TEST unit type
                    (scout ignored) -> declare victory for the opponent -> the game
                    ends to the post-game stats screen.
      RECOMMENDED - force-engage (attack-move both armies to center at t=0),
                    exact survivor readout (count_units_into_variable +
                    display_instructions), timeout anti-hang, scout safety
                    (no-attack stance).
      CINEMATIC   - camera framed on the arena, a matchup title card, and a
                    3-2-1 countdown freeze before the charge.

NOTES / KNOWN REFINEMENTS:
  * `research_upgrades` researches a universal combat-tech set per player with
    force=0 (only applies techs the civ actually has). The *precise* per-civ tech
    list could later be sourced from webapp/aoe2_reference.db for exactness.
  * The on-screen survivor readout embeds variables in the message using the
    `<variable_name>` token; whether DE substitutes it must be verified in-game.
    Regardless, the post-game stats screen (Military Units Killed) is the reliable
    fallback number source.

Run as a script to emit the Fire Archer vs Jian demo:
    PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python make_scenario.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.players import PlayerId
from AoE2ScenarioParser.datasets.object_support import Civilization, StartingAge
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.trigger_lists import (
    AttackStance,
    DiplomacyState,
    Operation,
    PanelLocation,
    Comparison,
    VisibilityState,
)

SCOUT_CONST = UnitInfo.SCOUT_CAVALRY.ID  # 448

WALL_TYPES = {
    "stone": BuildingInfo.STONE_WALL.ID,        # 117
    "fortified": BuildingInfo.FORTIFIED_WALL.ID,  # 155
    "palisade": BuildingInfo.PALISADE_WALL.ID,    # 72
    "fort": BuildingInfo.FORT_WALL.ID,            # 2678 (heavy decorative wall)
}


def _tid(tech: TechInfo) -> int:
    """TechInfo.value is (tech_id, effect_id); research_technology wants tech_id."""
    v = tech.value
    return v[0] if isinstance(v, (tuple, list)) else v


# Universal fully-upgraded combat tech set (blacksmith + university + stable/eco
# combat). force=0 means a civ only gets the ones it actually has.
FULL_UPGRADE_TECHS: List[int] = [_tid(t) for t in (
    TechInfo.FORGING, TechInfo.IRON_CASTING, TechInfo.BLAST_FURNACE,        # melee atk
    TechInfo.SCALE_MAIL_ARMOR, TechInfo.CHAIN_MAIL_ARMOR, TechInfo.PLATE_MAIL_ARMOR,  # inf/cav melee armor
    TechInfo.SCALE_BARDING_ARMOR, TechInfo.CHAIN_BARDING_ARMOR, TechInfo.PLATE_BARDING_ARMOR,  # cav armor
    TechInfo.FLETCHING, TechInfo.BODKIN_ARROW, TechInfo.BRACER,             # archer atk/range
    TechInfo.PADDED_ARCHER_ARMOR, TechInfo.LEATHER_ARCHER_ARMOR, TechInfo.RING_ARCHER_ARMOR,  # archer armor
    TechInfo.BALLISTICS, TechInfo.CHEMISTRY,                                # accuracy / +1 missile
    TechInfo.SQUIRES, TechInfo.BLOODLINES, TechInfo.HUSBANDRY,              # inf speed / cav hp+speed
)]


@dataclass
class Army:
    unit_const: int            # UnitInfo/.ID of the test unit (e.g. UnitInfo.ELITE_FIRE_ARCHER.ID)
    civ: Civilization          # Civilization.WU etc.
    count: int = 30
    label: str = "Army"        # display name for the title card / readout


@dataclass
class MatchupSpec:
    army1: Army
    army2: Army
    # arena / map
    arena_size: int = 40       # inner side length in tiles ("large ~40x40")
    map_size: int = 80         # square map dimension
    wall_type: str = "stone"
    formation_spacing: float = 1.0
    army_gap: int = 24         # tiles between the two formation centers
    # setup
    scouts: bool = True
    research_upgrades: bool = True
    starting_age: int = int(StartingAge.POST_IMPERIAL_AGE)  # 6
    # trigger tiers
    force_engage: bool = True
    survivor_readout: bool = True
    live_readout: bool = True        # looping on-screen count (so OCR can read it live)
    timeout_seconds: int = 180
    scout_safety: bool = True
    cinematic: bool = True
    countdown_seconds: int = 3
    # output
    output_name: str = "matchup"
    # scenario file FORMAT version. None -> AoE2ScenarioParser's latest (1.58, current
    # Windows DE). The Feral macOS port lags one patch (1.57); AoE2:DE refuses to load a
    # scenario whose format is NEWER than the game ("There seems to be a problem with
    # scenario ..."), so on Mac this must match the installed game (currently "1.57").
    scenario_version: "str | None" = None


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #
def _grid_positions(count: int, cx: float, cy: float, spacing: float) -> List[Tuple[float, float]]:
    """Lay `count` units in a centered ~square grid around (cx, cy)."""
    cols = max(1, int(math.ceil(math.sqrt(count))))
    rows = int(math.ceil(count / cols))
    w = (cols - 1) * spacing
    h = (rows - 1) * spacing
    x0 = cx - w / 2.0
    y0 = cy - h / 2.0
    pts = []
    for i in range(count):
        r, c = divmod(i, cols)
        pts.append((x0 + c * spacing, y0 + r * spacing))
    return pts


def _wall_perimeter(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[float, float]]:
    """Tile centers along the rectangle perimeter [x0,x1] x [y0,y1]."""
    pts = set()
    for x in range(x0, x1 + 1):
        pts.add((x, y0)); pts.add((x, y1))
    for y in range(y0, y1 + 1):
        pts.add((x0, y)); pts.add((x1, y))
    return [(x + 0.5, y + 0.5) for (x, y) in sorted(pts)]


# --------------------------------------------------------------------------- #
# builder
# --------------------------------------------------------------------------- #
def build_matchup_scenario(spec: MatchupSpec, out_dir: str | Path = ".") -> Path:
    scn = AoE2DEScenario.from_default(spec.scenario_version)

    pm = scn.player_manager
    um = scn.unit_manager
    tm = scn.trigger_manager

    # --- players -----------------------------------------------------------
    def player(pid):
        return next(p for p in pm.players if p.player_id == pid)

    # AI-vs-AI + spectator: army1 -> Player 2 (AI), army2 -> Player 3 (AI),
    # Player 1 = human spectator allied to both (just watches/records).
    pm.active_players = 3  # P1 spectator + P2 + P3 (Gaia is separate)
    p1, p2, p3 = player(1), player(2), player(3)
    p2.civilization = spec.army1.civ
    p3.civilization = spec.army2.civ
    for p in (p1, p2, p3):
        p.starting_age = spec.starting_age
    ALLY, ENEMY = int(DiplomacyState.ALLY), int(DiplomacyState.ENEMY)
    p1.diplomacy[2] = ALLY; p1.diplomacy[3] = ALLY      # spectator allied to both
    p2.diplomacy[1] = ALLY; p2.diplomacy[3] = ENEMY     # fighters: ally spectator, fight each other
    p3.diplomacy[1] = ALLY; p3.diplomacy[2] = ENEMY

    # --- arena geometry ----------------------------------------------------
    cx = cy = spec.map_size // 2
    half = spec.arena_size // 2
    ax0, ay0, ax1, ay1 = cx - half, cy - half, cx + half, cy + half  # inclusive tile box
    arena_area = dict(area_x1=ax0, area_y1=ay0, area_x2=ax1, area_y2=ay1)

    # --- walls owned by the spectator (P1) -------------------------------
    # P1 owning the walls keeps the spectator alive (has objects) and, since P1
    # is allied to both fighters, the walls are never attacked; they still block
    # movement to contain the fight.
    wall_const = WALL_TYPES.get(spec.wall_type, WALL_TYPES["stone"])
    for (wx, wy) in _wall_perimeter(ax0, ay0, ax1, ay1):
        um.add_unit(player=1, unit_const=wall_const, x=wx, y=wy)

    # --- keep-alive object for the spectator (P1) -------------------------
    # CRITICAL: AoE2 does NOT count walls toward a player's "has objects"
    # status, so a P1 owning ONLY walls is declared defeated the instant the
    # test starts -> "You have been defeated!" before the armies ever engage.
    # Give P1 one real, immobile building in a far corner so the spectator
    # stays alive for the whole fight. P1 is allied to both armies (never
    # attacked); a Town Center is a different object type than the test units,
    # so it never affects the "army wiped -> other wins" survivor checks.
    um.add_unit(player=1, unit_const=BuildingInfo.TOWN_CENTER.ID,
                x=ax0 - 6 + 0.5, y=ay1 + 6 + 0.5)

    # --- armies (army1 -> P2, army2 -> P3) --------------------------------
    gap = spec.army_gap / 2.0
    a1_center = (cx, cy - gap)   # army1 toward top (lower y)
    a2_center = (cx, cy + gap)   # army2 toward bottom (higher y)
    for (px, py) in _grid_positions(spec.army1.count, *a1_center, spec.formation_spacing):
        um.add_unit(player=2, unit_const=spec.army1.unit_const, x=px + 0.5, y=py + 0.5)
    for (px, py) in _grid_positions(spec.army2.count, *a2_center, spec.formation_spacing):
        um.add_unit(player=3, unit_const=spec.army2.unit_const, x=px + 0.5, y=py + 0.5)

    # --- scouts outside the arena (one per AI so it scouts with the scout,
    #     not a test unit) -------------------------------------------------
    if spec.scouts:
        um.add_unit(player=2, unit_const=SCOUT_CONST, x=ax0 - 8 + 0.5, y=ay0 - 8 + 0.5)
        um.add_unit(player=3, unit_const=SCOUT_CONST, x=ax1 + 8 + 0.5, y=ay1 + 8 + 0.5)

    # ----------------------------------------------------------------------
    #  TRIGGERS  (army1 on P2, army2 on P3; P1 = spectator)
    # ----------------------------------------------------------------------
    a1c, a2c = spec.army1.unit_const, spec.army2.unit_const
    FIGHTERS = ((2, a1c), (3, a2c))  # (player_id, test-unit const)

    # SETUP trigger (runs on load): camera (spectator P1), title, upgrades, scout stance
    setup = tm.add_trigger("Setup", enabled=True, looping=False)
    # Force diplomacy at runtime. The scenario player-diplomacy fields don't reliably apply
    # to HU players in Test mode, so the armies were treating P1's allied walls as ENEMY and
    # attacking them instead of each other. P1 (spectator + wall/TC owner) is MUTUALLY allied
    # to both fighters; P2 vs P3 are mutual enemies. mutual_diplomacy=True sets BOTH sides.
    setup.new_effect.change_diplomacy(source_player=1, target_player=2, diplomacy=ALLY, mutual_diplomacy=True)
    setup.new_effect.change_diplomacy(source_player=1, target_player=3, diplomacy=ALLY, mutual_diplomacy=True)
    setup.new_effect.change_diplomacy(source_player=2, target_player=3, diplomacy=ENEMY, mutual_diplomacy=True)
    # Reveal the whole arena to the spectator (P1) so the recording/OCR isn't fogged.
    for _fpid in (2, 3):
        setup.new_effect.set_player_visibility(
            source_player=1, target_player=_fpid, visibility_state=int(VisibilityState.VISIBLE))
    if spec.cinematic:
        setup.new_effect.change_view(source_player=1, location_x=cx, location_y=cy)
        title = f"{spec.army1.count} {spec.army1.label}  VS  {spec.army2.count} {spec.army2.label}"
        setup.new_effect.display_instructions(
            source_player=0, message=title, display_time=8,
            instruction_panel_position=int(PanelLocation.TOP),
        )
    if spec.research_upgrades:
        for pid, _ in FIGHTERS:
            for tech_id in FULL_UPGRADE_TECHS:
                setup.new_effect.research_technology(
                    source_player=pid, technology=tech_id, force_research_technology=0)
    if spec.scout_safety and spec.scouts:
        for pid, _ in FIGHTERS:
            setup.new_effect.change_object_stance(
                source_player=pid, object_list_unit_id=SCOUT_CONST,
                attack_stance=int(AttackStance.NO_ATTACK_STANCE))

    # OPTIONAL 3-2-1 countdown: freeze the armies, then release + force-engage
    engage_delay = spec.countdown_seconds if spec.cinematic else 0
    if spec.cinematic and engage_delay > 0:
        for pid, uc in FIGHTERS:
            setup.new_effect.stop_object(source_player=pid, object_list_unit_id=uc)
        for n in range(engage_delay, 0, -1):
            cd = tm.add_trigger(f"Countdown {n}", enabled=True, looping=False)
            cd.new_condition.timer(timer=engage_delay - n + 1)
            cd.new_effect.display_instructions(
                source_player=0, message=str(n), display_time=1,
                instruction_panel_position=int(PanelLocation.MIDDLE))

    # RECOMMENDED: force-engage. PATROL each army INTO the OTHER army's start position so
    # they cross the arena and collide in the middle. Patrol is more reliable than attack-move
    # to a single point (which can stall, or — pre-diplomacy-fix — target the nearest object).
    # P2 (owns a1c) patrols to where P3/a2 sits; P3 (owns a2c) patrols to where P2/a1 sits.
    if spec.force_engage:
        eng = tm.add_trigger("Engage", enabled=True, looping=False)
        if engage_delay:
            eng.new_condition.timer(timer=engage_delay + 1)
        eng.new_effect.patrol(source_player=2, object_list_unit_id=a1c,
                              location_x=int(round(a2_center[0])), location_y=int(round(a2_center[1])))
        eng.new_effect.patrol(source_player=3, object_list_unit_id=a2c,
                              location_x=int(round(a1_center[0])), location_y=int(round(a1_center[1])))

    # RECOMMENDED: exact survivor readout variables (var0=army1/P2, var1=army2/P3)
    if spec.survivor_readout:
        tm.add_variable("p2_left", 0)
        tm.add_variable("p3_left", 1)

    def emit_result(trig, headline: str):
        """Count survivors of each side into vars and display them."""
        if spec.survivor_readout:
            trig.new_effect.count_units_into_variable(
                source_player=2, object_list_unit_id=a1c, variable2=0, **arena_area)
            trig.new_effect.count_units_into_variable(
                source_player=3, object_list_unit_id=a2c, variable2=1, **arena_area)
            trig.new_effect.display_instructions(
                source_player=0, display_time=30,
                instruction_panel_position=int(PanelLocation.TOP),
                message=f"{headline}  |  {spec.army1.label}: <p2_left>   {spec.army2.label}: <p3_left>")

    # RECOMMENDED: live on-screen readout (looping every 1s) for the OCR extractor.
    if spec.live_readout and spec.survivor_readout:
        live = tm.add_trigger("Live readout", enabled=True, looping=True)
        live.new_condition.timer(timer=1)
        live.new_effect.count_units_into_variable(
            source_player=2, object_list_unit_id=a1c, variable2=0, **arena_area)
        live.new_effect.count_units_into_variable(
            source_player=3, object_list_unit_id=a2c, variable2=1, **arena_area)
        live.new_effect.display_instructions(
            source_player=0, display_time=2,
            instruction_panel_position=int(PanelLocation.TOP),
            message=f"{spec.army1.label}: <p2_left>   vs   {spec.army2.label}: <p3_left>")

    # CORE: when one AI's army is wiped, the OTHER AI is declared winner & the game
    # ends. P1 (spectator, allied to both) sees the result, never "You are defeated".
    t_p2_dead = tm.add_trigger("Army1 (P2) wiped -> P3 wins", enabled=True, looping=False)
    t_p2_dead.new_condition.own_fewer_objects(source_player=2, object_list=a1c, quantity=1)
    emit_result(t_p2_dead, f"{spec.army2.label} WIN")
    t_p2_dead.new_effect.declare_victory(source_player=3, enabled=1)

    t_p3_dead = tm.add_trigger("Army2 (P3) wiped -> P2 wins", enabled=True, looping=False)
    t_p3_dead.new_condition.own_fewer_objects(source_player=3, object_list=a2c, quantity=1)
    emit_result(t_p3_dead, f"{spec.army1.label} WIN")
    t_p3_dead.new_effect.declare_victory(source_player=2, enabled=1)

    # RECOMMENDED: timeout anti-hang -> tally 1s early, then decide by survivor count
    if spec.timeout_seconds:
        if spec.survivor_readout:
            tally = tm.add_trigger("Timeout tally", enabled=True, looping=False)
            tally.new_condition.timer(timer=max(1, spec.timeout_seconds - 1))
            emit_result(tally, "TIMEOUT")
            tw1 = tm.add_trigger("Timeout: P2 wins", enabled=True, looping=False)
            tw1.new_condition.timer(timer=spec.timeout_seconds)
            tw1.new_condition.compare_variables(
                variable=0, comparison=int(Comparison.LARGER_OR_EQUAL), variable2=1)
            tw1.new_effect.declare_victory(source_player=2, enabled=1)
            tw2 = tm.add_trigger("Timeout: P3 wins", enabled=True, looping=False)
            tw2.new_condition.timer(timer=spec.timeout_seconds)
            tw2.new_condition.compare_variables(
                variable=1, comparison=int(Comparison.LARGER), variable2=0)
            tw2.new_effect.declare_victory(source_player=3, enabled=1)
        else:
            t_to = tm.add_trigger("Timeout", enabled=True, looping=False)
            t_to.new_condition.timer(timer=spec.timeout_seconds)
            t_to.new_effect.declare_victory(source_player=2, enabled=1)

    # --- write -------------------------------------------------------------
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec.output_name}.aoe2scenario"
    scn.write_to_file(str(out_path))
    return out_path


# --------------------------------------------------------------------------- #
# demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    spec = MatchupSpec(
        army1=Army(UnitInfo.ELITE_FIRE_ARCHER.ID, Civilization.WU, 30, "Elite Fire Archer"),
        army2=Army(UnitInfo.JIAN_SWORDSMAN.ID, Civilization.WU, 30, "Jian Swordsman"),
        output_name="TEMPLATE_firearcher_vs_jian",
        scenario_version="1.57",  # Feral macOS port is on 1.57 (Windows DE is 1.58)
    )
    path = build_matchup_scenario(spec, out_dir=".")
    print(f"WROTE {path}")
