"""Advisor unit -> economics profile mapping report (stdlib + aoe2x.economy).

Prints how many of the 555 advisor units map to exactly one economics profile by
(civilization, name), the Shu War Chariot two-mode check, and per-unit price
differences between the advisor catalog costs and the economics purchase price.
Usage: python tools/economy/advisor_eco/check_mapping.py
"""
import collections

from common import advisor_units, economics_map
from aoe2x.economy.matchup import RuntimeData, evaluate_matchup


def main():
    data = RuntimeData()
    units = advisor_units()
    mapping, problems = economics_map(data, units)
    print(f"advisor units {len(units)}, mapped {len(mapping)}, issues {len(problems)}")
    for p in problems:
        print("  ", p)
    # Shu War Chariot: both modes, same headline?
    same = True
    for count in (1, 13, 27):
        heads = [evaluate_matchup(data, ("Shu", uid, mode, count), ("Wu", 6, "default", 27))["teams"][0]["investment"]["labor"]["villagerMinutes"]
                 for uid, mode in ((1962, "focus_fire"), (1980, "barrage"))]
        same &= abs(heads[0] - heads[1]) < 1e-9
    print("Shu War Chariot focus_fire == barrage headline:", same)
    diffs = collections.Counter()
    examples = []
    for uid, key in mapping.items():
        price = data.unit(*key)["pricing"]["purchaseCost"]
        cost = units[uid]["costs"]
        delta = {r: price.get(r, 0) - cost.get(r, 0) for r in ("food", "wood", "gold")}
        if any(abs(v) > 1e-9 for v in delta.values()):
            diffs["differs"] += 1
            examples.append((units[uid]["key"], cost, {r: price[r] for r in ("food", "wood", "gold")}))
        else:
            diffs["equal"] += 1
    print("advisor cost vs economics purchase price:", dict(diffs))
    for e in sorted(examples):
        print("  ", e)


if __name__ == "__main__":
    main()
