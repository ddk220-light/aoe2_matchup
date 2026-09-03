// Target-thrash fix (docs/superpowers/specs/2026-07-29-target-thrash-design.md).
// Tests are added incrementally, one section per commit of the four-part fix:
//   (a) STUCK_PROGRESS_RATE -- the rate expression is a no-op at dt=1/60.
//   (b) the pursuing/receding exemption.
//   (c) the stale lastDistToTarget baseline re-stamp.
//   (d) the reachability swap.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    STUCK_PROGRESS_RATE,
    PURSUIT_BAR_FRACTION,
    PURSUIT_MIN_ADVANTAGE,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

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

// ---- (e): the achievable-rate cap on the stuck bar (calibration exp. E4).
//
// The flat bar demands 1.0 tile/s of CLOSING distance. A chaser closes on a
// fleeing target at only the SPEED DIFFERENCE, so every melee unit slower
// than 1.6 t/s chasing a 0.6 t/s Siege Onager (Champion 1.06 -> 0.46 t/s,
// Halberdier 1.10 -> 0.50, Fire Lancer 1.16 -> 0.56, Battle Elephant 0.99 ->
// 0.39) never clears it, blacklists every onager every 0.8 s, and can never
// engage siege at all. Over the 105-fight tape corpus that boundary predicted
// the winner outcome exactly: the only two melee units that DO clear 30 px/s
// against an onager (Steppe Lancer 1.68 -> 32.4, Hussar 1.65 -> 31.5) were
// also the only two onager matchups the sim already got right.
const ONAGER_SPEED = 0.6;
const CHAMPION_SPEED = 1.06;

function pursuitStats(name, speed) {
    return {
        hp: 70, attack: 10, attack_range: 0, attack_speed: 0.5,
        movement_speed: speed, melee_armor: 0, pierce_armor: 0,
        outline_size: 0.2, accuracy: 100, unit_name: name,
    };
}

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

test("the relaxed bar never exceeds the achievable closing rate", () => {
    const sim = simStub(1);
    const chaser = new BattleUnit(
        "1-0", 1, pursuitStats("Champion", CHAMPION_SPEED), "champion", "Chinese", sim);
    const onager = new BattleUnit(
        "2-0", 2, pursuitStats("Siege Onager", ONAGER_SPEED), "siege_onager", "Aztecs", sim);

    const advantage = chaser.moveSpeed - onager.moveSpeed;
    assert.ok(
        Math.abs(advantage - 13.8) < 1e-9,
        "(1.06 - 0.6) tiles/s * 30 px/tile = 13.8 px/s of achievable closing",
    );
    assert.ok(
        advantage < STUCK_PROGRESS_RATE,
        "the whole bug: honest, physically-maximal pursuit cannot clear the flat bar",
    );
    assert.ok(
        advantage >= PURSUIT_MIN_ADVANTAGE,
        "and this chase is winnable enough to deserve the relaxed bar",
    );
    assert.ok(
        advantage * PURSUIT_BAR_FRACTION < advantage,
        "the relaxed bar must sit strictly below what the chaser can deliver",
    );
});

test("a chaser SLOWER than its fleeing target gets no relaxation at all", () => {
    const sim = simStub(1);
    // Champion (1.06) chasing a Heavy Cav Archer (1.54): uncatchable.
    const chaser = new BattleUnit(
        "1-0", 1, pursuitStats("Champion", CHAMPION_SPEED), "champion", "Chinese", sim);
    const kiter = new BattleUnit(
        "2-0", 2, pursuitStats("Heavy Cav Archer", 1.54), "heavy_cav_archer", "Magyars", sim);

    assert.ok(
        chaser.moveSpeed - kiter.moveSpeed < PURSUIT_MIN_ADVANTAGE,
        "an uncatchable chase must stay below the relaxation gate, so the unit " +
        "still blacklists and re-targets exactly as before -- this is what the " +
        "earlier, reverted blanket 'exempt all pursuit' fix got wrong",
    );
});

test("a near-equal-speed chase stays on the flat bar (the arbalester canary)", () => {
    const sim = simStub(1);
    // Champion (1.06) chasing an Arbalester (0.96): closes at 0.1 t/s = 3 px/s.
    const chaser = new BattleUnit(
        "1-0", 1, pursuitStats("Champion", CHAMPION_SPEED), "champion", "Chinese", sim);
    const arb = new BattleUnit(
        "2-0", 2, pursuitStats("Arbalester", 0.96), "arbalester", "Chinese", sim);

    const advantage = chaser.moveSpeed - arb.moveSpeed;
    assert.ok(
        advantage < PURSUIT_MIN_ADVANTAGE,
        "3 px/s would take ~30 s to cross three tiles -- re-targeting really is " +
        "correct here, and relaxing it regressed champion__vs__arbalester x6 " +
        "from 1-2 gated mismatches to 6-10",
    );
});

test("an honest pursuit of a fleeing onager closes instead of blacklisting", () => {
    const sim = simStub(1);
    const chaser = new BattleUnit(
        "1-0", 1, pursuitStats("Champion", CHAMPION_SPEED), "champion", "Chinese", sim);
    const onager = new BattleUnit(
        "2-0", 2, pursuitStats("Siege Onager", ONAGER_SPEED), "siege_onager", "Aztecs", sim);
    sim.team1.push(chaser);
    sim.team2.push(onager);

    chaser.x = 0; chaser.y = 0;
    onager.x = 200; onager.y = 0;
    chaser.target = onager;
    chaser.lastDistToTarget = chaser.distanceTo(onager);
    // The target is actively running away -- the state the relaxation keys on.
    onager.state = "kiting";

    const dt = 1 / 60;
    const startDist = chaser.distanceTo(onager);
    for (let i = 0; i < 120; i++) {
        // The onager flees along +x at its own speed; the champion pursues.
        onager.x += onager.moveSpeed * dt;
        chaser.moveTowardTarget(dt, [chaser, onager]);
        if (!chaser.target) break;
    }

    assert.ok(chaser.target, "the chaser must NOT have blacklisted its target");
    assert.equal(chaser.stuckTimer, 0, "and must never have accumulated stuck time");
    assert.ok(
        chaser.distanceTo(onager) < startDist,
        "an honest pursuit must actually close the gap",
    );
});

test("a chase that makes no progress at all still blacklists", () => {
    const sim = simStub(1);
    const chaser = new BattleUnit(
        "1-0", 1, pursuitStats("Champion", CHAMPION_SPEED), "champion", "Chinese", sim);
    // The kiter is flagged RANGED here, unlike the other fixtures in this file:
    // a fleeing Siege Onager is a ranged unit, and E14's melee target lock is
    // scoped to melee-vs-MELEE precisely so that it cannot touch a pursuit. A
    // melee-flagged "kiter" would now (correctly) be locked on and never
    // blacklisted, which would test the opposite of what this test is about.
    const kiter = new BattleUnit(
        "2-0", 2,
        { ...pursuitStats("Siege Onager", ONAGER_SPEED), attack_range: 9, is_ranged: true },
        "siege_onager", "Aztecs", sim);
    sim.team1.push(chaser);
    sim.team2.push(kiter);

    chaser.x = 0; chaser.y = 0;
    kiter.x = 200; kiter.y = 0;
    chaser.target = kiter;
    chaser.lastDistToTarget = chaser.distanceTo(kiter);
    kiter.state = "kiting";

    const dt = 1 / 60;
    for (let i = 0; i < 120 && chaser.target; i++) {
        // Wedged: the chaser is pinned, so the gap never shrinks.
        const before = { x: chaser.x, y: chaser.y };
        chaser.moveTowardTarget(dt, [chaser, kiter]);
        chaser.x = before.x;
        chaser.y = before.y;
    }

    assert.equal(
        chaser.target,
        null,
        "a genuinely blocked unit must still blacklist and re-target -- the " +
        "relaxed bar lowers the threshold, it never removes it",
    );
});
