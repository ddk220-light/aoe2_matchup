import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { validateMapFixture } from "../src/map-model.js";
import {
  buildFormationScene,
  buildRenderScene,
  createSimulationPresenter,
  pickFormationUnit,
} from "../viewer/map-renderer.js";


const fixtureUrl = new URL("../fixtures/golden_map.json", import.meta.url);


test("render scene preserves every source tile and Gaia object", async () => {
  const fixture = validateMapFixture(
    JSON.parse(await readFile(fixtureUrl, "utf8")),
  );
  const scene = buildRenderScene(fixture.map);

  assert.equal(scene.tiles.length, 256);
  assert.equal(scene.objects.length, 101);
  assert.deepEqual(
    scene.objects.find((object) => object.name === "PANDA_ROCK"),
    {
      reference_id: 1604,
      unit_const: 2082,
      name: "PANDA_ROCK",
      x: 9,
      y: 7,
      z: 0,
      rotation: 0,
      status: 2,
      kind: "rock",
    },
  );
});


test("render scene recognizes every vegetation category in the scenario", async () => {
  const fixture = validateMapFixture(
    JSON.parse(await readFile(fixtureUrl, "utf8")),
  );
  const scene = buildRenderScene(fixture.map);
  const vegetation = new Set(
    scene.objects
      .filter((object) => object.kind !== "rock")
      .map((object) => object.name),
  );

  assert.deepEqual(vegetation, new Set([
    "TREE_ITALIAN_PINE",
    "TREE_MONKEY_PUZZLE",
    "TREE_ACACIA",
    "TREE_OAK_GREEN",
    "TREE_OLIVE",
    "TREE_OAK_FOREST",
    "BUSH_B",
    "TREE_RAINFOREST",
  ]));
  assert.deepEqual(
    scene.objects.map((object) => object.x + object.y),
    [...scene.objects]
      .map((object) => object.x + object.y)
      .sort((a, b) => a - b),
  );
});


test("counterclockwise scene depth follows the rotated view", () => {
  const scene = buildRenderScene({
    width: 16,
    height: 16,
    tiles: [
      { x: 1, y: 1, elevation: 0, terrain_name: "DIRT_1" },
      { x: 14, y: 4, elevation: 0, terrain_name: "DIRT_1" },
    ],
    gaia_objects: [
      { reference_id: 1, unit_const: 1, name: "TREE_OAK_GREEN", x: 1.5, y: 1.5, z: 0 },
      { reference_id: 2, unit_const: 1, name: "TREE_OAK_GREEN", x: 14.5, y: 4.5, z: 0 },
    ],
  }, { orientation: "counterclockwise" });

  assert.deepEqual(scene.tiles.map(({ x, y }) => [x, y]), [[14, 4], [1, 1]]);
  assert.deepEqual(scene.objects.map(({ reference_id }) => reference_id), [2, 1]);
});


test("formation scene preserves source coordinates and uses rotated depth", () => {
  const units = [
    { reference_id: 1, player_id: 2, position: { x: 1.5, y: 1.5 }, rotation: 0 },
    { reference_id: 2, player_id: 3, position: { x: 14.5, y: 4.5 }, rotation: 1 },
  ];

  const scene = buildFormationScene(units);

  assert.deepEqual(scene.map((unit) => unit.reference_id), [2, 1]);
  assert.deepEqual(scene[0].position, { x: 14.5, y: 4.5 });
  assert.equal(scene[0].team, "p3");
  assert.equal(scene[1].team, "p2");
});


test("formation picking returns the nearest source unit", () => {
  const units = [
    { reference_id: 1, position: { x: 4.0, y: 4.0 } },
    { reference_id: 2, position: { x: 4.3, y: 4.1 } },
  ];

  assert.equal(pickFormationUnit(units, 4.25, 4.05, 0.3).reference_id, 2);
  assert.equal(pickFormationUnit(units, 8, 8, 0.3), null);
});


test("simulation presenter displays the supplied immutable tick without advancing the world", () => {
  let stepWorldCalls = 0;
  const displayed = [];
  const presenter = createSimulationPresenter({
    present(snapshot) {
      displayed.push(snapshot);
    },
    stepWorld() {
      stepWorldCalls += 1;
    },
  });
  const snapshotAtTick42 = Object.freeze({
    tick: 42,
    units: Object.freeze([
      Object.freeze({ referenceId: 1628, owner: 2, x: 4, y: 6, hp: 56, alive: true }),
    ]),
    events: Object.freeze([]),
  });

  presenter.setSimulationSnapshot(snapshotAtTick42);

  assert.equal(presenter.getDisplayedTick(), 42);
  assert.equal(presenter.getSimulationSnapshot(), snapshotAtTick42);
  assert.equal(displayed.at(-1), snapshotAtTick42);
  assert.equal(stepWorldCalls, 0);
});


test("simulation presenter rejects mutable or malformed snapshots", () => {
  const presenter = createSimulationPresenter({ present() {} });

  assert.throws(
    () => presenter.setSimulationSnapshot({ tick: 2, units: [], events: [] }),
    /immutable simulation snapshot/i,
  );
  assert.throws(
    () => presenter.setSimulationSnapshot(Object.freeze({ tick: -1, units: Object.freeze([]) })),
    /immutable simulation snapshot/i,
  );
  assert.throws(
    () => presenter.setSimulationSnapshot(Object.freeze({
      tick: 2,
      units: Object.freeze([{ referenceId: 1628 }]),
      events: Object.freeze([]),
    })),
    /immutable simulation snapshot/i,
  );
});
