// Phase B2 — the melee bump valve becomes reachable.
//
// E14 rule 2 (meleeBumpRetarget) is the release valve for a melee unit frozen
// on an unreachable target: bump into a different enemy and you switch to the
// one you bumped (AoE2:DE update 81058). B1's forensics
// (docs/calibration/b1_engagement_forensics.md §2b) measured that it never
// fires -- eligible on 0.2% of frozen ticks, 900 fires against 21 080
// stuck-bar trips -- and blamed the timing of its trigger
// `dist <= this.radius + enemy.radius + 1`, which is byte-for-byte the floor
// Simulation.resolveCollisions enforces at the END of every tick.
//
// B2 measured that and found the diagnosis one pixel off. The engine has TWO
// body floors: resolveCollisions' hard `radius + radius + 1` and
// calculateAvoidance's soft `radius + radius + 2`. The soft one is WIDER, so a
// cross-team pair pressed together settles against it and the hard pass never
// touches the pair at all -- consuming the hard pass's contact event instead
// of re-measuring its floor moves eligibility from 0.001 to 0.002, i.e. not at
// all. Contact is therefore the SOFT floor (the one that holds the standoff)
// plus the hard pass's contact event (for real overlaps). Neither is a new
// number.
//
// The tests below are in four groups:
//   1. the resolver records what it is supposed to record, and only that;
//   2. THE OLD BUG'S EXACT CASE -- a pair held at the soft floor, where the
//      pre-B2 rule froze, now bumps;
//   3. every other E14 gate is untouched (melee-vs-melee, target unreachable,
//      ranged never bumps, nearest wins);
//   4. off-switch: `B2.resolverContactBump = false` is bit-identical to the
//      pre-B2 engine, and a RANGED fight is bit-identical either way.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    B2,
    setB2,
} from "../../../apps/website/static/js/engine/constants.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const DT = 1 / 60;
const ALL_OFF = { resolverContactBump: false };

function withB2(overrides, fn) {
    const saved = { ...B2 };
    setB2(overrides);
    try {
        return fn();
    } finally {
        setB2(saved);
    }
}

function stats({ range = 0, isRanged = false, hp = 100 } = {}) {
    return {
        hp, attack: 10, attack_range: range, attack_speed: 0.5,
        movement_speed: 1.4, melee_armor: 0, pierce_armor: 0,
        outline_size: 0.4, collision_size: 0.25, accuracy: 100,
        unit_name: "U", is_ranged: isRanged,
    };
}

let nextId = 0;
function mk(sim, team, opts = {}) {
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, stats(opts), opts.slug || "u",
        "Chinese", sim,
    );
    (team === 1 ? sim.team1 : sim.team2).push(u);
    return u;
}

function newSim(seed = 1) {
    return new Simulation(900, 600, makeRng(seed));
}

// ---- shipped configuration -------------------------------------------------

test("[B2] the rule ships ON and carries exactly one flag", () => {
    assert.equal(B2.resolverContactBump, true);
    assert.equal(Object.keys(B2).length, 1);
});

test("[B2] setB2 rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setB2({ notARule: true }), /unknown flag/);
});

// ---- 1. what the resolver records ------------------------------------------

test("[B2] resolveCollisions records a cross-team pair it pushes apart", () => {
    const sim = newSim();
    const a = mk(sim, 1);
    const b = mk(sim, 2);
    a.x = 300; a.y = 300;
    b.x = 300 + a.radius + b.radius - 3; b.y = 300;   // overlapping
    sim.resolveCollisions([a, b]);
    assert.ok(a.bumpContacts.has(b), "the pusher records its victim");
    assert.ok(b.bumpContacts.has(a), "and the victim records the pusher");
});

test("[B2] a pair sitting EXACTLY on the floor is still recorded as touching", () => {
    // The floor is this pass's own fixed point: it drives every scrum to it and
    // then stops pushing. If "at the floor" did not count, the recorded set
    // would empty out the moment the crowd settled -- which is precisely the
    // state the valve has to fire in.
    const sim = newSim();
    const a = mk(sim, 1);
    const b = mk(sim, 2);
    a.x = 300; a.y = 300;
    b.x = 300 + a.radius + b.radius + 1; b.y = 300;   // == minDist
    sim.resolveCollisions([a, b]);
    assert.ok(a.bumpContacts.has(b));
    assert.ok(b.bumpContacts.has(a));
});

test("[B2] a pair OUTSIDE the hard floor is not recorded by the hard pass", () => {
    const sim = newSim();
    const a = mk(sim, 1);
    const b = mk(sim, 2);
    a.x = 300; a.y = 300;
    b.x = 300 + a.radius + b.radius + 2; b.y = 300;
    sim.resolveCollisions([a, b]);
    assert.equal(a.bumpContacts.size, 0);
    assert.equal(b.bumpContacts.size, 0);
});

test("[B2] SAME-team contact is never recorded -- a bump is an enemy event", () => {
    const sim = newSim();
    const a = mk(sim, 1);
    const ally = mk(sim, 1);
    a.x = 300; a.y = 300;
    ally.x = 300 + a.radius + ally.radius - 3; ally.y = 300;
    sim.resolveCollisions([a, ally]);
    assert.equal(a.bumpContacts.size, 0);
    assert.equal(ally.bumpContacts.size, 0);
});

test("[B2] the record is cleared at the top of every resolver call", () => {
    const sim = newSim();
    const a = mk(sim, 1);
    const b = mk(sim, 2);
    a.x = 300; a.y = 300;
    b.x = 300 + a.radius + b.radius - 3; b.y = 300;
    sim.resolveCollisions([a, b]);
    assert.ok(a.bumpContacts.has(b));
    // Walk them apart and resolve again: last tick's contact must not persist.
    b.x = 700;
    sim.resolveCollisions([a, b]);
    assert.equal(a.bumpContacts.size, 0, "contacts are per-tick, not cumulative");
});

test("[B2] three resolver passes over one pair record it once", () => {
    const sim = newSim();
    const a = mk(sim, 1);
    const b = mk(sim, 2);
    a.x = 300; a.y = 300;
    b.x = 300.5; b.y = 300;   // deeply overlapped: all three passes act
    sim.resolveCollisions([a, b]);
    assert.equal(a.bumpContacts.size, 1, "a Set, so pass count cannot leak in");
});

// ---- 2. the old bug's exact case -------------------------------------------

// The B1 anatomy, minimally: `a` is locked on `far` (well out of reach) and is
// pressed against `touching`, which it can hit right now. `gap` places
// `touching` that many px beyond the HARD floor -- the pre-B2 trigger's test.
function frozenScene(gap = 0) {
    const sim = newSim();
    const a = mk(sim, 1);
    const far = mk(sim, 2);
    const touching = mk(sim, 2);
    a.x = 300; a.y = 300;
    far.x = 300 + 5 * TILE_SIZE; far.y = 300;
    touching.x = 300 + a.radius + touching.radius + 1 + gap; touching.y = 300;
    a.target = far;
    return { sim, a, far, touching };
}

test("[B2] THE BUG: a pair held at the SOFT floor bumps, where pre-B2 froze", () => {
    // This is the measured steady state, not a contrived one: the soft
    // avoidance floor is radius+radius+2, one px outside the hard floor the
    // pre-B2 rule tested, so a pressed-together cross-team pair lives here and
    // nowhere else. B1 measured the gap at a median 1.0-1.7 px.
    const { sim, a, far, touching } = frozenScene(0.9);
    const hardGap = a.distanceTo(touching) - (a.radius + touching.radius + 1);
    const softGap = a.distanceTo(touching) - (a.radius + touching.radius + 2);
    assert.ok(hardGap > 0, `fixture: outside the HARD floor (${hardGap.toFixed(2)}px)`);
    assert.ok(softGap < 0, `fixture: inside the SOFT floor (${softGap.toFixed(2)}px)`);
    // The hard pass agrees it has nothing to do here -- so a resolver-event-only
    // fix would not have helped either. That is the B2 correction to B1, pinned.
    sim.resolveCollisions([a, far, touching]);
    assert.equal(a.bumpContacts.size, 0,
        "the hard pass never sees a pair the soft floor is holding");

    // Pre-B2 engine: the valve stays shut. This is the freeze.
    withB2(ALL_OFF, () => {
        a.target = far;
        a.meleeBumpRetarget(sim.team2);
        assert.equal(a.target, far, "pre-B2: the unit stays frozen on the far foe");
    });

    // B2: the soft floor is the engine's own "these bodies are pressed"
    // threshold, so the valve opens.
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, touching, "B2: retargets onto the body it is pressed against");
    assert.equal(a.stuckTimer, 0, "a bump is a fresh engagement");
});

test("[B2] a real overlap still bumps -- through the hard pass's contact event", () => {
    // Tick N's collision pass finds them overlapping and pushes them to the
    // hard floor; tick N+1 asks and gets a yes from the recorded event.
    const { sim, a, far, touching } = frozenScene(-4);   // overlapping
    sim.resolveCollisions([a, far, touching]);
    assert.ok(a.bumpContacts.has(touching), "the hard pass recorded the push");
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, touching);
});

test("[B2] the valve stays open across settled ticks -- the freeze cannot re-form", () => {
    // A pair at the soft floor is pushed by nothing and moves not at all. If
    // eligibility depended on a push having just happened, the fix would work
    // for one tick and then relapse; it must hold every tick.
    const { sim, a, far, touching } = frozenScene(0.9);
    for (let tick = 0; tick < 3; tick++) {
        sim.resolveCollisions([a, far, touching]);
        a.target = far;
        a.meleeBumpRetarget(sim.team2);
        assert.equal(a.target, touching, `tick ${tick}: valve still open`);
    }
});

test("[B2] an enemy outside BOTH floors does not trigger a bump", () => {
    const { sim, a, far, touching } = frozenScene(2);   // past hard AND soft
    sim.resolveCollisions([a, far, touching]);
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far, "standing near is not standing against");
});

test("[B2] a contact recorded last tick expires once the bodies separate", () => {
    const { sim, a, far, touching } = frozenScene(-4);
    sim.resolveCollisions([a, far, touching]);
    assert.ok(a.bumpContacts.has(touching));
    touching.x = 300 + 4 * TILE_SIZE;          // walked away
    sim.resolveCollisions([a, far, touching]);
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far, "no phantom bump off a stale contact");
});

// ---- 3. every other E14 gate is untouched ----------------------------------

test("[B2] a unit that CAN reach its target ignores the bodies it is pressed against", () => {
    const { sim, a, far, touching } = frozenScene(0.9);
    // Put `far` in reach WITHOUT putting it on the a-touching axis, so the
    // collision pass has no cascade to scatter and the fixture stays exactly
    // what it says it is.
    far.x = 300; far.y = 300 + a.radius + far.radius + 2;
    assert.ok(a.inRange(), "fixture: the held target really is reachable");
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far, "the reachable-target gate still declines the bump");
});

test("[B2] melee-vs-melee on both ends -- a chaser does not bump onto archers", () => {
    // Left unscoped this rule fires on every melee unit chasing archers and
    // took champion__vs__arbalester 6/6 -> 0/6 (E14). B2 widens WHEN a contact
    // counts, never WHOSE.
    const sim = newSim();
    const a = mk(sim, 1);
    const archer = mk(sim, 2, { range: 4, isRanged: true });
    const touching = mk(sim, 2, { range: 4, isRanged: true });
    a.x = 300; a.y = 300;
    archer.x = 300 + 8 * TILE_SIZE; archer.y = 300;
    touching.x = 300 + a.radius + touching.radius - 4; touching.y = 300;
    sim.resolveCollisions([a, archer, touching]);
    assert.ok(a.bumpContacts.has(touching), "the hard pass records it regardless");
    a.target = archer;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, archer, "pursuit is still the ranged round's business");
});

test("[B2] a RANGED unit never bump-retargets, however hard it is shoved", () => {
    const sim = newSim();
    const a = mk(sim, 1, { range: 4, isRanged: true });
    const far = mk(sim, 2);
    const touching = mk(sim, 2);
    a.x = 300; a.y = 300;
    far.x = 300 + 9 * TILE_SIZE; far.y = 300;
    touching.x = 300 + a.radius + touching.radius - 4; touching.y = 300;
    a.target = far;
    sim.resolveCollisions([a, far, touching]);
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far);
});

test("[B2] the NEAREST contacted enemy wins, whatever the array order", () => {
    // `nearer` is pushed onto team2 AFTER `touching`, so a first-match rule
    // would pick the wrong one.
    const { sim, a, far, touching } = frozenScene(0.9);
    const nearer = mk(sim, 2);
    nearer.x = 300; nearer.y = 300 + a.radius + nearer.radius + 0.5;
    assert.ok(a.distanceTo(nearer) < a.distanceTo(touching), "fixture: nearer is nearer");
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, nearer);
});

test("[B2] a dead contacted body is never retargeted onto", () => {
    const { sim, a, far, touching } = frozenScene(0.9);
    touching.state = "dead";
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far);
});

test("[B2] the rule consumes no randomness", () => {
    let draws = 0;
    const inner = makeRng(1);
    const rng = {
        next() { draws++; return inner.next(); },
        getState() { return inner.getState(); },
    };
    const sim = new Simulation(900, 600, rng);
    const a = mk(sim, 1);
    const far = mk(sim, 2);
    const touching = mk(sim, 2);
    a.x = 300; a.y = 300;
    far.x = 300 + 5 * TILE_SIZE; far.y = 300;
    touching.x = 300 + a.radius + touching.radius + 1.9; touching.y = 300;
    a.target = far;
    sim.resolveCollisions([a, far, touching]);
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, touching, "fixture: the bump really did fire");
    assert.equal(draws, 0, "contact loss comes from geometry, never from a draw");
});

// ---- 4. off-switch ---------------------------------------------------------

const MELEE = {
    hp: 70, attack: 12, attack_range: 0, attack_speed: 1.8,
    attack_delay: 0.4, movement_speed: 0.9, melee_armor: 1,
    pierce_armor: 1, outline_size: 0.2, accuracy: 100,
    unit_name: "Test Champion",
};
const ARCHER = {
    hp: 40, attack: 20, attack_range: 7, attack_speed: 2.0,
    projectile_speed: 7, accuracy: 100, movement_speed: 0.96,
    melee_armor: 0, pierce_armor: 0, outline_size: 0.2,
    unit_name: "Test Arbalester", is_ranged: true,
};

// Lopsided melee scrum -- the shape the defect lives in (B1: the two collapse
// families are the two most extreme count ratios in the corpus).
function scrumFight(seed, nBig = 14, nSmall = 5) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < nBig; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...MELEE }, "halberdier", "Franks", sim);
        u.x = 300 + (i % 3) * 18;
        u.y = 180 + Math.floor(i / 3) * 20;
        sim.team1.push(u);
    }
    for (let i = 0; i < nSmall; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...MELEE }, "paladin", "Goths", sim);
        u.x = 380 + (i % 2) * 16;
        u.y = 200 + i * 18;
        sim.team2.push(u);
    }
    return sim;
}

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

function runHash(build, seed, seconds = 30) {
    const sim = build(seed);
    for (let i = 0; i < 60 * seconds; i++) sim.update(DT);
    return sim.stateHash();
}

test("[B2] off is deterministic and DIFFERS from the shipped engine on a scrum", () => {
    const offA = withB2(ALL_OFF, () => runHash(scrumFight, 42));
    const offB = withB2(ALL_OFF, () => runHash(scrumFight, 42));
    assert.equal(offA, offB, "the off path must be deterministic");
    const on = runHash(scrumFight, 42);
    assert.notEqual(
        on, offA,
        "the rule must actually reach a melee scrum, or this test proves nothing",
    );
});

test("[B2] on is deterministic -- a Set-valued record cannot leak iteration order", () => {
    assert.equal(runHash(scrumFight, 7), runHash(scrumFight, 7));
    assert.equal(runHash(scrumFight, 8, 45), runHash(scrumFight, 8, 45));
});

test("[B2] a RANGED-vs-RANGED fight is bit-identical with the flag on and off", () => {
    // B2 lives behind meleeBumpRetarget's isRanged() gates on both ends, so the
    // ranged corpus must not move by so much as a float. This is the unit-level
    // counterpart of the 3-seed hash check over the ranged fight subset.
    for (const seed of [3, 11, 29]) {
        const on = runHash(archerFight, seed, 40);
        const off = withB2(ALL_OFF, () => runHash(archerFight, seed, 40));
        assert.equal(on, off, `ranged seed ${seed} must not move`);
    }
});

test("[B2] with the rule off the resolver records nothing at all", () => {
    withB2(ALL_OFF, () => {
        const sim = newSim();
        const a = mk(sim, 1);
        const b = mk(sim, 2);
        a.x = 300; a.y = 300;
        b.x = 300 + a.radius + b.radius - 3; b.y = 300;
        sim.resolveCollisions([a, b]);
        assert.equal(a.bumpContacts.size, 0, "no bookkeeping on the off path");
    });
});
