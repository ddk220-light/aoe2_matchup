import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,renameSync,openSync,closeSync,fsyncSync,appendFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';
import {verifyPolicyInputs} from './forecast-no-replay-policy.mjs';
export {digest};
export const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
export const ROOT=resolve(SIM,'../..');
export const DIR=resolve(SIM,'calibration/campaigns/civ-matchups-forecast-validation-2026-11-07');
export const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export const load=path=>JSON.parse(readFileSync(path,'utf8'));
export const lines=path=>readFileSync(path,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
export const gzlines=path=>gunzipSync(readFileSync(path)).toString('utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
export const now=()=>new Date().toISOString();
export function json(path,value){mkdirSync(dirname(path),{recursive:true});const tmp=path+'.tmp',fd=openSync(tmp,'w');
 try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,path);}
export function append(path,value){mkdirSync(dirname(path),{recursive:true});const fd=openSync(path,'a');try{appendFileSync(fd,JSON.stringify(value)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
export const FROZEN=load(resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'));
export function scenario(job){
 const base=FROZEN.scenarios[job.scenarioHash]??{...Object.values(FROZEN.scenarios).find(s=>s.family===job.family),engineFamily:job.engineFamily};
 assert.equal(digest(base),job.scenarioHash);return base;
}
export function payload(job,seed){return {jobId:job.id,seed,
 teams:job.teamKeys.map((key,i)=>({mechanics:FROZEN.profiles[key].mechanics,count:job.counts[i]})),
 scenario:scenario(job),disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false};}
export function required(rows){const seeds=new Map(rows.map(r=>[r.seed,r]));
 const initial=[0,1,2].filter(s=>!seeds.has(s));if(initial.length)return initial;
 return new Set([0,1,2].map(s=>seeds.get(s).winnerOwner)).size>1?[3,4,5,6,7,8,9].filter(s=>!seeds.has(s)):[];
}
export function canonicalOutcome(job,rows){assert.equal(required(rows).length,0,'incomplete seed set');
 const winners=new Set(rows.map(r=>r.winnerOwner));if(winners.size!==1||!winners.has(2)&&!winners.has(3))return 'close_uncertain';
 const hash=job.profileHashes[[...winners][0]-2];return hash===job.pairKey.split('|')[0]?'a_win':'b_win';}
export function exact(actual,expected){return ['ticks','winnerOwner','finalStateHash','eventLogHash'].every(k=>actual[k]===expected[k]);}
export function verifyManifest(){const m=load(resolve(DIR,'manifest.json')),{campaignHash,...body}=m;
 assert.equal(digest(body),campaignHash);assert.equal(process.version,m.nodeVersion);
 assert.equal(digest(Object.fromEntries(Object.entries(process.env).filter(([k])=>k.startsWith('AOE2X_EXP_')).sort())),digest(m.simulationEnvironment));
 verifyPolicyInputs(m,ROOT,DIR);
 return m;
}
