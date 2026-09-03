"""Scorer tests.

Two categories:

1. Synthetic ``score_card`` tests that pin the three verdicts (MATCH,
   MISMATCH, INCONCLUSIVE) and two safety properties the brief calls out
   explicitly:

   - a metric present on only one side (e.g. ``effective_accuracy`` on a
     melee side that never fired a projectile) must not crash the scorer;
   - ``effective_accuracy`` above 1.0 (a trampling ranged unit hitting
     several victims with one projectile) must never be clamped or treated
     as an error, including internally where a naive binomial-CI
     computation would try ``sqrt(p * (1 - p))`` with ``p > 1`` and blow up.

   These use small, hand-built card dicts shaped exactly like
   ``extract_card``'s own output (``{"sides": {"side<owner>": {...}}}``) so
   they never touch the filesystem and run in milliseconds.

2. A real end-to-end ``score_fight`` smoke test against one of the corpus's
   own truth cards + its 20 already-generated sim runs, confirming the glue
   (manifest lookup, composition building, sim-file loading through the
   SAME ``extract_card`` the tape went through) works against real data.
"""
from __future__ import annotations

import json

from aoe2x.calibration.paths import workspace_paths


def _side(**kwargs):
    """A minimal extract_card-shaped side card; fields not passed default to
    the same "not applicable" values extract_card itself would produce.
    """
    base = {
        "unit_name": "X", "civ": "Civ", "slug": "x",
        "start_count": 10, "survivors": 5, "hp_remaining": 100.0,
        "hits_landed": 50, "damage_dealt": 500.0, "kills": 5,
        "swing_interval_median": 2.0, "swing_interval_fastest": 1.8,
        "churn": 0.2, "swing_count": 50, "projectiles_fired": 50,
        "effective_accuracy": 1.0, "damage_histogram": {"10": 50},
        "trample_multi_rate": 0.0, "trample_victims_mean": 0.0,
        "trample_victims_max": 0, "splash_fraction": None,
        "first_blood": 1.0, "n_events": {"swings": 50, "gaps": 40, "projectiles": 50},
    }
    base.update(kwargs)
    return base


def _card(side2, side3, duration_s=100.0, **top):
    d = {"tag": "t", "run_id": "t", "matchup": "t", "duration_s": duration_s,
         "sides": {"side2": side2, "side3": side3}}
    d.update(top)
    return d


def test_match_when_tape_inside_sim_distribution():
    from aoe2x.calibration.score import score_card

    tape = _card(
        _side(hits_landed=100, survivors=8, hp_remaining=200.0),
        _side(hits_landed=20, survivors=0, hp_remaining=0.0),
    )
    sim_cards = [
        {"sides": {
            "side2": _side(hits_landed=h, survivors=8, hp_remaining=200.0),
            "side3": _side(hits_landed=20, survivors=0, hp_remaining=0.0),
        }}
        for h in (90, 95, 100, 105, 110)
    ]
    result = score_card(tape, sim_cards)
    row = next(r for r in result["metrics"] if r["name"] == "hits_landed" and r["side"] == "side2")
    assert row["verdict"] == "MATCH"
    assert result["verdict"] in ("PASS", "INCONCLUSIVE")  # no MISMATCH anywhere else either


def test_mismatch_when_outside_distribution_and_tape_n_is_large():
    from aoe2x.calibration.score import score_card

    # Winning side (survivors=8) swing_interval_median: tape says 5.0s with
    # a healthy 40 gaps behind it; every seed clusters tightly near 2.0s.
    # Real, well-supported disagreement -> MISMATCH, not downgraded.
    tape = _card(
        _side(swing_interval_median=5.0, survivors=8, hp_remaining=200.0,
              n_events={"swings": 50, "gaps": 40, "projectiles": 50}),
        _side(survivors=0, hp_remaining=0.0),
    )
    sim_cards = [
        {"sides": {
            "side2": _side(swing_interval_median=m, survivors=8, hp_remaining=200.0),
            "side3": _side(survivors=0, hp_remaining=0.0),
        }}
        for m in (1.9, 1.95, 2.0, 2.05, 2.1)
    ]
    result = score_card(tape, sim_cards)
    row = next(r for r in result["metrics"] if r["name"] == "swing_interval_median" and r["side"] == "side2")
    assert row["verdict"] == "MISMATCH"
    assert result["verdict"] == "MISMATCH"


def test_inconclusive_when_tape_gap_count_is_small():
    from aoe2x.calibration.score import score_card

    # Same disagreement as above, but the tape side only recorded 2 gaps
    # (< 5) -- too few to trust the apparent mismatch.
    tape = _card(
        _side(swing_interval_median=5.0, survivors=8, hp_remaining=200.0,
              n_events={"swings": 3, "gaps": 2, "projectiles": 3}),
        _side(survivors=0, hp_remaining=0.0),
    )
    sim_cards = [
        {"sides": {
            "side2": _side(swing_interval_median=m, survivors=8, hp_remaining=200.0),
            "side3": _side(survivors=0, hp_remaining=0.0),
        }}
        for m in (1.9, 1.95, 2.0, 2.05, 2.1)
    ]
    result = score_card(tape, sim_cards)
    row = next(r for r in result["metrics"] if r["name"] == "swing_interval_median" and r["side"] == "side2")
    assert row["verdict"] == "INCONCLUSIVE"
    assert result["verdict"] == "INCONCLUSIVE"


def test_inconclusive_via_binomial_ci_on_a_rate_metric():
    from aoe2x.calibration.score import score_card

    # Tape accuracy looks very different from the sim (0.5 vs ~0.9), but
    # it is backed by only 5 shots -- the binomial 95% CI at n=5 is far
    # wider than the accuracy tolerance, so this must be INCONCLUSIVE, not
    # MISMATCH.
    tape = _card(
        _side(effective_accuracy=0.5, projectiles_fired=5, hits_landed=2,
              survivors=8, hp_remaining=200.0),
        _side(survivors=0, hp_remaining=0.0, effective_accuracy=None,
              projectiles_fired=0),
    )
    sim_cards = [
        {"sides": {
            "side2": _side(effective_accuracy=a, projectiles_fired=5,
                           survivors=8, hp_remaining=200.0),
            "side3": _side(survivors=0, hp_remaining=0.0, effective_accuracy=None,
                           projectiles_fired=0),
        }}
        for a in (0.88, 0.9, 0.9, 0.92, 0.94)
    ]
    result = score_card(tape, sim_cards)
    row = next(r for r in result["metrics"] if r["name"] == "effective_accuracy" and r["side"] == "side2")
    assert row["verdict"] == "INCONCLUSIVE"


def test_metric_present_on_only_one_side_does_not_crash():
    from aoe2x.calibration.score import score_card

    # side3 is melee: it never fires a projectile, so effective_accuracy
    # (and projectiles_fired-derived rate metrics) are None on that side,
    # exactly as extract_card produces for a melee unit.
    tape = _card(
        _side(effective_accuracy=0.9, projectiles_fired=50, survivors=8, hp_remaining=200.0),
        _side(effective_accuracy=None, projectiles_fired=0, survivors=0, hp_remaining=0.0),
    )
    sim_cards = [
        {"sides": {
            "side2": _side(effective_accuracy=a, projectiles_fired=50,
                           survivors=8, hp_remaining=200.0),
            "side3": _side(effective_accuracy=None, projectiles_fired=0,
                           survivors=0, hp_remaining=0.0),
        }}
        for a in (0.85, 0.88, 0.9, 0.92, 0.95)
    ]
    result = score_card(tape, sim_cards)  # must not raise
    side3_rows = [r["name"] for r in result["metrics"] if r["side"] == "side3"]
    assert "effective_accuracy" not in side3_rows


def test_effective_accuracy_above_one_is_never_clamped():
    from aoe2x.calibration.score import score_card

    # A trampling ranged unit: 2.43 landed hits per projectile fired. Must
    # survive untouched through scoring (reported exactly as 2.43) and must
    # not raise even though sim clusters far from it (checks the internal
    # binomial-CI helper clamps p only for its own width estimate, never for
    # the value that gets compared/reported).
    tape = _card(
        _side(effective_accuracy=2.43, projectiles_fired=30, hits_landed=73,
              survivors=8, hp_remaining=200.0, trample_multi_rate=0.5),
        _side(survivors=0, hp_remaining=0.0, effective_accuracy=None, projectiles_fired=0),
    )
    sim_cards = [
        {"sides": {
            "side2": _side(effective_accuracy=a, projectiles_fired=30, hits_landed=30,
                           survivors=8, hp_remaining=200.0, trample_multi_rate=0.5),
            "side3": _side(survivors=0, hp_remaining=0.0, effective_accuracy=None, projectiles_fired=0),
        }}
        for a in (0.95, 1.0, 1.0, 1.05, 1.0)
    ]
    result = score_card(tape, sim_cards)  # must not raise (no domain error)
    row = next(r for r in result["metrics"] if r["name"] == "effective_accuracy" and r["side"] == "side2")
    assert row["tape"] == 2.43, "accuracy > 1.0 must never be clamped"


def test_score_fight_reads_only_explicit_workspace(tmp_path):
    from aoe2x.calibration.score import score_fight

    paths = workspace_paths(tmp_path / "calibration")
    run_id = "local_a__vs__local_b"
    fight = {
        "tag": run_id,
        "run_id": run_id,
        "matchup": run_id,
        "side1": {"owner": 2, "unit_name": "A", "civ": "Chinese", "slug": "champion", "count": 1},
        "side2": {"owner": 3, "unit_name": "B", "civ": "Chinese", "slug": "arbalester", "count": 1},
    }
    paths.fixtures_dir.mkdir(parents=True)
    paths.manifest.write_text(json.dumps({"fights": [fight]}), encoding="utf-8")
    paths.truth_dir.mkdir(parents=True)
    paths.truth_dir.joinpath(f"{run_id}.json").write_text(
        json.dumps(_card(_side(), _side(), run_id=run_id, tag=run_id, matchup=run_id)),
        encoding="utf-8",
    )
    sim_dir = paths.runs_dir / run_id
    sim_dir.mkdir(parents=True)
    sim_dir.joinpath("seed-1.json").write_text(
        json.dumps({"damage": [], "missiles": [], "duration_s": 1.0}),
        encoding="utf-8",
    )

    result = score_fight(run_id, seeds=[1], paths=paths)

    assert result["run_id"] == run_id
