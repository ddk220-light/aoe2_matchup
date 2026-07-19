"""Disambiguate the MvM/RvR load-crash. After all templates were rebuilt from the NEW 26 KB
template, the two crashers (MvM, RvR) differ from the two that work (RvM, MvR) in TWO confounded
ways at once:
  (1) STRUCTURE: crashers have BOTH fighting players on PromiDE; workers have 1 circle + 1 PromiDE.
  (2) UNITS/CIVS: crashers are the only ones using Woad Raider/Celts and Camel Archer/Berbers;
      workers only use Mangudai/Mongols and Jaguar/Aztecs.

These two diagnostics each hold one factor at the known-good setting so the crash points at the
other:

  DIAG_A  both PromiDE, KNOWN-GOOD units (Mangudai vs Jaguar).
          -> crashes  ==> cause is STRUCTURE (two PromiDE fighting players).
          -> loads    ==> structure is fine; cause is the units/civs.

  DIAG_B  one circle + one PromiDE (known-good STRUCTURE), SUSPECT units (Camel Archer vs Woad).
          -> loads    ==> those units/civs are fine; cause is the structure.
          -> crashes  ==> cause is a specific unit/civ (Camel Archer/Berbers or Woad/Celts).

Load BOTH in-game and report which crash. Expected if it's the structure: A crashes, B loads.
"""
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

REPO = Path(__file__).resolve().parent
NEW_SRC = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE"
               r"\76561198690498042\resources\_common\scenario\golden_template.aoe2scenario")
OUT_DIR = NEW_SRC.parent

CIRCLE   = ("ddkCircleModel.ai", 0)
STANDARD = ("PromiDE", 1)

# label -> (elite_const, civ)
U = {
    "Mangudai": (561, "Mongols"), "Jaguar Warrior": (726, "Aztecs"),
    "Camel Archer": (1009, "Berbers"), "Woad Raider": (534, "Celts"),
}

def swap_army(um, pid, const):
    for u in list(um.get_player_units(pid)):
        u.unit_const = const

def build(name, p2, p3, p1_ai=None):
    (p2_label, p2_ai), (p3_label, p3_ai) = p2, p3
    scn = AoE2DEScenario.from_file(str(NEW_SRC))
    um, pm = scn.unit_manager, scn.player_manager
    swap_army(um, 2, U[p2_label][0])
    swap_army(um, 3, U[p3_label][0])
    def player(pid): return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization[U[p2_label][1].upper()]
    player(3).civilization = Civilization[U[p3_label][1].upper()]
    player(1).civilization = Civilization[U[p3_label][1].upper()]
    pd2 = scn.sections["PlayerDataTwo"]
    pd2.ai_names[1], pd2.ai_type[1] = p2_ai
    pd2.ai_names[2], pd2.ai_type[2] = p3_ai
    if p1_ai is not None:
        pd2.ai_names[0], pd2.ai_type[0] = p1_ai
    out = OUT_DIR / f"{name}.aoe2scenario"
    if out.exists(): out.unlink()
    scn.write_to_file(str(out))
    print(f"{name}")
    print(f"    P1 AI={(p1_ai[0] if p1_ai else 'PromiDE (template default)')}")
    print(f"    P2 {p2_label:14s} ({U[p2_label][1]:8s}) AI={p2_ai[0]}({p2_ai[1]})")
    print(f"    P3 {p3_label:14s} ({U[p3_label][1]:8s}) AI={p3_ai[0]}({p3_ai[1]})")

CIRCLE_CCW = ("ddkCircleModelCCW.ai", 0)

if __name__ == "__main__":
    # DIAG_A: both PromiDE, known-good units  -> isolates STRUCTURE. RESULT: CRASHED => structure.
    build("diag A both-standard mangudai v jaguar", ("Mangudai", STANDARD), ("Jaguar Warrior", STANDARD))
    # DIAG_B: 1 circle + 1 PromiDE, suspect units -> isolates UNITS/CIVS. RESULT: LOADED => units fine.
    build("diag B mixed camel v woad", ("Camel Archer", CIRCLE), ("Woad Raider", STANDARD))
    # DIAG_C: the exact new-MvR layout (P2 Jaguar melee TOP PromiDE, P3 Mangudai ranged BOTTOM) but with
    #   the KNOWN-GOOD CW circle instead of CCW. Isolates the CCW file from the ranged-in-bottom layout:
    #     C loads  + MvR(CCW) crashes -> the CCW file/deploy (restart AoE2!).
    #     C crashes too                -> the ranged-in-BOTTOM layout itself is the problem.
    build("diag C mvr-layout cw circle", ("Jaguar Warrior", STANDARD), ("Mangudai", CIRCLE))  # RESULT: CRASHED
    # DIAG_E: DIAG B's exact units, AI swapped between bands (Camel/PromiDE TOP, Woad/circle BOTTOM).
    #   Isolates AI-position from units: if E crashes but B loads -> it's PromiDE-in-the-TOP, not the units.
    build("diag E camel-promide-top woad-circle-bottom", ("Camel Archer", STANDARD), ("Woad Raider", CIRCLE))
    # DIAG_F: THE FIX TEST = DIAG A (both fighters PromiDE, crashed) but P1 spectator taken OFF PromiDE.
    #   If F LOADS -> the trigger is TWO PromiDE players in the top; fix = set P1 to a non-PromiDE AI in
    #   every template, and MvM/RvR/new-MvR all work with both fighters still on standard.
    build("diag F p1-off-promide both-standard", ("Mangudai", STANDARD), ("Jaguar Warrior", STANDARD),
          p1_ai=("ddkModelAI.ai", 0))
    print(f"done -> {OUT_DIR}")
