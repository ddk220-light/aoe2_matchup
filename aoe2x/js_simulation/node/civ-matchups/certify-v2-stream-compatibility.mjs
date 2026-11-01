#!/usr/bin/env node
// Certify the output-only source delta between collision-repaired V2 and the
// streaming-hash runtime. This checks source identity; it never runs a fight.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { hashCanonicalJson } from '../../src/canonical-json.js';

const sim = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const root = resolve(sim, '../..');
const v2Root = resolve(process.env.CIV_V2_WORKTREE ?? '/workspace/aoe2_civ_collision_repair');
const v2ManifestPath = resolve(v2Root,
  'aoe2x/js_simulation/calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31/manifest.json');
const out = resolve(sim,
  'calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json');
const outputPaths = new Set([
  'aoe2x/js_simulation/src/canonical-json.js',
  'aoe2x/js_simulation/src/fight.js',
]);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const readJson = path => JSON.parse(readFileSync(path, 'utf8'));
const git = (...args) => execFileSync('git', args, {cwd: root, encoding: 'utf8'}).trim();

assert.equal(git('branch', '--show-current'),
  'simulations/civ-matchups-stream-hash-2026-10-31');
const v2 = readJson(v2ManifestPath);
const {campaignHash: v2Hash, ...v2Body} = v2;
assert.equal(hashCanonicalJson(v2Body), v2Hash, 'V2 manifest hash mismatch');
const shared = [], changed = [];
for (const entry of v2.runtimeFiles) {
  const oldHash = sha(readFileSync(resolve(v2Root, entry.path)));
  const newHash = sha(readFileSync(resolve(root, entry.path)));
  assert.equal(oldHash, entry.sha256, `V2 runtime changed: ${entry.path}`);
  (oldHash === newHash ? shared : changed).push({
    path: entry.path, v2Sha256: oldHash, streamSha256: newHash,
  });
}
assert.deepEqual(new Set(changed.map(x => x.path)), outputPaths,
  'unexpected runtime change beyond canonical JSON and fight output hashing');
const sharedRuntimeSha256 = hashCanonicalJson(shared);
const saved = process.argv.includes('--verify') ? readJson(out) : null;
if (saved) {
  assert.equal(execFileSync('git', ['merge-base', '--is-ancestor',
    saved.streamSourceCommit, 'HEAD'], {cwd: root}).length, 0);
}
const body = {
  schemaVersion: 1,
  name: 'civ-matchups-v2-stream-compatibility-2026-11-01',
  v2ManifestPath: relative(v2Root, v2ManifestPath),
  v2CampaignHash: v2Hash,
  v2SourceCommit: v2.sourceCommit,
  streamSourceCommit: saved?.streamSourceCommit ?? git('rev-parse', 'HEAD'),
  referenceDbSha256: v2.referenceDbSha256,
  engineConfig: v2.engineConfig,
  simulationEnvironment: v2.simulationEnvironment,
  sharedRuntimeSha256,
  sharedRuntimeFiles: shared,
  changedOutputFiles: changed,
  compatibilityScope: 'same frozen inputs and combat physics; event-log SHA-256 is streamed in Node',
  evidencePolicy: {
    existingV2Replays: 'retain original records and runtime source hashes',
    futureStreamRuns: 'store in a separate campaign and journal with own source hashes',
    completePair: 'seeds 0..2; if outcomes differ, seeds 3..9 also required',
    comparison: 'winner, final-state hash, and event-log hash must match on exact parity replays',
    prohibited: 'V3 outcomes as V2 evidence; diagnostic runs as campaign records',
  },
};
const manifest = {...body, campaignHash: hashCanonicalJson(body)};
if (process.argv.includes('--verify')) {
  assert(existsSync(out), 'compatibility manifest missing');
  assert.deepEqual(saved, manifest, 'compatibility manifest drift');
  console.log(JSON.stringify({verified: true, campaignHash: manifest.campaignHash,
    sharedRuntimeFiles: shared.length, changedOutputFiles: changed.length}));
} else {
  assert(!existsSync(out), 'compatibility manifest already exists; use --verify');
  mkdirSync(dirname(out), {recursive: true});
  writeFileSync(out, `${JSON.stringify(manifest, null, 2)}\n`, {flag: 'wx'});
  console.log(JSON.stringify({created: out, campaignHash: manifest.campaignHash,
    sharedRuntimeFiles: shared.length, changedOutputFiles: changed.length}));
}
