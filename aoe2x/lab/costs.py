"""Fail closed on legacy, stale, or incorrectly balanced capture plans."""

import hashlib
import json
import math
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2] / "data/recording-costs.json"


def validate_plan_costs(plan):
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw)
    balance = plan["balance"]
    if balance["mode"] not in (
        "equal_resources",
        "equal_count",
        "explicit",
        "geometric_shared_discount",
    ):
        raise ValueError("Unsupported balance mode")
    cap = balance["cap"]
    if type(cap) is not int or not 1 <= cap <= 27:
        raise ValueError("Invalid army cap")
    if (
        balance.get("costBasis") != catalog["costBasis"]
        or balance.get("costCatalogSha256") != hashlib.sha256(raw).hexdigest()
    ):
        raise ValueError(
            "Legacy or stale cost basis: create a new corrected job; never overwrite an archived capture"
        )
    costs = []
    if "maxResources" in balance:
        budget = balance["maxResources"]
        if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
            raise ValueError("Invalid resource ceiling")
    weights = balance["weights"]
    if set(weights) != {"food", "wood", "gold"} or any(
        type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100
        for v in weights.values()
    ):
        raise ValueError("Invalid resource weights")
    for key in ("side2", "side3"):
        side = plan[key]
        if type(side["count"]) is not int or not 1 <= side["count"] <= cap:
            raise ValueError("Invalid army count")
        effective = catalog["units"][side["civ"] + "|" + side["slug"]]["effectiveCost"]
        cost = sum(effective[r] * weights[r] for r in weights)
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError("Invalid effective cost")
        if (
            side.get("effectiveCost") != effective
            or side["weightedCost"] != cost
            or side["armyWeightedResources"] != side["count"] * cost
        ):
            raise ValueError("Incorrect effective unit cost or army resource total")
        costs.append(cost)
    if balance["mode"] == "equal_resources":
        a, b = costs
        if min(a, b) <= 0:
            raise ValueError("Non-positive weighted cost")
        cap = balance["cap"]
        budget = balance.get("maxResources", math.inf)
        n = min(cap, math.floor(budget / min(a, b))) if math.isfinite(budget) else cap
        expected = [n, math.floor(n * a / b)] if a <= b else [math.floor(n * b / a), n]
        if not math.isfinite(budget):
            expected = [max(1, count) for count in expected]
        if [plan["side2"]["count"], plan["side3"]["count"]] != expected:
            raise ValueError("Army counts do not match effective civilization costs")
    elif balance["mode"] == "geometric_shared_discount":
        policy_path = CATALOG.with_name("recording-balance.json")
        policy_bytes = policy_path.read_bytes()
        policy = json.loads(policy_bytes)
        if (
            policy.get("schemaVersion") != 1
            or policy.get("policy") != "geometric_shared_discount_unit_count_v2"
            or policy.get("populationMode") != "one_per_unit"
            or [
                policy.get(k + "DiscountEffectiveness")
                for k in ("food", "wood", "gold")
            ]
            != [0.5, 0.5, 1.0]
        ):
            raise ValueError("Unsupported geometric benchmark policy")
        sha = hashlib.sha256(policy_bytes).hexdigest()
        if (
            balance.get("comparisonCatalogSha256") != sha
            or balance.get("comparisonPolicy") != policy["policy"]
        ):
            raise ValueError("Stale geometric benchmark catalog")
        scores = []
        for key in ("side2", "side3"):
            side = plan[key]
            identity = side["civ"] + "|" + side["slug"]
            price, entry = catalog["units"][identity], policy["units"][identity]
            if (
                entry["master"] != price["master"]
                or type(entry["sharedAcrossCivilizations"]) is not bool
                or not math.isfinite(entry["population"])
                or entry["population"] <= 0
                or type(price["unitsPerPurchase"]) is not int
                or price["unitsPerPurchase"] < 1
            ):
                raise ValueError("Invalid geometric unit identity")
            base = {
                r: v / price["unitsPerPurchase"] for r, v in price["baseCost"].items()
            }
            comparison = dict(price["effectiveCost"])
            if entry["sharedAcrossCivilizations"]:
                for r in ("food", "wood"):
                    comparison[r] += 0.5 * max(0, base[r] - comparison[r])
            cost = sum(comparison[r] * weights[r] for r in weights)
            expected = dict(
                policy=policy["policy"],
                catalogSha256=sha,
                basePerUnit=base,
                comparisonResources=comparison,
                comparisonCost=cost,
                population=1,
                catalogPopulation=entry["population"],
                sharedAcrossCivilizations=entry["sharedAcrossCivilizations"],
                score=cost,
            )
            if (
                side.get("comparison") != expected
                or not math.isfinite(expected["score"])
                or expected["score"] <= 0
            ):
                raise ValueError("Invalid geometric comparison evidence")
            scores.append(expected["score"])
        a, b = scores
        cap = balance["cap"]
        smaller = max(
            1, min(cap, math.floor(cap * math.sqrt(min(a, b) / max(a, b)) + 0.5))
        )
        counts = [cap, smaller] if a <= b else [smaller, cap]
        if [plan[s]["count"] for s in ("side2", "side3")] != counts:
            raise ValueError("Counts do not match geometric benchmark")
        if any(
            plan[s]["armyWeightedResources"] > balance.get("maxResources", math.inf)
            for s in ("side2", "side3")
        ):
            raise ValueError("Geometric army exceeds actual-resource ceiling")
    return {
        "costBasis": catalog["costBasis"],
        "costCatalogSha256": balance["costCatalogSha256"],
        "verified": True,
    }
