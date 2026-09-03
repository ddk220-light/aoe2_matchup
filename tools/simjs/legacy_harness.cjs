// GOLDEN-CAPTURE HARNESS — adapted copy of the recording branch's vm harness.
//
//   Provenance: git show origin/aoe2_ai_for_simulation:apps/video/sim_v2/headless_sim.js
//
// Loads the REAL apps/website/static/js/simulate.js (+ its sibling scripts, in browser
// load order) in a vm sandbox so every closure/const is intact, stubs DOM/canvas, seeds
// Math.random with mulberry32 for determinism, and drives BattleSimulation.update() at
// the webapp's fixed 1/60 timestep. Combat / steering / flanking are byte-identical to
// production.
//
// WHAT CHANGED vs the upstream copy (and why):
//  1. REPO is two levels up (this file lives at tools/simjs/, not apps/video/sim_v2/).
//  2. EVERY experiment knob (RAMP/PACK/RTRUE/ENVELOP/CATCH/KITE/CHURN/...) is PINNED to
//     its production-default literal and no longer reads process.env or process.argv.
//     The golden panel must be captured from the SHIPPED engine, so none of the source
//     transforms below may fire. A hard assertion after the transform section proves the
//     source handed to the vm is unchanged from what was read off disk (modulo the CRLF
//     normalisation in read()) — see NO-TRANSFORM GUARD.
//  3. runFight() is replaced by runFightCaptured(), which records per-tick snapshots and
//     resolves unit stats from a frozen combat_dicts.json instead of a live Flask server.
// The transform blocks themselves are kept verbatim (inert) so the diff against the
// recording branch stays readable.
const fs = require("fs");
const vm = require("vm");
const path = require("path");

// This harness lives at tools/simjs/; the webapp sim it drives is two levels up at
// apps/website/static/js. Derive the repo root from __dirname so the harness is
// portable (no hard-coded absolute path).
const REPO = path.resolve(__dirname, "..", "..");
// PINNED: always the live webapp's static JS. No JSDIR override — the golden panel is
// defined as "what apps/website/static/js/simulate.js does at this commit".
const JSDIR = path.join(REPO, "apps", "website", "static", "js");

const RAMP = "ship";      // PINNED (was: env RAMP / argv[2]) — "ship" applies no transform
const MAX_S = 600;        // default fight cap in seconds; runFightCaptured takes its own
// Packing factor: scales the melee separation/collision spacing. 1.0 = ship.
// The game packs infantry far tighter than the sim's visual radius implies;
// PACK<1 shrinks the collision/avoidance minDist toward game-like density.
const PACK = 1.0;         // PINNED (was: env PACK)
// RTRUE: use the GAME's true collision radius (outline_size tiles * TILE_SIZE px)
// instead of the rendering-driven 10+outline*20 formula (which inflates infantry
// bodies 2.3x in diameter and causes the melee traffic jam). RSCALE fine-tunes.
const RTRUE = false;      // PINNED (was: env RTRUE === "1")
const RSCALE = 1.0;       // PINNED (was: env RSCALE)

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
// Kept for the NO-TRANSFORM GUARD at the end of the transform section.
const rawSimSrc = simSrc;

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
    const GRAZE_K = 1;    // PINNED (was: env GRAZE_K)
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
const AVHALO = 1.5;       // PINNED (was: env AVHALO)
const AVFORCE = 0.5;      // PINNED (was: env AVFORCE)
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
const SLOT = 0;           // PINNED (was: env SLOT)
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
const ENVELOP = false;    // PINNED (was: env ENVELOP === "1")
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
// CATCH: a melee unit whose target has stepped out of reach re-picks the closest
// enemy — INCLUDING when that target is ranged. ENVELOP added exactly this
// re-pick but excluded ranged targets (`!this.target.isRanged()`), which left a
// hole big enough to invert whole matchup tables: a melee unit locked onto one
// fleeing archer walks through the rest of the archer line without swinging.
// Measured (2026-07-27, 21 Slinger @0.96 vs 7 Paladin @1.35): the Paladins DO
// close to 0.6-0.8 tiles — adjacent — yet sit in state "moving" and land 7.1
// hits per unit in 180s (they should land ~90). 6 Cataphracts landed 0.8 each
// and died. The kiters were never faster; the chasers simply never attacked
// what was in front of them. Not a wall-slide artifact: KITE=0 changes it by
// almost nothing. The re-pick is free of the RETARGET wind-up because the
// switch is made while MARCHING (see the _marchSwitch exemption below).
const CATCH = false;      // PINNED (was: env CATCH === "1")
// CATCH_R: extra grab radius in TILES beyond strict attack reach. 0 = only an
// enemy already inside your swing; larger values let a chaser turn on a body it
// is nearly touching (the measured Paladins sat at 0.6-0.8 tiles, just outside
// a ~0.4-tile melee reach, which is why a strict in-reach test barely fired).
const CATCH_R = 0 * 30;   // PINNED (was: env CATCH_R) * TILE_SIZE (px per tile)
if (CATCH) {
    const C_OLD = ENVELOP
        ? `        } else if (!this.isRanged() && !this.target.isRanged() && !this.inRange()) {
            this.findTarget(enemies);
        }`
        : `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        }`;
    // Deliberately NOT a general re-pick: swing only at an enemy that is
    // ALREADY within attack range this tick. A blanket findTarget() re-pick
    // hands the chaser perfect target-switching and flips genuinely fast
    // kiters into losses (measured: ETG-vs-Genitour 0/5 -> 5/5, ETG-vs-Arambai
    // 0/5 -> 5/5, champi-vs-Blackwood 0/5 -> 5/5, all contradicting tape). A
    // kiter you can never touch stays untouched; one standing on your toes
    // does not.
    const C_SWING = `            let _b = null, _bd = Infinity;
            for (const _e of enemies) {
                if (_e.state === "dead" || _e === this.target) continue;
                // ...and only at an enemy no faster than you: a unit moving away
                // faster than you can swing is gone before the blow lands (melee
                // must stop, face and commit). Without this the arena's bounded
                // corners let a chaser tag genuinely uncatchable kiters in
                // passing — it drifted ETG-vs-Genitour 0/5 -> 3/5 against tape.
                if ((_e.moveSpeed || 0) > this.moveSpeed) continue;
                const _d = this.distanceTo(_e);
                if (_d <= this.attackRange + this.radius + _e.radius + ${CATCH_R} && _d < _bd) { _b = _e; _bd = _d; }
            }
            if (_b) this.target = _b;`;
    const C_NEW = ENVELOP
        ? `        } else if (!this.isRanged() && !this.inRange()) {
${C_SWING}
            else if (!this.target.isRanged()) this.findTarget(enemies);
        }`
        : `        if (!this.target || this.target.state === "dead") {
            this.findTarget(enemies);
        } else if (!this.isRanged() && !this.inRange()) {
${C_SWING}
        }`;
    if (!simSrc.includes(C_OLD)) { console.error("!! CATCH: target-acquisition block not found — aborting"); process.exit(2); }
    simSrc = simSrc.replace(C_OLD, C_NEW);
}
// RETARGET = seconds of attack wind-up when switching to a NEW target (turn +
// animation start; the real game loses ~this much per switch, which is why the
// in-game ETG's early throughput matches a FLAT 2.0s reload — the ramp doesn't
// pay off while chain-retargeting). JITTER adds uniform [0,J) per switch via the
// seeded Math.random — a per-seed variance source mirroring the game's own
// engine-timing nondeterminism.
const RETARGET = 0;       // PINNED (was: env RETARGET)
const JITTER = 0;         // PINNED (was: env JITTER)
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
const ADELAY = 0;         // PINNED (was: env ADELAY)
const AJIT = 0;           // PINNED (was: env AJIT)
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
const CHURN = 0;          // PINNED (was: env CHURN)
if (CHURN > 0) {
    const C_OLD = `        this.attackCooldown = this.reloadTime;
    }

    fireProjectile(target, isExtra = false) {`;
    // Crowd-scaled: interference is proportional to local crowding (within 2
    // tiles, saturating at CROWDN neighbors). In the thinned-out mop-up phase
    // churn vanishes — the winner finishes efficiently (game winner keeps ~19%
    // army HP) and the side that thins the field fights faster (snowball).
    const CROWDN = 6;     // PINNED (was: env CROWDN)
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
const TRAMPLE_K = 1;      // PINNED (was: env TRAMPLE_K)
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
const KITE = false;       // PINNED (was: env KITE === "1")
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
// RANGED-vs-RANGED (user rule, 2026-07-27): the ship engine never lets a ranged
// unit kite another ranged unit (shouldKite = !target.isRanged()). A unit that
// BOTH outranges AND outruns its ranged target genuinely can disengage and kite
// it, so __outclasses re-enables kiting for exactly that case. When either edge
// is missing neither can break away and it stays a stand-and-shoot brawl (Cav
// Archer vs Arbalest: Arbalest outranges, Cav Archer outruns -> no kiting).
// Mirrors the recording rig's template choice in build_golden_v2.py.
// KITE_CATCH: interception gate on the kite DECISION (see sim_v2_model.js).
// The rig's ground truth is a patrol loop on a bounded arena: whether kiting
// works is decided by the CHASER'S ABSOLUTE SPEED (can it cut the loop's
// chords?), not the speed ratio — Guecha 1.15 kites ETG 1.05 to a 3/3 win
// (ratio only 1.10), while Xianbei 1.54 is caught by champi 1.21 in 5/5 tapes
// (ratio 1.27). A kiter flees only chasers slower than KITE_CATCH; against a
// faster chaser it stands and fires (what the tape shows once cornered).
// Ranged-vs-ranged (target.isRanged()) never fled via shouldKite — unaffected.
const KITE_CATCH = 0;     // PINNED (was: env KITE_CATCH)
if (KITE_CATCH > 0) {
    const KR_OLD = `            const shouldKite = !this.target.isRanged();
            if (this.tooClose()) {`;
    const KR_NEW = `            const __canKite = this.moveSpeed <= (this.target.moveSpeed || 0)
                || (this.target.moveSpeed || 0) < ${KITE_CATCH} * TILE_SIZE
                || this.getDamageAgainst(this.target)
                    > Math.max(3, 0.05 * this.target.maxHp);
            const __outclasses = this.target.isRanged()
                && this.attackRange > this.target.attackRange
                && this.moveSpeed > (this.target.moveSpeed || 0);
            const shouldKite = (!this.target.isRanged() || __outclasses) && __canKite;
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
const TRAMPLE_CONE = 0;   // PINNED (was: env TRAMPLE_CONE)
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
const FLANK = 0;          // PINNED (was: env FLANK)
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

// ---- NO-TRANSFORM GUARD ------------------------------------------------------
// The whole point of this copy is that it runs the SHIPPED engine. Every knob above
// is pinned to its production default, so none of the transform blocks may have
// fired. Prove it rather than trust it: if simSrc drifted by even one byte, the
// captured panel would not be the production engine's behaviour and the golden would
// be silently wrong for every later extraction step.
if (simSrc !== rawSimSrc) {
    console.error(
        "!! legacy_harness.cjs transformed simulate.js — the golden panel must be " +
        "captured from the unmodified engine. Aborting.",
    );
    process.exit(2);
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

// ---- run one battle, recording snapshots (team1 = subject, team2 = opponent) --
//
// Replaces the upstream runFight(). Differences that matter:
//   * stats come from a frozen combat_dicts.json ({"<civ>|<slug>": {…}}) instead of a
//     live Flask server, and each fetch resolves a FRESH deep copy — exactly like a
//     real HTTP fetch parsing new JSON, so one fight can never mutate another's stats;
//   * it records the trajectory (see SNAPSHOT FORMAT below), not just the outcome;
//   * `winner` is reported RAW (sim.winner): 1, 2, 0 for mutual annihilation, or null
//     when the time cap is reached with both teams alive. The upstream HP-margin
//     tiebreak is deliberately NOT applied — the golden records what the engine did,
//     and any scoring convention belongs to the consumer.
//   * no BLOCK/GAP/BSP re-spawn: units keep the positions setupTeam() gives them,
//     which is what the production page does.
//
// SNAPSHOT FORMAT (mirrored by the parity runner in later tasks):
//   snapshots[i] = { tick, units: [[team, idx, x, y, hp, state], …] }
//     tick  — number of update() calls completed (0 = post-spawn, pre-update)
//     team  — 1 or 2;  idx — index within that team's array
//     x, y  — position in canvas px;  hp — currentHp;  state — unit state string
//     order — every team-1 unit in array order, then every team-2 unit; the dead are
//             included (their state is "dead") so array indices are stable for all ticks
//   cadence — tick 0, then after every 60th update() call, plus one final snapshot if
//             the fight ended off that cadence (so the last tick is always recorded)
//   final = { winner, time, alive1, alive2, hp1, hp2 }
//     time — sim.battleTime;  aliveN — units with state !== "dead"
//     hpN  — sum of currentHp over LIVING units only
// All numbers are written at full JSON double precision — never rounded.
async function runFightCaptured(dicts, row, seed, maxSeconds) {
    const dictFor = (civ, slug) => {
        const cd = dicts[`${civ}|${slug}`];
        if (!cd) throw new Error(`no combat dict for "${civ}|${slug}" — re-run dump_combat_dicts.py`);
        return cd;
    };
    const cd1 = dictFor(row.civ1, row.slug1);
    const cd2 = dictFor(row.civ2, row.slug2);

    sandbox.__setSeed(seed);
    const fakeCanvas = {
        width: 900, height: 600, style: {}, getContext: () => elStub(),
        getBoundingClientRect: () => ({ width: 900, height: 600, left: 0, top: 0, right: 900, bottom: 600 }),
    };
    const sim = new BattleSimulation(fakeCanvas);
    sandbox.__setSim(sim);
    sim.updateStats = () => {}; sim.updateDebugPanel = () => {}; sim.render = () => {};

    const key = (civ, slug) => `/api/ref/combat-unit/${encodeURIComponent(civ)}/${slug}?age=Imperial`;
    const STATS = { [key(row.civ1, row.slug1)]: cd1, [key(row.civ2, row.slug2)]: cd2 };
    sandbox.fetch = async (url) => {
        if (!(url in STATS)) {
            // Not fatal (production tolerates optional fetches), but the golden capture
            // should never silently feed the engine an empty payload unnoticed.
            console.error(`  [warn] unstubbed fetch: ${url}`);
            return { ok: true, json: async () => ({}) };
        }
        return { ok: true, json: async () => JSON.parse(JSON.stringify(STATS[url])) };
    };
    await sim.setupTeam(1, row.slug1, row.civ1, row.n1, "Imperial", {});
    await sim.setupTeam(2, row.slug2, row.civ2, row.n2, "Imperial", {});
    sandbox.fetch = defaultFetch;

    const snap = (tick) => {
        const units = [];
        for (let i = 0; i < sim.team1.length; i++) {
            const u = sim.team1[i];
            units.push([1, i, u.x, u.y, u.currentHp, u.state]);
        }
        for (let i = 0; i < sim.team2.length; i++) {
            const u = sim.team2[i];
            units.push([2, i, u.x, u.y, u.currentHp, u.state]);
        }
        return { tick, units };
    };

    const STEP = 1 / 60;
    // Integer tick budget rather than accumulating floats: 600 s is exactly 36000
    // update() calls, so the cap lands on the same tick on every machine and re-run.
    const maxTicks = Math.round(maxSeconds * 60);
    const snapshots = [snap(0)];
    let ticks = 0;
    while (sim.winner === null && ticks < maxTicks) {
        sim.update(STEP);
        ticks++;
        if (ticks % 60 === 0) snapshots.push(snap(ticks));
    }
    if (ticks % 60 !== 0) snapshots.push(snap(ticks));

    const living = (tm) => sim[tm].filter((u) => u.state !== "dead");
    const hpOf = (tm) => living(tm).reduce((s, u) => s + u.currentHp, 0);
    return {
        snapshots,
        final: {
            winner: sim.winner,          // 1 | 2 | 0 (mutual) | null (hit the time cap)
            time: sim.battleTime,
            alive1: living("team1").length,
            alive2: living("team2").length,
            hp1: hpOf("team1"),
            hp2: hpOf("team2"),
        },
    };
}

module.exports = { runFightCaptured, RAMP, MAX_S, sandbox };

// This module is a library; parity_capture.mjs require()s it and drives
// runFightCaptured(). Nothing here may be parameterised by the environment — see the
// NO-TRANSFORM GUARD above.
