"""Role: derive — schema + I/O for derived_data.db.

Holds analysis tables computed from matchup_db.db raw outcomes:
  - battle_scores:           ranking scores per (line, civ, unit, score_type)
  - advisor_recommendations: PARKED/LEGACY — its deriver was archived to
    .old/webapp/derive_advisor_recs.py (2026-06-10); nothing writes it and the
    live advisor simulates on the fly (best_units). DDL kept so existing DBs
    keep validating.

Reference data (units, techs, classes) stays in aoe2_reference.db; this
file only holds derivations that get rebuilt when the sim or scoring
formulas change.
"""

import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS battle_scores (
    id INTEGER PRIMARY KEY,
    line_slug TEXT NOT NULL,
    age TEXT NOT NULL,
    civ_name TEXT NOT NULL,
    unit_slug TEXT NOT NULL,
    score_type TEXT NOT NULL,
    score_value REAL NOT NULL,
    rank INTEGER,
    median_delta REAL,
    build_number TEXT NOT NULL DEFAULT '170934',
    UNIQUE(line_slug, age, civ_name, unit_slug, score_type, build_number)
);
CREATE INDEX IF NOT EXISTS idx_bs_line_age ON battle_scores(line_slug, age, build_number);
CREATE INDEX IF NOT EXISTS idx_bs_civ_unit ON battle_scores(civ_name, unit_slug, age, build_number);

CREATE TABLE IF NOT EXISTS advisor_recommendations (
    id INTEGER PRIMARY KEY,
    civ TEXT NOT NULL,
    opponent TEXT NOT NULL,
    rec_type TEXT NOT NULL,
    rec_rank INTEGER NOT NULL,
    unit_slug TEXT NOT NULL,
    unit_name TEXT NOT NULL,
    score REAL NOT NULL,
    UNIQUE(civ, opponent, rec_type, rec_rank)
);
CREATE INDEX IF NOT EXISTS idx_ar ON advisor_recommendations(civ, opponent);
"""


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
