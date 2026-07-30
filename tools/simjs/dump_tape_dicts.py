"""Export the tape corpus for the JS engine: combat dicts + an army-count plan.

Counterpart of dump_combat_dicts.py (which serves the golden parity panel). This
one serves the tape-validation rig, so it writes to data/validation/ and NEVER
to tools/simjs/golden/ -- that directory is the write-once parity baseline.

The plan file exists so the JS runner performs ZERO cost arithmetic. Three
incompatible army-count rules live in this repo (the recorder's weighted-cost
rule here, and two Battle Sim page rules in simulate.js); only this one produces
counts that mean anything against `tape_outcome`. Python owns it because
tape_rig.arena_counts is already proven to reproduce all 38 recorded counts.

    python tools/simjs/dump_tape_dicts.py

Fails loudly on any slug missing from the reference DB.
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402
from aoe2x.validation.tape_rig import arena_counts, weighted_cost    # noqa: E402

CORPUS = ROOT / "aoe2x" / "validation" / "tape_corpus.json"
REF_DB = ROOT / "data" / "golden" / "aoe2_reference.db"
OUT_DIR = ROOT / "data" / "validation"


def main() -> None:
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))["rows"]
    con = sqlite3.connect(str(REF_DB))
    con.row_factory = sqlite3.Row

    ref_cache = {}

    def ref(civ, slug):
        if (civ, slug) not in ref_cache:
            r = con.execute(
                "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?"
                " AND age='Imperial'", (civ, slug)).fetchone()
            ref_cache[(civ, slug)] = r
        return ref_cache[(civ, slug)]

    dicts, plan, missing = {}, [], []
    for r in rows:
        r1 = ref(r["subject_civ"], r["subject_slug"])
        r2 = ref(r["opp_civ"], r["opp_slug"])
        if r1 is None:
            missing.append(f'{r["subject_civ"]}/{r["subject_slug"]}')
            continue
        if r2 is None:
            missing.append(f'{r["opp_civ"]}/{r["opp_slug"]}')
            continue

        dicts[f'{r["subject_civ"]}|{r["subject_slug"]}'] = build_combat_dict_from_ref(r1)
        dicts[f'{r["opp_civ"]}|{r["opp_slug"]}'] = build_combat_dict_from_ref(r2)

        n1, n2 = r["n_subject"], r["n_opp"]
        eq_res = list(arena_counts(weighted_cost(r1), weighted_cost(r2)))
        plan.append({
            "plan_id": f'{r["subject_slug"]}__vs__{r["opp_civ"]}_{r["opp_slug"]}',
            "subject_civ": r["subject_civ"], "subject_slug": r["subject_slug"],
            "opp_civ": r["opp_civ"], "opp_slug": r["opp_slug"],
            "tape_outcome": r["tape_outcome"],
            "counts": {"tape": [n1, n2], "equal_resource": eq_res,
                       "equal_count": [n1, n1]},
            "cost": {
                "my_food": float(r1["final_cost_food"] or 0),
                "my_wood": float(r1["final_cost_wood"] or 0),
                "my_gold": float(r1["final_cost_gold"] or 0),
                "opp_food": float(r2["final_cost_food"] or 0),
                "opp_wood": float(r2["final_cost_wood"] or 0),
                "opp_gold": float(r2["final_cost_gold"] or 0),
            },
        })

    if missing:
        sys.exit("NOT IN DB: " + ", ".join(sorted(set(missing))))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "tape_combat_dicts.json").write_text(
        json.dumps(dicts, indent=1, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "tape_plan.json").write_text(
        json.dumps({"rows": plan}, indent=1), encoding="utf-8")
    print(f"wrote {len(dicts)} dicts and {len(plan)} plan rows -> {OUT_DIR}")

    drift = [p["plan_id"] for p in plan
             if p["counts"]["equal_resource"] != p["counts"]["tape"]]
    if drift:
        print(f"WARNING cost-model drift on {len(drift)} rows: {drift[:5]}")


if __name__ == "__main__":
    main()
