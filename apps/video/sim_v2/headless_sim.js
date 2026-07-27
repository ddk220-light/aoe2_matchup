// Headless runner for the webapp's flanking battle sim (apps/website/static/js/simulate.js).
// Loads the REAL file (+ its sibling scripts, in browser load order) in a vm sandbox so
// every closure/const is intact, stubs DOM/canvas, seeds Math.random for determinism, and
// drives BattleSimulation.update() at the webapp's fixed 1/60 timestep. Combat / steering /
// flanking are byte-identical to production.
//
// Usage: node headless_sim.js [ramp=ship|window|off] [nSeeds] [maxSeconds]
const fs = require("fs");
const vm = require("vm");
const path = require("path");

// This harness lives at apps/video/sim_v2/; the webapp sim it drives is three
// levels up at apps/website/static/js. Derive the repo root from __dirname so
// the harness is portable (no hard-coded absolute path).
const REPO = path.resolve(__dirname, "..", "..", "..");
const JSDIR = path.join(REPO, "apps", "website", "static", "js");

const RAMP = process.env.RAMP || process.argv[2] || "ship";       // ship | window | off
const N_SEEDS = parseInt(process.env.SEEDS || process.argv[3] || "8", 10);
const MAX_S = parseFloat(process.env.MAXS || process.argv[4] || "180");
// Packing factor: scales the melee separation/collision spacing. 1.0 = ship.
// The game packs infantry far tighter than the sim's visual radius implies;
// PACK<1 shrinks the collision/avoidance minDist toward game-like density.
const PACK = parseFloat(process.env.PACK || "1.0");
// RTRUE: use the GAME's true collision radius (outline_size tiles * TILE_SIZE px)
// instead of the rendering-driven 10+outline*20 formula (which inflates infantry
// bodies 2.3x in diameter and causes the melee traffic jam). RSCALE fine-tunes.
const RTRUE = process.env.RTRUE === "1";
const RSCALE = parseFloat(process.env.RSCALE || "1.0");

// ---- seeded PRNG (mulberry32), injected as Math.random for determinism -------
let _rngState = 1;
function rng() {
    _rngState |= 0; _rngState = (_rngState + 0x6D2B79F5) | 0;
    let t = Math.imul(_rngState ^ (_rngState >>> 15), 1 | _rngState);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

// ---- permissive DOM element stub (absorbs any property/method access) --------
function elStub() {
    const f = function () { return f; };
    return new Proxy(f, {
        get(_t, k) {
            if (k === "value") return "";
            if (k === "classList") return { add() {}, remove() {}, toggle() {}, contains() { return false; } };
            if (k === "getContext") return () => elStub();
            if (k === "width") return 900;
            if (k === "height") return 600;
            if (k === Symbol.toPrimitive) return () => "";
            return elStub();
        },
        set() { return true; }, apply() { return elStub(); },
    });
}
const documentStub = {
    getElementById: () => elStub(), querySelector: () => elStub(), querySelectorAll: () => [],
    createElement: () => elStub(), createTextNode: () => elStub(),
    addEventListener: () => {}, body: elStub(), head: elStub(),
};
const defaultFetch = async () => ({ ok: true, json: async () => ({}) });
const sandbox = {
    document: documentStub,
    window: { addEventListener: () => {}, location: { search: "" }, devicePixelRatio: 1 },
    navigator: { userAgent: "node" },
    performance: { now: () => 0 },
    requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
    setTimeout: (fn) => { return 0; }, clearTimeout: () => {},
    Image: class { constructor() { this.complete = false; this.naturalWidth = 0; } },
    alert: () => {}, console, URLSearchParams, TextEncoder, TextDecoder,
    fetch: defaultFetch,
    __rng: rng,
    __setSeed: (n) => { _rngState = (n >>> 0) || 1; },
    UNIT_SEARCH: {},
};
sandbox.globalThis = sandbox;

// ---- assemble source: sibling scripts (browser order) + simulate.js ----------
function read(f) { return fs.readFileSync(path.join(JSDIR, f), "utf8").replace(/\r\n/g, "\n"); }
let simSrc = read("simulate.js");

// Ramp variant: replace the monotonic ship ramp with the game-faithful 5s decaying
// window (reload = max(min, base - ramp * hits_in_last_5s)). This is the exact edit
// that will later be applied to the real file.
const SHIP_RAMP = `        if (this.attackSpeedRamp > 0) {
            const baseReload =
                this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
            this.rampReduction = Math.min(
                this.rampReduction + this.attackSpeedRamp,
                Math.max(0, baseReload - this.attackSpeedMin),
            );
            this.reloadTime = Math.max(
                this.attackSpeedMin,
                baseReload - this.rampReduction,
            );
        }`;
const WINDOW_RAMP = `        if (this.attackSpeedRamp > 0) {
            const baseReload =
                this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
            const _t = (typeof simulation !== "undefined" && simulation) ? simulation.battleTime : 0;
            if (!this._rampHits) this._rampHits = [];
            const _cut = _t - 5.0;
            this._rampHits = this._rampHits.filter((h) => h > _cut);
            this._rampHits.push(_t);
            this.reloadTime = Math.max(
                this.attackSpeedMin,
                baseReload - this.attackSpeedRamp * this._rampHits.length,
            );
        }`;
const OFF_RAMP = `        if (this.attackSpeedRamp > 0) {
            this.reloadTime = this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;
        }`;
// The real file now ships the 5s-window ramp, so SHIP_RAMP may be absent.
const fileIsWindow = simSrc.includes("this.rampHits");
if (RAMP === "window") {
    if (simSrc.includes(SHIP_RAMP)) simSrc = simSrc.replace(SHIP_RAMP, WINDOW_RAMP);
    else if (!fileIsWindow) { console.error("!! neither ship nor window ramp found — aborting"); process.exit(2); }
    // else: file already has window ramp — no-op
} else if (RAMP === "off") {
    if (simSrc.includes(SHIP_RAMP)) simSrc = simSrc.replace(SHIP_RAMP, OFF_RAMP);
    else if (fileIsWindow) {
        // strip the window block back to a flat reload
        const winBlock = simSrc.match(/if \(this\.attackSpeedRamp > 0\) \{[\s\S]*?this\.rampHits\.length,\n\s*\);\n\s*\}/);
        if (winBlock) simSrc = simSrc.replace(winBlock[0], "if (this.attackSpeedRamp > 0) {\n            this.reloadTime = this.attackSpeed > 0 ? 1.0 / this.attackSpeed : 2.0;\n        }");
    }
}
if (PACK !== 1.0) {
    const c1 = "const minDist = a.radius + b.radius + 1;";
    const c2 = "const minDist = this.radius + other.radius + 2;";
    if (!simSrc.includes(c1) || !simSrc.includes(c2)) { console.error("!! spacing lines not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(c1, `const minDist = (a.radius + b.radius) * ${PACK} + 1;`)
                   .replace(c2, `const minDist = (this.radius + other.radius) * ${PACK} + 2;`);
}
if (RTRUE) {   // game-true collision radius: outline_size (tiles) * TILE_SIZE
    const r1 = `        this.radius = Math.round(
            10 + Math.min(outlineSize, 1.0) * 20,
        );`;
    if (!simSrc.includes(r1)) { console.error("!! radius formula not found"); process.exit(2); }
    simSrc = simSrc.replace(r1,
        `        this.radius = Math.max(4, outlineSize * TILE_SIZE * ${RSCALE});
        // bodyRadius = the unit's VISIBLE body (the shipped render radius). RTRUE
        // shrinks this.radius to the pathing/collision circle, but a scattered
        // projectile (a miss) hits the visible BODY, not the collision dot — so the
        // graze test must keep the full render size here (see GRAZE_K below).
        this.bodyRadius = Math.round(10 + Math.min(outlineSize, 1.0) * 20);`);
    // GRAZE_K: miss-graze packing compensation. A missed projectile (accuracy roll
    // fail) lands at a random point within MISS_SPREAD and grazes any unit whose
    // body it lands on (Arambai deals FULL damage on a graze, miss_damage_percent=1
    // — its whole identity is scattered shots devastating a packed blob). The ship
    // test compares against enemy.radius; under RTRUE that is the tiny collision
    // dot (~6px infantry), so scattered shots fall in the gaps and the blob-graze
    // dies (measured: 30% connect == base accuracy, i.e. ~0 grazes). Test against
    // bodyRadius (the visible body, ~14px) and scale by GRAZE_K for the V2 arena's
    // looser packing vs the game's melee blob (same rationale as TRAMPLE_K).
    const GRAZE_K = parseFloat(process.env.GRAZE_K || "1");
    const GZ_OLD = "enemy.radius * enemy.radius";
    if (!simSrc.includes(GZ_OLD)) { console.error("!! graze test expr not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(GZ_OLD,
        `(enemy.bodyRadius * ${GRAZE_K}) * (enemy.bodyRadius * ${GRAZE_K})`);
}
// Flanking-flow envelopment: when a melee unit is blocked (stuck building), add a
// tangential slide around the obstruction toward the open flank so surplus
// attackers wrap the enemy formation instead of jamming into their own back line.
// Avoidance-wall fix (Part A of the principled envelopment fix): the soft
// separation halo (active to 1.5*minDist = 45px) sits OUTSIDE the 33px melee
// contact ring, so rear-rank attackers are repelled by their own engaged front
// rank before they can close to strike range. AVHALO shrinks that halo and
// AVFORCE kills the non-overlap standoff force, letting hard collision
// (resolveCollisions, ~29px) pack attackers into their 33px contact ring.
const AVHALO = parseFloat(process.env.AVHALO || "1.5");
const AVFORCE = process.env.AVFORCE != null ? parseFloat(process.env.AVFORCE) : 0.5;
if (AVHALO !== 1.5 || AVFORCE !== 0.5) {
    const a1 = "if (dist < minDist * 1.5 && dist > 0) {";
    const a2 = "const force = overlap > 0 ? 3 + overlap * 5 : 0.5;";
    if (!simSrc.includes(a1) || !simSrc.includes(a2)) { console.error("!! avoidance lines not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(a1, `if (dist < minDist * ${AVHALO} && dist > 0) {`)
                   .replace(a2, `const force = overlap > 0 ? 3 + overlap * 5 : ${AVFORCE};`);
}
// Part B (the real envelopment fix, per the AoE2 pathing reference): melee target
// selection = nearest REACHABLE enemy, re-evaluated every tick. An enemy whose
// contact ring already holds >= SLOT attackers is treated as not-reachable, so
// overflow attackers pick the next-nearest enemy -> they slide around the
// saturated front to flanks/rear -> encirclement emerges (no fudge multiplier).
const SLOT = parseInt(process.env.SLOT || "0", 10);
if (SLOT > 0) {
    const F_OLD = `            const dist = this.distanceTo(enemy);
            // Prefer targets not in blockedTargets
            if (!this.blockedTargets.has(enemy)) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }`;
    const F_NEW = `            const dist = this.distanceTo(enemy);
            let _open = !this.blockedTargets.has(enemy);
            const _ring = enemy.radius + this.radius + this.attackRange + 4;
            if (_open && !this.isRanged() && dist > _ring) {
                const _mates = this.team === 1 ? simulation.team1 : simulation.team2;
                let _load = 0;
                for (const _m of _mates) {
                    if (_m === this || _m.state === "dead") continue;
                    const _dx = _m.x - enemy.x, _dy = _m.y - enemy.y;
                    if (_dx * _dx + _dy * _dy <= _ring * _ring) { if (++_load >= ${SLOT}) { _open = false; break; } }
                }
            }
            if (_open) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }`;
    const U_OLD = `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        }
        if (!this.target) {`;
    const U_NEW = `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        } else if (!this.isRanged() && !this.inRange()) {
            this.findTarget(enemies);
        }
        if (!this.target) {`;
    if (!simSrc.includes(F_OLD)) { console.error("!! findTarget block not found — aborting"); process.exit(2); }
    if (!simSrc.includes(U_OLD)) { console.error("!! update target-acq block not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(F_OLD, F_NEW).replace(U_OLD, U_NEW);
}
// ENVELOP: SLOT done with the RIGHT geometry (2026-07-24). Same idea — a saturated
// target is unreachable, so overflow attackers spill around it to the flanks and rear
// and encirclement emerges — but fixing the two things that made flat SLOT a lateral
// move (it repaired the Warrior Priest + White Feather Guard pins and broke the Battle
// Elephant and Guecha rows, 12/15 either way):
//
//   1. CAPACITY IS SIZE-AWARE. How many attackers physically fit around a target is
//      n = floor(pi / asin(ra / (rt + ra))): 6 for equal bodies, ~9 around a body twice
//      your radius, fewer around something smaller. Flat SLOT=6 counted occupancy in a
//      ring that GREW with the target's radius while keeping the cap at 6, so a Battle
//      Elephant read as "full" when it can host far more — ETG attackers then refused
//      the elephant they were standing next to and wandered off (100% win -> 75% flip).
//   2. RANGED TARGETS ARE EXEMPT. You cannot saturate something that is running away,
//      and re-picking a chase target every tick let the ETG always switch to whichever
//      kiter was nearest instead of committing — which un-did the in-game-validated
//      KITE loss vs the Guecha (0% -> 38%). Melee-vs-melee only.
const ENVELOP = process.env.ENVELOP === "1";
if (ENVELOP) {
    const E_OLD = `            const dist = this.distanceTo(enemy);
            // Prefer targets not in blockedTargets
            if (!this.blockedTargets.has(enemy)) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }`;
    const E_NEW = `            const dist = this.distanceTo(enemy);
            let _open = !this.blockedTargets.has(enemy);
            const _ring = enemy.radius + this.radius + this.attackRange + 4;
            if (_open && !this.isRanged() && !enemy.isRanged() && dist > _ring) {
                const _s = Math.min(0.999, this.radius / (enemy.radius + this.radius));
                const _cap = Math.max(3, Math.floor(Math.PI / Math.asin(_s)));
                const _mates = this.team === 1 ? simulation.team1 : simulation.team2;
                let _load = 0;
                for (const _m of _mates) {
                    if (_m === this || _m.state === "dead") continue;
                    const _dx = _m.x - enemy.x, _dy = _m.y - enemy.y;
                    if (_dx * _dx + _dy * _dy <= _ring * _ring) { if (++_load >= _cap) { _open = false; break; } }
                }
            }
            if (_open) {
                if (dist < closestDist) {
                    closestDist = dist;
                    closest = enemy;
                }
            }`;
    const EU_OLD = `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        }
        if (!this.target) {`;
    // Re-target ONLY when the current target is genuinely saturated — that is the whole
    // envelopment trigger. Re-picking every tick (what flat SLOT did) pays the RETARGET
    // switch wind-up over and over as the nearest body jostles, which quietly halved the
    // ETG's output against a packed elephant line (100% win -> 75% flip) even though the
    // capacity cap itself never bound there.
    const EU_NEW = `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        } else if (!this.isRanged() && !this.target.isRanged() && !this.inRange()) {
            this.findTarget(enemies);
        }
        if (!this.target) {`;
    if (!simSrc.includes(E_OLD)) { console.error("!! ENVELOP: findTarget block not found — aborting"); process.exit(2); }
    if (!simSrc.includes(EU_OLD)) { console.error("!! ENVELOP: update target-acq block not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(E_OLD, E_NEW).replace(EU_OLD, EU_NEW);
}
// RETARGET = seconds of attack wind-up when switching to a NEW target (turn +
// animation start; the real game loses ~this much per switch, which is why the
// in-game ETG's early throughput matches a FLAT 2.0s reload — the ramp doesn't
// pay off while chain-retargeting). JITTER adds uniform [0,J) per switch via the
// seeded Math.random — a per-seed variance source mirroring the game's own
// engine-timing nondeterminism.
const RETARGET = parseFloat(process.env.RETARGET || "0");
const JITTER = parseFloat(process.env.JITTER || "0");
if (RETARGET > 0 || JITTER > 0) {
    const T_OLD = `        // Use unblocked target if available, else fall back to closest
        this.target = closest || fallback;`;
    // ADDITIVE: turning + stepping to the new target costs time ON TOP of any
    // remaining reload (max(cooldown, x) is swallowed by the 1.8s reload).
    const T_NEW = `        // Use unblocked target if available, else fall back to closest
        const _newT = closest || fallback;
        if (_newT && _newT !== this.target) {
            // The wind-up models "walk + re-face after your target dies", so it is charged
            // on first acquisition and on any switch made while ENGAGED or after a death.
            // Under ENVELOP a still-MARCHING unit re-picks its heading every tick as the
            // contact rings fill; it has begun no swing, so charging it there compounds
            // per tick and silently halves output (it cost the ETG the elephant row).
            const _marchSwitch = ${ENVELOP ? "true" : "false"} && this.target
                && this.target.state !== "dead" && !this.inRange();
            if (!_marchSwitch) {
                this.attackCooldown += ${RETARGET} + Math.random() * ${JITTER};
            }
        }
        this.target = _newT;`;
    if (!simSrc.includes(T_OLD)) { console.error("!! findTarget assignment not found"); process.exit(2); }
    simSrc = simSrc.replace(T_OLD, T_NEW);
}
// ADELAY/AJIT: arrival wind-up — when a unit stops moving in range it must
// stop/face/start the swing before the first hit (the game staggers first
// contact over ~1-2s; the sim otherwise lands ALL first hits at t0).
const ADELAY = parseFloat(process.env.ADELAY || "0");
const AJIT = parseFloat(process.env.AJIT || "0");
if (ADELAY > 0 || AJIT > 0) {
    const A_OLD = `            } else if (this.inRange()) {
                this.attackCooldown = this.attackDelay;
                this.wasMoving = false;`;
    const A_NEW = `            } else if (this.inRange()) {
                this.attackCooldown = Math.max(this.attackDelay,
                    ${ADELAY} + Math.random() * ${AJIT});
                this.wasMoving = false;`;
    if (!simSrc.includes(A_OLD)) { console.error("!! ranged arrival block not found"); process.exit(2); }
    simSrc = simSrc.replace(A_OLD, A_NEW);
    // MELEE arrival: the melee branch attacks the instant it is inRange with no
    // wind-up at all (wasMoving is never consumed there). Gate the first swing
    // after ANY movement behind a stop/face/raise-weapon delay.
    const M_OLD = `            } else if (this.inRange()) {
                if (this.attackCooldown <= 0) {
                    if (this.attackDelay > 0) {`;
    const M_NEW = `            } else if (this.inRange()) {
                if (this.wasMoving) {
                    this.attackCooldown = Math.max(this.attackCooldown,
                        ${ADELAY} + Math.random() * ${AJIT});
                    this.wasMoving = false;
                    this.state = "attacking";
                } else if (this.attackCooldown <= 0) {
                    if (this.attackDelay > 0) {`;
    if (!simSrc.includes(M_OLD)) { console.error("!! melee arrival block not found"); process.exit(2); }
    simSrc = simSrc.replace(M_OLD, M_NEW);
}
// CHURN: per-swing crowd interference for MELEE units — every swing cycle in a
// dense mêlée takes uniform [0, CHURN) longer (shoving, turning, target micro-
// movement). Measured in-game: BOTH sides run ~30-40% over nominal reload even
// before any deaths (Husk 2.5-3.3 vs nominal 2.0). Long gaps also decay the
// ETG ramp window naturally, which is why the game's ETG:Husk rate ratio is
// only ~1.3 (not the static-melee 1.67 the sim produced).
const CHURN = parseFloat(process.env.CHURN || "0");
if (CHURN > 0) {
    const C_OLD = `        this.attackCooldown = this.reloadTime;
    }

    fireProjectile(target, isExtra = false) {`;
    // Crowd-scaled: interference is proportional to local crowding (within 2
    // tiles, saturating at CROWDN neighbors). In the thinned-out mop-up phase
    // churn vanishes — the winner finishes efficiently (game winner keeps ~19%
    // army HP) and the side that thins the field fights faster (snowball).
    const CROWDN = parseFloat(process.env.CROWDN || "6");
    const C_NEW = `        if (!this.isRanged()) {
            let _n = 0;
            const _R2 = (2 * TILE_SIZE) * (2 * TILE_SIZE);
            for (const _u of simulation.team1) {
                if (_u !== this && _u.state !== "dead") {
                    const _dx = _u.x - this.x, _dy = _u.y - this.y;
                    if (_dx * _dx + _dy * _dy < _R2) _n++;
                }
            }
            for (const _u of simulation.team2) {
                if (_u !== this && _u.state !== "dead") {
                    const _dx = _u.x - this.x, _dy = _u.y - this.y;
                    if (_dx * _dx + _dy * _dy < _R2) _n++;
                }
            }
            const _cf = Math.min(1, _n / ${CROWDN});
            this.attackCooldown = this.reloadTime + Math.random() * ${CHURN} * _cf;
        } else {
            this.attackCooldown = this.reloadTime;
        }
    }

    fireProjectile(target, isExtra = false) {`;
    if (!simSrc.includes(C_OLD)) { console.error("!! performAttack cooldown line not found"); process.exit(2); }
    simSrc = simSrc.replace(C_OLD, C_NEW);
}
// TRAMPLE_K: packing compensation for the trample blast radius. simulate.js's
// trample reach (attacker hull + trample_radius + enemy hull) is sized for the
// GAME's tight melee packing; the V2 arena spawns looser (BSP=30 ~= 1 tile, about
// 1.5x the game's ~0.6-tile melee spacing), so the 0.5-tile blast reaches fewer
// neighbours than in-game and only ~1 unit/swing is trampled (game: several).
// Scale the blast radius by TRAMPLE_K to restore game coverage. Validated on the
// recorded ETG set: vs-elephant HP-margin MAE 9.5 -> 7.1 at K=1.5, no regressions.
const TRAMPLE_K = parseFloat(process.env.TRAMPLE_K || "1");
if (TRAMPLE_K !== 1) {
    const TK_OLD = "this.radius + trampleInfo.radius + enemy.radius";
    if (!simSrc.includes(TK_OLD)) { console.error("!! trample reach expr not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(TK_OLD, `this.radius + trampleInfo.radius * ${TRAMPLE_K} + enemy.radius`);
}
// KITE: wall-slide kiting. moveAwayFromTarget retreats DIRECTLY away from the
// chaser and clamps to the 900x600 canvas — so a kiting ranged unit runs into
// the wall/corner within seconds and gets pinned, and a faster kiter can never
// use its speed edge. The real 16x16 arena + ddkMatchupAI patrol loop lets a
// faster kiter circle indefinitely (measured 2026-07-19: Guecha 20 vs ETG 21
// in-game = 3/3 decisive Guecha wins keeping 50-100% of units, vs the sim's
// 27/73 coin-flip at S -6). Fix: when the retreat step would leave the arena,
// slide ALONG the boundary in whichever axis direction ends farthest from the
// chaser — the box becomes a loop track. Speed-gating stays emergent: a kiter
// slower than its chaser is still run down; corners still catch kiters whose
// chaser cuts the diagonal (the in-game loss basin).
const KITE = process.env.KITE === "1";
if (KITE) {
    const K_OLD = `        // Smooth velocity for kiting too
        const smoothing = 0.3;
        this.vx = this.vx * smoothing + dx * (1 - smoothing);
        this.vy = this.vy * smoothing + dy * (1 - smoothing);
        const vLen = Math.sqrt(
            this.vx * this.vx + this.vy * this.vy,
        );
        if (vLen > 0) {
            this.vx /= vLen;
            this.vy /= vLen;
        }
        const moveAmount = this.moveSpeed * dt;
        this.x += this.vx * moveAmount;
        this.y += this.vy * moveAmount;
        this.x = Math.max(
            this.radius,
            Math.min(CANVAS_WIDTH - this.radius, this.x),
        );
        this.y = Math.max(
            this.radius,
            Math.min(CANVAS_HEIGHT - this.radius, this.y),
        );
    }`;
    const K_NEW = `        // Smooth velocity for kiting too
        const smoothing = 0.3;
        this.vx = this.vx * smoothing + dx * (1 - smoothing);
        this.vy = this.vy * smoothing + dy * (1 - smoothing);
        const vLen = Math.sqrt(
            this.vx * this.vx + this.vy * this.vy,
        );
        if (vLen > 0) {
            this.vx /= vLen;
            this.vy /= vLen;
        }
        const moveAmount = this.moveSpeed * dt;
        const loX = this.radius, hiX = CANVAS_WIDTH - this.radius;
        const loY = this.radius, hiY = CANVAS_HEIGHT - this.radius;
        let nx = this.x + this.vx * moveAmount;
        let ny = this.y + this.vy * moveAmount;
        if ((nx < loX || nx > hiX || ny < loY || ny > hiY) && this.target) {
            // Pinned against the boundary: slide along the wall in whichever
            // axis step ends farthest from the pursuer (loop-track escape).
            let bestD = -1;
            let bx = Math.max(loX, Math.min(hiX, nx));
            let by = Math.max(loY, Math.min(hiY, ny));
            for (const c of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
                const px = Math.max(loX, Math.min(hiX, this.x + c[0] * moveAmount));
                const py = Math.max(loY, Math.min(hiY, this.y + c[1] * moveAmount));
                if (px === this.x && py === this.y) continue;
                const ddx = px - this.target.x, ddy = py - this.target.y;
                const d = ddx * ddx + ddy * ddy;
                if (d > bestD) { bestD = d; bx = px; by = py; this.vx = c[0]; this.vy = c[1]; }
            }
            this.x = bx; this.y = by;
        } else {
            this.x = Math.max(loX, Math.min(hiX, nx));
            this.y = Math.max(loY, Math.min(hiY, ny));
        }
    }`;
    if (!simSrc.includes(K_OLD)) { console.error("!! moveAwayFromTarget block not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(K_OLD, K_NEW);
}
// KITE_CATCH: interception gate on the kite DECISION (see sim_v2_model.js).
// The rig's ground truth is a patrol loop on a bounded arena: whether kiting
// works is decided by the CHASER'S ABSOLUTE SPEED (can it cut the loop's
// chords?), not the speed ratio — Guecha 1.15 kites ETG 1.05 to a 3/3 win
// (ratio only 1.10), while Xianbei 1.54 is caught by champi 1.21 in 5/5 tapes
// (ratio 1.27). A kiter flees only chasers slower than KITE_CATCH; against a
// faster chaser it stands and fires (what the tape shows once cornered).
// Ranged-vs-ranged (target.isRanged()) never fled via shouldKite — unaffected.
const KITE_CATCH = parseFloat(process.env.KITE_CATCH || "0");
if (KITE_CATCH > 0) {
    const KR_OLD = `            const shouldKite = !this.target.isRanged();
            if (this.tooClose()) {`;
    const KR_NEW = `            const __canKite = this.moveSpeed <= (this.target.moveSpeed || 0)
                || (this.target.moveSpeed || 0) < ${KITE_CATCH} * TILE_SIZE
                || this.getDamageAgainst(this.target)
                    > Math.max(3, 0.05 * this.target.maxHp);
            const shouldKite = !this.target.isRanged() && __canKite;
            if (this.tooClose() && __canKite) {`;
    if (!simSrc.includes(KR_OLD)) { console.error("!! kite-catch anchor not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(KR_OLD, KR_NEW);
}
// TRAMPLE_CONE: angular gate for CONICAL blast (dat blast_attack_level=162,
// "100% damage in a conical shape"). The ref schema has no blast-shape column,
// so config_combat models these units as omnidirectional trample — harmless in
// the position-less sims, but catastrophically wrong here: under ENVELOP the
// swarm surrounds the trampler and a 360-degree blast hits ~6 units where the
// real cone hits the 1-2 in FRONT (champi-vs-Ibirapema: sim wiped the champi
// in 18s; the tape is a 4/5 champi win). Splash only lands on enemies within
// TRAMPLE_CONE degrees (full width) of the attacker->target facing, for the
// slugs in CONE_SLUGS. Elephants keep their genuine 360-degree trample.
const TRAMPLE_CONE = parseFloat(process.env.TRAMPLE_CONE || "0");
const CONE_SLUGS = new Set(["ibirapema_warrior_tupi", "elite_ibirapema_warrior_tupi"]);
if (TRAMPLE_CONE > 0) {
    const TC_OLD = `                                enemy.takeDamage(trampleDmg, this);`;
    const TC_NEW = `                                let __coneOk = true;
                                if (this.trampleConeCos !== undefined && target) {
                                    const __fx = target.x - this.x, __fy = target.y - this.y;
                                    const __ex = enemy.x - this.x, __ey = enemy.y - this.y;
                                    const __fl = Math.hypot(__fx, __fy) || 1;
                                    const __el = Math.hypot(__ex, __ey) || 1;
                                    __coneOk = (__fx * __ex + __fy * __ey) / (__fl * __el) >= this.trampleConeCos;
                                }
                                if (__coneOk) enemy.takeDamage(trampleDmg, this);`;
    if (!simSrc.includes(TC_OLD)) { console.error("!! trample-cone anchor not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(TC_OLD, TC_NEW);
}
const FLANK = parseFloat(process.env.FLANK || "0");
if (FLANK > 0) {
    const OLD_AV = `        // If avoidance is strong (units very close), let it dominate
        if (avoidMag > 2) {
            dx = avoidance.x + dx * 0.2;
            dy = avoidance.y + dy * 0.2;
        } else {
            dx += avoidance.x;
            dy += avoidance.y;
        }`;
    const NEW_AV = `        const _seekx = dx, _seeky = dy;
        // If avoidance is strong (units very close), let it dominate
        if (avoidMag > 2) {
            dx = avoidance.x + dx * 0.2;
            dy = avoidance.y + dy * 0.2;
        } else {
            dx += avoidance.x;
            dy += avoidance.y;
        }
        if (!this.isRanged() && (this._blockT || 0) > 0.3) {
            let _tx = -_seeky, _ty = _seekx;
            if (_tx * avoidance.x + _ty * avoidance.y < 0) { _tx = -_tx; _ty = -_ty; }
            const _f = Math.min(1, (this._blockT || 0) - 0.3) * ${FLANK};
            dx += _tx * _f;
            dy += _ty * _f;
        }`;
    if (!simSrc.includes(OLD_AV)) { console.error("!! moveTowardTarget avoidance block not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(OLD_AV, NEW_AV);
    // Maintain a block-timer that (unlike stuckTimer) findTarget does NOT reset,
    // so the flank tangent still fires under Part B's every-tick retargeting.
    const S_OLD = `        if (newDist >= this.lastDistToTarget - 0.5) {
            this.stuckTimer += dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
        }`;
    const S_NEW = `        if (newDist >= this.lastDistToTarget - 0.5) {
            this.stuckTimer += dt;
            this._blockT = (this._blockT || 0) + dt;
        } else {
            this.stuckTimer = Math.max(0, this.stuckTimer - dt * 2);
            this._blockT = Math.max(0, (this._blockT || 0) - dt * 2);
        }`;
    if (!simSrc.includes(S_OLD)) { console.error("!! stuck-detection block not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(S_OLD, S_NEW);
}

const shim = `
;Math.random = __rng;
globalThis.__HL = { BattleSimulation, BattleUnit, Projectile, MeleeEffect, TILE_SIZE };
globalThis.__setSim = function (s) { simulation = s; };
`;
const combined = [
    read("constants.js"), read("unit_sprites.js"), read("api_client.js"),
    read("sim_params.js"), simSrc, shim,
].join("\n;\n");

const ctx = vm.createContext(sandbox);
vm.runInContext(combined, ctx, { filename: "combined.js" });
const { BattleSimulation } = sandbox.__HL;

// ---- run one battle (team1 = subject, team2 = opponent) ----------------------
async function runFight(cd1, slug1, civ1, n1, cd2, slug2, civ2, n2, seed) {
    sandbox.__setSeed(seed);
    const fakeCanvas = {
        width: 900, height: 600, style: {}, getContext: () => elStub(),
        getBoundingClientRect: () => ({ width: 900, height: 600, left: 0, top: 0, right: 900, bottom: 600 }),
    };
    const sim = new BattleSimulation(fakeCanvas);
    sandbox.__setSim(sim);
    sim.updateStats = () => {}; sim.updateDebugPanel = () => {}; sim.render = () => {};
    const key = (civ, slug) => `/api/ref/combat-unit/${encodeURIComponent(civ)}/${slug}?age=Imperial`;
    const STATS = { [key(civ1, slug1)]: cd1, [key(civ2, slug2)]: cd2 };
    sandbox.fetch = async (url) => ({ ok: true, json: async () => STATS[url] });
    await sim.setupTeam(1, slug1, civ1, n1, "Imperial", {});
    await sim.setupTeam(2, slug2, civ2, n2, "Imperial", {});
    sandbox.fetch = defaultFetch;
    if (TRAMPLE_CONE > 0) {
        // conical-blast units splash only inside the front arc (see the
        // TRAMPLE_CONE transform above); cos of the HALF-angle
        const coneCos = Math.cos((TRAMPLE_CONE / 2) * Math.PI / 180);
        if (CONE_SLUGS.has(slug1)) for (const u of sim.team1) u.trampleConeCos = coneCos;
        if (CONE_SLUGS.has(slug2)) for (const u of sim.team2) u.trampleConeCos = coneCos;
    }
    // Optional compact-block spawn (matches the real 16x16 arena clusters). A
    // full-height line-vs-line prevents envelopment; compact blocks let the
    // larger army wrap the smaller. gap = center separation; sp = unit spacing.
    // The V2 model sets BLOCK=1 (see sim_v2_model.js).
    if (process.env.BLOCK) {
        const gap = parseFloat(process.env.GAP || "130");
        const bsp = parseFloat(process.env.BSP || "0");   // fixed spacing px (game: 30 = 1 tile)
        const blockify = (team, cx) => {
            const n = team.length; if (!n) return;
            const r = team[0].radius;
            const sp = bsp > 0 ? bsp : r * 2.0 * (PACK < 1 ? PACK : 1);
            const cols = Math.max(1, Math.round(Math.sqrt(n)));
            const rows = Math.ceil(n / cols);
            for (let i = 0; i < n; i++) {
                const rr = Math.floor(i / cols), cc = i % cols;
                team[i].x = cx + (cc - (cols - 1) / 2) * sp + (rng() - 0.5) * 2;
                team[i].y = 300 + (rr - (rows - 1) / 2) * sp + (rng() - 0.5) * 2;
            }
        };
        blockify(sim.team1, 450 - gap);
        blockify(sim.team2, 450 + gap);
    }
    const STEP = 1 / 60;
    let t = 0;
    while (sim.winner === null && t < MAX_S) { sim.update(STEP); t += STEP; }
    const alive = (tm) => sim[tm].filter((u) => u.state !== "dead").length;
    const hp = (tm) => sim[tm].reduce((s, u) => s + Math.max(0, u.currentHp), 0);
    const mhp = (tm) => sim[tm].reduce((s, u) => s + u.maxHp, 0);
    const h1 = hp("team1") / Math.max(1, mhp("team1"));
    const h2 = hp("team2") / Math.max(1, mhp("team2"));
    let winner = sim.winner;
    if (winner === null) winner = h1 > h2 ? 1 : h2 > h1 ? 2 : 0;
    return { winner, alive1: alive("team1"), alive2: alive("team2"), h1, h2,
             margin: (h1 - h2) * 100, time: sim.battleTime };
}
module.exports = { runFight, RAMP, N_SEEDS, MAX_S, sandbox };

// This module is a library; callers require() it (via sim_v2_model.js) and drive
// runFight(). The 12-fight in-game calibration self-test that used to live here
// lived off ETG-specific fixtures — see the calibration record referenced in
// sim_v2/README.md. To exercise the harness directly, use run_pool_v2.js.
