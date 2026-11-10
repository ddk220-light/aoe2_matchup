import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { advancePersistentChaseRoute, planPersistentChaseRoute } from '../src/combat/chase-path.js';
import { createUnitState } from '../src/combat/unit-state.js';
import { createWorld, stepWorld } from '../src/combat/world.js';

const mechanics = JSON.parse(readFileSync(new URL('../fixtures/unit_stats/champion_chinese_imperial.json', import.meta.url)));
const make = (referenceId, owner, x, y) => createUnitState({referenceId, owner, x, y,
  facing: 0, mechanics, acquisitionRank: 0, acquisitionCount: 1});

test('terminal waypoint smoothing cannot stop short of melee range', () => {
  const route = {targetX: 1.6, targetY: 1, waypointIndex: 0,
    waypoints: [{x: 1.1, y: 1}], goalStopSpec: {metric: 'chebyshev', reach: 0.5}};
  assert.equal(advancePersistentChaseRoute({x: 1, y: 1}, route).waypointIndex, 0);
  assert.equal(advancePersistentChaseRoute({x: 1.1, y: 1}, route).waypointIndex, 1);
});

test('terminal projectile goal remains circular', () => {
  const route = {targetX: 2, targetY: 2, waypointIndex: 0,
    waypoints: [{x: 1.3, y: 1.3}], goalStopSpec: {metric: 'euclidean', reach: 1}};
  assert.equal(advancePersistentChaseRoute({x: 1.2, y: 1.2}, route).waypointIndex, 0);
  assert.equal(advancePersistentChaseRoute({x: 1.3, y: 1.3}, route).waypointIndex, 1);
});

test('recovery moves to an in-range cell centre instead of treating the actor as already there', () => {
  const mover = make(1, 2, 2.51, 3), target = make(2, 3, 3.12, 3);
  const route = planPersistentChaseRoute(mover, target, [],
    {width: 8, height: 8, obstacles: []}, {includeNonObstructingContacts: true});
  assert.ok(route?.waypoints.length > 0);
  assert.ok(route.goalStopSpec);
  assert.equal(advancePersistentChaseRoute(mover, route).waypointIndex, 0);
});

test('a narrow legal corridor can be routed without shrinking any collision body', () => {
  const mover = make(1, 2, 4.25, 2), target = make(2, 3, 4.25, 5);
  const obstacles = Array.from({length: 17}, (_, i) => i / 2).flatMap(y =>
    [3.5, 5].map(x => ({x, y, radius: 0.5})));
  const route = planPersistentChaseRoute(mover, target, [],
    {width: 8, height: 8, obstacles}, {includeNonObstructingContacts: true});
  assert.ok(route?.waypoints.length > 0);
  assert.equal(route.waypointTolerance, 0.0625 * 0.75);
  for (const point of route.waypoints) for (const obstacle of obstacles) {
    assert.ok(Math.hypot(point.x - obstacle.x, point.y - obstacle.y) >= 0.7);
  }
});

test('an unengaged scenario patrol returns and begins another outward leg', () => {
  let world = createWorld({ratio: 'synthetic-patrol-loop',
    map: {width: 30, height: 30, obstacles: []},
    units: [make(1, 2, 4, 4), make(2, 3, 25, 25)],
    triggers: [{trigger_index: 0, name: 'patrol', looping: false, conditions: [],
      effects: [{type: 'patrol', owner: 2, x: 8, y: 4,
        area: {x1: 3, y1: 3, x2: 5, y2: 5}, effect_index: 1}]}], disableAiOrders: true});
  let returning = false, outwardAgain = false;
  for (let tick = 0; tick < 1500; tick++) {
    world = stepWorld(world);
    const unit = world.units[0];
    returning ||= unit.moveOrder?.patrolReturning === true && unit.x < 7.5;
    if (returning && unit.moveOrder?.patrolReturning === false && unit.x > 4.5) {
      outwardAgain = true; break;
    }
  }
  assert.ok(returning && outwardAgain);
});

test('a dead opening patrol anchor does not prevent a delayed member acquiring a live enemy', () => {
  let world = createWorld({ratio: 'synthetic-dead-anchor',
    map: {width: 20, height: 20, obstacles: []},
    units: [make(1, 2, 4, 4), make(2, 3, 6, 4), make(3, 3, 6, 5)],
    triggers: [{trigger_index: 0, name: 'patrol', looping: false, conditions: [],
      effects: [{type: 'patrol', owner: 2, x: 10, y: 4,
        area: {x1: 3, y1: 3, x2: 5, y2: 5}, effect_index: 1}]}], disableAiOrders: true});
  world = stepWorld(world);
  world = {...world, patrolOpeningTargetByOwner: new Map([[2, Object.freeze([2])]]),
    units: world.units.map(unit => unit.referenceId === 2 ? {...unit, alive: false, hp: 0}
      : unit.referenceId === 1 ? {...unit, openingAcquisitionComplete: false,
        pursuitTargetId: null, moveOrder: {...unit.moveOrder, nextOpeningScanTick: 0}}
      : unit)};
  world = stepWorld(world);
  assert.equal(world.units[0].pursuitTargetId, 3);
});
