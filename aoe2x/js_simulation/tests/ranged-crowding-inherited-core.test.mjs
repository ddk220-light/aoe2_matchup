import assert from 'node:assert/strict';
import test from 'node:test';
import { planRangedCrowding } from '../src/combat/ranged-crowding.js';
import { createPairInteractionSnapshot } from '../src/combat/pair-interactions.js';
import { resolveMovementProposals } from '../src/combat/collision.js';

const map = { width: 10, height: 10, obstacles: [] };
const unit = (referenceId, x, radius, extra = {}) => ({
  referenceId, unitMaster: 1, owner: 2, alive: true, x, y: 4, action: 'moving',
  pursuitTargetId: null, engagedTargetId: null, attackTargetId: null,
  moveOrder: { kind: 'scenario-patrol', x, y: 8 },
  mechanics: {
    collision_size_tiles: { x: radius, y: radius },
    outline_size_tiles: { x: radius, y: radius },
    speed_tiles_per_second: 1.2, attack_range_tiles: 5,
    ranged: { projectile_speed_tiles_per_second: 7 },
  },
  ...extra,
});
const gap = (a, b) => Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y));

for (const radius of [0.2, 0.5]) {
  test(`inherited compliant overlap below the transit core stays valid (radius ${radius})`, () => {
    let units = [unit(41, 4, radius), unit(42, 4 + 2 * radius * 0.02, radius)];
    const initialGap = gap(...units);
    for (let tick = 0; tick < 3; tick++) {
      const crowd = planRangedCrowding(units,
        units.map(({ referenceId }) => ({ referenceId, dx: 0, dy: 0.01 })), tick);
      // A synthetic inherited state exercises reservation -> collision together.
      // It contains no campaign context, seed or saved battle execution.
      units = resolveMovementProposals(units, crowd.proposals, map, {
        pairInteractions: createPairInteractionSnapshot({ contactReservations: crowd.contactReservations }),
      });
      assert.ok(gap(...units) >= initialGap - 1e-12, 'inherited overlap must not deepen');
    }
    assert.ok(units.some(current => current.y > 4), 'valid shared motion must remain possible');
  });
}

test('new transit compression still keeps a nonzero body core', () => {
  const units = [unit(41, 4, 0.2), unit(42, 4.015, 0.2)];
  const crowd = planRangedCrowding(units, [
    { referenceId: 41, dx: 0.014, dy: 0 },
    { referenceId: 42, dx: 0, dy: 0 },
  ], 0);
  const moved = resolveMovementProposals(units, crowd.proposals, map, {
    pairInteractions: createPairInteractionSnapshot({ contactReservations: crowd.contactReservations }),
  });
  assert.ok(gap(...moved) >= 0.01 - 1e-12, 'fresh movement must not consume the body core');
});

test('an explicit invalid reservation is still rejected by collision validation', () => {
  const units = [unit(41, 4, 0.5), unit(42, 4.02, 0.5)];
  const crowd = planRangedCrowding(units, [], 0);
  const contactReservations = new Map(crowd.contactReservations);
  contactReservations.set('41:42', { ...contactReservations.get('41:42'), collisionExtent: 0.03 });
  assert.throws(() => resolveMovementProposals(units, [], map, {
    pairInteractions: createPairInteractionSnapshot({ contactReservations }),
  }), /starting overlap/);
});
