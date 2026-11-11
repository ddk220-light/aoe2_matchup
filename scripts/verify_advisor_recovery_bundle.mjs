// Pure saved-evidence hash checks; never import a simulation runner.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {hashCanonicalJson as hash} from '../aoe2x/js_simulation/src/canonical-json.js';

for (const item of JSON.parse(gunzipSync(readFileSync(process.argv[2])))) {
  assert.equal(hash(item.job.context), item.job.contextHash);
  const {reviewHash, ...review} = item.review;
  assert.equal(hash(review), reviewHash);
  for (const wrapped of item.runs) {
    const row = wrapped.record;
    const ref = (review.recordReferences ?? review.recordHashes).find(r => r.seed === row.seed);
    assert(ref);
    if (ref.recordHash || ref.hash) assert.equal(hash(row), ref.recordHash ?? ref.hash);
    if (ref.sha256IncludingNewline) assert.equal(wrapped.sourceReference.sha256IncludingNewline, ref.sha256IncludingNewline);
    assert.equal(row.contextHash, item.job.contextHash);
  }
}
console.log('Recovery context and review hashes verified without simulations.');
