import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";


const runnerUrl = new URL("./support/champion-ratio.mjs", import.meta.url);
const sourceArchiveUrl = new URL(
  "../calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip",
  import.meta.url,
);
const sourceOfTruthUrl = new URL("../calibration/source/source_of_truth.json", import.meta.url);
const truthUrl = new URL("../calibration/fixtures/champion_basics.json", import.meta.url);
const manifestUrl = new URL("../calibration/fixtures/manifest.json", import.meta.url);
const mechanicsUrl = new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
);

const AUTHORIZED_SOURCE = {
  archive: "aoe2_golden_basics_championvschampion_2026-08-04.zip",
  zipSha256: "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE",
  recordings: 15,
  manifestEntries: 15,
  truthFixtureSha256: "5D40A39DB397EBF191D4CA7C8A900E2026601123DA7064E33B046FEA45BA831E",
  mechanicsFixtureSha256: "20F5F9C1422502459986C44474FD9DC278AB9D359070B964BD7E7549DC97B5A6",
  datSha256: "CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF",
  referenceDbSha256: "51D602640E4C1A75F35286AA499821338B0EEE5DBA97E12A12D39E058CB11087",
};


async function loadRunner() {
  assert.equal(existsSync(fileURLToPath(runnerUrl)), true);
  return import(runnerUrl);
}


async function loadSourceChain() {
  const [archiveBytes, sourceOfTruth, truthBytes, manifest, mechanicsBytes] = await Promise.all([
    readFile(sourceArchiveUrl),
    readFile(sourceOfTruthUrl, "utf8").then(JSON.parse),
    readFile(truthUrl),
    readFile(manifestUrl, "utf8").then(JSON.parse),
    readFile(mechanicsUrl),
  ]);
  return {
    archiveBytes,
    sourceOfTruth,
    truthBytes,
    truth: JSON.parse(truthBytes.toString("utf8")),
    manifest,
    mechanicsBytes,
    mechanics: JSON.parse(mechanicsBytes.toString("utf8")),
  };
}


test("Champion diagnostics reject any unauthorized clean-room source link", async () => {
  const { runChampionRatio, verifyCleanroomSource } = await loadRunner();
  const source = await loadSourceChain();

  assert.deepEqual(verifyCleanroomSource(source), AUTHORIZED_SOURCE);
  assert.deepEqual(runChampionRatio("1v1").diagnostics.source, AUTHORIZED_SOURCE);
  assert.throws(
    () => verifyCleanroomSource({ ...source, archiveBytes: Buffer.from("not the archive") }),
    /clean-room source/,
  );
  assert.throws(
    () => verifyCleanroomSource({
      ...source,
      sourceOfTruth: { ...source.sourceOfTruth, sha256: "0".repeat(64) },
    }),
    /clean-room source/,
  );
  assert.throws(
    () => verifyCleanroomSource({
      ...source,
      truth: { ...source.truth, zip_sha256: "0".repeat(64) },
    }),
    /clean-room source/,
  );
  assert.throws(
    () => verifyCleanroomSource({
      ...source,
      manifest: { ...source.manifest, zip_sha256: "0".repeat(64) },
    }),
    /clean-room source/,
  );
  assert.throws(
    () => verifyCleanroomSource({
      ...source,
      manifest: {
        ...source.manifest,
        runs: [
          { ...source.manifest.runs[0], zip_sha256: "0".repeat(64) },
          ...source.manifest.runs.slice(1),
        ],
      },
    }),
    /clean-room source/,
  );
  assert.throws(
    () => verifyCleanroomSource({
      ...source,
      truthBytes: Buffer.from(JSON.stringify({ ...source.truth, edited: true })),
    }),
    /truth fixture SHA-256/,
  );
  assert.throws(
    () => verifyCleanroomSource({
      ...source,
      mechanicsBytes: Buffer.from(JSON.stringify({ ...source.mechanics, hp: 71 })),
    }),
    /mechanics fixture SHA-256/,
  );
});


test("Champion hashes use recursive key ordering and reject non-finite state", async () => {
  const { hashCanonicalJson } = await loadRunner();

  assert.equal(
    hashCanonicalJson({ second: 2, first: { z: 3, a: [2, { y: 1, x: 0 }] } }),
    hashCanonicalJson({ first: { a: [2, { x: 0, y: 1 }], z: 3 }, second: 2 }),
  );
  assert.throws(() => hashCanonicalJson({ invalid: Number.NaN }), /finite number/);
  assert.throws(() => hashCanonicalJson({ nested: [Number.POSITIVE_INFINITY] }), /finite number/);
});


test("interval diagnostics retain the union of simulation and tape attackers", async () => {
  const { compareSameAttackerIntervals } = await loadRunner();

  assert.deepEqual(compareSameAttackerIntervals(
    [{ id: 1628, seconds: [2] }, { id: 1700, seconds: [1.5] }],
    [{ id: 1628, seconds: [2.02] }, { id: 1699, seconds: [2.1] }],
  ), [
    { id: 1628, seconds: [-0.02] },
    { id: 1699, seconds: [null] },
    { id: 1700, seconds: [null] },
  ]);
});


test("Champion 1v1 ends with nine 14-HP hits and one 14-HP survivor", async () => {
  const { runChampionRatio } = await loadRunner();
  const result = runChampionRatio("1v1");

  assert.equal(result.damageEvents.length, 9);
  assert.deepEqual(new Set(result.damageEvents.map((event) => event.amount)), new Set([14]));
  assert.equal(result.winner.hp, 14);
  assert.equal(result.loser.hp, 0);
  assert.equal(result.livingUnits.length, 1);
});


test("Champion 1v1 hashes are repeatable and input-order invariant", async () => {
  const { runChampionRatio } = await loadRunner();
  const forward = Array.from({ length: 5 }, () => runChampionRatio("1v1"));
  const reversed = runChampionRatio("1v1", { reverseUnits: true });

  assert.match(forward[0].finalStateHash, /^[0-9a-f]{64}$/);
  assert.match(forward[0].eventLogHash, /^[0-9a-f]{64}$/);
  assert.deepEqual(new Set(forward.map(({ finalStateHash }) => finalStateHash)), new Set([
    forward[0].finalStateHash,
  ]));
  assert.deepEqual(new Set(forward.map(({ eventLogHash }) => eventLogHash)), new Set([
    forward[0].eventLogHash,
  ]));
  assert.equal(reversed.finalStateHash, forward[0].finalStateHash);
  assert.equal(reversed.eventLogHash, forward[0].eventLogHash);
});


test("Champion 1v1 reports trace deltas against all three clean-room tapes", async () => {
  const { runChampionRatio } = await loadRunner();
  const result = runChampionRatio("1v1");
  const expectedTapeEvidence = {
    "1v1": {
      firstDamage: { actorId: 1699, targetId: 1628, amount: 14 },
      kill: { actorId: 1699, targetId: 1628, amount: 14 },
      intervals: [
        { id: 1628, seconds: [2.022, 2.02, 2.018] },
        { id: 1699, seconds: [2.022, 2.02, 2.018, 2.018] },
      ],
    },
    "1v1_r2": {
      firstDamage: { actorId: 1628, targetId: 1699, amount: 14 },
      kill: { actorId: 1628, targetId: 1699, amount: 14 },
      intervals: [
        { id: 1628, seconds: [2.026, 2.012, 2.004, 2.012] },
        { id: 1699, seconds: [2.026, 2.012, 2.004] },
      ],
    },
    "1v1_r3": {
      firstDamage: { actorId: 1628, targetId: 1699, amount: 14 },
      kill: { actorId: 1628, targetId: 1699, amount: 14 },
      intervals: [
        { id: 1628, seconds: [2.014, 2.002, 2.014, 2.012] },
        { id: 1699, seconds: [2.014, 2.002, 2.014] },
      ],
    },
  };
  const requiredTraceFields = [
    "starts",
    "firstMoves",
    "movementDirections",
    "surfaceContact",
    "firstDamage",
    "sameAttackerIntervals",
    "kill",
    "hitsPerOwner",
    "winnerHp",
  ];

  assert.deepEqual(
    result.diagnostics.tapeComparisons.map(({ tag }) => tag),
    ["1v1", "1v1_r2", "1v1_r3"],
  );
  assert.match(result.diagnostics.firstMoveSamplingNote, /10 Hz sample.*not compared/);
  for (const comparison of result.diagnostics.tapeComparisons) {
    const expected = expectedTapeEvidence[comparison.tag];
    assert.deepEqual(Object.keys(comparison.simulation), requiredTraceFields);
    assert.deepEqual(Object.keys(comparison.tape), requiredTraceFields);
    assert.deepEqual(Object.keys(comparison.deltas), requiredTraceFields);
    assert.equal(comparison.simulation.starts.length, 2);
    assert.equal(comparison.tape.starts.length, 2);
    assert.deepEqual(comparison.deltas.starts, [
      { id: 1628, owner: 0, master: 0, x: 0, y: 0 },
      { id: 1699, owner: 0, master: 0, x: 0, y: 0 },
    ]);
    assert.deepEqual(
      {
        actorId: comparison.tape.firstDamage.actorId,
        targetId: comparison.tape.firstDamage.targetId,
        amount: comparison.tape.firstDamage.amount,
      },
      expected.firstDamage,
    );
    assert.deepEqual(
      {
        actorId: comparison.tape.kill.actorId,
        targetId: comparison.tape.kill.targetId,
        amount: comparison.tape.kill.amount,
      },
      expected.kill,
    );
    assert.ok(comparison.deltas.firstMoves.every(({ seconds }) => Number.isFinite(seconds)));
    assert.ok(Number.isFinite(comparison.deltas.surfaceContact.seconds));
    assert.ok(Number.isFinite(comparison.deltas.firstDamage.seconds));
    assert.ok(Number.isFinite(comparison.deltas.kill.seconds));
    assert.deepEqual(comparison.tape.sameAttackerIntervals, expected.intervals);
    assert.ok(comparison.deltas.sameAttackerIntervals.length > 0);
    assert.equal(comparison.deltas.winnerHp, 0);
    assert.ok(comparison.deltas.firstMoves.every((row) => (
      Object.keys(row).join(",") === "id,seconds"
    )));
  }
});
