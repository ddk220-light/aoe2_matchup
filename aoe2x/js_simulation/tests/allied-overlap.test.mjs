import assert from "node:assert/strict";
import test from "node:test";

import { updateExclusiveAlliedOverlap } from "../src/combat/allied-overlap.js";


const MECHANICS = Object.freeze({
  collision_size_tiles: Object.freeze({ x: 0.25, y: 0.25 }),
  min_collision_size_multiplier: 0.5,
});


function unit(referenceId, x, y) {
  return Object.freeze({ referenceId, owner: 3, x, y, alive: true, mechanics: MECHANICS });
}


function proposal(referenceId, dx, dy) {
  return Object.freeze({ referenceId, dx, dy });
}


test("three converging allies receive only one exclusive deep-overlap pair", () => {
  const result = updateExclusiveAlliedOverlap(
    null,
    [unit(1, 4, 4), unit(2, 4.5, 4), unit(3, 4.25, 4.5)],
    [proposal(1, 0.2, 0), proposal(2, -0.2, 0), proposal(3, 0, -0.2)],
    3,
  );

  assert.deepEqual([...result.pairKeys], ["1:2"]);
  assert.deepEqual([...result.reservedIds], [1, 2]);
  assert.equal(result.reservations.size, 1);
  assert.deepEqual([...result.shallowPairKeys], ["1:3"]);
});


test("an active deep-overlap pair remains exclusive while a third ally crowds it", () => {
  const previous = {
    reservations: new Map([["1:2", Object.freeze({ leftId: 1, rightId: 2 })]]),
  };
  const result = updateExclusiveAlliedOverlap(
    previous,
    [unit(1, 4, 4), unit(2, 4.3, 4), unit(3, 4.31, 4.1)],
    [proposal(1, 0.01, 0), proposal(2, 0.01, 0), proposal(3, -0.02, 0)],
    3,
  );

  assert.deepEqual([...result.pairKeys], ["1:2"]);
  assert.deepEqual([...result.reservedIds], [1, 2]);
  assert.deepEqual([...result.shallowPairKeys], ["2:3"]);
});


test("a deep-overlap reservation survives a stationary attack pause", () => {
  const previous = {
    reservations: new Map([["1:2", Object.freeze({ leftId: 1, rightId: 2 })]]),
  };
  const result = updateExclusiveAlliedOverlap(
    previous,
    [unit(1, 4, 4), unit(2, 4.3, 4), unit(3, 4.31, 4.1)],
    [proposal(1, 0, 0), proposal(2, 0, 0), proposal(3, 0, 0)],
    3,
  );

  assert.deepEqual([...result.pairKeys], ["1:2"]);
  assert.deepEqual([...result.reservedIds], [1, 2]);
});
