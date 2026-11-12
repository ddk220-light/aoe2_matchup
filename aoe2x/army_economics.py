"""Army purchase, queue and research accounting; independent of combat outcomes.

Gathering outputs are resources per villager-second. Negative outputs represent
recurring inputs (farm wood), not a separate charge added after optimization.
SciPy is imported only by the offline compiler's labor solver.
"""
from __future__ import annotations

import math

RESOURCES = ("food", "wood", "gold", "stone")
CONTEXT_SCHEMA_VERSION = 3
TRAINING_WINDOW_SECONDS = 60
RESOURCE_WEIGHTS = {"food": 1, "wood": 1, "gold": 1.5, "stone": 3}
MAX_ARMY = 27


def resources(values=None):
    return {r: float((values or {}).get(r, 0)) for r in RESOURCES}


def building_value(cost):
    return sum(cost.get(r, 0) * RESOURCE_WEIGHTS[r] for r in RESOURCES)


def purchase_bill(count, purchase_cost, units_per_purchase=1):
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= MAX_ARMY:
        raise ValueError(f"unit count must be an integer between 0 and {MAX_ARMY}")
    if not isinstance(units_per_purchase, int) or units_per_purchase < 1:
        raise ValueError("units per purchase must be a positive integer")
    if any(not math.isfinite(v) or v < 0 for v in resources(purchase_cost).values()):
        raise ValueError("purchase costs must be finite and nonnegative")
    orders = math.ceil(count / units_per_purchase)
    return {"count": count, "orders": orders,
            "producedUnits": orders * units_per_purchase,
            "surplusUnits": orders * units_per_purchase - count,
            "cost": {r: v * orders for r, v in resources(purchase_cost).items()}}


def add_costs(*costs):
    return {r: sum(c.get(r, 0) for c in costs) for r in RESOURCES}


def weighted_cost(cost):
    return {r: cost.get(r, 0) * RESOURCE_WEIGHTS[r] for r in RESOURCES}


def compile_labor_prices(activities):
    """Offline vertices of the labor LP dual: max demand·price, Aᵀprice ≤ 1.

    Evaluating these precomputed linear functions gives the exact optimum for
    any combined bill, including coproducts and refunds, without a runtime LP.
    A complete model must be able to supply every resource independently.
    """
    from itertools import combinations
    import numpy as np
    if not activities or any(solve_labor({r: 1}, activities) is None for r in RESOURCES):
        return None
    matrix = np.array([[a["outputs"].get(r, 0) for r in RESOURCES] for a in activities]
                      + (-np.eye(len(RESOURCES))).tolist())
    limits = np.array([1.] * len(activities) + [0.] * len(RESOURCES))
    vertices = {}
    for active in combinations(range(len(limits)), len(RESOURCES)):
        try:
            prices = np.linalg.solve(matrix[list(active)], limits[list(active)])
        except np.linalg.LinAlgError:
            continue
        if not np.isfinite(prices).all() or (matrix @ prices > limits + 1e-9).any():
            continue
        prices = np.maximum(prices, 0)
        vertices[tuple(np.round(prices, 12))] = prices.tolist()
    if not vertices:
        raise ValueError("No labor price vertices for a feasible economy")
    return list(vertices.values())


def compiled_labor(cost, prices):
    """Evaluate offline labor functions; negative resource bills are rebates."""
    demand = list(resources(cost).values())
    if any(not math.isfinite(v) for v in demand):
        raise ValueError("Resource bill must be finite")
    if all(v <= 0 for v in demand):
        seconds = 0.0
    elif prices is None:
        return None
    else:
        seconds = max(0.0, max(sum(v * p for v, p in zip(demand, row)) for row in prices))
    return {"seconds": seconds, "villagerMinutes": seconds / 60}


def production_for_window(route, orders, units_per_purchase=1):
    """Whole buildings completing all purchase orders within the fixed window."""
    result = {**(route or {}), "windowSeconds": TRAINING_WINDOW_SECONDS,
              "buildingCount": None, "investmentCost": None, "weightedInvestmentCost": None,
              "ordersPerBuilding": None, "trainingSeconds": None, "spareUnitCapacity": None}
    if route is None:
        return {**result, "status": "unresolved_training_route"}
    seconds = route["secondsPerOrder"]
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Training time must be positive and finite")
    if any(not math.isfinite(v) or v < 0 for v in resources(route["cost"]).values()):
        raise ValueError("Building costs must be finite and nonnegative")
    per_building = math.floor(TRAINING_WINDOW_SECONDS / seconds)
    result["ordersPerBuilding"] = per_building
    if orders and not per_building:
        return {**result, "status": "training_exceeds_window"}
    count = math.ceil(orders / per_building) if orders else 0
    return {**result, "status": "modeled", "buildingCount": count,
            "investmentCost": {r: v * count for r, v in resources(route["cost"]).items()},
            "weightedInvestmentCost": building_value(route["cost"]) * count,
            "trainingSeconds": math.ceil(orders / count) * seconds if orders else 0,
            "spareUnitCapacity": (count * per_building - orders) * units_per_purchase}


def select_investment_route(routes, orders, batch, base_cost, prices):
    alternatives = [production_for_window(r, orders, batch) for r in routes]
    feasible = [r for r in alternatives if r["status"] == "modeled"]
    for route in feasible:
        route["combinedLabor"] = compiled_labor(weighted_cost(add_costs(base_cost, route["investmentCost"])), prices)
    if not feasible:
        result = production_for_window(None, orders, batch)
        if alternatives:
            result["status"] = "training_exceeds_window"
        return result, alternatives
    # Withheld labor can still show a provisional resource-priced building
    # setup. It never makes the headline investment score available.
    feasible.sort(key=lambda r: (r["combinedLabor"]["seconds"] if r["combinedLabor"] is not None
                                else r["weightedInvestmentCost"],
                                r["trainingSeconds"], r["id"], r.get("trainedUnitId", 0)))
    return feasible[0], feasible + [r for r in alternatives if r["status"] != "modeled"]


def queue_seconds(orders, production):
    if orders == 0:
        return 0.0
    count = production["buildingCount"]
    seconds = production.get("secondsPerOrder")
    if count is None or count <= 0 or seconds is None:
        return None
    return math.ceil(orders / count) * seconds


def army_investment(army_cost, production, common_research, prices):
    status = production["status"]
    if status == "modeled" and not common_research["costIsFixed"]:
        status = "unresolved_common_research_cost"
    if status == "modeled" and prices is None:
        status = "unresolved_labor"
    components = {"army": resources(army_cost), "buildings": production["investmentCost"],
                  "commonResearch": common_research["net"]}
    bill = add_costs(*components.values()) if components["buildings"] is not None else None
    return {"status": status, "components": components, "cost": bill,
            "weightedCost": weighted_cost(bill) if bill is not None else None,
            "standaloneLabor": {key: compiled_labor(weighted_cost(cost), prices)
                                if cost is not None and (key != "commonResearch" or common_research["costIsFixed"])
                                else None for key, cost in components.items()},
            "labor": compiled_labor(weighted_cost(bill), prices) if status == "modeled" else None}


def investment_comparison(teams):
    scores = [t["investment"]["labor"] for t in teams]
    if any(x is None for x in scores):
        return {"status": "unavailable", "lowerTeam": None, "savingPercent": None}
    a, b = [s["seconds"] for s in scores]
    equal = math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return {"status": "available", "lowerTeam": None if equal else (1 if a < b else 2),
            "savingPercent": 0 if equal else 100 * (1 - min(a, b) / max(a, b))}


def solve_labor(cost, activities):
    """Minimum work satisfying a resource vector; no sale of unused surplus."""
    demand = resources(cost)
    if not any(demand.values()):
        return {"seconds": 0.0, "villagerMinutes": 0.0, "workByActivity": {},
                "surplus": resources()}
    from scipy.optimize import linprog
    if not activities:
        return None
    for activity in activities:
        if any(not math.isfinite(v) for v in resources(activity["outputs"]).values()):
            raise ValueError("activity outputs must be finite")
    result = linprog(
        [1.0] * len(activities),
        A_ub=[[-a["outputs"].get(r, 0) for a in activities] for r in RESOURCES],
        b_ub=[-demand[r] for r in RESOURCES], bounds=(0, None), method="highs",
    )
    if result.status == 2:  # Missing activity; never substitute a generic rate.
        return None
    if not result.success:
        raise RuntimeError(f"labor optimization failed: {result.message}")
    surplus = {r: sum(a["outputs"].get(r, 0) * seconds
                      for a, seconds in zip(activities, result.x)) - demand[r]
               for r in RESOURCES}
    if min(surplus.values()) < -1e-6:
        raise RuntimeError("labor optimizer failed resource conservation")
    return {"seconds": float(result.fun), "villagerMinutes": float(result.fun / 60),
            "workByActivity": {a["id"]: float(s) for a, s in zip(activities, result.x) if s > 1e-8},
            "surplus": {r: max(0.0, float(v)) for r, v in surplus.items()}}


def research_totals(technologies):
    rows = {t["id"]: t for t in technologies}.values()
    rows = list(rows)
    workload = None if any(t["seconds"] is None for t in rows) else sum(t["seconds"] for t in rows)
    by_building = {}
    for t in rows:
        if t["seconds"] is not None and t["seconds"] > 0:
            name = t.get("building", {}).get("name", "Unknown")
            by_building[name] = by_building.get(name, 0) + t["seconds"]
    return {"technologyCount": len(rows), "workloadSeconds": workload,
            "workloadByBuilding": by_building,
            "costIsFixed": all(t.get("costIsFixed", True) for t in rows),
            **{kind: {r: sum(t[kind].get(r, 0) for t in rows) for r in RESOURCES}
               for kind in ("upfront", "refund", "net")}}


def compare_research(left, right):
    maps = [{t["id"]: t for t in side} for side in (left, right)]
    common = maps[0].keys() & maps[1].keys()
    common_sides = [research_totals([m[k] for k in sorted(common)]) for m in maps]
    return {"commonIds": sorted(common), "common": common_sides,
            "exclusive": [research_totals([t for k, t in m.items() if k not in common]) for m in maps],
            "commonWorkloadDifferenceSeconds": (
                common_sides[0]["workloadSeconds"] - common_sides[1]["workloadSeconds"]
                if all(s["workloadSeconds"] is not None for s in common_sides) else None),
            "commonCostDifference": {
                r: common_sides[0]["net"][r] - common_sides[1]["net"][r] for r in RESOURCES}}


def research_infrastructure(technologies, production):
    buildings = {}
    existing = production.get("id") if production.get("buildingCount", 0) else None
    for tech in technologies:
        building = tech.get("building")
        if not building or tech.get("automaticFree"):
            continue
        buildings[building["id"]] = {**building, "alreadyAvailable": building["id"] == existing}
    rows = [buildings[k] for k in sorted(buildings)]
    return {"buildings": rows, "additionalCost": {
        r: sum(b["cost"].get(r, 0) for b in rows if not b["alreadyAvailable"]) for r in RESOURCES}}
