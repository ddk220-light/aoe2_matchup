"""Export combat dicts for the calibration corpus (real recorded fights).

Generalises dump_tape_dicts.py: same reference-DB query, same
build_combat_dict_from_ref() call, same fail-loudly style -- but reads
calibration/fixtures/manifest.json instead of the retired
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
from aoe2x.calibration.paths import CalibrationPaths, workspace_paths  # noqa: E402
from aoe2x.calibration.source import verify_source_archive  # noqa: E402

REF_DB = ROOT / "data" / "golden" / "aoe2_reference.db"


def main(paths: CalibrationPaths | None = None) -> None:
    resolved = paths or workspace_paths()
    verify_source_archive(resolved)
    fights = json.loads(resolved.manifest.read_text(encoding="utf-8"))["fights"]
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

    resolved.combat_dicts.parent.mkdir(parents=True, exist_ok=True)
    resolved.combat_dicts.write_text(
        json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(out)} dicts -> {resolved.combat_dicts}")


if __name__ == "__main__":
    main()
