"""One-shot: retarget the golden templates from ddkSquareV25 -> ddkMatchupAI.

Rewrites all THREE AI storage locations consistently (see MATCHUP_SCENARIO_SYSTEM.md):
  1. PlayerDataTwo.ai_names[slot]                  'ddkSquareV25.ai' -> 'ddkMatchupAI.ai'
  2. PlayerDataTwo.ai_files[slot].ai_per_file_text -> ddkMatchupAI.per content
  3. Files.ai_files[i].{ai_file_name, ai_file}     -> 'ddkMatchupAI.per' + content
The AI content is byte-identical to ddkSquareV25 except two comment lines, so behavior is
unchanged; only the name moves to the production one.
"""
from pathlib import Path
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser import settings
settings.PRINT_STATUS_UPDATES = False

REPO = Path(__file__).resolve().parent
TEMPLATES = REPO / "templates"
with (REPO / "ai_experiments" / "ddkMatchupAI.per").open(encoding="utf-8", newline="") as f:
    PER = f.read()

OLD_AI, NEW_AI = "ddkSquareV25.ai", "ddkMatchupAI.ai"
OLD_PER, NEW_PER = "ddkSquareV25.per", "ddkMatchupAI.per"

for name in ("golden_infvsinf", "golden_rangedvsinf", "golden_cavvsranged"):
    path = TEMPLATES / f"{name}.aoe2scenario"
    scn = AoE2DEScenario.from_file(str(path))
    pd2 = scn.sections["PlayerDataTwo"]
    hits = []
    for slot in range(16):
        if pd2.ai_names[slot] == OLD_AI:
            pd2.ai_names[slot] = NEW_AI
            pd2.retriever_map["ai_files"].data[slot].retriever_map["ai_per_file_text"].data = PER
            hits.append(f"slot{slot}(P{slot+1})")
    frm = scn.sections["Files"].retriever_map
    for e in frm["ai_files"].data:
        if e.retriever_map["ai_file_name"].data == OLD_PER:
            e.retriever_map["ai_file_name"].data = NEW_PER
            e.retriever_map["ai_file"].data = PER
            hits.append("Files-entry")
    assert len(hits) == 2, f"{name}: expected 1 slot + 1 Files entry, got {hits}"
    tmp = path.with_name(f"{name}.new.aoe2scenario")   # parser disallows same-path overwrite
    scn.write_to_file(str(tmp))
    tmp.replace(path)
    print(f"{name}: retargeted {hits} -> {NEW_AI}")
print("done")
