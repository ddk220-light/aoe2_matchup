# Hand Cannoneer Cohort Contact Motion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a Hand-Cannoneer-only contact-motion executor that uses one deterministic detour heading for the move-ordered formation while preserving existing slot destinations, volley cadence, and HCA output.

**Architecture:** A new pure `cohort-motion.js` module transforms direct per-unit movement proposals only when a two-or-more-unit kiting cohort is about to intersect an enemy body. `world.js` invokes it behind an optional kite-profile property before local avoidance and collision. The standard-units calibration harness injects that property explicitly, gathers motion/volley diagnostics, and enables it in the generated HC product profile only after every five/100-sample gate passes.

**Tech Stack:** Node.js ES modules, `node:test`, the existing deterministic 60-tick combat engine, and the standard-units tape-conditioned comparison harness.

## Global Constraints

- Use only `aoe2x/js_simulation/calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip` with SHA-256 `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`.
- Use exact canonical `frames.bin` starts; do not use automatic placement.
- Keep the Hand Cannoneer volley beat at exactly 240 ticks.
- Do not change damage, accuracy, projectile behavior, target assignment, starting positions, or opponent movement.
- Do not add opponent names, master IDs, matchup names, desired winners, or per-opponent constants.
- Profiles without `cohortMotion: "contact_heading"` must remain output-identical.
- HCA-versus-Champion scores, final-state hashes, and event-log hashes must remain identical across the five pinned control samples.
- Keep the candidate off the generated product profile unless every acceptance gate passes.
- Do not modify or revert the user's `AGENTS.md` change.

---

### Task 1: Pure cohort-heading planner

**Files:**
- Create: `aoe2x/js_simulation/src/combat/cohort-motion.js`
- Create: `aoe2x/js_simulation/tests/cohort-motion.test.mjs`

**Interfaces:**
- Consumes: `planCohortContactMotion({ units, proposals, enemies, map, preferredTurn })`, where `units`, `proposals`, and `enemies` are current frozen engine records and `preferredTurn` is `-1` or `1`.
- Produces: a frozen proposal array with the same reference IDs and proposal count as the input.

- [ ] **Step 1: Write failing direct-path and singleton tests**

  Add real unit records with literal collision radii and speeds. Assert that an unblocked cohort and a one-unit cohort return proposals that are deeply equal to the inputs.

- [ ] **Step 2: Run the focused test and verify the missing export failure**

  Run: `node --test tests/cohort-motion.test.mjs`

  Expected: module/export failure because `cohort-motion.js` does not exist.

- [ ] **Step 3: Write failing shared-heading behavior tests**

  Assert that two parallel direct proposals blocked by an enemy are replaced by equal-angle, full-speed proposals; preferred turn resolves symmetric clearance; an at-slot zero proposal remains zero; and a no-clearance geometry still returns deterministic proposals for the collision layer to constrain.

- [ ] **Step 4: Implement the minimal pure planner**

  Use 15-degree candidates from zero through 90 degrees, actual `collisionRadius`, map-bound checks, lexicographic scoring `(clear members, forward projection, smallest turn, preferred side)`, and no persistent state or RNG.

- [ ] **Step 5: Run planner tests to green**

  Run: `node --test tests/cohort-motion.test.mjs`

  Expected: all planner tests pass.

### Task 2: Profile-gated world integration

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/ai-orders.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Create: `aoe2x/js_simulation/tests/cohort-motion-world.test.mjs`

**Interfaces:**
- Consumes: `planCohortContactMotion` from Task 1 and optional `kiteProfile.cohortMotion`.
- Produces: `kiteState.profile.cohortMotion` only when the input profile explicitly carries `"contact_heading"`; world movement calls the planner before existing local avoidance/collision.

- [ ] **Step 1: Write a failing profile-isolation test**

  Assert that `createKiteState` preserves `cohortMotion: "contact_heading"`, rejects/omits other values, and leaves the default and HCA profiles without the property.

- [ ] **Step 2: Write a failing real-world movement test**

  Construct the same two-unit kiting formation twice: direct profile and cohort profile. Step both worlds through a contacted move order and assert the direct world keeps distinct slot headings while the cohort world emits aligned movement, without mutating move-order destinations or attack timers.

- [ ] **Step 3: Run the new tests and verify they fail for missing integration**

  Run: `node --test tests/cohort-motion-world.test.mjs`

- [ ] **Step 4: Implement minimal integration**

  Copy the validated profile property in `createKiteState`. In `moveUnits`, build ordinary direct proposals first, select living move-ordered kiting-side units that can move, and replace only their proposal subset through the pure planner when the cohort has at least two members. Use `kiteState.ringDirection || 1` for deterministic turn preference. Continue through the unchanged local-avoidance and collision functions.

- [ ] **Step 5: Run integration and movement tests**

  Run: `node --test tests/cohort-motion-world.test.mjs tests/cohort-motion.test.mjs tests/kite-profiles.test.mjs tests/standard-units-comparison.test.mjs`

  Expected: all focused tests pass; existing non-profiled hashes remain unchanged.

### Task 3: Explicit calibration experiment and diagnostics

**Files:**
- Modify: `aoe2x/js_simulation/src/standard-units-comparison.js`
- Modify: `aoe2x/js_simulation/tests/standard-units-comparison.test.mjs`
- Create: `aoe2x/js_simulation/src/kite-motion-diagnostics.js`
- Create: `aoe2x/js_simulation/tests/kite-motion-diagnostics.test.mjs`
- Modify: `aoe2x/js_simulation/tools/run_hand_cannoneer_clearance_suite.mjs`

**Interfaces:**
- Consumes: `runTapeConditioned(..., { cohortMotion: "contact_heading" })`.
- Produces: candidate samples with outcome diagnostics for contact exposure, contact-window median/p90, one-second escape rate, centroid spread, assigned shooters per beat, delivered damage per beat, and unresolved count.

- [ ] **Step 1: Write failing harness-injection test**

  Assert that the default Hand Cannoneer sample retains its pinned baseline hash while `{ cohortMotion: "contact_heading" }` changes movement output, and that a non-HC row is not modified by the HC runner.

- [ ] **Step 2: Write failing diagnostics tests from literal snapshots**

  Use a short hand-built sequence with known contact start/end ticks, centroid distances, `kite-attack`/damage events, and a 60-tick escape. Assert literal metric values rather than recomputing expectations with production helpers.

- [ ] **Step 3: Implement diagnostic reducer and harness option**

  Preserve completed-run snapshots long enough to reduce diagnostics, then discard them from report samples. For timeout results, record unresolved status without fabricating terminal diagnostics. Restrict the runner's candidate injection to the eight canonical HC owner-2 melee rows.

- [ ] **Step 4: Run diagnostic and comparison tests**

  Run: `node --test tests/kite-motion-diagnostics.test.mjs tests/standard-units-comparison.test.mjs tests/standard-units-runners.test.mjs`

### Task 4: Five-sample candidate screen

**Files:**
- Generate: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_cohort_motion_screen_2026-08-09.json`
- Generate: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_cohort_motion_screen_2026-08-09.md`

**Interfaces:**
- Consumes: the eight canonical HC rows and the explicit cohort experiment.
- Produces: five samples per row, baseline/candidate band error, winner distribution, timeout count, and intermediate diagnostics.

- [ ] **Step 1: Reverify the archive hash**

  Run: `Get-FileHash calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip -Algorithm SHA256`

  Expected: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`.

- [ ] **Step 2: Execute five samples for every HC row**

  Run the cohort runner with `--samples 5 --volatile-samples 5` and write separate screen outputs.

- [ ] **Step 3: Apply screen gates**

  Reject immediately for a stable winner flip, any timeout, greater-than-10 regression on a baseline-good row, HCA identity failure, volley cadence change, increased contact exposure, materially wider formation spread, or materially reduced volley participation. If rejected, keep the product profile disabled and report the evidence; do not tune a matchup constant.

### Task 5: Full acceptance suite

**Files:**
- Generate: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_cohort_motion_results_2026-08-09.json`
- Generate: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_cohort_motion_results_2026-08-09.md`
- Conditionally modify: `aoe2x/js_simulation/tools/derive_kite_profiles.py`
- Conditionally regenerate: `aoe2x/js_simulation/src/kite-profiles.js`

**Interfaces:**
- Consumes: five samples for stable rows, 100 for volatile HC rows, and the pinned HCA control fixture.
- Produces: final accept/reject report and, only on acceptance, the generated HC product-profile property.

- [ ] **Step 1: Run the approved five/100 schedule**

  Run the cohort runner with `--samples 5 --volatile-samples 100` from a fresh Node process.

- [ ] **Step 2: Apply all acceptance gates**

  Require aggregate error improvement, zero stable-winner regressions, zero greater-than-10 regressions on baseline-good rows, zero timeouts, exact five-sample HCA identity, unchanged 240-tick cadence, and improved motion diagnostics without volley-participation loss.

- [ ] **Step 3: Enable only an accepted candidate**

  If accepted, add `cohortMotion: "contact_heading"` only to the generated Hand Cannoneer profile in `derive_kite_profiles.py`, regenerate `kite-profiles.js`, and rerun the full acceptance report on the product path. If rejected, assert in `kite-profiles.test.mjs` that the property remains absent.

- [ ] **Step 4: List every remaining greater-than-25 row**

  The Markdown and JSON reports must name every candidate row whose final tape-band error exceeds 25 points, regardless of aggregate result.

### Task 6: Verification and handoff

**Files:**
- Verify all files above; do not stage unrelated workspace changes.

**Interfaces:**
- Consumes: final candidate/report state.
- Produces: evidence-backed handoff with active/disabled status.

- [ ] **Step 1: Run focused tests fresh**

  Run: `node --test tests/cohort-motion.test.mjs tests/cohort-motion-world.test.mjs tests/kite-motion-diagnostics.test.mjs tests/kite-profiles.test.mjs tests/standard-units-comparison.test.mjs tests/standard-units-runners.test.mjs`

- [ ] **Step 2: Run the full project suite with a bounded timeout**

  Run: `npm test`. Report its actual exit status and distinguish existing Champion fixture failures from new failures.

- [ ] **Step 3: Review the final diff and active profile**

  Confirm `AGENTS.md` is untouched by this task, no opponent-specific condition exists, and rejected behavior is not active.

- [ ] **Step 4: Report the result**

  Provide all eight tape/baseline/candidate means, band errors, volatile winner distributions, timeouts, intermediate motion/volley findings, HCA identity evidence, remaining greater-than-25 rows, and the explicit accept/reject decision.
