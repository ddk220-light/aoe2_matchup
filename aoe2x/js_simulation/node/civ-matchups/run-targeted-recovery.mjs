// One explicit recovery manifest; never starts or modifies a frozen campaign.
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
const manifestPath = resolve(process.argv[2]);
const dir = dirname(manifestPath);
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const lines = path => existsSync(path) ? readFileSync(path, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
const append = (path, value) => {
  const fd = openSync(path, 'a');
  try { appendFileSync(fd, JSON.stringify(value) + '\n'); fsyncSync(fd); } finally { closeSync(fd); }
};
const { manifestHash, ...manifest } = read(manifestPath);
assert.equal(digest(manifest), manifestHash);
assert.equal(manifest.physicsVersion, 'forecast-recovery-inherited-ranged-core-v1');
assert.equal(process.version, manifest.nodeVersion);
assert.deepEqual(Object.fromEntries(Object.entries(process.env).filter(([key]) => key.startsWith('AOE2X_EXP_'))), {});
for (const source of manifest.runtimeFiles) assert.equal(sha(resolve(root, source.path)), source.sha256, source.path);
for (const source of manifest.frozenSources) assert.equal(sha(source.path), source.sha256, source.path);
const { job, payload, originalOutcomes, policy } = read(resolve(dir, 'input.json'));
assert.deepEqual(manifest.allowedJobs, [job.id]);
assert.equal(sha(resolve(dir, 'input.json')), manifest.inputSha256);
assert.equal(digest(job.context), job.contextHash);
assert.equal(digest(payload.scenario), job.scenarioHash);
assert.deepEqual(payload.teams.map(team => team.count), job.counts);
assert.equal(policy.independentExactReplayRequired, false);
for (const path of manifest.nativeLedgers) assert(existsSync(path), 'original ledger missing: ' + path);
const originalRecords = manifest.nativeLedgers.flatMap(lines);
const rowsPath = resolve(dir, 'runs.jsonl'), attemptsPath = resolve(dir, 'attempts.jsonl');
const rows = lines(rowsPath);
assert.equal(new Set(rows.map(row => row.seed)).size, rows.length, 'duplicate recovery seed');
for (const row of rows) {
  assert.equal(row.manifestHash, manifestHash); assert.equal(row.contextHash, job.contextHash);
  assert.equal(row.physicsVersion, manifest.physicsVersion);
}
const attempts = lines(attemptsPath);
assert(!attempts.some(attempt => attempt.exhausted), 'Diagnose exhausted attempts before further recovery');
assert(attempts.filter(attempt => attempt.status === 'started').every(start =>
  attempts.some(end => end.attemptId === start.attemptId && end.status === 'finished')),
'Unclosed attempt requires saved-evidence diagnosis; never blindly relaunch');
const decision = () => screeningDecision(job, rows, originalOutcomes, policy);
const forbidden = seed => originalRecords.some(row => row.seed === seed && (
  row.matchupId === job.id || row.matchupId === job.nativeMatchupId || row.contextHash === job.contextHash));
assert(decision().requiredSeeds.every(seed => !forbidden(seed)), 'completed original seed must never rerun');
const sourceCommit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
for (const source of manifest.runtimeFiles) {
  const committed = execFileSync('git', ['show', `${sourceCommit}:${source.path}`], { cwd: root, maxBuffer: 16 * 1024 * 1024 });
  assert.equal(createHash('sha256').update(committed).digest('hex'), source.sha256, 'runtime must be locally committed');
}
if (process.argv.includes('--verify-only')) {
  console.log(JSON.stringify({ preflight: 'passed', manifestHash, completedSeeds: rows.map(row => row.seed), requiredSeeds: decision().requiredSeeds }));
  process.exit(0);
}
const lock = resolve(dir, '.runner.lock');
const fd = openSync(lock, 'wx');
writeFileSync(fd, JSON.stringify({ pid: process.pid, manifestHash, startedAt: new Date().toISOString() })); fsyncSync(fd); closeSync(fd);
mkdirSync(resolve(dir, 'progress'), { recursive: true });
const pool = new RankingWorkerPool(4, { workerUrl: new URL('../mismatch-validation-worker.mjs', import.meta.url), maxTicks: Number.MAX_SAFE_INTEGER });
try {
  while (decision().requiredSeeds.length) {
    const seed = decision().requiredSeeds[0];
    assert(!forbidden(seed) && !rows.some(row => row.seed === seed), 'Never rerun a completed seed');
    let saved = false;
    for (let attempt = 0; attempt < manifest.wallTimeoutSteps.length; attempt++) {
      const startedAt = new Date().toISOString(), start = performance.now();
      const attemptId = `${job.id}-${seed}-${Date.now()}`;
      const diagnosticProgressPath = resolve(dir, 'progress', attemptId + '.jsonl');
      append(attemptsPath, { status: 'started', attemptId, jobId: job.id, seed, attempt: attempt + 1, startedAt, diagnosticProgressPath, manifestHash });
      const outcome = await pool.run({ ...payload, seed, diagnosticProgressPath }, manifest.wallTimeoutSteps[attempt]);
      const finishedAt = new Date().toISOString(), wallSeconds = (performance.now() - start) / 1000;
      const result = outcome.result;
      if (result && ['win', 'loss', 'draw'].includes(result.outcome)) {
        const record = {
          manifestHash, sourceCommit, matchupId: job.id, contextHash: job.contextHash, pairKey: job.pairKey,
          physicsVersion: manifest.physicsVersion, executionVersion: 'lossless-event-stream-v1',
          seed, purpose: 'fresh_recovery_measurement', startedAt, finishedAt, wallSeconds,
          counts: job.counts, profileHashes: job.profileHashes, scenarioHash: job.scenarioHash,
          outcome: result.outcome, winnerOwner: result.winnerOwner, unitStartingHp: result.startingHpByOwner[2], opponentStartingHp: result.startingHpByOwner[3],
          unitRemainingHp: result.remainingByOwner[2]?.hp ?? 0, opponentRemainingHp: result.remainingByOwner[3]?.hp ?? 0,
          unitSurvivors: result.remainingByOwner[2]?.units ?? 0, opponentSurvivors: result.remainingByOwner[3]?.units ?? 0,
          ticks: result.ticks, simulationSeconds: result.ticks / 60, finalStateHash: result.finalStateHash, eventLogHash: result.eventLogHash,
          rawResult: result, frozenCampaignResult: false,
        };
        append(rowsPath, record); rows.push(record); saved = true;
        append(attemptsPath, { status: 'finished', attemptId, finishedAt, wallSeconds, completed: true, recordHash: digest(record) });
        console.log(JSON.stringify({ savedSeed: seed, winnerOwner: record.winnerOwner, unitRemainingHp: record.unitRemainingHp, opponentRemainingHp: record.opponentRemainingHp, wallSeconds }));
        break;
      }
      const exhausted = attempt === manifest.wallTimeoutSteps.length - 1;
      append(attemptsPath, { status: 'finished', attemptId, finishedAt, wallSeconds, completed: false, exhausted, ...outcome });
      console.log(JSON.stringify({ failedSeed: seed, attempt: attempt + 1, exhausted, error: outcome.error, watchdog: outcome.watchdog }));
    }
    if (!saved) throw new Error('Recovery exhausted; inspect fsynced snapshots before further work');
  }
  const review = { manifestHash, sourceCommit, jobId: job.id, contextHash: job.contextHash, physicsVersion: manifest.physicsVersion,
    reviewedAt: new Date().toISOString(), status: 'candidate_protocol_complete', frozenCampaignResult: false, productionEligible: false,
    samplingDecision: decision(), outcome: screeningOutcome(job, rows, originalOutcomes, policy),
    recordHashes: rows.map(row => ({ seed: row.seed, hash: digest(row) })), exactReplay: { required: false, performed: false, exact: null },
    limitation: 'Separate recovery-engine evidence. The frozen ledger is unchanged; broader mechanics review remains required before any future production inclusion.' };
  const reviewPath = resolve(dir, 'review.json');
  if (!existsSync(reviewPath)) {
    const reviewFd = openSync(reviewPath, 'wx');
    try { writeFileSync(reviewFd, JSON.stringify({ ...review, reviewHash: digest(review) }, null, 2) + '\n'); fsyncSync(reviewFd); } finally { closeSync(reviewFd); }
  }
  console.log(JSON.stringify({ status: review.status, seeds: rows.length, outcome: review.outcome, frozenCampaignResult: false }));
} finally { await pool.close(); unlinkSync(lock); }
