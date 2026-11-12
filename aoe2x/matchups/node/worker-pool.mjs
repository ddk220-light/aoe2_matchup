// Fixed-size worker pool with a per-task wall-clock watchdog.
//
// Ported from RB:aoe2x/js_simulation/node/ranking-worker-pool.mjs
// (RankingWorkerPool, used by every 2026 civ-matchup runner). Behaviour kept:
// a task that exceeds its watchdog resolves `{watchdog: true, lastProgress}`
// and its worker is terminated and respawned; a crashed worker resolves
// `{error: {name: "WorkerExit"}}` and is respawned; results are never
// synthesised from a timeout. Change: `workerData` (the pinned engine's
// runtime root and hook targets) is passed to each spawned worker, and the
// default worker is ./battle-worker.mjs.
//
// "A wall-clock watchdog remains to recover stuck workers; it is not an
// outcome classifier." (RB civ-matchups-campaign-2026-10-31/CAMPAIGN_PLAN.md)
import { Worker } from 'node:worker_threads';

export class BattleWorkerPool {
  constructor(size = 4, { workerUrl, maxTicks, workerData, execArgv } = {}) {
    if (!Number.isSafeInteger(size) || size < 1) throw new Error('invalid worker count');
    this.workerUrl = workerUrl ?? new URL('./battle-worker.mjs', import.meta.url);
    this.maxTicks = maxTicks;
    this.workerData = workerData;
    this.execArgv = execArgv;
    this.queue = [];
    this.sequence = 0;
    this.closed = false;
    this.slots = Array.from({ length: size }, () => ({ worker: null, task: null }));
    for (const slot of this.slots) this.spawn(slot);
  }
  spawn(slot) {
    const worker = new Worker(this.workerUrl, {
      workerData: this.workerData, ...(this.execArgv ? { execArgv: this.execArgv } : {}),
    });
    slot.worker = worker;
    worker.on('message', message => {
      if (slot.worker !== worker || (message.requestId ?? message.id) !== slot.task?.requestId) return;
      const task = slot.task;
      if (message.progress) { task.lastProgress = message.progress; return; }
      clearTimeout(task.timer);
      slot.task = null;
      task.resolve({ ...message, ...(task.lastProgress ? { lastProgress: task.lastProgress } : {}) });
      this.dispatch();
    });
    const failed = error => {
      if (slot.worker !== worker) return;
      slot.worker = null;
      if (slot.task) {
        clearTimeout(slot.task.timer);
        slot.task.resolve({ error: { name: 'WorkerExit', message: String(error) }, lastProgress: slot.task.lastProgress });
        slot.task = null;
      }
      worker.terminate();
      if (!this.closed) { this.spawn(slot); this.dispatch(); }
    };
    worker.on('error', failed);
    worker.on('exit', code => failed(`worker exited ${code}`));
  }
  run(job, timeoutSeconds = 120) {
    if (this.closed) throw new Error('pool closed');
    return new Promise(resolve => {
      this.queue.push({ requestId: ++this.sequence, job, timeoutSeconds, resolve });
      this.dispatch();
    });
  }
  dispatch() {
    if (this.closed) return;
    for (const slot of this.slots) {
      if (slot.task || !slot.worker || !this.queue.length) continue;
      const task = this.queue.shift();
      slot.task = task;
      task.timer = setTimeout(() => {
        const worker = slot.worker;
        slot.worker = null;
        slot.task = null;
        task.resolve({ watchdog: true, lastProgress: task.lastProgress });
        worker.terminate().finally(() => {
          if (!this.closed) { this.spawn(slot); this.dispatch(); }
        });
      }, task.timeoutSeconds * 1000);
      slot.worker.postMessage({ requestId: task.requestId, id: task.requestId, job: task.job, maxTicks: this.maxTicks });
    }
  }
  async close() {
    this.closed = true;
    for (const task of this.queue.splice(0)) task.resolve({ error: { name: 'PoolClosed', message: 'pool closed' } });
    await Promise.all(this.slots.map(slot => {
      const worker = slot.worker;
      slot.worker = null;
      if (slot.task) {
        clearTimeout(slot.task.timer);
        slot.task.resolve({ error: { name: 'PoolClosed', message: 'pool closed' } });
        slot.task = null;
      }
      return worker?.terminate();
    }));
  }
}
