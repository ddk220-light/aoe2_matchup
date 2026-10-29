import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
import { instrumentSource } from '../node/ranking-diagnostic-hooks.mjs';

test('diagnostic hooks preserve outcomes and can stop with the latest completed tick', () => {
  const original = readFileSync(new URL('../src/combat/world.js', import.meta.url), 'utf8');
  const transformed = instrumentSource('/src/combat/world.js', original);
  // Exercise the actual runWorld function, with small deterministic tick states.
  const functionSource = transformed.slice(transformed.indexOf('export function runWorld(')).replace('export ', '');
  const exercise = (limit, winTick) => {
    const observations = [];
    const sandbox = { DEFAULT_WORLD_TICKS: 9000, MAX_WORLD_TICKS: Number.MAX_SAFE_INTEGER,
      __rankingDiagnostic: { observe(world) { observations.push(world.tick); }, beforeStep() {},
        stopRequested() { return observations.at(-1) >= limit; } },
      stepWorld(world) { return { ...world, tick: world.tick + 1, events: [{ tick: world.tick + 1 }] }; },
      worldResult(world, outcome) { return { world, outcome, ticks: world.tick }; },
      outcome(world) { return world.tick === winTick ? { world, ticks: world.tick, outcome: 'win' } : null; },
    };
    vm.createContext(sandbox);
    vm.runInContext(`${functionSource}\nglobalThis.run = runWorld;`, sandbox);
    const world = { tick: 0, snapshots: [], eventLog: [], events: [] };
    return { result: sandbox.run(world, { maxTicks: 20000, retainSnapshots: false }), observations };
  };
  const win = exercise(50, 4);
  assert.equal(win.result.outcome, 'win'); assert.equal(win.result.ticks, 4);
  assert.deepEqual(win.observations, [0, 1, 2, 3, 4]);
  const stopped = exercise(3, 4);
  assert.equal(stopped.result.outcome, 'timeout'); assert.equal(stopped.result.ticks, 3);
  assert.equal(stopped.result.events.length, 3);
  // A decided fight wins over the wall-budget test at the same tick.
  assert.equal(exercise(4, 4).result.outcome, 'win');
});

test('game-time cap overrides are explicit and mismatched source fails closed', () => {
  const source = readFileSync(new URL('../src/fight.js', import.meta.url), 'utf8');
  assert.ok(instrumentSource('/src/fight.js', source).includes('const MAX_TICKS = globalThis.__rankingDiagnostic.maxTicks;'));
  assert.throws(() => instrumentSource('/src/fight.js', source.replace('const MAX_TICKS = 9000;', 'const MAX_TICKS = 9010;')), /mismatch/);
});

test('diagnostic process saves both clocks and a CPU profile when its processing allowance expires', () => {
  const temporary = mkdtempSync(resolve(tmpdir(), 'ranking-diagnostic-test-'));
  try {
    const runtime = resolve(temporary, 'runtime');
    const modulePath = resolve(runtime, 'aoe2x/js_simulation/node');
    mkdirSync(modulePath, { recursive: true });
    writeFileSync(resolve(modulePath, 'run-job.mjs'), `
      export async function runHeadlessJob() {
        const observer = globalThis.__rankingDiagnostic;
        const world = { tick: 0, units: [], events: [] };
        observer.observe(world);
        do {
          observer.beforeStep(world);
          Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 2);
          world.tick++;
          observer.observe(world);
        } while (!observer.stopRequested());
        return { outcome: 'timeout', ticks: world.tick };
      }
    `);
    const output = resolve(temporary, 'output');
    const specification = resolve(temporary, 'job.json');
    writeFileSync(specification, JSON.stringify({ runtime, output, wallSeconds: .03,
      removeGameCap: true, task: 'test', job: { jobId: 'test', seed: 0, teams: [] } }));
    const process = spawnSync(globalThis.process.execPath, [
      fileURLToPath(new URL('../node/ranking-diagnostic-job.mjs', import.meta.url)), specification,
    ], { encoding: 'utf8', timeout: 5000 });
    assert.equal(process.status, 0, process.stderr);
    const result = JSON.parse(readFileSync(resolve(output, 'result.json')));
    assert.equal(result.stopReason, 'processing_limit');
    assert.ok(result.processingWallSeconds >= .03);
    assert.ok(result.lastProgress.tick > 0);
    assert.equal(result.lastProgress.simulationSeconds, result.result.ticks / 60);
    assert.ok(JSON.parse(readFileSync(resolve(output, 'cpu.cpuprofile'))).nodes.length > 0);
    assert.ok(readFileSync(resolve(output, 'timeline.jsonl'), 'utf8').trim().split('\n').length >= 2);
  } finally { rmSync(temporary, { recursive: true, force: true }); }
});
