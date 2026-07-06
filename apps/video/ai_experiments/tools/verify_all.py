"""Verify the golden_template scenario (the user-made test bed, 2026-07-05):
right AIs pre-picked, flat waterless terrain, right armies, no triggers, in bounds.
The repo keeps a reference copy at apps/video/templates/golden_template.aoe2scenario."""
from pathlib import Path
from collections import Counter
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.terrains import TerrainId
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

SC = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198690498042\resources\_common\scenario")
NAME = "golden_template"
# per-player expectations: pid -> (ai_name, ai_type, {unit_const: count} or None=don't care)
EXPECT = {
    2: ("ddkModelAI.ai", 0, {1128: 21}),   # Burmese, 21 Elite Arambai
    3: ("ddkModelAI.ai", 0, {38: 21}),     # Berbers, 21 Knights (melee fallback path)
}
WATER = {t.value for t in TerrainId
         if any(k in t.name for k in ("WATER", "BEACH", "SHALLOW"))}

scn = AoE2DEScenario.from_file(str(SC / f"{NAME}.aoe2scenario"))
mm, um, tm = scn.map_manager, scn.unit_manager, scn.trigger_manager
n = mm.map_size
fails = []
if n != 16:
    fails.append(f"map size {n} != 16")
wet = sum(1 for t in mm.terrain if t.terrain_id in WATER)
if wet:
    fails.append(f"{wet} water/beach tiles")
hilly = sum(1 for t in mm.terrain if t.elevation != 0)
if hilly:
    fails.append(f"{hilly} tiles with elevation != 0")
if len(tm.triggers) != 1:   # the user's camera-center trigger on (8,7)
    fails.append(f"{len(tm.triggers)} triggers (expect 1 camera-center)")
pd2 = scn.sections["PlayerDataTwo"]
for pid, (ai, ai_type, army) in EXPECT.items():
    if pd2.ai_names[pid - 1] != ai or pd2.ai_type[pid - 1] != ai_type:
        fails.append(f"P{pid} ai={pd2.ai_names[pid - 1]!r}/{pd2.ai_type[pid - 1]} "
                     f"(expect {ai!r}/{ai_type})")
    have = Counter(u.unit_const for u in um.get_player_units(pid))
    if army is not None and dict(have) != army:
        fails.append(f"P{pid} army {dict(have)} (expect {army})")
oob = [(pid, u.unit_const, u.x, u.y) for pid in range(0, 4)
       for u in um.get_player_units(pid) if not (0 <= u.x < n and 0 <= u.y < n)]
if oob:
    fails.append(f"out of bounds: {oob}")

if fails:
    print(f"BAD {NAME}:")
    for f in fails:
        print("  -", f)
else:
    print(f"OK {NAME}: {n}x{n}, flat, no water, {len(tm.triggers)} triggers, "
          f"P2={pd2.ai_names[1]!r} P3={pd2.ai_names[2]!r}, armies + bounds good")
