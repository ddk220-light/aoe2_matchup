import assert from "node:assert/strict";
import test from "node:test";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  runPhase2Batch1Sample,
  scenarioFromPhase2Batch1Row,
} from "../src/phase2-batch1-comparison.js";
import {
  runPhase2Batch1Suite,
  runSchedule,
} from "../tools/run_phase2_batch1_suite.mjs";
import {
  mergePhase2Batch1RowReports,
  validatePhase2Batch1RowReport,
} from "../tools/run_recoverable_phase2_batch1.mjs";


const ROOT = new URL("../", import.meta.url);


test("Phase 2 schedule uses five stable samples and at most fifteen knife-edge samples", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const schedule = runSchedule(truth.rows);
  assert.equal(schedule.filter(({ tape }) => tape.volatile).length, 120);
  assert.equal(schedule.filter(({ tape }) => !tape.volatile).length, 560);
  assert.equal(schedule.length, 680);
  assert.throws(
    () => runSchedule(truth.rows, { samples: 5, volatileSamples: 16 }),
    /capped at 15 samples/,
  );
});


test("tape-normalized melee-versus-ranged rows keep the ranged kiter on owner 2", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_woad_raider_vs_arbalester");
  assert.equal(row.side2.slug, "arbalester");
  assert.equal(row.side3.slug, "elite_woad_raider");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex: 0, seed: 20260817, context });
  assert.equal(scenario.kiteOwner, 2);
  assert.equal(scenario.meleeCrowdOwner, 3);
  assert.equal(scenario.kiteNavigation, "cohesive");
  assert.equal(scenario.kiteMeleeOpeningOrder, "attack-move-all");
  assert.equal(scenario.kiteChaseDwellTicks, 0);
  assert.equal(scenario.preventiveContactSteering, true);
});


test("Phase 2 applies the evidence-backed War Wagon formation and body-contact policy only there", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const warWagonRow = truth.rows.find(({ id }) => id === "elite_war_wagon_vs_paladin");
  const championRow = truth.rows.find(({ id }) => id === "elite_war_wagon_vs_champion");
  const boyarRow = truth.rows.find(({ id }) => id === "elite_boyar_vs_paladin");
  const warWagonScenario = scenarioFromPhase2Batch1Row({
    row: warWagonRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const boyarScenario = scenarioFromPhase2Batch1Row({
    row: boyarRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  const championScenario = scenarioFromPhase2Batch1Row({
    row: championRow,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });

  assert.equal(warWagonScenario.kiteProfile.formationSpacingTiles, 0.6);
  assert.equal(warWagonScenario.attackMoveStickyPursuit, true);
  assert.equal(warWagonScenario.attackMoveTargetPressureTiles, 0.5);
  assert.ok(Math.abs(warWagonScenario.warWagonEnemyOverlapDepthTiles - 0.1) < 1e-12);
  assert.equal(warWagonScenario.warWagonEnemyOverlapMode, "always");
  assert.equal(championScenario.kiteProfile.formationSpacingTiles, 0.6);
  assert.equal(championScenario.attackMoveTargetPressureTiles, 0.4);
  assert.equal(championScenario.warWagonEnemyOverlapDepthTiles, 0);
  assert.equal(championScenario.warWagonEnemyOverlapMode, "always");
  assert.equal(boyarScenario.warWagonEnemyOverlapDepthTiles, undefined);
  assert.equal(boyarScenario.warWagonEnemyOverlapMode, undefined);
  assert.equal(boyarScenario.attackMoveStickyPursuit, undefined);
});


test("one Phase 2 sample runs from the exact golden starting roster", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const row = truth.rows.find(({ id }) => id === "elite_boyar_vs_champion");
  const context = await loadPhase2Batch1Context(ROOT, truth);
  const sample = runPhase2Batch1Sample({
    row,
    sampleIndex: 0,
    seed: 20260817,
    context,
  });
  assert.equal(sample.rowId, row.id);
  assert.equal(sample.sampleIndex, 0);
  assert.ok(["win", "timeout"].includes(sample.outcome));
  assert.ok(sample.outcome === "timeout" || Number.isFinite(sample.score));
});


test("recoverable row reports preserve the five/fifteen sample policy and knife-edge label", async () => {
  const truth = await loadPhase2Batch1Truth(ROOT);
  const rowIds = ["elite_longbowman_vs_champion", "elite_woad_raider_vs_paladin"];
  const reports = [];
  for (const rowId of rowIds) {
    reports.push(await runPhase2Batch1Suite({
      truth,
      context: {},
      rowIds: [rowId],
      runImpl: ({ row, sampleIndex, seed }) => ({
        rowId: row.id,
        sampleIndex,
        seed,
        outcome: "win",
        winnerOwner: row.runs[0].winner_owner,
        winnerHp: row.runs[0].winner_hp,
        score: row.runs[0].signed_score,
        ticks: 1,
      }),
    }));
  }
  assert.equal(validatePhase2Batch1RowReport(reports[0], rowIds[0]), true);
  assert.equal(validatePhase2Batch1RowReport(reports[1], rowIds[1]), true);
  const merged = mergePhase2Batch1RowReports(reports, rowIds);
  assert.equal(merged.schedule.stableRows, 1);
  assert.equal(merged.schedule.volatileRows, 1);
  assert.equal(merged.schedule.totalRuns, 20);
  assert.equal(merged.summary.knifeEdgeRows, 1);
  assert.equal(merged.rows.find(({ id }) => id === rowIds[1]).tapeClassification, "knife-edge");
});
