// C2-a diagnostic probe: how much of a kiter's retreat heading does the
// RADIAL BASIS actually decide?
//
// C-a1 replaces moveAwayFromTarget's radial basis with "straight away from the
// unit that just hit me", and the C1 M2 prediction was that the realised flee
// cosine to that bearing would move 0.61 -> ~0.88. Measured over the chase
// corpus it moved to 0.63. This probe asks why, by recording the MAGNITUDE of
// every term the method sums before it normalises:
//
//     dx,dy = basis (unit length, 1.0 by construction)
//           + steering.x/y   (orbit + cohesion, E5a/E10)
//           + avoidance      (calculateAvoidance, unbounded sum over bodies)
//           + arena obstacle steer
//
// plus the velocity smoothing that follows (this.vx = 0.3*vx + 0.7*dir), which
// carries the previous heading forward.
//
// It also records how long a contact break actually LASTS and what fraction of
// kiter unit-ticks it occupies -- i.e. whether the mechanism is live at all.
//
// Read-only: it wraps moveAwayFromTarget and calls straight through, and the
// engine's own arithmetic is untouched. `--verify-identity` re-runs every
// (fight, seed) with the wrapper removed and diffs the damage stream.
//
//   node tools/simjs/c2a_break_probe.mjs --tags-file <tags> --seeds 5 \
//        [--c2a off] [--verify-identity]
import { readFileSync } from "node:fs";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import {
    applyR5BSpec, applyR5D1Spec, applyR5DSpec, applyR5FSpec, applyB2Spec,
    applyC2ASpec, applyC2CSpec,
    loadManifest, loadCalibDicts, loadCalibSpawns, spawnsForFight,
} from "./calib_runner.mjs";
import { BattleUnit } from "../../apps/website/static/js/engine/battle_unit.js";
import { TILE_SIZE, C2C } from "../../apps/website/static/js/engine/constants.js";

const argv = process.argv.slice(2);
const flag = (n, d) => {
    const i = argv.indexOf(n);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : d;
};
const has = (n) => argv.includes(n);

const nSeeds = Number(flag("--seeds", "5"));
const tagsFile = flag("--tags-file", null);
const tagArg = String(flag("--tags", ""));
const raw = tagsFile ? readFileSync(tagsFile, "utf8") : tagArg;
const tags = new Set(raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean));
if (!tags.size) {
    console.error("--tags or --tags-file is required");
    process.exit(2);
}

applyR5BSpec(flag("--r5b", null));
applyR5D1Spec(flag("--r5d1", null));
applyR5DSpec(flag("--r5d", null));
applyR5FSpec(flag("--r5f", null));
applyB2Spec(flag("--b2", null));
applyC2ASpec(flag("--c2a", null));
applyC2CSpec(flag("--c2c", null));

const acc = {
    ticks: 0, breakTicks: 0,
    basis: 0, steer: 0, avoid: 0,       // summed magnitudes on BREAK ticks
    avoidFull: 0,                        // |avoidance| INCLUDING the social band
    steerDropped: 0,                     // |orbit+cohesion| that C2C dropped
    breakBasis: 0,                       // |basis| on break ticks (always 1)
    cosStep: 0, cosStepN: 0,             // cos(actual per-tick step, break bearing)
    cosPre: 0, cosPreN: 0,               // cos(pre-smoothing direction, bearing)
    episodes: [], liveNow: new Map(),
};

const origMove = BattleUnit.prototype.moveAwayFromTarget;
function installed(dt, allUnits, steering = null) {
    const hitter = this.contactBreakHitter();
    if (!hitter) return origMove.call(this, dt, allUnits, steering);

    // Reproduce the term magnitudes WITHOUT changing anything: the same
    // expressions the method is about to evaluate, evaluated here first.
    //
    // C2-c changes WHICH of those expressions the method evaluates, so the
    // reproduction has to branch the same way or the reported cos would
    // describe a composition the engine no longer uses. `pure` mirrors
    // moveAwayFromTarget's own `pureFlight` exactly; the full-avoidance and
    // dropped-steering magnitudes are still recorded on both paths so the
    // before/after is one run, not two.
    const pure = C2C.pureFlight;
    let bx = this.x - hitter.x, by = this.y - hitter.y;
    const bl = Math.hypot(bx, by) || 1;
    bx /= bl; by /= bl;
    const avFull = this.calculateAvoidance(allUnits);
    const av = pure ? this.calculateAvoidance(allUnits, true) : avFull;
    const sxRaw = steering ? steering.x : 0, syRaw = steering ? steering.y : 0;
    const sx = pure ? 0 : sxRaw, sy = pure ? 0 : syRaw;
    let px = bx + sx + av.x, py = by + sy + av.y;
    const pl = Math.hypot(px, py) || 1;

    acc.breakTicks++;
    acc.basis += 1;
    acc.steer += Math.hypot(sx, sy);
    acc.steerDropped += Math.hypot(sxRaw, syRaw);
    acc.avoid += Math.hypot(av.x, av.y);
    acc.avoidFull += Math.hypot(avFull.x, avFull.y);
    acc.cosPre += (px / pl) * bx + (py / pl) * by;
    acc.cosPreN++;

    const x0 = this.x, y0 = this.y;
    origMove.call(this, dt, allUnits, steering);
    const mx = this.x - x0, my = this.y - y0;
    const ml = Math.hypot(mx, my);
    if (ml > 1e-9) {
        acc.cosStep += (mx / ml) * bx + (my / ml) * by;
        acc.cosStepN++;
    }
}

function runOne({ dicts, fight, seed, positions, probe }) {
    const s1 = fight.side1, s2 = fight.side2;
    const row = {
        civ1: s1.civ, slug1: s1.slug, n1: s1.count,
        civ2: s2.civ, slug2: s2.slug, n2: s2.count,
    };
    const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });
    sim.eventLog = { damage: [], missiles: [] };
    if (probe) BattleUnit.prototype.moveAwayFromTarget = installed;
    const maxTicks = Math.round(MAX_SECONDS * 60);
    let ticks = 0;
    const live = new Map();      // unit -> tick the current break started
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
        if (probe) {
            for (const u of [...sim.team1, ...sim.team2]) {
                if (u.state === "dead") { live.delete(u); continue; }
                if (!u.isRanged() || u.minAttackRange > 0) continue;
                acc.ticks++;
                const on = u.contactBreakFrom !== null;
                if (on && !live.has(u)) live.set(u, ticks);
                if (!on && live.has(u)) {
                    acc.episodes.push((ticks - live.get(u)) * STEP);
                    live.delete(u);
                }
            }
        }
    }
    if (probe) {
        for (const [, t0] of live) acc.episodes.push((ticks - t0) * STEP);
        BattleUnit.prototype.moveAwayFromTarget = origMove;
    }
    return { damage: sim.eventLog.damage, duration: sim.battleTime };
}

const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const fights = loadManifest().filter((f) => tags.has(f.tag));
let mismatches = 0;
for (const f of fights) {
    const positions = spawnsForFight(spawns, f);
    for (let seed = 1; seed <= nSeeds; seed++) {
        const r = runOne({ dicts, fight: f, seed, positions, probe: true });
        if (has("--verify-identity")) {
            const bare = runOne({ dicts, fight: f, seed, positions, probe: false });
            if (JSON.stringify(r.damage) !== JSON.stringify(bare.damage)
                || r.duration !== bare.duration) {
                mismatches++;
                console.error(`IDENTITY BROKEN: ${f.run_id} seed ${seed}`);
            }
        }
    }
}

const med = (a) => {
    if (!a.length) return NaN;
    const s = [...a].sort((x, y) => x - y);
    return s[Math.floor(s.length / 2)];
};
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN);
const n = Math.max(1, acc.breakTicks);
console.log(`fights ${fights.length} x ${nSeeds} seeds`);
console.log(`kiter unit-ticks          ${acc.ticks}`);
console.log(`  with a live break       ${acc.breakTicks} (${(100 * acc.breakTicks / Math.max(1, acc.ticks)).toFixed(1)}%)`);
console.log(`break episodes            ${acc.episodes.length}  median ${med(acc.episodes).toFixed(2)}s  mean ${mean(acc.episodes).toFixed(2)}s  p90 ${(acc.episodes.length ? [...acc.episodes].sort((a, b) => a - b)[Math.floor(0.9 * acc.episodes.length)] : NaN).toFixed(2)}s`);
console.log("");
console.log("term magnitudes on a BREAK tick (mean, before normalisation):");
console.log(`  |radial basis|          ${(acc.basis / n).toFixed(3)}   (1.0 by construction)`);
console.log(`  |orbit + cohesion|      ${(acc.steer / n).toFixed(3)}${C2C.pureFlight ? `   (C2C dropped ${(acc.steerDropped / n).toFixed(3)})` : ""}`);
console.log(`  |avoidance|             ${(acc.avoid / n).toFixed(3)}${C2C.pureFlight ? `   (overlap band only; full band ${(acc.avoidFull / n).toFixed(3)})` : ""}`);
console.log("");
console.log(`cos(pre-smoothing dir, break bearing)   ${(acc.cosPre / Math.max(1, acc.cosPreN)).toFixed(3)}`);
console.log(`cos(actual tick step,  break bearing)   ${(acc.cosStep / Math.max(1, acc.cosStepN)).toFixed(3)}`);
console.log(`(tile size ${TILE_SIZE}px)`);
if (has("--verify-identity")) {
    console.log(mismatches === 0
        ? "identity check: PASS (probe is behaviour-neutral)"
        : `identity check: FAIL on ${mismatches} run(s)`);
}
