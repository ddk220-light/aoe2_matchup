import assert from 'node:assert/strict';
import test from 'node:test';
import {createLabPlan} from '../tools/aoe2lab_worker.mjs';
const plan = (slug, overrides={}) => createLabPlan({schemaVersion:1,side2:{slug:'elite_tiger_cavalry_wei'},side3:{slug},balance:{mode:'equal_resources',cap:27},...overrides});

test('Imperial costs include own-civ discounts and cost conversions', () => {
  for (const [slug, cost] of [
    ['elite_huskarl',{food:53,wood:0,gold:25}],
    ['elite_war_wagon',{food:0,wood:100,gold:60}],
    ['elite_magyar_huszar',{food:80,wood:0,gold:0}],
    ['elite_champi_warrior_incas',{food:35,wood:0,gold:25}],
    ['elite_blackwood_archer_tupi',{food:0,wood:17.5,gold:22.5}],
    ['elite_karambit_warrior',{food:25,wood:0,gold:15}],
  ]) assert.deepEqual(plan(slug).side3.effectiveCost,cost);
});

test('Champi vs Huskarl balances both discounted armies', () => {
  const p=plan('elite_huskarl',{side2:{slug:'elite_champi_warrior_incas'}});
  assert.deepEqual([p.side2.count,p.side3.count],[27,20]);
  assert.deepEqual([p.side2.armyWeightedResources,p.side3.armyWeightedResources],[1620,1560]);
  assert.equal(p.balance.costBasis,'fully_upgraded_imperial_v1');
  assert.match(p.balance.costCatalogSha256,/^[a-f0-9]{64}$/);
});

test('unsupported civ override cannot silently borrow another civ discount', () => {
  assert.throws(()=>plan('elite_huskarl',{side3:{slug:'elite_huskarl',civ:'Chinese'}}),/No verified Imperial cost/);
});
