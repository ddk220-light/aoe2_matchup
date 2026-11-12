"""Accounting invariants of the army-economics pipeline (ported from matchup-timings 829c65bec).

Tests that need the offline labor solver skip cleanly when SciPy is absent
(SciPy lives in requirements-economy.txt, not in the CI requirements).
"""
import pytest

from aoe2x.economy.accounting import (
    add_costs, army_investment, compare_research, compile_labor_prices, compiled_labor, investment_comparison,
    production_for_window, purchase_bill, queue_seconds, research_infrastructure, research_summary,
    research_totals, resources, select_investment_route, solve_labor, weighted_cost,
)

needs_scipy = pytest.mark.skipif(__import__("importlib").util.find_spec("scipy") is None,
                                 reason="SciPy (requirements-economy.txt) is an offline-only dependency")


@needs_scipy
def test_linear_labor_and_recurring_farm_wood():
    activities = [{"id": "food", "outputs": resources({"food": .5, "wood": -.05})},
                  {"id": "wood", "outputs": resources({"wood": 1})},
                  {"id": "gold", "outputs": resources({"gold": .5})}]
    result = solve_labor({"food": 50, "wood": 20, "gold": 10}, activities)
    assert result["seconds"] == pytest.approx(100 + 25 + 20)
    assert result["workByActivity"] == pytest.approx({"food": 100, "wood": 25, "gold": 20})


@needs_scipy
def test_coproduct_is_neither_double_counted_nor_sold():
    activities = [{"id": "wood", "outputs": {"wood": 1, "gold": .25}},
                  {"id": "gold", "outputs": {"gold": .5}}]
    assert solve_labor({"wood": 100, "gold": 30}, activities)["seconds"] == pytest.approx(110)
    result = solve_labor({"wood": 100}, activities)
    assert result["seconds"] == pytest.approx(100)
    assert result["surplus"]["gold"] == pytest.approx(25)
    assert solve_labor({"food": 1}, activities) is None
    assert solve_labor({}, [])["seconds"] == 0


def route(bid=1, cost=175, seconds=20):
    return {"id": bid, "cost": {"wood": cost}, "secondsPerOrder": seconds}


def complete_activities():
    return [{"id": r, "outputs": {r: 1}} for r in ("food", "wood", "gold", "stone")]


@pytest.mark.parametrize("orders,time,buildings,queue", [(5, 40, 5, 40), (7, 20, 3, 60),
    (7, 30, 4, 60), (5, 60, 5, 60), (0, 80, 0, 0), (14, 20, 5, 60)])
def test_discrete_training_window(orders, time, buildings, queue):
    p = production_for_window(route(seconds=time), orders)
    assert p["buildingCount"] == buildings
    assert p["trainingSeconds"] == queue
    assert p["investmentCost"]["wood"] == buildings * 175
    assert queue_seconds(orders, p) == queue
    assert queue_seconds(0, p) == 0


def test_faster_training_reduces_building_investment():
    ordinary = production_for_window(route(seconds=40), 5)
    faster = production_for_window(route(seconds=20), 5)
    assert ordinary["buildingCount"] == 5
    assert faster["buildingCount"] == 2
    assert faster["investmentCost"]["wood"] < ordinary["investmentCost"]["wood"]


@needs_scipy
def test_compiled_labor_matches_solver_with_coproducts_reseeding_and_refunds():
    import random
    activities = complete_activities()
    activities[0]["outputs"] = {"food": .5, "wood": -.05}
    activities[1]["outputs"] = {"wood": .8, "food": .1, "gold": .2}
    activities[2]["outputs"] = {"gold": .6}
    prices = compile_labor_prices(activities)
    rng = random.Random(23)
    for _ in range(50):
        cost = weighted_cost({r: rng.uniform(-40, 300) for r in ("food", "wood", "gold", "stone")})
        assert compiled_labor(cost, prices)["seconds"] == pytest.approx(solve_labor(cost, activities)["seconds"])
    assert compile_labor_prices(activities[:2]) is None
    assert compiled_labor({}, None)["seconds"] == 0
    assert compiled_labor({"food": 1}, None) is None


@needs_scipy
def test_weights_are_applied_once_after_pooling_bills():
    activities = complete_activities()
    activities[1]["outputs"]["gold"] = .5
    prices = compile_labor_prices(activities)
    common = {"net": {"gold": 25}, "costIsFixed": True}
    p = production_for_window(route(cost=0), 1)
    score = army_investment({"wood": 100}, p, common, prices)
    assert score["weightedCost"] == resources({"wood": 100, "gold": 37.5})
    assert score["labor"]["seconds"] == 100
    assert score["standaloneLabor"]["army"]["seconds"] + score["standaloneLabor"]["commonResearch"]["seconds"] > 100
    assert weighted_cost({"food": 10, "wood": 20, "gold": 30, "stone": 40}) == {"food": 10, "wood": 20, "gold": 45, "stone": 120}


@needs_scipy
def test_route_ranking_uses_combined_labor_then_queue_time_then_id():
    prices = compile_labor_prices(complete_activities())
    selected, _ = select_investment_route([route(1, 175, 40), route(2, 250, 20)], 5, 1, {}, prices)
    assert selected["id"] == 2  # More expensive each, fewer buildings.
    selected, _ = select_investment_route([route(1, 100, 30), route(2, 100, 20)], 2, 1, {}, prices)
    assert selected["id"] == 2
    selected, _ = select_investment_route([route(2), route(1)], 2, 1, {}, prices)
    assert selected["id"] == 1
    activities = complete_activities(); activities[3]["outputs"]["stone"] = 4
    stone = {"id": 3, "cost": {"stone": 100}, "secondsPerOrder": 20}
    selected, _ = select_investment_route([route(1, 100), stone], 1, 1, {}, compile_labor_prices(activities))
    assert selected["id"] == 3  # 300 weighted stone needs only 75 villager-seconds.


def test_unavailable_window_and_labor_do_not_make_headline_scores():
    common = {"net": {}, "costIsFixed": True}
    p, _ = select_investment_route([route(seconds=61)], 1, 1, {}, None)
    assert p["status"] == "training_exceeds_window"
    assert queue_seconds(1, p) is None
    assert army_investment({"food": 50}, p, common, None)["labor"] is None
    p, _ = select_investment_route([], 1, 1, {}, None)
    assert p["status"] == "unresolved_training_route"
    p, _ = select_investment_route([route()], 5, 1, {}, None)
    assert p["buildingCount"] == 2  # Infrastructure known even if labor is missing.
    assert army_investment({"food": 50}, p, common, None)["status"] == "unresolved_labor"
    assert army_investment({}, p, {**common, "costIsFixed": False}, None)["status"] == "unresolved_common_research_cost"
    assert investment_comparison([{"investment": {"labor": None}}] * 2)["status"] == "unavailable"


def test_investment_comparison_is_symmetric_and_equal_armies_match():
    teams = [{"investment": {"labor": {"seconds": n}}} for n in (100, 125)]
    assert investment_comparison(teams) == {"status": "available", "lowerTeam": 1, "savingPercent": pytest.approx(20)}
    assert investment_comparison(list(reversed(teams)))["lowerTeam"] == 2
    assert investment_comparison([teams[0], teams[0]])["lowerTeam"] is None


def test_batch_purchase_and_capacity():
    bill = purchase_bill(27, {"wood": 40, "gold": 45}, 2)
    assert (bill["orders"], bill["producedUnits"], bill["surplusUnits"]) == (14, 28, 1)
    assert bill["cost"] == resources({"wood": 560, "gold": 630})
    assert purchase_bill(0, {"gold": 45}, 2)["orders"] == 0
    with pytest.raises(ValueError):
        purchase_bill(True, {})


def tech(tid, seconds=10, food=100, refund=0, **extra):
    return {"id": tid, "seconds": seconds, "upfront": resources({"food": food}),
            "refund": resources({"gold": refund}), "net": resources({"food": food, "gold": -refund}),
            "building": {"id": 82, "name": "Castle", "cost": resources({"stone": 650})}, **extra}


def test_research_compares_common_ids_not_missing_upgrades():
    comparison = compare_research([tech(1, 20), tech(2, 500)], [tech(1, 10, 80, 20)])
    assert comparison["commonIds"] == [1]
    assert comparison["commonWorkloadDifferenceSeconds"] == 10
    assert comparison["exclusive"][0]["workloadSeconds"] == 500
    assert comparison["commonCostDifference"]["food"] == 20
    assert comparison["commonCostDifference"]["gold"] == 20


def test_infrastructure_deduplicates_and_credits_only_real_existing_buildings():
    ts = [tech(1), tech(2)]
    assert research_infrastructure(ts, {"id": 82, "buildingCount": 1})["additionalCost"] == resources()
    assert research_infrastructure(ts, {"id": 82, "buildingCount": 0})["additionalCost"]["stone"] == 650
    assert research_infrastructure([tech(1, 0, 0, automaticFree=True)], {})["buildings"] == []
