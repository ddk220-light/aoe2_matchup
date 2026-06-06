# Patch Analysis & Unit Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a flagship "Patches" feature — a readable per-patch log plus data-driven impact analysis (stat deltas, ranking moves, flipped matchups) tagged per build so each unit gets an evolution timeline; the result DBs that drive Rankings + Matchup Advisor become build-versioned and the live pages always read the current build.

**Architecture:** A new `patches.db` (registry + diff tables) is the source of truth for patch metadata and per-unit/per-matchup deltas. The derived result DBs (`derived_data.db::battle_scores`, `pool_scores.db`, `civ_power_units/<build>.json`) gain a `build_number` so every patch keeps an immutable, *complete* snapshot. A `patch_pipeline.py` orchestrates: archive → re-extract `.dat` → rebuild ref/main DBs → diff `ref_units` (prev vs new) → force-re-sim only changed unit slugs → diff matchup outcomes → write a new build-tagged result snapshot → insert the `patches` row and flip `is_current`. New Flask routes render the Patches timeline and per-unit analysis pages; the Battle Sim gains auto-run deep links.

**Tech Stack:** Python 3 / Flask, SQLite, PyPy (re-sim only), Jinja2 templates with inlined CSS/JS, vanilla JS (`simulate.js`), pytest + node test scripts.

---

## Background the engineer must know

- **Four-stage pipeline:** `extraction/run.py` (`.dat`→JSON) → `analysis/generate_reference.py` (`webapp/aoe2_reference.db`, ~30s) → `analysis/generate_main_db.py` (`webapp/aoe2_units.db`, ~2s) → webapp. Re-applies surgical patch `analysis/patches/patch_mayan_archer_cost.py` after a rebuild.
- **The matchup sim** is `webapp/run_matchup_battles.py` (PyPy-only). It writes raw 1v1 outcomes to `matchup_db.db` (table `matchup_battles`). **The real, full matchup DB is the LOCAL file `D:\AI\matchup_db.db` (~193 MB), NOT committed.** Only the *derived* result DBs are committed and carry data to production.
- **Derived result DBs (committed):** `webapp/derived_data.db` (`battle_scores`), `webapp/pool_scores.db` (`pool_scores`), `webapp/civ_power_units.json`. These drive the Rankings page (`/api/ref/unit-line`) and Matchup Advisor (`/api/civ-power-units`).
- **`sim_version`** = `sha256(simulation_real.py + config_combat.py)[:16]`. A *stat-only* patch does NOT change `sim_version`, so `run_matchup_battles.has_row_with_version()` would skip re-simming changed units. Task 8 adds a `--force` path to override this.
- **Per-matchup score** = `battle_outcome.signed_score(o)` = `100*(team1_hp_pct - team2_hp_pct)` if team1 won, negated if team2 won, 0 on draw. Computable directly from `matchup_battles` columns (`winner`, `team1_hp_pct`, `team2_hp_pct`).
- **Ranking score** lives in `battle_scores` keyed by `score_type` (role scores `general_combat`/`anti_archer`/`anti_cav`/`anti_trash` and composites `militia_value`/`ranged_effectiveness`/`stable_effectiveness`). `rank` is computed per `(line_slug, score_type)` across civs. **The headline ranking metric per unit is its line composite** (`militia_value` | `ranged_effectiveness` | `stable_effectiveness`). `patch_unit_ranking` therefore keys on `score_type`, NOT `scale` (refinement of the spec, which said `scale`; the per-`scale` dimension lives in `patch_matchup_changes`).
- **`battle_scores` also holds naval/siege rows written by OTHER pipelines** (not re-derived by `derive_unit_rankings.py`). A new build snapshot must **carry those forward** so the snapshot is complete (Task 11).
- **Deep-link params already parse** in `simulate.js` (~lines 2416–2467: `civ1/unit1/civ2/unit2/mode/resources/count1/count2`) but only *pre-load* selections. Task 15 adds `age1/age2` + `autorun`.
- **Tests:** `pytest` (testpaths=tests). JS tests are node scripts (see `tests/test_frontend_projectile_miss.js`). Run a single test: `pytest tests/test_x.py::test_y -v`.
- **Git:** work on `staging`. Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Do NOT push `main`. Do NOT commit `matchup_db.db`.
- **Windows note:** prints must be ASCII (`->` not `→`); the dev box is Windows (CRLF). Use absolute paths in shell commands.

## File Structure

**New files:**
- `webapp/patches_db.py` — schema + I/O + `get_current_build()` for `patches.db`.
- `webapp/migrate_baseline.py` — one-time: add `build_number`, tag existing data as `170934`, seed the baseline `patches` row, move `civ_power_units.json` → `civ_power_units/170934.json`.
- `webapp/ref_diff.py` — snapshot/diff `ref_units` (prev vs new) → per-(civ,slug) stat deltas + changed-slug set.
- `webapp/matchup_diff.py` — snapshot matchup outcomes for changed slugs + diff before/after → `patch_matchup_changes` rows; ranking diff helper → `patch_unit_ranking` rows.
- `webapp/patch_pipeline.py` — end-to-end orchestrator.
- `webapp/sim_params.js` (small, browser+node compatible) — pure `readSimParams(search)` deep-link parser, unit-testable.
- `webapp/templates/patches.html` — Patches timeline tab.
- `webapp/templates/patch_unit.html` — per-unit analysis page.
- Tests: `tests/test_patches_db.py`, `tests/test_versioning.py`, `tests/test_ref_diff.py`, `tests/test_matchup_diff.py`, `tests/test_patch_routes.py`, `tests/test_sim_params.js`.

**Modified files:**
- `webapp/derived_db.py`, `webapp/derive_unit_rankings.py` — `build_number` on `battle_scores`.
- `webapp/pool_scores_db.py`, `webapp/derive_pool_scores.py` — `build_number` on `pool_scores`.
- `webapp/best_units.py` — read current build; write `civ_power_units/<build>.json`; load by build.
- `webapp/pool_scores_query.py` — accept `build_number`.
- `webapp/app.py` — DB path constants; current-build resolution in `/api/ref/unit-line` + civ-power-units load; new `/patches` routes.
- `webapp/run_matchup_battles.py` — `--force` flag.
- `webapp/templates/base.html` — Patches nav tab.
- `webapp/static/js/simulate.js` + `webapp/templates/simulate.html` — load `sim_params.js`; auto-run + age params.

---

## PHASE 1 — Versioning foundation (data layer)

> **Implementation order:** build **Task 4 (`patches_db.py`) first** — it has no
> dependencies and Tasks 1, 2, 3, and 6 all `from patches_db import get_current_build`.
> If you implement Task 1 before Task 4, the new import line in `derive_unit_rankings.py`
> is a latent unresolved import (nothing in the test suite imports that module until the
> pipeline runs, so Task 1's targeted test still passes) — but doing Task 4 first avoids
> any full-suite import error between tasks.

### Task 1: Add `build_number` to `battle_scores`

**Files:**
- Modify: `webapp/derived_db.py` (SCHEMA + `create_db`)
- Modify: `webapp/derive_unit_rankings.py:140-308` (`compute_and_write_rankings`)
- Test: `tests/test_versioning.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_versioning.py
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import derived_db


def test_battle_scores_schema_has_build_number(tmp_path):
    db = str(tmp_path / "derived.db")
    conn = derived_db.create_db(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(battle_scores)")}
    assert "build_number" in cols
    # UNIQUE must include build_number so two builds can coexist for one unit
    conn.execute(
        "INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,score_type,"
        "score_value,rank,median_delta,build_number) VALUES "
        "('knight','imperial','Franks','knight','stable_effectiveness',90.0,1,5.0,'170934')"
    )
    conn.execute(
        "INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,score_type,"
        "score_value,rank,median_delta,build_number) VALUES "
        "('knight','imperial','Franks','knight','stable_effectiveness',88.0,2,3.0,'177723')"
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM battle_scores WHERE civ_name='Franks' "
                     "AND unit_slug='knight'").fetchone()[0]
    assert n == 2
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_versioning.py::test_battle_scores_schema_has_build_number -v`
Expected: FAIL — `build_number` column missing / UNIQUE violation on the second insert.

- [ ] **Step 3: Update the schema in `derived_db.py`**

Replace the `battle_scores` CREATE TABLE block (lines 18-31) with:

```python
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
```

(Leave the `advisor_recommendations` block and the closing `"""` unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_versioning.py::test_battle_scores_schema_has_build_number -v`
Expected: PASS

- [ ] **Step 5: Make `compute_and_write_rankings` build-aware**

In `webapp/derive_unit_rankings.py`:

Add an import near the top (after line 15):
```python
from patches_db import get_current_build  # resolves the build to tag rows with
```

Change the signature (line 140-143) to accept `build_number`:
```python
def compute_and_write_rankings(matchup_db_path=MATCHUP_DB_PATH,
                               ref_db_path=REF_DB_PATH,
                               derived_db_path=DERIVED_DB_PATH,
                               age="Imperial",
                               build_number=None):
    """Returns count of rows inserted into battle_scores. Rows are tagged with
    build_number (defaults to the current build from patches.db, then '170934')."""
    if build_number is None:
        build_number = get_current_build(derived_db_path=derived_db_path) or "170934"
```

Scope the first DELETE (lines 277-283) to the build by adding `AND build_number=?`:
```python
    for (line, civ, slug), _st_map in out.items():
        cur.execute(
            f"DELETE FROM battle_scores WHERE age=? AND civ_name=? "
            f"AND unit_slug=? AND line_slug != ? AND build_number=? "
            f"AND score_type IN ({land_score_phs})",
            (age_lower, civ, slug, line, build_number) + LAND_SCORE_TYPES,
        )
```

Scope the per-(line,st) DELETE (lines 289-292):
```python
            cur.execute(
                "DELETE FROM battle_scores WHERE line_slug=? AND age=? "
                "AND civ_name=? AND unit_slug=? AND score_type=? AND build_number=?",
                (line, age_lower, civ, slug, st, build_number),
            )
```

Add `build_number` to the INSERT (lines 297-303):
```python
            cur.execute("""
                INSERT INTO battle_scores
                (line_slug, age, civ_name, unit_slug, score_type, score_value,
                 rank, median_delta, build_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (line, age_lower, civ, slug, st, round(val, 1),
                  rank_idx, round(val - median_val, 1), build_number))
```

Add `--build` to `main()` (after line 313):
```python
    parser.add_argument("--build", dest="build", default=None,
                        help="Build number to tag rows with (default: current).")
```
and pass it (line 318-319):
```python
    n = compute_and_write_rankings(matchup_db_path=args.matchup_db,
                                   age=args.age.capitalize(),
                                   build_number=args.build)
```

> NOTE: `get_current_build` is created in Task 4. Tasks 1–4 land together before any standalone run of this script; the unit test above does not import `derive_unit_rankings`, so it passes independently.

- [ ] **Step 6: Commit**

```bash
git add webapp/derived_db.py webapp/derive_unit_rankings.py tests/test_versioning.py
git commit -m "feat(patches): build_number on battle_scores + build-aware rankings derivation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add `build_number` to `pool_scores`

**Files:**
- Modify: `webapp/pool_scores_db.py` (SCHEMA + `_INSERT_SQL`)
- Modify: `webapp/derive_pool_scores.py` (build param + row tagging)
- Modify: `webapp/pool_scores_query.py` (optional build filter)
- Test: `tests/test_versioning.py` (append)

- [ ] **Step 1: Write the failing test (append to `tests/test_versioning.py`)**

```python
import pool_scores_db


def _pool_row(civ, build, score):
    return dict(civ_name=civ, unit_slug="knight", pool="stable", scale="30v30",
                axis="hp", final_score=score, gc=None, ac=None, at=None, aa=None,
                n=10, mean=score, stddev=1.0, win_rate=0.5, decisive_win_rate=0.3,
                big_win_rate=0.2, catastrophic_loss_rate=0.1, sim_version="x",
                derived_at="2026-06-06", role_line_means=None, build_number=build)


def test_pool_scores_build_number(tmp_path):
    db = str(tmp_path / "pool.db")
    conn = pool_scores_db.create_db(db)
    pool_scores_db.insert_score(conn, _pool_row("Franks", "170934", 90.0))
    pool_scores_db.insert_score(conn, _pool_row("Franks", "177723", 85.0))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM pool_scores WHERE civ_name='Franks' "
                     "AND unit_slug='knight' AND scale='30v30' AND axis='hp'").fetchone()[0]
    assert n == 2
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_versioning.py::test_pool_scores_build_number -v`
Expected: FAIL — `build_number` not a column; PK collision collapses the two rows to one.

- [ ] **Step 3: Update `pool_scores_db.py` schema + insert**

Add `build_number TEXT NOT NULL DEFAULT '170934'` to the table and include it in the PK. Replace lines 8-35:

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
    build_number          TEXT NOT NULL DEFAULT '170934',
    PRIMARY KEY (civ_name, unit_slug, scale, axis, build_number)
);

CREATE INDEX IF NOT EXISTS idx_pool_scores_pool_axis_scale
    ON pool_scores (pool, axis, scale, build_number);
"""
```

Replace `_INSERT_SQL` (lines 46-60) to include `build_number`:
```python
_INSERT_SQL = """
INSERT OR REPLACE INTO pool_scores (
    civ_name, unit_slug, pool, scale, axis,
    final_score, gc, ac, at, aa,
    n, mean, stddev,
    win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
    sim_version, derived_at, role_line_means, build_number
) VALUES (
    :civ_name, :unit_slug, :pool, :scale, :axis,
    :final_score, :gc, :ac, :at, :aa,
    :n, :mean, :stddev,
    :win_rate, :decisive_win_rate, :big_win_rate, :catastrophic_loss_rate,
    :sim_version, :derived_at, :role_line_means, :build_number
)
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_versioning.py::test_pool_scores_build_number -v`
Expected: PASS

- [ ] **Step 5: Tag rows in `derive_pool_scores.py`**

In `webapp/derive_pool_scores.py`:
- Add import: `from patches_db import get_current_build`.
- In `main()`, add the CLI arg: `p.add_argument("--build", default=None)`.
- Resolve the build once after parsing args:
  ```python
  build_number = args.build or get_current_build(out_db_path=args.out) or "170934"
  ```
- Find where each `row` dict is built before `insert_score(conn, row)` and add `row["build_number"] = build_number` (if rows are built via a dict literal, add the key there).

- [ ] **Step 6: Add optional build filter to `pool_scores_query.load_pool_scores`**

Change the signature (line 18) and query (line 44-46):
```python
def load_pool_scores(db_path: str,
                     civ_unit_pairs: list[tuple[str, str]],
                     build_number: str | None = None) -> dict:
    ...
        sql = f"""
            SELECT civ_name, unit_slug, pool, scale, axis,
                   final_score, gc, ac, at, aa,
                   n, mean, stddev,
                   win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
                   role_line_means
            FROM pool_scores
            WHERE (civ_name, unit_slug) IN ({placeholders})
        """
        if build_number is not None:
            sql += " AND build_number = ?"
            params.append(build_number)
        cur = conn.execute(sql, params)
```

- [ ] **Step 7: Run the full versioning test file**

Run: `pytest tests/test_versioning.py tests/test_pool_scores_query.py tests/test_pool_scores_db.py -v`
Expected: PASS (existing pool tests still green — `build_number` has a default and `load_pool_scores` build filter is opt-in).

- [ ] **Step 8: Commit**

```bash
git add webapp/pool_scores_db.py webapp/derive_pool_scores.py webapp/pool_scores_query.py tests/test_versioning.py
git commit -m "feat(patches): build_number on pool_scores + build-aware pool derivation/query

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Version `civ_power_units` (read current build, write per-build JSON)

**Files:**
- Modify: `webapp/best_units.py` (paths, read filters, save/load by build)
- Test: `tests/test_versioning.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
import importlib


def test_power_units_path_for_build(monkeypatch, tmp_path):
    import best_units
    importlib.reload(best_units)
    monkeypatch.setattr(best_units, "POWER_UNITS_DIR", str(tmp_path / "cpu"))
    p = best_units.power_units_path("177723")
    assert p.endswith(os.path.join("cpu", "177723.json"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_versioning.py::test_power_units_path_for_build -v`
Expected: FAIL — `power_units_path` / `POWER_UNITS_DIR` not defined.

- [ ] **Step 3: Add per-build path helpers in `best_units.py`**

Near the path constants (lines 12-15), add:
```python
POWER_UNITS_DIR = os.path.join(os.path.dirname(__file__), "civ_power_units")


def power_units_path(build_number):
    return os.path.join(POWER_UNITS_DIR, f"{build_number}.json")
```

- [ ] **Step 4: Make `compute_civ_power_units` + save/load build-aware**

- Add `from patches_db import get_current_build` at the top.
- Change `compute_civ_power_units()` to `compute_civ_power_units(build_number=None)`; at the top resolve `build_number = build_number or get_current_build() or "170934"`.
- Add `AND build_number = ?` to the three `battle_scores` reads (lines ~213, ~926, ~1253) and the `pool_scores` read (line ~84), threading `build_number` into each query's params.
- Change `save_civ_power_units()` to:
  ```python
  def save_civ_power_units(build_number=None):
      build_number = build_number or get_current_build() or "170934"
      data = compute_civ_power_units(build_number=build_number)
      os.makedirs(POWER_UNITS_DIR, exist_ok=True)
      path = power_units_path(build_number)
      with open(path, "w") as f:
          json.dump(data, f, indent=2, sort_keys=True)
      print(f"Wrote {path} ({len(data)} civs, build {build_number})")
      return data
  ```
- Change `load_civ_power_units()` (line 1049) to accept a build and read the per-build file, falling back to the legacy flat file:
  ```python
  def load_civ_power_units(build_number=None):
      build_number = build_number or get_current_build()
      if build_number:
          p = power_units_path(build_number)
          if os.path.exists(p):
              with open(p, "r") as f:
                  return json.load(f)
      # legacy fallback (pre-migration single file)
      if os.path.exists(POWER_UNITS_PATH):
          with open(POWER_UNITS_PATH, "r") as f:
              return json.load(f)
      return None
  ```
- Update the `if __name__ == "__main__":` block (line ~1611) to `save_civ_power_units()`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_versioning.py::test_power_units_path_for_build -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/best_units.py tests/test_versioning.py
git commit -m "feat(patches): version civ_power_units per build (read current, write civ_power_units/<build>.json)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `patches.db` module — schema + `get_current_build` + I/O

**Files:**
- Create: `webapp/patches_db.py`
- Test: `tests/test_patches_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_patches_db.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import patches_db


def test_create_and_current_build(tmp_path):
    db = str(tmp_path / "patches.db")
    conn = patches_db.create_db(db)
    patches_db.insert_patch(conn, build_number="170934", release_date="2026-04-01",
                            title="Update 170934", summary_md="base", source_url="http://x",
                            baseline_build=None, is_current=1)
    patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
                            title="Update 177723", summary_md="notes", source_url="http://y",
                            baseline_build="170934", is_current=0)
    conn.commit()
    assert patches_db.get_current_build(patches_db_path=db) == "170934"
    patches_db.set_current_build(conn, "177723"); conn.commit()
    assert patches_db.get_current_build(patches_db_path=db) == "177723"
    # exactly one current
    n = conn.execute("SELECT COUNT(*) FROM patches WHERE is_current=1").fetchone()[0]
    assert n == 1
    conn.close()


def test_get_current_build_missing_db(tmp_path):
    assert patches_db.get_current_build(patches_db_path=str(tmp_path / "nope.db")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_patches_db.py -v`
Expected: FAIL — module `patches_db` does not exist.

- [ ] **Step 3: Create `webapp/patches_db.py`**

```python
"""Schema + I/O for patches.db — the patch registry and per-patch diff tables.

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
    conn.execute("UPDATE patches SET is_current=1 WHERE build_number=?", (build_number,))


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_patches_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/patches_db.py tests/test_patches_db.py
git commit -m "feat(patches): patches.db module (schema + get_current_build + I/O)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Baseline migration (`migrate_baseline.py`)

Rebuilds the committed `derived_data.db` / `pool_scores.db` to the new schema (UNIQUE/PK with `build_number`), tags every existing row `170934`, seeds the baseline `patches` row, and moves the flat `civ_power_units.json` to `civ_power_units/170934.json`. Idempotent.

**Files:**
- Create: `webapp/migrate_baseline.py`
- Test: `tests/test_versioning.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
def test_migrate_baseline_tags_and_rebuilds(tmp_path, monkeypatch):
    # Build OLD-schema derived_data.db (no build_number, old UNIQUE)
    import sqlite3, json
    dd = str(tmp_path / "derived_data.db")
    c = sqlite3.connect(dd)
    c.executescript("""
        CREATE TABLE battle_scores (id INTEGER PRIMARY KEY, line_slug TEXT, age TEXT,
          civ_name TEXT, unit_slug TEXT, score_type TEXT, score_value REAL,
          rank INTEGER, median_delta REAL,
          UNIQUE(line_slug,age,civ_name,unit_slug,score_type));
    """)
    c.execute("INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,score_type,"
              "score_value,rank,median_delta) VALUES "
              "('naval','imperial','Britons','galleon','naval_effectiveness',70,1,2)")
    c.commit(); c.close()

    ps = str(tmp_path / "pool_scores.db")
    c = sqlite3.connect(ps)
    c.executescript("""
        CREATE TABLE pool_scores (civ_name TEXT, unit_slug TEXT, pool TEXT, scale TEXT,
          axis TEXT, final_score REAL, gc REAL, ac REAL, at REAL, aa REAL, n INTEGER,
          mean REAL, stddev REAL, win_rate REAL, decisive_win_rate REAL,
          big_win_rate REAL, catastrophic_loss_rate REAL, sim_version TEXT,
          derived_at TEXT, role_line_means TEXT,
          PRIMARY KEY (civ_name,unit_slug,scale,axis));
    """)
    c.execute("INSERT INTO pool_scores VALUES ('Franks','knight','stable','30v30','hp',"
              "90,1,1,1,1,10,90,1,0.5,0.3,0.2,0.1,'x','2026','{}')")
    c.commit(); c.close()

    cpu_json = str(tmp_path / "civ_power_units.json")
    with open(cpu_json, "w") as f:
        json.dump({"Franks": {"imperial": {}}}, f)
    cpu_dir = str(tmp_path / "civ_power_units")
    patches = str(tmp_path / "patches.db")

    import migrate_baseline
    migrate_baseline.run(derived_db=dd, pool_db=ps, cpu_json=cpu_json,
                         cpu_dir=cpu_dir, patches_db=patches,
                         baseline_build="170934", release_date="2026-04-01",
                         source_url="http://x", summary_md="baseline")

    bc = sqlite3.connect(dd)
    cols = {r[1] for r in bc.execute("PRAGMA table_info(battle_scores)")}
    assert "build_number" in cols
    assert bc.execute("SELECT build_number FROM battle_scores").fetchone()[0] == "170934"
    bc.close()
    assert os.path.exists(os.path.join(cpu_dir, "170934.json"))
    import patches_db
    assert patches_db.get_current_build(patches_db_path=patches) == "170934"

    # Idempotent: second run does not raise and keeps one row
    migrate_baseline.run(derived_db=dd, pool_db=ps, cpu_json=cpu_json,
                         cpu_dir=cpu_dir, patches_db=patches,
                         baseline_build="170934", release_date="2026-04-01",
                         source_url="http://x", summary_md="baseline")
    bc = sqlite3.connect(dd)
    assert bc.execute("SELECT COUNT(*) FROM battle_scores").fetchone()[0] == 1
    bc.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_versioning.py::test_migrate_baseline_tags_and_rebuilds -v`
Expected: FAIL — `migrate_baseline` missing.

- [ ] **Step 3: Create `webapp/migrate_baseline.py`**

```python
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
    if os.path.exists(derived_db):
        c = sqlite3.connect(derived_db); _rebuild_battle_scores(c, baseline_build); c.close()
    if os.path.exists(pool_db):
        c = sqlite3.connect(pool_db); _rebuild_pool_scores(c, baseline_build); c.close()

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
```

> The `run()` parameter is named `patches_db` (a path) to match the test's `patches_db=patches` call site; the module aliases the import as `_patches_db` so there is no shadowing.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_versioning.py::test_migrate_baseline_tags_and_rebuilds -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/migrate_baseline.py tests/test_versioning.py
git commit -m "feat(patches): one-time baseline migration (tag existing data as 170934, rebuild schemas)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `app.py` read paths resolve current build

**Files:**
- Modify: `webapp/app.py` (path constants + `/api/ref/unit-line` battle_scores + pool_scores reads; civ-power-units load)
- Test: `tests/test_patch_routes.py` (smoke — exists after Task 12; here just wire constants)

- [ ] **Step 1: Add DB path constants + current-build helper**

After line 68 in `app.py`:
```python
PATCHES_DB_PATH = os.path.join(os.path.dirname(__file__), "patches.db")
```
Add an import with the other webapp imports:
```python
from patches_db import get_current_build
```
Add a request-time helper near `get_derived_db` (after line 98):
```python
def current_build():
    """Resolve the live build once per call (None if patches.db absent)."""
    return get_current_build(patches_db_path=PATCHES_DB_PATH)
```

- [ ] **Step 2: Build-filter the battle_scores read in `/api/ref/unit-line`**

Replace the derived query (lines 741-744) so it filters by current build when known:
```python
        derived_conn = get_derived_db()
        placeholders = ",".join("?" for _ in _score_line_slugs)
        _bld = current_build()
        if _bld:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value "
                f"FROM battle_scores WHERE line_slug IN ({placeholders}) "
                f"AND build_number = ?",
                _score_line_slugs + [_bld],
            ).fetchall()
        else:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value "
                f"FROM battle_scores WHERE line_slug IN ({placeholders})",
                _score_line_slugs,
            ).fetchall()
        derived_conn.close()
```

- [ ] **Step 3: Build-filter the pool_scores read**

Change line 976 to pass the build:
```python
    pool_scores_by_unit = load_pool_scores(pool_scores_db_path, all_unit_pairs,
                                           build_number=current_build())
```

- [ ] **Step 4: Build-filter the civ-power-units load**

Change line 1051 (`api_civ_power_units`):
```python
    data = load_civ_power_units(build_number=current_build())
```
(`load_civ_power_units` already resolves current build itself, but passing it keeps a single source of truth and avoids a double read.)

- [ ] **Step 5: Verify the app imports and routes still respond**

Run:
```bash
cd /d/AI/aoe2-unit-analyzer && PORT=5099 python webapp/app.py &
sleep 4
curl -s localhost:5099/api/ref/unit-line/knight | head -c 200
curl -s "localhost:5099/api/civ-power-units/Franks?age=imperial" | head -c 200
kill %1
```
Expected: both return JSON (not 500). (Pre-migration, `current_build()` returns None and queries fall back to unfiltered — still returns data.)

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py
git commit -m "feat(patches): app reads resolve current build for rankings + advisor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## PHASE 2 — Patch diff engine

### Task 7: `ref_diff.py` — diff `ref_units` (prev vs new)

Produces per-(civ,slug) stat deltas (for `patch_unit_changes`) and the union changed-slug set (for `--changed-units`). Diffs `aoe2_reference.db` snapshots — the right granularity (civ × slug × age, with both base and final stats), avoiding fragile unit-id→slug mapping.

**Files:**
- Create: `webapp/ref_diff.py`
- Test: `tests/test_ref_diff.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ref_diff.py
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import ref_diff


def _mk(path, rows):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE ref_units (civ_name TEXT, unit_slug TEXT, age TEXT, "
              "base_hp REAL, base_attack REAL, base_cost_food REAL, base_cost_wood REAL, "
              "base_cost_gold REAL, base_train_time REAL)")
    c.executemany("INSERT INTO ref_units VALUES (?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()


def test_diff_detects_changed_fields(tmp_path):
    prev = str(tmp_path / "prev.db"); new = str(tmp_path / "new.db")
    _mk(prev, [("Wei", "tiger_cavalry_wei", "Imperial", 115, 12, 70, 0, 90, 15)])
    _mk(new,  [("Wei", "tiger_cavalry_wei", "Imperial", 110, 12, 70, 0, 90, 18)])
    deltas, changed_slugs = ref_diff.diff(prev, new)
    fields = {(d["civ_name"], d["unit_slug"], d["field"]): (d["old_value"], d["new_value"])
              for d in deltas}
    assert fields[("Wei", "tiger_cavalry_wei", "base_hp")] == (115, 110)
    assert fields[("Wei", "tiger_cavalry_wei", "base_train_time")] == (15, 18)
    assert "tiger_cavalry_wei" in changed_slugs


def test_diff_no_change(tmp_path):
    prev = str(tmp_path / "p.db"); new = str(tmp_path / "n.db")
    _mk(prev, [("Franks", "knight", "Imperial", 100, 10, 60, 0, 75, 30)])
    _mk(new,  [("Franks", "knight", "Imperial", 100, 10, 60, 0, 75, 30)])
    deltas, changed_slugs = ref_diff.diff(prev, new)
    assert deltas == [] and changed_slugs == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ref_diff.py -v`
Expected: FAIL — `ref_diff` missing.

- [ ] **Step 3: Create `webapp/ref_diff.py`**

```python
"""Diff two aoe2_reference.db snapshots (prev vs new) at ref_units granularity.

Returns (deltas, changed_slugs):
  deltas        list of {civ_name, unit_slug, field, old_value, new_value}
  changed_slugs set of unit_slug whose stats changed for ANY civ (feeds the
                run_matchup_battles --changed-units incremental re-sim).
"""
import sqlite3

# Numeric ref_units columns whose change is a real game/balance change worth
# recording. base_* = raw .dat change; final_* would also catch tech/bonus
# shifts but we report base_* for clean "the game changed X" attribution.
DIFF_FIELDS = [
    "base_hp", "base_attack", "base_melee_armor", "base_pierce_armor",
    "base_range", "base_reload_time", "base_speed",
    "base_cost_food", "base_cost_wood", "base_cost_gold", "base_train_time",
]


def _load(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ref_units)")}
    fields = [f for f in DIFF_FIELDS if f in cols]
    rows = conn.execute(
        f"SELECT civ_name, unit_slug, age, {', '.join(fields)} FROM ref_units"
    ).fetchall()
    conn.close()
    out = {}
    for r in rows:
        out[(r["civ_name"], r["unit_slug"], r["age"])] = dict(r)
    return out, fields


def diff(prev_path, new_path):
    prev, pfields = _load(prev_path)
    new, nfields = _load(new_path)
    fields = [f for f in DIFF_FIELDS if f in pfields and f in nfields]
    deltas = []
    changed_slugs = set()
    for key, nrow in new.items():
        prow = prev.get(key)
        if prow is None:
            continue  # new unit/availability handled via notes, not stat diff
        civ, slug, _age = key
        for f in fields:
            ov, nv = prow.get(f), nrow.get(f)
            if ov is None and nv is None:
                continue
            if ov != nv:
                deltas.append({"civ_name": civ, "unit_slug": slug, "field": f,
                               "old_value": ov, "new_value": nv})
                changed_slugs.add(slug)
    # de-dup standard-unit deltas that repeat identically across civs is left to
    # the caller's display layer; changed_slugs is already a set.
    return deltas, changed_slugs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ref_diff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/ref_diff.py tests/test_ref_diff.py
git commit -m "feat(patches): ref_units diff engine (stat deltas + changed-slug set)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `--force` flag for `run_matchup_battles.py`

After a stat-only patch, `sim_version` is unchanged, so the version-skip would refuse to re-sim changed units. `--force` makes the pending-set ignore `has_row_with_version` (the upsert in `insert_outcome` then overwrites cleanly).

**Files:**
- Modify: `webapp/run_matchup_battles.py` (argparse + pending-group logic)
- Test: manual (PyPy-only script; logic verified by reading) + a tiny pure-logic test

- [ ] **Step 1: Write a failing pure-logic test**

Extract the skip decision into a testable function so we don't need PyPy in CI.

```python
# tests/test_versioning.py (append)
import importlib


def test_force_marks_all_pending():
    import run_matchup_battles as r  # NOTE: imports under CPython are fine; the
    # PyPy guard runs only in main(), not at import (see Step 3 guard move).
    members = [("A", "x", 0, "B", "y", 0)]
    # has_row=True everywhere; without force -> skip; with force -> pending
    assert r._group_pending(lambda *a: True, members, "30v30", "ver", force=False) is False
    assert r._group_pending(lambda *a: True, members, "30v30", "ver", force=True) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_versioning.py::test_force_marks_all_pending -v`
Expected: FAIL — `_group_pending` missing (and possibly the PyPy guard aborts import).

- [ ] **Step 3: Move the PyPy guard into `main()` and add `_group_pending` + `--force`**

In `run_matchup_battles.py`:

Move the guard (lines 22-29) so it lives at the **top of `main()`** instead of module scope (allows importing the helper under CPython for tests). The first lines of `main()` become:
```python
def main():
    if platform.python_implementation() != "PyPy":
        sys.stderr.write(
            "\nERROR: run_matchup_battles.py requires PyPy 3.\n"
            "  Then run: pypy3 -m webapp.run_matchup_battles\n\n")
        sys.exit(2)
```

Add a module-level helper (above `main`):
```python
def _group_pending(has_row_fn, members, scale_label, sim_version, force=False):
    """Return True if this dedup group must be (re-)simmed.

    force=True bypasses the version-skip (used after a stat-only patch where
    sim_version is unchanged but the unit stats changed)."""
    if force:
        return True
    return not all(
        has_row_fn(m[0], m[1], m[3], m[4], scale_label, sim_version)
        for m in members
    )
```

Add the CLI flag (after line 187):
```python
    parser.add_argument("--force", action="store_true",
                        help="Re-sim matched groups even if a row already exists "
                             "at the current sim_version (use after a stat-only "
                             "patch). Combine with --changed-units.")
```

Replace the pending loop (lines 287-299) with:
```python
    pending_keys = []
    skipped = 0
    for key, members in groups.items():
        scale_label = key[1]
        def _has(a, b, c, d, e, f):
            return has_row_with_version(out_conn, a, b, c, d, e, f)
        if _group_pending(_has, members, scale_label, sim_version, force=args.force):
            pending_keys.append(key)
        else:
            skipped += len(members)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_versioning.py::test_force_marks_all_pending -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/run_matchup_battles.py tests/test_versioning.py
git commit -m "feat(patches): --force re-sim for stat-only patches (sim_version unchanged)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: `matchup_diff.py` — snapshot + diff matchup outcomes

Snapshots `matchup_battles` rows for changed slugs (the "before"), and after the re-sim diffs them to produce `patch_matchup_changes` rows. Also provides the ranking-diff that compares two `battle_scores` build snapshots into `patch_unit_ranking`.

**Files:**
- Create: `webapp/matchup_diff.py`
- Test: `tests/test_matchup_diff.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_matchup_diff.py
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import matchup_diff


def _mk_matchup(path, rows):
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE matchup_battles (my_civ TEXT, my_unit_slug TEXT,
        opp_civ TEXT, opp_unit_slug TEXT, scale TEXT, winner INTEGER,
        team1_hp_pct REAL, team2_hp_pct REAL)""")
    c.executemany("INSERT INTO matchup_battles VALUES (?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()


def test_row_score():
    assert matchup_diff.row_score({"winner": 1, "team1_hp_pct": 0.8, "team2_hp_pct": 0.0}) == 80.0
    assert matchup_diff.row_score({"winner": 2, "team1_hp_pct": 0.0, "team2_hp_pct": 0.5}) == -50.0
    assert matchup_diff.row_score({"winner": 0, "team1_hp_pct": 0.0, "team2_hp_pct": 0.0}) == 0.0


def test_snapshot_and_diff_flip(tmp_path):
    before = str(tmp_path / "before.db")
    after = str(tmp_path / "after.db")
    # BEFORE: Tiger Cav (my) beats Knight (opp), winner=1 score +60
    _mk_matchup(before, [("Wei", "tiger_cavalry_wei", "Franks", "knight", "30v30", 1, 0.6, 0.0)])
    # AFTER: nerfed -> now loses, winner=2 score -20
    _mk_matchup(after, [("Wei", "tiger_cavalry_wei", "Franks", "knight", "30v30", 2, 0.0, 0.2)])
    snap = matchup_diff.snapshot(before, {"tiger_cavalry_wei"})
    changes = matchup_diff.diff_outcomes(snap, after, {"tiger_cavalry_wei"})
    assert len(changes) == 1
    ch = changes[0]
    assert ch["old_winner"] == 1 and ch["new_winner"] == 2
    assert ch["old_score"] == 60.0 and ch["new_score"] == -20.0
    assert ch["swing"] == -80.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_matchup_diff.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Create `webapp/matchup_diff.py`**

```python
"""Snapshot + diff matchup outcomes around a re-sim, and diff ranking snapshots.

row_score mirrors battle_outcome.signed_score but reads a DB row dict, so we can
compute the per-matchup signed score directly from matchup_battles columns.
"""
import sqlite3

_KEY = ("my_civ", "my_unit_slug", "opp_civ", "opp_unit_slug", "scale")


def row_score(row):
    w = row["winner"]
    if w == 0:
        return 0.0
    if w == 1:
        return round(100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"]), 4)
    return round(-100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"]), 4)


def _touches(row, changed_slugs):
    return row["my_unit_slug"] in changed_slugs or row["opp_unit_slug"] in changed_slugs


def snapshot(matchup_db_path, changed_slugs):
    """Capture {key: {winner, score}} for every matchup touching a changed slug."""
    conn = sqlite3.connect(matchup_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, winner, "
        "team1_hp_pct, team2_hp_pct FROM matchup_battles").fetchall()
    conn.close()
    out = {}
    for r in rows:
        if not _touches(r, changed_slugs):
            continue
        key = tuple(r[k] for k in _KEY)
        out[key] = {"winner": r["winner"], "score": row_score(r)}
    return out


def diff_outcomes(before_snapshot, after_db_path, changed_slugs, min_swing=1.0):
    """Compare a before-snapshot with the post-re-sim matchup DB.

    Returns a list of change dicts for matchups whose winner flipped OR whose
    score moved by >= min_swing."""
    conn = sqlite3.connect(after_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, winner, "
        "team1_hp_pct, team2_hp_pct FROM matchup_battles").fetchall()
    conn.close()
    changes = []
    for r in rows:
        if not _touches(r, changed_slugs):
            continue
        key = tuple(r[k] for k in _KEY)
        before = before_snapshot.get(key)
        if before is None:
            continue
        new_score = row_score(r)
        swing = round(new_score - before["score"], 4)
        if r["winner"] == before["winner"] and abs(swing) < min_swing:
            continue
        changes.append({
            "my_civ": r["my_civ"], "my_unit_slug": r["my_unit_slug"],
            "opp_civ": r["opp_civ"], "opp_unit_slug": r["opp_unit_slug"],
            "scale": r["scale"],
            "old_winner": before["winner"], "new_winner": r["winner"],
            "old_score": before["score"], "new_score": new_score, "swing": swing,
        })
    return changes


def diff_rankings(derived_db_path, old_build, new_build, changed_slugs):
    """Compare battle_scores between two builds for changed slugs.

    Returns list of {civ_name, unit_slug, score_type, old_score, new_score,
    old_rank, new_rank} for every (civ, slug, score_type) the unit has."""
    conn = sqlite3.connect(derived_db_path)
    conn.row_factory = sqlite3.Row

    def load(build):
        rows = conn.execute(
            "SELECT civ_name, unit_slug, score_type, score_value, rank "
            "FROM battle_scores WHERE build_number=?", (build,)).fetchall()
        return {(r["civ_name"], r["unit_slug"], r["score_type"]):
                (r["score_value"], r["rank"]) for r in rows}

    old = load(old_build)
    new = load(new_build)
    conn.close()
    out = []
    keys = set(old) | set(new)
    for (civ, slug, st) in keys:
        if slug not in changed_slugs:
            continue
        os_, or_ = old.get((civ, slug, st), (None, None))
        ns_, nr_ = new.get((civ, slug, st), (None, None))
        if (os_, or_) == (ns_, nr_):
            continue
        out.append({"civ_name": civ, "unit_slug": slug, "score_type": st,
                    "old_score": os_, "new_score": ns_,
                    "old_rank": or_, "new_rank": nr_})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_matchup_diff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/matchup_diff.py tests/test_matchup_diff.py
git commit -m "feat(patches): matchup + ranking outcome diff helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## PHASE 3 — Pipeline orchestrator

### Task 10: `patch_pipeline.py` — end-to-end orchestrator

Ties Phase 1–2 together. Designed to be run **once per patch** from the repo root. The heavy re-sim step shells out to PyPy. Because some steps (re-extract, re-sim) are environment-heavy and not unit-testable in CI, the orchestration logic is split into small pure functions that ARE tested; the `run()` driver wires them with subprocess calls and prints progress.

**Files:**
- Create: `webapp/patch_pipeline.py`
- Test: `tests/test_versioning.py` (append — test the pure helpers `carry_forward_battle_scores` and `write_patch_records`)

- [ ] **Step 1: Write failing tests for the pure helpers (append)**

```python
def test_carry_forward_battle_scores(tmp_path):
    import sqlite3
    import derived_db, patch_pipeline
    dd = str(tmp_path / "d.db")
    conn = derived_db.create_db(dd)
    # naval row only exists at old build; must be carried to new build
    conn.execute("INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,"
                 "score_type,score_value,rank,median_delta,build_number) VALUES "
                 "('naval','imperial','Britons','galleon','naval_effectiveness',70,1,2,'170934')")
    conn.commit(); conn.close()
    patch_pipeline.carry_forward_battle_scores(dd, "170934", "177723")
    conn = sqlite3.connect(dd)
    n = conn.execute("SELECT COUNT(*) FROM battle_scores WHERE build_number='177723' "
                     "AND unit_slug='galleon'").fetchone()[0]
    conn.close()
    assert n == 1


def test_write_patch_records(tmp_path):
    import patches_db, patch_pipeline
    pdb = str(tmp_path / "p.db")
    conn = patches_db.create_db(pdb)
    pid = patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
        title="Update 177723", summary_md="x", source_url="u",
        baseline_build="170934", is_current=0)
    conn.commit()
    patch_pipeline.write_patch_records(conn, pid,
        unit_changes=[{"civ_name":"Wei","unit_slug":"tiger_cavalry_wei",
                       "field":"base_hp","old_value":115,"new_value":110}],
        ranking_changes=[{"civ_name":"Wei","unit_slug":"tiger_cavalry_wei",
                       "score_type":"stable_effectiveness","old_score":90,"new_score":85,
                       "old_rank":1,"new_rank":4}],
        matchup_changes=[{"my_civ":"Wei","my_unit_slug":"tiger_cavalry_wei",
                       "opp_civ":"Franks","opp_unit_slug":"knight","scale":"30v30",
                       "old_winner":1,"new_winner":2,"old_score":60,"new_score":-20,"swing":-80}])
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM patch_unit_changes WHERE patch_id=?", (pid,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM patch_unit_ranking WHERE patch_id=?", (pid,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM patch_matchup_changes WHERE patch_id=?", (pid,)).fetchone()[0] == 1
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_versioning.py::test_carry_forward_battle_scores tests/test_versioning.py::test_write_patch_records -v`
Expected: FAIL — `patch_pipeline` missing.

- [ ] **Step 3: Create `webapp/patch_pipeline.py`**

```python
"""End-to-end patch pipeline. Run ONCE per new patch from the repo root:

  python -m webapp.patch_pipeline --build 177723 --release-date 2026-06-02 \
      --source-url https://www.ageofempires.com/news/...update-177723/ \
      --summary-file notes_177723.md --pypy /path/to/pypy3 \
      --matchup-db D:/AI/matchup_db.db

Steps:
  1. Archive extracted_data/ and snapshot aoe2_reference.db (the 'before').
  2. Re-extract the new .dat; rebuild ref + main DBs; re-apply surgical patches.
  3. Diff ref_units (before vs after) -> stat deltas + changed-slug set.
  4. Snapshot matchup outcomes for changed slugs (the 'before').
  5. Force re-sim only changed slugs (PyPy run_matchup_battles --force --changed-units).
  6. Diff matchup outcomes -> patch_matchup_changes.
  7. Carry forward prior-build battle_scores; re-derive land rankings + pool +
     civ_power_units at the NEW build (a complete snapshot).
  8. Diff ranking snapshots -> patch_unit_ranking. Insert patches row; flip current.
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys

_WEBAPP = os.path.dirname(__file__)
_ROOT = os.path.dirname(_WEBAPP)
DERIVED_DB = os.path.join(_WEBAPP, "derived_data.db")
POOL_DB = os.path.join(_WEBAPP, "pool_scores.db")
REF_DB = os.path.join(_WEBAPP, "aoe2_reference.db")
PATCHES_DB = os.path.join(_WEBAPP, "patches.db")
EXTRACTED = os.path.join(_ROOT, "extraction", "extracted_data")
EXTRACTED_PREV = os.path.join(_ROOT, "extraction", "extracted_data_prev")
REF_PREV = os.path.join(_WEBAPP, "aoe2_reference_prev.db")


def carry_forward_battle_scores(derived_db_path, old_build, new_build):
    """Copy every old-build battle_scores row to new_build (idempotent).

    Ensures the new build is a COMPLETE snapshot before re-derivation overwrites
    the land rows it owns; naval/siege rows (written by other pipelines and not
    re-derived) survive."""
    conn = sqlite3.connect(derived_db_path)
    conn.execute(
        "INSERT OR REPLACE INTO battle_scores "
        "(line_slug, age, civ_name, unit_slug, score_type, score_value, rank, "
        " median_delta, build_number) "
        "SELECT line_slug, age, civ_name, unit_slug, score_type, score_value, "
        " rank, median_delta, ? FROM battle_scores WHERE build_number=?",
        (new_build, old_build))
    conn.commit(); conn.close()


def write_patch_records(conn, patch_id, *, unit_changes, ranking_changes, matchup_changes):
    for d in unit_changes:
        conn.execute(
            "INSERT INTO patch_unit_changes (patch_id, civ_name, unit_slug, field, "
            "old_value, new_value, note) VALUES (?,?,?,?,?,?,?)",
            (patch_id, d["civ_name"], d["unit_slug"], d["field"],
             d.get("old_value"), d.get("new_value"), d.get("note")))
    for d in ranking_changes:
        conn.execute(
            "INSERT INTO patch_unit_ranking (patch_id, civ_name, unit_slug, "
            "score_type, old_score, new_score, old_rank, new_rank) VALUES (?,?,?,?,?,?,?,?)",
            (patch_id, d["civ_name"], d["unit_slug"], d["score_type"],
             d.get("old_score"), d.get("new_score"), d.get("old_rank"), d.get("new_rank")))
    for d in matchup_changes:
        conn.execute(
            "INSERT INTO patch_matchup_changes (patch_id, my_civ, my_unit_slug, "
            "opp_civ, opp_unit_slug, scale, old_winner, new_winner, old_score, "
            "new_score, swing) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (patch_id, d["my_civ"], d["my_unit_slug"], d["opp_civ"], d["opp_unit_slug"],
             d["scale"], d["old_winner"], d["new_winner"], d["old_score"],
             d["new_score"], d["swing"]))


def _run(cmd, **kw):
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kw)


def run(*, build, release_date, source_url, summary_md, baseline_build,
        pypy, matchup_db):
    import patches_db, ref_diff, matchup_diff

    # 1. Archive + snapshot the 'before'
    if os.path.isdir(EXTRACTED):
        if os.path.isdir(EXTRACTED_PREV):
            shutil.rmtree(EXTRACTED_PREV)
        shutil.copytree(EXTRACTED, EXTRACTED_PREV)
    shutil.copyfile(REF_DB, REF_PREV)
    print("[1/8] Archived extracted_data + aoe2_reference.db (before).")

    # 2. Re-extract + rebuild
    _run([sys.executable, "-m", "extraction.run"], cwd=_ROOT)
    _run([sys.executable, "-m", "analysis.generate_reference"], cwd=_ROOT)
    _run([sys.executable, "-m", "analysis.generate_main_db"], cwd=_ROOT)
    _run([sys.executable, os.path.join("analysis", "patches",
          "patch_mayan_archer_cost.py")], cwd=_ROOT)
    print("[2/8] Re-extracted + rebuilt ref/main DBs.")

    # 3. ref_units diff
    deltas, changed_slugs = ref_diff.diff(REF_PREV, REF_DB)
    print(f"[3/8] {len(deltas)} stat deltas across {len(changed_slugs)} changed slugs:"
          f" {sorted(changed_slugs)}")
    cu_file = os.path.join(_WEBAPP, f"changed_units_{build}.json")
    with open(cu_file, "w") as f:
        json.dump(sorted(changed_slugs), f)

    # 4. Snapshot before-outcomes
    before = matchup_diff.snapshot(matchup_db, changed_slugs)
    print(f"[4/8] Snapshotted {len(before)} before-outcomes.")

    # 5. Force re-sim changed slugs (PyPy)
    _run([pypy, "-m", "webapp.run_matchup_battles", "--force",
          "--changed-units", cu_file, "--db", matchup_db], cwd=_ROOT)
    print("[5/8] Re-sim complete.")

    # 6. Matchup diff
    matchup_changes = matchup_diff.diff_outcomes(before, matchup_db, changed_slugs)
    print(f"[6/8] {len(matchup_changes)} matchup changes.")

    # 7. Carry forward + re-derive at NEW build
    carry_forward_battle_scores(DERIVED_DB, baseline_build, build)
    _run([sys.executable, "-m", "webapp.derive_unit_rankings",
          "--matchup-db", matchup_db, "--build", build], cwd=_ROOT)
    _run([sys.executable, "-m", "webapp.derive_pool_scores",
          "--matchup-db", matchup_db, "--out", POOL_DB, "--build", build], cwd=_ROOT)
    # civ_power_units for the new build (best_units reads current build; set it first)
    pconn = patches_db.create_db(PATCHES_DB)
    pid = patches_db.insert_patch(pconn, build_number=build, release_date=release_date,
        title=f"Update {build}", summary_md=summary_md, source_url=source_url,
        baseline_build=baseline_build, is_current=0, created_at=release_date)
    patches_db.set_current_build(pconn, build)
    pconn.commit(); pconn.close()
    _run([sys.executable, "-c",
          "import sys; sys.path.insert(0, 'webapp'); import best_units; "
          f"best_units.save_civ_power_units('{build}')"], cwd=_ROOT)
    print("[7/8] Re-derived rankings/pool/power-units at new build.")

    # 8. Ranking diff + write records
    ranking_changes = matchup_diff.diff_rankings(DERIVED_DB, baseline_build, build,
                                                 changed_slugs)
    pconn = patches_db.create_db(PATCHES_DB)
    pid = patches_db.patch_id_for(pconn, build)
    # clear any prior run's records for this patch (idempotent re-run)
    for t in ("patch_unit_changes", "patch_unit_ranking", "patch_matchup_changes"):
        pconn.execute(f"DELETE FROM {t} WHERE patch_id=?", (pid,))
    write_patch_records(pconn, pid, unit_changes=deltas,
                        ranking_changes=ranking_changes, matchup_changes=matchup_changes)
    pconn.commit(); pconn.close()
    print(f"[8/8] Wrote patch {build}: {len(deltas)} stat deltas, "
          f"{len(ranking_changes)} ranking moves, {len(matchup_changes)} matchup flips.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--release-date", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--summary-file", required=True,
                   help="Path to a file with the user-pasted relevant patch notes (markdown).")
    p.add_argument("--baseline-build", default=None,
                   help="Defaults to the current build in patches.db.")
    p.add_argument("--pypy", default="pypy3",
                   help="pypy3 executable (default: 'pypy3' on PATH).")
    p.add_argument("--matchup-db", required=True, help="Path to the (local) matchup_db.db.")
    a = p.parse_args()
    import patches_db
    baseline = a.baseline_build or patches_db.get_current_build(patches_db_path=PATCHES_DB)
    with open(a.summary_file, encoding="utf-8") as f:
        summary_md = f.read()
    run(build=a.build, release_date=a.release_date, source_url=a.source_url,
        summary_md=summary_md, baseline_build=baseline, pypy=a.pypy,
        matchup_db=a.matchup_db)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_versioning.py::test_carry_forward_battle_scores tests/test_versioning.py::test_write_patch_records -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/patch_pipeline.py tests/test_versioning.py
git commit -m "feat(patches): patch_pipeline orchestrator (carry-forward snapshot + records)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## PHASE 4 — UI

### Task 11: `/patches` route + `patches.html` (timeline tab)

**Files:**
- Modify: `webapp/app.py` (new routes + a tiny markdown renderer)
- Create: `webapp/templates/patches.html`
- Test: `tests/test_patch_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_patch_routes.py
import os, sys, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))


def _seed_patches(path):
    import patches_db
    conn = patches_db.create_db(path)
    pid = patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
        title="Update 177723", summary_md="**Tiger Cavalry** HP 130 -> 125.",
        source_url="https://example.com/177723", baseline_build="170934", is_current=1)
    conn.execute("INSERT INTO patch_unit_changes (patch_id,civ_name,unit_slug,field,"
                 "old_value,new_value,note) VALUES (?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","base_hp",130,125,None))
    conn.commit(); conn.close()


def test_patches_page(tmp_path, monkeypatch):
    import app
    db = str(tmp_path / "patches.db")
    _seed_patches(db)
    monkeypatch.setattr(app, "PATCHES_DB_PATH", db)
    client = app.app.test_client()
    r = client.get("/patches")
    assert r.status_code == 200
    assert b"Update 177723" in r.data
    assert b"example.com/177723" in r.data


def test_render_markdown_basic():
    import app
    html = app.render_patch_summary("**bold** and [link](http://x)\n- one\n- two")
    assert "<strong>bold</strong>" in html
    assert '<a href="http://x"' in html
    assert "<li>one</li>" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_patch_routes.py -v`
Expected: FAIL — `/patches` route + `render_patch_summary` missing.

- [ ] **Step 3: Add the markdown helper + routes to `app.py`**

Add a tiny, safe markdown renderer (no new dependency) near the other helpers:

```python
import html as _html
import re as _re


def render_patch_summary(md):
    """Minimal, safe markdown -> HTML for user-pasted patch notes.

    Supports: escaping, **bold**, [text](url), `- ` bullet lists, blank-line
    paragraphs. Everything else is escaped plain text."""
    if not md:
        return ""
    md = _html.escape(md)
    out, in_list = [], False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{line[2:].strip()}</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if not line:
            out.append("")
        else:
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    txt = "\n".join(out)
    txt = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt)
    txt = _re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', txt)
    return txt
```

Add the routes (follow the `/units` pattern):
```python
def _patches_conn():
    import sqlite3
    conn = sqlite3.connect(PATCHES_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/patches")
def patches_page():
    if not os.path.exists(PATCHES_DB_PATH):
        return render_template("patches.html", patches=[], active_nav="patches")
    conn = _patches_conn()
    rows = conn.execute("SELECT * FROM patches ORDER BY release_date DESC").fetchall()
    patches = []
    for p in rows:
        chips = conn.execute(
            "SELECT DISTINCT civ_name, unit_slug FROM patch_unit_changes "
            "WHERE patch_id=? ORDER BY civ_name, unit_slug", (p["id"],)).fetchall()
        patches.append({
            "build_number": p["build_number"], "title": p["title"],
            "release_date": p["release_date"], "source_url": p["source_url"],
            "summary_html": render_patch_summary(p["summary_md"]),
            "units": [dict(c) for c in chips],
        })
    conn.close()
    return render_template("patches.html", patches=patches, active_nav="patches")
```

- [ ] **Step 4: Create `webapp/templates/patches.html`**

```html
{% extends "base.html" %}
{% block title %}Patches{% endblock %}
{% block content %}
<style>
  .patch-wrap { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
  .patch-card { background:#1c1f26; border:1px solid #2c313c; border-radius:10px;
    padding:20px 24px; margin-bottom:22px; }
  .patch-head { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  .patch-head h2 { margin:0; font-size:1.3rem; }
  .patch-date { color:#8b93a7; font-size:.9rem; }
  .patch-link { margin-left:auto; font-size:.85rem; }
  .patch-summary p { margin:.4rem 0; line-height:1.5; }
  .patch-summary ul { margin:.4rem 0 .4rem 1.2rem; }
  .unit-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
  .unit-chip { background:#262b35; border:1px solid #39414f; border-radius:999px;
    padding:5px 12px; font-size:.82rem; text-decoration:none; color:#dbe2f0; }
  .unit-chip:hover { background:#313a48; }
  .empty { color:#8b93a7; text-align:center; padding:60px 0; }
</style>
<div class="patch-wrap">
  <h1>Game Patches</h1>
  <p class="patch-date">How each balance update reshaped unit rankings and matchups in our simulator.</p>
  {% if not patches %}
    <div class="empty">No patches recorded yet.</div>
  {% endif %}
  {% for p in patches %}
  <div class="patch-card">
    <div class="patch-head">
      <h2>{{ p.title }}</h2>
      <span class="patch-date">{{ p.release_date }}</span>
      {% if p.source_url %}
      <a class="patch-link" href="{{ p.source_url }}" target="_blank" rel="noopener">Official notes &#8599;</a>
      {% endif %}
    </div>
    <div class="patch-summary">{{ p.summary_html|safe }}</div>
    {% if p.units %}
    <div class="unit-chips">
      {% for u in p.units %}
      <a class="unit-chip" href="/patches/{{ p.build_number }}/{{ u.civ_name }}/{{ u.unit_slug }}">
        {{ u.civ_name }} {{ u.unit_slug.replace('_', ' ') }}
      </a>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endblock %}
```

> Confirm `base.html` defines `{% block content %}` and `{% block title %}`. If the block names differ, match the existing templates (check `index.html`).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_patch_routes.py::test_patches_page tests/test_patch_routes.py::test_render_markdown_basic -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py webapp/templates/patches.html tests/test_patch_routes.py
git commit -m "feat(patches): /patches timeline tab + safe summary renderer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: `/patches/<build>/<civ>/<unit>` per-unit analysis page

**Files:**
- Modify: `webapp/app.py` (new route + deep-link URL builder)
- Create: `webapp/templates/patch_unit.html`
- Test: `tests/test_patch_routes.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
def _seed_unit_detail(path):
    import patches_db
    conn = patches_db.create_db(path)
    pid = patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
        title="Update 177723", summary_md="x", source_url="u",
        baseline_build="170934", is_current=1)
    conn.execute("INSERT INTO patch_unit_changes VALUES (?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","base_hp",130,125,None))
    conn.execute("INSERT INTO patch_unit_ranking VALUES (?,?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","stable_effectiveness",90,85,1,4))
    conn.execute("INSERT INTO patch_matchup_changes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","Franks","knight","30v30",1,2,60,-20,-80))
    conn.commit(); conn.close()


def test_patch_unit_page(tmp_path, monkeypatch):
    import app
    db = str(tmp_path / "patches.db")
    _seed_unit_detail(db)
    monkeypatch.setattr(app, "PATCHES_DB_PATH", db)
    client = app.app.test_client()
    r = client.get("/patches/177723/Wei/tiger_cavalry_wei")
    assert r.status_code == 200
    assert b"tiger" in r.data.lower()
    # deep link to the flipped matchup
    assert b"civ1=Wei" in r.data and b"unit2=knight" in r.data and b"autorun=1" in r.data


def test_deep_link_builder():
    import app
    url = app.battle_sim_deep_link("Wei", "tiger_cavalry_wei", "Franks", "knight", "30v30")
    assert url.startswith("/?")
    assert "civ1=Wei" in url and "unit1=tiger_cavalry_wei" in url
    assert "civ2=Franks" in url and "unit2=knight" in url
    assert "mode=count" in url and "autorun=1" in url
    url3k = app.battle_sim_deep_link("Wei", "tiger_cavalry_wei", "Franks", "knight", "3k")
    assert "mode=resources" in url3k and "resources=3000" in url3k
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_patch_routes.py::test_patch_unit_page tests/test_patch_routes.py::test_deep_link_builder -v`
Expected: FAIL — route + `battle_sim_deep_link` missing.

- [ ] **Step 3: Add the deep-link builder + route to `app.py`**

```python
from urllib.parse import urlencode


def battle_sim_deep_link(my_civ, my_slug, opp_civ, opp_slug, scale,
                         age1="Imperial", age2="Imperial"):
    """Build a Battle Sim URL that pre-loads + auto-runs this exact matchup."""
    params = {"civ1": my_civ, "unit1": my_slug, "civ2": opp_civ, "unit2": opp_slug,
              "age1": age1, "age2": age2, "autorun": "1"}
    if scale == "3k":
        params["mode"] = "resources"; params["resources"] = "3000"
    else:
        params["mode"] = "count"; params["count1"] = "30"; params["count2"] = "30"
    return "/?" + urlencode(params)


@app.route("/patches/<build>/<civ>/<path:unit>")
def patch_unit_page(build, civ, unit):
    if not os.path.exists(PATCHES_DB_PATH):
        abort(404)
    conn = _patches_conn()
    patch = conn.execute("SELECT * FROM patches WHERE build_number=?", (build,)).fetchone()
    if patch is None:
        conn.close(); abort(404)
    pid = patch["id"]
    stat_changes = [dict(r) for r in conn.execute(
        "SELECT field, old_value, new_value, note FROM patch_unit_changes "
        "WHERE patch_id=? AND civ_name=? AND unit_slug=? ORDER BY field",
        (pid, civ, unit)).fetchall()]
    ranking = [dict(r) for r in conn.execute(
        "SELECT score_type, old_score, new_score, old_rank, new_rank "
        "FROM patch_unit_ranking WHERE patch_id=? AND civ_name=? AND unit_slug=? "
        "ORDER BY score_type", (pid, civ, unit)).fetchall()]
    mrows = conn.execute(
        "SELECT * FROM patch_matchup_changes WHERE patch_id=? AND my_civ=? "
        "AND my_unit_slug=? ORDER BY swing", (pid, civ, unit)).fetchall()
    now_beats, now_loses, shifted = [], [], []
    for m in mrows:
        d = dict(m)
        d["link"] = battle_sim_deep_link(m["my_civ"], m["my_unit_slug"],
                                         m["opp_civ"], m["opp_unit_slug"], m["scale"])
        flipped_to_win = m["old_winner"] != 1 and m["new_winner"] == 1
        flipped_to_loss = m["old_winner"] == 1 and m["new_winner"] != 1
        if flipped_to_win:
            now_beats.append(d)
        elif flipped_to_loss:
            now_loses.append(d)
        else:
            shifted.append(d)
    # timeline: this unit across all patches
    timeline = [dict(r) for r in conn.execute(
        "SELECT p.build_number, p.release_date, c.field, c.old_value, c.new_value "
        "FROM patch_unit_changes c JOIN patches p ON p.id=c.patch_id "
        "WHERE c.civ_name=? AND c.unit_slug=? ORDER BY p.release_date",
        (civ, unit)).fetchall()]
    conn.close()
    return render_template("patch_unit.html", build=build, civ=civ, unit=unit,
                           patch=dict(patch), stat_changes=stat_changes, ranking=ranking,
                           now_beats=now_beats, now_loses=now_loses, shifted=shifted,
                           timeline=timeline, active_nav="patches")
```

Ensure `abort` is imported (`from flask import ..., abort`). Check the existing import line and add `abort` if missing.

- [ ] **Step 4: Create `webapp/templates/patch_unit.html`**

```html
{% extends "base.html" %}
{% block title %}{{ civ }} {{ unit.replace('_',' ') }} — {{ patch.title }}{% endblock %}
{% block content %}
<style>
  .pu-wrap { max-width: 920px; margin:0 auto; padding:24px 16px; }
  .pu-wrap h1 { margin-bottom:4px; }
  .pu-sub { color:#8b93a7; margin-bottom:24px; }
  .pu-sec { background:#1c1f26; border:1px solid #2c313c; border-radius:10px;
    padding:18px 22px; margin-bottom:20px; }
  .pu-sec h3 { margin-top:0; }
  table.pu { width:100%; border-collapse:collapse; }
  table.pu td, table.pu th { padding:7px 10px; text-align:left; border-bottom:1px solid #2c313c; }
  .up { color:#5ed18b; } .down { color:#e8736b; }
  .mlist a { color:#7fb2ff; text-decoration:none; }
  .mlist a:hover { text-decoration:underline; }
  .swing { font-variant-numeric: tabular-nums; }
  .back { font-size:.85rem; }
</style>
<div class="pu-wrap">
  <a class="back" href="/patches">&#8592; All patches</a>
  <h1>{{ civ }} {{ unit.replace('_',' ')|title }}</h1>
  <div class="pu-sub">{{ patch.title }} &middot; {{ patch.release_date }}</div>

  <div class="pu-sec">
    <h3>Stat changes</h3>
    {% if stat_changes %}
    <table class="pu"><tr><th>Field</th><th>Before</th><th>After</th></tr>
    {% for s in stat_changes %}
      <tr><td>{{ s.field.replace('base_','').replace('_',' ') }}</td>
        <td>{{ s.old_value }}</td>
        <td class="{{ 'up' if (s.new_value or 0) > (s.old_value or 0) else 'down' }}">
          {{ s.new_value }}{% if s.note %} <em>({{ s.note }})</em>{% endif %}</td></tr>
    {% endfor %}
    </table>
    {% else %}<p>No direct stat changes recorded.</p>{% endif %}
  </div>

  <div class="pu-sec">
    <h3>Ranking move</h3>
    {% if ranking %}
    <table class="pu"><tr><th>Score</th><th>Before</th><th>After</th><th>Rank</th></tr>
    {% for r in ranking %}
      <tr><td>{{ r.score_type.replace('_',' ') }}</td>
        <td>{{ r.old_score }}</td>
        <td class="{{ 'up' if (r.new_score or 0) >= (r.old_score or 0) else 'down' }}">{{ r.new_score }}</td>
        <td>#{{ r.old_rank }} &#8594; #{{ r.new_rank }}</td></tr>
    {% endfor %}
    </table>
    {% else %}<p>Ranking unchanged.</p>{% endif %}
  </div>

  {% macro mtable(items) %}
    <table class="pu mlist"><tr><th>Opponent</th><th>Scale</th><th>Score</th><th>Swing</th><th></th></tr>
    {% for m in items %}
      <tr><td>{{ m.opp_civ }} {{ m.opp_unit_slug.replace('_',' ') }}</td>
        <td>{{ m.scale }}</td>
        <td>{{ m.old_score }} &#8594; {{ m.new_score }}</td>
        <td class="swing {{ 'up' if m.swing >= 0 else 'down' }}">{{ '%+.0f'|format(m.swing) }}</td>
        <td><a href="{{ m.link }}">&#9654; View fight</a></td></tr>
    {% endfor %}
    </table>
  {% endmacro %}

  {% if now_beats %}<div class="pu-sec"><h3>Now beats</h3>{{ mtable(now_beats) }}</div>{% endif %}
  {% if now_loses %}<div class="pu-sec"><h3>Now loses to</h3>{{ mtable(now_loses) }}</div>{% endif %}
  {% if shifted %}<div class="pu-sec"><h3>Shifted margins</h3>{{ mtable(shifted) }}</div>{% endif %}

  {% if timeline|length > 1 %}
  <div class="pu-sec"><h3>Timeline</h3>
    <table class="pu"><tr><th>Patch</th><th>Field</th><th>Change</th></tr>
    {% for t in timeline %}
      <tr><td>{{ t.build_number }}</td><td>{{ t.field.replace('base_','').replace('_',' ') }}</td>
        <td>{{ t.old_value }} &#8594; {{ t.new_value }}</td></tr>
    {% endfor %}
    </table>
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_patch_routes.py -v`
Expected: PASS (all four route tests)

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py webapp/templates/patch_unit.html tests/test_patch_routes.py
git commit -m "feat(patches): per-unit analysis page with matchup flips + deep links

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 13: Add the "Patches" nav tab

**Files:**
- Modify: `webapp/templates/base.html` (nav-links block, after the Replay tab ~line 94)

- [ ] **Step 1: Add the tab**

Insert after the Replay `<a class="nav-tab">...</a>` block (after line 94):
```html
        <a href="/patches" class="nav-tab {% if active_nav == 'patches' %}active{% endif %}">
            <span class="nav-tab-icon">&#128221;</span>
            <span class="nav-tab-label">Patches</span>
            <span class="nav-tab-desc">Update history &amp; impact</span>
        </a>
```

- [ ] **Step 2: Verify the tab renders + highlights**

Run:
```bash
cd /d/AI/aoe2-unit-analyzer && PORT=5099 python webapp/app.py &
sleep 4
curl -s localhost:5099/patches | grep -o 'nav-tab active[^<]*Patches' || curl -s localhost:5099/patches | grep -c 'Patches'
kill %1
```
Expected: the Patches tab appears and is marked `active` on `/patches`.

- [ ] **Step 3: Commit**

```bash
git add webapp/templates/base.html
git commit -m "feat(patches): add Patches nav tab

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: Battle Sim deep-link auto-run + age params

The param parsing already exists in `simulate.js`; extract it into a pure, testable function, add `age1/age2` support, and auto-run when `autorun=1`.

**Files:**
- Create: `webapp/static/js/sim_params.js` (pure parser, browser+node — canonical location)
- Modify: `webapp/templates/simulate.html` (load the script)
- Modify: `webapp/static/js/simulate.js` (use parser; set ages; auto-run)
- Test: `tests/test_sim_params.js`

- [ ] **Step 1: Write the failing test**

```javascript
// tests/test_sim_params.js
const assert = require("assert");
const { readSimParams } = require("../webapp/static/js/sim_params.js");

const p = readSimParams("?civ1=Wei&unit1=tiger_cavalry_wei&civ2=Franks&unit2=knight&mode=count&age1=Imperial&autorun=1");
assert.strictEqual(p.civ1, "Wei");
assert.strictEqual(p.unit1, "tiger_cavalry_wei");
assert.strictEqual(p.civ2, "Franks");
assert.strictEqual(p.unit2, "knight");
assert.strictEqual(p.mode, "count");
assert.strictEqual(p.age1, "Imperial");
assert.strictEqual(p.autorun, true);

const empty = readSimParams("");
assert.strictEqual(empty.civ1, null);
assert.strictEqual(empty.autorun, false);

const r = readSimParams("?civ1=A&unit1=b&civ2=C&unit2=d&mode=resources&resources=3000");
assert.strictEqual(r.mode, "resources");
assert.strictEqual(r.resources, "3000");
console.log("sim_params tests passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_sim_params.js`
Expected: FAIL — cannot find `../webapp/static/js/sim_params.js`.

- [ ] **Step 3: Create `webapp/static/js/sim_params.js`**

```javascript
// Pure deep-link parser for the Battle Sim. Works in the browser and node.
(function (root) {
  function readSimParams(search) {
    const q = new URLSearchParams(search || "");
    const get = (k) => (q.has(k) ? q.get(k) : null);
    return {
      civ1: get("civ1"), unit1: get("unit1"),
      civ2: get("civ2"), unit2: get("unit2"),
      age1: get("age1"), age2: get("age2"),
      mode: get("mode"),
      resources: get("resources"),
      count1: get("count1"), count2: get("count2"),
      autorun: q.get("autorun") === "1",
    };
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { readSimParams };
  } else {
    root.readSimParams = readSimParams;
  }
})(typeof window !== "undefined" ? window : this);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_sim_params.js`
Expected: `sim_params tests passed`

- [ ] **Step 5: Load the parser in `simulate.html`**

Add before the `<script src=".../simulate.js">` tag:
```html
<script src="{{ url_for('static', filename='js/sim_params.js') }}"></script>
```
The canonical file lives at `webapp/static/js/sim_params.js` (served by Flask static) and the node test requires that same path — single source, no copy.

- [ ] **Step 6: Wire ages + auto-run into `simulate.js`**

In the existing param-handling block (~lines 2416–2467), replace the manual `URLSearchParams` parsing with `readSimParams(window.location.search)`, and:
- Before `selectCiv(1, civ1)`, if `params.age1` set: `setTeamAge(1, params.age1)`. Same for team 2 with `age2`.
- After both teams' selections complete (the existing code that calls `selectUnit`), add:
```javascript
  if (params.autorun && teamState[1].unitSlug && teamState[2].unitSlug) {
    // selections are in place; kick off the battle
    await startBattle();
  }
```
Make sure the enclosing init runs in an `async` context (the existing block already `await`s `selectCiv`). Keep the existing `mode`/`resources`/`count1`/`count2` handling.

- [ ] **Step 7: Manual verification**

Run:
```bash
cd /d/AI/aoe2-unit-analyzer && PORT=5099 python webapp/app.py &
sleep 4
curl -s "localhost:5099/?civ1=Franks&unit1=knight&civ2=Byzantines&unit2=cataphract_byzantines&mode=count&autorun=1" | grep -c sim_params.js
kill %1
```
Expected: returns `1` (the script tag is present). Then load the URL in a browser and confirm both teams preload and the battle auto-starts.

- [ ] **Step 8: Commit**

```bash
git add webapp/static/js/sim_params.js webapp/templates/simulate.html webapp/static/js/simulate.js tests/test_sim_params.js
git commit -m "feat(patches): Battle Sim deep-link auto-run + age params

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## PHASE 5 — Populate the first real patch (177723)

### Task 15: Run the baseline migration + 177723 pipeline; verify; commit data

This is an **operational** task (not TDD). It produces the committed data the deployed site serves.

- [ ] **Step 1: Save the user-pasted 177723 notes (well-formatted markdown)**

Create `webapp/patch_notes/177723.md` from the balance-change text the user pasted earlier
in this project (the Update 177723 relevant changes), formatted cleanly as markdown:
group by civ/unit with `## headings` and `- ` bullets, keep each change as a concise
before→after line (e.g. `- **Tiger Cavalry** HP 130 -> 125; train 15 -> 18s`). This is the
text rendered on the patch card by `render_patch_summary`. Per the IP constraint, this is the
**user's summary** (not the official notes verbatim); the card also links to `--source-url`.
The renderer supports `**bold**`, `[text](url)` links, `- ` bullets, and paragraphs.

- [ ] **Step 2: Run the baseline migration (tag current data as 170934)**

```bash
cd /d/AI/aoe2-unit-analyzer
python webapp/migrate_baseline.py --build 170934 --release-date 2026-04-01 \
  --source-url "https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-170934/" \
  --summary "Baseline snapshot captured before patch tracking began."
```
Verify: `python -c "import sys; sys.path.insert(0,'webapp'); import patches_db; print(patches_db.get_current_build())"` prints `170934`; `webapp/civ_power_units/170934.json` exists.

- [ ] **Step 3: Smoke-test the app on the migrated baseline**

```bash
PORT=5099 python webapp/app.py &
sleep 4
curl -s localhost:5099/api/ref/unit-line/knight | head -c 120     # rankings still populated
curl -s "localhost:5099/api/civ-power-units/Franks?age=imperial" | head -c 120
curl -s localhost:5099/patches | grep -c "170934"
kill %1
```
Expected: rankings + advisor return data; `/patches` shows the 170934 baseline card.

- [ ] **Step 4: Run the 177723 pipeline**

> The `.dat` already in `extraction/empires2_x2_p1.dat` is build 177723. The real matchup DB is the LOCAL `D:\AI\matchup_db.db`. `pypy3` is on PATH (PyPy 7.3.20 / Python 3.11.13), so `--pypy` can be omitted.

```bash
cd /d/AI/aoe2-unit-analyzer
python -m webapp.patch_pipeline --build 177723 --release-date 2026-06-02 \
  --source-url "https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-177723/" \
  --summary-file webapp/patch_notes/177723.md \
  --matchup-db "D:/AI/matchup_db.db"
```
Watch the `[3/8]` line: confirm the changed-slug set matches the known 177723 combat changes (tiger_cavalry_wei + elite, temple_guard/guecha for Muisca, blackwood_archer_tupi, composite_bowman_armenians + elite, slinger, champi line, xolotl, kamayuk). Cross-check against the pasted notes; investigate any unit in the notes that's missing from the diff (e.g., availability-only changes like "gains Siege Ram" won't appear as a stat delta — add a manual `note` row if desired).

- [ ] **Step 5: Verify the per-unit page + deep links**

```bash
PORT=5099 python webapp/app.py &
sleep 4
curl -s localhost:5099/patches | grep -c "177723"
curl -s localhost:5099/patches/177723/Wei/tiger_cavalry_wei | grep -c "View fight"
curl -s "localhost:5099/api/ref/unit-line/knight" | python -c "import sys,json; d=json.load(sys.stdin); print('ok')"
kill %1
```
Expected: 177723 card present; per-unit page renders matchup-flip deep links; rankings now reflect build 177723 (current).
Open `/patches/177723/Wei/tiger_cavalry_wei` in a browser, click a "View fight" link, confirm the Battle Sim auto-runs.

- [ ] **Step 6: Run the full test suite**

Run: `pytest && node tests/test_sim_params.js && node tests/test_frontend_projectile_miss.js`
Expected: all green.

- [ ] **Step 7: Commit the data + clean up**

```bash
cd /d/AI/aoe2-unit-analyzer
# Committed data artifacts (NOT matchup_db.db):
git add webapp/patches.db webapp/derived_data.db webapp/pool_scores.db \
        webapp/civ_power_units/ webapp/patch_notes/177723.md \
        extraction/extracted_data webapp/aoe2_reference.db webapp/aoe2_units.db
git status   # confirm matchup_db.db / matchup_db.db are NOT staged
git commit -m "data(patches): baseline 170934 + first tracked patch 177723

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
Then remove transient files: `webapp/changed_units_177723.json`, `webapp/aoe2_reference_prev.db`, `extraction/extracted_data_prev/` (or add them to `.gitignore`).

- [ ] **Step 8: Push to staging, ask the user to verify on the staging URL before promoting**

```bash
git push origin staging
```
Tell the user: staging is updated; please verify the Patches tab + a per-unit page + a deep-link fight on the staging URL before we promote to `main`.

---

## Self-Review notes (spec coverage)

- **Readable patch log** → Task 11 (`/patches`, summary + official link). **Impact analysis** → Tasks 9, 12 (stat deltas, ranking move, matchup flips). **Timeline** → Task 12 (timeline strip; cross-patch via `patch_unit_changes`). **Deep links** → Tasks 12 + 14.
- **Result-DB versioning** → Tasks 1–3, 6 (`build_number`, current-build reads). **Baseline migration** → Task 5. **patches.db** → Task 4. **Pipeline** → Tasks 7–10. **Nav tab** → Task 13. **Populate 177723** → Task 15.
- **Refinements vs spec (intentional):** (a) `patch_unit_ranking` keys on `score_type` (not `scale`) — that's what `battle_scores` actually stores; per-`scale` lives in `patch_matchup_changes`. (b) The diff engine reads `ref_units` snapshots (prev vs new) instead of `units.json`, giving civ×slug granularity and avoiding unit-id→slug mapping; `extracted_data_prev/` is still archived as a safety net. (c) New build snapshots **carry forward** non-re-derived rows (naval/siege) so each build is complete. (d) Deep-link param parsing already existed in `simulate.js`; Task 14 only adds `age1/age2` + `autorun`.
- **Out of scope (unchanged from spec):** versioning the stat-source DBs for historical fight replay; back-filling pre-170934 patches; live on-request re-sim; auto-fetching official notes.
```