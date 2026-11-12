import { parentPort, workerData } from "node:worker_threads";
import { closeSync, openSync, writeSync, fsyncSync, createReadStream, createWriteStream } from "node:fs";
import { rename, unlink } from "node:fs/promises";
import { createGzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { runHeadlessJob } from "./run-job.mjs";

const { job, playbackPath } = workerData;
const partial = `${playbackPath}.partial`;
const fd = openSync(partial, "w");
let closed = false;
try {
  writeSync(fd, `${JSON.stringify({ type: "job", jobId: job.jobId, seed: job.seed })}\n`);
  const result = await runHeadlessJob(job, { onSnapshot(snapshot) {
    writeSync(fd, `${JSON.stringify(snapshot)}\n`);
    if (snapshot.tick % 120 === 0) parentPort.postMessage({ progress: snapshot.tick });
  } });
  writeSync(fd, `${JSON.stringify({ type: "result", ...result })}\n`);
  fsyncSync(fd);
  closeSync(fd);
  closed = true;
  const compressed = `${playbackPath}.tmp`;
  await pipeline(createReadStream(partial), createGzip(), createWriteStream(compressed));
  await rename(compressed, playbackPath);
  await unlink(partial);
  parentPort.postMessage({ result });
} catch (error) {
  parentPort.postMessage({ error: { name: error.name, message: error.message, stack: error.stack } });
} finally {
  if (!closed) closeSync(fd);
}
