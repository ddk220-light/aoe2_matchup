#!/usr/bin/env node
// Run seeded battles against a pinned engine. Generic seam for the step-3 runner.
//
//   node [--max-old-space-size=3072] aoe2x/matchups/node/run-battles.mjs \
//     --engine aoe2x/matchups/engines/frozen-civ-matchups-v3 \
//     --jobs jobs.jsonl --out results.jsonl [--workers 4] \
//     [--timeout-steps 180,600,1800,3600] [--node-policy verified|exact|warn] \
//     [--environment '{}'] [--progress-dir DIR]
//
// Each input line is {"key": <string>, "payload": <runHeadlessJob payload>}.
// Each output line is {"key", "ok", "result"?, "attempts": [...], "wallSeconds"}.
// Like execute() in RB run-forecast-validation.mjs: a seed gets one attempt per
// watchdog step (180 -> 600 -> 1,800 -> 3,600 s); only a finished `win`/`draw`
// is a result; after the last step the seed is `exhausted`. Timeouts and errors
// are never turned into results. The tick ceiling is lifted
// (maxTicks = Number.MAX_SAFE_INTEGER), as in every 2026 civ-matchup runner.
//
// Serve mode (used by the Python run orchestrator, aoe2x/matchups/runner.py):
//
//   node run-battles.mjs --serve --engine DIR [--workers 4] [--node-policy P] [--environment '{}']
//
// prints one {"hello": {...engine, node...}} line, then reads requests
// {"key", "payload", "limitSeconds", "diagnosticProgressPath"?} on stdin and
// answers each with ONE attempt: {"key", "ok": true, "result", "startedAt",
// "wallSeconds"} or {"key", "ok": false, "watchdog", "error",
// "unfinishedOutcome", "lastProgress", "startedAt", "wallSeconds"}. The caller
// owns the watchdog escalation and the attempt log, so a kill of either
// process loses at most the attempts in flight. On stdin EOF, or when the
// parent process disappears, the pool is closed and the process exits.
import { readFileSync, openSync, appendFileSync, fsyncSync, closeSync, mkdirSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { BattleWorkerPool } from './worker-pool.mjs';
import { loadEngine } from './engine.mjs';

function options(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i].startsWith('--')) throw new Error(`unexpected argument ${argv[i]}`);
    out[argv[i].slice(2)] = argv[i + 1];
  }
  return out;
}

export function compactResult(r) {
  return {
    outcome: r.outcome, winnerOwner: r.winnerOwner, ticks: r.ticks,
    startingHpByOwner: r.startingHpByOwner, remainingByOwner: r.remainingByOwner,
    finalStateHash: r.finalStateHash, eventLogHash: r.eventLogHash, family: r.family,
  };
}

export async function runBattles({ engineDir, jobs, onResult, workers = 4, timeoutSteps = [180, 600, 1800, 3600],
  nodePolicy = 'verified', environment = {}, progressDir = null }) {
  const loaded = loadEngine(engineDir, { nodePolicy, environment });
  if (loaded.node.warning) console.error(JSON.stringify({ warning: loaded.node.warning }));
  const pool = new BattleWorkerPool(Math.max(1, Math.min(workers, jobs.length || 1)), {
    maxTicks: Number.MAX_SAFE_INTEGER, workerData: loaded.workerData,
  });
  if (progressDir) mkdirSync(progressDir, { recursive: true });
  try {
    await Promise.all(jobs.map(async ({ key, payload }) => {
      const attempts = [];
      const start = performance.now();
      for (let attempt = 0; attempt < timeoutSteps.length; attempt++) {
        const limitSeconds = timeoutSteps[attempt], begun = performance.now(), startedAt = new Date().toISOString();
        const diagnosticProgressPath = progressDir
          ? resolve(progressDir, `${String(key).replace(/[^\w.-]/g, '_')}-${Date.now()}-${attempt + 1}.jsonl`) : undefined;
        const reply = await pool.run({ ...payload, ...(diagnosticProgressPath ? { diagnosticProgressPath } : {}) }, limitSeconds);
        const wallSeconds = (performance.now() - begun) / 1000;
        if (reply.result && ['win', 'draw'].includes(reply.result.outcome)) {
          onResult({ key, ok: true, result: compactResult(reply.result), attempts, startedAt,
            wallSeconds, totalWallSeconds: (performance.now() - start) / 1000 });
          return;
        }
        attempts.push({ attempt: attempt + 1, startedAt, wallSeconds, limitSeconds, watchdog: reply.watchdog ?? false,
          error: reply.error ?? null, unfinishedOutcome: reply.result?.outcome ?? null,
          lastProgress: reply.lastProgress ?? null, exhausted: attempt === timeoutSteps.length - 1,
          progressPath: diagnosticProgressPath ?? null });
      }
      onResult({ key, ok: false, exhausted: true, attempts, totalWallSeconds: (performance.now() - start) / 1000 });
    }));
  } finally { await pool.close(); }
  return loaded;
}

export async function serve({ engineDir, workers = 4, nodePolicy = 'verified', environment = {},
  input = process.stdin, write = line => process.stdout.write(line + '\n') }) {
  const loaded = loadEngine(engineDir, { nodePolicy, environment });
  const pool = new BattleWorkerPool(Math.max(1, workers), {
    maxTicks: Number.MAX_SAFE_INTEGER, workerData: loaded.workerData,
  });
  const parent = process.ppid;
  const watch = setInterval(() => { if (process.ppid !== parent) process.exit(70); }, 1000);
  watch.unref();
  write(JSON.stringify({ hello: {
    engineId: loaded.engine.engineId, physicsVersion: loaded.engine.physicsVersion,
    executionVersion: loaded.engine.executionVersion, filesDigest: loaded.engine.filesDigest,
    node: loaded.node, workers: pool.slots.length, pid: process.pid,
  } }));
  const pending = new Set();
  const handle = async ({ key, payload, limitSeconds, diagnosticProgressPath }) => {
    const startedAt = new Date().toISOString(), begun = performance.now();
    const reply = await pool.run({ ...payload, ...(diagnosticProgressPath ? { diagnosticProgressPath } : {}) }, limitSeconds);
    const wallSeconds = (performance.now() - begun) / 1000;
    if (reply.result && ['win', 'draw'].includes(reply.result.outcome)) {
      write(JSON.stringify({ key, ok: true, result: compactResult(reply.result), startedAt, wallSeconds }));
    } else {
      write(JSON.stringify({ key, ok: false, watchdog: reply.watchdog ?? false, error: reply.error ?? null,
        unfinishedOutcome: reply.result?.outcome ?? null, lastProgress: reply.lastProgress ?? null,
        startedAt, wallSeconds }));
    }
  };
  try {
    for await (const line of createInterface({ input, crlfDelay: Infinity })) {
      if (!line.trim()) continue;
      const task = handle(JSON.parse(line)).catch(error => write(JSON.stringify({ fatal: String(error?.stack ?? error) })));
      pending.add(task); task.finally(() => pending.delete(task));
    }
  } finally {
    // EOF: the orchestrator is gone or done. In-flight attempts are abandoned (never results).
    clearInterval(watch);
    await pool.close();
  }
}

async function main() {
  const o = options(process.argv.slice(2).flatMap(a => a === '--serve' ? ['--serve', 'true'] : [a]));
  if (o.serve) {
    if (!o.engine) throw new Error('--engine is required');
    await serve({ engineDir: resolve(o.engine), workers: Number(o.workers ?? 4), nodePolicy: o['node-policy'] ?? 'verified',
      environment: JSON.parse(o.environment ?? '{}') });
    process.exit(0);
  }
  for (const k of ['engine', 'jobs', 'out']) if (!o[k]) throw new Error(`--${k} is required`);
  const jobs = readFileSync(o.jobs, 'utf8').split('\n').filter(Boolean).map(JSON.parse);
  const fd = openSync(o.out, 'a');
  const write = row => { appendFileSync(fd, JSON.stringify(row) + '\n'); fsyncSync(fd); };
  try {
    const loaded = await runBattles({
      engineDir: resolve(o.engine), jobs, onResult: write,
      workers: Number(o.workers ?? 4),
      timeoutSteps: (o['timeout-steps'] ?? '180,600,1800,3600').split(',').map(Number),
      nodePolicy: o['node-policy'] ?? 'verified',
      environment: JSON.parse(o.environment ?? '{}'),
      progressDir: o['progress-dir'] ?? null,
    });
    console.log(JSON.stringify({ engineId: loaded.engine.engineId, node: loaded.node, jobs: jobs.length }));
  } finally { closeSync(fd); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main();
