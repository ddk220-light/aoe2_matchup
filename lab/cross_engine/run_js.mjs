// Task 11 — JS side of the cross-engine comparison. READ-ONLY experiment.
//
// Runs the 16-unit roster (roster.json) as an unordered round-robin — 120
// pairs, 10 v 10, seeds 1..5 = 600 fights — through the EXTRACTED JS engine
// (apps/website/static/js/engine/, the bit-exact replica of the production
// Battle Sim) via tools/simjs/headless.mjs, and writes js_results.json.
//
//     node lab/cross_engine/run_js.mjs
//
// It imports the engine only through runFight() and reads only
// lab/cross_engine/{roster.json,combat_dicts.json} — combat_dicts.json is
// written by run_py.py, so BOTH engines are fed byte-identical unit stats out
// of the same data/golden/aoe2_reference.db rows. Run run_py.py first.
//
// Snapshots: runFight() records the golden's snapshot trajectory (one every 60
// ticks). We drop it immediately per fight and keep only `final`, so nothing
// accumulates across the 600 fights.
//
// CAP / TIMEOUT BEHAVIOUR: maxSeconds 600 -> an integer budget of 36000 ticks
// at 1/60 s (headless.mjs's documented form; identical to runToEnd(600) at this
// budget). If the budget runs out with both sides alive, sim.winner stays null
// — the JS declines to break the tie. There is no wall-clock cap and no
// early-exit rule of any kind on this side.
//
// NORMALISATION — the shared 4-value vocabulary, identical to run_py.py's
// normalise() (see that file's module docstring for the full mapping):
//     1 -> "a"   2 -> "b"   0 -> "draw" (mutual annihilation)
//     null -> "timeout_both_alive" (600 s budget spent, both sides alive)
// The raw winner is kept alongside so nothing is lost.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { runFight } from "../../tools/simjs/headless.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const readJson = (f) => JSON.parse(readFileSync(path.join(HERE, f), "utf8"));

const MAX_SECONDS = 600;

const roster = readJson("roster.json");
const dicts = readJson("combat_dicts.json");
const COUNT = roster.count_per_side;
const SEEDS = roster.seeds;

const byKey = new Map(roster.units.map((u) => [u.key, u]));
const keys = roster.units.map((u) => u.key);
const pairs = [];
for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) pairs.push([keys[i], keys[j]]);
}

function normalise(raw, aliveA, aliveB) {
    if (raw === 1) return "a";
    if (raw === 2) return "b";
    if (raw === 0) return aliveA === 0 && aliveB === 0 ? "draw" : "timeout_both_alive";
    return "timeout_both_alive"; // null: the 600 s budget ran out
}

console.log(
    `${pairs.length} pairs x ${SEEDS.length} seeds = ${pairs.length * SEEDS.length} fights`,
);

const rows = [];
const t0 = Date.now();
let n = 0;
for (const [a, b] of pairs) {
    const ua = byKey.get(a);
    const ub = byKey.get(b);
    const row = {
        civ1: ua.civ, slug1: ua.slug, n1: COUNT,
        civ2: ub.civ, slug2: ub.slug, n2: COUNT,
    };
    for (const seed of SEEDS) {
        const w0 = Date.now();
        const { final } = runFight({ dicts, row, seed, maxSeconds: MAX_SECONDS });
        const wall = (Date.now() - w0) / 1000;
        rows.push({
            a, b, seed,
            winner: normalise(final.winner, final.alive1, final.alive2),
            time: final.time,
            alive_a: final.alive1,
            alive_b: final.alive2,
            hp_a: final.hp1,
            hp_b: final.hp2,
            raw_winner: final.winner,
            end_reason: final.winner === null ? "time_cap" : "eliminated",
            wall_s: Number(wall.toFixed(3)),
        });
        if (wall > 300) console.log(`  !! slow fight ${a} vs ${b} seed ${seed}: ${wall.toFixed(0)}s wall`);
    }
    n++;
    if (n % 10 === 0 || n === pairs.length) {
        console.log(`[${n}/${pairs.length}] ${a} vs ${b}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
}

const payload = {
    engine: "js apps/website/static/js/engine (via tools/simjs/headless.mjs)",
    count_per_side: COUNT,
    seeds: SEEDS,
    max_seconds: MAX_SECONDS,
    max_wallclock: null,
    sim_dt: 1 / 60,
    wall_seconds_total: Number(((Date.now() - t0) / 1000).toFixed(1)),
    rows,
};
writeFileSync(path.join(HERE, "js_results.json"), JSON.stringify(payload, null, 1));
console.log(`wrote ${rows.length} rows -> js_results.json (${payload.wall_seconds_total}s)`);
