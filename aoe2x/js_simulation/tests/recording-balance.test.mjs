import assert from 'node:assert/strict';
import test from 'node:test';
import {createLabPlan} from '../tools/aoe2lab_worker.mjs';
import {geometricCounts,comparisonResourcesFor} from '../src/recording-balance.js';
function plan(a,b='paladin') {return createLabPlan({schemaVersion:1,side2:{slug:a},side3:{slug:b,civ:b==='paladin'?'Spanish':undefined},balance:{mode:'geometric_shared_discount',cap:27,maxResources:5000}});}
test('Champi is unchanged and Blackwood no longer gets a population multiplier',()=>{
  for(const [slug,count,cost] of [['elite_champi_warrior_incas',19,67.5],['elite_champi_warrior_mapuche',20,75],['elite_blackwood_archer_tupi',15,40]]) {
    const p=plan(slug);assert.deepEqual([p.side2.count,p.side3.count],[27,count]);assert.equal(p.side2.comparison.comparisonCost,cost);
  }
});
test('half-population and one-population units use the same comparison weight',()=>{
  for(const slug of ['elite_blackwood_archer_tupi','elite_karambit_warrior']) {
    const p=plan(slug);
    assert.equal(p.side2.comparison.population,1);
    assert.equal(p.side2.comparison.catalogPopulation,0.5);
    assert.equal(p.side2.comparison.score,p.side2.comparison.comparisonCost);
    assert.equal(p.balance.comparisonPolicy,'geometric_shared_discount_unit_count_v2');
    assert.deepEqual([p.side2.count,p.side3.count],geometricCounts(p.side2.comparison.comparisonCost,p.side3.comparison.comparisonCost,27));
  }
});
test('unique discounts stay fully effective and actual prices remain intact',()=>{
  const p=plan('elite_champi_warrior_incas','elite_huskarl');
  assert.equal(p.side2.weightedCost,60);assert.equal(p.side2.comparison.comparisonCost,67.5);
  assert.equal(p.side3.comparison.comparisonCost,p.side3.weightedCost);
  assert.equal(p.side3.comparison.sharedAcrossCivilizations,false);
});
test('geometric counts preserve orientation, cap and halves-up rounding',()=>{
  assert.deepEqual(geometricCounts(1,4,27),[27,14]);
  assert.deepEqual(geometricCounts(4,1,27),[14,27]);
  assert.deepEqual(geometricCounts(3,3,27),[27,27]);
});
test('food/wood savings are halved; gold savings and cost increases are intact',()=>{
  const p={baseCost:{food:50,wood:40,gold:25},effectiveCost:{food:35,wood:20,gold:10},unitsPerPurchase:1};
  assert.deepEqual(comparisonResourcesFor(p,true).comparisonResources,{food:42.5,wood:30,gold:10});
  assert.deepEqual(comparisonResourcesFor(p,false).comparisonResources,p.effectiveCost);
  assert.deepEqual(comparisonResourcesFor({...p,effectiveCost:{food:60,wood:40,gold:25}},true).comparisonResources,{food:60,wood:40,gold:25});
});
test('batch normalization precedes discount calculation',()=>{
  const p={baseCost:{food:0,wood:40,gold:60},effectiveCost:{food:0,wood:10,gold:20},unitsPerPurchase:2};
  assert.deepEqual(comparisonResourcesFor(p,true).comparisonResources,{food:0,wood:15,gold:20});
});
test('new Node requests default to the approved formula; explicit old mode remains available',()=>{
  const request={schemaVersion:1,side2:{slug:'elite_champi_warrior_incas'},side3:{slug:'paladin',civ:'Spanish'}};
  const current=createLabPlan(request);
  const legacy=createLabPlan({...request,balance:{mode:'equal_resources'}});
  assert.equal(current.balance.mode,'geometric_shared_discount');
  assert.deepEqual([current.side2.count,current.side3.count],[27,19]);
  assert.deepEqual([legacy.side2.count,legacy.side3.count],[27,12]);
  assert.notEqual(current.planHash,legacy.planHash);
});
test('invalid numerical inputs cannot silently produce NaN counts',()=>{
  for(const score of [0,-1,NaN,Infinity]) assert.throws(()=>geometricCounts(score,100,27),/positive and finite/);
  for(const cap of [0,28,2.5,NaN]) assert.throws(()=>geometricCounts(60,135,cap),/Cap/);
  assert.throws(()=>comparisonResourcesFor({baseCost:{food:50,wood:0,gold:25},effectiveCost:{food:35,wood:0,gold:25},unitsPerPurchase:0},true),/Invalid/);
});
