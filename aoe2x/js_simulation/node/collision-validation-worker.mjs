import { parentPort, workerData } from 'node:worker_threads';
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

// Validation-only stop controls and progress reporting. Physics stays untouched.
registerHooks({
  load(url, context, nextLoad) {
    const result = nextLoad(url, context);
    if (url.endsWith('/src/fight.js')) {
      const source = String(result.source);
      const target = 'maxTicks: MAX_TICKS,';
      if (source.split(target).length !== 2) throw new Error('fight stop hook changed');
      return { ...result, source: source.replace(target,
        'maxTicks: globalThis.__collisionValidationMaxTicks ?? MAX_TICKS,') };
    }
    if (url.endsWith('/src/combat/world.js')) {
      let source = String(result.source);
      const target = '  const publish = (current) => {';
      if (source.split(target).length !== 2) throw new Error('world progress hook changed');
      source = source.replace('const MAX_WORLD_TICKS = 9000;', 'const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;')
        .replace(target, target + '\n    globalThis.__collisionValidationProgress?.(current.tick);');
      return { ...result, source };
    }
    return result;
  },
});
const { runHeadlessJob } = await import(workerData?.runtimeRoot
  ? pathToFileURL(resolve(workerData.runtimeRoot, 'aoe2x/js_simulation/node/run-job.mjs')).href
  : './run-job.mjs');
parentPort.on('message', async ({ id, job, maxTicks }) => {
  let last = -Infinity;
  globalThis.__collisionValidationMaxTicks = maxTicks ?? 9000;
  globalThis.__collisionValidationProgress = tick => {
    if (performance.now() - last >= 1000) {
      last = performance.now(); parentPort.postMessage({ id, progress: { tick, simulationSeconds: tick / 60 } });
    }
  };
  try { parentPort.postMessage({ id, result: await runHeadlessJob(job) }); }
  catch (error) { parentPort.postMessage({ id, error: { name: error.name, message: error.message, stack: error.stack } }); }
});
