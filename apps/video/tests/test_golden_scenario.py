# apps/video/tests/test_golden_scenario.py
"""Game-free build of a golden-template matchup scenario, verified by reading the
written .aoe2scenario back with AoE2ScenarioParser (mirrors
ai_experiments/tools/verify_matchups.py).

Needs AoE2ScenarioParser -> run with apps/video/.venv:
    apps/video/.venv/Scripts/python.exe -m pytest apps/video/tests/test_golden_scenario.py -q
or, since that venv has no pytest, run the file directly (it self-executes):
    apps/video/.venv/Scripts/python.exe apps/video/tests/test_golden_scenario.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    from AoE2ScenarioParser.datasets.object_support import Civilization
    from AoE2ScenarioParser.datasets.effects import EffectId
    from AoE2ScenarioParser import settings
    settings.PRINT_STATUS_UPDATES = False
except ImportError:  # not installed in the system python -> skip under pytest,
    if __name__ != "__main__":  # but still runnable via apps/video/.venv (see header)
        import pytest
        pytest.skip("AoE2ScenarioParser unavailable (run with apps/video/.venv)",
                    allow_module_level=True)
    raise

from build_golden_matchups import build_golden_scenario


def test_build_golden_scenario(tmp_path):
    # sample pair: Elite Temple Guard (Muisca, melee) vs Mangudai (Mongols, ranged),
    # storyboard-scale counts that exceed the 21 ceiling so scaling is exercised.
    p2_side = ("Mongols", "mangudai", 30)          # ranged -> kiter slot P2
    p3_side = ("Muisca", "elite_temple_guard_muisca", 26)   # melee -> P3
    out = tmp_path / "golden_test.aoe2scenario"
    build_golden_scenario(p2_side, p3_side, out)
    assert out.exists()

    scn = AoE2DEScenario.from_file(str(out))
    um, pm, tm = scn.unit_manager, scn.player_manager, scn.trigger_manager
    pd2 = scn.sections["PlayerDataTwo"]

    def civ(pid):
        return next(p for p in pm.players if int(p.player_id) == pid).civilization

    # unit consts (from build_run.unit_const): Mangudai=11 on P2,
    # Elite Temple Guard=2587 on P3
    p2 = Counter(u.unit_const for u in um.get_player_units(2))
    p3 = Counter(u.unit_const for u in um.get_player_units(3))
    assert list(p2) == [11], p2
    assert list(p3) == [2587], p3

    # counts scaled by the same factor so both <= 21 (max ceiling)
    n2 = sum(p2.values())
    n3 = sum(p3.values())
    assert 0 < n2 <= 21 and 0 < n3 <= 21, (n2, n3)
    # the larger side (30) is the one that hits the 21 ceiling
    assert n2 == 21, n2

    # civs: P2 = Mongols, P3 = Muisca, P1 == P3
    assert civ(2) == Civilization.MONGOLS, civ(2)
    assert civ(3) == Civilization.MUISCA, civ(3)
    assert civ(1) == civ(3), (civ(1), civ(3))

    # both AI slots = ddkModelAI.ai / type 0
    for pid in (2, 3):
        assert pd2.ai_names[pid - 1] == "ddkModelAI.ai", pd2.ai_names[pid - 1]
        assert pd2.ai_type[pid - 1] == 0, pd2.ai_type[pid - 1]

    # exactly one trigger, carrying one CHANGE_VIEW (camera) effect
    assert len(tm.triggers) == 1, len(tm.triggers)
    cam = [e for t in tm.triggers for e in t.effects
           if int(e.effect_type) == int(EffectId.CHANGE_VIEW)]
    assert len(cam) == 1, len(cam)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_build_golden_scenario(Path(td))
    print("test_build_golden_scenario PASSED")
