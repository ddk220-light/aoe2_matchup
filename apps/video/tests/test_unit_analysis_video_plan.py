# apps/video/tests/test_unit_analysis_video_plan.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto.run_unit_analysis_video import build_plan

SB = {
    "schema_version": 1,
    "subject": {"civ": "Muisca", "slug": "elite_temple_guard_muisca",
                "name": "Elite Temple Guard", "stats": {}},
    "segments": [
        {"order": 1, "category": "expected_win", "rank": 1,
         "opponent": {"civ": "Persians", "slug": "heavy_camel",
                      "name": "Heavy Camel Rider"},
         "score": 79.1, "counts": {"subject": 26, "opponent": 37},
         "why": "bonus applies", "why_factors": {}},
        {"order": 2, "category": "unexpected_counter", "rank": 1,
         "opponent": {"civ": "Poles", "slug": "elite_obuch_poles",
                      "name": "Elite Obuch"},
         "score": -42.2, "counts": {"subject": 26, "opponent": 33},
         "why": "armor strip", "why_factors": {}},
    ],
    "category_lists": {
        "expected_win": [{"rank": 1, "name": "Heavy Camel Rider",
                          "civ": "Persians", "slug": "heavy_camel",
                          "score": 79.1, "picked": True}],
        "unexpected_win": [], "expected_counter": [],
        "unexpected_counter": [{"rank": 1, "name": "Elite Obuch",
                                "civ": "Poles", "slug": "elite_obuch_poles",
                                "score": -42.2, "picked": True}],
        "even": [{"rank": 1, "name": "Elite Berserk", "civ": "Vikings",
                  "slug": "elite_berserk_vikings", "score": 0.4,
                  "picked": False}],
    },
}


def test_build_plan_orders_and_labels(tmp_path):
    sb_path = tmp_path / "sb.json"
    sb_path.write_text(json.dumps(SB))
    plan = build_plan(sb_path)
    kinds = [step["kind"] for step in plan]
    # intro first, then per category: banner -> fights -> ranked card; even card last
    assert kinds[0] == "intro"
    assert kinds[1] == "banner" and plan[1]["category"] == "expected_win"
    assert kinds[2] == "fight" and plan[2]["spec"]["slug2"] == "heavy_camel"
    assert "ranked_card" in kinds and kinds[-1] == "even_card"
    fight = plan[2]["spec"]
    assert fight["label"] == "Expected Win #1 — Heavy Camel Rider"
    assert fight["category"] == "expected_win" and fight["why"] == "bonus applies"
