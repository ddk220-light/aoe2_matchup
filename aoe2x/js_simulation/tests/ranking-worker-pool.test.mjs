import test from "node:test";
import assert from "node:assert/strict";
import { RankingWorkerPool } from "../node/ranking-worker-pool.mjs";

const workerUrl = new URL(`data:text/javascript,${encodeURIComponent(`
  import { parentPort } from 'node:worker_threads';
  parentPort.on('message', ({ id, maxTicks, job }) => {
    parentPort.postMessage({ id, progress: { tick: 123, simulationSeconds: 2.05 } });
    if (!job.hang) setTimeout(() => parentPort.postMessage({ id, result: { maxTicks, seed: job.seed } }), 20);
  });
`)}`);

test("pool retains heartbeats until the matching final result and passes the configured tick limit", async () => {
  const pool = new RankingWorkerPool(1, { workerUrl, maxTicks: Number.MAX_SAFE_INTEGER });
  try {
    const result = await pool.run({ seed: 8 }, 5);
    assert.deepEqual(result.result, { maxTicks: Number.MAX_SAFE_INTEGER, seed: 8 });
    assert.equal(result.progress, undefined);
    assert.deepEqual(result.lastProgress, { tick: 123, simulationSeconds: 2.05 });
  } finally { await pool.close(); }
});

test("watchdog saves partial game time and replaces the worker for the next queued job", async () => {
  const pool = new RankingWorkerPool(1, { workerUrl });
  try {
    const timeout = pool.run({ hang: true }, 0.5);
    const next = pool.run({ seed: 9 }, 5);
    const result = await timeout;
    assert.equal(result.watchdog, true);
    assert.deepEqual(result.lastProgress, { tick: 123, simulationSeconds: 2.05 });
    assert.equal((await next).result.seed, 9);
  } finally { await pool.close(); }
});
