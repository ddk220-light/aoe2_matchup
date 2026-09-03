"""One-off: dump combat dicts for every (civ, slug) in golden/panel_spec.json.

These are the exact payloads the webapp's `/api/ref/combat-unit/<civ>/<slug>`
endpoint serves, frozen to a file so the golden parity capture (and every later
parity re-run) feeds the JS engine byte-identical unit stats without a database
or a running Flask server.

Run with the repo's python (needs the repo on sys.path; sqlite3 only, no
genieutils):

    python tools/simjs/dump_combat_dicts.py

Fails loudly on any slug not found — fix panel_spec.json, don't skip rows.
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402

spec = json.loads((ROOT / "tools/simjs/golden/panel_spec.json").read_text())
pairs = sorted({(r["civ1"], r["slug1"]) for r in spec} | {(r["civ2"], r["slug2"]) for r in spec})

con = sqlite3.connect(ROOT / "data/golden/aoe2_reference.db")
con.row_factory = sqlite3.Row
out, missing = {}, []
for civ, slug in pairs:
    row = con.execute(
        "select * from ref_units where civ_name=? and unit_slug=? and age='Imperial'",
        (civ, slug),
    ).fetchone()
    if row is None:
        missing.append(f"{civ}/{slug}")
        continue
    out[f"{civ}|{slug}"] = build_combat_dict_from_ref(row)
    print(f"  {civ:14s} {slug:42s} -> {row['unit_name']}")

if missing:
    sys.exit("NOT IN DB: " + ", ".join(missing))
dest = ROOT / "tools/simjs/golden/combat_dicts.json"
dest.write_text(json.dumps(out, indent=1, sort_keys=True))
print(f"wrote {len(out)} dicts -> {dest}")
