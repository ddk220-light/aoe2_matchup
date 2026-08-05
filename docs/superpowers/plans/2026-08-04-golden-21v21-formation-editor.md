# Golden 21v21 Formation Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exact, editable 21-versus-21 formation layer to the Golden Arena viewer and export valid edits as both JSON and a read-back-verified `.aoe2scenario` file.

**Architecture:** Python extracts and rewrites scenario records at the binary boundary; pure JavaScript owns editable placement state and deterministic validation; the canvas renderer only draws and maps pointers. The Node server exposes two narrow read routes and one size-limited scenario-export POST route, using a fixed no-shell Python subprocess and a disposable temporary directory.

**Tech Stack:** Python 3.12, AoE2ScenarioParser 0.8.2, JavaScript ES modules, Node.js 20 built-ins, HTML canvas, Node test runner, pytest.

> **Scope update:** During execution, the user reduced this checkpoint to
> rendering the exact 21-versus-21 placement for visual review. Editable
> placement, JSON export, scenario rewriting, and import/export UI remain
> intentionally deferred unless the placement review shows they are needed.

## Global Constraints

- The immutable source scenario SHA-256 is `a8d11848399a56a13cbf05b4812e5e95939f790b768285c67600c4e24c651113`.
- Retain exactly Player 2 references 1628–1648 and Player 3 references 1699–1719.
- Exported coordinates remain in the source scenario plane; the 90-degree counterclockwise transform is presentation-only.
- Do not introduce movement, targeting, collision physics, attacks, damage, or combat resolution.
- Do not mutate the checked-in source scenario or golden map fixture.
- Add no external npm dependencies.
- Reject out-of-bounds, non-tile-centered, forest-terrain, Gaia-cell, duplicate-cell, wrong-count, duplicate-reference, and wrong-source-hash layouts.
- Scenario export may modify only retained P2/P3 `x` and `y`, remove surplus P2/P3 army units, and preserve all other verified source structures.

---

### Task 1: Exact formation extraction fixture

**Files:**
- Create: `aoe2x/js_simulation/tools/export_golden_formation.py`
- Create: `aoe2x/js_simulation/fixtures/golden_formation_21v21.json`
- Create: `tests/test_cleanroom_formation_export.py`

**Interfaces:**
- Consumes: `extract_map()` from `tools/export_golden_map.py` and the immutable source scenario.
- Produces: `extract_formation(path: Path) -> dict` and schema-version-1 formation JSON with `source`, `sides`, and `validation` fields.

- [ ] **Step 1: Write failing extraction tests**

Assert literal reference arrays, unit constants, first/last positions, 21-per-side counts, source hash, and a zero-conflict validation result. Assert the checked-in JSON equals a fresh `extract_formation()` call.

```python
assert [u["reference_id"] for u in payload["sides"]["2"]] == list(range(1628, 1649))
assert [u["reference_id"] for u in payload["sides"]["3"]] == list(range(1699, 1720))
assert {u["unit_const"] for u in payload["sides"]["2"]} == {726}
assert {u["unit_const"] for u in payload["sides"]["3"]} == {74}
assert payload["validation"] == {"valid": True, "conflicts": []}
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_cleanroom_formation_export.py -q -p no:cacheprovider`

Expected: FAIL because `export_golden_formation` does not exist.

- [ ] **Step 3: Implement literal extraction and conflict audit**

Load player units in parser order, slice the first 21, retain reference ID, player, unit constant/name, x/y/z, and rotation, and audit occupied cells against forest terrain IDs `{10, 56, 128}`, every Gaia object's floored cell, and duplicate unit cells. Never synthesize coordinates.

- [ ] **Step 4: Generate the fixture and verify GREEN**

Run the exporter against `fixtures/source/golden_infvsinf.aoe2scenario`, then rerun the focused pytest file.

- [ ] **Step 5: Review the derived diff**

Confirm the fixture contains 42 unit records, no binary content, and no fields derived from another scenario or tape.

### Task 2: Pure editable formation model

**Files:**
- Create: `aoe2x/js_simulation/src/formation-model.js`
- Create: `aoe2x/js_simulation/tests/formation-model.test.mjs`

**Interfaces:**
- Consumes: validated map fixture plus formation fixture.
- Produces:
  - `validateFormationFixture(fixture, mapFixture) -> frozen fixture`
  - `createFormationEditor({ formation, map }) -> editor`
  - editor methods `snapshot()`, `moveUnit(referenceId, x, y)`, `nudgeSide(playerId, dx, dy)`, `undo()`, `redo()`, `reset()`, and `exportDocument()`.
  - `validatePlacement({ units, map, sourceSha256 }) -> { valid, conflicts }`

- [ ] **Step 1: Write failing behavior tests**

Cover exact initial state, tile-center snapping, valid individual movement, rejection without mutation for every conflict class, atomic side nudge, undo/redo, reset, immutable snapshots, and stable JSON export.

```javascript
const before = editor.snapshot();
const result = editor.moveUnit(1628, 8.61, 9.42);
assert.equal(result.valid, true);
assert.deepEqual(editor.snapshot().unitsByReference[1628].position, { x: 8.5, y: 9.5 });
editor.undo();
assert.deepEqual(editor.snapshot(), before);
```

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test aoe2x/js_simulation/tests/formation-model.test.mjs`

Expected: FAIL because `formation-model.js` does not exist.

- [ ] **Step 3: Implement validation and history**

Use integer cell keys (`floor(x),floor(y)`), snap to `floor(value)+0.5`, preserve source rotations, and maintain bounded past/future snapshot stacks. A failed move or nudge returns conflicts and does not push history.

- [ ] **Step 4: Run focused and existing model tests**

Run: `node --test aoe2x/js_simulation/tests/formation-model.test.mjs aoe2x/js_simulation/tests/map-model.test.mjs`

Expected: PASS.

### Task 3: Formation rendering and picking

**Files:**
- Modify: `aoe2x/js_simulation/viewer/map-renderer.js`
- Modify: `aoe2x/js_simulation/tests/map-renderer.test.mjs`

**Interfaces:**
- Consumes: `renderer.setUnits(units)`, source-plane unit coordinates, selected/hovered reference IDs, and optional drag preview.
- Produces:
  - `inspectAt(x, y)` returning `{ tile, object, unit }`
  - `setUnits(units)`
  - `setUnitSelection(referenceId)`
  - `setDragPreview({ referenceId, x, y, valid } | null)`

- [ ] **Step 1: Add failing scene and hit-test tests**

Assert rotated depth order, player styles, selection by reference ID, nearest-unit picking, and invalid-preview metadata without asserting procedural pixels.

- [ ] **Step 2: Run renderer tests and verify RED**

Run: `node --test aoe2x/js_simulation/tests/map-renderer.test.mjs`

Expected: FAIL because formation APIs are absent.

- [ ] **Step 3: Add placement-marker rendering**

Draw compact team-colored markers centered on projected unit coordinates, a facing tick from source rotation, reference labels behind a toggle, and a red destination-cell preview for invalid drags. Markers are presentation controls, not collision footprints.

- [ ] **Step 4: Preserve Gaia inspection and pointer inversion**

Unit hits take precedence over Gaia hits within the marker pick radius. Map pan/zoom and counterclockwise inverse mapping remain unchanged.

- [ ] **Step 5: Run renderer tests and verify GREEN**

Run the renderer and map-model test files together.

### Task 4: Read-back-verified scenario writer

**Files:**
- Create: `aoe2x/js_simulation/tools/write_edited_scenario.py`
- Create: `tests/test_cleanroom_scenario_writer.py`

**Interfaces:**
- Consumes: source scenario path, layout JSON path, and output path supplied as fixed CLI arguments.
- Produces: `write_edited_scenario(source: Path, layout: dict, output: Path) -> dict` and a scenario binary with exactly 21 retained army units per side.

- [ ] **Step 1: Write failing round-trip tests**

Use a temporary directory. Move one retained unit to a known valid empty cell, write the scenario, read it back, and assert exact P2/P3 reference sets, edited x/y, preserved rotations/unit constants, unchanged map signature, unchanged Gaia signature, and unchanged trigger/AI summaries. Assert invalid layouts create no output.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_cleanroom_scenario_writer.py -q -p no:cacheprovider`

Expected: FAIL because the writer does not exist.

- [ ] **Step 3: Implement strict rewrite**

Verify the source hash before parsing. Match retained records by `(player_id, reference_id)`, remove every surplus P2/P3 army unit, modify only `x` and `y`, write to a non-existing temporary output, parse the output, compare source/output structural summaries, and atomically move the verified file to the requested output.

- [ ] **Step 4: Add fixed CLI entry point**

Accept only `--source`, `--layout`, and `--output`; return nonzero on validation failure; emit a compact JSON success summary on stdout. Do not accept unit constants or executable commands from input.

- [ ] **Step 5: Run writer and extraction tests**

Run both formation-related pytest files plus `tests/test_cleanroom_map_export.py`.

### Task 5: Size-limited scenario export HTTP boundary

**Files:**
- Modify: `aoe2x/js_simulation/server.mjs`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

**Interfaces:**
- Adds `GET /api/formation` returning the derived formation fixture.
- Adds `POST /api/export/scenario` accepting layout JSON and returning `application/octet-stream` with attachment filename `golden_infvsinf_21v21_edited.aoe2scenario`.

- [ ] **Step 1: Write failing route tests**

Assert formation GET, method rejection, malformed JSON, request-too-large rejection, invalid-layout structured response, valid binary response headers/body, no public source-binary route, and cleanup after success/failure.

- [ ] **Step 2: Run server tests and verify RED**

Run: `node --test aoe2x/js_simulation/tests/server.test.mjs`

Expected: FAIL with missing formation/export routes.

- [ ] **Step 3: Implement request parsing and structured errors**

Limit the body to 256 KiB, set `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`, and return `{ error: { code, message, conflicts? } }` for 4xx responses.

- [ ] **Step 4: Implement safe scenario generation**

Create a unique directory under the OS temporary directory, write the submitted JSON, call `python -X utf8 tools/write_edited_scenario.py` with an argument array and `shell: false`, `windowsHide: true`, and a timeout, return the verified bytes, and recursively remove only the resolved unique temporary directory in `finally`.

- [ ] **Step 5: Run server tests and verify GREEN**

Run server tests, then all Node tests.

### Task 6: Formation editor interface and downloads

**Files:**
- Modify: `aoe2x/js_simulation/viewer/index.html`
- Modify: `aoe2x/js_simulation/viewer/styles.css`
- Modify: `aoe2x/js_simulation/viewer/app.js`
- Modify: `aoe2x/js_simulation/README.md`

**Interfaces:**
- Loads `api/map` and `api/formation`.
- Downloads JSON locally through a revoked Blob URL.
- Posts the same `exportDocument()` to `api/export/scenario` and downloads the binary response.

- [ ] **Step 1: Replace Stage 0 copy with Stage 1 placement language**

Keep the existing visual system while adding side counts, layout-valid status, undo/redo/reset, side nudge controls, unit-label toggle, selected-unit ledger, conflict list, and two explicit download buttons.

- [ ] **Step 2: Integrate editor state and drag semantics**

Pointer-down on a unit starts a unit drag; pointer-down elsewhere retains map pan/pinch behavior. Pointer movement previews the snapped cell. Pointer-up commits only a valid move. Keyboard Escape cancels a drag.

- [ ] **Step 3: Implement exports and visible failures**

Disable downloads when invalid. JSON uses `Blob`, `URL.createObjectURL()`, a temporary same-origin download anchor, and `URL.revokeObjectURL()`. Scenario export reports progress, handles structured server errors without losing state, and downloads the response Blob.

- [ ] **Step 4: Make desktop and phone controls usable**

Keep all controls visible without horizontal page overflow. On phone, use a compact stacked action tray and a full-width selected-unit ledger beneath the map.

- [ ] **Step 5: Update README**

Document Stage 1 scope, exact retained references, validation rules, both exports, local requirements, and commands.

### Task 7: Integrated verification and Tailnet review

**Files:**
- Modify only files required by failures found during verification.

**Interfaces:**
- Verifies the complete user-visible workflow at `https://dragonstar.tail82a190.ts.net/golden-map` with and without a trailing slash.

- [ ] **Step 1: Run full automated verification**

```powershell
python -m pytest tests/test_cleanroom_map_export.py tests/test_cleanroom_formation_export.py tests/test_cleanroom_scenario_writer.py -q -p no:cacheprovider
node --test aoe2x/js_simulation/tests
git diff --check -- aoe2x/js_simulation tests docs/superpowers/plans/2026-08-04-golden-21v21-formation-editor.md
```

- [ ] **Step 2: Verify the live desktop workflow**

Confirm 21/21 counts, zero initial conflicts, exact selected reference/coordinate display, valid drag, invalid tree-cell rejection, undo, reset, JSON download contents, scenario download headers/body, and no console errors.

- [ ] **Step 3: Verify phone layout**

Use a 390-by-844 viewport, confirm controls and downloads are reachable without page-width overflow, then reset the viewport.

- [ ] **Step 4: Verify both Tailnet URL forms**

Open `/golden-map` and `/golden-map/` in fresh navigations and confirm both fixtures and export endpoint resolve under the mount path.

- [ ] **Step 5: Final source-integrity check**

Recompute the source scenario SHA-256 and confirm the checked-in binary and `golden_map.json` are unchanged. Report any remaining limitation without introducing later-stage physics.
