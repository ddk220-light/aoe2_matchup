"""Corpus subset filters (aoe2x.calibration.filters).

The load-bearing property is CROSS-LANGUAGE agreement: `calib_runner.mjs
--melee-only` picks which fights to SIM and `score --melee-only` picks which
to SCORE, and if those two ever disagree a scoreboard silently loses (or
invents) fights. Both read calibration/fixtures/fight_sets.json, so these tests
pin the Python half against that file and against the real manifest; the JS
half is pinned by `test_fight_sets_json_is_the_only_definition` below, which
fails if anyone re-hardcodes a slug list in either language.
"""
from __future__ import annotations

import json

import pytest

from aoe2x.calibration import filters as F
from aoe2x.calibration.paths import workspace_paths
from aoe2x.paths import REPO_ROOT

MANIFEST = workspace_paths().manifest
SOURCE_LOCK = workspace_paths().source_lock


@pytest.fixture(scope="module")
def fights():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["fights"]


def test_manifest_uses_only_the_final_tape_source(fights):
    lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
    expected_hash = lock["sha256"]

    assert len(fights) == lock["recordings"] == 339
    assert len({f["run_id"] for f in fights}) == 339
    assert {f["zip_sha256"].upper() for f in fights} == {expected_hash}
    assert {f["source_archive"] for f in fights} == {
        "aoe2_golden_STANDARD_UNITS_FINAL.zip"
    }
    assert all(not f.get("quarantined") for f in fights)


def test_melee_set_matches_fight_sets_json():
    raw = json.loads(workspace_paths().fight_sets.read_text(encoding="utf-8"))
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


def test_melee_only_is_the_final_gate(fights):
    """FINAL is the sole corpus: 78 recordings carry the archive's broad
    ``melee`` class, while this project's stricter pure-melee filter excludes
    seven Elite Fire Lancer recordings because that unit has a ranged volley.
    The resulting 71-fight gate is pinned deliberately and must move only when
    the user replaces FINAL itself."""
    assert len(F.filter_fights(fights, melee_only=True)) == 71


def test_quarantined_fights_are_never_scored(fights):
    """FINAL contains no quarantined recordings, so exercise the filter with
    a synthetic quarantine marker rather than depending on an obsolete tape."""
    scoreable = fights[0]
    quarantined = {
        **fights[1],
        "tag": "synthetic_quarantined_tape",
        "run_id": "synthetic_quarantined_tape",
        "quarantined": True,
    }
    sample = [scoreable, quarantined]

    assert F.filter_fights(sample) == [scoreable]
    with pytest.raises(KeyError, match="quarantined"):
        F.filter_fights(sample, tags=[quarantined["tag"]])


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


def test_slug_set_reads_an_explicit_local_workspace(tmp_path):
    paths = workspace_paths(tmp_path / "calibration")
    paths.fixtures_dir.mkdir(parents=True)
    paths.fight_sets.write_text(
        json.dumps({"melee": ["local_only"]}), encoding="utf-8"
    )

    assert F.slug_set("melee", paths=paths) == frozenset({"local_only"})


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
            "it must read calibration/fixtures/fight_sets.json instead"
        )
