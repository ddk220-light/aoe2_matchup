"""extract_combat_dicts.py — dump V2-harness combat dicts from aoe2_reference.db.

Produces the `combat_dicts_all.json` format the V2 engine consumes
(run_pool_v2.js / headless_sim.js runFight): `{"Civ/slug": <combat dict>}`,
where each dict is exactly what /api/ref/combat-unit serves plus the extra
fields the harness needs (name, civ, total_cost, outline_size). This mirrors
`combat_dict()` in apps/video/sim_v2/build_v2_categorization.py on the
aoe2_ai_for_simulation branch — keep the two in lockstep.

Run from the repo root (aoe2x must be importable):

    python simulation_v2/extract_combat_dicts.py --out combat_dicts_all.json
    python simulation_v2/extract_combat_dicts.py --units Incas/elite_champi_warrior Malians/elite_gbeto_malians

Default: every Imperial civ x unit row in the DB (the full-rerun input).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402

REF_DB = Path(__file__).resolve().parents[1] / "data" / "golden" / "aoe2_reference.db"


# Units whose listed cost buys a BATCH, so per-unit cost is cost/batch. An
# explicit allowlist — NOT derivable from pop_space (Karambit is 0.5-pop but
# trains singly). Kept in lockstep with TRAIN_BATCH in
# apps/video/sim_v2/build_v2_categorization.py + apps/video/overlay/overlay_data.py
# on the aoe2_ai_for_simulation branch.
TRAIN_BATCH = {
    "blackwood_archer_tupi": 2,
    "elite_blackwood_archer_tupi": 2,
}


def _batch(row) -> int:
    return TRAIN_BATCH.get(row["unit_slug"], 1)


def combat_dict(row) -> dict:
    d = build_combat_dict_from_ref(row)
    d["name"] = row["unit_name"]
    d["civ"] = row["civ_name"]
    d["total_cost"] = (((row["final_cost_food"] or 0) + (row["final_cost_wood"] or 0)
                       + (row["final_cost_gold"] or 0)) / _batch(row))
    d["outline_size"] = row["outline_size_x"] or 0.2
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-db", default=str(REF_DB))
    ap.add_argument("--out", default="combat_dicts_all.json")
    ap.add_argument("--units", nargs="*", metavar="Civ/slug",
                    help="restrict to these units (default: every Imperial row)")
    a = ap.parse_args()

    conn = sqlite3.connect(a.ref_db)
    conn.row_factory = sqlite3.Row
    out: dict[str, dict] = {}
    if a.units:
        for key in a.units:
            civ, slug = key.split("/", 1)
            row = conn.execute(
                "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
                (civ, slug)).fetchone()
            if row is None:
                sys.exit(f"no Imperial ref row for {key}")
            out[key] = combat_dict(row)
    else:
        for row in conn.execute("SELECT * FROM ref_units WHERE age='Imperial'"):
            out[f"{row['civ_name']}/{row['unit_slug']}"] = combat_dict(row)

    Path(a.out).write_text(json.dumps(out), encoding="utf-8")
    print(f"wrote {len(out)} combat dicts -> {a.out}")


if __name__ == "__main__":
    main()
