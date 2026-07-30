// Group-kite steering (calibration experiment E5a).
//
// BattleUnit.kiteSteering() adds a tangential (orbit) + cohesion vector to the
// radial flee in moveAwayFromTarget, but ONLY for a side that passes a gate.
// The gate is the whole safety story: every fight it rejects must stay
// BIT-IDENTICAL to the pre-E5a engine, which is why kiteSteering returns null
// (skip the vector add entirely) rather than a zero vector.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    PURSUIT_MIN_ADVANTAGE,
    KITE_TANGENTIAL_WEIGHT,
    KITE_COHESION_WEIGHT,
} from "../../../apps/website/static/js/engine/constants.js";
import {
    BattleUnit,
    medianLiving,
} from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

// speed is in tiles/s (the stat-dict unit); range in tiles; minRange in tiles.
function stats(name, { speed = 1.0, range = 0, minRange = 0 } = {}) {
    return {
        hp: 70, attack: 10, attack_range: range, attack_speed: 0.5,
        movement_speed: speed, melee_armor: 0, pierce_armor: 0,
        outline_size: 0.2, accuracy: 100, unit_name: name,
        min_attack_range: minRange,
    };
}

let nextId = 0;
function mk(sim, team, opts, x, y) {
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, stats(opts.name || "U", opts),
        opts.slug || "u", "Chinese", sim,
    );
    u.x = x;
    u.y = y;
    return u;
}

// A canonical scene: `n` ranged units on team 1 in a row on the left, `m` melee
// units on team 2 in a row on the right.
function scene({ n = 3, m = 3, ranged = {}, melee = {} } = {}) {
    const sim = simStub(1);
    const t1 = [];
    const t2 = [];
    for (let i = 0; i < n; i++) t1.push(mk(sim, 1, { name: "R", ...ranged }, 200, 200 + i * 40));
    for (let i = 0; i < m; i++) t2.push(mk(sim, 2, { name: "M", ...melee }, 500, 200 + i * 40));
    sim.team1 = t1;
    sim.team2 = t2;
    return { sim, t1, t2, all: [...t1, ...t2] };
}

// ---- medianLiving ---------------------------------------------------------

test("medianLiving skips the dead, honours the team filter, and averages an even count", () => {
    const { t1, t2, all } = scene({
        n: 4, m: 2,
        ranged: { range: 8, speed: 1.0 },
        melee: { range: 0, speed: 1.0 },
    });
    const range = (u) => u.rawAttackRange;
    assert.equal(medianLiving(all, 1, range), 8, "all four archers alive");
    assert.equal(medianLiving(all, 2, range), 0, "melee side has no range");

    // Even count -> mean of the two middles.
    t1[0].rawAttackRange = 4;
    t1[1].rawAttackRange = 4;
    t1[2].rawAttackRange = 10;
    t1[3].rawAttackRange = 10;
    assert.equal(medianLiving(all, 1, range), 7);

    // Odd count after a death -> the true middle, and the corpse is ignored.
    t1[0].state = "dead";
    assert.equal(medianLiving(all, 1, range), 10);

    // Nobody left -> null, never NaN (kiteSteering keys its bail-out off this).
    for (const u of t2) u.state = "dead";
    assert.equal(medianLiving(all, 2, range), null);
});

// ---- the gate -------------------------------------------------------------
// Each of these four rejections is a family of corpus fights that MUST stay
// byte-identical to baseline.

test("melee-vs-melee never steers (0 > 0 is false)", () => {
    const { t1, t2, all } = scene({ ranged: { range: 0 }, melee: { range: 0 } });
    assert.equal(t1[0].kiteSteering(all, t2), null);
    assert.equal(t2[0].kiteSteering(all, t1), null);
});

test("equal ranges never steer -- the gate is STRICTLY out-ranging", () => {
    const { t1, t2, all } = scene({
        ranged: { range: 8, speed: 1.6 },
        melee: { range: 8, speed: 1.0 },
    });
    assert.equal(t1[0].kiteSteering(all, t2), null);
});

test("the out-ranged side never steers, even when it is much faster", () => {
    const { t1, t2, all } = scene({
        ranged: { range: 8, speed: 0.5 },
        melee: { range: 4, speed: 3.0 },
    });
    assert.equal(
        t2[0].kiteSteering(all, t1), null,
        "range 4 does not out-range range 8, so the fast side gets no orbit",
    );
});

test("a siege weapon (min-range dead zone) never steers, however far it out-ranges", () => {
    const { t1, t2, all } = scene({
        ranged: { range: 9, speed: 2.0, minRange: 3 },   // Siege Onager shape
        melee: { range: 0, speed: 1.0 },
    });
    assert.ok(t1[0].minAttackRange > 0, "precondition: the unit has a dead zone");
    assert.equal(
        t1[0].kiteSteering(all, t2), null,
        "siege owns a competing tooClose() reposition path and never runs the " +
        "tape's kite circuit -- this clause is what keeps every siege-attacker " +
        "fight bit-identical",
    );
});

test("a kiter with no speed margin never steers (the foot-archer canaries)", () => {
    // Arbalester 0.96 t/s fleeing a Champion 1.06 t/s: the kiter is SLOWER.
    const { t1, t2, all } = scene({
        ranged: { range: 8, speed: 0.96 },
        melee: { range: 0, speed: 1.06 },
    });
    assert.equal(
        t1[0].kiteSteering(all, t2), null,
        "circling costs radial recession, so it is only affordable with speed " +
        "to spare; ungated it broke champion__vs__arbalester and " +
        "champion__vs__hand_cannoneer, which baseline already got right",
    );
});

test("the speed-margin ramp is continuous and saturates at PURSUIT_MIN_ADVANTAGE", () => {
    // Margin exactly at the threshold -> full weight.
    const at = scene({
        ranged: { range: 8, speed: 1.0 + PURSUIT_MIN_ADVANTAGE / TILE_SIZE },
        melee: { range: 0, speed: 1.0 },
    });
    // Half the threshold -> half weight.
    const half = scene({
        ranged: { range: 8, speed: 1.0 + PURSUIT_MIN_ADVANTAGE / TILE_SIZE / 2 },
        melee: { range: 0, speed: 1.0 },
    });
    const sAt = at.t1[0].kiteSteering(at.all, at.t2);
    const sHalf = half.t1[0].kiteSteering(half.all, half.t2);
    assert.ok(sAt && sHalf, "both sides out-range and have a positive margin");

    // Same geometry in both scenes, so the cohesion part is identical and the
    // difference is purely the scaled orbit term.
    const orbitAt = { x: sAt.x - sHalf.x, y: sAt.y - sHalf.y };
    assert.ok(
        Math.hypot(orbitAt.x, orbitAt.y) > 1e-9,
        "halving the margin must actually halve the orbit, not be a no-op",
    );

    // A vanishing margin returns null rather than a zero vector, so the caller
    // skips the add and the fight stays bit-identical.
    const none = scene({
        ranged: { range: 8, speed: 1.0 },
        melee: { range: 0, speed: 1.0 },
    });
    assert.equal(none.t1[0].kiteSteering(none.all, none.t2), null);
});

// ---- the steering vector itself -------------------------------------------

test("the orbit sense is CLOCKWISE and identical for every unit on the side", () => {
    // Ranged ring around a single enemy at the centre, so each unit sits on a
    // different bearing from the enemy centroid.
    const sim = simStub(1);
    const foe = mk(sim, 2, { range: 0, speed: 1.0 }, 450, 300);
    const ring = [];
    for (let i = 0; i < 8; i++) {
        const a = (i * Math.PI) / 4;
        ring.push(mk(sim, 1, { range: 8, speed: 2.0 },
            450 + 120 * Math.cos(a), 300 + 120 * Math.sin(a)));
    }
    sim.team1 = ring;
    sim.team2 = [foe];
    const all = [...ring, foe];

    for (const u of ring) {
        const s = u.kiteSteering(all, [foe]);
        assert.ok(s, "every ring unit is in kite mode");
        // Radial (enemy centroid -> unit) and the pure orbit component.
        const rx = u.x - foe.x, ry = u.y - foe.y;
        const rlen = Math.hypot(rx, ry);
        // Strip cohesion: it points at the ring's own centroid, which is the
        // enemy's position here, i.e. exactly -radial.
        const coh = KITE_COHESION_WEIGHT * Math.min(1, rlen / (2 * TILE_SIZE));
        const ox = s.x + (coh * rx) / rlen;
        const oy = s.y + (coh * ry) / rlen;
        // Screen coords are y-down, so a clockwise turn is (x, y) -> (-y, x);
        // the cross product radial x orbit must be POSITIVE for every unit.
        const cross = rx * oy - ry * ox;
        assert.ok(
            cross > 0,
            `unit at bearing ${Math.atan2(ry, rx).toFixed(2)} must orbit clockwise`,
        );
        // And the orbit is perpendicular to the radial, at full weight.
        assert.ok(Math.abs(rx * ox + ry * oy) < 1e-9, "orbit is perpendicular to radial");
        assert.ok(
            Math.abs(Math.hypot(ox, oy) - KITE_TANGENTIAL_WEIGHT) < 1e-9,
            "margin is far above the ramp, so the orbit runs at full weight",
        );
    }
});

test("cohesion pulls toward the side's own living centroid and ramps to zero at it", () => {
    const { sim, t1, t2, all } = scene({
        n: 3, ranged: { range: 8, speed: 2.0 }, melee: { range: 0, speed: 1.0 },
    });
    void sim;
    // t1 sits at x=200, y=200/240/280 -> centroid (200, 240). The middle unit
    // IS the centroid, so its cohesion term must vanish.
    const mid = t1[1].kiteSteering(all, t2);
    const rx = t1[1].x - t2.reduce((s, u) => s + u.x, 0) / t2.length;
    const ry = t1[1].y - t2.reduce((s, u) => s + u.y, 0) / t2.length;
    const rlen = Math.hypot(rx, ry);
    assert.ok(
        Math.abs(Math.hypot(mid.x, mid.y) - KITE_TANGENTIAL_WEIGHT) < 1e-9,
        "a unit sitting on its own centroid gets orbit only, no cohesion kick",
    );
    assert.ok(Math.abs(rx * mid.x + ry * mid.y) / rlen < 1e-9);

    // Move the top unit well off the formation, then isolate its cohesion
    // component by subtracting the analytically-known orbit (the margin here is
    // far above the ramp, so the orbit is exactly KITE_TANGENTIAL_WEIGHT times
    // the clockwise perpendicular of the radial).
    t1[0].y = t1[1].y - TILE_SIZE * 3;
    const cy = t1.reduce((u2, u) => u2 + u.y, 0) / t1.length;
    const cx = t1.reduce((u2, u) => u2 + u.x, 0) / t1.length;
    const ex = t2.reduce((s, u) => s + u.x, 0) / t2.length;
    const ey = t2.reduce((s, u) => s + u.y, 0) / t2.length;
    const s0 = t1[0].kiteSteering(all, t2);
    const dx = t1[0].x - ex, dy = t1[0].y - ey;
    const dlen = Math.hypot(dx, dy);
    const cohOnly = {
        x: s0.x - KITE_TANGENTIAL_WEIGHT * (-dy / dlen),
        y: s0.y - KITE_TANGENTIAL_WEIGHT * (dx / dlen),
    };
    const toCentroid = { x: cx - t1[0].x, y: cy - t1[0].y };
    const tlen = Math.hypot(toCentroid.x, toCentroid.y);
    const clen = Math.hypot(cohOnly.x, cohOnly.y);
    assert.ok(
        (cohOnly.x * toCentroid.x + cohOnly.y * toCentroid.y) / (clen * tlen) > 1 - 1e-9,
        "the cohesion component must point from the unit straight at the centroid",
    );
    // 3 tiles out is past the 2-tile ramp, so it runs at full cohesion weight.
    assert.ok(Math.abs(clen - KITE_COHESION_WEIGHT) < 1e-9);
});

test("kiteSteering is pure and deterministic -- same scene, same vector, no mutation", () => {
    const { t1, t2, all } = scene({
        n: 5, m: 4, ranged: { range: 8, speed: 2.0 }, melee: { range: 0, speed: 1.0 },
    });
    const before = all.map((u) => `${u.x},${u.y},${u.vx},${u.vy},${u.state}`);
    const a = t1[2].kiteSteering(all, t2);
    const b = t1[2].kiteSteering(all, t2);
    assert.deepEqual(a, b, "no RNG, no clock, no accumulator: repeatable");
    assert.deepEqual(
        all.map((u) => `${u.x},${u.y},${u.vx},${u.vy},${u.state}`), before,
        "kiteSteering must not mutate any unit -- it only reads the scene",
    );
    // Argument order must not matter: the enemy list is summed in a fixed order
    // but the RESULT must not depend on how the caller ordered it.
    const rev = t1[2].kiteSteering(all, [...t2].reverse());
    assert.ok(Math.abs(rev.x - a.x) < 1e-12 && Math.abs(rev.y - a.y) < 1e-12);
});

test("moveAwayFromTarget without steering is bit-identical to the pre-E5a path", () => {
    // The bit-identity guarantee for every gated-out fight: passing null (or
    // omitting the argument) must leave the arithmetic untouched.
    function run(withArg) {
        const { t1, t2 } = scene({
            n: 3, m: 3, ranged: { range: 8, speed: 0.96 }, melee: { range: 0, speed: 1.06 },
        });
        const all = [...t1, ...t2];
        const u = t1[1];
        u.target = t2[1];
        for (let i = 0; i < 30; i++) {
            if (withArg) u.moveAwayFromTarget(1 / 60, all, null);
            else u.moveAwayFromTarget(1 / 60, all);
        }
        return [u.x, u.y, u.vx, u.vy];
    }
    assert.deepEqual(run(true), run(false));
});

test("steering actually deflects the flee path off pure-radial", () => {
    const { t1, t2, all } = scene({
        n: 3, m: 3, ranged: { range: 8, speed: 2.0 }, melee: { range: 0, speed: 1.0 },
    });
    const u = t1[1];
    u.target = t2[1];
    const x0 = u.x, y0 = u.y;
    const steering = u.kiteSteering(all, t2);
    assert.ok(steering, "precondition: this side is in kite mode");
    for (let i = 0; i < 30; i++) {
        u.moveAwayFromTarget(1 / 60, all, u.kiteSteering(all, t2));
    }
    const movedY = Math.abs(u.y - y0);
    assert.ok(
        movedY > 1,
        "a purely radial flee from a target on the same horizontal would keep " +
        "y fixed; the orbit term must move it off that line",
    );
    assert.ok(u.x < x0, "and it is still, on net, retreating");
});
