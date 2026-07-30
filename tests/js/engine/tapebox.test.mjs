// Tests for the "tapebox" scenario (apps/website/static/js/engine/arena.js's
// TapeBox + scenario.js's `spec.positions`) — E12's tape-faithful initial
// conditions for calibration scoring.
//
// Three jobs, in order of how much damage getting them wrong would do:
//
//   1. THE LEGACY PATH IS UNTOUCHED. Every scoreboard through E11, the golden
//      panel and tools/simjs/parity_check.mjs were produced with no arena and
//      the synthesised column layout. Turning tapebox on must not be able to
//      move any of them, so the plain path's spawns AND its rng draw stream are
//      pinned here.
//   2. SPAWNS ARE THE TAPE'S, EXACTLY. The whole point is that positions are
//      DATA, not a formation the engine invents: units land on the given tiles
//      to the floating-point bit, with no jitter, at every seed.
//   3. THE WALLS HOLD. Units are constrained to the tapes' own measured
//      position bounds, both at spawn and for the whole fight.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
    createSimulation,
    TapeBox,
    Arena,
    makeArena,
    TILE_SIZE,
    TAPEBOX_MIN_TILE,
    TAPEBOX_MAX_TILE,
} from "../../../apps/website/static/js/engine/index.js";

const dicts = JSON.parse(
    readFileSync("tools/simjs/golden/combat_dicts.json", "utf8"),
);
const CHAMP = dicts["Franks|champion"];
const JAG = dicts["Aztecs|elite_jaguar_warrior_aztecs"];

// A tape-shaped pair of blocks: 3x2 each, ~8 tiles apart in tile-y, which is
// the corpus's own layout (centroid separation median 8.12 tiles).
const POS_A = [
    [7.5, 3.5], [8.5, 3.5], [9.5, 3.5],
    [7.5, 4.5], [8.5, 4.5], [9.5, 4.5],
];
const POS_B = [
    [5.5, 11.5], [6.5, 11.5], [7.5, 11.5],
    [5.5, 12.5], [6.5, 12.5], [7.5, 12.5],
];

function tapeboxSim(seed, { posA = POS_A, posB = POS_B } = {}) {
    return createSimulation({
        teams: [
            {
                combatDict: CHAMP, slug: "champion", civ: "Franks",
                count: posA.length, positions: posA,
            },
            {
                combatDict: JAG, slug: "elite_jaguar_warrior_aztecs",
                civ: "Aztecs", count: posB.length, positions: posB,
            },
        ],
        seed,
        arena: "tapebox",
    });
}

function plainSim(seed, n = 6) {
    return createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: n },
            {
                combatDict: JAG, slug: "elite_jaguar_warrior_aztecs",
                civ: "Aztecs", count: n,
            },
        ],
        seed,
    });
}

// ---- 1. the legacy path is untouched ----------------------------------------

test("makeArena builds a TapeBox only for the explicit \"tapebox\" opt-in", () => {
    assert.ok(makeArena("tapebox") instanceof TapeBox);
    assert.equal(makeArena(null), null);
    assert.equal(makeArena("plain"), null);
    assert.equal(makeArena("plain-legacy"), null); // the CLI word is not a spec
    assert.ok(!(makeArena("golden") instanceof TapeBox));
    const t = new TapeBox({});
    assert.equal(makeArena(t), t);
});

test("tapebox consumes exactly the same rng draws as the plain path", () => {
    // One draw per unit in index order either way. The jitter is drawn and then
    // deliberately NOT applied to a tape position (see scenario.js), precisely
    // so this stays true and nothing downstream of spawning can shift.
    const plain = plainSim(9);
    const box = tapeboxSim(9);
    assert.equal(plain.rng.getState(), box.rng.getState());
});

test("the plain column layout is unchanged by the positions branch", () => {
    const sim = plainSim(4, 12);
    const xs = sim.team1.map((u) => u.x);
    const ys = sim.team1.map((u) => u.y);
    assert.equal(sim.arena, null);
    assert.ok(Math.max(...xs) - Math.min(...xs) <= 10); // jitter only
    assert.ok(Math.max(...ys) - Math.min(...ys) > 400);
    assert.ok(Math.min(...xs) < 60);
    assert.ok(Math.min(...sim.team2.map((u) => u.x)) > 800);
});

// ---- 2. spawns are the tape's, exactly ---------------------------------------

test("tapebox spawns land EXACTLY on the given tile positions", () => {
    const sim = tapeboxSim(1);
    const box = sim.arena;
    assert.ok(box instanceof TapeBox);
    for (const [team, pos] of [[sim.team1, POS_A], [sim.team2, POS_B]]) {
        team.forEach((u, i) => {
            const w = box.tileToWorld(pos[i][0], pos[i][1]);
            assert.equal(u.x, w.x, `team unit ${i} x`);
            assert.equal(u.y, w.y, `team unit ${i} y`);
        });
    }
});

test("no jitter: every seed spawns the same army in the same place", () => {
    const a = tapeboxSim(1);
    const b = tapeboxSim(17);
    for (const key of ["team1", "team2"]) {
        a[key].forEach((u, i) => {
            assert.equal(u.x, b[key][i].x);
            assert.equal(u.y, b[key][i].y);
        });
    }
});

test("the tile->world mapping centres the 16-tile map on the canvas", () => {
    const box = new TapeBox({});
    const c = box.tileToWorld(8, 8);
    assert.equal(c.x, 450);
    assert.equal(c.y, 300);
    // One tile is one TILE_SIZE, unrotated, both axes.
    const p = box.tileToWorld(9, 8);
    const q = box.tileToWorld(8, 9);
    assert.equal(p.x - c.x, TILE_SIZE);
    assert.equal(p.y, c.y);
    assert.equal(q.y - c.y, TILE_SIZE);
    assert.equal(q.x, c.x);
    // ...and the inverse round-trips.
    const back = box.worldToTile(p.x, p.y);
    assert.ok(Math.abs(back.tx - 9) < 1e-12 && Math.abs(back.ty - 8) < 1e-12);
});

test("a count/positions mismatch fails loudly instead of spawning a short army", () => {
    assert.throws(
        () =>
            createSimulation({
                teams: [
                    {
                        combatDict: CHAMP, slug: "champion", civ: "Franks",
                        count: 5, positions: POS_A, // 6 positions
                    },
                    {
                        combatDict: JAG, slug: "elite_jaguar_warrior_aztecs",
                        civ: "Aztecs", count: POS_B.length, positions: POS_B,
                    },
                ],
                seed: 1,
                arena: "tapebox",
            }),
        /5 units but 6 spawn positions/,
    );
});

test("positions without a tile-capable arena fail loudly", () => {
    assert.throws(
        () =>
            createSimulation({
                teams: [
                    {
                        combatDict: CHAMP, slug: "champion", civ: "Franks",
                        count: POS_A.length, positions: POS_A,
                    },
                    {
                        combatDict: JAG, slug: "elite_jaguar_warrior_aztecs",
                        civ: "Aztecs", count: POS_B.length, positions: POS_B,
                    },
                ],
                seed: 1, // no arena at all
            }),
        /needs an arena with tileToWorld/,
    );
});

// ---- 3. the walls hold -------------------------------------------------------

test("the play area is the tapes' measured 13.6-tile square, no obstruction", () => {
    const box = new TapeBox({});
    const lo = box.tileToWorld(TAPEBOX_MIN_TILE, TAPEBOX_MIN_TILE);
    const hi = box.tileToWorld(TAPEBOX_MAX_TILE, TAPEBOX_MAX_TILE);
    const poly = box.boundaryPath();
    assert.equal(poly.length, 4);
    assert.equal(Math.min(...poly.map((p) => p.x)), lo.x);
    assert.equal(Math.max(...poly.map((p) => p.x)), hi.x);
    assert.ok(
        Math.abs((hi.x - lo.x) / TILE_SIZE - (TAPEBOX_MAX_TILE - TAPEBOX_MIN_TILE)) < 1e-9,
    );
    // Square: same span on both axes.
    assert.equal(hi.x - lo.x, hi.y - lo.y);
    // Nothing is ever blocked, and obstacleSteer contributes nothing — that
    // omission is deliberate and documented in arena.js.
    assert.equal(box.blocks(450, 300), false);
    assert.equal(box.obstacleSteer(450, 300, 8, 1, 0), null);
    assert.deepEqual(box.obstructionShapes(), []);
    assert.equal(box.rockShape().r, 0);
});

test("constrain() clamps a unit to the walls, in CENTRE space (no radius pad)", () => {
    const box = new TapeBox({});
    const u = { x: -500, y: 5000, radius: 7.5 };
    box.constrain(u);
    assert.equal(u.x, box.x0);
    assert.equal(u.y, box.y1);
    assert.ok(box.isInside(u.x, u.y));
    // The bounds are the tapes' own unit-CENTRE extremes, so a body sitting on
    // the wall is at the wall, not a radius inside it.
    const t = box.worldToTile(u.x, u.y);
    assert.ok(Math.abs(t.tx - TAPEBOX_MIN_TILE) < 1e-12);
    assert.ok(Math.abs(t.ty - TAPEBOX_MAX_TILE) < 1e-12);

    // A unit already inside is left alone, bit for bit.
    const inside = { x: 451.25, y: 299.5, radius: 7.5 };
    box.constrain(inside);
    assert.equal(inside.x, 451.25);
    assert.equal(inside.y, 299.5);
});

test("a whole tapebox fight never puts a living unit outside the walls", () => {
    const sim = tapeboxSim(3);
    const box = sim.arena;
    let ticks = 0;
    while (sim.winner === null && ticks < 60 * 180) {
        sim.step(1 / 60);
        ticks++;
        if (ticks % 20) continue;
        for (const u of [...sim.team1, ...sim.team2]) {
            if (u.state === "dead") continue;
            assert.ok(box.isInside(u.x, u.y), `outside at tick ${ticks}`);
        }
    }
    assert.ok(ticks > 0);
    assert.notEqual(sim.winner, null, "fight never resolved");
});

test("spawns pressed against a wall are clamped, not left outside", () => {
    // Tape positions are always well inside the box, but the clamp is what
    // guarantees that — assert it rather than assume it.
    const sim = tapeboxSim(1, {
        posA: [[0.1, 0.1], [0.1, 1.1]],
        posB: [[15.9, 15.9], [15.9, 14.9]],
    });
    const box = sim.arena;
    for (const u of [...sim.team1, ...sim.team2]) {
        assert.ok(box.isInside(u.x, u.y), "spawned outside the walls");
    }
    assert.equal(sim.team1[0].x, box.x0);
    assert.equal(sim.team2[0].x, box.x1);
});

test("the golden arena still uses its corner anchors, not tape positions", () => {
    // The two specs must not have blurred into each other: Arena keeps
    // spawnLayout, TapeBox declines it.
    assert.equal(new Arena({}).usesSpawnAnchors, true);
    assert.equal(new TapeBox({}).usesSpawnAnchors, false);
});
