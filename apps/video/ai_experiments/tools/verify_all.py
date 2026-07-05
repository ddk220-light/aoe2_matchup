"""Verify EVERY ddk TEST scenario: right AI pre-picked, dirt+flat terrain, right armies,
everything in bounds."""
from pathlib import Path
from collections import Counter
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.terrains import TerrainId
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

SC = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198690498042\resources\_common\scenario")
# name -> (ai, p2const, p2n, p3const, p3n)
EXPECT = {
    "ddk TEST Blank":            ("ddkImmortalCoreG", None, 0, None, 0),
    "ddk TEST CavArcher":        ("ddkImmortalCoreG", 39, 12, 38, 8),
    "ddk TEST Bolas":            ("ddkImmortalCoreG", 2571, 12, 38, 8),
    "ddk TEST Longbow":          ("ddkImmortalCoreG", 530, 12, 38, 8),
    "ddk TEST Arambai":          ("ddkImmortalCoreG", 1128, 12, 38, 8),
    "ddk TEST HandCannon":       ("ddkImmortalCoreG", 5, 12, 38, 8),
    "ddk TEST Elephant":         ("ddkImmortalCoreG", 875, 12, 38, 8),
    "ddk TEST Mangudai":         ("ddkImmortalCoreG", 561, 12, 38, 8),
    "ddk TEST Obst Line":        ("ddkImmortalCoreH", 39, 12, 38, 8),
    "ddk TEST Obst Block":       ("ddkImmortalCoreH", 39, 12, 38, 8),
    "ddk TEST Obst Pillars":     ("ddkImmortalCoreH", 39, 12, 38, 8),
    "ddk TEST Obst Choke":       ("ddkImmortalCoreH", 39, 12, 38, 8),
    "ddk TEST Obst Pocket":      ("ddkImmortalCoreH", 39, 12, 38, 8),
    "ddk TEST RvR Strafe":       ("ddkImmortalCoreI", 492, 12, 492, 10),
    "ddk TEST Melee vs Archers": ("ddkMeleeV1", 38, 12, 492, 10),
    "ddk TEST Melee Mirror":     ("ddkMeleeV1", 38, 10, 38, 10),
    "ddk TEST Siege":            ("ddkImmortalCoreS", 280, 6, 492, 10),
}
ok = True
for name, (ai, c2, n2, c3, n3) in EXPECT.items():
    scn = AoE2DEScenario.from_file(str(SC / f"{name}.aoe2scenario"))
    mm, um = scn.map_manager, scn.unit_manager
    n = mm.map_size
    bad_t = sum(1 for t in mm.terrain
                if t.terrain_id != TerrainId.DIRT_1 or t.elevation != 0 or t.layer != -1)
    pd2 = scn.sections["PlayerDataTwo"]
    ai_ok = pd2.ai_names[1] == ai and pd2.ai_type[1] == 0
    p2 = Counter(u.unit_const for u in um.get_player_units(2))
    p3 = Counter(u.unit_const for u in um.get_player_units(3))
    oob = [1 for p in range(0, 4) for u in um.get_player_units(p)
           if not (0 <= u.x < n and 0 <= u.y < n)]
    armies_ok = ((c2 is None or p2.get(c2) == n2) and (c3 is None or p3.get(c3) == n3))
    good = bad_t == 0 and ai_ok and armies_ok and not oob
    ok &= good
    print(f"{'OK ' if good else 'BAD'} {name:26s} ai={pd2.ai_names[1]:18s} "
          f"P2={dict(p2)} P3={dict(p3)} terrain_bad={bad_t} oob={len(oob)}")
print("ALL 17 GOOD" if ok else "FAILURES ABOVE")
