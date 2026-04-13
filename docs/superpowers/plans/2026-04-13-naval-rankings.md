# Naval Rankings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Naval Effectiveness" 5th tab to the unit rankings page and a cannon_galleon sub-line to the Anti-Building tab, showing naval unit stats with no scoring column.

**Architecture:** Two tasks — (1) backend: add naval sub-line and aggregate entries to `UNIT_LINES` in `unit_lines.py`, which is all the existing `/api/ref/unit-line/<slug>` handler needs to serve naval data; (2) frontend: add naval tab definition, `NAVAL_SLUGS`, column spec, and stat logic to `rankings.js`. No pipeline changes; all naval unit data is already in `aoe2_reference.db`.

**Tech Stack:** Python/Flask, vanilla JS, SQLite

---

### Task 1: Naval line definitions in unit_lines.py + API test

**Files:**
- Modify: `webapp/unit_lines.py` (lines 268–287, inside UNIT_LINES before the closing `}`)
- Modify: `webapp/app.py` (line 470, SIEGE_LINE_SLUGS)
- Modify: `tests/conftest.py` (add Flask test client fixture)
- Create: `tests/test_naval_rankings.py`

**Background:** `UNIT_LINES` in `webapp/unit_lines.py` is the single source of truth for the rankings API. The handler at `webapp/app.py:535` bails with 404 if `line_slug not in UNIT_LINES`. For each aggregate slug it reads `line.get("sub_lines", [line_slug])`, then for each sub-slug it calls `UNIT_LINES[sub_slug]` to get `castle_slug`, `imperial_slug`, and `unique_units`. Adding entries for `galleon`, `fire`, `hulk`, `cannon_galleon`, and the `naval` aggregate is all that is needed — the handler already handles `castle_slug: None` (trebuchet/bombard_cannon use this exact pattern) and already handles missing battle scores gracefully (no rows returned from `battle_scores` → score fields simply absent).

Lou Chuan (Wu) appears in both `galleon` unique_units (anti-ship role) and `cannon_galleon` unique_units (siege role), so it shows in both sub-lines.

**Verify slugs before coding.** The `castle_slug`/`imperial_slug` values must match what is actually stored in `ref_units`. Run these two queries first:

```bash
cd webapp && sqlite3 aoe2_reference.db \
  "SELECT DISTINCT unit_slug, unit_name, age FROM ref_units \
   WHERE unit_name IN ('Galley','War Galley','Galleon','Fire Galley','Fire Ship', \
   'Fast Fire Ship','Hulk','War Hulk','Cannon Galleon','Elite Cannon Galleon') \
   AND civ_name='Britons' ORDER BY unit_name, age;"
```

```bash
sqlite3 aoe2_reference.db \
  "SELECT unit_slug, unit_name, civ_name, age FROM ref_units \
   WHERE unit_name IN ('Longboat','Elite Longboat','Caravel','Elite Caravel', \
   'Thirisadai','Turtle Ship','Elite Turtle Ship','Lou Chuan','Dromon','Catapult Galleon') \
   ORDER BY unit_name, civ_name;"
```

If any slug in the queries below differs from the DB output, use the DB value.

- [ ] **Step 1: Add Flask test client fixture to conftest.py**

`tests/conftest.py` currently only adds `webapp/` to `sys.path`. Append:

```python
import pytest
import app as flask_app

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_naval_rankings.py`:

```python
def test_naval_aggregate_returns_units(client):
    """Naval aggregate slug returns galleon/fire/hulk units."""
    resp = client.get("/api/ref/unit-line/naval")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert "imperial" in data
    assert len(data["imperial"]) > 0
    unit_names = {u["unit_name"] for u in data["imperial"]}
    assert "Galleon" in unit_names


def test_naval_galleon_subline(client):
    """Galleon sub-line slug returns galleon units and unique units."""
    resp = client.get("/api/ref/unit-line/galleon")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["imperial"]) > 0
    # Vikings unique should be present
    viking_names = [u["unit_name"] for u in data["imperial"] if u["civ_name"] == "Vikings"]
    assert any("Longboat" in n for n in viking_names)


def test_cannon_galleon_in_siege(client):
    """Siege aggregate now includes cannon_galleon sub-line in Imperial Age."""
    resp = client.get("/api/ref/unit-line/siege")
    assert resp.status_code == 200
    data = resp.get_json()
    line_slugs = {u["line_slug"] for u in data["imperial"]}
    assert "cannon_galleon" in line_slugs


def test_naval_no_score_columns(client):
    """Naval units have no battle score fields (no scoring yet)."""
    resp = client.get("/api/ref/unit-line/naval")
    data = resp.get_json()
    for unit in data["imperial"]:
        assert "militia_value" not in unit
        assert "ranged_effectiveness" not in unit
        assert "anti_building_score" not in unit
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
venv/bin/python3 -m pytest tests/test_naval_rankings.py -v
```

Expected: 4 FAILED — `test_naval_aggregate_returns_units` fails with 404 (naval not in UNIT_LINES); others similarly.

- [ ] **Step 4: Add naval sub-line entries to UNIT_LINES**

In `webapp/unit_lines.py`, find line 267 (after `"bombard_cannon"` entry closes, before `"archery"` aggregate). Insert these four sub-line entries:

```python
    "galleon": {
        "name": "Galleon Line",
        "building": "Dock",
        "castle_slug": "war_galley",
        "imperial_slug": "galleon",
        "unique_units": {
            "Vikings":    ("longboat_vikings",     "elite_longboat_vikings"),
            "Portuguese": ("caravel_portuguese",   "elite_caravel_portuguese"),
            "Dravidians": ("thirisadai_dravidians", "thirisadai_dravidians"),
            "Wu":         ("lou_chuan_wu",          "lou_chuan_wu"),
        },
    },
    "fire": {
        "name": "Fire Ship Line",
        "building": "Dock",
        "castle_slug": "fire_ship",
        "imperial_slug": "fast_fire_ship",
        "unique_units": {},
    },
    "hulk": {
        "name": "Hulk Line",
        "building": "Dock",
        "castle_slug": "hulk",
        "imperial_slug": "war_hulk",
        "unique_units": {
            "Koreans": ("turtle_ship_koreans", "elite_turtle_ship_koreans"),
        },
    },
    "cannon_galleon": {
        "name": "Cannon Galleon",
        "building": "Dock",
        "castle_slug": None,
        "imperial_slug": "cannon_galleon",
        "unique_units": {
            "Byzantines": (None, "dromon_byzantines"),
            "Mapuche":    (None, "catapult_galleon_mapuche"),
            "Wu":         (None, "lou_chuan_wu"),
            "Shu":        (None, "lou_chuan_shu"),
            "Wei":        (None, "lou_chuan_wei"),
        },
    },
```

- [ ] **Step 5: Add naval aggregate and update siege aggregate**

Still in `webapp/unit_lines.py`, find the `"siege"` aggregate at line ~283:

```python
    "siege": {
        "name": "Anti-Building Effectiveness",
        "building": "Siege Workshop",
        "sub_lines": ["ram", "trebuchet", "bombard_cannon"],
    },
```

Replace with:

```python
    "siege": {
        "name": "Anti-Building Effectiveness",
        "building": "Siege Workshop",
        "sub_lines": ["ram", "trebuchet", "bombard_cannon", "cannon_galleon"],
    },
    "naval": {
        "name": "Naval Effectiveness",
        "building": "Dock",
        "sub_lines": ["galleon", "fire", "hulk"],
    },
```

- [ ] **Step 6: Add cannon_galleon to SIEGE_LINE_SLUGS in app.py**

In `webapp/app.py` at line 470:

```python
SIEGE_LINE_SLUGS = {"ram", "mangonel", "trebuchet", "bombard_cannon"}
```

Change to:

```python
SIEGE_LINE_SLUGS = {"ram", "mangonel", "trebuchet", "bombard_cannon", "cannon_galleon"}
```

This ensures cannon_galleon units go through the DB score-attachment path (which returns no rows — correct, no scores exist yet) instead of the JSON fallback path (which would populate score fields with -999 sentinel values that we don't want).

- [ ] **Step 7: Run tests**

```bash
venv/bin/python3 -m pytest tests/test_naval_rankings.py tests/test_simulations.py -v
```

Expected: all pass. If `test_naval_galleon_subline` or `test_naval_aggregate_returns_units` fails with empty lists, the `castle_slug`/`imperial_slug` values don't match what's in `ref_units` — re-run the DB verification queries from the task header and correct the slugs in Step 4.

- [ ] **Step 8: Commit**

```bash
git add webapp/unit_lines.py webapp/app.py tests/conftest.py tests/test_naval_rankings.py
git commit -m "feat: add naval line definitions to UNIT_LINES for rankings API"
```

---

### Task 2: Naval tab in rankings.js

**Files:**
- Modify: `webapp/static/js/rankings.js` (multiple locations — all edits listed below with exact find strings)

**Background:** The frontend `UNIT_LINES` object (line 8) mirrors the backend structure and drives tab rendering. `selectLine(slug)` (line 660) sets `sortColumn` using the INFANTRY/ARCHERY/SIEGE_SLUGS sets. `renderTable()` (line 713) picks `statCols` and `columns` arrays using the same sets, then renders the HTML. Adding `NAVAL_SLUGS`, a `naval` UNIT_LINES entry, a `navalColumns` array, and wiring them into the three slug-dispatch chains is the complete change.

No automated test — verified visually by starting Flask and clicking through the UI.

- [ ] **Step 1: Add NAVAL_SLUGS and update SIEGE_SLUGS**

Find (line 656):
```js
const SIEGE_SLUGS = new Set([
    "siege",
]);
```

Replace with:
```js
const SIEGE_SLUGS = new Set([
    "siege",
    "cannon_galleon",
]);

const NAVAL_SLUGS = new Set([
    "galleon",
    "fire",
    "hulk",
    "naval",
]);
```

- [ ] **Step 2: Add naval to UNIT_LINES**

Find the closing `};` of the `UNIT_LINES` object (after the `siege` entry, line ~41). Insert before it:

```js
    naval: {
        name: "Naval Effectiveness",
        building: "Dock",
        castle: "War Galley",
        imperial: "Galleon",
        hasUnique: true,
        subLines: ["galleon", "fire", "hulk"],
    },
```

- [ ] **Step 3: Add LINE_LABELS for naval sub-lines**

Find `LINE_LABELS` (line 693). Add entries alongside the existing ones:

```js
    galleon: "Galleon",
    fire: "Fire Ship",
    hulk: "Hulk",
    cannon_galleon: "Cannon Galleon",
```

- [ ] **Step 4: Update sortColumn in selectLine()**

Find (line 680):
```js
    sortColumn =
        slug === "stable"
            ? "stable_effectiveness"
            : INFANTRY_SLUGS.has(slug)
                ? "militia_value"
                : ARCHERY_SLUGS.has(slug)
                    ? "ranged_effectiveness"
                    : SIEGE_SLUGS.has(slug)
                        ? "anti_building_score"
                        : "pes";
```

Replace with:
```js
    sortColumn =
        slug === "stable"
            ? "stable_effectiveness"
            : INFANTRY_SLUGS.has(slug)
                ? "militia_value"
                : ARCHERY_SLUGS.has(slug)
                    ? "ranged_effectiveness"
                    : SIEGE_SLUGS.has(slug)
                        ? "anti_building_score"
                        : NAVAL_SLUGS.has(slug)
                            ? "final_hp"
                            : "pes";
```

- [ ] **Step 5: Add isNaval and navalStatCols in renderTable()**

Find (line 914):
```js
    const isArchery = ARCHERY_SLUGS.has(currentLine);
    const isSiege = SIEGE_SLUGS.has(currentLine);
```

Replace with:
```js
    const isArchery = ARCHERY_SLUGS.has(currentLine);
    const isSiege = SIEGE_SLUGS.has(currentLine);
    const isNaval = NAVAL_SLUGS.has(currentLine);
```

Then find `siegeStatCols` (line 892) and add `navalStatCols` directly after it:

```js
    const navalStatCols = [
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
        "final_range",
    ];
```

- [ ] **Step 6: Wire navalStatCols into statCols selection**

Find (line 916):
```js
    const statCols =
        currentLine === "stable"
            ? stableStatCols
            : isSiege
                ? siegeStatCols
                : isInfantry
                    ? infantryStatCols
                    : isArchery
                        ? archeryStatCols
                        : defaultStatCols;
```

Replace with:
```js
    const statCols =
        currentLine === "stable"
            ? stableStatCols
            : isSiege
                ? siegeStatCols
                : isInfantry
                    ? infantryStatCols
                    : isArchery
                        ? archeryStatCols
                        : isNaval
                            ? navalStatCols
                            : defaultStatCols;
```

- [ ] **Step 7: Add navalColumns definition**

Find `stableColumns` (line 1071) and add `navalColumns` directly after it (before `const columns = ...`):

```js
    const navalColumns = [
        { key: "civ_name", label: "Civ" },
        { key: "unit_name", label: "Unit" },
        { key: "line_slug", label: "Line" },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed" },
        { key: "final_range", label: "Range" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
```

- [ ] **Step 8: Wire navalColumns into columns selection**

Find (line 1100):
```js
    const columns =
        currentLine === "stable"
            ? stableColumns
            : isSiege
                ? siegeColumns
                : isInfantry
                    ? infantryColumns
                    : isArchery
                        ? archeryColumns
                        : defaultColumns;
```

Replace with:
```js
    const columns =
        currentLine === "stable"
            ? stableColumns
            : isSiege
                ? siegeColumns
                : isInfantry
                    ? infantryColumns
                    : isArchery
                        ? archeryColumns
                        : isNaval
                            ? navalColumns
                            : defaultColumns;
```

- [ ] **Step 9: Start Flask and visually verify**

```bash
venv/bin/python3 webapp/app.py --port 5001
```

Open `http://localhost:5001/units`. Check:

1. **5th tab** "Naval Effectiveness" appears after Anti-Building.
2. Click Naval tab → **Imperial Age** shows Galleon, Fast Fire Ship, War Hulk rows for civs that have them. Longboat appears for Vikings. Turtle Ship appears for Koreans (hulk sub-line).
3. **Castle Age** shows War Galley, Fire Ship, Hulk.
4. **Line checkboxes**: Galleon, Fire Ship, Hulk. Unchecking one hides those rows.
5. **Column headers**: Civ, Unit, Line, DPS, HP, Atk, M.Arm, P.Arm, Speed, Range, Cost, Upg Cost, Special. No "Score" column.
6. Click **Anti-Building tab** → **Cannon Galleon** checkbox now present. Checking it shows Cannon Galleon rows with blank Score/TTK columns. Dromon appears for Byzantines. Lou Chuan appears for Wu/Shu/Wei.
7. Sorting by HP column works; sorting by Civ works.

- [ ] **Step 10: Run full test suite**

```bash
venv/bin/python3 -m pytest tests/ -v
```

Expected: all 31 tests pass (27 original + 4 new naval tests).

- [ ] **Step 11: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat: add naval effectiveness tab and cannon_galleon sub-line to rankings UI"
```
