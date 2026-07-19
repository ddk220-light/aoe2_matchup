"""ETG sim-validation scenarios: the V2 categorization's decision-relevant matchups,
built from the golden engagement templates at the SAME arena counts the V2 sim used
(sim_v2/results/elite_temple_guard_muisca.md), so in-game outcomes compare 1:1
against the sim's win-rate/margin rows.

Same minimal load-safe transform as build_civ_copies.py: retype army + trim counts
+ set civs — AI names/types/blobs/Files/positions untouched.

Matchup set (why each):
  coin-flips (sim least certain — these decide the categorization):
    konnik (67% ETG), warrior_priest (73%), condottiero (47%), guecha (27%)
  unexpected loss not yet in-game validated:
    cataphract (0%)
  anchors (sim certain — sanity + churn/trample probes):
    paladin (100%, attackDelay-melee churn probe), battle_elephant (100%, trample),
    champion (0%, expected loss)

Engagement kind: ETG is melee infantry -> golden_infvsinf for every melee opponent
(P2 = ETG on ddkMatchupAI patrol, P3 = opponent on NoneAi), golden_rangedvsinf for
the ranged Guecha (P2 = Guecha on patrol/kite, P3 = ETG on NoneAi).
"""
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

OUT_DIR = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198690498042\resources\_common\scenario")
TEMPLATES = Path(__file__).resolve().parent / "templates"

ETG = 2587           # ELITE_TEMPLE_GUARD (Muisca)

# (template, out_name, (P2 civ, P2 const, P2 count), (P3 civ, P3 const, P3 count))
# Counts = the V2 arena counts (subject v opp) from results/elite_temple_guard_muisca.md.
COPIES = [
    # --- coin-flips ---
    ("golden_infvsinf", "etg_konnik_infvsinf",          # sim: 67% ETG, S +4  (21v17)
     ("MUISCA", ETG, 21), ("BULGARIANS", 1227, 17)),    # Elite Konnik
    ("golden_infvsinf", "etg_warriorpriest_infvsinf",   # sim: 73% ETG, S +5  (17v21)
     ("MUISCA", ETG, 17), ("ARMENIANS", 1811, 21)),     # Warrior Priest
    ("golden_infvsinf", "etg_condottiero_infvsinf",     # sim: 47% ETG, S -1  (15v21)
     ("MUISCA", ETG, 15), ("ITALIANS", 882, 21)),       # Condottiero
    ("golden_rangedvsinf", "etg_guecha_rangedvsinf",    # sim: 27% ETG, S -6  (21v20)
     ("MUISCA", 2564, 20), ("MUISCA", ETG, 21)),        # Elite Guecha (ranged, patrol side)
    # --- unexpected loss, not yet in-game validated ---
    ("golden_infvsinf", "etg_cataphract_infvsinf",      # sim: 0% ETG, S -62  (21v15)
     ("MUISCA", ETG, 21), ("BYZANTINES", 553, 15)),     # Elite Cataphract
    # --- anchors ---
    ("golden_infvsinf", "etg_paladin_infvsinf",         # sim: 100% ETG, S +38 (21v16)
     ("MUISCA", ETG, 21), ("HUNS", 569, 16)),           # Paladin
    ("golden_infvsinf", "etg_battleelephant_infvsinf",  # sim: 100% ETG, S +37 (21v14)
     ("MUISCA", ETG, 21), ("VIETNAMESE", 1134, 14)),    # Elite Battle Elephant
    ("golden_infvsinf", "etg_champion_infvsinf",        # sim: 0% ETG, S -48  (12v21)
     ("MUISCA", ETG, 12), ("BERBERS", 567, 21)),        # Champion
]

def swap_army(um, pid, const, keep_n):
    units = list(um.get_player_units(pid))
    for u in units[:keep_n]:
        u.unit_const = const
    for u in units[keep_n:]:
        um.remove_unit(unit=u)
    return min(keep_n, len(units))

def build(src, out_name, p2, p3):
    (c2, u2, n2), (c3, u3, n3) = p2, p3
    scn = AoE2DEScenario.from_file(str(TEMPLATES / f"{src}.aoe2scenario"))
    um, pm = scn.unit_manager, scn.player_manager
    got2 = swap_army(um, 2, u2, n2)
    got3 = swap_army(um, 3, u3, n3)
    def player(pid): return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization[c2]
    player(3).civilization = Civilization[c3]
    player(1).civilization = Civilization[c3]          # P1 follows P3 (works_* pattern)
    out = OUT_DIR / f"{out_name}.aoe2scenario"
    if out.exists(): out.unlink()
    scn.write_to_file(str(out))
    print(f"{out_name:32s}  P2={c2:10s} {UnitInfo.from_id(u2).name:22s} x{got2:2d}"
          f"   P3={c3:10s} {UnitInfo.from_id(u3).name:22s} x{got3:2d}")

if __name__ == "__main__":
    for row in COPIES:
        build(*row)
    print("done ->", OUT_DIR)
