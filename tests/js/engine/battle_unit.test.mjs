import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit, setArmorClassNames } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

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

test("ranged steady-state: shot-to-shot == reloadTime, delay paid once up front", () => {
    const sim = simStub(7);
    // attack_speed 0.5 -> reload 2.0s; 0.5s windup. The target is RANGED so the
    // attacker has nothing to kite from and stands still for the whole test.
    const shooter = { ...STATS, attack_speed: 0.5, attack_delay: 0.5 };
    const a = new BattleUnit("1-0", 1, shooter, "a", "Franks", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 100000 }, "b", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 60; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const times = attackTimes(a, b, () => sim.projectiles.length, 60 * 8);
    assert.ok(times.length >= 4, `expected >=4 shots, got ${times.length}`);
    // First shot pays the windup exactly once (+ the tick that commits it and
    // the tick that resolves it -- 2 ticks of tick-quantization, no more).
    assert.ok(
        Math.abs(times[0] - a.attackDelay) <= DT * 2.5,
        `first shot at ${times[0]}, expected ~${a.attackDelay}`,
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
