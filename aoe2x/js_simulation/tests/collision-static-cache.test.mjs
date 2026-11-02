import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {resolveMovementProposals} from '../src/combat/collision.js';
import {createPairInteractionSnapshot} from '../src/combat/pair-interactions.js';

// Compare the memoized solve with exactly the same solver, with only the
// memoization bypassed. This exercises invalidation and tolerance changes.
const sourceUrl = new URL('../src/combat/collision.js', import.meta.url);
const source = readFileSync(sourceUrl, 'utf8');
assert(source.includes('function staticGeometryViolation('));
const uncachedSource = source.replace(
  /function staticGeometryViolation\([\s\S]*?\nfunction computeStaticGeometryViolation/,
  'function staticGeometryViolation(body, obstacles, bounds, tolerance) {\n'
  + '  return computeStaticGeometryViolation(body, obstacles, bounds, tolerance);\n'
  + '}\n\nfunction computeStaticGeometryViolation',
).replace(/from "(\.\/[^"]+)"/g, (_, relative) => `from "${new URL(relative, sourceUrl).href}"`);
const uncached = (await import('data:text/javascript;base64,' + Buffer.from(uncachedSource).toString('base64'))).resolveMovementProposals;
const run = (solve, input, recovery = false) => {
  const diagnostics = [], collisionRecoveryState = {active: recovery};
  const result = solve(input.snapshot, input.proposals, input.map, {
    pairInteractions: createPairInteractionSnapshot({contactReservations: new Map(input.reservations ?? [])}),
    collisionRecoveryState, onCollisionDiagnostics: value => diagnostics.push(value),
  });
  for (const unit of result) for (const key of ['strictGeometry', 'slopGeometry']) assert(!Object.hasOwn(unit, key));
  return {result, diagnostics, collisionRecoveryState};
};

test('static memoization preserves strict/slop recovery, every position and diagnostic', () => {
  const {input} = JSON.parse(readFileSync(new URL('../fixtures/collision/ranking-crossbow-hussar-residual.json', import.meta.url)));
  for (const active of [false, true]) assert.deepEqual(run(resolveMovementProposals, input, active), run(uncached, input, active));
});

test('static geometry cache invalidates on displacement and never survives changed obstacles or bounds', () => {
  let seed = 9127;
  const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 2**32);
  for (let iteration = 0; iteration < 30; iteration++) {
    const snapshot = Array.from({length: 12}, (_, i) => ({referenceId: i + 1, owner: i % 2 + 1,
      unitMaster: 567, x: 1 + i % 4 * .9, y: 1 + Math.floor(i / 4) * .9,
      mechanics: {collision_size_tiles: {x: .2, y: .2}}}));
    const proposals = snapshot.map(u => ({referenceId: u.referenceId, dx: (random() - .5) * .8, dy: (random() - .5) * .8}));
    const input = {snapshot, proposals, map: {width: 5 + random(), height: 5 + random(),
      obstacles: [{x: 4.3, y: 1.2 + random(), radius: .3}, {x: .3, y: 2.2, radius: .2}]}};
    assert.deepEqual(run(resolveMovementProposals, input, iteration % 2 === 0), run(uncached, input, iteration % 2 === 0));
  }
});
