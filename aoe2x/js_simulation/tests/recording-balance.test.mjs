import assert from 'node:assert/strict';
import test from 'node:test';
import {createLabPlan} from '../tools/aoe2lab_worker.mjs';
import {geometricCounts,comparisonResourcesFor, fieldedHussarBuffer, POLICY, DEFAULT_RESOURCE_WEIGHTS} from '../src/recording-balance.js';
function plan(a,b='paladin') {return createLabPlan({schemaVersion:1,side2:{slug:a},side3:{slug:b,civ:b==='paladin'?'Spanish':undefined},balance:{mode:'geometric_shared_discount',cap:27,maxResources:5000}});}
test('new resource weights and full discounts reach actual army counts',()=>{
  for(const [slug,count,cost] of [['elite_champi_warrior_incas',18,62.5],['elite_champi_warrior_mapuche',20,77.5],['elite_blackwood_archer_tupi',15,42.75]]) {
    const p=plan(slug);assert.deepEqual([p.side2.count,p.side3.count],[27,count]);assert.equal(p.side2.comparison.comparisonCost,cost);
    assert.deepEqual(p.balance.weights,DEFAULT_RESOURCE_WEIGHTS);
  }
});
test('registered Inca Slinger uses its fully discounted cost against Jomsviking',()=>{
  const p=createLabPlan({schemaVersion:1,
    side2:{slug:'elite_jomsviking_danes',civ:'Danes'},
    side3:{slug:'imp_slinger_incas',civ:'Incas'},
    scenario:{player4Buffer:'none'}});
  assert.deepEqual(p.side3.effectiveCost,{food:35,wood:25,gold:0});
  assert.equal(p.side3.weightedCost,57.5);
  assert.deepEqual([p.side2.count,p.side3.count],[23,27]);
  assert.equal(p.side3.comparison.population,1);
  assert.equal(p.scenario.hasPlayer4Gate,false);
});
test('half-population and one-population units use the same comparison weight',()=>{
  for(const slug of ['elite_blackwood_archer_tupi','elite_karambit_warrior']) {
    const p=plan(slug);
    assert.equal(p.side2.comparison.population,1);
    assert.equal(p.side2.comparison.catalogPopulation,0.5);
    assert.equal(p.side2.comparison.score,p.side2.comparison.comparisonCost);
    assert.equal(p.balance.comparisonPolicy,POLICY);
    assert.deepEqual([p.side2.count,p.side3.count],geometricCounts(p.side2.comparison.comparisonCost,p.side3.comparison.comparisonCost,27));
  }
});
test('shared and exclusive discounts are fully effective and actual prices remain intact',()=>{
  const p=plan('elite_champi_warrior_incas','elite_huskarl');
  assert.deepEqual(p.side2.effectiveCost,{food:35,wood:0,gold:25});
  assert.equal(p.side2.weightedCost,62.5);assert.equal(p.side2.comparison.comparisonCost,62.5);
  assert.equal(p.side3.comparison.comparisonCost,p.side3.weightedCost);
  assert.equal(p.side3.comparison.sharedAcrossCivilizations,false);
});
test('geometric counts preserve orientation, cap and halves-up rounding',()=>{
  assert.deepEqual(geometricCounts(1,4,27),[27,14]);
  assert.deepEqual(geometricCounts(4,1,27),[14,27]);
  assert.deepEqual(geometricCounts(3,3,27),[27,27]);
});
test('all resource discounts and cost increases are fully effective',()=>{
  const p={baseCost:{food:50,wood:40,gold:25},effectiveCost:{food:35,wood:20,gold:10},unitsPerPurchase:1};
  assert.deepEqual(comparisonResourcesFor(p,true).comparisonResources,p.effectiveCost);
  assert.deepEqual(comparisonResourcesFor(p,false).comparisonResources,p.effectiveCost);
  assert.deepEqual(comparisonResourcesFor({...p,effectiveCost:{food:60,wood:40,gold:25}},true).comparisonResources,{food:60,wood:40,gold:25});
});
test('batch costs are normalized once; effective prices already describe one physical unit',()=>{
  const p={baseCost:{food:0,wood:40,gold:60},effectiveCost:{food:0,wood:10,gold:20},unitsPerPurchase:2};
  const result=comparisonResourcesFor(p,true);
  assert.deepEqual(result.basePerUnit,{food:0,wood:20,gold:30});
  assert.deepEqual(result.comparisonResources,{food:0,wood:10,gold:20});
});
test('new Node requests default to the approved formula; explicit old mode remains available',()=>{
  const request={schemaVersion:1,side2:{slug:'elite_champi_warrior_incas'},side3:{slug:'paladin',civ:'Spanish'}};
  const current=createLabPlan(request);
  const legacy=createLabPlan({...request,balance:{mode:'equal_resources',weights:{food:1,wood:1,gold:1}}});
  assert.equal(current.balance.mode,'geometric_shared_discount');
  assert.deepEqual([current.side2.count,current.side3.count],[27,18]);
  assert.deepEqual([legacy.side2.count,legacy.side3.count],[27,12]);
  assert.notEqual(current.planHash,legacy.planHash);
});
test('invalid numerical inputs cannot silently produce NaN counts',()=>{
  for(const score of [0,-1,NaN,Infinity]) assert.throws(()=>geometricCounts(score,100,27),/positive and finite/);
  for(const cap of [0,28,2.5,NaN]) assert.throws(()=>geometricCounts(60,135,cap),/Cap/);
  assert.throws(()=>comparisonResourcesFor({baseCost:{food:50,wood:0,gold:25},effectiveCost:{food:35,wood:0,gold:25},unitsPerPurchase:0},true),/Invalid/);
});

test('buffer interpolation clamps and rounds halves up at resource boundaries',()=>{
  for(const [cost,count] of [[1,5],[1000,5],[1093.5,5],[1899.99,5],[1900,6],[2700,6],[5499.99,7],[5500,8],[10000,10],[12150,10]]) {
    assert.equal(fieldedHussarBuffer(3,1,cost).hussars,count);
  }
  for(const cost of [0,-1,NaN,Infinity]) assert.throws(()=>fieldedHussarBuffer(3,27,cost));
});

test('explicit historical buffers scale from the actual ranged count in either orientation',()=>{
  for(const [ranged,melee,expected] of [
    ['elite_blackwood_archer_tupi','elite_jaguar_warrior_aztecs',5],
    ['houfnice_bohemians','elite_jaguar_warrior_aztecs',7],
    ['houfnice_bohemians','elite_war_elephant_persians',10],
  ]) {
    for(const reversed of [false,true]) {
      const p=createLabPlan({schemaVersion:1,side2:{slug:reversed?melee:ranged},side3:{slug:reversed?ranged:melee},scenario:{player4Buffer:'scaled'}});
      const owner=reversed?3:2;
      assert.equal(p.scenario.player4Buffer,'scaled');
      assert.equal(p.scenario.player4Count,expected);
      assert.equal(p.scenario.player4Scaling.rangedOwner,owner);
      assert.equal(p.scenario.player4Scaling.armyWeightedCost,p[`side${owner}`].count*p[`side${owner}`].weightedCost);
      if(ranged==='houfnice_bohemians' && expected===7) {
        assert.ok(p[`side${owner}`].count<27);
        assert.ok(p.scenario.player4Scaling.armyWeightedCost<10000);
      }
    }
  }
});

test('same-class plans have no screen and explicit historical overrides remain available',()=>{
  for(const slugs of [['elite_blackwood_archer_tupi','houfnice_bohemians'],['elite_jaguar_warrior_aztecs','elite_teutonic_knight']]) {
    const p=createLabPlan({schemaVersion:1,side2:{slug:slugs[0]},side3:{slug:slugs[1]}});
    assert.equal(p.scenario.hasPlayer4Gate,false);
    assert.equal(p.scenario.player4Scaling,undefined);
    assert.equal(p.scenario.player4Count,undefined);
  }
  const input={schemaVersion:1,side2:{slug:'elite_blackwood_archer_tupi'},side3:{slug:'elite_jaguar_warrior_aztecs'}};
  const golden=createLabPlan({...input,scenario:{player4Buffer:'golden'}});
  assert.equal(golden.scenario.player4Count,undefined);
  assert.equal(golden.scenario.player4Scaling,undefined);
  const explicit=createLabPlan({...input,scenario:{player4Count:5}});
  assert.equal(explicit.scenario.player4Count,5);
  assert.equal(explicit.scenario.player4Scaling,undefined);
  assert.throws(()=>createLabPlan({...input,scenario:{player4Count:5,player4Buffer:'scaled'}}),/no explicit/);
});
