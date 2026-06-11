"""End-to-end regression test: derived scores for Viking Elite Berserk
must match the locked-in reference values.

Reads a small committed fixture (`tests/fixtures/berserker_matchups.db`)
containing the Vikings Elite Berserk matchup rows extracted from the
build-177723 matchup baseline. The fixture decouples this guardrail from
the volatile, non-committed `webapp/matchup_db.db` (a disposable local sim
cache that may hold a partial unit set). Pinned values are the current-sim
derivation of those fixture rows. This is the canonical guardrail that future
refactors of `derive_unit_scores` must preserve.

To regenerate after an intentional derivation change: rebuild the fixture from
the current baseline and re-pin the values below from the printed output.
"""
import os
import pytest
import sqlite3

from aoe2x.rank.derive_pool_scores import _fetch_unit_rows
from aoe2x.rank.pool_scores_lib import derive_unit_scores

MATCHUP_DB = os.path.join(
    os.path.dirname(__file__), "fixtures", "berserker_matchups.db",
)


@pytest.fixture(scope="module")
def berserker_rows_30v30():
    if not os.path.exists(MATCHUP_DB):
        pytest.skip(f"{MATCHUP_DB} not present")
    conn = sqlite3.connect(MATCHUP_DB)
    rows = _fetch_unit_rows(conn, "Vikings", "elite_berserk_vikings", "30v30")
    conn.close()
    return rows


@pytest.fixture(scope="module")
def berserker_rows_3k():
    if not os.path.exists(MATCHUP_DB):
        pytest.skip(f"{MATCHUP_DB} not present")
    conn = sqlite3.connect(MATCHUP_DB)
    rows = _fetch_unit_rows(conn, "Vikings", "elite_berserk_vikings", "3k")
    conn.close()
    return rows


def _by_axis(out_rows):
    return {r["axis"]: r for r in out_rows}


def test_berserker_pop_hp_score(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    assert hp["pool"] == "infantry"
    assert hp["final_score"] == pytest.approx(5.84, abs=0.5)
    assert hp["gc"] == pytest.approx(-11.02, abs=0.5)
    assert hp["ac"] == pytest.approx(-2.47, abs=0.5)
    assert hp["at"] == pytest.approx(92.85, abs=0.5)


def test_berserker_cost_hp_score(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    hp = _by_axis(out)["hp"]
    assert hp["final_score"] == pytest.approx(28.35, abs=0.5)
    assert hp["gc"] == pytest.approx(12.75, abs=0.5)
    assert hp["ac"] == pytest.approx(35.92, abs=0.5)
    assert hp["at"] == pytest.approx(93.58, abs=0.5)


def test_berserker_pop_cost_axis(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    cost = _by_axis(out)["cost"]
    # Re-pinned 2026-06-10: cost weights aligned to simulation_real
    # (wood 0.8 -> 0.7); was 4219.5 under the old 0.8 coefficient.
    assert cost["final_score"] == pytest.approx(4204.2, abs=10.0)


def test_berserker_cost_cost_axis(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    cost = _by_axis(out)["cost"]
    # Re-pinned 2026-06-10: cost weights aligned to simulation_real
    # (wood 0.8 -> 0.7); was 2763.3 under the old 0.8 coefficient.
    assert cost["final_score"] == pytest.approx(2751.4, abs=10.0)


def test_berserker_pop_speed_axis(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    sp = _by_axis(out)["speed"]
    assert sp["final_score"] == pytest.approx(-8.27, abs=0.5)


def test_berserker_cost_speed_axis(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    sp = _by_axis(out)["speed"]
    assert sp["final_score"] == pytest.approx(17.48, abs=0.5)


def test_berserker_shape_descriptors_pop(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    # Build-177723 baseline fixture: n=266, win-rate=58.27%, cat-loss=27.82%.
    # Tolerances allow for minor dedup-ordering and population differences.
    assert hp["n"] >= 200  # full population, exact n depends on dedup
    assert hp["win_rate"] == pytest.approx(58.27, abs=3.0)
    assert hp["catastrophic_loss_rate"] == pytest.approx(27.82, abs=3.0)


def test_berserker_pop_hp_per_line_means(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    rlm = hp["role_line_means"]
    # GC has militia/knight/archer.
    assert "GC" in rlm and set(rlm["GC"].keys()) == {"militia", "knight", "archer"}
    # AC has knight/camel/steppe_lancer/elephant.
    assert set(rlm["AC"].keys()) == {"knight", "camel", "steppe_lancer", "elephant"}
    # AT has spear/skirmisher/light_cav.
    assert set(rlm["AT"].keys()) == {"spear", "skirmisher", "light_cav"}
    # All values either float or None.
    for role_dict in rlm.values():
        for v in role_dict.values():
            assert v is None or isinstance(v, (int, float))


def test_berserker_pop_hp_per_line_means_pinned(berserker_rows_30v30):
    """Pin the actual GC-line values for the 30v30 HP axis as a regression guardrail."""
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    gc = hp["role_line_means"]["GC"]
    # PIN: build-177723 baseline fixture derivation. Tolerance 0.5.
    expected_militia = 16.578723404255317
    expected_knight  = -21.039473684210527
    expected_archer  = -28.60222222222222
    assert gc["militia"] == pytest.approx(expected_militia, abs=0.5)
    assert gc["knight"]  == pytest.approx(expected_knight,  abs=0.5)
    assert gc["archer"]  == pytest.approx(expected_archer,  abs=0.5)
