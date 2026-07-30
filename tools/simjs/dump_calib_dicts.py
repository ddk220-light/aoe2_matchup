"""Export combat dicts for the calibration corpus (real recorded fights).

Generalises dump_tape_dicts.py: same reference-DB query, same
build_combat_dict_from_ref() call, same fail-loudly style -- but reads
data/calibration/manifest.json (Task 1's ingest) instead of the retired
aoe2x/validation/tape_corpus.json, and writes ONLY combat dicts. Unlike
dump_tape_dicts.py there is no accompanying count/cost plan file: calibration
counts come straight from each manifest fight's side1.count/side2.count (the
real recorded army sizes), so tools/simjs/calib_runner.mjs needs no
count-arithmetic file at all -- it reads counts directly off the manifest.

    python tools/simjs/dump_calib_dicts.py

Fails loudly on any (civ, slug) referenced by the manifest but missing from
the reference DB.
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402

MANIFEST = ROOT / "data" / "calibration" / "manifest.json"
REF_DB = ROOT / "data" / "golden" / "aoe2_reference.db"
OUT_PATH = ROOT / "data" / "calibration" / "combat_dicts.json"


def main() -> None:
    fights = json.loads(MANIFEST.read_text(encoding="utf-8"))["fights"]
    pairs = sorted({
        (side["civ"], side["slug"])
        for fight in fights
        for side in (fight["side1"], fight["side2"])
    })

    con = sqlite3.connect(str(REF_DB))
    con.row_factory = sqlite3.Row

    out, missing = {}, []
    for civ, slug in pairs:
        row = con.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?"
            " AND age='Imperial'", (civ, slug)).fetchone()
        if row is None:
            missing.append(f"{civ}/{slug}")
            continue
        out[f"{civ}|{slug}"] = build_combat_dict_from_ref(row)
        print(f"  {civ:14s} {slug:42s} -> {row['unit_name']}")

    if missing:
        sys.exit("NOT IN DB: " + ", ".join(missing))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(out)} dicts -> {OUT_PATH}")


if __name__ == "__main__":
    main()
