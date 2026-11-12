"""Revision 2 recommendation impact on all 1,540 civilization pairs (3,080 plans).

Eco-win cells (loser side "Eco win" in classify.py) become caveats, not losses; the
winner keeps the win ("lite"); a gold strong contender replaces a main that still has
a real loss ("lite + contender main" = advisor_model variant ``eco_lite_main``, JS:
``model_rev2.mjs``). Kite clear wins and power wins stay ordinary wins.

Runs the headline thresholds (HP < 50%, eco >= 25%), the sensitivity grid
(HP 33/40/50% x eco 25/33%) and the headline without the kite rule; checks the Python
variant against model_rev2.mjs under Node for all pairs (--no-js to skip).
Writes $ADVISOR_ECO_OUT/impact_rev2.json and impact_rev2_examples.json.
Usage: python tools/economy/advisor_eco/impact_rev2.py [--no-js]
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import subprocess
from pathlib import Path

from advisor_model import build, summary
from classify import classify, load_bundle, motion
from common import OUT, advisor_units, civ_documents, connect, read_cells

HERE = Path(__file__).resolve().parent


def eco_win_set(cells, mo, hp, eco, kite=True):
    out = set()
    for c in cells:
        if c["outcome"] not in ("a_win", "b_win") or c["vm_a"] is None or c["vm_b"] is None:
            continue
        m = mo if kite else {**mo, c["a"]: {**mo[c["a"]], "ranged": False}, c["b"]: {**mo[c["b"]], "ranged": False}}
        wk, lk, w = classify(c, m, hp, eco)
        if lk == "eco":
            loser = c["b"] if w == "a" else c["a"]
            out.add((loser, c[w]))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-js", action="store_true")
    args = parser.parse_args()
    db = connect()
    units = advisor_units(db)
    documents = civ_documents(db, units)
    variants = load_bundle()
    mo = {uid: motion(variants[u["key"]]) for uid, u in units.items()}
    cells_list = list(read_cells())
    cells = {(c["a"], c["b"]): c for c in cells_list}
    pairs = list(itertools.combinations(sorted(documents), 2))
    name = lambda uid: units[uid]["name"] if uid is not None else None  # noqa: E731

    def describe(loser, winner):
        c = cells.get((loser, winner)) or cells.get((winner, loser))
        la = c["a"] == loser
        nl, nw = (c["count_a"], c["count_b"]) if la else (c["count_b"], c["count_a"])
        vl, vw = (c["vm_a"], c["vm_b"]) if la else (c["vm_b"], c["vm_a"])
        return (f"{nw} {name(winner)} beat {nl} {name(loser)} keeping {100 * c['hp_avg']:.0f}% HP "
                f"({c['seeds']} seed(s), {100 * c['hp_min']:.0f}-{100 * c['hp_max']:.0f}%); {vl:.0f} vs {vw:.0f} VM "
                f"(loser {100 * (1 - vl / vw):.0f}% cheaper)")

    def run(semi, collect=False):
        stats = collections.Counter()
        examples = collections.defaultdict(list)
        plans_out = {}
        for left, right in pairs:
            rows = documents[left][right]
            before = build(rows, units)
            lite = build(rows, units, semi, "eco_lite")
            after = build(rows, units, semi, "eco_lite_main")
            for side, civ, enemy in (("left", left, right), ("right", right, left)):
                sb, sl, sa = summary(before[side]), summary(lite[side]), summary(after[side])
                plans_out[(left, right, side)] = sa
                p = after[side]
                stats["plans"] += 1
                for tag, s in (("lite", sl), ("lite+contender main", sa)):
                    adds_b = sorted(a[0] for a in sb["additions"]); adds_s = sorted(a[0] for a in s["additions"])
                    stats[f"{tag}: main changed"] += sb["main"] != s["main"]
                    stats[f"{tag}: sidekick changed"] += sb["sidekick"] != s["sidekick"]
                    stats[f"{tag}: additions changed"] += adds_b != adds_s
                    stats[f"{tag}: fewer additions"] += len(s["additions"]) < len(sb["additions"])
                    stats[f"{tag}: more additions"] += len(s["additions"]) > len(sb["additions"])
                    stats[f"{tag}: any of main/sidekick/additions changed"] += (
                        sb["main"] != s["main"] or sb["sidekick"] != s["sidekick"] or adds_b != adds_s)
                    stats[f"{tag}: additions total before"] += len(sb["additions"])
                    stats[f"{tag}: additions total after"] += len(s["additions"])
                    stats[f"{tag}: unanswered total after"] += len(s["unanswered"])
                stats["unanswered total before"] += len(sb["unanswered"])
                contenders = [e for e in p["ranked"] if e["contender"]]
                stats["plans with a strong contender"] += bool(contenders)
                stats["plans with a gold strong contender with wins"] += any(
                    float(e["unit"]["costs"]["gold"]) > 0 and e["wins"] for e in contenders)
                stats["main is a strong contender"] += bool(p["main"] and p["main"]["contender"])
                stats["main shows eco-win caveat(s)"] += bool(p["main"] and p["main"]["semi_losses"])
                stats["main before had no real loss"] += bool(before[side]["main"] and not before[side]["main"]["losses"])
                stats["main after has no real loss"] += bool(p["main"] and not p["main"]["losses"])
                if collect:
                    rec = {"civ": civ, "enemy": enemy,
                           "before": {"main": name(sb["main"]), "sidekick": name(sb["sidekick"]),
                                      "additions": [[name(a), [name(x) for x in cov]] for a, cov in sb["additions"]],
                                      "main_losses": [name(x) for x in sb["main_losses"]]},
                           "after": {"main": name(sa["main"]), "sidekick": name(sa["sidekick"]),
                                     "additions": [[name(a), [name(x) for x in cov]] for a, cov in sa["additions"]],
                                     "main_losses": [name(x) for x in sa["main_losses"]],
                                     "main_caveats": [describe(r[0], r[1]) for r in p["main"]["semi_losses"]] if p["main"] else []},
                           "contenders": [{"unit": e["unit"]["name"], "wins": len(e["wins"]),
                                           "caveats": [describe(r[0], r[1]) for r in e["semi_losses"]]} for e in contenders]}
                    if sb["main"] != sa["main"]:
                        examples["main_changed"].append(rec)
                    elif len(sa["additions"]) < len(sb["additions"]):
                        examples["fewer_additions_same_main"].append(rec)
                    elif sb["sidekick"] != sa["sidekick"]:
                        examples["sidekick_changed"].append(rec)
                    if sb["main"] != sa["main"]:
                        stats_key = f"main change {name(sb['main'])} -> {name(sa['main'])}"
                        examples["_main_change_counts"].append(stats_key)
        return dict(stats), examples, plans_out

    out = {"grid": {}}
    headline = eco_win_set(cells_list, mo, 0.50, 0.25)
    stats, examples, plans_py = run(headline, collect=True)
    out["headline"] = {"ecoWinCells": len(headline), "stats": stats}
    out["mainChangeCounts"] = collections.Counter(examples.pop("_main_change_counts")).most_common(25)
    for hp in (0.33, 0.40, 0.50):
        for eco in (0.25, 0.33):
            key = f"hp<{hp:.2f} eco>={eco:.2f}"
            if (hp, eco) == (0.50, 0.25):
                out["grid"][key] = {"ecoWinCells": len(headline), "stats": stats}
                continue
            semi = eco_win_set(cells_list, mo, hp, eco)
            out["grid"][key] = {"ecoWinCells": len(semi), "stats": run(semi)[0]}
    nokite = eco_win_set(cells_list, mo, 0.50, 0.25, kite=False)
    out["headlineWithoutKiteRule"] = {"ecoWinCells": len(nokite), "stats": run(nokite)[0]}

    if not args.no_js:
        catalog = OUT / "advisor_units.json"
        catalog.write_text(json.dumps(list(units.values())))
        eco_file = OUT / "eco_wins_headline.json"
        eco_file.write_text(json.dumps({"ecoWins": sorted(headline)}))
        payload = "".join(json.dumps({"left": l, "right": r, "rows": documents[l][r]}) + "\n" for l, r in pairs)
        result = subprocess.run(["node", str(HERE / "dump_js_plans_rev2.mjs"), str(catalog), str(eco_file)],
                                input=payload, capture_output=True, text=True, check=True)
        mismatches = 0
        for line, (left, right) in zip(result.stdout.splitlines(), pairs):
            js = json.loads(line)
            for side in ("left", "right"):
                if plans_py[(left, right, side)] != js["plans"][side]:
                    mismatches += 1
        out["jsParity"] = {"plans": 2 * len(pairs), "mismatches": mismatches}
        print("JS parity (model_rev2.mjs vs advisor_model eco_lite_main):", out["jsParity"])
    (OUT / "impact_rev2.json").write_text(json.dumps(out, indent=1) + "\n")
    (OUT / "impact_rev2_examples.json").write_text(json.dumps(examples, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
