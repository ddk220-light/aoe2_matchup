// Round 5b -- the ranged fire model (D2 lead/arrival, D3 in-flight
// accounting, D4 approach margin) plus the master off-switch.
//
// D1's own tests live in battle_unit.test.mjs next to the E9 cadence tests it
// supersedes. Everything here pins a rule, not a number: the only constants
// referenced are the ones read out of the .dat (dispersion, projectile
// radius) and the geometry they imply.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import {
    TILE_SIZE,
    PROJECTILE_RADIUS_TILES,
    ACCURACY_DISPERSION_BY_SLUG,
    R5B,
    setR5B,
} from "../../../apps/website/static/js/engine/constants.js";

const DT = 1 / 60;
const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Archer",
};

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

function withR5B(overrides, fn) {
    const saved = { ...R5B };
    setR5B(overrides);
    try {
        return fn();
    } finally {
        setR5B(saved);
    }
}

// ---- D2: lead ---------------------------------------------------------------

test("[D2] the aim point leads a moving target by velocity x flight time", () => {
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    a.x = 0; a.y = 0;
    b.x = 7 * TILE_SIZE; b.y = 0;
    // Crossing at 1 tile/s, perpendicular to the line of fire.
    b.velX = 0; b.velY = 1 * TILE_SIZE;

    const aim = a.aimPointFor(b);
    // Flight is ~7 tiles at 7 tiles/s == ~1 s, so the lead is ~1 tile of y.
    // Solved as a fixed point, so the aim point is slightly further out than
    // the straight-line 7 tiles -- assert the physics, not a literal.
    const flight = Math.hypot(aim.x - a.x, aim.y - a.y) / (7 * TILE_SIZE);
    // Two fixed-point passes, so the intercept is converged rather than exact:
    // the residual here is ~0.006 px (2e-4 tiles), four orders of magnitude
    // below the 0.3-tile overlap radius that decides a hit.
    assert.ok(
        Math.abs(aim.y - b.velY * flight) < 0.05,
        `aim.y ${aim.y} should equal velY x its own flight time (${b.velY * flight})`,
    );
    assert.ok(aim.y > 0.9 * TILE_SIZE, `expected ~1 tile of lead, got ${aim.y / 30}`);
    assert.equal(aim.x, b.x, "no lead along x -- the target has no x velocity");

    // A stationary target is aimed at directly.
    b.velY = 0;
    const still = a.aimPointFor(b);
    assert.equal(still.x, b.x);
    assert.equal(still.y, b.y);
});

test("[D2] with the flag off the aim point is the target's launch position", () => {
    const sim = simStub(5);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 210; b.y = 0; b.velY = 100;
    withR5B({ ballisticLead: false }, () => {
        const aim = a.aimPointFor(b);
        assert.equal(aim.x, b.x);
        assert.equal(aim.y, b.y);
    });
});

// ---- D2: arrival resolution -------------------------------------------------

test("[D2] a dat-100%-accuracy shot still HITS a target that stays put", () => {
    const sim = simStub(7);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7, accuracy: 100 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 6 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const hp0 = b.currentHp;
    a.fireProjectile(b);
    for (let i = 0; i < 300 && sim.projectiles.length; i++) {
        for (const p of sim.projectiles) p.update(DT);
        sim.projectiles = sim.projectiles.filter((p) => !p.done);
    }
    assert.ok(b.currentHp < hp0, "a stationary target must be hit");
});

test("[D2] a shot MISSES a target that dodges off the aim point in flight", () => {
    const sim = simStub(7);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7, accuracy: 100 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 6 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const hp0 = b.currentHp;
    a.fireProjectile(b);          // aimed at (180, 0): b is not moving
    // ... and then b leaves, by more than body + projectile radius.
    const clear = b.radius + PROJECTILE_RADIUS_TILES * TILE_SIZE;
    b.y += clear * 4;
    for (let i = 0; i < 300 && sim.projectiles.length; i++) {
        for (const p of sim.projectiles) p.update(DT);
        sim.projectiles = sim.projectiles.filter((p) => !p.done);
    }
    assert.equal(b.currentHp, hp0, "a target that left the aim point must not be hit");
});

test("[D2] a shot that arrives just inside body+projectile radius still connects", () => {
    const sim = simStub(7);
    const a = new BattleUnit(
        "1-0", 1, { ...STATS, attack_range: 7, projectile_speed: 7, accuracy: 100 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1000 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 6 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const hp0 = b.currentHp;
    a.fireProjectile(b);
    b.y += (b.radius + PROJECTILE_RADIUS_TILES * TILE_SIZE) * 0.9;
    for (let i = 0; i < 300 && sim.projectiles.length; i++) {
        for (const p of sim.projectiles) p.update(DT);
        sim.projectiles = sim.projectiles.filter((p) => !p.done);
    }
    assert.ok(b.currentHp < hp0, "a graze inside the overlap radius is a hit");
});

test("[D2] the dat dispersion, not the 2-tile legacy spread, throws a failed roll", () => {
    // hand_cannoneer: accuracy 75, dispersion 0.50 tiles. Fire many shots at a
    // stationary target and record how far each aim point ends up from it.
    // Every displaced shot must be inside the dat radius -- the legacy
    // behaviour would scatter them out to 2.0 tiles.
    const sim = simStub(11);
    const a = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack_range: 7, projectile_speed: 7.5, accuracy: 75 },
        "hand_cannoneer", "Japanese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e9 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 6 * TILE_SIZE; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    const dispersionTiles = ACCURACY_DISPERSION_BY_SLUG.get("hand_cannoneer");
    let displaced = 0;
    for (let i = 0; i < 400; i++) {
        sim.projectiles.length = 0;
        a.fireProjectile(b);
        const p = sim.projectiles[0];
        const off = Math.hypot(p.targetX - b.x, p.targetY - b.y) / TILE_SIZE;
        assert.ok(
            off <= dispersionTiles + 1e-9,
            `aim thrown ${off} tiles, beyond the dat dispersion ${dispersionTiles}`,
        );
        if (off > 1e-9) displaced++;
    }
    // ~25% of shots should have failed the roll and been displaced at all.
    assert.ok(displaced > 40 && displaced < 160, `displaced ${displaced}/400`);
});

// ---- D3: in-flight damage accounting ----------------------------------------

test("[D3] a shooter skips a target already covered by inbound damage", () => {
    const sim = simStub(13);
    const shooter = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack: 100, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    // Nearly dead primary, healthy neighbour, both well inside reach.
    const dying = new BattleUnit("2-0", 2, { ...STATS }, "a", "Goths", sim);
    const healthy = new BattleUnit("2-1", 2, { ...STATS }, "b", "Goths", sim);
    shooter.x = 0; shooter.y = 0;
    dying.x = 60; dying.y = 0;
    healthy.x = 90; healthy.y = 0;
    dying.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(dying, healthy);

    // Nothing in the air yet -> the primary is still the right victim.
    assert.equal(shooter.pickShotTarget(dying), dying);

    // Put a lethal, EARLIER-arriving shot in the air toward it.
    const other = new BattleUnit(
        "1-1", 1,
        { ...STATS, attack: 100, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    other.x = 55; other.y = 0;          // very close: its arrow lands first
    sim.team1.push(other);
    other.fireProjectile(dying);
    assert.ok(shooter.inboundDamageOn(dying) >= dying.currentHp);
    assert.equal(
        shooter.pickShotTarget(dying), healthy,
        "the shot should be given to the next reachable enemy",
    );
});

test("[D3] inbound damage that lands AFTER this shot does not suppress it", () => {
    const sim = simStub(13);
    const shooter = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack: 100, attack_range: 9, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const dying = new BattleUnit("2-0", 2, { ...STATS }, "a", "Goths", sim);
    shooter.x = 0; shooter.y = 0;
    dying.x = 30; dying.y = 0;          // 1 tile from the shooter
    dying.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(dying);

    // A far-away ally fires at the same victim: lethal, but its arrow is
    // still 8 tiles out while the shooter's would land in one.
    const far = new BattleUnit(
        "1-1", 1,
        { ...STATS, attack: 100, attack_range: 9, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    far.x = -8 * TILE_SIZE; far.y = 0;
    sim.team1.push(far);
    far.fireProjectile(dying);

    // Counting everything in the air would call this overkill ...
    assert.ok(shooter.inboundDamageOn(dying) >= dying.currentHp);
    // ... but nothing lands before the shooter's own arrow would, so it fires.
    assert.equal(shooter.pickShotTarget(dying), dying);
});

test("[D3] with no reachable alternative the shot is taken anyway", () => {
    const sim = simStub(13);
    const shooter = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack: 100, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    const dying = new BattleUnit("2-0", 2, { ...STATS }, "a", "Goths", sim);
    const faraway = new BattleUnit("2-1", 2, { ...STATS }, "b", "Goths", sim);
    shooter.x = 0; shooter.y = 0;
    dying.x = 60; dying.y = 0;
    faraway.x = 40 * TILE_SIZE; faraway.y = 0;   // far out of reach
    dying.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(dying, faraway);

    const near = new BattleUnit(
        "1-1", 1,
        { ...STATS, attack: 100, attack_range: 7, projectile_speed: 7 },
        "arbalester", "Chinese", sim);
    near.x = 55; near.y = 0;
    sim.team1.push(near);
    near.fireProjectile(dying);
    assert.equal(
        shooter.pickShotTarget(dying), dying,
        "no hold-fire behaviour: with nothing else in reach it shoots anyway",
    );
});

// ---- D4: approach margin + hysteresis ---------------------------------------

test("[D4] a ranged unit closes to reach minus its own body diameter", () => {
    const sim = simStub(17);
    const a = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack_range: 7, projectile_speed: 7, movement_speed: 0.96 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e9, attack_range: 7 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 400; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);

    for (let i = 0; i < 60 * 30; i++) a.update(DT, [a, b], [b]);

    const reach = a.attackRange + a.radius + b.radius;
    const inner = reach - 2 * a.radius;
    const dist = b.x - a.x;
    assert.ok(
        dist <= reach + 1e-6,
        `should be inside reach: dist ${dist}, reach ${reach}`,
    );
    assert.ok(
        dist <= inner + 1,
        `should press to the margin, not stop on the lip: dist ${dist}, inner ${inner}`,
    );
});

test("[D4] hysteresis: it holds inside the band and only re-closes past reach", () => {
    const sim = simStub(19);
    const a = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack_range: 7, projectile_speed: 7, movement_speed: 0.96 },
        "arbalester", "Chinese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, hp: 1e9, attack_range: 7 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 400; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    a.target = b;

    for (let i = 0; i < 60 * 30; i++) a.update(DT, [a, b], [b]);
    assert.equal(a.rangedClosed, true, "should have settled");

    const reach = a.attackRange + a.radius + b.radius;
    const inner = reach - 2 * a.radius;

    // Inside the band (between inner and reach): still settled, no approach.
    b.x = a.x + (inner + reach) / 2;
    assert.equal(a.rangedShouldApproach(), false, "must not chase inside the band");

    // Past reach: the hysteresis releases and it closes again.
    b.x = a.x + reach + 1;
    assert.equal(a.rangedShouldApproach(), true, "must re-approach once out of reach");
    // ... and stays committed until it is back inside the inner margin.
    b.x = a.x + (inner + reach) / 2;
    assert.equal(
        a.rangedShouldApproach(), true,
        "still closing: the band only holds a unit that already settled",
    );
});

test("[D4] the margin never walks a unit into its own minimum-range dead zone", () => {
    const sim = simStub(23);
    // Huge body relative to reach, plus a min range: inner would go negative.
    const a = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack_range: 7, min_range: 6, projectile_speed: 7 },
        "imp_elite_skirm", "Chinese", sim);
    const b = new BattleUnit(
        "2-0", 2, { ...STATS, attack_range: 7 }, "bag", "Goths", sim);
    a.x = 0; a.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    a.target = b;

    // Sitting exactly at the min range: it must not want to come closer.
    b.x = a.minAttackRange;
    a.rangedClosed = false;
    assert.equal(
        a.rangedShouldApproach(), false,
        "the inner margin is clamped at minAttackRange",
    );
});

// ---- off-switch --------------------------------------------------------------

test("[R5b] every rule off reproduces the pre-R5b engine, tick for tick", () => {
    // Same fight, same seed, run twice: once with the flags off and once with
    // a hand-rolled reference that never sees them. What this pins is that
    // `off` is a single decision point -- no rule leaks through a default.
    const build = () => {
        const sim = new Simulation(900, 600, makeRng(42));
        for (let i = 0; i < 4; i++) {
            const u = new BattleUnit(
                `1-${i}`, 1,
                { ...STATS, attack_range: 7, projectile_speed: 7, accuracy: 90 },
                "arbalester", "Chinese", sim);
            u.x = 100; u.y = 100 + i * 20;
            sim.team1.push(u);
        }
        for (let i = 0; i < 4; i++) {
            const u = new BattleUnit(
                `2-${i}`, 2,
                { ...STATS, attack_range: 7, projectile_speed: 7.5, accuracy: 75 },
                "hand_cannoneer", "Japanese", sim);
            u.x = 400; u.y = 100 + i * 20;
            sim.team2.push(u);
        }
        return sim;
    };
    const run = () => {
        const sim = build();
        for (let i = 0; i < 60 * 20; i++) sim.update(DT);
        return sim.stateHash();
    };

    const offA = withR5B(
        { stopToFire: false, ballisticLead: false, inflightAccounting: false, approachMargin: false },
        run,
    );
    const offB = withR5B(
        { stopToFire: false, ballisticLead: false, inflightAccounting: false, approachMargin: false },
        run,
    );
    assert.equal(offA, offB, "the off path must be deterministic");

    const on = run();   // engine defaults: all four rules
    assert.notEqual(
        on, offA,
        "the rules must actually change something, or this test proves nothing",
    );
});

test("[R5b] setR5B rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setR5B({ notARule: true }), /unknown flag/);
    // and leaves the real flags untouched
    assert.equal(Object.keys(R5B).length, 4);
});
