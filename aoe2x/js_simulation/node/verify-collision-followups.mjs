// Separately versioned behavior checks; these are not parity-only optimizations.
import { Worker } from 'node:worker_threads';
import { readFileSync, readdirSync, mkdirSync, existsSync, writeFileSync,
  openSync, appendFileSync, fsyncSync, closeSync, renameSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { jobFor } from './full-ranking-campaign.mjs';

const [campaignPath, outputPath, performanceOutput] = process.argv.slice(2);
const campaign = resolve(campaignPath), output = resolve(outputPath);
const manifest = JSON.parse(readFileSync(resolve(campaign, 'manifest.json')));
const matchups = new Map(manifest.matchups.map(row => [row.id, row]));
const originals = readdirSync(resolve(campaign, 'runs')).filter(name => name.endsWith('.jsonl')).flatMap(name =>
  readFileSync(resolve(campaign, 'runs', name), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse));
const hashes = () => Object.fromEntries(['collision.js', 'world.js', 'contact-reservations.js'].map(name =>
  [name, createHash('sha256').update(readFileSync(new URL('../src/combat/' + name, import.meta.url))).digest('hex')]));
const sourceHashes = hashes(), sourceKey = JSON.stringify(sourceHashes);
const selected = [
  ['m_5ae9ad79f7d6a5ddeeb8', 2], ['m_ed79846db7272bf05960', 2],
  ['m_5c951a7bad151e048fb7', 0], ['m_9f24a61daa053dd6cbde', 0],
  ['m_bf1ed614717ec1806ca0', 0],
];
if (performanceOutput) {
  const performanceRows = readFileSync(resolve(performanceOutput, 'runs.jsonl'), 'utf8').trim()
    .split('\n').filter(Boolean).map(JSON.parse);
  for (const row of performanceRows.filter(row => row.kind === 'completion' && (row.watchdog || row.error))) {
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
atomic('manifest.json', { sourceHashes, campaignHash: manifest.campaignHash, maxWallSeconds: 120,
  note: 'Behavior corrections; changed hashes are reported, never substituted into the frozen campaign.',
  tasks: tasks.map(({ kind, row }) => ({ kind, matchupId: row.matchupId, seed: row.seed })) });
const done = new Set(records.map(row => `${row.kind}:${row.matchupId}:${row.seed}`));
let worker = new Worker(new URL('./collision-validation-worker.mjs', import.meta.url));
try {
  for (const task of tasks) {
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
      exact: record.exact, wallSeconds: record.wallSeconds, gameSeconds: record.result?.ticks / 60,
      outcome: record.result?.outcome, error: record.error, watchdog: record.watchdog }));
    if (message.error || message.watchdog) { await worker.terminate(); worker = new Worker(new URL('./collision-validation-worker.mjs', import.meta.url)); }
  }
} finally { await worker.terminate(); }
