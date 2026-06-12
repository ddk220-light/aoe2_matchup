"""Surgical patch: restore the full Mayan archer cost discount.

ROOT CAUSE
----------
The Mayan "archers cost less" civ bonus is encoded in the dat as three
cumulative cost-multiply tiers that stack from a Feudal baseline:

    Feudal  -10%  ->  x0.90
    Castle  -20%  ->  x0.89   (cumulative 0.90*0.89 = 0.801)
    Imperial-30%  ->  x0.88   (cumulative 0.90*0.89*0.88 = 0.70488)

Each tier's effect command enumerates the archer-line unit IDs available
at/after that age. The Feudal tier's command does NOT list the later-introduced
units (Crossbowman, Arbalester, Plumed Archer, Elite Plumed Archer), so
`get_civ_bonus_techs_for_unit` -> `effect_applies_to_unit` returns False for the
Feudal tier on those units and it is dropped. Because the Castle/Imperial tiers
are designed to *cumulate on top of* the Feudal tier, dropping Feudal leaves the
unit under-discounted:

    Plumed (Castle)      got x0.89  (-11%)   should be x0.801  (-20%)
    Arbalester (Imperial)got x0.89*0.88(-21%) should be x0.70488(-30%)

The webapp battle simulator (/api/ref/combat-unit) and the matchup table
(best_units -> simulate_real_battle) both read ref_units.final_cost_*, so the
in-sim unit counts for Mayan archers were wrong in the resources matchup.

FIX
---
Recompute final_cost_* for the four affected Mayan archer-line units from their
base cost times the FULL tier chain (incl. the Feudal x0.90 tier), end-rounded
once -- exactly what the pipeline would produce if the Feudal tier applied.
This is a surgical patch on the committed DB because a full pipeline regen
rewrites unrelated combat-property columns on every row (see the
"committed-dbs-stale-vs-pipeline" memo).

Idempotent: always recomputes from base_cost_*, so re-running is a no-op.

Run:  python -m analysis.patches.patch_mayan_archer_cost          (apply)
      python -m analysis.patches.patch_mayan_archer_cost --dry    (preview)
"""
import os
import sqlite3
import sys

from aoe2x.paths import GOLDEN_DIR as _GOLDEN_DIR
DB = os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db")

# (unit_slug, age) -> cumulative cost multiplier (full Mayan archer tier chain
# up to and including that age). Castle = 0.90*0.89; Imperial = 0.90*0.89*0.88.
CASTLE = 0.90 * 0.89          # 0.801    (-20%)
IMPERIAL = 0.90 * 0.89 * 0.88  # 0.70488  (-30%)

TARGETS = {
    ("crossbow", "Castle"): CASTLE,
    ("plumed_archer_mayans", "Castle"): CASTLE,
    ("arbalester", "Imperial"): IMPERIAL,
    ("elite_plumed_archer_mayans", "Imperial"): IMPERIAL,
}


def main():
    dry = "--dry" in sys.argv
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    changed = 0
    for (slug, age), mult in TARGETS.items():
        cur.execute(
            "SELECT id, base_cost_food, base_cost_wood, base_cost_gold, "
            "final_cost_food, final_cost_wood, final_cost_gold "
            "FROM ref_units WHERE civ_name='Mayans' AND unit_slug=? AND age=?",
            (slug, age),
        )
        rows = cur.fetchall()
        if not rows:
            print(f"  WARN: no row for Mayans/{slug}/{age}")
            continue
        for r in rows:
            nf = round((r["base_cost_food"] or 0) * mult)
            nw = round((r["base_cost_wood"] or 0) * mult)
            ng = round((r["base_cost_gold"] or 0) * mult)
            old = (r["final_cost_food"], r["final_cost_wood"], r["final_cost_gold"])
            new = (nf, nw, ng)
            mark = "" if old == new else "  <-- CHANGED"
            print(
                f"  {slug:30s} {age:9s} base(f{r['base_cost_food']:.0f} "
                f"w{r['base_cost_wood']:.0f} g{r['base_cost_gold']:.0f})  "
                f"final {tuple(int(x) for x in old)} -> {new}{mark}"
            )
            if old != new and not dry:
                cur.execute(
                    "UPDATE ref_units SET final_cost_food=?, final_cost_wood=?, "
                    "final_cost_gold=? WHERE id=?",
                    (nf, nw, ng, r["id"]),
                )
                changed += 1
    if dry:
        print("DRY RUN -- no changes written")
    else:
        conn.commit()
        print(f"Committed. Rows changed: {changed}")
    conn.close()


if __name__ == "__main__":
    main()
