// Verify stored evidence hashes only. This never executes a battle.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {hashCanonicalJson as digest} from '../aoe2x/js_simulation/src/canonical-json.js';

const snapshot=resolve(process.argv[2]);
const rows=gunzipSync(readFileSync(resolve(snapshot,'reviewed-contexts.jsonl.gz')))
  .toString('utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
let records=0;
for(const row of rows){
  const {reviewFile,reviewFileSha256,measuredRecords,freshControlRecord,originalEvidence,reviewHash,...body}=row;
  assert.equal(digest(body),reviewHash,'review hash mismatch');
  assert.equal(digest(row.context),row.contextHash,'context hash mismatch');
  assert.equal(measuredRecords.length,row.seedResults.length);
  for(const result of row.seedResults){
    const measured=measuredRecords.find(r=>r.seed===result.seed);
    assert(measured,'missing measured seed');
    assert.equal(digest(measured),result.recordHash,'native record hash mismatch');
    records++;
  }
}
console.log(JSON.stringify({reviewHashes:rows.length,recordHashes:records,simulationExecutions:0}));
