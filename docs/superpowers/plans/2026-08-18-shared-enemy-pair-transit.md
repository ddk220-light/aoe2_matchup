# Shared Enemy Pair Transit Implementation Plan

**Status (2026-08-18):** Enemy pair transit is implemented and the focused
golden gate passes for War Wagon-Paladin, War Wagon-Champion, HCA-Paladin, and
Boyar-HCA. The durable mechanics and reproducible results are recorded in
`aoe2x/js_simulation/calibration/reports/shared_enemy_pair_transit_2026-08-18/README.md`.
Allied formation packing remains a separate later stage.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the War Wagon-specific enemy-overlap exception with one deterministic, state-based pair interaction model that lets melee and reach-melee pursuers transiently pass non-target enemies without changing direct-target attack range or collapsing whole groups.

**Architecture:** Introduce a pure `PairInteractionSnapshot` resolver used by every dynamic-body subsystem, then add an experiment-gated enemy-transit state machine that derives swept contact, one-to-one non-target transit, and non-deepening inherited overlap from unit state and geometry. Prove the general rule against HCA-Paladin and both War Wagon golden controls before deleting the War Wagon runtime override. Allied HCA-HCA formation overlap remains unchanged in this plan and receives a separate implementation plan only after enemy transit is accepted.

**Tech Stack:** JavaScript ES modules, Node.js built-in test runner, existing deterministic world/collision pipeline, existing clean-room tape extractors and recoverable comparison runners, HTML Canvas viewer.

**Spec:** `docs/superpowers/specs/2026-08-18-shared-pair-interaction-design.md`

## Global Constraints

- Work only on `codex/experiment-steppe-reach-wedges`; do not deploy, push, merge, or touch production.
- Use only golden archives already copied under `aoe2x/js_simulation/calibration/source/` and recorded by exact SHA-256 in the active clean-room manifest.
- Verify the selected project-local archive hash before reading tape data. Stop on a missing archive or hash mismatch; never substitute another tape.
- No unit-, civilization-, or matchup-specific transit depth, timing, radius, or target-selection constant.
- Do not tune attack, armor, speed, reload, kiting clock, formation placement, or target selection in this experiment.
- Static obstacles, buildings, map bounds, dead units, ranged-initiated contacts, idle enemy pairs, and direct pursuit targets stay hard.
- Each live unit may participate in at most one deep enemy-transit reservation. Several geometry-derived shallow swept contacts may coexist.
- A released pair that remains overlapped may preserve or reduce its current overlap, but it may never deepen it.
- Direct-target movement stopping and attack range continue to use sourced physical/outline geometry; enemy transit affects only non-target obstruction.
- With `pairwiseEnemyTransit` absent or false, existing simulation output and deterministic hashes must remain unchanged.
- Use five simulation samples per golden row. Never exceed the agreed 15-sample ceiling; report unresolved long fights as knife's edge.
- Every comparison row must checkpoint atomically so a rerun skips completed rows.
- Do not add, delete, stage, or rewrite the unrelated untracked report directories already present in the worktree.

## Scope Boundary

This plan implements design Stages 1-3 only:

1. shared pair interaction contract with no default behavior change;
2. experiment-gated enemy swept contact, reserved transit, and inherited overlap;
3. War Wagon override removal after the focused golden gates pass.

Design Stage 4, allied formation overlap, is deliberately excluded. The current HCA-HCA metrics must remain unchanged throughout this plan. After the enemy rule is accepted, write a separate plan for migrating `allied-transit.js` and `allied-overlap.js` from unconditional same-formation transparency to bounded pair interactions.

## File and Responsibility Map

### Create

- `aoe2x/js_simulation/src/combat/pair-interactions.js`
  - Canonical dynamic-pair keys.
  - Snapshot validation and normalization.
  - Legacy `enemyOverlapDepthByMaster` compatibility adapter.
  - Purpose-specific pair classification: collision extent, path obstruction, attack surface, deepening permission, and diagnostic reason.
- `aoe2x/js_simulation/src/combat/enemy-transit.js`
  - Pure enemy-transit candidate detection.
  - Deterministic one-to-one matching.
  - Swept contact detection.
  - Reservation persistence/release and inherited-contact production.
- `aoe2x/js_simulation/tests/pair-interactions.test.mjs`
  - Contract, validation, compatibility, and direct-target geometry tests.
- `aoe2x/js_simulation/tests/enemy-transit.test.mjs`
  - State-machine and ordering-invariance tests.
- `aoe2x/js_simulation/tests/enemy-transit-report.test.mjs`
  - Golden metric aggregation, band checks, and checkpoint-resume tests.
- `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/measure_overlap.mjs`
  - Common tape/simulation overlap measurement using Chebyshev collision extents.
- `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/run_focused_comparisons.mjs`
  - Recoverable five-sample focused golden runner.
- `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/build_report.mjs`
  - JSON/HTML summary with tape bands, simulation metrics, outcomes, and failure diagnostics.
- `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/README.md`
  - Reproduction commands, archive hash, experiment status, and gate interpretation.

### Modify

- `aoe2x/js_simulation/src/combat/collision.js`
  - Consume the shared snapshot for starting validation, pair constraints, final validation, and recovery.
  - Retain compatibility re-exports while callers migrate.
- `aoe2x/js_simulation/src/combat/chase-path.js`
  - Omit only pairs whose shared classification has `pathObstructs: false`.
- `aoe2x/js_simulation/src/combat/local-avoidance.js`
  - Omit only non-obstructing pairs; keep all third bodies and static obstacles.
- `aoe2x/js_simulation/src/combat/movement.js`
  - Clamp direct pursuit using `attackSurfaceExtent`, not transit collision extent.
- `aoe2x/js_simulation/src/combat/attacks.js`
  - Use `attackSurfaceExtent` for stop-range checks.
- `aoe2x/js_simulation/src/combat/world.js`
  - Split raw movement intent from obstacle-aware planning.
  - Own enemy pair state across ticks and construct the authoritative snapshot.
  - Emit deterministic pair diagnostics.
- `aoe2x/js_simulation/src/fight.js`
  - Carry `pairwiseEnemyTransit` and expose aggregate diagnostics without changing default output hashes.
- `aoe2x/js_simulation/src/dedicated-golden-comparison.js`
  - Allow explicit experiment scenarios while retaining default control behavior.
- `aoe2x/js_simulation/src/phase2-batch1-comparison.js`
  - Enable the accepted general flag after the focused gates pass.
- `aoe2x/js_simulation/src/combat/kite-timing.js`
  - Remove War Wagon overlap policy only after the general model passes both War Wagon controls.
- `aoe2x/js_simulation/server.mjs`
  - Parse and pass `enemyTransit=pairwise` for viewer-only experiments.
- `aoe2x/js_simulation/viewer/battle-state.js`
  - Validate and preserve the experiment query parameter.
- `aoe2x/js_simulation/viewer/simulation-review.js`
  - Normalize pair diagnostic frames.
- `aoe2x/js_simulation/viewer/map-renderer.js`
  - Draw pair lines and diagnostic labels in debug mode.
- `aoe2x/js_simulation/viewer/app.js`
  - Display active pair counts and largest contact component.
- Existing focused tests listed in the tasks below.

## Authoritative Interfaces

`pair-interactions.js` exposes:

```js
export function dynamicPairKey(leftId, rightId);

export function createPairInteractionSnapshot({
  alliedTransitPairs = new Set(),
  alliedShrinkPairs = new Set(),
  alliedShallowPairs = new Set(),
  alliedShrinkReservedIds = new Set(),
  exclusiveAlliedShrinkOwners = new Set(),
  legacyEnemyOverlapDepthByMaster = new Map(),
  enemyTransitPairs = new Map(),
  sweptEnemyContactExtents = new Map(),
  inheritedEnemyContactExtents = new Map(),
} = {});

export function resolvePairInteraction(left, right, snapshot);
```

For enemy pairs, `resolvePairInteraction` returns a frozen object:

```js
{
  kind: "hard" | "legacy" | "swept" | "transit" | "inherited",
  collisionExtent: 0.5,
  pathObstructs: true,
  attackSurfaceExtent: 0.5,
  mayDeepen: false,
  reason: "hard-enemy-contact",
}
```

Contract rules:

- `hard`: all purpose extents use the physical collision extent.
- `legacy`: reproduces the current War Wagon master/mode policy exactly, including the old direct movement/stop behavior, until migration.
- `transit`: `collisionExtent` is `0`, `pathObstructs` is false, and `attackSurfaceExtent` stays physical.
- `swept` and `inherited`: `collisionExtent` is the stored legal Chebyshev separation, `pathObstructs` is true, `attackSurfaceExtent` stays physical, and `mayDeepen` is false.
- Allied pair behavior is represented in the same snapshot, but its existing eligibility rules are not changed in this plan.

`enemy-transit.js` exposes:

```js
export function createEnemyTransitState() {
  return Object.freeze({
    reservations: new Map(),
    inheritedContactExtents: new Map(),
  });
}

export function updateEnemyTransit({ state, units, proposals, tick });
```

`updateEnemyTransit` returns:

```js
{
  state: {
    reservations: new Map(),
    inheritedContactExtents: new Map(),
  },
  pairSnapshotData: {
    enemyTransitPairs: new Map(),
    sweptEnemyContactExtents: new Map(),
    inheritedEnemyContactExtents: new Map(),
  },
  diagnostics: [],
}
```

Every reservation record is:

```js
{
  chaserId,
  blockerId,
  pursuitTargetId,
  acquisitionAxis: "x" | "y",
  acquisitionSign: -1 | 1,
  acquiredTick,
}
```

---

### Task 1: Add the shared pair-interaction contract without changing behavior

**Files:**
- Create: `aoe2x/js_simulation/src/combat/pair-interactions.js`
- Create: `aoe2x/js_simulation/tests/pair-interactions.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/collision.js`
- Modify: `aoe2x/js_simulation/tests/movement-collision.test.mjs`
- Modify: `aoe2x/js_simulation/tests/chase-path.test.mjs`
- Modify: `aoe2x/js_simulation/tests/steppe-range.test.mjs`

- [ ] **Step 1: Write failing tests for canonical keys, hard contact, and snapshot validation.**

Add test fixtures with explicit owners, collision radii, unit masters, action state, and target IDs. Include these assertions:

```js
assert.equal(dynamicPairKey(9, 2), "2:9");
assert.throws(
  () => createPairInteractionSnapshot({ enemyTransitPairs: new Set() }),
  /enemy transit pairs must be a Map/,
);
assert.deepEqual(resolvePairInteraction(left, enemy, snapshot), {
  kind: "hard",
  collisionExtent: 0.4,
  pathObstructs: true,
  attackSurfaceExtent: 0.4,
  mayDeepen: false,
  reason: "hard-enemy-contact",
});
```

- [ ] **Step 2: Write failing compatibility tests for every existing War Wagon policy mode.**

Cover `always`, `attacking-any`, `attacking-target`, and `attacking-other`, including the current rule that an already-overlapping legacy pair remains legal through an action transition. Assert that the legacy resolver matches both current `enemyPairExtent` and current direct-target stop behavior.

- [ ] **Step 3: Run the focused tests and confirm the new module import fails.**

Run:

```powershell
node --test aoe2x/js_simulation/tests/pair-interactions.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs aoe2x/js_simulation/tests/chase-path.test.mjs aoe2x/js_simulation/tests/steppe-range.test.mjs
```

Expected: only the new contract tests fail with `ERR_MODULE_NOT_FOUND`; record any pre-existing unrelated failures separately rather than changing them.

- [ ] **Step 4: Implement the pure snapshot and legacy adapter.**

Move policy normalization and `configuredPolicyApplies` from `collision.js` into `pair-interactions.js`. Import `collisionRadius` from `targeting.js` so the new module does not import the collision solver. Validate every pair key, extent, and set/map type when the snapshot is created, not during the movement sweep.

- [ ] **Step 5: Replace collision-local legacy decisions with `resolvePairInteraction`.**

Keep temporary compatibility exports from `collision.js`:

```js
export function enemyOverlapDepthForPair(left, right, policies) {
  const snapshot = createPairInteractionSnapshot({
    legacyEnemyOverlapDepthByMaster: policies,
  });
  const interaction = resolvePairInteraction(left, right, snapshot);
  return interaction.attackSurfaceExtent - interaction.collisionExtent;
}
```

Use the snapshot for starting geometry, constraints, invalid-body reporting, restoration, and final geometry. Do not yet enable swept or reserved enemy behavior.

- [ ] **Step 6: Re-run the focused tests and confirm exact compatibility.**

Expected: all focused tests pass, including existing War Wagon numeric assertions and reversed-input determinism.

- [ ] **Step 7: Commit the no-behavior refactor.**

```powershell
git add aoe2x/js_simulation/src/combat/pair-interactions.js aoe2x/js_simulation/src/combat/collision.js aoe2x/js_simulation/tests/pair-interactions.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs aoe2x/js_simulation/tests/chase-path.test.mjs aoe2x/js_simulation/tests/steppe-range.test.mjs
git commit -m "refactor: centralize pair interaction geometry"
```

### Task 2: Implement the enemy-transit state machine as a pure module

**Files:**
- Create: `aoe2x/js_simulation/src/combat/enemy-transit.js`
- Create: `aoe2x/js_simulation/tests/enemy-transit.test.mjs`

- [ ] **Step 1: Write failing eligibility tests.**

Cover all of the following with small three-body fixtures:

- melee chaser + non-target enemy blocker + live target acquires transit;
- reach-melee chaser with `attack_range_tiles: 1` also qualifies;
- ranged mover, idle melee, zero-progress mover, dead unit, ally, static body, and direct target do not qualify;
- the blocker must be longitudinally between chaser and target and inside the radius-expanded segment corridor.

Use explicit output assertions:

```js
const updated = updateEnemyTransit({
  state: createEnemyTransitState(),
  units: [chaser, blocker, target],
  proposals: [proposal(chaser.referenceId, 1 / 60, 0)],
  tick: 120,
});
assert.deepEqual([...updated.state.reservations.keys()], ["1:2"]);
assert.equal(updated.state.reservations.get("1:2").pursuitTargetId, 3);
assert.equal(updated.pairSnapshotData.enemyTransitPairs.get("1:2").chaserId, 1);
```

- [ ] **Step 2: Write failing exclusivity and deterministic-order tests.**

Assert that two chasers competing for one blocker create exactly one reservation, that a third body cannot join an existing deep pair, and that reversing both `units` and `proposals` produces identical normalized state and diagnostics. Candidate order is: preserve a valid prior reservation, smallest forward clearance, smallest lateral corridor offset, then chaser ID and blocker ID.

- [ ] **Step 3: Write failing lifecycle tests.**

Cover persistence, axis crossing while separating, corridor exit, target death, chaser/blocker death, retargeting, blocker becoming the direct target, and release while overlapped. Assert that release produces an inherited extent equal to the current Chebyshev separation and never a fixed depth.

- [ ] **Step 4: Write failing swept and inherited-contact tests.**

Test a pair whose raw endpoints cross from outside the hard extent. Require at least one active melee pursuer, store the projected separation, and reject ranged-ranged and idle contacts. On the following update, assert that a deeper proposal retains the prior legal extent while a separating proposal increases it; delete inherited state when ordinary full separation is restored.

- [ ] **Step 5: Run the new tests and confirm module absence.**

```powershell
node --test aoe2x/js_simulation/tests/enemy-transit.test.mjs
```

Expected: `ERR_MODULE_NOT_FOUND` for `enemy-transit.js`.

- [ ] **Step 6: Implement deterministic geometry and lifecycle logic.**

Use Chebyshev collision extents and proposal endpoints. Do not introduce wall-clock timeouts. If a defensive tick ceiling is required for corrupt state, name it as a failure ceiling, emit `enemy-transit-recovered`, and convert current overlap to inherited contact rather than granting new penetration.

- [ ] **Step 7: Re-run the pure state tests.**

Expected: all cases pass; JSON-normalized state and diagnostics are identical under reversed input order.

- [ ] **Step 8: Commit the pure state machine.**

```powershell
git add aoe2x/js_simulation/src/combat/enemy-transit.js aoe2x/js_simulation/tests/enemy-transit.test.mjs
git commit -m "feat: add deterministic enemy transit reservations"
```

### Task 3: Route every dynamic-body subsystem through the shared snapshot

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/chase-path.js`
- Modify: `aoe2x/js_simulation/src/combat/local-avoidance.js`
- Modify: `aoe2x/js_simulation/src/combat/movement.js`
- Modify: `aoe2x/js_simulation/src/combat/attacks.js`
- Modify: `aoe2x/js_simulation/src/combat/collision.js`
- Modify: `aoe2x/js_simulation/tests/chase-path.test.mjs`
- Modify: `aoe2x/js_simulation/tests/local-avoidance.test.mjs`
- Modify: `aoe2x/js_simulation/tests/movement-collision.test.mjs`
- Modify: `aoe2x/js_simulation/tests/steppe-range.test.mjs`
- Modify: `aoe2x/js_simulation/tests/world-tick.test.mjs`

- [ ] **Step 1: Write failing subsystem-consistency tests.**

Construct one snapshot with a reserved chaser/blocker pair and assert:

- chase path does not mark the reserved blocker as an obstacle for that chaser;
- local avoidance omits only that pair;
- a third enemy still blocks pathing and final collision;
- the reserved pair may publish crossed endpoints;
- swept/inherited pairs may keep their stored extent but cannot deepen;
- starting geometry and final geometry agree on inherited contact;
- static obstacles and map bounds remain hard.

- [ ] **Step 2: Write the direct-target safety test before integration.**

```js
const interaction = resolvePairInteraction(chaser, directTarget, snapshot);
assert.equal(interaction.attackSurfaceExtent, fullPairExtent);
assert.equal(isWithinStopRange(chaser, directTarget, { pairInteractions: snapshot }), false);
const step = proposeMovement(chaser, directTarget, 60, { pairInteractions: snapshot });
assert.ok(Math.hypot(step.dx, step.dy) <= physicalSurfaceGap + 1e-12);
```

Also retain the existing Steppe Lancer outline-reach assertions. A reach-melee unit may transit a non-target blocker but must not gain extra attack range on its target.

- [ ] **Step 3: Run the focused subsystem tests and confirm they fail for ignored snapshot fields.**

```powershell
node --test aoe2x/js_simulation/tests/pair-interactions.test.mjs aoe2x/js_simulation/tests/chase-path.test.mjs aoe2x/js_simulation/tests/local-avoidance.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs aoe2x/js_simulation/tests/steppe-range.test.mjs aoe2x/js_simulation/tests/world-tick.test.mjs
```

- [ ] **Step 4: Thread `{ pairInteractions }` through all subsystem options.**

Remove subsystem-specific pair eligibility. Each caller obtains its decision from `resolvePairInteraction`:

```js
const interaction = resolvePairInteraction(mover, body, options.pairInteractions);
if (!interaction.pathObstructs) continue;
const reach = interaction.collisionExtent;
```

`movement.js` and `attacks.js` use `attackSurfaceExtent`; `collision.js` uses `collisionExtent` and `mayDeepen`. The legacy map is normalized once when the snapshot is created, not separately by each subsystem.

- [ ] **Step 5: Adapt existing allied pair sets into the same snapshot without changing allied eligibility.**

Pass the existing `alliedTransitPairs`, `alliedShrinkPairs`, `alliedShallowPairs`, reserved IDs, and exclusive owners into `createPairInteractionSnapshot`. Keep `updateAlliedTransit` and `updateExclusiveAlliedOverlap` unchanged. Existing allied tests must remain byte-for-byte behavior controls.

- [ ] **Step 6: Re-run the focused subsystem tests.**

Expected: new consistency tests pass, all current War Wagon compatibility tests pass, and existing allied transit/overlap tests are unchanged.

- [ ] **Step 7: Commit the shared physics integration.**

```powershell
git add aoe2x/js_simulation/src/combat/chase-path.js aoe2x/js_simulation/src/combat/local-avoidance.js aoe2x/js_simulation/src/combat/movement.js aoe2x/js_simulation/src/combat/attacks.js aoe2x/js_simulation/src/combat/collision.js aoe2x/js_simulation/tests/chase-path.test.mjs aoe2x/js_simulation/tests/local-avoidance.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs aoe2x/js_simulation/tests/steppe-range.test.mjs aoe2x/js_simulation/tests/world-tick.test.mjs
git commit -m "feat: route combat physics through pair interactions"
```

### Task 4: Integrate experiment-gated enemy state into world ticks

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Modify: `aoe2x/js_simulation/src/fight.js`
- Modify: `aoe2x/js_simulation/src/dedicated-golden-comparison.js`
- Modify: `aoe2x/js_simulation/src/phase2-batch1-comparison.js`
- Modify: `aoe2x/js_simulation/tests/world-tick.test.mjs`
- Modify: `aoe2x/js_simulation/tests/target-state.test.mjs`
- Modify: `aoe2x/js_simulation/tests/dedicated-golden-comparison.test.mjs`
- Modify: `aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs`

- [ ] **Step 1: Write failing world-state tests for the experiment flag.**

Assert that `createWorld` omits enemy-transit state when the flag is absent, creates empty state only when `pairwiseEnemyTransit: true`, and rejects non-boolean values. Add a three-body world tick where a pursuing Champion/Paladin acquires a non-target reservation, plus reversed-input and target-death cleanup cases.

- [ ] **Step 2: Write a no-flag determinism control.**

Run an existing fixed-seed world for a fixed tick count with no flag and compare its normalized result to the pre-refactor expected fixture already asserted by `world-tick.test.mjs`. Do not add experiment-only empty arrays or maps to default serialized output.

- [ ] **Step 3: Run the focused tests and confirm the scenario flag has no behavior yet.**

```powershell
node --test aoe2x/js_simulation/tests/world-tick.test.mjs aoe2x/js_simulation/tests/target-state.test.mjs aoe2x/js_simulation/tests/dedicated-golden-comparison.test.mjs aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs
```

- [ ] **Step 4: Split raw intent from obstacle-aware planning in `moveUnits`.**

Create an internal `buildRawMovementProposals` phase that computes direct move-order and pursuit intent from the immutable live snapshot without dynamic-body detours. Then:

1. update allied state using raw proposals;
2. update enemy transit using raw proposals when enabled;
3. construct one authoritative pair snapshot;
4. apply chase-path and local-avoidance planning with that snapshot;
5. update existing allied overlap state from the planned proposals;
6. rebuild the snapshot with allied overlap results but the same enemy decision;
7. resolve and validate movement with the shared snapshot.

This two-phase flow is required so a newly reserved enemy blocker is omitted from path planning in the same tick rather than one repath cycle later.

- [ ] **Step 5: Persist enemy state and deterministic diagnostics.**

Carry only active reservations and inherited extents to the next world. Emit acquisition, persistence, release reason, current separation, full extent, maximum depth, and defensive recovery records in canonical pair-key order. Keep diagnostics out of default worlds when the experiment is disabled.

- [ ] **Step 6: Pass the flag and aggregate diagnostics through `fight.js` and comparison scenarios.**

The default remains false. Explicit experiment scenarios set:

```js
pairwiseEnemyTransit: true
```

Do not enable it globally or remove the War Wagon legacy values in this task.

- [ ] **Step 7: Re-run focused world/comparison tests and the no-flag controls.**

Expected: experiment tests pass; default hashes/results stay unchanged; no non-finite position, invalid starting geometry, or unresolved final constraint occurs.

- [ ] **Step 8: Commit world integration.**

```powershell
git add aoe2x/js_simulation/src/combat/world.js aoe2x/js_simulation/src/fight.js aoe2x/js_simulation/src/dedicated-golden-comparison.js aoe2x/js_simulation/src/phase2-batch1-comparison.js aoe2x/js_simulation/tests/world-tick.test.mjs aoe2x/js_simulation/tests/target-state.test.mjs aoe2x/js_simulation/tests/dedicated-golden-comparison.test.mjs aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs
git commit -m "feat: integrate enemy transit into world ticks"
```

### Task 5: Expose the experiment and pair diagnostics in the existing viewer

**Files:**
- Modify: `aoe2x/js_simulation/server.mjs`
- Modify: `aoe2x/js_simulation/viewer/battle-state.js`
- Modify: `aoe2x/js_simulation/viewer/simulation-review.js`
- Modify: `aoe2x/js_simulation/viewer/map-renderer.js`
- Modify: `aoe2x/js_simulation/viewer/app.js`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`
- Modify: `aoe2x/js_simulation/tests/battle-state.test.mjs`

- [ ] **Step 1: Write failing query and endpoint tests.**

Accept only `enemyTransit=pairwise` or no parameter. Reject duplicates and unknown values. Assert that the API scenario receives `pairwiseEnemyTransit: true` only for the explicit value and that existing viewer URLs remain unchanged.

- [ ] **Step 2: Write failing diagnostic normalization tests.**

For a frame with an active transit, require normalized fields:

```js
{
  pairKey: "101:202",
  chaserId: 202,
  blockerId: 101,
  pursuitTargetId: 303,
  kind: "transit",
  separation: 0.43,
  fullExtent: 0.5,
  overlapDepth: 0.07,
  reason: "non-target-corridor",
}
```

- [ ] **Step 3: Run viewer/server tests and confirm the parameter is rejected or ignored.**

```powershell
node --test aoe2x/js_simulation/tests/server.test.mjs aoe2x/js_simulation/tests/battle-state.test.mjs
```

- [ ] **Step 4: Wire the flag and render diagnostics.**

In debug mode, draw a line from chaser to blocker, a lighter line from chaser to pursuit target, and a compact label with kind/depth. Add text counters for active deep reservations, swept contacts, inherited contacts, and largest contact component. Do not change simulation behavior in renderer code.

- [ ] **Step 5: Re-run viewer/server tests.**

Expected: old URLs and the new explicit experiment URL both pass. The server response carries pair diagnostics only when requested.

- [ ] **Step 6: Commit viewer diagnostics.**

```powershell
git add aoe2x/js_simulation/server.mjs aoe2x/js_simulation/viewer/battle-state.js aoe2x/js_simulation/viewer/simulation-review.js aoe2x/js_simulation/viewer/map-renderer.js aoe2x/js_simulation/viewer/app.js aoe2x/js_simulation/tests/server.test.mjs aoe2x/js_simulation/tests/battle-state.test.mjs
git commit -m "feat: visualize enemy pair transit diagnostics"
```

### Task 6: Build recoverable overlap and outcome gates

**Files:**
- Create: `aoe2x/js_simulation/tests/enemy-transit-report.test.mjs`
- Create: `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/measure_overlap.mjs`
- Create: `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/run_focused_comparisons.mjs`
- Create: `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/build_report.mjs`
- Create: `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/README.md`

- [ ] **Step 1: Verify the clean-room manifest and selected archive hashes before writing analysis code.**

Run the repository's existing manifest/hash verification command identified in the calibration README. Record each `zip_sha256` in the experiment `README.md`. If verification fails, stop this task and report the exact missing/mismatched archive.

- [ ] **Step 2: Write failing aggregation tests using small synthetic frame traces.**

Test:

- frames with any overlap;
- all-pair overlap observations;
- observations at or below 0.51 tiles;
- conditional run median overlap depth;
- longest continuous pair-overlap duration;
- overlap by chaser action and whether the chaser attacks the overlapped unit;
- five-run tape-band min/max aggregation;
- atomic per-row checkpoint creation and completed-row resume.

- [ ] **Step 3: Run the report test and confirm the analysis exports are absent.**

```powershell
node --test aoe2x/js_simulation/tests/enemy-transit-report.test.mjs
```

- [ ] **Step 4: Implement the common measurement and recoverable runner.**

The runner accepts only manifest-selected golden rows and fixed `--samples 5`. It writes one checkpoint immediately after each completed row, then atomically rewrites `progress.json` and `results.json`. On restart it validates scenario, seed set, source hash, engine commit, and experiment flags before skipping a checkpoint.

- [ ] **Step 5: Implement pass/fail reporting against the approved bands.**

The HTML and JSON report must show the following without rounding away failures:

| Control | Metric | Tape acceptance band |
|---|---|---:|
| HCA-Paladin 20v15 | frames with any overlap | 22.24-33.42% |
| HCA-Paladin 20v15 | all-pair overlap | 0.335-0.500% |
| HCA-Paladin 20v15 | separation <= 0.51 | 0.515-0.706% |
| HCA-Paladin 20v15 | conditional median depth | 0.038-0.071 |
| HCA-Paladin 20v15 | longest streak | 2.934-7.530 s |
| War Wagon-Champion 8v21 | frames with any overlap | 28.64-35.53% |
| War Wagon-Champion 8v21 | all-pair overlap | 0.44-0.66% |
| War Wagon-Champion 8v21 | conditional median depth | 0.035-0.101 |
| War Wagon-Paladin 15v17 | all-pair overlap | 0.72-1.06% |
| War Wagon-Paladin 15v17 | conditional median depth | 0.068-0.109 |

Also require the tape winner for both War Wagon controls. Read exact roster counts from each golden manifest row; if an existing evidence label differs from the manifest, the manifest wins and the report records the discrepancy.

- [ ] **Step 6: Re-run report tests and commit the harness.**

```powershell
node --test aoe2x/js_simulation/tests/enemy-transit-report.test.mjs
git add aoe2x/js_simulation/tests/enemy-transit-report.test.mjs aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/measure_overlap.mjs aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/run_focused_comparisons.mjs aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/build_report.mjs aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/README.md
git commit -m "test: add shared enemy transit golden gates"
```

### Task 7: Run the focused experiment and decide whether the general rule is accepted

**Files:**
- Generate under: `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/`
- Modify implementation only if a failed invariant isolates a defect in transit selection or lifecycle.

- [ ] **Step 1: Capture current-engine controls before enabling the experiment.**

Run HCA-Paladin and the two War Wagon rows with current behavior, five samples each. Checkpoint every row. Preserve current outcome deltas and overlap metrics as the comparison baseline.

- [ ] **Step 2: Run the same exact rows with `pairwiseEnemyTransit: true`.**

```powershell
node aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/run_focused_comparisons.mjs --variant pairwise-enemy-transit --samples 5 --workers auto-80pct --resume
node aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/build_report.mjs
```

The worker count may use at most approximately 80% of logical CPU capacity. Each worker processes separate rows/seeds and never shares mutable world state.

- [ ] **Step 3: Inspect engine integrity before interpreting outcomes.**

Require zero engine failures, non-finite positions, invalid starting worlds, unresolved constraints, duplicate deep reservations, direct-target reservations, and checkpoint mismatches. If any occur, fix only the violated pair-state/physics invariant, add a failing regression test, and repeat the three focused rows.

- [ ] **Step 4: Apply the acceptance decision.**

Proceed to Task 8 only if:

- all mandatory overlap metrics are within their tape bands;
- both War Wagon winners are correct;
- HCA-Paladin is not worse than the current outcome delta;
- no current correct winner flips;
- HCA-HCA overlap metrics are unchanged because allied behavior is out of scope.

If the gate fails, keep the flag experimental and the War Wagon override intact. Save the exact failing row/seed/pair diagnostics, add one regression test for the isolated geometric or lifecycle defect, and revise only candidate eligibility, deterministic matching, crossing release, or inherited-contact handling. Do not introduce a fixed depth, unit master check, or unrelated combat tuning.

- [ ] **Step 5: Commit only stable report source and concise accepted/rejected summary.**

Do not stage bulky checkpoints unless already established as tracked project artifacts. Record the engine commit, archive hashes, seeds, sample count, gate result, and report path in `README.md`.

### Task 8: Remove the War Wagon runtime exception after the general gate passes

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/kite-timing.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Modify: `aoe2x/js_simulation/src/phase2-batch1-comparison.js`
- Modify: `aoe2x/js_simulation/tests/kite-timing.test.mjs`
- Modify: `aoe2x/js_simulation/tests/world-tick.test.mjs`
- Modify: `aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs`

- [ ] **Step 1: Write failing migration tests.**

Change expectations so `warWagonChasePolicy` no longer emits `warWagonEnemyOverlapDepthTiles` or `warWagonEnemyOverlapMode`, War Wagon golden scenarios enable `pairwiseEnemyTransit: true`, and no runtime map is constructed solely from War Wagon master 829.

- [ ] **Step 2: Run migration tests and confirm they fail against the legacy override.**

```powershell
node --test aoe2x/js_simulation/tests/kite-timing.test.mjs aoe2x/js_simulation/tests/world-tick.test.mjs aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs
```

- [ ] **Step 3: Remove the War Wagon policy from scenario construction.**

Delete the fixed `0.1` runtime depth and `always` mode from `kite-timing.js` and phase-2 scenario construction. Keep the generic legacy adapter temporarily only if other explicit compatibility tests still exercise it; no accepted production scenario may depend on unit master 829 for overlap.

- [ ] **Step 4: Re-run unit tests and all three focused golden rows.**

The post-removal report must remain inside the same overlap bands and retain both War Wagon winners. If removal fails, restore the last accepted commit and report that the general rule did not yet replace the exception; do not blend both mechanisms.

- [ ] **Step 5: Commit the migration.**

```powershell
git add aoe2x/js_simulation/src/combat/kite-timing.js aoe2x/js_simulation/src/combat/world.js aoe2x/js_simulation/src/phase2-batch1-comparison.js aoe2x/js_simulation/tests/kite-timing.test.mjs aoe2x/js_simulation/tests/world-tick.test.mjs aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs
git commit -m "refactor: replace War Wagon overlap override"
```

### Task 9: Run focused regressions, document the accepted engine, and stop at the allied boundary

**Files:**
- Modify: `aoe2x/js_simulation/README.md`
- Modify: `docs/superpowers/specs/2026-08-18-shared-pair-interaction-design.md` only to record accepted implementation status and evidence links; do not rewrite the approved behavior.
- Modify: `aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/README.md`

- [ ] **Step 1: Run the complete focused unit test set.**

```powershell
node --test aoe2x/js_simulation/tests/pair-interactions.test.mjs aoe2x/js_simulation/tests/enemy-transit.test.mjs aoe2x/js_simulation/tests/allied-transit.test.mjs aoe2x/js_simulation/tests/allied-overlap.test.mjs aoe2x/js_simulation/tests/chase-path.test.mjs aoe2x/js_simulation/tests/local-avoidance.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs aoe2x/js_simulation/tests/steppe-range.test.mjs aoe2x/js_simulation/tests/world-tick.test.mjs aoe2x/js_simulation/tests/target-state.test.mjs aoe2x/js_simulation/tests/kite-timing.test.mjs aoe2x/js_simulation/tests/server.test.mjs aoe2x/js_simulation/tests/battle-state.test.mjs aoe2x/js_simulation/tests/enemy-transit-report.test.mjs
```

Expected: zero new failures. If the branch has documented pre-existing unrelated failures, list them by exact test name and prove they reproduce on the pre-change commit before proceeding.

- [ ] **Step 2: Run the required outcome controls with five samples per golden row.**

Controls:

- HCA-Paladin;
- HCA-Boyar;
- HCA-Elite Steppe Lancer;
- HCA-Hussar;
- ranged-Champion golden rows;
- Scorpion-Paladin;
- War Wagon-Paladin;
- War Wagon-Champion.

Require no wrong-winner regression, no new absolute tape delta above 25 points, no engine failure, and successful checkpoint completion. Do not run non-golden or user-unrequested matchups.

- [ ] **Step 3: Verify HCA-HCA remained unchanged.**

Compare the same fixed seeds before and after enemy transit. Because allied logic is untouched, HCA-HCA positions and overlap statistics must be identical. Record this as the Stage 4 baseline rather than attempting an allied fix here.

- [ ] **Step 4: Manually inspect the viewer experiment URL.**

Use the existing ranged-versus-melee viewer with:

```text
?mode=ranged-vs-melee-kiting&ranged=heavy_cav_archer&melee=paladin&navigation=cohesive&n2=15&n3=20&enemyTransit=pairwise
```

Verify that reserved melee units cross only non-target enemies, direct targets remain solid, a third unit cannot join a deep pair, inherited contacts separate without snapping, and diagnostics correspond to visible pairs.

- [ ] **Step 5: Update documentation.**

Document:

- the authoritative tick sequence;
- every interaction kind and purpose-specific extent;
- eligibility and lifecycle rules;
- deterministic matching and one-to-one invariant;
- experiment/default status;
- removed War Wagon override;
- clean-room source hashes and focused report link;
- known allied HCA-HCA mismatch and explicit deferral to a separate plan.

- [ ] **Step 6: Commit docs and stable report summary.**

```powershell
git add aoe2x/js_simulation/README.md docs/superpowers/specs/2026-08-18-shared-pair-interaction-design.md aoe2x/js_simulation/calibration/reports/shared_enemy_transit_experiment_2026-08-18/README.md
git commit -m "docs: record shared enemy pair transit engine"
```

- [ ] **Step 7: Stop and present the result.**

Report the exact commits, tests, archive hashes, tape-vs-simulation table, viewer URL, any remaining failures, and the deferred allied Stage 4 scope. Do not push or begin allied formation changes without a new user instruction.

## Completion Criteria

This plan is complete only when all of the following are true:

- one shared pair snapshot drives pathing, avoidance, movement, attack stopping, collision, and geometry validation;
- default/no-flag behavior is unchanged through the experiment stage;
- general enemy transit passes HCA-Paladin and both War Wagon overlap/outcome gates;
- the War Wagon-specific runtime overlap depth is removed rather than stacked with the general mechanic;
- direct-target attack/stop geometry remains sourced and unchanged;
- one-to-one deep reservations and non-deepening inherited overlap are enforced by tests;
- required golden controls have no wrong-winner regression, no new delta above 25, and no engine failure;
- HCA-HCA allied behavior is demonstrably unchanged and explicitly deferred;
- documentation and recoverable reports make the result reproducible;
- no production action or push has occurred.
