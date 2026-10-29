import { Worker } from "node:worker_threads";

export class RankingWorkerPool {
  constructor(size = 4) {
    if (!Number.isSafeInteger(size) || size < 1) throw new Error("invalid worker count");
    this.queue = [];
    this.sequence = 0;
    this.closed = false;
    this.slots = Array.from({ length: size }, () => ({ worker: null, task: null }));
    for (const slot of this.slots) this.spawn(slot);
  }
  spawn(slot) {
    const worker = new Worker(new URL("./ranking-pool-worker.mjs", import.meta.url));
    slot.worker = worker;
    worker.on("message", message => {
      if (slot.worker !== worker || message.requestId !== slot.task?.requestId) return;
      const task = slot.task;
      clearTimeout(task.timer);
      slot.task = null;
      task.resolve(message);
      this.dispatch();
    });
    const failed = error => {
      if (slot.worker !== worker) return;
      slot.worker = null;
      if (slot.task) {
        clearTimeout(slot.task.timer);
        slot.task.resolve({ error: { name: "WorkerExit", message: String(error) } });
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
        task.resolve({ watchdog: true });
        worker.terminate().finally(() => {
          if (!this.closed) { this.spawn(slot); this.dispatch(); }
        });
      }, task.timeoutSeconds * 1000);
      slot.worker.postMessage({ requestId: task.requestId, job: task.job });
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
