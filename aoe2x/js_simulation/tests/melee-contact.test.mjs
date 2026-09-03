import assert from "node:assert/strict";
import test from "node:test";

import { hasUnobstructedZeroRangeMeleeContact } from "../src/combat/melee-contact.js";


const mechanics = Object.freeze({
  attack_range_tiles: 0,
  collision_size_tiles: Object.freeze({ x: 0.25, y: 0.25 }),
  min_collision_size_multiplier: 0.5,
  ranged: null,
});


function unit(referenceId, owner, x, overrides = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y: 4,
    alive: true,
    action: "moving",
    mechanics,
    ...overrides,
  });
}


test("deep allied transit overlap is not a free zero-range attack position", () => {
  const actor = unit(1, 3, 4);
  const target = unit(3, 2, 4.5);
  const deeplyOverlappedTraveler = unit(2, 3, 4.1);

  assert.equal(
    hasUnobstructedZeroRangeMeleeContact(
      actor,
      target,
      [actor, deeplyOverlappedTraveler, target],
    ),
    false,
  );
});


test("sourced minimum allied separation remains a valid zero-range attack position", () => {
  const actor = unit(1, 3, 4);
  const target = unit(3, 2, 4.5);
  const shallowTraveler = unit(2, 3, 4, { y: 4.25 });

  assert.equal(
    hasUnobstructedZeroRangeMeleeContact(actor, target, [actor, shallowTraveler, target]),
    true,
  );
});

