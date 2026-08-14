# Hand Cannoneer Clearance-Grid Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give Hand Cannoneers a deterministic obstruction-grid route for their recorded move orders so their eight melee matchups reproduce tape outcomes more closely, while preserving the existing Heavy Cavalry Archer behavior bit-for-bit.

**Architecture:** Add a Hand-Cannoneer-only `kitedPath: "clearance_grid"` property to the generated kite profile. Generalize the existing deterministic chase A* so it can plan to a coordinate, then keep a separate per-kiter waypoint cache in `kiteState` and use it only while a profiled kiter executes a move order. Preserve the existing local `kitedEscape` switch and HCA path exactly. Measure the authorized standard-units tape corpus reproducibly and evaluate the implementation with fixed starts, five samples for stable rows, and 100 for volatile rows.

**Tech Stack:** Node.js ES modules and `node:test`; Python 3 standard library for archive/trace measurements; existing clean-room simulator and standard-units runners.

**Global constraints:** Use only the manifest-pinned standard-units archive (`38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`); do not edit derived fixtures by hand; do not add opponent-specific switches or constants; preserve the measured 240-tick Hand Cannoneer volley; keep HCA bit-identical; do not touch `AGENTS.md`.

### Task 1: Pin the Hand Cannoneer profile contract

**Files:**
- Modify: `aoe2x/js_simulation/tests/kite-profiles.test.mjs`
- Modify: `aoe2x/js_simulation/tools/derive_kite_profiles.py`
- Regenerate: `aoe2x/js_simulation/src/kite-profiles.js`

1. Add a failing test asserting `KITE_PROFILES.hand_cannoneer.kitedPath === "clearance_grid"`, every other profile has no `kitedPath`, and the existing cadence fields remain unchanged.
2. Run `node --test tests/kite-profiles.test.mjs` and confirm the new assertion fails for the missing property.
3. Extend only the Hand Cannoneer generator row with `kitedPath: "clearance_grid"`; retain the cadence construction and make the provenance explicit that the path choice is derived from standard-units movement/contact evidence.
4. Regenerate `src/kite-profiles.js` and rerun the focused test to green.

### Task 2: Generalize the deterministic grid planner

**Files:**
- Create: `aoe2x/js_simulation/tests/chase-path.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/chase-path.js`

1. Add focused failing tests for a coordinate-goal planner: clear line returns `null`; a blocking body produces a deterministic waypoint that clears it; trapped starts return `{stand:true}`; input objects are not mutated.
2. Run `node --test tests/chase-path.test.mjs` and confirm the missing export failure.
3. Extract the common A* implementation behind `planChaseAim`; export `planMoveAim(mover, goal, obstacles, map)` for coordinate goals while keeping `planChaseAim` behavior and signature intact.
4. Rerun the focused planner tests and existing movement/target tests.

### Task 3: Route only profiled Hand Cannoneer move orders

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/ai-orders.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Create: `aoe2x/js_simulation/tests/kited-clearance-path.test.mjs`

1. Add failing integration tests showing a `clearance_grid` kiter routes around a unit body, an otherwise identical unprofiled kiter keeps the old direct proposal, path state is cleared/replanned when the move-order coordinate changes, and HCA output hashes are identical with the feature present.
2. Run the new test file and confirm failures occur before implementation.
3. Copy optional `kitedPath` through `createKiteState` without changing profiles lacking the property.
4. Add `kiteState.kitedWaypoints`, separate from `chaseWaypoints`. For move-ordered units owned by the kiting side and carrying `clearance_grid`, plan against every other living collision body, reusing a plan only for the same order coordinate until the existing phased 0.5-second repath boundary.
5. Feed the planned coordinate into the ordinary movement proposal. Preserve all downstream local avoidance/collision resolution and preserve the `kitedEscape` path unchanged.
6. Rerun focused integration, planner, kite-profile, movement-collision, and world tests.

### Task 4: Make the tape motion measurement reproducible

**Files:**
- Create: `aoe2x/js_simulation/tools/measure_hand_cannoneer_kiting.py`
- Create: `tests/test_hand_cannoneer_kiting.py`
- Generate: `aoe2x/js_simulation/calibration/fixtures/standard_units/hand_cannoneer_kite_measurements.json`

1. Add failing Python tests for archive hash rejection, canonical row discovery, stable deterministic output, 240-tick/4-second volley preservation, and all eight canonical HC-vs-melee rows.
2. Implement the analyzer using the manifest-pinned project-local archive and decoded `frames.bin` traces. Record source members, tape run counts, contact exposure, contact-window duration, one-second escape rate, and one-second displacement. Do not infer or modify formation starts.
3. Run the analyzer twice and assert byte-identical output; then run the Python test file.

### Task 5: Run the acceptance experiment

**Files:**
- Create or modify: `aoe2x/js_simulation/tools/run_hand_cannoneer_clearance_suite.mjs`
- Generate: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_clearance_grid_results_2026-08-08.json`
- Generate: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_clearance_grid_results_2026-08-08.md`

1. Build a deterministic A/B runner over the eight canonical Hand Cannoneer owner-2 rows using exact imported tape starts. Use five samples for stable rows and 100 for the ten volatile benchmark rows; include the pre-change control, candidate result, tape score, absolute delta, winner counts, and regression flags.
2. Add the HCA-vs-Champion identity gate comparing final result and simulation hashes under the unchanged HCA configuration.
3. Execute the suite and apply the approved gates equally across the eight HC rows: no stable-winner regression; no greater-than-10-point regression on currently good rows; HCA bit-identical; aggregate HC error must improve and the previously greater-than-25-point rows must be reported explicitly.
4. If a gate fails, diagnose from per-row motion/contact outputs and make only unit-profile-level adjustments. Do not add opponent-specific logic. Repeat red/green tests and the suite after each adjustment.

### Task 6: Verify and hand off

**Files:**
- Verify all modified/generated files above.

1. Run `python -m unittest tests/test_hand_cannoneer_kiting.py`.
2. Run the focused Node tests for planner, kited routing, kite profiles, standard-units comparison, and runners.
3. Run `npm test` from `aoe2x/js_simulation`.
4. Re-verify the authorized ZIP SHA-256 and rerun the final comparison suite once from a clean process.
5. Review `git diff` for accidental changes, especially `AGENTS.md`, HCA profile fields, and opponent-specific conditions.
6. Report the eight HC tape/control/candidate rows, all failures and >25-point deltas, the 100-sample volatile results, HCA identity evidence, and an explicit accept/reject decision.
