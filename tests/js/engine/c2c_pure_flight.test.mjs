// Phase C2-c — pure flight during a contact break.
//
// C2A (docs/calibration/c2a_contact_break.md) built the kiter's contact break
// and it failed in isolation, for a reason its probe measured exactly: on a
// break tick the break's own bearing is a MINORITY of the vector
// moveAwayFromTarget sums.
//
//   |radial basis|      1.000   (unit, by construction)
//   |orbit + cohesion|  1.249
//   |avoidance|         2.221
//   cos(actual tick step, break bearing)  0.276   against a tape 0.88
//
// C2A's report closes the obvious door -- "do not rebuild this as a different
// basis; it will move the cosine by ~0.02 again" -- so C-c does not touch the
// basis. It changes the COMPOSITION: while a break is live the unit's movement
// is the break bearing plus COLLISION avoidance only. The two group-formation
// terms (kiteSteering's orbit + cohesion) are not applied, and avoidance is
// evaluated for what it physically is -- not walking through bodies -- rather
// than as the social spacing force that dominates the sum in a crowd.
//
// ZERO NEW CONSTANTS, and the tests below are written to prove that rather
// than assert it: every weight keeps its value and keeps applying off the
// break, and the avoidance narrowing selects between two bands the function
// already distinguishes (`overlap > 0`).
//
// Six groups:
//   1. the flag object and its setter;
//   2. the orbit/cohesion drop -- and that it is a DROP, not a re-weight;
//   3. the avoidance band -- social dropped, imminent overlap kept;
//   4. the return to normal composition the tick the break ends;
//   5. inertness -- without C2A.contactBreak the flag can never fire;
//   6. off-switch identity, scoping identities (r-v-r / m-v-m / siege), purity.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    C2A,
    setC2A,
    C2C,
    setC2C,
} from "../../../apps/website/static/js/engine/constants.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const DT = 1 / 60;

const C2A_OFF = { contactBreak: false, breakPriority: false };
const C2A_ON = { contactBreak: true, breakPriority: true };
const C2C_OFF = { pureFlight: false };
const C2C_ON = { pureFlight: true };

function withFlags(c2a, c2c, fn) {
    const savedA = { ...C2A };
    const savedC = { ...C2C };
    setC2A(c2a);
    setC2C(c2c);
    try {
        return fn();
    } finally {
        setC2A(savedA);
        setC2C(savedC);
    }
}

// ---- fixtures --------------------------------------------------------------
// Same three stat blocks as c2a_contact_break.test.mjs, deliberately: this rule
// lives inside that rule's state, so the scoping arguments have to be checked
// against the same bodies.

const MELEE = {
    hp: 70, attack: 12, attack_range: 0, attack_speed: 1.8,
    attack_delay: 0.4, movement_speed: 1.45, melee_armor: 1,
    pierce_armor: 1, outline_size: 0.2, accuracy: 100,
    unit_name: "Test Champion",
};
const ARCHER = {
    hp: 40, attack: 20, attack_range: 7, attack_speed: 2.0,
    projectile_speed: 7, accuracy: 100, movement_speed: 0.96,
    melee_armor: 0, pierce_armor: 0, outline_size: 0.2,
    unit_name: "Test Arbalester", is_ranged: true,
};
const SIEGE = {
    hp: 60, attack: 30, attack_range: 8, min_attack_range: 2, attack_speed: 3.6,
    projectile_speed: 4, accuracy: 100, movement_speed: 0.6,
    melee_armor: 0, pierce_armor: 0, outline_size: 0.3,
    unit_name: "Test Scorpion", is_ranged: true,
};

let nextId = 0;
function mk(sim, team, stats, slug = "u") {
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, { ...stats }, slug, "Chinese", sim,
    );
    (team === 1 ? sim.team1 : sim.team2).push(u);
    return u;
}

function newSim(seed = 1) {
    return new Simulation(900, 600, makeRng(seed));
}

// The geometry every composition test below uses, chosen so that ONE term is
// under test at a time:
//
//   kiter  (400, 300)          radius 6, so minDist to another 0.2-outline
//   hitter (425, 300)          body is 6 + 6 + 2 = 14 px
//
// 25 px separates them. That is inside the break's escape criterion
// (5 + 6 + 6 + 12 = 29 px, asserted below rather than assumed) and OUTSIDE
// calculateAvoidance's outer band (1.5 * 14 = 21 px), so the hitter itself
// contributes exactly zero avoidance and the only forces in play are the ones
// each test puts there. The break bearing is therefore pure -x.
const HITTER_AT = 25;

function breakScene() {
    const sim = newSim();
    const kiter = mk(sim, 1, ARCHER, "arbalester");
    const hitter = mk(sim, 2, MELEE, "champion");
    kiter.x = 400; kiter.y = 300;
    hitter.x = 400 + HITTER_AT; hitter.y = 300;
    kiter.target = hitter;
    hitter.target = kiter;
    kiter.takeDamage(5, hitter);
    return { sim, kiter, hitter };
}

// One tick of moveAwayFromTarget, reported as the realised step. `this.vx/vy`
// start at 0 and the smoothing is `0.3 * v + 0.7 * dir` followed by a
// renormalise, so a first tick's step direction IS the composed direction --
// no smoothing history to unpick.
function step(kiter, units, steering) {
    const x0 = kiter.x, y0 = kiter.y;
    kiter.moveAwayFromTarget(DT, units, steering);
    return { mx: kiter.x - x0, my: kiter.y - y0 };
}

// ---- 1. the flag -----------------------------------------------------------

test("[C2c] the rule ships OFF, and the object is exactly one rule", () => {
    assert.equal(C2C.pureFlight, false);
    assert.equal(Object.keys(C2C).length, 1);
});

test("[C2c] setC2C rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setC2C({ notARule: true }), /unknown flag/);
});

test("[C2c] fixture check: the scene's break really is live and the hitter is silent", () => {
    withFlags(C2A_ON, C2C_OFF, () => {
        const { kiter, hitter } = breakScene();
        assert.equal(kiter.contactBreakHitter(), hitter, "the break is live at 25 px");
        const escape =
            hitter.attackRange + hitter.radius + kiter.radius + 2 * kiter.radius;
        assert.ok(HITTER_AT < escape, `25 px is inside escape ${escape}`);
        const minDist = kiter.radius + hitter.radius + 2;
        assert.ok(HITTER_AT > minDist * 1.5,
            `and outside avoidance's outer band ${minDist * 1.5}`);
        const av = kiter.calculateAvoidance([kiter, hitter]);
        assert.equal(av.x, 0);
        assert.equal(av.y, 0);
    });
});

// ---- 2. the orbit + cohesion drop ------------------------------------------

test("[C2c] THE DROP: orbit + cohesion do not steer a unit in flight", () => {
    // A strong southward group term (`steering.x/y`) against a westward break
    // bearing. Pre-C2C the two compose and the unit leaves at ~45 deg; under
    // pure flight the group term is not there at all, so the step is the
    // bearing exactly.
    const steering = { x: 0, y: 1, rx: 0, ry: 0 };

    const before = withFlags(C2A_ON, C2C_OFF, () => {
        const { kiter, hitter } = breakScene();
        return step(kiter, [kiter, hitter], steering);
    });
    assert.ok(before.mx < 0, "pre-C2C: the break bearing is in there");
    assert.ok(before.my > 0, "pre-C2C: and so is the group term");

    const after = withFlags(C2A_ON, C2C_ON, () => {
        const { kiter, hitter } = breakScene();
        return step(kiter, [kiter, hitter], steering);
    });
    assert.ok(after.mx < 0, "pure flight: still running from the hitter");
    assert.ok(Math.abs(after.my) < 1e-9,
        `pure flight: no group contribution at all (my ${after.my})`);
});

test("[C2c] it is a DROP, not a re-weight -- no strength of group term survives", () => {
    // A re-weighted term would still bend the heading, just less. Ten decades
    // of group-term magnitude all give the same answer, which is the signature
    // of a term that is not being summed rather than one being scaled.
    withFlags(C2A_ON, C2C_ON, () => {
        for (const mag of [0.01, 0.1, 1, 10, 100, 1000]) {
            const { kiter, hitter } = breakScene();
            const { mx, my } = step(kiter, [kiter, hitter],
                { x: 0, y: mag, rx: 0, ry: 0 });
            assert.ok(mx < 0, `mag ${mag}: bearing intact`);
            assert.ok(Math.abs(my) < 1e-9, `mag ${mag}: my ${my}`);
        }
    });
});

test("[C2c] the group terms are untouched for a unit with no live break", () => {
    // The weights keep their values and keep applying: this is a
    // state-conditioned selection, not a change to kiteSteering.
    withFlags(C2A_ON, C2C_ON, () => {
        const sim = newSim();
        const kiter = mk(sim, 1, ARCHER, "arbalester");
        const foe = mk(sim, 2, MELEE, "champion");
        kiter.x = 400; kiter.y = 300;
        foe.x = 425; foe.y = 300;
        kiter.target = foe;
        assert.equal(kiter.contactBreakHitter(), null, "no hit, so no break");
        const { mx, my } = step(kiter, [kiter, foe], { x: 0, y: 1, rx: 0, ry: 0 });
        assert.ok(mx < 0);
        assert.ok(my > 0, "the group term still steers a unit that is not fleeing");
    });
});

// ---- 3. the avoidance band -------------------------------------------------

// A same-team body due NORTH of the kiter, at `gap` px. Its separation force on
// the kiter points due SOUTH, which no other term in the scene produces, so the
// sign of `my` is a clean read of whether that body was counted.
function withNeighbour(gap) {
    const { sim, kiter, hitter } = breakScene();
    const mate = mk(sim, 1, ARCHER, "arbalester");
    mate.x = 400; mate.y = 300 - gap;
    return { sim, kiter, hitter, mate };
}

const MIN_DIST = 6 + 6 + 2;        // two 0.2-outline bodies: 14 px

test("[C2c] THE BAND: the 1.0-1.5x social band is dropped in flight", () => {
    const gap = 17;                 // 14 < 17 < 21 -- touching nothing
    assert.ok(gap > MIN_DIST && gap < MIN_DIST * 1.5, "fixture: social band");

    const before = withFlags(C2A_ON, C2C_OFF, () => {
        const { kiter, hitter, mate } = withNeighbour(gap);
        return step(kiter, [kiter, hitter, mate], null);
    });
    assert.ok(before.my > 0, "pre-C2C: the polite-spacing push is in the sum");

    const after = withFlags(C2A_ON, C2C_ON, () => {
        const { kiter, hitter, mate } = withNeighbour(gap);
        return step(kiter, [kiter, hitter, mate], null);
    });
    assert.ok(Math.abs(after.my) < 1e-9,
        `pure flight: social spacing does not steer a fleeing unit (my ${after.my})`);
    assert.ok(after.mx < 0);
});

test("[C2c] and imminent OVERLAP is still avoided -- it is physics, not spacing", () => {
    const gap = 10;                 // inside minDist: the bodies interpenetrate
    assert.ok(gap < MIN_DIST, "fixture: overlap band");

    withFlags(C2A_ON, C2C_ON, () => {
        const { kiter, hitter, mate } = withNeighbour(gap);
        const { mx, my } = step(kiter, [kiter, hitter, mate], null);
        assert.ok(my > 0, "the overlapping body still pushes it off");
        assert.ok(mx < 0, "while it still runs from the hitter");
    });
});

test("[C2c] the band boundary is calculateAvoidance's OWN, not a new distance", () => {
    // Straddle `minDist` by half a pixel from each side. Anything the function
    // scores as overlapping survives; anything it scores as merely close does
    // not. No distance is introduced by the rule -- this IS the existing test.
    withFlags(C2A_ON, C2C_ON, () => {
        const inside = withNeighbour(MIN_DIST - 0.5);
        const av1 = inside.kiter.calculateAvoidance(
            [inside.kiter, inside.hitter, inside.mate], true);
        assert.ok(av1.y > 0, "just inside minDist: counted");

        const outside = withNeighbour(MIN_DIST + 0.5);
        const av2 = outside.kiter.calculateAvoidance(
            [outside.kiter, outside.hitter, outside.mate], true);
        assert.equal(av2.x, 0, "just outside minDist: not counted");
        assert.equal(av2.y, 0);
    });
});

test("[C2c] calculateAvoidance's default argument is the pre-C2C expression", () => {
    // The parameter is opt-in. Every other caller (moveTowardTarget, and
    // moveAwayFromTarget off a break) must be byte-identical, so the no-arg and
    // explicit-false forms have to agree exactly on both bands.
    withFlags(C2A_OFF, C2C_ON, () => {
        for (const gap of [8, 13.9, 14.1, 17, 20.9, 25]) {
            const { kiter, hitter, mate } = withNeighbour(gap);
            const units = [kiter, hitter, mate];
            const bare = kiter.calculateAvoidance(units);
            const explicit = kiter.calculateAvoidance(units, false);
            assert.equal(bare.x, explicit.x, `gap ${gap}`);
            assert.equal(bare.y, explicit.y, `gap ${gap}`);
        }
    });
});

test("[C2c] the narrowed sum is a SUBSET of the full one, never a new force", () => {
    // Every pair the narrowed pass counts is counted identically by the full
    // pass: same force, same direction. Checked by reconstructing the full sum
    // as narrowed + social-only over a mixed crowd.
    withFlags(C2A_OFF, C2C_OFF, () => {
        const sim = newSim();
        const kiter = mk(sim, 1, ARCHER, "arbalester");
        kiter.x = 400; kiter.y = 300;
        const units = [kiter];
        // Bodies at assorted bearings and gaps, straddling both bands.
        const places = [
            [0, -9], [12, 4], [-16, 6], [3, 18], [-19, -8], [20, -6], [7, -11],
        ];
        for (const [dx, dy] of places) {
            const u = mk(sim, dx > 0 ? 2 : 1, ARCHER, "arbalester");
            u.x = 400 + dx; u.y = 300 + dy;
            units.push(u);
        }
        const full = kiter.calculateAvoidance(units);
        const narrow = kiter.calculateAvoidance(units, true);
        assert.ok(Math.hypot(narrow.x, narrow.y) > 0, "fixture: something overlaps");

        // The social-only remainder, computed by removing every overlapping
        // body and asking for the full sum over the rest.
        const nonOverlapping = units.filter((o) => {
            if (o === kiter) return true;
            const d = Math.hypot(kiter.x - o.x, kiter.y - o.y);
            return d >= kiter.radius + o.radius + 2;
        });
        const social = kiter.calculateAvoidance(nonOverlapping);
        assert.ok(Math.abs(full.x - (narrow.x + social.x)) < 1e-9);
        assert.ok(Math.abs(full.y - (narrow.y + social.y)) < 1e-9);
    });
});

// ---- 4. the return to normal composition -----------------------------------

test("[C2c] the composition returns to normal the tick the break ends", () => {
    // Not a fade and not a cooldown: the break's end condition is a distance,
    // so on the very next call the group term and the social band are both back
    // at full strength. Same unit, same scene, one flag of state changed.
    withFlags(C2A_ON, C2C_ON, () => {
        const { kiter, hitter, mate } = withNeighbour(17);
        const units = [kiter, hitter, mate];
        const steering = { x: 0, y: 1, rx: 0, ry: 0 };

        const during = step(kiter, units, steering);
        assert.ok(Math.abs(during.my) < 1e-9, "in flight: neither term applies");

        // End the break the way the engine ends it -- put the hitter past the
        // escape distance -- rather than by poking the latch.
        hitter.x = kiter.x + 500;
        assert.equal(kiter.contactBreakHitter(), null, "the break really ended");
        kiter.vx = 0; kiter.vy = 0;      // isolate this tick from the last one
        const after = step(kiter, units, steering);
        assert.ok(after.my > 0,
            "group term and social band are both back, at full strength");
    });
});

test("[C2c] a break that ends mid-fight leaves NO residue on the unit", () => {
    // The rule stores nothing. Two units in the same geometry -- one that has
    // never had a break, one whose break has just ended -- must move
    // identically, or the rule has quietly become stateful.
    withFlags(C2A_ON, C2C_ON, () => {
        const steering = { x: 0.3, y: 1, rx: 0, ry: 0 };

        const { kiter: a, hitter: ha, mate: ma } = withNeighbour(17);
        a.moveAwayFromTarget(DT, [a, ha, ma], steering);   // one tick in flight
        ha.x = a.x + 500;
        assert.equal(a.contactBreakHitter(), null);
        a.x = 400; a.y = 300; a.vx = 0; a.vy = 0;
        ha.x = 425; ha.y = 300;
        const moved = step(a, [a, ha, ma], steering);

        const { kiter: b, hitter: hb, mate: mb } = withNeighbour(17);
        b.contactBreakFrom = null;                          // never broke
        const virgin = step(b, [b, hb, mb], steering);

        assert.equal(moved.mx, virgin.mx);
        assert.equal(moved.my, virgin.my);
    });
});

// ---- 5. inertness without C2A ----------------------------------------------

test("[C2c] without C2A.contactBreak the flag can never fire", () => {
    // Structural, not incidental: `pureFlight` is read only where
    // contactBreakHitter() is non-null, and that returns null unconditionally
    // with C2A.contactBreak off.
    const on = withFlags(C2A_OFF, C2C_ON, () => {
        const { kiter, hitter, mate } = withNeighbour(17);
        assert.equal(kiter.contactBreakHitter(), null);
        return step(kiter, [kiter, hitter, mate], { x: 0, y: 1, rx: 0, ry: 0 });
    });
    const off = withFlags(C2A_OFF, C2C_OFF, () => {
        const { kiter, hitter, mate } = withNeighbour(17);
        return step(kiter, [kiter, hitter, mate], { x: 0, y: 1, rx: 0, ry: 0 });
    });
    assert.equal(on.mx, off.mx);
    assert.equal(on.my, off.my);
    assert.ok(on.my > 0, "and both still take the group term");
});

// ---- 6. off-switch, scoping, purity ----------------------------------------

const ARCHER_FIGHT_SECONDS = 40;

function archerFight(seed, n = 6) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...ARCHER }, "arbalester", "Chinese", sim);
        u.x = 200 + (i % 2) * 25; u.y = 200 + i * 24;
        sim.team1.push(u);
    }
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...ARCHER }, "arbalester", "Goths", sim);
        u.x = 420 - (i % 2) * 25; u.y = 205 + i * 24;
        sim.team2.push(u);
    }
    return sim;
}

function meleeFight(seed, n = 8) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...MELEE }, "champion", "Franks", sim);
        u.x = 300 + (i % 3) * 18; u.y = 180 + Math.floor(i / 3) * 20;
        sim.team1.push(u);
    }
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...MELEE }, "halberdier", "Goths", sim);
        u.x = 400 + (i % 3) * 18; u.y = 180 + Math.floor(i / 3) * 20;
        sim.team2.push(u);
    }
    return sim;
}

function siegeFight(seed, n = 4) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...SIEGE }, "heavy_scorpion", "Chinese", sim);
        u.x = 240; u.y = 200 + i * 26;
        sim.team1.push(u);
    }
    for (let i = 0; i < n * 2; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...MELEE }, "hussar", "Goths", sim);
        u.x = 430 + (i % 2) * 18; u.y = 200 + Math.floor(i / 2) * 24;
        sim.team2.push(u);
    }
    return sim;
}

// Same tanky-chaser fixture c2a_contact_break.test.mjs uses, for the same
// reason: with the stock ARCHER the archers wipe the chasers before a blow
// lands, and the rule would read "identical" for the wrong reason.
const CHASER = {
    hp: 180, attack: 14, attack_range: 0, attack_speed: 1.8,
    attack_delay: 0.4, movement_speed: 1.45, melee_armor: 2,
    pierce_armor: 4, outline_size: 0.2, accuracy: 100,
    unit_name: "Test Chaser",
};
function chaseFight(seed, nArchers = 8, nChasers = 8) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < nArchers; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...ARCHER, attack: 8 },
            "arbalester", "Chinese", sim);
        u.x = 300 + (i % 2) * 22; u.y = 190 + Math.floor(i / 2) * 26;
        sim.team1.push(u);
    }
    for (let i = 0; i < nChasers; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...CHASER }, "champion", "Franks", sim);
        u.x = 420 + (i % 2) * 22; u.y = 190 + Math.floor(i / 2) * 26;
        sim.team2.push(u);
    }
    return sim;
}

function runHash(build, seed, seconds = 30) {
    const sim = build(seed);
    for (let i = 0; i < 60 * seconds; i++) sim.update(DT);
    return sim.stateHash();
}

test("[C2c] THE OFF SWITCH: pureFlight off reproduces the C2A engine exactly", () => {
    for (const seed of [42, 7]) {
        const off = withFlags(C2A_ON, C2C_OFF, () => runHash(chaseFight, seed));
        const off2 = withFlags(C2A_ON, C2C_OFF, () => runHash(chaseFight, seed));
        assert.equal(off, off2, "the off path is deterministic");
        const on = withFlags(C2A_ON, C2C_ON, () => runHash(chaseFight, seed));
        assert.notEqual(on, off,
            `seed ${seed}: the rule must actually reach a melee-chasing-ranged fight`);
    }
});

test("[C2c] and with everything off it reproduces the pre-C2 engine exactly", () => {
    for (const seed of [42, 7]) {
        const pre = withFlags(C2A_OFF, C2C_OFF, () => runHash(chaseFight, seed));
        const flagOnly = withFlags(C2A_OFF, C2C_ON, () => runHash(chaseFight, seed));
        assert.equal(flagOnly, pre, `seed ${seed}: C2C alone is inert`);
    }
});

test("[C2c] on is deterministic across repeated runs", () => {
    withFlags(C2A_ON, C2C_ON, () => {
        assert.equal(runHash(chaseFight, 7), runHash(chaseFight, 7));
        assert.equal(runHash(chaseFight, 8, 45), runHash(chaseFight, 8, 45));
    });
});

test("[C2c] a RANGED-vs-RANGED fight is bit-identical with C2A+C2C on", () => {
    // Inherited scope, not a re-declared one: the state this rule modifies can
    // only exist after a MELEE hit, and these fights contain no melee unit.
    for (const seed of [3, 11, 29]) {
        const on = withFlags(C2A_ON, C2C_ON,
            () => runHash(archerFight, seed, ARCHER_FIGHT_SECONDS));
        const off = withFlags(C2A_OFF, C2C_OFF,
            () => runHash(archerFight, seed, ARCHER_FIGHT_SECONDS));
        assert.equal(on, off, `ranged seed ${seed} must not move`);
    }
});

test("[C2c] a MELEE-vs-MELEE fight is bit-identical with C2A+C2C on", () => {
    for (const seed of [5, 13, 31]) {
        const on = withFlags(C2A_ON, C2C_ON, () => runHash(meleeFight, seed, 30));
        const off = withFlags(C2A_OFF, C2C_OFF, () => runHash(meleeFight, seed, 30));
        assert.equal(on, off, `melee seed ${seed} must not move`);
    }
});

test("[C2c] a SIEGE-vs-melee fight is bit-identical with C2A+C2C on", () => {
    for (const seed of [2, 17]) {
        const on = withFlags(C2A_ON, C2C_ON, () => runHash(siegeFight, seed, 30));
        const off = withFlags(C2A_OFF, C2C_OFF, () => runHash(siegeFight, seed, 30));
        assert.equal(on, off, `siege seed ${seed} must not move`);
    }
});

test("[C2c] moveTowardTarget is untouched -- the chaser's avoidance is unchanged", () => {
    // The narrowing is opt-in per call site and only moveAwayFromTarget opts
    // in. A melee unit closing on a victim keeps the full separation sum, which
    // is what holds a scrum's spacing.
    withFlags(C2A_ON, C2C_ON, () => {
        const sim = newSim();
        const chaser = mk(sim, 2, MELEE, "champion");
        const victim = mk(sim, 1, ARCHER, "arbalester");
        const mate = mk(sim, 2, MELEE, "champion");
        chaser.x = 400; chaser.y = 300;
        victim.x = 460; victim.y = 300;
        mate.x = 400; mate.y = 283;          // 17 px: the social band
        chaser.target = victim;
        const x0 = chaser.x, y0 = chaser.y;
        chaser.moveTowardTarget(DT, [chaser, victim, mate]);
        assert.ok(chaser.x - x0 > 0, "it closes on the victim");
        assert.ok(chaser.y - y0 > 0, "and is still pushed off its neighbour");
    });
});

test("[C2c] the rule consumes no randomness", () => {
    withFlags(C2A_ON, C2C_ON, () => {
        let draws = 0;
        const inner = makeRng(1);
        const rng = {
            next() { draws++; return inner.next(); },
            getState() { return inner.getState(); },
        };
        const sim = new Simulation(900, 600, rng);
        const kiter = mk(sim, 1, ARCHER, "arbalester");
        const hitter = mk(sim, 2, MELEE, "champion");
        const mate = mk(sim, 1, ARCHER, "arbalester");
        kiter.x = 400; kiter.y = 300;
        hitter.x = 425; hitter.y = 300;
        mate.x = 400; mate.y = 290;
        kiter.target = hitter;
        kiter.takeDamage(5, hitter);
        assert.equal(kiter.contactBreakHitter(), hitter, "fixture: the break is live");
        kiter.moveAwayFromTarget(DT, [kiter, hitter, mate], { x: 0, y: 1, rx: 0, ry: 0 });
        kiter.calculateAvoidance([kiter, hitter, mate], true);
        assert.equal(draws, 0, "pure flight is geometry, never a draw");
    });
});

test("[C2c] TILE_SIZE sanity -- the fixtures' px geometry is the engine's", () => {
    // The band arithmetic above is written in pixels; this pins the conversion
    // the numbers were derived from so a TILE_SIZE change fails loudly here
    // rather than silently moving a test's meaning.
    assert.equal(TILE_SIZE, 30);
});
