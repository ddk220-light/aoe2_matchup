import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { renderDedicatedCsv } from "./run_dedicated_ranged_melee_suite.mjs";


export function mergeDedicatedShards(shards) {
  if (!Array.isArray(shards) || shards.length < 1) throw new TypeError("shards are required");
  const shardCount = shards[0].schedule.shardCount;
  const indices = shards.map(({ schedule }) => schedule.shardIndex).toSorted((a, b) => a - b);
  if (shards.length !== shardCount
      || indices.some((value, index) => value !== index)
      || shards.some(({ schedule }) => schedule.shardCount !== shardCount)) {
    throw new Error("shard index/count coverage is incomplete");
  }
  const rows = shards.flatMap(({ rows: shardRows }) => shardRows);
  const matchupSummaries = shards.flatMap(({ matchupSummaries }) => matchupSummaries);
  if (new Set(rows.map(({ id }) => id)).size !== rows.length) {
    throw new Error("duplicate dedicated row across shards");
  }
  if (new Set(matchupSummaries.map(({ matchupId }) => matchupId)).size !== matchupSummaries.length) {
    throw new Error("duplicate dedicated matchup across shards");
  }
  const totalAttempts = rows.reduce((total, row) => total + row.samples.length, 0);
  if (matchupSummaries.length !== 17 || rows.length !== 85 || totalAttempts !== 425) {
    throw new Error(
      `incomplete merged corpus: ${matchupSummaries.length} matchups, ${rows.length} rows, ${totalAttempts} attempts`,
    );
  }
  const unresolvedRuns = rows.reduce((total, row) => total + row.comparison.unresolvedRuns, 0);
  const finiteDeltas = rows.map(({ comparison }) => comparison.absoluteMeanDelta).filter(Number.isFinite);
  const summary = Object.freeze({
    matchups: matchupSummaries.length,
    rows: rows.length,
    totalRuns: totalAttempts,
    resolvedRuns: totalAttempts - unresolvedRuns,
    unresolvedRuns,
    fullyUnresolvedRows: rows.filter(({ comparison }) => comparison.simulation.runs === 0).length,
    partiallyUnresolvedRows: rows.filter(({ comparison }) => (
      comparison.simulation.runs > 0 && comparison.unresolvedRuns > 0
    )).length,
    rowsOver25PointDelta: rows.filter(({ comparison }) => (
      comparison.absoluteMeanDelta > 25
    )).length,
    rowsInsideTapeBand: rows.filter(({ comparison }) => comparison.tapeBandError === 0).length,
    wrongWinnerRuns: rows.reduce((total, row) => total + row.comparison.wrongWinnerRuns, 0),
    meanAbsoluteMeanDelta: mean(finiteDeltas),
    medianAbsoluteMeanDelta: median(finiteDeltas),
    maximumAbsoluteMeanDelta: Math.max(...finiteDeltas),
  });
  return Object.freeze({
    ...shards[0],
    schedule: Object.freeze({
      matchups: 17,
      rows: 85,
      tapeRunsPerRow: 5,
      totalRuns: 425,
      shardCount,
    }),
    summary,
    matchupSummaries: Object.freeze(matchupSummaries.toSorted((left, right) => (
      left.matchupId.localeCompare(right.matchupId)
    ))),
    rows: Object.freeze(rows.toSorted((left, right) => left.id.localeCompare(right.id))),
  });
}


export async function main(argv = process.argv.slice(2)) {
  const root = argv[0]
    ? resolve(argv[0])
    : resolve(fileURLToPath(new URL(
      "../calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/shards/",
      import.meta.url,
    )));
  const output = argv[1] ? resolve(argv[1]) : dirname(root);
  const shards = await Promise.all([0, 1, 2, 3].map((index) => readFile(
    resolve(root, `shard-${index}`, "results.json"),
    "utf8",
  ).then(JSON.parse)));
  const merged = mergeDedicatedShards(shards);
  await Promise.all([
    writeFile(resolve(output, "results.json"), `${JSON.stringify(merged, null, 2)}\n`, "utf8"),
    writeFile(resolve(output, "results.csv"), renderDedicatedCsv(merged), "utf8"),
  ]);
  process.stdout.write(`${JSON.stringify(merged.summary)}\n`);
  return merged;
}


function mean(values) {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
}


function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
