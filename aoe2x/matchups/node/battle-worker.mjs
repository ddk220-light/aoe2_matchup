// One seeded battle per message, run against a pinned engine copy.
//
// Ported from RB:aoe2x/js_simulation/node/mismatch-validation-worker.mjs
// (the worker every mismatch/forecast campaign seed ran in; RB =
// origin/simulations/civ-forecast-recovery-2026-11-10). Behaviour kept:
//   * a module-load hook lifts the 9,000-tick game-time cap (fight.js
//     `maxTicks: MAX_TICKS,` and world.js `const MAX_WORLD_TICKS = 9000;`)
//     without editing the engine files, and adds a progress callback;
//   * progress is posted to the pool at most once per second (the pool keeps
//     the last one for watchdog reports);
//   * optional fsynced diagnostic snapshots every 30 s (never results).
// Changes: the hook only touches modules inside `workerData.runtimeRoot`
// (so a second engine version can sit beside this one), the hook targets are
// taken from the engine's ENGINE.json, and the runtime root is mandatory.
// Physics stays untouched.
import { parentPort, workerData } from 'node:worker_threads';
import { openSync, appendFileSync, fsyncSync, closeSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

if (!workerData?.runtimeRoot) throw new Error('battle-worker needs workerData.runtimeRoot');
const runtimeUrl = pathToFileURL(resolve(workerData.runtimeRoot) + '/').href;
const hooks = workerData.hooks;
if (!hooks?.fight || !hooks?.world) throw new Error('battle-worker needs the engine hook targets');

registerHooks({
  load(url, context, nextLoad) {
    const result = nextLoad(url, context);
    if (!url.startsWith(runtimeUrl)) return result;
    if (url.endsWith(hooks.fight.module)) {
      const source = String(result.source);
      if (source.split(hooks.fight.target).length !== 2) throw new Error('fight stop hook changed');
      return { ...result, source: source.replace(hooks.fight.target, hooks.fight.replacement) };
    }
    if (url.endsWith(hooks.world.module)) {
      let source = String(result.source);
      if (source.split(hooks.world.progressTarget).length !== 2) throw new Error('world progress hook changed');
      if (source.split(hooks.world.capTarget).length !== 2) throw new Error('world tick-cap hook changed');
      source = source.replace(hooks.world.capTarget, hooks.world.capReplacement)
        .replace(hooks.world.progressTarget,
          hooks.world.progressTarget + '\n    globalThis.__collisionValidationProgress?.(current);');
      return { ...result, source };
    }
    return result;
  },
});

const { runHeadlessJob } = await import(new URL(workerData.entry, runtimeUrl).href);

parentPort.on('message', async ({ id, job, maxTicks }) => {
  let last = -Infinity, lastWritten = -Infinity;
  const fd = job.diagnosticProgressPath ? openSync(job.diagnosticProgressPath, 'wx') : null;
  const eventCounts = {};
  globalThis.__collisionValidationMaxTicks = maxTicks ?? 9000;
  globalThis.__collisionValidationProgress = current => {
    const tick = current.tick;
    if (fd !== null) {
      for (const e of current.events) eventCounts[e.type] = (eventCounts[e.type] ?? 0) + 1;
      if (performance.now() - lastWritten >= 30000) {
        lastWritten = performance.now();
        const alive = current.units.filter(u => u.alive), byOwner = {};
        for (const u of alive) { byOwner[u.owner] ??= { units: 0, hp: 0 }; byOwner[u.owner].units++; byOwner[u.owner].hp += u.hp; }
        appendFileSync(fd, JSON.stringify({
          at: new Date().toISOString(), diagnosticOnly: true, tick, simulationSeconds: tick / 60,
          memoryUsage: process.memoryUsage(), byOwner, eventCounts,
          positions: alive.map(u => ({
            id: u.referenceId, owner: u.owner, hp: u.hp, x: u.x, y: u.y, action: u.action,
            pursuitTargetId: u.pursuitTargetId, engagedTargetId: u.engagedTargetId, attackTargetId: u.attackTargetId,
          })),
        }) + '\n');
        fsyncSync(fd);
      }
    }
    if (performance.now() - last >= 1000) {
      last = performance.now(); parentPort.postMessage({ id, progress: { tick, simulationSeconds: tick / 60 } });
    }
  };
  // The diagnostic path is a worker option, not a physics input.
  const { diagnosticProgressPath, ...physicsJob } = job;
  try { parentPort.postMessage({ id, result: await runHeadlessJob(physicsJob) }); }
  catch (error) { parentPort.postMessage({ id, error: { name: error.name, message: error.message, stack: error.stack } }); }
  finally { if (fd !== null) closeSync(fd); }
});
