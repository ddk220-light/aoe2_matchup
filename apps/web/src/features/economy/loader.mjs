/**
 * Loads army-economics documents the way the Matchup Advisor loads its data:
 * the immutable static file named by the release (components.economy.files in
 * src/generated/data-manifest.json, i.e. /data/<version>/<civ>.json) first,
 * the API (/api/economy/<Civ>, /api/economy) when no static URL is known.
 * One request per document; a failed request is forgotten so it can be retried.
 *
 * Not used by any page yet (the UI integration is a later, owner-led step).
 */
import {createRuntimeData, evaluateMatchup} from './matchup.mjs';

export const economyUrl = (files, name) => name === null
    ? files?.metadata?.url || '/api/economy'
    : files?.[name.toLowerCase()]?.url || `/api/economy/${encodeURIComponent(name)}`;

export function createEconomyLoader({files = null, fetch: fetchImpl = (...args) => globalThis.fetch(...args)} = {}) {
    const cache = new Map();
    function load(name) {
        const key = name === null ? 'metadata' : `civ:${name}`;
        if (!cache.has(key)) {
            cache.set(key, fetchImpl(economyUrl(files, name)).then(async response => {
                if (!response.ok) throw new Error('Army economics data unavailable');
                return response.json();
            }).catch(error => { cache.delete(key); throw error; }));
        }
        return cache.get(key);
    }
    const loader = {
        metadata: () => load(null),
        civilization: name => load(name),
        /** Runtime data (see matchup.mjs) holding the named civilizations. */
        async runtime(names) {
            const [metadata, ...documents] = await Promise.all([loader.metadata(), ...[...new Set(names)].map(load)]);
            return createRuntimeData(metadata, documents);
        },
        /** evaluateMatchup for `[civ, unitId, mode, count]` selections, loading both civilizations. */
        async evaluate(left, right, populations = [null, null]) {
            return evaluateMatchup(await loader.runtime([left[0], right[0]]), left, right, populations);
        },
    };
    return loader;
}
