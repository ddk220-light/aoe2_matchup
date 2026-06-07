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
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.terrains import TerrainId
from AoE2ScenarioParser.datasets.other import OtherInfo
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
    # boundary style: "wall" (stone/fortified perimeter — proven containment for real
    # matchups) or "natural" (no walls; a solid Gaia treeline on the arena perimeter
    # contains the fight, backed by tents + destroyed buildings for a battlefield look).
    boundary: str = "wall"
    # paint a shallow river band across the TOP of the map (cosmetic).
    river_top: bool = False
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
    # cosmetic map decoration: "none" | "meso_jungle" | "meso_ruins" | "meso_river"
    # (Central/South-American themed terrain + Gaia eye-candy around the arena).
    theme: str = "none"
    decor_seed: int = 7
    # showcase mode: armies are mutually ALLIED (never fight) so the decorated map
    # can be viewed/screenshotted statically without the match ending in a defeat screen.
    peaceful: bool = False


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
# Central-American themed map decoration (cosmetic; fight interior stays clear)
# --------------------------------------------------------------------------- #
_THEMES = {
    "meso_jungle": {  # lush Maya rainforest clearing
        "ground": TerrainId.GRASS_JUNGLE,
        "accents": [TerrainId.GRASS_JUNGLE_RAINFOREST, TerrainId.GRASS_FLOWERS_1, TerrainId.UNDERBRUSH_JUNGLE],
        "forest": TerrainId.FOREST_RAINFOREST,
        "trees": [OtherInfo.TREE_RAINFOREST, OtherInfo.TREE_JUNGLE, OtherInfo.TREE_PALM_FOREST],
        "structures": [OtherInfo.TEMPLE_RUIN, OtherInfo.ANDEAN_RUINS, OtherInfo.ROCK_JUNGLE, OtherInfo.ROCK_LIMESTONE],
        "plants": [OtherInfo.PLANT_RAINFOREST, OtherInfo.PLANT_UNDERBRUSH_TROPICAL, OtherInfo.PINEAPPLE_BUSH, OtherInfo.FERN_PATCH, OtherInfo.FLOWERS_1],
        "animals": [UnitInfo.MACAW, UnitInfo.JAGUAR, UnitInfo.MONKEY, UnitInfo.TAPIR],
        "n_trees": 100, "n_struct": 10, "n_plants": 80, "n_animals": 8, "n_battle": 20, "water": False,
    },
    "meso_ruins": {  # open stone-ruins plaza
        "ground": TerrainId.GRASS_JUNGLE,
        "accents": [TerrainId.DIRT_3, TerrainId.DIRT_SAVANNAH, TerrainId.GRASS_FLOWERS_2],
        "forest": TerrainId.FOREST_PALM_GRASS,
        "trees": [OtherInfo.TREE_PALM_FOREST, OtherInfo.TREE_BRAZILWOOD, OtherInfo.TREE_WAX_PALM, OtherInfo.PAPAYA_TREE],
        "structures": [OtherInfo.PURU_RUINS, OtherInfo.ANDEAN_RUINS, OtherInfo.TEMPLE_RUIN, OtherInfo.STATUE_LEFT, OtherInfo.STATUE_RIGHT, OtherInfo.ROCK_LIMESTONE, OtherInfo.ROCK_PILLAR],
        "plants": [OtherInfo.FLOWERS_2, OtherInfo.FERN_PATCH, OtherInfo.PINEAPPLE_BUSH, OtherInfo.PLANT_JUNGLE],
        "animals": [OtherInfo.HOWLER_MONKEY, UnitInfo.MACAW, UnitInfo.TURKEY, UnitInfo.DEER, UnitInfo.LLAMA_A],
        "n_trees": 60, "n_struct": 26, "n_plants": 65, "n_animals": 9, "n_battle": 26, "water": False,
    },
    "meso_river": {  # jungle with a riverside/water feature
        "ground": TerrainId.GRASS_JUNGLE,
        "accents": [TerrainId.GRASS_JUNGLE_RAINFOREST, TerrainId.GRASS_FLOWERS_1],
        "forest": TerrainId.FOREST_MANGROVE,
        "trees": [OtherInfo.TREE_MANGROVE, OtherInfo.TREE_RAINFOREST, OtherInfo.TREE_PALM_FOREST, OtherInfo.PAPAYA_TREE],
        "structures": [OtherInfo.ANDEAN_RUINS, OtherInfo.TEMPLE_RUIN, OtherInfo.ROCK_LIMESTONE],
        "plants": [OtherInfo.PLANT_RAINFOREST, OtherInfo.FERN_PATCH, OtherInfo.FLOWERS_1, OtherInfo.PINEAPPLE_BUSH],
        "animals": [UnitInfo.MACAW, UnitInfo.CAPYBARA, UnitInfo.CONDOR, UnitInfo.JAGUAR],
        "n_trees": 85, "n_struct": 10, "n_plants": 72, "n_animals": 10, "n_battle": 20, "water": True,
    },
}


# battlefield-aftermath eye-candy shared across themes (bones, fires, dead wood)
_BATTLE = [OtherInfo.SKELETON, OtherInfo.SKELETON_ANTIQUITY_SOLDIER,
           OtherInfo.SKELETON_ANTIQUITY_CIVILIAN, OtherInfo.ANIMAL_SKELETON,
           OtherInfo.BONFIRE, OtherInfo.TORCH_A, OtherInfo.TREE_DEAD,
           OtherInfo.STUMP, OtherInfo.FELLED_TREE]

# "tents" / encampment props (no literal tent object exists in the dataset; these
# canopy/camp props read as a war camp lining the boundary).
_TENTS = [OtherInfo.MARKET_STALL, OtherInfo.ASIAN_MARKET_STALLS, OtherInfo.GARDEN_PAVILION,
          OtherInfo.SIEGE_CAMP_EQUIPMENT, OtherInfo.SIEGE_CAMP_WEAPONS, OtherInfo.SIEGE_PROPS]

# destroyed / ruined buildings for the boundary (clearly "destroyed" + a couple of
# meso ruins so it stays on-theme).
_DESTROYED = [OtherInfo.BURNED_BUILDING_A, OtherInfo.BURNED_BUILDING_B, OtherInfo.BURNED_BUILDING_C,
              OtherInfo.RUBBLE_2_X_2, OtherInfo.RUBBLE_3_X_3, OtherInfo.RUBBLE_4_X_4,
              OtherInfo.TEMPLE_RUIN, OtherInfo.ANDEAN_RUINS]


def _decorate_meso(scn, spec, cx, cy, ax0, ay0, ax1, ay1):
    """Paint themed terrain + scatter Gaia eye-candy around the arena.
    Cosmetic only: the fight interior stays clear and gaia objects are a different
    unit type than the test units, so win-detection is unaffected. With
    ``spec.boundary == "natural"`` a solid Gaia treeline on the arena perimeter
    physically contains the fight (replacing the walls), backed by tents + destroyed
    buildings; with a river band optionally painted across the top of the map."""
    cfg = _THEMES.get(spec.theme)
    if cfg is None:
        return
    mm, um = scn.map_manager, scn.unit_manager
    rng = random.Random(spec.decor_seed)
    N = spec.map_size
    # geometry-adaptive bands (tuned to scale from the old 80/40 layout down to a
    # tiny map with a half-size arena).
    margin = ax0                              # tiles from map edge to the arena
    EDGE = max(3, min(6, margin // 4))        # forest backdrop band at the map rim
    OUT = max(5, margin - EDGE - 1)           # decorate band outside the arena
    arena_half = (ax1 - ax0) // 2
    FIGHT_CLEAR = max(2, arena_half - 4)      # keep the central combat lane empty
    area_scale = (N * N) / (80.0 * 80.0)      # scale object counts to map area
    ground = int(cfg["ground"])
    forest = int(cfg["forest"])
    accents = [int(t) for t in cfg["accents"]]

    def in_arena(x, y):                       # arena (+1 ring): keep clear
        return (ax0 - 1) <= x <= (ax1 + 1) and (ay0 - 1) <= y <= (ay1 + 1)

    reserved = [(ax0 - 6, ay1 + 6), (ax0 - 8, ay0 - 8), (ax1 + 8, ay1 + 8)]  # TC + scouts
    def reserved_near(x, y, r=3):
        return any(abs(x - rx) < r and abs(y - ry) < r for rx, ry in reserved)

    # river: forms the NORTH EDGE of the arena itself — the fight is bounded by water
    # on the top side (water blocks land units, so it contains them like the treeline
    # does on the other three sides). Only the arena center is recorded, so this sits
    # right at the visible top of frame. Jagged south (fight-facing) bank.
    water = set()
    if spec.river_top or cfg.get("water"):
        depth = 6                                     # rows of water at the arena's north edge
        for x in range(0, N):
            jag = rng.randint(0, 1)                   # ragged shoreline toward the fight
            for y in range(ay0 - depth, ay0 + 1 - jag):
                if 0 <= y < N and not reserved_near(x, y):
                    water.add((x, y))

    # 1) terrain: jungle base everywhere; forest backdrop at the rim; scattered
    #    accent patches in the clearing; river band (if any).
    for tile in mm.terrain:
        x, y = tile.x, tile.y
        if (x, y) in water:
            tile.terrain_id = int(TerrainId.WATER_AZURE)
        elif (x < EDGE or x > N - 1 - EDGE or y < EDGE or y > N - 1 - EDGE) and not in_arena(x, y):
            tile.terrain_id = forest
        else:
            tile.terrain_id = ground
            if not in_arena(x, y) and rng.random() < 0.12:
                tile.terrain_id = rng.choice(accents)
    if water:                                  # sandy shore along the river's banks
        for (x, y) in list(water):
            ny = y + 1                          # fight-facing (south) bank — the shoreline
            if 0 <= ny < N and (x, ny) not in water:
                mm.get_tile(x, ny).terrain_id = int(TerrainId.BEACH)
            for dx in (-1, 0, 1):               # natural shore on the outer (unseen) sides
                for dy in (-1, 0, 1):
                    nx, nyy = x + dx, y + dy
                    if 0 <= nx < N and 0 <= nyy < N and (nx, nyy) not in water and not in_arena(nx, nyy):
                        mm.get_tile(nx, nyy).terrain_id = int(TerrainId.BEACH)

    def on_perimeter(x, y):
        return (x in (ax0, ax1) and ay0 <= y <= ay1) or (y in (ay0, ay1) and ax0 <= x <= ax1)

    # 2) NATURAL BOUNDARY (replaces stone walls): a solid Gaia treeline on the arena
    #    perimeter (trees block movement -> contains the fight), backed by an outer
    #    band of tents + destroyed buildings for a battlefield-camp look.
    if spec.boundary == "natural":
        tree_ids = [int(getattr(o, "ID", o)) for o in cfg["trees"]]
        for (wx, wy) in _wall_perimeter(ax0, ay0, ax1, ay1):
            ix, iy = int(wx), int(wy)
            if (ix, iy) in water or reserved_near(ix, iy):
                continue
            um.add_unit(player=0, unit_const=rng.choice(tree_ids), x=wx, y=wy)
        border_items = [int(getattr(o, "ID", o)) for o in (_TENTS + _DESTROYED)]
        for i, (wx, wy) in enumerate(_wall_perimeter(ax0 - 2, ay0 - 2, ax1 + 2, ay1 + 2)):
            if i % 3 != 0:                     # sprinkle, don't pave
                continue
            ix, iy = int(wx), int(wy)
            if not (1 <= ix < N - 1 and 1 <= iy < N - 1):
                continue
            if (ix, iy) in water or reserved_near(ix, iy):
                continue
            um.add_unit(player=0, unit_const=rng.choice(border_items), x=wx, y=wy)

    # 3) scatter Gaia eye-candy: mostly OUTSIDE the arena (forest depth), with a few
    #    battlefield bones inside. Animals go outside only.
    def pick_inside():
        lo, hi = ax0 + 1, cx - FIGHT_CLEAR - 1
        if rng.random() < 0.5 and lo <= hi:
            x = rng.randint(lo, hi)
        else:
            x = rng.randint(cx + FIGHT_CLEAR + 1, ax1 - 1)
        return x, rng.randint(ay0 + 1, ay1 - 1)

    def pick_outside():
        if rng.random() < 0.5:
            x = rng.choice([rng.randint(ax0 - OUT, ax0 - 2), rng.randint(ax1 + 2, ax1 + OUT)])
            y = rng.randint(ay0 - OUT, ay1 + OUT)
        else:
            x = rng.randint(ax0 - OUT, ax1 + OUT)
            y = rng.choice([rng.randint(ay0 - OUT, ay0 - 2), rng.randint(ay1 + 2, ay1 + OUT)])
        return x, y

    def scatter(items, count, inside_frac):
        ids = [int(getattr(o, "ID", o)) for o in items]
        count = max(1, int(round(count * area_scale)))
        placed = tries = 0
        while placed < count and tries < count * 30:
            tries += 1
            x, y = pick_inside() if rng.random() < inside_frac else pick_outside()
            if not (1 <= x < N - 1 and 1 <= y < N - 1):
                continue
            if (x, y) in water or reserved_near(x, y) or on_perimeter(x, y):
                continue
            um.add_unit(player=0, unit_const=rng.choice(ids), x=x + 0.5, y=y + 0.5)
            placed += 1

    scatter(cfg["trees"], cfg["n_trees"], inside_frac=0.12)
    scatter(cfg["structures"], cfg["n_struct"], inside_frac=0.18)
    scatter(cfg["plants"], cfg["n_plants"], inside_frac=0.22)
    scatter(cfg["animals"], cfg["n_animals"], inside_frac=0.0)   # animals stay outside
    scatter(_BATTLE, cfg.get("n_battle", 18), inside_frac=0.5)   # battlefield bones/fires


# --------------------------------------------------------------------------- #
# builder
# --------------------------------------------------------------------------- #
def build_matchup_scenario(spec: MatchupSpec, out_dir: str | Path = ".") -> Path:
    scn = AoE2DEScenario.from_default(spec.scenario_version)

    pm = scn.player_manager
    um = scn.unit_manager
    tm = scn.trigger_manager

    # Resize the map (default scenario is 80x80). The builder previously relied on
    # that default; set it explicitly so spec.map_size actually takes effect.
    scn.map_manager.map_size = spec.map_size

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
    P23 = ALLY if spec.peaceful else ENEMY              # showcase -> no fight
    p1.diplomacy[2] = ALLY; p1.diplomacy[3] = ALLY      # spectator allied to both
    p2.diplomacy[1] = ALLY; p2.diplomacy[3] = P23       # fighters: ally spectator, fight each other
    p3.diplomacy[1] = ALLY; p3.diplomacy[2] = P23

    # --- arena geometry ----------------------------------------------------
    cx = cy = spec.map_size // 2
    half = spec.arena_size // 2
    ax0, ay0, ax1, ay1 = cx - half, cy - half, cx + half, cy + half  # inclusive tile box
    arena_area = dict(area_x1=ax0, area_y1=ay0, area_x2=ax1, area_y2=ay1)

    # --- boundary -----------------------------------------------------------
    # "wall": Gaia-blocking stone/fortified perimeter owned by P1 (proven
    #   containment for real matchups; P1 is allied to both so it's never attacked).
    # "natural": NO walls — a solid Gaia treeline on the arena perimeter (built in
    #   _decorate_meso) contains the fight instead, for a cleaner battlefield look.
    if spec.boundary == "wall":
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

    # --- cosmetic Central-American themed decoration (terrain + Gaia eye-candy) -
    if spec.theme and spec.theme != "none":
        _decorate_meso(scn, spec, cx, cy, ax0, ay0, ax1, ay1)

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
    setup.new_effect.change_diplomacy(source_player=2, target_player=3, diplomacy=P23, mutual_diplomacy=True)
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
