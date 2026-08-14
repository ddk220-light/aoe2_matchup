# Preventive Contact-Graph Steering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent attack-moving melee units from folding into persistent compact allied cliques while preserving full-speed pursuit and ordinary pairwise contact.

**Architecture:** A focused deterministic planner will evaluate the chasers' already-computed movement proposals against a projected allied contact graph. It will keep direct motion when that motion only extends an edge or remains clear, and choose the smallest full-speed lateral turn when a proposed step would close a triangle or create a four-unit compact clique. The feature is scenario-gated in the combat world and enabled by the ranged-versus-melee cohesive viewer; collision, attacks, unit timing, and non-viewer simulations remain unchanged.

**Tech Stack:** JavaScript ES modules, Node.js built-in test runner, existing deterministic combat/world pipeline and viewer server.

**Spec:** `aoe2x/js_simulation/calibration/reports/congestion_prevention_2026-08-13/report.html` and `aoe2x/js_simulation/calibration/reports/congestion_prevention_2026-08-13/artifact.json`

## Global Constraints

- No unit-, matchup-, outcome-, seed-, or elapsed-time-specific calibration.
- Contact is derived from each unit's sourced collision geometry; movement distance remains the unit's sourced per-tick speed.
- One-to-one and chain-forming allied contact remains legal. The planner intervenes only before internal contact-graph closure or compact multi-neighbor admission.
- Existing overlap may be preserved or reduced, but never deepened by the preventive candidate.
- Target, enemy, map-boundary, and static-obstacle behavior remain governed by the existing movement and collision layers.
- The initial rollout is an explicit scenario option enabled only for the cohesive ranged-versus-melee viewer.
- Run only focused unit tests and the requested 5 HCA versus 10 Champion observation.

---

### Task 1: Contact-graph candidate planner

**Files:**
- Create: `aoe2x/js_simulation/src/combat/contact-graph-steering.js`
- Create: `aoe2x/js_simulation/tests/contact-graph-steering.test.mjs`

- [x] **Step 1: Write failing behavioral tests for clear direct motion, triangle-closing detours, compact four-clique prevention, full-speed preservation, and deterministic input-order invariance.**
- [x] **Step 2: Run the focused test and confirm the expected failure because the planner does not exist.**
- [x] **Step 3: Implement deterministic direct/left/right candidate evaluation with projected contact-graph scoring.**
- [x] **Step 4: Re-run the focused test and confirm every case passes.**

### Task 2: World and viewer integration

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Modify: `aoe2x/js_simulation/src/fight.js`
- Modify: `aoe2x/js_simulation/tests/target-state.test.mjs`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

- [x] **Step 1: Write failing world/server tests proving the scenario flag is opt-in and the cohesive ranged-versus-melee viewer enables it.**
- [x] **Step 2: Run the focused tests and confirm they fail for the missing scenario behavior.**
- [x] **Step 3: Apply preventive steering after local route planning and before collision resolution for attack-moving chasers only.**
- [x] **Step 4: Thread the scenario option through the viewer response diagnostics and re-run the focused tests.**

### Task 3: Requested 5v10 validation and viewer refresh

**Files:**
- Verify: `aoe2x/js_simulation/calibration/analysis/congestion_prevention_2026-08-13.mjs`
- Verify: existing viewer/server files

- [x] **Step 1: Run focused navigation, world, and server tests.**
- [x] **Step 2: Run a fresh 5 HCA versus 10 Champion observation and compare compact-contact metrics with the recorded pre-change baseline and tape.**
- [x] **Step 3: Restart the local viewer server and request the exact viewer endpoint once.**
- [x] **Step 4: Report observed improvements and any remaining regression honestly; do not tune combat outcomes.**
