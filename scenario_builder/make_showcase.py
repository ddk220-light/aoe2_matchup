"""make_showcase.py — generate Central-American themed *showcase* battlefields.

These are the decorated, screenshot-friendly arenas (tiny map, half-size arena,
natural treeline+camp boundary instead of walls, a river across the top). By
default they are PEACEFUL (armies mutually allied) so the map can be viewed and
screenshotted statically without the match ending in a defeat screen.

Flip ``PEACEFUL = False`` (or pass ``--fight``) to emit the same look as a real
matchup arena (armies fight, survivor readout + victory triggers active).

Usage:
    .venv/bin/python make_showcase.py            # peaceful, into the game folder
    .venv/bin/python make_showcase.py --fight    # real-fight version
    .venv/bin/python make_showcase.py --out DIR   # write elsewhere
"""
from __future__ import annotations

import sys
from pathlib import Path

from make_scenario import Army, MatchupSpec, build_matchup_scenario
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.datasets.object_support import Civilization

# Feral macOS port scenario format.
SCEN_VERSION = "1.57"

# Default drop folder: the Feral VFS scenario dir on this Mac.
GAME_SCENARIO_DIR = Path(
    "/Users/deepak/Library/Application Support/Feral Interactive/Age Of Empires II/"
    "VFS/User/Games/Age of Empires 2 DE/76561198053842894/resources/_common/scenario"
)

# Compact "tiny" battlefield: half-size arena, armies close together, natural
# treeline boundary + top river. (old showcase was map 80 / arena 40 / gap 24.)
COMMON = dict(
    map_size=60,
    arena_size=20,
    army_gap=12,
    boundary="natural",
    river_top=True,
    scenario_version=SCEN_VERSION,
)

THEMES = ["meso_jungle", "meso_ruins", "meso_river"]
THEME_OUT = {"meso_jungle": "jungle", "meso_ruins": "ruins", "meso_river": "river"}


def build_all(out_dir: Path, peaceful: bool = True):
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for theme in THEMES:
        spec = MatchupSpec(
            army1=Army(UnitInfo.ELITE_FIRE_ARCHER.ID, Civilization.WU, 30, "Elite Fire Archer"),
            army2=Army(UnitInfo.JIAN_SWORDSMAN.ID, Civilization.WU, 30, "Jian Swordsman"),
            theme=theme,
            peaceful=peaceful,
            # peaceful showcase: no fight, no result triggers, stable static view.
            force_engage=not peaceful,
            survivor_readout=not peaceful,
            live_readout=not peaceful,
            # in peaceful mode disable the timeout (its declare_victory would boot the
            # spectator to a "defeated" screen mid-showcase); real fights keep 180s.
            timeout_seconds=0 if peaceful else 180,
            cinematic=True,
            output_name=f"MATCHUP_{THEME_OUT[theme]}" + ("" if peaceful else "_fight"),
            **COMMON,
        )
        path = build_matchup_scenario(spec, out_dir=out_dir)
        written.append(path)
        print(f"WROTE {path}")
    return written


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = sys.argv[1:]
    peaceful = "--fight" not in args
    out_dir = GAME_SCENARIO_DIR
    if "--out" in args:
        out_dir = Path(args[args.index("--out") + 1])
    build_all(out_dir, peaceful=peaceful)
