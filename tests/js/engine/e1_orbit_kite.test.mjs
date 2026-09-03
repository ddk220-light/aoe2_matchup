// E1 — orbit kite: the group-kiting retreat basis becomes a clockwise arc
// about the fight centre.
//
// Measurement (docs/calibration/e1_kite_orbit_tapes.md / _engine.md): 78/78
// kite tapes orbit the fight centre CLOCKWISE on screen (median +1.13
// revolutions, sign consistency 0.94, radius held at r-slope −0.030 t/s);
// the engine at the same spawns flees radially (+0.146 t/s outward in 78/78,
// wall band in median 5 s, 86% of kiter deaths at a wall). E1 replaces ONLY
// the retreat basis dx/dy in moveAwayFromTarget — waypoint = C + rotate(d,
// s/r) with s the existing per-tick kite step — and touches nothing else.
//
// Groups:
//   1. the flag object and its setter (defaults pinned OFF);
//   2. the mechanism under explicit override: clockwise sign per the
//      documented convention, radius preservation, degenerate-centre and
//      no-centre fallbacks, the blend variant's measured ratio;
//   3. scoping/inertness: flag-off identity, orbitBlend-alone inertness,
//      steering-null (non-group-kiting) unreachability, purity;
//   4. the fight centre: createSimulation computes the spawn-centroid
//      midpoint once.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
    TILE_SIZE,
    E1,
    setE1,
    E1_ORBIT_TANRAD,
    E1_ORBIT_MIN_RADIUS_TILES,
} from "../../../apps/website/static/js/engine/constants.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import { createSimulation } from "../../../apps/website/static/js/engine/scenario.js";

const DT = 1 / 60;

const E1_OFF = { orbitKite: false, orbitBlend: false };
const E1_ON = { orbitKite: true, orbitBlend: false };
const E1_BLEND = { orbitKite: true, orbitBlend: true };

// Same arrow-wrap pattern as the other flag tests (c2c_pure_flight etc.):
// override, run, ALWAYS restore.
function withE1(cfg, fn) {
    const saved = { ...E1 };
    setE1(cfg);
    try {
        return fn();
    } finally {
        setE1(saved);
    }
}

// ---- fixtures ---------------------------------------------------------------
// Same stat blocks as the C2 tests, so the group-kite gate arithmetic
// (median range 7 > 0) is the one every other retreat test already exercises.

const MELEE = {
    hp: 70, attack: 12, attack_range: 0, attack_speed: 1.8,
    attack_delay: 0.4, movement_speed: 1.45, melee_armor: 1,
    pierce_armor: 1, outline_size: 0.2, accuracy: 100,
    unit_name: "Test Champion",
};
const ARCHER = {
    hp: 40, attack: 20, attack_range: 7, attack_speed: 2.0,
    projectile_speed: 7, accuracy: 100, movement_speed: 0.96,
    melee_armor: 0, pierce_armor: 0, outline_size: 0.2,
    unit_name: "Test Arbalester", is_ranged: true,
};

let nextId = 0;
function mk(sim, team, stats, slug = "u") {
    const u = new BattleUnit(
        `${team}-${nextId++}`, team, { ...stats }, slug, "Chinese", sim,
    );
    (team === 1 ? sim.team1 : sim.team2).push(u);
    return u;
}

function newSim(seed = 1) {
    return new Simulation(900, 600, makeRng(seed));
}

// The canonical geometry: fight centre at the canvas centre, kiter due EAST of
// it at radius R, its melee target far enough away (200 px) that avoidance is
// exactly zero and the only forces are the basis and whatever steering the
// test passes. steering = {x:0, y:0, rx:1, ry:0} is a live group-kite result
// whose away-basis points due +x (radially outward at this position), with no
// orbit/cohesion contribution — so the realised first-tick step direction IS
// the basis (vx/vy start at 0; the 0.3 smoothing renormalises to the composed
// direction exactly, as the C2c tests established).
const C = { x: 450, y: 300 };
const R = 100;

function orbitScene({ fightCenter = { ...C }, kiterAt = { x: C.x + R, y: C.y } } = {}) {
    const sim = newSim();
    sim.fightCenter = fightCenter;
    const kiter = mk(sim, 1, ARCHER, "arbalester");
    const foe = mk(sim, 2, MELEE, "champion");
    kiter.x = kiterAt.x; kiter.y = kiterAt.y;
    foe.x = kiterAt.x + 200; foe.y = kiterAt.y;
    kiter.target = foe;
    return { sim, kiter, foe };
}

const AWAY_STEER = () => ({ x: 0, y: 0, rx: 1, ry: 0 });

function step(kiter, units, steering) {
    const x0 = kiter.x, y0 = kiter.y;
    kiter.moveAwayFromTarget(DT, units, steering);
    return { mx: kiter.x - x0, my: kiter.y - y0 };
}

// ---- 1. the flag ------------------------------------------------------------

test("[E1] defaults: both rules ship OFF, and the object is exactly two rules", () => {
    assert.equal(E1.orbitKite, false);
    assert.equal(E1.orbitBlend, false);
    assert.deepEqual(Object.keys(E1).sort(), ["orbitBlend", "orbitKite"]);
});

test("[E1] setE1 rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setE1({ notARule: true }), /unknown flag/);
});

test("[E1] the blend ratio is the tape's measured 1.77, not a tuned number", () => {
    // the orbit-kite regression analysis.
    assert.equal(E1_ORBIT_TANRAD, 1.77);
    assert.equal(E1_ORBIT_MIN_RADIUS_TILES, 0.5);
});

// ---- 2. the mechanism -------------------------------------------------------

test("[E1] THE SIGN: the arc waypoint is CLOCKWISE per the documented convention", () => {
    // The tape boards define positive dtheta = increasing atan2 in tile
    // coordinates = clockwise on screen (e1_kite_orbit_tapes.json
    // sign_convention; TapeBox.worldToTile is a positive uniform scale, so
    // engine world atan2 has the same sense). A kiter due EAST of C (theta 0)
    // advanced clockwise must move toward +y — and its unwrapped atan2 about C
    // must INCREASE.
    withE1(E1_ON, () => {
        const { kiter, foe } = orbitScene();
        const theta0 = Math.atan2(kiter.y - C.y, kiter.x - C.x);
        const { mx, my } = step(kiter, [kiter, foe], AWAY_STEER());
        assert.ok(my > 0, `east of C, clockwise = +y (my ${my})`);
        assert.ok(Math.abs(mx) < Math.abs(my) * 0.05,
            `the step is tangential, not radial (mx ${mx}, my ${my})`);
        const theta1 = Math.atan2(kiter.y - C.y, kiter.x - C.x);
        assert.ok(theta1 > theta0, "atan2 about C increased (positive dtheta)");
    });
});

test("[E1] the sign holds at every bearing, not just the east fixture", () => {
    // Clockwise (atan2-increasing) tangent at angle a is (-sin a, cos a).
    withE1(E1_ON, () => {
        for (const a of [0, Math.PI / 3, Math.PI / 2, Math.PI, -2.1, 2.8]) {
            const at = { x: C.x + R * Math.cos(a), y: C.y + R * Math.sin(a) };
            const { kiter, foe } = orbitScene({ kiterAt: at });
            const { mx, my } = step(kiter, [kiter, foe], AWAY_STEER());
            const len = Math.hypot(mx, my);
            const dot = (mx * -Math.sin(a) + my * Math.cos(a)) / len;
            assert.ok(dot > 0.99,
                `bearing ${a.toFixed(2)}: step is the clockwise tangent (cos ${dot})`);
        }
    });
});

test("[E1] radius is preserved: the arc waypoint neither balloons nor collapses r", () => {
    withE1(E1_ON, () => {
        const { kiter, foe } = orbitScene();
        // Many ticks along the arc with nothing else pulling: the radius about
        // C must hold to within the chord's second-order error, not drift the
        // way the radial basis (which grows r by moveSpeed*dt per tick) does.
        for (let i = 0; i < 240; i++) {
            kiter.moveAwayFromTarget(DT, [kiter, foe], AWAY_STEER());
            // keep the foe out of avoidance range while the kiter circles
            foe.x = kiter.x + 200; foe.y = kiter.y;
        }
        const r = Math.hypot(kiter.x - C.x, kiter.y - C.y);
        assert.ok(Math.abs(r - R) < 0.5,
            `after 4 s of orbiting, r ${r.toFixed(3)} still ~${R}`);
        // and it actually went somewhere: ~4 s * 28.8 px/s / (2*pi*100) of arc
        const theta = Math.atan2(kiter.y - C.y, kiter.x - C.x);
        assert.ok(theta > 0.5, `swept a real arc (theta ${theta.toFixed(3)})`);
    });
});

test("[E1] degenerate centre: inside 0.5 tiles of C the radial basis is kept", () => {
    withE1(E1_ON, () => {
        const inside = E1_ORBIT_MIN_RADIUS_TILES * TILE_SIZE - 1;
        const { kiter, foe } = orbitScene({
            kiterAt: { x: C.x + inside, y: C.y },
        });
        const { mx, my } = step(kiter, [kiter, foe], AWAY_STEER());
        assert.ok(mx > 0, "falls back to the away basis (+x)");
        assert.ok(Math.abs(my) < 1e-9, `no tangential component (my ${my})`);
    });
});

test("[E1] no fight centre on the sim: the step is the flag-off step exactly", () => {
    const off = withE1(E1_OFF, () => {
        const { kiter, foe } = orbitScene();
        return step(kiter, [kiter, foe], AWAY_STEER());
    });
    const noCentre = withE1(E1_ON, () => {
        const { kiter, foe } = orbitScene({ fightCenter: null });
        return step(kiter, [kiter, foe], AWAY_STEER());
    });
    assert.equal(noCentre.mx, off.mx);
    assert.equal(noCentre.my, off.my);
});

test("[E1] orbitBlend: tangent blends with the away basis at exactly 1.77:1", () => {
    withE1(E1_BLEND, () => {
        const { kiter, foe } = orbitScene();
        const { mx, my } = step(kiter, [kiter, foe], AWAY_STEER());
        assert.ok(mx > 0 && my > 0, "both components present");
        // away = (1, 0), tangent ~ (0, 1) at this bearing (chord error is
        // O(phi), phi = s/r ~ 0.005): the composed direction's slope is the
        // measured ratio.
        assert.ok(Math.abs(my / mx - E1_ORBIT_TANRAD) < 0.05,
            `my/mx ${(my / mx).toFixed(3)} ~ ${E1_ORBIT_TANRAD}`);
    });
});

// ---- 3. scoping / inertness ---------------------------------------------------

test("[E1] OFF is byte-identical: the flag-off step equals the pre-E1 composition", () => {
    // Structural claim made observable: with orbitKite off the E1 branch is
    // unreachable, so a scene WITH a fight centre must step exactly like one
    // without (the pre-E1 engine had no fightCenter at all).
    const withCentre = withE1(E1_OFF, () => {
        const { kiter, foe } = orbitScene();
        return step(kiter, [kiter, foe], AWAY_STEER());
    });
    const without = withE1(E1_OFF, () => {
        const { kiter, foe } = orbitScene({ fightCenter: null });
        return step(kiter, [kiter, foe], AWAY_STEER());
    });
    assert.equal(withCentre.mx, without.mx);
    assert.equal(withCentre.my, without.my);
    assert.ok(withCentre.mx > 0, "and it is the radial away step");
});

test("[E1] orbitBlend alone is inert — it is a modifier of orbitKite, not a rule", () => {
    const off = withE1(E1_OFF, () => {
        const { kiter, foe } = orbitScene();
        return step(kiter, [kiter, foe], AWAY_STEER());
    });
    const blendOnly = withE1({ orbitKite: false, orbitBlend: true }, () => {
        const { kiter, foe } = orbitScene();
        return step(kiter, [kiter, foe], AWAY_STEER());
    });
    assert.equal(blendOnly.mx, off.mx);
    assert.equal(blendOnly.my, off.my);
});

test("[E1] steering-null retreats (non-group-kiting) are untouched with the flag ON", () => {
    // kiteSteering returns null for siege / melee / non-out-ranging sides, and
    // the E1 branch is gated on steering — so a null-steering retreat with the
    // flag on must equal the flag-off one, fight centre present or not.
    const on = withE1(E1_ON, () => {
        const { kiter, foe } = orbitScene();
        return step(kiter, [kiter, foe], null);
    });
    const off = withE1(E1_OFF, () => {
        const { kiter, foe } = orbitScene();
        return step(kiter, [kiter, foe], null);
    });
    assert.equal(on.mx, off.mx);
    assert.equal(on.my, off.my);
});

test("[E1] the rule actually reaches a real kite fight (hash moves with the flag)", () => {
    // Same tanky-chaser fixture as the C2 tests: archers that must kite,
    // chasers that survive long enough to chase. fightCenter set the way
    // createSimulation sets it (spawn-centroid midpoint).
    const CHASER = {
        hp: 180, attack: 14, attack_range: 0, attack_speed: 1.8,
        attack_delay: 0.4, movement_speed: 1.45, melee_armor: 2,
        pierce_armor: 4, outline_size: 0.2, accuracy: 100,
        unit_name: "Test Chaser",
    };
    const build = (seed) => {
        const sim = newSim(seed);
        for (let i = 0; i < 8; i++) {
            const u = mk(sim, 1, { ...ARCHER, attack: 8 }, "arbalester");
            u.x = 300 + (i % 2) * 22; u.y = 190 + Math.floor(i / 2) * 26;
        }
        for (let i = 0; i < 8; i++) {
            const u = mk(sim, 2, CHASER, "champion");
            u.x = 420 + (i % 2) * 22; u.y = 190 + Math.floor(i / 2) * 26;
        }
        const cen = (team) => ({
            x: team.reduce((s, u) => s + u.x, 0) / team.length,
            y: team.reduce((s, u) => s + u.y, 0) / team.length,
        });
        const c1 = cen(sim.team1), c2 = cen(sim.team2);
        sim.fightCenter = { x: (c1.x + c2.x) / 2, y: (c1.y + c2.y) / 2 };
        return sim;
    };
    const run = (seed) => {
        const sim = build(seed);
        for (let i = 0; i < 60 * 30; i++) sim.update(DT);
        return sim.stateHash();
    };
    for (const seed of [42, 7]) {
        const off = withE1(E1_OFF, () => run(seed));
        const off2 = withE1(E1_OFF, () => run(seed));
        assert.equal(off, off2, "the off path is deterministic");
        const on = withE1(E1_ON, () => run(seed));
        assert.notEqual(on, off, `seed ${seed}: the orbit must reach the fight`);
    }
});

test("[E1] the rule consumes no randomness", () => {
    withE1(E1_ON, () => {
        let draws = 0;
        const inner = makeRng(1);
        const rng = {
            next() { draws++; return inner.next(); },
            getState() { return inner.getState(); },
        };
        const sim = new Simulation(900, 600, rng);
        sim.fightCenter = { ...C };
        const kiter = mk(sim, 1, ARCHER, "arbalester");
        const foe = mk(sim, 2, MELEE, "champion");
        kiter.x = C.x + R; kiter.y = C.y;
        foe.x = kiter.x + 200; foe.y = kiter.y;
        kiter.target = foe;
        kiter.moveAwayFromTarget(DT, [kiter, foe], AWAY_STEER());
        assert.equal(draws, 0, "the arc is geometry, never a draw");
    });
});

// ---- 4. the fight centre ------------------------------------------------------

test("[E1] createSimulation stores C = midpoint of the two spawn centroids", () => {
    const sim = createSimulation({
        teams: [
            { combatDict: ARCHER, slug: "arbalester", civ: "Chinese", count: 3 },
            { combatDict: MELEE, slug: "champion", civ: "Franks", count: 5 },
        ],
        seed: 11,
    });
    const cen = (team) => ({
        x: team.reduce((s, u) => s + u.x, 0) / team.length,
        y: team.reduce((s, u) => s + u.y, 0) / team.length,
    });
    const c1 = cen(sim.team1), c2 = cen(sim.team2);
    assert.ok(sim.fightCenter, "fightCenter is set");
    assert.ok(Math.abs(sim.fightCenter.x - (c1.x + c2.x) / 2) < 1e-9);
    assert.ok(Math.abs(sim.fightCenter.y - (c1.y + c2.y) / 2) < 1e-9);
});

test("[E1] TILE_SIZE sanity — the px geometry above is the engine's", () => {
    assert.equal(TILE_SIZE, 30);
});
