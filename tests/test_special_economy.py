import json

import pytest

from aoe2x.army_economics import resources, solve_labor
from tools.special_economy import apply_special_economy, pasture_activity


def activities():
    return [{"id": r, "outputs": resources({r: .5, **({"wood": -.05} if r == "food" else {})}),
             "scenarioSignature": r} for r in ("food", "wood", "gold", "stone")]


def parameter(rid, value, tech=1, effect=2):
    return {rid: {"final_parameter_value": value, "evidence": json.dumps([{"tech_id": tech, "effect_id": effect}])}}


@pytest.mark.parametrize("rid,resource,value", [(236, "food", 2), (266, "wood", 2.376)])
@pytest.mark.parametrize("fraction", [0, .8, 1])
def test_timed_income_excludes_all_non_gathering_time(rid, resource, value, fraction):
    original = activities()
    result, resolved = apply_special_economy(original, parameter(rid, value),
        {resource: {"activeFraction": fraction, "scenarioSignature": "counter"}}, [], None)
    activity = next(r for r in result if r["id"] == resource)
    assert activity["outputs"]["gold"] == pytest.approx(value / 60 * fraction)
    assert next(r for r in result if r["id"] == "food")["outputs"]["wood"] == -.05
    assert original == activities()
    assert resolved == {2}


def test_secondary_resources_share_the_same_labor_and_no_surplus_resale():
    result, _ = apply_special_economy(activities(), parameter(241, 100 / 3), {}, [], None)
    # 300 stone creates 100 gold using one 600-second activity.
    labor = solve_labor({"stone": 300, "gold": 100}, result)
    assert labor["seconds"] == pytest.approx(600)
    assert solve_labor({"stone": 300}, result)["seconds"] == pytest.approx(600)
    assert solve_labor({}, result)["seconds"] == 0
    result, _ = apply_special_economy(activities(), parameter(502, 7), {}, [], None)
    assert solve_labor({"wood": 100, "food": 7}, result)["seconds"] == pytest.approx(200)


def test_malian_dropoff_credit_preserves_gathering_scenario():
    result, _ = apply_special_economy(activities(), parameter(276, 10), {}, [], None)
    gold = next(r for r in result if r["id"] == "gold")
    assert gold["outputs"]["gold"] == pytest.approx(.55)
    assert gold["appliedMechanics"][0]["carryAndWorkRateUnchanged"]


def test_aura_uses_simulated_delivered_rates_and_preserves_farm_cost():
    scenarios = {r: {"rate": .53, "scenarioSignature": "faster-work", "auraApplied": True}
                 for r in ("food", "wood", "gold", "stone")}
    result, resolved = apply_special_economy(activities(), {}, scenarios, [{"effect_id": 939}], None)
    assert result[0]["outputs"]["food"] == .53
    assert result[0]["outputs"]["wood"] == pytest.approx(-.053)
    assert resolved == {939}
    _, resolved = apply_special_economy(activities(), {}, {}, [{"effect_id": 939}], None)
    assert resolved == set()


def test_missing_active_counter_does_not_resolve_timed_gold():
    result, resolved = apply_special_economy(activities(), parameter(236, 2), {}, [], None)
    assert result == activities()
    assert resolved == set()


def test_pasture_lifecycle_rate_and_civilization_wood_labor_are_counted_once():
    from pathlib import Path
    reference = json.loads((Path(__file__).resolve().parents[1] /
        "aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/pasture-online-reference.json").read_text())
    source = {"food": 1035, "herderCount": 2, "actors": {"1889": {"cost": {"wood": 110}}},
              "evidence": [{"technologyId": 1012}, {"technologyId": 1013}, {"technologyId": 1014}]}
    pasture = pasture_activity(source, reference)
    assert pasture["outputs"]["food"] == pytest.approx(25.2 / 60)
    assert pasture["outputs"]["wood"] / pasture["outputs"]["food"] == pytest.approx(-110 / 1035)
    for wood_rate in (.4, .6):
        jobs = [pasture, {"id": "wood", "outputs": resources({"wood": wood_rate})}]
        assert solve_labor({"food": 1035}, jobs)["seconds"] == pytest.approx(1035 / (25.2 / 60) + 110 / wood_rate)
        assert solve_labor({}, jobs)["seconds"] == 0
    assert pasture["status"] == "online_reference_estimate"
    assert pasture["appliedMechanics"][0]["assumptions"]["externalDropoffTravelSeconds"] == 0
