// Phase C2-B — the melee swing: when it may begin, when it lands.
//
// Two rules, both from docs/calibration/c1_chaser_cadence.md §M3, neither
// carrying a constant:
//
//   C-b STOP-TO-SWING. A melee swing may not BEGIN on a tick the unit spent
//       walking. Tape: a hit landed while both parties were moving is
//       0.0000/chaser-second in EVERY ONE of the 29 melee-chases-ranged
//       families (the tape chaser's own step at the instant its blow lands is
//       0.000 tiles, everywhere); the engine takes 19.8% of its hits that way.
//
//   C-c WINDUP-COMMIT. Reach is tested once, at swing START; the blow lands on
//       a LIVING victim however far it drifted. Tape: hits resolve at 1.43x the
//       attacker's own reach, the engine at 0.99x -- it applies damage exactly
//       at the inRange() boundary and never past it. E15c §2 saw the same thing
//       inside melee scrums: 7.46% of tape samples are a unit already LANDING
//       HITS on a victim it stands 0-0.5 tiles outside reach of, against 0.31%
//       in the engine.
//
// The groups below are:
//   1. shipped configuration and the setter's contract;
//   2. C-b: halt-then-swing, and the RE-TEST that makes it a rule rather than a
//      delay (a victim that leaves during the halt escapes the swing);
//   3. C-b: who does NOT pay -- the unit that closed early and stood, and the
//      unit that was merely shoved by the collision resolver;
//   4. C-c: a committed swing lands on a drifted victim. INCLUDING the half
//      that is already the engine's behaviour with the flag OFF (frame_delay >
//      0), pinned so a later round cannot delete it by accident;
//   5. C-c: the frame_delay-0 scope decision, pinned with its honest limit;
//   6. off-switch and ranged bit-identity.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    C2B,
    setC2B,
} from "../../../apps/website/static/js/engine/constants.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const DT = 1 / 60;
const ALL_OFF = { stopToSwing: false, committedSwingLands: false };
const ALL_ON = { stopToSwing: true, committedSwingLands: true };
const B_ONLY = { stopToSwing: true, committedSwingLands: false };
const C_ONLY = { stopToSwing: false, committedSwingLands: true };

function withC2B(overrides, fn) {
    const saved = { ...C2B };
    setC2B(overrides);
    try {
        return fn();
    } finally {
        setC2B(saved);
    }
}

function stats(o = {}) {
    return {
        hp: o.hp ?? 100,
        attack: o.attack ?? 10,
        attack_range: o.range ?? 0,
        attack_speed: o.attackSpeed ?? 0.5,
        attack_delay: o.delay ?? 0,
        movement_speed: o.speed ?? 1.4,
        melee_armor: 0,
        pierce_armor: 0,
        outline_size: 0.4,
        collision_size: 0.25,
        accuracy: 100,
        unit_name: "U",
        is_ranged: o.isRanged ?? false,
    };
}

let nextId = 0;
function mk(sim, team, o = {}) {
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, stats(o), o.slug || "u", "Chinese", sim,
    );
    u.x = o.x ?? 300;
    u.y = o.y ?? 300;
    (team === 1 ? sim.team1 : sim.team2).push(u);
    return u;
}

function newSim(seed = 1) {
    return new Simulation(900, 600, makeRng(seed));
}

// Reach exactly as inRange() computes it, so a fixture can be placed a known
// fraction of it away without duplicating the formula's terms.
const reachOf = (a, v) => a.attackRange + a.radius + v.radius;

// A duel driven by update() alone -- no Simulation.update, so nothing steers,
// collides or re-targets behind the test's back and each tick's decision is the
// melee branch's own. The caller places the bodies each tick.
function duel({ delay = 0, hp = 5000, gap } = {}) {
    const sim = newSim();
    const a = mk(sim, 1, { delay, x: 300, y: 300 });
    const v = mk(sim, 2, { hp, x: 300, y: 300 });
    a.target = v;
    v.target = a;
    const reach = reachOf(a, v);
    v.x = 300 + (gap ?? reach - 1);
    const tick = () => {
        sim.battleTime += DT;
        a.update(DT, [a, v], [v]);
    };
    return { sim, a, v, reach, tick };
}

// ---- 1. shipped configuration ----------------------------------------------

test("[C2B] both rules ship OFF, and the object has exactly two flags", () => {
    assert.equal(C2B.stopToSwing, false);
    assert.equal(C2B.committedSwingLands, false);
    assert.equal(Object.keys(C2B).length, 2);
});

test("[C2B] setC2B rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setC2B({ notARule: true }), /unknown flag/);
});

// ---- 2. C-b: halt, then swing ----------------------------------------------

test("[C-b] a melee unit that walked into reach halts instead of swinging out of the step", () => {
    withC2B(B_ONLY, () => {
        const sim = newSim();
        const a = mk(sim, 1, { x: 300, y: 300, speed: 1.4 });
        const v = mk(sim, 2, { x: 340, y: 300, hp: 5000 });
        a.target = v;
        const reach = reachOf(a, v);

        // Walk it in under its own locomotion until it is in reach.
        let ticks = 0;
        while (!a.inRange() && ticks++ < 600) {
            sim.battleTime += DT;
            a.update(DT, [a, v], [v]);
        }
        assert.ok(a.inRange(), "fixture: the attacker reached its victim");
        assert.equal(a.meleeWasMoving, true, "fixture: it arrived by walking");
        assert.equal(a.attackCooldown, 0, "fixture: its cooldown is ready");

        const hpBefore = v.currentHp;
        sim.battleTime += DT;
        a.update(DT, [a, v], [v]);          // the HALT tick
        assert.equal(v.currentHp, hpBefore, "no blow lands out of the step");
        assert.equal(a.meleeWasMoving, false, "it has come to a stop");

        sim.battleTime += DT;
        a.update(DT, [a, v], [v]);          // the SWING tick
        assert.ok(v.currentHp < hpBefore, "the swing lands from the stop");
    });
});

test("[C-b] with the rule off the same arrival swings in the very same tick", () => {
    withC2B(ALL_OFF, () => {
        const sim = newSim();
        const a = mk(sim, 1, { x: 300, y: 300, speed: 1.4 });
        const v = mk(sim, 2, { x: 340, y: 300, hp: 5000 });
        a.target = v;
        let ticks = 0;
        while (!a.inRange() && ticks++ < 600) {
            sim.battleTime += DT;
            a.update(DT, [a, v], [v]);
        }
        const hpBefore = v.currentHp;
        sim.battleTime += DT;
        a.update(DT, [a, v], [v]);
        assert.ok(v.currentHp < hpBefore, "base engine swings out of the step");
    });
});

test("[C-b] THE RE-TEST: a victim that leaves during the halt escapes the swing", () => {
    // This is the rule's whole content -- not the tick of delay, but that reach
    // is asked AGAIN once the unit has stopped. C1 M1: the tape's chaser is in
    // reach for 0.66 s of its cycle against the engine's 1.81.
    withC2B(B_ONLY, () => {
        const { a, v, reach, tick } = duel();
        a.meleeWasMoving = true;            // it arrived walking
        const hpBefore = v.currentHp;
        tick();                             // HALT
        assert.equal(v.currentHp, hpBefore);
        v.x = a.x + reach + 4;              // the kiter is gone
        tick();                             // would-be SWING tick
        assert.equal(v.currentHp, hpBefore, "the escaped victim is not hit");
        assert.equal(a.state, "moving", "the chaser goes back to closing");
    });
});

// ---- 3. C-b: who does not pay ----------------------------------------------

// Ticks from the opening (never-stepped) swing to the NEXT landing, for a
// planted duellist. `shoveAt` optionally runs the collision resolver on the
// given tick so the attacker is physically displaced without ever choosing to
// walk. Compared between configurations rather than against a hand-counted
// reload, so float residue in reloadTime / DT cannot decide a test.
function ticksToSecondHit(cfg, { shoveAt = null } = {}) {
    return withC2B(cfg, () => {
        const { a, v, sim, tick } = duel({ delay: 0 });
        tick();                             // opening swing (never stepped)
        const hp1 = v.currentHp;
        assert.ok(hp1 < v.maxHp, "fixture: the opening blow landed");
        let shoved = false;
        for (let i = 1; i <= 600; i++) {
            if (shoveAt === i) {
                const ally = mk(sim, 1, { x: a.x + 2, y: a.y });
                const xBefore = a.x;
                sim.resolveCollisions([a, v, ally]);
                assert.notEqual(a.x, xBefore, "fixture: the resolver moved it");
                assert.equal(a.meleeWasMoving, false, "a shove is not a step");
                shoved = true;
            }
            tick();
            if (v.currentHp < hp1) {
                assert.ok(shoveAt === null || shoved, "fixture: the shove happened");
                return i;
            }
        }
        throw new Error("no second hit inside 600 ticks");
    });
}

test("[C-b] a unit that closed early and stood out its reload pays nothing", () => {
    // The melee twin of R5b's §1b finding: the pre-swing halt is for coming to
    // a stop, and a unit that is already stopped when its cooldown expires owes
    // nothing. In a scrum this is EVERY unit (E15c: engaged melee units are
    // planted, p90 displacement 0.0 tiles), which is why melee-vs-melee must
    // barely move under this rule.
    const off = ticksToSecondHit(ALL_OFF);
    assert.equal(ticksToSecondHit(B_ONLY), off,
        "a planted duellist's cadence is not touched by C-b, not even by a tick");
});

test("[C-b] a unit SHOVED by the collision resolver has not 'moved' and still swings", () => {
    // The rule reads the unit's own locomotion decision, never its measured
    // displacement -- C1 M3 separates walking (cStep 0.046-0.24 tiles) from
    // body jitter with exactly this distinction.
    const off = ticksToSecondHit(ALL_OFF);
    assert.equal(ticksToSecondHit(B_ONLY, { shoveAt: 5 }), off,
        "being pushed around does not cost the shoved unit its swing");
});

// ---- 4. C-c: a committed swing lands ---------------------------------------

test("[C-c] ALREADY TRUE WITH THE FLAG OFF: a frame_delay>0 swing lands on a drifted victim", () => {
    // Pinned deliberately. The committedAttack branch has never re-tested reach
    // at the landing, so every paladin / camel / hussar / elephant in the
    // corpus already commits at contact and resolves on schedule. C2B does not
    // relax this -- it only extends it to frame_delay-0 units -- and a later
    // round must not delete the property by accident.
    withC2B(ALL_OFF, () => {
        const { a, v, reach, tick } = duel({ delay: 0.4 });
        tick();
        assert.ok(a.committedAttack, "fixture: the windup started");
        v.x = a.x + reach * 26;             // far outside any reading of reach
        const hpBefore = v.currentHp;
        for (let i = 0; i < 120 && a.committedAttack; i++) tick();
        assert.ok(v.currentHp < hpBefore, "the committed blow lands anyway");
        assert.ok(!a.inRange(), "and it landed with the victim out of reach");
    });
});

test("[C-c] a committed swing does NOT land on a victim that died during the windup", () => {
    // The one thing the landing DOES ask. A second living enemy is present so
    // update() keeps running (a unit with no living foe at all returns early and
    // never resolves anything -- pre-existing, and not this rule's business).
    for (const cfg of [ALL_OFF, ALL_ON]) {
        withC2B(cfg, () => {
            const sim = newSim();
            const a = mk(sim, 1, { delay: 0.4, x: 300, y: 300 });
            const v = mk(sim, 2, { hp: 5000, x: 300, y: 300 });
            const other = mk(sim, 2, { hp: 5000, x: 800, y: 300 });
            v.x = 300 + reachOf(a, v) - 1;
            a.target = v;
            const tick = () => {
                sim.battleTime += DT;
                a.update(DT, [a, v, other], [v, other]);
            };
            tick();
            assert.ok(a.committedAttack, "fixture: the windup started");
            v.state = "dead";
            for (let i = 0; i < 120 && a.committedAttack; i++) tick();
            assert.equal(a.committedAttack, null, "the swing resolved");
            assert.equal(v.currentHp, v.maxHp, "a corpse takes no damage");
        });
    }
});

// ---- 5. C-c: the frame_delay-0 scope decision ------------------------------

test("[C-c] a frame_delay-0 swing gains exactly ONE tick of commit -- no constant", () => {
    // The scope decision, pinned. attack_delay IS the dat's own damage frame
    // (extract_units.py:471, frame_delay / 60) and it is 0 for champion and
    // halberdier, so nothing in the data licenses a duration for their swing.
    // What the engine can honestly give it is its smallest resolvable interval,
    // one tick -- and the test asserts it is ONE, not a fitted number.
    withC2B(C_ONLY, () => {
        const { a, v, tick } = duel({ delay: 0 });
        const hpBefore = v.currentHp;
        tick();
        assert.ok(a.committedAttack, "the swing is committed, not resolved");
        assert.equal(a.committedAttack.timeLeft, 0, "the interval is the tick itself");
        assert.equal(a.committedAttack.zeroDelay, true);
        assert.equal(v.currentHp, hpBefore, "nothing has landed yet");
        tick();
        assert.ok(v.currentHp < hpBefore, "and it lands on the very next tick");
        assert.equal(a.committedAttack, null);
    });
});

test("[C-c] that one tick is enough for a drifted frame_delay-0 victim to be hit anyway", () => {
    withC2B(C_ONLY, () => {
        const { a, v, reach, tick } = duel({ delay: 0 });
        const hpBefore = v.currentHp;
        tick();                             // commit at reach
        v.x = a.x + reach * 3;              // drift out during the tick
        tick();                             // lands regardless
        assert.ok(v.currentHp < hpBefore, "reach was tested at the swing START");
        assert.ok(!a.inRange());
    });
});

test("[C-c] the reload is untouched: hit-to-hit is still exactly reloadTime", () => {
    // The rule moves WHICH TICK the blow lands on, not how often a unit swings.
    withC2B(C_ONLY, () => {
        const { a, v, tick } = duel({ delay: 0 });
        tick(); tick();                     // commit + land
        assert.ok(Math.abs(a.attackCooldown - a.reloadTime) < 1e-9,
            "the post-swing cooldown is the full reload");
    });
});

test("[C-c] an extra-strike melee unit keeps every strike -- the zero-delay arm uses performAttack", () => {
    // performAttackOn() lands ONE blow; performAttack() lands 1 + extra. Routing
    // frame_delay-0 units through the committed branch must not silently halve
    // a multi-strike melee unit's output.
    const run = (cfg) => withC2B(cfg, () => {
        const sim = newSim();
        const a = mk(sim, 1, { delay: 0, x: 300, y: 300 });
        a.extraProjectiles = 2;             // 3 strikes per swing
        const v = mk(sim, 2, { hp: 5000, x: 300 + reachOf(a, a) - 1, y: 300 });
        a.target = v;
        v.target = a;
        for (let i = 0; i < 3; i++) {
            sim.battleTime += DT;
            a.update(DT, [a, v], [v]);
        }
        return v.maxHp - v.currentHp;
    });
    assert.ok(run(ALL_OFF) > 0, "fixture: the base engine lands something");
    assert.equal(run(C_ONLY), run(ALL_OFF),
        "the same swing delivers the same total damage, one tick later");
});

// ---- 6. off-switch and ranged identity -------------------------------------

const MELEE = {
    hp: 70, attack: 12, attack_range: 0, attack_speed: 1.8,
    attack_delay: 0, movement_speed: 0.9, melee_armor: 1,
    pierce_armor: 1, outline_size: 0.2, accuracy: 100,
    unit_name: "Test Champion",
};
const ARCHER = {
    hp: 40, attack: 20, attack_range: 7, attack_speed: 2.0,
    projectile_speed: 7, accuracy: 100, movement_speed: 0.96,
    melee_armor: 0, pierce_armor: 0, outline_size: 0.2,
    unit_name: "Test Arbalester", is_ranged: true,
};

function scrumFight(seed, nA = 12, nB = 8) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < nA; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...MELEE }, "champion", "Franks", sim);
        u.x = 260 + (i % 3) * 18;
        u.y = 180 + Math.floor(i / 3) * 20;
        sim.team1.push(u);
    }
    for (let i = 0; i < nB; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...MELEE, attack_delay: 0.4 }, "paladin", "Goths", sim);
        u.x = 420 + (i % 2) * 16;
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

test("[C2B] the OFF path is the shipped default and is deterministic", () => {
    const a = withC2B(ALL_OFF, () => runHash(scrumFight, 42));
    const b = withC2B(ALL_OFF, () => runHash(scrumFight, 42));
    assert.equal(a, b);
    assert.equal(runHash(scrumFight, 42), a, "shipped default === all off");
});

test("[C2B] each rule ACTUALLY REACHES a melee scrum, or these tests prove nothing", () => {
    const off = withC2B(ALL_OFF, () => runHash(scrumFight, 42));
    for (const [name, cfg] of [["C-b", B_ONLY], ["C-c", C_ONLY], ["both", ALL_ON]]) {
        const on = withC2B(cfg, () => runHash(scrumFight, 42));
        assert.notEqual(on, off, `${name} must move a melee scrum`);
    }
});

test("[C2B] each rule is deterministic on its own", () => {
    for (const cfg of [B_ONLY, C_ONLY, ALL_ON]) {
        for (const seed of [7, 8]) {
            assert.equal(
                withC2B(cfg, () => runHash(scrumFight, seed)),
                withC2B(cfg, () => runHash(scrumFight, seed)),
            );
        }
    }
});

test("[C2B] a RANGED-vs-RANGED fight is bit-identical with both rules on and off", () => {
    // Both rules live inside update()'s MELEE arm, so the ranged corpus must not
    // move by so much as a float. Unit-level counterpart of the mixed-subset
    // hash panel in the round report.
    for (const seed of [3, 11, 29]) {
        const off = withC2B(ALL_OFF, () => runHash(archerFight, seed, 40));
        for (const cfg of [B_ONLY, C_ONLY, ALL_ON]) {
            assert.equal(
                withC2B(cfg, () => runHash(archerFight, seed, 40)), off,
                `ranged seed ${seed} must not move`,
            );
        }
    }
});

test("[C2B] with both rules off, meleeWasMoving is written but never read", () => {
    // The off-switch is bit-identical BY CONSTRUCTION, not merely by test: the
    // only new statement on the off path is bookkeeping into a field nothing
    // consults. This asserts the bookkeeping is live (so the on path is not
    // reading a dead flag) while the behaviour is not.
    withC2B(ALL_OFF, () => {
        const sim = newSim();
        const a = mk(sim, 1, { x: 300, y: 300, speed: 1.4 });
        const v = mk(sim, 2, { x: 400, y: 300, hp: 5000 });
        a.target = v;
        sim.battleTime += DT;
        a.update(DT, [a, v], [v]);
        assert.equal(a.meleeWasMoving, true, "the field tracks the walk");
        const hpBefore = v.currentHp;
        while (!a.inRange()) {
            sim.battleTime += DT;
            a.update(DT, [a, v], [v]);
        }
        sim.battleTime += DT;
        a.update(DT, [a, v], [v]);
        assert.ok(v.currentHp < hpBefore, "and it changes nothing");
    });
});
