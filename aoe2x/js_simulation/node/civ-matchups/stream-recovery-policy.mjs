import assert from 'node:assert/strict';

// Old-engine seeds reserve work for the existing replay runner. Their values
// never enter the repaired-engine decision, even while that replay is pending.
export function remainingSeeds(records, reservedSeeds = []) {
  const required = new Set([0, 1, 2, ...reservedSeeds]);
  const first = [0, 1, 2].map(seed => records.get(seed));
  if (first.every(Boolean) && new Set(first.map(r => r.outcome)).size > 1)
    for (let seed = 3; seed < 10; seed++) required.add(seed);
  return [...required].filter(seed => !records.has(seed)).sort((a, b) => a - b);
}

export function validateRecord(row, job, campaignHash) {
  assert.equal(row.campaignHash, campaignHash, 'recovery campaign hash mismatch');
  assert.equal(row.matchupId, job.id);
  assert.equal(row.pairKey, job.pairKey);
  assert.deepEqual(row.counts, job.counts);
  assert.deepEqual(row.profileHashes, job.profileHashes);
  assert.equal(row.scenarioHash, job.scenarioHash);
  assert(Number.isSafeInteger(row.seed) && row.seed >= 0 && row.seed <= 9);
  assert(['win', 'loss', 'draw'].includes(row.outcome));
  assert(Number.isSafeInteger(row.ticks) && row.ticks > 0);
  assert.equal(row.simulationSeconds, row.ticks / 60);
  for (const key of ['finalStateHash', 'eventLogHash']) assert(/^[a-f0-9]{64}$/.test(row[key]));
}

export function decision(records, reservedSeeds = []) {
  assert.equal(remainingSeeds(records, reservedSeeds).length, 0, 'missing required seed');
  const outcomes = new Set([...records.values()].map(r => r.outcome));
  return outcomes.size === 1 && !outcomes.has('draw') ? [...outcomes][0] : 'close_uncertain';
}
