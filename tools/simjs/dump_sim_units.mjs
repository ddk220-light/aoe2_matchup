// Writes a tape-shaped 10 Hz POSITION stream for sim runs, so the
// position-based forensics (melee_lock_forensics.py --positions) can ask the
// engine the same questions it asks the recordings.
//
// One file per (fight, seed): <out-dir>/<run_id>/seed-<n>.units.json
//   { run_id, seed, frames: [ { t, u: [[id, x, y, owner, hp], ...] } ] }
// x/y are TILES (px / TILE_SIZE) to match the tapes' units stream, and owners
// are remapped to recording-owner space exactly as calib_runner.mjs does.
//
//     node tools/simjs/dump_sim_units.mjs --out-dir <dir> [--seeds 1]
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import { TILE_SIZE } from "../../apps/website/static/js/engine/constants.js";
import { loadManifest, loadCalibDicts, loadCalibSpawns } from "./calib_runner.mjs";

const MELEE = new Set([
    "champion", "halberdier", "paladin", "heavy_camel", "hussar",
    "elite_steppe", "elite_elephant",
]);

const argv = process.argv.slice(2);
const flag = (n, d) => {
    const i = argv.indexOf(n);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : d;
};
const outDir = flag("--out-dir", "D:/AI/aoe2_golden/simruns");
const nSeeds = Number(flag("--seeds", "1"));

const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const fights = loadManifest().filter(
    (f) => MELEE.has(f.side1.slug) && MELEE.has(f.side2.slug));

let n = 0;
for (const f of fights) {
    const e = spawns[f.tag];
    const positions = { 1: e[String(f.side1.owner)], 2: e[String(f.side2.owner)] };
    const ownerOf = { 1: f.side1.owner, 2: f.side2.owner };
    const dir = path.join(outDir, f.run_id);
    mkdirSync(dir, { recursive: true });
    for (let seed = 1; seed <= nSeeds; seed++) {
        const row = {
            civ1: f.side1.civ, slug1: f.side1.slug, n1: f.side1.count,
            civ2: f.side2.civ, slug2: f.side2.slug, n2: f.side2.count,
        };
        const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });
        const frames = [];
        let next = 0;
        const maxTicks = Math.round(MAX_SECONDS * 60);
        let ticks = 0;
        while (sim.winner === null && ticks < maxTicks) {
            sim.step(STEP);
            ticks++;
            if (sim.battleTime >= next) {
                next += 0.1;
                frames.push({
                    t: sim.battleTime,
                    u: [...sim.team1, ...sim.team2]
                        .filter((u) => u.state !== "dead")
                        .map((u) => [u.id, u.x / TILE_SIZE, u.y / TILE_SIZE,
                            ownerOf[u.team], u.currentHp]),
                });
            }
        }
        writeFileSync(path.join(dir, `seed-${seed}.units.json`),
            JSON.stringify({ run_id: f.run_id, seed, frames }));
        n++;
    }
    console.log(`  ${f.run_id}`);
}
console.log(`wrote ${n} position files -> ${outDir}`);
