// One worker of calib_runner.mjs's (fight, seed) pool. Not a CLI — it is only
// ever spawned by `new Worker()` from calib_runner.mjs's parallel branch.
//
// The whole design goal is that this file adds NO behaviour. It loads its
// inputs through calib_runner.mjs's own loaders and runs each task through
// calib_runner.mjs's own `runAndWriteFightSeed`, so a file written here is
// produced by literally the same code as a file written by the sequential
// loop. Parallel/sequential byte-identity is therefore structural, not a
// coincidence two implementations have to be kept in step to preserve.
//
// Protocol (parent drives, worker pulls):
//   worker -> parent  { ready: true }                      "send me work"
//   parent -> worker  { runId, seed }                      one task
//   parent -> worker  { done: true }                       queue drained, exit
//   worker -> parent  { runId, seed, nDamage, nMissiles, elapsedMs }
//   worker -> parent  { runId, seed, error }               task threw
//
// `elapsedMs` is this task's own CPU-ish wall time, which the parent sums per
// fight so its progress lines still say something meaningful when 22 fights
// are in flight at once (they are labelled "cpu", not wall, for that reason).
import { parentPort, workerData } from "node:worker_threads";

import {
    applyR5BSpec,
    applyR5D1Spec,
    applyR5DSpec,
    applyB2Spec,
    loadCalibDicts,
    loadCalibSpawns,
    loadManifest,
    runAndWriteFightSeed,
    spawnsForFight,
} from "./calib_runner.mjs";

const { arenaArg, maxSeconds, outDir, r5bSpec, r5d1Spec, r5dSpec, b2Spec } = workerData;

// Round-5b / Round-5d / Phase-B2 rule flags. Applied BEFORE any fight is built,
// from the
// same spec strings the parent parsed, so every worker configures the engine
// identically and a parallel run stays byte-identical to `--workers 1`.
applyR5BSpec(r5bSpec ?? null);
applyR5D1Spec(r5d1Spec ?? null);
applyR5DSpec(r5dSpec ?? null);
applyB2Spec(b2Spec ?? null);

// Same arena table as the CLI. Duplicated as a two-line lookup rather than
// exported-and-imported because it is the CLI's own argument vocabulary; the
// parent has already validated arenaArg before any worker was created.
const ARENAS = { tapebox: "tapebox", golden: "golden", "plain-legacy": null };
const arena = ARENAS[arenaArg];

const dicts = loadCalibDicts();
const spawns = arenaArg === "tapebox" ? loadCalibSpawns() : null;

// run_id -> fight, so a task message only has to carry the id. Positions are
// derived here, per fight, by the same `spawnsForFight` the sequential loop
// calls — and memoised, because 20 seeds of one fight would otherwise rebuild
// an identical object 20 times.
const fightsById = new Map(loadManifest().map((f) => [f.run_id, f]));
const positionsById = new Map();
function positionsFor(fight) {
    if (!spawns) return null;
    if (!positionsById.has(fight.run_id)) {
        positionsById.set(fight.run_id, spawnsForFight(spawns, fight));
    }
    return positionsById.get(fight.run_id);
}

parentPort.on("message", (msg) => {
    if (msg.done) {
        parentPort.close();
        return;
    }
    const { runId, seed } = msg;
    const t0 = process.hrtime.bigint();
    try {
        const fight = fightsById.get(runId);
        if (!fight) throw new Error(`no manifest fight with run_id "${runId}"`);
        const { nDamage, nMissiles } = runAndWriteFightSeed({
            dicts, fight, seed, maxSeconds, arena,
            positions: positionsFor(fight), outDir,
        });
        parentPort.postMessage({
            runId, seed, nDamage, nMissiles,
            elapsedMs: Number(process.hrtime.bigint() - t0) / 1e6,
        });
    } catch (err) {
        parentPort.postMessage({ runId, seed, error: String(err && err.stack || err) });
    }
});

parentPort.postMessage({ ready: true });
