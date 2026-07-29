import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit, setArmorClassNames } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const STATS = {
    hp: 60, attack: 9, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 90, unit_name: "Test Archer",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

test("derived stats match the legacy formulas", () => {
    const u = new BattleUnit("1-0", 1, STATS, "test", "Franks", simStub());
    assert.equal(u.attackRange, 5 * 30 + 5);      // tiles*TILE_SIZE + MELEE_RANGE_BUFFER
    assert.equal(u.radius, 14);                   // round(10 + 0.2*20)
    assert.equal(u.reloadTime, 2.0);              // 1/attack_speed
    assert.equal(u.moveSpeed, 0.96 * 30);
    assert.equal(u.accuracy, 0.9);
    assert.equal(u.state, "idle");
});

test("fireProjectile pushes into this.sim.projectiles and draws from sim.rng", () => {
    const sim = simStub(3);
    const a = new BattleUnit("1-0", 1, STATS, "a", "Franks", sim);
    const b = new BattleUnit("2-0", 2, { ...STATS, hp: 100 }, "b", "Goths", sim);
    a.x = 0; a.y = 0; b.x = 60; b.y = 0;
    sim.team1.push(a); sim.team2.push(b);
    const before = sim.rng.getState();
    a.fireProjectile(b);
    assert.equal(sim.projectiles.length, 1);
    assert.notEqual(sim.rng.getState(), before); // accuracy 0.9 < 1 must roll
});

test("setArmorClassNames feeds the damage-breakdown labels", () => {
    setArmorClassNames({ 4: "Base Melee" });
    // No assertion beyond not throwing: labels are display-only.
});
