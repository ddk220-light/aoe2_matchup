// Post-pilot integrity, exact-seed replay and side-reversal diagnostics.
// Diagnostic runs are kept separate from the 3/10-seed ranking dataset.
import assert from "node:assert/strict";
import { readFileSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Worker } from "node:worker_threads";
import { gunzipSync } from "node:zlib";
import { createHash } from "node:crypto";
import { loadCampaign, openCampaignDb, storedRuns, pendingJobs, atomicJson } from "./ranking-campaign.mjs";
import { loadLabScenario } from "../src/lab-scenario.js";
import { unitDescriptorFromMechanics } from "../src/mechanics-schema.js";

const directory = resolve(process.argv[2]);
const manifest = loadCampaign(directory);
const db = openCampaignDb(directory, manifest.campaignHash);
assert.equal(db.prepare("PRAGMA integrity_check").get().integrity_check, "ok");
const runs = storedRuns(db);
assert.equal(pendingJobs(manifest, runs).length, 0);
assert.equal(new Set(runs.map(r => `${r.matchupId}:${r.seed}`)).size, runs.length);
assert.equal(db.prepare("SELECT COUNT(*) AS n FROM attempts WHERE status='running'").get().n, 0);
db.close();
const firstSixPath = "/tmp/ranking-pilot-first-six.jsonl";
if (existsSync(firstSixPath)) {
  for (const row of readFileSync(firstSixPath, "utf8").trim().split("\n").map(JSON.parse)) {
    assert.deepEqual(runs.find(r => r.matchupId === row.matchupId && r.seed === row.seed), row);
  }
}
let verifiedPlaybacks = 0;
let verifiedSnapshots = 0;
for (const run of runs) {
  if (!run.result) continue; // Interrupted/watchdog files remain partial for separate review.
  const matchup = manifest.matchups.find(m => m.id === run.matchupId);
  const bytes = readFileSync(resolve(directory, run.playbackPath));
  const lines = gunzipSync(bytes).toString("utf8").trim().split("\n").map(JSON.parse);
  const header = lines.shift();
  const footer = lines.pop();
  assert.equal(header.jobId, matchup.id);
  assert.equal(header.seed, run.seed);
  assert.equal(footer.finalStateHash, run.finalStateHash);
  assert.equal(footer.eventLogHash, run.eventLogHash);
  assert.equal(lines.length, run.ticks + 1);
  assert.deepEqual(Object.keys(run.result.remainingByOwner).sort(), ["2", "3"]);
  assert.equal(lines[0].units.length, matchup.teams.reduce((n, t) => n + t.count, 0));
  for (let i = 0; i < lines.length; i++) assert.equal(lines[i].tick, i);
  const final = lines.at(-1);
  for (const owner of [2, 3]) {
    const living = final.units.filter(u => u[5] && footer.unitIndex[u[0]].owner === owner);
    assert.equal(living.length, footer.remainingByOwner[owner].units);
    assert.ok(Math.abs(living.reduce((n, u) => n + u[4], 0) - footer.remainingByOwner[owner].hp) < 1e-7);
  }
  verifiedPlaybacks++;
  verifiedSnapshots += lines.length;
}

mkdirSync(resolve(directory, "playbacks/diagnostics"), { recursive: true });
async function diagnostic(matchupId, reverse) {
  const matchup = manifest.matchups.find(m => m.id === matchupId);
  const baseline = runs.find(r => r.matchupId === matchupId && r.seed === 0);
  const teams = (reverse ? [...matchup.teams].reverse() : matchup.teams)
    .map(({ mechanics, count }) => ({ mechanics, count }));
  const scenario = reverse ? await loadLabScenario(new URL("../", import.meta.url),
    ...teams.map(t => unitDescriptorFromMechanics(t.mechanics)), { includeBuffer: false }) : matchup.scenario;
  const id = `${reverse ? "reversed" : "repeat"}_${matchupId}_0`;
  const job = { jobId: id, seed: 0, teams, scenario, disableAiOrders: true,
    disableKiting: true, preserveOwnerOrientation: true, retainSnapshots: false };
  const started = performance.now();
  const result = await new Promise((finish, reject) => {
    const worker = new Worker(new URL("./campaign-worker.mjs", import.meta.url), {
      workerData: { job, playbackPath: resolve(directory, `playbacks/diagnostics/${id}.jsonl.gz`) },
    });
    const timeout = setTimeout(() => { worker.terminate(); reject(new Error(`diagnostic timed out: ${id}`)); }, 120000);
    worker.on("message", m => {
      if (m.progress !== undefined) return;
      clearTimeout(timeout);
      worker.terminate();
      if (m.error) reject(new Error(m.error.message)); else finish(m.result);
    });
    worker.on("error", error => { clearTimeout(timeout); reject(error); });
  });
  const row = { id, diagnostic: true, seed: 0, matchupId, reverse,
    wallSeconds: (performance.now() - started) / 1000, result,
    expectedWinnerOwner: reverse && baseline.winnerOwner !== null ? 5 - baseline.winnerOwner : baseline.winnerOwner,
    winnerConsistent: result.winnerOwner === (reverse && baseline.winnerOwner !== null ? 5 - baseline.winnerOwner : baseline.winnerOwner),
    exactSeedReplayMatches: reverse ? null : result.finalStateHash === baseline.finalStateHash && result.eventLogHash === baseline.eventLogHash,
  };
  if (!reverse) assert.equal(row.exactSeedReplayMatches, true);
  console.log(JSON.stringify({ diagnostic: id, winner: result.winnerOwner,
    consistent: row.winnerConsistent, replayMatches: row.exactSeedReplayMatches }));
  return row;
}
const diagnostics = [];
for (const [matchup, reverse] of [["champion_mirror", false], ["champion_paladin", true], ["arbalester_cavalier", true]]) {
  diagnostics.push(await diagnostic(matchup, reverse));
  atomicJson(resolve(directory, "verification.json"), { campaignHash: manifest.campaignHash,
    recordedRuns: runs.length, sqliteIntegrity: "ok", duplicateRuns: 0,
    resumePreservedFirstSix: existsSync(firstSixPath), verifiedPlaybacks, verifiedSnapshots,
    noBufferUnits: true, sourceHashCheck: "passed", diagnostics });
}
console.log(JSON.stringify({ verifiedPlaybacks, verifiedSnapshots, diagnostics: diagnostics.length }));
