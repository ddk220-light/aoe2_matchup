"""Default policy and presentation labels; always describe the persisted plan."""

DEFAULT_BALANCE = "geometric_shared_discount"
DEFAULT_COMPARISON_POLICY = "geometric_full_discount_weighted_resources_v3"
DEFAULT_RESOURCE_WEIGHTS = {"food": 1.0, "wood": 0.9, "gold": 1.1}
UNIT_POPULATION_POLICIES = {
    "geometric_shared_discount_unit_count_v2", DEFAULT_COMPARISON_POLICY,
}


def balance_caption(plan):
    balance = plan["balance"]
    labels = {
        "geometric_shared_discount": "Cost + population",
        "equal_resources": "Equal resources",
        "equal_count": "Equal unit count",
        "explicit": "Custom army counts",
    }
    if balance.get('comparisonPolicy') in UNIT_POPULATION_POLICIES:
        labels['geometric_shared_discount'] = 'Geometric cost balance'
    return f"{labels[balance['mode']]}  |  {balance['cap']}-unit cap"


def balance_description(plan):
    balance = plan["balance"]
    if balance["mode"] == DEFAULT_BALANCE:
        policy = balance.get('comparisonPolicy')
        rule = (
            ("Army sizes use the square root of the comparison-cost ratio, treating every physical unit as one population. "
             if policy in UNIT_POPULATION_POLICIES else
             "Army sizes balance resource cost and population efficiency using their geometric mean. ") +
            ("All civilization discounts count in full."
             if policy == DEFAULT_COMPARISON_POLICY else
             "For units shared across civilizations, food and wood discounts count at half strength; "
            "gold discounts count in full. Civilization-exclusive units use their actual discounted costs."
            )
        )
        if policy == DEFAULT_COMPARISON_POLICY:
            weights = {**DEFAULT_RESOURCE_WEIGHTS, **balance.get('weights', {})}
            rule += (f" Resource weights: food {weights['food']:g}, wood {weights['wood']:g}, "
                     f"gold {weights['gold']:g}.")
    elif balance["mode"] == "equal_resources":
        rule = "Equal resources using civilization-specific Imperial costs per individual unit."
    elif balance["mode"] == "equal_count":
        rule = "Equal numbers of units on each side."
    elif balance["mode"] == "explicit":
        rule = f"Custom army sizes: {plan['side2']['count']} versus {plan['side3']['count']} units."
    else:
        raise ValueError("Unknown balance policy; cannot describe the recording")
    return f"{rule} Maximum {balance['cap']} units per main army. Whole-unit rounding applies."
