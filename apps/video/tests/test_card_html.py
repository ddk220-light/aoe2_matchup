# apps/video/tests/test_card_html.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overlay.render_card import (
    build_category_banner_html, build_caption_pill_html,
    build_ranked_list_html,
)


def test_banner_contains_title_and_index():
    h = build_category_banner_html("Unexpected Counters", 4, 4)
    assert "Unexpected Counters" in h and "4/4" in h


def test_caption_pill_escapes_and_includes_text():
    h = build_caption_pill_html("Obuch strips 1 armor per hit — the tank <breaks>")
    assert "strips 1 armor per hit" in h and "<breaks>" not in h


def test_ranked_list_rows_and_pick_marker():
    rows = [{"rank": 1, "name": "Elite Skirmisher", "civ": "Armenians",
             "score": 81.0, "picked": False},
            {"rank": 2, "name": "Heavy Camel Rider", "civ": "Persians",
             "score": 79.1, "picked": True}]
    h = build_ranked_list_html("Expected Wins — full ranking", rows)
    assert "Elite Skirmisher" in h and "Heavy Camel Rider" in h
    assert h.index("Elite Skirmisher") < h.index("Heavy Camel Rider")
    assert "picked" in h            # css class marks recorded entries
