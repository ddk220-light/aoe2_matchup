import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";


const fixture = JSON.parse(await readFile(
  new URL("../fixtures/golden_map.json", import.meta.url),
  "utf8",
));


test("current golden map converts every literal Gaia object without synthetic geometry", () => {
  const physicsMap = buildArenaPhysicsMap(fixture);
  assert.equal(physicsMap.obstacles.length, fixture.map.gaia_objects.length);
  assert.equal(physicsMap.obstacles.length, 152);
  assert.equal(physicsMap.obstacles.every(({ radius }) => radius === 0.5), true);
  assert.deepEqual(
    physicsMap.obstacles.map(({ referenceId }) => referenceId),
    [...fixture.map.gaia_objects]
      .map(({ reference_id: referenceId }) => referenceId)
      .sort((left, right) => left - right),
  );
});


test("Golden Arena physics conversion is deterministic and immutable", () => {
  const first = buildArenaPhysicsMap(fixture);
  const second = buildArenaPhysicsMap(fixture);

  assert.deepEqual(first, second);
  assert.equal(Object.isFrozen(first), true);
  assert.equal(Object.isFrozen(first.obstacles), true);
  assert.equal(first.obstacles.every(Object.isFrozen), true);
});
