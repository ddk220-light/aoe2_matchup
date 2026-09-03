// W2 -- REACTION WINDOW (constants.js W2; measured 2026-08-02 on the
// STANDARD_UNITS champion melee fights: tape units first move at 1.2-2.0 s,
// the engine moved all of them on one tick at 0.12 s).
//
// THE RULE. With W2.reactionWindow on and BOTH armies all-melee, each unit
// stands (no acquisition, no movement, no swing) until its deterministic
// slot in the measured 1.2-2.0 s window; ranged/mixed fights and the
// flag-off engine never reach the hold.
//
// OFF-SWITCH. w2ReactionHold() short-circuits on the flag before reading
// anything, and the hold branch in update() sits behind that predicate --
// off is a no-op by construction, pinned below.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    W2,
    setW2,
    W2_REACTION_MIN_S,
    W2_REACTION_MAX_S,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

function withW2(cfg, fn) {
    const saved = { ...W2 };
    setW2(cfg);
    try {
        return fn();
    } finally {
        setW2(saved);
    }
}

const W2_ON = { reactionWindow: true };

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

// Two melee blocks, 3 tiles apart, mid-canvas (no arena clamp in the stub).
function meleeFixture(sim, { n = 4, rangedFoe = false } = {}) {
    const a = [];
    for (let i = 0; i < n; i++) {
        const u = mk(sim, 1);
        u.x = 5 * TILE_SIZE;
        u.y = (10 + i) * TILE_SIZE;
        u.attackCooldown = 1e9; // no swings: the test reads movement only
        a.push(u);
    }
    const foes = [];
    for (let i = 0; i < n; i++) {
        const u = mk(sim, 2, { isRanged: rangedFoe, range: rangedFoe ? 4 : 0 });
        u.x = 8 * TILE_SIZE;
        u.y = (10 + i) * TILE_SIZE;
        u.attackCooldown = 1e9;
        foes.push(u);
    }
    return { a, foes };
}

function runTicks(sim, movers, n) {
    const dt = 1 / 60;
    for (let i = 0; i < n; i++) {
        sim.battleTime += dt;
        for (const u of movers) u.update(dt, movers, u.team === 1 ? sim.team2 : sim.team1);
    }
}

// ---- shipped configuration ---------------------------------------------------

test("[W2] ships OFF", () => {
    assert.equal(W2.reactionWindow, false);
});

test("[W2] setW2 rejects unknown flags", () => {
    assert.throws(() => setW2({ nope: true }), /unknown flag/);
});

// ---- OFF is a no-op ------------------------------------------------------------

test("[W2 off] no hold, no slot assigned, units move immediately", () => {
    const sim = simStub();
    const { a, foes } = meleeFixture(sim);
    assert.equal(a[0].w2ReactionHold(), false, "flag off: gate is false");
    runTicks(sim, [...a, ...foes], 30); // 0.5 s
    assert.equal(a[0]._w2ReactionUntil, undefined, "off: no slot is ever read");
    assert.ok(a[0].target, "off: acquired a target at once");
});

// ---- the mechanism -------------------------------------------------------------

test("[W2] all-melee: units stand until their slot, then walk", () => {
    withW2(W2_ON, () => {
        const sim = simStub();
        const { a, foes } = meleeFixture(sim, { n: 4 });
        const movers = [...a, ...foes];
        // 1.0 s: inside everyone's window -- nobody may hold a target or move.
        runTicks(sim, movers, 60);
        for (const u of a) {
            assert.equal(u.x, 5 * TILE_SIZE, "inside the window: standing");
            assert.equal(u.state, "idle");
        }
        // 2.1 s: past the whole window -- everyone has acquired and is walking.
        runTicks(sim, movers, 66);
        for (const u of a) {
            assert.ok(u.target, "after the window: acquired");
            assert.ok(u.x > 5 * TILE_SIZE, "after the window: walking");
        }
    });
});

test("[W2] slots are deterministic and spread across the measured window", () => {
    withW2(W2_ON, () => {
        const sim = simStub();
        const { a } = meleeFixture(sim, { n: 5 });
        // Read the slot each unit would get (first update caches it).
        const dt = 1 / 60;
        for (const u of a) {
            sim.battleTime = 0;
            u.update(dt, [...a], []);
        }
        const slots = a.map((u) => u._w2ReactionUntil);
        assert.deepEqual(
            slots,
            [...slots].sort((x, y) => x - y),
            "slots increase along the team array",
        );
        assert.equal(slots[0], W2_REACTION_MIN_S, "first slot at the window edge");
        assert.equal(slots[slots.length - 1], W2_REACTION_MAX_S, "last slot at the far edge");
        for (const s of slots) {
            assert.ok(s >= W2_REACTION_MIN_S && s <= W2_REACTION_MAX_S);
        }
        // Determinism: a fresh fixture reproduces the identical assignment.
        nextId = 0;
        const sim2 = simStub();
        const b = meleeFixture(sim2, { n: 5 }).a;
        for (const u of b) {
            sim2.battleTime = 0;
            u.update(dt, [...b], []);
        }
        assert.deepEqual(b.map((u) => u._w2ReactionUntil), slots);
    });
});

test("[W2] the hold does not touch the swing schedule after it lifts", () => {
    withW2(W2_ON, () => {
        const sim = simStub();
        const { a, foes } = meleeFixture(sim, { n: 1 });
        const u = a[0];
        u.attackCooldown = 0; // ready to swing from the start
        u.x = 5 * TILE_SIZE;
        foes[0].x = 5.5 * TILE_SIZE; // already in reach
        const dt = 1 / 60;
        // Inside the window: standing, no swing even in reach.
        for (let i = 0; i < 30; i++) {
            sim.battleTime += dt;
            u.update(dt, [u, foes[0]], sim.team2);
        }
        assert.equal(foes[0].currentHp, foes[0].maxHp, "no swing inside the window");
        // Past the window (single unit: slot == MIN): swings.
        for (let i = 0; i < 90; i++) {
            sim.battleTime += dt;
            u.update(dt, [u, foes[0]], sim.team2);
        }
        assert.ok(foes[0].currentHp < foes[0].maxHp, "swings after the window");
    });
});

// ---- scope ---------------------------------------------------------------------

test("[W2] a fight with ANY ranged unit is excluded byte-for-byte", () => {
    const run = (on) => {
        const sim = simStub(makeRng(1));
        const { a, foes } = meleeFixture(sim, { n: 3, rangedFoe: true });
        const movers = [...a, ...foes];
        for (const u of movers) u.attackCooldown = 1e9;
        const wrap = on ? () => withW2(W2_ON, () => runTicks(sim, movers, 30)) : () => runTicks(sim, movers, 30);
        wrap();
        return movers.map((u) => [u.x, u.y, u.state]);
    };
    nextId = 0;
    const off = run(false);
    nextId = 0;
    const on = run(true);
    assert.deepEqual(on, off, "mixed fight: no hold, identical trajectories");
});

test("[W2] the gate draws no rng", () => {
    const draws = [];
    const inner = makeRng(1);
    const rng = {
        next() { draws.push(1); return inner.next(); },
        getState() { return inner.getState(); },
    };
    withW2(W2_ON, () => {
        const sim = simStub(rng);
        const { a, foes } = meleeFixture(sim, { n: 4 });
        const before = draws.length;
        runTicks(sim, [...a, ...foes], 150);
        assert.equal(draws.length, before, "hold + slots draw nothing");
    });
});
