#!/usr/bin/env node
import { availableParallelism } from "node:os";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { Worker } from "node:worker_threads";

import { runHeadlessJob } from "./run-job.mjs";

function argumentsFrom(argv) {
  const result = { workers: availableParallelism(), input: "-" };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--workers") result.workers = Number(argv[++index]);
    else if (arg === "--input") result.input = argv[++index];
    else throw new RangeError(`unknown argument ${arg}`);
  }
  if (!Number.isSafeInteger(result.workers) || result.workers < 1) {
    throw new RangeError("--workers must be a positive integer");
  }
  return result;
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

export function expandJobs(document) {
  const jobs = Array.isArray(document) ? document : (document.jobs ?? [document]);
  return jobs.flatMap((job) => {
    if (Array.isArray(job.seeds)) {
      return job.seeds.map((seed) => ({ ...job, seed, seeds: undefined }));
    }
    if (Number.isSafeInteger(job.seeds) && job.seeds > 0) {
      return Array.from({ length: job.seeds }, (_, seed) => ({ ...job, seed, seeds: undefined }));
    }
    return [job];
  });
}

function failedResult(job, error) {
  return {
    jobId: job?.jobId ?? null,
    seed: job?.seed ?? null,
    error: {
      name: error?.name ?? "Error",
      message: error?.message ?? String(error),
    },
  };
}

export async function parallelJobs(jobs, workerCount) {
  if (jobs.length <= 1 || workerCount === 1) {
    const rows = [];
    for (const job of jobs) {
      try {
        rows.push(await runHeadlessJob(job));
      } catch (error) {
        rows.push(failedResult(job, error));
      }
    }
    return rows;
  }
  const results = new Array(jobs.length);
  let next = 0;
  let completed = 0;
  const workers = [];
  return new Promise((resolve, reject) => {
    const stop = () => workers.forEach((worker) => worker.terminate());
    const dispatch = (worker) => {
      if (next >= jobs.length) return;
      const index = next++;
      worker.postMessage({ index, job: jobs[index] });
    };
    for (let i = 0; i < Math.min(workerCount, jobs.length); i += 1) {
      const worker = new Worker(new URL("./headless-worker.mjs", import.meta.url));
      workers.push(worker);
      worker.on("message", ({ index, result, error }) => {
        results[index] = error ? failedResult(jobs[index], error) : result;
        completed += 1;
        if (completed === jobs.length) {
          stop();
          resolve(results);
        } else dispatch(worker);
      });
      worker.on("error", (error) => {
        stop();
        reject(error);
      });
      dispatch(worker);
    }
  });
}

export function parseInput(raw) {
  const text = raw.trim();
  if (!text) throw new SyntaxError("headless input is empty");
  try {
    return [JSON.parse(text)];
  } catch (wholeDocumentError) {
    const lines = text.split(/\r?\n/).filter((line) => line.trim());
    if (lines.length <= 1) throw wholeDocumentError;
    return lines.map((line) => JSON.parse(line));
  }
}

async function main() {
  const options = argumentsFrom(process.argv.slice(2));
  const raw = options.input === "-"
    ? await readStdin()
    : await readFile(options.input, "utf8");
  const jobs = parseInput(raw).flatMap(expandJobs);
  const results = await parallelJobs(jobs, options.workers);
  process.stdout.write(`${JSON.stringify({ schemaVersion: 1, results })}\n`);
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  await main();
}
