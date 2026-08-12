# Local Clean-Room Battle Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the local clean-room viewer shell with a website-style Battle Simulation page that exposes only the 14 tested unit/civilization combinations and plays the new engine on the isometric Golden Arena.

**Architecture:** Keep `server.mjs`, `/api/fight`, and the clean-room renderer as the execution path. Add a deterministic display catalogue, a pure browser picker/request-state module, and a website-compatible viewer shell. Shared website assets are served through an explicit local-only allowlist; no old engine code is loaded.

**Tech Stack:** Node.js ES modules and test runner, browser HTML/CSS/Canvas, Python standard-library SQLite exporter.

## Global Constraints

- Do not modify the production website template, engine, routes, or deployment configuration.
- Do not add random simulation variation or a seed control.
- `UNIT_REGISTRY` remains the only authority for runnable unit/civilization combinations.
- Do not expose clean-room source archives, calibration fixtures, mechanics fixtures, or reports over HTTP.
- Preserve all unrelated dirty-worktree changes.

---

### Task 1: Deterministic Display Catalogue

**Files:**
- Create: `aoe2x/js_simulation/tools/export_viewer_catalogue.py`
- Create: `aoe2x/js_simulation/fixtures/viewer_unit_catalogue.json`
- Create: `tests/test_viewer_catalogue_export.py`
- Modify: `aoe2x/js_simulation/src/unit-registry.js`

**Interfaces:**
- Produces JSON `{schemaVersion, source, civilizations:[{name, units:[...]}]}`.
- Adds an explicit `catalogueName` to registry rows whose website display name differs from the engine label.

- [ ] Write a failing exporter test using a temporary SQLite database. Assert stable ordering, source SHA-256, and literal exported fields.
- [ ] Run `python -m pytest tests/test_viewer_catalogue_export.py -q -p no:cacheprovider` and confirm failure because the exporter does not exist.
- [ ] Implement the exporter with `sqlite3`, `hashlib`, `json`, and atomic replacement.
- [ ] Add explicit catalogue names where required and fail generation on a missing or ambiguous `(civ, catalogueName)` join.
- [ ] Regenerate the committed catalogue from `data/golden/aoe2_reference.db`.
- [ ] Run the focused Python test and confirm it passes.

### Task 2: Catalogue and Budget HTTP Contracts

**Files:**
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`
- Modify: `aoe2x/js_simulation/tests/fight.test.mjs` or the nearest existing fight contract test
- Modify: `aoe2x/js_simulation/server.mjs`
- Modify: `aoe2x/js_simulation/src/fight.js`
- Modify: `aoe2x/js_simulation/src/purchase.js`

**Interfaces:**
- `GET /api/catalogue` returns the display catalogue plus exact enabled engine mappings.
- `GET /api/fight?...&budget=<integer>` derives equal-resource counts; explicit counts and budget are mutually exclusive.

- [ ] Write failing server tests for catalogue availability, exact 14-row mapping, unsupported slugs, budget parsing, and source denial.
- [ ] Write a failing fight test proving a non-default budget changes counts while omitted budget remains byte-identical to the current result.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Extend request parsing and `runFight(root, selection)` with an optional validated budget passed to `deriveCounts`.
- [ ] Add `/api/catalogue` with immutable cached JSON and registry-derived enabled mappings.
- [ ] Run focused server/fight tests and confirm they pass.

### Task 3: Pure Picker and Request State

**Files:**
- Create: `aoe2x/js_simulation/viewer/battle-state.js`
- Create: `aoe2x/js_simulation/tests/battle-state.test.mjs`

**Interfaces:**
- `createBattleState({catalogue, units, capacityByFamily})`
- `selectCivilization(state, team, civ)`
- `selectUnit(state, team, catalogueKey)`
- `searchCatalogue(state, query)`
- `buildFightQuery(state)`
- `applyFightResult(state, result)`

- [ ] Write failing tests for civ-first navigation, exactly enabled combinations, disabled search results, count capacity, equal-resource query construction, and unsupported deep links.
- [ ] Run the test and confirm failure because the module does not exist.
- [ ] Implement immutable/data-oriented state helpers without DOM dependencies.
- [ ] Run the battle-state tests and confirm they pass.

### Task 4: Website-Style Viewer Shell

**Files:**
- Modify: `aoe2x/js_simulation/viewer/index.html`
- Modify: `aoe2x/js_simulation/viewer/styles.css`
- Create: `aoe2x/js_simulation/viewer/battle-page.js`
- Modify: `aoe2x/js_simulation/viewer/app.js`
- Modify: `aoe2x/js_simulation/server.mjs`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

**Interfaces:**
- Existing renderer/playback functions remain the map implementation.
- `battle-page.js` owns DOM picker/options behavior and calls an injected `loadFight(query)` adapter.
- The server exposes only allowlisted shared `base.css`, `simulate.css`, constants, and image assets.

- [ ] Add failing server/page tests for production-compatible control IDs, disabled upgrade mode, calibration disclosure, and forbidden old-engine assets.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Replace the viewer shell with the Battle Simulation markup and accessible picker rails.
- [ ] Implement catalogue rendering, search, supported/disabled cards, modes, Start/New Battle, live summaries, and URL state.
- [ ] Layer viewer CSS over the shared website styling for the isometric arena and disabled status.
- [ ] Wire the existing playback/renderer into the new page lifecycle.
- [ ] Run focused server and state tests until green.

### Task 5: Diagnostics and Review Export

**Files:**
- Modify: `aoe2x/js_simulation/viewer/simulation-review.js`
- Modify: `aoe2x/js_simulation/viewer/battle-page.js`
- Modify: `aoe2x/js_simulation/viewer/index.html`
- Modify: `aoe2x/js_simulation/tests/simulation-review.test.mjs`

**Interfaces:**
- Review export includes `{pair, mode, budget, counts, winner, winnerHp, finalStateHash, eventLogHash, flagged, note}`.

- [ ] Write failing tests for the enriched review payload and event-derived damage summary.
- [ ] Run the tests and confirm expected failures.
- [ ] Add the collapsible calibration panel and damage summary without old-engine formulas.
- [ ] Implement the enriched review export and preserve existing local-storage behavior.
- [ ] Run review tests and confirm they pass.

### Task 6: Integrated Verification

**Files:**
- Modify: `aoe2x/js_simulation/README.md`

**Interfaces:** None; this task verifies the completed local product.

- [ ] Document the local launch URL, tested-unit restriction, deterministic behavior, and two supported battle modes.
- [ ] Run focused Python catalogue tests.
- [ ] Run Node battle-state, server, fight, and review tests.
- [ ] Run the complete clean-room Node suite and record any pre-existing failures separately from viewer failures.
- [ ] Launch the local server and inspect desktop and mobile layouts in a browser.
- [ ] Verify one equal-number and one equal-resource fight, Pause/Resume, speed, New Battle, disabled-unit handling, and feedback export.
- [ ] Review `git diff --check`, `git status --short`, and the final diff to ensure no production or unrelated files changed.
