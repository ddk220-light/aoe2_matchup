// Role: engine — battlefield geometry, as an OPT-IN overlay on the plain
// rectangle the engine has always fought on. Two specs live here:
//
//   * `Arena` ("golden")  — the recording scenario rendered the way the game
//     presents it: a rotated diamond play area with the central tree cluster
//     and two corner spawn wedges. A LAB VISUAL.
//   * `TapeBox` ("tapebox") — the recording scenario's PHYSICS, with nothing
//     added: an axis-aligned walled box at the tapes' own measured position
//     bounds, no obstruction, and spawns supplied verbatim from the tape's
//     first frame. THE CALIBRATION SCORING GEOMETRY (see its own header).
//
// NOTHING IN HERE RUNS UNLESS A CALLER ASKS FOR IT. `createSimulation` leaves
// `sim.arena === null` by default, and every hook in sim.js / battle_unit.js /
// scenario.js is guarded on that null. With no arena the engine is bit-identical
// to before this module existed — that is the contract the 155-fight calibration
// corpus and tools/simjs/parity_check.mjs both depend on.
//
// ---------------------------------------------------------------------------
// GROUND TRUTH
// ---------------------------------------------------------------------------
// Two independent sources agree on the recording map, and this module is built
// from their intersection:
//
//   (a) docs/simulation-engine-migration.md §5.1 — the scenario file itself,
//       parsed with AoE2ScenarioParser: 16x16 tiles, a perimeter forest ring, a
//       central tree cluster around tiles (7-10, 5-8), and a Panda Rock at
//       (9.0, 7.0). 101 of 256 tiles solid.
//
//   (b) A walkable mask derived here from the tape corpus: every unit position
//       sample in all 155 recordings under D:/AI/aoe2_golden/tapes, quantised to
//       tiles and unioned. A tile no unit ever stood on in 155 fights is
//       treated as solid. At a >= 3-tape threshold that mask is:
//
//              0123456789012345
//           0  XXXXXXXXXXXXXXXX
//           1  XXXXXX........XX
//           2  XXXXX..........X
//           3  XXXX..........XX
//           4  XXX............X
//           5  XX......XX.....X
//           6  X......XXXX....X
//           7  X......XXXX....X
//           8  X.......XX.....X
//           9  X..............X
//          10  X.............XX
//          11  X............XXX
//          12  X...........XXXX
//          13  X..........XXXXX
//          14  XX........XXXXXX
//          15  XXXXXXXXXXXXXXXX
//
//       Rows 1-2 and 8-14 reproduce the doc's map tile for tile. The only
//       disagreement is inside the central cluster: the doc leaves a couple of
//       interior pockets at (8-9, 6) and (8, 7) nominally open, and no unit ever
//       walked into them — so the observed obstruction is SOLID, a 12-tile
//       diamond, and that is what this module models.
//
// The 12 blocked interior tiles are exactly { |cx - 9| + |cy - 7| <= 2 } in tile-
// CENTRE coordinates. Their centroid is (9.0, 7.0) — the Panda Rock's own
// position, to the tile. That is the whole obstruction.
//
// ---------------------------------------------------------------------------
// WHY A DIAMOND
// ---------------------------------------------------------------------------
// The doc (§5.3) is right that the diamond "does not matter" for physics: AoE2's
// tile grid is square and distances are Euclidean in tile space. So the arena is
// defined in TILE space and mapped into engine pixels by a pure 45 deg rotation
// with uniform scale. A rotation is an isometry: every distance, every radius and
// every speed is preserved exactly, so nothing about the combat model changes —
// the battlefield is simply presented the way the game presents it, with the
// tile square's corners pointing left / top / right / bottom.
//
//   world = (CX + c*(u + v), CY + c*(v - u)),  c = 1/sqrt(2)
//   local = (c*(X - Y), c*(X + Y))              X = x - CX, Y = y - CY
//
// `u`/`v` are tile-space offsets from the map centre in PIXELS (u = (tx - 8) *
// TILE_SIZE). The play area is |u| <= HALF and |v| <= HALF, which draws as a
// diamond inscribed in the canvas.
//
// ---------------------------------------------------------------------------
// SPAWNS
// ---------------------------------------------------------------------------
// Measured over the same 155 tapes (first frame of each .units.jsonl.gz):
//
//     owner 2 : 155 tapes, mean centroid (7.41, 3.93), mean bbox 6.1 x 4.0 tiles
//     owner 3 : 155 tapes, mean centroid (5.13, 12.04), mean bbox 6.2 x 3.0 tiles
//     centroid separation: min 7.63, median 8.11, mean 8.45, max 9.84 tiles
//
// So: two blobs, ~6 tiles wide and 3-4 ranks deep, ~8.1 tiles apart, separated
// almost entirely along tile-y — i.e. along `v`, with the blobs spread along `u`.
// Under the rotation above, two points that share a `u` and differ in `v` land on
// two ADJACENT corners of the diamond (the left corner and the bottom corner are
// the two ends of the tile square's u = -HALF edge). That adjacency is deliberate
// and load-bearing: with 90-degrees-apart spawns a fleeing side leads its chaser
// CLOCKWISE around the central cluster (the sense the recording AI's square
// patrol runs, and the sense BattleUnit.kiteSteering's tangential term already
// uses). With antipodal spawns the chasers split and flow around both sides of
// the cluster instead, which is not the behaviour this feature exists to show.
//
// The two anchors therefore sit at u = -0.60 * HALF, v = -+0.60 * HALF: rendered,
// one in the LEFT corner wedge and one in the BOTTOM corner wedge, 8.16 tiles
// apart (the tape median is 8.11). The longer-ranged side takes the left corner
// so that its retreat bearing — away from a threat to its lower-right — runs up
// the top-left edge and around the cluster clockwise.
//
// The obstruction centre sits 5.08 tiles off the straight line between the two
// anchors, with a 1.95-tile radius: the opening charge is NOT blocked (so a
// melee-vs-melee fight plays out much as it does on the plain rectangle), but a
// kiting lap runs straight into it.

import { TILE_SIZE, CANVAS_WIDTH, CANVAS_HEIGHT } from "./constants.js";

const SQRT1_2 = Math.SQRT1_2;

// ---- the spec ---------------------------------------------------------------

// Half-side of the playable tile square, in tiles. The recording map is 16x16
// with a solid perimeter ring, leaving a ~14x14 interior; 13.6 is that interior
// shrunk just enough that the rotated square's 288.5 px half-diagonal clears the
// 300 px half-height of the 900x600 canvas.
export const ARENA_HALF_TILES = 6.8;

// Centre of the recording map, in tiles. Everything below is expressed as an
// offset from here so the doc's tile coordinates can be used literally.
export const MAP_CENTRE_TILE = { x: 8, y: 8 };

// The 12 interior tiles no unit ever entered, as tile CENTRES. Equivalent to
// { |cx - 9| + |cy - 7| <= 2 }. The Panda Rock sits at the centroid, (9.0, 7.0).
export const OBSTRUCTION_TILES = [
    [8.5, 5.5], [9.5, 5.5],
    [7.5, 6.5], [8.5, 6.5], [9.5, 6.5], [10.5, 6.5],
    [7.5, 7.5], [8.5, 7.5], [9.5, 7.5], [10.5, 7.5],
    [8.5, 8.5], [9.5, 8.5],
];
export const OBSTRUCTION_CENTRE_TILE = { x: 9.0, y: 7.0 };
// Physics footprint: one disc, area-matched to the 12-tile diamond
// (sqrt(12 / pi) = 1.954). Using a disc rather than the literal tile set keeps
// steering smooth — units slide around a curve instead of catching on corners —
// and the drawn canopies cover it almost exactly.
export const OBSTRUCTION_RADIUS_TILES = 1.95;

// How far out from the obstruction's surface the soft avoidance field reaches.
export const OBSTRUCTION_FIELD_TILES = 2.0;
// Weight of the straight-away push at the surface, in the same unnormalised
// units as calculateAvoidance's separation force (0.5 per neighbour in the soft
// band, 3-8 when overlapping) — so this is "comparable to one crowding
// neighbour", ramping to ~3 at contact.
export const OBSTRUCTION_PUSH_WEIGHT = 3.0;
// Weight of the sideways slide, applied only to a unit actually heading INTO the
// cluster. This is what turns "stop at the trees" into "walk around them".
export const OBSTRUCTION_SLIDE_WEIGHT = 4.0;

// Fraction of the way from the map centre to a corner at which an army's blob is
// centred. 0.60 puts the two anchors 8.16 tiles apart (tape median 8.11).
export const SPAWN_ANCHOR_FRACTION = 0.6;
// Blob aspect: width (across the facing) divided by depth (ranks). The tapes
// average 6.1 x 4.0 and 6.2 x 3.0; 1.4 reproduces 6x4 for 21 units and 4x3 for 9.
export const SPAWN_BLOB_ASPECT = 1.4;

// ---- the arena --------------------------------------------------------------

export class Arena {
    // The golden arena places its armies with spawnLayout() off two corner
    // anchors. TapeBox does not (its spawns are tape data), and scenario.js
    // branches on this rather than on `instanceof`, so a future third spec only
    // has to answer the question, not be recognised.
    get usesSpawnAnchors() {
        return true;
    }

    constructor({
        mapW = CANVAS_WIDTH,
        mapH = CANVAS_HEIGHT,
        halfTiles = ARENA_HALF_TILES,
    } = {}) {
        this.cx = mapW / 2;
        this.cy = mapH / 2;
        // Half-side of the tile square, in PIXELS.
        this.half = halfTiles * TILE_SIZE;
        this.halfTiles = halfTiles;

        const oc = this.tileToLocal(
            OBSTRUCTION_CENTRE_TILE.x,
            OBSTRUCTION_CENTRE_TILE.y,
        );
        const ow = this.toWorld(oc.u, oc.v);
        this.obstruction = {
            x: ow.x,
            y: ow.y,
            r: OBSTRUCTION_RADIUS_TILES * TILE_SIZE,
            field: OBSTRUCTION_FIELD_TILES * TILE_SIZE,
        };

        // The two spawn anchors, on ADJACENT corners of the diamond (see the
        // header): equal `u`, opposite `v`. Index 0 renders in the LEFT corner
        // wedge, index 1 in the BOTTOM corner wedge.
        const a = SPAWN_ANCHOR_FRACTION * this.half;
        this.anchorsLocal = [
            { u: -a, v: -a },
            { u: -a, v: +a },
        ];
        this.anchors = this.anchorsLocal.map((p) => {
            const w = this.toWorld(p.u, p.v);
            return { x: w.x, y: w.y, u: p.u, v: p.v };
        });
    }

    // ---- coordinate transforms ----------------------------------------------

    // tile coordinates -> local (u, v) pixel offsets from the map centre.
    tileToLocal(tx, ty) {
        return {
            u: (tx - MAP_CENTRE_TILE.x) * TILE_SIZE,
            v: (ty - MAP_CENTRE_TILE.y) * TILE_SIZE,
        };
    }

    // local -> engine world pixels (the 45 deg rotation; an isometry).
    toWorld(u, v) {
        return {
            x: this.cx + SQRT1_2 * (u + v),
            y: this.cy + SQRT1_2 * (v - u),
        };
    }

    // engine world pixels -> local. Exact inverse of toWorld.
    toLocal(x, y) {
        const X = x - this.cx;
        const Y = y - this.cy;
        return { u: SQRT1_2 * (X - Y), v: SQRT1_2 * (X + Y) };
    }

    // ---- boundary ------------------------------------------------------------

    // The four diamond vertices in world pixels, in draw order
    // (left, top, right, bottom).
    boundaryPath() {
        const h = this.half;
        return [
            this.toWorld(-h, -h),
            this.toWorld(+h, -h),
            this.toWorld(+h, +h),
            this.toWorld(-h, +h),
        ];
    }

    // Is (x, y) inside the play area, keeping `pad` pixels of clearance?
    isInside(x, y, pad = 0) {
        const { u, v } = this.toLocal(x, y);
        const lim = this.half - pad;
        return Math.abs(u) <= lim && Math.abs(v) <= lim;
    }

    // Nearest point inside the play area (clamped in LOCAL axes, which is what
    // makes a corner behave like a corner rather than a rounded cap).
    clampToArena(x, y, pad = 0) {
        const { u, v } = this.toLocal(x, y);
        const lim = Math.max(0, this.half - pad);
        const cu = Math.min(lim, Math.max(-lim, u));
        const cv = Math.min(lim, Math.max(-lim, v));
        if (cu === u && cv === v) return { x, y };
        return this.toWorld(cu, cv);
    }

    // ---- obstruction ---------------------------------------------------------

    // Does a body of radius `pad` centred at (x, y) overlap the cluster?
    blocks(x, y, pad = 0) {
        const o = this.obstruction;
        const dx = x - o.x;
        const dy = y - o.y;
        const rr = o.r + pad;
        return dx * dx + dy * dy < rr * rr;
    }

    // Steering contribution for a unit at (x, y) with body radius `rad` that
    // WANTS to travel along the unit vector (dx, dy). Two terms:
    //
    //   * a radial push straight out of the cluster, ramping from 0 at the edge
    //     of the field to OBSTRUCTION_PUSH_WEIGHT at the surface (and beyond, if
    //     something shoved the unit inside);
    //   * a tangential slide, applied ONLY in proportion to how hard the unit is
    //     driving into the cluster (dot(desired, inward)). A unit walking past
    //     the trees is untouched; a unit walking at them is turned along the
    //     surface, on whichever side its own heading already favours — so a
    //     chaser rounds the cluster the short way instead of stalling on it.
    //
    // Pure: reads nothing off the sim, draws no randomness, mutates nothing.
    obstacleSteer(x, y, rad, dx, dy) {
        const o = this.obstruction;
        let rx = x - o.x;
        let ry = y - o.y;
        let d = Math.sqrt(rx * rx + ry * ry);
        const surface = o.r + rad;
        if (d >= surface + o.field) return null;
        if (d < 1e-6) {
            // Dead centre: pick a deterministic bearing rather than dividing by
            // zero. Sideways from the desired heading keeps it moving on through.
            rx = -dy;
            ry = dx;
            d = Math.sqrt(rx * rx + ry * ry) || 1;
        }
        const ux = rx / d;
        const uy = ry / d;
        // 0 at the outer edge of the field, 1 at the surface, >1 if embedded.
        const w = Math.min(2, (surface + o.field - d) / o.field);

        let sx = OBSTRUCTION_PUSH_WEIGHT * w * ux;
        let sy = OBSTRUCTION_PUSH_WEIGHT * w * uy;

        // How much of the desired heading points INTO the cluster.
        const into = -(dx * ux + dy * uy);
        if (into > 0) {
            // Tangent to the surface; take the sense the unit is already leaning.
            let tx = -uy;
            let ty = ux;
            if (dx * tx + dy * ty < 0) {
                tx = -tx;
                ty = -ty;
            }
            const k = OBSTRUCTION_SLIDE_WEIGHT * w * into;
            sx += k * tx;
            sy += k * ty;
        }
        return { x: sx, y: sy };
    }

    // ---- hard constraint -----------------------------------------------------

    // The arena's replacement for the engine's rectangle clamp: eject the unit
    // from the cluster, then clamp it inside the diamond. Called once per unit
    // per tick from Simulation.resolveCollisions, and from the two movement
    // paths in BattleUnit.
    constrain(unit) {
        const o = this.obstruction;
        const rad = unit.radius || 0;
        const surface = o.r + rad;
        let dx = unit.x - o.x;
        let dy = unit.y - o.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < surface) {
            if (d < 1e-6) {
                // Exactly on the rock: eject along +v (deterministic).
                const p = this.toWorld(0, surface);
                unit.x = p.x;
                unit.y = p.y;
            } else {
                unit.x = o.x + (dx / d) * surface;
                unit.y = o.y + (dy / d) * surface;
            }
        }
        const c = this.clampToArena(unit.x, unit.y, rad);
        unit.x = c.x;
        unit.y = c.y;
    }

    // ---- spawns --------------------------------------------------------------

    // Lay `count` units out as one tape-shaped blob on anchor `side` (0 = left
    // corner, 1 = bottom corner). Returns world positions in spawn order, front
    // rank first, plus the unit vector each one should face (toward the enemy
    // anchor) so the first tick's smoothed velocity already leans the right way.
    //
    // Fully deterministic: no randomness, no sim state.
    spawnLayout(side, count, spacing) {
        const me = this.anchorsLocal[side];
        const foe = this.anchorsLocal[side === 0 ? 1 : 0];

        // In LOCAL space the two anchors share a `u`, so "toward the enemy" is
        // +-v and the blob spreads along u — exactly the tape's layout (blobs
        // wide in tile-x, separated in tile-y).
        let fu = foe.u - me.u;
        let fv = foe.v - me.v;
        const flen = Math.hypot(fu, fv) || 1;
        fu /= flen;
        fv /= flen;
        // Left-hand normal of the facing, in local space.
        const wu = -fv;
        const wv = fu;

        const cols = Math.max(1, Math.ceil(Math.sqrt(count * SPAWN_BLOB_ASPECT)));
        const rows = Math.ceil(count / cols);

        // Blob half-extents, then a rigid inward shift if the outer file would
        // poke through the map edge. Shifting (rather than squashing) keeps the
        // measured centroid separation exact — it is purely a `v` quantity and
        // the shift is purely in `u`.
        const halfW = ((cols - 1) * spacing) / 2;
        let bu = me.u;
        const margin = 12;
        const outer = Math.abs(me.u) + halfW;
        if (outer > this.half - margin) {
            bu = me.u + Math.sign(me.u || -1) * -(outer - (this.half - margin));
        }

        const out = [];
        const depth0 = ((rows - 1) * spacing) / 2;
        for (let i = 0; i < count; i++) {
            const r = Math.floor(i / cols); // 0 = front rank (nearest the foe)
            const cIdx = i % cols;
            // Centre the last, possibly short, rank.
            const inRank = Math.min(cols, count - r * cols);
            const off = (cIdx - (inRank - 1) / 2) * spacing;
            const along = depth0 - r * spacing;
            const u = bu + wu * off + fu * along;
            const v = me.v + wv * off + fv * along;
            const w = this.toWorld(u, v);
            const f = this.toWorld(fu, fv);
            out.push({
                x: w.x,
                y: w.y,
                // Facing as a world unit vector (the rotation is an isometry, so
                // rotating the local unit vector keeps it a unit vector).
                fx: f.x - this.cx,
                fy: f.y - this.cy,
                // The blob's width axis in world space — what a spawn jitter
                // should ride along so it widens the rank rather than the file.
                wx: this.toWorld(wu, wv).x - this.cx,
                wy: this.toWorld(wu, wv).y - this.cy,
            });
        }
        return out;
    }

    // ---- render helpers ------------------------------------------------------

    // The blocked tiles as world-space quads, for the renderer's tree canopies.
    // Each entry is { x, y, quad: [[x,y] x4] } — `quad` is the tile itself,
    // rotated, so a drawn canopy can sit inside its own footprint.
    obstructionShapes() {
        const h = TILE_SIZE / 2;
        return OBSTRUCTION_TILES.map(([tx, ty]) => {
            const c = this.tileToLocal(tx, ty);
            const centre = this.toWorld(c.u, c.v);
            const quad = [
                [-h, -h],
                [+h, -h],
                [+h, +h],
                [-h, +h],
            ].map(([du, dv]) => this.toWorld(c.u + du, c.v + dv));
            return { x: centre.x, y: centre.y, quad };
        });
    }

    // World-space centre + radius of the Panda Rock, for the renderer.
    rockShape() {
        const c = this.tileToLocal(
            OBSTRUCTION_CENTRE_TILE.x,
            OBSTRUCTION_CENTRE_TILE.y,
        );
        const w = this.toWorld(c.u, c.v);
        return { x: w.x, y: w.y, r: TILE_SIZE * 0.55 };
    }

    // Local-axis grid lines (the isometric tile grid), as world segments.
    gridLines(stepTiles = 1) {
        const h = this.half;
        const step = stepTiles * TILE_SIZE;
        const lines = [];
        for (let u = -h; u <= h + 1e-6; u += step) {
            lines.push([this.toWorld(u, -h), this.toWorld(u, h)]);
        }
        for (let v = -h; v <= h + 1e-6; v += step) {
            lines.push([this.toWorld(-h, v), this.toWorld(h, v)]);
        }
        return lines;
    }
}

// =============================================================================
// TapeBox — the calibration corpus's ACTUAL initial conditions
// =============================================================================
//
// WHY THIS EXISTS
// ---------------
// Through E11 the calibration corpus was scored on a scenario that shares
// nothing with the recordings it is compared against:
//
//                        engine (pre-E12)          tape corpus
//   play area            30 x 20 tiles, open       13.6 x 13.6 tiles, walled
//   army shape           single-file column        2-D block, ~6 wide x 3-4 deep
//   start separation     28 tiles                  8.1 tiles (centroids)
//   nearest enemy pair   ~20 tiles                 4.0 tiles
//
// Every combat constant fitted on that scenario was fitted against the wrong
// initial condition. E11 made the cost visible: at true collision radii the
// chasers converge into one tight ball and envelop a ranged side that the
// tapes show holding a ~2.1-tile standoff, and the corpus fell 144 -> 135/155.
//
// GROUND TRUTH (measured, not assumed)
// ------------------------------------
// Every unit-position sample in all 155 recordings under D:/AI/aoe2_golden/tapes
// (tools/simjs/dump_calib_spawns.py reads the same stream):
//
//     x in [1.2, 14.8]      y in [1.2, 14.8]        (tiles, unit CENTRES)
//
// Both axes, over the whole corpus — a 13.6-tile square. That is the box below.
// First-frame geometry from the same scan: centroid separation min 7.63 /
// median 8.12 / max 9.84 tiles, nearest cross-army pair 4.00-6.08 tiles.
//
// WHAT IS DELIBERATELY *NOT* MODELLED
// -----------------------------------
// The real map also carries the central tree cluster the golden `Arena` above
// draws. It is left out here, knowingly:
//
//   * it sits ~5 tiles off the spawn-to-spawn line, so no melee approach ever
//     touches it — modelling it would change nothing this round measures;
//   * making a ranged side kite AROUND it needs pathfinding this engine does
//     not have, so an obstruction would produce grinding, not orbiting.
//
// So `TapeBox` is walls and spawns only. The diamond + cluster stay a lab
// visual, and this omission is a documented infidelity, not an oversight.
//
// COORDINATES
// -----------
// Axis-aligned and unrotated: world = (tile - 8) * TILE_SIZE + canvas centre,
// i.e. the recording's 16x16 tile map centred on whatever canvas the sim was
// built with. At the engine's default 900x600 the 16-tile map is 480 px and
// the walled box is 408 x 408 px — both fit, so no canvas constant moves.
//
// The bounds above are measured in unit-CENTRE space, so `constrain` clamps
// CENTRES to them with NO radius padding. Padding by the body radius would
// shrink the reachable area below what the tapes actually show, which is the
// exact class of error this module exists to remove.

// The tapes' measured position bounds, in tiles. Unit centres, both axes.
export const TAPEBOX_MIN_TILE = 1.2;
export const TAPEBOX_MAX_TILE = 14.8;

export class TapeBox {
    // Spawns come from the tape (scenario.js's `spec.positions`), never from a
    // corner anchor — see Arena.usesSpawnAnchors.
    get usesSpawnAnchors() {
        return false;
    }

    constructor({
        mapW = CANVAS_WIDTH,
        mapH = CANVAS_HEIGHT,
        minTile = TAPEBOX_MIN_TILE,
        maxTile = TAPEBOX_MAX_TILE,
    } = {}) {
        this.cx = mapW / 2;
        this.cy = mapH / 2;
        this.minTile = minTile;
        this.maxTile = maxTile;
        const lo = this.tileToWorld(minTile, minTile);
        const hi = this.tileToWorld(maxTile, maxTile);
        this.x0 = lo.x;
        this.y0 = lo.y;
        this.x1 = hi.x;
        this.y1 = hi.y;
    }

    // ---- coordinate transform ------------------------------------------------

    // Tile coordinates -> engine world pixels. The recording map is 16x16, so
    // tile 8 is its centre and lands on the canvas centre.
    tileToWorld(tx, ty) {
        return {
            x: this.cx + (tx - MAP_CENTRE_TILE.x) * TILE_SIZE,
            y: this.cy + (ty - MAP_CENTRE_TILE.y) * TILE_SIZE,
        };
    }

    worldToTile(x, y) {
        return {
            tx: (x - this.cx) / TILE_SIZE + MAP_CENTRE_TILE.x,
            ty: (y - this.cy) / TILE_SIZE + MAP_CENTRE_TILE.y,
        };
    }

    // ---- boundary ------------------------------------------------------------

    isInside(x, y, pad = 0) {
        return (
            x >= this.x0 + pad &&
            x <= this.x1 - pad &&
            y >= this.y0 + pad &&
            y <= this.y1 - pad
        );
    }

    clampToArena(x, y, pad = 0) {
        // `pad` is honoured for callers that want clearance, but `constrain`
        // below passes 0 on purpose (see the header): the wall bounds are
        // measured in unit-centre space already.
        const cx = Math.min(this.x1 - pad, Math.max(this.x0 + pad, x));
        const cy = Math.min(this.y1 - pad, Math.max(this.y0 + pad, y));
        return { x: cx, y: cy };
    }

    // ---- obstruction (there is none) -----------------------------------------

    blocks() {
        return false;
    }

    // Same signature as Arena.obstacleSteer; always null, so battle_unit.js's
    // `if (o)` guard skips the whole branch and steering is untouched.
    obstacleSteer() {
        return null;
    }

    // ---- hard constraint -----------------------------------------------------

    constrain(unit) {
        const c = this.clampToArena(unit.x, unit.y, 0);
        unit.x = c.x;
        unit.y = c.y;
    }

    // ---- render helpers ------------------------------------------------------
    // Same surface as Arena's so sim_renderer.drawArena can paint a TapeBox
    // without a special case. There is no cluster and no rock: the shapes list
    // is empty and the rock has zero radius (the renderer draws nothing).

    boundaryPath() {
        return [
            { x: this.x0, y: this.y0 },
            { x: this.x1, y: this.y0 },
            { x: this.x1, y: this.y1 },
            { x: this.x0, y: this.y1 },
        ];
    }

    obstructionShapes() {
        return [];
    }

    rockShape() {
        return { x: this.cx, y: this.cy, r: 0 };
    }

    gridLines(stepTiles = 1) {
        const step = stepTiles * TILE_SIZE;
        const lines = [];
        for (let x = this.x0; x <= this.x1 + 1e-6; x += step) {
            lines.push([{ x, y: this.y0 }, { x, y: this.y1 }]);
        }
        for (let y = this.y0; y <= this.y1 + 1e-6; y += step) {
            lines.push([{ x: this.x0, y }, { x: this.x1, y }]);
        }
        return lines;
    }
}

// Factory used by createSimulation. Anything other than the strings below —
// including undefined, null and "plain" — yields no arena at all, which is the
// engine's historical rectangle behaviour, bit for bit.
export function makeArena(kind, { mapW, mapH } = {}) {
    if (kind === "golden" || kind === true) return new Arena({ mapW, mapH });
    if (kind === "tapebox") return new TapeBox({ mapW, mapH });
    if (kind instanceof Arena || kind instanceof TapeBox) return kind;
    return null;
}
