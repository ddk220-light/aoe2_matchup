// Round 5f (ranged selection + silence advance) -- A1 advance-on-silence,
// A2 persist -> nearest-uncovered selection, A3 plannedDamage correctness,
// plus the master off-switch.
//
// Every test pins a RULE. The only numbers here are geometry (a reach, a body
// radius), hit points chosen to make a coverage test true or false, and the
// ONE constant R5f carries -- SILENCE_ADVANCE_CYCLES, which is a measured tape
// breakpoint (see constants.js) and is asserted against, never tuned.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { Simulation } from "../../../apps/website/static/js/engine/sim.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import {
    TILE_SIZE,
    R5F,
    setR5F,
    R5D1,
    setR5D1,
    SILENCE_ADVANCE_CYCLES,
} from "../../../apps/website/static/js/engine/constants.js";

const DT = 1 / 60;
const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Archer",
};
const ALL_OFF = {
    silenceAdvance: false, silenceClockOnLaunch: false,
    persistVictim: false, failedRollPlannedDamage: false,
};
// silenceClockOnLaunch is a MODIFIER of A1, not a fourth rule: it selects
// which of two clocks A1 reads and does nothing at all while A1 is off. It is
// therefore excluded from the "each rule is load-bearing alone" sweep and
// pinned by its own two tests instead.
const RULES = Object.keys(ALL_OFF).filter((k) => k !== "silenceClockOnLaunch");

function withR5F(overrides, fn) {
    const saved = { ...R5F };
    setR5F(overrides);
    try {
        return fn();
    } finally {
        setR5F(saved);
    }
}

function withR5D1(overrides, fn) {
    const saved = { ...R5D1 };
    setR5D1(overrides);
    try {
        return fn();
    } finally {
        setR5D1(saved);
    }
}

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

// Fly every projectile currently in the air to its arrival, without stepping
// the units (so nothing re-fires and the test controls the clock).
function flyProjectiles(sim, seconds = 5) {
    for (let i = 0; i < 60 * seconds; i++) {
        for (const p of sim.projectiles) p.update(DT);
        if (sim.projectiles.every((p) => p.done)) return;
    }
    throw new Error("projectiles never arrived");
}

// ---- A1: the silence clock ---------------------------------------------------

test("[A1] a LANDED hit resets the clock; a shot that grounds does not", () => {
    const sim = bareSim(3);
    const shooter = archer(sim, "1-0", 1);
    const victim = bag(sim, "2-0", 2, { hp: 1000 });
    shooter.x = 0; shooter.y = 0;
    victim.x = 2 * TILE_SIZE; victim.y = 0;
    sim.team1.push(shooter); sim.team2.push(victim);

    assert.equal(shooter.hasFiredRangedShot, false, "nothing fired yet");
    assert.equal(shooter.lastLandedHitTime, 0);

    sim.battleTime = 11.0;
    shooter.fireProjectile(victim);
    assert.equal(
        shooter.hasFiredRangedShot, true,
        "firing leaves the tape's never-fired bin, whatever the shot does",
    );
    assert.equal(
        shooter.lastLandedHitTime, 0,
        "the clock is stamped on ARRIVAL, not on launch",
    );
    sim.battleTime = 11.4;
    flyProjectiles(sim);
    assert.equal(
        shooter.lastLandedHitTime, 11.4,
        "a landed hit stamps the clock with the arrival instant",
    );

    // Now a shot that cannot land on anything: the roll fails and the body is
    // gone by the time it arrives, so nothing takes damage.
    sim.projectiles.length = 0;
    const ghost = bag(sim, "2-1", 2, { hp: 1000 });
    ghost.x = 3 * TILE_SIZE; ghost.y = 0;
    sim.team2.push(ghost);
    sim.battleTime = 20.0;
    shooter.fireProjectile(ghost);
    ghost.currentHp = 0;
    ghost.state = "dead";
    sim.battleTime = 20.5;
    flyProjectiles(sim);
    assert.equal(
        shooter.lastLandedHitTime, 11.4,
        "a shot that delivers nothing leaves the unit silent",
    );
});

test("[A1] the threshold is exactly SILENCE_ADVANCE_CYCLES reload cycles", () => {
    const sim = bareSim(5);
    const shooter = archer(sim, "1-0", 1);          // attack_speed 0.5 -> reload 2.0
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    shooter.x = 0; shooter.y = 0;
    foe.x = 2 * TILE_SIZE; foe.y = 0;
    sim.team1.push(shooter); sim.team2.push(foe);
    shooter.target = foe;
    shooter.hasFiredRangedShot = true;
    shooter.lastLandedHitTime = 0;

    const window = SILENCE_ADVANCE_CYCLES * shooter.reloadTime;
    sim.battleTime = window;
    assert.equal(
        shooter.silentBeyondCycles(), false,
        "AT the breakpoint is not PAST it -- the bin edge is strict",
    );
    sim.battleTime = window + 1e-6;
    assert.equal(shooter.silentBeyondCycles(), true, "past it, the unit is silent");

    // And it is the unit's OWN reload, not a shared duration.
    const fast = archer(sim, "1-1", 1, { attack_speed: 2.0 });   // reload 0.5
    fast.target = foe;
    fast.hasFiredRangedShot = true;
    fast.lastLandedHitTime = sim.battleTime - 1.5;
    assert.equal(
        fast.silentBeyondCycles(), true,
        "1.5 s of silence is 3 cycles for a 0.5 s reload",
    );
    const slow = archer(sim, "1-2", 1, { attack_speed: 0.25 });  // reload 4.0
    slow.target = foe;
    slow.hasFiredRangedShot = true;
    slow.lastLandedHitTime = sim.battleTime - 1.5;
    assert.equal(
        slow.silentBeyondCycles(), false,
        "... and less than half a cycle for a 4.0 s one",
    );
});

test("[A1] a unit that has never fired is exempt, and a dead target disarms it", () => {
    const sim = bareSim(7);
    const shooter = archer(sim, "1-0", 1);
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    shooter.x = 0; shooter.y = 0;
    foe.x = 2 * TILE_SIZE; foe.y = 0;
    sim.team1.push(shooter); sim.team2.push(foe);
    shooter.target = foe;
    sim.battleTime = 60;

    assert.equal(
        shooter.silentBeyondCycles(), false,
        "the opening approach is the tape's own separate bin -- A1 stays out",
    );
    shooter.hasFiredRangedShot = true;
    assert.equal(shooter.silentBeyondCycles(), true);

    shooter.target = null;
    assert.equal(shooter.silentBeyondCycles(), false, "nothing to advance toward");
    shooter.target = foe;
    foe.state = "dead";
    assert.equal(shooter.silentBeyondCycles(), false, "a corpse is not a live target");
});

test("[A1] a MELEE unit is never silence-advancing", () => {
    const sim = bareSim(11);
    const champ = bag(sim, "1-0", 1, { attack_range: 0 });
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    champ.x = 0; champ.y = 0;
    foe.x = 1 * TILE_SIZE; foe.y = 0;
    sim.team1.push(champ); sim.team2.push(foe);
    champ.target = foe;
    champ.hasFiredRangedShot = true;      // impossible in practice; forced here
    sim.battleTime = 600;
    assert.equal(champ.isRanged(), false, "precondition");
    assert.equal(
        champ.silentBeyondCycles(), false,
        "R5f is a ranged round -- the predicate refuses melee outright",
    );
});

test("[A1] a silent unit approaches from inside the R5b margin, and holds when it is not", () => {
    const sim = bareSim(13);
    const shooter = archer(sim, "1-0", 1);
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    sim.team1.push(shooter); sim.team2.push(foe);
    shooter.x = 0; shooter.y = 0;
    shooter.target = foe;

    const reach = shooter.attackRange + shooter.radius + foe.radius;
    const inner = reach - 2 * shooter.radius;
    foe.x = inner - 1; foe.y = 0;           // settled well inside the margin
    assert.equal(
        shooter.rangedShouldApproach(), false,
        "precondition: the margin holds it here",
    );
    assert.equal(shooter.rangedClosed, true, "and the latch says so");

    shooter.hasFiredRangedShot = true;
    shooter.lastLandedHitTime = 0;
    sim.battleTime = 3 * shooter.reloadTime;
    assert.equal(
        shooter.rangedShouldApproach(), true,
        "silence overrides the hold -- the unit closes",
    );
    assert.equal(
        shooter.rangedClosed, true,
        "the latch state machine still ran: A1 overrides the ANSWER, not the state",
    );
    withR5F({ silenceAdvance: false }, () => {
        assert.equal(
            shooter.rangedShouldApproach(), false,
            "with A1 off the same geometry and the same clock hold it there",
        );
    });

    // Landing a hit re-arms the hold immediately.
    shooter.lastLandedHitTime = sim.battleTime;
    assert.equal(
        shooter.rangedShouldApproach(), false,
        "the clock reset ends the advance",
    );
});

test("[A1] the minimum-range dead zone still binds", () => {
    const sim = bareSim(17);
    const skirm = new BattleUnit(
        "1-0", 1,
        { ...STATS, attack_range: 7, min_attack_range: 6, projectile_speed: 7 },
        "imp_elite_skirm", "Chinese", sim);
    const foe = bag(sim, "2-0", 2, { hp: 1000, attack_range: 7 });
    sim.team1.push(skirm); sim.team2.push(foe);
    skirm.x = 0; skirm.y = 0;
    skirm.target = foe;
    assert.ok(skirm.minAttackRange > 0, "precondition: a real dead zone");
    skirm.hasFiredRangedShot = true;
    skirm.lastLandedHitTime = 0;
    sim.battleTime = 600;

    foe.x = skirm.minAttackRange - 1; foe.y = 0;
    assert.equal(
        skirm.rangedShouldApproach(), false,
        "A1 overrides the margin HOLD, never the physical dead zone",
    );
});

// ---- A2: persist -> nearest-uncovered ----------------------------------------

test("[A2] the previous victim is kept while alive, in reach and uncovered", () => {
    const sim = bareSim(19);
    const shooter = archer(sim, "1-0", 1);
    const near = bag(sim, "2-0", 2);
    const held = bag(sim, "2-1", 2);
    shooter.x = 0; shooter.y = 0;
    near.x = 1 * TILE_SIZE; near.y = 0;
    held.x = 5 * TILE_SIZE; held.y = 0;
    sim.team1.push(shooter); sim.team2.push(near, held);
    shooter.target = near;
    shooter.lastShotVictim = held;

    assert.equal(
        shooter.pickShotTarget(near), held,
        "persistence beats the nearest body -- that is the whole rule",
    );
    withR5F({ persistVictim: false }, () => {
        assert.equal(
            shooter.pickShotTarget(near), near,
            "with A2 off T1's every-shot nearest re-pick is back, unchanged",
        );
    });
});

test("[A2] each of the three failure modes re-picks the nearest uncovered enemy", () => {
    const build = () => {
        const sim = bareSim(23);
        const shooter = archer(sim, "1-0", 1, { attack: 100 });
        const near = bag(sim, "2-0", 2);
        const held = bag(sim, "2-1", 2);
        shooter.x = 0; shooter.y = 0;
        near.x = 1 * TILE_SIZE; near.y = 0;
        held.x = 5 * TILE_SIZE; held.y = 0;
        sim.team1.push(shooter); sim.team2.push(near, held);
        shooter.target = near;
        shooter.lastShotVictim = held;
        return { sim, shooter, near, held };
    };

    // 1. the victim died
    {
        const { shooter, near, held } = build();
        held.state = "dead";
        assert.equal(shooter.pickShotTarget(near), near, "dead victim -> re-pick");
    }
    // 2. the victim left reach
    {
        const { shooter, near, held } = build();
        held.x = 40 * TILE_SIZE;
        assert.ok(!shooter.canReach(held), "precondition");
        assert.equal(shooter.pickShotTarget(near), near, "out of reach -> re-pick");
    }
    // 3. the victim is lethally covered
    {
        const { sim, shooter, near, held } = build();
        held.currentHp = 5;
        const ally = archer(sim, "1-1", 1, { attack: 100 });
        ally.x = 4.5 * TILE_SIZE; ally.y = 0;
        sim.team1.push(ally);
        ally.fireProjectile(held);
        assert.ok(
            shooter.coveredDamageOn(held) >= held.currentHp, "precondition",
        );
        assert.equal(
            shooter.pickShotTarget(near), near,
            "already dead on arrival -> re-pick, exactly as T1 would",
        );
    }
});

test("[A2] the re-pick fallback is T1's, all-covered branch included", () => {
    const sim = bareSim(29);
    const shooter = archer(sim, "1-0", 1, { attack: 100 });
    const a = bag(sim, "2-0", 2);
    const b = bag(sim, "2-1", 2);
    shooter.x = 0; shooter.y = 0;
    a.x = 3 * TILE_SIZE; a.y = 0;
    b.x = 2 * TILE_SIZE; b.y = 0;
    a.currentHp = 5; b.currentHp = 5;
    sim.team1.push(shooter); sim.team2.push(a, b);
    shooter.lastShotVictim = null;          // nothing to persist on

    const ally = archer(sim, "1-1", 1, { attack: 100 });
    ally.x = 0.5 * TILE_SIZE; ally.y = 0;
    sim.team1.push(ally);
    ally.fireProjectile(a);
    ally.fireProjectile(b);

    const before = sim.combatStats[1].allCovered;
    assert.equal(shooter.pickShotTarget(a), b, "nearest reachable, no hold-fire");
    assert.equal(
        sim.combatStats[1].allCovered, before + 1,
        "and the all-covered fallback is still counted",
    );
});

test("[A2] the volley's victim is remembered once, never the scatter target", () => {
    const sim = bareSim(31);
    const shooter = archer(sim, "1-0", 1);
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    const other = bag(sim, "2-1", 2, { hp: 1000 });
    shooter.x = 0; shooter.y = 0;
    foe.x = 2 * TILE_SIZE; foe.y = 0;
    other.x = 3 * TILE_SIZE; other.y = 0;
    sim.team1.push(shooter); sim.team2.push(foe, other);
    shooter.target = foe;
    shooter.extraProjectiles = 2;
    shooter.extraProjScatter = true;

    assert.equal(shooter.lastShotVictim, null);
    shooter.performAttack();
    assert.equal(
        shooter.lastShotVictim, foe,
        "the PRIMARY is the persisted victim; the extras scatter and are not",
    );
});

// ---- A3: what a failed-roll projectile advertises ---------------------------

function fireOne(sim, shooter, target) {
    sim.projectiles.length = 0;
    shooter.fireProjectile(target);
    return sim.projectiles[sim.projectiles.length - 1];
}

test("[A3] with P1 OFF a failed roll still advertises FULL -- the rule is a no-op there", () =>
    withR5D1({ reducedDamageHits: false }, () => {
        const sim = bareSim(37);
        const shooter = archer(sim, "1-0", 1);
        const foe = bag(sim, "2-0", 2, { hp: 1000 });
        shooter.x = 0; shooter.y = 0;
        foe.x = 2 * TILE_SIZE; foe.y = 0;
        sim.team1.push(shooter); sim.team2.push(foe);
        shooter.accuracy = 0;               // every roll fails, no rng needed

        const full = shooter.getDamageAgainst(foe);
        const p = fireOne(sim, shooter, foe);
        assert.equal(
            p.plannedDamage, full,
            "a displaced shot is still resolved on arrival and still pays full",
        );
        assert.equal(sim.tickClaims.get(foe), full, "one ledger, one number");
    }));

test("[A3] with P1 ON a failed roll advertises HALF, a made roll still FULL", () =>
    withR5D1({ reducedDamageHits: true }, () => {
        const sim = bareSim(41);
        const shooter = archer(sim, "1-0", 1);
        const foe = bag(sim, "2-0", 2, { hp: 1000 });
        shooter.x = 0; shooter.y = 0;
        foe.x = 2 * TILE_SIZE; foe.y = 0;
        sim.team1.push(shooter); sim.team2.push(foe);
        const full = shooter.getDamageAgainst(foe);

        shooter.accuracy = 0;
        sim.tickClaims.clear();
        let p = fireOne(sim, shooter, foe);
        assert.equal(p.plannedDamage, full * 0.5, "half of the post-armor damage");
        assert.equal(sim.tickClaims.get(foe), full * 0.5, "ledger agrees");

        withR5F({ failedRollPlannedDamage: false }, () => {
            sim.tickClaims.clear();
            p = fireOne(sim, shooter, foe);
            assert.equal(
                p.plannedDamage, full,
                "with A3 off the over-count is back -- that is the bug it fixes",
            );
        });

        shooter.accuracy = 1.0;
        sim.tickClaims.clear();
        p = fireOne(sim, shooter, foe);
        assert.equal(p.plannedDamage, full, "a shot that will hit advertises full");
    }));

test("[A3] an accuracy-100 unit cannot be moved by this rule at all", () => {
    // R5e M6: fail% is 0.0 on all nine accuracy-100 sides, so every column
    // there is byte-identical across the weightings.
    const sim = bareSim(43);
    const shooter = archer(sim, "1-0", 1);          // accuracy 100
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    shooter.x = 0; shooter.y = 0;
    foe.x = 2 * TILE_SIZE; foe.y = 0;
    sim.team1.push(shooter); sim.team2.push(foe);
    const full = shooter.getDamageAgainst(foe);
    for (const p1 of [false, true]) {
        withR5D1({ reducedDamageHits: p1 }, () => {
            assert.equal(fireOne(sim, shooter, foe).plannedDamage, full);
        });
    }
});

// ---- off-switch ---------------------------------------------------------------

const DUEL = {
    ...STATS, hp: 40, attack: 20, pierce_armor: 0,
    attack_range: 7, projectile_speed: 7, accuracy: 100,
};
const JITTER = [0, 13, -7, 21, -18, 5, -11, 17, -3, 9, 24, -22];

// Ragged lines: a unit's standing target stops being its nearest reachable
// enemy, which is what A2 changes, and units lose and regain victims, which is
// what A1 needs.
function spreadFight(seed, n = 8, over = {}, slug = "arbalester") {
    const sim = new Simulation(900, 600, makeRng(seed));
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(
            `1-${i}`, 1, { ...DUEL, ...over }, slug, "Chinese", sim);
        u.x = 180 + JITTER[i % 12];
        u.y = 120 + i * 30 + JITTER[(i + 3) % 12];
        sim.team1.push(u);
    }
    for (let i = 0; i < n; i++) {
        const u = new BattleUnit(
            `2-${i}`, 2, { ...DUEL, ...over }, slug, "Goths", sim);
        u.x = 430 + JITTER[(i + 5) % 12];
        u.y = 130 + i * 30 + JITTER[(i + 7) % 12];
        sim.team2.push(u);
    }
    return sim;
}

// The same fight fought by units that MISS: A3 needs a failed roll to exist,
// and A1's clock notices shots that deliver nothing.
// hp 20 against a 20-damage shot is the point of the fixture: with P1 on, a
// failed roll advertises 10 and a full one 20, so the advertised value is
// exactly what decides whether a victim reads as lethally covered.
const missFight = (seed) => spreadFight(seed, 8, { accuracy: 50, hp: 20 });

// Units that WHIFF: an unknown slug has no dat accuracy_dispersion, so a failed
// roll keeps the legacy 2-tile scatter and mostly grounds. That is the only
// state in which the two A1 clocks disagree -- the unit is firing on cadence
// (launch clock: not silent) and landing nothing (landed clock: silent).
const whiffFight = (seed) =>
    spreadFight(seed, 8, { accuracy: 15, hp: 20 }, "whiffer");

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

test("[R5f] every rule off is deterministic and differs from the shipped engine", () => {
    const offA = withR5F(ALL_OFF, () => runHash(spreadFight, 42));
    const offB = withR5F(ALL_OFF, () => runHash(spreadFight, 42));
    assert.equal(offA, offB, "the off path must be deterministic");
    const on = runHash(spreadFight, 42);
    assert.notEqual(
        on, offA,
        "the rules must actually change something, or this test proves nothing",
    );
});

test("[R5f] each rule is independently switchable and independently load-bearing", () => {
    // A3 is a no-op with R5D1.reducedDamageHits off BY CONSTRUCTION (see
    // constants.js) -- a failed roll under P1-off really does still pay full.
    // So it is asked under P1 ON, which is the only config in which it has
    // anything to say. That is a documented property of the rule, asserted
    // below, not an accommodation.
    for (const rule of RULES) {
        const p1 = rule === "failedRollPlannedDamage";
        const moved = [spreadFight, missFight].some((build) => withR5D1(
            { reducedDamageHits: p1 },
            () => {
                const off = withR5F(ALL_OFF, () => runHash(build, 8, 40));
                const only = withR5F({ ...ALL_OFF, [rule]: true },
                    () => runHash(build, 8, 40));
                return only !== off;
            },
        ));
        assert.ok(moved, `${rule} alone must move at least one fixture`);
    }
});

test("[R5f] A3 is provably inert while P1 is off", () => withR5D1(
    { reducedDamageHits: false },
    () => {
        for (const build of [spreadFight, missFight]) {
            const off = withR5F(ALL_OFF, () => runHash(build, 8, 40));
            const only = withR5F(
                { ...ALL_OFF, failedRollPlannedDamage: true },
                () => runHash(build, 8, 40));
            assert.equal(
                only, off,
                "the shipped config cannot see A3 -- report it as a no-op, not a win",
            );
        }
    },
));

test("[A1b] the launch clock is inert while A1 is off, and live while it is on", () => {
    // Inert: with silenceAdvance off, flipping the clock cannot move a fight.
    for (const build of [spreadFight, missFight, whiffFight]) {
        const a = withR5F({ ...ALL_OFF, silenceClockOnLaunch: false },
            () => runHash(build, 8, 40));
        const b = withR5F({ ...ALL_OFF, silenceClockOnLaunch: true },
            () => runHash(build, 8, 40));
        assert.equal(a, b, "a clock nobody reads cannot change anything");
    }
    // Live: with A1 on, the two clocks are genuinely different rules.
    const landed = withR5F(
        { ...ALL_OFF, silenceAdvance: true, silenceClockOnLaunch: false },
        () => runHash(whiffFight, 8, 40));
    const launched = withR5F(
        { ...ALL_OFF, silenceAdvance: true, silenceClockOnLaunch: true },
        () => runHash(whiffFight, 8, 40));
    assert.notEqual(
        landed, launched,
        "a unit that fires and misses is silent under one clock and not the other",
    );
});

test("[A1b] the launch clock reads the launch instant, not the arrival", () => {
    const sim = bareSim(47);
    const shooter = archer(sim, "1-0", 1);
    const foe = bag(sim, "2-0", 2, { hp: 1000 });
    shooter.x = 0; shooter.y = 0;
    foe.x = 2 * TILE_SIZE; foe.y = 0;
    sim.team1.push(shooter); sim.team2.push(foe);
    shooter.target = foe;

    sim.battleTime = 30.0;
    shooter.fireProjectile(foe);
    assert.equal(shooter.lastLaunchTime, 30.0);
    assert.equal(shooter.lastLandedHitTime, 0, "nothing has arrived yet");

    // 2.5 s later: 1.25 cycles since the launch, but 30+ s since anything
    // landed. The two clocks disagree, and each flag reads its own.
    sim.battleTime = 32.5;
    withR5F({ silenceAdvance: true, silenceClockOnLaunch: true }, () => {
        assert.equal(shooter.silentBeyondCycles(), false, "it just fired");
    });
    withR5F({ silenceAdvance: true, silenceClockOnLaunch: false }, () => {
        assert.equal(shooter.silentBeyondCycles(), true, "but it has landed nothing");
    });
});

test("[R5f] melee-vs-melee is untouched by all four flags", () => {
    // A1 lives behind isRanged() and the ranged branch of update(); A2 behind
    // pickShotTarget, which only ranged units call; A3 inside fireProjectile.
    // A melee fight must be bit-identical with the flags on and off.
    const on = runHash(meleeFight, 77, 40);
    const off = withR5F(ALL_OFF, () => runHash(meleeFight, 77, 40));
    assert.equal(on, off, "a melee fight must not move by so much as a float");
});

test("[R5f] setR5F rejects an unknown flag rather than silently ignoring it", () => {
    assert.throws(() => setR5F({ notARule: true }), /unknown flag/);
    assert.equal(Object.keys(R5F).length, 4);
});
