import { parentPort } from "node:worker_threads";

import { runHeadlessJob } from "./run-job.mjs";

parentPort.on("message", async ({ index, job }) => {
  try {
    parentPort.postMessage({ index, result: await runHeadlessJob(job) });
  } catch (error) {
    parentPort.postMessage({
      index,
      error: {
        name: error?.name ?? "Error",
        message: error?.message ?? String(error),
        stack: error?.stack ?? null,
      },
    });
  }
});
