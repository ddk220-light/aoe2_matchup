import assert from 'node:assert/strict';
import test from 'node:test';
import {ExactNoRouteCache} from '../src/combat/no-route-cache.js';

test('negative proofs distinguish every graph, goal and start input exactly',()=>{
  const cache=new ExactNoRouteCache();
  const fields=Array.from({length:5},()=>new Uint8Array(4));
  const key=cache.key(2,2,0,fields);cache.rememberExhausted(key);
  assert(cache.has(cache.key(2,2,0,fields.map(f=>f.slice()))));
  assert(!cache.has(cache.key(1,4,0,fields)));
  assert(!cache.has(cache.key(2,2,1,fields)));
  for(let field=0;field<fields.length;field++)for(let cell=0;cell<4;cell++){
    const changed=fields.map(f=>f.slice());changed[field][cell]=1;
    assert(!cache.has(cache.key(2,2,0,changed)));
  }
});

test('cache size is bounded and large grids decline caching',()=>{
  const cache=new ExactNoRouteCache(2);
  cache.rememberExhausted('a');cache.rememberExhausted('b');assert(cache.has('a'));
  cache.rememberExhausted('c');assert(!cache.has('b'));assert(cache.has('a'));assert(cache.has('c'));
  assert.equal(cache.key(100,100,0,[]),null);cache.rememberExhausted(null);
  assert.equal(cache.statistics().entries,2);assert(!cache.has(null));
});
