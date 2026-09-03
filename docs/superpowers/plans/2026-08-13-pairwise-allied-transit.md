# Pairwise Allied Transit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an experiment-gated, exclusive pairwise allied pass-through mechanic for attack-moving melee cohorts and expose it in the ranged-versus-melee viewer.

**Architecture:** A focused allied-transit module will maintain deterministic pair reservations from unit positions and desired movement proposals. Collision and local avoidance will treat only those reserved pairs as mutually transparent; every unit can hold at most one reservation, while enemy and map collision remain unchanged. The existing viewer attack-move scenario will enable the experiment without changing calibrated batch scenarios.

**Tech Stack:** JavaScript ES modules, Node.js built-in test runner, existing deterministic combat/world pipeline.

**Spec:** `aoe2x/js_simulation/calibration/reports/hca_champion_overlap_suite_2026-08-13.md` and `aoe2x/js_simulation/tools/measure_hca_champion_multi_overlap.mjs`

## Global Constraints

- No unit- or matchup-specific constants.
- A unit may participate in at most one deep-transit pair at a time.
- Pair selection is deterministic and derives from collision geometry, group-order membership, and actual desired motion.
- Enemy units, map bounds, and static obstacles remain hard collision constraints.
- Existing non-viewer simulations remain unchanged unless they explicitly enable the experiment.
- Do not run unrelated battle or tape comparison suites.

---

### Task 1: Deterministic exclusive pair reservations

**Files:**
- Create: `aoe2x/js_simulation/src/combat/allied-transit.js`
- Create: `aoe2x/js_simulation/tests/allied-transit.test.mjs`

**Interfaces:**
- Consumes: live units, desired movement proposals, cohort reference IDs, and prior reservations.
- Produces: `updateAlliedTransit(state, units, proposals)` returning the next reservation map and its canonical pair-key set.

- [x] **Step 1: Write failing tests for deterministic pair acquisition, exclusivity, persistence, crossing release, and stopped-unit rejection.**
- [x] **Step 2: Run `node --test tests/allied-transit.test.mjs` and confirm failure because the module is absent.**
- [x] **Step 3: Implement the smallest geometry-derived reservation selector that passes the tests.**
- [x] **Step 4: Re-run the focused test and confirm every case passes.**

### Task 2: Collision and local-avoidance integration

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/collision.js`
- Modify: `aoe2x/js_simulation/src/combat/local-avoidance.js`
- Modify: `aoe2x/js_simulation/tests/movement-collision.test.mjs`
- Modify: `aoe2x/js_simulation/tests/local-avoidance.test.mjs`

**Interfaces:**
- Consumes: canonical allied-transit pair keys from Task 1.
- Produces: optional `{ alliedTransitPairs }` arguments on movement resolution and local-avoidance planning.

- [x] **Step 1: Write failing behavioral tests showing one reserved pair can cross while its third ally still obstructs, and the reserved ally is omitted only from its partner's avoidance constraints.**
- [x] **Step 2: Run the focused tests and confirm the expected collision/avoidance failures.**
- [x] **Step 3: Add experiment-gated pair checks to collision and avoidance without changing default calls.**
- [x] **Step 4: Re-run both focused test files and confirm they pass.**

### Task 3: Attack-move cohort and viewer wiring

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/ai-orders.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Modify: `aoe2x/js_simulation/src/fight.js`
- Modify: `aoe2x/js_simulation/tests/target-state.test.mjs`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

**Interfaces:**
- Consumes: scenario flag `pairwiseAlliedTransit: true` and the opening `attack-move-all` command.
- Produces: an attack-move cohort whose reserved pairs are passed through avoidance, steering, and collision; ranged-versus-melee viewer scenarios enable the flag.

- [x] **Step 1: Write failing world/server tests proving the viewer scenario enables pairwise transit and that an attack-moving pair closes through allied contact without granting a third simultaneous partner.**
- [x] **Step 2: Run the focused tests and confirm they fail for the missing scenario behavior.**
- [x] **Step 3: Record the opening melee cohort, update reservations each tick, propagate pair keys through movement, and enable the viewer flag.**
- [x] **Step 4: Re-run the focused tests and confirm they pass.**

### Task 4: Verification and viewer refresh

**Files:**
- Verify only; no additional behavior changes.

**Interfaces:**
- Consumes: completed experiment implementation.
- Produces: fresh automated verification and the updated local viewer server.

- [x] **Step 1: Run the scoped transit, collision, obstacle, world, and server verification tests; preserve the 14 unrelated failures established in the pre-change dirty-branch baseline.**
- [x] **Step 2: Run the multi-overlap measurement tool to ensure the evidence script remains executable.**
- [x] **Step 3: Restart the local server on `127.0.0.1:5011`.**
- [x] **Step 4: Request the current ranged-versus-melee HCA/Champion endpoint once and verify the response and experiment diagnostics.**
