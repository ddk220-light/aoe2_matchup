# Hand Cannoneer Tape-Motion Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test a tape-derived 0.35-tile Hand Cannoneer formation spacing against the existing 0.50-tile simulator baseline without changing exact tape starts or Heavy Cavalry Archer behavior.

**Architecture:** Add one optional, validated kite-profile geometry property that is inert by default. Thread it through the explicit standard-units experiment API, then run a dedicated gated A/B harness over the eight HC-versus-melee rows and the HCA identity control.

**Tech Stack:** Node.js ES modules, `node:test`, existing deterministic combat engine, standard-units clean-room fixtures.

## Global Constraints

- Use only `aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip` with SHA-256 `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`.
- Preserve every row's exact canonical `frames.bin` starting positions.
- Do not add opponent-specific constants or alter cadence, targeting, ring topology, or placement.
- Keep the generated product Hand Cannoneer profile unchanged unless the full acceptance gate passes.
- Require HCA-vs-Champion scores, final-state hashes, and event-log hashes to remain bit-identical.

---

### Task 1: Optional formation-spacing profile

**Files:**
- Modify: `aoe2x/js_simulation/tests/kite-orders.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/ai-orders.js`

**Interfaces:**
- Consumes: `createKiteState(kiteOwner, kiteProfile, chaseCapture, kitedEscape)`.
- Produces: optional `kiteState.profile.formationSpacingTiles: number`; `kiteMoveOrder` falls back to exactly `0.5` when absent.

- [ ] **Step 1: Write failing profile-copy and default-behavior tests**

Add tests that create profiles with and without `formationSpacingTiles`, assert
that `0.35` is copied, assert that absence stays absent, and assert that zero,
negative, non-finite, and non-number values are ignored. Pin an existing move
order's destination with the property absent.

```js
const measured = createKiteState(2, {
  ...DEFAULT_KITE_PROFILE,
  formationSpacingTiles: 0.35,
});
assert.equal(measured.profile.formationSpacingTiles, 0.35);
assert.equal(createKiteState(2, DEFAULT_KITE_PROFILE).profile.formationSpacingTiles, undefined);
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `node --test tests/kite-orders.test.mjs`

Expected: FAIL because `createKiteState` does not copy
`formationSpacingTiles`.

- [ ] **Step 3: Implement the minimal optional property**

In `createKiteState`, copy only finite positive spacing values:

```js
...(Number.isFinite(kiteProfile.formationSpacingTiles)
  && kiteProfile.formationSpacingTiles > 0
  ? { formationSpacingTiles: kiteProfile.formationSpacingTiles }
  : {}),
```

In `kiteMoveOrder`, replace the fixed local spacing with:

```js
const spacing = state.profile.formationSpacingTiles ?? 0.5;
```

- [ ] **Step 4: Run focused tests and verify pass**

Run: `node --test tests/kite-orders.test.mjs tests/kite-profiles.test.mjs`

Expected: all tests PASS; product profile assertions still show no experimental
geometry property.

- [ ] **Step 5: Commit the runtime seam**

```bash
git add aoe2x/js_simulation/src/combat/ai-orders.js aoe2x/js_simulation/tests/kite-orders.test.mjs
git commit -m "feat(sim): support measured kite formation spacing"
```

### Task 2: Explicit tape-comparison experiment

**Files:**
- Modify: `aoe2x/js_simulation/tests/standard-units-comparison.test.mjs`
- Modify: `aoe2x/js_simulation/src/standard-units-comparison.js`

**Interfaces:**
- Consumes: `runTapeConditioned(root, row, sampleIndex, seed, experiment)`.
- Produces: explicit experiment object `{ formationSpacingTiles: 0.35 }` applied only when the selected row has a kite profile.

- [ ] **Step 1: Write failing isolation and determinism tests**

Add a test that runs one HC row as baseline and with
`{ formationSpacingTiles: 0.35 }`, verifies the candidate changes its final or
event hash, reruns the baseline, and verifies the two baseline hashes are
identical. The HCA isolation assertion belongs to the dedicated suite, which
must call HCA without the HC experiment object and compare its pinned hashes.

```js
const baseline = await runTapeConditioned(ROOT, hcRow, 0, SEED);
const candidate = await runTapeConditioned(ROOT, hcRow, 0, SEED, {
  formationSpacingTiles: 0.35,
});
const repeat = await runTapeConditioned(ROOT, hcRow, 0, SEED);
assert.notEqual(candidate.finalStateHash, baseline.finalStateHash);
assert.equal(repeat.finalStateHash, baseline.finalStateHash);
assert.equal(repeat.eventLogHash, baseline.eventLogHash);
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `node --test tests/standard-units-comparison.test.mjs`

Expected: FAIL because the experiment property is not threaded into the
scenario profile.

- [ ] **Step 3: Implement experiment propagation**

Merge the property into `kite.kiteProfile` only for a finite positive value:

```js
...(Number.isFinite(experiment?.formationSpacingTiles)
  && experiment.formationSpacingTiles > 0
  && kite.kiteProfile
  ? { kiteProfile: {
      ...kite.kiteProfile,
      formationSpacingTiles: experiment.formationSpacingTiles,
    } }
  : {}),
```

The dedicated suite, rather than combat code, limits use to HC rows.

- [ ] **Step 4: Run comparison and profile tests**

Run: `node --test tests/standard-units-comparison.test.mjs tests/kite-orders.test.mjs tests/kite-profiles.test.mjs`

Expected: all tests PASS.

- [ ] **Step 5: Commit the experiment seam**

```bash
git add aoe2x/js_simulation/src/standard-units-comparison.js aoe2x/js_simulation/tests/standard-units-comparison.test.mjs
git commit -m "test(sim): expose HC formation-spacing experiment"
```

### Task 3: Gated HC A/B suite and report

**Files:**
- Create: `aoe2x/js_simulation/tools/run_hand_cannoneer_motion_profile_suite.mjs`
- Create: `aoe2x/js_simulation/tests/hand-cannoneer-motion-profile-suite.test.mjs`
- Create after execution: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_motion_profile_results_2026-08-09.json`
- Create after execution: `aoe2x/js_simulation/calibration/reports/hand_cannoneer_motion_profile_results_2026-08-09.md`
- Modify only if accepted: `aoe2x/js_simulation/tools/derive_kite_profiles.py`
- Modify only if accepted: `aoe2x/js_simulation/src/kite-profiles.js`

**Interfaces:**
- Consumes: eight HC-versus-melee truth rows, the pinned standard-units baseline report, and `runTapeConditioned(..., { formationSpacingTiles: 0.35 })`.
- Produces: `evaluateFiveSampleGate(rows, hcaIdentity)` and a report with per-row tape band, baseline mean/error, candidate mean/error, timeout count, stable-winner status, and all greater-than-25-point failures.

- [ ] **Step 1: Write failing gate tests**

Test that the gate rejects an unresolved run, a wrong stable winner, an
aggregate regression, an over-10-point regression on a baseline-good row, or
failed HCA identity. Test that only a fully passing screen requests the
100-sample volatile expansion.

```js
assert.equal(evaluateFiveSampleGate(passingRows, true).expandVolatile, true);
assert.equal(evaluateFiveSampleGate([
  { ...passingRows[0], candidate: { ...passingRows[0].candidate, unresolvedRuns: 1 } },
], true).expandVolatile, false);
```

- [ ] **Step 2: Run the gate test and verify failure**

Run: `node --test tests/hand-cannoneer-motion-profile-suite.test.mjs`

Expected: FAIL because the suite module does not exist.

- [ ] **Step 3: Implement the five-sample screen and conditional expansion**

Use seed `20260411`, value `0.35`, and the existing HC melee master set
`[359, 441, 567, 1903, 330, 569, 1134, 1372]`. First run five samples for all
rows and five baseline HCA identity samples. Only if `expandVolatile` is true,
replace the candidate samples for volatile tape rows with samples 0-99.

The accepted condition is:

```js
accepted = hcaIdentity
  && unresolvedRuns === 0
  && stableWinnerFailures.length === 0
  && goodRowRegressions.length === 0
  && candidateBandError < baselineBandError;
```

Render the screen decision, whether expansion ran, per-row results, and every
candidate `bandError > 25` in Markdown. Exit nonzero for a rejected candidate
after writing both reports.

- [ ] **Step 4: Run focused suite tests**

Run: `node --test tests/hand-cannoneer-motion-profile-suite.test.mjs tests/standard-units-comparison.test.mjs tests/kite-orders.test.mjs tests/kite-profiles.test.mjs`

Expected: all tests PASS.

- [ ] **Step 5: Execute the A/B gate**

Run: `node tools/run_hand_cannoneer_motion_profile_suite.mjs`

Expected: reports are written even if the command exits 1 for rejection. If
the five-sample screen fails, the report must show that 100-sample expansion
was skipped.

- [ ] **Step 6: Apply product profile only on acceptance**

If and only if the report says `accepted: true`, teach
`derive_kite_profiles.py` to emit `formationSpacingTiles: 0.35` for
`hand_cannoneer`, regenerate `src/kite-profiles.js`, and update the profile
tests. If rejected, leave both generated-profile files unchanged.

- [ ] **Step 7: Verify the complete focused surface**

Run: `node --test tests/hand-cannoneer-motion-profile-suite.test.mjs tests/standard-units-comparison.test.mjs tests/cohort-motion.test.mjs tests/cohort-motion-world.test.mjs tests/kite-orders.test.mjs tests/kite-profiles.test.mjs`

Then run: `npm test`

Expected: focused tests PASS. Record any full-suite timeout or pre-existing
failure separately and do not describe it as caused by this candidate without
reproducing it in the focused surface.

- [ ] **Step 8: Commit the suite, report, and accepted profile if applicable**

```bash
git add aoe2x/js_simulation/tools/run_hand_cannoneer_motion_profile_suite.mjs aoe2x/js_simulation/tests/hand-cannoneer-motion-profile-suite.test.mjs aoe2x/js_simulation/calibration/reports/hand_cannoneer_motion_profile_results_2026-08-09.json aoe2x/js_simulation/calibration/reports/hand_cannoneer_motion_profile_results_2026-08-09.md
git commit -m "test(sim): evaluate measured HC motion profile"
```
