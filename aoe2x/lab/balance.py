"""Default policy and presentation labels; always describe the persisted plan."""

DEFAULT_BALANCE = "geometric_shared_discount"
DEFAULT_COMPARISON_POLICY = "geometric_shared_discount_unit_count_v2"


def balance_caption(plan):
    balance = plan["balance"]
    labels = {
        "geometric_shared_discount": "Cost + population",
        "equal_resources": "Equal resources",
        "equal_count": "Equal unit count",
        "explicit": "Custom army counts",
    }
    if balance.get('comparisonPolicy') == DEFAULT_COMPARISON_POLICY:
        labels['geometric_shared_discount'] = 'Geometric cost balance'
    return f"{labels[balance['mode']]}  |  {balance['cap']}-unit cap"


def balance_description(plan):
    balance = plan["balance"]
    if balance["mode"] == DEFAULT_BALANCE:
        rule = (
            ("Army sizes use the square root of the comparison-cost ratio, treating every physical unit as one population. "
             if balance.get('comparisonPolicy') == DEFAULT_COMPARISON_POLICY else
             "Army sizes balance resource cost and population efficiency using their geometric mean. ") +
            "For units shared across civilizations, food and wood discounts count at half strength; "
            "gold discounts count in full. Civilization-exclusive units use their actual discounted costs."
        )
    elif balance["mode"] == "equal_resources":
        rule = "Equal resources using civilization-specific Imperial costs per individual unit."
    elif balance["mode"] == "equal_count":
        rule = "Equal numbers of units on each side."
    elif balance["mode"] == "explicit":
        rule = f"Custom army sizes: {plan['side2']['count']} versus {plan['side3']['count']} units."
    else:
        raise ValueError("Unknown balance policy; cannot describe the recording")
    return f"{rule} Maximum {balance['cap']} units per main army. Whole-unit rounding applies."
