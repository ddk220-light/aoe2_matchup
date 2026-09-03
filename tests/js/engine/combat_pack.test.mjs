// Combat-pack compression (calibration experiment E8).
//
// A SAME-TEAM pair whose members are BOTH engaged in a fight at contact range
// compresses to COMBAT_PACK_FACTOR of the normal minimum separation, in both
// the hard floor (Simulation.resolveCollisions) and the soft one
// (BattleUnit.calculateAvoidance). Everything else -- cross-team pairs, pairs
// with an unengaged member, and every approach march -- keeps the pre-E8
// geometry exactly.
//
// The reason the mechanism exists, and the reason the CROSS-TEAM floor must NOT
// move, is the reach arithmetic (see constants.js). Compressing cross-team
// instead would pull the ENEMY line tighter and hand the extra attackers to the
// SHORT-reach side -- measured, it flips paladin__vs__elite_steppe from 5/20
// steppe wins back to 0/20.
//
// E11 RE-BASED THE ARITHMETIC. Every px figure in this file used to come from
// the old inflated radius formula (`round(10 + outline*20)` -> 18 px for a
// mounted unit). The physics radius is now the .dat's collision_size_x, which
// is 0.25 tiles = 7.5 px for everything mounted, so:
//
//                       pre-E11        E11
//     mounted radius      18 px       7.5 px
//     same-team floor     37 px        16 px    (rA + rB + 1)
//     1.0-reach reach     71 px        50 px    (30 + 5 + rA + rB)
//     0-reach   reach     41 px        20 px
//
// The tests below are written against the radius the engine reports rather
// than a hardcoded px count wherever that is possible.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    COMBAT_PACK_FACTOR,
    COMBAT_PACK_SLACK_TILES,
    COMBAT_PACK_RANGED,
    setW1,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

// `size` is the SELECTION circle (outline_size); `collision` is the physics
// radius. Default 0.4/0.25 = a mounted unit, matching the .dat.
function stats(name, { range = 0, size = 0.4, collision = null } = {}) {
    return {
        hp: 100, attack: 10, attack_range: range, attack_speed: 0.5,
        movement_speed: 1.4, melee_armor: 0, pierce_armor: 0,
        outline_size: size,
        collision_size: collision != null ? collision : Math.min(size, 0.25),
        accuracy: 100, unit_name: name,
    };
}

// The mounted physics radius every distance in this file is built from.
const R = 0.25 * TILE_SIZE; // 7.5 px

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

// Straight-line scene: two same-team units at `gap` px apart on the x axis,
// with one enemy `enemyGap` px beyond the leading one.
function pair({ gap = 30, enemyGap = 37, range = 1.0 } = {}) {
    const sim = simStub();
    const a = mk(sim, 1, { name: "A", range }, 0, 0);
    const b = mk(sim, 1, { name: "B", range }, gap, 0);
    const e = mk(sim, 2, { name: "E", range: 0 }, -enemyGap, 0);
    sim.team1 = [a, b];
    sim.team2 = [e];
    return { sim, a, b, e };
}

// ---- the predicate --------------------------------------------------------

test("computeCombatPack is false with no target, a dead target, or a dead self", () => {
    const { a, e } = pair();
    assert.equal(a.computeCombatPack(), false, "no target");
    a.target = e;
    assert.equal(a.computeCombatPack(), true, "target in reach");
    e.state = "dead";
    assert.equal(a.computeCombatPack(), false, "dead target");
    e.state = "attacking";
    a.state = "dead";
    assert.equal(a.computeCombatPack(), false, "dead self");
});

test("computeCombatPack admits the rank BEHIND the contact line but not the field", () => {
    // A 1.0-tile-reach mounted unit reaches 1.0*30 + 5 + 7.5 + 7.5 = 50 px,
    // and the slack adds 1.5 tiles = 45 px, so the predicate is true out to
    // 95 px and false past it.
    const { sim, a, e } = pair({ range: 1.0 });
    a.target = e;
    const reach = a.attackRange + a.radius + e.radius;
    assert.equal(reach, 1.0 * TILE_SIZE + 5 + 2 * R, "reach arithmetic pinned");
    assert.equal(reach, 50);
    const limit = reach + COMBAT_PACK_SLACK_TILES * TILE_SIZE;

    e.x = a.x - (reach - 1); // comfortably in reach -> front rank
    assert.equal(a.computeCombatPack(), true);
    e.x = a.x - (limit - 1); // out of reach, inside the slack -> second rank
    assert.equal(a.inRange(), false, "second rank really is out of reach");
    assert.equal(a.computeCombatPack(), true);
    e.x = a.x - (limit + 1); // past the slack -> still marching in
    assert.equal(a.computeCombatPack(), false);
    assert.ok(sim);
});

test("a 0-range melee unit gets a much smaller pack radius than a 1.0-range one", () => {
    // The asymmetry is the whole point: reach, not the pack rule, decides who
    // benefits. 0-range reach is 5 + 7.5 + 7.5 = 20 px vs the lancer's 50 px.
    const { a, e } = pair({ range: 0 });
    a.target = e;
    assert.equal(a.attackRange + a.radius + e.radius, 20);
    e.x = a.x - 100;
    assert.equal(a.computeCombatPack(), false, "100 px > 41 + 45");
});

// ---- hard floor: Simulation.resolveCollisions -----------------------------

// Build a real Simulation (not the stub) holding the given units.
function realSim(units1, units2) {
    const s = new Simulation(900, 600, makeRng(1));
    s.team1 = units1;
    s.team2 = units2;
    for (const u of [...units1, ...units2]) u.sim = s;
    return s;
}

function xGapAfterCollisions(aPacked, bPacked, sameTeam) {
    const sim = simStub();
    // 4 px apart: inside even the COMPRESSED floor (16 * COMBAT_PACK_FACTOR),
    // so resolveCollisions always pushes and the resulting gap is the floor
    // itself. It used to be 10 px, which was inside the old 37 px floor but is
    // NOT inside today's compressed 16 px one -- at 10 px the packed pair would
    // simply not be touched and the test would read 10 instead of the floor.
    const a = mk(sim, 1, { name: "A" }, 100, 100);
    const b = mk(sim, sameTeam ? 1 : 2, { name: "B" }, 104, 100);
    a.inCombatPack = aPacked;
    b.inCombatPack = bPacked;
    const s = sameTeam ? realSim([a, b], []) : realSim([a], [b]);
    s.resolveCollisions([a, b]);
    return Math.abs(b.x - a.x);
}

test("resolveCollisions compresses a same-team pair only when BOTH are packed", () => {
    const normal = R + R + 1; // a.radius + b.radius + 1 = 16
    assert.equal(xGapAfterCollisions(false, false, true).toFixed(6), normal.toFixed(6));
    assert.equal(xGapAfterCollisions(true, false, true).toFixed(6), normal.toFixed(6));
    assert.equal(xGapAfterCollisions(false, true, true).toFixed(6), normal.toFixed(6));
    assert.equal(
        xGapAfterCollisions(true, true, true).toFixed(6),
        (normal * COMBAT_PACK_FACTOR).toFixed(6),
    );
});

test("resolveCollisions leaves the CROSS-TEAM floor untouched even when both are packed", () => {
    const normal = R + R + 1;
    for (const [ap, bp] of [[false, false], [true, false], [false, true], [true, true]]) {
        assert.equal(
            xGapAfterCollisions(ap, bp, false).toFixed(6),
            normal.toFixed(6),
            `cross-team pair must not move (packed=${ap},${bp})`,
        );
    }
});

test("the floor is tight enough for a second rank of 1.0-reach melee, and the reach asymmetry holds", () => {
    // Front rank at the untouched cross-team floor + the same-team gap must
    // land inside the 1.0-reach unit's reach.
    const crossFloor = R + R + 1;               // 16 px
    const packedGap = crossFloor * COMBAT_PACK_FACTOR;
    const lancerReach = 1.0 * TILE_SIZE + 5 + 2 * R;   // 50 px
    const paladinReach = 5 + 2 * R;                    // 20 px

    assert.ok(crossFloor + packedGap <= lancerReach, "second rank reaches");

    // E11 NOTE -- this used to also assert "a THIRD rank does NOT reach".
    // That was never a fact about the game; it was a consequence of the
    // inflated 18 px radius (37 px floors). With the .dat's true 7.5 px the
    // ranks sit physically closer together, so how many of them fight is now
    // purely a function of COMBAT_PACK_FACTOR:
    //
    //     factor 1.0  -> 3 ranks   (16 + 2*16   = 48 <= 50)
    //     factor 0.8  -> 3 ranks   (16 + 2*12.8 = 41.6)
    //     factor 0.6  -> 4 ranks   (16 + 3*9.6  = 44.8)
    //
    // The tapes put the truth at the 2-3 rank boundary: over the
    // paladin__vs__elite_steppe recordings the steppe side's median same-team
    // nearest-neighbour distance is 0.595 tiles (17.9 px) and its cross-team
    // floor is 0.479 tiles (14.4 px), so rank 3 sits at 14.4 + 2*17.9 =
    // 50.2 px against a 50 px reach -- right on the line, rank 4 well past it.
    // So this asserts the BOUND (no more than three ranks), which is what
    // rules the over-tight factors out, rather than an exact count.
    const ranks = 1 + Math.floor((lancerReach - crossFloor) / packedGap);
    assert.ok(ranks >= 2, `1.0-reach melee must field a second rank, got ${ranks}`);
    assert.ok(
        ranks <= 3,
        `no more than three ranks may fight; COMBAT_PACK_FACTOR=` +
        `${COMBAT_PACK_FACTOR} gives ${ranks}`,
    );

    // The asymmetry that makes 1.0-tile reach worth having is what actually
    // matters, and it survives at every factor: a 0-reach unit's second rank
    // cannot fight no matter how tightly its side packs.
    assert.ok(
        crossFloor + packedGap > paladinReach,
        "a 0-reach unit gains no second rank from packing",
    );
});

// ---- soft floor: BattleUnit.calculateAvoidance ----------------------------

// Avoidance magnitude between exactly two units at distance `d`.
function avoidMag(d, aPacked, bPacked, sameTeam) {
    const sim = simStub();
    const a = mk(sim, 1, { name: "A" }, 0, 0);
    const b = mk(sim, sameTeam ? 1 : 2, { name: "B" }, d, 0);
    a.inCombatPack = aPacked;
    b.inCombatPack = bPacked;
    const v = a.calculateAvoidance([a, b]);
    return Math.hypot(v.x, v.y);
}

test("W1 removes the social band only for engaged allies", () => {
    const soft = R + R + 2; // 17px
    const d = soft * 1.25;  // inside the 1.5x social band, outside overlap
    setW1({ scrumWalk: true });
    try {
        assert.equal(avoidMag(d, false, false, true), 0.5, "approaching allies repel");
        assert.equal(avoidMag(d, true, false, true), 0.5, "half-engaged pair repels");
        assert.equal(avoidMag(d, true, true, true), 0, "engaged allies may close");

        const overlapping = soft - 1;
        assert.ok(
            avoidMag(overlapping, true, true, true) > 3,
            "actual overlap still receives the full separation force",
        );
    } finally {
        setW1({ scrumWalk: false });
    }
});

test("calculateAvoidance does not relax a cross-team pair or a half-packed pair", () => {
    const d = 30;
    const ref = avoidMag(d, false, false, true);
    assert.equal(avoidMag(d, true, true, false).toFixed(6), ref.toFixed(6), "cross-team");
    assert.equal(avoidMag(d, true, false, true).toFixed(6), ref.toFixed(6), "half-packed");
    assert.equal(avoidMag(d, false, true, true).toFixed(6), ref.toFixed(6), "half-packed");
});

// ---- wiring ---------------------------------------------------------------

test("Simulation.update refreshes inCombatPack once per tick, one tick behind targeting", () => {
    const sim = simStub();
    const a = mk(sim, 1, { name: "A", range: 1.0 }, 100, 100);
    const e = mk(sim, 2, { name: "E" }, 137, 100);
    const s = realSim([a], [e]);
    assert.equal(a.inCombatPack, false, "false before the first update()");
    // The refresh runs at the TOP of update(), before unit.update() picks a
    // target -- so the first tick still sees target === null and the flag can
    // only go true from the second tick on. That one-tick lag is deliberate:
    // it is what makes both members of a pair read the same value in
    // calculateAvoidance (mid-tick) and in resolveCollisions (end of tick).
    s.update(1 / 60);
    assert.equal(a.inCombatPack, false, "tick 1: flag predates target selection");
    assert.ok(a.target === e, "tick 1 did select the target");
    s.update(1 / 60);
    assert.equal(a.inCombatPack, true, "tick 2: engaged");
    assert.equal(e.inCombatPack, true);
});

test("COMBAT_PACK_RANGED gates ranged attackers out of packing when false", () => {
    const sim = simStub();
    const r = mk(sim, 1, { name: "R", range: 5 }, 0, 0);
    const e = mk(sim, 2, { name: "E" }, 60, 0);
    r.target = e;
    // isRanged() is derived from attack_range when is_ranged is absent.
    assert.equal(r.isRanged(), true);
    assert.equal(r.computeCombatPack(), COMBAT_PACK_RANGED);
});
