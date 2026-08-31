"""Export a civilization variant from the reference DB and a same-master fixture.

The structural Genie fields (collision, projectile, animation, obstruction) are
identical for a unit master.  This exporter validates the pinned DAT provenance
on an existing same-master fixture, then replaces every civilization-dependent
Imperial stat from the read-only reference database.  It is useful on machines
without ``genieutils`` while remaining reproducible and source-backed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

from export_unit_mechanics import _damage_against_self, _parse_classes


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", required=True, type=Path)
    parser.add_argument("--dat", required=True, type=Path)
    parser.add_argument("--base-fixture", required=True, type=Path)
    parser.add_argument("--unit-slug", required=True)
    parser.add_argument("--civ", required=True)
    parser.add_argument("--master", required=True, type=int)
    parser.add_argument(
        "--reload-multiplier",
        type=float,
        help="Source-backed civilization reload multiplier absent from the reference DB",
    )
    parser.add_argument(
        "--reload-evidence",
        type=Path,
        help="Text source that documents --reload-multiplier",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if (args.reload_multiplier is None) != (args.reload_evidence is None):
        raise SystemExit("reload multiplier and evidence must be supplied together")
    if args.reload_multiplier is not None:
        if not 0 < args.reload_multiplier <= 1:
            raise SystemExit("reload multiplier must be in (0, 1]")
        if not args.reload_evidence.is_file():
            raise SystemExit("reload evidence does not exist")

    base = json.loads(args.base_fixture.read_text(encoding="utf-8"))
    dat_hash = sha256(args.dat)
    if base.get("unit_master") != args.master:
        raise SystemExit("base fixture unit master differs")
    if base.get("provenance", {}).get("dat_sha256") != dat_hash:
        raise SystemExit("base fixture DAT hash differs from the selected DAT")

    uri = f"{args.reference_db.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, civ_name, age, final_hp, final_range, final_reload_time,
                   final_accuracy, final_los, final_attacks_json,
                   final_armors_json, pop_space
            FROM ref_units
            WHERE unit_slug = ? AND civ_name = ? AND age = 'Imperial'
            """,
            (args.unit_slug, args.civ),
        ).fetchall()
        if len(rows) != 1:
            raise SystemExit(f"expected one reference row; found {len(rows)}")
        row = dict(rows[0])
        speed = connection.execute(
            """
            SELECT speed FROM ref_stat_chain
            WHERE ref_unit_id = ? ORDER BY step_order DESC LIMIT 1
            """,
            (row["id"],),
        ).fetchone()
        if speed is None:
            raise SystemExit("reference row has no stat-chain speed")

    result = deepcopy(base)
    attacks = _parse_classes(row["final_attacks_json"])
    armors = _parse_classes(row["final_armors_json"])
    reload_seconds = float(row["final_reload_time"])
    if args.reload_multiplier is not None:
        reload_seconds *= args.reload_multiplier
    result.update({
        "civilization": row["civ_name"],
        "age": row["age"],
        "hp": int(row["final_hp"]),
        "speed_tiles_per_second": float(speed["speed"]),
        "attack_range_tiles": float(row["final_range"]),
        "reload_seconds": reload_seconds,
        "line_of_sight_tiles": float(row["final_los"]),
        "attack_classes": attacks,
        "armor_classes": armors,
        "population_space": float(row["pop_space"]),
        "derived": {"damage_vs_self": _damage_against_self(attacks, armors)},
    })
    if result.get("ranged") is not None:
        result["ranged"]["accuracy_percent"] = float(row["final_accuracy"])
    provenance = result["provenance"]
    provenance.update({
        "reference_db_sha256": sha256(args.reference_db),
        "dat_sha256": dat_hash,
        "reference_selector": (
            f"ref_units WHERE unit_slug='{args.unit_slug}' AND "
            f"civ_name='{args.civ}' AND age='Imperial'"
        ),
        "dat_selector": f"same unit master {args.master} structural fields",
        "structural_base_fixture": args.base_fixture.name,
        "structural_base_fixture_sha256": sha256(args.base_fixture),
    })
    if args.reload_multiplier is not None:
        provenance.update({
            "reload_base_seconds": float(row["final_reload_time"]),
            "reload_multiplier": args.reload_multiplier,
            "reload_evidence": str(args.reload_evidence),
            "reload_evidence_sha256": sha256(args.reload_evidence),
        })
        provenance["fields"]["reload_seconds"] = (
            "ref_units.final_reload_time * source-backed civilization reload multiplier"
        )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
