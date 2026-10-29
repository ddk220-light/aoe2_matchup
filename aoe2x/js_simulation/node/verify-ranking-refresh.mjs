// Validate the refresh's worker protocol and mechanical-equivalence reuse on its exact source.
import { readFileSync, writeFileSync, renameSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { RankingWorkerPool } from './ranking-worker-pool.mjs';
import { jobFor } from './full-ranking-campaign.mjs';
import { combatProfileHash } from './ranking-equivalence.mjs';
const [campaignPath, validationPath] = process.argv.slice(2);
const manifest = JSON.parse(readFileSync(resolve(campaignPath, 'manifest.json')));
const validation = JSON.parse(readFileSync(resolve(validationPath, 'manifest.json')));
const rows = readFileSync(resolve(validationPath, 'runs.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
const controlRows = rows.filter(row => row.kind === 'control' && row.seed === 0);
if (controlRows.length !== 10) throw new Error('all ten seed-zero pilot controls must exist');
const reportPath = resolve(validationPath, 'refresh-verification.json');
const report = existsSync(reportPath) ? JSON.parse(readFileSync(reportPath))
  : { sourceHashes: validation.sourceHashes, parity: [], equivalence: [], clock: null };
if (JSON.stringify(report.sourceHashes) !== JSON.stringify(validation.sourceHashes)) throw new Error('source changed since previous refresh checks');
const save = () => {
  const path = resolve(validationPath, 'refresh-verification.json');
  writeFileSync(path + '.tmp', JSON.stringify(report, null, 2) + '\n'); renameSync(path + '.tmp', path);
};
const assertSource = () => {
  for (const [name, expected] of Object.entries(validation.sourceHashes)) {
    const actual = createHash('sha256').update(readFileSync(new URL('../src/' + name, import.meta.url))).digest('hex');
    if (actual !== expected) throw new Error('source changed: ' + name);
  }
};
const pool = new RankingWorkerPool(1);
const clockPool = new RankingWorkerPool(1, {
  workerUrl: new URL('./collision-validation-worker.mjs', import.meta.url), maxTicks: Number.MAX_SAFE_INTEGER,
});
const matchups = new Map(manifest.matchups.map(row => [row.id, row]));
const run = async (pool, job) => {
  assertSource(); const started = performance.now(); const message = await pool.run(job);
  return { ...message, wallSeconds: (performance.now() - started) / 1000 };
};
try {
  for (const row of controlRows) {
    if (report.parity.some(check => check.matchupId === row.matchupId && check.exact)) continue;
    const actual = await run(pool, jobFor(manifest, matchups.get(row.matchupId), 0));
    const exact = ['finalStateHash', 'eventLogHash'].every(k => actual.result?.[k] === row.result?.[k]);
    report.parity.push({ matchupId: row.matchupId, seed: 0, exact, ...actual }); save();
    if (!exact) throw new Error('normal-worker parity failed');
  }
  const first = report.parity[0];
  if (!report.clock?.exact) {
  const clock = await run(clockPool, jobFor(manifest, matchups.get(first.matchupId), 0));
  report.clock = { ...clock, matchupId: first.matchupId, seed: 0,
    exact: ['finalStateHash', 'eventLogHash'].every(k => clock.result?.[k] === first.result?.[k]) }; save();
  if (!report.clock.exact) throw new Error('extended-clock pool parity failed');
  }
  for (const [a, b, slug, opponent] of [
    ['Spanish', 'Armenians', 'halberdier', 'champion'],
    ['Spanish', 'Berbers', 'imp_elite_skirm', 'arbalester'],
    ['Spanish', 'Khmer', 'hussar', 'arbalester'],
    ['Bengalis', 'Saxons', 'heavy_scorpion', 'champion'],
    ['Saracens', 'Khmer', 'hand_cannoneer', 'arbalester'],
  ]) {
    if (report.equivalence.some(check => check.civilizations[0] === a && check.civilizations[1] === b && check.slug === slug && check.opponent === opponent && check.exact)) continue;
    const pair = [a, b].map(civ => manifest.matchups.find(m => m.civilization === civ && m.slug === slug && m.opponent === opponent));
    if (pair.some(m => !m) || combatProfileHash(manifest.profiles[pair[0].teamKeys[0]].mechanics)
        !== combatProfileHash(manifest.profiles[pair[1].teamKeys[0]].mechanics)) throw new Error('invalid equivalence pair');
    const results = [];
    for (const m of pair) results.push(await run(pool, { ...jobFor(manifest, m, 0), verifyFinalSnapshot: true }));
    const [x, y] = results;
    const exact = Boolean(x.result && y.result && x.finalSnapshotHash === y.finalSnapshotHash
      && x.result.eventLogHash === y.result.eventLogHash && x.result.ticks === y.result.ticks
      && JSON.stringify(x.result.remainingByOwner) === JSON.stringify(y.result.remainingByOwner)
      && x.result.winnerOwner === y.result.winnerOwner);
    report.equivalence.push({ civilizations: [a, b], slug, opponent, seed: 0, exact, results }); save();
    if (!exact) throw new Error('equivalence parity failed');
  }
  report.allExact = report.parity.every(row => row.exact) && report.equivalence.every(row => row.exact) && report.clock.exact;
  save(); console.log(JSON.stringify({ allExact: report.allExact, parity: report.parity.length, equivalence: report.equivalence.length }));
} finally { await pool.close(); await clockPool.close(); }
