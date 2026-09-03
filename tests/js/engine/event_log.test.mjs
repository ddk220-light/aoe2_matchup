import { test } from "node:test";
import assert from "node:assert/strict";
import { createSimulation } from "../../../apps/website/static/js/engine/index.js";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

const ARCHER = { hp: 40, attack: 6, attack_range: 5, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 0, outline_size: 0.2, accuracy: 100,
    unit_name: "A", cost_food: 0, cost_wood: 25, cost_gold: 45, hp_regen: 0 };
const MELEE = { hp: 100, attack: 10, attack_range: 0, attack_speed: 0.5, attack_delay: 0,
    movement_speed: 1.2, melee_armor: 0, pierce_armor: 0, outline_size: 0.3, accuracy: 100,
    unit_name: "M", cost_food: 60, cost_wood: 0, cost_gold: 20, hp_regen: 0 };

function run(seed, withLog) {
    const sim = createSimulation({ teams: [
        { combatDict: ARCHER, slug: "a", civ: "Britons", count: 5 },
        { combatDict: MELEE, slug: "m", civ: "Franks", count: 5 }], seed });
    if (withLog) sim.eventLog = { damage: [], missiles: [] };
    const hashes = [];
    let ticks = 0;
    while (sim.winner === null && ticks < 60 * 120) {
        sim.step(1 / 60); ticks++;
        if (ticks % 60 === 0) hashes.push(sim.stateHash());
    }
    return { hashes, log: sim.eventLog, winner: sim.winner, time: sim.battleTime };
}

test("recording does not perturb the simulation", () => {
    const off = run(1, false), on = run(1, true);
    assert.deepEqual(on.hashes, off.hashes, "stateHash stream must be identical");
    assert.equal(on.winner, off.winner);
    assert.equal(on.time, off.time);
});

test("eventLog defaults to null and costs nothing", () => {
    const r = run(2, false);
    assert.equal(r.log, null);
});

test("damage events carry the tape's shape", () => {
    const r = run(3, true);
    assert.ok(r.log.damage.length > 0);
    for (const e of r.log.damage.slice(0, 20)) {
        for (const k of ["t", "attacker", "victim", "damage", "victim_hp_after",
                         "kill", "attacker_owner", "victim_owner"]) {
            assert.ok(e[k] !== undefined, `missing ${k}`);
        }
        assert.ok(e.attacker_owner !== e.victim_owner, "damage must cross teams");
    }
    const kills = r.log.damage.filter((e) => e.kill).length;
    assert.ok(kills > 0, "kill flags must be set");
});

test("every projectile gets a distinct id", () => {
    const r = run(4, true);
    assert.ok(r.log.missiles.length > 0);
    const ids = new Set(r.log.missiles.map((m) => m.id));
    assert.equal(ids.size, r.log.missiles.length, "projectile ids must be unique");
});

// Damage reflect (Khitan Lamellar Armor, damage_reflect_percent on the combat
// dict) mutates the ATTACKER's currentHp directly inside takeDamage, with no
// recursive call into attacker.takeDamage. A prior version of the recorder
// missed this: a reflect kill produced a real unit death with zero damage
// events. Exercised directly against BattleUnit (no full sim/rng needed --
// takeDamage draws no randomness) so the reflect math is exact and
// deterministic.
test("a damage-reflect kill still produces a role-reversed damage event", () => {
    const sim = {
        team1: [], team2: [], projectiles: [], effects: [], battleTime: 42,
        rng: makeRng(1), eventLog: { damage: [], missiles: [] },
    };
    const attacker = new BattleUnit("1-0", 1, {
        hp: 10, attack: 20, attack_range: 0, attack_speed: 1, attack_delay: 0,
        movement_speed: 1, melee_armor: 0, pierce_armor: 0, outline_size: 0.3,
        accuracy: 100, unit_name: "Attacker",
    }, "melee_attacker", "Franks", sim);
    const reflector = new BattleUnit("2-0", 2, {
        hp: 100, attack: 5, attack_range: 0, attack_speed: 1, attack_delay: 0,
        movement_speed: 1, melee_armor: 0, pierce_armor: 0, outline_size: 0.3,
        accuracy: 100, unit_name: "Reflector", damage_reflect_percent: 1.0,
    }, "liao_dao", "Khitans", sim);
    sim.team1.push(attacker);
    sim.team2.push(reflector);

    // 15 dmg to the reflector (hp 100 -> 85, survives) bounces 15*1.0 = 15
    // back onto the attacker (hp 10 -> clamped to 0, dies).
    reflector.takeDamage(15, attacker);

    assert.equal(attacker.currentHp, 0);
    assert.equal(attacker.state, "dead");
    assert.equal(reflector.currentHp, 85);
    assert.notEqual(reflector.state, "dead");

    assert.equal(sim.eventLog.damage.length, 2, "reflect bounce + main hit");
    const [reflectEvt, mainEvt] = sim.eventLog.damage;

    // Reflect event: roles reversed -- the reflector is the source, the
    // original attacker is the one who took damage and died.
    assert.equal(reflectEvt.attacker, reflector.id);
    assert.equal(reflectEvt.victim, attacker.id);
    assert.equal(reflectEvt.damage, 10); // 10 hp actually applied (clamped at 0), not the raw 15
    assert.equal(reflectEvt.victim_hp_after, 0);
    assert.equal(reflectEvt.kill, true);
    assert.equal(reflectEvt.attacker_owner, reflector.team);
    assert.equal(reflectEvt.victim_owner, attacker.team);

    // Main hit: unchanged roles, the reflector took the original 15 damage.
    assert.equal(mainEvt.attacker, attacker.id);
    assert.equal(mainEvt.victim, reflector.id);
    assert.equal(mainEvt.damage, 15);
    assert.equal(mainEvt.victim_hp_after, 85);
    assert.equal(mainEvt.kill, false);
});
