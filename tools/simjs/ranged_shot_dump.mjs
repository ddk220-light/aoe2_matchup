// R5 forensics: dump the engine's RANGED fights in the same shape the tapes
// expose, so every tape statistic has an engine twin computed by the same code.
//
// The recordings for the six ranged-vs-ranged fights carry a MISSILES stream
// (one row per projectile per frame: id, owner, fired_from, x, y), which the
// melee corpus never had. The engine logs missiles too (sim.eventLog.missiles
// via BattleUnit.recordMissile), but only `{t, id, fired_from, owner}` -- no
// target, no launch geometry, no impact. Those three are exactly what the R5
// questions need (range at launch, target movement state at launch, hit vs
// miss per shot), so this file adds them WITHOUT touching the engine:
//
//   BattleUnit.prototype.fireProjectile is wrapped here, in tools/, and the
//   wrapper only READS `this` and `target` (ids, x, y, hp) before delegating
//   to the original and stamping those reads onto the missile record the
//   original just pushed. It draws no rng, mutates no engine state, changes
//   no call ordering and is not in stateHash() -- so a run with the wrapper
//   installed is bit-identical to one without it. `--verify-identity` proves
//   that on every (fight, seed) by re-running the same seed with the wrapper
//   removed and diffing the damage stream.
//
// One file per (fight, seed): <out-dir>/<run_id>/seed-<n>.shots.json
//   {
//     run_id, tag, seed, duration_s, winner_owner, sides,       // as calib_runner
//     damage:   [ {t, attacker, victim, damage, victim_hp_after, kill,
//                  attacker_owner, victim_owner}, ... ],
//     missiles: [ {t, id, fired_from, owner, target, sx, sy, tx, ty,
//                  dist_tiles, speed_tiles, impact_t, target_hp}, ... ],
//     frames:   [ {t, u: [[id, x_tiles, y_tiles, owner, hp], ...]}, ... ]  // 10 Hz
//   }
//
// Owners are remapped from engine team space (1/2) into recording owner space
// (the manifest's side1.owner / side2.owner) exactly as calib_runner.mjs does
// -- side labels do NOT follow the tag's word order, so everything downstream
// keys off the owner number.
//
//     node tools/simjs/ranged_shot_dump.mjs --tags <t1,t2,...> --seeds 20 \
//         --out-dir D:/AI/aoe2_golden/simruns_r5_ranged
//     node tools/simjs/ranged_shot_dump.mjs --tags <...> --seeds 3 --verify-identity
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import { BattleUnit } from "../../apps/website/static/js/engine/battle_unit.js";
import { TILE_SIZE } from "../../apps/website/static/js/engine/constants.js";
import {
    applyR5BSpec, applyR5D1Spec, applyR5DSpec, applyR5FSpec, applyD2Spec,
} from "./calib_runner.mjs";
import {
    loadManifest, loadCalibDicts, loadCalibSpawns, spawnsForFight,
} from "./calib_runner.mjs";

// ---- the wrapper ----------------------------------------------------------
// Installed/removed around a run so --verify-identity can A/B the same seed.
const ORIGINAL_FIRE = BattleUnit.prototype.fireProjectile;

function installShotProbe() {
    BattleUnit.prototype.fireProjectile = function (target, isExtra = false) {
        const log = this.sim && this.sim.eventLog;
        const before = log ? log.missiles.length : -1;
        // Read-only snapshot of the launch, taken BEFORE the original runs so
        // the target's position is the one the projectile was aimed at (the
        // engine freezes impact at the launch-time target position).
        const snap = (log && target)
            ? {
                target: target.id,
                sx: this.x / TILE_SIZE,
                sy: this.y / TILE_SIZE,
                tx: target.x / TILE_SIZE,
                ty: target.y / TILE_SIZE,
                target_hp: target.currentHp,
                is_extra: isExtra ? 1 : 0,
                speed_tiles: (this.projectileSpeed > 0
                    ? this.projectileSpeed : 7 * TILE_SIZE) / TILE_SIZE,
                // R5e additions, both read-only and both taken BEFORE the
                // original runs, because the original mutates the state each
                // one depends on.
                //
                // `aimx/aimy` is the UNDISPLACED aim point. fireProjectile
                // computes exactly this and then, if and only if the accuracy
                // roll FAILED, throws it by up to the dat dispersion; the
                // projectile's own `targetX/targetY` (recorded as ax/ay below)
                // is the post-throw point. So `ax != aimx` is an exact,
                // rng-free readout of "this shot's accuracy roll failed" --
                // which is the population R5e's plannedDamage question is
                // about, and which is otherwise unobservable from outside
                // (`willHit` is a local). aimPointFor() draws no rng, mutates
                // nothing and is already called by the original with the same
                // arguments, so calling it here is a pure duplicate read.
                //
                // `covered` is the engine's OWN coverage arithmetic for the
                // victim this shot is going to, at the instant of the launch:
                // coveredDamageOn() = in-flight-arriving-first (D3) + this
                // tick's claims (T2). It has to be read before the original
                // because the original's claimShot() adds THIS shot to the
                // ledger. covered >= target_hp is the exact signature of T1's
                // `best || primary` all-covered fallback, since selectShotTarget
                // returns a covered victim only when every reachable enemy is
                // covered. Also a pure read: it iterates sim.projectiles and
                // reads sim.tickClaims, and writes neither.
                aimx: this.aimPointFor(target).x / TILE_SIZE,
                aimy: this.aimPointFor(target).y / TILE_SIZE,
                covered: this.coveredDamageOn(target),
            }
            : null;
        const out = ORIGINAL_FIRE.call(this, target, isExtra);
        if (log && snap && log.missiles.length > before) {
            const m = log.missiles[log.missiles.length - 1];
            // WHERE THE SHOT IS ACTUALLY GOING. `tx, ty` above is the target's
            // position at launch, which is what the PRE-R5b engine aimed at.
            // Since R5b/D2 the aim point is the ballistic intercept, displaced
            // again if the accuracy roll failed, so the launch-time target
            // position is neither the impact point nor the right flight
            // length -- deriving impact_t from it mis-times every shot at a
            // mover by the lead, which is exactly the population the R5c
            // questions are about. The projectile the original just pushed
            // carries the real one, so read it off instead of recomputing it.
            const proj = this.sim.projectiles[this.sim.projectiles.length - 1];
            if (proj) {
                snap.ax = proj.targetX / TILE_SIZE;   // true impact point
                snap.ay = proj.targetY / TILE_SIZE;
                snap.planned = proj.plannedDamage;
                snap.flight_tiles = Math.hypot(snap.ax - snap.sx,
                                               snap.ay - snap.sy);
                snap.impact_t = m.t + snap.flight_tiles
                    / (proj.speed / TILE_SIZE);
            }
            const dx = snap.tx - snap.sx, dy = snap.ty - snap.sy;
            snap.dist_tiles = Math.hypot(dx, dy);
            if (snap.impact_t === undefined) {
                snap.impact_t = m.t + snap.dist_tiles / snap.speed_tiles;
            }
            Object.assign(m, snap);
        }
        return out;
    };
}

function removeShotProbe() {
    BattleUnit.prototype.fireProjectile = ORIGINAL_FIRE;
}

// ---- one (fight, seed) ----------------------------------------------------

function sideSummary(team, side) {
    const alive = team.filter((u) => u.state !== "dead");
    return {
        owner: side.owner, unit_name: side.unit_name, civ: side.civ,
        slug: side.slug, start_count: side.count,
        survivors: alive.length,
        hp_remaining: alive.reduce((s, u) => s + u.currentHp, 0),
    };
}

function runOne({ dicts, fight, seed, positions, withFrames = true }) {
    const s1 = fight.side1, s2 = fight.side2;
    const row = {
        civ1: s1.civ, slug1: s1.slug, n1: s1.count,
        civ2: s2.civ, slug2: s2.slug, n2: s2.count,
    };
    const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });
    sim.eventLog = { damage: [], missiles: [] };

    const ownerOf = { 1: s1.owner, 2: s2.owner };
    const frames = [];
    let next = 0;
    const maxTicks = Math.round(MAX_SECONDS * 60);
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
        if (withFrames && sim.battleTime >= next) {
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
    return {
        run_id: fight.run_id, tag: fight.tag, seed,
        duration_s: sim.battleTime,
        winner: sim.winner,
        winner_owner: ownerOf[sim.winner] ?? null,
        sides: {
            [String(s1.owner)]: sideSummary(sim.team1, s1),
            [String(s2.owner)]: sideSummary(sim.team2, s2),
        },
        damage: sim.eventLog.damage.map((e) => ({
            ...e,
            attacker_owner: ownerOf[e.attacker_owner],
            victim_owner: ownerOf[e.victim_owner],
        })),
        missiles: sim.eventLog.missiles.map((m) => ({
            ...m, owner: ownerOf[m.owner],
        })),
        frames,
    };
}

// ---- CLI ------------------------------------------------------------------
const argv = process.argv.slice(2);
const flag = (n, d) => {
    const i = argv.indexOf(n);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : d;
};
const has = (n) => argv.includes(n);

const outDir = flag("--out-dir", "D:/AI/aoe2_golden/simruns_r5_ranged");
const nSeeds = Number(flag("--seeds", "20"));
const tags = new Set(String(flag("--tags", "")).split(",").filter(Boolean));
if (!tags.size) {
    console.error("--tags is required (comma-separated manifest tags)");
    process.exit(2);
}

// Round-5b rule selection, same spec grammar as calib_runner.mjs --r5b, so the
// emergence suite can be measured on any stage of the marginal sweep (and on
// `off`, i.e. the pre-R5b engine the forensics report itself measured).
applyR5BSpec(flag("--r5b", null));
// Round-5d-1 projectile/aim rules, same grammar (`--r5d1 off` == the R5b
// engine 71cd4a9, which is the engine column the R5c report measured).
applyR5D1Spec(flag("--r5d1", null));
// Same for the Round-5d targeting/approach rules (--r5d off == pre-R5d).
applyR5DSpec(flag("--r5d", null));
// Same for the Round-5f selection/silence rules (--r5f off == pre-R5f).
applyR5FSpec(flag("--r5f", null));
// Same for the Phase-D2 siege projectile/blast rules (--d2 off == pre-D2,
// bb2e6fa, which is the engine column the D1 report itself measured).
applyD2Spec(flag("--d2", null));

const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const fights = loadManifest().filter((f) => tags.has(f.tag));
const missing = [...tags].filter((t) => !fights.some((f) => f.tag === t));
if (missing.length) {
    console.error(`no manifest fight for tag(s): ${missing.join(", ")}`);
    process.exit(2);
}

let nFiles = 0, nShots = 0, mismatches = 0;
for (const f of fights) {
    const positions = spawnsForFight(spawns, f);
    const dir = path.join(outDir, f.run_id);
    mkdirSync(dir, { recursive: true });
    for (let seed = 1; seed <= nSeeds; seed++) {
        installShotProbe();
        const rec = runOne({ dicts, fight: f, seed, positions });
        removeShotProbe();
        if (has("--verify-identity")) {
            const bare = runOne({ dicts, fight: f, seed, positions, withFrames: false });
            const a = JSON.stringify(rec.damage);
            const b = JSON.stringify(bare.damage);
            if (a !== b || rec.duration_s !== bare.duration_s) {
                mismatches++;
                console.error(`IDENTITY BROKEN: ${f.run_id} seed ${seed}`);
            }
        }
        writeFileSync(path.join(dir, `seed-${seed}.shots.json`), JSON.stringify(rec));
        nFiles++;
        nShots += rec.missiles.length;
    }
    console.log(`  ${f.run_id}`);
}
console.log(`wrote ${nFiles} shot files (${nShots} missiles) -> ${outDir}`);
if (has("--verify-identity")) {
    console.log(mismatches === 0
        ? "identity check: PASS (probe is behaviour-neutral on every seed)"
        : `identity check: FAIL on ${mismatches} run(s)`);
}
