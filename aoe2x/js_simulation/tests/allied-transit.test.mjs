import assert from "node:assert/strict";
import test from "node:test";

import {
  alliedTransitPairKey,
  updateAlliedTransit,
} from "../src/combat/allied-transit.js";


function unit(referenceId, x, y = 5, owner = 3, {
  attackRange = 0,
  pursuitTargetId = null,
  speed = 0.9,
  reload = 2,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive: true,
    pursuitTargetId,
    mechanics: Object.freeze({
      attack_range_tiles: attackRange,
      collision_size_tiles: Object.freeze({ x: 0.2, y: 0.2 }),
      outline_size_tiles: Object.freeze({ x: 0.2, y: 0.2 }),
      speed_tiles_per_second: speed,
      reload_seconds: reload,
    }),
  });
}


function proposal(referenceId, dx, dy = 0) {
  return Object.freeze({ referenceId, dx, dy });
}


function state(cohort, reservations = new Map(), mode = "ordinary") {
  return { cohort: new Set(cohort), reservations, mode };
}


test("allied transit canonicalizes pair keys independently of argument order", () => {
  assert.equal(alliedTransitPairKey(9, 2), "2:9");
  assert.equal(alliedTransitPairKey(2, 9), "2:9");
});


test("allied transit assigns at most one deterministic partner to each mover", () => {
  const result = updateAlliedTransit(
    state([1, 2, 3]),
    [unit(1, 2), unit(2, 2.39), unit(3, 2.78)],
    [proposal(1, 0.04), proposal(2, 0.02), proposal(3, 0.01)],
  );

  assert.deepEqual([...result.pairKeys], ["1:2"]);
  assert.equal(result.reservations.size, 1);
  assert.equal(
    [...result.reservations.values()].filter(({ leftId, rightId }) => (
      leftId === 2 || rightId === 2
    )).length,
    1,
  );
});


test("an active transit reservation persists instead of switching to a closer ally", () => {
  const reservation = Object.freeze({ leftId: 1, rightId: 2, axis: "x", sign: 1 });
  const result = updateAlliedTransit(
    state([1, 2, 3], new Map([["1:2", reservation]])),
    [unit(1, 2), unit(2, 2.25), unit(3, 2.26)],
    [proposal(1, 0.02), proposal(2, -0.01), proposal(3, -0.02)],
  );

  assert.deepEqual([...result.pairKeys], ["1:2"]);
  assert.equal(result.reservations.get("1:2"), reservation);
});


test("an active reservation releases when its pair only co-moves inside the envelope", () => {
  const reservation = Object.freeze({ leftId: 1, rightId: 2, axis: "x", sign: 1 });
  const result = updateAlliedTransit(
    state([1, 2], new Map([["1:2", reservation]])),
    [unit(1, 2), unit(2, 2.15)],
    [proposal(1, 0.02), proposal(2, 0.02)],
  );

  assert.deepEqual([...result.pairKeys], []);
  assert.equal(result.reservations.size, 0);
});


test("a reservation releases after its pair crosses and cannot immediately reacquire while separating", () => {
  const reservation = Object.freeze({ leftId: 1, rightId: 2, axis: "x", sign: 1 });
  const result = updateAlliedTransit(
    state([1, 2], new Map([["1:2", reservation]])),
    [unit(1, 2.21), unit(2, 2.19)],
    [proposal(1, 0.02), proposal(2, -0.02)],
  );

  assert.deepEqual([...result.pairKeys], []);
  assert.equal(result.reservations.size, 0);
});


test("an active reservation releases after the pair clears its ordinary collision envelope", () => {
  const reservation = Object.freeze({ leftId: 1, rightId: 2, axis: "x", sign: 1 });
  const result = updateAlliedTransit(
    state([1, 2], new Map([["1:2", reservation]])),
    [unit(1, 2), unit(2, 2.6)],
    [proposal(1, 0.02), proposal(2, 0.02)],
  );

  assert.deepEqual([...result.pairKeys], []);
  assert.equal(result.reservations.size, 0);
});


test("stopped, dead, out-of-cohort, and enemy pairs never begin allied transit", () => {
  const dead = { ...unit(4, 3.17), alive: false };
  const result = updateAlliedTransit(
    state([1, 2, 4]),
    [unit(1, 2), unit(2, 2.39), unit(3, 2.78), dead, unit(5, 3.56, 5, 2)],
    [
      proposal(1, 0.02),
      proposal(2, 0),
      proposal(3, -0.02),
      proposal(4, -0.02),
      proposal(5, -0.02),
    ],
  );

  assert.deepEqual([...result.pairKeys], []);
});


test("opposing allied movers collide normally instead of beginning transit", () => {
  const result = updateAlliedTransit(
    state([1, 2]),
    [unit(1, 2), unit(2, 2.39)],
    [proposal(1, 0.02), proposal(2, -0.02)],
  );

  assert.deepEqual([...result.pairKeys], []);
});


test("allied transit releases when either partner reaches its pursuit target", () => {
  const reservation = Object.freeze({ leftId: 1, rightId: 2, axis: "x", sign: 1 });
  const left = { ...unit(1, 2), pursuitTargetId: 10 };
  const right = { ...unit(2, 2.15), pursuitTargetId: 10 };
  const target = unit(10, 2.45, 5, 2);
  const result = updateAlliedTransit(
    state([1, 2], new Map([["1:2", reservation]])),
    [left, right, target],
    [proposal(1, 0.02), proposal(2, 0.01), proposal(10, 0)],
  );

  assert.deepEqual([...result.pairKeys], []);
});


test("reach-wedge transit lets a pursuing reach melee unit pass one stopped front-line ally", () => {
  const rear = unit(1, 2, 5, 3, {
    attackRange: 1, pursuitTargetId: 10, speed: 1.6,
  });
  const front = unit(2, 2.39, 5, 3, {
    attackRange: 1, pursuitTargetId: 10, speed: 1.6,
  });
  const target = unit(10, 3.7, 5, 2, { speed: 1.5 });

  const ordinary = updateAlliedTransit(
    state([1, 2]),
    [rear, front, target],
    [proposal(1, 0.02), proposal(2, 0), proposal(10, 0)],
  );
  assert.deepEqual([...ordinary.pairKeys], []);

  const wedge = updateAlliedTransit(
    state([1, 2], new Map(), "reach-wedge"),
    [rear, front, target],
    [proposal(1, 0.02), proposal(2, 0), proposal(10, 0)],
  );
  assert.deepEqual([...wedge.pairKeys], ["1:2"]);
  assert.equal(wedge.reservations.get("1:2").moverId, 1);
  assert.equal(wedge.reservations.get("1:2").frontId, 2);
});


test("reach-wedge transit remains exclusive when two rear units approach one front ally", () => {
  const target = unit(10, 3.7, 5, 2, { speed: 1.5 });
  const result = updateAlliedTransit(
    state([1, 2, 3], new Map(), "reach-wedge"),
    [
      unit(1, 2, 4.98, 3, { attackRange: 1, pursuitTargetId: 10, speed: 1.6 }),
      unit(2, 2.39, 5, 3, { attackRange: 1, pursuitTargetId: 10, speed: 1.6 }),
      unit(3, 2, 5.02, 3, { attackRange: 1, pursuitTargetId: 10, speed: 1.6 }),
      target,
    ],
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0.02), proposal(10, 0)],
  );

  assert.equal(result.reservations.size, 1);
  assert.deepEqual([...result.pairKeys], ["1:2"]);
});


test("reach-wedge transit applies to any one-range melee unit regardless of target speed", () => {
  const result = updateAlliedTransit(
    state([1, 2], new Map(), "reach-wedge"),
    [
      unit(1, 2, 5, 3, {
        attackRange: 1, pursuitTargetId: 10, speed: 1.6, reload: 2,
      }),
      unit(2, 2.39, 5, 3, {
        attackRange: 1, pursuitTargetId: 10, speed: 1.6, reload: 2,
      }),
      unit(10, 3.7, 5, 2, { speed: 0.9 }),
    ],
    [proposal(1, 0.02), proposal(2, 0), proposal(10, 0)],
  );

  assert.deepEqual([...result.pairKeys], ["1:2"]);
});
