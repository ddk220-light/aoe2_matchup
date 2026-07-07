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
        `        this.radius = Math.max(4, outlineSize * TILE_SIZE * ${RSCALE});`);
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
            this.attackCooldown += ${RETARGET} + Math.random() * ${JITTER};
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
