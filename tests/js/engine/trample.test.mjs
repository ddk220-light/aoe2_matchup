import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Burmese Elite Battle Elephant's real combat dict (data/calibration/combat_dicts.json):
// trample_percent=0.25, trample_radius=0.4 (tiles), trample_flat_damage=0,
// outline_size=0.5 (-> radius 20px), attack=18, melee_armor 0 target -> trample
// damage floor(18*0.25)=4 per victim. TILE_SIZE=30, so trample_radius=12px.
const TRAMPLER_STATS = {
    hp: 320, attack: 18, attack_range: 0, attack_speed: 0.5, attack_delay: 0.167,
    movement_speed: 0.99, melee_armor: 6, pierce_armor: 9, outline_size: 0.5,
    accuracy: 100, unit_name: "Elite Battle Elephant",
    trample_percent: 0.25, trample_radius: 0.4, trample_flat_damage: 0,
};

// A small victim (outline_size 0.2 -> radius 14px), e.g. a Champion.
const VICTIM_STATS = {
    hp: 60, attack: 9, attack_range: 0, attack_speed: 0.5, attack_delay: 0.2,
    movement_speed: 0.96, melee_armor: 0, pierce_armor: 1, outline_size: 0.2,
    accuracy: 90, unit_name: "Test Victim",
};

function simStub(seed = 1) {
    return { team1: [], team2: [], projectiles: [], effects: [], battleTime: 0, rng: makeRng(seed) };
}

test("trample splashes a nearby victim within attacker-body + trample + victim-body reach", () => {
    const sim = simStub(1);
    const elephant = new BattleUnit("1-0", 1, TRAMPLER_STATS, "elite_elephant", "Burmese", sim);
    const primary = new BattleUnit("2-0", 2, VICTIM_STATS, "champion", "Franks", sim);
    const nearbyVictim = new BattleUnit("2-1", 2, VICTIM_STATS, "champion", "Franks", sim);
    const farVictim = new BattleUnit("2-2", 2, VICTIM_STATS, "champion", "Franks", sim);

    // Sanity-check the radii this test's distances are built from.
    assert.equal(elephant.radius, 20);
    assert.equal(nearbyVictim.radius, 14);
    assert.equal(elephant.trampleRadius, 12); // 0.4 tiles * TILE_SIZE(30)

    elephant.x = 0; elephant.y = 0;
    primary.x = 10; primary.y = 0; // the swing's actual target

    // Reach if the attacker's own body radius is (wrongly) omitted:
    // trampleRadius(12) + victim.radius(14) = 26.
    // Correct edge-to-edge reach: elephant.radius(20) + trampleRadius(12) +
    // victim.radius(14) = 46 -- the blast emanates from the trampler's BODY,
    // not a point (see simulation_real.py's identical reach formula and its
    // comment on this exact omission).
    nearbyVictim.x = 35; nearbyVictim.y = 0; // 26 < 35 <= 46
    farVictim.x = 55; farVictim.y = 0;       // outside even the correct reach

    sim.team1.push(elephant);
    sim.team2.push(primary, nearbyVictim, farVictim);

    elephant.performAttackOn(primary);

    assert.equal(
        nearbyVictim.currentHp,
        56,
        "a victim within the attacker-body-inclusive trample reach must take " +
        "floor(18*0.25)=4 splash damage (60 - 4 = 56)",
    );
    assert.equal(
        farVictim.currentHp,
        60,
        "a victim outside the trample reach entirely must be untouched",
    );
});
