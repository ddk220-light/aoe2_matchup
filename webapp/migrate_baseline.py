"""One-time baseline migration: tag the existing committed result DBs as build
170934, rebuild their schemas to include build_number, seed the baseline
patches row, and move civ_power_units.json -> civ_power_units/170934.json.

Idempotent: re-running detects build_number already present and only ensures
the patches row + per-build JSON exist.
"""
import argparse
import os
import shutil
import sqlite3

import patches_db as _patches_db  # aliased so a `patches_db` path param can't shadow it

_WEBAPP = os.path.dirname(__file__)
DEFAULT_DERIVED = os.path.join(_WEBAPP, "derived_data.db")
DEFAULT_POOL = os.path.join(_WEBAPP, "pool_scores.db")
DEFAULT_CPU_JSON = os.path.join(_WEBAPP, "civ_power_units.json")
DEFAULT_CPU_DIR = os.path.join(_WEBAPP, "civ_power_units")
DEFAULT_PATCHES = os.path.join(_WEBAPP, "patches.db")


def _has_col(conn, table, col):
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def _rebuild_battle_scores(conn, build):
    if _has_col(conn, "battle_scores", "build_number"):
        return
    conn.executescript(f"""
        ALTER TABLE battle_scores RENAME TO battle_scores_old;
        CREATE TABLE battle_scores (
            id INTEGER PRIMARY KEY, line_slug TEXT NOT NULL, age TEXT NOT NULL,
            civ_name TEXT NOT NULL, unit_slug TEXT NOT NULL, score_type TEXT NOT NULL,
            score_value REAL NOT NULL, rank INTEGER, median_delta REAL,
            build_number TEXT NOT NULL DEFAULT '{build}',
            UNIQUE(line_slug, age, civ_name, unit_slug, score_type, build_number)
        );
        INSERT INTO battle_scores
          (line_slug, age, civ_name, unit_slug, score_type, score_value, rank,
           median_delta, build_number)
          SELECT line_slug, age, civ_name, unit_slug, score_type, score_value, rank,
                 median_delta, '{build}' FROM battle_scores_old;
        DROP TABLE battle_scores_old;
        CREATE INDEX IF NOT EXISTS idx_bs_line_age ON battle_scores(line_slug, age, build_number);
        CREATE INDEX IF NOT EXISTS idx_bs_civ_unit ON battle_scores(civ_name, unit_slug, age, build_number);
    """)
    conn.commit()


def _rebuild_pool_scores(conn, build):
    if _has_col(conn, "pool_scores", "build_number"):
        return
    conn.executescript(f"""
        ALTER TABLE pool_scores RENAME TO pool_scores_old;
        CREATE TABLE pool_scores (
            civ_name TEXT NOT NULL, unit_slug TEXT NOT NULL, pool TEXT NOT NULL,
            scale TEXT NOT NULL, axis TEXT NOT NULL, final_score REAL NOT NULL,
            gc REAL, ac REAL, at REAL, aa REAL, n INTEGER NOT NULL, mean REAL NOT NULL,
            stddev REAL NOT NULL, win_rate REAL NOT NULL, decisive_win_rate REAL NOT NULL,
            big_win_rate REAL NOT NULL, catastrophic_loss_rate REAL NOT NULL,
            sim_version TEXT, derived_at TEXT NOT NULL, role_line_means TEXT,
            build_number TEXT NOT NULL DEFAULT '{build}',
            PRIMARY KEY (civ_name, unit_slug, scale, axis, build_number)
        );
        INSERT INTO pool_scores
          SELECT civ_name, unit_slug, pool, scale, axis, final_score, gc, ac, at, aa,
                 n, mean, stddev, win_rate, decisive_win_rate, big_win_rate,
                 catastrophic_loss_rate, sim_version, derived_at, role_line_means,
                 '{build}' FROM pool_scores_old;
        DROP TABLE pool_scores_old;
        CREATE INDEX IF NOT EXISTS idx_pool_scores_pool_axis_scale
            ON pool_scores (pool, axis, scale, build_number);
    """)
    conn.commit()


def run(*, derived_db=DEFAULT_DERIVED, pool_db=DEFAULT_POOL,
        cpu_json=DEFAULT_CPU_JSON, cpu_dir=DEFAULT_CPU_DIR,
        patches_db=DEFAULT_PATCHES,
        baseline_build="170934", release_date=None, source_url=None,
        summary_md=None):
    # baseline_build is interpolated into the rebuild DDL via f-string, so it
    # must be a bare numeric build id (it always is — '170934', '177723').
    if not str(baseline_build).isdigit():
        raise ValueError(f"baseline_build must be a numeric build id, got {baseline_build!r}")
    if os.path.exists(derived_db):
        c = sqlite3.connect(derived_db)
        try:
            _rebuild_battle_scores(c, baseline_build)
        finally:
            c.close()
    if os.path.exists(pool_db):
        c = sqlite3.connect(pool_db)
        try:
            _rebuild_pool_scores(c, baseline_build)
        finally:
            c.close()

    os.makedirs(cpu_dir, exist_ok=True)
    dest = os.path.join(cpu_dir, f"{baseline_build}.json")
    if os.path.exists(cpu_json) and not os.path.exists(dest):
        shutil.copyfile(cpu_json, dest)

    pconn = _patches_db.create_db(patches_db)
    if _patches_db.patch_id_for(pconn, baseline_build) is None:
        _patches_db.insert_patch(pconn, build_number=baseline_build, release_date=release_date,
                                 title=f"Update {baseline_build}", summary_md=summary_md or "",
                                 source_url=source_url, baseline_build=None, is_current=1,
                                 created_at=release_date)
        _patches_db.set_current_build(pconn, baseline_build)
    pconn.commit(); pconn.close()
    print(f"Baseline migration complete (build {baseline_build}).")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--build", default="170934")
    p.add_argument("--release-date", default="2026-04-01")
    p.add_argument("--source-url", default="")
    p.add_argument("--summary", default="Baseline snapshot (pre-patch-tracking).")
    a = p.parse_args()
    run(baseline_build=a.build, release_date=a.release_date,
        source_url=a.source_url, summary_md=a.summary)


if __name__ == "__main__":
    main()
