"""Generate civ/unit matchup scenarios from the GOLDEN engagement templates.

The golden templates (repo: apps/video/templates/golden_*.aoe2scenario, recorded 2026-07-18
from the user's hand-fixed, in-game-confirmed works_* files) are the canonical per-engagement
layouts:
  golden_infvsinf     P2 inf  on ddkMatchupAI (top)    vs P3 inf    on NoneAi (bottom)
  golden_rangedvsinf  P2 rng  on ddkMatchupAI (top)    vs P3 inf    on NoneAi (bottom)
  golden_cavvsranged  P2 cav  on NoneAi      (east!)   vs P3 ranged on ddkMatchupAI (bottom)

Key facts they encode (found the hard way):
  * The DE standard AI (PromiDE) does NOT work for infantry or ranged armies -> use the
    editor's "None" AI = ai_names='NoneAi', ai_type=2, 54-char self-disabling stub blob.
  * PromiDE survives only on the P1 human/spectator slot.
  * Cavalry-vs-ranged needs repositioned units (cav east, ranged bottom).

This script changes ONLY unit_const (army retype), army COUNTS (equal-resources trim,
max 25/side), and civilizations — nothing else (AI names/types/blobs/Files/positions of
kept units untouched), the minimal transform that has always been load-safe.

EQUAL RESOURCES: per-unit weighted cost food*1.0 + wood*0.7 + gold*1.5 (keep in lockstep
with aoe2x/sim/simulation_real.weighted_cost). The cheaper-per-unit side gets MAX_COUNT=25;
the pricier side is trimmed so total weighted cost matches. Costs come live from
data/golden/aoe2_reference.db (final_cost_*, Imperial fully-upgraded).
"""
import os, sqlite3
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

OUT_DIR = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198690498042\resources\_common\scenario")
TEMPLATES = Path(__file__).resolve().parent / "templates"
REF_DB = Path(__file__).resolve().parents[2] / "data" / "golden" / "aoe2_reference.db"

MAX_COUNT = 25
WF, WW, WG = 1.0, 0.7, 1.5     # lockstep with simulation_real.weighted_cost

# (template, output, (P2 civ, P2 const, P2 cost-slug), (P3 civ, P3 const, P3 cost-slug))
# P1 civ follows P3. Cost slugs are ref-DB unit_slugs (knight line is stored as 'paladin').
COPIES = [
    ("golden_infvsinf",    "aztec_celt_infvsinf",
     ("AZTECS", 567, "champion"),                 # Champion
     ("CELTS",  534, "elite_woad_raider_celts")), # Elite Woad Raider
    ("golden_rangedvsinf", "aztec_celt_rangedvsinf",
     ("AZTECS", 492, "arbalester"),               # Arbalester
     ("CELTS",  567, "champion")),                # Champion
    ("golden_cavvsranged", "aztec_celt_cavvsranged",
     ("CELTS",  283, "paladin"),                  # Cavalier (knight-line cost; Aztecs have no cavalry)
     ("AZTECS", 492, "arbalester")),              # Arbalester
]

def wcost(civ, slug):
    cur = sqlite3.connect(REF_DB).cursor()
    row = cur.execute(
        "SELECT final_cost_food, final_cost_wood, final_cost_gold FROM ref_units "
        "WHERE unit_slug=? AND civ_name=?", (slug, civ.title())).fetchone()
    assert row, f"no ref-DB cost for {slug}/{civ}"
    f, w, g = row
    return WF * f + WW * w + WG * g

def equal_counts(c2, c3):
    """Cheaper-per-unit side -> MAX_COUNT; pricier side trimmed to match total cost."""
    if c2 <= c3:
        return MAX_COUNT, max(1, round(MAX_COUNT * c2 / c3))
    return max(1, round(MAX_COUNT * c3 / c2)), MAX_COUNT

def swap_army(um, pid, const, keep_n):
    units = list(um.get_player_units(pid))
    for u in units[:keep_n]:
        u.unit_const = const
    for u in units[keep_n:]:
        um.remove_unit(unit=u)
    return min(keep_n, len(units))

def build(src, out_name, p2, p3):
    (c2, u2, s2), (c3, u3, s3) = p2, p3
    w2, w3 = wcost(c2, s2), wcost(c3, s3)
    n2, n3 = equal_counts(w2, w3)
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
    t2, t3 = got2 * w2, got3 * w3
    print(f"{out_name:26s}  P2={c2:7s} {UnitInfo.from_id(u2).name:18s} x{got2:2d} (w={w2:6.1f}, tot={t2:7.1f})")
    print(f"{'':26s}  P3={c3:7s} {UnitInfo.from_id(u3).name:18s} x{got3:2d} (w={w3:6.1f}, tot={t3:7.1f})"
          f"   balance={min(t2,t3)/max(t2,t3)*100:.1f}%")

if __name__ == "__main__":
    for row in COPIES:
        build(*row)
    print("done ->", OUT_DIR)
