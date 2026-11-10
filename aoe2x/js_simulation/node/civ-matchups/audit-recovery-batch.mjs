// Read-only evidence audit plus a new immutable summary. No battle execution.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, existsSync, readdirSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { hashCanonicalJson as digest } from '../../src/canonical-json.js';
import { screeningDecision, screeningOutcome } from './forecast-screening-policy.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const dir = resolve(process.argv[2]), output = resolve(process.argv[3]);
assert(!existsSync(output), 'Never overwrite an audit');
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const fileSha = path => sha(readFileSync(path));
const cache = new Map();
function records(path) {
  if (!cache.has(path)) cache.set(path, readFileSync(path, 'utf8').trim().split('\n').filter(Boolean).map((line, i) =>
    ({record: JSON.parse(line), path, line: i + 1, sha256IncludingNewline: sha(line + '\n')})));
  return cache.get(path);
}
const manifests = new Map();
function manifestAt(path) {
  const full = read(path), {manifestHash, ...body} = full;
  assert.equal(digest(body), manifestHash);
  assert.equal(fileSha(resolve(dirname(path), 'input.json')), body.inputSha256);
  manifests.set(manifestHash, {...full, path});
  if (body.parentManifestPath) manifestAt(body.parentManifestPath);
  return full;
}
const m = manifestAt(resolve(dir, 'manifest.json'));
for (const source of m.frozenSources) assert.equal(fileSha(source.path), source.sha256, source.path);
const {cases, policy} = read(resolve(dir, 'input.json'));
const fresh = existsSync(resolve(dir, 'runs.jsonl')) ? records(resolve(dir, 'runs.jsonl')) : [];
const attempts = existsSync(resolve(dir, 'attempts.jsonl')) ? records(resolve(dir, 'attempts.jsonl')).map(r => r.record) : [];
const verifiedCommits = new Set(), checkedReferences = new Set();
function verifyReference(ref) {
  const actual = records(ref.path)[ref.line - 1];
  assert(actual);
  assert.equal(actual.sha256IncludingNewline, ref.sha256IncludingNewline);
  assert.deepEqual(actual.record, ref.record);
  checkedReferences.add(`${ref.path}:${ref.line}`);
  return actual.record;
}
function verifyRun(row) {
  assert(['win', 'loss', 'draw'].includes(row.outcome));
  assert(Number.isSafeInteger(row.seed) && row.seed >= 0 && row.seed <= 9);
  assert(Number.isSafeInteger(row.ticks) && row.ticks > 0);
  assert.equal(row.simulationSeconds, row.ticks / 60);
  for (const side of ['unit', 'opponent']) {
    assert(Number.isFinite(row[side + 'StartingHp']) && row[side + 'StartingHp'] > 0);
    assert(Number.isFinite(row[side + 'RemainingHp']) && row[side + 'RemainingHp'] >= 0);
    assert(Number.isInteger(row[side + 'Survivors']) && row[side + 'Survivors'] >= 0);
  }
  if (row.winnerOwner === 2) { assert.equal(row.opponentSurvivors, 0); assert.equal(row.opponentRemainingHp, 0); }
  else if (row.winnerOwner === 3) { assert.equal(row.unitSurvivors, 0); assert.equal(row.unitRemainingHp, 0); }
  else { assert.equal(row.unitSurvivors + row.opponentSurvivors, 0); }
  assert.match(row.finalStateHash, /^[0-9a-f]{64}$/); assert.match(row.eventLogHash, /^[0-9a-f]{64}$/);
  if (!row.manifestHash) return; // Original frozen records keep their own provenance.
  const manifest = manifests.get(row.manifestHash); assert(manifest, 'unknown recovery manifest');
  assert.equal(row.physicsVersion, manifest.physicsVersion);
  assert.deepEqual(row.rawResult.remainingByOwner[2]?.hp ?? 0, row.unitRemainingHp);
  assert.deepEqual(row.rawResult.remainingByOwner[3]?.hp ?? 0, row.opponentRemainingHp);
  assert.equal(row.rawResult.winnerOwner, row.winnerOwner);
  const commitKey = `${row.sourceCommit}:${row.manifestHash}`;
  if (!verifiedCommits.has(commitKey)) {
    for (const source of manifest.runtimeFiles) assert.equal(sha(execFileSync('git', ['show', `${row.sourceCommit}:${source.path}`],
      {cwd: root, maxBuffer: 16 * 1024 * 1024})), source.sha256, source.path);
    verifiedCommits.add(commitKey);
  }
}
const results = [];
for (const c of cases) {
  const refs = [...c.preservedNativeReferences, ...fresh.filter(ref => ref.record.matchupId === c.job.id)];
  const rows = refs.map(verifyReference);
  assert.equal(new Set(rows.map(r => r.seed)).size, rows.length, 'repeated completed seed');
  for (const row of rows) {
    verifyRun(row);
    assert.equal(row.contextHash, c.job.contextHash);
    assert.deepEqual(row.counts, c.job.counts);
    assert.deepEqual(row.profileHashes, c.job.profileHashes);
    assert.equal(row.scenarioHash, c.job.scenarioHash);
  }
  const decision = screeningDecision(c.job, rows, c.originalOutcomes, policy);
  const reviewPath = resolve(dir, 'reviews', c.job.id + '.json');
  const complete = decision.requiredSeeds.length === 0;
  const outcome = complete ? screeningOutcome(c.job, rows, c.originalOutcomes, policy) : null;
  const earlierEngineComparison = (c.historicalProjectionReferences ?? []).map(ref => {
    const prior = ref.record;
    assert.deepEqual(prior.profileHashes, c.job.profileHashes);
    assert.deepEqual(prior.counts, c.job.counts);
    assert.equal(prior.scenarioHash, c.job.scenarioHash);
    const current = rows.find(row => row.seed === prior.seed);
    return {seed: prior.seed, source: {path: ref.path, line: ref.line, recordSha256: ref.recordSha256},
      earlierPhysicsVersion: prior.physicsVersion, earlierWinnerOwner: prior.winnerOwner,
      newWinnerOwner: current?.winnerOwner ?? null,
      sameWinner: current ? current.winnerOwner === prior.winnerOwner : null,
      earlierHp: [prior.unitRemainingHp, prior.opponentRemainingHp],
      newHp: current ? [current.unitRemainingHp, current.opponentRemainingHp] : null};
  });
  if (complete) {
    assert(existsSync(reviewPath), 'complete seed set must have a saved review');
    const {reviewHash, ...review} = read(reviewPath);
    assert.equal(digest(review), reviewHash);
    assert.deepEqual(review.samplingDecision, decision);
    assert.equal(review.outcome, outcome);
    assert.deepEqual(review.exactReplay, {required: false, performed: false, exact: null});
    assert.equal(review.productionEligible, false);
  }
  results.push({jobId: c.job.id, label: c.label, category: c.category, displayedCells: c.job.displayedCells,
    complete, evidenceLevel: complete ? decision.evidenceLevel : null, requiredSeeds: decision.requiredSeeds,
    outcome, originalOutcomes: c.originalOutcomes, changed: complete ? c.originalOutcomes.some(o => o !== outcome) : null,
    mixedWinners: new Set(rows.map(r => r.winnerOwner)).size > 1,
    physicsVersions: [...new Set(rows.map(r => r.physicsVersion))],
    review: complete ? reviewPath : null, earlierEngineComparison,
    seeds: refs.map(({record, ...ref}) => ({...ref, seed: record.seed, winnerOwner: record.winnerOwner,
      hp: [record.unitRemainingHp, record.opponentRemainingHp], survivors: [record.unitSurvivors, record.opponentSurvivors],
      physicsVersion: record.physicsVersion, finalStateHash: record.finalStateHash, eventLogHash: record.eventLogHash}))});
}
const complete = results.filter(r => r.complete);
const closed = new Set(attempts.filter(a => a.status === 'finished').map(a => a.attemptId));
const summary = {createdAt: new Date().toISOString(), simulationExecutionsForAudit: 0, manifestHash: m.manifestHash,
  sourceCommit: execFileSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'}).trim(),
  cases: results.length, complete: complete.length, remaining: results.filter(r => !r.complete).length,
  singleSeedConfirmations: complete.filter(r => r.evidenceLevel === 'single_seed_confirmation').length,
  multiSeedValidations: complete.filter(r => r.evidenceLevel === 'multi_seed_validation').length,
  changed: complete.filter(r => r.changed).length, retained: complete.filter(r => !r.changed).length,
  mixedWinners: complete.filter(r => r.mixedWinners).length,
  completeWithMixedEngineVersions: complete.filter(r => r.physicsVersions.length > 1).length,
  checkedRunReferences: checkedReferences.size, checkedRuntimeCommitManifests: verifiedCommits.size,
  unclosedAttempts: attempts.filter(a => a.status === 'started' && !closed.has(a.attemptId)),
  exhaustedContexts: [...new Set(attempts.filter(a => a.exhausted).map(a => a.jobId))],
  frozenSourcesVerified: m.frozenSources.length, productionEligible: false, publication: 'local only',
  limitation: 'Agreement-dependent stopping is not an unbiased accuracy estimate. Recovery engine behavior has synthetic regression coverage, not a new complete live-game fidelity validation. Mixed-version seed sets are explicitly marked.', results};
mkdirSync(dirname(output), {recursive: true});
writeFileSync(output, JSON.stringify(summary, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify({...summary, results: undefined, unclosedAttempts: summary.unclosedAttempts.length}));
