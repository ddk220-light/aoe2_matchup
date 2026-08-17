# Unique-Unit Batch 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first twenty fully upgraded unique-unit families to the clean-room JavaScript simulator and viewer, then compare only the exact matchups found in the authorized unique-unit golden archive.

**Architecture:** Extend the existing data exporter and immutable registry rather than adding hand-authored combat objects. Generic combat families continue to drive navigation; new conditional damage behavior is represented as sourced fixture data and applied in the shared damage pipeline. Tape intake and comparison remain isolated under `calibration/` and use the existing recoverable benchmark framework.

**Tech Stack:** Node.js ES modules and `node:test`, Python fixture exporters, SQLite reference data, Genie `.dat` extraction, JSON mechanics fixtures, HTML/Canvas viewer.

**Spec:** `aoe2x/js_simulation/docs/superpowers/specs/2026-08-17-unique-unit-expansion-design.md`

## Global Constraints

- Use build 177723 source data.
- Do not read an unmanifested archive as evidence.
- Do not use old calibration output as tape truth.
- Do not add opponent-specific rules or fitted random variation.
- Write and observe a failing test before each production-code change.
- Preserve all existing untracked report artifacts.
- Stop after Batch 1 is implemented, tested, compared, and reported.

---

### Task 1: Intake the unique-unit golden archive

**Files:**
- Create: `aoe2x/js_simulation/calibration/source/<authorized-unique-archive>.zip`
- Modify: `aoe2x/js_simulation/calibration/source/manifest.json`
- Create: `aoe2x/js_simulation/calibration/fixtures/unique_units_batch_1/tape_inventory.json`
- Test: `aoe2x/js_simulation/tests/unique-units-golden-corpus.test.mjs`

**Interfaces:**
- Consumes: user-designated external archive path.
- Produces: one `zip_sha256` manifest entry and a deterministic inventory of tape rows, repeats, unit slugs, civilizations, counts, modes, and source filenames.

- [ ] **Step 1: Hash the external archive and display its exact filename, size, and SHA-256 without copying it.**
- [ ] **Step 2: Confirm that the selected file is the user-designated unique-unit archive; do not substitute a similarly named ZIP.**
- [ ] **Step 3: Copy the archive byte-for-byte into `calibration/source/` and verify the copied SHA-256 equals the external hash.**
- [ ] **Step 4: Write a failing corpus test that expects the new manifest entry and rejects any inventory row whose `zip_sha256` differs.**
- [ ] **Step 5: Run `node --test tests/unique-units-golden-corpus.test.mjs` and confirm the failure is the absent manifest entry.**
- [ ] **Step 6: Add the manifest entry and inventory extractor output, recording every Batch 1 tape row and exact repeat.**
- [ ] **Step 7: Re-run the corpus test and confirm it passes.**
- [ ] **Step 8: Commit only the manifest, inventory, test, and authorized source archive.**

### Task 2: Generalize the fixture exporter for Batch 1 mechanics

**Files:**
- Modify: `aoe2x/js_simulation/tools/export_unit_mechanics.py`
- Create: `aoe2x/js_simulation/tests/unique-unit-fixtures.test.mjs`
- Create: `aoe2x/js_simulation/fixtures/unit_stats/<batch-1-unit>.json` for twenty units

**Interfaces:**
- Consumes: `unit_slug`, civilization, Genie master ID, build-177723 reference DB, and matching `.dat`.
- Produces: mechanics JSON containing attacks, armors, exact speed, range, reload, animation-derived attack delay, accuracy, projectile data, collision geometry, and conditional damage modifiers.

- [ ] **Step 1: Write fixture-contract tests for the twenty expected slugs, civilizations, and master IDs.**
- [ ] **Step 2: Add assertions for ranged melee-class projectiles, low gunpowder accuracy, Warrior Priest combat-only output, and Shotel mounted-attacker reduction.**
- [ ] **Step 3: Run the fixture test and confirm it fails because the fixtures and conditional modifier are absent.**
- [ ] **Step 4: Extend the exporter with a `damage_reduction_by_attacker_category` object sourced from the build data/config technology chain.**
- [ ] **Step 5: Regenerate all twenty fixtures without manually editing generated JSON.**
- [ ] **Step 6: Re-run the fixture test and confirm all source and mechanics assertions pass.**
- [ ] **Step 7: Commit the exporter, tests, and generated fixtures.**

### Task 3: Register the twenty units and classify their control behavior

**Files:**
- Modify: `aoe2x/js_simulation/src/unit-registry.js`
- Modify: `aoe2x/js_simulation/tests/unit-registry.test.mjs`
- Modify: `aoe2x/js_simulation/src/kite-profiles.js` only if the existing derived controller requires explicit generated rows
- Modify: `aoe2x/js_simulation/tests/kite-profiles.test.mjs`

**Interfaces:**
- Consumes: Batch 1 mechanics fixtures.
- Produces: registry lookup rows and behavior classes used by placement, targeting, kiting, purchase, server APIs, and the viewer.

- [ ] **Step 1: Change the registry test to expect 34 total rows and the twenty new slugs.**
- [ ] **Step 2: Assert that Longbowman, Throwing Axeman, Gbeto, Genoese Crossbowman, Plumed Archer, Mangudai, Rattan Archer, Janissary, Conquistador, and War Wagon are mobile ranged.**
- [ ] **Step 3: Assert that the remaining Batch 1 units are melee and Warrior Priest has no healing capability field.**
- [ ] **Step 4: Run the registry tests and confirm they fail on the missing rows.**
- [ ] **Step 5: Add the twenty immutable registry rows with sourced base costs and fixture names.**
- [ ] **Step 6: Derive any required kiting-profile entries from reload, attack delay, movement speed, and the shared order quantum; do not hand-calibrate unit clocks.**
- [ ] **Step 7: Run registry and kiting-profile tests and confirm they pass.**
- [ ] **Step 8: Commit the registry and behavior classification.**

### Task 4: Apply Royal Heirs in the shared damage pipeline

**Files:**
- Modify: `aoe2x/js_simulation/src/combat/attacks.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js` if attacker-category state is not already available at damage resolution
- Create: `aoe2x/js_simulation/tests/conditional-damage-reduction.test.mjs`

**Interfaces:**
- Consumes: target fixture `damage_reduction_by_attacker_category` and attacker mechanics category.
- Produces: final damage reduced by three for mounted attackers while leaving infantry and siege attackers unchanged.

- [ ] **Step 1: Write tests showing a Shotel takes three less damage from melee cavalry and cavalry archers but unchanged damage from infantry and foot archers.**
- [ ] **Step 2: Assert minimum-damage and bonus-damage ordering explicitly so the modifier cannot become generic armor.**
- [ ] **Step 3: Run the focused test and confirm the mounted cases fail.**
- [ ] **Step 4: Add a generic conditional incoming-damage modifier in the shared damage calculation.**
- [ ] **Step 5: Re-run the focused test and the existing ranged/melee attack tests.**
- [ ] **Step 6: Commit the conditional damage mechanic.**

### Task 5: Verify Gbeto and ranged-melee projectile kiting

**Files:**
- Create: `aoe2x/js_simulation/tests/unique-unit-kiting.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/world.js` only if generic mobile-ranged classification does not already activate cohesive kiting
- Modify: `aoe2x/js_simulation/src/combat/attacks.js` only if projectile damage incorrectly assumes pierce class

**Interfaces:**
- Consumes: mobile-ranged registry class and fixture attack-class map.
- Produces: ordinary cohesive kiting with independently correct melee or pierce projectile damage.

- [ ] **Step 1: Write a Gbeto test that observes a move-fire cycle and verifies that target melee armor, not pierce armor, mitigates the projectile.**
- [ ] **Step 2: Write a Throwing Axeman test for the same separation of movement family from damage class.**
- [ ] **Step 3: Run the tests and confirm any missing generic behavior fails for the expected reason.**
- [ ] **Step 4: Make the smallest generic change required; do not add Gbeto- or Throwing-Axeman-specific branches.**
- [ ] **Step 5: Re-run the new tests plus `kite-timing`, `kite-orders`, and `ranged-attack`.**
- [ ] **Step 6: Commit the generic ranged-melee support.**

### Task 6: Expose Batch 1 in the viewer

**Files:**
- Regenerate: `aoe2x/js_simulation/fixtures/viewer_unit_catalogue.json` if source catalogue changes are required
- Modify: `aoe2x/js_simulation/viewer/app.js` only if a generic catalogue assumption blocks unique rows
- Modify: `aoe2x/js_simulation/tests/viewer-selection.test.mjs`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`

**Interfaces:**
- Consumes: unit registry and viewer catalogue.
- Produces: enabled civilization/unit choices, manual counts, equal-resource setup, deterministic seeds, telemetry, and deep-link query parameters.

- [ ] **Step 1: Write viewer/server tests that expect every Batch 1 row to be enabled and preserve all untested units as visible-but-disabled.**
- [ ] **Step 2: Run the tests and confirm they fail because Batch 1 is not exposed.**
- [ ] **Step 3: Update only the generic catalogue/selection path necessary to expose registry-backed unique rows.**
- [ ] **Step 4: Re-run viewer, server, and viewer-simulation tests.**
- [ ] **Step 5: Commit the viewer exposure.**

### Task 7: Run regression and golden comparison gates

**Files:**
- Create: `aoe2x/js_simulation/calibration/reports/unique_units_batch_1_<date>/progress.json`
- Create: `aoe2x/js_simulation/calibration/reports/unique_units_batch_1_<date>/results.jsonl`
- Create: `aoe2x/js_simulation/calibration/reports/unique_units_batch_1_<date>/report.html`
- Create: `aoe2x/js_simulation/calibration/reports/unique_units_batch_1_<date>/README.md`

**Interfaces:**
- Consumes: exact tape inventory, Batch 1 engine, five samples per row, standard-unit regression suite.
- Produces: resumable result records and a human-readable comparison report.

- [ ] **Step 1: Run `node --test tests` and record the exact pass/fail counts.**
- [ ] **Step 2: Run the existing standard-unit comparison gate and verify no unexplained winner regression.**
- [ ] **Step 3: Launch the recoverable unique Batch 1 runner with bounded parallel workers and immediate per-scenario persistence.**
- [ ] **Step 4: Resume from `progress.json` if interrupted; never repeat a completed scenario.**
- [ ] **Step 5: Run five samples for every golden row and expand only volatile rows, up to 100.**
- [ ] **Step 6: Generate the report with tape winner, simulation winner, signed winner-HP percentages, delta, wrong-winner flag, convergence, and failures.**
- [ ] **Step 7: Verify direct local and Tailnet viewer links for representative Batch 1 matchups.**
- [ ] **Step 8: Commit code, fixtures, tests, documentation, and compact report metadata; exclude bulky transient worker output unless the existing report policy requires it.**
- [ ] **Step 9: Stop and present Batch 1 for user review before starting Batch 2.**

