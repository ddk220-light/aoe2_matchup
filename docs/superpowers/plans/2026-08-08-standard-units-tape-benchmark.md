# Standard-Units Tape Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild an auditable 101-row truth fixture from the verified standard-units `frames.bin` archive, run the approved 5-sample/100-sample engine comparison, and publish a reproducible local report.

**Architecture:** A dependency-free Python importer validates the project-local archive, derives immutable row/run evidence from its summary and unit streams, and writes a generated fixture below `aoe2x/js_simulation/calibration/`. A JavaScript comparison module consumes that fixture with the existing combat world, reports tape-conditioned and product-path results separately, and never alters combat mechanics.

**Tech Stack:** Python 3 standard library (`zipfile`, `gzip`, `hashlib`, `json`); Node ESM; `node:test`; existing JavaScript combat engine.

## Global Constraints

- The only tape source is `aoe2x/js_simulation/calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip` with SHA-256 `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`.
- Import must reject a different path, filename, archive hash, missing `frames.bin`, missing summary, missing units stream, or a non-101-row/339-recording corpus.
- Derived fixtures and reports live only below `aoe2x/js_simulation/calibration/`; no fixture is hand-edited to improve a simulation result.
- The baseline benchmark runs five deterministic acquisition-order samples per row; the ten rows whose tape outcomes flip winner are expanded to 100 total samples.
- Product-path controls run normal input, identical repeat, and reversed dropdown input for every row.
- Preserve existing user changes, do not deploy, do not push, and do not mutate production data.

---

### Task 1: Import and validate standard-units truth

**Files:**
- Create: `aoe2x/js_simulation/tools/import_standard_units.py`
- Create: `tests/test_standard_units_import.py`
- Create: `aoe2x/js_simulation/calibration/fixtures/standard_units/standard_units_truth.json` (generated)

**Interfaces:**
- Produces `import_archive(archive: Path) -> dict`.
- Produces `write_truth_fixture(archive: Path, output: Path) -> dict`.
- The fixture has `schema_version`, archive provenance, `rows`, and per-row `runs` with `starting_units`, source-member paths, winner, score, and timeout status.

- [ ] **Step 1: Write the failing importer tests**

```python
def test_import_requires_the_manifested_project_local_archive():
    with pytest.raises(ValueError, match="project-local authorized source"):
        import_archive(tmp_path / "replacement.zip")


def test_import_rebuilds_the_complete_standard_corpus():
    truth = import_archive(AUTHORIZED_ARCHIVE)
    assert truth["zip_sha256"] == REQUIRED_SHA256
    assert len(truth["rows"]) == 101
    assert sum(len(row["runs"]) for row in truth["rows"]) == 339
    assert sum(run["status"] == "timeout" for row in truth["rows"] for run in row["runs"]) == 1
```

- [ ] **Step 2: Run the importer test to verify it fails**

Run: `python -m pytest tests/test_standard_units_import.py -q`

Expected: FAIL because `import_standard_units` does not exist.

- [ ] **Step 3: Implement the minimal archive importer**

```python
def import_archive(archive: Path) -> dict:
    _verify_authorized_archive(archive)
    with ZipFile(archive) as source:
        recordings = _read_complete_recordings(source)
    rows = _group_by_actual_side_masters_and_counts(recordings)
    _validate_corpus(rows)
    return _make_truth_fixture(rows)
```

Each recording must retain the exact `.frames.bin`, `.summary.json`, and `.units.jsonl.gz` member names. Starting units come from the first observed unit sample per id; when a summary omits `hp_start`, its winner starting HP comes from those same first samples, never from mutable engine statistics.

- [ ] **Step 4: Run importer tests to verify they pass and generate the fixture**

Run: `python -m pytest tests/test_standard_units_import.py -q`

Expected: PASS; generated fixture has 101 rows, 339 recordings, one timeout, and the approved archive hash.

- [ ] **Step 5: Commit only this task if a commit is requested**

```bash
git add aoe2x/js_simulation/tools/import_standard_units.py tests/test_standard_units_import.py aoe2x/js_simulation/calibration/fixtures/standard_units/standard_units_truth.json
git commit -m "test: import standard-units tape truth"
```

### Task 2: Add pure comparison and tape-conditioned run support

**Files:**
- Create: `aoe2x/js_simulation/src/standard-units-comparison.js`
- Create: `aoe2x/js_simulation/tests/standard-units-comparison.test.mjs`

**Interfaces:**
- `signedScore({ winnerOwner, winnerHp, startingHpByOwner }) -> number | null`
- `summarizeTape(row) -> { mean, min, max, side3WinRate, scoredRuns, timeoutRuns, volatile }`
- `compareRow({ row, simulationScores }) -> { mean, bandError, wrongStableWinner, side3WinRateError }`
- `runTapeConditioned(root, row, sampleIndex, seed) -> { winnerOwner, winnerHp, score, ticks, diagnostics }`

- [ ] **Step 1: Write the failing scoring and determinism tests**

```javascript
test("band error is zero inside the observed tape range", () => {
  assert.equal(compareRow({ row: tapeRow(-20, -10), simulationScores: [-15] }).bandError, 0);
});

test("a stable tape winner is marked wrong only when the simulated sign differs", () => {
  assert.equal(compareRow({ row: tapeRow(-20, -10), simulationScores: [12] }).wrongStableWinner, true);
});

test("sample zero preserves roster order and repeated seeded runs hash identically", async () => {
  assert.deepEqual(await runTapeConditioned(ROOT, row, 0, SEED), await runTapeConditioned(ROOT, row, 0, SEED));
});
```

- [ ] **Step 2: Run the focused Node test to verify it fails**

Run: `node --test aoe2x/js_simulation/tests/standard-units-comparison.test.mjs`

Expected: FAIL because `standard-units-comparison.js` does not exist.

- [ ] **Step 3: Implement the comparison module**

```javascript
export function signedScore({ winnerOwner, winnerHp, startingHpByOwner }) {
  if (winnerOwner === null) return null;
  const magnitude = 100 * winnerHp / startingHpByOwner[winnerOwner];
  return winnerOwner === 2 ? -magnitude : magnitude;
}

export function bandDistance(value, min, max) {
  return value < min ? min - value : value > max ? value - max : 0;
}
```

The run helper must use each row’s tape-derived canonical start, a fixed `20260411` shuffle generator, `sampleIndex === 0` as identity order, `MAX_TICKS = 9000`, current `KITE_PROFILES` for a mobile-ranged versus non-mobile-ranged row, and the existing `createWorld`/`runWorld` engine. It must not alter unit HP, damage, speed, placement, or outcomes.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `node --test aoe2x/js_simulation/tests/standard-units-comparison.test.mjs`

Expected: PASS; invalid signs, timeout scores, seed repeatability, and tape-band math are covered.

- [ ] **Step 5: Commit only this task if a commit is requested**

```bash
git add aoe2x/js_simulation/src/standard-units-comparison.js aoe2x/js_simulation/tests/standard-units-comparison.test.mjs
git commit -m "feat: compare standard-unit tape runs"
```

### Task 3: Add reproducible suite runners and report rendering

**Files:**
- Create: `aoe2x/js_simulation/tools/run_standard_units_suite.mjs`
- Create: `aoe2x/js_simulation/tools/run_standard_units_product_suite.mjs`
- Create: `aoe2x/js_simulation/tests/standard-units-runners.test.mjs`

**Interfaces:**
- `runStandardUnitsSuite({ root, samples, volatileSamples, seed }) -> report`
- `runStandardUnitsProductSuite({ root }) -> report`
- `renderStandardUnitsMarkdown(report) -> string`
- `writeStandardUnitsReport({ report, outputJson, outputMarkdown }) -> Promise<void>`

- [ ] **Step 1: Write the failing runner/report tests**

```javascript
test("the run schedule is five samples for every row and 100 total for volatile rows", () => {
  assert.equal(runSchedule({ rows: [stableRow, volatileRow], samples: 5, volatileSamples: 100 }).length, 105);
});

test("product controls contain normal, repeat, and reversed input for every row", async () => {
  const report = await runStandardUnitsProductSuite({ root: ROOT, rows: [fixtureRow] });
  assert.deepEqual(report.rows[0].controls.map(({ name }) => name), ["normal", "repeat", "reversed"]);
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `node --test aoe2x/js_simulation/tests/standard-units-runners.test.mjs`

Expected: FAIL because the runners do not exist.

- [ ] **Step 3: Implement local-only runners**

```javascript
const report = await runStandardUnitsSuite({
  root,
  samples: 5,
  volatileSamples: 100,
  seed: 20260411,
});
await writeStandardUnitsReport({
  report,
  outputJson: new URL("../calibration/reports/standard_units_simulation_results_2026-08-08.json", import.meta.url),
  outputMarkdown: new URL("../calibration/reports/standard_units_simulation_results_2026-08-08.md", import.meta.url),
});
```

The tape-conditioned report must preserve per-sample results and aggregate wrong stable winners, band error, tape-band coverage, winner-probability error, unresolved runs, and category breakdowns. The product report must mark itself `generated_placement_product_path`, preserve normal/repeat/reversed hashes, and never be merged into the tape-conditioned KPIs.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `node --test aoe2x/js_simulation/tests/standard-units-runners.test.mjs`

Expected: PASS; schedule is 1,455 tape-conditioned runs and 303 product controls for the 101-row fixture.

- [ ] **Step 5: Commit only this task if a commit is requested**

```bash
git add aoe2x/js_simulation/tools/run_standard_units_suite.mjs aoe2x/js_simulation/tools/run_standard_units_product_suite.mjs aoe2x/js_simulation/tests/standard-units-runners.test.mjs
git commit -m "feat: run standard-units benchmark suite"
```

### Task 4: Execute, verify, and publish the local comparison

**Files:**
- Create: `aoe2x/js_simulation/calibration/reports/standard_units_simulation_results_2026-08-08.json`
- Create: `aoe2x/js_simulation/calibration/reports/standard_units_simulation_results_2026-08-08.md`
- Create: `aoe2x/js_simulation/calibration/reports/standard_units_product_results_2026-08-08.json`
- Create: `aoe2x/js_simulation/calibration/reports/standard_units_product_results_2026-08-08.md`

- [ ] **Step 1: Reverify the archive before executing the suite**

Run: `Get-FileHash -LiteralPath 'D:\AI\aoe2_matchup\aoe2x\js_simulation\calibration\source\aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip' -Algorithm SHA256`

Expected: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`.

- [ ] **Step 2: Generate the fresh truth fixture**

Run: `python aoe2x/js_simulation/tools/import_standard_units.py`

Expected: the importer reports 101 rows, 339 recordings, 338 scored recordings, and one timeout.

- [ ] **Step 3: Run the two approved benchmark lanes**

Run: `node aoe2x/js_simulation/tools/run_standard_units_suite.mjs --samples 5 --volatile-samples 100 --seed 20260411`

Run: `node aoe2x/js_simulation/tools/run_standard_units_product_suite.mjs`

Expected: tape-conditioned schedule is 1,455 runs; product schedule is 303 controls.

- [ ] **Step 4: Run the focused and complete regression suites**

Run: `node --test aoe2x/js_simulation/tests/standard-units-comparison.test.mjs aoe2x/js_simulation/tests/standard-units-runners.test.mjs`

Run: `npm test --prefix aoe2x/js_simulation`

Expected: all selected and project tests pass.

- [ ] **Step 5: Inspect results against acceptance criteria and report exact evidence**

The final chat result must distinguish tape-conditioned from product-path results; list all wrong stable winners, all product determinism failures, all unresolved simulations, and the ten volatile rows. It must not claim the engine is optimized or correct without the fresh report values.

## Self-Review

- Source provenance, archive hash, 101-row grouping, 339 recordings, one timeout, deterministic sampling, volatility expansion, product controls, and local-only output are covered by Tasks 1-4.
- No tape-derived fixture is manually edited, and no task changes combat mechanics.
- The imported `starting_hp_by_owner` is tape-derived, preventing later mechanics changes from altering the truth denominator.
- The runner schedule is exact: `91 * 5 + 10 * 100 = 1,455` tape-conditioned runs and `101 * 3 = 303` product controls.

## Execution Handoff

The user approved inline execution in this session. Execute Tasks 1-4 in order with the red-green checks above.
