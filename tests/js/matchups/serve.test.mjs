// run-battles.mjs --serve: the one-attempt-per-request protocol the Python runner
// (aoe2x/matchups/runner.py) drives. One archived 2026 seed must replay exactly,
// a tiny wall limit must come back as a watchdog failure (never a result), and
// the process must exit when its stdin closes. Runs without RB.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gunzipSync } from 'node:zlib';
import { engineDirectory } from '../../../aoe2x/matchups/node/engine.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const gz = path => JSON.parse(gunzipSync(readFileSync(path)).toString('utf8'));
const bundle = gz(join(ROOT, 'aoe2x/matchups/bundles/campaign-2026-185872-188329.json.gz'));
const scenarioSet = gz(join(ROOT, 'aoe2x/matchups/scenarios/frozen-ranking-scenarios-v1.json.gz'));
const fixture = JSON.parse(readFileSync(join(ROOT, 'tests/fixtures/matchups/replay-smoke.json'), 'utf8'));
const variants = new Map(bundle.variants.map(v => [v.key, v]));

function payload(s) {
  let scenario = scenarioSet.scenarios.find(e => e.hash === s.job.scenarioHash)?.scenario;
  scenario ??= { ...scenarioSet.scenarios.find(e => e.scenario.family === s.job.family).scenario, engineFamily: s.job.engineFamily };
  return { jobId: s.job.id, seed: s.seed,
    teams: s.job.teamKeys.map((k, n) => ({ mechanics: variants.get(k).mechanics, count: s.job.counts[n] })),
    scenario, disableAiOrders: true, disableKiting: true, preserveOwnerOrientation: true, retainSnapshots: false };
}

test('serve mode answers one attempt per request and exits on stdin EOF', async () => {
  const child = spawn(process.execPath, [join(ROOT, 'aoe2x/matchups/node/run-battles.mjs'), '--serve',
    '--engine', engineDirectory('frozen-civ-matchups-v3'), '--workers', '2', '--node-policy', 'warn'],
  { stdio: ['pipe', 'pipe', 'inherit'] });
  const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
  const next = async () => JSON.parse((await lines.next()).value);
  const hello = (await next()).hello;
  assert.equal(hello.engineId, 'frozen-civ-matchups-v3');
  assert.equal(hello.node.version, process.version);
  assert.equal(hello.workers, 2);
  const s = fixture.seeds[0];
  child.stdin.write(JSON.stringify({ key: 'ok', payload: payload(s), limitSeconds: 120 }) + '\n');
  child.stdin.write(JSON.stringify({ key: 'tiny', payload: payload(s), limitSeconds: 0.001 }) + '\n');
  const replies = new Map();
  for (let i = 0; i < 2; i++) { const r = await next(); replies.set(r.key, r); }
  const tiny = replies.get('tiny');
  assert.equal(tiny.ok, false);
  assert.equal(tiny.watchdog, true);
  assert.equal(tiny.result, undefined);
  const ok = replies.get('ok');
  assert.equal(ok.ok, true, JSON.stringify(ok));
  const r = ok.result;
  assert.deepEqual({ winnerOwner: r.winnerOwner, ticks: r.ticks, finalStateHash: r.finalStateHash, eventLogHash: r.eventLogHash },
    { winnerOwner: s.expected.winnerOwner, ticks: s.expected.ticks, finalStateHash: s.expected.finalStateHash,
      eventLogHash: s.expected.eventLogHash });
  const exited = new Promise(done => child.on('exit', code => done(code)));
  child.stdin.end();
  assert.equal(await exited, 0);
});
