# Simulation V3 Unit Rankings Staging Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the completed Simulation V3 land-unit campaign as the single cost-based rankings source on staging while retaining retail Siege, Naval, and Matchup Advisor candidate data.

**Architecture:** Build a new same-schema `derived_data_v3.db` from an explicit union of V3 land scores and retail Siege/Naval scores, then route rankings, SEO unit pages, and civilization power generation to that artifact. Keep Matchup Advisor candidate selection on `derived_data.db`, simplify the rankings UI to one score model, regenerate the committed power-unit JSON, and fast-forward the result into `staging` without touching `main`.

**Tech Stack:** Python 3.11, SQLite, Flask/Jinja, browser JavaScript/CSS, pytest, Node syntax checking, Git/GitHub Actions, Railway staging auto-deploy.

**Spec:** `docs/superpowers/specs/2026-09-03-v3-rankings-staging-cutover-design.md`

## Global Constraints

- Target staging only; do not push or merge to `main` and do not perform a production database write or production deployment.
- Use AoE2 build number `177723`; engine identity stays in metadata rather than a fabricated game build.
- V3 resource weights are food `1`, wood `1`, and gold `1`; the unit cap is `27`.
- Publish exactly the accepted V3 source snapshot: 755 variants total, 4,530 matchups, 22,650 runs, 15,855 score rows, five runs per matchup, six yardsticks per variant, and zero failures.
- Publish V3 score rows only for stages `infantry`, `archery`, and `cavalry`; do not publish V3 `v3_combat_effectiveness` Siege rows.
- Keep Mangonel stat-only and keep retail Siege/Naval ranking semantics.
- Rankings, SEO unit-line pages, and civilization power units use `derived_data_v3.db`; Matchup Advisor candidate selection uses `derived_data.db`.
- Remove the Pop/Cost/Average ranking-scale UI and all rankings-page reads from `pool_scores.db`.
- Keep one visually uniform table and do not add legacy-source badges for Siege/Naval.
- Preserve all current staging changes by working from and reintegrating with `origin/staging`.
- Keep the implementation narrow; no full advisor-corpus generation, simulation-engine changes, or unrelated UI redesign.

## File Structure

### Create

- `aoe2x/rank/build_v3_serving_db.py` — deterministic builder and validation for the hybrid serving artifact and provenance manifest.
- `tests/test_build_v3_serving_db.py` — synthetic SQLite tests for V3 selection, retail allowlists, ranks, validation, and metadata.
- `tests/test_v3_rankings_api.py` — API/SSR tests for explicit final-score routing and V3 breakdowns.
- `tests/test_best_units_v3_routing.py` — tests that civilization power and advisor candidates open different derived databases.
- `tests/test_v3_rankings_ui.py` — template/JavaScript contract tests for the single-score uniform table.
- `data/golden/derived_data_v3.db` — committed hybrid serving database.
- `data/golden/derived_data_v3.metadata.json` — committed source and validation manifest.

### Modify

- `apps/website/app.py` — rankings DB connector, score mapping, generic ranking payload, SEO/overview score use, and removal of pool-score attachment.
- `apps/website/templates/rankings.html` — remove scale controls and update methodology copy.
- `apps/website/static/js/rankings.js` — single-score table, V3 breakdown disclosure, unified columns, sorting, and CSV.
- `apps/website/static/css/rankings.css` — remove scale/pool styles and style the compact breakdown disclosure.
- `aoe2x/advisor/best_units.py` — split rankings/advisor connectors and remove the pool-score percentile preference.
- `data/golden/civ_power_units/177723.json` — regenerate from the hybrid V3 serving artifact.
- `tests/test_seo_phase2.py` — update SSR expectations from two-scale Average to equal-resource scoring.
- `tests/test_naval_rankings.py` — route its temporary score fixture through the rankings DB path without mutating the retail artifact.

### Remove

- `tests/test_pool_scores_api.py` — superseded by `tests/test_v3_rankings_api.py`; pool payload attachment is no longer a rankings contract.

---

### Task 1: Build and validate the hybrid V3 serving database

**Files:**

- Create: `aoe2x/rank/build_v3_serving_db.py`
- Create: `tests/test_build_v3_serving_db.py`
- Reuse: `aoe2x/rank/derived_db.py`

**Interfaces:**

- Consumes: V3 campaign SQLite path, retail derived SQLite path, output SQLite path, metadata JSON path, and game build string.
- Produces: `build_serving_db(v3_db_path: str, retail_db_path: str, output_db_path: str, metadata_path: str, build_number: str = "177723", expected_summary: dict[str, int] | None = None) -> dict[str, object]`.
- Produces: CLI `python -m aoe2x.rank.build_v3_serving_db --v3-db ... --retail-db ... --output-db ... --metadata ... --build-number 177723`.

- [ ] **Step 1: Write failing tests for source validation and selection**

Create SQLite fixtures with the real V3 table column names and assert the
builder rejects failed/incomplete input before writing output:

```python
def test_rejects_campaign_failures(tmp_path):
    v3 = make_v3_fixture(tmp_path / "v3.db", failures=1)
    retail = make_retail_fixture(tmp_path / "retail.db")
    with pytest.raises(ValueError, match="campaign failures"):
        build_serving_db(
            str(v3), str(retail), str(tmp_path / "out.db"),
            str(tmp_path / "out.metadata.json"),
            expected_summary={"failures": 1, "matchups": 18, "runs": 90, "scores": 63},
        )


def test_rejects_wrong_resource_weights(tmp_path):
    v3 = make_v3_fixture(tmp_path / "v3.db", resource_weights={"food": 1, "wood": 1, "gold": 1.5})
    retail = make_retail_fixture(tmp_path / "retail.db")
    with pytest.raises(ValueError, match="resource_weights"):
        build_serving_db(
            str(v3), str(retail), str(tmp_path / "out.db"),
            str(tmp_path / "out.metadata.json"), expected_summary=fixture_summary(),
        )
```

The fixture must include `campaign_metadata`, `campaign_failures`,
`ranking_matchups`, `ranking_runs`, and V3 `battle_scores`, including one row
for each land stage and one Siege row that must be excluded.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
pytest -q tests/test_build_v3_serving_db.py
```

Expected: collection fails because `aoe2x.rank.build_v3_serving_db` does not
exist.

- [ ] **Step 3: Define the exact source and retention allowlists**

Add these constants to the new module:

```python
BUILD_NUMBER = "177723"
EXPECTED_SOURCE_SUMMARY = {
    "failures": 0,
    "matchups": 4530,
    "runs": 22650,
    "scores": 15855,
}
EXPECTED_V3_LAND_VARIANTS = 522
EXPECTED_V3_LAND_SCORE_ROWS = 10962
EXPECTED_RETAIL_ROWS_BY_LINE = {
    "ram": 1378,
    "trebuchet": 650,
    "bombard_cannon": 364,
    "cannon_galleon": 637,
    "galleon": 1120,
    "fire": 1060,
    "hulk": 1080,
}
EXPECTED_PUBLISHED_ROWS = 17251
V3_STAGES = ("infantry", "archery", "cavalry")
V3_FINAL_SCORE_BY_STAGE = {
    "infantry": "militia_value",
    "archery": "ranged_effectiveness",
    "cavalry": "stable_effectiveness",
}
V3_COMMON_SCORE_TYPES = {
    "general_combat", "anti_cav", "anti_archer", "anti_trash",
    "aa_v3_27_vs_arb", "aa_v3_27_vs_arb_raw",
    "ac_v3_27_vs_paladin", "ac_v3_27_vs_paladin_raw",
    "at_v3_27_vs_elite_skirm", "at_v3_27_vs_elite_skirm_raw",
    "at_v3_27_vs_halb", "at_v3_27_vs_halb_raw",
    "at_v3_27_vs_hussar", "at_v3_27_vs_hussar_raw",
    "gc_v3_27_vs_arb", "gc_v3_27_vs_arb_raw",
    "gc_v3_27_vs_champ", "gc_v3_27_vs_champ_raw",
    "gc_v3_27_vs_paladin", "gc_v3_27_vs_paladin_raw",
}
SIEGE_LINES = {"ram", "trebuchet", "bombard_cannon", "cannon_galleon"}
SIEGE_SCORE_TYPES = {"anti_building_score"} | {
    f"ab_{target}_{mode}_{measure}"
    for target in ("persian", "teuton", "byzantine")
    for mode in ("5k", "5u")
    for measure in ("dmg", "ttk")
}
NAVAL_LINES = {"galleon", "fire", "hulk"}
NAVAL_SCORE_TYPES = {
    "naval_effectiveness",
    "vs_fire", "vs_fire_30v30", "vs_fire_3k",
    "vs_galleon", "vs_galleon_30v30", "vs_galleon_3k",
    "vs_hulk", "vs_hulk_30v30", "vs_hulk_3k",
}
```

- [ ] **Step 4: Implement metadata decoding and strict V3 validation**

Implement these signatures:

```python
def _load_campaign_metadata(conn: sqlite3.Connection) -> dict[str, object]:
    return {
        row["key"]: json.loads(row["value_json"])
        for row in conn.execute("SELECT key, value_json FROM campaign_metadata")
    }


def _validate_v3_source(
    conn: sqlite3.Connection,
    expected_summary: dict[str, int],
) -> dict[str, object]:
    metadata = _load_campaign_metadata(conn)
    if metadata.get("last_summary") != expected_summary:
        raise ValueError(f"campaign summary mismatch: {metadata.get('last_summary')!r}")
    if conn.execute("SELECT COUNT(*) FROM campaign_failures").fetchone()[0]:
        raise ValueError("campaign failures must be zero")
    if metadata.get("seed_count") != 5:
        raise ValueError("seed_count must be 5")
    if metadata.get("resource_weights") != {"food": 1, "wood": 1, "gold": 1}:
        raise ValueError("resource_weights must be 1:1:1")
    if metadata.get("unit_cap") != 27:
        raise ValueError("unit_cap must be 27")
    return metadata
```

Also validate with SQL that every `ranking_matchups` row has
`resolved_seeds=5` and `failed_seeds=0`, every published land variant has six
distinct opponent pairs, and each land stage contains exactly the common score
types plus its final composite. When `expected_summary` is the production
constant, require 522 land variants, 10,962 land score rows, the exact retained
retail counts above, and 17,251 total published rows.

- [ ] **Step 5: Implement explicit row selection and deterministic rank writing**

Read V3 rows only where `stage_name IN ('infantry','archery','cavalry')` and
retail rows only where both line and score type match the constants above and
`build_number='177723'`. Write the existing serving schema through
`aoe2x.rank.derived_db.create_db()`.

Partition rows by `(line_slug, age, score_type, build_number)`, sort with the
deterministic key `(-score_value, civ_name, unit_slug)`, assign sequential ranks
from one, and compute `median_delta` from the upper-middle sorted score value to
match the current derivation convention:

```python
def _rank_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(row["line_slug"], row["age"], row["score_type"], row["build_number"])].append(row)
    ranked = []
    for entries in groups.values():
        median = sorted(float(row["score_value"]) for row in entries)[len(entries) // 2]
        entries.sort(key=lambda row: (-float(row["score_value"]), row["civ_name"], row["unit_slug"]))
        for rank, row in enumerate(entries, 1):
            ranked.append({**row, "rank": rank, "median_delta": round(float(row["score_value"]) - median, 1)})
    return ranked
```

- [ ] **Step 6: Implement atomic output and manifest writing**

Build the database and JSON beside their destinations under temporary names.
Validate row counts, score-type allowlists, uniqueness, contiguous ranks, and
build number before replacing the destinations with `os.replace()`.

Return and serialize this manifest shape:

```python
manifest = {
    "schema_version": 1,
    "game_build": build_number,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "v3_source": str(Path(v3_db_path).resolve()),
    "retail_source": str(Path(retail_db_path).resolve()),
    "engine_revision": metadata["engine_revision"],
    "mechanics_build": metadata["source_mechanics_build"],
    "seed_count": metadata["seed_count"],
    "resource_weights": metadata["resource_weights"],
    "unit_cap": metadata["unit_cap"],
    "source_summary": metadata["last_summary"],
    "published_stages": list(V3_STAGES),
    "retained_retail_lines": sorted(SIEGE_LINES | NAVAL_LINES),
    "published_rows": len(ranked_rows),
}
```

The output `advisor_recommendations` table remains empty.

- [ ] **Step 7: Add the CLI and run the focused tests GREEN**

Use required `argparse` flags for every path and default only the build number.
Then run:

```powershell
pytest -q tests/test_build_v3_serving_db.py
```

Expected: all builder validation, filtering, rank, and manifest tests pass.

- [ ] **Step 8: Commit Task 1**

```powershell
git add aoe2x/rank/build_v3_serving_db.py tests/test_build_v3_serving_db.py
git commit -m "feat: build hybrid v3 rankings database"
```

---

### Task 2: Generate and certify the committed V3 artifact

**Files:**

- Create: `data/golden/derived_data_v3.db`
- Create: `data/golden/derived_data_v3.metadata.json`
- Test: `tests/test_build_v3_serving_db.py`

**Interfaces:**

- Consumes: the accepted local campaign at `D:/AI/aoe2_matchup/data/local/v3_unit_rankings.db` and staging retail artifact `data/golden/derived_data.db`.
- Produces: the two committed golden artifacts consumed by Tasks 3 and 4.

- [ ] **Step 1: Run the builder against the accepted campaign**

From the isolated staging worktree:

```powershell
Get-FileHash data/golden/derived_data.db -Algorithm SHA256
python -m aoe2x.rank.build_v3_serving_db `
  --v3-db D:/AI/aoe2_matchup/data/local/v3_unit_rankings.db `
  --retail-db data/golden/derived_data.db `
  --output-db data/golden/derived_data_v3.db `
  --metadata data/golden/derived_data_v3.metadata.json `
  --build-number 177723
```

Expected: prints the manifest summary and exits zero after publishing the two
files. Record the retail database hash for the non-mutation check in Step 3.

- [ ] **Step 2: Verify the artifact contract with read-only SQL**

Run:

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/golden/derived_data_v3.db'); print(c.execute('select build_number,count(*) from battle_scores group by build_number').fetchall()); print(c.execute(\"select score_type,count(*) from battle_scores where score_type in ('militia_value','ranged_effectiveness','stable_effectiveness','anti_building_score','naval_effectiveness') group by score_type order by score_type\").fetchall()); print(c.execute('select count(*) from advisor_recommendations').fetchone()[0])"
```

Expected: only build `177723`, all five final score types present, and zero
advisor recommendation rows. Separately assert no `v3_combat_effectiveness`
row and no `mangonel` score row.

- [ ] **Step 3: Re-run the builder and prove deterministic content**

Record the SHA-256 of both outputs, rerun the command, and compare the database
hash. The database must remain byte-identical. The manifest may change only in
`generated_at`; compare it after excluding that key. Re-hash
`data/golden/derived_data.db` and confirm it still equals the hash recorded in
Step 1.

```powershell
Get-FileHash data/golden/derived_data_v3.db -Algorithm SHA256
python -m aoe2x.rank.build_v3_serving_db --v3-db D:/AI/aoe2_matchup/data/local/v3_unit_rankings.db --retail-db data/golden/derived_data.db --output-db data/golden/derived_data_v3.db --metadata data/golden/derived_data_v3.metadata.json --build-number 177723
Get-FileHash data/golden/derived_data_v3.db -Algorithm SHA256
```

- [ ] **Step 4: Commit Task 2**

```powershell
git add data/golden/derived_data_v3.db data/golden/derived_data_v3.metadata.json
git commit -m "data: publish v3 unit ranking scores"
```

---

### Task 3: Route rankings and SEO to the V3 artifact

**Files:**

- Modify: `apps/website/app.py:60,130-160,674-703,1709-2045`
- Create: `tests/test_v3_rankings_api.py`
- Remove: `tests/test_pool_scores_api.py`
- Modify: `tests/test_seo_phase2.py`
- Modify: `tests/test_naval_rankings.py`

**Interfaces:**

- Consumes: `data/golden/derived_data_v3.db` and existing `ref_units` data.
- Produces: generic row fields `ranking_score_type: str`, `ranking_score: float`, `ranking_rank: int`, `ranking_median_delta: float`, and optional `ranking_breakdown: dict`.
- Produces: `get_rankings_derived_db() -> sqlite3.Connection`.

- [ ] **Step 1: Write failing API tests for explicit score selection**

Create a temporary same-schema rankings DB, monkeypatch
`app.RANKINGS_DERIVED_DB_PATH`, and use real reference rows. Insert both a high
supporting score and a different final score to prove the final mapping is not
order-dependent:

```python
def test_jaguar_uses_militia_value_and_v3_breakdown(client, monkeypatch, tmp_path):
    db_path = make_rankings_db(tmp_path / "rankings.db", [
        score("militia", "Aztecs", "elite_jaguar_warrior_aztecs", "general_combat", 99.0, 1, 49.0),
        score("militia", "Aztecs", "elite_jaguar_warrior_aztecs", "militia_value", 71.5, 4, 8.2),
        score("militia", "Aztecs", "elite_jaguar_warrior_aztecs", "gc_v3_27_vs_champ", 88.0, 2, 12.0),
    ])
    monkeypatch.setattr(app, "RANKINGS_DERIVED_DB_PATH", str(db_path))
    payload = client.get("/api/ref/unit-line/militia").get_json()
    jaguar = find(payload["imperial"], "Aztecs", "elite_jaguar_warrior_aztecs")
    assert jaguar["ranking_score_type"] == "militia_value"
    assert jaguar["ranking_score"] == 71.5
    assert jaguar["ranking_rank"] == 4
    assert jaguar["ranking_median_delta"] == 8.2
    assert jaguar["ranking_breakdown"]["yardsticks"][0] == {
        "key": "champion", "label": "Champion", "score": 88.0,
    }
    assert "pool_scores" not in jaguar
```

Add parallel assertions for one Paladin (`stable_effectiveness`), one
Arbalester (`ranged_effectiveness`), one Trebuchet (`anti_building_score`), and
one Galleon (`naval_effectiveness`). Assert Mangonel has no generic score.

- [ ] **Step 2: Run the new API/SEO tests and confirm RED**

```powershell
pytest -q tests/test_v3_rankings_api.py tests/test_seo_phase2.py tests/test_naval_rankings.py
```

Expected: V3 routing/generic ranking assertions fail against the retail and
pool-score implementation.

- [ ] **Step 3: Add the rankings connector and exact line mapping**

In `apps/website/app.py`, remove the `load_pool_scores` import and add:

```python
RETAIL_DERIVED_DB_PATH = os.path.join(str(_GOLDEN_DIR), "derived_data.db")
RANKINGS_DERIVED_DB_PATH = os.path.join(str(_GOLDEN_DIR), "derived_data_v3.db")

FINAL_SCORE_TYPE_BY_LINE = {
    "militia": "militia_value", "spear": "militia_value", "shock_infantry": "militia_value",
    "archer": "ranged_effectiveness", "skirmisher": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness", "scorpion": "ranged_effectiveness",
    "gunpowder": "ranged_effectiveness",
    "knight": "stable_effectiveness", "light_cav": "stable_effectiveness",
    "camel": "stable_effectiveness", "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
    "ram": "anti_building_score", "trebuchet": "anti_building_score",
    "bombard_cannon": "anti_building_score", "cannon_galleon": "anti_building_score",
    "galleon": "naval_effectiveness", "fire": "naval_effectiveness",
    "hulk": "naval_effectiveness",
}


def get_rankings_derived_db():
    conn = sqlite3.connect(RANKINGS_DERIVED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

- [ ] **Step 4: Attach generic score and breakdown fields**

Change the `battle_scores` query to include `rank` and `median_delta`, store the
full score-row payload per unit, retain the scalar score-type keys for existing
hover behavior, and attach the final generic fields from the unit's concrete
`sub_slug`:

```python
final_type = FINAL_SCORE_TYPE_BY_LINE.get(sub_slug)
final_row = score_rows.get(final_type) if final_type else None
if final_row:
    entry["ranking_score_type"] = final_type
    entry["ranking_score"] = final_row["score_value"]
    entry["ranking_rank"] = final_row["rank"]
    entry["ranking_median_delta"] = final_row["median_delta"]
```

For V3 land final types, attach:

```python
entry["ranking_breakdown"] = {
    "roles": {
        "GC": entry.get("general_combat"),
        "AC": entry.get("anti_cav"),
        "AT": entry.get("anti_trash"),
        "AA": entry.get("anti_archer"),
    },
    "yardsticks": [
        {"key": "champion", "label": "Champion", "score": entry.get("gc_v3_27_vs_champ")},
        {"key": "paladin", "label": "Paladin", "score": entry.get("gc_v3_27_vs_paladin")},
        {"key": "arbalester", "label": "Arbalester", "score": entry.get("gc_v3_27_vs_arb")},
        {"key": "halberdier", "label": "Halberdier", "score": entry.get("at_v3_27_vs_halb")},
        {"key": "elite_skirmisher", "label": "Elite Skirmisher", "score": entry.get("at_v3_27_vs_elite_skirm")},
        {"key": "hussar", "label": "Hussar", "score": entry.get("at_v3_27_vs_hussar")},
    ],
}
```

Filter `None` role/yardstick entries before returning JSON. Remove the complete
`pool_scores.db` attachment block.

- [ ] **Step 5: Make SSR and overview use only the generic final score**

Delete `_LINE_PAGE_SCORE_KEYS` and the ordered fallback loop. Use:

```python
def _row_score(row):
    value = row.get("ranking_score")
    return value if isinstance(value, (int, float)) else None


def _ranking_default_score(unit):
    value = unit.get("ranking_score")
    return value if isinstance(value, (int, float)) else None
```

Update docstrings from Average/two-scale language to current final ranking
score language.

- [ ] **Step 6: Replace obsolete tests and isolate Naval fixtures**

Delete `tests/test_pool_scores_api.py`. In `tests/test_naval_rankings.py`, build
a temporary `derived_data_v3.db` fixture and monkeypatch
`app.RANKINGS_DERIVED_DB_PATH` rather than modifying the committed retail DB.
Update `tests/test_seo_phase2.py` so the SSR render test asserts
`"equal resources"` and rejects `"30v30"` / `"3,000-resource"` methodology
copy.

- [ ] **Step 7: Run Task 3 tests GREEN**

```powershell
pytest -q tests/test_v3_rankings_api.py tests/test_seo_phase2.py tests/test_seo_unit_line_pages.py tests/test_naval_rankings.py
```

Expected: API, SEO, rankings overview, Siege, Mangonel, and Naval cases pass.

- [ ] **Step 8: Commit Task 3**

```powershell
git add apps/website/app.py tests/test_v3_rankings_api.py tests/test_seo_phase2.py tests/test_naval_rankings.py
git rm tests/test_pool_scores_api.py
git commit -m "feat: serve rankings from v3 data"
```

---

### Task 4: Split civilization-power and advisor database routing

**Files:**

- Modify: `aoe2x/advisor/best_units.py:29-115,785-835,1219-1330,1644-1675`
- Create: `tests/test_best_units_v3_routing.py`
- Modify: `data/golden/civ_power_units/177723.json`

**Interfaces:**

- Consumes: hybrid rankings database for offline civilization power generation and retail database for live advisor candidates.
- Produces: `_get_rankings_derived_db() -> sqlite3.Connection` and `_get_advisor_derived_db() -> sqlite3.Connection`.
- Produces: regenerated `data/golden/civ_power_units/177723.json`.

- [ ] **Step 1: Write failing routing and percentile tests**

```python
def test_rankings_and_advisor_connectors_are_distinct(monkeypatch, tmp_path):
    rankings = make_marker_db(tmp_path / "rankings.db", "v3")
    retail = make_marker_db(tmp_path / "retail.db", "retail")
    monkeypatch.setattr(best_units, "RANKINGS_DERIVED_DB_PATH", str(rankings))
    monkeypatch.setattr(best_units, "ADVISOR_DERIVED_DB_PATH", str(retail))
    assert best_units._get_rankings_derived_db().execute("SELECT value FROM marker").fetchone()[0] == "v3"
    assert best_units._get_advisor_derived_db().execute("SELECT value FROM marker").fetchone()[0] == "retail"


def test_build_unit_entry_uses_v3_rank_percentile_not_pool_override():
    entry = build_minimal_entry(rank=1, line_count=11)
    assert entry["percentile"] == 100.0
```

Add a monkeypatched call-site test proving `compute_civ_power_units()` asks for
the rankings connector and the advisor recommendation path asks for the advisor
connector.

- [ ] **Step 2: Run the routing tests and confirm RED**

```powershell
pytest -q tests/test_best_units_v3_routing.py
```

Expected: the new connector names are missing and the existing implementation
still opens one shared derived path.

- [ ] **Step 3: Introduce explicit connectors and remove pool preference**

Replace the shared constants/helper with:

```python
RANKINGS_DERIVED_DB_PATH = os.path.join(str(_DATA_DIR), "derived_data_v3.db")
ADVISOR_DERIVED_DB_PATH = os.path.join(str(_DATA_DIR), "derived_data.db")


def _connect_derived(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_rankings_derived_db():
    return _connect_derived(RANKINGS_DERIVED_DB_PATH)


def _get_advisor_derived_db():
    return _connect_derived(ADVISOR_DERIVED_DB_PATH)
```

Delete `POOL_SCORES_DB_PATH`, `_line_imperial_slugs()`, and
`_load_pool_score_percentiles()`. Remove the `pool_pct_lookup` parameter and
branch from `_build_unit_entry()` so percentile always derives from V3/retail
`rank` and the line partition count.

- [ ] **Step 4: Route each call site deliberately**

Use `_get_rankings_derived_db()` only inside `compute_civ_power_units()`. Use
`_get_advisor_derived_db()` at the live counter-candidate query around the
existing Step 2 block. Remove all comments and argument plumbing that describe
`pool_scores.db` as the ranking source.

- [ ] **Step 5: Run routing tests GREEN**

```powershell
pytest -q tests/test_best_units_v3_routing.py tests/test_versioning.py
```

Expected: database separation and build-version behavior pass.

- [ ] **Step 6: Regenerate build 177723 civilization power data**

```powershell
python -c "from aoe2x.advisor.best_units import save_civ_power_units; save_civ_power_units('177723')"
```

Expected: writes `data/golden/civ_power_units/177723.json` for all civilizations.

- [ ] **Step 7: Cross-check generated power entries against V3 final rows**

Use a read-only script to compare at least Aztec Jaguar Warrior, Frank Paladin,
Briton Arbalester, one retained Siege entry, and one retained Naval entry. For
each simulated line, JSON `score`, `rank`, `median_delta`, and percentile must
derive from the corresponding final score row in `derived_data_v3.db`.

```powershell
python -c "import json,sqlite3; d=json.load(open('data/golden/civ_power_units/177723.json',encoding='utf-8')); c=sqlite3.connect('data/golden/derived_data_v3.db'); print(d['Aztecs']['imperial']['power_units']['infantry']['militia'][0]['score']); print(c.execute(\"select score_value from battle_scores where build_number='177723' and civ_name='Aztecs' and unit_slug='elite_jaguar_warrior_aztecs' and score_type='militia_value'\").fetchone()[0])"
```

- [ ] **Step 8: Commit Task 4**

```powershell
git add aoe2x/advisor/best_units.py tests/test_best_units_v3_routing.py data/golden/civ_power_units/177723.json
git commit -m "feat: use v3 rankings for civilization power"
```

---

### Task 5: Simplify the rankings UI to one uniform score table

**Files:**

- Modify: `apps/website/templates/rankings.html:12-55`
- Modify: `apps/website/static/js/rankings.js:68-190,905-1205,1205-2100`
- Modify: `apps/website/static/css/rankings.css:45-100,556-730`
- Create: `tests/test_v3_rankings_ui.py`

**Interfaces:**

- Consumes: generic `ranking_*` fields and optional `ranking_breakdown` from Task 3.
- Produces: a shared table with Rank, Civ, Unit, conditional Line, Score, Δ Line, Cost, Breakdown, and Special.
- Produces: CSV with the same single-score semantics.

- [ ] **Step 1: Write failing template and JavaScript contract tests**

```python
def test_rankings_page_describes_one_equal_resource_score(client):
    body = client.get("/units").get_data(as_text=True)
    assert "Equal-resource simulations" in body
    assert "scoreScaleToggle" not in body
    assert "Pop (30v30)" not in body
    assert "Cost (3k)" not in body
    assert "Average" not in body


def test_rankings_javascript_uses_generic_ranking_payload():
    source = Path("apps/website/static/js/rankings.js").read_text(encoding="utf-8")
    for required in ("ranking_score", "ranking_rank", "ranking_median_delta", "ranking_breakdown"):
        assert required in source
    for retired in ("currentScoreScale", "setScoreScale", "getPoolScoreValue", "getPoolLineValue", "pool_scores"):
        assert retired not in source
```

Add an API-render smoke assertion that the page still includes the line tabs,
civilization filter, CSV button, and uniform table container.

- [ ] **Step 2: Run the UI tests and confirm RED**

```powershell
pytest -q tests/test_v3_rankings_ui.py tests/test_seo_phase2.py
```

Expected: current scale controls, Average methodology, and pool-score JavaScript
violate the new contract.

- [ ] **Step 3: Remove scale controls and replace methodology copy**

Delete the `score-toggles` block from `rankings.html`. Replace the SSR intro
with:

```html
<p class="rankings-ssr-intro">
    Land units are ranked from five-run Simulation V3 equal-resource matchups at
    full Imperial upgrades. Food, wood, and gold are weighted 1:1:1, and armies
    are capped at 27 units. Higher scores are stronger.
</p>
```

Keep the existing JSON-LD, line guides, staging V3 page changes, and navigation.

- [ ] **Step 4: Replace pool-scale state with generic score helpers**

Remove `currentScoreAxis`, `currentScoreScale`, `POOL_SCORE_LINES`, scale setter,
pool readers, pool hover renderers, and pool role-line definitions. Add:

```javascript
const SIEGE_SLUGS = new Set([
    "siege", "ram", "mangonel", "trebuchet", "bombard_cannon", "cannon_galleon",
]);
const NAVAL_SLUGS = new Set(["naval", "galleon", "fire", "hulk"]);

function finalScoreLabel() {
    return (SIEGE_SLUGS.has(currentLine) || NAVAL_SLUGS.has(currentLine))
        ? "Score"
        : "V3 Score";
}

function finalScoreInfo() {
    return (SIEGE_SLUGS.has(currentLine) || NAVAL_SLUGS.has(currentLine))
        ? "The published final score for this unit line. Higher is stronger."
        : "Five seeded Simulation V3 runs per yardstick at equal resources. Food, wood, and gold are weighted 1:1:1; armies are capped at 27 units.";
}

function renderRankingBreakdown(row) {
    const breakdown = row.ranking_breakdown;
    if (!breakdown) return "—";
    const roles = Object.entries(breakdown.roles || {})
        .map(([name, score]) => `<span><strong>${name}</strong> ${_fmt(score)}</span>`)
        .join("");
    const yardsticks = (breakdown.yardsticks || [])
        .map((item) => `<li><span>${item.label}</span><strong>${_fmt(item.score)}</strong></li>`)
        .join("");
    return `<details class="ranking-breakdown"><summary>View</summary><div class="ranking-role-list">${roles}</div><ul>${yardsticks}</ul></details>`;
}
```

- [ ] **Step 5: Build one shared compact column definition**

Replace the separate pool/Siege/Naval column arrays with:

```javascript
function buildColumns() {
    const showLine = currentLine === "infantry" || currentLine === "archery" ||
        currentLine === "stable" || currentLine === "siege" || currentLine === "naval";
    return [
        { key: "ranking_rank", label: "Rank" },
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        ...(showLine ? [{ key: "line_slug", label: "Line" }] : []),
        { key: "ranking_score", label: finalScoreLabel(), info: finalScoreInfo() },
        { key: "ranking_median_delta", label: "Δ Line" },
        { key: "total_cost", label: "Cost" },
        { key: "ranking_breakdown", label: "Breakdown" },
        { key: "dps", label: "DPS", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_hp", label: "HP", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_attack", label: "Atk", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "armor_combined", label: "M/P Arm", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_speed", label: "Speed", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "final_range", label: "Range", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "total_upgrade_cost", label: "Upg Cost", expandable: "Special", hiddenWhenCollapsed: true },
        { key: "special_abilities", label: "Special", expandable: "Special" },
    ];
}
```

Default selection sorts by `ranking_score` descending. Render
`ranking_breakdown` through `renderRankingBreakdown()`, render signed
`ranking_median_delta`, and render a dash for stat-only Mangonel score/rank.
Preserve the current civ filter, line checkboxes, hover cards, sprite handling,
missing-tech content, and Special stat expansion.

Reduce `expandedGroups` to the single `Special` group, make the Special header
chevron and Expand/Collapse button available on every ranking family, and
remove the pool-specific `_isPoolPage()` / `_groupExistsForCurrentPool()`
branching. This keeps the same expansion interaction for land, Siege, and
Naval.

- [ ] **Step 6: Simplify CSV to the single score model**

Use one CSV column list for all families:

```javascript
const csvColumns = [
    { key: "ranking_rank", label: "Rank" },
    { key: "civ_name", label: "Civilization" },
    { key: "unit_name", label: "Unit" },
    { key: "line_slug", label: "Line" },
    { key: "ranking_score_type", label: "Score Type" },
    { key: "ranking_score", label: "Score" },
    { key: "ranking_median_delta", label: "Delta vs Line Median" },
    { key: "total_cost", label: "Cost (Food+Wood+Gold)" },
    { key: "general_combat", label: "GC" },
    { key: "anti_cav", label: "AC" },
    { key: "anti_trash", label: "AT" },
    { key: "anti_archer", label: "AA" },
    { key: "gc_v3_27_vs_champ", label: "vs Champion" },
    { key: "gc_v3_27_vs_paladin", label: "vs Paladin" },
    { key: "gc_v3_27_vs_arb", label: "vs Arbalester" },
    { key: "at_v3_27_vs_halb", label: "vs Halberdier" },
    { key: "at_v3_27_vs_elite_skirm", label: "vs Elite Skirmisher" },
    { key: "at_v3_27_vs_hussar", label: "vs Hussar" },
];
```

Rows without a field export an empty cell. Remove PES, RES, 30v30, 3K, 5K,
pool role, and scale-dependent export branches.

- [ ] **Step 7: Update CSS for the compact disclosure**

Delete `.score-toggles`, `.score-toggle-*`, `.score-btn`,
`.hover-pool-score`, and `.hover-pool-role` rules. Keep the existing table,
responsive, sticky-column, filter, and Special expansion rules. Add:

```css
.ranking-breakdown summary {
    color: var(--gold);
    cursor: pointer;
    font-family: var(--font-display);
    font-size: var(--fs-xs);
}
.ranking-breakdown[open] {
    min-width: 13rem;
}
.ranking-role-list {
    display: flex;
    gap: 0.6rem;
    margin: 0.5rem 0;
}
.ranking-breakdown ul {
    list-style: none;
    margin: 0;
    padding: 0;
}
.ranking-breakdown li {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
}
```

- [ ] **Step 8: Run UI and JavaScript checks GREEN**

```powershell
pytest -q tests/test_v3_rankings_ui.py tests/test_v3_rankings_api.py tests/test_seo_phase2.py tests/test_seo_unit_line_pages.py
node --check apps/website/static/js/rankings.js
```

Expected: all tests pass and Node reports no syntax error.

- [ ] **Step 9: Commit Task 5**

```powershell
git add apps/website/templates/rankings.html apps/website/static/js/rankings.js apps/website/static/css/rankings.css tests/test_v3_rankings_ui.py
git commit -m "feat: simplify v3 unit rankings table"
```

---

### Task 6: Verify, integrate, and push staging

**Files:**

- Verify: all files changed in Tasks 1–5
- Integrate: Git branches `codex/v3-rankings-staging` and `staging`
- Push: `origin/staging` only

**Interfaces:**

- Consumes: completed feature branch based on `origin/staging`.
- Produces: tested staging commit and Railway staging auto-deploy trigger.

- [ ] **Step 1: Run the focused cutover suite**

```powershell
pytest -q tests/test_build_v3_serving_db.py tests/test_v3_rankings_api.py tests/test_best_units_v3_routing.py tests/test_v3_rankings_ui.py tests/test_seo_phase2.py tests/test_seo_unit_line_pages.py tests/test_naval_rankings.py tests/test_versioning.py
node --check apps/website/static/js/rankings.js
```

Expected: all focused checks pass.

- [ ] **Step 2: Run repository CI commands locally**

```powershell
pytest -q
node tests/test_frontend_projectile_miss.js
node tests/test_sim_params.js
```

Expected: the same commands configured in `.github/workflows/ci.yml` pass. If
an unrelated pre-existing failure appears, record it separately and do not
expand into an unrelated hardening pass.

- [ ] **Step 3: Perform read-only data smoke checks**

Verify:

```powershell
python -c "import json,sqlite3; c=sqlite3.connect('data/golden/derived_data_v3.db'); print(c.execute(\"select count(*) from battle_scores where build_number!='177723'\").fetchone()); print(c.execute(\"select count(*) from battle_scores where score_type='v3_combat_effectiveness'\").fetchone()); print(c.execute(\"select count(*) from battle_scores where line_slug='mangonel'\").fetchone()); print(json.load(open('data/golden/derived_data_v3.metadata.json',encoding='utf-8'))['engine_revision'])"
```

Expected: all three counts are zero and engine revision is
`96c9404dc3f2bb5b6f617d1e640142d7d7836acf`.

Use Flask's test client to smoke `/units`, one line from each V3 family,
`/units/militia`, one Siege line, one Naval line, `/api/civ-power-units/Aztecs`,
and one Matchup Advisor recommendation request. Confirm advisor candidate SQL
uses `data/golden/derived_data.db` in the routing test output.

- [ ] **Step 4: Review the complete feature diff and working tree**

```powershell
git status --short --branch
git diff --check origin/staging...HEAD
git diff --stat origin/staging...HEAD
git log --oneline origin/staging..HEAD
```

Expected: only the planned files are changed, no whitespace errors, and the
dirty V3 campaign worktree remains untouched.

Also compare the current SHA-256 of `data/golden/derived_data.db` with the value
recorded before Task 2. An unchanged retail artifact is the rollback guarantee:
reverting the consumer-routing commits restores the old rankings immediately.

- [ ] **Step 5: Reconcile any newer staging commits**

```powershell
git fetch origin
git merge --no-edit origin/staging
```

If the merge is already up to date, continue. If it creates conflicts, resolve
only the planned rankings surfaces while retaining both newer staging changes
and this feature, then rerun Steps 1–4.

- [ ] **Step 6: Fast-forward local staging in a separate release worktree**

Create a release worktree so the user's root `simulationv3` checkout and dirty
campaign worktree are not switched:

```powershell
git worktree add D:/AI/aoe2_matchup/.worktrees/v3-rankings-staging-release staging
git -C D:/AI/aoe2_matchup/.worktrees/v3-rankings-staging-release merge --ff-only origin/staging
git -C D:/AI/aoe2_matchup/.worktrees/v3-rankings-staging-release merge --ff-only codex/v3-rankings-staging
```

Expected: local `staging` contains the existing staging history plus the
reviewed feature commits with no force operation and no `main` change.

- [ ] **Step 7: Push staging and verify the remote ref**

The user explicitly authorized this staging push:

```powershell
git -C D:/AI/aoe2_matchup/.worktrees/v3-rankings-staging-release push origin staging
git ls-remote origin refs/heads/staging
```

Expected: the remote staging SHA equals the local staging SHA. Do not push any
other branch.

- [ ] **Step 8: Confirm staging CI/deploy signal and report**

Confirm the staging GitHub Actions run reaches a terminal state. Because the
repository maps `staging` to Railway's staging environment, the push triggers
the staging auto-deploy. Report the pushed SHA, CI result, data counts, and the
specific pages/API paths to inspect. Do not promote to `main`; production needs
a separate explicit approval.
