// W1 -- SCRUM WALK (docs/calibration/ps_live_forensics.md, measurements in
// data/calibration/analysis/ps_live_forensics.json).
//
// THE DEFECT. On the 12 position-valid paladin__vs__elite_steppe live rounds
// the engine's opening is exact (concurrency, ring density, the 2/4/6
// attackers-per-victim ceiling) but a blocked melee attacker whose locked
// victim is out of reach PARKS: idle-out-of-reach 28.8% of living-paladin
// frames vs the tape's 6.8%, walking 5.7% vs 22.8%. The tape's blocked
// attacker walks TANGENTIALLY around the blocking mass to the next open face.
//
// THE RULE. With W1.scrumWalk on, a MELEE unit whose current lock is alive,
// MELEE (established melee-vs-melee scope), OUT OF REACH, and whose straight
// lane is blocked (E15b's own laneClear() corridor test, re-asked every tick
// -- no timer) swaps its approach basis for the chord toward its
// offset-from-lock rotated about the lock by phi = moveSpeed*dt / r (E1's
// rotate math; no new magnitude constant), in whichever rotation sense has
// the lower summed blocker proximity (sum of 1/d^2 -- a comparison, not a
// threshold). It keeps its lock; the radial approach resumes the tick the
// lane clears or the lock comes in reach.
//
// OFF-SWITCH. w1ScrumBlocked() short-circuits on the flag before reading
// anything, and the basis swap in moveTowardTarget is behind
// `if (W1.scrumWalk)` -- off is a no-op by construction, pinned below.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    W1,
    setW1,
} from "../../../apps/website/static/js/engine/constants.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Same arrow-wrap pattern as the other flag tests (c3/c4/e1): override, run,
// ALWAYS restore.
function withW1(cfg, fn) {
    const saved = { ...W1 };
    setW1(cfg);
    try {
        return fn();
    } finally {
        setW1(saved);
    }
}

const W1_ON = { scrumWalk: true };

function simStub(rng) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: rng || makeRng(1),
    };
}

function stats({
    range = 0, isRanged = false, hp = 100, attack = 10,
} = {}) {
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

// Mid-canvas anchor: the stub sim has no arena, so moveTowardTarget's
// rectangle clamp lives at the canvas edge -- a fixture at y = 0 would be
// clamped every tick and fake an asymmetry. Keep everything far from walls.
const AX = 5 * TILE_SIZE;
const AY = 10 * TILE_SIZE;

// The canonical blocked-scrum fixture: attacker at the anchor, its melee lock
// 3 tiles down +x (far out of reach), and a blocking body dead-centre on the
// straight lane. laneClear(lock) is false by construction. The attacker's
// stuckTimer is primed positive -- the engine's own no-progress verdict,
// which in a real scrum the stuck bar accrues after one stalled tick; the
// gate reads it, it never invents one.
function blockedFixture(sim, { blockerTeam = 1, stuck = 0.2 } = {}) {
    const a = mk(sim, 1);
    const t = mk(sim, 2, { hp: 1e6 });
    a.x = AX; a.y = AY;
    t.x = AX + 3 * TILE_SIZE; t.y = AY;
    const b = mk(sim, blockerTeam, { hp: 1e6 });
    b.x = AX + 1.5 * TILE_SIZE; b.y = AY;
    a.target = t;
    a.hasAcquiredTarget = true;
    a.stuckTimer = stuck;
    a.lastDistToTarget = a.distanceTo(t);
    // Cooldown up so the attacker never swings mid-test; the lock is 3 tiles
    // away anyway.
    a.attackCooldown = 1e9;
    b.attackCooldown = 1e9;
    return { a, t, b };
}

function runTicks(sim, mover, allUnits, enemies, n) {
    const dt = 1 / 60;
    const path = [];
    for (let i = 0; i < n; i++) {
        sim.battleTime += dt;
        mover.update(dt, allUnits, enemies);
        path.push([mover.x, mover.y]);
    }
    return path;
}

// ---- shipped configuration ---------------------------------------------------

test("[W1] ships OFF", () => {
    // OFF until the W1 iteration boards land -- same A/B gate discipline as
    // E1/C3/C4. The defaults board must be byte-identical with this flag
    // absent (parity_check.mjs is the structural proof).
    assert.equal(W1.scrumWalk, false);
});

test("[W1] setW1 rejects unknown flags", () => {
    assert.throws(() => setW1({ nope: true }), /unknown flag/);
});

// ---- OFF is a no-op ------------------------------------------------------------

test("[W1 off] the gate short-circuits and the basis is never swapped", () => {
    const sim = simStub();
    const { a } = blockedFixture(sim);
    assert.equal(a.w1ScrumBlocked(), false, "flag off: gate is false");
    assert.equal(a.w1ScrumWaypoint(1 / 60), null, "flag off: no waypoint");
});

// ---- the mechanism -------------------------------------------------------------

test("[W1] a blocked out-of-reach attacker drifts tangentially instead of pushing radially", () => {
    // Flag OFF: the blocker is outside avoidance reach at the start, so the
    // attacker walks the straight lane (pure +x, y stays 0). Flag ON: the
    // very same fixture drifts off-axis (either rotation sense) while
    // holding, not closing, the radial gap this early in the arc.
    const N = 30; // 0.5 s
    const off = (() => {
        const sim = simStub(makeRng(1));
        const { a, t, b } = blockedFixture(sim);
        const path = runTicks(sim, a, [a, b, t], sim.team2, N);
        const closed = 3 * TILE_SIZE - Math.sqrt(
            (path[N - 1][0] - t.x) ** 2 + (path[N - 1][1] - t.y) ** 2,
        );
        return { path, closed };
    })();
    assert.equal(off.path[N - 1][1], AY, "flag off: the radial push has no y");

    withW1(W1_ON, () => {
        const sim = simStub(makeRng(1));
        const { a, t, b } = blockedFixture(sim);
        assert.equal(a.w1ScrumBlocked(), true, "fixture really is blocked");
        const r0 = a.distanceTo(t);
        const path = runTicks(sim, a, [a, b, t], sim.team2, N);
        const y = path[N - 1][1] - AY;
        assert.ok(Math.abs(y) > 0.2 * a.moveSpeed * (N / 60),
            `tangential drift, either sense (|y| = ${Math.abs(y)})`);
        // A tangential arc holds the radius: the attacker must not have
        // closed the radial gap the way the flag-off radial walk does.
        const r1 = a.distanceTo(t);
        assert.ok(r0 - r1 < 0.5 * off.closed,
            `arc holds the radius (closed ${r0 - r1} vs radial ${off.closed})`);
        assert.equal(a.target, t, "the lock is kept while drifting");
        assert.equal(a.state, "moving", "drifting is walking, not idling");
    });
});

test("[W1] the drift takes the less obstructed rotation sense", () => {
    // A second blocking mass parked below the lane makes the -y side the
    // crowded one: the drift must go +y. Mirroring it above the lane must
    // flip the choice -- the comparison is summed blocker proximity, so the
    // test asserts both senses are reachable.
    for (const side of [1, -1]) {
        withW1(W1_ON, () => {
            const sim = simStub(makeRng(1));
            const { a, t, b } = blockedFixture(sim);
            const c = mk(sim, 1, { hp: 1e6 });
            c.x = AX; c.y = AY + side * -1.0 * TILE_SIZE; // crowd one side
            c.attackCooldown = 1e9;
            const wp = a.w1ScrumWaypoint(1 / 60);
            assert.ok(wp, "blocked: a waypoint exists");
            assert.ok(Math.sign(wp.y - a.y) === side,
                `crowd at ${side * -1}y => drift toward ${side}y (wp.y ${wp.y})`);
        });
    }
});

test("[W1] a blocked lane WITHOUT the engine's no-progress verdict does not drift", () => {
    // The opening-preservation clause, measured this round: a unit in a
    // moving queue has its lane occupied every tick but is still closing --
    // the stuck bar decays 2x while progress is made -- and it must keep
    // pressing radially (that press is what builds the tape-exact opening
    // ring: first10s 8.0, ceiling 2/4/6). Only stuckTimer > 0 -- the
    // engine's own stalled verdict -- opens the gate.
    withW1(W1_ON, () => {
        const sim = simStub(makeRng(1));
        const { a } = blockedFixture(sim, { stuck: 0 });
        assert.equal(a.w1ScrumBlocked(), false, "progressing: gate is false");
        assert.equal(a.w1ScrumWaypoint(1 / 60), null);
        a.stuckTimer = 0.05; // the engine's verdict after one stalled tick
        assert.equal(a.w1ScrumBlocked(), true, "stalled: gate opens");
    });
});

test("[W1] normal approach resumes the tick the lane clears", () => {
    withW1(W1_ON, () => {
        const sim = simStub(makeRng(1));
        const { a, t, b } = blockedFixture(sim);
        assert.equal(a.w1ScrumBlocked(), true);
        // The blocker steps far off the corridor: the gate must drop the
        // same tick, with no latch or timer holding the drift.
        b.y = AY + 3 * TILE_SIZE;
        assert.equal(a.w1ScrumBlocked(), false, "lane clear => gate off");
        assert.equal(a.w1ScrumWaypoint(1 / 60), null);
    });
});

test("[W1] an UNBLOCKED attacker approaches byte-identically to the flag-off engine", () => {
    const N = 60;
    const run = () => {
        const sim = simStub(makeRng(1));
        const a = mk(sim, 1);
        const t = mk(sim, 2, { hp: 1e6 });
        a.x = AX; a.y = AY + 0.3 * TILE_SIZE;
        t.x = AX + 3 * TILE_SIZE; t.y = AY;
        a.target = t; a.hasAcquiredTarget = true;
        a.attackCooldown = 1e9;
        return runTicks(sim, a, [a, t], sim.team2, N);
    };
    nextId = 0;
    const off = run();
    nextId = 0;
    const on = withW1(W1_ON, run);
    assert.deepEqual(on, off, "no blocker: trajectories identical");
});

test("[W1] an IN-REACH attacker is unaffected even with bodies packed around it", () => {
    withW1(W1_ON, () => {
        const sim = simStub(makeRng(1));
        const a = mk(sim, 1);
        const t = mk(sim, 2, { hp: 1e6 });
        a.x = AX; a.y = AY;
        t.x = AX + a.radius + t.radius; t.y = AY;
        const b = mk(sim, 1, { hp: 1e6 });
        b.x = AX + (a.radius + t.radius) / 2; b.y = AY + 1; // on the (trivial) lane
        a.target = t; a.hasAcquiredTarget = true;
        assert.equal(a.w1ScrumBlocked(), false, "in reach: gate is false");
        const dt = 1 / 60;
        sim.battleTime += dt;
        a.update(dt, [a, b, t], sim.team2);
        assert.equal(a.x, AX, "in-reach attacker does not walk");
        assert.notEqual(a.state, "moving");
    });
});

test("[W1] RANGED units are excluded on both ends", () => {
    withW1(W1_ON, () => {
        // Ranged attacker: never reaches the drift whatever its lane looks
        // like.
        const sim = simStub(makeRng(1));
        const archer = mk(sim, 1, { range: 4, isRanged: true });
        const t = mk(sim, 2, { hp: 1e6 });
        archer.x = AX; archer.y = AY;
        t.x = AX + 8 * TILE_SIZE; t.y = AY;
        const b = mk(sim, 1, { hp: 1e6 });
        b.x = AX + 4 * TILE_SIZE; b.y = AY;
        archer.target = t;
        archer.stuckTimer = 0.2; // even with the stalled verdict primed
        assert.equal(archer.w1ScrumBlocked(), false, "ranged attacker: excluded");

        // Melee attacker chasing a RANGED target: a pursuit, not a brawl --
        // same scope as MELEE_TARGET_LOCK / bump retarget / the lane rule.
        const sim2 = simStub(makeRng(1));
        const a = mk(sim2, 1);
        const rt = mk(sim2, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = AX; a.y = AY;
        rt.x = AX + 3 * TILE_SIZE; rt.y = AY;
        const b2 = mk(sim2, 1, { hp: 1e6 });
        b2.x = AX + 1.5 * TILE_SIZE; b2.y = AY;
        a.target = rt;
        a.stuckTimer = 0.2; // even with the stalled verdict primed
        assert.equal(a.w1ScrumBlocked(), false, "ranged victim: excluded");
    });
});

test("[W1] a melee-chases-ranged trajectory is byte-identical with the flag on", () => {
    // The behavioural twin of the scope assertion above: same blocked
    // geometry, ranged victim -- the walk must be the flag-off walk exactly.
    const N = 60;
    const run = () => {
        const sim = simStub(makeRng(1));
        const a = mk(sim, 1);
        const rt = mk(sim, 2, { range: 4, isRanged: true, hp: 1e6 });
        a.x = AX; a.y = AY;
        rt.x = AX + 3 * TILE_SIZE; rt.y = AY;
        const b = mk(sim, 1, { hp: 1e6 });
        b.x = AX + 1.5 * TILE_SIZE; b.y = AY;
        b.attackCooldown = 1e9;
        a.target = rt; a.hasAcquiredTarget = true;
        a.attackCooldown = 1e9;
        return runTicks(sim, a, [a, b, rt], sim.team2, N);
    };
    nextId = 0;
    const off = run();
    nextId = 0;
    const on = withW1(W1_ON, run);
    assert.deepEqual(on, off, "pursuit of a ranged victim: untouched");
});

test("[W1] the drift never touches the rng", () => {
    const draws = [];
    const inner = makeRng(1);
    const rng = {
        next() { draws.push(1); return inner.next(); },
        getState() { return inner.getState(); },
    };
    withW1(W1_ON, () => {
        const sim = simStub(rng);
        const { a, t, b } = blockedFixture(sim);
        const before = draws.length;
        a.w1ScrumBlocked();
        a.w1ScrumWaypoint(1 / 60);
        runTicks(sim, a, [a, b, t], sim.team2, 30);
        assert.equal(draws.length, before, "gate + waypoint + walk draw nothing");
    });
});
