// Target-thrash fix (docs/superpowers/specs/2026-07-29-target-thrash-design.md).
// Tests are added incrementally, one section per commit of the four-part fix:
//   (a) STUCK_PROGRESS_RATE -- the rate expression is a no-op at dt=1/60.
//   (b) the pursuing/receding exemption.
//   (c) the stale lastDistToTarget baseline re-stamp.
//   (d) the reachability swap.
import { test } from "node:test";
import assert from "node:assert/strict";
import { STUCK_PROGRESS_RATE } from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const BASE = {
    hp: 100, attack: 10, attack_range: 0, attack_speed: 0.5, attack_delay: 0,
    movement_speed: 1.0, melee_armor: 0, pierce_armor: 0, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Unit",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

// ---- (a): the rate expression must be an EXACT no-op at the current tick
// rate. This is the load-bearing IEEE-754 fact the whole step (a) rests on:
// if this ever stops being exactly 0.5, moveTowardTarget's stuck bar has
// silently changed behavior at 60fps and the calib byte-identity check
// (tools/simjs/calib_runner.mjs before/after, see task-10-report.md) would
// have caught it -- this test pins the same fact at the unit level.
test("STUCK_PROGRESS_RATE * dt(1/60) is bit-exact today's historical 0.5 literal", () => {
    const dt = 1 / 60;
    assert.equal(STUCK_PROGRESS_RATE * dt, 0.5);
    // Belt-and-braces: also confirm the rate itself is 1.0 tile/s (30px / 30px-per-tile).
    assert.equal(STUCK_PROGRESS_RATE, 30);
});

// ---- (b): the pursuing/receding exemption ----------------------------------
// Colinear 1-unit-vs-1-unit scenarios (both units far from anything else, so
// calculateAvoidance contributes exactly (0,0) and velocity smoothing
// converges to unit magnitude on tick 1 -- see task-10-report.md for the
// closed-form derivation this test's constants were picked from): a chaser
// at moveSpeed 30px/s (movement_speed 1.0) closes 1.0px/tick; a target that
// "flees" by being nudged 0.9px/tick (net closing 0.1px/tick, well under the
// 0.5px/tick stalled bar) reproduces the "Paladin closing on a fleeing
// Arbalester at ~0.53 t/s" pathology in miniature.
test("(b) honest chase: pursuing && receding exempts an honestly-closing chase from the stuck bar", () => {
    const sim = simStub(10);
    const chaser = new BattleUnit("1-0", 1, { ...BASE, movement_speed: 1.0 }, "chaser", "Franks", sim);
    const target = new BattleUnit("2-0", 2, { ...BASE, movement_speed: 1.0 }, "target", "Mongols", sim);
    chaser.x = 0; chaser.y = 0;
    target.x = 200; target.y = 0;
    sim.team1.push(chaser); sim.team2.push(target);
    chaser.target = target;
    chaser.lastDistToTarget = chaser.distanceTo(target);

    const dt = 1 / 60;
    const fleeStep = 0.9; // px/tick, applied directly -- models the target's own flee move
    for (let i = 0; i < 120; i++) {
        sim.battleTime += dt;
        chaser.moveTowardTarget(dt, [chaser, target]);
        target.x += fleeStep;
    }
    assert.equal(
        chaser.stuckTimer, 0,
        "an honestly-closing chase of a genuinely fleeing target must never accumulate stuckTimer",
    );
    assert.equal(chaser.blockedTargets.size, 0, "must never blacklist a genuinely fleeing, honestly-pursued target");
    assert.equal(chaser.target, target, "must never lose/null the target while honestly pursuing");
});

test("(b) scrum-wedge: a stalled chase of a NON-fleeing target still accumulates and blacklists", () => {
    const sim = simStub(11);
    // Slow enough that its own approach never clears the stuck bar, but the
    // target here never moves at all -- receding is false regardless of
    // pursuing, so the exemption must never fire.
    const chaser = new BattleUnit("1-0", 1, { ...BASE, movement_speed: 0.1 }, "chaser", "Franks", sim);
    const target = new BattleUnit("2-0", 2, { ...BASE, movement_speed: 1.0 }, "target", "Mongols", sim);
    chaser.x = 0; chaser.y = 0;
    target.x = 200; target.y = 0; // stationary -- never moved by this test
    sim.team1.push(chaser); sim.team2.push(target);
    chaser.target = target;
    chaser.lastDistToTarget = chaser.distanceTo(target);

    const dt = 1 / 60;
    let blacklisted = false;
    for (let i = 0; i < 120 && !blacklisted; i++) {
        sim.battleTime += dt;
        chaser.moveTowardTarget(dt, [chaser, target]);
        if (chaser.target === null) blacklisted = true;
    }
    assert.ok(blacklisted, "a stalled chase of a target that never moves must still blacklist within 120 ticks (2s)");
    assert.equal(chaser.blockedTargets.has(target), true);
    assert.equal(chaser.stuckTimer, 0);
});

// ---- (c): the stale lastDistToTarget baseline ------------------------------
// lastDistToTarget is written only inside moveTowardTarget and findTarget --
// the kiting/attacking branches never touch it. A unit that spends several
// ticks in one of those branches and then re-enters moving compares an
// N-tick-old distance against a bar sized for ONE tick. This test isolates
// that defect from the (b) exemption by keeping the target stationary (so
// `receding` reads false regardless of staleness) and instead repositioning
// the CHASER itself during the "gap" (as collision resolution or a kite
// elsewhere would), then giving it one perfectly healthy re-entry tick.
test("(c) stale lastDistToTarget baseline: re-entry after a gap re-baselines instead of judging across it", () => {
    const sim = simStub(12);
    const chaser = new BattleUnit("1-0", 1, { ...BASE, movement_speed: 2.0 }, "chaser", "Franks", sim);
    const target = new BattleUnit("2-0", 2, { ...BASE, movement_speed: 1.0 }, "target", "Mongols", sim);
    chaser.x = 400; chaser.y = 300;
    target.x = 500; target.y = 300; // stationary throughout -- isolates from (b)
    sim.team1.push(chaser); sim.team2.push(target);
    chaser.target = target;
    chaser.lastDistToTarget = chaser.distanceTo(target);

    const dt = 1 / 60;

    // Tick 1: a normal, healthy approach -- establishes the baseline.
    sim.battleTime += dt;
    chaser.moveTowardTarget(dt, [chaser, target]);
    assert.equal(chaser.stuckTimer, 0, "a healthy first tick must not be stalled");

    // Gap: 5 ticks pass with this unit in a different branch (kiting/
    // attacking) that never calls moveTowardTarget -- lastDistToTarget goes
    // stale relative to sim.battleTime. The chaser is bumped 30px further
    // from its (still stationary) target during the gap.
    sim.battleTime += 5 * dt;
    chaser.x -= 30;

    // Re-entry tick: the chaser closes a full, healthy moveAmount step --
    // comfortably clearing the stuck bar on its OWN one-tick progress. Only
    // a stale multi-tick-old baseline could flag this as stalled.
    sim.battleTime += dt;
    chaser.moveTowardTarget(dt, [chaser, target]);
    assert.equal(
        chaser.stuckTimer, 0,
        "re-entry after a gap must judge against a re-baselined (current) " +
        "distance, not accumulate stuckTimer off a stale multi-tick-old one",
    );
});
