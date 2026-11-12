"""Accounting invariants and the actual compiled page integration contract."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess

import pytest

from aoe2x.army_economics import (
    compare_research, investment_comparison, production_for_window, purchase_bill, queue_seconds, select_investment_route,
    add_costs, army_investment, compile_labor_prices, compiled_labor, weighted_cost,
    research_infrastructure, resources, solve_labor,
)
from apps.website.services.army_context import ArmyContext, ContextUnavailable
from apps.website.services.battles import build_battle_config

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data/golden/army_context.db"
REFERENCE = ROOT / "data/golden/aoe2_reference_simulation.db"


def connect():
    c = sqlite3.connect(REFERENCE)
    c.row_factory = sqlite3.Row
    return c


def selection(civ, master, count=27, mode=None):
    with connect() as c:
        slug = c.execute("SELECT unit_slug FROM ref_units WHERE civ_name=? AND unit_master=?", (civ, master)).fetchone()[0]
    return {"civ": civ, "unit_slug": slug, "count": count, **({"mode": mode} if mode else {})}


def config(a, b, *, store=None, army=None):
    with connect() as c:
        civs = {r[0] for r in c.execute("SELECT DISTINCT civ_name FROM ref_units")}
    return build_battle_config({"teams": [a, b], "army": army or {"mode": "explicit"},
                                "seed": 123, "engagement_mode": "direct"},
                               connect=connect, valid_civs=lambda: civs,
                               cost_resolver=store.apply_cost if store else None)


@pytest.fixture(scope="module")
def store():
    return ArmyContext(RUNTIME, "review")


def test_linear_labor_and_recurring_farm_wood():
    activities = [{"id": "food", "outputs": resources({"food": .5, "wood": -.05})},
                  {"id": "wood", "outputs": resources({"wood": 1})},
                  {"id": "gold", "outputs": resources({"gold": .5})}]
    result = solve_labor({"food": 50, "wood": 20, "gold": 10}, activities)
    assert result["seconds"] == pytest.approx(100 + 25 + 20)
    assert result["workByActivity"] == pytest.approx({"food": 100, "wood": 25, "gold": 20})


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


def test_actual_profile_coverage_and_source_join(store):
    with connect() as c:
        profiles = c.execute("SELECT m.*,u.civ_name FROM ref_unit_mechanics m JOIN ref_units u ON u.id=m.ref_unit_id").fetchall()
    for profile in profiles:
        team = {"civ": profile["civ_name"], "mode": profile["mode"], "mechanics_hash": profile["mechanics_hash"],
                "mechanics": json.loads(profile["mechanics_json"])}
        unit = store.unit(team)
        assert len(unit["lookup"]) == 28
        assert unit["lookup"][0]["trainingSeconds"] == 0
        assert unit["lookup"][0]["labor"]["seconds"] == 0
        assert unit["lookup"][0]["weightedLabor"]["seconds"] == 0
        if unit["production"]["status"] == "modeled":
            assert unit["production"]["trainingSeconds"] <= 60
            assert unit["production"]["buildingCount"] > 0
            for entry in unit["lookup"]:
                if entry["weightedLabor"] is not None:
                    assert entry["weightedLabor"]["seconds"] >= entry["labor"]["seconds"] - 1e-8
    assert len(profiles) == 1031


@pytest.mark.parametrize("civ,uid,building", [("Huns", 757, "Stable"), ("Goths", 555, "Barracks"),
                                            ("Bulgarians", 1227, "Krepost"), ("Spanish", 42, "Castle")])
def test_training_routes(store, civ, uid, building):
    a = selection(civ, uid)
    u = store.response(config(a, a, store=store))["teams"][0]
    assert u["production"]["name"] == building
    if civ == "Huns":
        assert 483 in {t["id"] for t in u["research"]["military"]["technologies"]}
    if civ == "Goths":
        assert 16 in {t["id"] for t in u["research"]["military"]["technologies"]}


def test_alternate_forms_and_unavailable_routes(store):
    for civ, uid in [("Berbers", 1631), ("Chinese", 529)]:
        a = selection(civ, uid)
        u = store.response(config(a, a, store=store))["teams"][0]
        assert u["production"]["status"] == "unresolved_training_route"
        assert u["startingArmy"]["trainingSeconds"] is None
    a = selection("Bengalis", 1740)
    u = store.response(config(a, a, store=store))["teams"][0]
    assert u["production"]["trainedUnitId"] == 1761
    assert u["production"]["formIdentity"]["displayUnitId"] == 1740
    a = selection("Shu", 1962, mode="barrage")
    u = store.response(config(a, a, store=store))["teams"][0]
    assert (u["unitId"], u["sourceUnitId"]) == (1980, 1962)


def test_batch_and_conditional_cost_policies(store):
    a = selection("Tupi", 2581)
    u = store.response(config(a, a, store=store))["teams"][0]
    assert u["startingArmy"]["orders"] == 14
    assert u["startingArmy"]["surplusUnits"] == 1
    assert u["pricing"]["physicalUnitCost"]["wood"] == 20
    # Initial purchase's spare unit covers the first loss. Further batch
    # purchases are cumulative, not independently rounded for every death.
    losses = u["replacementLookup"]
    assert losses[1]["initialSurplusUsed"] == 1
    assert losses[1]["weightedLabor"]["seconds"] == 0
    assert losses[1]["orders"] == 0
    assert losses[2]["orders"] == losses[3]["orders"] == 1
    assert losses[2]["surplusUnits"] == 1
    assert losses[3]["surplusUnits"] == 0
    assert losses[4]["orders"] == 2
    with sqlite3.connect(RUNTIME) as c:
        saxons = [json.loads(r[0]) for r in c.execute("SELECT payload FROM units WHERE civ='Saxons'")]
    discounted = [u for u in saxons if u["pricing"]["conditionalMultiplier"] == .8]
    assert len(discounted) == 6
    assert all(u["pricing"]["conditionalContext"] for u in discounted)


def test_verified_price_overlay_preserves_every_non_cost_mechanic(store):
    for civ, uid, expected in [("Magyars", 871, {"food": 80, "wood": 0, "gold": 0}),
                               ("Mapuche", 2571, {"food": 0, "wood": 43, "gold": 47}),
                               ("Mayans", 492, {"food": 0, "wood": 18, "gold": 32}),
                               ("Mayans", 765, {"food": 0, "wood": 39, "gold": 39})]:
        a, b = selection(civ, uid), selection("Spanish", 567)
        old, new = config(a, b), config(a, b, store=store)
        for left, right in zip(old["teams"], new["teams"]):
            original, corrected = copy.deepcopy(left["mechanics"]), copy.deepcopy(right["mechanics"])
            original.pop("cost"); corrected.pop("cost")
            assert original == corrected
            assert left["count"] == right["count"]
        assert new["teams"][0]["mechanics"]["cost"] == expected


def test_counts_come_from_the_same_resolver(store):
    a, b = selection("Mayans", 492), selection("Spanish", 569)
    battle = config(a, b, store=store, army={"mode": "resource_budgets", "budgets": [5000, 5000]})
    context = store.response(battle)
    assert context["schemaVersion"] == 3
    assert context["trainingWindowSeconds"] == 60
    assert context["resourceWeights"] == {"food": 1, "wood": 1, "gold": 1.5, "stone": 3}
    assert context["investmentComparison"]["status"] == "available"
    assert [t["count"] for t in context["teams"]] == [t["count"] for t in battle["teams"]]
    assert all(len(t["lookup"]) == t["count"] + 1 for t in context["teams"])
    assert all(len(t["replacementLookup"]) == t["count"] + 1 for t in context["teams"])


def test_food_army_includes_farm_woodcutters(store):
    a = selection("Spanish", 441)  # Hussar: food-only unit bill.
    u = store.response(config(a, a, store=store))["teams"][0]
    assert u["startingArmy"]["cost"]["wood"] == 0
    assert u["startingArmy"]["labor"]["workByActivity"]["wood"] > 0
    assert u["startingArmy"]["weightedLabor"]["seconds"] == pytest.approx(u["startingArmy"]["labor"]["seconds"])


def test_cost_corrections_leave_fixed_seed_combat_trajectories_unchanged(store):
    configs = []
    for civ, uid in [("Magyars", 871), ("Mapuche", 2571), ("Mayans", 492), ("Mayans", 765)]:
        a, b = selection(civ, uid, 3), selection("Spanish", 567, 3)
        configs.extend([config(a, b), config(a, b, store=store)])
    result = subprocess.run(["node", str(ROOT / "tests/army_economics_combat.mjs")], input=json.dumps(configs),
                            text=True, capture_output=True, timeout=180, check=True)
    results = json.loads(result.stdout)
    assert len(results) == 8
    for i in range(0, 8, 2):
        assert results[i] == results[i + 1]


def test_free_upgrades_refunds_and_persian_work_rates(store):
    with sqlite3.connect(RUNTIME) as c:
        def civ(name):
            return json.loads(c.execute('SELECT payload FROM civilizations WHERE civ=?', (name,)).fetchone()[0])
        vikings = {t["id"]: t for t in civ("Vikings")["technologies"]}
        assert vikings[213]["seconds"] == 0  # Wheelbarrow
        assert not any(vikings[213]["upfront"].values())
        persians = {t["id"]: t for t in civ("Persians")["technologies"]}
        assert persians[213]["seconds"] == pytest.approx(62.5)
    a = selection("Spanish", 567)
    ts = store.response(config(a, a, store=store))["teams"][0]["research"]["military"]["technologies"]
    assert any(t["refund"]["gold"] == 20 for t in ts)
    assert all(t["net"]["gold"] == pytest.approx(t["upfront"]["gold"] - t["refund"]["gold"]) for t in ts)


def test_flemish_population_is_explicit_and_does_not_poison_cache(store):
    a = selection("Burgundians", 1699)
    battle = config(a, a, store=store)
    def f(response):
        return next(t for t in response["teams"][0]["research"]["military"]["technologies"] if t["id"] == 755)
    base = f(store.response(battle)); variable = f(store.response(battle, [50, None]))
    assert base["upfront"]["food"] == 200
    assert variable["upfront"]["food"] == 700
    assert f(store.response(battle)) == base
    for invalid in ([True, None], [-1, None], [1.5, None], [1], "50"):
        with pytest.raises(ValueError):
            store.response(battle, invalid)


def test_pasture_estimate_and_release_gate_are_honest(store, tmp_path):
    a = selection("Khitans", 567)
    u = store.response(config(a, a, store=store))["teams"][0]
    assert u["startingArmy"]["labor"] is not None
    assert not u["economy"]["blockers"]
    assert u["investment"]["labor"] is not None
    assert u["economy"]["pastureModel"]["foodPerVillagerMinute"] == pytest.approx(25.2)
    assert store.metadata["releaseReady"]
    released = ArmyContext(RUNTIME, "released")
    assert released.response(config(a, a, store=released))["status"] == "estimate"
    # A waiver of gathering measurements must not bypass other release blockers.
    blocked = tmp_path / "blocked.db"
    with sqlite3.connect(blocked) as db:
        db.execute("CREATE TABLE metadata (id INTEGER PRIMARY KEY, payload TEXT)")
        db.execute("INSERT INTO metadata VALUES(1, ?)", (json.dumps({**store.metadata, "releaseReady": False}),))
    with pytest.raises(ContextUnavailable):
        ArmyContext(blocked, "released")
    a = selection("Spanish", 567)
    bad = config(a, a)["teams"][0]; bad["mechanics_hash"] = "changed"
    with pytest.raises(ContextUnavailable):
        store.unit(bad)


@pytest.mark.parametrize("schema", [1, 2])
def test_previous_schema_is_rejected(store, tmp_path, schema):
    old = tmp_path / "old-context.db"
    metadata = {**store.metadata, "schemaVersion": schema}
    with sqlite3.connect(old) as db:
        db.execute("CREATE TABLE metadata (id INTEGER PRIMARY KEY, payload TEXT)")
        db.execute("INSERT INTO metadata VALUES(1, ?)", (json.dumps(metadata),))
    with pytest.raises(ContextUnavailable, match="Unsupported army context schema"):
        ArmyContext(old, "review")


def test_endpoint_disabled_review_validation_and_combat_fallback(client, monkeypatch):
    import app as website
    monkeypatch.setitem(website.app.config, "ARMY_CONTEXT_DB", str(RUNTIME))
    monkeypatch.setitem(website.app.config, "ARMY_ECONOMICS_MODE", "off")
    a = selection("Spanish", 567)
    payload = {"teams": [a, a], "army": {"mode": "explicit"}, "engagement_mode": "direct"}
    assert client.post('/api/v3/army-context', json=payload).status_code == 404
    monkeypatch.setitem(website.app.config, "ARMY_ECONOMICS_MODE", "review")
    assert client.post('/api/v3/army-context', json=payload).status_code == 200
    assert client.post('/api/v3/army-context', json={**payload, "contextVersion": "stale"}).status_code == 409
    assert client.post('/api/v3/army-context', json={**payload, "convertedVillagers": [True, None]}).status_code == 400
    assert client.post('/api/v3/army-context', json=[]).status_code == 400
    monkeypatch.setitem(website.app.config, "ARMY_CONTEXT_DB", "/tmp/no-such-army-context.db")
    assert client.post('/api/v3/army-context', json=payload).status_code == 503
    battle = client.post('/api/v3/battle-config', json=payload)
    assert battle.status_code == 200
    assert battle.json["armyContextVersion"] is None


@pytest.mark.parametrize("left,right,buildings", [
    (("Spanish", 567), ("Saracens", 492), [3, 4]),
    (("Spanish", 567), ("Saracens", 567), [3, 3]),
    (("Chinese", 492), ("Saracens", 492), [4, 4]),
])
def test_endpoint_investment_uses_only_common_techs_and_correct_infrastructure(store, left, right, buildings):
    a, b = selection(*left, 7), selection(*right, 7)
    response = store.response(config(a, b, store=store))
    for i, team in enumerate(response["teams"]):
        common = response["researchComparison"]["common"][i]
        score = team["investment"]
        assert score["components"]["commonResearch"] == common["net"]
        assert score["cost"] == add_costs(team["startingArmy"]["cost"], team["production"]["investmentCost"], common["net"])
        assert score["labor"]["seconds"] == pytest.approx(solve_labor(weighted_cost(score["cost"]), team["economy"]["activities"])["seconds"])
        assert team["startingArmy"]["trainingSeconds"] <= 60
        assert team["replacementLookup"][0]["weightedLabor"]["seconds"] == 0
        assert all(b["alreadyAvailable"] == (b["id"] == team["production"]["id"]) for b in team["research"]["allInfrastructure"]["buildings"])
    if left[1] == right[1]:
        assert response["researchComparison"]["common"][0]["technologyCount"] > 0
        if left[0] == "Spanish":
            assert response["researchComparison"]["common"][0]["refund"]["gold"] > 0
        if left[0] == "Chinese":
            assert sum(response["researchComparison"]["common"][0]["upfront"].values()) < sum(response["researchComparison"]["common"][1]["upfront"].values())
    else:
        assert response["researchComparison"]["exclusive"][0]["technologyCount"] > 0
    assert [t["production"]["buildingCount"] for t in response["teams"]] == buildings
    assert store.response(config(a, a, store=store))["investmentComparison"]["lowerTeam"] is None


def test_all_compiled_economies_match_offline_solver(store):
    with sqlite3.connect(RUNTIME) as db:
        economies = [json.loads(r[0]) for r in db.execute("SELECT payload FROM civilizations")]
    for economy in economies:
        if economy["blockers"]:
            assert economy["laborPrices"] is None
            continue
        for cost in ({"food": 800, "wood": 600, "gold": 1000, "stone": 1950},
                     {"food": 80}, {"food": 200, "gold": -40}, {"wood": 200, "stone": 350}):
            bill = weighted_cost(cost)
            assert compiled_labor(bill, economy["laborPrices"])["seconds"] == pytest.approx(solve_labor(bill, economy["activities"])["seconds"])


def test_explicit_scope_exceptions_do_not_pretend_validation(store):
    excluded = store.metadata["scopeExceptions"]
    assert {(r["civ"], r.get("unitId"), r.get("technologyId")) for r in excluded} == {
        ("Wei", None, 1061), ("Berbers", 1631, None), ("Chinese", 529, None), ("Burgundians", None, 755)}
    assert all(r["status"] == "excluded_by_user" for r in excluded)
    assert not any(r["code"] in ("unresolved_training_route", "dynamic_research_cost_unvalidated") for r in store.metadata["blockers"])
    assert store.metadata["blockers"] == []
    assert store.metadata["gatheringValidation"]["status"] == "deferred_by_user"
    a = selection("Wei", 441)
    response = store.response(config(a, a, store=store))
    assert response["teams"][0]["investment"]["labor"] is not None
    economy = response["teams"][0]["economy"]
    assert not economy["blockers"]
    assert economy["scopeExceptions"][0]["technologyId"] == 1061
    effect = next(e for e in economy["effects"] if e["technologyId"] == 1061)
    assert effect["calculationStatus"] == "excluded_by_user"
    assert response["auraAssumption"]["coverage"] == 1
    assert response["auraAssumption"]["placementRequired"] is False
    assert response["auraAssumption"]["infrastructureCostIncluded"] is False
    assert response["releaseReady"]
    assert response["status"] == "estimate"


def test_pasture_animals_and_herders_are_independent_source_parameters(store):
    a = selection("Khitans", 567)
    source = store.response(config(a, a, store=store))["teams"][0]["economy"]["pastureSourceInputs"]
    assert source["food"] == 1035
    assert source["animalCount"] == 9
    assert source["herderCount"] == 2
    assert source["actors"]["1892"]["roundedCarry"] == 6
    assert source["actors"]["1889"]["cost"]["wood"] == 110
    assert {e["technologyId"] for e in source["evidence"]} == {1012, 1013, 1014}
    assert source["status"] == "online_reference_estimate"


def test_scope_waivers_are_narrow():
    from tools.army_context_policy import exclusion_reason
    assert exclusion_reason({"code": "unresolved_economy_mechanic", "civ": "Wei", "technologyId": 1061})
    assert exclusion_reason({"code": "unresolved_economy_mechanic", "civ": "Wei", "technologyId": 9999}) is None
    assert exclusion_reason({"code": "controlled_observations_missing"}) is None
    assert exclusion_reason({"code": "unresolved_training_route", "civ": "Chinese", "unitId": 492}) is None


@pytest.mark.parametrize("civ,resource,kind", [
    ("Burgundians", "food", "gold_per_active_gathering_minute"),
    ("Vietnamese", "wood", "gold_per_active_gathering_minute"),
    ("Georgians", "food", "worker_work_rate_aura"),
    ("Malians", "gold", "extra_dropoff_credit"),
    ("Poles", "stone", "coproduct"), ("Shu", "wood", "coproduct"),
])
def test_resolved_special_economies_reach_runtime_without_claiming_validation(store, civ, resource, kind):
    with sqlite3.connect(RUNTIME) as db:
        economy = json.loads(db.execute("SELECT payload FROM civilizations WHERE civ=?", (civ,)).fetchone()[0])
    assert not economy["blockers"]
    assert economy["laborPrices"]
    activity = next(a for a in economy["activities"] if a["id"] == resource)
    mechanic = next(m for m in activity["appliedMechanics"] if m["kind"] == kind)
    assert mechanic["technologyIds"]
    assert activity["status"] == "scenario_estimate"
    assert store.metadata["releaseReady"]
    assert store.metadata["gatheringValidation"]["status"] != "validated"
    if kind == "gold_per_active_gathering_minute":
        assert 0 < activity["outputs"]["gold"] < mechanic["value"] / 60
    if resource == "food":
        assert activity["outputs"]["wood"] < 0
