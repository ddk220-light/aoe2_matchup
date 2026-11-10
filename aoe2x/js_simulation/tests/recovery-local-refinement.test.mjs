import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {createUnitState} from '../src/combat/unit-state.js';
import {planPersistentChaseRoute} from '../src/combat/chase-path.js';

const mechanics = JSON.parse(readFileSync(new URL('../fixtures/unit_stats/champion_chinese_imperial.json', import.meta.url)));
const unit = (referenceId, owner, x, y) => createUnitState({referenceId, owner, x, y, facing: 0, mechanics});

test('local refinement finds a contact-width corridor that the coarser raster misses', () => {
  const mover = unit(1, 2, 4.25, 2), target = unit(2, 3, 4.25, 5);
  const obstacles = Array.from({length: 17}, (_, i) => i / 2).flatMap(y =>
    [3.54, 4.96].map(x => ({x, y, radius: 0.5})));
  const route = planPersistentChaseRoute(mover, target, [],
    {width: 8, height: 8, obstacles}, {includeNonObstructingContacts: true});
  assert.ok(route?.waypoints.length > 0);
  assert.equal(route.waypointTolerance, 0.015625 * 0.75);
  assert.equal(route.targetX, target.x); assert.equal(route.targetY, target.y);
  let before = mover;
  // Check swept static clearance, not only the legal cell centres.
  for (const point of route.waypoints) {
    for (const o of obstacles) {
      const dx = point.x - before.x, dy = point.y - before.y;
      const t = Math.max(0, Math.min(1, ((o.x - before.x) * dx + (o.y - before.y) * dy) / (dx * dx + dy * dy)));
      assert.ok(Math.hypot(before.x + t * dx - o.x, before.y + t * dy - o.y) >= 0.7);
    }
    before = point;
  }
});

test('local refinement does not invent a path through a physically closed passage', () => {
  const mover = unit(1, 2, 2, 4), target = unit(2, 3, 6, 4);
  const obstacles = Array.from({length: 17}, (_, i) => ({x: 4, y: i / 2, radius: 0.5}));
  assert.equal(planPersistentChaseRoute(mover, target, [],
    {width: 8, height: 8, obstacles}, {includeNonObstructingContacts: true}).stand, true);
});
