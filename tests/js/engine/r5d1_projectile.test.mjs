// Round 5d-1 -- the projectile/aim corrections: P1 reduced-damage displaced
// hits and P2 the trailing-window ballistic lead, plus their off-switch.
//
// Everything here pins a RULE or a measured value. The only numbers quoted are
// ones the tape produced (13 -> 6.5) or ones the .dat produced (dispersion,
// projectile radius); no test asserts a tuned constant.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import {
    TILE_SIZE,
    PROJECTILE_RADIUS_TILES,
    LEAD_WINDOW_SECONDS,
    R5B,
    setR5B,
    R5D1,
    setR5D1,
} from "../../../apps/website/static/js/engine/constants.js";

const DT = 1 / 60;
const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Archer",
};

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

function withR5D1(overrides, fn) {
    const saved = { ...R5D1 };
    setR5D1(overrides);
    try {
        return fn();
    } finally {
        setR5D1(saved);
    }
}

function withFlags(r5b, r5d1, fn) {
    const savedB = { ...R5B };
    const savedD = { ...R5D1 };
    setR5B(r5b);
    setR5D1(r5d1);
    try {
        return fn();
    } finally {
        setR5B(savedB);
        setR5D1(savedD);
    }
}

/** Fly every live projectile to its arrival. */
function land(sim) {
    for (let i = 0; i < 2000 && sim.projectiles.length; i++) {
        for (const p of sim.projectiles) p.update(DT);
        sim.projectiles = sim.projectiles.filter((p) => !p.done);
    }
}

// A hand cannoneer (dat accuracy 75, dispersion 0.50) whose next roll is
// FORCED to fail, so a single shot can be inspected. Overriding the accuracy
// is not a behaviour change under test -- it is how the test picks the branch.
function forcedMissHC(sim, opts = {}) {
    const a = new BattleUnit(
        "1-0", 1,
        {
            ...STATS, attack: 17, attack_range: 7, projectile_speed: 7.5,
            accuracy: 75, ...opts,
        },
        "hand_cannoneer", "Japanese", sim);
    a.accuracy = 0;      // every roll fails
    return a;
}

// ---- P1: the arithmetic -----------------------------------------------------

test("[P1] a displaced hit applies exactly half the FINAL damage, unrounded", () => withR5D1({ reducedDamageHits: true }, () => {
    // The tape's own case: hand cannoneer attack 17 into pierce armor 4 is a
    // full hit of 13.0 and a reduced hit of 6.5 -- not floor(6.5) = 6, and not
    // half-the-raw-attack-then-armor (8.5 - 4 = 4.5).
    // (P1 ships OFF until the land-rate side closes -- see constants.js; the
    // mechanism itself is pinned here under an explicit override.)
    const sim = simStub(3);
    const a = forcedMissHC(sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0; b.x = 5 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    assert.equal(a.getDamageAgainst(b), 13, "full damage must be 17 - 4");

    // Aim the shot so its displacement cannot clear the body: put the roll's
    // scatter under the body radius by firing repeatedly until one lands on it.
    // Deterministic rng, so this is a fixed sequence, not a retry loop.
    const hp0 = b.currentHp;
    let reduced = 0;
    for (let i = 0; i < 60; i++) {
        const before = b.currentHp;
        a.fireProjectile(b);
        land(sim);
        const dealt = before - b.currentHp;
        if (dealt > 0) {
            assert.equal(dealt, 6.5, `a displaced hit must apply 6.5, got ${dealt}`);
            reduced++;
        }
    }
    assert.ok(reduced > 0, "at least one of 60 forced misses must land on the body");
    assert.equal(
        (hp0 - b.currentHp) % 6.5, 0,
        "every application in this run is a half hit",
    );
}));

test("[P1] the half is computed against the body actually struck", () => withR5D1({ reducedDamageHits: true }, () => {
    // A neighbour with different pierce armor takes half of ITS OWN final
    // damage, not half of the primary's -- "half the final post-armor damage"
    // is a statement about the unit that is hit.
    const sim = simStub(3);
    const a = forcedMissHC(sim);
    const target = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000, pierce_armor: 4 }, "arbalester", "Britons", sim);
    const neighbour = new BattleUnit(
        "2-1", 2, { ...STATS, hp: 1000, pierce_armor: 8 }, "imp_elite_skirm", "Britons", sim);
    a.x = 0; a.y = 0;
    target.x = 5 * TILE_SIZE; target.y = 0;
    // Far enough that the primary can never be the overlapping body.
    neighbour.x = 5 * TILE_SIZE; neighbour.y = 4 * TILE_SIZE;
    sim.team1.push(a); sim.team2.push(target, neighbour);

    assert.equal(a.getDamageAgainst(neighbour), 9, "17 - 8");
    // Fire AT the neighbour so the displaced landing point is near its body.
    let reduced = 0;
    for (let i = 0; i < 60; i++) {
        const before = neighbour.currentHp;
        a.fireProjectile(neighbour);
        land(sim);
        const dealt = before - neighbour.currentHp;
        if (dealt > 0) {
            assert.equal(dealt, 4.5, `expected 9/2, got ${dealt}`);
            reduced++;
        }
    }
    assert.ok(reduced > 0);
    assert.equal(target.currentHp, target.maxHp, "the primary was never near the landing point");
}));

// ---- P1: the geometry -------------------------------------------------------

test("[P1] the INTENDED target is the usual victim -- it is not excluded", () => {
    // R5b's graze branch opened with `if (enemy === target) continue`, which is
    // why it fired zero times in 120 seed-runs: the tape's reduced hit lands on
    // the intended target 26 times out of 27.
    const sim = simStub(9);
    const a = forcedMissHC(sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e6, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0; b.x = 5 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    let hits = 0;
    for (let i = 0; i < 400; i++) {
        const before = b.currentHp;
        a.fireProjectile(b);
        land(sim);
        if (b.currentHp < before) hits++;
    }
    // A uniform displacement in [0, 0.5] tiles clears a 0.2 + 0.1 = 0.3 tile
    // body roughly 40% of the time, so ~60% of forced misses still connect.
    assert.ok(hits > 150, `the intended target must be hittable; got ${hits}/400`);
    assert.ok(hits < 350, `and the big throws must still miss it; got ${hits}/400`);
});

test("[P1] the window is landing point vs body + projectile radius", () => withR5D1({ reducedDamageHits: true }, () => {
    // Not the old centre-within-0.2-tiles test. Place a body so its CENTRE is
    // outside the landing point's radius but its EDGE is inside, and it must
    // still be struck.
    const sim = simStub(1);
    const a = forcedMissHC(sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0; b.x = 5 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const reach = b.radius + PROJECTILE_RADIUS_TILES * TILE_SIZE;
    assert.ok(reach > b.radius, "the projectile's own body must widen the window");

    // Fire, then read the real landing point off the projectile and move the
    // body so its centre sits at 0.95 * reach from it -- outside b.radius
    // (0.2 tiles = 6 px) but inside reach (0.3 tiles = 9 px).
    a.fireProjectile(b);
    const p = sim.projectiles[0];
    b.x = p.targetX + reach * 0.95;
    b.y = p.targetY;
    assert.ok(
        Math.hypot(b.x - p.targetX, b.y - p.targetY) > b.radius,
        "the centre must be outside the old centre-only window",
    );
    const before = b.currentHp;
    land(sim);
    assert.equal(before - b.currentHp, 6.5, "an edge overlap is a reduced hit");
}));

test("[P1] a displaced shot that overlaps nobody grounds harmlessly", () => {
    const sim = simStub(1);
    const a = forcedMissHC(sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0; b.x = 5 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    a.fireProjectile(b);
    const p = sim.projectiles[0];
    // Step the body clear of the landing point by more than body+projectile.
    const reach = b.radius + PROJECTILE_RADIUS_TILES * TILE_SIZE;
    b.x = p.targetX + reach * 3;
    b.y = p.targetY;
    const before = b.currentHp;
    land(sim);
    assert.equal(b.currentHp, before, "nothing under the landing point, nothing applied");
});

test("[P1] the flight path is NOT swept -- only the landing point resolves", () => {
    // A body parked squarely on the line of fire, halfway to the target, takes
    // nothing. There is no pass-through collision for these units, and the
    // tape agrees: one confirmed stray in the whole corpus.
    const sim = simStub(1);
    const a = forcedMissHC(sim);
    const target = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000, pierce_armor: 4 }, "arbalester", "Britons", sim);
    const inTheWay = new BattleUnit(
        "2-1", 2, { ...STATS, hp: 1000, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0;
    target.x = 6 * TILE_SIZE; target.y = 0;
    inTheWay.x = 3 * TILE_SIZE; inTheWay.y = 0;   // dead on the chord
    sim.team1.push(a); sim.team2.push(target, inTheWay);

    const before = inTheWay.currentHp;
    for (let i = 0; i < 40; i++) {
        a.fireProjectile(target);
        land(sim);
    }
    assert.equal(
        inTheWay.currentHp, before,
        "a unit the shot flew over must never be damaged",
    );
});

test("[P1] a failed roll can never be a FULL hit, even on the primary", () => withR5D1({ reducedDamageHits: true }, () => {
    // R5b resolved a failed roll that still landed on the primary as full
    // damage. Under P1 that is precisely the half hit.
    const sim = simStub(5);
    const a = forcedMissHC(sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e6, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0; b.x = 5 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    for (let i = 0; i < 200; i++) {
        const before = b.currentHp;
        a.fireProjectile(b);
        land(sim);
        const dealt = before - b.currentHp;
        assert.ok(dealt === 0 || dealt === 6.5, `unexpected application ${dealt}`);
    }
}));

test("[P1] an accuracy-100 unit is untouched -- it never fails a roll", () => {
    // Zero reduced-damage events on any accuracy-100 side, across all six
    // tapes. The mechanic is the accuracy roll's consequence and nothing else.
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack: 17, attack_range: 7, projectile_speed: 7, accuracy: 100 },
        "arbalester", "Britons", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e6, pierce_armor: 4 }, "arbalester", "Britons", sim);
    a.x = 0; a.y = 0; b.x = 5 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    for (let i = 0; i < 50; i++) {
        const before = b.currentHp;
        a.fireProjectile(b);
        land(sim);
        assert.equal(before - b.currentHp, 13, "full damage every time, never a half");
    }
});

// ---- P2: the trailing-window lead -------------------------------------------

// Walk a unit at a constant velocity for `seconds`, feeding the ring buffer
// exactly the way Simulation.update() does: one refreshVelocity per tick, off
// the pre-move position.
function walk(unit, vxPxPerSec, vyPxPerSec, seconds) {
    const ticks = Math.round(seconds / DT);
    for (let i = 0; i < ticks; i++) {
        unit.refreshVelocity(DT);
        unit.x += vxPxPerSec * DT;
        unit.y += vyPxPerSec * DT;
    }
    unit.refreshVelocity(DT);
}

test("[P2] the lead is the intercept of the target's WINDOWED motion", () => withR5D1({ trailingWindowLead: true }, () => {
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    a.x = 0; a.y = 0;
    b.x = 7 * TILE_SIZE; b.y = -2 * TILE_SIZE;
    // Crossing at 1 tile/s for two full windows, ending at y = 0.
    walk(b, 0, 1 * TILE_SIZE, 2 * TILE_SIZE / (1 * TILE_SIZE));

    const wv = b.windowVelocity();
    assert.ok(Math.abs(wv.vy - 1 * TILE_SIZE) < 1e-6, `window vy ${wv.vy}`);
    assert.equal(wv.vx, 0);

    const aim = a.aimPointFor(b);
    // Full intercept: the aim point's own flight time, times the measured
    // velocity, IS the offset. Converged, so this holds to floating point.
    const flight = Math.hypot(aim.x - a.x, aim.y - a.y) / (7 * TILE_SIZE);
    assert.ok(
        Math.abs(aim.y - (b.y + wv.vy * flight)) < 1e-6,
        `aim.y ${aim.y} must be the converged intercept ${b.y + wv.vy * flight}`,
    );
    assert.equal(aim.x, b.x, "no lead along x -- no measured x motion");
}));

test("[P2] a target that JUST stopped is still led -- the whole point", () => withR5D1({ trailingWindowLead: true }, () => {
    // This is the R5c Q2d failure verbatim: D1 stops a unit to fire and D4
    // parks it at the margin, so its instantaneous velocity on the launch tick
    // is exactly zero even though it has been walking. The one-tick reading
    // sees nothing; the window still sees the motion.
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 7 * TILE_SIZE; b.y = 0;

    walk(b, 0, 1 * TILE_SIZE, 1.0);      // a second of walking ...
    b.refreshVelocity(DT);               // ... then one tick standing still.

    assert.equal(b.velX, 0);
    assert.equal(b.velY, 0, "the instantaneous velocity is zero, as R5c measured");

    const led = a.aimPointFor(b);
    assert.ok(
        Math.abs(led.y - b.y) > 0.5 * TILE_SIZE,
        `the window must still carry lead; got ${(led.y - b.y) / TILE_SIZE} tiles`,
    );

    withR5D1({ trailingWindowLead: false }, () => {
        const flat = a.aimPointFor(b);
        assert.equal(flat.y, b.y, "R5b's one-tick reading has no lead at all here");
    });
}));

test("[P2] a target stopped for longer than the window is aimed at directly", () => {
    // The window is a measurement of RECENT motion: once the walk has scrolled
    // out of it, there is nothing to lead.
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 7 * TILE_SIZE; b.y = 0;

    walk(b, 0, 1 * TILE_SIZE, 1.0);
    walk(b, 0, 0, LEAD_WINDOW_SECONDS * 2);

    const wv = b.windowVelocity();
    assert.equal(wv.vx, 0);
    assert.equal(wv.vy, 0, "the window has flushed");
    const aim = a.aimPointFor(b);
    assert.equal(aim.x, b.x);
    assert.equal(aim.y, b.y);
});

test("[P2] the ring buffer measures 0.3 s of WALL CLOCK, not 18 ticks", () => {
    // Sized off the real dt on the first refresh, so a different tick rate
    // still gets a 0.3 s ruler -- the same lesson as the stuck bar's px/s rate.
    const sim = simStub(5);
    const fast = new BattleUnit("1-0", 1, { ...STATS }, "arbalester", "Chinese", sim);
    const slow = new BattleUnit("1-1", 1, { ...STATS }, "arbalester", "Chinese", sim);
    fast.x = 0; fast.y = 0; slow.x = 0; slow.y = 0;

    const run = (u, dt) => {
        // Walk 1 tile/s for a full second at this tick rate.
        for (let t = 0; t < Math.round(1 / dt); t++) {
            u.refreshVelocity(dt);
            u.y += TILE_SIZE * dt;
        }
        u.refreshVelocity(dt);
    };
    run(fast, DT);
    run(slow, 1 / 15);

    assert.equal(
        fast.histX.length, Math.round(LEAD_WINDOW_SECONDS / DT) + 1,
        "60 Hz: 18 intervals + 1",
    );
    assert.equal(
        slow.histX.length, Math.round(LEAD_WINDOW_SECONDS / (1 / 15)) + 1,
        "15 Hz: 4.5 -> 5 intervals + 1",
    );
    // Both measure the same real velocity despite very different tick counts.
    assert.ok(Math.abs(fast.windowVelocity().vy - TILE_SIZE) < 1e-6);
    assert.ok(Math.abs(slow.windowVelocity().vy - TILE_SIZE) < 1e-6);
});

test("[P2] warm-up: fewer samples than the window measure the span they have", () => {
    const sim = simStub(5);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    b.x = 0; b.y = 0;
    assert.deepEqual(b.windowVelocity(), { vx: 0, vy: 0 }, "no samples, no motion");
    b.refreshVelocity(DT);
    assert.deepEqual(b.windowVelocity(), { vx: 0, vy: 0 }, "one sample is not a span");
    b.y += TILE_SIZE * DT;
    b.refreshVelocity(DT);
    assert.ok(
        Math.abs(b.windowVelocity().vy - TILE_SIZE) < 1e-9,
        "two samples one tick apart: 1 tile/s",
    );
});

test("[P2] the intercept converges rather than stopping at two passes", () => withR5D1({ trailingWindowLead: true }, () => {
    // A target running along the line of fire is the case two passes leave
    // short: each pass pushes the aim point further out, which lengthens the
    // flight, which pushes it further again.
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 9, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 8 * TILE_SIZE; b.y = 0;
    walk(b, 3 * TILE_SIZE, 0, 1.0);          // fleeing at 3 tiles/s

    const aim = a.aimPointFor(b);
    const flight = Math.hypot(aim.x - a.x, aim.y - a.y) / (7 * TILE_SIZE);
    const residual = Math.abs(aim.x - (b.x + b.windowVelocity().vx * flight));
    assert.ok(residual < 1e-6, `intercept residual ${residual} px is not converged`);
}));

// ---- off-switch and melee identity ------------------------------------------

function rangedFight() {
    const sim = new Simulation(900, 600, makeRng(42));
    for (let i = 0; i < 4; i++) {
        const u = new BattleUnit(
            `1-${i}`, 1,
            { ...STATS, attack_range: 7, projectile_speed: 7, accuracy: 90 },
            "arbalester", "Chinese", sim);
        u.x = 100; u.y = 100 + i * 20;
        sim.team1.push(u);
    }
    for (let i = 0; i < 4; i++) {
        const u = new BattleUnit(
            `2-${i}`, 2,
            { ...STATS, attack_range: 7, projectile_speed: 7.5, accuracy: 75 },
            "hand_cannoneer", "Japanese", sim);
        u.x = 400; u.y = 100 + i * 20;
        sim.team2.push(u);
    }
    return sim;
}

// P2 only bites when a target is actually in motion while being shot at, and
// the symmetric line fight above is over the moment both sides park. This one
// keeps a side WALKING under fire, diagonally, so the lead has a perpendicular
// component: long-reach, near-immobile shooters against short-reach runners
// that have to cross the field to answer.
function crossingFight() {
    const sim = new Simulation(900, 600, makeRng(42));
    for (let i = 0; i < 4; i++) {
        const u = new BattleUnit(
            `1-${i}`, 1,
            {
                ...STATS, hp: 300, attack_range: 8, projectile_speed: 7,
                accuracy: 100, movement_speed: 0.3,
            },
            "arbalester", "Chinese", sim);
        u.x = 120; u.y = 80 + i * 30;
        sim.team1.push(u);
    }
    for (let i = 0; i < 4; i++) {
        const u = new BattleUnit(
            `2-${i}`, 2,
            {
                ...STATS, hp: 300, attack_range: 2, projectile_speed: 7,
                accuracy: 100, movement_speed: 1.4,
            },
            "imp_elite_skirm", "Japanese", sim);
        u.x = 500; u.y = 420 + i * 30;
        sim.team2.push(u);
    }
    return sim;
}

function meleeFight() {
    const sim = new Simulation(900, 600, makeRng(77));
    const melee = { ...STATS, attack: 13, attack_range: 0, movement_speed: 1.05 };
    for (let i = 0; i < 5; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...melee }, "champion", "Franks", sim);
        u.x = 150; u.y = 100 + i * 22;
        sim.team1.push(u);
    }
    for (let i = 0; i < 5; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...melee }, "halberdier", "Goths", sim);
        u.x = 380; u.y = 100 + i * 22;
        sim.team2.push(u);
    }
    return sim;
}

function hashOf(build, seconds = 20) {
    const sim = build();
    for (let i = 0; i < 60 * seconds; i++) sim.update(DT);
    return sim.stateHash();
}

test("[R5d-1] both rules off is bit-identical to the R5b engine", () => {
    const r5bOn = {
        stopToFire: true, ballisticLead: true,
        inflightAccounting: true, approachMargin: true,
    };
    const off = { reducedDamageHits: false, trailingWindowLead: false };
    const a = withFlags(r5bOn, off, () => hashOf(rangedFight));
    const b = withFlags(r5bOn, off, () => hashOf(rangedFight));
    assert.equal(a, b, "the off path must be deterministic");

    const on = withFlags(
        r5bOn, { reducedDamageHits: true, trailingWindowLead: true },
        () => hashOf(rangedFight));
    assert.notEqual(
        on, a,
        "the rules must actually change something, or this test proves nothing",
    );

    // Each rule alone also moves the fight -- neither is dead code. P1 is
    // checked on the hand cannoneer fight (it needs a unit that can fail a
    // roll) and P2 on the crossing fight (it needs a target in motion).
    const p1Only = withFlags(
        r5bOn, { reducedDamageHits: true, trailingWindowLead: false },
        () => hashOf(rangedFight));
    assert.notEqual(p1Only, a, "P1 alone must change the fight");

    const crossOff = withFlags(r5bOn, off, () => hashOf(crossingFight, 40));
    const crossP2 = withFlags(
        r5bOn, { reducedDamageHits: false, trailingWindowLead: true },
        () => hashOf(crossingFight, 40));
    assert.notEqual(crossP2, crossOff, "P2 alone must change a fight with movers in it");
});

test("[R5d-1] melee is provably untouched", () => {
    // No melee path reads either flag: a pure-melee fight must hash the same
    // in all four flag combinations.
    const r5bOn = {
        stopToFire: true, ballisticLead: true,
        inflightAccounting: true, approachMargin: true,
    };
    const combos = [
        { reducedDamageHits: false, trailingWindowLead: false },
        { reducedDamageHits: true, trailingWindowLead: false },
        { reducedDamageHits: false, trailingWindowLead: true },
        { reducedDamageHits: true, trailingWindowLead: true },
    ];
    const hashes = combos.map((c) => withFlags(r5bOn, c, () => hashOf(meleeFight, 30)));
    for (const h of hashes) {
        assert.equal(h, hashes[0], "a melee fight must not see R5d-1 at all");
    }
});

test("[R5d-1] setR5D1 rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setR5D1({ notARule: true }), /unknown flag/);
    assert.equal(Object.keys(R5D1).length, 2);
});
