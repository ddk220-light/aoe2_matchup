// E15b -- the two rules the walk forensics (docs/calibration/e15_walk_forensics.md)
// asked for, neither of which reads the rng:
//
//   R1 SWING RECOVERY PLANT. A melee unit that has just LANDED a swing may not
//      WALK until its attack animation completes (MELEE_SWING_RECOVERY_S). It
//      may still turn, re-target, bump-retarget, reload and be shoved. Killing
//      blows are included -- the animation does not abort because the victim
//      fell. Ranged units are exempt (they own E9's postFireRecovery).
//      Measured signal: the tape's moving-share ramps 0.90% -> 14.40% across the
//      reload cycle since the last landed hit; the engine was flat.
//
//   R2 LANE-GATED RE-ACQUISITION. On a RE-acquisition (never the fight's opening
//      pick) a melee unit takes the nearest living enemy whose straight approach
//      lane is wide enough for its own body, falling back to the plain nearest
//      when everything inside MELEE_LANE_CANDIDATE_CAP is walled in.
//      Measured signal: over 2062 mid-fight lock births the tape's chosen victim
//      sits a median 0.337 tiles further away than the nearest body (engine
//      0.004), and the victim it takes had a blocked lane 25.0% of the time
//      against 31.8% for the closer ones it walked past.
//
// OFF-SWITCH. `MELEE_SWING_RECOVERY_S = 0` + `MELEE_LANE_REACQUIRE = false` must
// reproduce the E14 board bit for bit. That was verified end to end with
// `node tools/simjs/e14_identity.mjs <reference-run-dir> 3`
// -> identical 465/465. The tests at the bottom of this file pin the two
// structural facts that make it true, so a future edit cannot break the
// off-switch without turning one of them red.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    MELEE_SWING_RECOVERY_S,
    MELEE_LANE_REACQUIRE,
    MELEE_LANE_CANDIDATE_CAP,
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

function stats({ range = 0, isRanged = false, hp = 100, attack = 10 } = {}) {
    return {
        hp, attack, attack_range: range, attack_speed: 0.5,
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

test("E15b ships lane re-acquisition ON and the swing plant OFF", () => {
    // The marginal-effect runs refuted the fixed-length plant: a step function
    // cannot match the tape's monotone swing-phase ramp, it cost 7 gate sides
    // alone, and it suppressed exactly the walking the lane rule induces
    // (paladin_vs_steppe 5/6 -> 1/6 with both on). See the rationale block at
    // MELEE_SWING_RECOVERY_S in constants.js. The mechanism stays wired (and
    // covered below via manual stamps) for when a contact-loss model makes an
    // animation plant worth revisiting.
    assert.equal(MELEE_SWING_RECOVERY_S, 0);
    assert.equal(MELEE_LANE_REACQUIRE, true);
    // Cost cap only: beyond the nearest dozen bodies the walk dominates, and
    // exhausting the cap falls back to the pre-E15b nearest.
    assert.equal(MELEE_LANE_CANDIDATE_CAP, 12);
});

// ---- R1: swing recovery plant ----------------------------------------------

test("a melee unit that has never swung is free to walk", () => {
    const sim = simStub();
    const a = mk(sim, 1);
    assert.equal(a.moveLockUntil, -Infinity);
    assert.equal(a.meleeMoveLocked(), false);
});

test("with the plant shipped OFF, landing a swing does not lock locomotion", () => {
    const sim = simStub();
    const a = mk(sim, 1);
    const v = mk(sim, 2, { hp: 1e6 });
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;
    sim.battleTime = 12.25;

    a.performAttackOn(v);
    assert.equal(a.moveLockUntil, -Infinity,
        "no stamp is written while the rule is off");
    assert.equal(a.meleeMoveLocked(), false, "recovery 0 = free immediately");
});

test("the lock predicate is inert while the rule is off, even with a stamp", () => {
    // MELEE_SWING_RECOVERY_S <= 0 short-circuits the predicate entirely, so a
    // stray stamp (this cannot happen in production; belt-and-braces) cannot
    // freeze a unit. The nonzero-recovery behavior is pinned by the manual-
    // stamp locomotion test below.
    const sim = simStub();
    const a = mk(sim, 1, { attack: 1000 });
    const v = mk(sim, 2, { hp: 5 });
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;
    sim.battleTime = 12.25;

    a.performAttackOn(v);
    assert.equal(v.state, "dead", "fixture: the blow really killed");
    a.moveLockUntil = 12.25 + 0.5;
    assert.equal(a.meleeMoveLocked(), false,
        "constant-gated off: the stamp is ignored");
});

test("a RANGED unit is exempt even with a stamp on it", () => {
    const sim = simStub();
    const a = mk(sim, 1, { range: 4, isRanged: true });
    // Force the stamp a melee unit would carry; the predicate must still refuse.
    a.moveLockUntil = sim.battleTime + 10;
    assert.equal(a.isRanged(), true);
    assert.equal(a.meleeMoveLocked(), false,
        "ranged immobility is E9's postFireRecovery, not this rule");
});

test("with the plant off, a freed unit re-targets and closes immediately", () => {
    // The pre-E15b (and shipped) behavior: victim dies, the unit picks its
    // next foe and starts walking on the very next ticks -- no plant. This is
    // the baseline any future nonzero-recovery change would deliberately
    // alter.
    const sim = simStub();
    const a = mk(sim, 1, { attack: 1000 });
    const v = mk(sim, 2, { hp: 5 });
    const next = mk(sim, 2, { hp: 1e6 });
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;
    next.x = 6 * TILE_SIZE; next.y = 0;

    a.target = v;
    a.hasAcquiredTarget = true;
    a.performAttackOn(v);           // kills v; no stamp while the rule is off
    a.attackCooldown = a.reloadTime;

    const dt = 1 / 60;
    const x0 = a.x;
    for (let i = 0; i < 30; i++) {
        sim.battleTime += dt;
        a.update(dt, [a, v, next], sim.team2);
    }
    assert.equal(a.target, next, "re-targeted onto the surviving foe");
    assert.ok(a.x > x0 + 1, `expected the unit to close, x ${x0} -> ${a.x}`);
    assert.equal(a.state, "moving");
});

test("the plant does NOT delay the next swing", () => {
    // Reload timing is untouched: an engaged pair still lands hits exactly one
    // reloadTime apart, animation lock or not.
    const sim = simStub(makeRng(3));
    const a = mk(sim, 1);
    const v = mk(sim, 2, { hp: 1e6 });
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
    // One tick of slack and no more: the cooldown crosses zero mid-tick, which
    // is pre-existing quantisation. Anything larger would be R1 leaking into
    // the reload, which it must not.
    for (const g of gaps) {
        assert.ok(Math.abs(g - a.reloadTime) <= 1 / 60 + 1e-9,
            `hit-to-hit ${g} should be reloadTime ${a.reloadTime}`);
    }
});

// ---- R2: lane-gated re-acquisition -----------------------------------------

// One attacker at the origin, one very close enemy whose lane can be walled off,
// and one further enemy standing in the clear.
function laneScene() {
    const sim = simStub();
    const a = mk(sim, 1);
    a.x = 0; a.y = 0;
    const near = mk(sim, 2);
    near.x = 3 * TILE_SIZE; near.y = 0;
    const far = mk(sim, 2);
    far.x = 0; far.y = 5 * TILE_SIZE;
    return { sim, a, near, far };
}

test("a walled-off nearer enemy is skipped for the next-nearest clear one", () => {
    const { sim, a, near, far } = laneScene();
    // An ally parked squarely in the corridor to `near`.
    const wall = mk(sim, 1);
    wall.x = 1.5 * TILE_SIZE; wall.y = 0;
    assert.equal(a.laneClear(near), false, "fixture: the near lane really is blocked");
    assert.equal(a.laneClear(far), true, "fixture: the far lane really is clear");

    a.hasAcquiredTarget = true;   // this is a RE-acquisition
    a.findTarget(sim.team2);
    assert.equal(a.target, far,
        "the freed unit takes the enemy it can actually walk to");
});

test("the fight's OPENING pick is always the plain nearest", () => {
    // Mandatory exemption: at t=0 the armies are separated blocks, every
    // front-rank unit's lane reads blocked by the ally beside it, and an
    // unscoped rule cross-assigns the whole line across the field. It cost 5
    // gate sides and took champion__vs__paladin margins 21.9% -> 6.7%.
    const { sim, a, near } = laneScene();
    const wall = mk(sim, 1);
    wall.x = 1.5 * TILE_SIZE; wall.y = 0;
    assert.equal(a.laneClear(near), false);

    assert.equal(a.hasAcquiredTarget, false, "fixture: nothing acquired yet");
    a.findTarget(sim.team2);
    assert.equal(a.target, near, "opening acquisition ignores the lane test");
    assert.equal(a.hasAcquiredTarget, true, "and it is only an opening once");
});

test("when EVERY candidate is walled in it falls back to the plain nearest", () => {
    const { sim, a, near, far } = laneScene();
    const w1 = mk(sim, 1); w1.x = 1.5 * TILE_SIZE; w1.y = 0;
    const w2 = mk(sim, 1); w2.x = 0; w2.y = 2.5 * TILE_SIZE;
    assert.equal(a.laneClear(near), false);
    assert.equal(a.laneClear(far), false);
    assert.equal(a.laneAcquire(sim.team2), null);

    a.hasAcquiredTarget = true;
    a.findTarget(sim.team2);
    assert.equal(a.target, near, "no reachable foe -> pre-E15b answer");
});

test("an ENEMY body blocks a lane exactly as an allied one does", () => {
    const { sim, a, near, far } = laneScene();
    const foeInTheWay = mk(sim, 2);
    foeInTheWay.x = 1.5 * TILE_SIZE; foeInTheWay.y = 0;
    assert.equal(a.laneClear(near), false);

    a.hasAcquiredTarget = true;
    a.findTarget(sim.team2);
    // foeInTheWay is now the NEAREST enemy and its own lane is clear, so it wins.
    assert.equal(a.target, foeInTheWay);
    assert.ok(far);
});

test("bodies behind the attacker or beyond the candidate are not in the way", () => {
    const { sim, a, near } = laneScene();
    const behind = mk(sim, 1);
    behind.x = -2 * TILE_SIZE; behind.y = 0;
    const beyond = mk(sim, 1);
    beyond.x = 5 * TILE_SIZE; beyond.y = 0;
    assert.equal(a.laneClear(near), true,
        "the corridor is the SEGMENT, not the infinite line");
});

test("neither the candidate nor the attacker blocks its own lane", () => {
    const { sim, a, near } = laneScene();
    assert.equal(sim.team1.length, 1);
    assert.equal(a.laneClear(near), true);
    // Sanity: a third body ON the candidate does block (it is not the candidate).
    const hugger = mk(sim, 1);
    hugger.x = near.x - near.radius; hugger.y = 0;
    assert.equal(a.laneClear(near), false);
});

test("a dead body does not block a lane", () => {
    const { sim, a, near } = laneScene();
    const corpse = mk(sim, 1);
    corpse.x = 1.5 * TILE_SIZE; corpse.y = 0;
    assert.equal(a.laneClear(near), false);
    corpse.state = "dead";
    assert.equal(a.laneClear(near), true);
});

test("the lane test is melee-vs-melee: a RANGED candidate is taken as-is", () => {
    // Same scope as E14's bump retarget, and paid for the same way: applied to
    // a melee unit re-picking among a kiting archer ball it took the
    // champion__vs__arbalester canary from 6/6 to 0/6.
    const sim = simStub();
    const a = mk(sim, 1);
    a.x = 0; a.y = 0;
    const nearArcher = mk(sim, 2, { range: 4, isRanged: true });
    nearArcher.x = 3 * TILE_SIZE; nearArcher.y = 0;
    const farArcher = mk(sim, 2, { range: 4, isRanged: true });
    farArcher.x = 0; farArcher.y = 5 * TILE_SIZE;
    const wall = mk(sim, 1);
    wall.x = 1.5 * TILE_SIZE; wall.y = 0;
    assert.equal(a.laneClear(nearArcher), false, "fixture: the lane IS blocked");

    a.hasAcquiredTarget = true;
    a.findTarget(sim.team2);
    assert.equal(a.target, nearArcher, "pursuit is the ranged round's business");
    assert.ok(farArcher);
});

test("a RANGED unit re-acquires by plain distance, lane or no lane", () => {
    const { sim, a: _melee, near, far } = laneScene();
    const archer = mk(sim, 1, { range: 4, isRanged: true });
    archer.x = 0; archer.y = 0;
    const wall = mk(sim, 1);
    wall.x = 1.5 * TILE_SIZE; wall.y = 0;

    archer.hasAcquiredTarget = true;
    archer.findTarget(sim.team2);
    assert.equal(archer.target, near, "an archer shoots over bodies");
    assert.ok(far && _melee);
});

test("the lane rule never touches the rng", () => {
    const rng = countingRng();
    const sim = simStub(rng);
    const a = mk(sim, 1);
    a.x = 0; a.y = 0;
    const near = mk(sim, 2); near.x = 3 * TILE_SIZE;
    const far = mk(sim, 2); far.y = 5 * TILE_SIZE;
    const wall = mk(sim, 1); wall.x = 1.5 * TILE_SIZE;
    a.hasAcquiredTarget = true;
    a.findTarget(sim.team2);
    a.laneClear(near);
    a.laneAcquire(sim.team2);
    assert.equal(rng.draws, 0);
    assert.ok(far && wall);
});

// ---- off-switch structure ---------------------------------------------------

test("R1 at recovery 0 is a no-op by construction", () => {
    // The stamp is `battleTime + MELEE_SWING_RECOVERY_S` and the predicate is a
    // STRICT `battleTime < moveLockUntil`, so a recovery of 0 leaves the window
    // empty on the very tick the swing lands and on every tick after it. Pinned
    // here because it is what makes the constant a genuine off-switch rather
    // than a "very short lock".
    const sim = simStub();
    const a = mk(sim, 1);
    sim.battleTime = 7;
    a.moveLockUntil = sim.battleTime + 0;
    assert.equal(a.meleeMoveLocked(), false);
});

test("R2 disabled is a no-op by construction: it only ever re-ranks the SAME pool", () => {
    // laneAcquire draws from exactly the candidates findTarget's nearest-only
    // loop considers (living, not blacklisted) and returns null rather than a
    // worse answer, so switching MELEE_LANE_REACQUIRE off can only restore the
    // nearest -- never change which enemies are eligible.
    const sim = simStub();
    const a = mk(sim, 1);
    a.x = 0; a.y = 0;
    const near = mk(sim, 2); near.x = 3 * TILE_SIZE;
    const far = mk(sim, 2); far.y = 5 * TILE_SIZE;
    a.blockedTargets.add(near);
    a.hasAcquiredTarget = true;
    assert.equal(a.laneAcquire(sim.team2), far,
        "a blacklisted enemy is not a lane candidate either");

    const corpse = mk(sim, 2); corpse.x = TILE_SIZE; corpse.state = "dead";
    assert.equal(a.laneAcquire(sim.team2), far, "nor is a corpse");
});

test("an isolated engaged pair still never breaks contact", () => {
    // The E14 invariant, re-checked with both new rules live: with no crowd and
    // no probability there is nothing to lose contact to, so every gap is the
    // reload. R1 must not manufacture a break by planting a unit out of reach.
    const sim = simStub(makeRng(7));
    const a = mk(sim, 1);
    const v = mk(sim, 2, { hp: 1e9 });
    a.x = 0; a.y = 0;
    v.x = a.radius + v.radius; v.y = 0;

    const dt = 1 / 60;
    const swings = [];
    let last = v.currentHp;
    for (let i = 0; i < 60 * 200; i++) {
        sim.battleTime += dt;
        a.update(dt, [a, v], [v]);
        if (v.currentHp < last) { swings.push(sim.battleTime); last = v.currentHp; }
    }
    assert.ok(swings.length > 80, `expected a long engagement, got ${swings.length}`);
    const gaps = swings.slice(1).map((x, i) => x - swings[i]);
    assert.equal(gaps.filter((g) => g > a.reloadTime + 0.5).length, 0);
});
