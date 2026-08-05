import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  createProjection,
  objectAtTile,
  sortObjectsForRender,
  validateMapFixture,
} from "../src/map-model.js";


const fixtureUrl = new URL("../fixtures/golden_map.json", import.meta.url);

async function loadFixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}


test("projection round-trips ground coordinates within 0.001 tile", () => {
  const projection = createProjection({
    mapWidth: 16,
    mapHeight: 16,
    tileWidth: 72,
    tileHeight: 36,
    originX: 640,
    originY: 80,
  });

  for (const point of [
    { x: 0, y: 0 },
    { x: 8, y: 8 },
    { x: 15.5, y: 15.5 },
    { x: 3.25, y: 11.75 },
  ]) {
    const screen = projection.tileToScreen(point.x, point.y, 0);
    const tile = projection.screenToTile(screen.x, screen.y);
    assert.ok(Math.abs(tile.x - point.x) <= 0.001);
    assert.ok(Math.abs(tile.y - point.y) <= 0.001);
  }
});


test("counterclockwise view rotates map corners while preserving the geometric centre", () => {
  const projection = createProjection({
    mapWidth: 16,
    mapHeight: 16,
    tileWidth: 72,
    tileHeight: 36,
    originX: 0,
    originY: 0,
    orientation: "counterclockwise",
  });

  assert.deepEqual(projection.tileToScreen(0, 0), { x: -576, y: 288 });
  assert.deepEqual(projection.tileToScreen(16, 0), { x: 0, y: 0 });
  assert.deepEqual(projection.tileToScreen(16, 16), { x: 576, y: 288 });
  assert.deepEqual(projection.tileToScreen(0, 16), { x: 0, y: 576 });
  assert.deepEqual(projection.tileToScreen(8, 8), { x: 0, y: 288 });

  const screen = projection.tileToScreen(9, 7);
  const tile = projection.screenToTile(screen.x, screen.y);
  assert.ok(Math.abs(tile.x - 9) <= 0.001);
  assert.ok(Math.abs(tile.y - 7) <= 0.001);
});


test("fixture validation preserves all literal map records", async () => {
  const fixture = validateMapFixture(await loadFixture());

  assert.equal(fixture.map.width, 16);
  assert.equal(fixture.map.height, 16);
  assert.equal(fixture.map.tiles.length, 256);
  assert.equal(fixture.map.gaia_objects.length, 101);
  assert.equal(new Set(fixture.map.tiles.map(({ x, y }) => `${x},${y}`)).size, 256);
  assert.ok(Object.isFrozen(fixture));
  assert.ok(Object.isFrozen(fixture.map));
});


test("fixture validation rejects transposed or incomplete map data", async () => {
  const fixture = await loadFixture();
  fixture.map.tiles.pop();

  assert.throws(
    () => validateMapFixture(fixture),
    /exactly 256 unique terrain tiles/,
  );
});


test("Gaia objects render from back to front using isometric depth", () => {
  const objects = [
    { reference_id: 3, x: 8.5, y: 7.5 },
    { reference_id: 1, x: 2.5, y: 1.5 },
    { reference_id: 2, x: 9.0, y: 7.0 },
  ];

  assert.deepEqual(
    sortObjectsForRender(objects).map((object) => object.reference_id),
    [1, 2, 3],
  );
  assert.deepEqual(objects.map((object) => object.reference_id), [3, 1, 2]);
});


test("object picking returns only the nearest object inside the tile radius", () => {
  const objects = [
    { reference_id: 1, x: 4.0, y: 4.0 },
    { reference_id: 2, x: 4.3, y: 4.1 },
  ];

  assert.equal(objectAtTile(objects, 4.25, 4.05, 0.3).reference_id, 2);
  assert.equal(objectAtTile(objects, 8, 8, 0.3), null);
});
