/*
 * Frontend projectile-accuracy / miss-graze tests for the on-page battle sim.
 *
 * Extracts the LIVE `BattleUnit` class from webapp/static/js/simulate.js (rather
 * than a hand-copied snapshot) and exercises fireProjectile under mocked
 * browser globals, so it tests exactly what ships. Mirrors the backend model in
 * webapp/simulation_real.py fire_projectile + tests/test_position_sim_abilities.
 *
 * Run:  node tests/test_frontend_projectile_miss.js
 */
const fs = require("fs");
const path = require("path");
const assert = require("assert");

// ---- extract `class BattleUnit { ... }` from the live source by brace match
const src = fs.readFileSync(
    path.join(__dirname, "..", "webapp", "static", "js", "simulate.js"),
    "utf8",
);
const start = src.indexOf("class BattleUnit");
assert(start >= 0, "BattleUnit class not found in simulate.js");
let i = src.indexOf("{", start);
let depth = 0;
let end = -1;
for (; i < src.length; i++) {
    const ch = src[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
        depth--;
        if (depth === 0) {
            end = i + 1;
            break;
        }
    }
}
assert(end > start, "could not brace-match BattleUnit class");
const classSrc = src.slice(start, end);

// ---- mocked browser globals the class closes over
const TILE_SIZE = 30;
const MELEE_RANGE_BUFFER = 5;
const CANVAS_WIDTH = 900;
const CANVAS_HEIGHT = 600;
const armorClassNames = {};
const simulation = { team1: [], team2: [], projectiles: [], effects: [] };
// Projectile stub: fire the onHit impact callback synchronously so a single
// fireProjectile() call resolves immediately (no animation loop in tests).
class Projectile {
    constructor(x, y, tx, ty, sp, team, siege, onHit) {
        this.done = false;
        if (onHit) onHit();
        this.done = true;
    }
    update() {}
}
class MeleeEffect {
    constructor() {
        this.done = true;
    }
    update() {}
}

const BattleUnit = eval(`(${classSrc})`);

// ---- helpers
function archerStats(extra = {}) {
    return Object.assign(
        {
            hp: 40,
            attack: 100, // big so graze/half is unambiguous
            attack_range: 5,
            attack_speed: 1,
            attack_delay: 0,
            movement_speed: 1,
            melee_armor: 0,
            pierce_armor: 0,
            attacks_json: '{"3":100}',
            armors_json: '{"3":0,"4":0}',
            accuracy: 100,
            base_accuracy: 100,
            outline_size: 0.2,
        },
        extra,
    );
}

function mk(stats, team, id) {
    const u = new BattleUnit(id, team, stats, "", "");
    u.x = 0;
    u.y = 0;
    u.state = "idle";
    return u;
}

let passed = 0;
function test(name, fn) {
    simulation.team1 = [];
    simulation.team2 = [];
    simulation.projectiles = [];
    simulation.effects = [];
    const realRandom = Math.random;
    try {
        fn();
        console.log("  ok  -", name);
        passed++;
    } finally {
        Math.random = realRandom;
    }
}

// 1) accuracy is read from stats as a 0-1 fraction
test("accuracy read from stats (80 -> 0.8)", () => {
    const u = mk(archerStats({ accuracy: 80, base_accuracy: 65 }), 1, "a");
    assert.strictEqual(u.accuracy, 0.8);
    assert.strictEqual(u.baseAccuracy, 0.65);
});

// 2) 100% accuracy always hits (full damage to a lone target)
test("100% accuracy always hits", () => {
    const a = mk(archerStats({ accuracy: 100 }), 1, "a");
    const t = mk(archerStats(), 2, "t");
    t.x = 100;
    t.y = 0;
    simulation.team1 = [a];
    simulation.team2 = [t];
    a.target = t;
    const hp0 = t.currentHp;
    a.fireProjectile(t);
    assert(t.currentHp < hp0, "target should take damage on a guaranteed hit");
});

// 3) a guaranteed miss with no other unit nearby deals ZERO damage
test("forced miss + no neighbor = 0 damage", () => {
    const a = mk(archerStats(), 1, "a");
    a.accuracy = 0; // force miss (willHit: Math.random() < 0 -> false)
    const t = mk(archerStats(), 2, "t");
    t.x = 100;
    t.y = 0;
    simulation.team1 = [a];
    simulation.team2 = [t];
    a.target = t;
    const hp0 = t.currentHp;
    a.fireProjectile(t);
    assert.strictEqual(t.currentHp, hp0, "missed shot must not damage the target");
});

// 4) default graze (no missDamagePercent) deals 0.5x to a grazed neighbor
test("forced miss grazes neighbor for 0.5x by default", () => {
    Math.random = () => 0; // angle=0, dist=0 -> arrow lands exactly at impact
    const a = mk(archerStats(), 1, "a");
    a.accuracy = 0; // force miss
    const t = mk(archerStats(), 2, "t");
    t.x = 100;
    t.y = 0;
    const n = mk(archerStats({ hp: 999 }), 2, "n"); // survives the graze
    n.x = 100; // neighbor sits at the impact point -> grazed
    n.y = 0;
    simulation.team1 = [a];
    simulation.team2 = [t, n];
    a.target = t;
    const dmg = a.getDamageAgainst(t); // 100 vs 0 pierce armor
    const nhp0 = n.currentHp;
    a.fireProjectile(t);
    assert.strictEqual(t.currentHp, 40, "target (intended) takes nothing on a miss");
    assert.strictEqual(
        n.currentHp,
        nhp0 - Math.floor(dmg * 0.5),
        "neighbor grazed for 0.5x",
    );
});

// 5) Arambai (missDamagePercent=1.0) grazes a neighbor for FULL damage
test("Arambai miss_damage_percent=1.0 grazes for full damage", () => {
    Math.random = () => 0;
    const a = mk(archerStats({ miss_damage_percent: 1.0 }), 1, "a");
    assert.strictEqual(a.missDamagePercent, 1.0);
    a.accuracy = 0; // force miss
    const t = mk(archerStats({ hp: 999 }), 2, "t");
    t.x = 100;
    t.y = 0;
    const n = mk(archerStats({ hp: 999 }), 2, "n");
    n.x = 100;
    n.y = 0;
    simulation.team1 = [a];
    simulation.team2 = [t, n];
    a.target = t;
    const dmg = a.getDamageAgainst(t);
    const nhp0 = n.currentHp;
    a.fireProjectile(t);
    assert.strictEqual(n.currentHp, nhp0 - dmg, "Arambai graze = full damage");
});

// 6) statistical: accuracy=0.5 hits roughly half the time over many shots
test("accuracy ~0.5 hits about half over many shots", () => {
    const a = mk(archerStats({ accuracy: 50 }), 1, "a");
    let hits = 0;
    const N = 4000;
    for (let k = 0; k < N; k++) {
        const t = mk(archerStats({ hp: 1e9 }), 2, "t" + k);
        t.x = 100;
        t.y = 0;
        simulation.team1 = [a];
        simulation.team2 = [t]; // lone target: a miss can't graze anyone
        a.target = t;
        const hp0 = t.currentHp;
        a.fireProjectile(t);
        if (t.currentHp < hp0) hits++;
    }
    const frac = hits / N;
    assert(
        frac > 0.45 && frac < 0.55,
        `hit fraction ${frac} not within [0.45,0.55]`,
    );
});

// 7) extra/secondary projectiles use baseAccuracy (Thumb Ring is primary-only)
test("isExtra uses baseAccuracy not accuracy", () => {
    const a = mk(archerStats({ accuracy: 100, base_accuracy: 1 }), 1, "a");
    // base_accuracy=1 -> 0.01 fraction -> extra shots essentially always miss
    let hits = 0;
    const N = 500;
    for (let k = 0; k < N; k++) {
        const t = mk(archerStats({ hp: 1e9 }), 2, "t" + k);
        t.x = 100;
        t.y = 0;
        simulation.team1 = [a];
        simulation.team2 = [t];
        a.target = t;
        const hp0 = t.currentHp;
        a.fireProjectile(t, true); // isExtra=true
        if (t.currentHp < hp0) hits++;
    }
    assert(hits < 25, `extra shots should almost always miss, got ${hits}/${N} hits`);
});

console.log(`\n${passed}/7 frontend projectile-miss tests passed`);
if (passed !== 7) process.exit(1);
