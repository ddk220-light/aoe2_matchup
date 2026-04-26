import os
import sqlite3

import pytest

from webapp.battle_outcome import BattleOutcome, signed_score, average_outcomes
from webapp.combat_unit_loader import build_combat_dict_from_ref
from webapp.simulation import prepare_combat_unit
from webapp.simulation_real import simulate_real_battle


REF_DB = os.path.join(os.path.dirname(__file__), "..", "webapp", "aoe2_reference.db")


def _load(civ, slug, age="Imperial"):
    conn = sqlite3.connect(REF_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ, slug, age),
    ).fetchone()
    conn.close()
    if row is None:
        pytest.skip(f"{civ}/{slug}/{age} not in ref DB")
    cd = build_combat_dict_from_ref(row)
    cu = prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]
    cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]
    cu["outline_size"] = cd.get("outline_size", 0.2)
    cu["cost"] = cd["cost_food"] + cd["cost_wood"] + cd["cost_gold"]
    return cu


def _outcome(**overrides):
    base = dict(
        winner=1, end_reason="eliminated", game_time_s=20.0,
        team1_hp_pct=0.6, team2_hp_pct=0.0,
        team1_survivors=18, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )
    base.update(overrides)
    return BattleOutcome(**base)


def test_signed_score_team1_win_full_health():
    o = _outcome(winner=1, team1_hp_pct=1.0, team2_hp_pct=0.0)
    assert signed_score(o) == 100.0


def test_signed_score_team2_win_negates():
    o = _outcome(winner=2, team1_hp_pct=0.0, team2_hp_pct=0.7)
    assert signed_score(o) == -70.0


def test_signed_score_close_team1():
    o = _outcome(winner=1, team1_hp_pct=0.55, team2_hp_pct=0.45)
    assert signed_score(o) == 10.0


def test_signed_score_draw_returns_zero():
    o = _outcome(winner=0, team1_hp_pct=0.3, team2_hp_pct=0.3)
    assert signed_score(o) == 0.0


def test_average_outcomes_means_numeric_fields():
    a = _outcome(team1_hp_pct=0.5, team2_hp_pct=0.0, game_time_s=30.0,
                 team1_survivors=20, team2_survivors=0,
                 team1_resources_lost=500, team2_resources_lost=2400)
    b = _outcome(team1_hp_pct=0.7, team2_hp_pct=0.0, game_time_s=20.0,
                 team1_survivors=24, team2_survivors=0,
                 team1_resources_lost=300, team2_resources_lost=2400)
    avg = average_outcomes([a, b])
    assert avg.team1_hp_pct == 0.6
    assert avg.team2_hp_pct == 0.0
    assert avg.game_time_s == 25.0
    assert avg.team1_survivors == 22
    assert avg.team1_resources_lost == 400
    assert avg.winner == 1   # majority


def test_average_outcomes_majority_winner():
    runs = [_outcome(winner=1), _outcome(winner=2), _outcome(winner=1)]
    assert average_outcomes(runs).winner == 1


def test_average_outcomes_tie_picks_higher_hp_side():
    a = _outcome(winner=1, team1_hp_pct=0.4, team2_hp_pct=0.0)
    b = _outcome(winner=2, team1_hp_pct=0.0, team2_hp_pct=0.5)
    avg = average_outcomes([a, b])
    assert avg.winner == 2  # avg t2_hp_pct (0.25) > avg t1_hp_pct (0.20)


def test_simulate_real_battle_returns_battle_outcome():
    champ = _load("Vikings", "champion")
    halb = _load("Britons", "halberdier")
    out = simulate_real_battle(champ, halb, resources=3000, fixed_count=30, seed=0)
    assert isinstance(out, BattleOutcome)
    assert out.winner in (1, 2, 0)
    assert out.end_reason in ("eliminated", "time_cap")
    assert 0.0 <= out.team1_hp_pct <= 1.0
    assert 0.0 <= out.team2_hp_pct <= 1.0
    assert out.team1_start_count == 30
    assert out.team2_start_count == 30
    assert out.team1_survivors <= 30
    assert out.game_time_s > 0


def test_simulate_real_battle_legacy_tuple_via_kwarg():
    champ = _load("Vikings", "champion")
    halb = _load("Britons", "halberdier")
    legacy = simulate_real_battle(
        champ, halb, resources=3000, fixed_count=30, seed=0,
        return_hp=True, _legacy_tuple=True,
    )
    assert isinstance(legacy, tuple)
    assert len(legacy) == 5  # winner, r1, r2, hp1, hp2
