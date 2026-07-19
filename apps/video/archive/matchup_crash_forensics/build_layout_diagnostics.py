"""Layout diagnostics: is the MAP (top-band obstacles / army position) why PromiDE-on-P2
crashes? Both scenarios reproduce the crashing config (BOTH fighting players on PromiDE,
clean 3-location AI data) and change exactly ONE layout variable:

  diag H1 promide-armies-bottom : armies UNTOUCHED map, but P2's 30 units RELOCATED to clear
        bottom-half tiles (terrain 6, no GAIA object, no P3 unit). If it LOADS, PromiDE is
        fine anywhere below — the TOP-band position/obstacles are the trigger.
  diag H2 promide-top-cleared   : armies stay in place, but the top box x[2..11] y[0..8] is
        REALLY cleared: every GAIA object in it removed (incl. the (9,7) obj 2082) AND all
        terrain 10/128 in it repainted to 6. If it LOADS, the obstacles themselves crash
        PromiDE's load-time analysis. (The earlier diag G only repainted terrain — it left
        every tree/rock OBJECT standing, and carried the stale-Files bug, so it proved nothing.)

Interpretation matrix: H1 loads + H2 loads -> layout confirmed, either fix works.
H1 loads + H2 crashes -> it's the position/edge itself, not the objects. Both crash ->
layout is NOT the cause (then: editor ground-truth test).
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False
from make_matchup_templates import set_ai, sync_files_section, STANDARD, NEW_SRC

OUT_DIR = NEW_SRC.parent
JAGUAR, WOAD = 726, 534

def base_both_promide():
    """The crashing config, cleanly built: MvM (Jaguar vs Woad), both PromiDE, consistent AI."""
    scn = AoE2DEScenario.from_file(str(NEW_SRC))
    um, pm = scn.unit_manager, scn.player_manager
    for u in list(um.get_player_units(2)): u.unit_const = JAGUAR
    for u in list(um.get_player_units(3)): u.unit_const = WOAD
    def player(pid): return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization.AZTECS
    player(3).civilization = Civilization.CELTS
    player(1).civilization = Civilization.CELTS
    set_ai(scn, 2, STANDARD)
    set_ai(scn, 3, STANDARD)
    sync_files_section(scn, [STANDARD, STANDARD])
    return scn

def write(scn, name):
    out = OUT_DIR / f"{name}.aoe2scenario"
    if out.exists(): out.unlink()
    scn.write_to_file(str(out))
    print(f"wrote {out.name}")

# --- H1: relocate P2's army to clear bottom-half tiles ---
scn = base_both_promide()
um, mm = scn.unit_manager, scn.map_manager
blocked = set()
for pid in (0, 1, 3):
    for u in um.get_player_units(pid):
        blocked.add((int(u.x), int(u.y)))
clear = [(x, y) for y in range(7, 11) for x in range(1, 15)
         if mm.get_tile(x, y).terrain_id == 6 and (x, y) not in blocked]
p2 = list(um.get_player_units(2))
assert len(clear) >= len(p2), f"only {len(clear)} clear tiles for {len(p2)} units"
for u, (x, y) in zip(p2, clear):
    u.x, u.y = x + 0.5, y + 0.5
ys = [u.y for u in p2]
print(f"H1: relocated {len(p2)} P2 units to y[{min(ys)},{max(ys)}] (clear bottom half)")
write(scn, "diag H1 promide-armies-bottom")

# --- H2: armies in place, top box truly cleared (objects AND terrain) ---
scn = base_both_promide()
um, mm = scn.unit_manager, scn.map_manager
removed = []
for u in list(um.get_player_units(0)):
    if 2.0 <= u.x <= 12.0 and 0.0 <= u.y <= 9.0:
        removed.append((u.unit_const, u.x, u.y))
        um.remove_unit(unit=u)
n_ter = 0
for x in range(2, 12):
    for y in range(0, 9):
        t = mm.get_tile(x, y)
        if t.terrain_id in (10, 128):
            t.terrain_id = 6; n_ter += 1
print(f"H2: removed {len(removed)} GAIA objects (incl. {[c for c,_,_ in removed if c==2082]!r} 2082s), repainted {n_ter} tiles")
write(scn, "diag H2 promide-top-cleared")
