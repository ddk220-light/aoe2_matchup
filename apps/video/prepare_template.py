"""prepare_template.py — one-time cleanup of the golden matchup template.

The golden template (`templates/template_landscape_jungle.aoe2scenario`) is the
hand-decorated jungle battlefield the user built in the in-game Scenario Editor.
It carries a `Setup` trigger that researches a universal combat-tech set for both
fighting players — but the armies start in the **Post-Imperial age**, so every
relevant upgrade is already applied automatically. Those research effects are
therefore redundant; this strips them so the template is clean.

It does NOT touch the map, decoration, units, players, or the other triggers
(diplomacy / camera / title / countdown / win conditions). Run once after pulling
a fresh template out of the editor; the result is committed to the repo.

    python prepare_template.py            # cleans templates/template_landscape_jungle.aoe2scenario in place
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.effects import EffectId

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "templates" / "template_landscape_jungle.aoe2scenario"
RESEARCH = int(EffectId.RESEARCH_TECHNOLOGY)  # effect type 2


def strip_tech_effects(scn) -> int:
    """Remove every RESEARCH_TECHNOLOGY effect from every trigger. Returns count."""
    removed = 0
    for trig in scn.trigger_manager.triggers:
        kept = []
        for eff in trig.effects:
            et = eff.effect_type
            et = int(et) if not isinstance(et, int) else et
            if et == RESEARCH:
                removed += 1
            else:
                kept.append(eff)
        trig.effects = kept
    return removed


def main(path: Path = TEMPLATE) -> None:
    if not path.exists():
        sys.exit(f"template not found: {path}")
    scn = AoE2DEScenario.from_file(str(path))
    n = strip_tech_effects(scn)
    # the parser refuses to overwrite its own source file, so write to a sibling
    # temp file and atomically move it into place.
    fd, tmp = tempfile.mkstemp(suffix=".aoe2scenario", dir=str(path.parent))
    os.close(fd)
    os.unlink(tmp)  # parser also refuses to overwrite an existing file
    scn.write_to_file(tmp)
    os.replace(tmp, str(path))
    print(f"removed {n} RESEARCH_TECHNOLOGY effect(s) -> {path.name}")


if __name__ == "__main__":
    main()
