import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  runPhase2Batch1Sample,
} from "../../src/phase2-batch1-comparison.js";

const EXPECTED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const ROOT = new URL("../../", import.meta.url);
const [rowId, rawSampleIndex = "0"] = process.argv.slice(2);
const sampleIndex = Number(rawSampleIndex);

if (!rowId || !Number.isInteger(sampleIndex) || sampleIndex < 0) {
  throw new Error("usage: run_phase2_one_sample_2026-08-20.mjs ROW_ID [SAMPLE_INDEX]");
}

const truth = await loadPhase2Batch1Truth(ROOT);
if (truth.archive?.zip_sha256 !== EXPECTED_SHA256) {
  throw new Error(`unexpected Phase 2 archive hash in truth: ${truth.archive?.zip_sha256}`);
}
const archivePath = new URL(`../../${truth.archive.path}`, ROOT);
const observedHash = await sha256(archivePath);
if (observedHash !== EXPECTED_SHA256) {
  throw new Error(`Phase 2 archive hash mismatch: ${observedHash}`);
}

const row = truth.rows.find(({ id }) => id === rowId);
if (!row) throw new Error(`unknown Phase 2 row: ${rowId}`);
const context = await loadPhase2Batch1Context(ROOT, truth);
const startedAt = performance.now();
const result = runPhase2Batch1Sample({
  row,
  sampleIndex,
  seed: 20260817,
  context,
});
const wallMilliseconds = performance.now() - startedAt;

process.stdout.write(`${JSON.stringify({
  archiveSha256: observedHash,
  rowId,
  sampleIndex,
  wallMilliseconds: Number(wallMilliseconds.toFixed(1)),
  ...result,
}, null, 2)}\n`);

async function sha256(url) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(url)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}
