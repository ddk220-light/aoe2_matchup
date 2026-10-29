import { readFileSync, writeFileSync } from "node:fs";
import { RankingWorkerPool } from "./ranking-worker-pool.mjs";

const directory = process.argv[2];
const output = process.argv[3];
const manifest = JSON.parse(readFileSync(`${directory}/manifest.json`, "utf8"));
const saved = readFileSync(`${directory}/runs.jsonl`, "utf8").trim().split("\n").map(JSON.parse);
const pool = new RankingWorkerPool(4);
const start = performance.now();
const checks = [];
try {
  await Promise.all(manifest.matchups.map(async matchup => {
    const job = { jobId: matchup.id, seed: 0,
      teams: matchup.teams.map(({ mechanics, count }) => ({ mechanics, count })),
      scenario: matchup.scenario, disableAiOrders: true, disableKiting: true,
      preserveOwnerOrientation: true, retainSnapshots: false };
    const message = await pool.run(job);
    const expected = saved.find(r => r.matchupId === matchup.id && r.seed === 0);
    const exact = message.result?.finalStateHash === expected.finalStateHash
      && message.result?.eventLogHash === expected.eventLogHash;
    checks.push({ matchupId: matchup.id, exact, error: message.error ?? null, watchdog: message.watchdog ?? false });
    console.log(JSON.stringify(checks.at(-1)));
  }));
  const report = { workers: 4, jobs: checks.length, elapsedSeconds: (performance.now() - start) / 1000,
    allExact: checks.every(c => c.exact), checks };
  writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
  if (!report.allExact) throw new Error("Headless/persistent-worker parity failed");
  console.log(JSON.stringify({ ...report, checks: undefined }));
} finally { await pool.close(); }
