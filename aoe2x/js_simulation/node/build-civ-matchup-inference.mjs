#!/usr/bin/env node
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {buildPhaseOne} from './civ-matchups/phase-one.mjs';

if(process.argv.includes('--help')) {
  process.stdout.write('Usage: node build-civ-matchup-inference.mjs --phase infer-only [--output DIR]\n');
  process.exit(0);
}
const args=process.argv.slice(2);
if(args[0]!=='--phase'||args[1]!=='infer-only'||(args.length!==2 && !(args.length===4&&args[2]==='--output'))) {
  throw new Error('Only --phase infer-only [--output DIR] is supported');
}
const defaultOutput=fileURLToPath(new URL('../calibration/campaigns/civ-matchups-inference-phase1-2026-10-31/',import.meta.url));
const result=buildPhaseOne(resolve(args[3]??defaultOutput));
process.stdout.write(JSON.stringify({manifestHash:result.manifestHash,coverage:result.coverage.profiles,
  uniqueNeedsSim:result.uniqueNeedsSim,ruleValidation:result.ruleValidation,simulationJobsRun:0},null,2)+'\n');
