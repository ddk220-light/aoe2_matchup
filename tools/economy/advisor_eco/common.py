"""Shared helpers for the advisor x army-economics analysis (stdlib only).

Analysis scripts, not site code: they read the committed advisor dataset
(`data/golden/civ_matchups_first_pass.db`) and the committed army-economics
artefact (`data/army_economics/army_context.jsonl.gz`, via `aoe2x.economy`) and
write their large outputs to a scratch directory (``ADVISOR_ECO_OUT``).
See docs/army-economics/ADVISOR_ECO_DESIGN.md.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sqlite3
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ADVISOR_DB = REPO / "data" / "golden" / "civ_matchups_first_pass.db"
OUT = Path(os.environ.get("ADVISOR_ECO_OUT", "/tmp/advisor-eco"))
CELLS_CSV = OUT / "cells.csv.gz"

# Proposed thresholds (owner, 2026-11-12).
HP_LIMIT = 0.33          # winner keeps < 33% of its starting HP (seed average)
ECO_SAVING = 0.33        # loser army >= 33% fewer villager-minutes than the winner army
# Sensitivity bands ("fails only one condition").
HP_NEAR = 0.40
ECO_NEAR = 0.25


def connect():
    return sqlite3.connect(f"file:{ADVISOR_DB}?mode=ro", uri=True)


def advisor_units(db=None):
    db = db or connect()
    return {u["id"]: u for u in (json.loads(r[0]) for r in db.execute("SELECT data FROM units ORDER BY id"))}


def evidence_decoder(db):
    dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    return lambda blob: json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))


def economics_map(data, units):
    """Advisor unit id -> (civ, unitId, mode) in the economics runtime.

    Matching key: (civilization, display name). Every advisor unit must match
    exactly one economics profile, except Shu War Chariot, which has two modes
    (focus_fire, barrage) with identical economics (checked by the caller).
    """
    by_name = {}
    for key in data.keys():
        by_name.setdefault((key[0], data.unit(*key)["name"]), []).append(key)
    mapping, problems = {}, []
    for uid, unit in units.items():
        keys = by_name.get((unit["civilization"], unit["name"]), [])
        if not keys:
            problems.append((uid, unit["key"], "no economics profile"))
            continue
        if len(keys) > 1:
            problems.append((uid, unit["key"], f"{len(keys)} profiles: " + ", ".join(k[2] for k in keys)))
        mapping[uid] = sorted(keys, key=lambda k: k[2] != "default")[0]
    return mapping, problems


def read_cells(path=CELLS_CSV):
    numeric = {"a", "b", "count_a", "count_b", "seeds", "seeds_won_a", "seeds_won_b", "draws", "evidence_id", "gold_a", "gold_b"}
    floats = {"hp_avg", "hp_avg_won", "hp_min", "hp_max", "vm_a", "vm_b", "full_vm_a", "full_vm_b",
              "wcost_a", "wcost_b", "saving", "army_vm_a", "army_vm_b", "common_vm_a", "common_vm_b"}
    with gzip.open(path, "rt", newline="") as handle:
        for row in csv.DictReader(handle):
            for key in numeric:
                row[key] = int(row[key]) if row[key] != "" else None
            for key in floats:
                row[key] = float(row[key]) if row[key] != "" else None
            yield row


def civ_documents(db=None, units=None):
    """{civ: {opponent civ: rows}} exactly as ``aoe2_api.services.advisor.advisor_matchups``."""
    db = db or connect()
    units = units or advisor_units(db)
    inverse = {"a_win": "b_win", "b_win": "a_win", "equivalent": "equivalent", "close_uncertain": "close_uncertain"}
    by_civ = {}
    for uid, unit in units.items():
        by_civ.setdefault(unit["civilization"], set()).add(uid)
    records = db.execute("SELECT * FROM cells ORDER BY a, b").fetchall()
    documents = {civ: {} for civ in by_civ}
    for civ, own in by_civ.items():
        for a, b, outcome, evidence, ca, cb, tier, flags, eid in records:
            if a not in own and b not in own:
                continue
            if a not in own:
                a, b, ca, cb, outcome = b, a, cb, ca, inverse[outcome]
            documents[civ].setdefault(units[b]["civilization"], []).append([a, b, outcome, evidence, ca, cb, tier, flags, eid])
    return documents
