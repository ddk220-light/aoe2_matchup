// A separate, source-bound recovery ledger. Never mutates a frozen campaign.
import assert from 'node:assert/strict';
import { readFileSync, existsSync, mkdirSync, openSync, writeFileSync, appendFileSync, fsyncSync, closeSync, unlinkSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { RankingWorkerPool } from '../ranking-worker-pool.mjs';
import { hashCanonicalJson as digest } from '../../src/canonical-json.js';
import { screeningDecision, screeningOutcome } from './forecast-screening-policy.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const manifestPath = resolve(process.argv[2]), dir = dirname(manifestPath);
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const lines = path => existsSync(path) ? readFileSync(path, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
const append = (path, value) => {
  const fd = openSync(path, 'a');
  try { appendFileSync(fd, JSON.stringify(value) + '\n'); fsyncSync(fd); } finally { closeSync(fd); }
};
const immutable = (path, value) => {
  const fd = openSync(path, 'wx');
  try { writeFileSync(fd, JSON.stringify(value, null, 2) + '\n'); fsyncSync(fd); } finally { closeSync(fd); }
};
const { manifestHash, ...manifest } = read(manifestPath);
assert.equal(digest(manifest), manifestHash);
assert.equal(manifest.kind, 'explicit-forecast-recovery');
assert.equal(process.version, manifest.nodeVersion);
assert.equal(manifest.workers, 4);
assert.deepEqual(Object.fromEntries(Object.entries(process.env).filter(([key]) => key.startsWith('AOE2X_EXP_'))), {});
for (const source of [...manifest.runtimeFiles, ...manifest.frozenSources]) {
  assert.equal(hash(readFileSync(resolve(root, source.path))), source.sha256, source.path);
}
assert.equal(hash(readFileSync(resolve(dir, 'input.json'))), manifest.inputSha256);
const { cases, policy } = read(resolve(dir, 'input.json'));
assert.deepEqual(cases.map(c => c.job.id), manifest.allowedJobs);
assert.equal(policy.independentExactReplayRequired, false);
const originals = manifest.nativeLedgers.flatMap(lines);
const rowsPath = resolve(dir, 'runs.jsonl'), attemptsPath = resolve(dir, 'attempts.jsonl');
const rows = lines(rowsPath), attempts = lines(attemptsPath);
const sourceCommit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
for (const source of manifest.runtimeFiles) {
  assert.equal(hash(execFileSync('git', ['show', `${sourceCommit}:${source.path}`],
    { cwd: root, maxBuffer: 16 * 1024 * 1024 })), source.sha256, 'runtime must be locally committed');
}
const byId = new Map(cases.map(c => [c.job.id, c]));
const observations = c => [...c.preservedNativeReferences.map(ref => ref.record), ...rows.filter(r => r.matchupId === c.job.id)];
const decision = c => screeningDecision(c.job, observations(c), c.originalOutcomes, policy);
const forbidden = (c, seed) => originals.some(row => row.seed === seed && row.contextHash === c.job.contextHash)
  || rows.some(row => row.matchupId === c.job.id && row.seed === seed);
assert.equal(new Set(rows.map(r => `${r.matchupId}:${r.seed}`)).size, rows.length, 'duplicate recovery seed');
for (const row of rows) {
  assert.equal(row.manifestHash, manifestHash);
  assert.equal(row.physicsVersion, manifest.physicsVersion);
  assert.equal(row.contextHash, byId.get(row.matchupId)?.job.contextHash);
}
for (const c of cases) {
  assert.equal(digest(c.job.context), c.job.contextHash);
  assert.equal(digest(c.payload.scenario), c.job.scenarioHash);
  assert.deepEqual(c.payload.teams.map(t => t.count), c.job.counts);
  const originalSeeds = originals.filter(r => r.contextHash === c.job.contextHash);
  assert.deepEqual(originalSeeds.map(r => digest(r)).sort(), c.preservedNativeReferences.map(ref => digest(ref.record)).sort());
  for (const ref of c.preservedNativeReferences) {
    const line = readFileSync(ref.path, 'utf8').split('\n')[ref.line - 1];
    assert.equal(hash(line + '\n'), ref.sha256IncludingNewline);
    assert.deepEqual(JSON.parse(line), ref.record);
  }
  assert(decision(c).requiredSeeds.every(seed => !forbidden(c, seed)), 'completed native seed must never rerun');
  if (c.category === 'cross_engine_projection') {
    assert(manifest.authorizedCrossEngineReruns.includes(c.job.id));
    assert.equal(c.preservedNativeReferences.length, 0);
    assert(policy.legacyInProgressJobs.includes(c.job.id), 'retain minimum three distinct seeds for authorized reruns');
  }
}
const closed = new Set(attempts.filter(a => a.status === 'finished').map(a => a.attemptId));
assert(attempts.filter(a => a.status === 'started').every(a => closed.has(a.attemptId)), 'unclosed attempt needs diagnosis');
const exhaustedJobs = new Set(attempts.filter(a => a.exhausted).map(a => a.jobId));
if (process.argv.includes('--verify-only')) {
  console.log(JSON.stringify({preflight: 'passed', manifestHash, completedRecords: rows.length,
    completeCases: cases.filter(c => !decision(c).requiredSeeds.length).length,
    exhaustedJobs: [...exhaustedJobs]})); process.exit(0);
}
const lock = resolve(dir, '.runner.lock');
immutable(lock, {pid: process.pid, manifestHash, sourceCommit, startedAt: new Date().toISOString()});
mkdirSync(resolve(dir, 'progress'), {recursive: true});
mkdirSync(resolve(dir, 'reviews'), {recursive: true});
const pool = new RankingWorkerPool(4, {workerUrl: new URL('../recovery-validation-worker.mjs', import.meta.url), maxTicks: Number.MAX_SAFE_INTEGER});
let administrativeError = null;
const stopRequested = () => administrativeError !== null || existsSync(resolve(dir, 'STOP'));
let nextCase = 0;
async function runCase(c) {
  if (exhaustedJobs.has(c.job.id)) return;
  while (decision(c).requiredSeeds.length && !stopRequested()) {
    const seed = decision(c).requiredSeeds[0];
    assert(!forbidden(c, seed), 'Never rerun a completed seed');
    const prior = attempts.filter(a => a.status === 'started' && a.jobId === c.job.id && a.seed === seed).length;
    let saved = false;
    for (let attempt = prior; attempt < manifest.wallTimeoutSteps.length && !stopRequested(); attempt++) {
      const startedAt = new Date().toISOString(), start = performance.now();
      const attemptId = `${c.job.id}-${seed}-${Date.now()}`;
      const diagnosticProgressPath = resolve(dir, 'progress', attemptId + '.jsonl');
      const started = {status: 'started', attemptId, jobId: c.job.id, seed, attempt: attempt + 1, startedAt,
        diagnosticProgressPath, manifestHash, sourceCommit, limitSeconds: manifest.wallTimeoutSteps[attempt]};
      append(attemptsPath, started); attempts.push(started);
      console.log(JSON.stringify(started));
      const outcome = await pool.run({...c.payload, seed, diagnosticProgressPath}, manifest.wallTimeoutSteps[attempt]);
      const finishedAt = new Date().toISOString(), wallSeconds = (performance.now() - start) / 1000;
      const result = outcome.result;
      if (result && ['win', 'loss', 'draw'].includes(result.outcome)) {
        const record = {manifestHash, sourceCommit, matchupId: c.job.id, contextHash: c.job.contextHash, pairKey: c.job.pairKey,
          physicsVersion: manifest.physicsVersion, executionVersion: 'lossless-event-stream-v1', seed,
          purpose: c.category === 'cross_engine_projection' ? 'owner_authorized_cross_engine_rerun' : 'missing_seed_recovery',
          startedAt, finishedAt, wallSeconds, counts: c.job.counts, profileHashes: c.job.profileHashes, scenarioHash: c.job.scenarioHash,
          outcome: result.outcome, winnerOwner: result.winnerOwner, unitStartingHp: result.startingHpByOwner[2], opponentStartingHp: result.startingHpByOwner[3],
          unitRemainingHp: result.remainingByOwner[2]?.hp ?? 0, opponentRemainingHp: result.remainingByOwner[3]?.hp ?? 0,
          unitSurvivors: result.remainingByOwner[2]?.units ?? 0, opponentSurvivors: result.remainingByOwner[3]?.units ?? 0,
          ticks: result.ticks, simulationSeconds: result.ticks / 60, finalStateHash: result.finalStateHash, eventLogHash: result.eventLogHash,
          rawResult: result, frozenCampaignResult: false};
        append(rowsPath, record); rows.push(record); saved = true;
        const finished = {status: 'finished', attemptId, jobId: c.job.id, seed, finishedAt, wallSeconds, completed: true, recordHash: digest(record)};
        append(attemptsPath, finished); attempts.push(finished);
        console.log(JSON.stringify({saved: c.job.id, seed, winner: record.winnerOwner, hp: [record.unitRemainingHp, record.opponentRemainingHp], wallSeconds}));
        break;
      }
      const exhausted = attempt === manifest.wallTimeoutSteps.length - 1;
      const finished = {status: 'finished', attemptId, jobId: c.job.id, seed, finishedAt, wallSeconds, completed: false, exhausted, ...outcome};
      append(attemptsPath, finished); attempts.push(finished); console.log(JSON.stringify(finished));
      if (exhausted) exhaustedJobs.add(c.job.id);
    }
    if (!saved) return;
  }
  if (decision(c).requiredSeeds.length) return;
  const reviewPath = resolve(dir, 'reviews', c.job.id + '.json');
  if (existsSync(reviewPath)) return;
  const all = observations(c);
  const review = {manifestHash, sourceCommit, jobId: c.job.id, contextHash: c.job.contextHash, label: c.label,
    reviewedAt: new Date().toISOString(), status: 'candidate_protocol_complete', frozenCampaignResult: false, productionEligible: false,
    physicsVersions: [...new Set(all.map(r => r.physicsVersion))],
    samplingDecision: decision(c), outcome: screeningOutcome(c.job, all, c.originalOutcomes, policy),
    recordReferences: [...c.preservedNativeReferences.map(({record, ...ref}) => ({...ref, seed: record.seed, physicsVersion: record.physicsVersion})),
      ...rows.filter(r => r.matchupId === c.job.id).map(r => ({path: rowsPath, seed: r.seed, physicsVersion: r.physicsVersion, recordHash: digest(r)}))],
    authorizedCrossEngineRerun: c.category === 'cross_engine_projection',
    exactReplay: {required: false, performed: false, exact: null},
    limitation: 'Recovery results retain their engine version. A combined protocol may include preserved frozen-engine seeds; it is not a homogeneous frozen-engine validation.'};
  immutable(reviewPath, {...review, reviewHash: digest(review)});
  console.log(JSON.stringify({reviewed: c.job.id, records: all.length, outcome: review.outcome}));
}
try {
  await Promise.all(Array.from({length: 4}, async () => {
    try {
      while (nextCase < cases.length && !stopRequested()) await runCase(cases[nextCase++]);
    } catch (error) {
      // Let already dispatched battles finish and save their results before
      // closing the pool. An administrative error is never a battle result.
      administrativeError = error;
      append(resolve(dir, 'administrative-errors.jsonl'), {at: new Date().toISOString(), name: error.name, message: error.message, stack: error.stack});
    }
  }));
  console.log(JSON.stringify({finished: true, stoppedBetweenAttempts: stopRequested(), completedCases: cases.filter(c => !decision(c).requiredSeeds.length).length, exhaustedJobs: [...exhaustedJobs]}));
  if (administrativeError) throw administrativeError;
} finally { await pool.close(); unlinkSync(lock); }
