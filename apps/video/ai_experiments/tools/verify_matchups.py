"""Verify the 5 golden matchup scenarios: units/civs/AIs/counts, P1 civ == P3 civ,
positions preserved from template, camera trigger + P1 map revealers intact, bounds."""
from pathlib import Path
from collections import Counter
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

SC = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198690498042\resources\_common\scenario")
TPL = Path(r"C:\dev\aoe2\aoe2_matchup\apps\video\templates\golden_template.aoe2scenario")

# template reference positions (order preserved)
t = AoE2DEScenario.from_file(str(TPL))
tpos = {pid: [(round(u.x,3), round(u.y,3), round(getattr(u,'rotation',0),3))
              for u in t.unit_manager.get_player_units(pid)] for pid in (2, 3)}

# name -> (p2const, p2civ, p2n, p3const, p3civ, p3n)
EXP = {
    "golden guecha vs jaguar":            (2564, "MUISCA", 18, 726,  "AZTECS", 21),
    "golden woad vs blackwood":           (2581, "TUPI",   21, 534,  "CELTS",  18),
    "golden ballista elephant vs magyar": (1122, "KHMER",  10, 871,  "MAGYARS",21),
    "golden mangudai vs camel archer":    (561,  "MONGOLS",19, 1009, "BERBERS",21),
    "golden temple guard vs gbeto":       (1015, "MALIANS",21, 2587, "MUISCA", 17),
}
allok = True
for name, (c2, civ2, n2, c3, civ3, n3) in EXP.items():
    scn = AoE2DEScenario.from_file(str(SC / f"{name}.aoe2scenario"))
    um, pm, tm = scn.unit_manager, scn.player_manager, scn.trigger_manager
    pd2 = scn.sections["PlayerDataTwo"]
    def civ(pid): return next(p for p in pm.players if int(p.player_id)==pid).civilization
    p2 = Counter(u.unit_const for u in um.get_player_units(2))
    p3 = Counter(u.unit_const for u in um.get_player_units(3))
    fails = []
    if dict(p2) != {c2: n2}: fails.append(f"P2 army {dict(p2)} != {{{c2}:{n2}}}")
    if dict(p3) != {c3: n3}: fails.append(f"P3 army {dict(p3)} != {{{c3}:{n3}}}")
    if civ(2) != Civilization[civ2]: fails.append(f"P2 civ {civ(2)}")
    if civ(3) != Civilization[civ3]: fails.append(f"P3 civ {civ(3)}")
    if civ(1) != Civilization[civ3]: fails.append(f"P1 civ {civ(1)} != P3 {civ3}")
    if pd2.ai_names[1] != "ddkImmortalCoreG.ai": fails.append(f"P2 ai {pd2.ai_names[1]!r}")
    if pd2.ai_names[2] != "Immortal v0d10f.ai": fails.append(f"P3 ai {pd2.ai_names[2]!r}")
    # positions preserved (first nX of the template layout)
    for pid, nX in ((2, n2), (3, n3)):
        got = [(round(u.x,3), round(u.y,3), round(getattr(u,'rotation',0),3))
               for u in um.get_player_units(pid)]
        if got != tpos[pid][:nX]:
            fails.append(f"P{pid} positions differ from template[:{nX}]")
    # P1 revealers (1775 x2) + keep-alives (2551,1291) + camera trigger
    p1 = Counter(u.unit_const for u in um.get_player_units(1))
    if p1.get(1775) != 2: fails.append(f"P1 map revealers {p1.get(1775)}")
    if not (p1.get(2551) and p1.get(1291)): fails.append("P1 keep-alives missing")
    if len(tm.triggers) != 1: fails.append(f"{len(tm.triggers)} triggers (want 1 camera)")
    n = scn.map_manager.map_size
    oob = [1 for pid in range(0,4) for u in um.get_player_units(pid)
           if not (0 <= u.x < n and 0 <= u.y < n)]
    if oob: fails.append(f"{len(oob)} out of bounds")
    allok &= not fails
    tag = "OK " if not fails else "BAD"
    print(f"{tag} {name}")
    for f in fails: print("      -", f)
print("\nALL 5 GOOD" if allok else "\nFAILURES ABOVE")
