# HC Physics-Radius Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task by task.

**Goal:** Make the Hand Cannoneer calibration viewer display every unit at its exact simulation collision radius, then document how current AoE2 unit collision fields and observed FINAL-tape compression relate to simulation behavior.

**Architecture:** Add a calibration-only renderer that reuses the shared simulation renderer for the arena, effects, projectiles, and result overlay while suppressing its decorative unit sprites. The calibration renderer then draws unit discs directly from `unit.radius`, with an inward stroke and a one-tile ruler. Serve that renderer through every HC comparison bundle without changing production website rendering or combat mechanics. A separate read-only audit extracts collision-related fields from the currently installed Genie `.dat` and compares them with spacing observed only in the locked FINAL tape.

**Tech Stack:** Browser JavaScript modules, Python HTTP server and pytest, Node smoke test, `genieutils` through the project’s configured Conda Python, Markdown diagnostics.

**Global constraints:**

- Use only `calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip` as tape truth.
- Do not read, derive from, or restore archived/older tape results.
- Keep all changes in calibration, test, tool, and documentation paths; do not alter production combat rendering or deployment state.
- The visible edge of a unit disc must equal `unit.radius`; HP bars and labels are annotations, not geometry.

---

## Task 1: Add a failing exact-radius viewer test

**Files:**

- Modify: `tests/test_hc_compare_viewer.py`

- [ ] Add a test asserting that the calibration viewer exposes `/bundle/h1/physics_renderer.js`.
- [ ] Assert that the module draws from `unit.radius`, contains the `TILE_SIZE` ruler, does not use `unit.drawRadius`, and is selected by `app.js`.
- [ ] Run the focused pytest and confirm it fails because the calibration renderer does not exist yet.

## Task 2: Implement the calibration-only physics renderer

**Files:**

- Create: `calibration/viewer/physics_renderer.js`
- Modify: `calibration/viewer/app.js`
- Modify: `calibration/viewer/hc_compare_server.py`
- Modify: `calibration/viewer/hc_variant_smoke.mjs`

- [ ] Implement `PhysicsSimRenderer`, preserving the shared renderer’s non-unit layers while replacing decorative unit drawings with exact-radius discs.
- [ ] Draw fill to `unit.radius` and an inward boundary stroke whose outside edge never exceeds that radius.
- [ ] Keep team color, death state, attack indication, HP bars, and target overlays readable without changing geometry.
- [ ] Add a 30-pixel/one-tile ruler using the engine’s `TILE_SIZE` constant.
- [ ] Route the module through Base, Recovery, H1, H2, and H3 bundles and load it from the viewer app.
- [ ] Extend the Node smoke test to instantiate the new renderer.
- [ ] Run focused and full viewer tests until green.

## Task 3: Verify the live local and Tailnet viewer

**Files:**

- Verify: `calibration/viewer/index.html`
- Verify: `calibration/viewer/app.js`
- Verify: `calibration/viewer/physics_renderer.js`

- [ ] Restart only the calibration viewer process so the new server route is active.
- [ ] Fetch the local HC comparison URL and every physics-renderer bundle route.
- [ ] Run the browser/Node smoke checks for the top three HC problem matchups across Base, H1, H2, and H3.
- [ ] Verify the existing Tailnet URL returns the updated viewer and report the direct phone link.

## Task 4: Extract current Genie collision data

**Files:**

- Create: `tools/simjs/collision_dat_audit.py`
- Create: `calibration/analysis/current_genie_collision_fields.json`

- [ ] Inspect the installed `genieutils` model and current `empires2_x2_p1.dat` for collision, obstruction, clearance, outline, and minimum-size multiplier fields.
- [ ] Resolve the exact standard-unit IDs from project configuration rather than matching ambiguous display names.
- [ ] Export the relevant per-unit values with source path, source file timestamp/hash, unit IDs, and extraction timestamp.
- [ ] Add a self-check that all standard units are present and numeric radius fields are sane.

## Task 5: Compare Genie fields with FINAL-tape spacing and research engine behavior

**Files:**

- Create: `calibration/analysis/collision_behavior_diagnostics.md`
- Create or modify: `tools/simjs/collision_tape_audit.py`

- [ ] Validate the FINAL ZIP SHA-256 before reading it.
- [ ] Calculate same-owner nearest-neighbor spacing by standard unit, matchup family, and observed command/activity where available.
- [ ] Distinguish nominal collision diameter from observed transient spacing; quantify how often units are closer than the nominal diameter.
- [ ] Research primary sources for collision-size patches, obstruction-type semantics, and parser field definitions.
- [ ] State which behavior is directly evidenced, which is inferred, and what remains unverified—especially patrol/formation-dependent compression.
- [ ] Recommend the smallest simulation experiments that could isolate runtime compression without treating old tapes as evidence.

## Task 6: Final verification and handoff

**Files:**

- Verify all changed files above.

- [ ] Run the complete HC viewer pytest file, Node smoke test, JavaScript syntax checks, and Python syntax checks.
- [ ] Re-run the collision extraction and FINAL-tape audit from scratch and verify deterministic outputs.
- [ ] Inspect `git diff` to confirm no production renderer or old-tape path changed.
- [ ] Summarize the exact UI result, extracted collision fields, tape deltas, research findings, remaining uncertainty, and Tailnet link.
