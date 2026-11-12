"""List every advisor plan whose main unit or sidekick changes under the current owner rules
(HP < 50%, eco >= 25%, kite eligibility and dominance per classify.py).
Writes $ADVISOR_ECO_OUT/plan_changes_rev3.json and prints a compact table.
Usage: python tools/economy/advisor_eco/list_changes_rev3.py"""
from __future__ import annotations

import itertools
import json

from advisor_model import build, summary
from classify import ECO, HP_LIMIT, load_bundle, motion
from common import OUT, advisor_units, civ_documents, connect, read_cells
from impact_rev2 import eco_win_set


def main():
    db = connect()
    units = advisor_units(db)
    documents = civ_documents(db, units)
    variants = load_bundle()
    mo = {uid: motion(variants[u["key"]]) for uid, u in units.items()}
    cells_list = list(read_cells())
    cells = {(c["a"], c["b"]): c for c in cells_list}
    semi = eco_win_set(cells_list, mo, HP_LIMIT, ECO)
    name = lambda uid: units[uid]["name"] if uid is not None else None  # noqa: E731

    def cell(x, y):
        c = cells.get((x, y)); flip = False
        if c is None:
            c = cells.get((y, x)); flip = True
        return c, flip

    def caveat(loser, winner):
        c, flip = cell(loser, winner)
        nl, nw = (c["count_b"], c["count_a"]) if flip else (c["count_a"], c["count_b"])
        vl, vw = (c["vm_b"], c["vm_a"]) if flip else (c["vm_a"], c["vm_b"])
        return {"enemy": name(winner), "armies": f"{nl} vs {nw}", "winnerHpPct": round(100 * c["hp_avg"]),
                "seeds": c["seeds"], "vm": [round(vl), round(vw)], "cheaperPct": round(100 * (1 - vl / vw))}

    out = []
    for left, right in itertools.combinations(sorted(documents), 2):
        rows = documents[left][right]
        before, after = build(rows, units), build(rows, units, semi, "eco_lite_main")
        for side, civ, enemy in (("left", left, right), ("right", right, left)):
            sb, sa = summary(before[side]), summary(after[side])
            if sb["main"] == sa["main"] and sb["sidekick"] == sa["sidekick"]:
                continue
            p, q = after[side], before[side]
            out.append({
                "civ": civ, "enemy": enemy,
                "mainBefore": name(sb["main"]), "mainAfter": name(sa["main"]),
                "mainBeforeLosses": [name(x) for x in sb["main_losses"]],
                "mainBeforeWins": len(q["main"]["wins"]) if q["main"] else 0,
                "mainAfterWins": len(p["main"]["wins"]) if p["main"] else 0,
                "mainAfterCaveats": [caveat(r[0], r[1]) for r in p["main"]["semi_losses"]] if p["main"] else [],
                "sidekickBefore": name(sb["sidekick"]), "sidekickAfter": name(sa["sidekick"]),
                "additionsBefore": len(sb["additions"]), "additionsAfter": len(sa["additions"]),
            })
    (OUT / "plan_changes_rev3.json").write_text(json.dumps(out, indent=1))
    mains = [r for r in out if r["mainBefore"] != r["mainAfter"]]
    print(f"plans with main or sidekick change: {len(out)}; main changed: {len(mains)}")


if __name__ == "__main__":
    main()
