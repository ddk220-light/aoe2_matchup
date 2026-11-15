"""Build the committed per-cell value artefact for the Matchup Advisor (Revision 5).

Output: ``data/golden/advisor_cell_metrics.json.gz`` (deterministic: canonical JSON, gzip
mtime 0), schema 2. For every *observed* advisor cell (a, b) of
``data/golden/civ_matchups_first_pass.db`` (DB orientation, as stored):

    [a, b, value_a]

``value_a`` is the matchup value from a's side (``advisor_value.cell_value``: winner HP x
replenish, production and speed ratios; negative for a loss, 0 for a draw), rounded to
``VALUE_DIGITS``. Identity cells are not listed (the API serves 0 for them).

Inputs (docs/architecture/runbooks.md, "Advisor eco metrics"):
- ``$ADVISOR_ECO_OUT/cells.csv.gz`` from ``extract_cells.py`` (seed HP, army and building
  villager-minutes per observed cell; needs branch ``simulations/civ-matchups-campaign-2026-10-31``
  for the first-pass run records),
- the frozen campaign bundle (branch ``matchup-runs`` or ``$ADVISOR_ECO_OUT/bundle.json.gz``)
  for unit speed and ranged class,
- ``data/golden/civ_matchups_first_pass.db`` (its SHA-256 is recorded; the advisor tests fail
  when the DB changes and this artefact is not rebuilt).

Usage: ADVISOR_ECO_OUT=... python tools/economy/advisor_eco/build_advisor_metrics.py
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import gzip

from advisor_value import CONSTANTS, cell_value
from classify import BUNDLE_HASH, load_bundle, motion
from common import ADVISOR_DB, CELLS_CSV, REPO, advisor_units, connect, read_cells

DESTINATION = REPO / "data" / "golden" / "advisor_cell_metrics.json.gz"
SCHEMA_VERSION = 2
VALUE_DIGITS = 4


def sha256_file(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def build():
    db = connect()
    units = advisor_units(db)
    variants = load_bundle()
    assert all(variants[u["key"]]["profileHash"] == u["profileHash"] for u in units.values()), "bundle/profile mismatch"
    mo = {uid: motion(variants[u["key"]]) for uid, u in units.items()}
    observed = {(a, b): outcome for a, b, outcome in
                db.execute("SELECT a, b, outcome FROM cells WHERE evidence_type='observed'")}
    rows, counts = [], collections.Counter()
    for c in read_cells():
        key = (c["a"], c["b"])
        if observed.get(key) != c["outcome"]:
            raise SystemExit(f"cells.csv.gz is stale for cell {key}: rerun extract_cells.py")
        if c["outcome"] in ("a_win", "b_win") and None in (c["army_vm_a"], c["army_vm_b"], c["bld_vm_a"], c["bld_vm_b"]):
            raise SystemExit(f"cell {key} has no army economics: rerun extract_cells.py")
        value, parts = cell_value(c, mo)
        counts["draw" if parts is None else "decided"] += 1
        if parts is not None and not parts["hpKnown"]:
            counts["decidedWithoutSeedHp"] += 1
        rows.append([c["a"], c["b"], round(value, VALUE_DIGITS)])
    missing = set(observed) - {(r[0], r[1]) for r in rows}
    if missing:
        raise SystemExit(f"{len(missing)} observed cells have no metrics: rerun extract_cells.py")
    rows.sort(key=lambda r: (r[0], r[1]))
    dataset = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "description": "Per-cell matchup value (Revision 5) for the Matchup Advisor "
                       "(tools/economy/advisor_eco/build_advisor_metrics.py, advisor_value.py).",
        "advisorDataset": {"path": "data/golden/civ_matchups_first_pass.db", "sha256": sha256_file(ADVISOR_DB),
                           "sourceCommit": dataset.get("source_commit")},
        "inputs": {"bundleHash": BUNDLE_HASH, "cellsCsvRows": len(rows)},
        "value": {**CONSTANTS, "digits": VALUE_DIGITS},
        "columns": ["a", "b", "value_a"],
        "cells": rows,
        "counts": dict(sorted(counts.items())),
    }


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DESTINATION))
    args = parser.parse_args()
    if not CELLS_CSV.is_file():
        raise SystemExit(f"{CELLS_CSV} missing: set ADVISOR_ECO_OUT and run extract_cells.py first")
    artefact = build()
    data = gzip.compress(encode(artefact), compresslevel=9, mtime=0)
    with open(args.out, "wb") as handle:
        handle.write(data)
    print(json.dumps({"out": args.out, "bytes": len(data), "cells": len(artefact["cells"]),
                      "counts": artefact["counts"]}, indent=1))


if __name__ == "__main__":
    main()
