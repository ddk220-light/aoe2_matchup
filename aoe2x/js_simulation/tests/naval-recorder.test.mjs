import assert from 'node:assert/strict';
import test from 'node:test';
import { createLabPlan, runSeed } from '../tools/aoe2lab_worker.mjs';

const request = (maxResources = 5000, cap = 15) => ({
  schemaVersion: 1,
  side2: { slug: 'galleon_portuguese' },
  side3: { slug: 'fire_ship_bulgarians' },
  balance: { mode: 'equal_resources', cap, maxResources },
  scenario: { goldenFamily: 'water', player4Buffer: 'none' },
});

test('naval recording uses discounted costs, 15 authored slots, and no simulation', async () => {
  const p = createLabPlan(request());
  assert.deepEqual([p.side2.count, p.side3.count], [15, 14]);
  assert.deepEqual([p.side2.armyWeightedResources, p.side3.armyWeightedResources], [1710, 1680]);
  assert.equal(p.scenario.hasPlayer4Gate, false);
  await assert.rejects(runSeed(p, 1), /recording-only/);
  assert.throws(() => createLabPlan(request(5000, 16)), /15 slots/);
});

test('resource ceiling reduces armies and rejects unaffordable battles', () => {
  const p = createLabPlan(request(1000));
  assert.deepEqual([p.side2.count, p.side3.count], [8, 7]);
  assert.throws(() => createLabPlan(request(100)), /cannot fund/);
  assert.throws(() => createLabPlan(request(-1)), /positive/);
});
