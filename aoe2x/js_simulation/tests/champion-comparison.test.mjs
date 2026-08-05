import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import {
  auditSimulationSource,
  compareChampionSuite,
  createChampionPlaybackData,
  renderChampionMarkdown,
  serializeChampionReport,
  validateChampionRun,
} from "../src/champion-comparison.js";
import { writeChampionReport } from "../tools/run_champion_suite.mjs";
import { runChampionRatio } from "./support/champion-ratio.mjs";


const truthUrl = new URL("../calibration/fixtures/champion_basics.json", import.meta.url);
const mechanicsUrl = new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url);
const clockUrl = new URL(
  "../calibration/reports/champion_clock_forensics.json",
  import.meta.url,
);
const [truth, mechanics, clockEvidence] = await Promise.all([
  readFile(truthUrl, "utf8").then(JSON.parse),
  readFile(mechanicsUrl, "utf8").then(JSON.parse),
  readFile(clockUrl, "utf8").then(JSON.parse),
]);
const RATIOS = ["1v1", "2v1", "2v3", "5v3", "6v3"];
const AUDITED_FILES = [
  "src/champion-scenarios.js",
  "src/formation-model.js",
  "src/map-model.js",
  "src/simulation-clock.js",
  "src/canonical-json.js",
  "src/combat/attacks.js",
  "src/combat/collision.js",
  "src/combat/local-avoidance.js",
  "src/combat/movement.js",
  "src/combat/targeting.js",
  "src/combat/unit-state.js",
  "src/combat/world.js",
  "tests/support/champion-ratio.mjs",
];
const executableSource = Object.fromEntries(await Promise.all(AUDITED_FILES.map(async (path) => [
  path,
  await readFile(new URL(`../${path}`, import.meta.url), "utf8"),
])));
const AUDIT_OPTIONS = {
  allowances: [
    {
      file: "src/champion-scenarios.js",
      category: "ratio-specific branch",
      token: "if (!SUPPORTED_RATIOS.has(ratio) || !truth.ratios?.[ratio]) {",
      context: "if (!SUPPORTED_RATIOS.has(ratio) || !truth.ratios?.[ratio]) {",
      expectedCount: 1,
      reason: "locked ratio inventory and roster validation select starting state; they do not alter combat physics",
    },
    {
      file: "src/champion-scenarios.js",
      category: "owner-specific branch",
      token: "owner === 2",
      context: "2: units.filter(({ owner }) => owner === 2).map(({ referenceId }) => referenceId),",
      expectedCount: 1,
      reason: "locked roster metadata groups scenario units without altering combat physics",
    },
    {
      file: "src/champion-scenarios.js",
      category: "owner-specific branch",
      token: "owner === 3",
      context: "3: units.filter(({ owner }) => owner === 3).map(({ referenceId }) => referenceId),",
      expectedCount: 1,
      reason: "locked roster metadata groups scenario units without altering combat physics",
    },
    ...[
      "if (!['default', 'counterclockwise'].includes(orientation)) {",
      "if (orientation === \"counterclockwise\") return { x: y, y: mapWidth - x };",
      "if (orientation === \"counterclockwise\") return { x: mapWidth - y, y: x };",
      "const viewedA = orientation === \"counterclockwise\"",
      "const viewedB = orientation === \"counterclockwise\"",
    ].map((context) => ({
      file: "src/map-model.js",
      category: "global turn rule",
      token: "counterclockwise",
      context,
      expectedCount: 1,
      reason: "counterclockwise is the locked map-view coordinate transform, not a unit steering rule",
    })),
    {
      file: "src/combat/attacks.js",
      category: "HP/damage modifier",
      token: "damage +=",
      context: "damage += Math.max(0, requireFinite(attack, `attack class ${classId}`) - armor);",
      expectedCount: 1,
      reason: "source-backed matching armor-class bonuses are accumulated before the AoE minimum-damage rule",
    },
    {
      file: "tests/support/champion-ratio.mjs",
      category: "ratio-specific branch",
      token: "if (fixture.ratios?.[ratio]?.runs?.length !== repeatCount) {",
      context: "if (fixture.ratios?.[ratio]?.runs?.length !== repeatCount) {",
      expectedCount: 1,
      reason: "authorized ratio inventory and fixture validation select scenarios; they do not alter combat physics",
    },
  ],
  exclusions: [
    {
      file: "src/champion-comparison.js",
      reason: "reporting and static-lint implementation is self-referential and does not advance simulation physics",
    },
  ],
};


function runSuite() {
  return RATIOS.map((ratio) => ({
    ratio,
    runs: [
      runChampionRatio(ratio),
      runChampionRatio(ratio),
      runChampionRatio(ratio, { reverseUnits: true }),
    ],
  }));
}


const simulationResults = runSuite();


function compareRealSuite({ results = simulationResults, truthFixture = truth } = {}) {
  return compareChampionSuite({
    truth: truthFixture,
    simulationResults: results,
    clockEvidence,
    mechanics,
    sourceAudit: auditSimulationSource(executableSource, AUDIT_OPTIONS),
  });
}


function mutatePrimary(ratio, mutation) {
  return simulationResults.map((row) => row.ratio === ratio ? {
    ...row,
    runs: [mutation(row.runs[0]), ...row.runs.slice(1)],
  } : row);
}


test("the report requires exact median winner HP for every ratio", () => {
  const report = compareRealSuite();

  assert.deepEqual(report.ratios.map(({ ratio, hpDelta }) => [ratio, hpDelta]), [
    ["1v1", 0],
    ["2v1", 0],
    ["2v3", 0],
    ["5v3", 0],
    ["6v3", 0],
  ]);
  assert.deepEqual(report.ratios.map(({ hpPctDelta }) => hpPctDelta), [0, 0, 0, 0, 0]);
  assert.deepEqual(report.ratios.map(({ simulation }) => ({
    winnerOwner: simulation.winnerOwner,
    winnerHp: simulation.winnerHp,
    winnerHpPct: simulation.winnerHpPct,
    survivors: simulation.survivors,
    damageEvents: simulation.damageEvents,
  })), [
    { winnerOwner: 2, winnerHp: 14, winnerHpPct: 20, survivors: 1, damageEvents: 9 },
    { winnerOwner: 2, winnerHp: 112, winnerHpPct: 80, survivors: 2, damageEvents: 7 },
    { winnerOwner: 3, winnerHp: 126, winnerHpPct: 60, survivors: 2, damageEvents: 16 },
    { winnerOwner: 2, winnerHp: 252, winnerHpPct: 72, survivors: 4, damageEvents: 22 },
    { winnerOwner: 2, winnerHp: 336, winnerHpPct: 80, survivors: 6, damageEvents: 21 },
  ]);
  assert.ok(report.ratios.every(({ winnerCorrect }) => winnerCorrect));
  assert.ok(report.ratios.every(({ survivorCountWithinTapeRange }) => (
    survivorCountWithinTapeRange
  )));
  assert.ok(report.ratios.every(({ damageEventCountWithinTapeRange }) => (
    damageEventCountWithinTapeRange
  )));
  assert.ok(report.ratios.every(({ determinism }) => (
    determinism.repeatMatches && determinism.reverseOrderMatches
  )));
  assert.ok(report.ratios.every(({ passed }) => passed));
  assert.equal(report.passed, true);
});


test("the report preserves source, clock, mechanics, and per-ratio trace diagnostics", () => {
  const report = compareRealSuite();

  assert.deepEqual(report.source, {
    archive: "aoe2_golden_basics_championvschampion_2026-08-04.zip",
    archivePath: "aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip",
    zipSha256: "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE",
    recordings: 15,
    repeatsPerRatio: { "1v1": 3, "2v1": 3, "2v3": 3, "5v3": 3, "6v3": 3 },
    verifiedByRunner: true,
    truthFixture: {
      path: "aoe2x/js_simulation/calibration/fixtures/champion_basics.json",
      sha256: "5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E",
      verification: "byte_exact_runtime_lock",
      reproducibilityTest: "tests/test_cleanroom_champion_basics.py::test_generated_fixture_matches_checked_in_fixture",
    },
    mechanicsFixture: {
      path: "aoe2x/js_simulation/fixtures/unit_stats/champion_chinese_imperial.json",
      sha256: "4D4FE28BBBD2C5BDAC76AC7C2594C8FE569B877A75F230BB47B965848455D0F0",
      verification: "byte_exact_runtime_lock",
      reproducibilityTest: "tests/test_cleanroom_champion_mechanics.py::test_exporter_maps_controlled_sources_reproducibly",
      reproducibilityScope: "controlled exporter sources; this report did not re-extract the installed Genie data",
    },
  });
  assert.deepEqual(report.clock, {
    ticksPerSecond: 60,
    status: "provisional_not_published",
    selectionBasis: "60 Hz is a provisional simulation hypothesis; it is not selected from HP, winner, or outcome accuracy.",
    runsAnalyzed: 15,
    ratiosAnalyzed: ["1v1", "2v1", "2v3", "5v3", "6v3"],
    sourceVerified: true,
  });
  assert.deepEqual(report.mechanics.values, {
    unitMaster: 567,
    civilization: "Chinese",
    hp: 70,
    speedTilesPerSecond: 1.06,
    collisionRadiusTiles: 0.2,
    attackRangeTiles: 0,
    reloadSeconds: 2,
    attackDelaySeconds: 0,
    lineOfSightTiles: 5,
    damageVsSelf: 14,
  });
  assert.equal(report.mechanics.provenance.datSha256.length, 64);
  assert.equal(report.mechanics.provenance.referenceDbSha256.length, 64);
  assert.equal(
    report.mechanics.provenance.datSha256,
    "CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF",
  );
  assert.equal(
    report.mechanics.provenance.referenceDbSha256,
    "51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087",
  );
  assert.equal(report.mechanics.provenance.fixtureSha256, report.source.mechanicsFixture.sha256);
  assert.equal(report.mechanics.verified, true);
  assert.equal(report.mechanics.sourceAudit.passed, true);
  assert.deepEqual(report.mechanics.sourceAudit.findings, []);
  assert.equal(report.mechanics.sourceAudit.kind, "heuristic_static_lint");
  assert.match(report.mechanics.sourceAudit.assurance, /not a proof/i);
  assert.ok(report.mechanics.sourceAudit.approvedFindings.length > 0);
  assert.deepEqual(report.mechanics.sourceAudit.exclusions, AUDIT_OPTIONS.exclusions);

  for (const row of report.ratios) {
    assert.ok(Number.isSafeInteger(row.diagnostics.firstMovement.tick));
    assert.ok(row.diagnostics.firstMovement.actorIds.length > 0);
    assert.equal(row.diagnostics.firstDamage.amount, 14);
    assert.ok(Number.isSafeInteger(row.diagnostics.finalKill.tick));
    assert.ok(row.diagnostics.distanceTraveled.totalTiles > 0);
    assert.ok(row.diagnostics.distanceTraveled.byUnit.length > 0);
    assert.ok(row.diagnostics.blockedTicks.byUnit.length > 0);
    assert.ok(row.diagnostics.targetTimeline.length > 0);
    assert.ok(Array.isArray(row.diagnostics.attacksCanceledByDeath.events));
    assert.equal(row.validity.passed, true);
  }
});


test("the executable-source audit rejects every prohibited calibration shortcut", () => {
  const prohibited = auditSimulationSource({
    "combat/forced.js": `
      if (world.ratio === "5v3") useAlternatePath();
      if (unit.owner === 2) favorWinner();
      const postSwingPauseTicks = 42;
      damage *= 1.1;
      const compressionRatio = 0.8;
      const globalTurn = "clockwise";
      const roll = Math.random();
    `,
  });

  assert.equal(prohibited.passed, false);
  assert.deepEqual(new Set(prohibited.findings.map(({ category }) => category)), new Set([
    "ratio-specific branch",
    "owner-specific branch",
    "fitted timing rule",
    "HP/damage modifier",
    "speed/radius/compression multiplier",
    "global turn rule",
    "randomness",
  ]));

  const alternatives = auditSimulationSource({
    "combat/alternatives.js": `
      speed *= 0.8;
      radius /= 2;
      damage = 13;
      hp = 999;
      if (unit["owner"] === 3) favorWinner();
      if (Number(world.ratio[0]) === units.length) alterContact();
      const roll = randomBytes(1);
    `,
  });
  assert.equal(alternatives.passed, false);
  assert.deepEqual(new Set(alternatives.findings.map(({ category }) => category)), new Set([
    "ratio-specific branch",
    "owner-specific branch",
    "HP/damage modifier",
    "speed/radius/compression multiplier",
    "randomness",
  ]));

  const actual = auditSimulationSource(executableSource, AUDIT_OPTIONS);
  assert.equal(actual.passed, true);
  assert.deepEqual(actual.findings, []);
  assert.deepEqual(actual.files, AUDITED_FILES);
  assert.ok(actual.approvedFindings.length > 0);

  const duplicatedApprovedBranch = auditSimulationSource({
    ...executableSource,
    "src/champion-scenarios.js": `${executableSource["src/champion-scenarios.js"]}\n`
      + "if (!SUPPORTED_RATIOS.has(ratio) || !truth.ratios?.[ratio]) {",
  }, AUDIT_OPTIONS);
  assert.equal(duplicatedApprovedBranch.passed, false);
  assert.equal(
    duplicatedApprovedBranch.findings.filter(({ file, category }) => (
      file === "src/champion-scenarios.js" && category === "ratio-specific branch"
    )).length,
    2,
  );
});


test("overall PASS rejects malformed hit, geometry, reference, completion, and terminal state", () => {
  const replaceFirstDamage = (result, replacement) => {
    let changed = false;
    const events = result.events.map((event) => {
      if (changed || event.type !== "damage") return event;
      changed = true;
      return { ...event, ...replacement(event) };
    });
    return { ...result, events, damageEvents: events.filter(({ type }) => type === "damage") };
  };
  const mutations = [
    {
      gate: "everyDamageExactly14",
      mutate: (result) => replaceFirstDamage(result, () => ({ amount: 13 })),
    },
    {
      gate: "liveBodiesNonOverlapping",
      mutate: (result) => {
        const snapshot = result.snapshots[1];
        const [anchor, overlapping] = snapshot.units;
        const units = snapshot.units.map((unit) => unit.referenceId === overlapping.referenceId
          ? { ...unit, x: anchor.x, y: anchor.y }
          : unit);
        return {
          ...result,
          snapshots: result.snapshots.map((row, index) => index === 1
            ? { ...snapshot, units }
            : row),
        };
      },
    },
    {
      gate: "targetReferencesAndLifecycleValid",
      mutate: (result) => replaceFirstDamage(result, (event) => ({ targetId: event.actorId })),
    },
    {
      gate: "completedWithoutStalemateOrTimeout",
      mutate: (result) => ({ ...result, outcome: "timeout", timedOut: true }),
    },
    {
      gate: "terminalWinnerValid",
      mutate: (result) => ({ ...result, winnerOwner: 3 }),
    },
  ];

  for (const { gate, mutate } of mutations) {
    const report = compareRealSuite({ results: mutatePrimary("1v1", mutate) });
    const row = report.ratios.find(({ ratio }) => ratio === "1v1");
    assert.equal(row.validity[gate], false, `${gate} must reject its mutation`);
    assert.equal(row.validity.passed, false);
    assert.equal(row.passed, false);
    assert.equal(report.passed, false);
  }
});


test("strict target validity rejects snapshot, lifecycle, and target-event corruption", () => {
  const result = runChampionRatio("2v3");
  const mutateSnapshotUnit = (snapshotIndex, referenceId, replacement) => ({
    ...result,
    snapshots: result.snapshots.map((snapshot, index) => index === snapshotIndex ? {
      ...snapshot,
      units: snapshot.units.map((unit) => unit.referenceId === referenceId
        ? { ...unit, ...replacement(unit, snapshot) }
        : unit),
    } : snapshot),
  });
  const first = result.snapshots[1];
  const actor = first.units.find(({ alive }) => alive);
  const friendly = first.units.find((unit) => (
    unit.alive && unit.owner === actor.owner && unit.referenceId !== actor.referenceId
  ));
  const enemy = first.units.find((unit) => unit.alive && unit.owner !== actor.owner);

  const mutations = [
    mutateSnapshotUnit(1, actor.referenceId, () => ({ pursuitTargetId: friendly.referenceId })),
    mutateSnapshotUnit(1, actor.referenceId, () => ({ pursuitTargetId: 999999 })),
    mutateSnapshotUnit(1, actor.referenceId, () => ({ engagedTargetId: friendly.referenceId })),
    mutateSnapshotUnit(1, actor.referenceId, () => ({
      action: "idle",
      attackTargetId: enemy.referenceId,
      windupTicksRemaining: 0,
    })),
  ];

  const death = result.events.find(({ type }) => type === "death");
  const deathSnapshot = result.snapshots.find(({ tick }) => tick === death.tick);
  const deadTarget = deathSnapshot.units.find(
    ({ referenceId }) => referenceId === death.targetId,
  );
  const deathTickActor = deathSnapshot.units.find((unit) => (
    unit.alive && unit.owner !== deadTarget.owner
  ));
  mutations.push(mutateSnapshotUnit(
    result.snapshots.indexOf(deathSnapshot),
    deathTickActor.referenceId,
    () => ({ engagedTargetId: death.targetId }),
  ));
  mutations.push(mutateSnapshotUnit(
    result.snapshots.indexOf(deathSnapshot),
    deathTickActor.referenceId,
    () => ({
      action: "attacking",
      attackTargetId: death.targetId,
      actionTimers: { windup: 1, reload: 0 },
    }),
  ));
  const staleTick = death.tick + 1;
  const staleSnapshot = result.snapshots.find(({ tick }) => tick === staleTick);
  const staleActor = staleSnapshot.units.find((unit) => (
    unit.alive && unit.owner !== staleSnapshot.units.find(
      ({ referenceId }) => referenceId === death.targetId,
    ).owner
  ));
  mutations.push(mutateSnapshotUnit(
    result.snapshots.indexOf(staleSnapshot),
    staleActor.referenceId,
    () => ({ pursuitTargetId: death.targetId }),
  ));

  const pursuitEventIndex = result.events.findIndex(({ type }) => type === "pursuit-acquired");
  mutations.push({
    ...result,
    events: result.events.map((event, index) => index === pursuitEventIndex
      ? { ...event, targetId: event.actorId }
      : event),
  });

  for (const eventType of ["pursuit-acquired", "engagement-started", "attack-start", "damage"]) {
    const eventIndex = result.events.findIndex(({ type }) => type === eventType);
    mutations.push({
      ...result,
      events: result.events.map((event, index) => index === eventIndex
        ? { ...event, targetId: event.actorId }
        : event),
    });
  }

  const invalidation = result.events.find(({ type, reason }) => (
    type === "pursuit-invalidated" && reason === "target-dead"
  ));
  mutations.push({
    ...result,
    events: result.events.filter((event) => event !== invalidation),
  });

  for (const mutation of mutations) {
    const validity = validateChampionRun(mutation);
    assert.equal(validity.targetReferencesAndLifecycleValid, false);
    assert.equal(validity.passed, false);
  }
});


test("tape HP percentage is recomputed from median HP and validated against the fixture", () => {
  const report = compareRealSuite();
  assert.ok(report.ratios.every(({ tape }) => (
    tape.medianWinnerHpPct === tape.medianWinnerHp / tape.medianWinnerStartingHp * 100
    && tape.fixtureMedianWinnerHpPct === tape.medianWinnerHpPct
    && tape.fixtureMedianWinnerHpPctMatches
  )));

  const alteredTruth = JSON.parse(JSON.stringify(truth));
  alteredTruth.ratios["2v1"].median_winner_hp_pct = 79;
  const altered = compareRealSuite({ truthFixture: alteredTruth });
  const row = altered.ratios.find(({ ratio }) => ratio === "2v1");
  assert.equal(row.tape.medianWinnerHpPct, 80);
  assert.equal(row.tape.fixtureMedianWinnerHpPct, 79);
  assert.equal(row.tape.fixtureMedianWinnerHpPctMatches, false);
  assert.equal(row.hpPctDelta, 0);
  assert.equal(row.passed, false);
  assert.equal(altered.passed, false);
});


test("every ratio preserves all three tape comparisons and declares the playback boundary", () => {
  const report = compareRealSuite();
  for (const row of report.ratios) {
    assert.deepEqual(
      row.tapeComparisons.map(({ tag }) => tag),
      [row.ratio, `${row.ratio}_r2`, `${row.ratio}_r3`],
    );
    for (const comparison of row.tapeComparisons) {
      assert.ok(comparison.deltas.starts.length > 0);
      assert.ok(comparison.deltas.firstMoves.length > 0);
      assert.ok(Object.hasOwn(comparison.deltas, "surfaceContact"));
      assert.ok(Object.hasOwn(comparison.deltas, "firstDamage"));
      assert.ok(Object.hasOwn(comparison.deltas, "sameAttackerIntervals"));
      assert.ok(Object.hasOwn(comparison.deltas, "kill"));
      assert.ok(Object.hasOwn(comparison.deltas, "hitsPerOwner"));
      assert.ok(Object.hasOwn(comparison.deltas, "winnerHp"));
    }
    assert.deepEqual(row.playback, {
      schemaVersion: 1,
      provider: "createChampionPlaybackData",
      module: "aoe2x/js_simulation/src/champion-comparison.js",
      runner: "aoe2x/js_simulation/tests/support/champion-ratio.mjs",
      ratio: row.ratio,
      snapshots: row.simulation.snapshotCount,
      events: row.simulation.eventCount,
      embedsFullTrace: false,
      immutableRunnerFields: ["snapshots", "events"],
      verification: "strict_run_source_and_canonical_hashes",
    });
  }

  const result = simulationResults[0].runs[0];
  const playback = createChampionPlaybackData(result);
  assert.equal(playback.ratio, "1v1");
  assert.equal(playback.snapshots, result.snapshots);
  assert.equal(playback.events, result.events);
  assert.equal(playback.source.truthFixtureSha256, report.source.truthFixture.sha256);
  assert.equal(Object.isFrozen(playback), true);
  assert.equal(Object.isFrozen(playback.snapshots), true);
  assert.equal(Object.isFrozen(playback.events), true);
  assert.equal(Object.isFrozen(playback.snapshots[0].units[0]), true);
  assert.equal(Object.isFrozen(playback.source), true);
});


test("playback serializer rejects unverified, mutable, fabricated, and corrupted runs", () => {
  const result = simulationResults[0].runs[0];
  const replace = (patch) => ({ ...result, ...patch });
  const mutableSnapshots = Object.freeze(result.snapshots.map((snapshot, index) => index === 0
    ? { ...snapshot, units: snapshot.units.map((unit) => ({ ...unit })) }
    : snapshot));
  const corruptEvents = Object.freeze(result.events.map((event, index) => index === 0
    ? Object.freeze({ ...event, targetId: 999999 })
    : event));

  const invalid = [
    replace({ snapshots: Object.freeze([]), events: Object.freeze([]) }),
    replace({ snapshots: mutableSnapshots }),
    replace({ events: corruptEvents }),
    replace({ finalStateHash: "0".repeat(64) }),
    replace({ eventLogHash: "0".repeat(64) }),
    replace({ world: Object.freeze({ ...result.world, ratio: "9v9" }) }),
    replace({ diagnostics: Object.freeze({
      ...result.diagnostics,
      source: Object.freeze({ ...result.diagnostics.source, zipSha256: "BAD" }),
    }) }),
  ];
  for (const fabricated of invalid) {
    assert.throws(() => createChampionPlaybackData(fabricated), /playback/i);
  }
});


test("JSON and Markdown reports regenerate byte-identically from one report object", async () => {
  const first = compareRealSuite();
  const second = compareRealSuite();
  const firstJson = serializeChampionReport(first);
  const firstMarkdown = renderChampionMarkdown(first);

  assert.equal(serializeChampionReport(second), firstJson);
  assert.equal(renderChampionMarkdown(second), firstMarkdown);
  assert.match(firstMarkdown, /# Champion clean-room simulation results/);
  assert.match(firstMarkdown, /\| 5v3 \| 2 \| 252\/350 \| 72% \| 2 \| 252\/350 \| 72% \| \+0 \| \+0 pp \|/);
  assert.match(firstMarkdown, /provisional_not_published/);
  assert.match(firstMarkdown, /Heuristic static lint found no unapproved shortcut-pattern matches/);
  assert.match(firstMarkdown, /not a proof of absence or bypass resistance/);
  assert.doesNotMatch(firstMarkdown, /No prohibited calibration shortcuts detected/);
  assert.match(firstMarkdown, /createChampionPlaybackData/);
  assert.match(firstMarkdown, /5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E/);

  const outputDirectory = await mkdtemp(new URL("./.tmp-champion-report-", import.meta.url));
  const outputJson = join(outputDirectory, "results.json");
  const outputMarkdown = join(outputDirectory, "results.md");
  try {
    await writeChampionReport({ report: first, outputJson, outputMarkdown });
    assert.equal(await readFile(outputJson, "utf8"), firstJson);
    assert.equal(await readFile(outputMarkdown, "utf8"), firstMarkdown);
  } finally {
    await rm(outputDirectory, { recursive: true, force: true });
  }
});
