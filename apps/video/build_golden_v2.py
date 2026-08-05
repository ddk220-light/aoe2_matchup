"""Adapter: the RECORDING rig (run_matchup build_fn) -> the FINAL 2026-07-18 golden
engagement templates (ddkMatchupAI patrol + NoneAi, the panda-map layouts recorded
from the user's hand-fixed works_* files).

This replaces build_golden_matchups.build_golden_from_sides for recordings — that
older adapter builds from the RETIRED 2026-07-05 golden_template.aoe2scenario
(flat 16x16, ddkModelAI both sides). The user caught recordings running on the old
map on 2026-07-19; every new recording must use these templates.

Template selection (the mapping build_etg_validation.py validated in-game):
  both sides melee       -> golden_meleevsmelee (NEW 2026-07-30), subject on P2.
                             Melee = attack range <= 1, so the Steppe Lancer counts.
                             Hand-placed 21v21 in facing blocks 2 tiles apart: the old
                             golden_infvsinf started them 8.6 tiles apart and the
                             patrolling side arrived piecemeal, losing fights it wins
                             when both armies commit at once.
                             BOTH sides run NoneAi here — uniquely among the templates.
                             The armies already start in contact, so nothing needs
                             driving in, and putting one side on ddkMatchupAI makes the
                             two sides behave differently in a fight that should be
                             symmetric.
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
T_MELEE_VS_MELEE = TEMPLATES / "golden_meleevsmelee.aoe2scenario"
T_SIEGE = TEMPLATES / "golden_siegevsinf.aoe2scenario"
# Reload at or above this is "siege" for template purposes (2026-07-31). The number is
# measured, not chosen: across 300+ decoded tapes only the Siege Onager (6.0 s reload) and
# Bombard Cannon (6.5 s) go quiet while enemies are still standing -- they keep firing for
# 0.71 and 0.86 of their opportunity window, where every other unit scores 0.94-1.00. The
# Heavy Scorpion (3.6 s, 70 tapes, 0.94) and Hand Cannoneer (3.45 s, 20 tapes, 0.97) are
# fine, so the boundary sits between 3.6 and 6.0; 4.0 keeps both proven-healthy units out
# while catching every ram/trebuchet/bombard that is too slow to be measured yet.
SIEGE_RELOAD = 4.0
MAX_COUNT = 25                      # positions per side in the golden templates
# The melee template is hand-placed 21v21 in facing blocks, so it has exactly 21 slots a
# side — fewer than the older templates. Trimming to a per-template budget keeps a big
# army from silently arriving under-strength.
TEMPLATE_MAX = {T_MELEE_VS_MELEE.name: 21}


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


def _reload(civ, slug):
    """Imperial reload time for a civ/slug, or 0 if the ref DB has no row."""
    import sqlite3
    ref_db = Path(__file__).resolve().parents[2] / "data" / "golden" / "aoe2_reference.db"
    conn = sqlite3.connect(str(ref_db))
    try:
        for cand in (slug, f"{slug}_{civ.lower()}"):
            row = conn.execute(
                "SELECT final_reload_time FROM ref_units "
                "WHERE civ_name=? AND unit_slug=? AND age='Imperial'", (civ, cand)
            ).fetchone()
            if row is not None:
                return float(row[0] or 0)
    finally:
        conn.close()
    return 0.0


def _is_siege(civ, slug):
    try:
        return _reload(civ, _strip_civ_suffix(civ, slug)) >= SIEGE_RELOAD
    except Exception:
        return False


def _is_melee(civ, slug, flag):
    """Melee = attack range <= 1 (user rule, 2026-07-30).

    Read from the ref DB rather than the unit card's is_ranged flag, because the rule is
    stated in terms of range and the Steppe Lancer — range 1 — is the case that matters:
    it must brawl, not skirmish. The flag is only the fallback when the row is missing."""
    try:
        return _range_speed(civ, _strip_civ_suffix(civ, slug))[0] <= 1.0
    except Exception:
        return not flag


def _swap_army(um, pid, const, keep_n):
    units = list(um.get_player_units(pid))
    if keep_n > len(units):
        # Silently fielding a smaller army than the caller asked for would break equal
        # resources and quietly poison the golden row. Fail the fight instead.
        raise ValueError(f"template has only {len(units)} P{pid} positions, need {keep_n}")
    for u in units[:keep_n]:
        u.unit_const = const
    for u in units[keep_n:]:
        um.remove_unit(unit=u)
    return keep_n


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
    (civ1, key1, _), (civ2, key2, _) = side1, side2
    n1, n2 = counts
    r1, r2 = ranged
    # MELEE vs MELEE gets its own template (2026-07-30). The old golden_infvsinf starts
    # the armies 8.6 tiles apart, so the patrolling side rode in and joined the fight a
    # few at a time and got destroyed piecemeal — measured on Paladin vs Elite Steppe
    # Lancer, where first-contact times spread over 25 s and the Lancers won a matchup
    # the Paladins win in the hand-run game. The new template is hand-placed 21v21 in
    # facing blocks 2 tiles apart, so both armies commit at once.
    # SIEGE first (2026-07-31). A 6-second wind-up does not survive the patrol AI's
    # re-orders: measured on tape, the onagers fire ONE volley and then stand idle for the
    # remaining ~17 s while the enemy keeps hitting them. A 3.45 s Hand Cannoneer on the
    # same patrol slot fires for the whole fight, so this is about reload length, not the
    # AI as such. Both sides go on NoneAi, same layout as golden_rangedvsinf.
    # ...but only for siege that actually SHOOTS. golden_siegevsinf inherits the ranged
    # layout, where P2 starts well back from the enemy — fine for an onager, fatal for a
    # Siege Ram: range 0 with NoneAi means nothing ever orders it to close, so it stands
    # at spawn for the whole fight and swings zero times (measured: 3 ram tapes, active
    # 0.00). Melee siege belongs on the melee template, which starts both sides in contact.
    s1 = _is_siege(civ1, key1) and not _is_melee(civ1, key1, r1)
    s2 = _is_siege(civ2, key2) and not _is_melee(civ2, key2, r2)
    if s1 or s2:
        template = T_SIEGE
        # the siege side takes P2, matching golden_rangedvsinf's ranged-side slot
        p2, p3 = ((civ1, key1, n1), (civ2, key2, n2)) if s1 else \
                 ((civ2, key2, n2), (civ1, key1, n1))
        print(f"[build_v2] siege detected -> {T_SIEGE.name} (NoneAi both sides)", flush=True)
        return _write(scn_template=template, p2=p2, p3=p3, out_path=out_path)
    if _is_melee(civ1, key1, r1) and _is_melee(civ2, key2, r2):
        template = T_MELEE_VS_MELEE
        p2, p3 = (civ1, key1, n1), (civ2, key2, n2)
        return _write(scn_template=template, p2=p2, p3=p3, out_path=out_path)
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

    return _write(scn_template=template, p2=p2, p3=p3, out_path=out_path)


def _write(scn_template, p2, p3, out_path):
    """Apply the (civ, slug, count) sides to a chosen template and write it out."""
    from build_run import unit_const

    template = scn_template
    (p2_civ, p2_slug, p2_n), (p3_civ, p3_slug, p3_n) = p2, p3
    c2 = unit_const(_strip_civ_suffix(p2_civ, p2_slug))
    c3 = unit_const(_strip_civ_suffix(p3_civ, p3_slug))
    p2_n, p3_n = _scale_counts(p2_n, p3_n, TEMPLATE_MAX.get(template.name, MAX_COUNT))

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
    # The melee and siege templates run BOTH sides on NoneAi -- don't label P2 "patrol".
    p2_ai = "NoneAi" if template in (T_MELEE_VS_MELEE, T_SIEGE) else "patrol"
    print(f"[build_v2] {template.name}: P2 {p2_civ}/{p2_slug} x{got2} ({p2_ai}) "
          f"vs P3 {p3_civ}/{p3_slug} x{got3} (NoneAi)", flush=True)
    return out_path
