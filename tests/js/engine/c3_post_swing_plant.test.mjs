// C3 -- POST-SWING PLANT (docs/calibration/c3_chaser_pursuit_forensics.md §Q3,
// data/calibration/analysis/c3_chaser_pursuit.json).
//
// THE MEASUREMENT. The tape's melee chaser, after every LANDED swing on a
// ranged kiter, stands planted for a median 0.64-0.74 s -- five distinct
// chaser classes, six families, ZERO halts under 0.2 s anywhere -- while the
// E1-on engine's chasers halt 0.0 s. That halt is ~100 % of the kiter's
// per-reload escape, and `interval = max(reload, halt + re-close)` with the
// measured medians reproduces the tape's swing cycle in 5/6 families,
// including the halberdier control (reload 3.0 swallows the plant, so such
// fights must NOT change).
//
// THE RULE. With C3.postSwingPlant on, a MELEE unit that LANDS a swing on a
// RANGED victim may not MOVE for POST_SWING_PLANT_S (0.7 s, the centre of the
// measured 0.64-0.74 band). Movement only:
//   * the next swing is NOT delayed -- a victim still in reach at reload
//     expiry is hit at bare reloadTime (update()'s in-reach attack branch is
//     tested before the plant branch);
//   * windup/damage application is untouched -- the stamp happens at hit
//     RESOLUTION in performAttackOn, after the damage path is already
//     committed;
//   * melee victims never stamp the lock (C2B refuted a melee-vs-melee
//     plant), so melee-vs-melee is bit-identical with the flag on;
//   * ranged attackers never reach the stamp and are excluded by the
//     predicate besides.
//
// OFF-SWITCH. Flag off + MELEE_SWING_RECOVERY_S 0 short-circuits
// meleeMoveLocked() before it reads the stamp, and the stamp itself is behind
// `if (C3.postSwingPlant ...)` -- off is a no-op by construction, pinned by
// the defaults test below.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    C3,
    setC3,
    POST_SWING_PLANT_S,
    MELEE_SWING_RECOVERY_S,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Same arrow-wrap pattern as the other flag tests (e1_orbit_kite etc.):
// override, run, ALWAYS restore.
function withC3(cfg, fn) {
    const saved = { ...C3 };
    setC3(cfg);
    try {
        return fn();
    } finally {
        setC3(saved);
    }
}

const C3_ON = { postSwingPlant: true };

function simStub(rng) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: rng || makeRng(1),
    };
}

function stats({
    range = 0, isRanged = false, hp = 100, attack = 10, armors = null,
} = {}) {
    return {
        hp, attack, attack_range: range, attack_speed: 0.5,
        movement_speed: 1.4, melee_armor: 0, pierce_armor: 0,
        outline_size: 0.4, collision_size: 0.25, accuracy: 100,
        unit_name: "U", is_ranged: isRanged,
        armors_json: armors ? JSON.stringify(armors) : null,
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

// ---- shipped configuration ---------------------------------------------------

test("[C3] ships OFF, at the measured duration", () => {
    // OFF until the C3 iteration boards land -- flipping it changes every
    // melee-chases-ranged fight, so it goes through the same A/B gate
    // discipline as E1.orbitKite (whose knife edge it is the mechanism for).
    assert.equal(C3.postSwingPlant, false);
    // The duration is the centre of the tape's measured 0.64-0.74 s halt
    // band (five chaser classes) -- a tape quantity, never scoreboard-tuned.
    assert.equal(POST_SWING_PLANT_S, 0.7);
    // The C3 stamp is only ever additive on top of the (shipped-0) E15b
    // recovery; if that constant ever comes back nonzero, re-examine overlap.
    assert.equal(MELEE_SWING_RECOVERY_S, 0);
});

test("[C3] setC3 rejects unknown flags", () => {
    assert.throws(() => setC3({ nope: true }), /unknown flag/);
});

// ---- OFF is a no-op ------------------------------------------------------------

test("[C3 off] landing a swing on a RANGED victim writes no stamp", () => {
    const sim = simStub();
    const a = mk(sim, 1);
    const v = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;
    sim.battleTime = 8.5;

    a.performAttackOn(v);
    assert.equal(a.moveLockUntil, -Infinity, "no stamp while the flag is off");
    assert.equal(a.meleeMoveLocked(), false);
});

test("[C3 off] the predicate is inert even with a stray stamp", () => {
    // Belt-and-braces twin of the E15b off test: with the flag off AND
    // recovery 0 the predicate short-circuits before reading moveLockUntil.
    const sim = simStub();
    const a = mk(sim, 1);
    sim.battleTime = 8.5;
    a.moveLockUntil = sim.battleTime + POST_SWING_PLANT_S;
    assert.equal(a.meleeMoveLocked(), false);
});

// ---- the mechanism -------------------------------------------------------------

test("[C3] a landed swing on a RANGED victim locks movement for exactly 0.7 s", () => {
    withC3(C3_ON, () => {
        const sim = simStub();
        const a = mk(sim, 1);
        const v = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;
        sim.battleTime = 8.5;

        a.performAttackOn(v);
        assert.equal(a.moveLockUntil, 8.5 + POST_SWING_PLANT_S);
        assert.equal(a.meleeMoveLocked(), true, "locked at the landing");
        sim.battleTime = 8.5 + POST_SWING_PLANT_S - 1e-6;
        assert.equal(a.meleeMoveLocked(), true, "still locked just inside");
        sim.battleTime = 8.5 + POST_SWING_PLANT_S;
        assert.equal(a.meleeMoveLocked(), false,
            "strict <: released exactly at the boundary tick");
    });
});

test("[C3] a planted chaser does not walk while the escaped victim opens the gap", () => {
    // The scenario the rule exists for: the victim leaves reach the moment the
    // blow lands; the chaser must stand for the plant, then resume the chase.
    withC3(C3_ON, () => {
        const sim = simStub(makeRng(5));
        const a = mk(sim, 1);
        const v = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;

        a.target = v;
        a.hasAcquiredTarget = true;
        sim.battleTime = 10;
        a.performAttackOn(v);
        a.attackCooldown = a.reloadTime;
        v.x = 3 * TILE_SIZE; // the kiter is gone by the next tick

        const dt = 1 / 60;
        const x0 = a.x;
        // Inside the plant window: the chaser may not displace itself.
        for (let i = 0; i < Math.floor((POST_SWING_PLANT_S - 0.02) / dt); i++) {
            sim.battleTime += dt;
            a.update(dt, [a, v], sim.team2);
            assert.equal(a.x, x0, `no self-locomotion at t=${sim.battleTime}`);
            assert.notEqual(a.state, "moving");
        }
        // After it: honest full-speed pursuit resumes.
        for (let i = 0; i < 60; i++) {
            sim.battleTime += dt;
            a.update(dt, [a, v], sim.team2);
        }
        assert.ok(a.x > x0 + 0.5 * TILE_SIZE,
            `released and closing again (x ${x0} -> ${a.x})`);
        assert.equal(a.state, "moving");
    });
});

test("[C3] the plant does NOT delay the next swing when the victim stays in reach", () => {
    // The halberdier-control invariant: when reload swallows the plant and
    // the victim never leaves reach, hit-to-hit is bare reloadTime -- the
    // in-reach attack branch outruns the plant branch.
    withC3(C3_ON, () => {
        const sim = simStub(makeRng(3));
        const a = mk(sim, 1);
        const v = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;

        const dt = 1 / 60;
        const swings = [];
        let last = v.currentHp;
        for (let i = 0; i < 60 * 60; i++) {
            sim.battleTime += dt;
            a.update(dt, [a, v], [v]);
            if (v.currentHp < last) { swings.push(sim.battleTime); last = v.currentHp; }
        }
        assert.ok(swings.length > 20, `expected a long engagement, got ${swings.length}`);
        const gaps = swings.slice(1).map((x, i) => x - swings[i]);
        for (const g of gaps) {
            assert.ok(Math.abs(g - a.reloadTime) <= 1 / 60 + 1e-9,
                `hit-to-hit ${g} should be reloadTime ${a.reloadTime}`);
        }
    });
});

test("[C3] a MELEE victim never stamps the lock", () => {
    // The C2B-refuted case: melee-vs-melee is bit-identical with the flag on.
    withC3(C3_ON, () => {
        const sim = simStub();
        const a = mk(sim, 1);
        const v = mk(sim, 2, { hp: 1e6 }); // melee victim
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;
        sim.battleTime = 8.5;

        a.performAttackOn(v);
        assert.equal(a.moveLockUntil, -Infinity,
            "melee victim: no stamp, ever");
        assert.equal(a.meleeMoveLocked(), false);
    });
});

test("[C3] a SIEGE victim (armor class 20) never stamps the lock", () => {
    // C4-round refinement: the plant was measured on chasers pursuing ranged
    // KITERS; siege carries is_ranged = 1 in the combat dicts, and the C4
    // full gate traced the siege-attacker HP-pts regressions to melee units
    // planting against onagers/scorpions. The dat's Siege Weapons armor
    // class (20) is the exclusion -- NOT minAttackRange, whose 1.0 on the
    // imp skirmisher would wrongly exclude a foot kiter. Re-measure when
    // the new onager tape lands.
    withC3(C3_ON, () => {
        const sim = simStub();
        const a = mk(sim, 1);
        const v = mk(sim, 2, {
            range: 8, isRanged: true, hp: 1e6,
            armors: { 3: 0, 4: 0, 20: 0, 31: 0 }, // the onager/scorpion set
        });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;
        sim.battleTime = 8.5;

        a.performAttackOn(v);
        assert.equal(a.moveLockUntil, -Infinity,
            "siege victim: no stamp, ever");
        assert.equal(a.meleeMoveLocked(), false);
    });
});

test("[C3] a RANGED attacker is exempt even with a stamp forced onto it", () => {
    withC3(C3_ON, () => {
        const sim = simStub();
        const archer = mk(sim, 1, { range: 4, isRanged: true });
        archer.moveLockUntil = sim.battleTime + 10;
        assert.equal(archer.isRanged(), true);
        assert.equal(archer.meleeMoveLocked(), false,
            "ranged immobility is E9's postFireRecovery, not this rule");
    });
});

test("[C3] a killing blow on a ranged victim still plants (the swing has to finish)", () => {
    withC3(C3_ON, () => {
        const sim = simStub();
        const a = mk(sim, 1, { attack: 1000 });
        const v = mk(sim, 2, { range: 4, isRanged: true, hp: 5 });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;
        sim.battleTime = 3;

        a.performAttackOn(v);
        assert.equal(v.state, "dead", "fixture: the blow really killed");
        assert.equal(a.moveLockUntil, 3 + POST_SWING_PLANT_S);
        assert.equal(a.meleeMoveLocked(), true);
    });
});

test("[C3] the stamp only ever EXTENDS the lock, never shortens it", () => {
    withC3(C3_ON, () => {
        const sim = simStub();
        const a = mk(sim, 1);
        const v = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;
        sim.battleTime = 2;
        a.moveLockUntil = 2 + 5; // a (hypothetical) longer lock already owed
        a.performAttackOn(v);
        assert.equal(a.moveLockUntil, 7, "Math.max: the longer lock survives");
    });
});

test("[C3] the plant never touches the rng", () => {
    const draws = [];
    const inner = makeRng(1);
    const rng = {
        next() { draws.push(1); return inner.next(); },
        getState() { return inner.getState(); },
    };
    withC3(C3_ON, () => {
        const sim = simStub(rng);
        const a = mk(sim, 1);
        const v = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = 0; a.y = 0;
        v.x = a.radius + v.radius; v.y = 0;
        const before = draws.length;
        a.performAttackOn(v);
        a.meleeMoveLocked();
        assert.equal(draws.length, before, "stamp + predicate draw nothing");
    });
});
