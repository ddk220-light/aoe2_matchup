// Refresh only the captured-live side of an existing expanded-roster comparison.
// Simulator seeds and their outcomes are preserved byte-for-byte.
import { readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";


function argument(prefix) {
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length);
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function summary(values) {
  return { mean: mean(values), min: Math.min(...values), max: Math.max(...values) };
}


const captureDirectory = resolve(argument("--capture=") ?? "");
const comparisonFile = resolve(argument("--comparison=") ?? "");
const matchupKey = argument("--matchup=");
if (!captureDirectory || !comparisonFile || !matchupKey) {
  throw new Error("--capture, --comparison and --matchup are required");
}

const [capture, report] = await Promise.all([
  readFile(join(captureDirectory, "capture_manifest.json"), "utf8").then(JSON.parse),
  readFile(comparisonFile, "utf8").then(JSON.parse),
]);
const row = report.rows?.find(({ key }) => key === matchupKey);
if (!row) throw new Error(`comparison has no row ${matchupKey}`);
const capturedRuns = (capture.runs?.[matchupKey] ?? [])
  .toSorted((left, right) => left.repeat - right.repeat);
if (capturedRuns.length === 0) throw new Error(`${matchupKey} has no completed live captures`);

function observedOwner(winner) {
  if (winner === row.side2.slug) return 2;
  if (winner === row.side3.slug) return 3;
  throw new Error(`capture winner ${winner} does not match either comparison roster side`);
}

row.live = capturedRuns.map(({ repeat, capture: observed }) => ({
  repeat,
  winnerOwner: observedOwner(observed.winner),
  winnerHp: observed.winner_hp,
  survivorCount: observed.survivors,
  eliminationSeconds: observed.elimination_time_s,
  framesBin: join(
    captureDirectory,
    matchupKey,
    `run_${String(repeat).padStart(3, "0")}`,
    "raw recordings",
    `${matchupKey}.frames.bin`,
  ),
  framesSha256: observed.frames_sha256,
}));
const liveWinnerOwners = row.live.map(({ winnerOwner }) => winnerOwner);
const liveHp = summary(row.live.map(({ winnerHp }) => winnerHp));
row.liveSummary = { winnerOwners: liveWinnerOwners, winnerHp: liveHp };

const resolved = row.simulation.filter(({ winnerOwner }) => Number.isSafeInteger(winnerOwner));
const simHp = summary(resolved.map(({ winnerHp }) => winnerHp));
const simulationWinnerOwners = resolved.map(({ winnerOwner }) => winnerOwner);
const stableLiveWinner = liveWinnerOwners.every((owner) => owner === liveWinnerOwners[0])
  ? liveWinnerOwners[0] : null;
const correctWinnerRuns = stableLiveWinner === null
  ? null
  : simulationWinnerOwners.filter((owner) => owner === stableLiveWinner).length;
const relativeWinnerHpDelta = Math.abs(simHp.mean - liveHp.mean) / liveHp.mean;
row.simulationSummary = {
  ...row.simulationSummary,
  resolved: resolved.length,
  winnerOwners: simulationWinnerOwners,
  winnerHp: simHp,
  correctWinnerRuns,
  relativeWinnerHpDelta,
  success: stableLiveWinner !== null
    && correctWinnerRuns === resolved.length
    && resolved.length === report.config.openingSeeds.length
    && relativeWinnerHpDelta < 0.10,
};

const failures = report.rows.filter(({ simulationSummary }) => simulationSummary.success !== true);
report.generatedAt = new Date().toISOString();
report.source.captureManifest = join(captureDirectory, "capture_manifest.json");
report.source.captureRoot = captureDirectory;
report.summary = {
  matchups: report.rows.length,
  successes: report.rows.length - failures.length,
  failures: failures.length,
  wrongWinnerMatchups: failures.filter(({ liveSummary, simulationSummary }) => (
    liveSummary.winnerOwners.every((owner) => owner === liveSummary.winnerOwners[0])
      && simulationSummary.winnerOwners.some(
        (owner) => owner !== liveSummary.winnerOwners[0],
      )
  )).length,
  aboveTenPercentHp: failures.filter(({ simulationSummary }) => (
    simulationSummary.relativeWinnerHpDelta >= 0.10
  )).length,
};
report.failureKeys = failures.map(({ key }) => key);

await writeFile(comparisonFile, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({
  matchup: matchupKey,
  liveRuns: row.live.length,
  liveWinnerOwners,
  liveWinnerHp: liveHp,
  simulationWinnerOwners,
  simulationWinnerHp: simHp,
  relativeWinnerHpDelta,
  success: row.simulationSummary.success,
})}\n`);
