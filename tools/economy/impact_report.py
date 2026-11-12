#!/usr/bin/env python3
"""Compare two compiled runtime databases unit by unit (before/after a rebuild).

    python tools/economy/impact_report.py BEFORE.db AFTER.db [--count 27] [--csv out.csv]

Per (civ, unit, mode) present in both databases, at ``--count`` units:
  armyVM      army purchase + 60-second production buildings, weighted villager-minutes (no research)
  mirrorVM    headline of the unit against itself (common research = its full package)
  researchVM  full combat research package, weighted villager-minutes
  researchSec full combat research package, summed research seconds
Rows only in one database are listed separately. Both databases are evaluated
with the current accounting code, so differences come from the data.
"""
import argparse
import csv
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aoe2x.economy.accounting import (  # noqa: E402
    add_costs, army_investment, compiled_labor, research_totals, select_investment_route, weighted_cost,
)


def load(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        civs = {c: json.loads(p) for c, p in db.execute("SELECT civ, payload FROM civilizations")}
        units = {(c, u, m): json.loads(p) for c, u, m, p in db.execute("SELECT civ, unit_id, mode, payload FROM units")}
    return civs, units


def figures(unit, economy, count):
    prices = economy["laborPrices"]
    start = unit["lookup"][count]
    totals = research_totals(unit["research"]["military"]["technologies"])
    def headline(research):
        production, _ = select_investment_route(unit["productionRoutes"], start["orders"],
                                                unit["pricing"]["unitsPerPurchase"],
                                                add_costs(start["cost"], research["net"]), prices)
        score = army_investment(start["cost"], production, research, prices)
        return None if score["labor"] is None else score["labor"]["villagerMinutes"], production
    empty = research_totals([])
    army, production = headline(empty)
    mirror, _ = headline(totals)
    research = compiled_labor(weighted_cost(totals["net"]), prices) if totals["costIsFixed"] else None
    return {"armyVM": army, "mirrorVM": mirror,
            "researchVM": None if research is None else research["villagerMinutes"],
            "researchSec": totals["workloadSeconds"], "researchCount": totals["technologyCount"],
            "building": production.get("name"), "buildings": production.get("buildingCount"),
            "unitCost": unit["pricing"]["physicalUnitCost"]}


def compare(before, after, count):
    (cb, ub), (ca, ua) = load(before), load(after)
    rows = []
    for key in sorted(ub.keys() & ua.keys()):
        b = figures(ub[key], cb[key[0]], count)
        a = figures(ua[key], ca[key[0]], count)
        row = {"civ": key[0], "unitId": key[1], "mode": key[2], "name": ua[key]["name"]}
        for k in ("armyVM", "mirrorVM", "researchVM", "researchSec", "researchCount", "building", "buildings"):
            row[k + "_before"], row[k + "_after"] = b[k], a[k]
        row["unitCost_before"] = json.dumps({r: v for r, v in b["unitCost"].items() if v})
        row["unitCost_after"] = json.dumps({r: v for r, v in a["unitCost"].items() if v})
        for k in ("armyVM", "mirrorVM", "researchVM", "researchSec"):
            x, y = b[k], a[k]
            row[k + "_delta"] = None if x is None or y is None else y - x
            row[k + "_pct"] = None if not x or y is None else 100 * (y - x) / x
        rows.append(row)
    return rows, sorted(ub.keys() - ua.keys()), sorted(ua.keys() - ub.keys())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--count", type=int, default=27)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    rows, removed, added = compare(args.before, args.after, args.count)
    changed = [r for r in rows if any(abs(r[k + "_delta"] or 0) > 1e-9 for k in ("armyVM", "mirrorVM", "researchVM", "researchSec"))
               or r["building_before"] != r["building_after"]]
    if args.csv:
        with args.csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(changed)
    print(f"{len(rows)} common rows; {len(changed)} changed; removed {removed}; added {added}")
    for r in sorted(changed, key=lambda r: -abs(r["mirrorVM_pct"] or 0))[:10]:
        print(f"{r['civ']:12} {r['name']:28} mirror {r['mirrorVM_before']:.1f} -> {r['mirrorVM_after']:.1f} "
              f"({r['mirrorVM_pct']:+.1f}%)")


if __name__ == "__main__":
    main()
