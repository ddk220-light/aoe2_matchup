import assert from "node:assert/strict";
import test from "node:test";

import { createSoloNavigationState } from "../src/combat/solo-navigation.js";


function unit(referenceId, x, y) {
  return {
    referenceId,
    x,
    y,
    mechanics: {
      collision_size_tiles: { x: 0.45, y: 0.45 },
      speed_tiles_per_second: 1.32,
    },
  };
}


test("cohesive navigation honors the formation profile's measured slot spacing", () => {
  const state = createSoloNavigationState(
    "cohesive",
    [
      unit(1, 4, 4),
      unit(2, 5, 4),
      unit(3, 4, 5),
      unit(4, 5, 5),
    ],
    { width: 16, height: 16, obstacles: [] },
    { formationSpacingTiles: 0.6 },
  );

  const xCoordinates = [...new Set([...state.slots.values()].map(({ x }) => x))].sort();
  const yCoordinates = [...new Set([...state.slots.values()].map(({ y }) => y))].sort();
  assert.deepEqual(xCoordinates, [-0.3, 0.3]);
  assert.deepEqual(yCoordinates, [-0.3, 0.3]);
});


test("cohesive navigation retains the established compact spacing by default", () => {
  const state = createSoloNavigationState(
    "cohesive",
    [unit(1, 4, 4), unit(2, 5, 4)],
    { width: 16, height: 16, obstacles: [] },
  );
  const xCoordinates = [...state.slots.values()].map(({ x }) => x).sort();
  assert.deepEqual(xCoordinates, [-0.24, 0.24]);
});
