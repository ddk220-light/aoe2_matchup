import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { hashCanonicalJson } from '../src/canonical-json.js';
import { resolveMovementProposals } from '../src/combat/collision.js';
import { createPairInteractionSnapshot } from '../src/combat/pair-interactions.js';

const unit = (referenceId, x, y, extra = {}) => ({ referenceId, x, y,
  owner: 2, unitMaster: 567, mechanics: { collision_size_tiles: { x: .2, y: .2 } }, ...extra });

test('ranking obstacle residual preserves exact baseline positions, diagnostics, and recovery', () => {
  const fixture = JSON.parse(readFileSync(new URL('../fixtures/collision/ranking-crossbow-hussar-residual.json', import.meta.url)));
  const { input, expected } = fixture;
  const diagnostics = [], collisionRecoveryState = { active: false };
  const result = resolveMovementProposals(input.snapshot, input.proposals, input.map, {
    pairInteractions: createPairInteractionSnapshot({ contactReservations: new Map(input.reservations) }),
    collisionRecoveryState, onCollisionDiagnostics: value => diagnostics.push(value),
  });
  assert.equal(hashCanonicalJson(result), expected.hash);
  assert.deepEqual(diagnostics, expected.diagnostics);
  assert.deepEqual(collisionRecoveryState, expected.recovery);
  assert.ok(result.every(body => !Object.hasOwn(body, 'pairInteractions') && !Object.hasOwn(body, 'staticConstraints')));
});

test('collision caches are scoped to one solve when formation status changes', () => {
  const units = [unit(1, 4, 4), unit(2, 4.45, 4)].map(body => ({ ...body,
    moveOrder: { kind: 'scenario-patrol' }, openingAcquisitionComplete: false }));
  const proposals = [{ referenceId: 1, dx: .08, dy: 0 }, { referenceId: 2, dx: -.08, dy: 0 }];
  const map = { width: 10, height: 10, obstacles: [] };
  const transit = resolveMovementProposals(units, proposals, map);
  const acquired = resolveMovementProposals(units.map(body => ({ ...body, openingAcquisitionComplete: true })), proposals, map);
  assert.equal(transit[0].x, 4.08);
  assert.ok(Math.abs(acquired[0].x - 4.025) < 1e-12);
  assert.ok(acquired[1].x - acquired[0].x >= .4 - 1e-12);
});

test('distant obstacles do not change the exact nearby collision result', () => {
  const units = [unit(1, 4, 4)];
  const proposals = [{ referenceId: 1, dx: .8, dy: .2 }];
  const obstacle = { referenceId: 99, x: 5, y: 4, radius: .5 };
  const distant = Array.from({ length: 60 }, (_, index) => ({ referenceId: index + 1,
    x: 1 + index % 10, y: index < 30 ? 1 : 19, radius: .4 }));
  const alone = resolveMovementProposals(units, proposals, { width: 20, height: 20, obstacles: [obstacle] });
  const surrounded = resolveMovementProposals(units, proposals, { width: 20, height: 20, obstacles: [...distant, obstacle] });
  assert.deepEqual(surrounded, alone);
  assert.equal(alone[0].x, 4.3); assert.equal(alone[0].y, 4.2);
});

test('broad phase retains an obstacle crossed by a long movement', () => {
  const result = resolveMovementProposals([unit(1, 2, 4)], [{ referenceId: 1, dx: 6, dy: 0 }],
    { width: 20, height: 20, obstacles: [{ x: 5, y: 4, radius: .5 }] });
  assert.equal(result[0].x, 4.3);
});
