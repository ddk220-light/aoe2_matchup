import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Chinese Elite Fire Lancer's real combat dict (data/calibration/combat_dicts.json):
// charge_projectile_count=3, charge_attack_range=4 (tiles -> 120px),
// charge_recharge_time=30, charge_ignores_armor=1,
// charge_projectile_attacks={"3":3,"17":2,...} -> 5 armour-ignoring damage/hit.
// attack_range 0 -> melee unit, so it takes the melee branch of update().
const LANCER_STATS = {
    hp: 100, attack: 14, attack_range: 0, attack_speed: 0.5, attack_delay: 0.167,
    movement_speed: 1.2, melee_armor: 5, pierce_armor: 5, outline_size: 0.2,
    accuracy: 100, unit_name: "Elite Fire Lancer",
    charge_projectile_count: 3,
    charge_projectile_speed: 7.5,
    charge_attack_range: 4,
    charge_ignores_armor: 1,
    charge_recharge_time: 30,
    charge_projectile_attacks_json: JSON.stringify({ 3: 3, 17: 2 }),
};

const VICTIM_STATS = {
    hp: 60, attack: 9, attack_range: 0, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 100, unit_name: "Test Victim",
};

const DT = 1 / 60;

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

// Drop every projectile currently in flight onto its victim, then clear the
// queue -- these tests care about WHO a volley was aimed at, not travel time.
function landProjectiles(sim) {
    for (const p of sim.projectiles) p.onHit();
    sim.projectiles.length = 0;
}

function buildScene(nVictims, victimStats = VICTIM_STATS, spacing = 26) {
    const sim = simStub(1);
    const lancer = new BattleUnit("1-0", 1, LANCER_STATS, "elite_fire_lancer", "Chinese", sim);
    lancer.x = 0;
    lancer.y = 0;
    sim.team1.push(lancer);
    const victims = [];
    for (let i = 0; i < nVictims; i++) {
        const v = new BattleUnit(`2-${i}`, 2, victimStats, "champion", "Franks", sim);
        // Fan the victims out along +x at increasing distance, all comfortably
        // inside charge reach (120px + 14 + 14 = 148px edge-to-edge).
        v.x = 40 + i * spacing;
        v.y = 0;
        sim.team2.push(v);
        victims.push(v);
    }
    return { sim, lancer, victims, all: [lancer, ...victims] };
}

test("a charge volley spreads its 3 projectiles over 3 DISTINCT enemies in range", () => {
    const { sim, lancer, victims, all } = buildScene(4);
    assert.equal(lancer.chargeAttackRange, 120); // 4 tiles * TILE_SIZE(30)

    lancer.target = victims[0];
    lancer.update(DT, all, sim.team2);

    assert.equal(sim.projectiles.length, 3, "the volley must fire exactly charge_projectile_count projectiles");
    landProjectiles(sim);

    // 5 armour-ignoring damage per charge projectile -> 60 - 5 = 55.
    const hit = victims.filter((v) => v.currentHp < 60);
    assert.equal(hit.length, 3, "three projectiles must land on three DIFFERENT enemies, not all on the target");
    assert.deepEqual(
        victims.map((v) => v.currentHp),
        [55, 55, 55, 60],
        "the three NEAREST enemies (target first, then nearest-first) each take exactly one charge hit",
    );
});

test("a lone enemy still eats the whole volley", () => {
    const { sim, lancer, victims, all } = buildScene(1);
    lancer.target = victims[0];
    lancer.update(DT, all, sim.team2);

    assert.equal(sim.projectiles.length, 3);
    landProjectiles(sim);
    assert.equal(
        victims[0].currentHp, 45,
        "with no other enemy in reach all 3 projectiles hit the sole target (60 - 3*5)",
    );
});

test("two enemies in reach split a 3-projectile volley 2/1, surplus wrapping to the primary", () => {
    const { sim, lancer, victims, all } = buildScene(2);
    lancer.target = victims[0];
    lancer.update(DT, all, sim.team2);

    assert.equal(sim.projectiles.length, 3);
    landProjectiles(sim);
    assert.deepEqual(
        victims.map((v) => v.currentHp),
        [50, 55],
        "distinct targets first, then the leftover projectile wraps back onto the primary",
    );
});

test("only enemies INSIDE charge range join the volley", () => {
    // Second victim parked past the 148px edge-to-edge charge reach.
    const { sim, lancer, victims, all } = buildScene(2);
    victims[1].x = 400;
    lancer.target = victims[0];
    lancer.update(DT, all, sim.team2);
    landProjectiles(sim);
    assert.deepEqual(
        victims.map((v) => v.currentHp),
        [45, 60],
        "an out-of-range enemy must not be sprayed; the whole volley stays on the in-range target",
    );
});

test("the volley RECHARGES after charge_recharge_time and fires again", () => {
    // Give the victim enough HP to survive 40s of melee so the fight is still
    // running when the recharge lands.
    const { sim, lancer, victims, all } = buildScene(
        1, { ...VICTIM_STATS, hp: 100000 },
    );
    lancer.target = victims[0];

    const volleyTimes = [];
    for (let tick = 0; tick < 40 * 60; tick++) {
        lancer.update(DT, all, sim.team2);
        if (sim.projectiles.length) {
            assert.equal(
                sim.projectiles.length, 3,
                "a fire lancer only ever emits projectiles as a full 3-shot volley",
            );
            volleyTimes.push(tick * DT);
            sim.projectiles.length = 0;
        }
    }

    assert.equal(
        volleyTimes.length, 2,
        `40s at charge_recharge_time=30 must contain exactly 2 volleys, got ${volleyTimes.length} ` +
        `at ${JSON.stringify(volleyTimes)} -- the volley is NOT a one-shot`,
    );
    assert.ok(volleyTimes[0] < 1, "the first volley fires as soon as the lancer is in charge range");
    assert.ok(
        volleyTimes[1] >= 30 && volleyTimes[1] < 32.1,
        `the second volley must land just after the 30s recharge (got ${volleyTimes[1]}s)`,
    );
});

test("a charge unit with no charge_recharge_time stays one-shot (legacy fallback)", () => {
    const sim = simStub(1);
    const stats = { ...LANCER_STATS, charge_recharge_time: 0 };
    const lancer = new BattleUnit("1-0", 1, stats, "elite_fire_lancer", "Chinese", sim);
    const victim = new BattleUnit("2-0", 2, { ...VICTIM_STATS, hp: 100000 }, "champion", "Franks", sim);
    lancer.x = 0; lancer.y = 0; victim.x = 40; victim.y = 0;
    sim.team1.push(lancer); sim.team2.push(victim);
    lancer.target = victim;

    let volleys = 0;
    for (let tick = 0; tick < 40 * 60; tick++) {
        lancer.update(DT, [lancer, victim], sim.team2);
        if (sim.projectiles.length) { volleys++; sim.projectiles.length = 0; }
    }
    assert.equal(volleys, 1, "without a recharge time the volley must remain one-shot");
    assert.equal(lancer.hasUsedCharge, true);
});

// NOT PINNED HERE, deliberately: the truth cards record projectiles_fired = 0
// for elite_fire_lancer in BOTH corpus siege fights (vs siege_onager, vs
// heavy_scorpion) against 63-93 in every non-siege fight, i.e. the real charge
// volley never targets siege. Gating the volley on !target.isSiege() was built
// and measured over the whole corpus
// (data/calibration/runs/20260730T151710Z-e2-fire-lancer-siegegate.json): it
// removes 9 gated mismatches but COSTS a winner
// (elite_fire_lancer__vs__heavy_scorpion goes 0.6 agreement -> 0.15 and flips),
// because the volley damage is currently papering over a separate deficit in
// melee-vs-siege. Left out until that deficit is fixed.

test("the volley picks targets deterministically -- no sim.rng draw", () => {
    const { sim, lancer, victims, all } = buildScene(4);
    const before = sim.rng.getState();
    lancer.target = victims[0];
    lancer.update(DT, all, sim.team2);
    assert.equal(
        sim.rng.getState(), before,
        "charge-volley target selection must not consume RNG (accuracy is 100 here, so nothing else rolls)",
    );
});
