import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  calculateDamage,
  chargeProjectileDamage,
  chargeSpec,
  rangedSpec,
  trampleSpec,
} from "../src/combat/attacks.js";
import { unitBySlug } from "../src/unit-registry.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const SUBJECTS = [
  "jian_swordsman_wu",
  "xianbei_raider_wei",
  "mounted_trebuchet_khitans",
  "grenadier_jurchens",
  "war_chariot_shu",
  "elite_white_feather_guard_shu",
  "elite_tiger_cavalry_wei",
  "elite_blackwood_archer_tupi",
  "elite_ibirapema_warrior_tupi",
  "elite_temple_guard_muisca",
  "elite_guecha_warrior_muisca",
  "elite_bolas_rider_mapuche",
  "elite_kona_mapuche",
  "elite_hussite_wagon_bohemians",
  "elite_samurai_japanese",
  "elite_chu_ko_nu_chinese",
  "elite_kipchak_cumans",
  "elite_coustillier_burgundians",
  "elite_obuch_poles",
];


async function mechanics(slug) {
  const row = unitBySlug(slug);
  assert.ok(row, `${slug} is registered`);
  return JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${row.fixture}`, import.meta.url),
    "utf8",
  ));
}


test("the captured unique roster has generated mechanics and effect metadata", async () => {
  for (const slug of SUBJECTS) {
    const value = await mechanics(slug);
    assert.ok(value.effects && Object.keys(value.effects).length > 0, slug);
    assert.match(value.provenance.reference_selector, new RegExp(slug));
  }
});


test("multi-projectile, charge, splash, pass-through and hazard weapons export distinctly",
  async () => {
    const xianbei = await mechanics("xianbei_raider_wei");
    const xianbeiCharge = chargeSpec(xianbei);
    assert.equal(xianbeiCharge.projectileCount, 5);
    assert.equal(xianbeiCharge.addsToNormalAttack, true);
    assert.equal(xianbeiCharge.attackRangeTiles, 7);

    const bolas = chargeSpec(await mechanics("elite_bolas_rider_mapuche"));
    assert.equal(bolas.projectileCount, 1);
    assert.equal(bolas.ignoresArmor, false);

    const grenade = rangedSpec(await mechanics("grenadier_jurchens"));
    assert.equal(grenade.passThrough, false);
    assert.equal(grenade.extraProjectileCount, 1);
    assert.equal(grenade.impactSplashRadius, 0.65);

    const mounted = await mechanics("mounted_trebuchet_khitans");
    assert.equal(rangedSpec(mounted).passThrough, false);
    assert.equal(mounted.effects.impact_hazard_damage_per_second, 2);

    const chariot = rangedSpec(await mechanics("war_chariot_shu"));
    assert.equal(chariot.passThrough, true);
    assert.equal(chariot.extraProjectileCount, 6);
    assert.equal(chariot.passThroughCount, 3);

    const chu = rangedSpec(await mechanics("elite_chu_ko_nu_chinese"));
    assert.equal(chu.extraProjectileCount, 4);
    assert.deepEqual(chu.extraProjectileAttacks, { 3: 3 });
  });


test("dynamic armor strip, transform, kill bonus and execute participate in class damage", () => {
  const baseMechanics = {
    attack_classes: { 4: 10 },
    armor_classes: { 4: 2, 3: 3 },
    effects: {},
    hp: 100,
  };
  const target = {
    hp: 40,
    maxHp: 100,
    mechanics: baseMechanics,
    specialState: { armorStripped: 1, transformed: false },
  };
  const actor = {
    mechanics: {
      ...baseMechanics,
      effects: { execute_damage_per_step: 1, execute_hp_step: 0.15 },
    },
    specialState: { killAttackBonus: 2, nearbyAttackBonus: 0, transformed: false },
  };
  // 10 - (2 - 1) + 2 kill attack + floor(60% / 15%) execute.
  assert.equal(calculateDamage(actor, target), 15);

  actor.specialState.transformed = true;
  actor.mechanics.effects.transform_attacks = { 4: 17 };
  assert.equal(calculateDamage(actor, target), 22);
});


test("Elite Coustillier charge adds attack before the single armor subtraction", async () => {
  const coustillier = await mechanics("elite_coustillier_burgundians");
  const paladin = await mechanics("paladin");
  const durablePaladin = {
    ...paladin,
    hp: 1000,
    attack_classes: { ...paladin.attack_classes, 4: 1 },
  };
  const spawn = (referenceId, owner, x, unitMechanics) => createUnitState({
    referenceId,
    owner,
    x,
    y: 4,
    facing: 0,
    mechanics: unitMechanics,
    acquisitionRank: 0,
    acquisitionCount: 1,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
  let world = createWorld({
    ratio: "coustillier-charge-test",
    units: [
      spawn(1, 2, 4, coustillier),
      spawn(2, 3, 4.5, durablePaladin),
    ],
  });
  for (let tick = 0; tick < 2700; tick += 1) world = stepWorld(world);
  const hits = world.eventLog.filter((event) => (
    event.type === "damage" && event.actorId === 1 && event.targetId === 2
  ));
  assert.equal(hits[0].amount, 35);
  assert.ok(hits.some(({ amount }) => amount === 10),
    "ordinary attacks continue while charge recharges");
  const charged = hits.filter(({ amount }) => amount === 35);
  assert.ok(charged.length >= 2, "charge becomes available again after 40 seconds");
  assert.ok(charged[1].tick - charged[0].tick >= 40 * 60);
});


test("Elite Samurai speed charge stays latched through contact and adds one attack", async () => {
  const samurai = await mechanics("elite_samurai_japanese");
  const paladin = await mechanics("paladin");
  const durablePaladin = {
    ...paladin,
    hp: 1000,
    speed_tiles_per_second: 0,
    attack_classes: { ...paladin.attack_classes, 4: 1 },
  };
  const spawn = (referenceId, owner, x, unitMechanics) => createUnitState({
    referenceId,
    owner,
    x,
    y: 4,
    facing: 0,
    mechanics: unitMechanics,
    acquisitionRank: 0,
    acquisitionCount: 1,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
  let world = createWorld({
    ratio: "samurai-speed-charge-test",
    units: [
      spawn(1, 2, 4, samurai),
      spawn(2, 3, 10, durablePaladin),
    ],
  });
  let observedLatchedInsideMinimum = false;
  for (let tick = 0; tick < 900; tick += 1) {
    world = stepWorld(world);
    const actor = world.units.find(({ referenceId }) => referenceId === 1);
    const target = world.units.find(({ referenceId }) => referenceId === 2);
    const distance = Math.hypot(target.x - actor.x, target.y - actor.y);
    if (distance < samurai.effects.charged_speed_min_target_distance_tiles
        && actor.specialState.chargedSpeedActive) {
      observedLatchedInsideMinimum = true;
      assert.ok(Math.abs(actor.mechanics.speed_tiles_per_second
        - samurai.speed_tiles_per_second * samurai.effects.charged_speed_multiplier) < 1e-9);
    }
    if (world.eventLog.some((event) => event.type === "damage" && event.actorId === 1)) break;
  }
  assert.equal(observedLatchedInsideMinimum, true);
  const firstHit = world.eventLog.find((event) => (
    event.type === "damage" && event.actorId === 1 && event.targetId === 2
  ));
  assert.equal(firstHit.amount, 12);
  const actor = world.units.find(({ referenceId }) => referenceId === 1);
  assert.equal(actor.specialState.chargedSpeedActive, false);
  assert.equal(actor.specialState.chargedSpeedTargetId, null);
});


test("Elite Samurai Japanese reload is not capped by its longer source graphic", async () => {
  const samurai = await mechanics("elite_samurai_japanese");
  const paladin = await mechanics("paladin");
  const target = {
    ...paladin,
    hp: 5000,
    speed_tiles_per_second: 0,
    attack_classes: { 4: 1 },
  };
  const spawn = (referenceId, owner, x, unitMechanics) => createUnitState({
    referenceId,
    owner,
    x,
    y: 4,
    facing: 0,
    mechanics: unitMechanics,
    acquisitionRank: 0,
    acquisitionCount: 1,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
  let world = createWorld({
    ratio: "samurai-reload-test",
    units: [spawn(1, 2, 4, samurai), spawn(2, 3, 4.4, target)],
  });
  for (let tick = 0; tick < 500; tick += 1) world = stepWorld(world);
  const hits = world.eventLog.filter((event) => (
    event.type === "damage" && event.actorId === 1 && event.targetId === 2
  ));
  const intervals = hits.slice(1).map((hit, index) => hit.tick - hits[index].tick);
  assert.ok(intervals.length >= 3);
  // One scheduler boundary tick follows the 86-tick (ceil(1.425 * 60))
  // reload; critically this is below the old 97-tick visual-animation cap.
  assert.deepEqual([...new Set(intervals)], [87]);
});


test("White Feather Guard formation HP scales proportionally and attacks slow movement",
  async () => {
    const guard = await mechanics("elite_white_feather_guard_shu");
    const paladin = await mechanics("paladin");
    const spawn = (referenceId, owner, x, y, unitMechanics) => createUnitState({
      referenceId,
      owner,
      x,
      y,
      facing: 0,
      mechanics: unitMechanics,
      acquisitionRank: 0,
      acquisitionCount: 1,
      actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
    });
    let world = createWorld({
      ratio: "white-feather-effects-test",
      units: [
        spawn(1, 2, 4, 4, guard),
        spawn(2, 2, 4, 5, guard),
        spawn(3, 2, 5, 4, guard),
        spawn(4, 3, 4.4, 4, { ...paladin, hp: 1000, attack_classes: { 4: 1 } }),
      ],
    });
    const initialGuard = world.units.find(({ referenceId }) => referenceId === 1);
    assert.equal(initialGuard.maxHp, 101);
    assert.equal(initialGuard.hp, 101);
    for (let tick = 0; tick < 180; tick += 1) world = stepWorld(world);
    const slowed = world.units.find(({ referenceId }) => referenceId === 4);
    assert.equal(slowed.specialState.slowMultiplier, 0.85);
    assert.ok(slowed.specialState.slowUntilTick > world.tick);
    assert.ok(Math.abs(slowed.mechanics.speed_tiles_per_second
      - paladin.speed_tiles_per_second * 0.85) < 1e-9);
  });


test("Ibirapema trample and charge armor semantics are sourced", async () => {
  assert.deepEqual(trampleSpec(await mechanics("elite_ibirapema_warrior_tupi")), {
    shape: "forward-cone",
    widthTiles: 1,
    halfAngleRadians: Math.PI / 8,
    damageFraction: 1,
  });
  const bolasMechanics = await mechanics("elite_bolas_rider_mapuche");
  const spec = chargeSpec(bolasMechanics);
  const target = { mechanics: { armor_classes: { 3: 4, 17: 0, 30: 0, 8: 0 } } };
  assert.equal(chargeProjectileDamage(spec, target), 13);
});
