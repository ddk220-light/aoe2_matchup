// Independent repeated game measurements; no search over engine parameters/seeds.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {simulateFarms} from './farm-gathering-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=path.resolve(process.argv[2]??path.join(root,'aoe2x/js_simulation/calibration/economy/farms-repeated-reference-2026-11-09'));
const previous=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-refinement-2026-11-09');
const read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const stats=a=>{const m=mean(a),sd=Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1));return {n:a.length,mean:m,sd,se:sd/Math.sqrt(a.length)};};
const input=read(path.join(out,'published-observations.json'));
assert.equal(input.extra_seconds.length,36);
assert.equal(input.extra_seconds.flat().filter(x=>x===null).length,2);
for(const row of input.extra_seconds)assert.equal(row.length,8);
for(let i=0;i<8;i++){
 const m=mean(input.extra_seconds.filter(row=>row[i]!==null).map(row=>row[i]+input.offset_seconds));
 assert(Math.abs(m-input.published_column_mean_seconds[i])<=.05,'Transcription must reproduce each published column mean');
}
const fixture=read(path.join(previous,'fixture-none.json'));
assert.equal(fixture.farm.food,input.food);
// Square ring shown in the source image. A1..A4 share an edge with the
// 3x3 building; B1..B4 touch its corners. Rotation is arbitrary.
const origins=[[0,-3],[3,0],[0,3],[-3,0],[3,-3],[3,3],[-3,3],[-3,-3]];
const mill={x0:0,y0:0,x1:3,y1:3};
const farms=origins.map(([x,y],id)=>({id,x0:x,y0:y,x1:x+3,y1:y+3,position:id<4?'side':'corner'}));
const enginePath=path.join(root,'tools/farm-gathering-sim.mjs'),engineHash=sha(enginePath);
const runs=[];
for(let seed=0;seed<36;seed++){
 const r=simulateFarms(fixture,{duration:650,mill,farms,seed,reseed:false});
 const seconds=r.final.farms.map(f=>f.last_depleted_at);
 assert(seconds.every(t=>t>0&&t<650),'All reference farms must deplete');
 assert(r.final.agents.every(a=>Math.abs(a.harvested-input.food)<1e-6));
 runs.push({seed,seconds,checks:r.checks});
 if(seed%6===5)console.log(`Completed ${seed+1}/36 eight-farm runs`);
}
function compare(indices,label){
 const reference=input.extra_seconds.flatMap(row=>indices.filter(i=>row[i]!==null).map(i=>row[i]+input.offset_seconds));
 const model=runs.flatMap(r=>indices.map(i=>r.seconds[i]));
 const a=stats(reference),b=stats(model);
 // The author computes food / mean lifetime, so use the identical estimator.
 const referenceRate=60*input.food/a.mean,modelRate=60*input.food/b.mean;
 return {label,reference_seconds:a,model_seconds:b,reference_rate:referenceRate,model_rate:modelRate,
  difference_percent:(modelRate/referenceRate-1)*100,within_one_percent:Math.abs(modelRate/referenceRate-1)<.01};
}
const groups=[compare([0,1,2,3],'Adjacent (A)'),compare([4,5,6,7],'Corner (B)')];
const positions=input.columns.map((label,i)=>compare([i],label));
const old=read(path.join(previous,'paired-seed-validation.json')).groups;
assert.equal(engineHash,sha(enginePath),'Engine changed during audit');
assert.equal(engineHash,read(path.join(previous,'paired-seed-validation.json')).after_engine_sha256);
const result={source:input.url,engine_sha256:engineHash,seeds:36,
 estimator:'60 * 175 / mean(depletion_seconds), matching the published table. Not mean of individual reciprocal times.',
 scenario:{mill,farms,initial_pool:fixture.farm.initial_pool,food:fixture.farm.food,profile:'none'},
 groups,positions,runs,previous_reference:old.map(r=>({profile:r.profile,position:r.position,reference_rate:r.reference,model_rate:r.after.mean,difference_percent:r.after_error_percent})),
 limitations:input.limitations};
fs.writeFileSync(path.join(out,'comparison.json'),JSON.stringify(result,null,2)+'\n');
fs.writeFileSync(path.join(out,'fixture.json'),JSON.stringify(fixture,null,2)+'\n');
const lines=['# Repeated farming-reference audit','',
 'The engine is unchanged. This audit adds an independent published experiment with 36 sets of eight farms. It does not replace the earlier six-case comparison.','',
 `Source: [Vixark: Folwark Farming Analysis](${input.url}). The source table contains 286 usable observations; two cells are blank and are excluded rather than imputed.`, '',
 'The image shows a 3×3 drop site surrounded by eight 3×3 farms. The calculation uses the author’s stated 175 food gathered per farm, without instant collection. This tests ordinary farmer movement in that geometry; it does not validate the Poles bonus.','',
 '| Farm group | Published mean seconds | Simulated mean seconds | Published food/min | Simulated food/min | Difference |','|---|---:|---:|---:|---:|---:|',
 ...groups.map(g=>`| ${g.label} | ${g.reference_seconds.mean.toFixed(3)} | ${g.model_seconds.mean.toFixed(3)} | ${g.reference_rate.toFixed(3)} | ${g.model_rate.toFixed(3)} | ${g.difference_percent.toFixed(3)}% |`),'',
 'Each model group includes 144 depletion times across the first 36 seeds. The rate estimator matches the source: food divided by mean lifetime. Reference observations from one setup may be correlated; treating all farms as independent would understate uncertainty.','',
 '## Previous benchmark retained','',
 '| Upgrades | Farm | Difference |','|---|---|---:|',
 ...result.previous_reference.map(r=>`| ${r.profile} | ${r.position} | ${r.difference_percent.toFixed(3)}% |`),'',
 'These are the existing 32-seed results, with their original mean-of-individual-rates estimator. No seed selection, changed parameters, or reference replacement was used.','',
 '## Limits','',...input.limitations.map(s=>'- '+s),'',
 'Passing a group mean is narrower than validating every position, upgrade level, or civilization. Current-DE recordings with known starts and drop-off events are still needed for a universal sub-1% claim.',''];
fs.writeFileSync(path.join(out,'README.md'),lines.join('\n'));
fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify({code:{'tools/farm-gathering-sim.mjs':engineHash,'tools/gold-mining-sim.mjs':sha(path.join(root,'tools/gold-mining-sim.mjs')),'tools/audit_farm_repeated_reference.mjs':sha(fileURLToPath(import.meta.url))},artifacts:Object.fromEntries(['published-observations.json','comparison.json','fixture.json','README.md'].map(n=>[n,sha(path.join(out,n))]))},null,2)+'\n');
console.log(JSON.stringify({groups,positions},null,2));
