# Generic Melee Contact Physics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one tape-measured, owner-symmetric pair-contact mechanism that governs generic melee overlap and restores the three failing Phase 2 stable winners without regressing established controls.

**Architecture:** A pure contact-reservation manager classifies and arbitrates allied and enemy pair states from sourced collision mechanics and frozen movement intent. It publishes one immutable reservation map through `pair-interactions.js`, so avoidance, collision, engagement, and attack reach consume the same contact surface. A separate manifested-golden analyzer measures tape and simulation overlap by relationship, motion, attack state, depth, duration, and graph topology.

**Tech Stack:** Node.js 20 ES modules, `node:test`, immutable JavaScript state, 60 Hz simulation ticks, JSONL decoded tape traces, recoverable per-row golden benchmark workers.

**Spec:** `aoe2x/js_simulation/docs/superpowers/specs/2026-08-18-generic-melee-contact-physics-design.md`

## Global Constraints

- Golden evidence must come only from `aoe2x/js_simulation/calibration/source/aoe2_golden_phase2_WITH_TAPES.zip` with SHA-256 `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`.
- Never branch on unit slug, civilization, opponent, matchup row, army ratio, desired winner, or owner number.
- Unit-specific contact inputs are limited to sourced collision size, minimum collision multiplier, attack range, and live physical/target state.
- Preserve the tick order `target acquisition -> orders -> proposals -> contact state -> avoidance -> collision -> engagement -> attack -> damage`.
- Deep overlap is pairwise: one deep reservation per unit and no deep triangle.
- Stable rows use five deterministic samples. Tape-classified knife-edge rows may use at most 15.
- A passing stable row may not flip winner, cross from at most 25 points delta to above 25, or regress more than five points without diagnosis.
- Do not weaken collision convergence, add outcome RNG, or modify speed, damage, HP, armor, reload, or attack delay.
- Do not push to `main`, deploy, or mutate production.

## File Structure

### Create

- `aoe2x/js_simulation/tools/pair-contact-metrics.mjs` — pure tape/simulation pair-frame classification and aggregation.
- `aoe2x/js_simulation/tools/measure_pair_contact_states.mjs` — manifested-golden CLI that loads decoded traces and current simulation snapshots, then writes atomic JSON/Markdown reports.
- `aoe2x/js_simulation/src/combat/contact-reservations.js` — sole dynamic allied/enemy contact-state authority.
- `aoe2x/js_simulation/tests/pair-contact-metrics.test.mjs` — synthetic metric semantics.
- `aoe2x/js_simulation/tests/measure-pair-contact-states.test.mjs` — source validation and report rendering.
- `aoe2x/js_simulation/tests/contact-reservations.test.mjs` — pure reservation state machine, extent, and topology tests.
- `aoe2x/js_simulation/calibration/reports/generic_melee_contact_baseline_2026-08-18/` — source-pinned baseline artifacts.
- `aoe2x/js_simulation/calibration/reports/generic_melee_contact_current_engine_2026-08-18/` — final contact and outcome artifacts.

### Modify

- `aoe2x/js_simulation/src/combat/pair-interactions.js` — normalize and resolve unified reservations.
- `aoe2x/js_simulation/src/combat/world.js` — derive generic melee participants and update contact state once per tick.
- `aoe2x/js_simulation/src/combat/collision.js` — consume unified inherited/releasing extents without policy decisions.
- `aoe2x/js_simulation/src/combat/local-avoidance.js` — use only the unified pair snapshot.
- `aoe2x/js_simulation/src/combat/chase-path.js` — use the same contact obstruction result as collision.
- `aoe2x/js_simulation/src/combat/attacks.js` — use the same engagement contact surface.
- `aoe2x/js_simulation/src/phase2-batch1-comparison.js` — remove owner-selected crowd configuration.
- `aoe2x/js_simulation/src/dedicated-golden-comparison.js` — remove owner-selected crowd configuration.
- `aoe2x/js_simulation/src/placement.js` and viewer scenario construction only where they currently emit melee crowd flags.
- `aoe2x/js_simulation/tests/pair-interactions.test.mjs`
- `aoe2x/js_simulation/tests/world-tick.test.mjs`
- `aoe2x/js_simulation/tests/local-avoidance.test.mjs`
- `aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs`
- `aoe2x/js_simulation/tests/dedicated-golden-comparison.test.mjs`
- `aoe2x/js_simulation/tests/contact-graph-steering.test.mjs`
- `aoe2x/js_simulation/tests/allied-overlap.test.mjs`, `allied-transit.test.mjs`, and `enemy-transit.test.mjs` during migration.
- `aoe2x/js_simulation/docs/CURRENT_ENGINE_2026-08-15.md`
- `aoe2x/js_simulation/docs/GOLDEN_TAPE_COMPARISON_WORKFLOW.md`
- `aoe2x/js_simulation/calibration/reports/phase2_melee_failures_diagnosis_2026-08-18/report.md`

### Retire after parity

- `aoe2x/js_simulation/src/combat/allied-overlap.js`
- Dynamic state portions of `aoe2x/js_simulation/src/combat/allied-transit.js`
- `aoe2x/js_simulation/src/combat/enemy-transit.js`

Keep any still-used canonical pair-key or geometry helper by moving it to
`pair-interactions.js` or `contact-reservations.js` before deletion.

---

### Task 1: Pair-contact measurement kernel

**Files:**
- Create: `aoe2x/js_simulation/tools/pair-contact-metrics.mjs`
- Create: `aoe2x/js_simulation/tests/pair-contact-metrics.test.mjs`

**Interfaces:**
- Consumes: normalized frames `{ timeMs, units }`, where a unit contains `id`, `owner`, `master`, `x`, `y`, `radius`, `hp`, `moving`, `attacking`, `pursuitTargetId`, `engagedTargetId`, and `attackTargetId`.
- Produces: `analyzePairContactFrames(frames) -> PairContactReport` and `percentile(values, probability) -> number | null`.
- `PairContactReport.populations` is keyed by `relationship|motion|attack|intent|phase`, where intent is `direct-target`, `corridor-contact`, or `none`, and phase is `entering`, `persisting`, or `leaving`.
- `PairContactReport.relationships` keeps relationship-wide contact-window and graph metrics so motion, attack, intent, or phase changes do not fragment one physical contact window.

- [ ] **Step 1: Write the failing synthetic classification test**

```js
import assert from "node:assert/strict";
import test from "node:test";
import { analyzePairContactFrames } from "../tools/pair-contact-metrics.mjs";

const frame = (timeMs, units) => Object.freeze({ timeMs, units: Object.freeze(units) });
const unit = (id, owner, x, {
  master = owner,
  moving = false,
  attacking = false,
  targetId = null,
} = {}) => Object.freeze({
  id, owner, master, x, y: 4, radius: 0.25, hp: 100,
  moving, attacking,
  pursuitTargetId: targetId,
  engagedTargetId: targetId,
  attackTargetId: attacking ? targetId : null,
});

test("pair contact metrics separate relationship, motion, attack, intent, and phase", () => {
  const report = analyzePairContactFrames([
    frame(0, [unit(1, 2, 4), unit(2, 2, 4.6), unit(3, 3, 5.2)]),
    frame(100, [
      unit(1, 2, 4.2, { moving: true, targetId: 3 }),
      unit(2, 2, 4.55, { attacking: true, targetId: 3 }),
      unit(3, 3, 4.5, { moving: true, targetId: 1 }),
    ]),
  ]);

  assert.equal(report.populations["same-master-allies|one-moving|one-attacking|none|entering"].overlapPairs, 1);
  assert.equal(report.populations["enemies|both-moving|neither-attacking|direct-target|entering"].overlapPairs, 1);
  assert.equal(report.populations["enemies|both-moving|neither-attacking|direct-target|entering"].medianDepth, 0.2);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
node --test tests/pair-contact-metrics.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `pair-contact-metrics.mjs`.

- [ ] **Step 3: Implement the minimal classifier and accumulator**

```js
export function analyzePairContactFrames(frames) {
  const populations = new Map();
  for (const frame of frames) {
    const live = frame.units.filter(({ hp }) => hp > 0);
    for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
        observe(populations, frame.timeMs, live[leftIndex], live[rightIndex]);
      }
    }
  }
  return Object.freeze({ populations: finishPopulations(populations) });
}

function pairState(left, right) {
  const relationship = left.owner !== right.owner
    ? "enemies"
    : (left.master === right.master ? "same-master-allies" : "mixed-master-allies");
  const moving = Number(left.moving) + Number(right.moving);
  const attacking = Number(left.attacking) + Number(right.attacking);
  return {
    relationship,
    motion: ["neither-moving", "one-moving", "both-moving"][moving],
    attack: ["neither-attacking", "one-attacking", "both-attacking"][attacking],
    intent: enemyIntent(left, right),
  };
}
```

Complete `observe()` and `finishPopulations()` in the same file with:

- Chebyshev separation;
- `fullExtent = left.radius + right.radius`;
- `depth = Math.max(0, fullExtent - separation)`;
- normalized depth;
- contiguous pair contact windows keyed by canonical ID pair;
- entering, persisting, and leaving contact from the previous sampled pair-frame;
- enemy intent from pursuit, engagement, and attack target IDs;
- p01/p05/median/p95/p99 and literal extrema;
- per-frame overlap graph degree, component, triangle, and four-clique counts.

- [ ] **Step 4: Add tests for duration and graph topology**

```js
test("contact windows and graph topology do not mistake a three-stack for pairs", () => {
  const frames = [0, 100, 200].map((timeMs) => frame(timeMs, [
    unit(1, 2, 4.00), unit(2, 2, 4.25), unit(3, 2, 4.40),
  ]));
  const report = analyzePairContactFrames(frames);
  const row = report.relationships["same-master-allies"];
  assert.equal(row.maximumLocalDegree, 2);
  assert.equal(row.maximumComponentSize, 3);
  assert.equal(row.maximumTriangles, 1);
  assert.equal(row.contactWindowMs.median, 300);
});
```

- [ ] **Step 5: Run the focused test and verify GREEN**

Run: `node --test tests/pair-contact-metrics.test.mjs`

Expected: all pair-contact metric tests PASS.

- [ ] **Step 6: Commit the measurement kernel**

```powershell
git add -- tools/pair-contact-metrics.mjs tests/pair-contact-metrics.test.mjs
git commit -m "test: add pair contact measurement kernel"
```

---

### Task 2: Manifested analyzer and baseline report

**Files:**
- Create: `aoe2x/js_simulation/tools/measure_pair_contact_states.mjs`
- Create: `aoe2x/js_simulation/tests/measure-pair-contact-states.test.mjs`
- Create: `aoe2x/js_simulation/calibration/reports/generic_melee_contact_baseline_2026-08-18/report.json`
- Create: `aoe2x/js_simulation/calibration/reports/generic_melee_contact_baseline_2026-08-18/report.md`
- Create: `aoe2x/js_simulation/calibration/reports/generic_melee_contact_baseline_2026-08-18/run-manifest.json`

**Interfaces:**
- Consumes: Phase 2 truth rows, verified archive metadata, decoded `*.tape_trace.jsonl`, and current simulation snapshots.
- Produces: `runPairContactAnalysis({ rowIds, traceDirectories, outputDirectory, samples, seed }) -> report`.
- CLI flags: `--row-ids`, `--trace-dirs`, `--output-dir`, `--samples`; trace directories are a comma-separated ordered list and samples must be `1..15`.

- [ ] **Step 1: Write the failing source-validation and report test**

```js
import assert from "node:assert/strict";
import test from "node:test";
import { validateAnalysisSource, renderPairContactMarkdown } from
  "../tools/measure_pair_contact_states.mjs";

test("pair contact reports require the authorized Phase 2 archive hash", () => {
  assert.throws(() => validateAnalysisSource({
    name: "wrong.zip", zip_sha256: "00",
  }), /authorized Phase 2 archive/);
  assert.doesNotThrow(() => validateAnalysisSource({
    name: "aoe2_golden_phase2_WITH_TAPES.zip",
    zip_sha256: "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6",
  }));
});

test("markdown exposes relationship, motion, attack, intent, phase, depth, and graph metrics", () => {
  const markdown = renderPairContactMarkdown({
    source: { name: "golden.zip", zipSha256: "ABC" },
    rows: [{ id: "row", populations: [{ relationship: "enemies",
      motion: "both-moving", attack: "one-attacking",
      intent: "direct-target", phase: "persisting", pairShare: 0.1,
      medianDepth: 0.05, p99Depth: 0.1, maximumLocalDegree: 2 }]}],
  });
  assert.match(markdown, /both-moving/);
  assert.match(markdown, /one-attacking/);
  assert.match(markdown, /direct-target/);
  assert.match(markdown, /persisting/);
  assert.match(markdown, /p99/);
  assert.match(markdown, /local degree/i);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/measure-pair-contact-states.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement source validation, loaders, and atomic writers**

```js
export const PHASE2_ARCHIVE = Object.freeze({
  name: "aoe2_golden_phase2_WITH_TAPES.zip",
  zipSha256: "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6",
});

export function validateAnalysisSource(archive) {
  if (archive?.name !== PHASE2_ARCHIVE.name
      || archive?.zip_sha256 !== PHASE2_ARCHIVE.zipSha256) {
    throw new Error("pair-contact analysis requires the authorized Phase 2 archive");
  }
  return true;
}

async function atomicWrite(path, contents) {
  const temporary = `${path}.${process.pid}.tmp`;
  const handle = await open(temporary, "w");
  try {
    await handle.writeFile(contents, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
  await rename(temporary, path);
}
```

Implement `runPairContactAnalysis()` by normalizing tape and simulation frames
into Task 1's schema and calling `analyzePairContactFrames()` for each run. Keep
tape and simulation run metrics separate, then aggregate only after preserving
run-level values.

- [ ] **Step 4: Verify the focused analyzer tests GREEN**

Run: `node --test tests/pair-contact-metrics.test.mjs tests/measure-pair-contact-states.test.mjs`

Expected: all tests PASS.

- [ ] **Step 5: Generate the pre-change baseline**

Run from `aoe2x/js_simulation`:

```powershell
node tools/measure_pair_contact_states.mjs --row-ids elite_keshik_vs_champion,elite_keshik_vs_paladin,elite_shotel_warrior_vs_paladin,elite_boyar_vs_champion,elite_boyar_vs_paladin --trace-dirs calibration/reports/phase2_keshik_champion_diagnosis_2026-08-18,calibration/reports/phase2_melee_failures_diagnosis_2026-08-18 --output-dir calibration/reports/generic_melee_contact_baseline_2026-08-18 --samples 5
```

If a named trace is absent, decode that exact manifested row from the authorized
archive into the baseline directory; do not substitute another trace.

- [ ] **Step 6: Audit baseline completeness**

Run:

```powershell
node -e "const r=require('fs').readFileSync('calibration/reports/generic_melee_contact_baseline_2026-08-18/report.json','utf8');const j=JSON.parse(r);if(j.rows.length!==5||j.rows.some(x=>!x.tape?.runs?.length||!x.simulation?.runs?.length))process.exit(1)"
```

Expected: exit code 0; report includes all five rows, archive hash, tape runs,
simulation samples, and every state population.

- [ ] **Step 7: Commit analyzer and immutable baseline**

```powershell
git add -- tools/pair-contact-metrics.mjs tools/measure_pair_contact_states.mjs tests/pair-contact-metrics.test.mjs tests/measure-pair-contact-states.test.mjs calibration/reports/generic_melee_contact_baseline_2026-08-18
git commit -m "feat: measure tape pair contact states"
```

---

### Task 3: Pure generic contact-reservation manager

**Files:**
- Create: `aoe2x/js_simulation/src/combat/contact-reservations.js`
- Create: `aoe2x/js_simulation/tests/contact-reservations.test.mjs`

**Interfaces:**
- Produces `createContactReservationState() -> { reservations: Map, inheritedExtents: Map }`.
- Produces `updateContactReservations({ state, units, proposals, tick }) -> { state, contactReservations, diagnostics }`.
- Reservation fields are `{ leftId, rightId, kind, collisionExtent, attackSurfaceExtent, pathObstructs, mayDeepen, initiatorId, targetId, acquiredTick }`.
- Kinds are `allied-transit`, `enemy-transit`, `engagement-contact`, and `releasing`.

- [ ] **Step 1: Write failing mechanics-floor and topology tests**

```js
import assert from "node:assert/strict";
import test from "node:test";
import {
  createContactReservationState,
  updateContactReservations,
} from "../src/combat/contact-reservations.js";

const mechanics = (radius, multiplier = 0.5, range = 0) => Object.freeze({
  collision_size_tiles: Object.freeze({ x: radius, y: radius }),
  min_collision_size_multiplier: multiplier,
  attack_range_tiles: range,
});
const unit = (referenceId, owner, x, overrides = {}) => Object.freeze({
  referenceId, owner, x, y: 4, alive: true,
  mechanics: mechanics(0.25), pursuitTargetId: null,
  engagedTargetId: null, attackTargetId: null, action: "moving", ...overrides,
});
const proposal = (referenceId, dx) => Object.freeze({ referenceId, dx, dy: 0 });

test("a closing allied pair derives its floor from both sourced multipliers", () => {
  const result = updateContactReservations({
    state: createContactReservationState(), tick: 10,
    units: [unit(1, 2, 4), unit(2, 2, 4.5)],
    proposals: [proposal(1, 0.1), proposal(2, -0.1)],
  });
  assert.equal(result.contactReservations.get("1:2").kind, "allied-transit");
  assert.equal(result.contactReservations.get("1:2").collisionExtent, 0.25);
});

test("three closing allies cannot form two deep edges or a deep triangle", () => {
  const result = updateContactReservations({
    state: createContactReservationState(), tick: 10,
    units: [unit(1, 2, 4), unit(2, 2, 4.5), unit(3, 2, 4.25)],
    proposals: [proposal(1, 0.1), proposal(2, -0.1), proposal(3, 0.05)],
  });
  assert.equal(result.contactReservations.size, 1);
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test tests/contact-reservations.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement immutable state validation and mechanics-derived extents**

```js
export function createContactReservationState() {
  return Object.freeze({ reservations: new Map(), inheritedExtents: new Map() });
}

function movingFloor(left, right) {
  return collisionRadius(left) * minimumMultiplier(left)
    + collisionRadius(right) * minimumMultiplier(right);
}

function minimumMultiplier(unit) {
  const value = unit.mechanics?.min_collision_size_multiplier;
  if (!Number.isFinite(value) || value <= 0 || value > 1) {
    throw new RangeError("minimum collision multiplier must be within (0, 1]");
  }
  return value;
}
```

Implement canonical candidate generation and sort by:

1. swept time of contact;
2. projected normalized depth, shallowest first;
3. greater progress toward valid destination or target;
4. canonical pair key.

Arbitrate one deep edge per reference ID. Do not emit shallow shrink permission.

- [ ] **Step 4: Add failing movement/attack state tests**

```js
test("stopped or attacking allies cannot newly acquire transit", () => {
  for (const action of ["idle", "attacking"]) {
    const units = [unit(1, 2, 4, { action }), unit(2, 2, 4.45, { action })];
    const result = updateContactReservations({
      state: createContactReservationState(), units,
      proposals: [proposal(1, 0), proposal(2, 0)], tick: 20,
    });
    assert.equal(result.contactReservations.size, 0);
  }
});

test("an inherited pair releases monotonically without further deepening", () => {
  const state = Object.freeze({
    reservations: new Map(), inheritedExtents: new Map([["1:2", 0.3]]),
  });
  const result = updateContactReservations({
    state, tick: 20,
    units: [unit(1, 2, 4), unit(2, 2, 4.3)],
    proposals: [proposal(1, -0.05), proposal(2, 0.05)],
  });
  const release = result.contactReservations.get("1:2");
  assert.equal(release.kind, "releasing");
  assert.equal(release.collisionExtent, 0.3);
  assert.equal(release.mayDeepen, false);
});
```

- [ ] **Step 5: Implement enemy modes and release**

Direct enemy target contact produces `engagement-contact`. A melee pursuer
closing through a non-target enemy produces `enemy-transit`. Range-one melee
eligibility derives from `attack_range_tiles >= 1`; no master or slug check is
allowed. Releasing reservations publish the inherited current extent and
`mayDeepen: false` until ordinary full extent is restored.

```js
function directTarget(left, right) {
  return left.pursuitTargetId === right.referenceId
    || left.engagedTargetId === right.referenceId
    || left.attackTargetId === right.referenceId;
}

function reservationKind(left, right) {
  if (left.owner === right.owner) return "allied-transit";
  return directTarget(left, right) || directTarget(right, left)
    ? "engagement-contact" : "enemy-transit";
}
```

- [ ] **Step 6: Add owner, array-order, mixed-radius, death, and range-one tests**

For each test, run the same physical scene after swapping owners and reversing
the unit/proposal arrays. Compare sorted reservation objects after owner
normalization. Add a `0.20 + 0.25` mixed-radius test, target-death release test,
and range-one melee corridor test.

- [ ] **Step 7: Run pure tests and verify GREEN**

Run:

```powershell
node --test tests/contact-reservations.test.mjs tests/pair-contact-metrics.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 8: Commit the pure manager**

```powershell
git add -- src/combat/contact-reservations.js tests/contact-reservations.test.mjs
git commit -m "feat: add generic pair contact reservations"
```

---

### Task 4: Unified pair-interaction snapshot

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/pair-interactions.js`
- Modify: `aoe2x/js_simulation/tests/pair-interactions.test.mjs`

**Interfaces:**
- Consumes: `contactReservations: Map<string, ContactReservation>` from Task 3.
- Produces: `createPairInteractionSnapshot({ contactReservations })` and unchanged `resolvePairInteraction(left, right, snapshot)` return shape.
- During migration, legacy inputs remain accepted but a canonical pair may not exist in both unified and legacy state.

- [ ] **Step 1: Write the failing unified-snapshot test**

```js
test("unified contact reservations are the authoritative pair surface", () => {
  const left = unit({ referenceId: 1, owner: 2, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 2, radius: 0.25 });
  const snapshot = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1, rightId: 2, kind: "allied-transit",
      collisionExtent: 0.25, attackSurfaceExtent: 0.5,
      pathObstructs: true, mayDeepen: true,
      initiatorId: 1, targetId: null, acquiredTick: 10,
    })]]),
  });
  assert.deepEqual(resolvePairInteraction(left, right, snapshot), {
    kind: "allied-transit", collisionExtent: 0.25,
    pathObstructs: true, attackSurfaceExtent: 0.5,
    mayDeepen: true, reason: "unified-contact-reservation",
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `node --test tests/pair-interactions.test.mjs`

Expected: FAIL because `contactReservations` is ignored.

- [ ] **Step 3: Normalize unified reservations and resolve them first**

```js
function normalizeContactReservations(value) {
  const result = new Map();
  for (const [key, reservation] of requireMap(value, "contact reservations")) {
    validateCanonicalPairKey(key, "contact reservation");
    if (dynamicPairKey(reservation.leftId, reservation.rightId) !== key) {
      throw new TypeError("contact reservation IDs must match its pair key");
    }
    result.set(key, Object.freeze({ ...reservation }));
  }
  return result;
}
```

In `resolvePairInteraction()`, return the unified reservation's exact public
geometry before evaluating legacy stores. Throw during snapshot construction if
the same key appears in unified and legacy reservation maps.

- [ ] **Step 4: Add validation and consumer-consistency tests**

Assert malformed extents, invalid kinds, non-canonical keys, mismatched IDs, and
duplicate unified/legacy keys throw. Assert collision, path obstruction, and
attack surface all come from the same reservation.

- [ ] **Step 5: Run pair and collision tests GREEN**

Run:

```powershell
node --test tests/pair-interactions.test.mjs tests/movement-collision.test.mjs tests/collision-recovery.test.mjs tests/local-avoidance.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 6: Commit the common snapshot boundary**

```powershell
git add -- src/combat/pair-interactions.js tests/pair-interactions.test.mjs
git commit -m "refactor: resolve unified contact surfaces"
```

---

### Task 5: World integration and generic owner symmetry

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Modify: `aoe2x/js_simulation/src/combat/collision.js`
- Modify: `aoe2x/js_simulation/src/combat/local-avoidance.js`
- Modify: `aoe2x/js_simulation/src/combat/chase-path.js`
- Modify: `aoe2x/js_simulation/src/combat/attacks.js`
- Modify: `aoe2x/js_simulation/src/phase2-batch1-comparison.js`
- Modify: `aoe2x/js_simulation/src/dedicated-golden-comparison.js`
- Modify: `aoe2x/js_simulation/tests/world-tick.test.mjs`
- Modify: `aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs`
- Modify: `aoe2x/js_simulation/tests/dedicated-golden-comparison.test.mjs`

**Interfaces:**
- `world.contactReservationState` is always present when any live unit has melee mode.
- `stepWorld()` calls `updateContactReservations()` once per tick after raw movement proposals.
- Scenario builders no longer emit `meleeCrowdOwner`, `meleeCrowdOwners`, or `pairwiseEnemyTransit` for ordinary melee physics.

- [ ] **Step 1: Write failing world-construction and symmetry tests**

```js
test("melee contact state is mechanics-derived rather than selected by owner", () => {
  const world = createWorld(scenario([
    meleeUnit({ referenceId: 1, owner: 2 }),
    meleeUnit({ referenceId: 2, owner: 3 }),
  ]));
  assert.ok(world.contactReservationState);
  assert.equal(Object.hasOwn(world, "crowdState"), false);
  assert.equal(Object.hasOwn(world, "crowdStates"), false);
  assert.equal(Object.hasOwn(world, "enemyTransitState"), false);
});

test("owner swap preserves normalized contact diagnostics", () => {
  const original = runWorld(createWorld(contactScenario({ swapOwners: false })));
  const swapped = runWorld(createWorld(contactScenario({ swapOwners: true })));
  assert.deepEqual(normalizeOwners(swapped.events), normalizeOwners(original.events));
});
```

- [ ] **Step 2: Run focused world tests and verify RED**

Run: `node --test tests/world-tick.test.mjs tests/phase2-batch1-comparison.test.mjs`

Expected: FAIL because the world still creates separate crowd/enemy-transit states.

- [ ] **Step 3: Integrate one contact-state update**

```js
const contactReservationState = units.some((unit) => (
  unit.mechanics?.ranged === undefined || unit.mechanics.ranged === null
)) ? createContactReservationState() : null;
```

In `moveUnits()`:

```js
const contactUpdate = contactReservationState
  ? updateContactReservations({
      state: contactReservationState, units: live, proposals, tick,
    })
  : null;
const pairInteractions = createPairInteractionSnapshot({
  contactReservations: contactUpdate?.contactReservations ?? new Map(),
});
```

Store `contactUpdate.state` on the world and append its diagnostics to the event
log. Pass only this snapshot to avoidance, collision, path planning, and attack
reach for unified keys.

- [ ] **Step 4: Remove owner-selected melee configuration from scenario builders**

Delete ordinary-melee emission and validation of:

```js
meleeCrowdOwner
meleeCrowdOwners
pairwiseEnemyTransit
```

Derive the set of melee owners inside `world.js` only when preventive steering
needs an owner partition. Iterate every derived melee owner with the same
physics and strength. Keep kiting orders and one-range intent, but do not let
them select an alternate collision law.

- [ ] **Step 5: Add contact-lane integration tests**

Add a 3-on-1 convergence scene proving one deep allied pair and one ordinary
third-unit surface. Add a surplus-unit scene proving rejected rear units take a
lateral clear proposal rather than inheriting the pair's reduced extent. Add a
direct engagement scene proving `attacks.js` and `collision.js` read the same
surface.

- [ ] **Step 6: Run focused integration tests GREEN**

Run:

```powershell
node --test tests/contact-reservations.test.mjs tests/pair-interactions.test.mjs tests/world-tick.test.mjs tests/local-avoidance.test.mjs tests/phase2-batch1-comparison.test.mjs tests/dedicated-golden-comparison.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 7: Commit world integration**

```powershell
git add -- src/combat/world.js src/combat/collision.js src/combat/local-avoidance.js src/combat/chase-path.js src/combat/attacks.js src/phase2-batch1-comparison.js src/dedicated-golden-comparison.js tests/world-tick.test.mjs tests/local-avoidance.test.mjs tests/phase2-batch1-comparison.test.mjs tests/dedicated-golden-comparison.test.mjs
git commit -m "feat: apply generic melee contact physics"
```

---

### Task 6: Retire independent overlap authorities

**Files:**
- Delete: `aoe2x/js_simulation/src/combat/allied-overlap.js`
- Delete or reduce to key helpers: `aoe2x/js_simulation/src/combat/allied-transit.js`
- Delete: `aoe2x/js_simulation/src/combat/enemy-transit.js`
- Modify: `aoe2x/js_simulation/src/combat/pair-interactions.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`
- Modify/Delete: corresponding overlap/transit tests after porting every retained invariant.

**Interfaces:**
- `contact-reservations.js` is the only dynamic reduced-extent state owner.
- `createPairInteractionSnapshot()` no longer accepts `alliedShrinkPairs`, `alliedShallowPairs`, `exclusiveAlliedShrinkOwners`, `enemyTransitPairs`, `sweptEnemyContactExtents`, or `inheritedEnemyContactExtents`.

- [ ] **Step 1: Port every retained legacy invariant into the unified tests**

Before deletion, enumerate test names from:

```powershell
node --test --test-name-pattern="." tests/allied-overlap.test.mjs tests/allied-transit.test.mjs tests/enemy-transit.test.mjs
```

For each behavior still allowed by the spec, add an equivalent assertion to
`contact-reservations.test.mjs`. Explicitly preserve inherited-contact recovery,
swept-contact handling, direct-target capture, range-one wedge entry, death
release, array-order determinism, and collision-failure prevention.

- [ ] **Step 2: Add the failing exclusive-authority test**

```js
test("pair snapshots reject retired independent contact authorities", () => {
  assert.throws(() => createPairInteractionSnapshot({
    alliedShrinkPairs: new Set(["1:2"]),
  }), /unknown pair interaction option/);
  assert.throws(() => createPairInteractionSnapshot({
    enemyTransitPairs: new Map(),
  }), /unknown pair interaction option/);
});
```

- [ ] **Step 3: Run the test and verify RED**

Run: `node --test tests/pair-interactions.test.mjs`

Expected: FAIL because legacy options are still accepted.

- [ ] **Step 4: Remove legacy stores and option branches**

Move `dynamicPairKey` and any retained pure geometric helper before deleting
modules. Remove old imports, world fields, scenario validation, snapshot
normalizers, and legacy resolution branches. Keep War Wagon or ranged-ingress
policies only if they are expressed through generic reservation inputs; no
master-ID policy may remain in collision resolution.

- [ ] **Step 5: Run all contact and world tests GREEN**

Run:

```powershell
node --test tests/contact-reservations.test.mjs tests/pair-interactions.test.mjs tests/movement-collision.test.mjs tests/collision-recovery.test.mjs tests/local-avoidance.test.mjs tests/contact-graph-steering.test.mjs tests/world-tick.test.mjs tests/target-state.test.mjs
```

Expected: all tests PASS with no import of deleted modules.

- [ ] **Step 6: Scan for retired policy names**

Run:

```powershell
rg -n "meleeCrowdOwner|meleeCrowdOwners|alliedShrinkPairs|alliedShallowPairs|enemyTransitState|enemyTransitPairs|legacyEnemyOverlapDepthByMaster" src tests
```

Expected: no runtime matches. A migration-history comment is allowed only in
documentation, not source or tests.

- [ ] **Step 7: Commit authority consolidation**

```powershell
git add -- src/combat tests
git commit -m "refactor: consolidate contact reservation authority"
```

---

### Task 7: Focused tape physics and outcome gates

**Files:**
- Create: `aoe2x/js_simulation/calibration/reports/generic_melee_contact_current_engine_2026-08-18/report.json`
- Create: `aoe2x/js_simulation/calibration/reports/generic_melee_contact_current_engine_2026-08-18/report.md`
- Create: focused recoverable outcome checkpoints in the same report directory.
- Modify production code only after a new single-hypothesis failing test identifies a remaining physical discrepancy.

**Interfaces:**
- Consumes: Task 2 baseline and current unified engine.
- Produces: before/after tape-vs-simulation contact table and focused Phase 2 outcome report.

- [ ] **Step 1: Run the full JavaScript test suite**

Run: `npm test`

Expected: all tests PASS before golden sampling.

- [ ] **Step 2: Generate the post-change contact report**

Run the same five-row command from Task 2 with output directory:

```text
calibration/reports/generic_melee_contact_current_engine_2026-08-18
```

Expected: report contains the same row IDs, archive hash, samples, and state
populations as baseline.

- [ ] **Step 3: Compare contact distributions**

Add a report section for every relationship/motion/attack/intent/phase population showing:

- baseline simulation;
- current simulation;
- tape repeat range;
- direction of change;
- pass/fail for pair share, p05/median/p95 depth, duration, maximum local degree,
  component size, triangles, and attack access.

Reject the candidate if an aggregate improves only by making a moving or
attacking subpopulation worse on the opposite side of the tape range.

- [ ] **Step 4: Run the focused recoverable outcome suite**

```powershell
node tools/run_recoverable_phase2_batch1.mjs --output-dir calibration/reports/generic_melee_contact_current_engine_2026-08-18/outcomes --workers 7 --row-ids elite_keshik_vs_champion,elite_keshik_vs_paladin,elite_shotel_warrior_vs_paladin,elite_boyar_vs_champion,elite_boyar_vs_paladin,elite_woad_raider_vs_champion,elite_woad_raider_vs_paladin
```

Expected:

- zero unresolved runs;
- correct stable winner for all three diagnosed rows;
- Keshik-versus-Paladin mean inside its tape repeat range;
- no passing control flips winner or crosses/regresses beyond global gates.

- [ ] **Step 5: If a gate fails, return to one measured hypothesis**

Do not stack changes. Add one failing unit or world test that reproduces the
specific mismatched state population, implement one mechanics-derived change,
rerun that test, the contact report, and the seven-row suite. After three failed
hypotheses, stop and revisit the architecture with the user.

- [ ] **Step 6: Commit focused evidence only after gates pass**

```powershell
git add -- calibration/reports/generic_melee_contact_current_engine_2026-08-18
git commit -m "test: verify generic melee contact against tape"
```

---

### Task 8: Impacted portfolio, documentation, and final verification

**Files:**
- Modify: `aoe2x/js_simulation/tools/run_recoverable_phase2_batch1.mjs`
- Modify: `aoe2x/js_simulation/tests/phase2-batch1-comparison.test.mjs`
- Modify: `aoe2x/js_simulation/docs/CURRENT_ENGINE_2026-08-15.md`
- Modify: `aoe2x/js_simulation/docs/GOLDEN_TAPE_COMPARISON_WORKFLOW.md`
- Modify: `aoe2x/js_simulation/calibration/reports/phase2_melee_failures_diagnosis_2026-08-18/report.md`
- Create: `aoe2x/js_simulation/calibration/reports/generic_melee_contact_impacted_portfolio_2026-08-18/`

**Interfaces:**
- Consumes: manifested Phase 2 and dedicated golden rows containing melee units.
- Produces: recoverable final portfolio, current-engine documentation, and final regression summary.

- [ ] **Step 1: Select impacted manifested rows mechanically**

Add an exported selector test to the recoverable runner:

```js
test("impacted contact portfolio includes every manifested row with a melee side", () => {
  const selected = selectMeleeContactRowIds(truth.rows, registry);
  assert.ok(selected.includes("elite_keshik_vs_champion"));
  assert.ok(selected.includes("elite_shotel_warrior_vs_paladin"));
  assert.equal(selected.some((id) => id.includes("unmanifested")), false);
});
```

Implement selection from registry combat class/mechanics, not row-name strings.

- [ ] **Step 2: Run impacted rows with atomic checkpoints**

Use the existing recoverable runners with automatic 80% CPU worker selection.
Write to `generic_melee_contact_impacted_portfolio_2026-08-18`. Do not reuse
checkpoints whose engine signature differs.

- [ ] **Step 3: Audit portfolio gates**

The final report must list:

- all wrong stable winners;
- all rows above 25 points absolute mean delta;
- all individual delta regressions over five points;
- all unresolved or collision-failure samples;
- contact-state populations outside tape range;
- samples used per row, proving five stable and at most 15 knife-edge samples.

Expected: no new wrong stable winner, no engine failure, and no undeclared gate
regression.

- [ ] **Step 4: Update engine and workflow documentation**

Document the five-state contact machine, mechanics-derived floors, pairwise
topology invariants, unified tick boundary, owner symmetry, analyzer metrics,
and recoverable validation procedure. Update the diagnosis report with final
before/after outcome and contact tables.

- [ ] **Step 5: Run final verification**

Run:

```powershell
npm test
node --check src/combat/contact-reservations.js
node --check tools/pair-contact-metrics.mjs
node --check tools/measure_pair_contact_states.mjs
git diff --check
```

Expected: all tests and syntax checks PASS; `git diff --check` reports no new
whitespace errors. Existing Windows global-ignore permission warnings are not
engine failures.

- [ ] **Step 6: Commit final documentation and portfolio**

```powershell
git add -- docs/CURRENT_ENGINE_2026-08-15.md docs/GOLDEN_TAPE_COMPARISON_WORKFLOW.md calibration/reports/phase2_melee_failures_diagnosis_2026-08-18/report.md calibration/reports/generic_melee_contact_impacted_portfolio_2026-08-18
git commit -m "docs: record generic melee contact calibration"
```

- [ ] **Step 7: Report completion without production action**

Provide the user:

- commit IDs;
- focused and portfolio report links;
- tape versus simulation outcomes for the three repaired rows;
- any remaining wrong winner or >25-point row;
- test counts and engine-failure count;
- confirmation that nothing was pushed to `main` or deployed.
