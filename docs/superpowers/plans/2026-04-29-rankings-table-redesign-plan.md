# Rankings Table Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Unit Rankings page to a slim 8-column default view with progressive column-group expansion (per-role line breakdowns + raw stats), a Special column that surfaces missing techs, and an Expand All / Collapse All button.

**Architecture:** Backend persists per-line means as a JSON column on `pool_scores` and adds a `missing_techs` field to the `/api/ref/unit-line` payload. Frontend keeps a transient `expandedRoles` set, renders cells with a `col-expandable` class that animates `max-width` on collapse, and reuses the existing `sortBy()` for per-line column sorting via denormalized `role_line_<ROLE>_<line>` keys on enriched rows.

**Tech Stack:** Python 3, SQLite, Flask, vanilla JavaScript, vanilla CSS. Pytest for backend tests.

**Spec:** [`docs/superpowers/specs/2026-04-29-rankings-table-redesign-design.md`](../specs/2026-04-29-rankings-table-redesign-design.md)

---

## File Map

**Backend (Python):**
- Modify `webapp/pool_scores_db.py` — schema + insert SQL gain `role_line_means TEXT`.
- Modify `webapp/pool_scores_lib.py` — `derive_unit_scores()` emits `role_line_means` per output row.
- Modify `webapp/derive_pool_scores.py` — orchestrator runs `ALTER TABLE` migration if missing, JSON-encodes the field on insert.
- Modify `webapp/pool_scores_query.py` — `load_pool_scores()` decodes `role_line_means` JSON into payload.
- Modify `webapp/app.py` — `api_ref_unit_line` attaches `missing_techs` per unit row using existing `_compute_missing_techs` helper.

**Frontend (JS / CSS / HTML):**
- Modify `webapp/static/js/rankings.js` — slim column defs, expansion state, chevron handlers, per-line column rendering, missing-techs cell, expand-all wiring.
- Modify `webapp/static/css/rankings.css` — chevron styles, slide animation classes, missing-techs styles.
- Modify `webapp/templates/index.html` — Expand All button next to CSV export.

**Tests:**
- Modify `tests/test_pool_scores_db.py` — assert new column in schema test.
- Modify `tests/test_pool_scores_lib.py` — assert `role_line_means` shape in `derive_unit_scores` output.
- Modify `tests/test_pool_scores_integration.py` — pin Berserker per-line values.
- Modify `tests/test_pool_scores_api.py` — assert `role_line_means` and `missing_techs` in API response.

**Data file:**
- Modify `webapp/pool_scores.db` — re-derived after schema migration; committed (per existing Railway-deployment convention).

---

## Task 1: Schema gains `role_line_means` column

**Files:**
- Modify: `webapp/pool_scores_db.py:8-34` (SCHEMA constant) and `:45-59` (`_INSERT_SQL`)
- Test: `tests/test_pool_scores_db.py`

- [ ] **Step 1: Update schema test to require `role_line_means TEXT`**

Edit `tests/test_pool_scores_db.py` — extend the `expected` dict in `test_pool_scores_columns_match_spec`:

```python
def test_pool_scores_columns_match_spec(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1]: r[2] for r in cur.fetchall()}
    expected = {
        "civ_name": "TEXT", "unit_slug": "TEXT", "pool": "TEXT",
        "scale": "TEXT", "axis": "TEXT",
        "final_score": "REAL", "gc": "REAL", "ac": "REAL",
        "at": "REAL", "aa": "REAL",
        "n": "INTEGER", "mean": "REAL", "stddev": "REAL",
        "win_rate": "REAL", "decisive_win_rate": "REAL",
        "big_win_rate": "REAL", "catastrophic_loss_rate": "REAL",
        "sim_version": "TEXT", "derived_at": "TEXT",
        "role_line_means": "TEXT",
    }
    for col, ctype in expected.items():
        assert col in cols, f"missing column: {col}"
        assert cols[col] == ctype, f"{col}: expected {ctype}, got {cols[col]}"
    conn.close()
```

Add a new test for the insert path round-tripping a JSON value:

```python
def test_insert_writes_role_line_means_json(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 8.9, "gc": -6.8, "ac": -1.6, "at": 92.7, "aa": None,
        "n": 269, "mean": 35.2, "stddev": 59.5,
        "win_rate": 61.7, "decisive_win_rate": 53.4,
        "big_win_rate": 47.1, "catastrophic_loss_rate": 27.1,
        "sim_version": "v", "derived_at": "t",
        "role_line_means": '{"GC":{"militia":-10.2,"knight":-5.5,"archer":-4.6}}',
    })
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT role_line_means FROM pool_scores WHERE unit_slug='elite_berserk_vikings'")
    (got,) = cur.fetchone()
    assert got == '{"GC":{"militia":-10.2,"knight":-5.5,"archer":-4.6}}'
    conn.close()
```

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/test_pool_scores_db.py -v`
Expected: `test_pool_scores_columns_match_spec` FAIL ("missing column: role_line_means"); `test_insert_writes_role_line_means_json` FAIL (sqlite3 error: no such column).

- [ ] **Step 3: Add the column to the schema and INSERT statement**

Edit `webapp/pool_scores_db.py`. Replace the `SCHEMA` constant and `_INSERT_SQL`:

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS pool_scores (
    civ_name              TEXT NOT NULL,
    unit_slug             TEXT NOT NULL,
    pool                  TEXT NOT NULL,
    scale                 TEXT NOT NULL,
    axis                  TEXT NOT NULL,
    final_score           REAL NOT NULL,
    gc                    REAL,
    ac                    REAL,
    at                    REAL,
    aa                    REAL,
    n                     INTEGER NOT NULL,
    mean                  REAL NOT NULL,
    stddev                REAL NOT NULL,
    win_rate              REAL NOT NULL,
    decisive_win_rate     REAL NOT NULL,
    big_win_rate          REAL NOT NULL,
    catastrophic_loss_rate REAL NOT NULL,
    sim_version           TEXT,
    derived_at            TEXT NOT NULL,
    role_line_means       TEXT,
    PRIMARY KEY (civ_name, unit_slug, scale, axis)
);

CREATE INDEX IF NOT EXISTS idx_pool_scores_pool_axis_scale
    ON pool_scores (pool, axis, scale);
"""


_INSERT_SQL = """
INSERT OR REPLACE INTO pool_scores (
    civ_name, unit_slug, pool, scale, axis,
    final_score, gc, ac, at, aa,
    n, mean, stddev,
    win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
    sim_version, derived_at, role_line_means
) VALUES (
    :civ_name, :unit_slug, :pool, :scale, :axis,
    :final_score, :gc, :ac, :at, :aa,
    :n, :mean, :stddev,
    :win_rate, :decisive_win_rate, :big_win_rate, :catastrophic_loss_rate,
    :sim_version, :derived_at, :role_line_means
)
"""
```

The existing `insert_score` function passes `row` straight through; no code change there. Callers must include `role_line_means` in the dict (defaulting to `None` if absent — handled by named param).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pool_scores_db.py -v`
Expected: all four tests PASS, including the two existing ones (`test_create_db_has_pool_scores_table`, `test_insert_replaces_on_duplicate_key`).

The pre-existing `test_insert_and_read_back` and `test_insert_replaces_on_duplicate_key` will keep working because they don't pass `role_line_means` and SQLite will allow the missing named param to default to NULL via the explicit `:role_line_means` placeholder. **Wait** — sqlite3's named-parameter binding raises `ProgrammingError` if a placeholder is missing from the dict. Add `role_line_means: None` to those two tests' insert dicts:

```python
# test_insert_and_read_back: add to the insert_score(...) call:
"role_line_means": None,

# test_insert_replaces_on_duplicate_key: add to the payload dict:
"role_line_means": None,
```

Re-run: `pytest tests/test_pool_scores_db.py -v` → all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_db.py tests/test_pool_scores_db.py
git commit -m "feat(pool-scores): add role_line_means column to schema"
```

---

## Task 2: `derive_unit_scores` emits per-line means

**Files:**
- Modify: `webapp/pool_scores_lib.py:260-354` (`derive_unit_scores`)
- Test: `tests/test_pool_scores_lib.py`

- [ ] **Step 1: Write failing tests for `role_line_means` in output**

Append to `tests/test_pool_scores_lib.py`:

```python
import pytest
from pool_scores_lib import derive_unit_scores


def _row(opp_slug, winner=1, t1=0.5, t2=0.0, dedup="g"):
    """Synthetic matchup_battles row helper. Costs equal to keep cost-axis simple."""
    return {
        "opp_unit_slug": opp_slug, "winner": winner,
        "team1_hp_pct": t1, "team2_hp_pct": t2,
        "my_count": 30, "my_cost_food": 60, "my_cost_wood": 0, "my_cost_gold": 20,
        "opp_count": 30, "opp_cost_food": 60, "opp_cost_wood": 0, "opp_cost_gold": 20,
        "game_time_s": 60.0, "dedup_group": dedup,
    }


def test_role_line_means_present_per_axis():
    # Champion (infantry pool) vs three opponents — one per GC line.
    rows = [
        _row("champion", winner=1, t1=0.7, t2=0.0, dedup="m"),    # vs militia
        _row("paladin",  winner=2, t1=0.0, t2=0.8, dedup="k"),    # vs knight
        _row("arbalester", winner=1, t1=0.5, t2=0.0, dedup="a"),  # vs archer
    ]
    out = derive_unit_scores(
        civ="Vikings", unit_slug="champion", scale="30v30", rows=rows,
    )
    assert len(out) == 3  # hp, cost, speed
    for axis_row in out:
        assert "role_line_means" in axis_row
        rlm = axis_row["role_line_means"]
        assert "GC" in rlm
        assert set(rlm["GC"].keys()) == {"militia", "knight", "archer"}
        # AC and AT should also be present because POOL_ROLES["infantry"] includes them.
        assert "AC" in rlm
        assert "AT" in rlm


def test_role_line_means_hp_values_for_champion():
    rows = [
        _row("champion",  winner=1, t1=0.7, t2=0.0, dedup="m"),  # raw hp_score = +70
        _row("paladin",   winner=2, t1=0.0, t2=0.8, dedup="k"),  # raw hp_score = -80 -> adj -160
        _row("arbalester", winner=1, t1=0.5, t2=0.0, dedup="a"), # raw hp_score = +50
    ]
    out = derive_unit_scores(
        civ="Vikings", unit_slug="champion", scale="30v30", rows=rows,
    )
    hp = next(r for r in out if r["axis"] == "hp")
    rlm = hp["role_line_means"]
    assert rlm["GC"]["militia"] == pytest.approx(70.0)
    assert rlm["GC"]["knight"]  == pytest.approx(-160.0)
    assert rlm["GC"]["archer"]  == pytest.approx(50.0)


def test_role_line_means_lines_with_no_data_are_null():
    # Champion vs militia only — knight and archer lines for GC have no data.
    rows = [_row("champion", winner=1, t1=0.6, t2=0.0, dedup="m")]
    out = derive_unit_scores(
        civ="Vikings", unit_slug="champion", scale="30v30", rows=rows,
    )
    hp = next(r for r in out if r["axis"] == "hp")
    rlm = hp["role_line_means"]
    assert rlm["GC"]["militia"] == pytest.approx(60.0)
    assert rlm["GC"]["knight"]  is None
    assert rlm["GC"]["archer"]  is None


def test_knight_appears_in_both_gc_and_ac_per_line_means():
    """Spec: knight is in both GC and AC lists for infantry pool."""
    rows = [_row("paladin", winner=2, t1=0.0, t2=1.0, dedup="k")]  # raw -100 -> adj -200
    out = derive_unit_scores(
        civ="Vikings", unit_slug="champion", scale="30v30", rows=rows,
    )
    hp = next(r for r in out if r["axis"] == "hp")
    rlm = hp["role_line_means"]
    assert rlm["GC"]["knight"] == pytest.approx(-200.0)
    assert rlm["AC"]["knight"] == pytest.approx(-200.0)
```

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/test_pool_scores_lib.py -v -k role_line_means`
Expected: 4 FAILs with `KeyError: 'role_line_means'` or `assert "role_line_means" in axis_row`.

- [ ] **Step 3: Thread per-line means through `derive_unit_scores`**

Edit `webapp/pool_scores_lib.py`. Replace the body of `derive_unit_scores()` (currently lines 260–354). The change is in the per-axis loop — compute and stash `role_line_means` alongside `role_means`:

```python
def derive_unit_scores(*, civ: str, unit_slug: str, scale: str,
                       rows: list,
                       sim_version=None) -> list:
    """Derive 3 output rows (one per axis) for one (civ, unit, scale).

    `rows` is the list of matchup_battles rows for this unit at this
    scale. Each row must have the keys used by `_row()` in the tests.
    Returns an empty list if the unit's pool can't be determined
    (e.g. siege/naval/monk, out of scope for this stage).

    Each opponent's line is bucketed into ALL matching roles — a line may
    appear in more than one role (e.g. knight counts in both GC and AC for
    the infantry pool, producing the ~0.27 effective weight described in
    the spec).
    """
    pool = unit_to_pool(UNIT_LINES, unit_slug)
    if pool is None:
        return []

    role_def = POOL_ROLES[pool]
    # Bucket: (line_key, role) -> axis -> {dedup_group: value}
    line_axis_values: dict = defaultdict(lambda: {"hp": {}, "cost": {}, "speed": {}})
    raw_hp_by_dedup: dict = {}

    for r in rows:
        opp_slug = r["opp_unit_slug"]
        opp_line_keys = _opponent_lines(opp_slug)
        if not opp_line_keys:
            continue

        my_total = r["my_count"] * weighted_cost(
            r["my_cost_food"], r["my_cost_wood"], r["my_cost_gold"])
        opp_total = r["opp_count"] * weighted_cost(
            r["opp_cost_food"], r["opp_cost_wood"], r["opp_cost_gold"])
        raw_hp = hp_score(r["team1_hp_pct"], r["team2_hp_pct"], r["winner"])
        adj_hp = apply_loss_aversion(raw_hp)
        cost = cost_score(r["team1_hp_pct"], r["team2_hp_pct"], r["winner"],
                          my_total, opp_total)
        speed = speed_score(r["winner"], r["game_time_s"])

        dedup = r["dedup_group"]
        raw_hp_by_dedup.setdefault(dedup, raw_hp)

        for line_key in opp_line_keys:
            for role, lines in role_def.items():
                if line_key in lines:
                    line_axis_values[(line_key, role)]["hp"].setdefault(dedup, adj_hp)
                    line_axis_values[(line_key, role)]["cost"].setdefault(dedup, cost)
                    line_axis_values[(line_key, role)]["speed"].setdefault(dedup, speed)

    shape = compute_shape(raw_hp_by_dedup.values())

    derived_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out_rows = []
    for axis in ("hp", "cost", "speed"):
        # Per-line mean → per-role mean across lines that had data.
        role_means: dict = {}
        # Per-line means per role: every line in POOL_ROLES[pool][role] gets a key,
        # value is None if no data, else the mean of dedup-survivors.
        role_line_means: dict = {}
        for role, lines in role_def.items():
            line_vals = []
            per_line_for_role: dict = {}
            for line in lines:
                vals = line_axis_values.get((line, role), {}).get(axis, {})
                if vals:
                    mean_v = sum(vals.values()) / len(vals)
                    line_vals.append(mean_v)
                    per_line_for_role[line] = mean_v
                else:
                    per_line_for_role[line] = None
            role_means[role] = sum(line_vals) / len(line_vals) if line_vals else 0.0
            role_line_means[role] = per_line_for_role

        final = final_score_for_pool(role_means, pool)
        weights = POOL_WEIGHTS[pool]

        out_rows.append({
            "civ_name": civ, "unit_slug": unit_slug,
            "pool": pool, "scale": scale, "axis": axis,
            "final_score": final,
            "gc": role_means.get("GC", 0.0) if "GC" in weights else None,
            "ac": role_means.get("AC", 0.0) if "AC" in weights else None,
            "at": role_means.get("AT", 0.0) if "AT" in weights else None,
            "aa": role_means.get("AA", 0.0) if "AA" in weights else None,
            "n": shape["n"], "mean": shape["mean"], "stddev": shape["stddev"],
            "win_rate": shape["win_rate"],
            "decisive_win_rate": shape["decisive_win_rate"],
            "big_win_rate": shape["big_win_rate"],
            "catastrophic_loss_rate": shape["catastrophic_loss_rate"],
            "sim_version": sim_version, "derived_at": derived_at,
            "role_line_means": role_line_means,
        })
    return out_rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all tests PASS, including the 4 new `role_line_means` tests.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): emit per-line means from derive_unit_scores"
```

---

## Task 3: Orchestrator JSON-encodes & runs migration

**Files:**
- Modify: `webapp/derive_pool_scores.py:1-118`

The orchestrator must (a) JSON-encode the dict for the new column, and (b) tolerate an existing `pool_scores.db` lacking the column by running an `ALTER TABLE` once.

- [ ] **Step 1: Add an integration test for the orchestrator**

Append to `tests/test_pool_scores_db.py`:

```python
import json
import sqlite3
from derive_pool_scores import main as derive_main


def test_orchestrator_writes_json_role_line_means(tmp_path):
    """End-to-end: derive on a tiny synthetic matchup DB and verify the JSON column."""
    matchup_path = tmp_path / "matchup.db"
    out_path = tmp_path / "pool.db"

    # Build a minimal matchup_battles fixture: one champion vs one paladin row.
    mc = sqlite3.connect(matchup_path)
    mc.executescript("""
        CREATE TABLE matchup_battles (
            my_civ TEXT, my_unit_slug TEXT, opp_unit_slug TEXT,
            scale TEXT, winner INTEGER,
            team1_hp_pct REAL, team2_hp_pct REAL,
            my_count INTEGER, my_cost_food REAL, my_cost_wood REAL, my_cost_gold REAL,
            opp_count INTEGER, opp_cost_food REAL, opp_cost_wood REAL, opp_cost_gold REAL,
            game_time_s REAL, dedup_group TEXT, sim_version TEXT
        );
    """)
    mc.execute("""
        INSERT INTO matchup_battles VALUES
        ('Vikings','champion','paladin','30v30',2,0.0,0.5,30,60,0,20,30,60,0,80,40.0,'g1','vTEST')
    """)
    mc.commit()
    mc.close()

    rc = derive_main(["--matchup-db", str(matchup_path), "--out", str(out_path)])
    assert rc == 0

    conn = sqlite3.connect(out_path)
    cur = conn.execute(
        "SELECT axis, role_line_means FROM pool_scores WHERE unit_slug='champion' AND scale='30v30'"
    )
    rows = dict(cur.fetchall())
    conn.close()

    assert "hp" in rows
    rlm = json.loads(rows["hp"])
    # GC has militia/knight/archer; only knight got data.
    assert rlm["GC"]["knight"] is not None
    assert rlm["GC"]["militia"] is None
    assert rlm["GC"]["archer"] is None


def test_orchestrator_migrates_existing_db_without_column(tmp_path):
    """Old pool_scores.db (no role_line_means column) gets ALTER TABLE on next run."""
    out_path = tmp_path / "pool.db"

    # Create an OLD schema (no role_line_means).
    legacy = sqlite3.connect(out_path)
    legacy.executescript("""
        CREATE TABLE pool_scores (
            civ_name TEXT, unit_slug TEXT, pool TEXT, scale TEXT, axis TEXT,
            final_score REAL, gc REAL, ac REAL, at REAL, aa REAL,
            n INTEGER, mean REAL, stddev REAL,
            win_rate REAL, decisive_win_rate REAL, big_win_rate REAL,
            catastrophic_loss_rate REAL,
            sim_version TEXT, derived_at TEXT,
            PRIMARY KEY (civ_name, unit_slug, scale, axis)
        );
    """)
    legacy.commit()
    legacy.close()

    # Empty matchup DB so derive does no real work but still opens the out DB.
    matchup_path = tmp_path / "matchup.db"
    mc = sqlite3.connect(matchup_path)
    mc.executescript("""
        CREATE TABLE matchup_battles (
            my_civ TEXT, my_unit_slug TEXT, opp_unit_slug TEXT,
            scale TEXT, winner INTEGER,
            team1_hp_pct REAL, team2_hp_pct REAL,
            my_count INTEGER, my_cost_food REAL, my_cost_wood REAL, my_cost_gold REAL,
            opp_count INTEGER, opp_cost_food REAL, opp_cost_wood REAL, opp_cost_gold REAL,
            game_time_s REAL, dedup_group TEXT, sim_version TEXT
        );
    """)
    mc.commit()
    mc.close()

    derive_main(["--matchup-db", str(matchup_path), "--out", str(out_path)])

    conn = sqlite3.connect(out_path)
    cur = conn.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1] for r in cur.fetchall()}
    conn.close()
    assert "role_line_means" in cols
```

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/test_pool_scores_db.py -v -k orchestrator`
Expected: 2 FAILs (`role_line_means` is a dict in the row, but `_INSERT_SQL` expects it as a string; migration test fails because legacy DB lacks the column and there's no ALTER).

- [ ] **Step 3: JSON-encode in orchestrator + add migration**

Edit `webapp/derive_pool_scores.py`. Replace the file with:

```python
"""Derive pool scores for every (civ, unit_slug, scale) in matchup_db.

Run from the webapp/ directory (matches the project's existing
script-running convention — see CLAUDE.md):

    cd webapp && python derive_pool_scores.py

Or with explicit paths:

    cd webapp && python derive_pool_scores.py \\
        --matchup-db matchup_db.db --out pool_scores.db

For each combat unit in the three pools (infantry/stable/archer), writes
six rows to pool_scores.db: 3 axes (hp, cost, speed) × 2 scales (30v30, 3k).
Units outside those pools (siege, naval, monks) are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict

from pool_scores_lib import derive_unit_scores, unit_to_pool
from pool_scores_db import create_db, insert_score
from unit_lines import UNIT_LINES

_WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MATCHUP_DB = os.path.join(_WEBAPP_DIR, "matchup_db.db")
DEFAULT_OUT_DB = os.path.join(_WEBAPP_DIR, "pool_scores.db")

ROW_KEYS = (
    "opp_unit_slug", "winner", "team1_hp_pct", "team2_hp_pct",
    "my_count", "my_cost_food", "my_cost_wood", "my_cost_gold",
    "opp_count", "opp_cost_food", "opp_cost_wood", "opp_cost_gold",
    "game_time_s", "dedup_group",
)


def _fetch_unit_rows(matchup_conn: sqlite3.Connection,
                     civ: str, unit_slug: str, scale: str) -> list[dict]:
    cur = matchup_conn.cursor()
    cur.execute(f"""
        SELECT {", ".join(ROW_KEYS)}
        FROM matchup_battles
        WHERE my_civ = ? AND my_unit_slug = ? AND scale = ?
    """, (civ, unit_slug, scale))
    return [dict(zip(ROW_KEYS, r)) for r in cur.fetchall()]


def _list_unit_pairs(matchup_conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """All (civ, unit_slug) pairs that have at least one battle row."""
    cur = matchup_conn.cursor()
    cur.execute("""
        SELECT DISTINCT my_civ, my_unit_slug
        FROM matchup_battles
        ORDER BY my_civ, my_unit_slug
    """)
    return [(r[0], r[1]) for r in cur.fetchall()]


def _sim_version_for(matchup_conn: sqlite3.Connection,
                     civ: str, unit_slug: str) -> str | None:
    cur = matchup_conn.cursor()
    cur.execute("""
        SELECT sim_version FROM matchup_battles
        WHERE my_civ = ? AND my_unit_slug = ?
        LIMIT 1
    """, (civ, unit_slug))
    row = cur.fetchone()
    return row[0] if row else None


def _migrate_role_line_means_column(conn: sqlite3.Connection) -> None:
    """Add role_line_means column to legacy DBs that pre-date this column.

    Idempotent: PRAGMA table_info reports current columns; only ALTER if missing.
    """
    cur = conn.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1] for r in cur.fetchall()}
    if "role_line_means" not in cols:
        conn.execute("ALTER TABLE pool_scores ADD COLUMN role_line_means TEXT")
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--matchup-db", default=DEFAULT_MATCHUP_DB)
    p.add_argument("--out", default=DEFAULT_OUT_DB)
    args = p.parse_args(argv)

    matchup_conn = sqlite3.connect(args.matchup_db)
    out_conn = create_db(args.out)
    _migrate_role_line_means_column(out_conn)

    pairs = _list_unit_pairs(matchup_conn)
    written = 0
    skipped_no_pool = 0
    by_pool: dict[str, int] = defaultdict(int)

    for civ, unit_slug in pairs:
        if unit_to_pool(UNIT_LINES, unit_slug) is None:
            skipped_no_pool += 1
            continue
        sim_version = _sim_version_for(matchup_conn, civ, unit_slug)
        for scale in ("30v30", "3k"):
            rows = _fetch_unit_rows(matchup_conn, civ, unit_slug, scale)
            if not rows:
                continue
            out_rows = derive_unit_scores(
                civ=civ, unit_slug=unit_slug, scale=scale, rows=rows,
                sim_version=sim_version,
            )
            for row in out_rows:
                # JSON-encode the per-line breakdown for the TEXT column.
                rlm = row.get("role_line_means")
                row["role_line_means"] = json.dumps(rlm) if rlm is not None else None
                insert_score(out_conn, row)
                written += 1
                by_pool[row["pool"]] += 1
        out_conn.commit()

    matchup_conn.close()
    out_conn.close()

    print(f"Wrote {written} rows to {args.out}")
    print(f"  by pool: {dict(by_pool)}")
    print(f"  skipped (no pool): {skipped_no_pool} (civ, unit) pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pool_scores_db.py -v`
Expected: all tests PASS, including the two new orchestrator tests.

- [ ] **Step 5: Commit**

```bash
git add webapp/derive_pool_scores.py tests/test_pool_scores_db.py
git commit -m "feat(pool-scores): orchestrator JSON-encodes role_line_means + migrates legacy DBs"
```

---

## Task 4: `load_pool_scores` decodes per-line means

**Files:**
- Modify: `webapp/pool_scores_query.py`

- [ ] **Step 1: Update `test_pool_scores_query.py` to require `role_line_means` in payload**

Open `tests/test_pool_scores_query.py`. Add this test (assumes the existing tests use `tmp_path`-built DBs):

```python
import json
from pool_scores_db import create_db, insert_score
from pool_scores_query import load_pool_scores


def test_load_decodes_role_line_means(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 8.9, "gc": -6.8, "ac": -1.6, "at": 92.7, "aa": None,
        "n": 269, "mean": 35.2, "stddev": 59.5,
        "win_rate": 61.7, "decisive_win_rate": 53.4,
        "big_win_rate": 47.1, "catastrophic_loss_rate": 27.1,
        "sim_version": "v", "derived_at": "t",
        "role_line_means": json.dumps({
            "GC": {"militia": -10.2, "knight": -5.5, "archer": -4.6},
            "AC": {"knight": -2.1, "camel": 0.0, "steppe_lancer": None, "elephant": -2.8},
            "AT": {"spear": 92.7, "skirmisher": 91.4, "light_cav": 94.0},
        }),
    })
    conn.commit()
    conn.close()

    payload = load_pool_scores(str(db_path), [("Vikings", "elite_berserk_vikings")])
    unit = payload[("Vikings", "elite_berserk_vikings")]
    hp = unit["scales"]["30v30"]["hp"]
    assert "role_line_means" in hp
    assert hp["role_line_means"]["GC"]["militia"] == pytest.approx(-10.2)
    assert hp["role_line_means"]["AC"]["steppe_lancer"] is None


def test_load_missing_role_line_means_yields_empty_dict(tmp_path):
    """Old rows where role_line_means is NULL should still load (return {})."""
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "champion",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 0, "gc": 0, "ac": 0, "at": 0, "aa": None,
        "n": 1, "mean": 0, "stddev": 0,
        "win_rate": 0, "decisive_win_rate": 0,
        "big_win_rate": 0, "catastrophic_loss_rate": 0,
        "sim_version": "v", "derived_at": "t",
        "role_line_means": None,
    })
    conn.commit()
    conn.close()

    payload = load_pool_scores(str(db_path), [("Vikings", "champion")])
    hp = payload[("Vikings", "champion")]["scales"]["30v30"]["hp"]
    assert hp["role_line_means"] == {}
```

Add `import pytest` at the top of the test file if it's not already there.

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/test_pool_scores_query.py -v -k role_line_means`
Expected: 2 FAILs with `KeyError: 'role_line_means'`.

- [ ] **Step 3: Decode JSON in `load_pool_scores`**

Edit `webapp/pool_scores_query.py`. Replace the file:

```python
"""Query helper for pool_scores.db.

Loads structured per-unit payloads keyed by (civ_name, unit_slug).
Used by the /api/ref/unit-line endpoint to attach pool-scores data
to each unit row in the rankings view.
"""
import json
import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "pool_scores.db")

_SHAPE_KEYS = ("n", "mean", "stddev", "win_rate", "decisive_win_rate",
               "big_win_rate", "catastrophic_loss_rate")
_ROLE_KEYS = ("gc", "ac", "at", "aa")


def load_pool_scores(db_path: str,
                     civ_unit_pairs: list[tuple[str, str]]) -> dict:
    """Return {(civ_name, unit_slug): payload, ...} for known units.

    Each scale's per-axis dict gains a `role_line_means` key with the
    decoded JSON breakdown (`{}` when the DB column is NULL).

    Units not present in pool_scores.db are simply absent from the result.
    Empty input → empty dict. Missing DB file → empty dict.
    """
    if not civ_unit_pairs or not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ", ".join("(?, ?)" for _ in civ_unit_pairs)
        params: list[str] = []
        for civ, slug in civ_unit_pairs:
            params.extend((civ, slug))
        cur = conn.execute(f"""
            SELECT civ_name, unit_slug, pool, scale, axis,
                   final_score, gc, ac, at, aa,
                   n, mean, stddev,
                   win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
                   role_line_means
            FROM pool_scores
            WHERE (civ_name, unit_slug) IN ({placeholders})
        """, params)
        rows = cur.fetchall()
    finally:
        conn.close()

    result: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["civ_name"], row["unit_slug"])
        unit_payload = result.setdefault(key, {
            "pool": row["pool"],
            "scales": {},
        })
        scale_payload = unit_payload["scales"].setdefault(row["scale"], {
            "hp": None, "cost": None, "speed": None, "shape": None,
        })
        rlm_raw = row["role_line_means"]
        rlm = json.loads(rlm_raw) if rlm_raw else {}
        scale_payload[row["axis"]] = {
            "final": row["final_score"],
            **{k: row[k] for k in _ROLE_KEYS},
            "role_line_means": rlm,
        }
        if scale_payload["shape"] is None:
            scale_payload["shape"] = {k: row[k] for k in _SHAPE_KEYS}

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pool_scores_query.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_query.py tests/test_pool_scores_query.py
git commit -m "feat(pool-scores): decode role_line_means in load_pool_scores"
```

---

## Task 5: Re-derive `pool_scores.db` and pin Berserker per-line values

**Files:**
- Modify: `webapp/pool_scores.db` (regenerate + commit)
- Modify: `tests/test_pool_scores_integration.py`

- [ ] **Step 1: Re-derive the database**

Run from project root:
```bash
cd webapp && python derive_pool_scores.py && cd ..
```

Expected output: `Wrote 2766 rows to .../pool_scores.db` (or whatever the current pool_scores total is — match it to the prior re-derivation log). The migration step is a no-op for the existing DB (column added back in Task 1's schema), or re-applies via the orchestrator's `_migrate_role_line_means_column` call.

- [ ] **Step 2: Verify the column populated for Berserker**

Run:
```bash
sqlite3 webapp/pool_scores.db "SELECT axis, json_extract(role_line_means, '$.GC.militia') AS gc_militia, json_extract(role_line_means, '$.GC.knight') AS gc_knight, json_extract(role_line_means, '$.GC.archer') AS gc_archer FROM pool_scores WHERE civ_name='Vikings' AND unit_slug='elite_berserk_vikings' AND scale='30v30'"
```

Expected: 3 rows (hp, cost, speed) each with non-null per-line values for GC.

Capture the actual `gc_militia / gc_knight / gc_archer` HP-axis values from this query — they are the pinned reference numbers for Step 3.

- [ ] **Step 3: Add a Berserker per-line regression test**

Append to `tests/test_pool_scores_integration.py`:

```python
def test_berserker_pop_hp_per_line_means(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    rlm = hp["role_line_means"]
    # GC has militia/knight/archer.
    assert "GC" in rlm and set(rlm["GC"].keys()) == {"militia", "knight", "archer"}
    # AC has knight/camel/steppe_lancer/elephant.
    assert set(rlm["AC"].keys()) == {"knight", "camel", "steppe_lancer", "elephant"}
    # AT has spear/skirmisher/light_cav.
    assert set(rlm["AT"].keys()) == {"spear", "skirmisher", "light_cav"}
    # All values either float or None.
    for role_dict in rlm.values():
        for v in role_dict.values():
            assert v is None or isinstance(v, (int, float))


def test_berserker_pop_hp_per_line_means_pinned(berserker_rows_30v30):
    """Pin the actual GC-line values for the 30v30 HP axis as a regression guardrail.

    Replace the `expected_*` numbers with the values printed by the
    sqlite3 query in Task 5 / Step 2 before committing.
    """
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    gc = hp["role_line_means"]["GC"]
    # PIN: copy values from sqlite query (Task 5 Step 2). Tolerance 0.5.
    expected_militia = ...   # fill from the query
    expected_knight  = ...
    expected_archer  = ...
    assert gc["militia"] == pytest.approx(expected_militia, abs=0.5)
    assert gc["knight"]  == pytest.approx(expected_knight,  abs=0.5)
    assert gc["archer"]  == pytest.approx(expected_archer,  abs=0.5)
```

After running Step 2's sqlite query, replace the three `...` placeholders with the actual values. (This is the only step in this plan that requires a value derived at runtime — it's unavoidable because the live values depend on whichever sim version produced `matchup_db.db`.)

- [ ] **Step 4: Run integration tests**

Run: `pytest tests/test_pool_scores_integration.py -v`
Expected: existing 7 tests PASS + 2 new ones PASS.

- [ ] **Step 5: Commit DB and tests**

```bash
git add webapp/pool_scores.db tests/test_pool_scores_integration.py
git commit -m "data(pool-scores): re-derive with role_line_means + pin Berserker per-line values"
```

---

## Task 6: API attaches `missing_techs` per unit row

**Files:**
- Modify: `webapp/app.py:665-682` (`_attach_special` and surrounding helpers in `api_ref_unit_line`)
- Test: `tests/test_pool_scores_api.py`

- [ ] **Step 1: Write failing API tests for `missing_techs` and `role_line_means`**

Append to `tests/test_pool_scores_api.py`:

```python
def test_unit_row_includes_missing_techs(client):
    resp = client.get("/api/ref/unit-line/militia")
    assert resp.status_code == 200
    data = resp.get_json()
    # Find any non-Goth row — Goths get all militia techs so they'd test
    # the empty case; pick a civ that's known to lack at least one tech.
    aztec_champ = _find(data["imperial"], "Aztecs", "champion")
    assert aztec_champ is not None
    assert "missing_techs" in aztec_champ
    assert isinstance(aztec_champ["missing_techs"], list)


def test_unit_row_includes_role_line_means(client):
    resp = client.get("/api/ref/unit-line/militia")
    data = resp.get_json()
    berserker = _find(data["imperial"], "Vikings", "elite_berserk_vikings")
    pop_hp = berserker["pool_scores"]["scales"]["30v30"]["hp"]
    assert "role_line_means" in pop_hp
    rlm = pop_hp["role_line_means"]
    assert "GC" in rlm and set(rlm["GC"].keys()) == {"militia", "knight", "archer"}
    assert "AC" in rlm
    assert "AT" in rlm
```

- [ ] **Step 2: Run tests to verify failures**

Run: `pytest tests/test_pool_scores_api.py -v -k "missing_techs or role_line_means"`
Expected: `test_unit_row_includes_missing_techs` FAILs (`'missing_techs' not in aztec_champ`); `test_unit_row_includes_role_line_means` FAILs (`'role_line_means' not in pop_hp`) — wait, Task 4 already populated `role_line_means` in the load helper, so this one may already PASS. If it does, that's fine; the test still asserts the contract.

- [ ] **Step 3: Attach `missing_techs` in `_attach_special`**

Edit `webapp/app.py` near line 665. The existing `_attach_special` runs a single SQL query against `ref_special_effects`. We extend it to also pull techs and call `_compute_missing_techs`.

First, add import near the top of `app.py` (find the existing import block around line 1-15):

```python
from best_units import (
    _compute_missing_techs as compute_missing_techs,
    _parse_techs_and_bonuses as parse_techs_and_bonuses,
)
```

Then before the `for sub_slug in sub_lines:` loop in `api_ref_unit_line` (around line 685, after `_attach_special` is defined and after the score helpers), build a per-slug "reference techs" map: the union of techs any civ has applied to each slug. We need this once per response so multiple units share the lookup.

Insert this block right after the `_ABILITY_LABELS` constant and before `_attach_special` (around line 663):

```python
# Build reference tech sets per unit_slug across all civs in scope.
# For each slug, the set of standard techs that ANY civ has applied.
# Used for missing-techs computation — a civ "missing" a tech is one in
# this reference set that they don't have applied.
_reference_techs_by_slug: dict[str, set[str]] = {}
_per_slug_civ_techs: dict[tuple[str, str], list[tuple[str, str]]] = {}
rc.execute("""
    SELECT ru.civ_name, ru.unit_slug, rta.tech_name, rta.tech_type
      FROM ref_units ru
      JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
""")
for r in rc.fetchall():
    _per_slug_civ_techs.setdefault((r["civ_name"], r["unit_slug"]), []).append(
        (r["tech_name"], r["tech_type"])
    )
# Build reference set per slug from all civ contributions.
_per_slug_effects: dict[tuple[str, str], list[tuple[str, str]]] = {}
rc.execute("""
    SELECT ru.civ_name, ru.unit_slug, rse.property_name, rse.property_value
      FROM ref_units ru
      JOIN ref_special_effects rse ON rse.ref_unit_id = ru.id
""")
for r in rc.fetchall():
    _per_slug_effects.setdefault((r["civ_name"], r["unit_slug"]), []).append(
        (r["property_name"], r["property_value"])
    )
for (civ, slug), techs in _per_slug_civ_techs.items():
    standard_techs, _bonus, _eff = parse_techs_and_bonuses(techs, [])
    _reference_techs_by_slug.setdefault(slug, set()).update(standard_techs)
```

Then modify `_attach_special` to compute and attach `missing_techs`:

```python
def _attach_special(entry):
    rc.execute(
        "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
        (entry["id"],),
    )
    parts = []
    for pname, pval in rc.fetchall():
        label = _ABILITY_LABELS.get(pname)
        if label is None:
            continue
        try:
            v = float(pval)
        except (ValueError, TypeError):
            continue
        if v == 0:
            continue
        parts.append(label.format(v=v))
    entry["special_abilities"] = "; ".join(parts) if parts else ""

    # Missing techs: this civ's standard techs vs the per-slug reference.
    civ_techs = _per_slug_civ_techs.get((entry["civ_name"], entry["unit_slug"]), [])
    standard_techs, _bonus, _eff = parse_techs_and_bonuses(civ_techs, [])
    reference = _reference_techs_by_slug.get(entry["unit_slug"], set())
    entry["missing_techs"] = compute_missing_techs(standard_techs, reference, entry["unit_slug"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pool_scores_api.py -v`
Expected: all tests PASS, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_pool_scores_api.py
git commit -m "feat(pool-scores-api): attach missing_techs and role_line_means to unit rows"
```

---

## Task 7: Frontend slim default columns

**Files:**
- Modify: `webapp/static/js/rankings.js:1289-1437` (column definitions)

This task removes excess columns from the default view. Per-line columns and Special-expansion columns are added in later tasks.

- [ ] **Step 1: Replace the `infantryColumns`, `archeryColumns`, and `stableColumns` arrays**

In `rankings.js`, replace the three arrays with the slim layout. The siege and naval arrays are unchanged.

```js
const infantryColumns = [
    { key: "civ_name", label: "Civ" },
    { key: "unit_name", label: "Unit" },
    ...(currentLine === "infantry"
        ? [{ key: "line_slug", label: "Line" }]
        : []),
    {
        key: "pool_score",
        label: scoreColumnLabel(currentScoreAxis, currentScoreScale),
        info: scoreColumnInfo(currentScoreAxis, currentScoreScale),
    },
    {
        key: "pool_gc",
        label: "GC",
        info: roleColumnInfo("GC", "infantry"),
        expandable: "GC",
    },
    {
        key: "pool_ac",
        label: "AC",
        info: roleColumnInfo("AC", "infantry"),
        expandable: "AC",
    },
    {
        key: "pool_at",
        label: "AT",
        info: roleColumnInfo("AT", "infantry"),
        expandable: "AT",
    },
    { key: "special_abilities", label: "Special", expandable: "Special" },
];
const archeryColumns = [
    { key: "civ_name", label: "Civ" },
    { key: "unit_name", label: "Unit" },
    ...(currentLine === "archery"
        ? [{ key: "line_slug", label: "Line" }]
        : []),
    {
        key: "pool_score",
        label: scoreColumnLabel(currentScoreAxis, currentScoreScale),
        info: scoreColumnInfo(currentScoreAxis, currentScoreScale),
    },
    {
        key: "pool_gc",
        label: "GC",
        info: roleColumnInfo("GC", "archery"),
        expandable: "GC",
    },
    {
        key: "pool_aa",
        label: "AA",
        info: roleColumnInfo("AA", "archery"),
        expandable: "AA",
    },
    { key: "special_abilities", label: "Special", expandable: "Special" },
];
const stableColumns = [
    { key: "civ_name", label: "Civ" },
    { key: "unit_name", label: "Unit" },
    { key: "line_slug", label: "Line" },
    {
        key: "pool_score",
        label: scoreColumnLabel(currentScoreAxis, currentScoreScale),
        info: scoreColumnInfo(currentScoreAxis, currentScoreScale),
    },
    {
        key: "pool_gc",
        label: "GC",
        info: roleColumnInfo("GC", "stable"),
        expandable: "GC",
    },
    {
        key: "pool_ac",
        label: "AC",
        info: roleColumnInfo("AC", "stable"),
        expandable: "AC",
    },
    { key: "special_abilities", label: "Special", expandable: "Special" },
];
```

The `expandable` property tags which group a column belongs to. Cells without it are always visible.

- [ ] **Step 2: Manually verify the slim view renders**

Run: `PORT=5002 python3 webapp/app.py` and open `http://localhost:5002/`. Switch to Infantry tab. Expected columns: `Civ | Unit | Line | HP | GC | AC | AT | Special` (8). Same check on Archer (7 cols, no AT) and Stable (7 cols, no AT). Siege/Naval unchanged.

- [ ] **Step 3: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat(rankings-table): slim default column layout for pool tabs"
```

---

## Task 8: Frontend expansion state + chevron headers

**Files:**
- Modify: `webapp/static/js/rankings.js:60-70` (state) and `:1465-1480` (header rendering)

- [ ] **Step 1: Add expansion state and helpers**

In `rankings.js`, near the state declarations (around line 70 after `currentScoreScale`), add:

```js
// Per-group expansion state — fully transient, resets on page load.
// Groups are: "GC", "AC", "AT", "AA", "Special".
const expandedGroups = new Set();

function toggleGroup(group) {
    if (expandedGroups.has(group)) expandedGroups.delete(group);
    else expandedGroups.add(group);
    renderTable();
}

function expandAll() {
    expandedGroups.add("GC");
    expandedGroups.add("AC");
    expandedGroups.add("AT");
    expandedGroups.add("AA");
    expandedGroups.add("Special");
    renderTable();
}

function collapseAll() {
    expandedGroups.clear();
    renderTable();
}

function isExpanded(group) {
    return expandedGroups.has(group);
}
```

- [ ] **Step 2: Render chevrons in expandable headers**

In `rankings.js`, find the header-rendering loop (around line 1465 — `for (const col of columns)`). Replace it with:

```js
html += '<table class="stats-table"><thead><tr>';
for (const col of columns) {
    const isSorted = sortColumn === col.key;
    const arrow = isSorted
        ? sortDir === "asc" ? "▲" : "▼"
        : "▴";
    const infoHtml = col.info
        ? `<span class="info-icon" title="${col.info}">ⓘ</span>`
        : "";
    let chevronHtml = "";
    if (col.expandable) {
        const expanded = isExpanded(col.expandable);
        const ch = expanded ? "▾" : "▸";  // ▾ : ▸
        chevronHtml = `<span class="col-chevron" onclick="event.stopPropagation();toggleGroup('${col.expandable}')" title="${expanded ? 'Collapse' : 'Expand'}">${ch}</span>`;
    }
    html += `<th class="${isSorted ? "sorted" : ""}" onclick="sortBy('${col.key}')">
        ${col.label}${infoHtml}${chevronHtml}<span class="sort-arrow">${arrow}</span>
    </th>`;
}
html += "</tr></thead><tbody>";
```

`event.stopPropagation()` prevents the chevron click from also firing the sort handler on the `<th>`.

- [ ] **Step 3: Manually verify the chevrons appear and toggle**

Reload `http://localhost:5002/`, infantry tab. Expected: `GC ▸`, `AC ▸`, `AT ▸`, `Special ▸` headers. Click any chevron — character flips to `▾`; clicking again flips back. (No new columns reveal yet — that's Task 9.) Click the column label (not the chevron) — sorting still works.

- [ ] **Step 4: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat(rankings-table): expansion state + chevron toggle in headers"
```

---

## Task 9: Frontend per-line column rendering for role expansion

**Files:**
- Modify: `webapp/static/js/rankings.js` — column-def builder, enrichment loop, and a `LINE_LABEL_SHORT` map.

- [ ] **Step 1: Add the line-label short-form map**

Near the existing `LINE_LABELS` constant (around line 873), add:

```js
// Short labels used for per-line breakdown column headers (vs <Line>).
const LINE_LABEL_SHORT = {
    militia: "Militia",
    knight: "Knight",
    archer: "Archer",
    spear: "Spear",
    skirmisher: "Skirm",
    light_cav: "Lt Cav",
    camel: "Camel",
    steppe_lancer: "Stp Lan",
    elephant: "Elephant",
    cav_archer: "Cav Arch",
    gunpowder: "Gun",
};

// Lines defined for each (pool, role) — must mirror POOL_ROLES in pool_scores_lib.py.
const POOL_ROLE_LINES = {
    infantry: {
        GC: ["militia", "knight", "archer"],
        AC: ["knight", "camel", "steppe_lancer", "elephant"],
        AT: ["spear", "skirmisher", "light_cav"],
    },
    stable: {
        GC: ["militia", "knight", "archer"],
        AC: ["knight", "camel", "steppe_lancer", "elephant", "light_cav"],
    },
    archer: {
        GC: ["militia", "knight", "archer"],
        AA: ["archer", "skirmisher", "cav_archer", "gunpowder"],
    },
};
```

- [ ] **Step 2: Add a helper to read a per-line value from a unit row**

Right after `getPoolScoreValue` (around line 95–112), add:

```js
// Read the per-line breakdown for one (role, line_key) under the active scale.
function getPoolLineValue(unitRow, role, lineKey) {
    const ps = unitRow && unitRow.pool_scores;
    if (!ps || !ps.scales) return null;
    const axis = currentScoreAxis;
    const readScale = (k) => {
        const sc = ps.scales[k];
        if (!sc || !sc[axis] || !sc[axis].role_line_means) return null;
        const r = sc[axis].role_line_means[role];
        if (!r) return null;
        const v = r[lineKey];
        return v == null ? null : v;
    };
    if (currentScoreScale === "average") {
        const a = readScale("30v30");
        const b = readScale("3k");
        if (a == null || b == null) return null;
        return (a + b) / 2;
    }
    return readScale(currentScoreScale === "pop" ? "30v30" : "3k");
}
```

- [ ] **Step 3: Denormalize per-line values onto enriched rows**

In `rankings.js`'s `renderTable()` enrichment loop (around line 1009–1092), after the existing `pool_aa: getPoolScoreValue(...)` line in the returned object, add:

```js
            // Denormalize per-line breakdowns so existing sortBy() works.
            // Key format: role_line_<ROLE>_<line_key>
            ...buildRoleLineFields(r),
```

And define `buildRoleLineFields` next to the other helpers (above `renderTable`):

```js
function buildRoleLineFields(row) {
    const ps = row.pool_scores;
    if (!ps) return {};
    const pool = ps.pool;
    const def = POOL_ROLE_LINES[pool];
    if (!def) return {};
    const out = {};
    for (const role of Object.keys(def)) {
        for (const line of def[role]) {
            out[`role_line_${role}_${line}`] = getPoolLineValue(row, role, line);
        }
    }
    return out;
}
```

- [ ] **Step 4: Insert per-line column defs into the column arrays**

Modify the column-array construction. After each role-column entry (e.g., the `pool_gc` entry in `infantryColumns`), inject per-line columns when `expandedGroups.has(role)`. Since column arrays are built once per render, fold this into a builder. Replace the `infantryColumns`, `archeryColumns`, `stableColumns` arrays with a single helper `buildColumns(pool)` and replace the `columns =` ternary that selects between them.

Add this helper near the top of the column-defs section (just before `const defaultColumns`):

```js
function _roleColumn(role, pool, label) {
    return {
        key: `pool_${role.toLowerCase()}`,
        label,
        info: roleColumnInfo(role, pool),
        expandable: role,
    };
}

function _perLineColumns(pool, role) {
    if (!isExpanded(role)) return [];
    const lines = POOL_ROLE_LINES[pool]?.[role] || [];
    return lines.map((line) => ({
        key: `role_line_${role}_${line}`,
        label: `vs ${LINE_LABEL_SHORT[line] || line}`,
        expandable: role,
        perLine: true,
    }));
}

function buildColumns(pool) {
    const showLine =
        (pool === "infantry" && currentLine === "infantry") ||
        (pool === "archer" && currentLine === "archery") ||
        pool === "stable";
    const cols = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        ...(showLine ? [{ key: "line_slug", label: "Line" }] : []),
        {
            key: "pool_score",
            label: scoreColumnLabel(currentScoreAxis, currentScoreScale),
            info: scoreColumnInfo(currentScoreAxis, currentScoreScale),
        },
        _roleColumn("GC", pool, "GC"),
        ..._perLineColumns(pool, "GC"),
    ];
    if (pool === "infantry") {
        cols.push(_roleColumn("AC", pool, "AC"), ..._perLineColumns(pool, "AC"));
        cols.push(_roleColumn("AT", pool, "AT"), ..._perLineColumns(pool, "AT"));
    } else if (pool === "stable") {
        cols.push(_roleColumn("AC", pool, "AC"), ..._perLineColumns(pool, "AC"));
    } else if (pool === "archer") {
        cols.push(_roleColumn("AA", pool, "AA"), ..._perLineColumns(pool, "AA"));
    }
    cols.push({
        key: "special_abilities", label: "Special", expandable: "Special",
    });
    return cols;
}
```

Then replace the `columns =` ternary block:

```js
let columns;
if (currentLine === "stable") {
    columns = buildColumns("stable");
} else if (isSiege) {
    columns = siegeColumns;
} else if (isInfantry) {
    columns = buildColumns("infantry");
} else if (isArchery) {
    columns = buildColumns("archer");
} else if (isNaval) {
    columns = navalColumns;
} else {
    columns = defaultColumns;
}
```

Delete the now-unused `infantryColumns`, `archeryColumns`, `stableColumns` arrays.

- [ ] **Step 5: Format per-line cells in `fmtCell`**

In the `fmtCell` function (around line 1483), per-line columns inherit the score-cell formatting because their key starts with `role_line_`. Add an early branch:

```js
if (k.startsWith("role_line_")) {
    if (v === undefined || v === null) return `<td>—</td>`;
    return `<td>${v.toFixed(1)}</td>`;
}
```

Place this right after the `if (k === "special_abilities")` branch, before the generic numeric branch.

- [ ] **Step 6: Manually verify per-line columns appear when expanded**

Reload `http://localhost:5002/`. Click `GC ▸` chevron on infantry tab. Expected: 3 new columns appear (`vs Militia`, `vs Knight`, `vs Archer`) right after GC. Each shows a numeric value or `—`. Click any of those headers — sorts. Click `GC ▾` again — columns disappear.

Test on Archer and Stable tabs too. Verify Stable AC reveals 5 columns (knight/camel/steppe_lancer/elephant/light_cav).

- [ ] **Step 7: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat(rankings-table): per-line breakdown columns for role expansion"
```

---

## Task 10: Frontend Special-column expansion (raw stats)

**Files:**
- Modify: `webapp/static/js/rankings.js` (column builder)

- [ ] **Step 1: Insert stat columns when Special is expanded**

Update `buildColumns(pool)` — replace the final `cols.push({ key: "special_abilities", ... })` with:

```js
    if (isExpanded("Special")) {
        cols.push(
            { key: "dps",              label: "DPS",     expandable: "Special" },
            { key: "final_hp",         label: "HP",      expandable: "Special" },
            { key: "final_attack",     label: "Atk",     expandable: "Special" },
            { key: "armor_combined",   label: "M/P Arm", expandable: "Special" },
            { key: "final_speed",      label: "Speed",   expandable: "Special" },
        );
        if (pool === "archer") {
            cols.push({ key: "final_range", label: "Range", expandable: "Special" });
        }
        cols.push(
            { key: "total_cost",          label: "Cost",     expandable: "Special" },
            { key: "total_upgrade_cost",  label: "Upg Cost", expandable: "Special" },
        );
    }
    cols.push({
        key: "special_abilities", label: "Special", expandable: "Special",
    });
    return cols;
}
```

- [ ] **Step 2: Compute `armor_combined` in the enrichment loop**

In `renderTable()`'s `enriched.map(...)` block, add a field on the returned object:

```js
            armor_combined: `${r.final_melee_armor || 0}/${r.final_pierce_armor || 0}`,
            armor_sort_key: r.final_melee_armor || 0,
```

- [ ] **Step 3: Render the combined armor cell + handle sort key**

In `fmtCell`, add a branch (right after `if (k.startsWith("role_line_"))`):

```js
if (k === "armor_combined") {
    return `<td>${v}</td>`;
}
```

In `sortBy` (around line 1564), if the user clicks the `armor_combined` header we sort on `armor_sort_key` instead. Update `sortBy`:

```js
function sortBy(column) {
    if (sortColumn === column) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
        sortColumn = column;
        sortDir =
            column === "civ_name" || column === "unit_name"
                ? "asc"
                : "desc";
    }
    renderTable();
}
```

Inside `renderTable()`'s sort step, swap the column key for armor:

```js
filtered.sort((a, b) => {
    const sortKey = sortColumn === "armor_combined" ? "armor_sort_key" : sortColumn;
    let va = a[sortKey], vb = b[sortKey];
    // ...rest of the existing sort body, replacing all `a[sortColumn]` with `a[sortKey]`...
```

Make the analogous change in any other place in `renderTable()` that reads `r[sortColumn]`.

- [ ] **Step 4: Manually verify Special expansion**

Reload, infantry tab, click `Special ▸`. Expected: 7 new columns appear (DPS, HP, Atk, M/P Arm, Speed, Cost, Upg Cost) before the Special cell. Verify M/P Arm reads `0/4` style and sorts ascending by melee armor when clicked. Switch to Archer tab — verify Range column also appears between Speed and Cost when Special is expanded.

- [ ] **Step 5: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat(rankings-table): special column expands to raw stats"
```

---

## Task 11: Frontend missing-techs in Special cell

**Files:**
- Modify: `webapp/static/js/rankings.js` (`fmtCell` for `special_abilities`)
- Modify: `webapp/static/css/rankings.css`

- [ ] **Step 1: Render two-line Special cell**

In `fmtCell`, replace the existing branch:

```js
if (k === "special_abilities") {
    return `<td style="white-space:normal;max-width:200px;font-size:0.7rem">${v || "—"}</td>`;
}
```

with:

```js
if (k === "special_abilities") {
    const effects = v || "";
    const missing = row.missing_techs || [];
    const lines = [];
    if (effects) lines.push(`<div class="special-effects">${effects}</div>`);
    if (missing.length > 0) {
        lines.push(
            `<div class="special-missing">❌ Missing: ${missing.join(", ")}</div>`,
        );
    }
    if (lines.length === 0) lines.push("—");
    return `<td class="special-cell">${lines.join("")}</td>`;
}
```

- [ ] **Step 2: Add CSS for the two-line cell**

Append to `webapp/static/css/rankings.css`:

```css
/* === Special column two-line layout === */
.special-cell {
    white-space: normal;
    max-width: 220px;
    font-size: 0.7rem;
    line-height: 1.3;
}
.special-cell .special-effects {
    color: var(--text);
}
.special-cell .special-missing {
    color: var(--text-muted);
    font-size: 0.65rem;
    margin-top: 2px;
}
```

- [ ] **Step 3: Manually verify**

Reload. On infantry tab, find a non-Goth row (e.g., Aztec Champion). Expected: Special cell shows missing techs on a second muted line prefixed with ❌. Goth militia rows show no missing-techs line (Goths have all militia-line techs).

- [ ] **Step 4: Commit**

```bash
git add webapp/static/js/rankings.js webapp/static/css/rankings.css
git commit -m "feat(rankings-table): two-line Special cell with missing techs"
```

---

## Task 12: Frontend Expand All / Collapse All button

**Files:**
- Modify: `webapp/static/js/rankings.js` (top-of-table HTML in `renderTable()`)

- [ ] **Step 1: Add the button next to the CSV export**

In `renderTable()` around line 1446 — locate the existing block:

```js
let html = `<div class="civ-filter-wrap">
    <input type="text" id="civFilterInput" placeholder="Filter by civilization..." value="${civFilter}" oninput="renderTable()" />
    <button class="export-btn" onclick="exportCSV()" title="Export current view as CSV">Export CSV</button>`;
```

Replace with:

```js
const allExpanded = ["GC", "AC", "AT", "AA", "Special"]
    .filter((g) => _groupExistsForCurrentPool(g))
    .every((g) => isExpanded(g));
const expandBtnLabel = allExpanded ? "▾ Collapse All" : "▸ Expand All";
const expandBtnAction = allExpanded ? "collapseAll()" : "expandAll()";

let html = `<div class="civ-filter-wrap">
    <input type="text" id="civFilterInput" placeholder="Filter by civilization..." value="${civFilter}" oninput="renderTable()" />
    <button class="export-btn" onclick="exportCSV()" title="Export current view as CSV">Export CSV</button>
    ${_isPoolPage() ? `<button class="expand-btn" onclick="${expandBtnAction}">${expandBtnLabel}</button>` : ""}`;
```

Add the helper functions near the other state helpers (above `renderTable`):

```js
function _isPoolPage() {
    // The expand button only appears on pool tabs (infantry/archer/stable),
    // not siege/naval which keep their legacy columns.
    const isInfantry = INFANTRY_SLUGS.has(currentLine);
    const isArchery = ARCHERY_SLUGS.has(currentLine);
    const isStable = currentLine === "stable" ||
        UNIT_LINES.stable.subLines.includes(currentLine);
    return isInfantry || isArchery || isStable;
}

function _groupExistsForCurrentPool(group) {
    const isInfantry = INFANTRY_SLUGS.has(currentLine);
    const isArchery = ARCHERY_SLUGS.has(currentLine);
    const isStable = currentLine === "stable" ||
        UNIT_LINES.stable.subLines.includes(currentLine);
    if (group === "Special") return isInfantry || isArchery || isStable;
    if (group === "GC") return isInfantry || isArchery || isStable;
    if (group === "AC") return isInfantry || isStable;
    if (group === "AT") return isInfantry;
    if (group === "AA") return isArchery;
    return false;
}
```

- [ ] **Step 2: Add CSS for the expand button**

Append to `webapp/static/css/rankings.css`:

```css
.expand-btn {
    margin-left: 8px;
    padding: 4px 10px;
    background: var(--bg-warm);
    color: var(--text);
    border: 1px solid var(--border-light);
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
}
.expand-btn:hover {
    background: var(--bg-hover);
    border-color: var(--gold-dark);
}
```

- [ ] **Step 3: Manually verify**

Reload. Infantry tab: button reads `▸ Expand All`. Click — all 4 groups (GC/AC/AT/Special) expand simultaneously, button flips to `▾ Collapse All`. Click again — everything collapses. Verify button does not appear on Siege or Naval tabs.

Mixed-state behavior: collapse all, then click only `GC ▸` chevron. Button still reads `▸ Expand All`. Click it — remaining groups expand; now button reads `▾ Collapse All`. Click — everything collapses.

- [ ] **Step 4: Commit**

```bash
git add webapp/static/js/rankings.js webapp/static/css/rankings.css
git commit -m "feat(rankings-table): expand all / collapse all button"
```

---

## Task 13: Frontend slide animation

**Files:**
- Modify: `webapp/static/css/rankings.css`
- Modify: `webapp/static/js/rankings.js` (rendering uses `col-expandable collapsed` class for hidden cells)

This task changes expansion to keep cells in the DOM (with `max-width: 0`) rather than excluding them from the column array, so CSS transitions can drive the slide.

- [ ] **Step 1: Add the slide CSS**

Append to `webapp/static/css/rankings.css`:

```css
/* === Slide animation for expandable columns === */
.col-expandable {
    transition: max-width 200ms ease, padding 200ms ease, opacity 150ms ease;
    overflow: hidden;
    white-space: nowrap;
    max-width: 240px;
    opacity: 1;
}
.col-expandable.collapsed {
    max-width: 0;
    padding-left: 0;
    padding-right: 0;
    opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
    .col-expandable {
        transition: none;
    }
}
```

- [ ] **Step 2: Switch from "exclude column when collapsed" to "render with collapsed class"**

In `_perLineColumns(pool, role)` and the Special-expansion block of `buildColumns(pool)`, the columns must be **always emitted** but tagged so the renderer can apply the collapsed class. Replace `_perLineColumns`:

```js
function _perLineColumns(pool, role) {
    const lines = POOL_ROLE_LINES[pool]?.[role] || [];
    return lines.map((line) => ({
        key: `role_line_${role}_${line}`,
        label: `vs ${LINE_LABEL_SHORT[line] || line}`,
        expandable: role,
        perLine: true,
        hiddenWhenCollapsed: true,
    }));
}
```

In the Special expansion section of `buildColumns`, drop the `if (isExpanded("Special"))` guard and tag those columns:

```js
    cols.push(
        { key: "dps",              label: "DPS",     expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_hp",         label: "HP",      expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_attack",     label: "Atk",     expandable: "Special", hiddenWhenCollapsed: true },
        { key: "armor_combined",   label: "M/P Arm", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_speed",      label: "Speed",   expandable: "Special", hiddenWhenCollapsed: true },
    );
    if (pool === "archer") {
        cols.push({ key: "final_range", label: "Range", expandable: "Special", hiddenWhenCollapsed: true });
    }
    cols.push(
        { key: "total_cost",          label: "Cost",     expandable: "Special", hiddenWhenCollapsed: true },
        { key: "total_upgrade_cost",  label: "Upg Cost", expandable: "Special", hiddenWhenCollapsed: true },
    );
    cols.push({
        key: "special_abilities", label: "Special", expandable: "Special",
    });
    return cols;
}
```

- [ ] **Step 3: Apply `collapsed` class in header and cell rendering**

Modify the header loop:

```js
for (const col of columns) {
    const isSorted = sortColumn === col.key;
    const arrow = isSorted ? sortDir === "asc" ? "▲" : "▼" : "▴";
    const infoHtml = col.info
        ? `<span class="info-icon" title="${col.info}">ⓘ</span>` : "";
    let chevronHtml = "";
    if (col.expandable && !col.hiddenWhenCollapsed) {
        const expanded = isExpanded(col.expandable);
        const ch = expanded ? "▾" : "▸";
        chevronHtml = `<span class="col-chevron" onclick="event.stopPropagation();toggleGroup('${col.expandable}')" title="${expanded ? 'Collapse' : 'Expand'}">${ch}</span>`;
    }
    const collapsedClass = (col.hiddenWhenCollapsed && !isExpanded(col.expandable))
        ? "col-expandable collapsed"
        : (col.hiddenWhenCollapsed ? "col-expandable" : "");
    const sortedClass = isSorted ? "sorted" : "";
    const cls = [collapsedClass, sortedClass].filter(Boolean).join(" ");
    html += `<th class="${cls}" onclick="sortBy('${col.key}')">
        ${col.label}${infoHtml}${chevronHtml}<span class="sort-arrow">${arrow}</span>
    </th>`;
}
```

Modify `fmtCell` to apply the same class on `<td>`:

```js
function fmtCell(col, row, rowIdx) {
    const k = col.key;
    const collapsed = col.hiddenWhenCollapsed && !isExpanded(col.expandable);
    const expandableClass = col.hiddenWhenCollapsed
        ? (collapsed ? "col-expandable collapsed" : "col-expandable")
        : "";

    // ... existing cell-content logic; wherever you build the <td ... > tag,
    // include the expandableClass on its className attribute.
```

The simplest mechanical change: every `return ` in `fmtCell` that returns a `<td...>` string needs the `expandableClass` added. Find each `<td` opener and append `${expandableClass}` to its `class=`.

For the simpler returns:

```js
return `<td class="${expandableClass}">—</td>`;
return `<td class="${expandableClass}">${v}</td>`;
```

For the conditional ones already producing classes:

```js
const allClasses = [cls, hcClass, expandableClass].filter(Boolean).join(" ");
return `<td class="${allClasses}" onmouseenter="..." onmouseleave="..." onclick="...">${formatted}</td>`;
```

Be sure to include `expandableClass` everywhere `fmtCell` builds a `<td>`.

- [ ] **Step 4: Manually verify slide animation**

Reload. Click `GC ▸` chevron — per-line columns should slide out from the right side of GC over ~200ms. Click `GC ▾` — they slide back. Same for AC, AT, Special. Verify reduced-motion (DevTools → Rendering → "Emulate CSS prefers-reduced-motion: reduce") shows instant transitions.

- [ ] **Step 5: Commit**

```bash
git add webapp/static/css/rankings.css webapp/static/js/rankings.js
git commit -m "feat(rankings-table): slide animation for column expansion"
```

---

## Task 14: Final smoke test + commit re-derived DB

**Files:** none modified beyond verification.

- [ ] **Step 1: Full smoke test**

Run `PORT=5002 python3 webapp/app.py` and verify each of the following on `http://localhost:5002/`:

1. **Infantry tab default view** (8 cols): Civ, Unit, Line, HP, GC ▸, AC ▸, AT ▸, Special ▸.
2. **Archer tab default view** (7 cols): no AT.
3. **Stable tab default view** (7 cols): no AT.
4. **Click GC chevron** → 3 per-line columns slide out; sort by `vs Knight` works; values are non-null where data exists.
5. **Click GC chevron again** → columns slide back; sort retained on hidden column.
6. **Click Expand All** → all groups expand; button label flips to `▾ Collapse All`.
7. **Click Collapse All** → all groups collapse; button flips back.
8. **Special cell** shows `;`-separated effects on top line, `❌ Missing: ...` on a muted second line for civs with missing techs.
9. **Click Special chevron** → DPS / HP / Atk / M/P Arm / Speed / [Range] / Cost / Upg Cost columns slide out.
10. **Switch from infantry to archer tab** → expansion state resets to all collapsed.
11. **Refresh page** → all collapsed.
12. **Siege tab** → unchanged column layout, no expand button visible.

If everything looks right, the implementation is done.

- [ ] **Step 2: Run the full test suite**

```bash
pytest
```

Expected: all tests PASS. Pay particular attention to the four pool-scores test files modified across this plan.

- [ ] **Step 3: Final commit (if any uncommitted housekeeping)**

```bash
git status
# If anything is unstaged, commit it with a descriptive message.
```

---

## Self-Review Checklist (for plan authors)

**Spec coverage:**
- §"Default column layout (slim view)" → Tasks 7, 9, 10, 12
- §"Expansion behavior" → Tasks 8, 9, 10, 13 (animation), 12 (button)
- §"Special column content" → Task 11
- §"Backend schema & API" → Tasks 1, 2, 3, 4, 6
- §"Frontend state model" → Tasks 8, 9
- §"Testing" → Tests added in Tasks 1, 2, 3, 4, 5, 6
- §"Reference values" → Task 5 pins Berserker per-line values

All sections covered.

**Type / name consistency:**
- `role_line_means` — used in DB column, lib output dict key, JSON encoding, query payload, API output, JS `getPoolLineValue` access path. Consistent.
- `expandedGroups` — single set used by `toggleGroup`, `expandAll`, `collapseAll`, `isExpanded`, `_groupExistsForCurrentPool`. Consistent.
- `POOL_ROLE_LINES` (JS) ↔ `POOL_ROLES` (Python) — same line keys; JS mirrors Python definition. Consistent.
- `expandable` / `hiddenWhenCollapsed` / `perLine` — column-def flags, all defined when introduced. Consistent.

**Placeholder scan:**
- Task 5 / Step 3 has `expected_militia = ...` placeholders — these are intentional and resolved by Step 2's sqlite query before committing. Documented inline.
- No other `TBD` / `TODO` / vague-instruction patterns present.
