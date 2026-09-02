import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";


const [outputArgument, ...inputArguments] = process.argv.slice(2);
if (!outputArgument || inputArguments.length < 1) {
  throw new Error("usage: node merge_comparison_reports.mjs OUTPUT INPUT...");
}

const reports = await Promise.all(inputArguments.map(async (input) => (
  JSON.parse(await readFile(resolve(input), "utf8"))
)));
const rows = reports.flatMap(({ rows }) => rows)
  .toSorted((left, right) => left.key.localeCompare(right.key));
const keys = rows.map(({ key }) => key);
if (new Set(keys).size !== keys.length) throw new Error("duplicate matchup key in inputs");
for (const row of rows) {
  if (row.simulationSummary.resolved !== 5 || row.simulation.length !== 5) {
    throw new Error(`${row.key} does not contain five resolved simulation seeds`);
  }
}
const failures = rows.filter(({ simulationSummary }) => !simulationSummary.success);
const wrongWinnerRows = rows.filter(({ liveSummary, simulationSummary }) => (
  liveSummary.winnerOwners.every((owner) => owner === liveSummary.winnerOwners[0])
  && simulationSummary.winnerOwners.some((owner) => owner !== liveSummary.winnerOwners[0])
));
const hpMissRows = rows.filter(({ simulationSummary }) => (
  Math.abs(simulationSummary.hpPercentagePointDelta) > 10
));
const merged = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  source: reports[0].source,
  config: reports[0].config,
  summary: {
    matchups: rows.length,
    simulationRuns: rows.length * 5,
    successes: rows.length - failures.length,
    failures: failures.length,
    wrongWinnerMatchups: wrongWinnerRows.length,
    aboveTenPercentagePointsHp: hpMissRows.length,
  },
  failureKeys: failures.map(({ key }) => key),
  wrongWinnerKeys: wrongWinnerRows.map(({ key }) => key),
  aboveTenPercentagePointKeys: hpMissRows.map(({ key }) => key),
  rows,
};
await writeFile(resolve(outputArgument), `${JSON.stringify(merged, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(merged.summary)}\n`);
