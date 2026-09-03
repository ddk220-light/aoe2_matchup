// Round 5d (targeting / approach) -- T1 per-shot re-selection, T2 the
// same-tick claim ledger, T3 the death of the rangedClosed latch, plus the
// master off-switch.
//
// Every test here pins a RULE. The only numbers that appear are geometry
// (a reach, a body radius) and hit points chosen to make a coverage test
// true or false -- there is no tuned constant in R5d to pin.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import {
    TILE_SIZE,
    R5D,
    setR5D,
} from "../../../apps/website/static/js/engine/constants.js";

const DT = 1 / 60;
const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Archer",
};
const ALL_OFF = { perShotSelect: false, sameTickClaims: false, reapproach: false };

function withR5D(overrides, fn) {
    const saved = { ...R5D };
    setR5D(overrides);
    try {
        return fn();
    } finally {
        setR5D(saved);
    }
}

// A real Simulation, so the T2 ledger and the T1 counters exist. Nothing here
// steps it -- the units are driven directly.
function bareSim(seed = 1) {
    return new Simulation(900, 600, makeRng(seed));
}

function archer(sim, id, team, over = {}) {
    return new BattleUnit(
        id, team,
        { ...STATS, attack_range: 7, projectile_speed: 7, ...over },
        "arbalester", "Chinese", sim);
}

function bag(sim, id, team, over = {}) {
    return new BattleUnit(id, team, { ...STATS, ...over }, "bag", "Goths", sim);
}

// ---- T1: per-shot re-selection ----------------------------------------------

test("[T1] the shot goes to the NEAREST reachable enemy, not the standing target", () => {
    const sim = bareSim(3);
    const shooter = archer(sim, "1-0", 1);
    const near = bag(sim, "2-0", 2);
    const far = bag(sim, "2-1", 2);
    shooter.x = 0; shooter.y = 0;
    near.x = 2 * TILE_SIZE; near.y = 0;
    far.x = 6 * TILE_SIZE; far.y = 0;
    sim.team1.push(shooter); sim.team2.push(near, far);
    // The unit's acquisition target is the FAR one -- stale, but alive and in
    // reach, so R5b's redirect would have left it alone.
    shooter.target = far;

    assert.equal(
        shooter.pickShotTarget(far), near,
        "selection is per-shot: the standing target gets no privilege",
    );
    withR5D({ perShotSelect: false }, () => {
        assert.equal(
            shooter.pickShotTarget(far), far,
            "with T1 off the R5b rule keeps the standing target",
        );
    });
});

test("[T1] a lethally covered nearest enemy is skipped for the next one out", () => {
    const sim = bareSim(5);
    const shooter = archer(sim, "1-0", 1, { attack: 100 });
    const dying = bag(sim, "2-0", 2);
    const healthy = bag(sim, "2-1", 2);
    shooter.x = 0; shooter.y = 0;
    dying.x = 2 * TILE_SIZE; dying.y = 0;
    healthy.x = 3 * TILE_SIZE; healthy.y = 0;
    dying.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(dying, healthy);

    // Nothing committed yet: the nearest enemy is the right victim.
    assert.equal(shooter.pickShotTarget(dying), dying);

    // A closer ally puts a lethal, earlier-arriving arrow in the air.
    const ally = archer(sim, "1-1", 1, { attack: 100 });
    ally.x = 1.8 * TILE_SIZE; ally.y = 0;
    sim.team1.push(ally);
    ally.fireProjectile(dying);

    assert.equal(
        shooter.pickShotTarget(dying), healthy,
        "a victim already dead on arrival is not shot again",
    );
});

test("[T1] coverage is per-victim, not a blanket -- an uncovered nearer enemy still wins", () => {
    const sim = bareSim(7);
    const shooter = archer(sim, "1-0", 1, { attack: 100 });
    const nearCovered = bag(sim, "2-0", 2);
    const midOpen = bag(sim, "2-1", 2);
    const farOpen = bag(sim, "2-2", 2);
    shooter.x = 0; shooter.y = 0;
    nearCovered.x = 1 * TILE_SIZE; nearCovered.y = 0;
    midOpen.x = 3 * TILE_SIZE; midOpen.y = 0;
    farOpen.x = 5 * TILE_SIZE; farOpen.y = 0;
    nearCovered.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(nearCovered, midOpen, farOpen);

    const ally = archer(sim, "1-1", 1, { attack: 100 });
    ally.x = 0.5 * TILE_SIZE; ally.y = 0;
    sim.team1.push(ally);
    ally.fireProjectile(nearCovered);

    assert.equal(
        shooter.pickShotTarget(nearCovered), midOpen,
        "the NEXT nearest uncovered enemy, not the farthest and not a rotation",
    );
});

test("[T1] with every reachable enemy covered it shoots the nearest anyway", () => {
    const sim = bareSim(11);
    const shooter = archer(sim, "1-0", 1, { attack: 100 });
    const a = bag(sim, "2-0", 2);
    const b = bag(sim, "2-1", 2);
    const outOfReach = bag(sim, "2-2", 2);
    shooter.x = 0; shooter.y = 0;
    a.x = 3 * TILE_SIZE; a.y = 0;
    b.x = 2 * TILE_SIZE; b.y = 0;
    outOfReach.x = 40 * TILE_SIZE; outOfReach.y = 0;
    a.currentHp = 5; b.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(a, b, outOfReach);

    const ally = archer(sim, "1-1", 1, { attack: 100 });
    ally.x = 0.5 * TILE_SIZE; ally.y = 0;
    sim.team1.push(ally);
    ally.fireProjectile(a);
    ally.fireProjectile(b);

    const before = sim.combatStats[1].allCovered;
    assert.equal(
        shooter.pickShotTarget(a), b,
        "no hold-fire: the fallback is the NEAREST reachable enemy",
    );
    assert.equal(
        sim.combatStats[1].allCovered, before + 1,
        "the all-covered fallback is counted so its rate can be reported",
    );
});

// ---- T2: same-tick claim ledger ---------------------------------------------

test("[T2] a second shooter in the same tick sees the first one's commitment", () => {
    // The pair the forensics attribute 27-43% of residual HC waste to: a FAR
    // shooter commits first, a NEAR shooter fires an instant later in the same
    // tick. The near shooter's arrow lands first, so the arrival-order test
    // discards the far one -- correctly, for a shot fired in a previous tick,
    // and wrongly here, because neither could have seen the other.
    const sim = bareSim(13);
    const far = archer(sim, "1-0", 1, { attack: 100, attack_range: 9 });
    const near = archer(sim, "1-1", 1, { attack: 100, attack_range: 9 });
    const dying = bag(sim, "2-0", 2);
    const other = bag(sim, "2-1", 2);
    far.x = 0; far.y = 0;
    near.x = 7 * TILE_SIZE; near.y = 0;
    dying.x = 8 * TILE_SIZE; dying.y = 0;
    other.x = 9 * TILE_SIZE; other.y = 0;
    dying.currentHp = 5;
    sim.team1.push(far, near); sim.team2.push(dying, other);

    far.fireProjectile(dying);          // committed, but 8 tiles of flight away

    // The arrival-order test alone still calls the victim open ...
    withR5D({ sameTickClaims: false }, () => {
        assert.ok(
            near.inboundDamageOn(dying, near.flightTimeTo(dying)) < dying.currentHp,
            "precondition: the far arrow lands after the near one would",
        );
        assert.equal(near.pickShotTarget(dying), dying, "... so both shoot it");
    });
    // ... and the ledger is what makes the second shooter divert.
    assert.equal(
        near.pickShotTarget(dying), other,
        "the same-tick claim covers the victim for every later shooter",
    );
});

test("[T2] a claimed shot is counted ONCE, not twice", () => {
    // The claimed projectile is in sim.projectiles AND in the ledger. If
    // inboundDamageOn did not drop it, its damage would be double-counted and
    // a half-lethal volley would read as lethal.
    const sim = bareSim(17);
    const ally = archer(sim, "1-0", 1, { attack: 100 });
    const shooter = archer(sim, "1-1", 1, { attack: 100 });
    const victim = bag(sim, "2-0", 2, { hp: 1000 });
    ally.x = 0; ally.y = 0;
    shooter.x = 1 * TILE_SIZE; shooter.y = 0;
    victim.x = 3 * TILE_SIZE; victim.y = 0;
    sim.team1.push(ally, shooter); sim.team2.push(victim);

    ally.fireProjectile(victim);
    const dmg = sim.projectiles[0].plannedDamage;
    assert.ok(dmg > 0, "precondition: the shot plans real damage");
    assert.equal(
        shooter.coveredDamageOn(victim), dmg,
        "one arrow in the air is one arrow of coverage",
    );
});

test("[T2] the ledger does not survive a tick", () => {
    const sim = bareSim(19);
    const ally = archer(sim, "1-0", 1);
    const victim = bag(sim, "2-0", 2, { hp: 1000 });
    ally.x = 0; ally.y = 0;
    victim.x = 3 * TILE_SIZE; victim.y = 0;
    sim.team1.push(ally); sim.team2.push(victim);

    ally.fireProjectile(victim);
    assert.equal(sim.tickClaims.size, 1);
    sim.update(DT);
    assert.equal(sim.tickClaims.size, 0, "claims are cleared at the top of update()");
    assert.equal(sim.tickClaimShots.size, 0);
});

// ---- T3: the latch is gone ---------------------------------------------------

test("[T3] a settled unit re-approaches a target that drifts out to the lip", () => withR5D({ reapproach: true }, () => {
    // T3 ships OFF (refuted -- the margin binds, not the latch's memory; see
    // constants.js), so the mechanism is pinned here under an explicit
    // override.
    const sim = bareSim(23);
    const a = archer(sim, "1-0", 1, { movement_speed: 0.96 });
    const b = bag(sim, "2-0", 2, { hp: 1e9, attack_range: 7 });
    a.x = 0; a.y = 0; b.x = 400; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    a.target = b;

    for (let i = 0; i < 60 * 30; i++) a.update(DT, [a, b], [b]);

    const reach = a.attackRange + a.radius + b.radius;
    const inner = reach - 2 * a.radius;
    assert.ok(
        a.distanceTo(b) <= inner + 1,
        "precondition: it closed to the margin",
    );

    // The target drifts out to the middle of the old hysteresis band -- still
    // inside reach, so the latch would have held the unit where it stood.
    b.x = a.x + (inner + reach) / 2;
    assert.equal(
        a.rangedShouldApproach(), true,
        "outside the margin is outside the margin, settled or not",
    );
    withR5D({ reapproach: false }, () => {
        // The latch is state, so state it: this is what the old rule had
        // recorded by the time the unit settled, and it is why the same
        // geometry answered the other way.
        a.rangedClosed = true;
        assert.equal(
            a.rangedShouldApproach(), false,
            "the latch this replaces held it there -- that is the bug",
        );
    });

    // And it holds once it is back inside the margin.
    b.x = a.x + inner - 1;
    assert.equal(a.rangedShouldApproach(), false, "inside the margin it holds");
}));

test("[T3] approach is a pure function of the current distance -- no memory", () => withR5D({ reapproach: true }, () => {
    const sim = bareSim(29);
    const a = archer(sim, "1-0", 1);
    const b = bag(sim, "2-0", 2, { hp: 1e9 });
    a.x = 0; a.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    a.target = b;
    const reach = a.attackRange + a.radius + b.radius;
    const inner = reach - 2 * a.radius;

    // Walk the target in and out repeatedly: the answer must depend only on
    // where it is now, in both directions, every time.
    for (let i = 0; i < 3; i++) {
        b.x = a.x + inner - 1;
        assert.equal(a.rangedShouldApproach(), false);
        b.x = a.x + inner + 1;
        assert.equal(a.rangedShouldApproach(), true);
        b.x = a.x + reach + 50;
        assert.equal(a.rangedShouldApproach(), true);
    }
}));

test("[T3] the margin is still clamped out of the minimum-range dead zone", () => {
    const sim = bareSim(31);
    const a = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack_range: 7, min_range: 6, projectile_speed: 7 },
        "imp_elite_skirm", "Chinese", sim);
    const b = bag(sim, "2-0", 2, { attack_range: 7 });
    a.x = 0; a.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    a.target = b;

    b.x = a.minAttackRange;
    assert.equal(
        a.rangedShouldApproach(), false,
        "T3 reuses R5b's clamp -- it must not walk into its own dead zone",
    );
});

// ---- off-switch ---------------------------------------------------------------

// Two fight fixtures, because the three rules answer different questions and a
// single toy fight does not ask all three. Both use a two-shot HP pool so a
// single inbound arrow can be lethal coverage (otherwise T1 and T2 have
// nothing to decline), and neither uses rng for its layout.
const DUEL = {
    ...STATS, hp: 40, attack: 20, pierce_armor: 0,
    attack_range: 7, projectile_speed: 7, accuracy: 100,
};
const JITTER = [0, 13, -7, 21, -18, 5, -11, 17, -3, 9, 24, -22];

// Ragged lines: bodies shuffle, so a unit's standing target stops being its
// nearest reachable enemy -- which is the only thing T1 changes. T3 shows up
// here too (the lines keep closing).
function spreadFight(seed, n = 8) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...DUEL }, "arbalester", "Chinese", sim);
        u.x = 180 + JITTER[i % 12];
        u.y = 120 + i * 30 + JITTER[(i + 3) % 12];
        sim.team1.push(u);
    }
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...DUEL }, "arbalester", "Goths", sim);
        u.x = 430 + JITTER[(i + 5) % 12];
        u.y = 130 + i * 30 + JITTER[(i + 7) % 12];
        sim.team2.push(u);
    }
    return sim;
}

// Tight, aligned columns: everyone's cooldown comes up together and several
// shooters commit inside the same tick, which is the pair T2 is about.
function volleyFight(seed, n = 6) {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...DUEL }, "arbalester", "Chinese", sim);
        u.x = 200 + (i % 2) * 25; u.y = 200 + i * 24;
        sim.team1.push(u);
    }
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...DUEL }, "arbalester", "Goths", sim);
        u.x = 420 - (i % 2) * 25; u.y = 205 + i * 24;
        sim.team2.push(u);
    }
    return sim;
}

function meleeFight(seed) {
    const sim = new Simulation(900, 600, makeRng(seed));
    const melee = {
        hp: 70, attack: 12, attack_range: 0, attack_speed: 1.8,
        attack_delay: 0.4, movement_speed: 0.9, melee_armor: 1,
        pierce_armor: 1, outline_size: 0.2, accuracy: 100,
        unit_name: "Test Champion",
    };
    for (let i = 0; i < 5; i++) {
        const u = new BattleUnit(`1-${i}`, 1, { ...melee }, "champion", "Franks", sim);
        u.x = 150; u.y = 100 + i * 22;
        sim.team1.push(u);
    }
    for (let i = 0; i < 5; i++) {
        const u = new BattleUnit(`2-${i}`, 2, { ...melee }, "champion", "Goths", sim);
        u.x = 350; u.y = 100 + i * 22;
        sim.team2.push(u);
    }
    return sim;
}

function runHash(build, seed, seconds = 20) {
    const sim = build(seed);
    for (let i = 0; i < 60 * seconds; i++) sim.update(DT);
    return sim.stateHash();
}

test("[R5d] every rule off is deterministic and differs from the shipped engine", () => {
    const offA = withR5D(ALL_OFF, () => runHash(spreadFight, 42));
    const offB = withR5D(ALL_OFF, () => runHash(spreadFight, 42));
    assert.equal(offA, offB, "the off path must be deterministic");

    const on = runHash(spreadFight, 42);
    assert.notEqual(
        on, offA,
        "the rules must actually change something, or this test proves nothing",
    );
});

test("[R5d] each rule is independently switchable and independently load-bearing", () => {
    // A rule that cannot move ANY fight on its own is either dead code or is
    // only reachable through another rule -- either way the off-switch would
    // be untestable. Each is asked on both fixtures and has to move one.
    for (const rule of Object.keys(R5D)) {
        const moved = [spreadFight, volleyFight].some((build) => {
            const off = withR5D(ALL_OFF, () => runHash(build, 8, 40));
            const only = withR5D({ ...ALL_OFF, [rule]: true }, () => runHash(build, 8, 40));
            return only !== off;
        });
        assert.ok(moved, `${rule} alone must move at least one fixture`);
    }
});

test("[R5d] melee-vs-melee is untouched by all three rules", () => {
    // R5d is a RANGED round. T1 and T2 live behind isRanged() / fireProjectile
    // and T3 behind the ranged branch of update(), so a melee fight must be
    // bit-identical with the flags on and off.
    const on = runHash(meleeFight, 77, 40);
    const off = withR5D(ALL_OFF, () => runHash(meleeFight, 77, 40));
    assert.equal(on, off, "a melee fight must not move by so much as a float");
});

test("[R5d] setR5D rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setR5D({ notARule: true }), /unknown flag/);
    assert.equal(Object.keys(R5D).length, 3);
});
