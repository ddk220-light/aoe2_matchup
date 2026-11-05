import { Worker } from 'node:worker_threads';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { jobFor } from './full-ranking-campaign.mjs';

const [baselineRoot, campaignPath, outputPath] = process.argv.slice(2);
const output = resolve(outputPath); mkdirSync(output, { recursive: true });
const manifest = JSON.parse(readFileSync(resolve(campaignPath, 'manifest.json')));
const baselineSourceSha256 = createHash('sha256').update(readFileSync(resolve(baselineRoot,
  'aoe2x/js_simulation/src/combat/collision.js'))).digest('hex');
const pairs = [
  ['Vikings|heavy_mounted_crossbowman', 'hca'],
  ['Franks|arbalester', 'hussar'],
  ['Chinese|heavy_scorpion', 'skirmisher'],
];
for (const [unit, opponent] of pairs) {
  const matchup = manifest.matchups.find(row => row.teamKeys[0] === unit && row.opponent === opponent);
  if (!matchup) throw new Error(`missing reference ${unit}/${opponent}`);
  const path = resolve(output, `${matchup.id}_0.json`);
  if (existsSync(path)) continue;
  const worker = new Worker(new URL('./collision-validation-worker.mjs', import.meta.url), {
    workerData: { runtimeRoot: resolve(baselineRoot) },
  });
  const started = performance.now(); let lastProgress;
  const message = await new Promise(resolveResult => {
    const timer = setTimeout(() => resolveResult({ watchdog: true }), 600000);
    worker.on('message', value => {
      if (value.progress) { lastProgress = value.progress; return; }
      clearTimeout(timer); resolveResult(value);
    });
    worker.on('error', error => { clearTimeout(timer); resolveResult({ error: { message: error.message } }); });
    worker.postMessage({ id: 0, job: jobFor(manifest, matchup, 0), maxTicks: Number.MAX_SAFE_INTEGER });
  });
  await worker.terminate();
  const row = { baselineSourceSha256, matchupId: matchup.id, seed: 0, teams: matchup.teamKeys,
    wallSeconds: (performance.now() - started) / 1000, lastProgress, ...message };
  writeFileSync(path, JSON.stringify(row, null, 2) + '\n');
  console.log(JSON.stringify({ teams: matchup.teamKeys, wallSeconds: row.wallSeconds, outcome: row.result?.outcome,
    gameSeconds: row.result?.ticks / 60, error: row.error, watchdog: row.watchdog }));
}
