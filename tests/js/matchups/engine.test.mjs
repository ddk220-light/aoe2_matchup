// Pinned matchup engine: file verification, Node-version policy, hash parity
// with the committed mechanics bundle, and an exact replay of two archived
// 2026 seeds (tests/fixtures/matchups/replay-smoke.json). Runs without RB.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, cpSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { gunzipSync } from 'node:zlib';
import { loadEngine, checkNodeVersion, checkEnvironment, engineDirectory } from '../../../aoe2x/matchups/node/engine.mjs';
import { runBattles } from '../../../aoe2x/matchups/node/run-battles.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const ENGINE = engineDirectory('frozen-civ-matchups-v3');
const SIM = pathToFileURL(join(ENGINE, 'aoe2x/js_simulation/')).href;
const gz = path => JSON.parse(gunzipSync(readFileSync(path)).toString('utf8'));
const bundle = gz(join(ROOT, 'aoe2x/matchups/bundles/campaign-2026-185872-188329.json.gz'));
const scenarioSet = gz(join(ROOT, 'aoe2x/matchups/scenarios/frozen-ranking-scenarios-v1.json.gz'));

test('every pinned file matches ENGINE.json', () => {
  const loaded = loadEngine(ENGINE, { nodePolicy: 'warn' });
  assert.equal(loaded.engine.files.length, 62);
  assert.equal(loaded.engine.physicsVersion, 'frozen-civ-matchups-v3');
  assert.equal(loaded.engine.executionVersion, 'lossless-event-stream-v1');
  assert.equal(loaded.engine.node.pinned, 'v24.19.0');
});

test('a changed engine file is refused', () => {
  const copy = mkdtempSync(join(tmpdir(), 'engine-'));
  try {
    cpSync(ENGINE, copy, { recursive: true });
    const target = join(copy, 'aoe2x/js_simulation/src/fight.js');
    writeFileSync(target, readFileSync(target, 'utf8') + '\n// changed\n');
    assert.throws(() => loadEngine(copy, { nodePolicy: 'warn' }), /changed aoe2x\/js_simulation\/src\/fight\.js/);
  } finally { rmSync(copy, { recursive: true, force: true }); }
});

test('node version policy: exact, verified, warn', () => {
  const engine = { node: { pinned: 'v24.19.0', verified: [{ version: 'v24.22.1' }] } };
  assert.equal(checkNodeVersion(engine, 'exact', 'v24.19.0').status, 'pinned');
  assert.throws(() => checkNodeVersion(engine, 'exact', 'v24.22.1'), /policy exact/);
  assert.equal(checkNodeVersion(engine, 'verified', 'v24.22.1').status, 'verified');
  assert.throws(() => checkNodeVersion(engine, 'verified', 'v20.0.0'), /no recorded replay evidence/);
  const warned = checkNodeVersion(engine, 'warn', 'v20.0.0');
  assert.equal(warned.status, 'unverified');
  assert.match(warned.warning, /no recorded replay evidence/);
  assert.throws(() => checkNodeVersion(engine, 'loose', 'v24.19.0'), /unknown node version policy/);
});

test('experiment environment must equal the allowed set', () => {
  assert.deepEqual(checkEnvironment({}, { PATH: '/bin' }), {});
  assert.throws(() => checkEnvironment({}, { AOE2X_EXP_FOO: '1' }), /differs from allowed/);
  assert.deepEqual(checkEnvironment({ AOE2X_EXP_FOO: '1' }, { AOE2X_EXP_FOO: '1' }), { AOE2X_EXP_FOO: '1' });
});

test('bundle hashes equal the pinned engine hashCanonicalJson / combatProfileHash', async () => {
  const { hashCanonicalJson } = await import(new URL('src/canonical-json.js', SIM).href);
  const { combatProfileHash } = await import(new URL('node/ranking-equivalence.mjs', SIM).href);
  assert.equal(bundle.variants.length, 555);
  for (const v of bundle.variants) {
    assert.equal(hashCanonicalJson(v.mechanics), v.mechanicsHash, v.key);
    assert.equal(combatProfileHash(v.mechanics), v.profileHash, v.key);
  }
  const { bundleHash, ...body } = bundle;
  assert.equal(hashCanonicalJson(body), bundleHash);
  for (const { hash, scenario } of scenarioSet.scenarios) assert.equal(hashCanonicalJson(scenario), hash);
  assert.equal(new Set(bundle.variants.map(v => v.profileHash)).size, 374);
});

test('archived 2026 seeds replay exactly', async () => {
  const fixture = JSON.parse(readFileSync(join(ROOT, 'tests/fixtures/matchups/replay-smoke.json'), 'utf8'));
  const variants = new Map(bundle.variants.map(v => [v.key, v]));
  const jobs = fixture.seeds.map((s, i) => {
    let scenario = scenarioSet.scenarios.find(e => e.hash === s.job.scenarioHash)?.scenario;
    scenario ??= { ...scenarioSet.scenarios.find(e => e.scenario.family === s.job.family).scenario, engineFamily: s.job.engineFamily };
    return { key: String(i), payload: { jobId: s.job.id, seed: s.seed,
      teams: s.job.teamKeys.map((k, n) => ({ mechanics: variants.get(k).mechanics, count: s.job.counts[n] })),
      scenario, disableAiOrders: true, disableKiting: true, preserveOwnerOrientation: true, retainSnapshots: false } };
  });
  const results = new Map();
  await runBattles({ engineDir: ENGINE, jobs, workers: 2, timeoutSteps: [120], nodePolicy: 'warn',
    onResult: row => results.set(row.key, row) });
  fixture.seeds.forEach((s, i) => {
    const row = results.get(String(i));
    assert.ok(row?.ok, JSON.stringify(row));
    const r = row.result;
    const actual = {
      outcome: r.outcome === 'draw' ? 'draw' : r.winnerOwner === 2 ? 'win' : 'loss',
      winnerOwner: r.winnerOwner, ticks: r.ticks,
      unitStartingHp: r.startingHpByOwner[2], opponentStartingHp: r.startingHpByOwner[3],
      unitRemainingHp: r.remainingByOwner[2]?.hp ?? 0, opponentRemainingHp: r.remainingByOwner[3]?.hp ?? 0,
      unitSurvivors: r.remainingByOwner[2]?.units ?? 0, opponentSurvivors: r.remainingByOwner[3]?.units ?? 0,
      finalStateHash: r.finalStateHash, eventLogHash: r.eventLogHash,
    };
    assert.deepEqual(actual, s.expected, s.source);
  });
});
