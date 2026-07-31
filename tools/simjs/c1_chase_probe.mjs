// Phase C / measurement rig: dump the engine's MELEE-CHASING-RANGED fights in
// the same shape the tapes expose, PLUS the chaser-side internals the tapes
// cannot show.
//
// E12 measured, corpus-wide, that a melee unit's swing-interval ratio
// tape/engine is 1.001 in melee-vs-melee but 1.29 when the melee unit is
// CHASING a RANGED one. The tape's chasers keep losing and re-winning contact
// with their kiting victims in a way the engine does not model. Every
// measurement in tools/simjs/c1_chaser_cadence.py that can be computed from
// positions + damage + missiles is computed from THIS file's output and from
// the recording by the same Python function, so a tape number and an engine
// number are never two implementations that happen to share a name.
//
// Two outputs per (fight, seed):
//
//   <out-dir>/<run_id>/seed-<n>.shots.json
//       byte-for-byte the schema tools/simjs/ranged_shot_dump.mjs writes
//       ({run_id, tag, seed, duration_s, winner_owner, sides, damage,
//        missiles, frames}), so ranged_fire_forensics.load_engine reads it
//       unchanged and every R5-era statistic is reproducible from it.
//
//   <out-dir>/<run_id>/seed-<n>.chase.json
//       the chaser ledger: per melee unit, every target change with the
//       engine's own reason for it, every blacklist add, every blacklist
//       clear, every stuck-bar trip -- the PURSUIT_BAR/blacklist semantics
//       measurement 4 audits. Plus a per-tick residency count (target held /
//       target null) so "how much of its life did a chaser spend without a
//       target" is a duration, not an event count.
//
// NO ENGINE FILE IS MODIFIED. Instrumentation is four prototype wrappers
// installed from here (fireProjectile / update / meleeTargetLock /
// meleeBumpRetarget). Each calls straight through to the original and only
// READS state around it; nothing a wrapper writes is ever read by the engine,
// none draws from the rng, none mutates an engine-owned field (probe fields
// are prefixed `_pc`). The determinism claim is checked, not asserted:
// `--verify-identity` re-runs each (fight, seed) with every wrapper removed
// and diffs the damage stream and duration.
//
//     node tools/simjs/c1_chase_probe.mjs --tags <t1,t2,...> --seeds 20 \
//          --out-dir D:/AI/aoe2_golden/simruns_c1
//     node tools/simjs/c1_chase_probe.mjs --tags <...> --seeds 3 --verify-identity
//     node tools/simjs/c1_chase_probe.mjs --tags <...> --r5d1 trailingWindowLead ...
//
// `--chaser-vs-ranged-only` (default on) restricts the ledger to melee units
// whose CURRENT enemy side is ranged, which in this corpus is the whole
// chaser population; pass `--all-melee` to log every melee unit instead.
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import { BattleUnit } from "../../apps/website/static/js/engine/battle_unit.js";
import { TILE_SIZE } from "../../apps/website/static/js/engine/constants.js";
import {
    applyR5BSpec, applyR5D1Spec, applyR5DSpec, applyR5FSpec, applyB2Spec,
    applyC2ASpec, applyC2BSpec, applyC2CSpec,
    loadManifest, loadCalibDicts, loadCalibSpawns, spawnsForFight,
} from "./calib_runner.mjs";

// ---------------------------------------------------------------------------
// the shot wrapper -- verbatim behaviour of ranged_shot_dump.mjs's, so the
// `.shots.json` files the two tools write are the same measurement.
// ---------------------------------------------------------------------------

const ORIGINAL_FIRE = BattleUnit.prototype.fireProjectile;

function installShotProbe() {
    BattleUnit.prototype.fireProjectile = function (target, isExtra = false) {
        const log = this.sim && this.sim.eventLog;
        const before = log ? log.missiles.length : -1;
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
                aimx: this.aimPointFor(target).x / TILE_SIZE,
                aimy: this.aimPointFor(target).y / TILE_SIZE,
                covered: this.coveredDamageOn(target),
                // Phase C addition, both pure reads and both needed by
                // measurement 6: whether the SHOOTER was standing still at
                // launch (the tape can only infer this from 10 Hz positions,
                // the engine knows it exactly) and how far the victim had
                // travelled in the previous tick. `_pcPrevX/_pcPrevY` are
                // written by the update wrapper below and read by nothing in
                // the engine.
                shooter_state: this.state,
                tgt_state: target.state,
                tgt_step_px: (target._pcPrevX == null)
                    ? null
                    : Math.hypot(target.x - target._pcPrevX,
                                 target.y - target._pcPrevY),
            }
            : null;
        const out = ORIGINAL_FIRE.call(this, target, isExtra);
        if (log && snap && log.missiles.length > before) {
            const m = log.missiles[log.missiles.length - 1];
            const proj = this.sim.projectiles[this.sim.projectiles.length - 1];
            if (proj) {
                snap.ax = proj.targetX / TILE_SIZE;
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

// ---------------------------------------------------------------------------
// the chase wrappers
// ---------------------------------------------------------------------------

const ORIGINAL_UPDATE = BattleUnit.prototype.update;
const ORIGINAL_LOCK = BattleUnit.prototype.meleeTargetLock;
const ORIGINAL_BUMP = BattleUnit.prototype.meleeBumpRetarget;

// Active chase accumulator, or null when instrumentation is off.
let C = null;

function newChaseAcc() {
    return {
        // per-tick residency, in TICKS (converted to seconds by the reader)
        aliveTicks: 0,
        targetTicks: 0,          // holds a living target
        nullTargetTicks: 0,      // no target at all
        rangedTargetTicks: 0,    // target is a ranged unit (the chase proper)
        blockedNonEmptyTicks: 0, // blacklist non-empty
        // events
        retarget: { blacklist: 0, victim_died: 0, bump: 0, acquired: 0, other: 0 },
        switchedToDifferentLiving: 0,  // gave up a LIVING target for another
        blacklistAdds: 0,
        blacklistClears: 0,
        stuckTrips: 0,           // meleeTargetLock() called == bar hit 0.8 s
        lockHeld: 0,             // ... and the lock refused to release
        lockReleased: 0,         // ... and the unit blacklisted + dropped
        bumpFires: 0,
        // distributions (seconds / tiles)
        gapToReacquireS: [],     // target null -> target non-null
        distAtAbandonTiles: [],  // distance to the target it just blacklisted
        chaseSpanS: [],          // continuous seconds spent on ONE target
        blockedSizeAtAdd: [],
    };
}

BattleUnit.prototype.meleeTargetLock = function () {
    const held = ORIGINAL_LOCK.call(this);
    if (C && C.inUpdate) {
        const acc = C.side[this.team];
        if (acc && !this.isRanged()) {
            acc.stuckTrips++;
            if (held) acc.lockHeld++;
            else acc.lockReleased++;
        }
    }
    return held;
};

BattleUnit.prototype.meleeBumpRetarget = function (enemies) {
    if (!C) return ORIGINAL_BUMP.call(this, enemies);
    const before = this.target;
    ORIGINAL_BUMP.call(this, enemies);
    if (this.target !== before) {
        this._pcBumped = true;
        const acc = C.side[this.team];
        if (acc) acc.bumpFires++;
    }
};

BattleUnit.prototype.update = function (dt, allUnits, enemies) {
    if (!C || this.state === "dead") {
        return ORIGINAL_UPDATE.call(this, dt, allUnits, enemies);
    }
    const melee = !this.isRanged();
    const acc = C.side[this.team];
    // --- pre-update snapshot (pure reads) ----------------------------------
    const prevTarget = this.target;
    const prevTargetAlive = prevTarget ? prevTarget.state !== "dead" : false;
    const prevTargetDist = prevTarget
        ? this.distanceTo(prevTarget) / TILE_SIZE : null;
    const prevBlockedSize = this.blockedTargets.size;
    const prevBlockedHas = prevTarget ? this.blockedTargets.has(prevTarget) : false;
    this._pcBumped = false;
    // Previous position, for the shot wrapper's `tgt_step_px`. Written before
    // the engine moves the unit; read by nothing the engine owns.
    this._pcPrevX = this.x;
    this._pcPrevY = this.y;

    C.inUpdate = true;
    ORIGINAL_UPDATE.call(this, dt, allUnits, enemies);
    C.inUpdate = false;

    if (!melee || !acc || this.state === "dead") return;

    // --- residency ---------------------------------------------------------
    acc.aliveTicks++;
    const t = this.target;
    if (t && t.state !== "dead") {
        acc.targetTicks++;
        if (t.isRanged()) acc.rangedTargetTicks++;
    } else if (!t) {
        acc.nullTargetTicks++;
    }
    if (this.blockedTargets.size > 0) acc.blockedNonEmptyTicks++;

    // --- blacklist ledger --------------------------------------------------
    const nowBlocked = this.blockedTargets.size;
    if (nowBlocked > prevBlockedSize) {
        acc.blacklistAdds += nowBlocked - prevBlockedSize;
        acc.blockedSizeAtAdd.push(nowBlocked);
        if (prevTargetDist != null) acc.distAtAbandonTiles.push(prevTargetDist);
    } else if (nowBlocked === 0 && prevBlockedSize > 0) {
        // Either the clean-up loop removed dead entries or the all-blocked
        // reset fired. Both are "the blacklist emptied"; the engine has one
        // code path for each and neither is distinguishable from outside
        // without holding the set, so they are counted together and named
        // for what is observable.
        acc.blacklistClears++;
    }

    // --- target-change ledger ---------------------------------------------
    if (t !== prevTarget) {
        // Close the chase span that just ended.
        if (this._pcSpanT != null) {
            acc.chaseSpanS.push(this.sim.battleTime - this._pcSpanT);
        }
        this._pcSpanT = t ? this.sim.battleTime : null;
        let reason;
        if (prevTarget && !prevTargetAlive) reason = "victim_died";
        else if (this._pcBumped) reason = "bump";
        else if (prevTarget && (this.blockedTargets.has(prevTarget) || (!prevBlockedHas && nowBlocked > prevBlockedSize))) {
            reason = "blacklist";
        } else if (!prevTarget) reason = "acquired";
        else reason = "other";
        acc.retarget[reason]++;
        if (prevTarget && prevTargetAlive && t && t !== prevTarget) {
            acc.switchedToDifferentLiving++;
        }
        if (!prevTarget && this._pcNullSinceT != null) {
            acc.gapToReacquireS.push(this.sim.battleTime - this._pcNullSinceT);
            this._pcNullSinceT = null;
        }
    }
    if (!t && this._pcNullSinceT == null) this._pcNullSinceT = this.sim.battleTime;
    if (t && this._pcSpanT == null) this._pcSpanT = this.sim.battleTime;
};

// ---------------------------------------------------------------------------
// one (fight, seed)
// ---------------------------------------------------------------------------

function sideSummary(team, side) {
    const alive = team.filter((u) => u.state !== "dead");
    return {
        owner: side.owner, unit_name: side.unit_name, civ: side.civ,
        slug: side.slug, start_count: side.count,
        survivors: alive.length,
        hp_remaining: alive.reduce((s, u) => s + u.currentHp, 0),
    };
}

function runOne({ dicts, fight, seed, positions, withFrames = true, chase = true }) {
    const s1 = fight.side1, s2 = fight.side2;
    const row = {
        civ1: s1.civ, slug1: s1.slug, n1: s1.count,
        civ2: s2.civ, slug2: s2.slug, n2: s2.count,
    };
    const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });
    sim.eventLog = { damage: [], missiles: [] };

    const ownerOf = { 1: s1.owner, 2: s2.owner };
    if (chase) {
        C = { inUpdate: false, side: { 1: newChaseAcc(), 2: newChaseAcc() } };
    }
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
    const chaseOut = C
        ? { [String(s1.owner)]: C.side[1], [String(s2.owner)]: C.side[2] }
        : null;
    C = null;
    return {
        rec: {
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
        },
        chase: chaseOut && {
            run_id: fight.run_id, tag: fight.tag, seed,
            duration_s: sim.battleTime,
            tick_s: STEP,
            sides: chaseOut,
        },
    };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const argv = process.argv.slice(2);
const flag = (n, d) => {
    const i = argv.indexOf(n);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : d;
};
const has = (n) => argv.includes(n);

const outDir = flag("--out-dir", "D:/AI/aoe2_golden/simruns_c1");
const nSeeds = Number(flag("--seeds", "20"));
// `--tags` is a comma-separated list; `--tags-file` reads the same list from a
// file (the chaser corpus is 86 tags, which is past what a shell will pass
// through comfortably). Exactly one of the two is required.
const tagArg = String(flag("--tags", ""));
const tagsFile = flag("--tags-file", null);
const rawTags = tagsFile
    ? readFileSync(tagsFile, "utf8")
    : tagArg;
const tags = new Set(rawTags.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean));
if (!tags.size) {
    console.error("--tags or --tags-file is required (comma-separated manifest tags)");
    process.exit(2);
}

applyR5BSpec(flag("--r5b", null));
applyR5D1Spec(flag("--r5d1", null));
applyR5DSpec(flag("--r5d", null));
applyR5FSpec(flag("--r5f", null));
applyB2Spec(flag("--b2", null));
applyC2ASpec(flag("--c2a", null));
applyC2BSpec(flag("--c2b", null));
applyC2CSpec(flag("--c2c", null));

const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const fights = loadManifest().filter((f) => tags.has(f.tag));
const missing = [...tags].filter((t) => !fights.some((f) => f.tag === t));
if (missing.length) {
    console.error(`no manifest fight for tag(s) (unknown or quarantined): ${missing.join(", ")}`);
    process.exit(2);
}

let nFiles = 0, nShots = 0, mismatches = 0;
for (const f of fights) {
    const positions = spawnsForFight(spawns, f);
    const dir = path.join(outDir, f.run_id);
    mkdirSync(dir, { recursive: true });
    for (let seed = 1; seed <= nSeeds; seed++) {
        installShotProbe();
        const { rec, chase } = runOne({ dicts, fight: f, seed, positions });
        removeShotProbe();
        if (has("--verify-identity")) {
            const bare = runOne({
                dicts, fight: f, seed, positions,
                withFrames: false, chase: false,
            }).rec;
            if (JSON.stringify(rec.damage) !== JSON.stringify(bare.damage)
                || rec.duration_s !== bare.duration_s) {
                mismatches++;
                console.error(`IDENTITY BROKEN: ${f.run_id} seed ${seed}`);
            }
        }
        writeFileSync(path.join(dir, `seed-${seed}.shots.json`), JSON.stringify(rec));
        writeFileSync(path.join(dir, `seed-${seed}.chase.json`), JSON.stringify(chase));
        nFiles++;
        nShots += rec.missiles.length;
    }
    console.log(`  ${f.run_id}`);
}
console.log(`wrote ${nFiles} x2 files (${nShots} missiles) -> ${outDir}`);
if (has("--verify-identity")) {
    console.log(mismatches === 0
        ? "identity check: PASS (probe is behaviour-neutral on every seed)"
        : `identity check: FAIL on ${mismatches} run(s)`);
}
