import { Worker } from "node:worker_threads";

export class RankingWorkerPool {
  constructor(size = 4, { workerUrl, maxTicks } = {}) {
    if (!Number.isSafeInteger(size) || size < 1) throw new Error("invalid worker count");
    this.workerUrl = workerUrl ?? new URL("./ranking-pool-worker.mjs", import.meta.url);
    this.maxTicks = maxTicks;
    this.queue = [];
    this.sequence = 0;
    this.closed = false;
    this.slots = Array.from({ length: size }, () => ({ worker: null, task: null }));
    for (const slot of this.slots) this.spawn(slot);
  }
  spawn(slot) {
    const worker = new Worker(this.workerUrl);
    slot.worker = worker;
    worker.on("message", message => {
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
        slot.task.resolve({ error: { name: "WorkerExit", message: String(error) }, lastProgress: slot.task.lastProgress });
        slot.task = null;
      }
      worker.terminate();
      if (!this.closed) { this.spawn(slot); this.dispatch(); }
    };
    worker.on("error", failed);
    worker.on("exit", code => failed(`worker exited ${code}`));
  }
  run(job, timeoutSeconds = 120) {
    if (this.closed) throw new Error("pool closed");
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
    for (const task of this.queue.splice(0)) task.resolve({ error: { name: "PoolClosed", message: "pool closed" } });
    await Promise.all(this.slots.map(slot => {
      const worker = slot.worker;
      slot.worker = null;
      if (slot.task) {
        clearTimeout(slot.task.timer);
        slot.task.resolve({ error: { name: "PoolClosed", message: "pool closed" } });
        slot.task = null;
      }
      return worker?.terminate();
    }));
  }
}
