// Tests for the opt-in golden arena (apps/website/static/js/engine/arena.js).
//
// Two jobs, and the first one matters more than the second:
//
//   1. PROVE THE FEATURE IS INERT WHEN OFF. Every batch run, the 155-fight
//      calibration corpus and tools/simjs/parity_check.mjs all build sims with
//      no `arena` field, and they must keep producing bit-identical results. The
//      "plain default" tests below pin that: same seed, same hash stream, with
//      and against a sim built through the new code path.
//
//   2. Check the arena itself does what it claims: spawns land inside the play
//      area and outside the trees, the trees are actually impassable, and a
//      chaser routes AROUND them rather than stopping at them.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
    createSimulation,
    Arena,
    makeArena,
    TILE_SIZE,
} from "../../../apps/website/static/js/engine/index.js";

const dicts = JSON.parse(
    readFileSync("tools/simjs/golden/combat_dicts.json", "utf8"),
);
const CHAMP = dicts["Franks|champion"];
const JAG = dicts["Aztecs|elite_jaguar_warrior_aztecs"];

function makeSim(seed, arena, n = 12) {
    return createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: n },
            {
                combatDict: JAG,
                slug: "elite_jaguar_warrior_aztecs",
                civ: "Aztecs",
                count: n,
            },
        ],
        seed,
        arena,
    });
}

// ---- 1. the OFF path is untouched -------------------------------------------

test("no arena field => sim.arena is null (the plain rectangle)", () => {
    assert.equal(makeSim(3).arena, null);
    assert.equal(makeSim(3, null).arena, null);
    assert.equal(makeSim(3, "plain").arena, null);
    assert.equal(makeSim(3, undefined).arena, null);
});

test("plain default: hash stream identical with and without an explicit null", () => {
    const a = makeSim(7);
    const b = makeSim(7, null);
    assert.equal(a.stateHash(), b.stateHash());
    for (let i = 0; i < 900; i++) {
        a.step();
        b.step();
        assert.equal(a.stateHash(), b.stateHash(), `diverged at tick ${i + 1}`);
    }
});

test("plain spawns still use the full-height line, untouched by the arena code", () => {
    const sim = makeSim(4);
    // The historical layout: one file per team down the map, ~30 px in from the
    // left/right edge, spread over nearly the whole 600 px height.
    const xs = sim.team1.map((u) => u.x);
    const ys = sim.team1.map((u) => u.y);
    assert.ok(Math.max(...xs) - Math.min(...xs) <= 10); // jitter only
    assert.ok(Math.max(...ys) - Math.min(...ys) > 400);
    assert.ok(Math.min(...xs) < 60);
    assert.ok(Math.min(...sim.team2.map((u) => u.x)) > 800);
});

test("an arena consumes exactly the same rng draws as the plain path", () => {
    // One draw per unit, in index order, either way — so a scenario that turns
    // the arena on cannot shift the stream for anything downstream of spawning.
    const plain = makeSim(9);
    const golden = makeSim(9, "golden");
    assert.equal(plain.rng.getState(), golden.rng.getState());
});

// ---- 2. the arena's geometry -------------------------------------------------

test("the play area is a diamond with corners at left/top/right/bottom", () => {
    const a = new Arena({});
    const [left, top, right, bottom] = a.boundaryPath();
    assert.ok(Math.abs(left.y - 300) < 1e-9);
    assert.ok(Math.abs(right.y - 300) < 1e-9);
    assert.ok(Math.abs(top.x - 450) < 1e-9);
    assert.ok(Math.abs(bottom.x - 450) < 1e-9);
    assert.ok(left.x < top.x && top.x < right.x);
    assert.ok(top.y < left.y && left.y < bottom.y);
    // Inside the canvas, and the four corners really are on the boundary.
    for (const p of [left, top, right, bottom]) {
        assert.ok(p.x >= 0 && p.x <= 900 && p.y >= 0 && p.y <= 600);
        assert.ok(a.isInside(p.x, p.y, -1e-6));
    }
    // Off-diamond points (the canvas corners) are out.
    assert.ok(!a.isInside(5, 5));
    assert.ok(!a.isInside(895, 595));
});

test("the tile<->world mapping is an isometry (distances survive the rotation)", () => {
    const a = new Arena({});
    const p = a.toWorld(...Object.values(a.tileToLocal(3, 4)));
    const q = a.toWorld(...Object.values(a.tileToLocal(11, 9)));
    const tileDist = Math.hypot(11 - 3, 9 - 4) * TILE_SIZE;
    assert.ok(Math.abs(Math.hypot(q.x - p.x, q.y - p.y) - tileDist) < 1e-9);
    // ...and the inverse round-trips.
    const back = a.toLocal(p.x, p.y);
    const fwd = a.tileToLocal(3, 4);
    assert.ok(Math.abs(back.u - fwd.u) < 1e-9 && Math.abs(back.v - fwd.v) < 1e-9);
});

test("the obstruction sits on the Panda Rock's tile and matches the derived cluster", () => {
    const a = new Arena({});
    // Tile (9, 7) is both the scenario's Panda Rock and the centroid of the 12
    // interior tiles no unit entered in any of the 155 tapes.
    const c = a.tileToLocal(9, 7);
    const w = a.toWorld(c.u, c.v);
    assert.ok(Math.abs(a.obstruction.x - w.x) < 1e-9);
    assert.ok(Math.abs(a.obstruction.y - w.y) < 1e-9);
    assert.ok(a.blocks(w.x, w.y));
    // Every blocked tile centre is inside the physics disc; a tile one step
    // outside the cluster is not.
    for (const s of a.obstructionShapes()) assert.ok(a.blocks(s.x, s.y));
    const outside = a.tileToLocal(6.5, 7.5); // (6,7): open in doc AND in the mask
    const ow = a.toWorld(outside.u, outside.v);
    assert.ok(!a.blocks(ow.x, ow.y));
});

test("spawn anchors are ADJACENT corners at the tapes' measured separation", () => {
    const a = new Arena({});
    const [p, q] = a.anchors;
    // Left-corner wedge and bottom-corner wedge: one is left of centre at the
    // centre height, the other below centre at the centre width.
    assert.ok(p.x < 450 && Math.abs(p.y - 300) < 1e-9);
    assert.ok(q.y > 300 && Math.abs(q.x - 450) < 1e-9);
    // 90 degrees apart about the map centre, not antipodal.
    const ang = (r) => Math.atan2(r.y - 300, r.x - 450);
    let d = Math.abs(ang(p) - ang(q));
    if (d > Math.PI) d = 2 * Math.PI - d;
    assert.ok(Math.abs(d - Math.PI / 2) < 1e-9, `anchors ${d} rad apart`);
    // Tape centroid separation over 155 recordings: min 7.63, median 8.11,
    // mean 8.45, max 9.84 tiles.
    const sep = Math.hypot(p.x - q.x, p.y - q.y) / TILE_SIZE;
    assert.ok(sep > 7.6 && sep < 9.9, `separation ${sep} tiles`);
});

test("golden spawns land inside the diamond, outside the trees, as two blobs", () => {
    const sim = makeSim(2, "golden", 21);
    const arena = sim.arena;
    assert.ok(arena);
    for (const u of [...sim.team1, ...sim.team2]) {
        assert.ok(arena.isInside(u.x, u.y, u.radius - 1e-6), "spawned outside");
        assert.ok(!arena.blocks(u.x, u.y, u.radius - 1e-6), "spawned in trees");
    }
    // A blob, not the plain path's 20-tile-tall file.
    for (const team of [sim.team1, sim.team2]) {
        const xs = team.map((u) => u.x);
        const ys = team.map((u) => u.y);
        const w = (Math.max(...xs) - Math.min(...xs)) / TILE_SIZE;
        const h = (Math.max(...ys) - Math.min(...ys)) / TILE_SIZE;
        assert.ok(w > 1 && w < 9, `blob width ${w} tiles`);
        assert.ok(h > 1 && h < 9, `blob depth ${h} tiles`);
    }
});

test("the longer-ranged side takes the left corner", () => {
    const ARB = dicts["Britons|arbalester"] || dicts["Franks|champion"];
    if (ARB === CHAMP) return; // fixture without a ranged unit: nothing to assert
    const leftIsTeam2 = createSimulation({
        teams: [
            { combatDict: CHAMP, slug: "champion", civ: "Franks", count: 6 },
            { combatDict: ARB, slug: "arbalester", civ: "Britons", count: 6 },
        ],
        seed: 1,
        arena: "golden",
    });
    const cx = (t) => t.reduce((s, u) => s + u.x, 0) / t.length;
    assert.ok(cx(leftIsTeam2.team2) < cx(leftIsTeam2.team1));
});

// ---- 3. the obstruction is impassable, and units go around it ----------------

test("constrain() ejects a unit shoved into the trees and keeps it in the map", () => {
    const a = new Arena({});
    const u = { x: a.obstruction.x + 3, y: a.obstruction.y - 2, radius: 14 };
    a.constrain(u);
    assert.ok(!a.blocks(u.x, u.y, u.radius - 1e-6));
    assert.ok(
        Math.abs(
            Math.hypot(u.x - a.obstruction.x, u.y - a.obstruction.y) -
                (a.obstruction.r + u.radius),
        ) < 1e-9,
    );

    const far = { x: 5, y: 5, radius: 14 };
    a.constrain(far);
    assert.ok(a.isInside(far.x, far.y, far.radius - 1e-6));
});

test("a straight line through the cluster is blocked; steering turns it aside", () => {
    const a = new Arena({});
    const o = a.obstruction;
    // Walk due east straight at the cluster centre, ignoring the arena: the
    // path is blocked, which is the property the steering exists to solve.
    const start = { x: o.x - 200, y: o.y };
    let blocked = false;
    for (let t = 0; t <= 1; t += 1 / 400) {
        const x = start.x + t * 400;
        if (a.blocks(x, start.y, 14)) blocked = true;
    }
    assert.ok(blocked, "the cluster does not actually block a straight line");

    // Now with steering: same start, same goal, avoidance applied each step.
    const u = { x: start.x, y: start.y, radius: 14 };
    let hit = false;
    for (let i = 0; i < 900; i++) {
        let dx = o.x + 200 - u.x;
        let dy = o.y - u.y;
        const L = Math.hypot(dx, dy) || 1;
        dx /= L;
        dy /= L;
        const s = a.obstacleSteer(u.x, u.y, u.radius, dx, dy);
        if (s) {
            dx += s.x;
            dy += s.y;
            const l2 = Math.hypot(dx, dy) || 1;
            dx /= l2;
            dy /= l2;
        }
        u.x += dx * 2;
        u.y += dy * 2;
        if (a.blocks(u.x, u.y, u.radius - 1e-6)) hit = true;
        if (Math.hypot(u.x - (o.x + 200), u.y - o.y) < 6) break;
    }
    assert.ok(!hit, "steered path entered the trees");
    // It got past — i.e. it went AROUND rather than stalling on the near side.
    assert.ok(u.x > o.x + o.r, `stalled at x=${u.x}`);
    // ...and it really did detour: a straight run would never leave y = o.y.
    assert.ok(Math.abs(u.y - o.y) > 1, "no lateral detour at all");
});

test("a whole golden fight never puts a living unit in the trees or off the map", () => {
    const sim = makeSim(6, "golden", 16);
    const a = sim.arena;
    let ticks = 0;
    while (sim.winner === null && ticks < 60 * 120) {
        sim.step(1 / 60);
        ticks++;
        if (ticks % 20) continue;
        for (const u of [...sim.team1, ...sim.team2]) {
            if (u.state === "dead") continue;
            assert.ok(a.isInside(u.x, u.y, u.radius - 0.5), `outside at t${ticks}`);
            assert.ok(!a.blocks(u.x, u.y, u.radius - 0.5), `in trees at t${ticks}`);
        }
    }
    assert.ok(ticks > 0);
});

test("the render helpers the canvas needs all return usable geometry", () => {
    // sim_renderer.js's drawArena calls exactly these four; a rename here would
    // otherwise only show up as a blank battlefield in the browser.
    const a = new Arena({});
    assert.equal(a.boundaryPath().length, 4);

    const shapes = a.obstructionShapes();
    assert.equal(shapes.length, 12); // the 12 tiles no unit ever entered
    for (const s of shapes) {
        assert.equal(s.quad.length, 4);
        assert.ok(Number.isFinite(s.x) && Number.isFinite(s.y));
        // Each quad is one tile: side TILE_SIZE, centred on the tile centre.
        const side = Math.hypot(
            s.quad[1].x - s.quad[0].x,
            s.quad[1].y - s.quad[0].y,
        );
        assert.ok(Math.abs(side - TILE_SIZE) < 1e-9);
    }

    const rock = a.rockShape();
    assert.ok(rock.r > 0);
    assert.ok(Math.abs(rock.x - a.obstruction.x) < 1e-9);
    assert.ok(Math.abs(rock.y - a.obstruction.y) < 1e-9);

    // One line per tile in each local axis, both endpoints on the boundary.
    const lines = a.gridLines(1);
    assert.ok(lines.length >= 2 * (2 * a.halfTiles));
    for (const [p, q] of lines) {
        assert.ok(a.isInside(p.x, p.y, -1e-6) && a.isInside(q.x, q.y, -1e-6));
    }
});

test("makeArena only builds on an explicit opt-in", () => {
    assert.equal(makeArena(null), null);
    assert.equal(makeArena(undefined), null);
    assert.equal(makeArena("plain"), null);
    assert.equal(makeArena(false), null);
    assert.ok(makeArena("golden") instanceof Arena);
    const a = new Arena({});
    assert.equal(makeArena(a), a);
});
