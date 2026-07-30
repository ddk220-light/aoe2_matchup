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
// move, is the reach arithmetic (see constants.js): a 1.0-tile-reach melee unit
// reaches 71 px past its own centre, a front-rank ally sits at the untouched
// 37 px cross-team floor, so a second rank only ever fights if the same-team
// floor drops below 34 px. Compressing cross-team instead would pull the ENEMY
// line tighter and hand the extra attackers to the SHORT-reach side -- measured,
// it flips paladin__vs__elite_steppe from 5/20 steppe wins back to 0/20.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    COMBAT_PACK_FACTOR,
    COMBAT_PACK_SLACK_TILES,
    COMBAT_PACK_RANGED,
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

function stats(name, { range = 0, size = 0.4 } = {}) {
    return {
        hp: 100, attack: 10, attack_range: range, attack_speed: 0.5,
        movement_speed: 1.4, melee_armor: 0, pierce_armor: 0,
        outline_size: size, accuracy: 100, unit_name: name,
    };
}

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
    // A 1.0-tile-reach unit with an 18 px radius reaches
    // 1.0*30 + 5 + 18 + 18 = 71 px, and the slack adds 1.5 tiles = 45 px, so
    // the predicate is true out to 116 px and false past it.
    const { sim, a, e } = pair({ range: 1.0 });
    a.target = e;
    const reach = a.attackRange + a.radius + e.radius;
    assert.equal(reach, 71, "reach arithmetic pinned");
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
    // benefits. 0-range reach is 5 + 18 + 18 = 41 px vs the lancer's 71 px.
    const { a, e } = pair({ range: 0 });
    a.target = e;
    assert.equal(a.attackRange + a.radius + e.radius, 41);
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
    const a = mk(sim, 1, { name: "A" }, 100, 100);
    const b = mk(sim, sameTeam ? 1 : 2, { name: "B" }, 110, 100);
    a.inCombatPack = aPacked;
    b.inCombatPack = bPacked;
    const s = sameTeam ? realSim([a, b], []) : realSim([a], [b]);
    s.resolveCollisions([a, b]);
    return Math.abs(b.x - a.x);
}

test("resolveCollisions compresses a same-team pair only when BOTH are packed", () => {
    const normal = 18 + 18 + 1; // a.radius + b.radius + 1
    assert.equal(xGapAfterCollisions(false, false, true).toFixed(6), normal.toFixed(6));
    assert.equal(xGapAfterCollisions(true, false, true).toFixed(6), normal.toFixed(6));
    assert.equal(xGapAfterCollisions(false, true, true).toFixed(6), normal.toFixed(6));
    assert.equal(
        xGapAfterCollisions(true, true, true).toFixed(6),
        (normal * COMBAT_PACK_FACTOR).toFixed(6),
    );
});

test("resolveCollisions leaves the CROSS-TEAM floor untouched even when both are packed", () => {
    const normal = 18 + 18 + 1;
    for (const [ap, bp] of [[false, false], [true, false], [false, true], [true, true]]) {
        assert.equal(
            xGapAfterCollisions(ap, bp, false).toFixed(6),
            normal.toFixed(6),
            `cross-team pair must not move (packed=${ap},${bp})`,
        );
    }
});

test("the compressed floor is tight enough for a second rank of 1.0-reach melee", () => {
    // front rank at the untouched cross-team floor + compressed same-team gap
    // must land inside the lancer's 71 px reach; a THIRD rank must not.
    const crossFloor = 37;
    const packedGap = 37 * COMBAT_PACK_FACTOR;
    assert.ok(crossFloor + packedGap <= 71, "second rank reaches");
    assert.ok(crossFloor + 2 * packedGap > 71, "third rank does not");
    // and the UNCOMPRESSED gap does not -- the bug this fixes
    assert.ok(crossFloor + 37 > 71, "pre-E8 second rank could never reach");
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

test("calculateAvoidance relaxes the soft floor for a packed same-team pair", () => {
    // 30 px is inside the normal soft minDist (18+18+2 = 38) but outside the
    // compressed one (38 * 0.6 = 22.8), so the packed pair should feel only the
    // weak out-of-band 0.5 force while the unpacked pair feels the strong one.
    const d = 30;
    const unpacked = avoidMag(d, false, false, true);
    const packed = avoidMag(d, true, true, true);
    assert.ok(unpacked > 3, `unpacked pair overlaps hard, got ${unpacked}`);
    assert.equal(packed.toFixed(6), (0.5).toFixed(6), "packed pair: weak band force only");
    assert.ok(packed < unpacked);
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
