// Melee target lock + bump retarget (calibration E14), the MECHANISTIC
// replacement for E13's stochastic contact churn.
//
// E13 drew two probabilities against the rng after every melee swing and paid
// a fixed 5.8 s gap. Those constants were fitted to this corpus's unit types
// and army sizes and cannot generalise, so they were deleted. What is tested
// here instead is the physical rule set:
//
//   1. TARGET LOCK  -- the stuck bar may not blacklist a living MELEE target
//      for a MELEE unit, unless that victim's contact slots are already full
//      (MELEE_CONTACT_SLOTS attackers in reach of it). A pursuit -- a ranged
//      unit, or a RANGED target -- keeps the bar unchanged.
//   2. BUMP RETARGET -- a melee unit that cannot reach its target and is in
//      body contact with a different living melee enemy switches to the one it
//      is touching (AoE2:DE update 81058).
//
// Neither rule touches the rng: the no-op assertions below check the WIRING
// (both flags off restores the pre-E14 stuck bar exactly), not a seed.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    MELEE_TARGET_LOCK,
    MELEE_CONTACT_SLOTS,
    MELEE_BUMP_RETARGET,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

function countingRng() {
    const inner = makeRng(1);
    let draws = 0;
    return {
        next() { draws++; return inner.next(); },
        getState() { return inner.getState(); },
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
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, stats(opts), opts.slug || "u",
        "Chinese", sim,
    );
    (team === 1 ? sim.team1 : sim.team2).push(u);
    return u;
}

// ---- shipped configuration -------------------------------------------------

test("both E14 rules ship ON and the slot cap is the tape's measured ceiling", () => {
    assert.equal(MELEE_TARGET_LOCK, true);
    assert.equal(MELEE_BUMP_RETARGET, true);
    // attackers-per-victim over the 31 pure-melee recordings: median 2, p90 3,
    // max 4 -- on BOTH streams. The cap is that max, not a tuned number.
    assert.equal(MELEE_CONTACT_SLOTS, 4);
});

// ---- rule 1: target lock ---------------------------------------------------

test("a melee unit holding a living melee foe is locked on", () => {
    const sim = simStub();
    const a = mk(sim, 1);
    const v = mk(sim, 2);
    a.target = v;
    assert.equal(a.meleeTargetLock(), true);
});

test("a RANGED unit is never locked -- the stuck bar still owns pursuit", () => {
    const sim = simStub();
    const a = mk(sim, 1, { range: 4, isRanged: true });
    const v = mk(sim, 2);
    a.target = v;
    assert.equal(a.isRanged(), true);
    assert.equal(a.meleeTargetLock(), false);
});

test("a melee unit chasing a RANGED foe is not locked either", () => {
    const sim = simStub();
    const a = mk(sim, 1);
    const v = mk(sim, 2, { range: 4, isRanged: true });
    a.target = v;
    assert.equal(a.meleeTargetLock(), false);
});

test("a 1.0-reach MELEE unit (Steppe Lancer) locks like any other melee unit", () => {
    const sim = simStub();
    const a = mk(sim, 1, { range: 1.0, slug: "elite_steppe" });
    const v = mk(sim, 2);
    a.target = v;
    assert.equal(a.isRanged(), false);
    assert.equal(a.meleeTargetLock(), true);
});

test("the lock releases once the victim's contact slots are full", () => {
    const sim = simStub();
    const v = mk(sim, 2);
    v.x = 0; v.y = 0;
    const a = mk(sim, 1);
    a.target = v;
    // Park the newcomer well outside reach: it is the one queueing.
    a.x = 4 * TILE_SIZE; a.y = 0;
    assert.equal(a.meleeTargetLock(), true, "empty ring: locked");

    // Fill the ring with allies that really are in reach of v.
    for (let i = 0; i < MELEE_CONTACT_SLOTS; i++) {
        const ally = mk(sim, 1);
        ally.target = v;
        ally.x = (i % 2 ? 1 : -1) * (ally.radius + v.radius);
        ally.y = i < 2 ? 0 : 1;
        assert.ok(ally.distanceTo(v) <= ally.attackRange + ally.radius + v.radius);
    }
    assert.equal(a.meleeTargetLock(), false,
        "ring full: the stuck bar gets its old job back");
});

test("allies that are NOT in reach of the victim do not occupy a slot", () => {
    const sim = simStub();
    const v = mk(sim, 2);
    const a = mk(sim, 1);
    a.target = v;
    a.x = 4 * TILE_SIZE;
    for (let i = 0; i < MELEE_CONTACT_SLOTS + 2; i++) {
        const far = mk(sim, 1);
        far.target = v;
        far.x = 6 * TILE_SIZE + i; // committed but nowhere near
    }
    assert.equal(a.meleeTargetLock(), true,
        "occupancy is who can SWING at it, not who intends to");
});

test("dead allies and enemy units never occupy a slot", () => {
    const sim = simStub();
    const v = mk(sim, 2);
    const a = mk(sim, 1);
    a.target = v;
    a.x = 4 * TILE_SIZE;
    for (let i = 0; i < MELEE_CONTACT_SLOTS; i++) {
        const corpse = mk(sim, 1);
        corpse.target = v;
        corpse.x = 0; corpse.y = 0;
        corpse.state = "dead";
    }
    const foe = mk(sim, 2);
    foe.target = v;
    foe.x = 0; foe.y = 0;
    assert.equal(a.meleeTargetLock(), true);
});

// ---- rule 2: bump retarget -------------------------------------------------

function bumpScene() {
    const sim = simStub();
    const a = mk(sim, 1);
    const far = mk(sim, 2);
    const touching = mk(sim, 2);
    a.x = 0; a.y = 0;
    far.x = 5 * TILE_SIZE; far.y = 0;          // locked on, out of reach
    touching.x = a.radius + touching.radius; touching.y = 0;  // body contact
    a.target = far;
    return { sim, a, far, touching };
}

test("a melee unit that cannot reach its target switches to the enemy it is touching", () => {
    const { a, far, touching, sim } = bumpScene();
    assert.equal(a.inRange(), false, "fixture: the locked foe really is out of reach");
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, touching);
    assert.equal(a.stuckTimer, 0, "a bump is a fresh engagement");
    assert.notEqual(a.target, far);
});

test("a unit that CAN reach its target ignores everything it is touching", () => {
    const { a, far, touching, sim } = bumpScene();
    far.x = a.radius + far.radius; far.y = 0; // now in reach
    assert.equal(a.inRange(), true);
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far, "no opportunistic switching while engaged");
    assert.ok(touching);
});

test("an enemy merely NEAR -- not touching -- does not trigger a bump", () => {
    const { a, far, touching, sim } = bumpScene();
    touching.x = a.radius + touching.radius + 2; // just past the collision floor
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far);
});

test("the NEAREST touching enemy wins, whatever the array order", () => {
    const { a, sim } = bumpScene();
    const nearer = mk(sim, 2);
    nearer.x = a.radius + nearer.radius - 0.5; nearer.y = 0;
    // nearer was pushed last, so a first-match rule would pick the other one
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, nearer);
});

test("bump retargeting is melee-vs-melee on both ends", () => {
    // A melee unit CHASING archers bumps them constantly; letting the rule fire
    // there turned the champion__vs__arbalester canary 6/6 -> 0/6.
    const sim = simStub();
    const a = mk(sim, 1);
    const archer = mk(sim, 2, { range: 4, isRanged: true });
    const touching = mk(sim, 2, { range: 4, isRanged: true });
    a.x = 0; a.y = 0;
    archer.x = 8 * TILE_SIZE;
    touching.x = a.radius + touching.radius;
    a.target = archer;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, archer, "pursuit is the ranged round's business");
});

test("a ranged unit never bump-retargets", () => {
    const sim = simStub();
    const a = mk(sim, 1, { range: 4, isRanged: true });
    const far = mk(sim, 2);
    const touching = mk(sim, 2);
    a.x = 0; far.x = 9 * TILE_SIZE; touching.x = a.radius + touching.radius;
    a.target = far;
    a.meleeBumpRetarget(sim.team2);
    assert.equal(a.target, far);
});

// ---- no randomness anywhere -----------------------------------------------

test("neither rule consumes the rng stream", () => {
    const rng = countingRng();
    const sim = simStub(rng);
    const a = mk(sim, 1);
    const far = mk(sim, 2);
    const touching = mk(sim, 2);
    a.x = 0; far.x = 5 * TILE_SIZE; touching.x = a.radius + touching.radius;
    a.target = far;
    a.meleeTargetLock();
    a.meleeBumpRetarget(sim.team2);
    assert.equal(rng.draws, 0,
        "E13's per-swing draw is gone; contact loss now comes from geometry");
});

// ---- end to end: a lone engaged pair no longer churns ----------------------

test("a melee unit alone with an unkillable foe now swings without interruption", () => {
    // The direct behavioural inverse of E13: with no crowd, no shoving and no
    // probability, there is nothing left to break contact -- every gap is the
    // reload. Any future break in THIS fixture would be a bug, not a model.
    const sim = simStub(makeRng(7));
    const a = mk(sim, 1);
    const v = mk(sim, 2);
    v.maxHp = 1e9; v.currentHp = 1e9;
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;

    const swings = [];
    let t = 0;
    const dt = 1 / 60;
    let last = v.currentHp;
    for (let i = 0; i < 60 * 200; i++) {
        a.update(dt, [a, v], [v]);
        t += dt;
        if (v.currentHp < last) { swings.push(t); last = v.currentHp; }
    }
    assert.ok(swings.length > 80, `expected a long engagement, got ${swings.length}`);
    const gaps = swings.slice(1).map((x, i) => x - swings[i]);
    const breaks = gaps.filter((g) => g > a.reloadTime + 0.5);
    assert.equal(breaks.length, 0,
        "an isolated pair has no physical reason to lose contact");
});
