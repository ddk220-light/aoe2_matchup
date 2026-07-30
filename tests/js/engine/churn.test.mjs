// Task 6: crowd churn. A unit packed among several other units (either
// side) loses time to shoving/re-facing/re-acquiring its target, so its
// effective attack interval (churnCooldown()) should run longer than its
// nominal reload -- and exactly equal the nominal reload with nobody
// nearby. See battle_unit.js churnCooldown() and constants.js CHURN_MAX/
// _RADIUS/_SATURATION.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";
import { CHURN_RADIUS, CHURN_SATURATION } from "../../../apps/website/static/js/engine/constants.js";

const STATS = {
    hp: 60, attack: 9, attack_range: 0, attack_speed: 0.5, attack_delay: 0,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 90, unit_name: "Test Melee",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

test("no neighbours: churnCooldown equals the nominal reload exactly", () => {
    const sim = simStub(1);
    const u = new BattleUnit("1-0", 1, STATS, "u", "Franks", sim);
    sim.team1.push(u);
    u.x = 0; u.y = 0;
    // Nothing else on the field at all -- zero crowding regardless of RNG draw.
    assert.equal(u.churnCooldown(), u.reloadTime);

    // A lone ally/enemy well outside CHURN_RADIUS still counts as zero crowding.
    const far = new BattleUnit("2-0", 2, STATS, "far", "Goths", sim);
    far.x = CHURN_RADIUS * 10; far.y = 0;
    sim.team2.push(far);
    assert.equal(u.churnCooldown(), u.reloadTime);
});

test("several allies adjacent: churnCooldown exceeds the nominal reload", () => {
    const sim = simStub(7);
    const u = new BattleUnit("1-0", 1, STATS, "u", "Franks", sim);
    u.x = 0; u.y = 0;
    sim.team1.push(u);
    // Pack CHURN_SATURATION neighbours (a mix of both teams, matching the
    // reference shape's "either side" crowding) well inside CHURN_RADIUS so
    // crowding saturates at 1.0.
    for (let i = 0; i < CHURN_SATURATION; i++) {
        const team = i % 2 === 0 ? 1 : 2;
        const ally = new BattleUnit(`n-${i}`, team, STATS, `n${i}`, "Franks", sim);
        ally.x = 1 + i; // well within CHURN_RADIUS, distinct positions
        ally.y = 0;
        (team === 1 ? sim.team1 : sim.team2).push(ally);
    }

    const result = u.churnCooldown();
    assert.ok(
        result > u.reloadTime,
        `expected churnCooldown() (${result}) to exceed nominal reload (${u.reloadTime})`,
    );
});

test("dead neighbours never count toward crowding", () => {
    const sim = simStub(1);
    const u = new BattleUnit("1-0", 1, STATS, "u", "Franks", sim);
    u.x = 0; u.y = 0;
    sim.team1.push(u);
    for (let i = 0; i < CHURN_SATURATION; i++) {
        const corpse = new BattleUnit(`d-${i}`, 2, STATS, `d${i}`, "Goths", sim);
        corpse.x = 1; corpse.y = 0;
        corpse.state = "dead";
        sim.team2.push(corpse);
    }
    assert.equal(u.churnCooldown(), u.reloadTime);
});

test("self is never counted as its own neighbour", () => {
    const sim = simStub(1);
    const u = new BattleUnit("1-0", 1, STATS, "u", "Franks", sim);
    u.x = 0; u.y = 0;
    sim.team1.push(u);
    assert.equal(u.churnCooldown(), u.reloadTime);
});
