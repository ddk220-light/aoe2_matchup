import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  ARENA_CENTER_CORE,
  buildArenaPhysicsMap,
} from "../src/arena-physics-map.js";


const fixture = JSON.parse(await readFile(
  new URL("../fixtures/golden_map.json", import.meta.url),
  "utf8",
));


test("Golden Arena center has a gap-free core without changing its outer objects", () => {
  const physicsMap = buildArenaPhysicsMap(fixture);
  const core = physicsMap.obstacles.filter(({ referenceId }) => (
    referenceId === ARENA_CENTER_CORE.referenceId
  ));

  assert.deepEqual(core, [ARENA_CENTER_CORE]);
  assert.equal(physicsMap.obstacles.length, fixture.map.gaia_objects.length);

  const centralObjects = fixture.map.gaia_objects.filter(({ x, y }) => (
    x >= 7 && x <= 11 && y >= 5 && y <= 9
  ));
  assert.equal(centralObjects.length, 9);
  for (const object of centralObjects) {
    assert.equal(
      physicsMap.obstacles.some(({ referenceId }) => referenceId === object.reference_id),
      true,
      `central perimeter object ${object.reference_id} was removed`,
    );
  }

  // Every inward seam between neighboring perimeter objects is behind the
  // enlarged central rock. A unit cannot cross the perimeter and become
  // trapped in the middle, even at zero collision radius.
  const perimeter = centralObjects.filter(({ reference_id: referenceId }) => (
    referenceId !== ARENA_CENTER_CORE.referenceId
  ));
  for (let left = 0; left < perimeter.length; left += 1) {
    for (let right = left + 1; right < perimeter.length; right += 1) {
      const distance = Math.hypot(
        perimeter[left].x - perimeter[right].x,
        perimeter[left].y - perimeter[right].y,
      );
      if (distance > Math.SQRT2 + 1e-12) continue;
      const seam = {
        x: (perimeter[left].x + perimeter[right].x) / 2,
        y: (perimeter[left].y + perimeter[right].y) / 2,
      };
      assert.ok(
        Math.hypot(seam.x - core[0].x, seam.y - core[0].y) <= core[0].radius,
        `open inward seam between ${perimeter[left].reference_id} and `
          + `${perimeter[right].reference_id}`,
      );
    }
  }
});


test("Golden Arena physics conversion is deterministic and immutable", () => {
  const first = buildArenaPhysicsMap(fixture);
  const second = buildArenaPhysicsMap(fixture);

  assert.deepEqual(first, second);
  assert.equal(Object.isFrozen(first), true);
  assert.equal(Object.isFrozen(first.obstacles), true);
  assert.equal(first.obstacles.every(Object.isFrozen), true);
});
