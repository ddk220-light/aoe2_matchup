"""Recorder purchase-cost convention shared by runtime profiles and comparisons."""

RESOURCES = ("food", "wood", "gold")


def effective_cost(row):
    """Fully discounted cost per physical unit (recorder policy at 2cced342).

    Saxon maximum conditional discount: four controlled TCs/Castles, 20%.
    Blackwood Archer purchase trains two units; divide after resource rounding.
    """
    purchase = {r: row[f"final_cost_{r}"] for r in RESOURCES}
    multiplier = 0.8 if row["civ_name"] == "Saxons" and row["unit_class"] in (0, 6, 44) else 1
    batch = 2 if row["unit_master"] in (2579, 2581) else 1
    costs = {r: round(value * multiplier) / batch for r, value in purchase.items()}
    return costs, dict(referencePurchaseCost=purchase, unitsPerPurchase=batch,
                      conditionalMultiplier=multiplier,
                      conditionalContext="four controlled Town Centers/Castles; maximum 20% discount"
                      if multiplier != 1 else None)
