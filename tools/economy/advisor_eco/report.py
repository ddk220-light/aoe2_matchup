"""Distributions for the "narrow loss, cheaper to rebuild" label (reads cells.csv.gz).

Prints Markdown tables (pasted into docs/army-economics/ADVISOR_ECO_DESIGN.md)
and writes $ADVISOR_ECO_OUT/report_summary.json.
Usage: python tools/economy/advisor_eco/report.py
"""
from __future__ import annotations

import collections
import json
import math

from common import ECO_NEAR, ECO_SAVING, HP_LIMIT, HP_NEAR, OUT, advisor_units, connect, read_cells

FULL_RATIO = 0.67   # proposed note: one full package <= 67% of the other's ...
FULL_ABS = 20.0     # ... and at least 20 weighted villager-minutes cheaper


def pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "-"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(headers))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    cells = list(read_cells())
    db = connect()
    units = advisor_units(db)
    all_cells = db.execute("SELECT a, b, outcome, evidence_type, count_a, count_b FROM cells").fetchall()
    summary, md = {}, []

    decided = [c for c in cells if c["outcome"] in ("a_win", "b_win")]
    with_seeds = [c for c in decided if c["seeds"]]
    eco_ok = [c for c in with_seeds if c["saving"] is not None]
    semi = [c for c in eco_ok if c["label"]]
    summary.update(observed=len(cells), decided=len(decided), close=len(cells) - len(decided),
                   decided_with_seeds=len(with_seeds), decided_no_seed=len(decided) - len(with_seeds),
                   eco_available=len(eco_ok), semi=len(semi),
                   semi_contexts=len({c["evidence_id"] for c in semi}),
                   eco_unavailable_examples=collections.Counter(
                       f'{c["name_a"] if c["vm_a"] is None else c["name_b"]}' for c in with_seeds if c["saving"] is None).most_common(8))
    md.append("## Coverage\n")
    et = collections.Counter(c[3] for c in all_cells)
    md.append(table(["Cells", "Count"], [
        ["all advisor cells", len(all_cells)], ["identity (mirror profiles, no fight)", et["identity"]],
        ["inferred (never simulated)", et["inferred"]], ["observed (simulated)", len(cells)],
        ["observed, close_uncertain (stay close)", len(cells) - len(decided)],
        ["observed, decided, no seed HP recoverable", len(decided) - len(with_seeds)],
        ["observed, decided, economics unavailable", len(with_seeds) - len(eco_ok)],
        ["**evaluated for the label**", len(eco_ok)]]))

    # Seeds
    seeds = collections.Counter(c["seeds"] for c in cells)
    disagree = [c for c in decided if c["seeds_won_a"] and c["seeds_won_b"]]
    close_split = [c for c in cells if c["outcome"] == "close_uncertain"]
    loser_majority = [c for c in decided if (c["seeds_won_b"] > c["seeds_won_a"]) == (c["outcome"] == "a_win") and c["seeds_won_a"] != c["seeds_won_b"]]
    summary.update(seed_count_distribution=dict(sorted(seeds.items())), decided_with_split_seeds=len(disagree),
                   decided_outcome_against_seed_majority=len(loser_majority),
                   close_uncertain_split=sum(1 for c in close_split if c["seeds_won_a"] and c["seeds_won_b"]),
                   close_uncertain_unanimous=sum(1 for c in close_split if not (c["seeds_won_a"] and c["seeds_won_b"])))
    md.append("\n## Seeds\n")
    md.append(table(["Seeds per cell", "Cells"], [[k, v] for k, v in sorted(seeds.items())]))
    md.append(f"\nDecided cells whose seeds split: {len(disagree)} ({pct(len(disagree), len(decided))}); "
              f"decided against the seed majority: {len(loser_majority)}; close_uncertain cells: {len(close_split)} "
              f"({summary['close_uncertain_split']} split, {summary['close_uncertain_unanimous']} unanimous).")
    semi_split = sum(1 for c in semi if c["seeds_won_a"] and c["seeds_won_b"])
    summary["semi_with_split_seeds"] = semi_split

    # HP and eco distributions on the evaluated cells
    hp_bins = [0, .1, .2, .33, .4, .5, .75, 1.0001]
    eco_bins = [-math.inf, 0, .1, .25, .33, .5, 1]
    def binned(values, edges):
        counts = [0] * (len(edges) - 1)
        for v in values:
            for i in range(len(edges) - 1):
                if edges[i] <= v < edges[i + 1]:
                    counts[i] += 1
                    break
        return counts
    hp = binned([c["hp_avg"] for c in eco_ok], hp_bins)
    eco = binned([c["saving"] for c in eco_ok], eco_bins)
    md.append("\n## Winner HP (seed mean, lost seeds count as 0) and loser saving\n")
    md.append(table(["Winner HP left", "Cells"], [[f"{hp_bins[i]:.0%}–{min(hp_bins[i+1],1):.0%}", n] for i, n in enumerate(hp)]))
    md.append("")
    md.append(table(["Loser army cheaper by", "Cells"], [[("< 0% (loser dearer)" if i == 0 else f"{eco_bins[i]:.0%}–{eco_bins[i+1]:.0%}"), n] for i, n in enumerate(eco)]))
    hp_only = sum(1 for c in eco_ok if c["hp_avg"] < HP_LIMIT)
    eco_only = sum(1 for c in eco_ok if c["saving"] >= ECO_SAVING)
    near_hp = [c for c in eco_ok if HP_LIMIT <= c["hp_avg"] < HP_NEAR and c["saving"] >= ECO_SAVING]
    near_eco = [c for c in eco_ok if c["hp_avg"] < HP_LIMIT and ECO_NEAR <= c["saving"] < ECO_SAVING]
    alt_won = sum(1 for c in eco_ok if c["hp_avg_won"] is not None and c["hp_avg_won"] < HP_LIMIT and c["saving"] >= ECO_SAVING)
    summary.update(hp_condition=hp_only, eco_condition=eco_only, near_hp=len(near_hp), near_eco=len(near_eco),
                   semi_if_hp_mean_over_won_seeds=alt_won)

    md.append("\n## Label counts and sensitivity\n")
    md.append(table(["Rule", "Cells", "Share of evaluated", "Contexts"], [
        ["winner HP < 33% (any cost)", hp_only, pct(hp_only, len(eco_ok)), ""],
        ["loser army ≥ 33% cheaper (any HP)", eco_only, pct(eco_only, len(eco_ok)), ""],
        ["**both: narrow loss, cheaper to rebuild**", len(semi), pct(len(semi), len(eco_ok)), summary["semi_contexts"]],
        ["near miss: HP 33–40%, eco ≥ 33%", len(near_hp), pct(len(near_hp), len(eco_ok)), len({c['evidence_id'] for c in near_hp})],
        ["near miss: HP < 33%, eco 25–33%", len(near_eco), pct(len(near_eco), len(eco_ok)), len({c['evidence_id'] for c in near_eco})],
        ["variant: HP mean over won seeds only", alt_won, pct(alt_won, len(eco_ok)), ""],
        ["label cells whose seeds split", semi_split, pct(semi_split, len(semi)) + " of label", ""]]))

    # Unit class pairs (loser -> winner)
    def side(c, which):
        loser_is_a = c["outcome"] == "b_win"
        idx = "a" if (which == "loser") == loser_is_a else "b"
        return idx
    def cls(c, which):
        return "gold" if c["gold_" + side(c, which)] else "trash"
    pair_all = collections.Counter((cls(c, "loser"), cls(c, "winner")) for c in eco_ok)
    pair_semi = collections.Counter((cls(c, "loser"), cls(c, "winner")) for c in semi)
    md.append("\n## By unit class (loser → winner; trash = no gold cost)\n")
    md.append(table(["Loser → winner", "Decided cells", "Label cells", "Label rate", "Share of labels"],
                    [[f"{l} → {w}", pair_all[(l, w)], pair_semi[(l, w)], pct(pair_semi[(l, w)], pair_all[(l, w)]),
                      pct(pair_semi[(l, w)], len(semi))] for l, w in [("trash", "gold"), ("gold", "gold"), ("trash", "trash"), ("gold", "trash")]]))
    groups = collections.Counter((c["group_" + side(c, "loser")], c["group_" + side(c, "winner")]) for c in semi)
    groups_all = collections.Counter((c["group_" + side(c, "loser")], c["group_" + side(c, "winner")]) for c in eco_ok)
    md.append("\n" + table(["Loser group → winner group", "Label cells", "Rate"],
                           [[f"{l} → {w}", n, pct(n, groups_all[(l, w)])] for (l, w), n in groups.most_common(10)]))
    loser_units = collections.Counter(c["name_" + side(c, "loser")] for c in semi)
    winner_units = collections.Counter(c["name_" + side(c, "winner")] for c in semi)
    md.append("\nMost frequent losers: " + ", ".join(f"{n} {k}" for k, n in loser_units.most_common(10)))
    md.append("\nMost frequent winners: " + ", ".join(f"{n} {k}" for k, n in winner_units.most_common(10)))

    # Civilizations
    civ_l = collections.Counter(c["civ_" + side(c, "loser")] for c in semi)
    civ_w = collections.Counter(c["civ_" + side(c, "winner")] for c in semi)
    civ_decided_l = collections.Counter(c["civ_" + side(c, "loser")] for c in eco_ok)
    rates = sorted(((civ_l[civ] / civ_decided_l[civ], civ) for civ in civ_decided_l), reverse=True)
    md.append("\n## By civilization (as the cheaper loser)\n")
    md.append(table(["Civilization", "Label cells as loser", "Rate of its losses", "Label cells as winner"],
                    [[civ, civ_l[civ], f"{100*r:.1f}%", civ_w[civ]] for r, civ in rates[:8]] + [["…", "", "", ""]] +
                    [[civ, civ_l[civ], f"{100*r:.1f}%", civ_w[civ]] for r, civ in rates[-5:]]))
    summary["civ_rate_as_loser"] = {civ: round(r, 4) for r, civ in rates}

    # Army sizing bias
    cheaper_unit = sum(1 for c in semi if c["wcost_" + side(c, "loser")] < c["wcost_" + side(c, "winner")])
    equal_unit = sum(1 for c in semi if c["wcost_" + side(c, "loser")] == c["wcost_" + side(c, "winner")])
    loser_27 = sum(1 for c in semi if c["count_" + side(c, "loser")] == 27)
    base_cheaper = sum(1 for c in eco_ok if c["wcost_" + side(c, "loser")] < c["wcost_" + side(c, "winner")])
    ratio_semi = sorted(c["wcost_" + side(c, "winner")] / c["wcost_" + side(c, "loser")] for c in semi)
    sqrt_check = []
    for c in eco_ok:
        cheap, dear = sorted([c["wcost_a"], c["wcost_b"]])
        n_cheap, n_dear = (c["count_a"], c["count_b"]) if c["wcost_a"] <= c["wcost_b"] else (c["count_b"], c["count_a"])
        sqrt_check.append((n_dear * dear) / (n_cheap * cheap))
    summary.update(semi_loser_cheaper_unit=cheaper_unit, semi_equal_unit_cost=equal_unit, semi_loser_27=loser_27,
                   base_loser_cheaper_unit=base_cheaper,
                   semi_unit_cost_ratio_quartiles=[ratio_semi[int(q * (len(ratio_semi) - 1))] for q in (0, .25, .5, .75, 1)] if ratio_semi else [],
                   army_resource_ratio_dear_over_cheap_quartiles=sorted(sqrt_check)[::max(1, len(sqrt_check) // 4)][:5])
    md.append("\n## Army-sizing bias\n")
    md.append(table(["Measure", "Value"], [
        ["label cells where the loser is the cheaper unit (advisor weighted resource cost per unit)", f"{cheaper_unit} ({pct(cheaper_unit, len(semi))})"],
        ["… where the loser fielded 27 units (the cheaper side's fixed count)", f"{loser_27} ({pct(loser_27, len(semi))})"],
        ["baseline: all evaluated decided cells where the loser is the cheaper unit", f"{base_cheaper} ({pct(base_cheaper, len(eco_ok))})"],
        ["winner/loser unit-cost ratio in label cells (min / median / max)", " / ".join(f"{x:.2f}" for x in (ratio_semi[0], ratio_semi[len(ratio_semi)//2], ratio_semi[-1])) if ratio_semi else "-"]]))

    # Cheaper-to-fully-upgrade note (all cells: depends on units only)
    full = {}
    for c in cells:
        full[c["a"]] = c["full_vm_a"]
        full[c["b"]] = c["full_vm_b"]
    missing = [u for u in units if u not in full]
    note = collections.Counter()
    ratios = []
    for a, b, outcome, et_, ca, cb in all_cells:
        fa, fb = full.get(a), full.get(b)
        if fa is None or fb is None:
            note["unknown"] += 1
            continue
        lo, hi = sorted([fa, fb])
        ratios.append(lo / hi if hi else 1)
        if hi and lo <= FULL_RATIO * hi and hi - lo >= FULL_ABS:
            note["note"] += 1
            note["note_" + et_] += 1
        note["all"] += 1
    sweep = []
    for r, ab in [(0.5, 20), (0.67, 0), (0.67, 20), (0.67, 40), (0.8, 20)]:
        n = 0
        for a, b, *_ in all_cells:
            fa, fb = full.get(a), full.get(b)
            if fa is None or fb is None:
                continue
            lo, hi = sorted([fa, fb])
            n += bool(hi and lo <= r * hi and hi - lo >= ab)
        sweep.append([f"≤ {r:.0%} of the other and ≥ {ab} VM cheaper", n, pct(n, note["all"])])
    full_values = sorted(v for v in full.values() if v is not None)
    summary.update(full_note=dict(note), full_missing_units=len(missing),
                   full_vm_quartiles=[full_values[int(q * (len(full_values) - 1))] for q in (0, .25, .5, .75, 1)])
    md.append("\n## Note: cheaper to fully upgrade (all cells, unit-level)\n")
    md.append(table(["Threshold", "Cells with the note", "Share"], sweep))
    md.append(f"\nFull military research per unit, weighted villager-minutes (min / quartiles / max): "
              + " / ".join(f"{x:.0f}" for x in summary["full_vm_quartiles"]) + f"; units without a value: {len(missing)}.")

    text = "\n".join(md) + "\n"
    (OUT / "report.md").write_text(text)
    (OUT / "report_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    print(text)
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
