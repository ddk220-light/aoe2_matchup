// Persistent worker: the same V3 engine, without per-tick playback serialization.
import { parentPort } from "node:worker_threads";
import { runHeadlessJob } from "./run-job.mjs";

parentPort.on("message", async ({ requestId, job }) => {
  try {
    const result = await runHeadlessJob(job);
    parentPort.postMessage({ requestId, result });
  } catch (error) {
    parentPort.postMessage({ requestId, error: { name: error.name, message: error.message, stack: error.stack } });
  }
});
