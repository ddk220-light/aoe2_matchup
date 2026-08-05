# Clean-room Champion Small Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic 60-Hz tick simulator that reproduces the authorized Chinese Champion-versus-Champion 1v1, 2v1, 2v3, 5v3, and 6v3 recordings through general targeting, movement, collision, attack, death, and retargeting mechanics.

**Architecture:** Verify and convert the sole tape archive into immutable truth fixtures, export Champion mechanics with field-level provenance, and run all combat through a frozen-snapshot tick pipeline. Each ratio is an acceptance gate that extends one shared engine; no ratio receives a special parameter, and this milestone contains no randomness.

**Tech Stack:** Python standard library plus the project's existing `genieutils-py` extraction dependency for tape and game-data fixtures; Node.js ES modules and `node:test` for the headless simulator, comparisons, server, and viewer.

## Global Constraints

- The only permitted tape is `aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`.
- Its required SHA-256 is `33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`.
- Every active clean-room manifest row must contain that exact `zip_sha256`.
- Never read a legacy tape, tape-derived fixture, calibration report, or old simulation parameter.
- Preserve the locked map and formation source hash `f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4`.
- Scenario coordinates and reference IDs come from the locked formation; all combatants are replaced with Chinese Imperial Champion master `567`.
- Use integer simulation ticks with `TICKS_PER_SECOND = 60`; treat 60 Hz as a documented, revisable engine hypothesis rather than a published AoE2:DE fact.
- Browser refresh rate, Node timers, recorder sampling rate, and tape wall-clock duration never advance simulation physics.
- Do not add an RNG module, seed field, randomized delay, randomized event ordering, or probability target in this milestone.
- Ready events are ordered by ready tick, actor reference ID, target reference ID, and event type.
- Do not add tuned reaction delays, pauses, steering weights, collision multipliers, compression ratios, clockwise rules, winner biases, or ratio-specific branches.
- Missing game-data mechanics are errors. Do not replace missing fields with defaults copied from legacy code.
- Strict outcome targets are medians from the three authorized repeats; tape timing and trajectories remain diagnostic evidence.
- Stop a fight after 3,600 ticks as an explicit failure, never as a draw or simulated result.

---

## Evidence and required outcomes

| Ratio | Repeats | Required winner | Strict median winner HP | Observed survivor count | Observed damage-event count |
| --- | ---: | --- | ---: | --- | --- |
| 1v1 | 3 | either owner | 14/70 = 20% | 1 | 9 |
| 2v1 | 3 | side2 | 112/140 = 80% | 2 | 7-8 |
| 2v3 | 3 | side3 | 126/210 = 60% | 2 | 16 |
| 5v3 | 3 | side2 | 252/350 = 72% | 4-5 | 22-25 |
| 6v3 | 3 | side2 | 336/420 = 80% | 5-6 | 21-23 |

The plan advances in that order. Every completed stage reruns all earlier
stages. If an outcome misses, inspect the earliest divergent target, movement,
contact, or attack event. Do not repair an outcome with a new free parameter.

## Planned file structure

| File | Responsibility |
| --- | --- |
| `aoe2x/js_simulation/calibration/source/source_of_truth.json` | Sole archive identity and expected inventory |
| `aoe2x/js_simulation/calibration/fixtures/manifest.json` | Fifteen run records tied to the archive hash |
| `aoe2x/js_simulation/calibration/fixtures/champion_basics.json` | All five ratios, exact starts, outcomes, samples, and damage events |
| `aoe2x/js_simulation/calibration/reports/champion_clock_forensics.json` | Recorder and event-quantization diagnostics |
| `aoe2x/js_simulation/tools/import_champion_basics.py` | Reproducible archive verifier and fixture generator |
| `aoe2x/js_simulation/tools/analyze_champion_clock.py` | Read-only clock evidence analysis |
| `aoe2x/js_simulation/tools/export_champion_mechanics.py` | Reference DB plus installed Genie `.dat` exporter |
| `aoe2x/js_simulation/fixtures/unit_stats/champion_chinese_imperial.json` | Clean-room mechanics and field provenance |
| `aoe2x/js_simulation/src/simulation-clock.js` | Integer tick conversions and constants |
| `aoe2x/js_simulation/src/champion-scenarios.js` | Build each ratio from locked coordinates and Champion mechanics |
| `aoe2x/js_simulation/src/combat/unit-state.js` | Immutable unit-state construction and validation |
| `aoe2x/js_simulation/src/combat/targeting.js` | Candidate filtering, ranking, locking, and invalidation |
| `aoe2x/js_simulation/src/combat/movement.js` | Desired pursuit displacement |
| `aoe2x/js_simulation/src/combat/collision.js` | Symmetric dynamic and static contact resolution |
| `aoe2x/js_simulation/src/combat/attacks.js` | Reach, windup, reload, damage, death, and cancellation |
| `aoe2x/js_simulation/src/combat/world.js` | Eight-phase tick pipeline and event publication |
| `aoe2x/js_simulation/src/champion-comparison.js` | Strict gates and diagnostic comparisons for all ratios |
| `aoe2x/js_simulation/tools/run_champion_suite.mjs` | Headless runner and JSON/Markdown report writer |
| Existing viewer and server files | Ratio selection, tick controls, overlays, and fixture endpoints |

### Task 1: Lock and ingest all fifteen authorized recordings

**Files:**
- Create: `aoe2x/js_simulation/calibration/source/source_of_truth.json`
- Create: `aoe2x/js_simulation/calibration/fixtures/manifest.json`
- Create: `aoe2x/js_simulation/calibration/fixtures/champion_basics.json`
- Create: `aoe2x/js_simulation/tools/import_champion_basics.py`
- Create: `tests/test_cleanroom_champion_basics.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the authorized project-local archive.
- Produces: `import_archive(archive: Path) -> tuple[dict, dict]`, returning the manifest and complete Champion truth fixture.

- [ ] **Step 1: Write the failing source-authority test**

```python
def test_source_authority_names_only_the_champion_basics_archive():
    authority = json.loads(SOURCE_OF_TRUTH.read_text(encoding="utf-8"))
    assert authority == {
        "archive": "aoe2_golden_basics_championvschampion_2026-08-04.zip",
        "sha256": "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE",
        "recordings": 15,
        "ratios": {"1v1": 3, "2v1": 3, "2v3": 3, "5v3": 3, "6v3": 3},
    }
```

- [ ] **Step 2: Run the source test and verify it fails because the authority file does not exist**

Run: `python -m pytest tests/test_cleanroom_champion_basics.py::test_source_authority_names_only_the_champion_basics_archive -q -p no:cacheprovider`

- [ ] **Step 3: Write failing inventory and reproducibility tests**

```python
def test_importer_finds_three_repeats_for_every_ratio():
    manifest, truth = import_archive(ARCHIVE)
    assert len(manifest["runs"]) == 15
    assert {key: len(value["runs"]) for key, value in truth["ratios"].items()} == {
        "1v1": 3, "2v1": 3, "2v3": 3, "5v3": 3, "6v3": 3,
    }
    assert all(row["zip_sha256"] == REQUIRED_SHA for row in manifest["runs"])

def test_generated_fixture_matches_checked_in_fixture():
    _, regenerated = import_archive(ARCHIVE)
    checked_in = json.loads(TRUTH_FIXTURE.read_text(encoding="utf-8"))
    assert regenerated == checked_in
```

- [ ] **Step 4: Implement archive verification before member reads**

`import_archive` must hash the archive, reject a mismatch, require exactly the
five ratios and three tags per ratio, and require each run's summary, metadata,
unit samples, damage events, missile events, and command stream.

- [ ] **Step 5: Generate the complete truth fixture**

For each run store composition, exact reference IDs and start coordinates,
ordered unit samples, ordered damage events, winner, aggregate starting and
remaining HP, survivor count, first damage, final kill, and source member names.
Do not extract or track raw video, `frames.bin`, or `reseed.bin`.

- [ ] **Step 6: Add outcome assertions for all five ratios**

```python
def test_authorized_ratio_medians_are_locked():
    truth = json.loads(TRUTH_FIXTURE.read_text(encoding="utf-8"))
    assert {ratio: row["median_winner_hp_pct"] for ratio, row in truth["ratios"].items()} == {
        "1v1": 20.0, "2v1": 80.0, "2v3": 60.0, "5v3": 72.0, "6v3": 80.0,
    }
```

- [ ] **Step 7: Ignore only large source and regenerated raw material**

Add ignore rules for `aoe2x/js_simulation/calibration/source/*.zip` and raw
extraction directories. Keep authority, manifest, truth, and report JSON files
tracked.

- [ ] **Step 8: Run the complete importer tests**

Run: `python -m pytest tests/test_cleanroom_champion_basics.py -q -p no:cacheprovider`

Expected: all pass, exactly 15 manifest rows, and no archive other than the
authorized hash is referenced.

- [ ] **Step 9: Commit the source boundary**

```powershell
git add .gitignore aoe2x/js_simulation/calibration/source/source_of_truth.json aoe2x/js_simulation/calibration/fixtures aoe2x/js_simulation/tools/import_champion_basics.py tests/test_cleanroom_champion_basics.py
git commit -m "test(sim): lock champion basics truth corpus"
```

### Task 2: Record clock evidence and add the integer simulation clock

**Files:**
- Create: `aoe2x/js_simulation/tools/analyze_champion_clock.py`
- Create: `aoe2x/js_simulation/calibration/reports/champion_clock_forensics.json`
- Create: `aoe2x/js_simulation/src/simulation-clock.js`
- Create: `aoe2x/js_simulation/tests/simulation-clock.test.mjs`
- Create: `tests/test_cleanroom_champion_clock.py`

**Interfaces:**
- Consumes: `champion_basics.json`.
- Produces: `analyze_clock(truth: dict) -> dict`, `TICKS_PER_SECOND`, `secondsToTicksCeil(seconds)`, and `ticksToSeconds(ticks)`.

- [ ] **Step 1: Write a failing forensics test**

```python
def test_clock_report_separates_recorder_rate_from_engine_hypothesis():
    report = analyze_clock(load_truth())
    assert report["recorder_stream_hz"] == [59.4]
    assert report["position_sample_hz"] == [10.0]
    assert report["engine_hypothesis_hz"] == 60
    assert report["claim"] == "provisional_not_published"
    assert report["same_attacker_intervals_s"]["count"] > 0
```

- [ ] **Step 2: Implement the read-only clock analysis**

Compute same-attacker damage intervals, equal-timestamp attack counts, observed
recorder rates, and residuals from mapping intervals to 50-Hz and 60-Hz ticks.
The report must preserve both candidates and must not select a rate from final
HP accuracy.

- [ ] **Step 3: Generate and verify the tracked clock report**

Run: `python aoe2x/js_simulation/tools/analyze_champion_clock.py --truth aoe2x/js_simulation/calibration/fixtures/champion_basics.json --output aoe2x/js_simulation/calibration/reports/champion_clock_forensics.json`

Run: `python -m pytest tests/test_cleanroom_champion_clock.py -q -p no:cacheprovider`

- [ ] **Step 4: Write failing integer-clock tests**

```javascript
test("the clean-room clock is an explicit 60 Hz hypothesis", () => {
  assert.equal(TICKS_PER_SECOND, 60);
  assert.equal(secondsToTicksCeil(2), 120);
  assert.equal(ticksToSeconds(120), 2);
});

test("fractional readiness always advances to a real tick", () => {
  assert.equal(secondsToTicksCeil(0.001), 1);
  assert.equal(secondsToTicksCeil(2.001), 121);
});
```

- [ ] **Step 5: Implement pure clock conversions**

Validate finite, nonnegative inputs. Keep ticks as integers and expose no
wall-clock or timer APIs.

- [ ] **Step 6: Run clock tests and commit**

Run: `node --test aoe2x/js_simulation/tests/simulation-clock.test.mjs`

```powershell
git add aoe2x/js_simulation/tools/analyze_champion_clock.py aoe2x/js_simulation/calibration/reports/champion_clock_forensics.json aoe2x/js_simulation/src/simulation-clock.js aoe2x/js_simulation/tests/simulation-clock.test.mjs tests/test_cleanroom_champion_clock.py
git commit -m "feat(sim): add champion clock evidence and integer ticks"
```

### Task 3: Export a clean-room Chinese Champion mechanics fixture

**Files:**
- Create: `aoe2x/js_simulation/tools/export_champion_mechanics.py`
- Create: `aoe2x/js_simulation/fixtures/unit_stats/champion_chinese_imperial.json`
- Create: `tests/test_cleanroom_champion_mechanics.py`

**Interfaces:**
- Consumes: read-only `data/golden/aoe2_reference.db` and an explicit installed AoE2:DE Genie `.dat` path supplied with `--dat`.
- Produces: `export_champion_mechanics(reference_db: Path, dat_path: Path) -> dict`.

- [ ] **Step 1: Write a failing mechanics-value test**

```python
def test_chinese_champion_core_mechanics_are_source_backed():
    fixture = load_fixture()
    assert fixture["unit_master"] == 567
    assert fixture["civilization"] == "Chinese"
    assert fixture["hp"] == 70
    assert fixture["speed_tiles_per_second"] == 1.06
    assert fixture["attack_range_tiles"] == 0.0
    assert fixture["reload_seconds"] == 2.0
    assert fixture["attack_delay_seconds"] == 0.0
    assert fixture["line_of_sight_tiles"] == 5.0
    assert fixture["outline_size_tiles"]["x"] == 0.2
    assert fixture["derived"]["damage_vs_self"] == 14
```

- [ ] **Step 2: Write a failing raw-Genie provenance test**

```python
def test_collision_fields_have_raw_dat_provenance():
    fixture = load_fixture()
    assert fixture["collision_size_tiles"]["x"] > 0
    assert fixture["clearance_size_tiles"]
    assert fixture["obstruction"]["type"] is not None
    assert fixture["provenance"]["reference_db_sha256"]
    assert fixture["provenance"]["dat_sha256"]
    assert fixture["provenance"]["fields"]["collision_size_tiles.x"] == "unit.collision_size_x"
```

- [ ] **Step 3: Implement the reference DB read in SQLite read-only mode**

Select the unique Chinese Imperial row with `unit_slug='champion'`. Retain raw
attack and armor class maps, and derive self-damage with the AoE class rule
instead of storing 14 as an override.

- [ ] **Step 4: Implement fresh Genie field extraction**

Parse the supplied `.dat`, select Champion unit `567`, and export collision
size X/Y/Z, clearance size, outline size X/Y/Z, obstruction type/class,
movement-block fields, attack graphic, frame delay, and source hash. Do not
read old collision audit JSON.

- [ ] **Step 5: Generate the fixture and run tests**

Run:

```powershell
python aoe2x/js_simulation/tools/export_champion_mechanics.py --reference-db data/golden/aoe2_reference.db --dat "$env:AOE2_DAT_PATH" --output aoe2x/js_simulation/fixtures/unit_stats/champion_chinese_imperial.json
python -m pytest tests/test_cleanroom_champion_mechanics.py -q -p no:cacheprovider
```

Expected: the command fails clearly when `AOE2_DAT_PATH` is absent or points to
the wrong file; it never falls back to a guessed path or legacy report.

- [ ] **Step 6: Commit the mechanics boundary**

```powershell
git add aoe2x/js_simulation/tools/export_champion_mechanics.py aoe2x/js_simulation/fixtures/unit_stats/champion_chinese_imperial.json tests/test_cleanroom_champion_mechanics.py
git commit -m "feat(sim): export clean-room champion mechanics"
```

### Task 4: Build ratio scenarios from locked placement and Champion mechanics

**Files:**
- Create: `aoe2x/js_simulation/src/champion-scenarios.js`
- Create: `aoe2x/js_simulation/src/combat/unit-state.js`
- Create: `aoe2x/js_simulation/tests/champion-scenarios.test.mjs`

**Interfaces:**
- Consumes: validated formation, truth, and Champion mechanics objects.
- Produces: `createChampionScenario({ ratio, formation, truth, mechanics }) -> { ratio, units, mapHash }` and `createUnitState(input) -> UnitState`.

- [ ] **Step 1: Write failing ratio-count and position tests**

```javascript
for (const [ratio, counts] of Object.entries({
  "1v1": [1, 1], "2v1": [2, 1], "2v3": [2, 3], "5v3": [5, 3], "6v3": [6, 3],
})) {
  test(`${ratio} uses the literal first source records`, () => {
    const scenario = createChampionScenario({ ratio, formation, truth, mechanics });
    assert.equal(scenario.units.filter((unit) => unit.owner === 2).length, counts[0]);
    assert.equal(scenario.units.filter((unit) => unit.owner === 3).length, counts[1]);
    assert.deepEqual(
      scenario.units.map(({ referenceId, x, y }) => [referenceId, x, y]),
      truth.ratios[ratio].canonical_start_positions,
    );
  });
}
```

- [ ] **Step 2: Write a failing type-separation test**

```javascript
test("placement unit types cannot leak into the Champion roster", () => {
  const scenario = createChampionScenario({ ratio: "1v1", formation, truth, mechanics });
  assert.deepEqual(new Set(scenario.units.map((unit) => unit.unitMaster)), new Set([567]));
  assert.deepEqual(new Set(scenario.units.map((unit) => unit.hp)), new Set([70]));
});
```

- [ ] **Step 3: Implement immutable unit-state creation and scenario validation**

Each unit starts alive with the scenario reference ID, owner, literal position
and facing, Champion mechanics reference, `targetId = null`, action `idle`, and
integer action timers. Reject unknown ratios, duplicate references, nonfinite
coordinates, and starting conflicts recorded by the locked formation.

- [ ] **Step 4: Run tests and commit**

Run: `node --test aoe2x/js_simulation/tests/champion-scenarios.test.mjs`

```powershell
git add aoe2x/js_simulation/src/champion-scenarios.js aoe2x/js_simulation/src/combat/unit-state.js aoe2x/js_simulation/tests/champion-scenarios.test.mjs
git commit -m "feat(sim): build champion ratio scenarios"
```

### Task 5: Implement deterministic targeting, pursuit, and physical contact

**Files:**
- Create: `aoe2x/js_simulation/src/combat/targeting.js`
- Create: `aoe2x/js_simulation/src/combat/movement.js`
- Create: `aoe2x/js_simulation/src/combat/collision.js`
- Create: `aoe2x/js_simulation/tests/targeting.test.mjs`
- Create: `aoe2x/js_simulation/tests/movement-collision.test.mjs`

**Interfaces:**
- Produces: `surfaceGap(a, b)`, `selectPursuitTarget(unit, snapshot)`,
  `selectEngagementTarget(unit, snapshot, contacts)`,
  `proposeMovement(unit, target, ticksPerSecond)`,
  `resolveMovementProposals(snapshot, proposals, map)`, and
  `queryEnemyContactManifold(before, after)`.

- [ ] **Step 1: Write failing target-ranking tests**

```javascript
test("a targetless unit chooses the nearest visible enemy by surface gap", () => {
  assert.equal(selectPursuitTarget(attacker, snapshot).referenceId, nearest.referenceId);
});

test("an exact distance tie is broken by reference ID and not owner or array order", () => {
  assert.equal(selectPursuitTarget(attacker, snapshot).referenceId, 1699);
  assert.equal(selectPursuitTarget(attacker, [...snapshot].reverse()).referenceId, 1699);
});
```

- [ ] **Step 2: Implement target filtering and locking primitives**

Filter dead and friendly units, enforce extracted line of sight, rank by surface
gap and reference ID, and return `null` when no enemy is visible. This module
does not mutate units and does not retarget a live locked target.

- [ ] **Step 3: Write failing movement and contact tests**

```javascript
test("unblocked pursuit moves exactly speed divided by 60", () => {
  const proposal = proposeMovement(unit, target, 60);
  assert.ok(Math.abs(Math.hypot(proposal.dx, proposal.dy) - 1.06 / 60) < 1e-12);
});

test("head-on Champions stop without penetrating their collision bodies", () => {
  const next = resolveMovementProposals(snapshot, proposals, map);
  assert.ok(surfaceGap(next[0], next[1]) >= -1e-12);
});
```

- [ ] **Step 4: Implement frozen-snapshot movement proposals**

Normalize the target direction, clamp displacement to the remaining surface
gap, and keep proposal generation independent of processing order.

- [ ] **Step 5: Implement symmetric collision resolution**

Resolve all proposals together. Remove inward normal velocity, preserve a
collision-free tangential component, and otherwise stop the unit for that
tick. Sort pair constraints by reference IDs. Add no collision coefficient or
preferred turn direction.

- [ ] **Step 6: Run focused tests and commit**

Run: `node --test aoe2x/js_simulation/tests/targeting.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs`

```powershell
git add aoe2x/js_simulation/src/combat/targeting.js aoe2x/js_simulation/src/combat/movement.js aoe2x/js_simulation/src/combat/collision.js aoe2x/js_simulation/tests/targeting.test.mjs aoe2x/js_simulation/tests/movement-collision.test.mjs
git commit -m "feat(sim): add deterministic champion pursuit and contact"
```

### Task 6: Implement the eight-phase deterministic world tick

**Files:**
- Create: `aoe2x/js_simulation/src/combat/attacks.js`
- Create: `aoe2x/js_simulation/src/combat/world.js`
- Create: `aoe2x/js_simulation/tests/world-tick.test.mjs`

**Interfaces:**
- Produces: `createWorld(scenario) -> World`, `stepWorld(world) -> World`, `runWorld(world, { maxTicks }) -> Result`, and attack event constructors.

- [ ] **Step 1: Write a failing phase-order test**

```javascript
test("both sides decide from the same start-of-tick snapshot", () => {
  const forward = stepWorld(createWorld(scenario));
  const reversed = stepWorld(createWorld({ ...scenario, units: [...scenario.units].reverse() }));
  assert.deepEqual(normalizeWorld(forward), normalizeWorld(reversed));
});
```

- [ ] **Step 2: Write a failing deterministic event-order test**

```javascript
test("same-tick attacks use reference IDs rather than owner or input order", () => {
  const events = orderReadyAttacks([attackFrom1699, attackFrom1628]);
  assert.deepEqual(events.map((event) => event.actorId), [1628, 1699]);
});
```

- [ ] **Step 3: Implement the world tick pipeline**

Implement snapshot, pursuit validation/acquisition, movement proposal,
collision/contact resolution, engagement selection, swing-target capture,
attack progression, sequential damage commit, and immutable event publication
in the approved order.

- [ ] **Step 4: Implement attack readiness and class-derived damage**

Use integer ticks converted from extracted attack delay and reload. Use the
body-surface range test. At commit time, cancel an attack when its actor or
target was killed earlier in the tick. Emit `pursuit-acquired`,
`pursuit-invalidated`, `move`, `blocked`, `engagement-started`,
`engagement-ended`, `attack-start`, `damage`, `death`, and `attack-canceled`
events with reference IDs.

- [ ] **Step 5: Add invariant and safety tests**

```javascript
test("the runner fails rather than returning a timeout outcome", () => {
  assert.throws(() => runWorld(stalemate, { maxTicks: 3600 }), /exceeded 3600 ticks/);
});

test("published live units never retain a friendly target", () => {
  assert.equal(result.snapshots.some((snapshot) => hasFriendlyTarget(snapshot)), false);
});
```

- [ ] **Step 6: Run world tests and commit**

Run: `node --test aoe2x/js_simulation/tests/world-tick.test.mjs`

```powershell
git add aoe2x/js_simulation/src/combat/attacks.js aoe2x/js_simulation/src/combat/world.js aoe2x/js_simulation/tests/world-tick.test.mjs
git commit -m "feat(sim): add deterministic champion world ticks"
```

### Task 7: Pass the 1v1 direct-engagement gate

**Files:**
- Create: `aoe2x/js_simulation/tests/champion-1v1.test.mjs`
- Modify: shared combat modules only when the failing trace identifies a general mechanic error.

**Interfaces:**
- Consumes: `createChampionScenario` and `runWorld`.
- Produces: the first complete deterministic Champion fight trace.

- [ ] **Step 1: Write the strict 1v1 outcome test**

```javascript
test("Champion 1v1 ends with nine 14-HP hits and one 14-HP survivor", () => {
  const result = runChampionRatio("1v1");
  assert.equal(result.damageEvents.length, 9);
  assert.deepEqual(new Set(result.damageEvents.map((event) => event.amount)), new Set([14]));
  assert.equal(result.winner.hp, 14);
  assert.equal(result.loser.hp, 0);
  assert.equal(result.livingUnits.length, 1);
});
```

- [ ] **Step 2: Write deterministic and order-invariance tests**

Run the fight five times and require identical final-state and event-log hashes.
Reverse the input array and require the same hashes. Do not assert that a
specific owner wins.

- [ ] **Step 3: Add 1v1 trace diagnostics**

Compare exact spawns, first movement, movement direction, surface contact,
first damage, same-attacker damage intervals, kill tick, hits per owner, and
winner HP against all three tapes. Timing fields report deltas but do not alter
mechanics.

- [ ] **Step 4: Run the 1v1 gate**

Run: `node --test aoe2x/js_simulation/tests/champion-1v1.test.mjs`

Expected: exact HP/damage gate passes, deterministic hashes match, and the
diagnostic report contains all three tape comparisons.

- [ ] **Step 5: Commit the 1v1 milestone**

```powershell
git add aoe2x/js_simulation/src/combat aoe2x/js_simulation/tests/champion-1v1.test.mjs
git commit -m "feat(sim): pass champion one-versus-one gate"
```

### Task 8: Pass the 2v1 shared-target and body-contact gate

**Files:**
- Create: `aoe2x/js_simulation/tests/champion-2v1.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/collision.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`

**Interfaces:**
- Extends the shared engine with behavior exposed by two attackers pursuing one target; creates no ratio branch.

- [ ] **Step 1: Write the strict 2v1 test**

```javascript
test("Champion 2v1 matches the authorized median outcome", () => {
  const result = runChampionRatio("2v1");
  assert.equal(result.winnerOwner, 2);
  assert.equal(result.winnerHp, 112);
  assert.equal(result.livingUnits.length, 2);
  assert.ok(result.damageEvents.length >= 7 && result.damageEvents.length <= 8);
});
```

- [ ] **Step 2: Write contact-graph tests**

Require both side2 units to acquire reference `1699`, prohibit all body
penetration, and require the second attacker either to reach legal contact or
to record blocked/sliding ticks. Array reversal must not change the trace.

- [ ] **Step 3: Run 1v1 and 2v1 together and inspect the first divergent event on failure**

Run: `node --test aoe2x/js_simulation/tests/champion-1v1.test.mjs aoe2x/js_simulation/tests/champion-2v1.test.mjs`

Only modify general collision or phase logic supported by the per-unit tape
positions and attacker/victim damage IDs.

- [ ] **Step 4: Commit the 2v1 gate**

```powershell
git add aoe2x/js_simulation/src/combat aoe2x/js_simulation/tests/champion-2v1.test.mjs
git commit -m "feat(sim): pass champion two-versus-one gate"
```

### Task 9: Pass the 2v3 death and retargeting gate

**Files:**
- Create: `aoe2x/js_simulation/tests/champion-2v3.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/targeting.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`

**Interfaces:**
- Extends shared dead-target invalidation and reacquisition; creates no ratio-specific behavior.

- [ ] **Step 1: Write the strict 2v3 test**

```javascript
test("Champion 2v3 matches the exact repeated tape outcome", () => {
  const result = runChampionRatio("2v3");
  assert.equal(result.winnerOwner, 3);
  assert.equal(result.winnerHp, 126);
  assert.equal(result.livingUnits.length, 2);
  assert.equal(result.damageEvents.length, 16);
});
```

- [ ] **Step 2: Write pursuit and attack lifecycle tests**

For every `pursuitTargetId` change, require a preceding `death` and
`pursuit-invalidated` event for the old pursuit target. Prohibit
block-triggered pursuit changes and attacks committed against dead targets.
Task 10 later separates physical `engagedTargetId` transitions and immutable
per-swing `attackTargetId` from this death-only pursuit lifecycle.

- [ ] **Step 3: Run the cumulative gate**

Run: `node --test aoe2x/js_simulation/tests/champion-1v1.test.mjs aoe2x/js_simulation/tests/champion-2v1.test.mjs aoe2x/js_simulation/tests/champion-2v3.test.mjs`

- [ ] **Step 4: Commit the 2v3 gate**

```powershell
git add aoe2x/js_simulation/src/combat aoe2x/js_simulation/tests/champion-2v3.test.mjs
git commit -m "feat(sim): pass champion two-versus-three gate"
```

### Task 10: Pass the 5v3 local-crowding gate

**Files:**
- Create: `aoe2x/js_simulation/tests/champion-5v3.test.mjs`
- Create: `aoe2x/js_simulation/tests/target-state.test.mjs`
- Modify: `aoe2x/js_simulation/src/combat/collision.js`
- Modify: `aoe2x/js_simulation/src/combat/local-avoidance.js`
- Modify: `aoe2x/js_simulation/src/combat/targeting.js`
- Modify: `aoe2x/js_simulation/src/combat/unit-state.js`
- Modify: `aoe2x/js_simulation/src/combat/world.js`

**Interfaces:**
- Splits pursuit, physical engagement, and immutable swing targets; exposes a
  pure resolved-contact manifold; exercises the existing normal/tangential
  response under multiple ranks; adds no formation or ratio rule.

- [ ] **Step 1: Write the strict 5v3 test**

```javascript
test("Champion 5v3 matches the authorized median outcome", () => {
  const result = runChampionRatio("5v3");
  assert.equal(result.winnerOwner, 2);
  assert.equal(result.winnerHp, 252);
  assert.ok(new Set([4, 5]).has(result.livingUnits.length));
  assert.ok(result.damageEvents.length >= 22 && result.damageEvents.length <= 25);
});
```

- [ ] **Step 2: Write congestion invariants**

Require zero prohibited overlap in every snapshot, no forced global turn
direction, at least one blocked or tangential-slide event when the trace
contains allied contact, and eventual progress for every living unit with a
reachable target.

- [ ] **Step 3: Run the cumulative 1v1-through-5v3 gate**

Run: `node --test aoe2x/js_simulation/tests/champion-1v1.test.mjs aoe2x/js_simulation/tests/champion-2v1.test.mjs aoe2x/js_simulation/tests/champion-2v3.test.mjs aoe2x/js_simulation/tests/champion-5v3.test.mjs`

- [ ] **Step 4: Commit the 5v3 gate**

```powershell
git add aoe2x/js_simulation/src/combat aoe2x/js_simulation/tests/champion-5v3.test.mjs
git commit -m "feat(sim): pass champion five-versus-three gate"
```

### Task 11: Pass the 6v3 overflow-attacker gate

**Files:**
- Create: `aoe2x/js_simulation/tests/champion-6v3.test.mjs`
- Modify: shared targeting, movement, or collision modules only when trace evidence requires it.

**Interfaces:**
- Validates that the shared engine handles additional attackers without a special overflow rule.

- [ ] **Step 1: Write the strict 6v3 test**

```javascript
test("Champion 6v3 matches the authorized median outcome", () => {
  const result = runChampionRatio("6v3");
  assert.equal(result.winnerOwner, 2);
  assert.equal(result.winnerHp, 336);
  assert.ok(new Set([5, 6]).has(result.livingUnits.length));
  assert.ok(result.damageEvents.length >= 21 && result.damageEvents.length <= 23);
});
```

- [ ] **Step 2: Write overflow progress tests**

Every living attacker with a visible enemy must be in pursuit, blocked by a
specific body, in contact, winding up, or reloading. No unit may remain idle
without an event explaining why.

- [ ] **Step 3: Run every ratio test**

Run: `node --test aoe2x/js_simulation/tests/champion-*.test.mjs`

- [ ] **Step 4: Commit the 6v3 gate**

```powershell
git add aoe2x/js_simulation/src/combat aoe2x/js_simulation/tests/champion-6v3.test.mjs
git commit -m "feat(sim): pass champion six-versus-three gate"
```

### Task 12: Produce the all-ratio comparison report

**Files:**
- Create: `aoe2x/js_simulation/src/champion-comparison.js`
- Create: `aoe2x/js_simulation/tools/run_champion_suite.mjs`
- Create: `aoe2x/js_simulation/tests/champion-comparison.test.mjs`
- Create: `aoe2x/js_simulation/calibration/reports/champion_simulation_results.json`
- Create: `aoe2x/js_simulation/calibration/reports/champion_simulation_results.md`

**Interfaces:**
- Produces: `compareChampionSuite({ truth, simulationResults }) -> SuiteReport` and a CLI that writes JSON and Markdown from the same object.

- [ ] **Step 1: Write failing strict-gate tests**

```javascript
test("the report requires exact median winner HP for every ratio", () => {
  const report = compareChampionSuite({ truth, simulationResults });
  assert.deepEqual(report.ratios.map(({ ratio, hpDelta }) => [ratio, hpDelta]), [
    ["1v1", 0], ["2v1", 0], ["2v3", 0], ["5v3", 0], ["6v3", 0],
  ]);
  assert.equal(report.passed, true);
});
```

- [ ] **Step 2: Implement outcome and diagnostic calculations**

Report tape median HP, simulation HP, signed HP percentage, absolute delta,
winner correctness, survivor and damage-event bounds, determinism hash, first
movement, first damage, kill time, distance traveled, blocked ticks, target
timeline, and attacks canceled by death.

- [ ] **Step 3: Run the suite twice and prove byte-identical outputs**

Run:

```powershell
node aoe2x/js_simulation/tools/run_champion_suite.mjs --truth aoe2x/js_simulation/calibration/fixtures/champion_basics.json --output-json aoe2x/js_simulation/calibration/reports/champion_simulation_results.json --output-md aoe2x/js_simulation/calibration/reports/champion_simulation_results.md
node --test aoe2x/js_simulation/tests/champion-comparison.test.mjs
```

- [ ] **Step 4: Commit the comparison boundary**

```powershell
git add aoe2x/js_simulation/src/champion-comparison.js aoe2x/js_simulation/tools/run_champion_suite.mjs aoe2x/js_simulation/tests/champion-comparison.test.mjs aoe2x/js_simulation/calibration/reports/champion_simulation_results.json aoe2x/js_simulation/calibration/reports/champion_simulation_results.md
git commit -m "test(sim): gate all champion small-group ratios"
```

### Task 13: Add ratio playback and tick diagnostics to the approved viewer

**Files:**
- Modify: `aoe2x/js_simulation/server.mjs`
- Modify: `aoe2x/js_simulation/viewer/index.html`
- Modify: `aoe2x/js_simulation/viewer/app.js`
- Modify: `aoe2x/js_simulation/viewer/map-renderer.js`
- Modify: `aoe2x/js_simulation/viewer/styles.css`
- Modify: `aoe2x/js_simulation/tests/server.test.mjs`
- Modify: `aoe2x/js_simulation/tests/map-renderer.test.mjs`
- Create: `aoe2x/js_simulation/tests/viewer-simulation.test.mjs`

**Interfaces:**
- Server adds read-only `/api/champion/truth`, `/api/champion/mechanics`, and `/api/champion/result?ratio=<ratio>&repeat=<repeat>` endpoints.
- Renderer consumes simulation snapshots but never calls `stepWorld`.
- Viewer URLs preserve `ratio` and `repeat`; suspicious-run flags and notes are stored locally and export as JSON without modifying truth or simulation results.

- [ ] **Step 1: Write failing endpoint tests**

Require all three endpoints to return no-store JSON, reject unknown ratios, and
keep the source zip and raw fixtures inaccessible.

- [ ] **Step 2: Write failing renderer-state tests**

```javascript
test("the viewer renders the supplied tick without advancing the world", () => {
  renderer.setSimulationSnapshot(snapshotAtTick42);
  assert.equal(renderer.getDisplayedTick(), 42);
  assert.equal(stepWorldCalls, 0);
});

test("review flags round-trip without changing simulation state", () => {
  const before = renderer.getSimulationSnapshot();
  feedback.flag({ ratio: "2v3", repeat: 2, note: "target switch looks late" });
  assert.deepEqual(renderer.getSimulationSnapshot(), before);
  assert.deepEqual(feedback.exportJson().runs[0], {
    ratio: "2v3", repeat: 2, flagged: true, note: "target switch looks late",
  });
});
```

- [ ] **Step 3: Add simulation controls**

Add ratio selection, play, pause, reset, single tick, next event, tape repeat
selection, tick/seconds readout, HP, action state, target lines, collision
circles, attack reach, and an event timeline. Keep ratio and repeat in the URL.
Add a suspicious-run checkbox, note field, clear-feedback action, and JSON
feedback export backed by browser-local storage. Do not add seed controls.

- [ ] **Step 4: Preserve map rendering invariants**

Keep the map fixture, counterclockwise view transform, Panda Rock position,
Gaia layer, pan/zoom, and 21v21 formation view unchanged. Add an explicit
control to return from simulation playback to the locked formation.

- [ ] **Step 5: Run viewer and server tests**

Run: `node --test aoe2x/js_simulation/tests/server.test.mjs aoe2x/js_simulation/tests/map-renderer.test.mjs aoe2x/js_simulation/tests/viewer-simulation.test.mjs`

- [ ] **Step 6: Start the local server and inspect all ratios**

Run: `node aoe2x/js_simulation/server.mjs --host 127.0.0.1 --port 5011`

Verify the local and existing Tailnet route load, every ratio animates, single
tick and next event are exact, refresh preserves URL selection and local review
flags, feedback export downloads valid JSON, and the browser console has zero
errors.

- [ ] **Step 7: Commit viewer playback**

```powershell
git add aoe2x/js_simulation/server.mjs aoe2x/js_simulation/viewer aoe2x/js_simulation/tests
git commit -m "feat(sim): visualize champion tick simulations"
```

### Task 14: Lock the Champion small-groups milestone

**Files:**
- Modify: `aoe2x/js_simulation/README.md`
- Create: `aoe2x/js_simulation/docs/MILESTONE_02_CHAMPION_SMALL_GROUPS.md`
- Modify: `docs/superpowers/specs/2026-08-04-cleanroom-champion-tick-simulator-design.md` only if verified implementation differs from the approved design.

**Interfaces:**
- Produces the durable milestone record and exact verification commands.

- [ ] **Step 1: Correct stale README formation descriptions**

Replace the retired Elite-Jaguar-versus-Militia text with the actual locked
Paladin/Elite-Steppe source formation and explain that ratio scenarios replace
those unit types with Champion mechanics while retaining coordinates.

- [ ] **Step 2: Document provenance and results**

Record archive and scenario hashes, game version `180059`, 60-Hz hypothesis,
mechanics source hashes, exact outcomes for all five ratios, per-ratio trace
links, no-randomness rule, and all known residual diagnostic timing differences.

- [ ] **Step 3: Run full verification**

Run:

```powershell
python -m pytest tests/test_cleanroom_map_export.py tests/test_cleanroom_champion_basics.py tests/test_cleanroom_champion_clock.py tests/test_cleanroom_champion_mechanics.py -q -p no:cacheprovider
node --test aoe2x/js_simulation/tests
node aoe2x/js_simulation/tools/run_champion_suite.mjs --truth aoe2x/js_simulation/calibration/fixtures/champion_basics.json --output-json aoe2x/js_simulation/calibration/reports/champion_simulation_results.json --output-md aoe2x/js_simulation/calibration/reports/champion_simulation_results.md
git diff --check
```

Expected: every Python and JavaScript test passes; the suite report says
`passed: true`; every ratio has zero median HP delta; repeated executions have
identical hashes; and no source or manifest hash differs from the authority.

- [ ] **Step 4: Inspect the final worktree scope**

Run: `git status --short` and `git diff --stat`. Confirm that unrelated dirty
files remain untouched and the ignored source zip is not staged.

- [ ] **Step 5: Commit the milestone**

```powershell
git add aoe2x/js_simulation/README.md aoe2x/js_simulation/docs/MILESTONE_02_CHAMPION_SMALL_GROUPS.md aoe2x/js_simulation/calibration/reports
git commit -m "docs(sim): lock champion small-groups milestone"
```

## Execution order and review gates

Execute Tasks 1-7 first and review the 1v1 trace before adding another ratio.
Then execute exactly one ratio task at a time in the order 2v1, 2v3, 5v3, 6v3.
The comparison report, viewer integration, and milestone lock follow only after
all five headless gates pass.

If 60 Hz produces a systematic trace error, preserve the report, compare the
50-Hz and 60-Hz residuals from Task 2, and request an explicit clock-provenance
change before modifying `TICKS_PER_SECOND`. Do not select a clock rate by asking
which one gives the preferred final HP.
