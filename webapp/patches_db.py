"""Role: patch-tooling — schema + I/O for patches.db, the patch registry and
per-patch diff tables (also read at serve time via get_current_build).

Tables:
  patches              one row per game build; is_current=1 marks the live build
  patch_unit_changes   raw per-(civ,unit) stat deltas from the ref_units diff
  patch_unit_ranking   how a unit's ranking score/rank moved (per score_type)
  patch_matchup_changes matchups that shifted for a changed unit (per scale)

get_current_build() is the single resolver every stat page goes through.
"""
import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "patches.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS patches (
    id INTEGER PRIMARY KEY,
    build_number TEXT UNIQUE NOT NULL,
    release_date TEXT,
    title TEXT,
    summary_md TEXT,
    source_url TEXT,
    baseline_build TEXT,
    is_current INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS patch_unit_changes (
    patch_id INTEGER, civ_name TEXT, unit_slug TEXT,
    field TEXT, old_value REAL, new_value REAL, note TEXT
);
CREATE TABLE IF NOT EXISTS patch_unit_ranking (
    patch_id INTEGER, civ_name TEXT, unit_slug TEXT, score_type TEXT,
    old_score REAL, new_score REAL, old_rank INTEGER, new_rank INTEGER
);
CREATE TABLE IF NOT EXISTS patch_matchup_changes (
    patch_id INTEGER, my_civ TEXT, my_unit_slug TEXT,
    opp_civ TEXT, opp_unit_slug TEXT, scale TEXT,
    old_winner INTEGER, new_winner INTEGER,
    old_score REAL, new_score REAL, swing REAL
);
CREATE INDEX IF NOT EXISTS idx_puc ON patch_unit_changes(patch_id, civ_name, unit_slug);
CREATE INDEX IF NOT EXISTS idx_pur ON patch_unit_ranking(patch_id, civ_name, unit_slug);
CREATE INDEX IF NOT EXISTS idx_pmc ON patch_matchup_changes(patch_id, my_civ, my_unit_slug);
"""


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_patch(conn, *, build_number, release_date, title, summary_md,
                 source_url, baseline_build, is_current=0, created_at=None):
    conn.execute(
        "INSERT OR REPLACE INTO patches "
        "(build_number, release_date, title, summary_md, source_url, "
        " baseline_build, is_current, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (build_number, release_date, title, summary_md, source_url,
         baseline_build, is_current, created_at),
    )
    return conn.execute("SELECT id FROM patches WHERE build_number=?",
                        (build_number,)).fetchone()[0]


def set_current_build(conn, build_number):
    conn.execute("UPDATE patches SET is_current=0")
    cur = conn.execute("UPDATE patches SET is_current=1 WHERE build_number=?", (build_number,))
    if cur.rowcount == 0:
        raise ValueError(f"build_number {build_number!r} not found in patches table")


def patch_id_for(conn, build_number):
    r = conn.execute("SELECT id FROM patches WHERE build_number=?",
                     (build_number,)).fetchone()
    return r[0] if r else None


def get_current_build(patches_db_path=DEFAULT_DB_PATH, **_ignored):
    """Return the current build_number, or None if patches.db is absent/empty.

    Extra kwargs (derived_db_path/out_db_path) are accepted and ignored so
    callers can pass their own DB path without knowing patches.db's location.
    """
    if not os.path.exists(patches_db_path):
        return None
    conn = sqlite3.connect(patches_db_path)
    try:
        r = conn.execute(
            "SELECT build_number FROM patches WHERE is_current=1 "
            "ORDER BY release_date DESC LIMIT 1").fetchone()
        if r:
            return r[0]
        r = conn.execute(
            "SELECT build_number FROM patches ORDER BY release_date DESC LIMIT 1"
        ).fetchone()
        return r[0] if r else None
    finally:
        conn.close()
