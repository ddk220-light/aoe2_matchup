"""Adapter: the RECORDING rig (run_matchup build_fn) -> the FINAL 2026-07-18 golden
engagement templates (ddkMatchupAI patrol + NoneAi, the panda-map layouts recorded
from the user's hand-fixed works_* files).

This replaces build_golden_matchups.build_golden_from_sides for recordings — that
older adapter builds from the RETIRED 2026-07-05 golden_template.aoe2scenario
(flat 16x16, ddkModelAI both sides). The user caught recordings running on the old
map on 2026-07-19; every new recording must use these templates.

Template selection (the mapping build_etg_validation.py validated in-game):
  exactly one side ranged -> golden_rangedvsinf, RANGED side on P2 (ddkMatchupAI
                             patrol/kite slot), melee side on P3 (NoneAi chaser)
  otherwise               -> golden_infvsinf, SUBJECT (side1) on P2 patrol,
                             opponent on P3 (NoneAi) — melee cavalry/elephant
                             opponents chase natively on NoneAi (validated:
                             paladin/cataphract/battle-elephant runs)
  both sides ranged      -> the kiter is the side that BOTH outranges AND outruns
                             the other (user rule 2026-07-27); it goes on P2 with
                             the other side treated as the melee chaser. If
                             neither side has both edges, nobody can disengage:
                             it is a stand-and-shoot brawl on golden_infvsinf.
                             (Cav Archer vs Arbalest: Arbalest outranges, Cav
                             Archer outruns -> brawl.)
(golden_cavvsranged exists for a CAV subject vs ranged; no matchup needs it yet.)

Transform = build_civ_copies' minimal load-safe set: retype armies (unit_const),
trim counts, set civs (P1 follows P3). AI names/types/blobs/Files/positions are
NOT touched — scenarios store the AI in 3 places and any mismatch silently
crashes the load.

Counts come straight from the caller (run_matchup's equal-resources numbers, the
same arena counts the V2 sim used); scaled down only if they exceed the
template's 25 positions/side.
"""
import os
import tempfile
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization
from AoE2ScenarioParser import settings

settings.PRINT_STATUS_UPDATES = False

TEMPLATES = Path(__file__).resolve().parent / "templates"
T_INF_VS_INF = TEMPLATES / "golden_infvsinf.aoe2scenario"
T_RANGED_VS_INF = TEMPLATES / "golden_rangedvsinf.aoe2scenario"
MAX_COUNT = 25                      # positions per side in the golden templates


def _strip_civ_suffix(civ, slug):
    suffix = "_" + civ.lower()
    return slug[: -len(suffix)] if slug.endswith(suffix) else slug


def _range_speed(civ, slug):
    """(attack_range, movement_speed) for a civ/slug from the reference DB."""
    import sqlite3
    # Derive the DB path from this file (apps/video/ -> repo root); the rig runs
    # on the video venv, which does not have the repo root on sys.path.
    ref_db = Path(__file__).resolve().parents[2] / "data" / "golden" / "aoe2_reference.db"
    conn = sqlite3.connect(str(ref_db))
    # The rig hands uniques their CIV-STRIPPED key (elite_chu_ko_nu) while the
    # ref DB stores the suffixed slug (elite_chu_ko_nu_chinese) — try both.
    try:
        row = None
        for cand in (slug, f"{slug}_{civ.lower()}"):
            row = conn.execute(
                "SELECT final_range, final_speed FROM ref_units "
                "WHERE civ_name=? AND unit_slug=? AND age='Imperial'", (civ, cand)
            ).fetchone()
            if row is not None:
                break
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"no Imperial ref row for {civ}/{slug}")
    return float(row[0] or 0), float(row[1] or 0)


def _swap_army(um, pid, const, keep_n):
    units = list(um.get_player_units(pid))
    for u in units[:keep_n]:
        u.unit_const = const
    for u in units[keep_n:]:
        um.remove_unit(unit=u)
    return min(keep_n, len(units))


def _scale_counts(n2, n3, max_count=MAX_COUNT):
    hi = max(n2, n3)
    if hi <= max_count:
        return int(n2), int(n3)
    f = max_count / float(hi)
    return max(1, round(n2 * f)), max(1, round(n3 * f))


def build_v2_from_sides(side1, side2, out_path, counts=(21, 21),
                        ranged=(False, False)):
    """run_matchup build_fn: side1/side2 = (civ, slug, label) from resolve_side.
    Selects the golden engagement template, assigns P2 (patrol) / P3 (NoneAi),
    and writes the scenario to out_path. Downstream sidecar labeling relies on
    record_until_end.select_sidecar's start-count order detection, exactly as
    with the old adapter."""
    from build_run import unit_const

    (civ1, key1, _), (civ2, key2, _) = side1, side2
    n1, n2 = counts
    r1, r2 = ranged
    if r1 and r2:
        # BOTH RANGED (user rule, 2026-07-27): one ranged unit can only kite
        # another if it BOTH outranges AND outruns it — then it is the "ranged"
        # side and the other is treated as the melee chaser. If either edge is
        # missing neither can disengage, so it is a stand-and-shoot brawl and the
        # melee-vs-melee template applies. (User's example: Cavalry Archer vs
        # Arbalest — the Arbalest outranges, the Cav Archer outruns, so neither
        # kites.) Replaces a hard raise that made ranged subjects unfilmable
        # against every archer/skirm/gunpowder/cav-archer opponent.
        rs1, rs2 = _range_speed(civ1, key1), _range_speed(civ2, key2)
        if rs1[0] > rs2[0] and rs1[1] > rs2[1]:
            r1, r2 = True, False
        elif rs2[0] > rs1[0] and rs2[1] > rs1[1]:
            r1, r2 = False, True
        else:
            r1 = r2 = False
        print(f"[build_v2] both ranged -> {'side1 kites' if r1 else 'side2 kites' if r2 else 'brawl (melee-vs-melee)'} "
              f"(range/speed {rs1} vs {rs2})", flush=True)
    if r2 and not r1:                 # opponent kites -> P2; subject chases P3
        template = T_RANGED_VS_INF
        p2, p3 = (civ2, key2, n2), (civ1, key1, n1)
    elif r1 and not r2:               # subject kites -> P2
        template = T_RANGED_VS_INF
        p2, p3 = (civ1, key1, n1), (civ2, key2, n2)
    else:                             # both melee -> subject patrols on P2
        template = T_INF_VS_INF
        p2, p3 = (civ1, key1, n1), (civ2, key2, n2)

    (p2_civ, p2_slug, p2_n), (p3_civ, p3_slug, p3_n) = p2, p3
    c2 = unit_const(_strip_civ_suffix(p2_civ, p2_slug))
    c3 = unit_const(_strip_civ_suffix(p3_civ, p3_slug))
    p2_n, p3_n = _scale_counts(p2_n, p3_n)

    scn = AoE2DEScenario.from_file(str(template))
    um, pm = scn.unit_manager, scn.player_manager
    got2 = _swap_army(um, 2, c2, p2_n)
    got3 = _swap_army(um, 3, c3, p3_n)

    def player(pid):
        return next(p for p in pm.players if int(p.player_id) == pid)
    player(2).civilization = Civilization[p2_civ.upper()]
    player(3).civilization = Civilization[p3_civ.upper()]
    player(1).civilization = Civilization[p3_civ.upper()]   # P1 follows P3

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # the parser refuses to overwrite -> temp write + atomic replace
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(out_path.parent))
    os.close(fd)
    os.unlink(tmp)
    scn.write_to_file(tmp)
    os.replace(tmp, str(out_path))
    print(f"[build_v2] {template.name}: P2 {p2_civ}/{p2_slug} x{got2} (patrol) "
          f"vs P3 {p3_civ}/{p3_slug} x{got3} (NoneAi)", flush=True)
    return out_path
