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
  * trim counts for EQUAL RESOURCES (weighted food 1.0 / wood 1.0 / gold 1.5 — the
    video pipeline's overlay_data.COST_WEIGHT_*; NOTE this diverges from production
    simulation_real.weighted_cost, still wood 0.7). 21 is the ceiling from
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
WF, WW, WG = 1.0, 1.0, 1.5           # weighted_cost weights (food, wood, gold)
# ddkModelAI on BOTH slots (2026-07-05): the v3 diplomacy-stance enemy detection is
# slot-independent, ranged balls kite, and pure-melee armies hit the AI's melee
# fallback (engine auto-fight restored after ~10s of game time).
AI_RANGED = ("ddkModelAI.ai", 0)     # P2 kiter
AI_MELEE  = ("ddkModelAI.ai", 0)     # P3 melee

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


def _strip_civ_suffix(civ, slug):
    """Unique-unit slugs carry the civ as a suffix (elite_temple_guard_muisca ->
    elite_temple_guard); standard units keep the plain slug."""
    suffix = "_" + civ.lower()
    return slug[: -len(suffix)] if slug.endswith(suffix) else slug


def _scale_counts(n2, n3, max_count):
    """Scale both counts by the SAME factor so max(n2, n3) <= max_count, keeping
    each side >= 1. No-op when both already fit."""
    hi = max(n2, n3)
    if hi <= max_count:
        return int(n2), int(n3)
    factor = max_count / float(hi)
    return max(1, round(n2 * factor)), max(1, round(n3 * factor))


def _centroid(um, pid, const):
    pts = [(u.x, u.y) for u in um.get_player_units(pid) if u.unit_const == const]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _set_camera(scn, target):
    """Retarget the golden template's single CHANGE_VIEW (camera) effect to `target`
    (x, y). The golden template carries exactly Trigger 0 = one camera effect, so
    off-center fights stay framed. Ported from build_run._set_camera."""
    from AoE2ScenarioParser.datasets.effects import EffectId
    if target is None:
        return None
    vx, vy = int(round(target[0])), int(round(target[1]))
    CHANGE_VIEW = int(EffectId.CHANGE_VIEW)
    for trig in scn.trigger_manager.triggers:
        for eff in trig.effects:
            if int(eff.effect_type) == CHANGE_VIEW:
                eff.location_x = vx
                eff.location_y = vy
    return (vx, vy)


def build_golden_scenario(p2_side, p3_side, out_path, *, max_count=MAX_COUNT,
                          template=TEMPLATE):
    """Generalized golden-template builder (any pair, not just the 5 hand-listed).

    p2_side / p3_side = (civ:str, slug:str, count:int); P2 = the ranged/kiter slot,
    P3 = the melee/chaser slot (the caller assigns ranged->P2). Unit const comes from
    build_run.unit_const(slug minus civ suffix); civs set with P1 == P3; both AI slots
    = ddkModelAI.ai/type0; both counts scaled by the SAME factor so max <= max_count
    (the template holds 21 positions/side); the single camera trigger is retargeted to
    the P2 (kiter) army so the fight stays framed. Writes to out_path (a temp/out file,
    NOT the game folder) and returns Path."""
    import os
    import tempfile
    from build_run import unit_const

    p2_civ, p2_slug, p2_count = p2_side
    p3_civ, p3_slug, p3_count = p3_side
    r_const = unit_const(_strip_civ_suffix(p2_civ, p2_slug))
    m_const = unit_const(_strip_civ_suffix(p3_civ, p3_slug))
    n2, n3 = _scale_counts(p2_count, p3_count, max_count)

    scn = AoE2DEScenario.from_file(str(template))
    um, pm = scn.unit_manager, scn.player_manager
    swap_army(um, 2, r_const, n2)          # P2 = ranged kiter
    swap_army(um, 3, m_const, n3)          # P3 = melee chaser

    def player(pid):
        return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization[p2_civ.upper()]
    player(3).civilization = Civilization[p3_civ.upper()]
    player(1).civilization = Civilization[p3_civ.upper()]   # P1 civ == P3 civ

    pd2 = scn.sections["PlayerDataTwo"]
    pd2.ai_names[1], pd2.ai_type[1] = AI_RANGED             # P2 = ddkModelAI
    pd2.ai_names[2], pd2.ai_type[2] = AI_MELEE              # P3 = ddkModelAI

    # KEEP the template's hand-authored camera (Trigger 0 CHANGE_VIEW, at the fixed
    # collision center ~(8,7)). build_golden preserves the template's formation POSITIONS
    # (only unit types swap + counts trim), so every matchup fights where the template was
    # framed for. Retargeting to the P2 army centroid put the camera off to one corner
    # (5.55,5.55) and framed the fight wrong (user-confirmed 2026-07-06) — so we leave the
    # template's CHANGE_VIEW untouched. (_set_camera/_centroid kept for the general case.)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # the parser refuses to overwrite an existing file -> write temp then move
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd)
    os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))
    return out_path


def build_golden_from_sides(side1, side2, out_path, counts=(30, 30),
                            ranged=(False, False)):
    """Adapter matching build_run's (side1, side2, out_path, counts=, ranged=) calling
    convention, so it can be passed as run_matchup(build_fn=...). side1/side2 are
    (civ, unit_key, label) as produced by resolve_side.

    The RANGED side takes the P2 kiter slot (both-ranged / both-melee -> side1/subject on
    P2); the other side is P3. This is empirically the RELIABLE kiting slot — a short-range
    ranged unit (e.g. Chakram Thrower) placed on P3 gets run down instead of kiting, which
    FLIPS the outcome. The resulting side1/side2 -> P2/P3 order mismatch with the overlay's
    (subject, opponent) labels is corrected downstream: record_until_end.select_sidecar
    detects the reversed start-count order and swaps the sidecar sides, so the HP bar +
    results card stay correctly labeled AND pass the gRPC sanity gate. See the sidecar-swap
    note there. Delegates to build_golden_scenario (counts scaled to 21)."""
    (civ1, key1, _), (civ2, key2, _) = side1, side2
    n1, n2 = counts
    r1, r2 = ranged
    if r2 and not r1:                         # only side 2 is ranged -> it kites (P2)
        p2, p3 = (civ2, key2, n2), (civ1, key1, n1)
    else:                                     # side 1 ranged, or same-kind -> side1 on P2
        p2, p3 = (civ1, key1, n1), (civ2, key2, n2)
    return build_golden_scenario(p2, p3, out_path)


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
    print(f"    P3 ddkModelAI  {p3_label:17s} ({m_civ:8s}) x{got3:2d}  "
          f"unit_cost={c3:5.1f}  total={got3*c3:6.1f}   P1 civ={m_civ}")
    print(f"    resource balance: {min(got2*c2,got3*c3)/max(got2*c2,got3*c3)*100:.1f}% "
          f"(diff {abs(got2*c2-got3*c3):.1f})")

if __name__ == "__main__":
    for m in MATCHUPS:
        build(*m)
