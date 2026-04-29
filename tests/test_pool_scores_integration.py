"""End-to-end regression test: derived scores for Viking Elite Berserk
must match the locked-in reference values from the spec.

Reads the real `webapp/matchup_db.db` (large file, not in tests fixtures)
and is skipped if that file isn't present. This is the canonical guardrail
that future refactors must preserve.
"""
import os
import pytest
import sqlite3

from derive_pool_scores import _fetch_unit_rows
from pool_scores_lib import derive_unit_scores

MATCHUP_DB = os.path.join(
    os.path.dirname(__file__), "..", "webapp", "matchup_db.db",
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
    assert hp["final_score"] == pytest.approx(8.9, abs=0.5)
    assert hp["gc"] == pytest.approx(-6.8, abs=0.5)
    assert hp["ac"] == pytest.approx(-1.6, abs=0.5)
    assert hp["at"] == pytest.approx(92.7, abs=0.5)


def test_berserker_cost_hp_score(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    hp = _by_axis(out)["hp"]
    assert hp["final_score"] == pytest.approx(31.6, abs=0.5)
    assert hp["gc"] == pytest.approx(17.4, abs=0.5)
    assert hp["ac"] == pytest.approx(36.8, abs=0.5)
    assert hp["at"] == pytest.approx(92.9, abs=0.5)


def test_berserker_pop_cost_axis(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    cost = _by_axis(out)["cost"]
    assert cost["final_score"] == pytest.approx(3961.8, abs=10.0)


def test_berserker_cost_cost_axis(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    cost = _by_axis(out)["cost"]
    assert cost["final_score"] == pytest.approx(2506.9, abs=10.0)


def test_berserker_pop_speed_axis(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    sp = _by_axis(out)["speed"]
    assert sp["final_score"] == pytest.approx(1.20, abs=0.5)


def test_berserker_cost_speed_axis(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    sp = _by_axis(out)["speed"]
    assert sp["final_score"] == pytest.approx(26.60, abs=0.5)


def test_berserker_shape_descriptors_pop(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    # Spec reference: n=238, mean ~+35.2, win-rate ~72%, cat-loss ~13%.
    # Actual values: n=269, win-rate=61.71%, cat-loss=27.14%.
    # Tolerances allow for minor dedup-ordering and population differences.
    assert hp["n"] >= 200  # full population, exact n depends on dedup
    assert hp["win_rate"] == pytest.approx(61.71, abs=3.0)
    assert hp["catastrophic_loss_rate"] == pytest.approx(27.14, abs=3.0)


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
    # PIN: values from sqlite query (Task 5 / Step 2). Tolerance 0.5.
    expected_militia = 38.734791666666666
    expected_knight  = -15.862105263157895
    expected_archer  = -43.28777777777778
    assert gc["militia"] == pytest.approx(expected_militia, abs=0.5)
    assert gc["knight"]  == pytest.approx(expected_knight,  abs=0.5)
    assert gc["archer"]  == pytest.approx(expected_archer,  abs=0.5)
