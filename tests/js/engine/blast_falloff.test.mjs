// Siege blast falloff, fitted to the recorded tapes (calibration experiment E4).
//
// Representative champion-versus-siege-onager regression case (a
// 4-Siege-Onager vs 21-Champion fight) and .../siege_onager__vs__hussar. Each
// stone's damage.jsonl impact group, with every victim's position taken from
// the 10 Hz units stream and the impact point from the missile track's last
// sample, gives a clean distance -> damage curve:
//
//   dist(tiles)  0.43   0.48   0.56   0.75   1.12   1.21   1.39   1.77
//   damage      64.30  60.70  59.09  46.29  29.94  26.18  17.65   1.00
//
// Attack 76 vs Champion melee armor 4 => 72 net at the centre. The curve is a
// straight line from full damage at the victim's own body edge to ZERO one
// blast radius (splash_radius = 1.5 tiles) beyond it, with a 1-damage floor --
// e.g. d=1.39 predicts 72*(1-(1.39-0.2)/1.5) = 17.5 against 17.6 observed, and
// d=1.77 is already past the edge and lands on the floor.
//
// The engine previously (a) inflated every single-stone blast radius to a
// minimum of 2.5 tiles and (b) fell off only to 25% of full damage at that
// edge, so a unit 2.4 tiles from the impact took ~20 damage where the real
// game deals 1. Integrated over the disc that is ~4.2x too much blast damage
// per shot.
import { test } from "node:test";
import assert from "node:assert/strict";
import { BattleUnit } from "../../../apps/website/static/js/engine/battle_unit.js";
import { makeRng } from "../../../apps/website/static/js/engine/rng.js";

// Aztec Siege Onager combat dictionary.
const ONAGER_STATS = {
    hp: 70, attack: 76, attack_range: 9, attack_speed: 1 / 6,
    movement_speed: 0.6, melee_armor: 0, pierce_armor: 8,
    outline_size: 0.5, collision_size: 0.5,
    accuracy: 100, base_accuracy: 100, unit_name: "Siege Onager",
    splash_radius: 1.5, projectile_speed: 3.5, min_attack_range: 3,
    is_siege_projectile: 1,
    attacks_json: JSON.stringify({ 4: 76 }),
};

// Chinese Champion: collision_size 0.2 -> physics radius 6px (E11: the .dat's
// collision_size_x, not the old `round(10 + outline*20)` = 14px), melee armor 4.
const CHAMPION_STATS = {
    hp: 70, attack: 18, attack_range: 0, attack_speed: 0.5,
    movement_speed: 1.06, melee_armor: 4, pierce_armor: 5,
    outline_size: 0.2, collision_size: 0.2,
    accuracy: 100, base_accuracy: 100, unit_name: "Champion",
    armors_json: JSON.stringify({ 4: 4, 3: 5 }),
};

function simStub(seed = 1) {
    return {
        team1: [], team2: [], projectiles: [], effects: [],
        battleTime: 0, rng: makeRng(seed),
    };
}

// Fire one stone at `primary` and step the projectile until it lands.
function fireAndLand(sim, onager, primary) {
    onager.fireProjectile(primary, onager.getDamageAgainst(primary));
    for (let i = 0; i < 6000 && sim.projectiles.length; i++) {
        for (const p of [...sim.projectiles]) p.update(1 / 60);
        sim.projectiles = sim.projectiles.filter((p) => !p.dead);
    }
}

test("blast radius is the unit's true splash_radius, not a 2.5-tile floor", () => {
    const sim = simStub(1);
    const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
    assert.equal(
        onager.splashRadius,
        45,
        "1.5 tiles * TILE_SIZE(30) = 45px -- the engine must not inflate it",
    );
});

test("splash falls off linearly to ZERO one radius beyond the victim's edge", () => {
    const sim = simStub(1);
    const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
    const primary = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
    // Victims at 0.75 and 1.39 tiles from the impact point (the tape rows above).
    const near = new BattleUnit("2-1", 2, CHAMPION_STATS, "champion", "Chinese", sim);
    const far = new BattleUnit("2-2", 2, CHAMPION_STATS, "champion", "Chinese", sim);
    // Well outside splashR + radius = 45 + 6 = 51px: must be untouched.
    const outside = new BattleUnit("2-3", 2, CHAMPION_STATS, "champion", "Chinese", sim);

    assert.equal(near.radius, 6);

    onager.x = -300; onager.y = 0;
    primary.x = 0; primary.y = 0;
    near.x = 0.75 * 30; near.y = 0;   // 22.5px
    far.x = 1.39 * 30; far.y = 0;     // 41.7px
    outside.x = 200; outside.y = 0;

    sim.team1.push(onager);
    sim.team2.push(primary, near, far, outside);

    // Base the expectations on the engine's own post-armor damage, so this
    // test pins the FALLOFF SHAPE and nothing else.
    const netDamage = onager.getDamageAgainst(primary);

    fireAndLand(sim, onager, primary);

    // falloff = 1 - (dist - victim.radius)/splashR, floored at 1 damage.
    const expect = (distPx) =>
        Math.max(
            1,
            Math.round(
                netDamage *
                    (1 - Math.min(1, Math.max(0, distPx - 6) / 45)),
            ),
        );

    assert.equal(primary.currentHp, 0, "a direct hit takes the full, un-attenuated damage");
    assert.equal(near.currentHp, 70 - expect(22.5), "near victim takes the linear-falloff splash");
    assert.equal(far.currentHp, 70 - expect(41.7), "far victim takes strictly less, linearly");
    assert.ok(
        70 - far.currentHp < 70 - near.currentHp,
        "damage must decrease monotonically with distance from the impact",
    );
    assert.equal(outside.currentHp, 70, "a victim beyond splashR + its radius is untouched");
});

test("a victim at the very edge of the blast takes the 1-damage floor, not 25% of full", () => {
    const sim = simStub(1);
    const onager = new BattleUnit("1-0", 1, ONAGER_STATS, "siege_onager", "Aztecs", sim);
    const primary = new BattleUnit("2-0", 2, CHAMPION_STATS, "champion", "Chinese", sim);
    const edge = new BattleUnit("2-1", 2, CHAMPION_STATS, "champion", "Chinese", sim);

    onager.x = -300; onager.y = 0;
    primary.x = 0; primary.y = 0;
    // Just inside splashR + radius (51px) -- edgeDist 44 of 45, so ~0 falloff.
    edge.x = 50; edge.y = 0;

    sim.team1.push(onager);
    sim.team2.push(primary, edge);
    fireAndLand(sim, onager, primary);

    // edgeDist 44 of splashR 45 -> falloff 0.022 -> round(71*0.022) = 2.
    // The old 25%-of-full edge floor would have dealt round(71*0.25) = 18.
    assert.equal(
        edge.currentHp,
        68,
        "a victim at the blast edge must take ~0, not a quarter of full damage",
    );
});
