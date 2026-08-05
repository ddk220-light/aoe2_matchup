import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";


const runnerUrl = new URL("./support/champion-ratio.mjs", import.meta.url);


async function loadRunner() {
  assert.equal(existsSync(fileURLToPath(runnerUrl)), true);
  return import(runnerUrl);
}


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
  for (const comparison of result.diagnostics.tapeComparisons) {
    assert.deepEqual(Object.keys(comparison.simulation), requiredTraceFields);
    assert.deepEqual(Object.keys(comparison.tape), requiredTraceFields);
    assert.deepEqual(Object.keys(comparison.deltas), requiredTraceFields);
    assert.equal(comparison.simulation.starts.length, 2);
    assert.equal(comparison.tape.starts.length, 2);
  }
});
