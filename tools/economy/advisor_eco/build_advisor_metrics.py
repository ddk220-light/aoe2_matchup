"""Build the committed per-cell metrics artefact for the eco-aware Matchup Advisor (Revision 4).

Output: ``data/golden/advisor_cell_metrics.json.gz`` (deterministic: canonical JSON, gzip
mtime 0). It holds, for every *observed* advisor cell (a, b) of
``data/golden/civ_matchups_first_pass.db`` (DB orientation, ``a < b`` as stored):

    [a, b, category_a, category_b, winner_hp, vm_a, vm_b]

- ``category_*``: the Revision 3 category from that unit's side (``classify.py``:
  kite eligibility, dominance needs winner HP >= 50% and a >= 25% cheaper army, power /
  eco / cheap split at winner HP 50%), or ``close`` for observed close cells.
- ``winner_hp``: the cell winner's remaining HP fraction (seed mean, lost seeds 0), rounded
  to ``HP_DIGITS``; ``null`` for close cells and the 962 decided cells without seed HP.
- ``vm_a``/``vm_b``: both armies' 60-second investment in weighted villager-minutes
  (production buildings and common research included), rounded to ``VM_DIGITS``.

plus ``fullResearchVm`` (advisor unit id -> full research package in villager-minutes, for the
"cheaper to fully upgrade" badge; Flemish Militia has none). Identity and inferred
(never simulated) cells are not listed: the API derives ``close`` / ``pending`` for them from
the advisor DB itself.

Inputs (see docs/architecture/runbooks.md, "Advisor eco metrics"):
- ``$ADVISOR_ECO_OUT/cells.csv.gz`` from ``extract_cells.py`` (seed HP + 60-s investment per
  observed cell; ~10 min single process; needs branch
  ``simulations/civ-matchups-campaign-2026-10-31`` for the first-pass run records),
- the frozen campaign bundle (branch ``matchup-runs`` or ``$ADVISOR_ECO_OUT/bundle.json.gz``)
  for the kite rule,
- ``data/golden/civ_matchups_first_pass.db`` (its SHA-256 is recorded; the advisor tests fail
  when the DB changes and this artefact is not rebuilt).

Usage: ADVISOR_ECO_OUT=... python tools/economy/advisor_eco/build_advisor_metrics.py [--check-classification]
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json

from advisor_model_rev4 import LOSS_KEY, WIN_KEY
from classify import BUNDLE_HASH, ECO, HP_LIMIT, KITE_MIN_RANGE, BADGE_RATIO, classify, load_bundle, motion
from common import ADVISOR_DB, CELLS_CSV, REPO, advisor_units, connect, read_cells

DESTINATION = REPO / "data" / "golden" / "advisor_cell_metrics.json.gz"
SCHEMA_VERSION = 1
HP_DIGITS = 4   # winner HP fraction: 0.01 % of starting HP
VM_DIGITS = 2   # villager-minutes
CATEGORIES = ["dominance", "kite", "plain_win", "power_win", "eco_win", "close",
              "cheap_loss", "plain_loss", "kited_loss", "outclassed_loss"]
LABEL_TO_KEY = {"Complete dominance": "dominance", "Clear win (kite)": "kite", "Plain win": "plain_win",
                "Power win": "power_win", "Eco win": "eco_win", "Cheap loss": "cheap_loss",
                "Cheap loss (HP unknown)": "cheap_loss", "Plain loss": "plain_loss", "Kited loss": "kited_loss",
                "Outclassed loss": "outclassed_loss"}


def sha256_file(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def rnd(value, digits):
    return None if value is None else round(value, digits)


def build():
    db = connect()
    units = advisor_units(db)
    variants = load_bundle()
    assert all(variants[u["key"]]["profileHash"] == u["profileHash"] for u in units.values()), "bundle/profile mismatch"
    mo = {uid: motion(variants[u["key"]]) for uid, u in units.items()}
    observed = {(a, b): outcome for a, b, outcome in
                db.execute("SELECT a, b, outcome FROM cells WHERE evidence_type='observed'")}
    rows, full, counts = [], {}, collections.Counter()
    for c in read_cells():
        key = (c["a"], c["b"])
        if observed.get(key) != c["outcome"]:
            raise SystemExit(f"cells.csv.gz is stale for cell {key}: rerun extract_cells.py")
        for side in "ab":
            if c["full_vm_" + side] is not None:
                full[c[side]] = round(c["full_vm_" + side], VM_DIGITS)
        vm_a, vm_b = rnd(c["vm_a"], VM_DIGITS), rnd(c["vm_b"], VM_DIGITS)
        if c["outcome"] in ("a_win", "b_win") and c["vm_a"] is not None and c["vm_b"] is not None:
            wk, lk, w = classify(c, mo)
            cat = {w: WIN_KEY[wk], ("b" if w == "a" else "a"): LOSS_KEY[lk]}
            hp = rnd(c["hp_avg"], HP_DIGITS)
        else:
            cat, hp = {"a": "close", "b": "close"}, None
        counts[f"{cat['a']}/{cat['b']}"] += 1
        rows.append([c["a"], c["b"], cat["a"], cat["b"], hp, vm_a, vm_b])
    missing = set(observed) - {(r[0], r[1]) for r in rows}
    if missing:
        raise SystemExit(f"{len(missing)} observed cells have no metrics: rerun extract_cells.py")
    rows.sort(key=lambda r: (r[0], r[1]))
    dataset = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
    artefact = {
        "schemaVersion": SCHEMA_VERSION,
        "description": "Per-cell Revision 3 categories, winner HP and 60-s army investment for the eco-aware "
                       "Matchup Advisor (tools/economy/advisor_eco/build_advisor_metrics.py).",
        "advisorDataset": {"path": "data/golden/civ_matchups_first_pass.db", "sha256": sha256_file(ADVISOR_DB),
                           "sourceCommit": dataset.get("source_commit")},
        "inputs": {"bundleHash": BUNDLE_HASH, "cellsCsvRows": len(rows)},
        "thresholds": {"winnerHpBelow": HP_LIMIT, "cheaperArmyBy": ECO, "kiteMinRangeTiles": KITE_MIN_RANGE,
                       "badgeResearchRatio": BADGE_RATIO},
        "rounding": {"winnerHpDigits": HP_DIGITS, "villagerMinuteDigits": VM_DIGITS},
        "categories": CATEGORIES,
        "columns": ["a", "b", "category_a", "category_b", "winner_hp", "vm_a", "vm_b"],
        "cells": rows,
        "fullResearchVm": {str(k): full[k] for k in sorted(full)},
        "counts": dict(sorted(counts.items())),
    }
    return artefact


def check_classification(artefact):
    """Every decided cell's category equals docs/army-economics/advisor-classification.csv.gz."""
    by_key = {(r[0], r[1]): r for r in artefact["cells"]}
    checked = 0
    with gzip.open(REPO / "docs" / "army-economics" / "advisor-classification.csv.gz", "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            a, b = int(row["a_id"]), int(row["b_id"])
            got = by_key[(a, b)]
            assert (got[2], got[3]) == (LABEL_TO_KEY[row["category_a"]], LABEL_TO_KEY[row["category_b"]]), (a, b, got, row)
            checked += 1
    decided = sum(1 for r in artefact["cells"] if r[2] != "close")
    assert checked == decided, (checked, decided)
    return checked


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-classification", action="store_true",
                        help="assert the categories equal the committed advisor-classification.csv.gz")
    parser.add_argument("--out", default=str(DESTINATION))
    args = parser.parse_args()
    if not CELLS_CSV.is_file():
        raise SystemExit(f"{CELLS_CSV} missing: set ADVISOR_ECO_OUT and run extract_cells.py first")
    artefact = build()
    if args.check_classification:
        print("classification agrees on", check_classification(artefact), "decided cells")
    data = gzip.compress(encode(artefact), compresslevel=9, mtime=0)
    with open(args.out, "wb") as handle:
        handle.write(data)
    print(json.dumps({"out": args.out, "bytes": len(data), "cells": len(artefact["cells"]),
                      "fullResearchUnits": len(artefact["fullResearchVm"]), "counts": artefact["counts"]}, indent=1))


if __name__ == "__main__":
    main()
