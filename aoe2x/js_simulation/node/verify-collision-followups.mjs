// Separately versioned behavior checks; these are not parity-only optimizations.
import { Worker } from 'node:worker_threads';
import { readFileSync, readdirSync, mkdirSync, existsSync, writeFileSync,
  openSync, appendFileSync, fsyncSync, closeSync, renameSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { jobFor } from './full-ranking-campaign.mjs';

const [campaignPath, outputPath, performanceOutput, ...options] = process.argv.slice(2);
const allFlagged = options.includes('--all-flagged');
const workerCount = Number(options.find(value => value.startsWith('--workers='))?.split('=')[1] ?? 1);
if (!Number.isInteger(workerCount) || workerCount < 1 || workerCount > 4) throw new Error('workers must be 1..4');
if (allFlagged && !performanceOutput) throw new Error('--all-flagged requires performance results');
const campaign = resolve(campaignPath), output = resolve(outputPath);
const manifest = JSON.parse(readFileSync(resolve(campaign, 'manifest.json')));
const matchups = new Map(manifest.matchups.map(row => [row.id, row]));
const originals = readdirSync(resolve(campaign, 'runs')).filter(name => name.endsWith('.jsonl')).flatMap(name =>
  readFileSync(resolve(campaign, 'runs', name), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse));
const sourceRoot = new URL('../src/', import.meta.url);
const hashes = () => Object.fromEntries(readdirSync(sourceRoot, { recursive: true })
  .filter(name => name.endsWith('.js')).sort().map(name =>
    [name, createHash('sha256').update(readFileSync(new URL(name, sourceRoot))).digest('hex')]));
const sourceHashes = hashes(), sourceKey = JSON.stringify(sourceHashes);
const selected = allFlagged ? [] : [
  ['m_5ae9ad79f7d6a5ddeeb8', 2], ['m_ed79846db7272bf05960', 2],
  ['m_5c951a7bad151e048fb7', 0], ['m_9f24a61daa053dd6cbde', 0],
  ['m_bf1ed614717ec1806ca0', 0],
];
if (performanceOutput) {
  const performanceRows = readFileSync(resolve(performanceOutput, 'runs.jsonl'), 'utf8').trim()
    .split('\n').filter(Boolean).map(JSON.parse);
  for (const row of performanceRows.filter(row => row.kind === 'completion' && (allFlagged || row.watchdog || row.error))) {
    if (!selected.some(([id, seed]) => id === row.matchupId && seed === row.seed)) selected.push([row.matchupId, row.seed]);
  }
}
const tasks = [...originals.filter(row => row.provenance?.kind === 'pilot').map(row => ({ kind: 'control', row })),
  ...selected.map(([matchupId, seed]) => ({ kind: 'anomaly',
    row: originals.find(row => row.matchupId === matchupId && row.seed === seed) }))];
if (tasks.some(task => !task.row)) throw new Error('missing baseline row');
mkdirSync(output, { recursive: true });
const journal = resolve(output, 'runs.jsonl');
const records = existsSync(journal) ? readFileSync(journal, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
if (records.some(row => JSON.stringify(row.sourceHashes) !== sourceKey)) throw new Error('source changed; choose a new output');
const atomic = (name, value) => {
  const path = resolve(output, name); writeFileSync(path + '.tmp', JSON.stringify(value, null, 2) + '\n'); renameSync(path + '.tmp', path);
};
atomic('manifest.json', { sourceHashes, campaignHash: manifest.campaignHash, maxWallSeconds: 120, workerCount, allFlagged,
  note: 'Behavior corrections; changed hashes are reported, never substituted into the frozen campaign.',
  tasks: tasks.map(({ kind, row }) => ({ kind, matchupId: row.matchupId, seed: row.seed })) });
const done = new Set(records.map(row => `${row.kind}:${row.matchupId}:${row.seed}`));
const pending = tasks.filter(({ kind, row }) => !done.has(`${kind}:${row.matchupId}:${row.seed}`));
let nextTask = 0;
async function runLane() {
  let worker = new Worker(new URL('./collision-validation-worker.mjs', import.meta.url));
  try {
  while (nextTask < pending.length) {
    const task = pending[nextTask++];
    const row = task.row, key = `${task.kind}:${row.matchupId}:${row.seed}`;
    if (done.has(key)) continue;
    if (JSON.stringify(hashes()) !== sourceKey) throw new Error('source changed while checking');
    const started = performance.now(); let lastProgress;
    const message = await new Promise(resolveTask => {
      const finish = value => { clearTimeout(timer); worker.off('message', receive); worker.off('error', error); resolveTask(value); };
      const receive = value => { if (value.progress) lastProgress = value.progress; else finish(value); };
      const error = error => finish({ error: { message: error.message } });
      const timer = setTimeout(() => finish({ watchdog: true }), 120000);
      worker.on('message', receive); worker.on('error', error);
      worker.postMessage({ id: key, job: jobFor(manifest, matchups.get(row.matchupId), row.seed),
        maxTicks: task.kind === 'control' ? 9000 : Number.MAX_SAFE_INTEGER });
    });
    const record = { kind: task.kind, matchupId: row.matchupId, seed: row.seed, sourceHashes,
      teams: matchups.get(row.matchupId).teamKeys, wallSeconds: (performance.now() - started) / 1000,
      lastProgress, baseline: row.result ?? null,
      exact: task.kind === 'control' ? ['finalStateHash', 'eventLogHash'].every(key => row.result?.[key] === message.result?.[key]) : null,
      ...message };
    const fd = openSync(journal, 'a');
    try { appendFileSync(fd, JSON.stringify(record) + '\n'); fsyncSync(fd); } finally { closeSync(fd); }
    records.push(record);
    atomic('progress.json', { updatedAt: new Date().toISOString(), completed: records.length, total: tasks.length,
      exactControls: records.filter(row => row.exact === true).length,
      changedControls: records.filter(row => row.exact === false).length,
      decidedAnomalies: records.filter(row => row.kind === 'anomaly' && ['win', 'draw'].includes(row.result?.outcome)).length,
      errors: records.filter(row => row.error).length, watchdogs: records.filter(row => row.watchdog).length });
    console.log(JSON.stringify({ completed: records.length, kind: record.kind, teams: record.teams, seed: row.seed,
      exact: record.exact, wallSeconds: record.wallSeconds,
      gameSeconds: (record.result?.ticks ?? record.lastProgress?.tick) / 60,
      outcome: record.result?.outcome, error: record.error, watchdog: record.watchdog }));
    if (message.error || message.watchdog) { await worker.terminate(); worker = new Worker(new URL('./collision-validation-worker.mjs', import.meta.url)); }
  }
  } finally { await worker.terminate(); }
}
const lanes = await Promise.allSettled(Array.from({ length: workerCount }, runLane));
const failures = lanes.filter(result => result.status === 'rejected');
if (failures.length) throw new AggregateError(failures.map(result => result.reason));
