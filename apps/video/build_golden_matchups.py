"""Build the 5 golden_template matchup scenarios (2026-07-05).

Base = apps/video/templates/golden_template.aoe2scenario (the user's hand-made test
bed: 16x16 flat, P1 human spectator w/ map revealers + a camera-center trigger,
P2 = ddkImmortalCoreG kiter, P3 = stock Immortal v0d10f, up to 21 units/side in a
fixed formation). We KEEP every position/rotation and only:
  * swap P2's army -> the matchup's RANGED unit  (kiter, on ddkModelAI)
  * swap P3's army -> the matchup's MELEE unit    (chaser, AI = none: it just
    auto-fights/chases natively, which the user confirmed works)
  * set P2 civ = ranged unit's civ, P3 civ = melee unit's civ
  * set P1 civ = P3 civ                          (user rule)
  * trim counts for EQUAL RESOURCES (weighted food 1.0 / wood 0.7 / gold 1.5,
    the canonical aoe2x/sim/simulation_real.weighted_cost). 21 is the ceiling from
    the template; the cheaper-per-unit side stays at 21, the pricier side is trimmed
    so total weighted cost matches -- never above 21.

For the one ranged-vs-ranged pair (mangudai vs camel archer) the first-named unit
(mangudai) takes the ddkImmortalCoreG slot; both are cavalry archers.

Elite unit consts from AoE2ScenarioParser datasets; costs from data/golden/aoe2_reference.db.
"""
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

REPO = Path(__file__).resolve().parent
TEMPLATE = REPO / "templates" / "golden_template.aoe2scenario"
OUT_DIR = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE"
               r"\76561198690498042\resources\_common\scenario")

MAX_COUNT = 21                       # ceiling from the template layout
WF, WW, WG = 1.0, 0.7, 1.5           # weighted_cost weights (food, wood, gold)
AI_RANGED = ("ddkModelAI.ai", 0)     # P2 kiter (custom personality)
AI_MELEE  = ("NoneAi", 2)            # P3 melee: none -> native aggressive chase

def wcost(f, w, g):
    return WF * f + WW * w + WG * g

# label -> (elite_const, civ, food, wood, gold)  [costs = final/elite from ref DB]
U = {
    "Guecha Warrior":   (2564, "Muisca",  0,  50, 60),   # ranged (Archer)
    "Jaguar Warrior":   (726,  "Aztecs",  60, 0,  30),   # melee  (Infantry)
    "Blackwood Archer": (2581, "Tupi",    0,  35, 45),   # ranged (Archer)
    "Woad Raider":      (534,  "Celts",   70, 0,  25),   # melee  (Infantry)
    "Ballista Elephant":(1122, "Khmer",   100,0,  80),   # ranged (Ballista)
    "Magyar Huszar":    (871,  "Magyars", 35, 0,  45),   # melee  (Cavalry)
    "Mangudai":         (561,  "Mongols", 0,  55, 65),   # ranged (Cav Archer)
    "Camel Archer":     (1009, "Berbers", 0,  50, 60),   # ranged (Cav Archer)
    "Gbeto":            (1015, "Malians", 50, 0,  40),   # ranged (Infantry, throws)
    "Temple Guard":     (2587, "Muisca",  70, 0,  45),   # melee  (Infantry)
}

# (filename, P2 ranged/kiter unit, P3 melee/chaser unit)
MATCHUPS = [
    ("golden guecha vs jaguar",            "Guecha Warrior",   "Jaguar Warrior"),
    ("golden woad vs blackwood",           "Blackwood Archer", "Woad Raider"),
    ("golden ballista elephant vs magyar", "Ballista Elephant","Magyar Huszar"),
    ("golden mangudai vs camel archer",    "Mangudai",         "Camel Archer"),
    ("golden temple guard vs gbeto",       "Gbeto",            "Temple Guard"),
]

def equal_counts(cost_p2, cost_p3):
    """Cheaper-per-unit side -> MAX_COUNT; pricier side trimmed to match total cost."""
    if cost_p2 <= cost_p3:
        n2 = MAX_COUNT
        n3 = max(1, round(MAX_COUNT * cost_p2 / cost_p3))
    else:
        n3 = MAX_COUNT
        n2 = max(1, round(MAX_COUNT * cost_p3 / cost_p2))
    return n2, n3

def swap_army(um, pid, new_const, keep_n):
    """Retype the first keep_n of pid's units to new_const (preserving x/y/rotation);
    remove the surplus. Returns the number kept."""
    units = list(um.get_player_units(pid))
    for u in units[:keep_n]:
        u.unit_const = new_const
    for u in units[keep_n:]:
        um.remove_unit(unit=u)
    return min(keep_n, len(units))

def build(fname, p2_label, p3_label):
    r_const, r_civ, rf, rw, rg = U[p2_label]
    m_const, m_civ, mf, mw, mg = U[p3_label]
    c2, c3 = wcost(rf, rw, rg), wcost(mf, mw, mg)
    n2, n3 = equal_counts(c2, c3)

    scn = AoE2DEScenario.from_file(str(TEMPLATE))
    um, pm = scn.unit_manager, scn.player_manager
    got2 = swap_army(um, 2, r_const, n2)   # P2 = ddkImmortalCoreG = ranged kiter
    got3 = swap_army(um, 3, m_const, n3)   # P3 = Immortal        = melee chaser

    def player(pid):
        return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization[r_civ.upper()]
    player(3).civilization = Civilization[m_civ.upper()]
    player(1).civilization = Civilization[m_civ.upper()]   # P1 civ == P3 civ

    pd2 = scn.sections["PlayerDataTwo"]
    pd2.ai_names[1], pd2.ai_type[1] = AI_RANGED            # P2 = ddkModelAI
    pd2.ai_names[2], pd2.ai_type[2] = AI_MELEE             # P3 = none

    out = OUT_DIR / f"{fname}.aoe2scenario"
    if out.exists():
        out.unlink()                                       # delete old, regenerate
    scn.write_to_file(str(out))
    print(f"{fname}")
    print(f"    P2 ddkModelAI  {p2_label:17s} ({r_civ:8s}) x{got2:2d}  "
          f"unit_cost={c2:5.1f}  total={got2*c2:6.1f}")
    print(f"    P3 none        {p3_label:17s} ({m_civ:8s}) x{got3:2d}  "
          f"unit_cost={c3:5.1f}  total={got3*c3:6.1f}   P1 civ={m_civ}")
    print(f"    resource balance: {min(got2*c2,got3*c3)/max(got2*c2,got3*c3)*100:.1f}% "
          f"(diff {abs(got2*c2-got3*c3):.1f})")

if __name__ == "__main__":
    for m in MATCHUPS:
        build(*m)
