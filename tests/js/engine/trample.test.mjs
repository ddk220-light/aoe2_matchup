import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Burmese Elite Battle Elephant combat dictionary:
// trample_percent=0.25, trample_radius=0.4 (tiles), trample_flat_damage=0,
// attack=18, melee_armor 0 target -> 18*0.25=4.5 damage per victim.
// TILE_SIZE=30, so trample_radius=12px.
//
// E11: outline_size (0.5) is the SELECTION CIRCLE; the physics radius is the
// .dat's collision_size_x, which for a battle elephant is 0.25 tiles -- the
// same as a horse. The elephant is big to LOOK at and normal-sized to bump
// into. That makes its physics radius 7.5px, where the old
// `round(10 + outline*20)` formula said 20px.
const TRAMPLER_STATS = {
    hp: 320, attack: 18, attack_range: 0, attack_speed: 0.5, attack_delay: 0.167,
    movement_speed: 0.99, melee_armor: 6, pierce_armor: 9,
    outline_size: 0.5, collision_size: 0.25,
    accuracy: 100, unit_name: "Elite Battle Elephant",
    trample_percent: 0.25, trample_radius: 0.4, trample_flat_damage: 0,
};

// A small victim (collision_size 0.2 -> radius 6px), e.g. a Champion.
const VICTIM_STATS = {
    hp: 60, attack: 9, attack_range: 0, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1,
    outline_size: 0.2, collision_size: 0.2,
    accuracy: 90, unit_name: "Test Victim",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

test("trample uses blast plus victim body and movement tolerance without attacker expansion", () => {
    const sim = simStub(1);
    const elephant = new BattleUnit("1-0", 1, TRAMPLER_STATS, "elite_elephant", "Burmese", sim);
    const primary = new BattleUnit("2-0", 2, VICTIM_STATS, "champion", "Franks", sim);
    const nearbyVictim = new BattleUnit("2-1", 2, VICTIM_STATS, "champion", "Franks", sim);
    const farVictim = new BattleUnit("2-2", 2, VICTIM_STATS, "champion", "Franks", sim);

    // Sanity-check the radii this test's distances are built from.
    assert.equal(elephant.radius, 7.5);       // collision 0.25 tiles * 30
    assert.equal(nearbyVictim.radius, 6);     // collision 0.20 tiles * 30
    assert.equal(elephant.drawRadius, 20);    // selection circle, renderer only
    assert.equal(elephant.trampleRadius, 12); // 0.4 tiles * TILE_SIZE(30)

    elephant.x = 0; elephant.y = 0;
    primary.x = 5; primary.y = 0; // the swing's actual target

    // The blast disc is centred on the attacker. A victim body intersects it
    // through trampleRadius(12) + victim.radius(6), with the movement
    // resolver's 2px contact tolerance. The Elephant's own 7.5px collision
    // radius must not expand the damage disc to 25.5px.
    nearbyVictim.x = 20; nearbyVictim.y = 0; // exactly on the tolerated edge
    farVictim.x = 22; farVictim.y = 0;       // only the old body-expanded rule hit

    sim.team1.push(elephant);
    sim.team2.push(primary, nearbyVictim, farVictim);

    elephant.performAttackOn(primary);

    assert.equal(
        nearbyVictim.currentHp,
        55.5,
        "a victim intersecting the blast disc must take fractional " +
        "18*0.25=4.5 splash damage",
    );
    assert.equal(
        farVictim.currentHp,
        60,
        "the attacker's body radius must not expand trample reach",
    );
});
