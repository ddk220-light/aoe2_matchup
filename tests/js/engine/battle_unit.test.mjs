import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit, setArmorClassNames } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import {
    FIRE_CYCLE_QUANTUM,
    RANGED_STOP_OVERHEAD,
    RANGED_POST_FIRE_RECOVERY,
    RANGED_POST_FIRE_RECOVERY_BY_SLUG,
} from "../../../apps/website/static/js/engine/constants.js";

const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 90, unit_name: "Test Archer",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

test("derived stats match the legacy formulas", () => {
    const u = new BattleUnit("1-0", 1, STATS, "test", "Franks", simStub());
    assert.equal(u.attackRange, 5 * 30 + 5);      // tiles*TILE_SIZE + MELEE_RANGE_BUFFER
    assert.equal(u.radius, 14);                   // round(10 + 0.2*20)
    assert.equal(u.reloadTime, 2.0);              // 1/attack_speed
    assert.equal(u.moveSpeed, 0.96 * 30);
    assert.equal(u.accuracy, 0.9);
    assert.equal(u.state, "idle");
});

test("fireProjectile pushes into this.sim.projectiles and draws from sim.rng", () => {
    const sim = simStub(3);
    const a = new BattleUnit("1-0", 1, STATS, "a", "Franks", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 100 }, "b", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 60; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    const before = sim.rng.getState();
    a.fireProjectile(b);
    assert.equal(sim.projectiles.length, 1);
    assert.notEqual(sim.rng.getState(), before); // accuracy 0.9 < 1 must roll
});

test("setArmorClassNames feeds the damage-breakdown labels", () => {
    setArmorClassNames({ 4: "Base Melee" });
    // No assertion beyond not throwing: labels are display-only.
});

// ---- swing cycle -------------------------------------------------------------
// The attack_delay is a WINDUP INSIDE the reload period, not an extra cost on top
// of it: real AoE2 (and the calibration tapes) show hit-to-hit == reload_time
// flat, with the delay paid exactly once when the unit first engages. Before the
// fix the engine charged it every swing (melee: delay + reload; ranged: reload +
// delay + the wasMoving round trip), which is what these two tests pin shut.
const DT = 1 / 60;

// Ticks a single unit (only `a` moves/attacks; `b` is an inert punching bag) and
// returns the battle-times at which `a` landed an attack, detected by the caller's
// probe. Deliberately drives update() directly, so no other unit's behavior can
// perturb the cycle being measured.
function attackTimes(a, b, probe, steps) {
    const times = [];
    let t = 0;
    let prev = probe();
    for (let i = 0; i < steps; i++) {
        a.update(DT, [a, b], [b]);
        t += DT;
        const now = probe();
        if (now !== prev) {
            times.push(t);
            prev = now;
        }
    }
    return times;
}

test("ranged steady-state (stood still): shot-to-shot == reloadTime, delay paid once up front", () => {
    const sim = simStub(7);
    // attack_speed 0.5 -> reload 2.0s; 0.5s windup. The target is RANGED so the
    // attacker has nothing to kite from and stands still for the whole test --
    // the STOOD-STILL regime, which the tapes put at a bare reload_time (E9:
    // arbalester 1.718 on reload 1.7, hand_cannoneer 3.468 on 3.45, over 2,073
    // stood-still cycles). Reload 2.0 also sits exactly on the 2/3 s fire-cycle
    // quantum, so the quantised regime would be 2.0 here too -- the moving case
    // is pinned separately below, where the two regimes actually differ.
    const shooter = { ...STATS, attack_speed: 0.5, attack_delay: 0.5 };
    const a = new BattleUnit("1-0", 1, shooter, "a", "Franks", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 100000 }, "b", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 60; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const times = attackTimes(a, b, () => sim.projectiles.length, 60 * 8);
    assert.ok(times.length >= 4, `expected >=4 shots, got ${times.length}`);
    // The OPENING shot pays the windup once, plus the stop/turn overhead: a
    // unit starts life having walked into range (movedSinceShot starts true),
    // which is exactly the "had to halt to shoot" case. (+ the tick that
    // commits the windup and the tick that resolves it.)
    assert.ok(
        Math.abs(times[0] - (a.attackDelay + RANGED_STOP_OVERHEAD)) <= DT * 2.5,
        `first shot at ${times[0]}, expected ~${a.attackDelay + RANGED_STOP_OVERHEAD}`,
    );
    // Every later shot is one flat reload apart -- NOT reload + delay. The
    // only slack allowed is tick quantization (the tick that commits the
    // windup plus float residue on the two countdowns): <= 2 ticks, never the
    // 0.5s the pre-fix engine added.
    for (let i = 1; i < times.length; i++) {
        const gap = times[i] - times[i - 1];
        assert.ok(
            Math.abs(gap - a.reloadTime) <= DT * 2.5,
            `shot ${i} gap ${gap}, expected ~${a.reloadTime}`,
        );
        assert.ok(gap < a.reloadTime + a.attackDelay / 2, "delay re-paid per shot");
    }
});

test("melee steady-state: hit-to-hit == reloadTime, delay paid once up front", () => {
    const sim = simStub(11);
    // attack_range 0 -> melee; 2.0s reload with a 0.5s windup.
    const swinger = {
        ...STATS, attack_range: 0, attack_speed: 0.5, attack_delay: 0.5,
    };
    const a = new BattleUnit("1-0", 1, swinger, "a", "Franks", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 100000 }, "b", "Goths", sim);
    // 30px apart: inside attackRange(5) + both radii(14+14) = 33.
    a.x = 0; a.y = 0; b.x = 30; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    assert.ok(!a.isRanged());

    const times = attackTimes(a, b, () => b.currentHp, 60 * 8);
    assert.ok(times.length >= 4, `expected >=4 hits, got ${times.length}`);
    assert.ok(
        Math.abs(times[0] - a.attackDelay) <= DT * 2.5,
        `first hit at ${times[0]}, expected ~${a.attackDelay}`,
    );
    for (let i = 1; i < times.length; i++) {
        const gap = times[i] - times[i - 1];
        assert.ok(
            Math.abs(gap - a.reloadTime) <= DT * 2.5,
            `hit ${i} gap ${gap}, expected ~${a.reloadTime}`,
        );
        assert.ok(gap < a.reloadTime + a.attackDelay / 2, "delay re-paid per swing");
    }
});

// ---- absorption is UNIVERSAL, not per-unit (experiment E1b, 2026-07-30) -------
//
// E1b hypothesised that some units -- gunpowder and/or big-windup archers --
// do NOT absorb the windup, so their cycle would be reload + attack_delay (the
// pre-E1 behaviour). The 105-fight tape corpus falsifies that outright.
//
// The argument is a bound, not a correlation. Engagement overhead (kiting,
// chasing, re-acquiring) can only ever ADD to an observed swing interval, never
// subtract. So a unit's LOWEST tape swing_interval_median across every context
// it was recorded in is a hard UPPER BOUND on its true attack cycle. For all
// eleven corpus units with attack_delay > 0 that bound lands on reload_time
// + 0.012..0.029s (uniform tape quantisation) and strictly BELOW reload +
// delay -- which mathematically excludes the additive model for every one of
// them, including the two E1b singled out:
//
//   unit               reload  delay   reload+delay   min tape median (context)
//   arbalester          1.700  0.333      2.033        1.722  vs heavy_scorpion
//   hand_cannoneer      3.450  0.250      3.700        3.466  vs imp_elite_skirm
//   heavy_cav_archer    1.800  0.767      2.567        1.829  vs imp_elite_skirm
//   imp_elite_skirm     3.000  0.317      3.317        3.022  vs heavy_scorpion
//   heavy_camel         2.000  0.333      2.333        2.012  vs elite_fire_lancer
//   paladin             1.900  0.217      2.117        1.914  vs elite_fire_lancer
//
// The elevated 1.99 / 4.00 medians that motivated E1b come only from fights
// where the shooter OUT-RANGES its target and kites; that residual is an
// engagement cost (it is largest for the SLOWEST shooter and smallest for the
// one with the BIGGEST windup, the exact opposite of a frame-delay signature).
// It belongs to the engagement round, not to attack scheduling.
//
// E9 (2026-07-30) identified that engagement cost exactly: splitting all 21,296
// tape gaps by whether the shooter MOVED during the cycle shows the elevated
// medians are the moving half quantised onto a 2/3 s grid, and the tape
// ceilings tabulated below are the standing half. So these cases are now
// specifically the STOOD-STILL regime -- which is why they use a ranged
// punching bag the attacker never kites from. The moving regime is pinned by
// the stand-and-shoot tests further down.
//
// These cases pin the falsification shut: real corpus stats, both classes,
// asserting the cycle sits on reload AND under the tape's empirical ceiling.
const CORPUS_CYCLE_CASES = [
    // slug,             reload, delay, ranged, min tape swing_interval_median
    ["arbalester",         1.7,   0.333, true,  1.722],
    ["hand_cannoneer",     3.45,  0.25,  true,  3.466],
    ["heavy_cav_archer",   1.8,   0.767, true,  1.829],
    ["imp_elite_skirm",    3.0,   0.317, true,  3.022],
    ["heavy_camel",        2.0,   0.333, false, 2.012],
    ["paladin",            1.9,   0.217, false, 1.914],
];

for (const [slug, reload, delay, ranged, tapeCeiling] of CORPUS_CYCLE_CASES) {
    test(`corpus steady-state: ${slug} cycle == reload (${reload}s), not reload+delay`, () => {
        const sim = simStub(23);
        const stats = {
            ...STATS,
            attack_speed: 1 / reload,
            attack_delay: delay,
            attack_range: ranged ? 7 : 0,
        };
        const a = new BattleUnit("1-0", 1, stats, slug, "Franks", sim);
        // Ranged punching bag: the attacker has nothing to kite away from, so
        // this measures the bare attack cycle with zero engagement overhead --
        // the same condition the un-micro'd tape fights were selected for.
        const b = new BattleUnit("2-0", 2, { ...STATS, hp: 1e9 }, "b", "Goths", sim);
        a.x = 0; a.y = 0; b.x = 60; b.y = 0;
        sim.team1.push(a); sim.team2.push(b);
        assert.equal(a.isRanged(), ranged);

        const probe = ranged ? () => sim.projectiles.length : () => b.currentHp;
        // Long enough for >= 4 gaps even at the hand cannoneer's 3.45s reload.
        const times = attackTimes(a, b, probe, Math.ceil(60 * (reload * 6 + 2)));
        assert.ok(times.length >= 5, `${slug}: expected >=5 attacks, got ${times.length}`);

        for (let i = 1; i < times.length; i++) {
            const gap = times[i] - times[i - 1];
            assert.ok(
                Math.abs(gap - reload) <= DT * 2.5,
                `${slug}: gap ${i} was ${gap}, expected ~${reload}`,
            );
            // The load-bearing assertion: under the tape's own ceiling, which
            // sits below reload + delay. An additive-windup regression fails
            // here even if someone widens the tolerance above.
            assert.ok(
                gap <= tapeCeiling + DT * 2.5,
                `${slug}: gap ${i} was ${gap}, above the tape ceiling ${tapeCeiling}`,
            );
            assert.ok(
                gap < reload + delay - 1e-9,
                `${slug}: gap ${i} was ${gap} -- additive windup (${reload + delay}s) is back`,
            );
        }
    });
}

// ---- ranged stand-and-shoot cost (experiment E9, 2026-07-30) -----------------
//
// Measured over all 140 tapes / 21,296 missile-launch gaps. The law, and the
// per-unit numbers behind these constants, are documented in constants.js. What
// these tests pin:
//   1. the quantised cadence a MOVING shooter pays (vs. the bare reload a
//      standing one pays, already covered by CORPUS_CYCLE_CASES above);
//   2. that a reload already sitting on the grid is not bumped a whole slot;
//   3. that the post-fire recovery really immobilises the unit;
//   4. that the recovery runs CONCURRENTLY with the reload (additive cadence
//      was falsified by the tape -- see constants.js);
//   5. that the melee path is untouched.

test("fireCycleLength: quantised up to the 2/3 s grid, on-grid reloads unchanged", () => {
    const sim = simStub(31);
    // [reload, expected cycle] -- the four mobile corpus shooters plus the two
    // siege reloads, whose expectations are the tape's own moving medians
    // (2.000 / 2.008 / 3.998 / 3.334 / 4.020 / 6.028).
    const cases = [
        [1.7, 2.0],            // arbalester
        [1.8, 2.0],            // heavy_cav_archer
        [3.45, 4.0],           // hand_cannoneer
        [3.0, 10 / 3],         // imp_elite_skirm -- the case that falsifies a
                               // 1.0 s quantum, which would predict 3.0 flat
        [3.6, 4.0],            // heavy_scorpion
        [6.0, 6.0],            // siege_onager -- EXACTLY 9 quanta, must not be
                               // bumped to 6.667 by float residue
        [2 / 3, 2 / 3],        // one bare quantum, on-grid
    ];
    for (const [reload, expected] of cases) {
        const u = new BattleUnit(
            "1-0", 1, { ...STATS, attack_speed: 1 / reload, attack_range: 7 },
            "u", "Franks", sim,
        );
        assert.ok(
            Math.abs(u.fireCycleLength() - expected) < 1e-9,
            `reload ${reload}: got ${u.fireCycleLength()}, expected ${expected}`,
        );
        // Never shortens a cycle, and never adds a whole slot more than needed.
        assert.ok(u.fireCycleLength() >= reload - 1e-9);
        assert.ok(u.fireCycleLength() < reload + FIRE_CYCLE_QUANTUM);
    }
});

// slug, reload, delay, quantised cycle == the unit's own tape moving median.
const MOVING_CYCLE_CASES = [
    ["arbalester", 1.7, 0.333, 2.0],       // tape moving median 2.000
    ["hand_cannoneer", 3.45, 0.25, 4.0],   // tape moving median 3.998
    ["imp_elite_skirm", 3.0, 0.317, 10 / 3], // tape moving median 3.334
];

for (const [slug, reload, delay, cycle] of MOVING_CYCLE_CASES) {
    test(`moving shooter: ${slug} launch-to-launch == ${cycle.toFixed(3)}s, not reload`, () => {
        const sim = simStub(13);
        // Ranged punching bag so the position stays put and the ONLY thing under
        // test is the cadence arithmetic; markRangedMovement() stands in for
        // "this unit kited this cycle", which is what the tape's moving half
        // measures.
        const a = new BattleUnit(
            "1-0", 1,
            { ...STATS, attack_speed: 1 / reload, attack_delay: delay, attack_range: 7 },
            slug, "Chinese", sim,
        );
        const b = new BattleUnit("2-0", 2, { ...STATS, hp: 1e9, attack_range: 7 }, "b", "Goths", sim);
        a.x = 0; a.y = 0; b.x = 60; b.y = 0;
        sim.team1.push(a); sim.team2.push(b);

        const times = [];
        let prev = 0, t = 0;
        for (let i = 0; i < Math.ceil(60 * (cycle * 6 + 2)); i++) {
            a.update(DT, [a, b], [b]);
            t += DT;
            if (sim.projectiles.length !== prev) {
                times.push(t);
                prev = sim.projectiles.length;
                a.markRangedMovement();  // "it kited during this cycle"
            }
        }
        assert.ok(times.length >= 5, `${slug}: expected >=5 shots, got ${times.length}`);
        assert.ok(Math.abs(a.fireCycleLength() - cycle) < 1e-9);

        const additive = reload + a.postFireRecovery;
        // Only meaningful where the two candidate models actually separate:
        // for the arbalester 1.7 + 0.33 == 2.03 sits inside a couple of ticks of
        // the quantised 2.0, which is precisely why the tape needed the hand
        // cannoneer (3.78 vs 4.00) to discriminate them at all.
        const separable = Math.abs(cycle - additive) > DT * 5;
        for (let i = 1; i < times.length; i++) {
            const gap = times[i] - times[i - 1];
            assert.ok(
                Math.abs(gap - cycle) <= DT * 2.5,
                `${slug}: gap ${i} was ${gap}, expected the quantised ${cycle}`,
            );
            assert.ok(
                gap > reload + DT * 2.5,
                `${slug}: gap ${i} was ${gap} -- moving shooter fired at bare reload`,
            );
            if (separable) {
                assert.ok(
                    Math.abs(gap - additive) > DT * 2.5,
                    `${slug}: gap ${i} == reload + recovery -- additive cadence is back`,
                );
            }
        }
    });
}

test("post-fire recovery immobilises the shooter, then releases it", () => {
    const sim = simStub(17);
    // MELEE bag -> shouldKite is true, so the shooter wants to move the instant
    // it is allowed to. Anything it does move is therefore the recovery ending.
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_speed: 1 / 1.7, attack_delay: 0.333, attack_range: 7 },
        "arbalester", "Chinese", sim,
    );
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e9, attack_range: 0 }, "b", "Goths", sim,
    );
    a.x = 0; a.y = 0; b.x = 60; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    assert.equal(a.postFireRecovery, RANGED_POST_FIRE_RECOVERY);

    let t = 0, shotT = null, shotX = null, frozenUntil = null, movedAt = null;
    for (let i = 0; i < 60 * 4; i++) {
        const before = sim.projectiles.length;
        a.update(DT, [a, b], [b]);
        t += DT;
        if (shotT === null && sim.projectiles.length !== before) {
            shotT = t; shotX = a.x;
        } else if (shotT !== null && movedAt === null) {
            if (Math.abs(a.x - shotX) > 1e-9) movedAt = t;
            else frozenUntil = t;
        }
    }
    assert.ok(shotT !== null, "no shot fired");
    assert.ok(movedAt !== null, "shooter never resumed moving after the shot");
    const frozen = movedAt - shotT;
    assert.ok(
        Math.abs(frozen - a.postFireRecovery) <= DT * 2.5,
        `frozen for ${frozen}s after the shot, expected ~${a.postFireRecovery}`,
    );
    assert.ok(frozenUntil !== null && frozenUntil < movedAt);
});

test("post-fire recovery honours the per-slug tape overrides", () => {
    const sim = simStub(19);
    const mk = (slug) =>
        new BattleUnit("1-0", 1, { ...STATS, attack_range: 7 }, slug, "Franks", sim);
    // The two units whose tape recovery differs from the shared default by more
    // than the 0.05 s sampling resolution (see constants.js).
    assert.equal(mk("heavy_cav_archer").postFireRecovery, 0.43);
    assert.equal(mk("imp_elite_skirm").postFireRecovery, 0.20);
    // Everything else, corpus or not, takes the shared value.
    for (const slug of ["arbalester", "hand_cannoneer", "siege_onager", "made_up_unit"]) {
        assert.equal(mk(slug).postFireRecovery, RANGED_POST_FIRE_RECOVERY);
    }
    for (const [slug, v] of RANGED_POST_FIRE_RECOVERY_BY_SLUG) {
        assert.equal(mk(slug).postFireRecovery, v);
    }
});

test("melee path pays no stand-and-shoot cost", () => {
    const sim = simStub(23);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 0, attack_speed: 0.5, attack_delay: 0.5 },
        "champion", "Chinese", sim,
    );
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 1e9, attack_range: 0 }, "b", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 30; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    assert.ok(!a.isRanged());

    const times = attackTimes(a, b, () => b.currentHp, 60 * 8);
    assert.ok(times.length >= 4);
    // First swing at the bare attack_delay -- no stop/turn overhead -- and the
    // recovery timer is never armed for a melee unit.
    assert.ok(
        Math.abs(times[0] - a.attackDelay) <= DT * 2.5,
        `first melee hit at ${times[0]}, expected ~${a.attackDelay} (no ranged overhead)`,
    );
    assert.equal(a.fireRecovery, 0);
    for (let i = 1; i < times.length; i++) {
        assert.ok(Math.abs(times[i] - times[i - 1] - a.reloadTime) <= DT * 2.5);
    }
});
