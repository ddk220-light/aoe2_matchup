# Ranged Solo Movement Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Implemented and verified locally on 2026-08-11.

**Goal:** Add a shareable unit selector for five ranged units to the existing 21-unit enemy-free movement lab.

**Architecture:** Derive recurring ranged attack/movement timing from mechanics on the shared AI command grid, then generalize the hard-coded solo runner behind its existing endpoint, publish an explicit unit allowlist, and make cohesive formation geometry use real collision radii. Existing tape profiles validate the derivation but are not its runtime inputs. The viewer reads the allowlist from `/api/units`, keeps `unit` and `navigation` in the URL, and renders the selected registry metadata.

**Tech Stack:** Node.js ES modules, Node test runner, browser JavaScript, HTML/CSS, existing clean-room mechanics fixtures.

## Global Constraints

- Preserve the legacy Hand Cannoneer deep link and default.
- Run exactly 21 owner-2 units with no enemy roster.
- Select only `hand_cannoneer`, `arbalester`, `heavy_cav_archer`, `heavy_scorpion`, and `imp_elite_skirm`.
- Use each unit's real clean-room mechanics; do not force-fit combat outcomes.
- Derive recurring cycle and post-release movement phases from reload and attack delay; movement speed controls achieved distance, not cadence.
- Preserve opening/top-up/formation choices only as named AI policy, never as per-unit recurring clock values.
- Do not deploy or modify production.

---

### Task 1: URL and API Contract

**Files:**
- Modify: `aoe2x/js_simulation/tests/battle-state.test.mjs`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`
- Modify: `aoe2x/js_simulation/viewer/battle-state.js`
- Modify: `aoe2x/js_simulation/server.mjs`

**Interfaces:**
- Consumes: `soloMovementRequest(urlValue)` and the existing solo endpoint.
- Produces: `{ endpoint, unit, navigation, query }` and a server-validated `unit` query parameter.

- [x] **Step 1: Write failing browser-state and server tests**

```js
assert.equal(soloMovementRequest("/?mode=hand-cannoneer-solo-movement&unit=arbalester").unit,
  "arbalester");
assert.equal((await fetch(`${baseUrl}/api/solo-hand-cannoneers?unit=champion`)).status, 400);
```

- [x] **Step 2: Run the focused tests and confirm the failures are caused by the missing `unit` contract**

```powershell
node --test tests/battle-state.test.mjs --test-name-pattern "movement link"
node --test tests/server.test.mjs --test-name-pattern "solo movement endpoint"
```

- [x] **Step 3: Add strict parsing, defaulting, and allowlist metadata**

```js
const unit = url.searchParams.get("unit") ?? "hand_cannoneer";
const query = new URLSearchParams({ unit, navigation }).toString();
```

- [x] **Step 4: Re-run the focused tests until the contract is green**

```powershell
node --test tests/battle-state.test.mjs --test-name-pattern "movement link"
```

### Task 2: Mechanics-Derived Ranged Timing

**Files:**
- Create: `aoe2x/js_simulation/src/combat/kite-timing.js`
- Create: `aoe2x/js_simulation/tests/kite-timing.test.mjs`
- Modify: `aoe2x/js_simulation/src/fight.js`

**Interfaces:**
- Consumes: mechanics fields `reload_seconds` and `attack_delay_seconds`, plus named opening/formation policy.
- Produces: `deriveKiteProfile(mechanics, policy)` with `beatTicks`, `firstBeatTick`, `moveOffsetTicks`, `topupOffsetTicks`, and `preMoveTicks`.

- [x] **Step 1: Write failing literal tests for all four accepted tape profiles and a synthetic new unit**

```js
assert.deepEqual(deriveKiteProfile(arbalester, {}), {
  beatTicks: 120, firstBeatTick: 120, moveOffsetTicks: [40],
  topupOffsetTicks: [], preMoveTicks: [80],
});
```

- [x] **Step 2: Run the timing test and confirm it fails because the derivation module does not exist**

```powershell
node --test tests/kite-timing.test.mjs
```

- [x] **Step 3: Implement reload-grid and post-release phase derivation**

```js
const beatTicks = Math.ceil(reloadTicks / 40) * 40;
const firstMoveOffset = Math.ceil(attackDelayTicks / 40) * 40;
```

- [x] **Step 4: Use the derived result on the fight request path and prove existing move-order ticks do not change**

```powershell
node --test tests/kite-timing.test.mjs tests/kite-profiles.test.mjs
```

### Task 3: Generic Engine Runner and Collision-Aware Formation

**Files:**
- Modify: `aoe2x/js_simulation/src/fight.js`
- Modify: `aoe2x/js_simulation/src/combat/solo-navigation.js`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

**Interfaces:**
- Consumes: selected registry slug, mechanics fixture, and existing `KITE_PROFILES`.
- Produces: `runSoloRangedMovement(root, { map, navigation, unitSlug })` and collision-aware destinations.

- [x] **Step 1: Add failing tests for all five mechanics rows and actual-radius obstacle clearance**

```js
for (const slug of soloSlugs) {
  const run = await (await fetch(`${baseUrl}/api/solo-hand-cannoneers?unit=${slug}`)).json();
  assert.equal(run.side2.slug, slug);
  assert.equal(Object.keys(run.unitIndex).length, 21);
}
```

- [x] **Step 2: Run the engine/server tests and confirm non-Hand-Cannoneer requests fail**

```powershell
node --test tests/server.test.mjs --test-name-pattern "selectable ranged units"
```

- [x] **Step 3: Generalize the runner and compute slot/envelope geometry from body radius**

```js
const spacing = 0.48; // formation movers may compress through allies
const clearance = maximumSlotExtent + maximumCollisionRadius;
const leash = Math.max(0.62, 2 * maximumCollisionRadius);
```

- [x] **Step 4: Re-run the selected-unit and obstacle tests until green**

```powershell
node --test tests/server.test.mjs --test-name-pattern "selectable ranged units|cohesive solo navigation"
```

### Task 4: Viewer Selector and Deep Links

**Files:**
- Modify: `aoe2x/js_simulation/viewer/index.html`
- Modify: `aoe2x/js_simulation/viewer/app.js`
- Modify: `aoe2x/js_simulation/viewer/styles.css`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

**Interfaces:**
- Consumes: `/api/units.soloMovementSlugs` and parsed `soloRequest.unit`.
- Produces: `#soloMovementUnit`, dynamic unit copy, and URL-preserving selector changes.

- [x] **Step 1: Add a failing shell test for the selector and unit-aware URL update**

```js
assert.match(pageBody, /id="soloMovementUnit"/);
assert.match(appBody, /searchParams\.set\("unit"/);
```

- [x] **Step 2: Run the shell test and verify it fails because the selector is absent**

```powershell
node --test tests/server.test.mjs --test-name-pattern "viewer page exposes"
```

- [x] **Step 3: Render the registry-backed selector and selected-unit labels**

```js
for (const slug of units.soloMovementSlugs) {
  unitSelect.append(new Option(unitsBySlug.get(slug).label, slug));
}
```

- [x] **Step 4: Re-run viewer and browser-state tests**

```powershell
node --test tests/battle-state.test.mjs tests/server.test.mjs --test-name-pattern "movement link|viewer page exposes|solo movement endpoint"
```

### Task 5: Documentation and Verification

**Files:**
- Modify: `aoe2x/js_simulation/docs/HAND_CANNONEER_SOLO_NAVIGATION_2026-08-11.md`
- Modify: `aoe2x/js_simulation/README.md`

**Interfaces:**
- Consumes: verified URL contract and test results.
- Produces: exact local/Tailnet deep links and a documented Scorpion limitation.

- [x] **Step 1: Run syntax and focused automated verification**

```powershell
node --check src/fight.js
node --check src/combat/solo-navigation.js
node --check viewer/battle-state.js
node --check viewer/app.js
node --check server.mjs
node --test tests/battle-state.test.mjs tests/server.test.mjs --test-name-pattern "movement link|selectable ranged units|cohesive solo navigation|viewer page exposes"
```

- [x] **Step 2: Verify the local and Tailnet pages interactively**

```text
/?mode=hand-cannoneer-solo-movement&unit=heavy_cav_archer&navigation=cohesive
```

- [x] **Step 3: Record the five selections, semantics, and verified links in the existing navigation docs**

- [x] **Step 4: Review the final diff without staging unrelated working-tree changes**

```powershell
git diff -- aoe2x/js_simulation/src/fight.js aoe2x/js_simulation/src/combat/solo-navigation.js aoe2x/js_simulation/server.mjs aoe2x/js_simulation/viewer aoe2x/js_simulation/tests/battle-state.test.mjs aoe2x/js_simulation/tests/server.test.mjs aoe2x/js_simulation/README.md aoe2x/js_simulation/docs/HAND_CANNONEER_SOLO_NAVIGATION_2026-08-11.md docs/superpowers
```
