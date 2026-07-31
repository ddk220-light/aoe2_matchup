// Phase C2-a — the kiter's contact break.
//
// C1 (docs/calibration/c1_chaser_cadence.md) measured that a melee unit chasing
// a ranged one swings 1.22x slower on tape than in this engine, and that the
// cause is CONTACT DURATION on the kiter's side rather than anything about the
// chaser: after taking a melee hit the tape's kiter starts moving in a median
// 0.08 s, runs at cos 0.88 to "away from the unit that hit it", and opens 1.03
// tiles of radial separation inside one chaser reload. This engine's takes
// 0.42 s, runs at cos 0.61, and opens 0.05 tiles.
//
// C-a is that break, as two flags (constants.js C2A):
//   contactBreak   -- latch the HITTER; while it is within escape distance the
//                     retreat basis is "away from the hitter", replacing E10a's
//                     shared enemy-centroid basis.
//   breakPriority  -- while the break is live, retreating outranks stopping to
//                     fire (R5B-D1's launch test and the approach/settle arm).
//
// Neither rule carries a number. The escape distance is the hitter's OWN reach
// (inRange()'s arithmetic) plus the kiter's OWN body diameter, both of which
// the engine already computes for other reasons.
//
// The tests are in five groups:
//   1. the trigger, and only the trigger -- a MELEE hit on a NON-SIEGE RANGED
//      body, which is what makes ranged-vs-ranged and melee-vs-melee
//      unreachable by construction rather than by a scope check;
//   2. the bearing -- away from the HITTER, not the target and not the centroid;
//   3. the priority -- the break beats stop-to-fire and beats re-approach;
//   4. the end -- a physical escape criterion, no timer, no decay;
//   5. off-switch and blast radius: flag-off identity, ranged-vs-ranged and
//      melee-vs-melee bit-identity with the flags ON, siege untouched, no rng.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    C2A,
    setC2A,
} from "../../../apps/website/static/js/engine/constants.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const DT = 1 / 60;
const ALL_OFF = { contactBreak: false, breakPriority: false };
// C-a1 alone: the bearing without the priority. Used to pin which half does
// what, exactly as b2_bump_contact.test.mjs pins B2a against B2a+B2b.
const BEARING_ONLY = { contactBreak: true, breakPriority: false };

function withC2A(overrides, fn) {
    const saved = { ...C2A };
    setC2A(overrides);
    try {
        return fn();
    } finally {
        setC2A(saved);
    }
}

// ---- fixtures --------------------------------------------------------------

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
// Siege: the minimum-range dead zone is the whole point -- it is the clause
// that keeps every siege fight out of this rule (and out of kiteSteering).
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

// One kiter (team 1) at the origin point, one melee chaser (team 2) placed at
// `hitterAt` px along +x. Nothing is ticked -- the scenes below drive exactly
// the call they are testing.
function scene({ hitterAt = 20, kiterStats = ARCHER } = {}) {
    const sim = newSim();
    const kiter = mk(sim, 1, kiterStats, "arbalester");
    const hitter = mk(sim, 2, MELEE, "champion");
    kiter.x = 400; kiter.y = 300;
    hitter.x = 400 + hitterAt; hitter.y = 300;
    kiter.target = hitter;
    hitter.target = kiter;
    return { sim, kiter, hitter };
}

// The rule's own escape distance, recomputed here from the units rather than
// copied from the engine, so a silent change to either term fails a test.
function escapeDist(kiter, hitter) {
    return hitter.attackRange + hitter.radius + kiter.radius + 2 * kiter.radius;
}

// ---- shipped configuration -------------------------------------------------

// SHIPPED OFF -- the prediction failed (see constants.js and
// docs/calibration/c2a_contact_break.md). The mechanism stays wired and tested
// under explicit override, exactly as R5D.reapproach / R5F.silenceAdvance /
// R5F.persistVictim do, so every test below drives it through withC2A().
const BOTH_ON = { contactBreak: true, breakPriority: true };

// The rules ship OFF, so every BEHAVIOURAL test has to arm them explicitly.
// `ctest` is `test` with both flags on for the duration of the body; the
// nested withC2A(ALL_OFF) calls inside individual tests still work, because
// withC2A saves and restores whatever it found.
const ctest = (name, fn) => test(name, () => withC2A(BOTH_ON, fn));

test("[C2a] both rules ship OFF, and the object is exactly two rules", () => {
    assert.equal(C2A.contactBreak, false);
    assert.equal(C2A.breakPriority, false);
    assert.equal(Object.keys(C2A).length, 2);
});

test("[C2a] setC2A rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setC2A({ notARule: true }), /unknown flag/);
});

// ---- 1. the trigger --------------------------------------------------------

ctest("[C2a] a MELEE hit on a ranged body latches that hitter", () => {
    const { kiter, hitter } = scene();
    assert.equal(kiter.contactBreakFrom, null, "nothing latched before the hit");
    kiter.takeDamage(5, hitter);
    assert.equal(kiter.contactBreakFrom, hitter);
    assert.equal(kiter.contactBreakHitter(), hitter, "and the break is live");
});

ctest("[C2a] a RANGED attacker never latches a break -- this is why r-v-r cannot move", () => {
    // The single clause that makes ranged-vs-ranged unreachable BY
    // CONSTRUCTION: those fights contain no melee attacker at all, so there is
    // no scope check to get wrong.
    const { sim, kiter } = scene();
    const shooter = mk(sim, 2, ARCHER, "arbalester");
    shooter.x = 500; shooter.y = 300;
    kiter.takeDamage(5, shooter);
    assert.equal(kiter.contactBreakFrom, null);
});

ctest("[C2a] a MELEE victim never latches a break -- melee-vs-melee cannot move", () => {
    const sim = newSim();
    const victim = mk(sim, 1, MELEE, "champion");
    const hitter = mk(sim, 2, MELEE, "champion");
    victim.x = 400; victim.y = 300;
    hitter.x = 420; hitter.y = 300;
    victim.takeDamage(5, hitter);
    assert.equal(victim.contactBreakFrom, null);
});

ctest("[C2a] a SIEGE victim never latches a break -- min-range units are excluded", () => {
    // Same clause and same reason as kiteSteering's gate 2: Siege Onager (3.0)
    // and Heavy Scorpion (2.0) run tooClose(), not a kite circuit.
    const { kiter, hitter } = scene({ kiterStats: SIEGE });
    assert.ok(kiter.minAttackRange > 0, "fixture: the victim really is siege");
    kiter.takeDamage(5, hitter);
    assert.equal(kiter.contactBreakFrom, null);
});

ctest("[C2a] a 0-damage application is not a hit", () => {
    const { kiter, hitter } = scene();
    kiter.takeDamage(0, hitter);
    assert.equal(kiter.contactBreakFrom, null);
});

ctest("[C2a] a killing blow latches nothing on the corpse", () => {
    const { kiter, hitter } = scene();
    kiter.takeDamage(kiter.currentHp + 10, hitter);
    assert.equal(kiter.state, "dead", "fixture: the blow really killed it");
    assert.equal(kiter.contactBreakFrom, null);
});

ctest("[C2a] a later hitter supersedes the earlier one", () => {
    // The tape's kiter answers the unit that just hit it, present tense. No
    // queue and no priority between hitters -- the latest contact is the one
    // being broken.
    const { sim, kiter, hitter } = scene();
    const second = mk(sim, 2, MELEE, "champion");
    second.x = 400; second.y = 318;
    kiter.takeDamage(5, hitter);
    kiter.takeDamage(5, second);
    assert.equal(kiter.contactBreakFrom, second);
});

ctest("[C2a] with contactBreak off nothing is ever recorded", () => {
    withC2A(ALL_OFF, () => {
        const { kiter, hitter } = scene();
        kiter.takeDamage(5, hitter);
        assert.equal(kiter.contactBreakFrom, null, "no bookkeeping on the off path");
        assert.equal(kiter.contactBreakHitter(), null);
    });
});

// ---- 2. the bearing --------------------------------------------------------

ctest("[C2a] THE BEARING: the kiter runs away from the HITTER, not from its target", () => {
    // The defect's exact shape. The kiter's own target sits to the NORTH while
    // the unit that hit it stands to the EAST: pre-C2 the retreat basis is the
    // per-target radial (or E10a's centroid), so the kiter runs north and opens
    // no separation at all from the body in contact with it.
    const sim = newSim();
    const kiter = mk(sim, 1, ARCHER, "arbalester");
    const far = mk(sim, 2, MELEE, "champion");
    const hitter = mk(sim, 2, MELEE, "champion");
    kiter.x = 400; kiter.y = 300;
    far.x = 400; far.y = 300 - 6 * TILE_SIZE;      // north, out of contact
    hitter.x = 400 + 20; hitter.y = 300;           // east, touching
    kiter.target = far;

    const x0 = kiter.x, y0 = kiter.y;
    kiter.takeDamage(5, hitter);
    kiter.moveAwayFromTarget(DT, [kiter, far, hitter], null);
    const mx = kiter.x - x0, my = kiter.y - y0;
    const mlen = Math.hypot(mx, my);
    assert.ok(mlen > 0, "it moved");
    // Cosine with "straight away from the hitter" == -x here.
    const cos = -mx / mlen;
    assert.ok(cos > 0.9, `runs away from the hitter (cos ${cos.toFixed(3)})`);

    // Without the rule the same scene runs the other way -- away from `far`,
    // i.e. SOUTH, which leaves the hitter exactly where it was.
    withC2A(ALL_OFF, () => {
        const s2 = newSim();
        const k2 = mk(s2, 1, ARCHER, "arbalester");
        const f2 = mk(s2, 2, MELEE, "champion");
        const h2 = mk(s2, 2, MELEE, "champion");
        k2.x = 400; k2.y = 300;
        f2.x = 400; f2.y = 300 - 6 * TILE_SIZE;
        h2.x = 420; h2.y = 300;
        k2.target = f2;
        k2.takeDamage(5, h2);
        k2.moveAwayFromTarget(DT, [k2, f2, h2], null);
        const cos2 = -(k2.x - 400) / Math.hypot(k2.x - 400, k2.y - 300);
        assert.ok(cos2 < 0.5,
            `pre-C2 the bearing ignores the hitter (cos ${cos2.toFixed(3)})`);
    });
});

ctest("[C2a] the break's bearing supersedes E10a's shared centroid basis", () => {
    // `steering.rx/ry` is E10a's one-bearing-per-side retreat basis. Hand it a
    // basis pointing NORTH while the hitter stands EAST: the break wins.
    const { kiter, hitter, sim } = scene({ hitterAt: 20 });
    kiter.takeDamage(5, hitter);
    const x0 = kiter.x, y0 = kiter.y;
    kiter.moveAwayFromTarget(DT, [kiter, hitter], { x: 0, y: 0, rx: 0, ry: -1 });
    const cos = -(kiter.x - x0) / Math.hypot(kiter.x - x0, kiter.y - y0);
    assert.ok(cos > 0.9, `hitter-away wins over the centroid basis (cos ${cos.toFixed(3)})`);
    assert.ok(sim);

    // ...and the moment the break ends, the shared basis is back. No blend, no
    // fade: E10a is superseded, not weakened.
    kiter.contactBreakFrom = null;
    const x1 = kiter.x, y1 = kiter.y;
    kiter.moveAwayFromTarget(DT, [kiter, hitter], { x: 0, y: 0, rx: 0, ry: -1 });
    assert.ok(kiter.y - y1 < 0, "back to the centroid basis (north)");
    assert.ok(Math.abs(kiter.x - x1) < Math.abs(kiter.y - y1));
});

ctest("[C2a] cohesion and orbit are still added on top of the break's bearing", () => {
    // The break replaces the RADIAL BASIS only. If it also swallowed
    // steering.x/y the kiting ball would stop being a ball for as long as any
    // of its members were in contact, which is not what M2 measured.
    const { kiter, hitter } = scene({ hitterAt: 20 });
    kiter.takeDamage(5, hitter);
    const x0 = kiter.x, y0 = kiter.y;
    // A strong southward group term against a westward break bearing: the
    // result must be neither pure west nor pure south.
    kiter.moveAwayFromTarget(DT, [kiter, hitter], { x: 0, y: 1, rx: 0, ry: 0 });
    const mx = kiter.x - x0, my = kiter.y - y0;
    assert.ok(mx < 0, "the break's westward bearing is still in there");
    assert.ok(my > 0, "and so is the group term");
});

// ---- 3. the priority -------------------------------------------------------

// A kiter with its cooldown up and a chaser inside its reach: the pre-C2 engine
// parks and shoots (R5B-D1's launch test is the first thing the ranged branch
// asks). This is the modal post-hit tick C1 M2 measured.
function stopToFireScene() {
    const sim = newSim();
    const kiter = mk(sim, 1, ARCHER, "arbalester");
    const hitter = mk(sim, 2, MELEE, "champion");
    kiter.x = 400; kiter.y = 300;
    hitter.x = 400 + 20; hitter.y = 300;
    kiter.target = hitter;
    hitter.target = kiter;
    kiter.attackCooldown = 0;
    kiter.fireRecovery = 0;
    kiter.hasAcquiredTarget = true;
    return { sim, kiter, hitter };
}

ctest("[C2a] pre-C2 a kiter in this scene STOPS TO FIRE -- or the test proves nothing", () => {
    withC2A(ALL_OFF, () => {
        const { sim, kiter, hitter } = stopToFireScene();
        assert.ok(kiter.inRange(), "fixture: the chaser is inside the kiter's reach");
        const x0 = kiter.x;
        kiter.update(DT, [kiter, hitter], sim.team2);
        assert.equal(kiter.state, "attacking");
        assert.equal(kiter.x, x0, "it did not move at all");
    });
});

ctest("[C2a] THE PRIORITY: a live break beats stop-to-fire, and the unit leaves at once", () => {
    const { sim, kiter, hitter } = stopToFireScene();
    kiter.takeDamage(5, hitter);
    const x0 = kiter.x;
    kiter.update(DT, [kiter, hitter], sim.team2);
    assert.equal(kiter.state, "kiting", "retreating outranks the shot");
    assert.ok(kiter.x < x0, "and it is already moving on the very next tick");
    assert.equal(kiter.committedAttack, null, "no windup was started");
});

ctest("[C2a] breakPriority alone is what does that -- C-a1 without it still fires", () => {
    withC2A(BEARING_ONLY, () => {
        const { sim, kiter, hitter } = stopToFireScene();
        kiter.takeDamage(5, hitter);
        const x0 = kiter.x;
        kiter.update(DT, [kiter, hitter], sim.team2);
        assert.equal(kiter.state, "attacking", "the bearing rule does not reorder the chain");
        assert.equal(kiter.x, x0);
    });
});

ctest("[C2a] the break also beats the RE-APPROACH arm -- it never walks at its hitter", () => {
    // Cooldown up, chaser just outside reach: pre-C2 the unit walks TOWARD it
    // (rangedShouldApproach). That is the other half of the 0.42 s latency.
    const sim = newSim();
    const kiter = mk(sim, 1, ARCHER, "arbalester");
    const hitter = mk(sim, 2, MELEE, "champion");
    kiter.x = 400; kiter.y = 300;
    hitter.x = 400 + 9 * TILE_SIZE; hitter.y = 300;   // outside reach (7 tiles)
    kiter.target = hitter;
    kiter.attackCooldown = 0;
    assert.ok(!kiter.inRange(), "fixture: out of reach, so the approach arm is next");

    // Hit from close range by a SECOND melee unit while the walk is on.
    const toucher = mk(sim, 2, MELEE, "champion");
    toucher.x = 400 + 20; toucher.y = 300;
    kiter.takeDamage(5, toucher);
    const x0 = kiter.x;
    kiter.update(DT, [kiter, hitter, toucher], sim.team2);
    assert.equal(kiter.state, "kiting");
    assert.ok(kiter.x < x0, "it retreats instead of closing on the distant target");
});

ctest("[C2a] the priority does not override a committed windup or the fire recovery", () => {
    // Stated as a limit, not an omission: those two are E9-measured commitments
    // of an animation already in flight and are shared with the ranged round.
    const { sim, kiter, hitter } = stopToFireScene();
    kiter.takeDamage(5, hitter);
    kiter.fireRecovery = 0.3;
    const x0 = kiter.x;
    kiter.update(DT, [kiter, hitter], sim.team2);
    assert.equal(kiter.state, "attacking");
    assert.equal(kiter.x, x0, "recovery still freezes the unit");
});

// ---- 4. the end condition --------------------------------------------------

ctest("[C2a] THE ESCAPE: the break holds up to reach + one body diameter, then ends", () => {
    const { kiter, hitter } = scene();
    kiter.takeDamage(5, hitter);
    const d = escapeDist(kiter, hitter);

    hitter.x = kiter.x + d - 0.5;
    assert.equal(kiter.contactBreakHitter(), hitter, "just inside: still breaking");

    hitter.x = kiter.x + d + 0.5;
    assert.equal(kiter.contactBreakHitter(), null, "past it: normal kiting resumes");
    assert.equal(kiter.contactBreakFrom, null, "and the latch drops itself");
});

ctest("[C2a] the escape distance is the HITTER's reach, not the kiter's", () => {
    // A kiter with 7 tiles of range escaping a 0-range champion must not have
    // to travel its OWN reach to do it. The criterion is what the hitter can
    // touch, plus the fleeing body's own width.
    const { kiter, hitter } = scene();
    const d = escapeDist(kiter, hitter);
    assert.ok(d < 2 * TILE_SIZE,
        `escape is a contact-scale distance, got ${(d / TILE_SIZE).toFixed(2)} tiles`);
    assert.ok(d > hitter.attackRange + hitter.radius + kiter.radius,
        "and it is strictly outside what the hitter can reach");
});

ctest("[C2a] the break is not a timer -- it survives arbitrarily many ticks in contact", () => {
    const { sim, kiter, hitter } = scene();
    kiter.takeDamage(5, hitter);
    for (let i = 0; i < 600; i++) {
        // Pin the pair in contact: the criterion is a distance, so as long as
        // the distance holds the break must hold, for any number of ticks.
        kiter.x = 400; kiter.y = 300;
        hitter.x = 420; hitter.y = 300;
        assert.equal(kiter.contactBreakHitter(), hitter, `tick ${i}`);
    }
    assert.ok(sim);
});

ctest("[C2a] the break dies with its cause when the hitter dies", () => {
    const { kiter, hitter } = scene();
    kiter.takeDamage(5, hitter);
    hitter.state = "dead";
    assert.equal(kiter.contactBreakHitter(), null);
    assert.equal(kiter.contactBreakFrom, null);
});

ctest("[C2a] a re-hit after an escape re-arms the break", () => {
    const { kiter, hitter } = scene();
    kiter.takeDamage(5, hitter);
    hitter.x = kiter.x + 400;
    assert.equal(kiter.contactBreakHitter(), null);
    hitter.x = kiter.x + 20;
    assert.equal(kiter.contactBreakHitter(), null, "distance alone does not re-arm it");
    kiter.takeDamage(5, hitter);
    assert.equal(kiter.contactBreakHitter(), hitter, "a new HIT does");
});

// ---- 5. off-switch, blast radius, purity -----------------------------------

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

// The fight this rule is FOR: melee chasing ranged. The chaser is deliberately
// tanky (the corpus's champion/halberdier vs cav-archer families are exactly
// this shape) so that it actually LANDS hits -- with the stock ARCHER fixture
// eight arbalesters wipe eight champions before a single blow connects, and the
// rule would then be trivially "identical" for the wrong reason.
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

ctest("[C2a] off is deterministic and DIFFERS from the armed engine on a chase", () => {
    const offA = withC2A(ALL_OFF, () => runHash(chaseFight, 42));
    const offB = withC2A(ALL_OFF, () => runHash(chaseFight, 42));
    assert.equal(offA, offB, "the off path must be deterministic");
    const on = runHash(chaseFight, 42);
    assert.notEqual(
        on, offA,
        "the rule must actually reach a melee-chasing-ranged fight, or this proves nothing",
    );
});

ctest("[C2a] on is deterministic across repeated runs", () => {
    assert.equal(runHash(chaseFight, 7), runHash(chaseFight, 7));
    assert.equal(runHash(chaseFight, 8, 45), runHash(chaseFight, 8, 45));
});

ctest("[C2a] a RANGED-vs-RANGED fight is bit-identical with the flags on and off", () => {
    // BY CONSTRUCTION, not by a scope test: the trigger is a melee hit and
    // these fights contain no melee unit. This is the unit-level counterpart of
    // the hash check over the six ranged corpus fights.
    for (const seed of [3, 11, 29]) {
        const on = runHash(archerFight, seed, ARCHER_FIGHT_SECONDS);
        const off = withC2A(ALL_OFF, () => runHash(archerFight, seed, ARCHER_FIGHT_SECONDS));
        assert.equal(on, off, `ranged seed ${seed} must not move`);
    }
});

ctest("[C2a] a MELEE-vs-MELEE fight is bit-identical with the flags on and off", () => {
    // The rule lives on a ranged unit's reaction; a melee victim never latches.
    for (const seed of [5, 13, 31]) {
        const on = runHash(meleeFight, seed, 30);
        const off = withC2A(ALL_OFF, () => runHash(meleeFight, seed, 30));
        assert.equal(on, off, `melee seed ${seed} must not move`);
    }
});

ctest("[C2a] a SIEGE-vs-melee fight is bit-identical with the flags on and off", () => {
    for (const seed of [2, 17]) {
        const on = runHash(siegeFight, seed, 30);
        const off = withC2A(ALL_OFF, () => runHash(siegeFight, seed, 30));
        assert.equal(on, off, `siege seed ${seed} must not move`);
    }
});

ctest("[C2a] the rule consumes no randomness", () => {
    let draws = 0;
    const inner = makeRng(1);
    const rng = {
        next() { draws++; return inner.next(); },
        getState() { return inner.getState(); },
    };
    const sim = new Simulation(900, 600, rng);
    const kiter = mk(sim, 1, ARCHER, "arbalester");
    const hitter = mk(sim, 2, MELEE, "champion");
    kiter.x = 400; kiter.y = 300;
    hitter.x = 420; hitter.y = 300;
    kiter.target = hitter;
    kiter.takeDamage(5, hitter);
    assert.equal(kiter.contactBreakHitter(), hitter, "fixture: the break really is live");
    kiter.moveAwayFromTarget(DT, [kiter, hitter], null);
    kiter.contactBreakHitter();
    assert.equal(draws, 0, "contact break is geometry, never a draw");
});

ctest("[C2a] contactBreakHitter is idempotent -- calling it twice changes nothing", () => {
    const { kiter, hitter } = scene();
    kiter.takeDamage(5, hitter);
    assert.equal(kiter.contactBreakHitter(), hitter);
    assert.equal(kiter.contactBreakHitter(), hitter);
    hitter.x = kiter.x + 400;
    assert.equal(kiter.contactBreakHitter(), null);
    assert.equal(kiter.contactBreakHitter(), null);
});
