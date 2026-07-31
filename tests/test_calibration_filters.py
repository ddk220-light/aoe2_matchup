"""Corpus subset filters (aoe2x.calibration.filters).

The load-bearing property is CROSS-LANGUAGE agreement: `calib_runner.mjs
--melee-only` picks which fights to SIM and `score --melee-only` picks which
to SCORE, and if those two ever disagree a scoreboard silently loses (or
invents) fights. Both read data/calibration/fight_sets.json, so these tests
pin the Python half against that file and against the real manifest; the JS
half is pinned by `test_fight_sets_json_is_the_only_definition` below, which
fails if anyone re-hardcodes a slug list in either language.
"""
from __future__ import annotations

import json

import pytest

from aoe2x.calibration import filters as F
from aoe2x.paths import REPO_ROOT

MANIFEST = REPO_ROOT / "data" / "calibration" / "manifest.json"


@pytest.fixture(scope="module")
def fights():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["fights"]


def test_melee_set_matches_fight_sets_json():
    raw = json.loads(F.FIGHT_SETS_PATH.read_text(encoding="utf-8"))
    assert F.MELEE_SLUGS == frozenset(raw["melee"])
    assert F.BASIC_MELEE_SLUGS == frozenset(raw["basic_melee"])
    # basic_melee is documented as a subset of melee; the HP report splits
    # "basic" out of "all melee" and would double-count otherwise.
    assert F.BASIC_MELEE_SLUGS < F.MELEE_SLUGS


def test_elite_fire_lancer_is_not_melee():
    """It has a ranged volley. Its absence is a deliberate, documented call,
    not an oversight -- pin it so a future edit has to argue with a test."""
    assert "elite_fire_lancer" not in F.MELEE_SLUGS


def test_no_filters_selects_everything(fights):
    # "Everything" = everything scoreable: quarantined recordings (known-bad
    # truth) are dropped unconditionally, filters or no filters.
    scoreable = [f for f in fights if not f.get("quarantined")]
    assert F.filter_fights(fights) == scoreable
    assert F.describe_filter() is None


def test_melee_only_is_both_sides(fights):
    sel = F.filter_fights(fights, melee_only=True)
    assert sel, "melee subset must not be empty"
    assert len(sel) < len(fights), "melee subset must be a proper subset"
    for f in sel:
        assert f["side1"]["slug"] in F.MELEE_SLUGS
        assert f["side2"]["slug"] in F.MELEE_SLUGS
    # ...and nothing melee was dropped: a SCOREABLE fight is in iff BOTH
    # sides are (quarantined entries are dropped regardless of composition).
    excluded = [f for f in fights if f not in sel and not f.get("quarantined")]
    for f in excluded:
        assert not (
            f["side1"]["slug"] in F.MELEE_SLUGS and f["side2"]["slug"] in F.MELEE_SLUGS
        )


def test_melee_only_is_the_round4_gate(fights):
    """The pure-melee gate the campaign's KPI is defined over
    (tools/simjs/melee_hp_report.py's docstring). If the corpus grows this
    number legitimately moves -- but it should move deliberately, with the
    report's docstring updated in the same commit.

    History: 31 (original corpus) -> 89 with the 2026-07-30 v2 melee
    re-recording (67 fights, of which 58 are both-sides-melee; fire-lancer
    fights are excluded by the slug set) -> 83 after quarantining the six
    bad-capture paladin_vs_steppe originals."""
    assert len(F.filter_fights(fights, melee_only=True)) == 83


def test_quarantined_fights_are_never_scored(fights):
    """The six 2026-07-30 paladin_vs_steppe captures carry `quarantined` in
    the manifest (opposite winner vs the v2 x12 re-recording + the user's
    live reproduction). They must be dropped from EVERY selection, and an
    explicit --tags request for one must fail loudly, not shrink silently."""
    selected = F.filter_fights(fights)
    assert all(not f.get("quarantined") for f in selected)
    assert any(f.get("quarantined") for f in fights), "fixture: manifest has them"
    quarantined_tag = next(f["tag"] for f in fights if f.get("quarantined"))
    try:
        F.filter_fights(fights, tags=[quarantined_tag])
    except KeyError as exc:
        assert "quarantined" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("explicit quarantined tag must raise")


def test_filters_preserve_manifest_order(fights):
    sel = F.filter_fights(fights, melee_only=True)
    order = [f["run_id"] for f in fights]
    assert [f["run_id"] for f in sel] == [r for r in order
                                          if r in {s["run_id"] for s in sel}]


def test_tags_exact_match(fights):
    tag = fights[0]["tag"]
    sel = F.filter_fights(fights, tags=[tag])
    assert [f["tag"] for f in sel] == [tag]


def test_unknown_tag_raises_rather_than_silently_shrinking(fights):
    """A typo'd tag must not just produce a smaller, plausible-looking run."""
    with pytest.raises(KeyError, match="no-such-tag"):
        F.filter_fights(fights, tags=["no-such-tag"])


def test_match_is_a_regex_on_run_id(fights):
    sel = F.filter_fights(fights, match=r"_r\d$")
    assert sel
    assert all(f["run_id"][-1].isdigit() for f in sel)
    assert len(sel) < len(fights)


def test_filters_combine_with_and(fights):
    both = F.filter_fights(fights, melee_only=True, match="^champion")
    melee = {f["run_id"] for f in F.filter_fights(fights, melee_only=True)}
    champ = {f["run_id"] for f in F.filter_fights(fights, match="^champion")}
    assert {f["run_id"] for f in both} == melee & champ


def test_describe_filter_labels_every_combination():
    assert F.describe_filter(melee_only=True) == "melee-only"
    assert F.describe_filter(tags=["a", "b"]) == "tags=a,b"
    assert F.describe_filter(match="^x") == "match=^x"
    assert F.describe_filter(melee_only=True, match="^x") == "melee-only+match=^x"


def test_slug_set_rejects_unknown_name():
    with pytest.raises(KeyError, match="nope"):
        F.slug_set("nope")


def test_fight_sets_json_is_the_only_definition():
    """No tool may keep a private copy of the melee slug list.

    The three consumers are the JS runner, this module, and the HP report.
    Only fight_sets.json and this module's own loader may contain the
    literal roster; if a copy reappears in a consumer, the two languages can
    drift and `--melee-only` starts meaning two different things.
    """
    roster = {"champion", "halberdier", "paladin", "heavy_camel", "hussar"}
    consumers = [
        REPO_ROOT / "tools" / "simjs" / "calib_runner.mjs",
        REPO_ROOT / "tools" / "simjs" / "calib_worker.mjs",
        REPO_ROOT / "tools" / "simjs" / "melee_hp_report.py",
        REPO_ROOT / "aoe2x" / "calibration" / "score.py",
    ]
    for path in consumers:
        text = path.read_text(encoding="utf-8")
        # A copy of the set would mention every one of the five basic slugs.
        present = {s for s in roster if f'"{s}"' in text or f"'{s}'" in text}
        assert present != roster, (
            f"{path.name} looks like it re-hardcodes the melee slug roster; "
            "it must read data/calibration/fight_sets.json instead"
        )
