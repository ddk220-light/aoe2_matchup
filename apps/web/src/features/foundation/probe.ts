import release from '../../generated/release.json';
export async function runProbe() {
  const response = await fetch('/api/v3/battle-config', {
    method: 'POST', headers: {'Content-Type': 'application/json',
      'X-AoE2-Simulation-Version': release.components.simulator.version,
      'X-AoE2-Engine-Version':release.components.engine.version},
    body: JSON.stringify({army:{mode:'explicit'}, engagement_mode:'direct', seed:100,
      teams:[{civ:'Spanish',unit_slug:'champion',count:2}, {civ:'Spanish',unit_slug:'paladin',count:2}]}),
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) throw new Error(`Battle configuration returned ${response.status}`);
  const config = await response.json();
  if (response.headers.get('X-AoE2-Simulation-Version') !== release.components.simulator.version
      || response.headers.get('X-AoE2-Engine-Version') !== release.components.engine.version) {
    throw new Error('Simulation data and worker versions do not match. Reload the page.');
  }
  const worker = new Worker(release.engine_worker_url, {type:'module'});
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {worker.terminate(); reject(new Error('Worker timed out'));}, 30_000);
    const finish = (callback: () => void) => {clearTimeout(timer); worker.terminate(); callback();};
    worker.onerror = event => finish(() => reject(new Error(event.message)));
    worker.onmessage = event => {
      if (event.data.type === 'error') finish(() => reject(new Error(event.data.error)));
      if (event.data.type === 'complete') finish(() => resolve(event.data.result));
    };
    worker.postMessage({type:'run', config});
  });
}
