"""Build engine inputs independently of Flask or the legacy combat adapter."""
import secrets
from aoe2x.dbgen.v3_mechanics import MECHANICS_SCHEMA_VERSION
from aoe2x.js_simulation.scenario_config import build_scenario_payload
from .mechanics import _find_ref_unit, _load_v3_mechanics, _load_v3_auxiliary_mechanics

_V3_FAMILY_CAPACITIES = {
    # The public Golden Arena supplies 27 authored placement cells on both
    # sides for every visual family. Internal calibration tables may be smaller,
    # but public fights pass these explicit scenario placements to the engine.
    "rvr": (27, 27),
    "kite": (27, 27),
    "siege": (27, 27),
    "waves": (27, 27),
}


def _v3_engine_family(class2, class3):
    ranged = {"mobile_ranged", "siege_ranged"}
    if class2 in ranged and class3 in ranged:
        return "rvr"
    if "mobile_ranged" in (class2, class3):
        return "kite"
    if "siege_ranged" in (class2, class3):
        return "siege"
    return "waves"


def _v3_visual_family(class2, class3):
    ranged = {"mobile_ranged", "siege_ranged"}
    if class2 not in ranged and class3 not in ranged:
        return "melee_vs_melee"
    if class2 in ranged and class3 in ranged:
        return "ranged_vs_ranged"
    return "ranged_vs_melee" if class2 in ranged else "melee_vs_ranged"


def _v3_public_capacities(class2, class3, family):
    inner2, inner3 = _V3_FAMILY_CAPACITIES[family]
    role = {"kite": "mobile_ranged", "siege": "siege_ranged"}.get(family)
    normalized = role is not None and class3 == role
    return ((inner3, inner2) if normalized else (inner2, inner3)), normalized


def _positive_number(value, label, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return float(value)


def _nonnegative_number(value, label, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{label} must be a nonnegative number")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return float(value)


def _bounded_integer(value, label, *, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if integer != value or integer < minimum or integer > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return integer


def _v3_counts(army, teams, capacities):
    if not isinstance(army, dict):
        raise ValueError("army must be an object")
    mode = army.get("mode", "equal_resources")
    cap = _bounded_integer(army.get("cap", 27), "army.cap", minimum=1, maximum=27)
    limits = (min(cap, capacities[0]), min(cap, capacities[1]))
    if mode == "explicit":
        counts = tuple(
            _bounded_integer(
                team.get("count"), f"team {index} count", minimum=1, maximum=limit
            )
            for index, (team, limit) in enumerate(zip(teams, limits), 1)
        )
    elif mode == "equal_count":
        count = _bounded_integer(
            army.get("count", 20), "army.count", minimum=1, maximum=min(limits)
        )
        counts = (count, count)
    elif mode in {"equal_resources", "resource_budgets"}:
        weights = army.get("weights", {})
        if not isinstance(weights, dict):
            raise ValueError("army.weights must be an object")
        wf = _nonnegative_number(weights.get("food", 1), "food weight", maximum=10)
        ww = _nonnegative_number(weights.get("wood", 1), "wood weight", maximum=10)
        wg = _nonnegative_number(weights.get("gold", 1), "gold weight", maximum=10)
        if wf + ww + wg <= 0:
            raise ValueError("at least one resource weight must be positive")
        costs = []
        for team in teams:
            cost = team["mechanics"]["cost"]
            costs.append(cost["food"] * wf + cost["wood"] * ww + cost["gold"] * wg)
        if costs[0] <= 0 or costs[1] <= 0:
            raise ValueError("selected unit has zero weighted resource cost")
        if mode == "equal_resources":
            budget = _positive_number(
                army.get("budget", 3000), "army.budget", maximum=20000
            )
            cheap = 0 if costs[0] <= costs[1] else 1
            dear = 1 - cheap
            counts = [0, 0]
            counts[cheap] = min(limits[cheap], int(budget // costs[cheap]))
            counts[dear] = min(
                limits[dear],
                max(1, int((counts[cheap] * costs[cheap]) // costs[dear])),
            )
            counts = tuple(counts)
        else:
            budgets = army.get("budgets")
            if not isinstance(budgets, list) or len(budgets) != 2:
                raise ValueError("army.budgets must contain Team A and Team B budgets")
            budgets = tuple(
                _positive_number(value, f"team {index} budget")
                for index, value in enumerate(budgets, 1)
            )
            # Resource-based armies preserve the requested Team A : Team B
            # spending ratio. If either side would exceed the scenario's 27-unit
            # capacity, scale both theoretical counts by the same factor before
            # flooring. Equal budgets therefore retain the established behavior:
            # the cheaper army fills to 27 and the dearer army matches its spend.
            theoretical = tuple(
                budget / cost for budget, cost in zip(budgets, costs)
            )
            scale = min(
                1.0,
                *(limit / count for limit, count in zip(limits, theoretical)),
            )
            counts = tuple(
                min(limit, max(1, int(count * scale)))
                for limit, count in zip(limits, theoretical)
            )
    else:
        raise ValueError(
            "army.mode must be explicit, equal_count, equal_resources, or resource_budgets"
        )
    for index, (count, limit) in enumerate(zip(counts, limits), 1):
        if count < 1 or count > limit:
            raise ValueError(f"team {index} count must be between 1 and {limit}")
    return counts



def build_battle_config(document, *, connect, valid_civs):
    if not isinstance(document, dict):
        raise ValueError("JSON object required")
    selections = document.get("teams")
    if not isinstance(selections, list) or len(selections) != 2:
        raise ValueError("teams must contain exactly two selections")
    connection = connect()
    cursor = connection.cursor()
    teams = []
    try:
        for selection in selections:
            if not isinstance(selection, dict):
                raise ValueError("each team selection must be an object")
            civ = selection.get("civ")
            slug = selection.get("unit_slug")
            age = selection.get("age", "Imperial")
            if not isinstance(civ, str) or civ not in valid_civs():
                raise ValueError(f"unknown civilization {civ!r}")
            if age not in ("Imperial", "imperial"):
                raise ValueError(f"invalid age {age!r}")
            row = _find_ref_unit(cursor, civ, slug, age)
            if row is None:
                raise ValueError(f"unit {slug!r} is unavailable for {civ}")
            combat = _load_v3_mechanics(cursor, row["id"], selection.get("mode"))
            teams.append({
                "civ": civ,
                "unit_slug": slug,
                "unit_name": row["unit_name"],
                "mode": combat["mechanics_mode"],
                "mechanics_hash": combat["mechanics_hash"],
                "mechanics": combat["mechanics"],
                "count": selection.get("count"),
            })
        classes = (teams[0]["mechanics"]["behavior_class"], teams[1]["mechanics"]["behavior_class"])
        engine_family = _v3_engine_family(*classes)
        visual_family = _v3_visual_family(*classes)
        capacities, normalized = _v3_public_capacities(*classes, engine_family)
        counts = _v3_counts(document.get("army", {}), teams, capacities)
        for team, count in zip(teams, counts):
            team["count"] = count
        engagement = document.get("engagement_mode", "direct")
        if engagement not in ("direct", "ranged_buffer"):
            raise ValueError("engagement_mode must be direct or ranged_buffer")
        # The public option is intentionally safe to leave on. It only changes
        # mixed ranged/melee fights; same-family fights continue as direct
        # engagements instead of rejecting an otherwise valid battle.
        if engagement == "ranged_buffer" and visual_family not in (
            "ranged_vs_melee", "melee_vs_ranged"
        ):
            engagement = "direct"
        scenario = build_scenario_payload(
            visual_family,
            engine_family=engine_family,
            include_buffer=engagement == "ranged_buffer",
        )
        if engagement == "ranged_buffer":
            buffer_combat = _load_v3_auxiliary_mechanics(cursor, "scout_cavalry")
            buffer = scenario["auxiliaryArmiesByOwner"]["4"]
            buffer.update(
                {
                    "unit_name": "Scout Cavalry",
                    "mechanics_hash": buffer_combat["mechanics_hash"],
                    "mechanics": buffer_combat["mechanics"],
                }
            )
        seed = document.get("seed")
        if seed is None:
            seed = secrets.randbits(32)
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("seed must be a uint32")
    finally:
        connection.close()
    return {
        "schemaVersion": 1,
        "engineVersion": "simulationv3",
        "mechanicsSchemaVersion": MECHANICS_SCHEMA_VERSION,
        "seed": seed,
        "engagementMode": engagement,
        "teams": teams,
        "scenario": {**scenario, "orientationNormalized": normalized},
    }
