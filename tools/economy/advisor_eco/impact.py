"""Recommendation impact of the proposed rule on all 1,540 civilization pairs.

Runs advisor_model.build for variants "current" (= the live model, see
check_js_parity.py), "eco" (semi-losses become caveats, contender flag) and
"eco_main" (eco + a gold strong contender is preferred as main) and reports how
often main / sidekick / additions / unanswered change, plus example candidates.
Writes $ADVISOR_ECO_OUT/impact.json (+ impact_examples.txt).
Usage: python tools/economy/advisor_eco/impact.py
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json

from advisor_model import build, summary
from common import ECO_SAVING, HP_LIMIT, OUT, advisor_units, civ_documents, connect, read_cells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost", choices=["headline", "purchase"], default="headline",
                        help="headline = owner's rule; purchase = army purchase bill only (sensitivity)")
    args = parser.parse_args()
    suffix = "" if args.cost == "headline" else "_purchase"
    db = connect()
    units = advisor_units(db)
    documents = civ_documents(db, units)
    cells = {(c["a"], c["b"]): c for c in read_cells()}
    semi = set()
    for c in cells.values():
        if args.cost == "purchase":
            if c["saving"] is None or c["hp_avg"] >= HP_LIMIT:
                continue
            loser = "b" if c["outcome"] == "a_win" else "a"
            winner = "a" if loser == "b" else "b"
            if 1 - c["army_vm_" + loser] / c["army_vm_" + winner] >= ECO_SAVING:
                semi.add((c[loser], c[winner]))
        elif c["label"]:
            semi.add((c["b"], c["a"]) if c["outcome"] == "a_win" else (c["a"], c["b"]))

    def cell(x, y):
        c = cells.get((x, y)) or cells.get((y, x))
        return c

    def describe(loser, winner):
        c = cell(loser, winner)
        if not c:
            return f"{units[loser]['name']} vs {units[winner]['name']}: no simulated cell"
        la = c["a"] == loser
        nl, nw = (c["count_a"], c["count_b"]) if la else (c["count_b"], c["count_a"])
        vl, vw = (c["vm_a"], c["vm_b"]) if la else (c["vm_b"], c["vm_a"])
        al, aw = (c["army_vm_a"], c["army_vm_b"]) if la else (c["army_vm_b"], c["army_vm_a"])
        return (f"{nw} {units[winner]['name']} beat {nl} {units[loser]['name']} keeping {100*c['hp_avg']:.0f}% HP "
                f"(seeds {c['seeds']}, range {100*c['hp_min']:.0f}–{100*c['hp_max']:.0f}%); 60-s investment "
                f"{vl:.0f} vs {vw:.0f} VM (loser {100*(1-vl/vw):.0f}% cheaper; army only {al:.0f} vs {aw:.0f})")

    stats = collections.Counter()
    examples = collections.defaultdict(list)
    for left, right in itertools.combinations(sorted(documents), 2):
        rows = documents[left][right]
        plans = {v: build(rows, units, semi, v) for v in ("current", "eco_lite", "eco_lite_main", "eco", "eco_main")}
        for side, civ, enemy in (("left", left, right), ("right", right, left)):
            before, lite, lite_main, eco, eco_main = (plans[v][side] for v in ("current", "eco_lite", "eco_lite_main", "eco", "eco_main"))
            sb, sl, slm, se, sm = summary(before), summary(lite), summary(lite_main), summary(eco), summary(eco_main)
            stats["plans"] += 1
            semis = [e for e in eco["ranked"] if e["semi_losses"]]
            contenders = [e for e in eco["ranked"] if e["contender"]]
            gold_contenders = [e for e in contenders if float(e["unit"]["costs"]["gold"]) > 0 and e["wins"]]
            stats["plans_with_any_semi_row"] += bool(semis)
            main_semi = eco["main"]["semi_losses"] if eco["main"] else []
            lite_semi = lite_main["main"]["semi_losses"] if lite_main["main"] else []
            stats["plans_lite_main_has_semi_caveat"] += bool(lite_semi)
            stats["plans_lite_main_is_contender"] += bool(lite_main["main"] and lite_main["main"]["contender"])
            stats["semi_caveats_on_lite_main"] += len(lite_semi)
            stats["plans_main_has_semi_caveat"] += bool(main_semi)
            stats["plans_with_contender"] += bool(contenders)
            stats["plans_with_gold_contender"] += bool(gold_contenders)
            stats["plans_eco_main_is_contender"] += bool(eco["main"] and eco["main"]["contender"])
            stats["plans_before_main_flawless"] += bool(before["main"] and not before["main"]["losses"])
            stats["plans_eco_main_flawless_or_contender"] += bool(eco["main"] and not eco["main"]["losses"])
            for name, s in (("eco_lite", sl), ("eco_lite_main", slm), ("eco", se), ("eco_main", sm)):
                stats[f"{name}: main changed"] += sb["main"] != s["main"]
                stats[f"{name}: sidekick changed"] += sb["sidekick"] != s["sidekick"]
                stats[f"{name}: additions changed"] += sorted(a[0] for a in sb["additions"]) != sorted(a[0] for a in s["additions"])
                stats[f"{name}: fewer additions"] += len(s["additions"]) < len(sb["additions"])
                stats[f"{name}: more additions"] += len(s["additions"]) > len(sb["additions"])
                stats[f"{name}: unanswered changed"] += sb["unanswered"] != s["unanswered"]
                stats[f"{name}: any of main/sidekick/additions changed"] += (
                    sb["main"] != s["main"] or sb["sidekick"] != s["sidekick"]
                    or sorted(a[0] for a in sb["additions"]) != sorted(a[0] for a in s["additions"]))
                stats[f"{name}: additions before"] += len(sb["additions"])
                stats[f"{name}: additions after"] += len(s["additions"])
            record = {"civ": civ, "enemy": enemy,
                      "before": {"main": units[sb["main"]]["name"] if sb["main"] is not None else None,
                                 "sidekick": units[sb["sidekick"]]["name"] if sb["sidekick"] is not None else None,
                                 "additions": [[units[a]["name"], [units[x]["name"] for x in cov]] for a, cov in sb["additions"]],
                                 "main_losses": [units[x]["name"] for x in sb["main_losses"]]},
                      "eco": {"main": units[se["main"]]["name"] if se["main"] is not None else None,
                              "sidekick": units[se["sidekick"]]["name"] if se["sidekick"] is not None else None,
                              "additions": [[units[a]["name"], [units[x]["name"] for x in cov]] for a, cov in se["additions"]],
                              "main_losses": [units[x]["name"] for x in se["main_losses"]],
                              "main_caveats": [describe(r[0], r[1]) for r in main_semi]},
                      "lite_main_caveats": [describe(r[0], r[1]) for r in lite_semi],
                      "eco_main": {"main": units[sm["main"]]["name"] if sm["main"] is not None else None},
                      "eco_lite": {"main": units[sl["main"]]["name"] if sl["main"] is not None else None,
                                   "sidekick": units[sl["sidekick"]]["name"] if sl["sidekick"] is not None else None,
                                   "additions": [[units[a]["name"], [units[x]["name"] for x in cov]] for a, cov in sl["additions"]]},
                      "contenders": [{"unit": e["unit"]["name"], "wins": len(e["wins"]), "close": len(e["close"]),
                                      "caveats": [describe(r[0], r[1]) for r in e["semi_losses"]]} for e in contenders]}
            if sb["main"] != slm["main"]:
                record["eco_lite_main"] = {"main": units[slm["main"]]["name"],
                                           "sidekick": units[slm["sidekick"]]["name"] if slm["sidekick"] is not None else None,
                                           "additions": [[units[a]["name"], [units[x]["name"] for x in cov]] for a, cov in slm["additions"]]}
                examples["main_changed_eco_lite_main"].append(record)
            if sb["main"] != sl["main"]:
                examples["main_changed_eco_lite"].append(record)
            if len(sl["additions"]) < len(sb["additions"]):
                examples["fewer_additions_lite"].append(record)
            if sb["main"] != se["main"]:
                examples["main_changed_eco"].append(record)
            if sb["main"] != sm["main"]:
                examples["main_changed_eco_main"].append(record)
            if len(se["additions"]) < len(sb["additions"]) and sb["main"] == se["main"]:
                examples["fewer_additions_same_main"].append(record)
            if gold_contenders and (eco["main"] is None or not eco["main"]["contender"]):
                examples["gold_contender_not_main"].append(record)
            if main_semi:
                examples["main_with_caveat"].append(record)
    stats = dict(stats)
    (OUT / f"impact{suffix}.json").write_text(json.dumps({"stats": stats, "semiCells": len(semi),
                                                 "exampleCounts": {k: len(v) for k, v in examples.items()}}, indent=1) + "\n")
    (OUT / f"impact_examples{suffix}.json").write_text(json.dumps(examples, indent=1) + "\n")
    print(json.dumps(stats, indent=1))
    print({k: len(v) for k, v in examples.items()})


if __name__ == "__main__":
    main()
