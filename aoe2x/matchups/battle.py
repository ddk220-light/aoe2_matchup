"""Army counts, scenario families and physical contexts.

Python ports of the engine helpers the 2026 inventory used (all in the pinned
engine copy, ``engines/frozen-civ-matchups-v3/aoe2x/js_simulation/``):

* ``deriveRecordedBattleSetup()`` - ``src/battle-setup.js`` (army counts),
* ``isRangedClass()`` / ``scenarioFamilyFor()`` - ``src/lab-scenario.js``,
* ``resolveFamily()`` - ``src/placement.js`` (engine family),
* ``context()`` inside ``profilesAndPairs()`` - RB
  ``aoe2x/js_simulation/node/civ-matchups/phase-one.mjs``.

Counts are computed here (not by the engine) and passed to the engine as
explicit team counts, so the cap and the resource weights are run settings.
"""
from __future__ import annotations

import math

DEFAULT_CAP = 27
DEFAULT_WEIGHTS = {"food": 1, "wood": 0.9, "gold": 1.1}
RANGED_CLASSES = frozenset({"mobile_ranged", "siege_ranged"})


def js_round(value: float) -> int:
    """``Math.round``: halves round toward +infinity."""
    return math.floor(value + 0.5)


def weighted_cost(cost: dict, weights: dict = DEFAULT_WEIGHTS) -> float:
    # Same operation order as battle-setup.js: food + 0.9*wood + 1.1*gold
    # (x*1 == x exactly in IEEE arithmetic, so the food weight is safe).
    return weights["food"] * cost["food"] + weights["wood"] * cost["wood"] + weights["gold"] * cost["gold"]


def army_counts(cost2: float, cost3: float, cap: int = DEFAULT_CAP) -> tuple[int, int]:
    """Cheaper side fields ``cap``; dearer = max(1, round(cap * sqrt(cheaper / dearer)))."""
    n2 = cap if cost2 <= cost3 else max(1, js_round(cap * math.sqrt(cost3 / cost2)))
    n3 = cap if cost3 <= cost2 else max(1, js_round(cap * math.sqrt(cost2 / cost3)))
    return n2, n3


def is_ranged(unit_class: str) -> bool:
    return unit_class in RANGED_CLASSES


def scenario_family(class2: str, class3: str) -> str:
    r2, r3 = is_ranged(class2), is_ranged(class3)
    if not r2 and not r3:
        return "melee_vs_melee"
    if r2 and r3:
        return "ranged_vs_ranged"
    return "ranged_vs_melee" if r2 else "melee_vs_ranged"


def engine_family(class2: str, class3: str) -> str:
    if class2 in RANGED_CLASSES and class3 in RANGED_CLASSES:
        return "rvr"
    if "mobile_ranged" in (class2, class3):
        return "kite"
    if "siege_ranged" in (class2, class3):
        return "siege"
    return "waves"


def policy_text(battle: dict) -> str:
    """The context ``policy`` string; equals the 2026 text for the 2026 settings."""
    parts = [f"{battle['armyCap']}-geometric-cost-v3"]
    weights = battle["resourceWeights"]
    if weights != DEFAULT_WEIGHTS:
        parts.append(f"weights food {weights['food']} wood {weights['wood']} gold {weights['gold']}")
    parts.append("zero buffers")
    for flag in ("disableAiOrders", "disableKiting", "preserveOwnerOrientation"):
        if battle[flag]:
            parts.append(flag)
    return "; ".join(parts)


class ContextBuilder:
    """``context(leftHash, rightHash)``: the physical battle for an oriented profile pair."""

    def __init__(self, mechanics_by_profile: dict, scenarios, battle: dict):
        self.mechanics = mechanics_by_profile
        self.scenarios = scenarios
        self.battle = battle
        self.policy = policy_text(battle)

    def __call__(self, left: str, right: str) -> dict:
        a, b = self.mechanics[left], self.mechanics[right]
        weights = self.battle["resourceWeights"]
        cost2, cost3 = weighted_cost(a["cost"], weights), weighted_cost(b["cost"], weights)
        n2, n3 = army_counts(cost2, cost3, self.battle["armyCap"])
        family = scenario_family(a["behavior_class"], b["behavior_class"])
        efam = engine_family(a["behavior_class"], b["behavior_class"])
        scenario_hash, _ = self.scenarios.resolve(family, efam)
        return {"profiles": [left, right], "counts": [n2, n3], "scenarioHash": scenario_hash,
                "family": family, "engineFamily": efam, "weightedCosts": [cost2, cost3],
                "policy": self.policy}
