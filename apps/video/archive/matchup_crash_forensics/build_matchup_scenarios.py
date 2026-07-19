"""Generate runnable matchup scenarios from the 4 matchup templates.

Given a matchup (P2 unit, P3 unit), classify each as ranged/melee, pick the template whose
slot layout + AI already match those kinds, retype the placeholder units to the real ones,
set civs, and write a loadable scenario into the AoE2 save folder.  AI personalities are
NOT touched here -- each template already bakes them in (ranged=ddkCircleModel, melee=PromiDE).

Template picked by (P2 kind, P3 kind):
    (ranged, melee) -> ranged_vs_melee     (P2 ranged top,  P3 melee bottom)
    (melee, ranged) -> melee_vs_ranged     (P2 melee bottom, P3 ranged top)  [swapped layout]
    (ranged, ranged)-> ranged_vs_ranged
    (melee, melee)  -> melee_vs_melee

Full counts (30/side for mixed = new template, 21/side for same-type = old template). Equal-
resource trimming is available via equal_counts() but OFF by default for these validation runs.
"""
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

REPO = Path(__file__).resolve().parent                     # apps/video
TEMPLATES = REPO / "templates"
OUT_DIR = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE"
               r"\76561198690498042\resources\_common\scenario")

WF, WW, WG = 1.0, 0.7, 1.5           # weighted_cost weights (food, wood, gold)

# label -> (elite_const, civ, kind, food, wood, gold)
U = {
    "Mangudai":         (561,  "Mongols", "ranged", 0,  55, 65),
    "Camel Archer":     (1009, "Berbers", "ranged", 0,  50, 60),
    "Guecha Warrior":   (2564, "Muisca",  "ranged", 0,  50, 60),
    "Ballista Elephant":(1122, "Khmer",   "ranged", 100,0,  80),
    "Gbeto":            (1015, "Malians", "ranged", 50, 0,  40),
    "Jaguar Warrior":   (726,  "Aztecs",  "melee",  60, 0,  30),
    "Woad Raider":      (534,  "Celts",   "melee",  70, 0,  25),
    "Temple Guard":     (2587, "Muisca",  "melee",  70, 0,  45),
    "Magyar Huszar":    (871,  "Magyars", "melee",  35, 0,  45),
}

TEMPLATE_FOR = {
    ("ranged", "melee"):  "ranged_vs_melee.aoe2scenario",
    ("melee",  "ranged"): "melee_vs_ranged.aoe2scenario",
    ("ranged", "ranged"): "ranged_vs_ranged.aoe2scenario",
    ("melee",  "melee"):  "melee_vs_melee.aoe2scenario",
}

def wcost(f, w, g):
    return WF * f + WW * w + WG * g

def swap_army(um, pid, new_const, keep_n):
    units = list(um.get_player_units(pid))
    for u in units[:keep_n]:
        u.unit_const = new_const
    for u in units[keep_n:]:
        um.remove_unit(unit=u)
    return min(keep_n, len(units))

def build(out_name, p2_label, p3_label):
    p2 = U[p2_label]; p3 = U[p3_label]
    p2_const, p2_civ, p2_kind = p2[0], p2[1], p2[2]
    p3_const, p3_civ, p3_kind = p3[0], p3[1], p3[2]

    template = TEMPLATES / TEMPLATE_FOR[(p2_kind, p3_kind)]
    scn = AoE2DEScenario.from_file(str(template))
    um, pm = scn.unit_manager, scn.player_manager

    n2 = swap_army(um, 2, p2_const, len(list(um.get_player_units(2))))   # keep all
    n3 = swap_army(um, 3, p3_const, len(list(um.get_player_units(3))))

    def player(pid):
        return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization[p2_civ.upper()]
    player(3).civilization = Civilization[p3_civ.upper()]
    player(1).civilization = Civilization[p3_civ.upper()]      # P1 civ == P3 civ (old rule)

    pd2 = scn.sections["PlayerDataTwo"]
    ai2 = (pd2.ai_names[1], pd2.ai_type[1])
    ai3 = (pd2.ai_names[2], pd2.ai_type[2])

    out = OUT_DIR / f"{out_name}.aoe2scenario"
    if out.exists():
        out.unlink()
    scn.write_to_file(str(out))
    print(f"{out_name}  [{template.name}]")
    print(f"    P2  {p2_label:17s} ({p2_civ:8s}) {p2_kind:6s} x{n2:2d}  AI={ai2[0]}({ai2[1]})")
    print(f"    P3  {p3_label:17s} ({p3_civ:8s}) {p3_kind:6s} x{n3:2d}  AI={ai3[0]}({ai3[1]})")

# The validation scenarios (one per gameplay option).
TESTS = [
    ("test melee vs melee",   "Jaguar Warrior", "Woad Raider"),    # MvM  -> both PromiDE
    ("test ranged vs ranged", "Mangudai",       "Camel Archer"),   # RvR  -> both PromiDE
    ("test ranged vs melee",  "Mangudai",       "Jaguar Warrior"), # RvM  -> P2 circle(top)  vs P3 PromiDE(bottom)
    ("test melee vs ranged",  "Jaguar Warrior", "Mangudai"),       # MvR  -> P2 PromiDE(bottom) vs P3 circle(top)
                                                                   #        (swap: tests the circle AI on the P3 slot)
]

if __name__ == "__main__":
    for t in TESTS:
        build(*t)
    print(f"done -> {OUT_DIR}")
