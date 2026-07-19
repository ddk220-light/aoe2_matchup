"""Build the 4 matchup TEMPLATE scenarios, one per (P2 type, P3 type) combination.

Two source layouts (both 16x16, P1 = spectator w/ map revealers):
  NEW  = the user's freshly-made golden_template in the AoE2 save folder:
         30 units/side, P2 = RANGED in the TOP area, P3 = MELEE in the BOTTOM.
  OLD  = repo templates/golden_template.aoe2scenario: 21 units/side (symmetric-ish).

Personalities (baked into each template; the scenario generator leaves AI untouched):
  RANGED in TOP    -> ddkCircleModel.ai     (type 0, CLOCKWISE square patrol, = ddkSquareV25)
  RANGED in BOTTOM -> ddkCircleModelCCW.ai  (type 0, ANTICLOCKWISE twin)
  MELEE            -> PromiDE               (type 1, the built-in DE "standard" AI)

NO position swapping (2026-07-08: the swap looked jarring). Base positions are always kept
(P2 = TOP, P3 = BOTTOM). To make the ranged ball kite AWAY from its enemy regardless of which
band it sits in, the ranged side picks its rotation by band: TOP ball (enemy below) = clockwise;
BOTTOM ball (enemy above) = anticlockwise.

Outputs -> apps/video/templates/ (all from NEW; the OLD 840 KB template crashes the current
build -- see MATCHUP_SCENARIO_SYSTEM.md):
  ranged_vs_melee.aoe2scenario   P2=circle CW (ranged, TOP)      P3=PromiDE (melee, BOTTOM)
  melee_vs_ranged.aoe2scenario   P2=PromiDE (melee, TOP)         P3=circle CCW (ranged, BOTTOM)
  ranged_vs_ranged.aoe2scenario  P2=PromiDE                      P3=PromiDE
  melee_vs_melee.aoe2scenario    P2=PromiDE                      P3=PromiDE

The circle AIs are used ONLY in the asymmetric mixed matchups (ranged kites melee). Symmetric
matchups (RvR, MvM) run PromiDE on both sides -- no kiting needed. (RvR/MvM currently crash on
load; cause under investigation -- see build_crash_diagnostics.py.)
"""
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

REPO = Path(__file__).resolve().parent                     # apps/video
TEMPLATES = REPO / "templates"
NEW_SRC = Path(r"C:\Users\ddk22\Games\Age of Empires 2 DE"
               r"\76561198690498042\resources\_common\scenario\golden_template.aoe2scenario")
OLD_SRC = TEMPLATES / "golden_template.aoe2scenario"

CIRCLE     = ("ddkCircleModel.ai", 0)     # ranged, TOP band -> clockwise patrol
CIRCLE_CCW = ("ddkCircleModelCCW.ai", 0)  # ranged, BOTTOM band -> anticlockwise patrol
STANDARD   = ("PromiDE", 1)               # built-in DE standard AI — PROVEN ONLY ON P3.
# ⭐ PromiDE on the P2 slot crashes DE on load even with all three AI storage locations
# (ai_names/ai_type, per-slot blob, Files section) fully consistent — engine-side, cause
# unknown (exhaustive P2-vs-P3 data diff is clean). P2 must therefore run a custom .per.
# ddkModelAI: melee armies hit its fallback (engine auto-fight after ~10s, in-game confirmed
# 2026-07-05); ranged armies kite (its native behavior).
MODEL      = ("ddkModelAI.ai", 0)

def _promide_blob():
    """The PromiDE loader script, taken from the NEW template's P3 slot (a known-good
    PromiDE slot set up in the editor)."""
    scn = AoE2DEScenario.from_file(str(NEW_SRC))
    pd2 = scn.sections["PlayerDataTwo"]
    blob = pd2.retriever_map["ai_files"].data[2].retriever_map["ai_per_file_text"].data
    assert blob and "Promisory" in blob, f"unexpected PromiDE blob ({len(blob or '')} chars)"
    return blob

PROMIDE_BLOB = _promide_blob()

AI_EXPERIMENTS = REPO / "ai_experiments"

def set_ai(scn, pid, personality):
    """Assign a slot's AI: name + type + the EMBEDDED per-slot script blob.

    ⭐ ROOT CAUSE of the 2026-07-08 load crashes: scenarios embed each slot's AI script in
    PlayerDataTwo.ai_files[slot].ai_per_file_text. The editor put the full 51 KB custom .per
    in P2's slot; changing only ai_names/ai_type to "PromiDE" left that custom blob under a
    builtin AI name -> native BugSplat on load (no log). A PromiDE slot must carry the PromiDE
    loader blob; a custom slot gets its own .per content.
    """
    pd2 = scn.sections["PlayerDataTwo"]
    name, ai_type = personality
    pd2.ai_names[pid - 1], pd2.ai_type[pid - 1] = name, ai_type
    if ai_type == 1 and name == "PromiDE":
        blob = PROMIDE_BLOB
    else:  # custom .per: embed the real script content (name is "<file>.ai" -> <file>.per)
        per = AI_EXPERIMENTS / (name.removesuffix(".ai") + ".per")
        with per.open(encoding="utf-8", newline="") as f:   # keep CRLF exactly as on disk
            blob = f.read()
    pd2.retriever_map["ai_files"].data[pid - 1].retriever_map["ai_per_file_text"].data = blob

def sync_files_section(scn, personalities):
    """⭐ THIRD place scenarios store AI data: the trailing Files section embeds
    <name>.per entries (ai_file_name + full content). The editor left ddkSquareV25.per
    there; a stale/orphaned entry that doesn't match the slot assignments crashes DE on
    load (this — not PlayerDataTwo alone — was the remaining crasher after the blob fix).
    Rewrite it to exactly the custom AIs in use; empty (present=0) when all-builtin,
    mirroring what the editor writes for a builtin-only scenario."""
    rm = scn.sections["Files"].retriever_map
    customs = [name for name, ai_type in personalities if ai_type == 0]
    entries = rm["ai_files"].data
    if not customs:
        rm["ai_files_present"].data = 0
        rm["number_of_ai_files"].data = []
        rm["ai_files"].data = []
        return
    import copy
    while len(entries) < len(customs):        # clone the template's entry struct as needed
        entries.append(copy.deepcopy(entries[0]))
    for entry, name in zip(entries, customs):
        per = AI_EXPERIMENTS / (name.removesuffix(".ai") + ".per")
        with per.open(encoding="utf-8", newline="") as f:
            content = f.read()
        entry.retriever_map["ai_file_name"].data = per.name
        entry.retriever_map["ai_file"].data = content
    rm["ai_files_present"].data = 1
    rm["number_of_ai_files"].data = len(customs)
    rm["ai_files"].data = entries[:len(customs)]

def swap_p2_p3(scn):
    """Swap ownership of every P2 unit with every P3 unit (snapshot lists first)."""
    um = scn.unit_manager
    p2 = list(um.get_player_units(2))
    p3 = list(um.get_player_units(3))
    for u in p2:
        um.change_ownership(u, 3)
    for u in p3:
        um.change_ownership(u, 2)

def build(src, out_name, p2_ai, p3_ai, swap=False):
    scn = AoE2DEScenario.from_file(str(src))
    if swap:
        swap_p2_p3(scn)
    set_ai(scn, 2, p2_ai)
    set_ai(scn, 3, p3_ai)
    sync_files_section(scn, [p2_ai, p3_ai])
    out = TEMPLATES / out_name
    if out.exists():
        out.unlink()
    scn.write_to_file(str(out))
    # report
    um = scn.unit_manager
    n2 = len(list(um.get_player_units(2)))
    n3 = len(list(um.get_player_units(3)))
    print(f"{out_name:30s}  P2={p2_ai[0]:18s}(x{n2})  P3={p3_ai[0]:18s}(x{n3})")

if __name__ == "__main__":
    # ALL FOUR derive from NEW_SRC. The OLD 840 KB repo golden_template carries ~800 KB of
    # stale embedded data (background image / files blob) that the CURRENT game build crashes
    # on at load (confirmed 2026-07-08: OLD-derived MvM/RvR crash, NEW-derived RvM loads fine;
    # both are scenario_version 1.58 so it is NOT a version/unit-count issue). NEW is the
    # user's freshly-made 26 KB template and loads cleanly, with 30 units/side both top & bottom.
    build(NEW_SRC, "ranged_vs_melee.aoe2scenario",  CIRCLE, STANDARD)     # P2 ranged TOP = CW circle
    build(NEW_SRC, "melee_vs_ranged.aoe2scenario",  MODEL,  CIRCLE_CCW)   # P2 melee = fallback fighter, P3 ranged BOTTOM = CCW
    build(NEW_SRC, "ranged_vs_ranged.aoe2scenario", MODEL,  STANDARD)     # P2 ranged = kiter (custom), P3 = standard
    build(NEW_SRC, "melee_vs_melee.aoe2scenario",    MODEL,  STANDARD)     # P2 melee = fallback fighter, P3 = standard
    print("done -> apps/video/templates/")
