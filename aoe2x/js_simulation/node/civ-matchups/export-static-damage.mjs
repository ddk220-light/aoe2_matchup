#!/usr/bin/env node
// Export full-health, one-hit damage against every profile as predictive data.
// This does not simulate a fight and does not stand in for a matchup result.
import {readFileSync, writeFileSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {calculateDamage} from '../../src/combat/attacks.js';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const source=resolve(process.argv[2]??'/workspace/aoe2_path_recovery/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/latest-inference');
const destination=process.argv[3];
if(!destination)throw new Error('output path required');
const variants=JSON.parse(readFileSync(resolve(source,'variant-profiles.json')));
const definition=JSON.parse(readFileSync(resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const byHash=new Map();
for(const variant of variants){
  const mechanics=definition.profiles[variant.key]?.mechanics;
  if(!mechanics)throw new Error(`missing mechanics ${variant.key}`);
  if(!byHash.has(variant.profileHash))byHash.set(variant.profileHash,mechanics);
}
const hashes=[...byHash.keys()].sort();
const units=hashes.map(hash=>{const mechanics=byHash.get(hash);
  return {mechanics,hp:mechanics.hp,maxHp:mechanics.hp};});
let exceptions=0;
const damage=units.map(actor=>units.map(target=>{
  try{return calculateDamage(actor,target);}catch(error){
    if(!(error instanceof TypeError))throw error;
    exceptions++;return null;
  }
}));
writeFileSync(destination,JSON.stringify({kind:'static full-health one-hit damage features',
  hashes,damage,exceptions,simulationJobsRun:0})+'\n');
console.log(JSON.stringify({profiles:hashes.length,exceptions,output:destination}));
