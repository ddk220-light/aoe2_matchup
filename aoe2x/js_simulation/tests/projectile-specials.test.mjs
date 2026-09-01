import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { attackDelayTicks, calculateDamage, rangedSpec } from "../src/combat/attacks.js";
import {
  blastFalloffFraction,
  displacedAimPoint,
  projectileArcFlightFactor,
  selectProjectileLandingVictim,
  siegeDebrisLandingPoints,
} from "../src/combat/projectile-mechanics.js";
import { isWithinReach } from "../src/combat/targeting.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const handCannoneer = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/hand_cannoneer_spanish_imperial.json", import.meta.url), "utf8"));
const arbalester = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/arbalester_chinese_imperial.json", import.meta.url), "utf8"));
const skirmisher = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/elite_skirmisher_chinese_imperial.json", import.meta.url), "utf8"));
const onager = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/siege_onager_aztecs_imperial.json", import.meta.url), "utf8"));


function spawn({
  referenceId,
  owner,
  x,
  y,
  mechanics,
  behaviorFamily,
  rank = referenceId - 1,
  count = 2,
}) {
  return createUnitState({
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    ...(behaviorFamily === undefined ? {} : { behaviorFamily }),
    acquisitionRank: rank,
    acquisitionCount: count,
  });
}


function run(units, ticks) {
  let world = createWorld({ ratio: "projectile-specials", units });
  for (let index = 0; index < ticks; index += 1) world = stepWorld(world);
  return world;
}


function inert(source, overrides = {}) {
  return {
    ...source,
    hp: 10_000,
    speed_tiles_per_second: 0,
    line_of_sight_tiles: 0,
    attack_range_tiles: 0,
    reload_seconds: 1_000,
    ...overrides,
  };
}


test("failed accuracy scatter is uniform in radius around the authored aim", () => {
  const point = displacedAimPoint({
    aimX: 4,
    aimY: 7,
    dispersionTiles: 0.5,
    radialRoll: 0.5,
    angleRoll: 0.25,
  });
  assert.ok(Math.abs(point.x - 4) < 1e-12);
  assert.ok(Math.abs(point.y - 7.25) < 1e-12);
});


test("landing collision includes projectile width and picks the nearest body", () => {
  const mechanics = {
    collision_size_tiles: { x: 0.2, y: 0.2 },
  };
  const farther = { referenceId: 9, alive: true, x: 0.29, y: 0, mechanics };
  const nearer = { referenceId: 5, alive: true, x: 0.1, y: 0, mechanics };
  const outside = { referenceId: 1, alive: true, x: 0.301, y: 0, mechanics };
  assert.equal(
    selectProjectileLandingVictim([farther, outside, nearer], 0, 0, 0.1),
    nearer,
  );
  assert.equal(
    selectProjectileLandingVictim([outside], 0, 0, 0.1),
    null,
  );
});


test("a Hand Cannoneer failed roll lands for exact half post-armor damage", () => {
  const forcedMiss = {
    ...handCannoneer,
    hp: 1_000_000,
    ranged: { ...handCannoneer.ranged, accuracy_percent: 0 },
  };
  const armorClasses = Object.fromEntries(
    Object.keys(handCannoneer.attack_classes).map((classId) => [classId, 100]));
  const durableTarget = {
    ...arbalester,
    hp: 1_000_000,
    reload_seconds: 1000,
    armor_classes: armorClasses,
  };
  assert.equal(calculateDamage({ mechanics: forcedMiss }, { mechanics: durableTarget }), 1);
  const world = run([
    spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: forcedMiss }),
    spawn({ referenceId: 2, owner: 3, x: 7, y: 4, mechanics: durableTarget }),
  ], 6000);
  const hits = world.eventLog.filter((event) => (
    event.type === "damage" && event.actorId === 1 && event.kind === "stray-projectile"
  ));
  assert.ok(hits.length >= 10, `expected repeated reduced hits, got ${hits.length}`);
  assert.ok(hits.every(({ amount }) => amount === 0.5));
  assert.equal(world.eventLog.some((event) => (
    event.type === "damage" && event.actorId === 1 && event.kind === "ranged-projectile"
  )), false, "accuracy-zero shots must never become full hits");
});


test("Siege Onager falloff is measured from each victim body edge", () => {
  const mechanics = { collision_size_tiles: { x: 0.2, y: 0.2 } };
  const victim = (x) => ({ x, y: 0, mechanics });
  assert.equal(blastFalloffFraction(victim(0.1), 0, 0, 1.5), 1);
  assert.ok(Math.abs(blastFalloffFraction(victim(0.75), 0, 0, 1.5)
    - (1 - 0.55 / 1.5)) < 1e-12);
  assert.equal(blastFalloffFraction(victim(1.7), 0, 0, 1.5), 0);
  assert.equal(blastFalloffFraction(victim(1.701), 0, 0, 1.5), null);
});


test("one Onager shot exposes nine heading-oriented equal-area debris points", () => {
  const points = siegeDebrisLandingPoints({
    impactX: 5,
    impactY: 0,
    shooterX: 0,
    shooterY: 0,
    count: 9,
  });
  assert.equal(points.length, 9);
  for (let index = 0; index < points.length; index += 1) {
    const radius = Math.hypot(points[index].x - 5, points[index].y);
    assert.ok(Math.abs(radius - Math.sqrt((index + 0.5) / 9)) < 1e-12);
  }
  assert.ok(Math.abs(projectileArcFlightFactor(0.4) - 1.3337054031759343) < 1e-12);
});


test("a zero-frame-delay siege shell releases on the next engine tick", () => {
  assert.equal(onager.frame_delay, 0);
  assert.equal(attackDelayTicks(onager), 0);
});


test("an Onager-family shell released during PATROL reaction keeps the command aim", () => {
  const durableOnager = { ...onager, hp: 10_000 };
  const durableTarget = inert(arbalester);
  let world = createWorld({
    ratio: "onager-patrol-command-aim",
    map: { width: 20, height: 20, obstacles: [] },
    units: [
      spawn({
        referenceId: 1,
        owner: 2,
        x: 12,
        y: 3,
        mechanics: durableOnager,
        behaviorFamily: "onager",
      }),
      spawn({
        referenceId: 2,
        owner: 3,
        x: 5.5,
        y: 10,
        mechanics: durableTarget,
      }),
    ],
    triggers: [{
      trigger_index: 0,
      name: "Starting",
      looping: false,
      conditions: [],
      effects: [{
        type: "patrol",
        owner: 2,
        x: 2,
        y: 13,
        area: { x1: 8, y1: 0, x2: 15, y2: 7 },
        effect_index: 1,
      }],
    }],
    disableAiOrders: true,
  });
  for (let tick = 0; tick < 60 && !(world.projectiles?.length > 0); tick += 1) {
    world = stepWorld(world);
  }
  const shell = world.projectiles?.find(({ kind }) => kind === "shell");
  assert.ok(shell, "the early PATROL scan must release an Onager shell");
  assert.equal(shell.targetId, 2, "the acquired combat target remains the unit");
  assert.deepEqual([shell.aimX, shell.aimY], [2, 13]);
});


test("Siege Onager primary splash damages an allied Player-4 body", () => {
  const targetMechanics = inert(arbalester);
  const allyMechanics = inert(arbalester);
  let world = createWorld({
    ratio: "onager-player4-friendly-fire",
    units: [
      spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: { ...onager, hp: 10_000 }, count: 3 }),
      spawn({ referenceId: 2, owner: 3, x: 8, y: 4, mechanics: targetMechanics, count: 3 }),
      spawn({ referenceId: 3, owner: 4, x: 8, y: 5, mechanics: allyMechanics, count: 3 }),
    ],
    diplomacyByOwner: {
      2: { 3: 3, 4: 0 },
      3: { 2: 3, 4: 3 },
      4: { 2: 0, 3: 3 },
    },
    disableAiOrders: true,
  });
  for (let index = 0; index < 400; index += 1) world = stepWorld(world);
  assert.ok(world.eventLog.some((event) => (
    event.type === "damage"
      && event.actorId === 1
      && event.targetId === 2
      && event.kind === "shell-projectile"
  )), "the hostile aim-point body must take the primary blast");
  assert.ok(world.eventLog.some((event) => (
    event.type === "damage"
      && event.actorId === 1
      && event.targetId === 3
      && event.kind === "shell-projectile"
  )), "friendly-fire splash must include the allied Player-4 body");
});


test("Siege Onager shell keeps its launch-time aim when a target moves away", () => {
  const runner = inert(arbalester, { speed_tiles_per_second: 4 });
  let world = createWorld({
    ratio: "onager-no-ballistics",
    map: { width: 20, height: 20, obstacles: [] },
    units: [
      spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: { ...onager, hp: 10_000 } }),
      spawn({ referenceId: 2, owner: 3, x: 8, y: 4, mechanics: runner }),
    ],
    triggers: [{
      trigger_index: 0,
      name: "Runner",
      looping: false,
      conditions: [],
      effects: [{
        type: "patrol",
        owner: 3,
        x: 8,
        y: 18,
        area: { x1: 7, y1: 3, x2: 9, y2: 5 },
        effect_index: 1,
      }],
    }],
    disableAiOrders: true,
  });
  for (let index = 0; index < 300; index += 1) world = stepWorld(world);
  assert.ok(world.eventLog.some((event) => (
    event.type === "attack-start" && event.actorId === 1
  )), "the Onager must release at least one shell");
  assert.equal(world.eventLog.some((event) => (
    event.type === "damage"
      && event.actorId === 1
      && event.targetId === 2
      && event.kind === "shell-projectile"
  )), false, "a shell must not home onto the target after launch");
});


test("the new ranged fixtures expose their DAT minimum ranges", () => {
  assert.equal(rangedSpec(skirmisher).minRangeTiles, 1);
  assert.equal(rangedSpec(onager).minRangeTiles, 3);
  const skirm = spawn({
    referenceId: 1, owner: 2, x: 4, y: 4, mechanics: skirmisher, count: 3,
  });
  const close = spawn({
    referenceId: 2, owner: 3, x: 4.5, y: 4, mechanics: arbalester, count: 3,
  });
  const far = spawn({
    referenceId: 3, owner: 3, x: 6, y: 4, mechanics: arbalester, count: 3,
  });
  assert.equal(isWithinReach(skirm, close), false);
  assert.equal(isWithinReach(skirm, far), true);
});
