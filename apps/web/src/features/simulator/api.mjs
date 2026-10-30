import {catalog} from './catalog.mjs';
import {operation} from '../../lib/operations.mjs';
export {LatestRequest} from '../rankings/api.mjs';
const mismatch = () => Object.assign(new Error('Simulation data and worker versions do not match. Reload the page.'), {requiresReload:true});
async function checkVersions(response,signal) {
    const simulator = response.headers.get('X-AoE2-Simulation-Version');
    const engine = response.headers.get('X-AoE2-Engine-Version');
    if(simulator || engine) {
        if(simulator !== catalog.versions.simulator || engine !== catalog.versions.engine) throw mismatch();
        return;
    }
    // The frozen Railway rollback has no migration headers. Verify its existing
    // public release identity before giving a configuration to the worker.
    const legacyResponse = await fetch('/api/release',{signal,cache:'no-store'});
    if(!legacyResponse.ok) throw mismatch();
    const legacy = await legacyResponse.json(), expected = catalog.legacy_release;
    if(legacy.engine?.source_sha256 !== expected.engine.source_sha256
       || legacy.reference_sha256 !== expected.reference_sha256
       || legacy.mechanics_schema_version !== expected.mechanics_schema_version) throw mismatch();
}
export async function requestJson(url,{method='GET',body,signal,timeoutMs=10000}={}) {
    const controller=new AbortController();
    const abort=()=>controller.abort(signal?.reason);
    if(signal?.aborted) abort(); else signal?.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(()=>controller.abort(new Error('Request timed out')),timeoutMs);
    const configuration = url.startsWith('/api/v3/');
    const started = performance.now();
    try {
        const response=await fetch(url,{method,signal:controller.signal,
            ...(configuration||body!==undefined?{headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),
                ...(configuration?{'X-AoE2-Simulation-Version':catalog.versions.simulator,'X-AoE2-Engine-Version':catalog.versions.engine}:{})}}:{}),
            ...(body===undefined?{}:{body:JSON.stringify(body)})});
        const data=await response.json();
        if(!response.ok||data?.error)throw Object.assign(new Error(data?.detail||data?.error||`HTTP ${response.status}`),
            {requiresReload:configuration&&response.status===409});
        if(configuration) {
            await checkVersions(response,controller.signal);
            performance.mark('aoe2-configuration-ready');
            operation('configuration_ready', performance.now() - started);
        }
        return data;
    } catch (error) {
        if (configuration && !signal?.aborted) operation('configuration_error', performance.now() - started);
        throw error;
    } finally {clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
