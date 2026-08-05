import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const clockModuleUrl = new URL("../src/simulation-clock.js", import.meta.url);
const clockModulePath = fileURLToPath(clockModuleUrl);

async function loadClock() {
  assert.equal(existsSync(clockModulePath), true);
  return import(clockModuleUrl);
}

test("the clean-room clock is an explicit 60 Hz hypothesis", async () => {
  const { TICKS_PER_SECOND, secondsToTicksCeil, ticksToSeconds } = await loadClock();

  assert.equal(TICKS_PER_SECOND, 60);
  assert.equal(secondsToTicksCeil(2), 120);
  assert.equal(ticksToSeconds(120), 2);
});

test("fractional readiness always advances to a real tick", async () => {
  const { secondsToTicksCeil } = await loadClock();

  assert.equal(secondsToTicksCeil(0.001), 1);
  assert.equal(secondsToTicksCeil(2.001), 121);
});

test("readiness rejects seconds that cannot produce a safe integer tick", async () => {
  const { secondsToTicksCeil } = await loadClock();

  assert.throws(() => secondsToTicksCeil(Number.MAX_VALUE), RangeError);
});

test("clock conversions reject invalid seconds and non-integer ticks", async () => {
  const { secondsToTicksCeil, ticksToSeconds } = await loadClock();

  for (const value of [-0.001, Number.NaN, Infinity]) {
    assert.throws(() => secondsToTicksCeil(value), RangeError);
  }
  for (const value of [-1, 0.5, Number.NaN, Infinity]) {
    assert.throws(() => ticksToSeconds(value), RangeError);
  }
});
