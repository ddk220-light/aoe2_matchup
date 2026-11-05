import assert from 'node:assert/strict';
import test from 'node:test';
import {hashCanonicalJson,hashCanonicalJsonStreaming} from '../src/canonical-json.js';

test('streamed canonical hash agrees on nested and sparse values', () => {
  const shared={z:-0,a:'emoji 🚀 and quote " and \\'};
  const sparse=[,shared,,3.14];
  const examples=[null,true,false,0,-0,1e-9,'Unicode é 🚀',[],{},
    {b:[shared,{text:'a\nb\t\u0000'}],a:sparse},sparse,
    Array.from({length:100000},(_,i)=>({tick:i,actor:i%27,type:'move',point:[i/60,i%13]}))];
  for(const value of examples)assert.equal(hashCanonicalJsonStreaming(value),hashCanonicalJson(value));
});

test('streamed canonical hash rejects the same unsupported values', () => {
  const cyclic={};cyclic.self=cyclic;
  for(const value of [undefined,NaN,Infinity,BigInt(1),cyclic,new Date()]){
    assert.throws(()=>hashCanonicalJson(value));
    assert.throws(()=>hashCanonicalJsonStreaming(value));
  }
});
