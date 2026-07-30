// Melee contact churn + post-kill re-acquisition fumble (calibration E13).
//
// The engine used to glue a melee unit to its target: once in reach it swung
// every reload until one of them died, and the instant a target died it picked
// the next one on the very next tick. Neither is what the recordings show.
// Classified over the 31 pure-melee tapes (see constants.js for the full
// table): a real melee unit breaks contact with a STILL-LIVING foe on 3.83% of
// its swings against the engine's 0.36%, and 34.3% of its killing blows are
// followed by a slow re-acquisition against the engine's 11.7%.
//
// BattleUnit.maybeMeleeChurn is the single hook for both. It is called from
// both melee swing paths with the unit the swing was aimed at, and which of
// the two probabilities applies is decided by whether that unit is now dead.
//
// These tests drive the rng directly rather than overriding the constants, so
// they pin the WIRING (which branch, which rate, what it does to the unit)
// against the shipped numbers instead of against a test-only configuration.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    MELEE_CHURN_PER_SWING,
    MELEE_KILL_REACQUIRE_FUMBLE,
    MELEE_CHURN_GAP_SECONDS,
    MELEE_CHURN_CROWD_GAIN,
    MELEE_CHURN_MAX,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// An rng that always returns the same number, and counts its draws -- the
// draw COUNT is load-bearing in two of the tests below (a rate of 0, and a
// ranged unit, must not consume the stream at all, or turning the mechanism
// off would silently reseed every fight after it).
function fixedRng(value) {
    let draws = 0;
    return {
        next() { draws++; return value; },
        getState() { return 1; },
        get draws() { return draws; },
    };
}

function simStub(rng) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: rng || makeRng(1),
    };
}

function stats({ range = 0, isRanged = false } = {}) {
    return {
        hp: 100, attack: 10, attack_range: range, attack_speed: 0.5,
        movement_speed: 1.4, melee_armor: 0, pierce_armor: 0,
        outline_size: 0.4, collision_size: 0.25, accuracy: 100,
        unit_name: "U", is_ranged: isRanged,
    };
}

let nextId = 0;
function mk(sim, team, opts = {}) {
    return new BattleUnit(
        `${team}-${nextId++}`, team, stats(opts), opts.slug || "u",
        "Chinese", sim,
    );
}

// A melee attacker with a living victim already assigned, mid-cooldown as it
// would be immediately after a swing resolved.
function scene(rng, opts = {}) {
    const sim = simStub(rng);
    const a = mk(sim, 1, opts);
    const v = mk(sim, 2);
    a.x = 0; a.y = 0; v.x = 10; v.y = 0;
    a.target = v;
    a.attackCooldown = a.reloadTime;
    sim.team1 = [a];
    sim.team2 = [v];
    return { sim, a, v };
}

// ---- the shipped rates are what the tests below assume ---------------------

test("the two churn rates are distinct and ordered, so one draw can tell them apart", () => {
    assert.ok(MELEE_CHURN_PER_SWING > 0);
    assert.ok(MELEE_KILL_REACQUIRE_FUMBLE > MELEE_CHURN_PER_SWING,
        "a fumbled hand-off after a kill is measured far commoner than a " +
        "mid-fight shove; the branch test below relies on the ordering");
    assert.ok(MELEE_CHURN_GAP_SECONDS > 0);
});

// ---- living victim: the contact-churn branch ------------------------------

test("a melee unit that draws under the churn rate drops its target and pays the gap", () => {
    const { a, v } = scene(fixedRng(0));
    a.maybeMeleeChurn(v);
    assert.equal(a.target, null, "target released for re-acquisition");
    assert.equal(a.attackCooldown, MELEE_CHURN_GAP_SECONDS);
});

test("a melee unit that draws over the churn rate keeps swinging unchanged", () => {
    const { a, v } = scene(fixedRng(0.999));
    const cd = a.attackCooldown;
    a.maybeMeleeChurn(v);
    assert.equal(a.target, v, "still engaged");
    assert.equal(a.attackCooldown, cd, "cooldown untouched");
});

test("a draw between the two rates fires only for a DEAD victim", () => {
    // The whole point of one hook, two rates: the same number is a miss for a
    // living foe and a hit for a hand-off. Pick a value strictly between them.
    const between = (MELEE_CHURN_PER_SWING + MELEE_KILL_REACQUIRE_FUMBLE) / 2;

    const alive = scene(fixedRng(between));
    alive.a.maybeMeleeChurn(alive.v);
    assert.equal(alive.a.target, alive.v, "living victim: below fumble, above churn -> no break");

    const killed = scene(fixedRng(between));
    killed.v.state = "dead";
    killed.a.maybeMeleeChurn(killed.v);
    assert.equal(killed.a.target, null, "dead victim: the fumble rate applies");
    assert.equal(killed.a.attackCooldown, MELEE_CHURN_GAP_SECONDS);
});

// ---- scope: melee only, and no stray rng consumption ----------------------

test("a RANGED unit is exempt and does not consume the rng stream", () => {
    const rng = fixedRng(0);
    const sim = simStub(rng);
    const a = mk(sim, 1, { range: 4, isRanged: true });
    const v = mk(sim, 2);
    a.target = v;
    assert.equal(a.isRanged(), true, "fixture really is ranged");
    a.maybeMeleeChurn(v);
    assert.equal(a.target, v, "ranged units keep the E9 fire-cycle law, untouched");
    assert.equal(rng.draws, 0, "no draw taken");
});

test("a 1.0-reach MELEE unit (Steppe Lancer) is in scope", () => {
    // is_ranged is an explicit flag precisely because reach >= 1.0 no longer
    // implies ranged; the churn must follow the flag, not the reach.
    const rng = fixedRng(0);
    const sim = simStub(rng);
    const a = mk(sim, 1, { range: 1.0, isRanged: false, slug: "elite_steppe" });
    const v = mk(sim, 2);
    a.target = v;
    assert.equal(a.isRanged(), false);
    a.maybeMeleeChurn(v);
    assert.equal(a.target, null, "lancers churn like any other melee unit");
    assert.equal(rng.draws, 1);
});

test("no victim means no draw and no state change", () => {
    const rng = fixedRng(0);
    const { a } = scene(rng);
    const cd = a.attackCooldown;
    a.maybeMeleeChurn(null);
    assert.equal(a.attackCooldown, cd);
    assert.equal(rng.draws, 0);
});

// ---- the crowd term (measured harmful, shipped off, kept wired) -----------

test("contestingAllies counts only living same-team units on the same victim", () => {
    const sim = simStub();
    const v = mk(sim, 2);
    const a = mk(sim, 1);
    const b = mk(sim, 1);
    const c = mk(sim, 1);
    const dead = mk(sim, 1);
    const other = mk(sim, 2); // enemy team, must never count
    sim.team1 = [a, b, c, dead];
    sim.team2 = [v, other];
    a.target = v; b.target = v; dead.target = v; other.target = v;
    c.target = other;
    dead.state = "dead";
    assert.equal(a.contestingAllies(v), 2, "a and b, not c, not the corpse, not the enemy");
});

test("MELEE_CHURN_CROWD_GAIN ships at 0, which is a documented no-op", () => {
    // Measured harmful in E13 (constants.js carries the sweep). Pinned so a
    // future round has to change the number deliberately, and so the cap it
    // would need stays sane if it ever does.
    assert.equal(MELEE_CHURN_CROWD_GAIN, 0);
    assert.ok(MELEE_CHURN_MAX > MELEE_CHURN_PER_SWING);
});

// ---- end to end: bouts become bounded ------------------------------------

test("over a long engagement a melee unit really does break contact repeatedly", () => {
    // Integration check against the actual constants and the real rng: a unit
    // parked in reach of an unkillable foe should, across many swings, both
    // land hits at the reload cadence AND periodically go quiet. Pre-E13 this
    // produced one unbroken bout.
    const sim = simStub(makeRng(7));
    const a = mk(sim, 1);
    const v = mk(sim, 2);
    v.maxHp = 1e9; v.currentHp = 1e9; // never dies -> isolates the LIVING branch
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;
    sim.team1 = [a];
    sim.team2 = [v];

    const swings = [];
    let t = 0;
    const dt = 1 / 60;
    let last = v.currentHp;
    for (let i = 0; i < 60 * 400; i++) {
        a.update(dt, [a, v], [v]);
        t += dt;
        if (v.currentHp < last) { swings.push(t); last = v.currentHp; }
    }
    assert.ok(swings.length > 40, `expected a long engagement, got ${swings.length} swings`);

    const gaps = swings.slice(1).map((x, i) => x - swings[i]);
    const breaks = gaps.filter((g) => g > a.reloadTime + 0.5);
    assert.ok(breaks.length > 0, "the unit never broke contact at all");
    // Every break should be the measured gap, not some other duration.
    for (const g of breaks) {
        assert.ok(Math.abs(g - MELEE_CHURN_GAP_SECONDS) < 0.2,
            `break gap ${g.toFixed(2)}s is not the ${MELEE_CHURN_GAP_SECONDS}s constant`);
    }
    // ...and the rate should land in the same order of magnitude as the tape's
    // 3.83 per 100 swings that the constant was fitted to. A wide band on
    // purpose: this is a wiring test, not a re-fit of the constant.
    const rate = breaks.length / swings.length;
    assert.ok(rate > 0.01 && rate < 0.15,
        `break rate ${rate.toFixed(3)} per swing is outside the plausible band`);
    assert.ok(TILE_SIZE > 0);
});
