"""Guard the strict close-finish threshold and the ordering of match scores."""
import copy
import json
import pytest

import report_knight_line_rankings as reporting
from report_knight_line_rankings import (
    exception_review_fingerprint,
    exception_review_key,
    match_score,
    performance_highlights,
    ranking_exceptions,
    ranking_outcome,
    review_ranking_exceptions,
)


def test_rosters_reproduce_without_machine_local_queues_or_intro_profiles(monkeypatch, tmp_path):
    """A fresh analysis checkout needs the tracked roster, not a recording PC."""
    manifest = reporting.read(reporting.SOURCE_MANIFEST)
    isolated_manifest = tmp_path / "ranking_sources.json"
    isolated_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(reporting, "REPO", tmp_path)
    monkeypatch.setattr(reporting, "SOURCE_MANIFEST", isolated_manifest)
    camels = reporting.source_specs("camel")
    knights = reporting.source_specs("knight")
    assert len(camels) == len({v["key"] for v in camels}) == 9
    assert len(knights) == len({v["key"] for v in knights}) == 17
    assert sum(bool(v.get("optionalOverrides")) for v in knights) == 9
    assert next(v for v in knights if v["key"] == "paladin-persians")["folders"] == ["knight-v2-savar-persians"]
    assert camels == manifest["camel"] and knights == manifest["knight"]


@pytest.mark.parametrize("policy,captured,expected,eligible", [
    ("geometric_shared_discount_v1", [21, 27], [21, 27], True),
    ("geometric_shared_discount_unit_count_v2", [21, 27], [21, 27], True),
    ("geometric_shared_discount_v1", [10, 27], [15, 27], False),
    ("geometric_shared_discount_v1", [13, 27], [18, 27], False),
    ("unknown", [21, 27], [21, 27], False),
])
def test_capture_equivalence_uses_actual_counts_not_only_policy_label(policy, captured, expected, eligible):
    assert reporting.counts_match_current_policy(policy, captured, expected) is eligible


@pytest.mark.parametrize("owner", [2, 3])
@pytest.mark.parametrize("hp", [0, 0.01, 9.999999])
def test_under_ten_percent_is_a_draw_whichever_side_survives(owner, hp):
    assert ranking_outcome(owner, hp) == "D"


@pytest.mark.parametrize("owner, expected", [(2, "W"), (3, "L")])
@pytest.mark.parametrize("hp", [10.0, 10.000001, 100.0])
def test_exactly_ten_percent_and_above_preserves_the_result(owner, expected, hp):
    assert ranking_outcome(owner, hp) == expected


def test_actual_draw_and_close_finish_have_the_same_fixed_score():
    assert ranking_outcome(None, 0) == "D"
    # Even extraneous HP/rarity values must not increase the draw award.
    assert match_score(dict(outcome="D", hpFraction=1, rarityBonus=1)) == 0.5


def test_draw_scores_between_a_loss_and_a_win():
    loss = match_score(dict(outcome="L", hpFraction=0.1, rarityBonus=0))
    draw = match_score(dict(outcome="D", hpFraction=0, rarityBonus=0))
    win = match_score(dict(outcome="W", hpFraction=0.1, rarityBonus=0))
    assert loss < draw < win


@pytest.mark.parametrize("recorded", ["W", "L", "D"])
def test_higher_ranked_draw_qualifies_without_changing_its_actual_result(recorded):
    ranks = [dict(key="high", label="Higher", rank=1),
             dict(key="low", label="Lower", rank=2)]
    series = {
        "high": dict(rows={"opponent": dict(outcome="D", recordedOutcome=recorded,
                                             winnerHpPercent=6.0, points=0.5)}),
        "low": dict(rows={"opponent": dict(outcome="W", opponent="Opponent",
                                            opponentCivilization="Test", winnerHpPercent=20.0)}),
    }
    before = copy.deepcopy(series)
    result = ranking_exceptions(ranks, series, ["opponent"])
    assert len(result) == 1
    higher = result[0]["higherRankedNonWinners"][0]
    assert higher["outcome"] == "D" and higher["recordedOutcome"] == recorded
    assert series == before


def test_near_win_is_not_an_exception_against_a_higher_ranked_loser():
    ranks = [dict(key="high", label="Higher", rank=1),
             dict(key="low", label="Lower", rank=2)]
    series = {
        "high": dict(rows={"opponent": dict(outcome="L")}),
        "low": dict(rows={"opponent": dict(outcome="D", recordedOutcome="W")}),
    }
    assert ranking_exceptions(ranks, series, ["opponent"]) == []


def test_equal_overall_ranks_do_not_create_an_unexpected_win():
    ranks = [dict(key="first", label="First", rank=1),
             dict(key="second", label="Second", rank=1)]
    series = {"first": dict(rows={"opponent": dict(outcome="D")}),
              "second": dict(rows={"opponent": dict(outcome="W")})}
    assert ranking_exceptions(ranks, series, ["opponent"]) == []


@pytest.mark.parametrize("lower_hp,higher_hp,qualifies", [
    (19.0, 10.0, False),  # A large relative improvement is not a 10-point gap.
    (30.0, 20.0, False),
    (30.1, 20.1, False),
    (30.000001, 20.0, True),
    (30.0, 20.000001, False),
    (32.0, 20.0, True),  # Newly included by the reduced threshold.
    (20.0, 40.0, False),
])
def test_both_win_requires_strictly_more_than_ten_percentage_points(lower_hp, higher_hp, qualifies):
    ranks = [dict(key="high", label="Higher", rank=1),
             dict(key="low", label="Lower", rank=2)]
    series = {key: dict(rows={"opponent": dict(outcome="W", recordedOutcome="W",
                                              opponent="Opponent", opponentCivilization="Test",
                                              winnerHpPercent=hp)})
              for key, hp in (("high", higher_hp), ("low", lower_hp))}
    before = copy.deepcopy(series)
    results = ranking_exceptions(ranks, series, ["opponent"])
    assert bool(results) is qualifies
    if qualifies:
        assert results[0]["higherRankedNonWinners"] == []
        other = results[0]["higherRankedHpWins"][0]
        assert other["key"] == "high" and other["outcome"] == "W"
        assert other["hpGapPercentagePoints"] == pytest.approx(lower_hp - higher_hp)
    assert series == before


def test_one_lower_ranked_win_can_have_both_kinds_of_exception_without_duplication():
    ranks = [dict(key="loss", label="Loses", rank=1),
             dict(key="win", label="Wins narrowly", rank=2),
             dict(key="low", label="Lower", rank=3)]
    series = {key: dict(rows={"opponent": dict(outcome=outcome, recordedOutcome=outcome,
                                              opponent="Opponent", opponentCivilization="Test",
                                              winnerHpPercent=hp)})
              for key, outcome, hp in (("loss", "L", 70), ("win", "W", 20), ("low", "W", 50))}
    results = ranking_exceptions(ranks, series, ["opponent"])
    lower = [r for r in results if r["lowerRankedWinner"] == "low"]
    assert len(lower) == 1
    assert [r["key"] for r in lower[0]["higherRankedNonWinners"]] == ["loss"]
    assert [r["key"] for r in lower[0]["higherRankedHpWins"]] == ["win"]


def review_example():
    ranks = [dict(key="high", label="Higher", rank=1), dict(key="low", label="Lower", rank=2)]
    series = {key: dict(rows={"opponent": dict(outcome=outcome, recordedOutcome=outcome,
                                              opponent="Opponent", opponentCivilization="Test",
                                              winnerHpPercent=hp, counts=[25, 27], points=points)})
              for key, outcome, hp, points in (("high", "L", 20, -0.2), ("low", "W", 30, 2.3))}
    return ranking_exceptions(ranks, series, ["opponent"]), series


def test_missing_explanation_retains_an_unexpected_win():
    exceptions, series = review_example()
    reviewed = review_ranking_exceptions(exceptions, series)
    assert reviewed["retained"] == exceptions
    assert len(reviewed["unreviewed"]) == 1
    assert reviewed["inconclusive"] == []


@pytest.mark.parametrize("status", ["retain", "dismiss_obvious"])
def test_only_explicit_current_dismissal_filters_highlights_and_never_scores(status):
    exceptions, series = review_example()
    exception, comparison = exceptions[0], exceptions[0]["higherRankedNonWinners"][0]
    decision = dict(status=status, rationale="A reviewed matchup-specific reason",
                    evidence={"abilityTradeoff": "Combat regeneration versus more starting HP"},
                    fingerprint=exception_review_fingerprint(exception, comparison, series))
    review = dict(decisions={exception_review_key(exception, comparison): decision})
    before = copy.deepcopy((exceptions, series))
    reviewed = review_ranking_exceptions(exceptions, series, review)
    assert bool(reviewed["retained"]) is (status == "retain")
    assert bool(reviewed["inconclusive"]) is (status == "dismiss_obvious")
    assert reviewed["unreviewed"] == []
    assert (exceptions, series) == before


def test_changed_capture_invalidates_a_dismissal_and_retains_the_new_result():
    exceptions, series = review_example()
    exception, comparison = exceptions[0], exceptions[0]["higherRankedNonWinners"][0]
    review = dict(decisions={exception_review_key(exception, comparison): dict(
        status="dismiss_obvious", rationale="Old capture review", evidence={"reviewed": True},
        fingerprint=exception_review_fingerprint(exception, comparison, series))})
    series["low"]["rows"]["opponent"]["counts"] = [27, 27]
    reviewed = review_ranking_exceptions(exceptions, series, review)
    assert reviewed["retained"] == exceptions
    assert len(reviewed["unreviewed"]) == 1
    assert reviewed["inconclusive"] == []


@pytest.mark.parametrize("lower_enemy_hp,higher_enemy_hp,qualifies", [
    (20.0, 29.0, False),
    (20.0, 30.0, False),
    (20.1, 30.1, False),
    (20.0, 30.000001, True),
    (20.0, 32.0, True),
    (60.0, 20.0, False),  # Leaving more enemy HP is worse, not better.
])
def test_better_defeat_reverses_hp_subtraction_and_keeps_loss_labels(lower_enemy_hp, higher_enemy_hp, qualifies):
    ranks = [dict(key="high", label="Higher", rank=1), dict(key="low", label="Lower", rank=2)]
    series = {key: dict(rows={"opponent": dict(outcome="L", recordedOutcome="L",
                                              opponent="Opponent", opponentCivilization="Test",
                                              winnerHpPercent=hp, points=-hp/100)})
              for key, hp in (("high", higher_enemy_hp), ("low", lower_enemy_hp))}
    before = copy.deepcopy(series)
    results = ranking_exceptions(ranks, series, ["opponent"])
    assert bool(results) is qualifies
    if qualifies:
        e = results[0]
        assert e["outcome"] == "L" and e["hpOwner"] == "opponent"
        assert e["lowerRankedWinner"] is None and e["lowerRankedVariant"] == "low"
        assert not e["higherRankedNonWinners"] and not e["higherRankedHpWins"]
        h = e["higherRankedHpLosses"][0]
        assert h["outcome"] == "L"
        assert h["hpGapPercentagePoints"] == pytest.approx(higher_enemy_hp - lower_enemy_hp)
        reviewed = review_ranking_exceptions(results, series)
        assert reviewed["retained"] == results
    assert series == before


@pytest.mark.parametrize("higher_outcome", ["W", "D"])
def test_loss_never_qualifies_against_a_higher_ranked_win_or_draw(higher_outcome):
    ranks = [dict(key="high", label="Higher", rank=1), dict(key="low", label="Lower", rank=2)]
    series = {key: dict(rows={"opponent": dict(outcome=outcome, recordedOutcome=outcome,
                                              opponent="Opponent", opponentCivilization="Test",
                                              winnerHpPercent=hp)})
              for key, outcome, hp in (("high", higher_outcome, 90), ("low", "L", 20))}
    assert ranking_exceptions(ranks, series, ["opponent"]) == []


def highlight_example():
    ranks = [dict(key=key, label=key.upper(), rank=i + 1) for i, key in enumerate("abcde")]
    battles = {
        "alpha": [("W", 60), ("L", 80), ("L", 50), ("W", 20), ("L", 90)],
        "beta": [("L", 50), ("L", 80), ("L", 90), ("L", 90), ("W", 20)],
        "gamma": [("L", 50), ("W", 50), ("W", 50), ("W", 50), ("W", 20)],
    }
    series = {v["key"]: dict(rows={slug: dict(opponent=slug, opponentCivilization="Test",
                                              outcome=values[i][0], recordedOutcome=values[i][0],
                                              winnerHpPercent=values[i][1])
                                   for slug, values in battles.items()})
              for i, v in enumerate(ranks)}
    return ranks, series, list(battles)


def test_highlight_order_counts_distinct_peers_not_rank_distance():
    ranks, series, opponents = highlight_example()
    exceptions = ranking_exceptions(ranks, series, opponents)
    before = copy.deepcopy((ranks, series, exceptions))
    h = performance_highlights(ranks, series, opponents, exceptions)
    assert (h["topUpward"][0]["key"], h["topUpward"][0]["opponentSlug"], h["topUpward"][0]["jumpCount"]) == ("e", "beta", 4)
    row = next(r for r in h["allUpward"] if r["key"] == "e" and r["opponentSlug"] == "gamma")
    assert row["jumpCount"] == 1  # Rank five beats rank one; this is one peer, not four.
    for field in ("topUpward", "topDownward"):
        counts = [r["jumpCount"] for r in h[field]]
        assert counts == sorted(counts, reverse=True)
    assert (ranks, series, exceptions) == before


def test_downward_list_is_the_exact_inverse_without_duplicating_peers():
    ranks, series, opponents = highlight_example()
    exceptions = ranking_exceptions(ranks, series, opponents)
    exceptions.append(copy.deepcopy(exceptions[0]))
    h = performance_highlights(ranks, series, opponents, exceptions)
    up = {(r["key"], p["key"], r["opponentSlug"]) for r in h["allUpward"] for p in r["peers"]}
    down = {(p["key"], r["key"], r["opponentSlug"]) for r in h["allDownward"] for p in r["peers"]}
    assert up == down
    assert sum(r["jumpCount"] for r in h["allUpward"]) == len(up)
    assert sum(r["jumpCount"] for r in h["allDownward"]) == len(down)


def test_rare_win_order_is_independent_of_overall_rank_and_draws_are_not_losses():
    ranks, series, opponents = highlight_example()
    h = performance_highlights(ranks, series, opponents, [])
    rare = h["topRareWins"]
    assert (rare[0]["key"], rare[0]["opponentSlug"], rare[0]["otherLosses"]) == ("e", "beta", 4)
    assert rare[0]["soleWinner"] and rare[0]["otherWins"] == 0
    series["a"]["rows"]["beta"]["outcome"] = "D"
    h = performance_highlights(ranks, series, opponents, [])
    row = next(r for r in h["allRareWins"] if r["key"] == "e")
    assert row["otherLosses"] == 3 and row["otherDraws"] == 1
    limited = performance_highlights(ranks, series, opponents, [], limit=1)
    assert len(limited["topRareWins"]) == 1


def test_dismissed_pair_cannot_reappear_in_either_highlight_list():
    exceptions, series = review_example()
    e, peer = exceptions[0], exceptions[0]["higherRankedNonWinners"][0]
    review = dict(decisions={exception_review_key(e, peer): dict(
        status="dismiss_obvious", rationale="Reviewed obvious anomaly", evidence={"checked": True},
        fingerprint=exception_review_fingerprint(e, peer, series))})
    ranks = [dict(key="high", label="Higher", rank=1), dict(key="low", label="Lower", rank=2)]
    series["high"]["rows"]["opponent"].update(opponent="Opponent", opponentCivilization="Test")
    reviewed = review_ranking_exceptions(exceptions, series, review)
    h = performance_highlights(ranks, series, ["opponent"], reviewed["retained"])
    assert h["topUpward"] == [] and h["topDownward"] == []


def test_default_limit_is_twenty_five_without_padding_short_lists():
    ranks = [dict(key="high", label="Higher", rank=1), dict(key="low", label="Lower", rank=2)]
    opponents = [f"opponent_{i:02d}" for i in range(30)]
    series = {key: dict(rows={slug: dict(outcome=outcome, recordedOutcome=outcome,
                                         opponent=slug, opponentCivilization="Test", winnerHpPercent=50)
                              for slug in opponents}) for key, outcome in (("high", "L"), ("low", "W"))}
    h = performance_highlights(ranks, series, opponents, ranking_exceptions(ranks, series, opponents))
    assert h["limit"] == 25
    for top, all_rows in (("topUpward", "allUpward"), ("topDownward", "allDownward"), ("topRareWins", "allRareWins")):
        assert len(h[top]) == 25 and len(h[all_rows]) == 30
        assert h[top] == h[all_rows][:25]
    short = performance_highlights(ranks, series, opponents[:3], ranking_exceptions(ranks, series, opponents[:3]))
    assert len(short["topRareWins"]) == 3
