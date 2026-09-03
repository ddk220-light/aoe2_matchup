import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";

import { createWorld, stepWorld } from "../../src/combat/world.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";


const EXPECTED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const ROOT = new URL("../../", import.meta.url);
const [rowId, rawMaxTicks = "18000", rawSampleIndex = "0"] = process.argv.slice(2);
const maxTicks = Number(rawMaxTicks);
const sampleIndex = Number(rawSampleIndex);
if (!rowId || !Number.isSafeInteger(maxTicks) || maxTicks < 1
    || !Number.isSafeInteger(sampleIndex) || sampleIndex < 0) {
  throw new Error("usage: run_phase2_extended_one_sample_2026-08-20.mjs ROW_ID [MAX_TICKS] [SAMPLE_INDEX]");
}

const truth = await loadPhase2Batch1Truth(ROOT);
if (truth.archive?.zip_sha256 !== EXPECTED_SHA256) throw new Error("unexpected archive hash");
const archivePath = new URL(`../../${truth.archive.path}`, ROOT);
const observedHash = await sha256(archivePath);
if (observedHash !== EXPECTED_SHA256) throw new Error(`archive hash mismatch: ${observedHash}`);
const row = truth.rows.find(({ id }) => id === rowId);
if (!row) throw new Error(`unknown Phase 2 row: ${rowId}`);
const context = await loadPhase2Batch1Context(ROOT, truth);
let world = createWorld(scenarioFromPhase2Batch1Row({
  row,
  sampleIndex,
  seed: 20260817,
  context,
}));
const initialHpByOwner = hpByOwner(world.units);
const startedAt = performance.now();
for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
  world = stepWorld(world);
  if (liveOwners(world.units).size <= 1) break;
  world = Object.freeze({ ...world, snapshots: Object.freeze([]), eventLog: Object.freeze([]) });
}
const survivingHpByOwner = hpByOwner(world.units.filter(({ alive }) => alive));
const owners = [...liveOwners(world.units)];
const winnerOwner = owners.length === 1 ? owners[0] : null;
const winnerHp = winnerOwner === null ? null : survivingHpByOwner.get(winnerOwner) ?? 0;
const score = winnerOwner === null
  ? null
  : (winnerOwner === 2 ? -1 : 1) * 100 * winnerHp / initialHpByOwner.get(winnerOwner);
process.stdout.write(`${JSON.stringify({
  archiveSha256: observedHash,
  rowId,
  sampleIndex,
  ticks: world.tick,
  wallMilliseconds: Number((performance.now() - startedAt).toFixed(1)),
  outcome: winnerOwner === null ? "unresolved" : "win",
  winnerOwner,
  winnerHp,
  score,
  live: Object.fromEntries([...survivingHpByOwner].map(([owner, hp]) => [owner, {
    hp,
    units: world.units.filter((unit) => unit.alive && unit.owner === owner).length,
  }])),
}, null, 2)}\n`);


function hpByOwner(units) {
  const result = new Map();
  for (const unit of units) result.set(unit.owner, (result.get(unit.owner) ?? 0) + unit.hp);
  return result;
}


function liveOwners(units) {
  return new Set(units.filter(({ alive }) => alive).map(({ owner }) => owner));
}


async function sha256(url) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(url)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}
