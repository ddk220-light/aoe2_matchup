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
(golden_cavvsranged exists for a CAV subject vs ranged; no ETG matchup needs it —
raise rather than guess if both sides are ranged.)

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
        raise ValueError("both sides ranged: no validated golden template mapping")
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
