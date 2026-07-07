"""Unit tests for the reel matchup-selection rule (pure logic, no ffmpeg)."""
import json
from pathlib import Path

import pytest

from auto.build_reel import select_reel_matchups, _footage_verdict

REPO = Path(__file__).resolve().parents[3]
ETG_CAT = REPO / "apps" / "video" / "sim_v2" / "results" / "elite_temple_guard_muisca.json"


def _row(slug, name):
    return {"slug": slug, "name": name, "civ": "X"}


def test_prefers_one_unexpected_of_each_valence():
    cat = {"showcase": {
        "unexpected_win": [_row("a", "A")],
        "unexpected_loss": [_row("b", "B")],
        "expected_win": [_row("c", "C")],
        "expected_loss": [_row("d", "D")],
    }}
    picks = select_reel_matchups(cat)
    assert [k for k, _ in picks] == ["unexpected_win", "unexpected_loss"]


def test_lone_unexpected_loss_pairs_with_expected_win():
    cat = {"showcase": {
        "unexpected_loss": [_row("b", "B")],
        "expected_win": [_row("c", "C")],
        "expected_loss": [_row("d", "D")],
    }}
    picks = select_reel_matchups(cat)
    assert [k for k, _ in picks] == ["unexpected_loss", "expected_win"]


def test_lone_unexpected_win_pairs_with_expected_loss():
    cat = {"showcase": {
        "unexpected_win": [_row("a", "A")],
        "expected_win": [_row("c", "C")],
        "expected_loss": [_row("d", "D")],
    }}
    picks = select_reel_matchups(cat)
    assert [k for k, _ in picks] == ["unexpected_win", "expected_loss"]


def test_no_surprises_shows_the_units_range():
    cat = {"showcase": {
        "expected_win": [_row("c", "C")],
        "expected_loss": [_row("d", "D")],
    }}
    picks = select_reel_matchups(cat)
    assert [k for k, _ in picks] == ["expected_win", "expected_loss"]


def test_capped_at_two():
    cat = {"showcase": {k: [_row(k, k)] for k in
                        ("unexpected_win", "unexpected_loss", "expected_win", "expected_loss")}}
    assert len(select_reel_matchups(cat)) == 2


def test_footage_verdict_matches_who_actually_won():
    # subject favoured -> win is expected, loss is the surprise
    assert _footage_verdict("subject", True) == "expected_win"
    assert _footage_verdict("subject", False) == "unexpected_loss"
    # opponent (or both) favoured -> a subject win is the surprise
    assert _footage_verdict("opponent", True) == "unexpected_win"
    assert _footage_verdict("opponent", False) == "expected_loss"
    assert _footage_verdict("both", True) == "unexpected_win"
    # nobody favoured -> plain win/loss
    assert _footage_verdict("neither", True) == "win"
    assert _footage_verdict("neither", False) == "loss"


@pytest.mark.skipif(not ETG_CAT.exists(), reason="ETG categorization JSON not present")
def test_temple_guard_real_categorization():
    cat = json.load(open(ETG_CAT))
    picks = select_reel_matchups(cat)
    kinds = [k for k, _ in picks]
    # ETG has 0 unexpected wins, 2 unexpected losses -> lone loss + best expected win
    assert kinds == ["unexpected_loss", "expected_win"]
    assert picks[0][1]["slug"] == "elite_cataphract_byzantines"
