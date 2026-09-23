// Local patch-candidate comparison; never updates rankings or recorded outcomes.
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve, relative, isAbsolute } from "node:path";
import { parallelJobs } from "./headless-runner.mjs";
import { deriveRecordedBattleSetup } from "../src/battle-setup.js";

export function compareRecordedResult(metadata, simulation) {
  const captured = metadata.expected.outcome;
  if (simulation.error) return {
    jobId: metadata.jobId, status: "error", recorded: captured, error: simulation.error,
  };
  // The recorder divides game time by gameSpeed and rounds to video seconds.
  // Preserve that source value, but compare like-for-like game seconds.
  if (metadata.recordingClock?.rows !== "video_seconds"
      || !(metadata.recordingClock.gameSpeed > 0)) throw new Error("recorded clock must specify video_seconds and gameSpeed");
  const recorded = { ...captured,
    eliminationGameSeconds: captured.eliminationTimeSeconds * metadata.recordingClock.gameSpeed,
  };
  const owner = simulation.winnerOwner;
  const hpPercent = owner == null ? 0
    : 100 * simulation.winnerHp / simulation.startingHpByOwner[owner];
  const signedHp = owner === 2 ? hpPercent : -hpPercent;
  const seconds = simulation.ticks / 60;
  return {
    jobId: metadata.jobId, status: "preliminary", recorded,
    simulation: {
      ...simulation, survivors: simulation.remainingByOwner[owner]?.units ?? 0,
      signedRemainingHpPercent: signedHp, eliminationTimeSeconds: seconds,
    },
    winnerMatches: owner === recorded.winnerOwner,
    signedHpPercentagePointDifference: signedHp - recorded.signedRemainingHpPercent,
    durationDifferenceSeconds: seconds - recorded.eliminationGameSeconds,
  };
}

async function main() {
  const options = { workers: 4 };
  for (let i = 2; i < process.argv.length; i += 2) {
    const key = process.argv[i].replace(/^--/, "");
    options[key] = process.argv[i + 1];
  }
  if (!options.input || !options.output) throw new Error("--input and --output are required");
  const output = resolve(options.output);
  const local = fileURLToPath(new URL("../calibration/lab/", import.meta.url));
  const within = relative(local, output);
  if (within.startsWith("..") || isAbsolute(within)) throw new Error("output must be inside calibration/lab");
  const document = JSON.parse(await readFile(options.input, "utf8"));
  const evidence = new Map(document.metadata.matchups.map(row => [row.jobId, row]));
  // Settle setup agreement before spending CPU on any fights. Never substitute
  // a captured count or cost into a candidate simply to make this check pass.
  for (const job of document.jobs) {
    const sides = job.teams.map(t => ({ class: t.mechanics.behavior_class, effectiveCost: t.effectiveCost }));
    const setup = deriveRecordedBattleSetup(...sides);
    const expected = evidence.get(job.jobId).expected;
    if (setup.n2 !== expected.side2.count || setup.n3 !== expected.side3.count
        || setup.player4Count !== expected.player4Count) {
      throw new Error(`recorded setup differs for ${job.jobId}: ${JSON.stringify(setup)}`);
    }
    for (let i = 0; i < 2; i += 1) {
      for (const r of ["food", "wood", "gold"]) {
        if (sides[i].effectiveCost[r] !== expected[`side${i + 2}`].effectiveCost[r]) {
          throw new Error(`recorded ${r} cost differs for ${job.jobId}, side ${i + 2}`);
        }
      }
    }
  }
  console.log(`Running ${document.jobs.length} preliminary comparisons with ${options.workers} workers`);
  const results = await parallelJobs(document.jobs, Number(options.workers));
  const comparisons = results.map(result => compareRecordedResult(evidence.get(result.jobId), result));
  const summary = {
    runs: comparisons.length, errors: comparisons.filter(row => row.status === "error").length,
    matchingWinners: comparisons.filter(row => row.winnerMatches === true).length,
    flippedWinners: comparisons.filter(row => row.winnerMatches === false).length,
  };
  const report = {
    status: "preliminary_not_ranking_ready", createdAt: new Date().toISOString(), summary,
    limitations: [
      "Hamask, Shield Wall, technology-applied flat trample, and smart-mode-8 inherited charge damage are implemented.",
      "Jarl armor-reduction tooltip conflicts with raw/recorded evidence; no speculative stripping added.",
      "Gothikon uses two separately spent charges and 30-second recovery per charge; inter-throw timing follows sourced reload/special animation and is not live-validated.",
      "Jomsviking torch inherits carrier damage and remains restricted to buildings/ships; the land recordings do not validate torch flight behavior.",
      "One seed per matchup compared with one existing recording; matching winners do not establish calibration.",
      "Recorded elimination is integer-game-second sampled, converted to video seconds, then rounded; normalized durations are approximate.",
    ],
    source: document.metadata, comparisons,
  };
  await writeFile(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ ...summary, output }));
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) await main();
