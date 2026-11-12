// Persistent worker: the same V3 engine, without per-tick playback serialization.
import { parentPort } from "node:worker_threads";
import { runHeadlessJob } from "./run-job.mjs";
import { hashCanonicalJson } from "../src/canonical-json.js";

parentPort.on("message", async ({ requestId, job }) => {
  try {
    let finalSnapshot;
    const result = await runHeadlessJob(job, job.verifyFinalSnapshot ? {
      onSnapshot(snapshot) { finalSnapshot = snapshot; },
    } : {});
    parentPort.postMessage({ requestId, result,
      ...(job.verifyFinalSnapshot ? { finalSnapshotHash: hashCanonicalJson(finalSnapshot) } : {}) });
  } catch (error) {
    parentPort.postMessage({ requestId, error: { name: error.name, message: error.message, stack: error.stack } });
  }
});
