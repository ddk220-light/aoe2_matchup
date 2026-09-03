import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  loadDedicatedComparisonContext,
  scenarioFromDedicatedRun,
} from "../../../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../../../src/dedicated-golden-corpus.js";
import { createWorld, runWorld } from "../../../src/combat/world.js";

const reportDir = path.dirname(fileURLToPath(import.meta.url));
const resultsPath = path.resolve(
  reportDir,
  "../dedicated_ranged_melee_steering_050_parallel_2026-08-14/results.json",
);
const outputPath = path.join(reportDir, "analysis.json");
const results = JSON.parse(fs.readFileSync(resultsPath, "utf8"));

const TICKS_PER_SECOND = 60;

function quantile(sorted, probability) {
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

function round(value, digits = 2) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

const attempts = results.rows.flatMap((row) =>
  row.samples.map((sample) => ({
    ...sample,
    rowId: row.id,
    matchupId: row.matchupId,
    matchup: row.matchup,
    ratio: row.ratio,
  })),
);
const resolvedAttempts = attempts.filter((attempt) => attempt.outcome === "win");
const resolvedTicks = resolvedAttempts.map((attempt) => attempt.ticks).sort((a, b) => a - b);
const totalResolvedTicks = resolvedTicks.reduce((sum, ticks) => sum + ticks, 0);

const duration = {
  ticksPerSecond: TICKS_PER_SECOND,
  tickLimit: results.config.maxTicks,
  tickLimitSeconds: results.config.maxTicks / TICKS_PER_SECOND,
  tickLimitMinutes: results.config.maxTicks / TICKS_PER_SECOND / 60,
  attempts: attempts.length,
  resolvedAttempts: resolvedAttempts.length,
  timeoutAttempts: attempts.length - resolvedAttempts.length,
  meanTicks: round(totalResolvedTicks / resolvedTicks.length),
  medianTicks: round(quantile(resolvedTicks, 0.5)),
  p75Ticks: round(quantile(resolvedTicks, 0.75)),
  p90Ticks: round(quantile(resolvedTicks, 0.9)),
  p95Ticks: round(quantile(resolvedTicks, 0.95)),
  p99Ticks: round(quantile(resolvedTicks, 0.99)),
  maxTicks: resolvedTicks.at(-1),
};
for (const key of ["mean", "median", "p75", "p90", "p95", "p99", "max"]) {
  duration[`${key}Seconds`] = round(duration[`${key}Ticks`] / TICKS_PER_SECOND);
}
duration.resolvedAttemptsAboveCandidateCap = Object.fromEntries(
  [3600, 4500, 5400, 6000, 7200, 9000].map((cap) => [
    cap,
    resolvedTicks.filter((ticks) => ticks > cap).length,
  ]),
);

const rows = results.rows.map((row) => ({
  id: row.id,
  matchupId: row.matchupId,
  matchup: row.matchup,
  ratio: row.ratio,
  meanTicks: round(row.samples.reduce((sum, sample) => sum + sample.ticks, 0) / row.samples.length),
  maxTicks: Math.max(...row.samples.map((sample) => sample.ticks)),
  meanSeconds: round(
    row.samples.reduce((sum, sample) => sum + sample.ticks, 0) /
      row.samples.length /
      TICKS_PER_SECOND,
  ),
  maxSeconds: round(Math.max(...row.samples.map((sample) => sample.ticks)) / TICKS_PER_SECOND),
  outcomes: [...new Set(row.samples.map((sample) => sample.outcome))],
  tapeScore: round(row.comparison.tape.mean),
  simulationScore: round(row.comparison.simulation.mean),
  meanDelta: round(row.comparison.meanDelta),
  absoluteMeanDelta: round(row.comparison.absoluteMeanDelta),
  wrongWinnerRuns: row.comparison.wrongWinnerRuns,
}));

const steppeRows = rows.filter((row) => row.matchup.includes("Steppe Lancer"));
const steppeMatchups = [...new Set(steppeRows.map((row) => row.matchupId))].map((matchupId) => {
  const matching = steppeRows.filter((row) => row.matchupId === matchupId);
  return {
    matchupId,
    matchup: matching[0].matchup,
    rowCount: matching.length,
    meanAbsoluteDelta: round(
      matching.reduce((sum, row) => sum + row.absoluteMeanDelta, 0) / matching.length,
    ),
    maxAbsoluteDelta: round(Math.max(...matching.map((row) => row.absoluteMeanDelta))),
    rowsAbove25: matching.filter((row) => row.absoluteMeanDelta > 25).length,
    wrongWinnerRuns: matching.reduce((sum, row) => sum + row.wrongWinnerRuns, 0),
  };
});

const simulationRoot = new URL("../../../", import.meta.url);
const [corpus, context] = await Promise.all([
  loadDedicatedGoldenCorpus(simulationRoot),
  loadDedicatedComparisonContext(simulationRoot),
]);
const timeoutStateRows = [];
for (const timeoutRow of rows.filter((row) => row.outcomes.includes("timeout"))) {
  const matchup = corpus.matchups.find(({ id }) => id === timeoutRow.matchupId);
  const row = matchup?.ratios.find(({ id }) => id === timeoutRow.id);
  if (!row) throw new Error(`cannot resolve timeout row ${timeoutRow.id}`);
  const states = [];
  for (const run of row.runs) {
    const scenario = scenarioFromDedicatedRun({
      row: { ...row, rangedSlug: matchup.rangedSlug, meleeSlug: matchup.meleeSlug },
      run,
      mechanicsByMaster: context.mechanicsByMaster,
      map: context.map,
    });
    let finalWorld;
    try {
      const result = runWorld(createWorld(scenario), {
        maxTicks: results.config.maxTicks,
        retainSnapshots: false,
      });
      finalWorld = result.world;
    } catch (error) {
      if (!String(error?.message ?? error).includes("world exceeded")) throw error;
      finalWorld = error.world;
    }
    const finalByOwner = Object.fromEntries([2, 3].map((owner) => {
      const ownerUnits = finalWorld.units.filter((unit) => unit.owner === owner);
      return [owner, {
        unitsAlive: ownerUnits.filter((unit) => unit.alive).length,
        hp: round(ownerUnits.reduce((sum, unit) => sum + unit.hp, 0)),
        startingHp: run.starting_hp_by_owner[String(owner)],
        hpFraction: round(
          ownerUnits.reduce((sum, unit) => sum + unit.hp, 0) /
            run.starting_hp_by_owner[String(owner)],
          4,
        ),
      }];
    }));
    states.push({
      repeat: run.repeat,
      tick: finalWorld.tick,
      owner2: finalByOwner[2],
      owner3: finalByOwner[3],
      normalizedHpLeadOwner3Points: round(
        (finalByOwner[3].hpFraction - finalByOwner[2].hpFraction) * 100,
      ),
    });
  }
  timeoutStateRows.push({ rowId: timeoutRow.id, states });
}

const analysis = {
  generatedAt: new Date().toISOString(),
  source: path.relative(process.cwd(), resultsPath).replaceAll("\\", "/"),
  duration,
  longestResolvedRows: rows
    .filter((row) => row.outcomes.length === 1 && row.outcomes[0] === "win")
    .sort((a, b) => b.maxTicks - a.maxTicks)
    .slice(0, 15),
  timeoutRows: rows.filter((row) => row.outcomes.includes("timeout")),
  timeoutStates: timeoutStateRows,
  steppeMatchups,
  steppeRows,
};

fs.writeFileSync(outputPath, `${JSON.stringify(analysis, null, 2)}\n`);
console.log(JSON.stringify(analysis, null, 2));
