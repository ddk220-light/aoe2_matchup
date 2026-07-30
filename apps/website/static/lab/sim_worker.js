/*
 * Role: lab — the multi-seed scoreboard worker for the sim harness.
 *
 * A 600 s fight at 60 Hz is 36 000 ticks; ten of them back-to-back on the main
 * thread would freeze the page for seconds. Running them here keeps the harness
 * clickable (that responsiveness is a stated acceptance criterion) and costs
 * nothing in fidelity: this is the same engine module the page imports, so a
 * scoreboard row and a watched fight with the same seed are the same battle.
 *
 * Protocol
 *   in : { teams: [spec1, spec2], seeds: number[], arena? }  (specs are createSimulation's;
 *        `arena` is createSimulation's own opt-in field — "golden" or omitted)
 *   out: { seed, winner, time, alive1, alive2, hp1, hp2 }   one per seed, in order
 *        { seed, error }                                    one seed blew up
 *        { done: true, count }                              batch finished
 *
 * A new batch simply replaces the old one — the harness terminate()s the worker
 * to cancel, so there is no in-flight cancellation handshake to get wrong.
 */
import { createSimulation } from "/static/js/engine/index.js";

const MAX_SECONDS = 600; // same cap the batch runners and the parity golden use

onmessage = (e) => {
    const { teams, seeds, arena = null } = e.data || {};
    if (!Array.isArray(teams) || !Array.isArray(seeds)) {
        postMessage({ error: "worker needs { teams, seeds }" });
        return;
    }
    for (const seed of seeds) {
        try {
            // Fresh sim per seed: createSimulation deep-copies the combat dicts,
            // so the same `teams` object is safe to reuse across the whole batch.
            const sim = createSimulation({ teams, seed, arena });
            const r = sim.runToEnd(MAX_SECONDS);
            postMessage({ seed, ...r });
        } catch (err) {
            postMessage({ seed, error: String((err && err.message) || err) });
        }
    }
    postMessage({ done: true, count: seeds.length });
};
