import { Worker } from 'node:worker_threads';
import { readFileSync, readdirSync, mkdirSync, existsSync, openSync, closeSync, fsyncSync,
  appendFileSync, writeFileSync, renameSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { jobFor } from './full-ranking-campaign.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, all) =>
  index % 2 ? pairs : [...pairs, [value, all[index + 1]]], []));
const campaign = resolve(args['--campaign']);
const diagnostics = resolve(args['--diagnostics']);
const output = resolve(args['--output']);
const mode = args['--mode'] ?? 'smoke';
const workerCount = Number(args['--workers'] ?? 2);
const manifest = JSON.parse(readFileSync(resolve(campaign, 'manifest.json')));
const matchups = new Map(manifest.matchups.map(row => [row.id, row]));
const originals = readdirSync(resolve(campaign, 'runs')).filter(name => name.endsWith('.jsonl')).flatMap(name =>
  readFileSync(resolve(campaign, 'runs', name), 'utf8').trim().split('\n').filter(Boolean).map(line => JSON.parse(line)));
const diagnosticRows = JSON.parse(readFileSync(resolve(diagnostics, 'summary.json')));
const sourceSha256 = createHash('sha256').update(readFileSync(new URL('../src/combat/collision.js', import.meta.url))).digest('hex');
if (process.version !== manifest.nodeVersion) throw new Error('validation Node version differs from campaign');
for (const entry of manifest.runtimeFiles.filter(entry => entry.path.includes('/src/')
  || entry.path.endsWith('/node/run-job.mjs'))) {
  if (entry.path.endsWith('/src/combat/collision.js')) continue;
  const path = new URL(`../../../${entry.path}`, import.meta.url);
  const actual = createHash('sha256').update(readFileSync(path)).digest('hex');
  if (actual !== entry.sha256) throw new Error(`non-collision runtime changed: ${entry.path}`);
}
const environment = Object.fromEntries(Object.keys(process.env).filter(key => key.startsWith('AOE2X_EXP_'))
  .sort().map(key => [key, process.env[key]]));
if (JSON.stringify(environment) !== JSON.stringify(manifest.simulationEnvironment)) throw new Error('simulation environment changed');
const named = row => matchups.get(row.matchupId).teamKeys.map(key => {
  const mechanics = manifest.profiles[key].mechanics; return `${mechanics.civilization} ${mechanics.unit_name}`;
});
const pilots = originals.filter(row => row.provenance?.kind === 'pilot');
const flagged = originals.filter(row => ['undecided', 'error'].includes(row.outcome));
let tasks;
if (mode === 'smoke') {
  const selected = [
    ['Vikings Mounted Crossbowman', 'Saracens Heavy Cavalry Archer'],
    ['Franks Crossbowman', 'Spanish Hussar'],
    ['Chinese Heavy Scorpion', 'Spanish Elite Skirmisher'],
    ['Mayans Elite Plumed Archer', 'Saracens Heavy Cavalry Archer'],
  ].map(teams => flagged.find(row => row.seed === 0 && JSON.stringify(named(row)) === JSON.stringify(teams)));
  if (selected.some(row => !row)) throw new Error('missing smoke case');
  tasks = [
    ...pilots.filter(row => row.seed === 0).slice(0, 3).map(row => ({ kind: 'control', row, expected: row.result, maxTicks: 9000 })),
    ...selected.flatMap(row => {
      const diagnostic = diagnosticRows.find(candidate => candidate.matchupId === row.matchupId && candidate.seed === row.seed);
      if (!diagnostic?.result) throw new Error('missing diagnostic prefix');
      return [
        { kind: 'prefix', row, expected: diagnostic.result, maxTicks: diagnostic.result.ticks },
        { kind: 'completion', row, maxTicks: Number.MAX_SAFE_INTEGER },
      ];
    }),
  ];
} else if (mode === 'full') {
  tasks = [
    ...pilots.map(row => ({ kind: 'control', row, expected: row.result, maxTicks: 9000 })),
    ...diagnosticRows.filter(row => row.result).map(diagnostic => ({ kind: 'prefix',
      row: originals.find(row => row.matchupId === diagnostic.matchupId && row.seed === diagnostic.seed),
      expected: diagnostic.result, maxTicks: diagnostic.result.ticks })),
    ...flagged.map(row => ({ kind: 'completion', row, maxTicks: Number.MAX_SAFE_INTEGER })),
  ];
} else throw new Error('mode must be smoke or full');
mkdirSync(output, { recursive: true });
writeFileSync(resolve(output, '.gitignore'), '*.log\n*.tmp\n');
const journal = resolve(output, 'runs.jsonl');
const records = existsSync(journal) ? readFileSync(journal, 'utf8').trim().split('\n')
  .filter(Boolean).map(line => JSON.parse(line)) : [];
if (records.some(row => row.sourceSha256 !== sourceSha256)) throw new Error('candidate changed; use a new output directory');
const key = task => `${task.kind}:${task.row?.matchupId ?? task.matchupId}:${task.row?.seed ?? task.seed}:${task.maxTicks}`;
const done = new Set(records.map(key));
const pending = tasks.filter(task => !done.has(key(task)));
const atomic = (name, value) => {
  const path = resolve(output, name); writeFileSync(`${path}.tmp`, JSON.stringify(value, null, 2) + '\n'); renameSync(`${path}.tmp`, path);
};
atomic('manifest.json', { sourceSha256, campaignHash: manifest.campaignHash, mode, workers: workerCount,
  maxWallSeconds: 120, tasks: tasks.map(task => ({ kind: task.kind, matchupId: task.row.matchupId, seed: task.row.seed, maxTicks: task.maxTicks })) });
let next = 0, failed = false;
const workers = new Set();
const exportStatus = () => atomic('progress.json', { updatedAt: new Date().toISOString(), sourceSha256,
  completed: records.length, total: tasks.length, mismatches: records.filter(r => r.exact === false).length,
  decided: records.filter(r => r.kind === 'completion' && ['win', 'draw'].includes(r.result?.outcome)).length,
  processingTimeouts: records.filter(r => r.watchdog).length,
  expectedPrefixStops: records.filter(r => r.kind === 'prefix' && r.result?.outcome === 'timeout').length,
  engineErrors: records.filter(r => r.error).length, failed });
function spawn() {
  const worker = new Worker(new URL('./collision-validation-worker.mjs', import.meta.url)); workers.add(worker); return worker;
}
async function execute(worker, task, id) {
  const started = performance.now(); let progress = null;
  const message = await new Promise(resolveTask => {
    const cleanup = () => { clearTimeout(timer); worker.off('message', received); worker.off('error', errored); };
    const received = value => {
      if (value.id !== id) return;
      if (value.progress) { progress = value.progress; return; }
      cleanup(); resolveTask(value);
    };
    const errored = error => { cleanup(); resolveTask({ error: { message: error.message } }); };
    const timer = setTimeout(() => { cleanup(); resolveTask({ watchdog: true }); }, 120000);
    worker.on('message', received); worker.on('error', errored);
    worker.postMessage({ id, job: jobFor(manifest, matchups.get(task.row.matchupId), task.row.seed), maxTicks: task.maxTicks });
  });
  const exact = task.expected ? ['finalStateHash', 'eventLogHash'].every(key => message.result?.[key] === task.expected[key]) : null;
  const record = { sourceSha256, kind: task.kind, matchupId: task.row.matchupId, seed: task.row.seed,
    teams: named(task.row), wallSeconds: (performance.now() - started) / 1000, originalWallSeconds: task.row.wallSeconds,
    maxTicks: task.maxTicks, exact, lastProgress: progress, ...message };
  const fd = openSync(journal, 'a');
  try { appendFileSync(fd, JSON.stringify(record) + '\n'); fsyncSync(fd); } finally { closeSync(fd); }
  records.push(record); exportStatus();
  console.log(JSON.stringify({ completed: records.length, total: tasks.length, kind: record.kind,
    teams: record.teams, seed: record.seed, wallSeconds: record.wallSeconds, exact,
    outcome: record.result?.outcome, gameSeconds: (record.result?.ticks ?? progress?.tick) / 60, error: record.error?.message, watchdog: record.watchdog }));
  if (exact === false) failed = true;
  return message.watchdog || message.error;
}
try {
  await Promise.all(Array.from({ length: workerCount }, async () => {
    let worker = spawn();
    while (!failed && next < pending.length) {
      const currentSha = createHash('sha256').update(readFileSync(new URL('../src/combat/collision.js', import.meta.url))).digest('hex');
      if (currentSha !== sourceSha256) throw new Error('candidate changed during validation');
      const id = next++, task = pending[id];
      if (await execute(worker, task, id)) { await worker.terminate(); workers.delete(worker); worker = spawn(); }
    }
  }));
} finally { await Promise.all([...workers].map(worker => worker.terminate())); }
exportStatus();
if (failed) process.exitCode = 1;
