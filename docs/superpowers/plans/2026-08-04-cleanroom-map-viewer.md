# Clean-Room Golden Map Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Tailnet-viewable, map-only inspector that renders the exact
terrain and Gaia object placement shared by the golden recording scenarios.

**Architecture:** Export one authoritative `.aoe2scenario` into a versioned,
read-only JSON fixture with a Python parser tool, then render it through a new
dependency-free Canvas 2D JavaScript application. Pure coordinate and map-model
functions remain separate from the renderer and are covered by Node's built-in
test runner. A small local-only Node HTTP server serves the viewer and map API.

**Tech Stack:** Python 3.12, AoE2ScenarioParser 0.8.2, JavaScript ES modules,
Canvas 2D, Node.js 20 built-in `node:test` and `node:http`.

## Global Constraints

- Work only under `aoe2x/js_simulation/`, its tests, and this plan document.
- Do not import behavior or rendering code from `apps/website/static/js/engine/`
  or `simulation_v2/`.
- Do not modify production website files, databases, or deployment settings.
- Stage 0 contains no units, simulator clock, targeting, movement, or combat.
- Use `golden_infvsinf.aoe2scenario` as the checked-in source fixture because
  Champion-versus-Champion is the next stage.
- Record that `golden_infvsinf`, `golden_rangedvsinf`, and
  `golden_cavvsranged` have identical terrain and Gaia-object hashes before
  selecting the infantry scenario.
- Preserve literal terrain tiles and Gaia coordinates; do not replace the
  central obstruction with a circle or inferred mask.
- The server binds to `127.0.0.1` by default and accepts an explicit host/port
  for Tailnet use.
- No external npm dependencies.

---

### Task 1: Establish the authoritative map fixture

**Files:**

- Create: `aoe2x/js_simulation/fixtures/source/golden_infvsinf.aoe2scenario`
- Create: `aoe2x/js_simulation/tools/export_golden_map.py`
- Create: `tests/test_cleanroom_map_export.py`
- Create: `aoe2x/js_simulation/fixtures/golden_map.json`

**Interfaces:**

- Consumes: `AoE2DEScenario.from_file(path)` and the source scenario binary.
- Produces: `extract_map(path: Path) -> dict` and the `golden_map.json` schema:
  `{schema_version, source, map, terrain_counts, object_counts}`.

- [ ] **Step 1: Copy the binary scenario fixture from the repository object**

Copy the already-extracted repository object from
`.scratch/stage0_golden_scenarios_20260804/apps/video/templates/golden_infvsinf.aoe2scenario`
to `aoe2x/js_simulation/fixtures/source/golden_infvsinf.aoe2scenario`. Verify its
SHA-256 is
`a8d11848399a56a13cbf05b4812e5e95939f790b768285c67600c4e24c651113`.

- [ ] **Step 2: Write the failing exporter tests**

The test imports `extract_map` and asserts:

```python
payload = extract_map(SCENARIO)
assert payload["schema_version"] == 1
assert payload["map"]["width"] == 16
assert payload["map"]["height"] == 16
assert len(payload["map"]["tiles"]) == 256
assert len(payload["map"]["gaia_objects"]) == 101
assert payload["terrain_counts"] == {
    "6:DIRT_1": 156,
    "10:FOREST_OAK": 7,
    "56:FOREST_RAINFOREST": 1,
    "128:FOREST_DRY_SOUTH_AMERICAN": 92,
}
assert payload["object_counts"]["1348:TREE_ITALIAN_PINE"] == 32
assert payload["object_counts"]["2082:PANDA_ROCK"] == 1
```

It also asserts unique `(x, y)` tile coordinates and stable sorting by `y, x`.

- [ ] **Step 3: Run the exporter test and verify RED**

Run:

```powershell
python -m pytest tests/test_cleanroom_map_export.py -q
```

Expected: collection/import failure because `export_golden_map.py` does not
exist.

- [ ] **Step 4: Implement the minimal scenario exporter**

Implement:

```python
def extract_map(path: Path) -> dict:
    scenario = AoE2DEScenario.from_file(str(path))
    # Serialize all tiles and Gaia objects exactly; names come from
    # TerrainId, UnitInfo, and OtherInfo. Unknown IDs retain an UNKNOWN_<id>
    # name rather than being dropped.
```

Each tile contains `x`, `y`, `terrain_id`, `terrain_name`, `elevation`, and
`layer`. Each Gaia object contains `reference_id`, `unit_const`, `name`, `x`,
`y`, `z`, `rotation`, and `status`. Source metadata contains scenario filename,
SHA-256, parser version, scenario version, and repository ref.

- [ ] **Step 5: Run the exporter test and verify GREEN**

Run the same pytest command. Expected: all tests pass.

- [ ] **Step 6: Generate and validate `golden_map.json`**

Run:

```powershell
python aoe2x/js_simulation/tools/export_golden_map.py `
  --scenario aoe2x/js_simulation/fixtures/source/golden_infvsinf.aoe2scenario `
  --output aoe2x/js_simulation/fixtures/golden_map.json
```

Re-run the exporter test and confirm the checked-in JSON equals
`extract_map(SCENARIO)`.

---

### Task 2: Implement the pure map model and isometric transform

**Files:**

- Create: `aoe2x/js_simulation/package.json`
- Create: `aoe2x/js_simulation/src/map-model.js`
- Create: `aoe2x/js_simulation/tests/map-model.test.mjs`

**Interfaces:**

- Consumes: the exported JSON object.
- Produces:
  - `validateMapFixture(data) -> frozen map fixture`
  - `createProjection({mapWidth, mapHeight, tileWidth, tileHeight, originX, originY})`
  - projection methods `tileToScreen(x, y, elevation)` and
    `screenToTile(screenX, screenY)`
  - `sortObjectsForRender(objects) -> array`
  - `objectAtTile(objects, x, y, radius) -> object | null`

- [ ] **Step 1: Write failing Node tests**

Tests must cover:

```javascript
const projection = createProjection({
  mapWidth: 16, mapHeight: 16,
  tileWidth: 72, tileHeight: 36,
  originX: 640, originY: 80,
});
for (const point of [{x: 0, y: 0}, {x: 8, y: 8}, {x: 15.5, y: 15.5}]) {
  const screen = projection.tileToScreen(point.x, point.y, 0);
  const tile = projection.screenToTile(screen.x, screen.y);
  assert.ok(Math.abs(tile.x - point.x) <= 0.001);
  assert.ok(Math.abs(tile.y - point.y) <= 0.001);
}
```

Also test schema rejection, 256 unique tiles, render ordering by isometric depth,
and nearest-object selection.

- [ ] **Step 2: Run Node tests and verify RED**

Run:

```powershell
node --test aoe2x/js_simulation/tests/map-model.test.mjs
```

Expected: module-not-found failure for `src/map-model.js`.

- [ ] **Step 3: Implement the minimal pure functions**

Use the conventional isometric transform:

```javascript
screenX = originX + (x - y) * tileWidth / 2;
screenY = originY + (x + y) * tileHeight / 2 - elevation * elevationHeight;
```

The inverse must ignore elevation for cursor-to-ground lookup because Stage 0's
source map is flat. Reject non-16×16 or incomplete fixtures with clear errors.

- [ ] **Step 4: Run Node tests and verify GREEN**

Run the same Node command. Expected: all tests pass.

---

### Task 3: Build the map-only inspector UI

**Files:**

- Create: `aoe2x/js_simulation/viewer/index.html`
- Create: `aoe2x/js_simulation/viewer/styles.css`
- Create: `aoe2x/js_simulation/viewer/app.js`
- Create: `aoe2x/js_simulation/viewer/map-renderer.js`

**Interfaces:**

- Consumes: `GET /api/map` and functions from `src/map-model.js`.
- Produces: a responsive map inspector with Canvas 2D rendering and read-only
  controls.

- [ ] **Step 1: Add a failing render-scene behavior test**

Add `map-renderer.test.mjs`. Load the real fixture and call the renderer's pure
`buildRenderScene(map)` boundary. Assert it returns exactly 256 terrain draw
records and 101 depth-sorted Gaia draw records, preserves the Panda Rock at
`(9.0, 7.0)`, and retains all eight tree/bush object categories. This catches a
renderer that drops or moves source objects without asserting on HTML source.

- [ ] **Step 2: Run the contract test and verify RED**

Expected: module-not-found failure for `viewer/map-renderer.js`.

- [ ] **Step 3: Implement the semantic HTML and visual system**

Use an “archivist's field table” direction: deep charcoal framing, warm parchment
panels, oxidized-brass accents, and a natural jungle-green map. Use Georgia for
the display face and Verdana for compact instrument labels so no network font is
required. Avoid generic dashboard cards and purple gradients.

The page must include:

- map title and verified-source badge;
- a large central canvas;
- compact overlay controls suitable for phone use;
- object/terrain counts;
- selected-object inspector;
- cursor tile coordinates;
- a clear “MAP ONLY · NO SIMULATION LOADED” status.

- [ ] **Step 4: Implement the renderer**

Render all 256 ground diamonds from the exact terrain fixture. Use distinct
procedural tree silhouettes for pine, monkey puzzle, acacia, green oak, olive,
forest oak, rainforest, and bush; render the Panda Rock separately. Object
positions and depth ordering must come directly from the fixture.

Implement toggles for grid, objects, labels, and obstruction footprints. Add
wheel/pinch zoom, pointer drag pan, reset view, hover highlight, and tap/click
selection. Controls change presentation only and never mutate fixture data.

- [ ] **Step 5: Run all Node tests and verify GREEN**

Run:

```powershell
node --test aoe2x/js_simulation/tests
```

Expected: all tests pass.

---

### Task 4: Add the isolated local server

**Files:**

- Create: `aoe2x/js_simulation/server.mjs`
- Create: `aoe2x/js_simulation/tests/server.test.mjs`
- Create: `aoe2x/js_simulation/README.md`

**Interfaces:**

- Consumes: viewer files, source modules, and `fixtures/golden_map.json`.
- Produces: `createMapServer({root})`, `GET /`, static module routes, and
  `GET /api/map`.

- [ ] **Step 1: Write failing server tests**

Start `createMapServer` on an ephemeral port and assert:

- `/` returns HTML and status 200;
- `/api/map` returns schema version 1 and 101 Gaia objects;
- `/src/map-model.js` returns JavaScript;
- traversal such as `/../package.json` returns 404;
- unknown paths return 404;
- responses include `Cache-Control: no-store`.

- [ ] **Step 2: Run server tests and verify RED**

Run:

```powershell
node --test aoe2x/js_simulation/tests/server.test.mjs
```

Expected: module-not-found failure for `server.mjs`.

- [ ] **Step 3: Implement the minimal Node HTTP server**

Use `node:http`, `node:fs/promises`, `node:path`, and `node:url` only. Resolve
every static path under an allow-listed root and reject paths that escape it.
Command-line options are `--host` and `--port`, defaulting to `127.0.0.1:5011`.

- [ ] **Step 4: Document local use and source provenance**

The README must show:

```powershell
node aoe2x/js_simulation/server.mjs --host 127.0.0.1 --port 5011
```

It must state that this is a non-production map-only viewer, identify the source
scenario SHA-256, and explain how to regenerate the JSON fixture.

- [ ] **Step 5: Run all tests and verify GREEN**

Run both pytest and Node test suites. Expected: all tests pass with no warnings.

---

### Task 5: Visual verification and Tailnet handoff

**Files:**

- Modify only if verification finds defects in the files created above.

**Interfaces:**

- Consumes: running local server.
- Produces: verified local and Tailnet URLs plus a user-reviewable Stage 0 map.

- [ ] **Step 1: Start the server locally**

Run the Node server on `127.0.0.1:5011` in the background.

- [ ] **Step 2: Inspect the page in the browser**

Verify desktop and phone-sized layouts, all overlays, pan/zoom, selection,
source badge, and absence of console errors. Capture a screenshot for visual
inspection.

- [ ] **Step 3: Check the current Tailscale Serve configuration**

Use read-only status first. If the existing Tailnet hostname can safely proxy
the new local port without affecting production, update the local Tailnet serve
mapping and verify the HTTPS URL. This is local diagnostic hosting, not a
production deployment.

- [ ] **Step 4: Run final verification**

Run:

```powershell
python -m pytest tests/test_cleanroom_map_export.py -q
node --test aoe2x/js_simulation/tests
git diff --check -- aoe2x/js_simulation tests/test_cleanroom_map_export.py
```

Expected: all tests pass, no whitespace errors, no production files changed.

- [ ] **Step 5: Stop at the Stage 0 user-approval gate**

Provide the Tailnet URL and request visual feedback. Do not add units or combat
logic until the user approves the map.
