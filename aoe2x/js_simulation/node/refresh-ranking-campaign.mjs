#!/usr/bin/env node
// Recompute the existing, approved matrix on a new engine; never import old outcomes.
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { hashCanonicalJson as digest } from '../src/canonical-json.js';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const sim = resolve(root, 'aoe2x/js_simulation');
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const json = path => JSON.parse(readFileSync(path, 'utf8'));

export function prepareRefresh(previousDirectory, directory, validationDirectory) {
  if (existsSync(resolve(directory, 'manifest.json'))) throw new Error('campaign exists; resume it');
  const previous = json(resolve(previousDirectory, 'manifest.json'));
  const { campaignHash: previousHash, ...previousDefinition } = previous;
  if (digest(previousDefinition) !== previousHash) throw new Error('previous manifest hash mismatch');
  const validation = json(resolve(validationDirectory, 'summary.json'));
  const validationManifest = json(resolve(validationDirectory, 'manifest.json'));
  const testStatus = json(resolve(validationDirectory, 'test-status.json'));
  const refreshVerification = json(resolve(validationDirectory, 'refresh-verification.json'));
  if (!refreshVerification.allExact || refreshVerification.parity.length !== 10
      || refreshVerification.equivalence.length !== 5 || !refreshVerification.clock?.exact
      || digest(refreshVerification.sourceHashes) !== digest(validation.sourceHashes)) {
    throw new Error('current-engine worker and equivalence checks must pass');
  }
  if (!validation.complete || validation.controlFailures !== 0 || validation.controls !== 37 || validation.anomalyRetries !== 107
      || validation.anomalyOutcomes.win + (validation.anomalyOutcomes.draw ?? 0) !== 107
      || testStatus.failed !== 0 || testStatus.exitCode !== 0) {
    throw new Error('all flagged cases and regression checks must pass before refresh');
  }
  for (const [name, hash] of Object.entries(validation.sourceHashes)) {
    if (sha(resolve(sim, 'src', name)) !== hash) throw new Error(`validated source changed: ${name}`);
  }
  if (validationManifest.campaignHash !== previousHash) throw new Error('validation used different inputs');
  const runtimePaths = new Set(previous.runtimeFiles.map(entry => entry.path));
  for (const name of readdirSync(resolve(sim, 'src'), { recursive: true }).filter(name => name.endsWith('.js'))) {
    runtimePaths.add(relative(root, resolve(sim, 'src', name)));
  }
  for (const name of ['refresh-ranking-campaign.mjs', 'collision-validation-worker.mjs', 'verify-ranking-refresh.mjs']) {
    runtimePaths.add(relative(root, resolve(sim, 'node', name)));
  }
  const branch = execFileSync('git', ['branch', '--show-current'], { cwd: root, encoding: 'utf8' }).trim();
  if (!branch.startsWith('simulations/')) throw new Error('refresh publication requires a simulations branch');
  const sourceCommit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
  const definition = {
    ...previousDefinition,
    campaignName: 'unit-rankings-path-recovery-2026-10-29', createdAt: new Date().toISOString(),
    sourceCommit, engineBaseCommit: sourceCommit, nodeVersion: process.version,
    runtimeFiles: [...runtimePaths].sort().map(path => ({ path, sha256: sha(resolve(root, path)) })),
    publishBranch: branch,
    refreshedFrom: { campaignHash: previousHash, directory: relative(root, previousDirectory),
      note: 'Matrix, costs, unit profiles, equivalence groups and phases preserved; zero old results imported.' },
    validation: { directory: relative(root, validationDirectory),
      summarySha256: sha(resolve(validationDirectory, 'summary.json')), testStatusSha256: sha(resolve(validationDirectory, 'test-status.json')),
      refreshVerificationSha256: sha(resolve(validationDirectory, 'refresh-verification.json')) },
    policy: { ...previous.policy, reusePilotRuns: false, maxSimulationTicks: Number.MAX_SAFE_INTEGER,
      wallTimeoutSeconds: 120, workers: 4 },
    reuseCampaign: null,
  };
  // These describe the previous orchestration checks, not fresh benchmark measurements.
  definition.historicalBenchmark = definition.benchmark;
  delete definition.benchmark;
  definition.historicalEquivalenceVerification = definition.equivalenceVerification;
  definition.equivalenceVerification = { allExact: true, pairs: 5,
    checks: refreshVerification.equivalence.map(({ results, ...check }) => check) };
  const manifest = { ...definition, campaignHash: digest(definition) };
  mkdirSync(directory, { recursive: true });
  for (const [name, value] of [['manifest.json', manifest], ['equivalence.json', manifest.equivalence]]) {
    writeFileSync(resolve(directory, name), JSON.stringify(value, null, 2) + '\n');
  }
  writeFileSync(resolve(directory, '.gitignore'), '*.sqlite*\n*.tmp\n.runner.lock\n*.log\n*.pid\n');
  writeFileSync(resolve(directory, 'PLAN.md'), `# Consistent engine refresh\n\n`
    + `Recompute all ${manifest.equivalence.distinctMatchups} distinct matchups (${manifest.matchups.length} table rows) on the corrected engine. `
    + `Keep the approved profiles, opponent pools, 27-unit balancing, three-to-ten seed rule and ${manifest.phases.length} review phases. `
    + `No old pilot or campaign outcomes are imported.\n\n`
    + `Use four persistent workers. Save every run to SQLite and fsynced JSONL; record game time and processing time, including the last heartbeat on a processing cutoff. `
    + `There is no practical game-time cutoff. Keep the 120-second processing watchdog and report every unresolved run.\n\n`
    + `Each phase checks source fingerprints, coverage, database integrity and an exact-seed replay. Advance automatically after those checks. `
    + `Publish at each phase boundary, 250 new results, or ten minutes. Resume uses existing journals and records. Scoring and browser integration remain deferred.\n`);
  return manifest;
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const [previous, output, validation] = process.argv.slice(2);
  const manifest = prepareRefresh(resolve(previous), resolve(output), resolve(validation));
  console.log(JSON.stringify({ campaignHash: manifest.campaignHash, phases: manifest.phases.length,
    matchups: manifest.equivalence.distinctMatchups, branch: manifest.publishBranch }));
}
