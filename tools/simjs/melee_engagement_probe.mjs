// Phase B / measurement 2 + 4 + 5: WHY does the engine's outnumbered melee side
// stop swinging?
//
// The v2 re-baseline (docs/calibration/v2_melee_rebaseline.md §6c) established
// the defect as a COUNT of swinging bodies, not a rate: paladin offence 0.99x,
// cadence 1.00x, damage/armour exact, but the outnumbered side's concurrent-
// attacker count runs 0.73-0.75x of the tape's. This probe asks the engine, tick
// by tick, what the missing bodies were doing instead.
//
// NO ENGINE FILE IS MODIFIED. Instrumentation is four prototype wrappers
// installed from here (update / findTarget / meleeTargetLock /
// meleeBumpRetarget), each of which calls straight through to the original and
// only READS state afterwards. Nothing the wrappers write is ever read by the
// engine, none of them draws from the rng, and none of them mutates a unit field
// the engine owns -- every probe field is prefixed `_pj`. The determinism claim
// is not taken on trust: `--verify <clean-runs-dir>` diffs this run's damage
// stream against a plain calib_runner.mjs run of the same (fight, seed) and
// fails loudly on the first mismatch.
//
//     node tools/simjs/calib_runner.mjs --tags <T> --seeds 20 --out-dir <clean>
//     node tools/simjs/melee_engagement_probe.mjs --tags <T> --seeds 20 \
//          --out-dir <probe> --pos-seeds 5 --verify <clean>
//
// Per (fight, seed) it writes <out-dir>/<run_id>/seed-<n>.probe.json:
//   { run_id, tag, seed, duration_s, winner_owner, sides, damage, probe }
// and, for seed <= --pos-seeds, a tape-shaped 10 Hz position stream
// <out-dir>/<run_id>/seed-<n>.units.json in the exact format
// dump_sim_units.mjs writes, so the position-based forensics can read either.
//
// ---- what a "wasted tick" is ----------------------------------------------
// For a LIVING MELEE unit, after its own update() has run:
//
//   engaged      state is "attacking" or "committed" -- it is inside the swing
//                loop (mid-windup, mid-reload, or landing a blow).
//   in reach     at least one living enemy sits inside this unit's OWN reach
//                test, `attackRange + radius + enemy.radius` -- the identical
//                expression inRange() uses, so "could have swung at somebody"
//                is the engine's own predicate and not a tuned radius.
//   WASTED TICK  in reach AND NOT engaged. A fight was available and the unit
//                declined it.
//
// Every wasted tick is classified into exactly one bucket, and consecutive
// same-bucket ticks are collapsed into an EPISODE whose duration is reported.
// Buckets (`probe.<owner>.wasted`):
//
//   lock_out_of_reach   the unit holds a living target that is OUTSIDE its
//                       reach while a different enemy is inside it. E14's
//                       target lock is the only thing keeping it there.
//   lane_journey        same, but the current target was picked by E15b's lane
//                       rule in preference to a NEARER enemy -- the unit is
//                       walking a lane it chose.
//   no_target           target null/dead and findTarget produced nothing.
//   no_target_blacklist ... with a non-empty blockedTargets set.
//   other               anything else (a state-machine branch not covered
//                       above). Reported so the buckets are exhaustive; a
//                       non-zero count here means this taxonomy is incomplete.
//
// A unit-tick that is neither engaged nor wasted is OUT OF CONTACT: nothing at
// all is inside its reach. That is the third and (measured first) much larger
// share of the non-engaged time, so it is classified too (`outOfContact`):
//
//   approach_nearest     walking at the nearest living enemy -- an honest
//                        approach, the best case.
//   approach_nonnearest  walking at a living enemy that is NOT the nearest,
//                        i.e. past somebody closer. `approachExtraTiles`
//                        records how much farther.
//   approach_lane        ... where E15b's lane rule made that choice.
//   approach_no_target   no target at all.
//
// and `stalledTicks` counts approach ticks on which the distance to the nearest
// living enemy did NOT fall -- a unit walking but making no headway, which is
// what a body-jam looks like from the outside.
//
// Sub-flags recorded on every lock_out_of_reach / lane_journey tick:
//
//   lockProtected  meleeTargetLock() is true, i.e. the stuck bar is FORBIDDEN
//                  from blacklisting this target. This is the E14 lock actively
//                  holding the unit off a reachable enemy.
//   bumpEligible   some enemy other than the target is inside the bump test's
//                  own floor (radius + radius + 1 px), i.e. rule 2 should have
//                  fired. Expected ~0; a non-zero count would mean the bump is
//                  broken rather than merely out of range.
//   crowdedOut     EVERY enemy inside this unit's reach already has
//                  MELEE_CONTACT_SLOTS allies of ours swinging at it. The unit
//                  genuinely has nowhere to stand -- a legitimate reason not to
//                  swing, and the control that separates slot starvation from
//                  lock freezing.
//
// `bumpGapTiles` is the distance from the nearest in-reach enemy's BUMP FLOOR:
// dist - (radius + radius + 1), in tiles. It is the width of the band in which
// an enemy is hittable but not touchable -- the band in which the lock holds and
// the bump cannot fire.
import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildFight, STEP, MAX_SECONDS } from "./headless.mjs";
import { BattleUnit } from "../../apps/website/static/js/engine/index.js";
import {
    TILE_SIZE, MELEE_CONTACT_SLOTS,
} from "../../apps/website/static/js/engine/constants.js";
import {
    loadManifest, loadCalibDicts, loadCalibSpawns, spawnsForFight,
    applyW1Spec, applyW2Spec,
} from "./calib_runner.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
void HERE;

// ---------------------------------------------------------------------------
// accumulators
// ---------------------------------------------------------------------------

const WASTE_CLASSES = [
    "lock_out_of_reach", "lane_journey", "no_target", "no_target_blacklist",
    "other",
];
const APPROACH_CLASSES = [
    "approach_nearest", "approach_nonnearest", "approach_lane",
    "approach_no_target",
];

// Fight time is binned at this resolution so the concurrency/engagement
// timeline (measurement 1) can be normalised to fight length in Python without
// the probe having to know the duration up front.
const BIN_S = 2.0;

function newSideAcc() {
    const wasted = {};
    for (const c of WASTE_CLASSES) wasted[c] = 0;
    const epi = {};
    for (const c of WASTE_CLASSES) epi[c] = [];
    const approach = {};
    for (const c of APPROACH_CLASSES) approach[c] = 0;
    return {
        aliveTicks: 0,
        engagedTicks: 0,
        reachTicks: 0,        // ticks with >= 1 living enemy inside own reach
        wastedTicks: 0,
        wasted,
        episodes: epi,
        // out-of-contact (nothing inside own reach, not engaged)
        outTicks: 0,
        approach,
        stalledTicks: 0,
        approachExtraTiles: [],
        nearestDistTiles: [],
        // per-BIN_S timeline: [alive, engaged, wasted, out] per bin
        bins: [],
        // sub-flags, counted over lock_out_of_reach + lane_journey ticks
        lockProtected: 0,
        bumpEligible: 0,
        crowdedOut: 0,
        primeSuspect: 0,      // lockProtected && !crowdedOut && !bumpEligible
        primeEpisodes: [],
        bumpGapTiles: [],     // sampled at 1 Hz to keep the file small
        lockOverreachTiles: [],
        // re-acquisition ledger (measurement 5)
        acquisitions: 0,
        reacquisitions: 0,    // findTarget with hasAcquiredTarget already true
        laneDiverts: 0,
        laneExtraTiles: [],
        laneJourneyS: [],     // divert -> next engaged tick
        plainJourneyS: [],    // non-diverted re-acquisition -> next engaged tick
        // E14 / stuck-bar ledger (measurement 4)
        stuckTrips: 0,        // stuck bar reached 0.8 s on a melee unit
        slotRelease: 0,       // ... and meleeTargetLock() let it blacklist
        lockHeld: 0,          // ... and the lock refused
        bumpFires: 0,
        // measurement 4, geometric: attackers-in-reach per victim of THIS side's
        // units, sampled at 10 Hz. Histogram index = attacker count.
        apvHist: [],
    };
}

let P = null;   // active probe accumulator, or null when instrumentation is off

// ---------------------------------------------------------------------------
// prototype wrappers -- install once, call straight through
// ---------------------------------------------------------------------------

const origUpdate = BattleUnit.prototype.update;
const origFindTarget = BattleUnit.prototype.findTarget;
const origLock = BattleUnit.prototype.meleeTargetLock;
const origBump = BattleUnit.prototype.meleeBumpRetarget;

function reachTo(u, e) {
    return u.attackRange + u.radius + e.radius;
}

// Allies of `u`'s team already targeting `victim` AND inside their own reach of
// it -- the identical count meleeTargetLock() does, minus `u` itself.
function attackersInReach(u, victim) {
    const allies = u.team === 1 ? u.sim.team1 : u.sim.team2;
    let n = 0;
    for (const a of allies) {
        if (a === u || a.state === "dead" || a.target !== victim) continue;
        if (a.distanceTo(victim) <= reachTo(a, victim)) n++;
    }
    return n;
}

BattleUnit.prototype.findTarget = function (enemies) {
    if (!P) return origFindTarget.call(this, enemies);
    const wasAcquired = this.hasAcquiredTarget;
    // The pre-E15b answer, recomputed exactly as findTarget's own loop does:
    // nearest living enemy that is not blacklisted.
    let closest = null, closestDist = Infinity;
    for (const e of enemies) {
        if (e.state === "dead") continue;
        if (this.blockedTargets.has(e)) continue;
        const d = this.distanceTo(e);
        if (d < closestDist) { closestDist = d; closest = e; }
    }
    const t = origFindTarget.call(this, enemies);
    const acc = P.side[this.team];
    if (acc && !this.isRanged() && t) {
        acc.acquisitions++;
        this._pjLane = false;
        this._pjJourneyT = this.sim.battleTime;
        this._pjJourneyLane = false;
        if (wasAcquired) {
            acc.reacquisitions++;
            if (closest && t !== closest) {
                acc.laneDiverts++;
                acc.laneExtraTiles.push(
                    (this.distanceTo(t) - closestDist) / TILE_SIZE);
                this._pjLane = true;
                this._pjJourneyLane = true;
            }
        }
    }
    return t;
};

BattleUnit.prototype.meleeTargetLock = function () {
    const held = origLock.call(this);
    if (P && P.countLockCalls) {
        const acc = P.side[this.team];
        if (acc) {
            acc.stuckTrips++;
            if (held) acc.lockHeld++;
            else acc.slotRelease++;
        }
    }
    return held;
};

BattleUnit.prototype.meleeBumpRetarget = function (enemies) {
    if (!P) return origBump.call(this, enemies);
    const before = this.target;
    origBump.call(this, enemies);
    if (this.target !== before) {
        const acc = P.side[this.team];
        if (acc) acc.bumpFires++;
        this._pjLane = false;
        this._pjJourneyT = this.sim.battleTime;
        this._pjJourneyLane = false;
    }
};

BattleUnit.prototype.update = function (dt, allUnits, enemies) {
    if (!P || this.state === "dead") {
        return origUpdate.call(this, dt, allUnits, enemies);
    }
    // meleeTargetLock is called from exactly one place in the engine -- the
    // stuck bar in moveTowardTarget -- so counting calls that happen INSIDE
    // update() is counting stuck-bar trips. The probe's own calls below happen
    // with the flag off and are therefore never counted.
    P.countLockCalls = true;
    origUpdate.call(this, dt, allUnits, enemies);
    P.countLockCalls = false;
    if (this.state === "dead" || this.isRanged()) return;
    classify(this, enemies);
};

// ---------------------------------------------------------------------------
// the per-tick classification
// ---------------------------------------------------------------------------

function closeEpisode(u, acc) {
    if (!u._pjEpiClass) return;
    const dur = u.sim.battleTime - u._pjEpiT;
    acc.episodes[u._pjEpiClass].push(dur);
    if (u._pjEpiPrime) acc.primeEpisodes.push(dur);
    u._pjEpiClass = null;
    u._pjEpiPrime = false;
}

function bin(acc, t) {
    const i = Math.floor(t / BIN_S);
    while (acc.bins.length <= i) acc.bins.push([0, 0, 0, 0]);
    return acc.bins[i];
}

function classify(u, enemies) {
    const acc = P.side[u.team];
    if (!acc) return;
    acc.aliveTicks++;
    const b = bin(acc, u.sim.battleTime);
    b[0]++;
    const engaged = u.state === "attacking" || u.state === "committed";
    if (engaged) {
        acc.engagedTicks++;
        // A journey ends when the unit is back in the swing loop.
        if (u._pjJourneyT != null) {
            const j = u.sim.battleTime - u._pjJourneyT;
            (u._pjJourneyLane ? acc.laneJourneyS : acc.plainJourneyS).push(j);
            u._pjJourneyT = null;
        }
    }

    // --- who could this unit hit right now? --------------------------------
    let nInReach = 0;
    let minBumpGap = Infinity;
    let allFull = true;
    let nearest = null, nearestDist = Infinity;
    for (const e of enemies) {
        if (e.state === "dead") continue;
        const d = u.distanceTo(e);
        if (d < nearestDist) { nearestDist = d; nearest = e; }
        if (d > reachTo(u, e)) continue;
        nInReach++;
        const gap = d - (u.radius + e.radius + 1);
        if (gap < minBumpGap) minBumpGap = gap;
        if (allFull && attackersInReach(u, e) < MELEE_CONTACT_SLOTS) {
            allFull = false;
        }
    }
    if (nInReach > 0) acc.reachTicks++;
    const prevNearest = u._pjPrevNearest;
    u._pjPrevNearest = nearestDist;

    // --- measurement 4, geometric: how crowded are THIS side's own bodies? --
    // Sampled at 10 Hz (every 6th tick) to keep the cost linear-ish.
    if (P.tick % 6 === 0) {
        const foes = u.team === 1 ? u.sim.team2 : u.sim.team1;
        let n = 0;
        for (const a of foes) {
            if (a.state === "dead" || a.target !== u) continue;
            if (a.distanceTo(u) <= reachTo(a, u)) n++;
        }
        acc.apvHist[n] = (acc.apvHist[n] || 0) + 1;
    }

    if (engaged) { b[1]++; closeEpisode(u, acc); return; }

    // --- out of contact: nothing at all is hittable -------------------------
    if (nInReach === 0) {
        closeEpisode(u, acc);
        acc.outTicks++;
        b[3]++;
        const t0 = u.target;
        if (!t0 || t0.state === "dead") {
            acc.approach.approach_no_target++;
        } else if (t0 === nearest) {
            acc.approach.approach_nearest++;
        } else {
            acc.approach[u._pjLane ? "approach_lane" : "approach_nonnearest"]++;
            if (P.tick % 60 === 0) {
                acc.approachExtraTiles.push(
                    (u.distanceTo(t0) - nearestDist) / TILE_SIZE);
            }
        }
        // A unit walking without closing on the nearest enemy is jammed.
        // 1e-9 tolerance, not a tuned epsilon: the test is "did the distance
        // fall at all", and float noise is the only thing being excluded.
        if (prevNearest != null && nearestDist >= prevNearest - 1e-9) {
            acc.stalledTicks++;
        }
        if (P.tick % 60 === 0) acc.nearestDistTiles.push(nearestDist / TILE_SIZE);
        return;
    }

    // --- a wasted tick ------------------------------------------------------
    acc.wastedTicks++;
    b[2]++;
    const t = u.target;
    let cls;
    if (!t || t.state === "dead") {
        cls = u.blockedTargets.size > 0 ? "no_target_blacklist" : "no_target";
    } else if (u.distanceTo(t) > reachTo(u, t)) {
        cls = u._pjLane ? "lane_journey" : "lock_out_of_reach";
    } else {
        // target IS in reach yet the unit is not engaged -- by construction
        // unreachable through the melee branch of update(); reported so the
        // taxonomy stays honest rather than silently absorbing a surprise.
        cls = "other";
    }
    acc.wasted[cls]++;

    let prime = false;
    if (cls === "lock_out_of_reach" || cls === "lane_journey") {
        const lockProtected = origLock.call(u);
        const bumpEligible = minBumpGap <= 0;
        if (lockProtected) acc.lockProtected++;
        if (bumpEligible) acc.bumpEligible++;
        if (allFull) acc.crowdedOut++;
        prime = lockProtected && !allFull && !bumpEligible;
        if (prime) acc.primeSuspect++;
        if (P.tick % 60 === 0) {
            acc.bumpGapTiles.push(minBumpGap / TILE_SIZE);
            acc.lockOverreachTiles.push(
                (u.distanceTo(t) - reachTo(u, t)) / TILE_SIZE);
        }
    }

    if (u._pjEpiClass !== cls || u._pjEpiPrime !== prime) {
        closeEpisode(u, acc);
        u._pjEpiClass = cls;
        u._pjEpiPrime = prime;
        u._pjEpiT = u.sim.battleTime;
    }
}

// ---------------------------------------------------------------------------
// summarisation -- histograms, not raw samples, so files stay small
// ---------------------------------------------------------------------------

function q(vals, p) {
    if (!vals.length) return null;
    const s = [...vals].sort((a, b) => a - b);
    const i = p * (s.length - 1);
    const lo = Math.floor(i), hi = Math.min(lo + 1, s.length - 1);
    return s[lo] + (s[hi] - s[lo]) * (i - lo);
}

function summariseSamples(vals) {
    if (!vals.length) return { n: 0 };
    let sum = 0;
    for (const v of vals) sum += v;
    return {
        n: vals.length,
        mean: sum / vals.length,
        p10: q(vals, 0.10),
        median: q(vals, 0.50),
        p90: q(vals, 0.90),
        max: Math.max(...vals),
    };
}

function finaliseSide(acc) {
    const out = {
        aliveTicks: acc.aliveTicks,
        engagedTicks: acc.engagedTicks,
        reachTicks: acc.reachTicks,
        wastedTicks: acc.wastedTicks,
        wasted: acc.wasted,
        outTicks: acc.outTicks,
        approach: acc.approach,
        stalledTicks: acc.stalledTicks,
        approachExtraTiles: summariseSamples(acc.approachExtraTiles),
        nearestDistTiles: summariseSamples(acc.nearestDistTiles),
        bins: acc.bins,
        lockProtected: acc.lockProtected,
        bumpEligible: acc.bumpEligible,
        crowdedOut: acc.crowdedOut,
        primeSuspect: acc.primeSuspect,
        acquisitions: acc.acquisitions,
        reacquisitions: acc.reacquisitions,
        laneDiverts: acc.laneDiverts,
        stuckTrips: acc.stuckTrips,
        slotRelease: acc.slotRelease,
        lockHeld: acc.lockHeld,
        bumpFires: acc.bumpFires,
        apvHist: [...acc.apvHist].map((v) => v || 0),
        episodes: {},
        primeEpisodes: summariseSamples(acc.primeEpisodes),
        laneExtraTiles: summariseSamples(acc.laneExtraTiles),
        laneJourneyS: summariseSamples(acc.laneJourneyS),
        plainJourneyS: summariseSamples(acc.plainJourneyS),
        bumpGapTiles: summariseSamples(acc.bumpGapTiles),
        lockOverreachTiles: summariseSamples(acc.lockOverreachTiles),
    };
    for (const c of WASTE_CLASSES) {
        out.episodes[c] = summariseSamples(acc.episodes[c]);
    }
    return out;
}

// ---------------------------------------------------------------------------
// runner
// ---------------------------------------------------------------------------

function runOne({ dicts, fight, seed, positions, wantPositions }) {
    const s1 = fight.side1, s2 = fight.side2;
    const row = {
        civ1: s1.civ, slug1: s1.slug, n1: s1.count,
        civ2: s2.civ, slug2: s2.slug, n2: s2.count,
    };
    const sim = buildFight({ dicts, row, seed, arena: "tapebox", positions });
    sim.eventLog = { damage: [], missiles: [] };

    P = { side: { 1: newSideAcc(), 2: newSideAcc() }, tick: 0, countLockCalls: false };

    const frames = [];
    let nextFrame = 0;
    const ownerOf = { 1: s1.owner, 2: s2.owner };
    const maxTicks = Math.round(MAX_SECONDS * 60);
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.step(STEP);
        ticks++;
        P.tick = ticks;
        if (wantPositions && sim.battleTime >= nextFrame) {
            nextFrame += 0.1;
            frames.push({
                t: sim.battleTime,
                u: [...sim.team1, ...sim.team2]
                    .filter((u) => u.state !== "dead")
                    .map((u) => [u.id, u.x / TILE_SIZE, u.y / TILE_SIZE,
                        ownerOf[u.team], u.currentHp]),
            });
        }
    }

    const probe = {
        [String(s1.owner)]: finaliseSide(P.side[1]),
        [String(s2.owner)]: finaliseSide(P.side[2]),
    };
    P = null;

    const damage = sim.eventLog.damage.map((e) => ({
        ...e,
        attacker_owner: ownerOf[e.attacker_owner],
        victim_owner: ownerOf[e.victim_owner],
    }));
    const sideSummary = (team, side) => {
        const alive = team.filter((u) => u.state !== "dead");
        return {
            owner: side.owner, civ: side.civ, slug: side.slug,
            start_count: side.count, survivors: alive.length,
            hp_remaining: alive.reduce((s, u) => s + u.currentHp, 0),
        };
    };
    return {
        record: {
            run_id: fight.run_id, tag: fight.tag, seed,
            duration_s: sim.battleTime,
            winner_owner: ownerOf[sim.winner] ?? null,
            sides: {
                [String(s1.owner)]: sideSummary(sim.team1, s1),
                [String(s2.owner)]: sideSummary(sim.team2, s2),
            },
            damage,
            probe,
        },
        frames: wantPositions ? frames : null,
    };
}

// ---- CLI ------------------------------------------------------------------
const argv = process.argv.slice(2);
const flag = (n, d) => {
    const i = argv.indexOf(n);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : d;
};
const outDir = flag("--out-dir", "D:/AI/aoe2_golden/simruns_b1_probe");
const nSeeds = Number(flag("--seeds", "20"));
const posSeeds = Number(flag("--pos-seeds", "5"));
const verifyDir = flag("--verify", null);
const tagsArg = flag("--tags", null);
// Same flag grammar as calib_runner.mjs (`--w1 scrumWalk` / `--w1 off`);
// applied in-process before any fight is built.
applyW1Spec(flag("--w1", null));
applyW2Spec(flag("--w2", null));

const dicts = loadCalibDicts();
const spawns = loadCalibSpawns();
const all = loadManifest();
let fights = all;
if (tagsArg) {
    const wanted = new Set(tagsArg.split(",").filter(Boolean));
    const have = new Set(all.map((f) => f.tag));
    const unknown = [...wanted].filter((t) => !have.has(t)).sort();
    if (unknown.length) {
        console.error(`--tags: unknown (or quarantined) tag(s): ${unknown.join(", ")}`);
        process.exit(2);
    }
    fights = all.filter((f) => wanted.has(f.tag));
}
if (!fights.length) {
    console.error("no fights selected");
    process.exit(2);
}

console.log(`probe: ${fights.length} fights x ${nSeeds} seeds -> ${outDir}`);
const t0 = process.hrtime.bigint();
let nFiles = 0, nVerified = 0;
for (const fight of fights) {
    const positions = spawnsForFight(spawns, fight);
    const dir = path.join(outDir, fight.run_id);
    mkdirSync(dir, { recursive: true });
    for (let seed = 1; seed <= nSeeds; seed++) {
        const { record, frames } = runOne({
            dicts, fight, seed, positions, wantPositions: seed <= posSeeds,
        });
        if (verifyDir) {
            const clean = path.join(verifyDir, fight.run_id, `seed-${seed}.json`);
            if (existsSync(clean)) {
                const ref = JSON.parse(readFileSync(clean, "utf8"));
                const a = JSON.stringify(ref.damage);
                const b = JSON.stringify(record.damage);
                if (a !== b || Math.abs(ref.duration_s - record.duration_s) > 1e-12) {
                    console.error(
                        `DETERMINISM FAILURE: ${fight.run_id} seed ${seed} — the ` +
                        "probe changed the fight. Instrumentation is not read-only.");
                    process.exit(3);
                }
                nVerified++;
            }
        }
        writeFileSync(path.join(dir, `seed-${seed}.probe.json`),
            JSON.stringify(record));
        if (frames) {
            writeFileSync(path.join(dir, `seed-${seed}.units.json`),
                JSON.stringify({ run_id: fight.run_id, seed, frames }));
        }
        nFiles++;
    }
    console.log(`  ${fight.run_id}`);
}
const wall = Number(process.hrtime.bigint() - t0) / 1e9;
console.log(`wrote ${nFiles} probe files -> ${outDir} (${wall.toFixed(1)}s)`);
if (verifyDir) {
    console.log(`determinism: ${nVerified}/${nFiles} (fight, seed) damage streams ` +
        "byte-identical to the un-instrumented run");
}
