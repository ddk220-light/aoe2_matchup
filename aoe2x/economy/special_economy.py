"""Source-derived secondary outputs; engine behavior supported by review evidence.

These mechanisms are scenario estimates, never substitutes for measured captures.
"""
from copy import deepcopy
import hashlib
import json
import math

# Resource IDs describe reusable engine hooks. Values come from DAT replay.
TIMED_GOLD = {236: "food", 266: "wood"}
COPRODUCT = {241: ("stone", "gold"), 502: ("wood", "food")}


def pasture_activity(source, reference):
    """Use the authorized lifecycle average; charge renewal wood in its vector."""
    rate = reference["foodPerVillagerMinute"] / 60
    food = source["food"]
    cost = source["actors"]["1889"]["cost"]["wood"]
    if not all(math.isfinite(x) and x > 0 for x in (rate, food, cost)):
        raise ValueError("Pasture rate, yield and renewal wood must be positive")
    if not reference["assumptions"]["rateIncludesRebuilding"]:
        raise ValueError("Pasture reference must include lifecycle rebuilding time")
    technology_ids = sorted({e["technologyId"] for e in source["evidence"]})
    model = {"kind": "pasture_online_average", "foodPerVillagerMinute": rate * 60,
             "woodPerFood": cost / food, "foodPerPasture": food, "woodPerPasture": cost,
             "workersPerPasture": source["herderCount"], "technologyIds": technology_ids,
             "reference": reference["reference"], "assumptions": reference["assumptions"],
             "description": f"Pasture estimate: {rate * 60:g} food/villager-minute, immediate food credit; {cost:g} wood per {food:g} food. Lifecycle rate includes rebuilding."}
    return {"id": "food", "outputs": {"food": rate, "wood": -rate * cost / food, "gold": 0, "stone": 0},
            "status": "online_reference_estimate", "appliedMechanics": [model],
            "scenarioSignature": hashlib.sha256(json.dumps(
                {"source": source, "reference": reference}, sort_keys=True).encode()).hexdigest()}


def apply_special_economy(activities, parameters, scenarios, pending, online_source):
    activities = deepcopy(activities)
    by_resource = {a["id"]: a for a in activities}
    resolved = set()
    aura = any(r["effect_id"] == 939 for r in pending)
    if aura and all(r in scenarios for r in ("food", "wood", "gold", "stone")):
        for resource, activity in by_resource.items():
            scenario = scenarios[resource]
            if not scenario["auraApplied"]:
                raise ValueError("Church scenario must include the work-rate aura")
            scale = scenario["rate"] / activity["outputs"][resource]
            activity["outputs"] = {r: v * scale for r, v in activity["outputs"].items()}
            activity.update(scenarioSignature=scenario["scenarioSignature"],
                            appliedMechanics=[{"kind": "worker_work_rate_aura", "workRateMultiplier": 1.1,
                                              "coverage": 1, "infrastructureCostIncluded": False,
                                              "technologyIds": [934], "source": online_source,
                                              "includesReseedingWork": True}])
        resolved.add(939)
    for rid, parameter in parameters.items():
        value = parameter["final_parameter_value"]
        if value <= 0 or rid not in (*TIMED_GOLD, *COPRODUCT, 276):
            continue
        evidence = json.loads(parameter["evidence"])
        mechanic = {"resourceParameterId": rid, "value": value, "evidence": evidence,
                    "technologyIds": sorted({r["tech_id"] for r in evidence}),
                    "semanticsSource": "User confirmation 2026-11-11; online game descriptions",
                    "onlineSource": online_source}
        if rid in TIMED_GOLD:
            resource = TIMED_GOLD[rid]
            scenario = scenarios.get(resource)
            if scenario is None:
                continue
            fraction = scenario["activeFraction"]
            if not 0 <= fraction <= 1:
                raise ValueError("Active gathering fraction must be between zero and one")
            activity = by_resource[resource]
            activity["outputs"]["gold"] += value / 60 * fraction
            mechanic.update(kind="gold_per_active_gathering_minute", activeFraction=fraction,
                            activeTimeSource=scenario["scenarioSignature"],
                            excludedTime=["walking", "drop-off", "construction", "idle", "tree felling"])
        elif rid in COPRODUCT:
            resource, secondary = COPRODUCT[rid]
            activity = by_resource[resource]
            activity["outputs"][secondary] += activity["outputs"][resource] * value / 100
            mechanic.update(kind="coproduct", primary=resource, secondary=secondary, ratio=value / 100)
        else:
            activity = by_resource["gold"]
            activity["outputs"]["gold"] *= 1 + value / 100
            mechanic.update(kind="extra_dropoff_credit", carryAndWorkRateUnchanged=True,
                            timing="Bonus is credited on deposit; output is the long-run credited yield, including eventual deposit of carried gold.")
        activity.setdefault("appliedMechanics", []).append(mechanic)
        activity["scenarioSignature"] = hashlib.sha256(json.dumps(
            {"base": activity["scenarioSignature"], "mechanic": mechanic}, sort_keys=True).encode()).hexdigest()
        resolved.update(e["effect_id"] for e in evidence)
    return activities, resolved
