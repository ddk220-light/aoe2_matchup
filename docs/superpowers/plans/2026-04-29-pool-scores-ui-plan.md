# Pool Scores UI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the six pool-scores flavors (3 axes × 2 scales) on the existing Unit Rankings page via two radio-button toggles, replacing legacy composite columns for the three covered pools.

**Architecture:** Backend extends `/api/ref/unit-line/<slug>` to attach a `pool_scores` payload per unit (loaded from `pool_scores.db` via a small helper module). Frontend toggles are pure client-side — they pick which fields from the already-fetched payload to display and re-sort. Siege/naval tabs keep legacy columns and hide the toggles.

**Tech Stack:** Python 3 + Flask + SQLite (backend), vanilla JS + HTML + CSS (frontend), pytest (tests).

**Spec:** `docs/superpowers/specs/2026-04-29-pool-scores-ui-design.md`

---

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `webapp/pool_scores_query.py` | Create | Helper: load `pool_scores` rows for a set of (civ, unit_slug) pairs at one age, return the structured payload |
| `webapp/app.py` | Modify | `/api/ref/unit-line/<slug>` attaches `pool_scores` field per unit row |
| `webapp/templates/index.html` | Modify | Add two radio-toggle groups |
| `webapp/static/css/rankings.css` | Modify | Style the new toggles to match the age-toggle pattern |
| `webapp/static/js/rankings.js` | Modify | Toggle state, score column rendering, hover content, sort behavior, siege/naval hiding |
| `tests/test_pool_scores_query.py` | Create | Unit tests for the helper |
| `tests/test_pool_scores_api.py` | Create | Integration tests for the API extension |

---

## Constants and conventions

- **Working directory:** `D:/AI/aoe2-unit-analyzer`
- **Run pytest from repo root:** `cd D:/AI/aoe2-unit-analyzer && pytest tests/...`
- **Bare imports** in tests/lib (no `webapp.` prefix); `tests/conftest.py` adds `webapp/` to sys.path.
- **Run webapp scripts** from `webapp/` directory: `cd webapp && python derive_pool_scores.py`
- **HEREDOC commit pattern** with co-author trailer:
  ```bash
  git commit -m "$(cat <<'EOF'
  feat(...): message

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```
- **Default toggle state:** `axis="hp"`, `scale="average"`.
- **Covered pools:** `infantry`, `stable`, `archery` (UI line-tab slug; the underlying pool name in `pool_scores.db` is `archer`).

---

## Task 1: Backend helper — load pool_scores by (civ, unit) pairs

**Files:**
- Create: `webapp/pool_scores_query.py`
- Create: `tests/test_pool_scores_query.py`

The helper loads pool_scores.db rows for a batch of (civ_name, unit_slug) pairs and returns a dict keyed by `(civ_name, unit_slug)` → structured payload (or `None` if the unit isn't in pool_scores.db).

Structured payload shape:

```python
{
    "pool": "infantry",  # or "stable", "archer"
    "scales": {
        "30v30": {
            "hp":   {"final": 8.9,  "gc": -6.8, "ac": -1.6, "at": 92.7, "aa": None},
            "cost": {"final": 3961.8, "gc": 4485.6, "ac": 5270.4, "at": 208.8, "aa": None},
            "speed":{"final": 1.2,   "gc": -9.8, "ac": -5.5, "at": 59.0, "aa": None},
            "shape": {"n": 269, "win_rate": 61.7, "decisive_win_rate": 53.4,
                      "big_win_rate": 47.1, "catastrophic_loss_rate": 27.1,
                      "stddev": 59.5, "mean": 35.2},
        },
        "3k": {...same structure...},
    },
}
```

- [ ] **Step 1: Write failing tests**

`tests/test_pool_scores_query.py`:
```python
"""Unit tests for webapp/pool_scores_query.py."""
import os
import sqlite3
import pytest

from pool_scores_db import create_db, insert_score
from pool_scores_query import load_pool_scores


def _make_row(civ, slug, scale, axis, **overrides):
    base = {
        "civ_name": civ, "unit_slug": slug,
        "pool": "infantry", "scale": scale, "axis": axis,
        "final_score": 0.0, "gc": 0.0, "ac": 0.0, "at": 0.0, "aa": None,
        "n": 1, "mean": 0.0, "stddev": 0.0,
        "win_rate": 0.0, "decisive_win_rate": 0.0,
        "big_win_rate": 0.0, "catastrophic_loss_rate": 0.0,
        "sim_version": "v1", "derived_at": "t1",
    }
    base.update(overrides)
    return base


def test_load_returns_empty_when_no_rows(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    conn.close()
    result = load_pool_scores(str(db_path), [("Vikings", "elite_berserk_vikings")])
    assert result == {}


def test_load_returns_payload_for_known_unit(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    # Two scales × three axes = 6 rows
    for scale in ("30v30", "3k"):
        for axis in ("hp", "cost", "speed"):
            insert_score(conn, _make_row(
                "Vikings", "elite_berserk_vikings", scale, axis,
                final_score=10.0, gc=5.0, ac=3.0, at=90.0,
                n=200, win_rate=70.0, catastrophic_loss_rate=10.0,
                stddev=50.0, mean=20.0,
                decisive_win_rate=60.0, big_win_rate=50.0,
            ))
    conn.commit()
    conn.close()

    result = load_pool_scores(str(db_path),
                              [("Vikings", "elite_berserk_vikings")])
    payload = result[("Vikings", "elite_berserk_vikings")]
    assert payload["pool"] == "infantry"
    assert set(payload["scales"]) == {"30v30", "3k"}
    pop_hp = payload["scales"]["30v30"]["hp"]
    assert pop_hp["final"] == 10.0
    assert pop_hp["gc"] == 5.0
    assert pop_hp["ac"] == 3.0
    assert pop_hp["at"] == 90.0
    assert pop_hp["aa"] is None
    shape = payload["scales"]["30v30"]["shape"]
    assert shape["n"] == 200
    assert shape["win_rate"] == 70.0
    assert shape["catastrophic_loss_rate"] == 10.0


def test_load_skips_units_not_in_db(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "30v30", "hp"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "30v30", "cost"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "30v30", "speed"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "3k", "hp"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "3k", "cost"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "3k", "speed"))
    conn.commit()
    conn.close()

    result = load_pool_scores(str(db_path), [
        ("Vikings", "elite_berserk_vikings"),
        ("Britons", "trebuchet"),  # not in db
    ])
    assert ("Vikings", "elite_berserk_vikings") in result
    assert ("Britons", "trebuchet") not in result
    assert len(result) == 1


def test_load_returns_empty_dict_for_empty_input(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    conn.close()
    assert load_pool_scores(str(db_path), []) == {}


def test_load_partial_scales_handled_gracefully(tmp_path):
    """If a unit only has 30v30 rows but no 3k, still return what's available."""
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    for axis in ("hp", "cost", "speed"):
        insert_score(conn, _make_row(
            "Vikings", "elite_berserk_vikings", "30v30", axis, final_score=5.0))
    conn.commit()
    conn.close()

    result = load_pool_scores(str(db_path), [("Vikings", "elite_berserk_vikings")])
    payload = result[("Vikings", "elite_berserk_vikings")]
    assert "30v30" in payload["scales"]
    # Missing 3k means no entry for that scale.
    assert "3k" not in payload["scales"]
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_query.py -v`
Expected: FAIL with `ImportError: No module named 'pool_scores_query'`.

- [ ] **Step 3: Implement the helper**

`webapp/pool_scores_query.py`:
```python
"""Query helper for pool_scores.db.

Loads structured per-unit payloads keyed by (civ_name, unit_slug).
Used by the /api/ref/unit-line endpoint to attach pool-scores data
to each unit row in the rankings view.
"""
import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "pool_scores.db")

_SHAPE_KEYS = ("n", "mean", "stddev", "win_rate", "decisive_win_rate",
               "big_win_rate", "catastrophic_loss_rate")
_ROLE_KEYS = ("gc", "ac", "at", "aa")


def load_pool_scores(db_path: str,
                     civ_unit_pairs: list[tuple[str, str]]) -> dict:
    """Return {(civ_name, unit_slug): payload, ...} for known units.

    Units not present in pool_scores.db are simply absent from the result.
    Empty input → empty dict. Missing DB file → empty dict.
    """
    if not civ_unit_pairs or not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Build placeholders for all (civ, unit) pairs in one query.
        placeholders = ", ".join("(?, ?)" for _ in civ_unit_pairs)
        params: list[str] = []
        for civ, slug in civ_unit_pairs:
            params.extend((civ, slug))
        cur = conn.execute(f"""
            SELECT civ_name, unit_slug, pool, scale, axis,
                   final_score, gc, ac, at, aa,
                   n, mean, stddev,
                   win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate
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
        # Per-axis: final + role components.
        scale_payload[row["axis"]] = {
            "final": row["final_score"],
            **{k: row[k] for k in _ROLE_KEYS},
        }
        # Shape descriptors are identical across axes for one (unit, scale)
        # — just take whichever axis we see first.
        if scale_payload["shape"] is None:
            scale_payload["shape"] = {k: row[k] for k in _SHAPE_KEYS}

    return result
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_query.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_query.py tests/test_pool_scores_query.py
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): backend helper for loading pool_scores by unit

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: API extension — attach pool_scores to /api/ref/unit-line response

**Files:**
- Modify: `webapp/app.py` (in `api_ref_unit_line` function around line 547)
- Create: `tests/test_pool_scores_api.py`

For each unit row in the line response, when the unit is in `pool_scores.db`, attach a `pool_scores` field with the payload from Task 1. Out-of-pool units (e.g. trebuchet, galleon) get no `pool_scores` field — frontend uses presence/absence to decide whether to show toggles.

- [ ] **Step 1: Write failing API integration tests**

`tests/test_pool_scores_api.py`:
```python
"""Integration tests for /api/ref/unit-line pool_scores attachment."""
import os
import pytest


@pytest.fixture(autouse=True)
def _require_real_dbs():
    """Skip if the live pool_scores.db isn't generated yet."""
    p = os.path.join(os.path.dirname(__file__), "..", "webapp", "pool_scores.db")
    if not os.path.exists(p):
        pytest.skip(f"{p} not present — run derive_pool_scores.py first")


def _find(rows, civ, slug):
    return next((u for u in rows if u["civ_name"] == civ and u["unit_slug"] == slug), None)


def test_pool_scores_attached_for_infantry_unit(client):
    resp = client.get("/api/ref/unit-line/militia")
    assert resp.status_code == 200
    data = resp.get_json()
    berserker = _find(data["imperial"], "Vikings", "elite_berserk_vikings")
    assert berserker is not None
    assert "pool_scores" in berserker
    ps = berserker["pool_scores"]
    assert ps["pool"] == "infantry"
    assert "30v30" in ps["scales"]
    assert "3k" in ps["scales"]
    pop_hp = ps["scales"]["30v30"]["hp"]
    assert pop_hp["final"] == pytest.approx(8.9, abs=0.5)
    assert pop_hp["at"] == pytest.approx(92.7, abs=0.5)


def test_pool_scores_attached_for_stable_unit(client):
    resp = client.get("/api/ref/unit-line/knight")
    assert resp.status_code == 200
    data = resp.get_json()
    paladin = _find(data["imperial"], "Franks", "paladin")
    assert paladin is not None
    assert "pool_scores" in paladin
    assert paladin["pool_scores"]["pool"] == "stable"


def test_pool_scores_attached_for_archer_unit(client):
    resp = client.get("/api/ref/unit-line/archer")
    assert resp.status_code == 200
    data = resp.get_json()
    arb = _find(data["imperial"], "Britons", "arbalester")
    assert arb is not None
    assert "pool_scores" in arb
    assert arb["pool_scores"]["pool"] == "archer"


def test_pool_scores_absent_for_siege_unit(client):
    """Trebuchet is in the trebuchet line — not covered by pool_scores."""
    resp = client.get("/api/ref/unit-line/trebuchet")
    assert resp.status_code == 200
    data = resp.get_json()
    treb = _find(data["imperial"], "Britons", "trebuchet")
    assert treb is not None
    assert "pool_scores" not in treb


def test_pool_scores_absent_for_naval_unit(client):
    resp = client.get("/api/ref/unit-line/galleon")
    assert resp.status_code == 200
    data = resp.get_json()
    galleon = _find(data["imperial"], "Britons", "galleon")
    assert galleon is not None
    assert "pool_scores" not in galleon


def test_pool_scores_shape_descriptors_present(client):
    resp = client.get("/api/ref/unit-line/militia")
    data = resp.get_json()
    berserker = _find(data["imperial"], "Vikings", "elite_berserk_vikings")
    shape = berserker["pool_scores"]["scales"]["30v30"]["shape"]
    assert shape["n"] >= 200
    assert "win_rate" in shape
    assert "catastrophic_loss_rate" in shape
    assert "stddev" in shape
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_api.py -v`
Expected: tests SKIP (if pool_scores.db missing) or FAIL with `KeyError: 'pool_scores'`.

If tests SKIP, regenerate the DB first:
```bash
cd D:/AI/aoe2-unit-analyzer/webapp && python derive_pool_scores.py
```

- [ ] **Step 3: Add pool_scores attachment in api_ref_unit_line**

Open `webapp/app.py` and find the `api_ref_unit_line` function (around line 547). Near the top of the file's import block (around line 10–20), add:

```python
from pool_scores_query import load_pool_scores
```

Inside `api_ref_unit_line`, after `result["castle"]` and `result["imperial"]` lists are fully populated (i.e., after the existing loop that calls `_attach_scores` and `_attach_special` ends), add a final pass to attach pool_scores. Find the section that returns the result (look for `return jsonify(result)` near the end of the function) and just before that return statement, insert:

```python
    # Attach pool_scores payload for units covered by pool_scores.db.
    # Out-of-pool units (siege/naval) simply don't get the field.
    pool_scores_db_path = os.path.join(os.path.dirname(__file__), "pool_scores.db")
    all_unit_pairs = [
        (entry["civ_name"], entry["unit_slug"])
        for age_key in ("castle", "imperial")
        for entry in result[age_key]
    ]
    pool_scores_by_unit = load_pool_scores(pool_scores_db_path, all_unit_pairs)
    for age_key in ("castle", "imperial"):
        for entry in result[age_key]:
            key = (entry["civ_name"], entry["unit_slug"])
            if key in pool_scores_by_unit:
                entry["pool_scores"] = pool_scores_by_unit[key]
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_api.py -v`
Expected: 6 PASS.

Run the full suite to verify no regressions:
Run: `pytest -q`
Expected: previously-passing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_pool_scores_api.py
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): attach pool_scores payload to unit-line API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Toggle UI — HTML + CSS

**Files:**
- Modify: `webapp/templates/index.html`
- Modify: `webapp/static/css/rankings.css`

Add two radio-button groups (Score axis, Scale) just below the existing age-toggle. Style them to match the age-toggle's button-group look. The toggles will have `id="scoreAxisToggle"` and `id="scoreScaleToggle"` containers; each group has three buttons with `onclick` handlers that call `setScoreAxis(...)` / `setScoreScale(...)` (defined in Task 4).

- [ ] **Step 1: Add HTML markup**

Open `webapp/templates/index.html`. The current structure (around line 16) has `<div class="age-toggle">` with two buttons. Right after the closing `</div>` of `age-toggle` (currently around line 33), add:

```html
    <div class="score-toggles">
        <div class="score-toggle-group" id="scoreAxisToggle" data-toggle-group="axis">
            <span class="score-toggle-label">Score axis:</span>
            <button class="score-btn active" data-value="hp" onclick="setScoreAxis('hp')">HP%</button>
            <button class="score-btn" data-value="cost" onclick="setScoreAxis('cost')">Resource cost</button>
            <button class="score-btn" data-value="speed" onclick="setScoreAxis('speed')">Speed</button>
        </div>
        <div class="score-toggle-group" id="scoreScaleToggle" data-toggle-group="scale">
            <span class="score-toggle-label">Scale:</span>
            <button class="score-btn" data-value="pop" onclick="setScoreScale('pop')">Pop (30v30)</button>
            <button class="score-btn" data-value="cost" onclick="setScoreScale('cost')">Cost (3k)</button>
            <button class="score-btn active" data-value="average" onclick="setScoreScale('average')">Average</button>
        </div>
        <div class="score-toggle-note" id="scoreToggleNote" hidden>
            Toggles apply to infantry, stable, and archery pools. Siege and naval still use the legacy composite score.
        </div>
    </div>
```

The full modified file should look like:
```html
{% extends 'base.html' %}

{% block title %}Unit Rankings — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/rankings.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Unit Rankings</h1>
    <p class="subtitle">Compare unit stats across civilizations</p>
</div>

<div class="container">
    <div class="age-toggle">
        <button class="age-btn" onclick="setAge('Castle')">
            ...existing castle button SVG and text...
            Castle Age
        </button>
        <button class="age-btn active" onclick="setAge('Imperial')">
            ...existing imperial button SVG and text...
            Imperial Age
        </button>
    </div>
    <div class="score-toggles">
        <div class="score-toggle-group" id="scoreAxisToggle" data-toggle-group="axis">
            <span class="score-toggle-label">Score axis:</span>
            <button class="score-btn active" data-value="hp" onclick="setScoreAxis('hp')">HP%</button>
            <button class="score-btn" data-value="cost" onclick="setScoreAxis('cost')">Resource cost</button>
            <button class="score-btn" data-value="speed" onclick="setScoreAxis('speed')">Speed</button>
        </div>
        <div class="score-toggle-group" id="scoreScaleToggle" data-toggle-group="scale">
            <span class="score-toggle-label">Scale:</span>
            <button class="score-btn" data-value="pop" onclick="setScoreScale('pop')">Pop (30v30)</button>
            <button class="score-btn" data-value="cost" onclick="setScoreScale('cost')">Cost (3k)</button>
            <button class="score-btn active" data-value="average" onclick="setScoreScale('average')">Average</button>
        </div>
        <div class="score-toggle-note" id="scoreToggleNote" hidden>
            Toggles apply to infantry, stable, and archery pools. Siege and naval still use the legacy composite score.
        </div>
    </div>
    <div id="lineSelector"></div>
    <div class="table-container" id="tableContainer"></div>
</div>
{% endblock %}

{% block page_js %}
<script src="{{ url_for('static', filename='js/rankings.js') }}"></script>
{% endblock %}
```

(Don't actually re-type the existing castle/imperial SVG markup — leave those buttons as they are.)

- [ ] **Step 2: Add CSS styles**

Open `webapp/static/css/rankings.css`. Find the `.age-btn.active` rule (around line 27) and add the new `.score-toggles`, `.score-toggle-group`, `.score-btn`, and `.score-toggle-note` rules right after it.

Append these rules:
```css
/* Score axis + scale toggles */
.score-toggles {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
    margin: 12px 0 8px 0;
}

.score-toggle-group {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--card-bg, #1a1a1a);
    border: 1px solid var(--border, #333);
    border-radius: 6px;
    padding: 4px 8px;
}

.score-toggle-label {
    font-size: 12px;
    color: var(--text-muted, #888);
    margin-right: 6px;
}

.score-btn {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text, #ccc);
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}

.score-btn:hover {
    background: var(--hover-bg, #222);
}

.score-btn.active {
    background: var(--accent, #5a8edc);
    color: #fff;
    font-weight: 600;
}

.score-toggle-note {
    font-size: 11px;
    color: var(--text-muted, #888);
    font-style: italic;
    flex-basis: 100%;
}
```

- [ ] **Step 3: Manual verification**

Start the dev server:
```bash
cd D:/AI/aoe2-unit-analyzer && PORT=5002 python webapp/app.py
```
Open http://localhost:5002/ in a browser. You should see two new toggle groups below the Castle/Imperial age toggle. Clicking buttons doesn't yet do anything — Task 4 wires up the handlers. Stop the server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add webapp/templates/index.html webapp/static/css/rankings.css
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): add score axis + scale toggle UI scaffolding

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Toggle state + helper functions

**Files:**
- Modify: `webapp/static/js/rankings.js`

Add toggle state variables and the helper functions that read pool_scores fields based on the active toggles. After this task, clicking the toggles updates the highlighting and re-renders the table (which will continue to render the OLD columns until Task 5 swaps them).

- [ ] **Step 1: Add state vars and helpers near the top of rankings.js**

Find the `// ===== STATE =====` block in `webapp/static/js/rankings.js` (around line 59). Just after the existing state vars (around line 68, after `const statChainCache = {};`), add:

```javascript
// Pool-scores toggle state. Defaults: HP axis, Average scale.
let currentScoreAxis = "hp";       // "hp" | "cost" | "speed"
let currentScoreScale = "average"; // "pop" | "cost" | "average"

// Lines covered by pool_scores.db; toggles apply only to these tabs.
const POOL_SCORE_LINES = new Set([
    "infantry", "militia", "spear", "shock_infantry",
    "archery", "archer", "skirmisher", "cav_archer", "scorpion", "gunpowder",
    "stable", "knight", "light_cav", "camel", "steppe_lancer", "elephant",
]);

function lineUsesPoolScores(slug) {
    return POOL_SCORE_LINES.has(slug);
}

// Score-axis convention: cost is "lower = better"; hp/speed are "higher = better".
function scoreAxisDirection(axis) {
    return axis === "cost" ? "asc" : "desc";
}

// Read a pool-scores value for a unit row, axis, scale.
// Returns null if the unit has no pool_scores or the requested fields are missing.
function getPoolScoreValue(unitRow, axis, scale, role = "final") {
    const ps = unitRow && unitRow.pool_scores;
    if (!ps || !ps.scales) return null;
    if (scale === "average") {
        const a = ps.scales["30v30"];
        const b = ps.scales["3k"];
        if (!a || !b || !a[axis] || !b[axis]) return null;
        const va = a[axis][role];
        const vb = b[axis][role];
        if (va == null || vb == null) return null;
        return (va + vb) / 2;
    }
    const scaleKey = scale === "pop" ? "30v30" : "3k";
    const sc = ps.scales[scaleKey];
    if (!sc || !sc[axis]) return null;
    const v = sc[axis][role];
    return v == null ? null : v;
}
```

- [ ] **Step 2: Add toggle handlers**

In the same file, find the `setAge` function (search for `function setAge`). Right after it, add:

```javascript
function setScoreAxis(axis) {
    currentScoreAxis = axis;
    document.querySelectorAll("#scoreAxisToggle .score-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.value === axis);
    });
    // Reset sort to the score column with natural direction for new axis.
    if (currentLine && lineUsesPoolScores(currentLine)) {
        sortColumn = "pool_score";
        sortDir = scoreAxisDirection(axis);
    }
    if (currentData) renderTable();
}

function setScoreScale(scale) {
    currentScoreScale = scale;
    document.querySelectorAll("#scoreScaleToggle .score-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.value === scale);
    });
    if (currentData) renderTable();
}
```

- [ ] **Step 3: Show / hide the toggle group based on current line**

Still in `rankings.js`, find the `selectLine` function (around line 730). Inside it, after `currentLine = slug;` and before the line-info / sort-column logic, add:

```javascript
    // Show/hide the score toggles based on whether the current line is
    // covered by pool_scores.db.
    const togglesEl = document.querySelector(".score-toggles");
    const noteEl = document.getElementById("scoreToggleNote");
    if (togglesEl) {
        const covered = lineUsesPoolScores(slug);
        togglesEl.querySelectorAll(".score-toggle-group").forEach((g) => {
            g.style.display = covered ? "" : "none";
        });
        if (noteEl) noteEl.hidden = covered;
    }
```

- [ ] **Step 4: Manual verification**

```bash
cd D:/AI/aoe2-unit-analyzer && PORT=5002 python webapp/app.py
```

Open http://localhost:5002/. Click between Castle / Imperial age — works as before. Click each toggle button — the active highlight should move correctly. Click the "Siege" line tab — toggles disappear and the note appears. Click "Infantry" — toggles reappear. Stop the server.

- [ ] **Step 5: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): toggle state, handlers, hide/show by tab

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Replace legacy score columns with toggle-driven columns for covered pools

**Files:**
- Modify: `webapp/static/js/rankings.js`

For the three covered line tabs (infantry/archery/stable, plus their sub-line slugs), replace the legacy column blocks (`infantryColumns`, `archeryColumns`, `stableColumns`) with new column lists that use a single `pool_score` Score column plus role components (GC, AC/AT/AA). The score field is computed at render-time from `pool_scores` and the active toggles.

- [ ] **Step 1: Add the score-injection step to `enriched.map`**

Find the `enriched = rows.map((r) => {` block in `renderTable` (around line 805). At the bottom of the returned object, add four new computed fields:

Locate the `return {` inside the map callback (around line 861). Before the closing `};`, add:

```javascript
            pool_score: getPoolScoreValue(r, currentScoreAxis, currentScoreScale, "final"),
            pool_gc: getPoolScoreValue(r, currentScoreAxis, currentScoreScale, "gc"),
            pool_ac: getPoolScoreValue(r, currentScoreAxis, currentScoreScale, "ac"),
            pool_at: getPoolScoreValue(r, currentScoreAxis, currentScoreScale, "at"),
            pool_aa: getPoolScoreValue(r, currentScoreAxis, currentScoreScale, "aa"),
```

- [ ] **Step 2: Replace the infantry column / stat-col blocks**

In `renderTable`, find the `infantryStatCols` array (around line 958–969). Replace it with:

```javascript
    const infantryStatCols = [
        "pool_score",
        "pool_gc",
        "pool_ac",
        "pool_at",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
    ];
```

Find the `infantryColumns` array (around line 1080). Replace it with:

```javascript
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
        },
        {
            key: "pool_ac",
            label: "AC",
            info: roleColumnInfo("AC", "infantry"),
        },
        {
            key: "pool_at",
            label: "AT",
            info: roleColumnInfo("AT", "infantry"),
        },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
```

- [ ] **Step 3: Replace the archery column / stat-col blocks**

Find `archeryStatCols` (around line 970). Replace with:
```javascript
    const archeryStatCols = [
        "pool_score",
        "pool_gc",
        "pool_aa",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
        "final_range",
    ];
```

Find `archeryColumns` (around line 1116). Replace with:

```javascript
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
        },
        {
            key: "pool_aa",
            label: "AA",
            info: roleColumnInfo("AA", "archery"),
        },
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

- [ ] **Step 4: Replace the stable column / stat-col blocks**

Find `stableStatCols` (around line 992). Replace with:
```javascript
    const stableStatCols = [
        "pool_score",
        "pool_gc",
        "pool_ac",
        "dps",
        "final_hp",
        "final_attack",
        "final_melee_armor",
        "final_pierce_armor",
        "final_speed",
    ];
```

Find `stableColumns` (around line 1168). Replace with:

```javascript
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
        },
        {
            key: "pool_ac",
            label: "AC",
            info: roleColumnInfo("AC", "stable"),
        },
        { key: "dps", label: "DPS" },
        { key: "final_hp", label: "HP" },
        { key: "final_attack", label: "Atk" },
        { key: "final_melee_armor", label: "M.Arm" },
        { key: "final_pierce_armor", label: "P.Arm" },
        { key: "final_speed", label: "Speed (raw)" },
        { key: "total_cost", label: "Cost" },
        { key: "total_upgrade_cost", label: "Upg Cost" },
        { key: "special_abilities", label: "Special" },
    ];
```

- [ ] **Step 5: Add the column-label and info helpers**

Just above `function renderTable()` (around line 789), add the new helpers:

```javascript
function scoreColumnLabel(axis, scale) {
    const axisLabel = axis === "hp" ? "HP" : axis === "cost" ? "Cost" : "Speed";
    const scaleLabel = scale === "pop" ? "Pop" : scale === "cost" ? "3k" : "Avg";
    if (axis === "cost") {
        return `${axisLabel} (${scaleLabel}, lower=better)`;
    }
    return `${axisLabel} (${scaleLabel})`;
}

function scoreColumnInfo(axis, scale) {
    const axisDesc = {
        hp:    "HP-based score: 100 × (winner_hp − loser_hp), signed by who won, with λ=2 loss aversion.",
        cost:  "Resource cost (weighted: 0.8 wood + food + 1.5 gold). For a win, cost = my_spent. For a loss, cost = 2 × (my_spent + opp_remaining). Lower is better.",
        speed: "Speed-to-win: linear, T_MAX=120s. Win = +100 × (1 − t/120). Loss = −2 × 100 × (1 − t/120).",
    }[axis];
    const scaleDesc = scale === "average"
        ? "Average of pop (30v30) and cost (3k cost-matched) values."
        : scale === "pop"
            ? "Population-matched (30v30 fixed-count)."
            : "Cost-matched (3k weighted resources, capped at 30 units).";
    return `${axisDesc}\n\n${scaleDesc}\n\nFinal score = 0.7 × GC + (pool-specific role weights). No normalization, no speed/range weighting.`;
}

function roleColumnInfo(role, pool) {
    const lineSets = {
        GC: "militia, knight, archer line opponents",
        AC: pool === "infantry"
            ? "knight, camel, steppe_lancer, elephant line opponents"
            : "knight, camel, steppe_lancer, elephant, light_cav line opponents",
        AT: "spear, skirmisher, light_cav line opponents",
        AA: "archer, skirmisher, cav_archer, gunpowder line opponents",
    };
    return `${role} role: average across ${lineSets[role]}. Within each line: mean adjusted_signed_score (λ=2 loss aversion), deduped by fingerprint. Across lines: equally weighted mean.`;
}
```

- [ ] **Step 6: Manual verification**

```bash
cd D:/AI/aoe2-unit-analyzer && PORT=5002 python webapp/app.py
```

Open http://localhost:5002/. Switch to the Infantry tab — Score, GC, AC, AT columns should now appear in place of the old composite columns. Toggle Score axis and Scale — the displayed Score values should update. Verify Berserker (Vikings → Imperial → infantry) shows roughly +20 at default (HP × Avg) and updates when you switch to HP × Pop (~+8.9). Stop server.

- [ ] **Step 7: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): swap legacy score columns for toggle-driven columns

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Sort behavior — ascending direction for cost axis

**Files:**
- Modify: `webapp/static/js/rankings.js`

When the user clicks a covered tab, default sort is `pool_score` with the axis-natural direction (asc for cost, desc for hp/speed). When the user toggles axis, the sort direction flips to match. Clicking the column header still toggles asc/desc.

- [ ] **Step 1: Update selectLine default sort for covered pools**

Find the `selectLine` function in `rankings.js` (around line 730). Locate the existing `sortColumn = ...` ternary chain (around line 749–760) and replace it with:

```javascript
    if (lineUsesPoolScores(slug)) {
        sortColumn = "pool_score";
        sortDir = scoreAxisDirection(currentScoreAxis);
    } else {
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
                                ? "naval_effectiveness"
                                : "pes";
        sortDir = "desc";
    }
```

(Note: the existing `pool_score` covers the infantry/archery/stable cases; the `else` branch keeps legacy behavior for siege/naval/other.)

- [ ] **Step 2: Manual verification**

```bash
cd D:/AI/aoe2-unit-analyzer && PORT=5002 python webapp/app.py
```

Open http://localhost:5002/. Switch to Infantry tab with default toggles (HP × Avg) — table should sort with highest Score at top. Toggle Score axis to "Resource cost" — table should re-sort with LOWEST cost at top. Click the Score column header — sort flips. Stop server.

- [ ] **Step 3: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): natural sort direction per axis (cost ascending)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Hover card content for Score and role columns

**Files:**
- Modify: `webapp/static/js/rankings.js`

The existing hover-card system (`getHoverCardEl`, `positionHoverCard`, etc.) renders tooltips on numeric cells. For pool_score / pool_gc / pool_ac / pool_at / pool_aa cells we add custom content that includes the shape descriptors for the active scale.

- [ ] **Step 1: Locate the hover dispatch**

Open `webapp/static/js/rankings.js` and search for `SCORE_BREAKDOWN` and `function showHoverCard`. The existing system maps a column key to a renderer in `SCORE_BREAKDOWN`. We add new entries for the pool_score keys.

Find the `SCORE_BREAKDOWN` constant (declared around line 71). At the END of the object (just before the closing `};` around line 167), add:

```javascript
    // Pool-score breakdowns (driven by toggle state).
    pool_score: {
        title: "Score",
        formula: "dynamic",  // sentinel — renderer reads currentScoreAxis/Scale
        subs: "pool_score_breakdown",
    },
    pool_gc: {
        title: "GC (General Combat)",
        formula: "dynamic",
        subs: "pool_role_breakdown",
    },
    pool_ac: {
        title: "AC (Anti-Cav)",
        formula: "dynamic",
        subs: "pool_role_breakdown",
    },
    pool_at: {
        title: "AT (Anti-Trash)",
        formula: "dynamic",
        subs: "pool_role_breakdown",
    },
    pool_aa: {
        title: "AA (Anti-Archer)",
        formula: "dynamic",
        subs: "pool_role_breakdown",
    },
```

- [ ] **Step 2: Add the SCORE_KEYS entries**

Find the `SCORE_KEYS` Set (around line 169). Add the five new keys:

```javascript
    "pool_score",
    "pool_gc",
    "pool_ac",
    "pool_at",
    "pool_aa",
```

Insert these alongside the other entries in the Set.

- [ ] **Step 3: Add the custom hover renderer**

Find where existing custom renderers are dispatched. Search for `siege_breakdown` (a sentinel similar to what we're adding). It's used inside `showHoverCard` or `buildHoverCardHtml` (look for the function that handles hover card content).

Search rankings.js for `subs === "siege_breakdown"`. Just above that line (where it dispatches custom renderers), add a check for our new sentinels:

```javascript
    if (config.subs === "pool_score_breakdown") {
        return renderPoolScoreHover(unitRow, currentScoreAxis, currentScoreScale);
    }
    if (config.subs === "pool_role_breakdown") {
        const role = colKey.replace("pool_", "").toUpperCase();
        return renderPoolRoleHover(unitRow, role, currentScoreAxis, currentScoreScale);
    }
```

(Adjust variable names to match the surrounding code — `unitRow`, `colKey`, etc. may be named differently in `showHoverCard`. Read the function and use whatever local names exist for the unit row and column key.)

- [ ] **Step 4: Implement the renderer functions**

Just above `function renderTable()` (so they're defined before use), add:

```javascript
function _fmt(v, digits = 1) {
    if (v == null) return "—";
    return Number(v).toFixed(digits);
}

function renderPoolScoreHover(unitRow, axis, scale) {
    const ps = unitRow && unitRow.pool_scores;
    if (!ps) return "<div class='hover-empty'>No pool-score data for this unit.</div>";

    const axisLabel = axis === "hp" ? "HP%" : axis === "cost" ? "Resource cost" : "Speed";
    const scaleLabel = scale === "pop" ? "Pop (30v30)" : scale === "cost" ? "Cost (3k)" : "Average";
    const final = getPoolScoreValue(unitRow, axis, scale, "final");
    const gc = getPoolScoreValue(unitRow, axis, scale, "gc");
    const ac = getPoolScoreValue(unitRow, axis, scale, "ac");
    const at = getPoolScoreValue(unitRow, axis, scale, "at");
    const aa = getPoolScoreValue(unitRow, axis, scale, "aa");

    let rolesHtml = "";
    if (gc != null) rolesHtml += `<span class='role'>GC ${_fmt(gc)}</span>`;
    if (ac != null) rolesHtml += `<span class='role'>AC ${_fmt(ac)}</span>`;
    if (at != null) rolesHtml += `<span class='role'>AT ${_fmt(at)}</span>`;
    if (aa != null) rolesHtml += `<span class='role'>AA ${_fmt(aa)}</span>`;

    const decimals = axis === "cost" ? 0 : 2;
    let shapeHtml = "";
    if (scale === "average") {
        const a = ps.scales["30v30"]?.shape;
        const b = ps.scales["3k"]?.shape;
        if (a && b) {
            shapeHtml = `<div class='shape-pair'>
                <div><strong>Pop:</strong> n=${a.n}, win ${_fmt(a.win_rate)}%, cat-loss ${_fmt(a.catastrophic_loss_rate)}%, stddev ${_fmt(a.stddev)}</div>
                <div><strong>Cost:</strong> n=${b.n}, win ${_fmt(b.win_rate)}%, cat-loss ${_fmt(b.catastrophic_loss_rate)}%, stddev ${_fmt(b.stddev)}</div>
            </div>`;
        }
    } else {
        const sk = scale === "pop" ? "30v30" : "3k";
        const sh = ps.scales[sk]?.shape;
        if (sh) {
            shapeHtml = `<div>n=${sh.n}, win ${_fmt(sh.win_rate)}%, cat-loss ${_fmt(sh.catastrophic_loss_rate)}%, stddev ${_fmt(sh.stddev)}</div>`;
        }
    }

    return `<div class='hover-pool-score'>
        <div class='hover-title'>${unitRow.unit_name || unitRow.unit_slug} — ${axisLabel} × ${scaleLabel}</div>
        <div class='hover-final'>final ${_fmt(final, decimals)}</div>
        <div class='hover-roles'>${rolesHtml}</div>
        ${shapeHtml}
        <div class='hover-note'>Final score = 0.7 × GC + pool-specific role weights. λ=2 loss aversion on negative atomic scores. ${axis === "cost" ? "Lower is better." : "Higher is better."}</div>
    </div>`;
}

function renderPoolRoleHover(unitRow, role, axis, scale) {
    const lineSets = {
        GC: "militia, knight, archer line opponents",
        AC: "knight, camel, steppe_lancer, elephant" + (unitRow?.pool_scores?.pool === "infantry" ? "" : ", light_cav") + " line opponents",
        AT: "spear, skirmisher, light_cav line opponents",
        AA: "archer, skirmisher, cav_archer, gunpowder line opponents",
    };
    const value = getPoolScoreValue(unitRow, axis, scale, role.toLowerCase());
    return `<div class='hover-pool-role'>
        <div class='hover-title'>${role} — ${unitRow.unit_name || unitRow.unit_slug}</div>
        <div class='hover-final'>${role} = ${_fmt(value)}</div>
        <div class='hover-note'>Average across ${lineSets[role]}.<br>Within each line: mean adjusted signed score (λ=2). Across lines: equally weighted mean. Deduped by fingerprint.</div>
    </div>`;
}
```

- [ ] **Step 5: Add minimal CSS for the new hover content**

Open `webapp/static/css/rankings.css`. Append:

```css
.hover-pool-score, .hover-pool-role {
    font-size: 12px;
    line-height: 1.5;
    max-width: 360px;
}
.hover-pool-score .hover-title,
.hover-pool-role .hover-title {
    font-weight: 600;
    margin-bottom: 4px;
}
.hover-pool-score .hover-final,
.hover-pool-role .hover-final {
    font-size: 14px;
    margin-bottom: 4px;
}
.hover-pool-score .hover-roles .role {
    display: inline-block;
    margin-right: 8px;
    color: var(--text-muted, #888);
}
.hover-pool-score .hover-note,
.hover-pool-role .hover-note {
    font-size: 11px;
    color: var(--text-muted, #888);
    font-style: italic;
    margin-top: 6px;
}
.hover-pool-score .shape-pair > div {
    margin: 2px 0;
}
.hover-empty {
    color: var(--text-muted, #888);
    font-style: italic;
}
```

- [ ] **Step 6: Manual verification**

```bash
cd D:/AI/aoe2-unit-analyzer && PORT=5002 python webapp/app.py
```

Open http://localhost:5002/. On Infantry tab, hover over a Score cell — you should see a tooltip with final score, role breakdowns, shape descriptors. Hover over a GC cell — should see role-specific tooltip. Toggle scale to "Pop" or "Cost" — shape descriptors should change to show only one scale. Stop server.

- [ ] **Step 7: Commit**

```bash
git add webapp/static/js/rankings.js webapp/static/css/rankings.css
git commit -m "$(cat <<'EOF'
feat(pool-scores-ui): hover cards for Score and role columns with new methodology

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Final smoke test and verification

**Files:** none modified.

Manual end-to-end verification of the full UI integration. No commit in this task — just confirm everything works.

- [ ] **Step 1: Regenerate pool_scores.db (in case any prior runs were stale)**

```bash
cd D:/AI/aoe2-unit-analyzer/webapp && rm -f pool_scores.db && python derive_pool_scores.py
```

Expected: `Wrote 2766 rows ...`.

- [ ] **Step 2: Run the full test suite**

```bash
cd D:/AI/aoe2-unit-analyzer && pytest -q
```

Expected: all tests pass, including the new ones from Tasks 1 and 2.

- [ ] **Step 3: Start dev server and walk the UI**

```bash
PORT=5002 python webapp/app.py
```

In a browser, open http://localhost:5002/ and verify:

1. Toggles appear below the age toggle. Defaults: HP% active, Average active.
2. **Infantry tab → Vikings → Imperial → Berserker:** Score column shows ~+20.25 (HP × Avg).
3. Toggle Score axis to "Resource cost": Score column header updates to "Cost (Avg, lower=better)" and the table re-sorts ascending. Berserker shows ~3234 (avg of 3962 and 2507).
4. Toggle Scale to "Pop": Score updates to ~3961.8 for Berserker.
5. Toggle Scale to "Cost": Score updates to ~2506.9.
6. Switch to Stable tab → Franks → paladin: Score, GC, AC columns show. No AT/AA columns.
7. Switch to Archery tab → Britons → arbalester: Score, GC, AA columns show. No AC/AT.
8. Switch to Siege tab: toggles disappear, footnote appears, legacy "Anti-Building Score" column visible as before.
9. Switch to Naval tab: same as siege — legacy columns, toggles hidden.
10. Hover over a Score cell: tooltip shows axis explanation, role breakdown, shape descriptors.
11. Hover over a GC cell: tooltip shows GC methodology and the GC line set.
12. Hover over a civ name: existing tech/effect tooltip still works (unchanged).
13. Click Castle Age toggle: old castle stats appear, score columns still work (sub-line filtering preserved).

If any check fails, file a bug as a follow-up issue.

- [ ] **Step 4: No commit**

This task is verification only.

---

## Self-review

**1. Spec coverage** (against `2026-04-29-pool-scores-ui-design.md`):
- ✅ Toggle UI (Task 3, 4)
- ✅ Default state HP × Average (Task 4 state vars)
- ✅ Replace legacy score columns for covered pools (Task 5)
- ✅ Existing stats columns preserved (Task 5 — only score-related cols changed)
- ✅ Existing tech/unique-effect hovers preserved (Task 5 doesn't touch civ/unit cell hovers)
- ✅ No normalization, raw values shown (Task 5 — `pool_score` is `getPoolScoreValue` direct read)
- ✅ Cost axis sort ascending (Task 6)
- ✅ Score column header text reflects active toggle (Task 5 — `scoreColumnLabel`)
- ✅ Hover content with shape descriptors (Task 7)
- ✅ Hover for role columns with new methodology (Task 7)
- ✅ Pool coverage: infantry/stable/archery only, siege/naval keep legacy (Task 4 hide/show + Task 5 only modifies covered column blocks)
- ✅ API extension via `/api/ref/unit-line` (Task 2)
- ✅ Backend helper module (Task 1)
- ✅ Berserker reference values verifiable (Task 8 manual checks)
- ⏸ Profile labels — explicitly deferred per spec
- ⏸ Persisted toggle state — explicitly deferred per spec
- ⏸ Cleaning up legacy `battle_scores` — explicitly deferred per spec

**2. Placeholder scan:** No TBD/TODO. Each task has concrete code. Manual verification steps are explicit.

**3. Type / name consistency:**
- `currentScoreAxis`, `currentScoreScale` used consistently across Tasks 4, 5, 6, 7.
- `pool_score`, `pool_gc`, `pool_ac`, `pool_at`, `pool_aa` keys consistent across Tasks 5 (column defs) and 7 (hover sentinels + SCORE_KEYS).
- `getPoolScoreValue(unitRow, axis, scale, role)` signature consistent across Tasks 4, 5, 7.
- `lineUsesPoolScores(slug)` defined in Task 4, used in Tasks 4 and 6.
- `scoreAxisDirection(axis)` defined in Task 4, used in Tasks 4 and 6.
- `scoreColumnLabel`, `scoreColumnInfo`, `roleColumnInfo` defined in Task 5, used in Task 5 column defs.

No drift. Plan is internally consistent.
