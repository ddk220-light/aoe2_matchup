"""GOLDEN: the Elite Temple Guard storyboard, built from the real batch
baseline, must reproduce the locked 12 picks and cover every pool opponent.

Locked spec: docs/superpowers/specs/2026-07-05-etg-picks-locked.md
Reference dry run: docs/superpowers/specs/2026-07-05-etg-dbsource-dryrun.py
"""
import os

import pytest

from aoe2x.analysis.matchup_sources import MatchupDbSource
from aoe2x.analysis.unit_video_story import build_storyboard

MATCHUP_DB = r"C:\AI\matchup_baseline_177723.db"

pytestmark = pytest.mark.skipif(
    not os.path.exists(MATCHUP_DB),
    reason=f"golden matchup baseline not present: {MATCHUP_DB}")

SUBJECT_CIV, SUBJECT_SLUG = "Muisca", "elite_temple_guard_muisca"

# The FINAL 12 PICKS table (locked 2026-07-05). (slug, civ) per category.
LOCKED = {
    "expected_win": [
        ("heavy_camel", "Persians"),
        ("elite_tarkan_huns", "Huns"),
        ("elite_shrivamsha_rider_gurjaras", "Gurjaras"),
    ],
    "unexpected_win": [
        ("elite_white_feather_guard_shu", "Shu"),
        ("elite_ibirapema_warrior_tupi", "Tupi"),
        ("elite_huskarl_goths", "Goths"),
    ],
    "expected_counter": [
        ("grenadier_jurchens", "Jurchens"),
        ("elite_chakram_thrower_gurjaras", "Gurjaras"),
        ("elite_chu_ko_nu_chinese", "Chinese"),
    ],
    "unexpected_counter": [
        ("elite_urumi_swordsman_dravidians", "Dravidians"),
        ("elite_obuch_poles", "Poles"),
        ("elite_serjeant_sicilians", "Sicilians"),
    ],
}

CATEGORY_ORDER = ("expected_win", "unexpected_win",
                  "expected_counter", "unexpected_counter")


@pytest.fixture(scope="module")
def storyboard():
    src = MatchupDbSource(MATCHUP_DB)
    return build_storyboard(SUBJECT_CIV, SUBJECT_SLUG, src,
                            matchup_db_name="matchup_baseline_177723.db")


def test_schema_and_subject(storyboard):
    assert storyboard["schema_version"] == 1
    assert storyboard["build"] == "177723"
    assert storyboard["subject"]["slug"] == SUBJECT_SLUG
    assert storyboard["subject"]["name"] == "Elite Temple Guard"
    assert storyboard["subject"]["stats"]["cat"] == "infantry"
    assert storyboard["generated"]["source"] == "MatchupDbSource"
    assert storyboard["generated"]["scale"] == "3k"


def test_twelve_segments_in_narrative_order(storyboard):
    segs = storyboard["segments"]
    assert len(segs) == 12
    cats = [s["category"] for s in segs]
    assert cats == (["expected_win"] * 3 + ["unexpected_win"] * 3
                    + ["expected_counter"] * 3 + ["unexpected_counter"] * 3)
    assert [s["order"] for s in segs] == list(range(1, 13))


def test_locked_twelve_picks(storyboard):
    segs = storyboard["segments"]
    got = {cat: [] for cat in CATEGORY_ORDER}
    for s in segs:
        got[s["category"]].append((s["opponent"]["slug"], s["opponent"]["civ"]))
    for cat in CATEGORY_ORDER:
        assert got[cat] == LOCKED[cat], f"{cat} picks drifted from locked spec"


def test_expected_counter_is_curated_mix_not_margin_sort(storyboard):
    # The curated MIX ignores raw margin order (grenadier -100, chakram -94,
    # chu ko nu -93) and is a gunpowder + 2 archers trio.
    ec = [s["opponent"]["slug"] for s in storyboard["segments"]
          if s["category"] == "expected_counter"]
    assert ec == ["grenadier_jurchens", "elite_chakram_thrower_gurjaras",
                  "elite_chu_ko_nu_chinese"]


def test_category_lists_cover_all_75_pool_slugs(storyboard):
    lists = storyboard["category_lists"]
    assert set(lists.keys()) == {
        "expected_win", "unexpected_win", "expected_counter",
        "unexpected_counter", "even"}
    all_slugs = [u["slug"] for lst in lists.values() for u in lst]
    assert len(all_slugs) == 75
    assert len(set(all_slugs)) == 75
    # all_results is the same population
    assert len(storyboard["all_results"]) == 75
    assert set(all_slugs) == {r["slug"] for r in storyboard["all_results"]}


def test_each_segment_carries_recorder_fields(storyboard):
    for s in storyboard["segments"]:
        assert s["counts"]["subject"] > 0 and s["counts"]["opponent"] > 0
        assert isinstance(s["why"], str) and s["why"]
        assert "subject" in s["hp_left"] and "opponent" in s["hp_left"]
        assert s["n"] is not None


def test_picked_flag_matches_segments(storyboard):
    picked = {u["slug"] for lst in storyboard["category_lists"].values()
              for u in lst if u["picked"]}
    seg_slugs = {s["opponent"]["slug"] for s in storyboard["segments"]}
    assert picked == seg_slugs
