#!/usr/bin/env node
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {buildPhaseOne} from './civ-matchups/phase-one.mjs';

if(process.argv.includes('--help')) {
  process.stdout.write('Usage: node build-civ-matchup-inference.mjs --phase infer-only [--output DIR] [--campaign-dir DIR]\n');
  process.exit(0);
}
const args=process.argv.slice(2);
if(args[0]!=='--phase'||args[1]!=='infer-only'||(args.length-2)%2)throw new Error('invalid phase/options');
const options={};
for(let i=2;i<args.length;i+=2){
  if(!['--output','--campaign-dir'].includes(args[i]))throw new Error('invalid option');
  if(args[i]==='--campaign-dir'){
    options[args[i]]??=[];options[args[i]].push(args[i+1]);
  }else if(options[args[i]])throw new Error('duplicate output');
  else options[args[i]]=args[i+1];
}
const defaultOutput=fileURLToPath(new URL('../calibration/campaigns/civ-matchups-inference-phase1-2026-10-31/',import.meta.url));
const result=buildPhaseOne(resolve(options['--output']??defaultOutput),{
  campaignDirectories:(options['--campaign-dir']??[]).map(x=>resolve(x))});
process.stdout.write(JSON.stringify({manifestHash:result.manifestHash,coverage:result.coverage.profiles,
  uniqueNeedsSim:result.uniqueNeedsSim,ruleValidation:result.ruleValidation,simulationJobsRun:0},null,2)+'\n');
