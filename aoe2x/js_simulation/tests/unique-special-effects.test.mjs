import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  calculateDamage,
  chargeProjectileDamage,
  chargeSpec,
  meleeChargeSpec,
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

const NEXT_SUBJECTS = [
  "elite_ratha_(melee)_bengalis",
  "elite_ratha_(ranged)_bengalis",
  "elite_konnik_bulgarians",
  "elite_arambai_burmese",
  "elite_urumi_swordsman_dravidians",
  "elite_shrivamsha_rider_gurjaras",
  "elite_liao_dao_khitans",
  "elite_ballista_elephant_khmer",
  "elite_fire_archer_wu",
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

test("the next captured unique roster has generated Imperial mechanics", async () => {
  for (const slug of NEXT_SUBJECTS) {
    const value = await mechanics(slug);
    assert.equal(value.age, "Imperial", slug);
    assert.ok(value.effects && Object.keys(value.effects).length > 0, slug);
    assert.match(value.provenance.reference_selector, new RegExp(
      slug.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
    ));
  }
});


test("Elite Fire Archer uses its canonical primary-plus-secondary volley", async () => {
  const fireArcher = await mechanics("elite_fire_archer_wu");
  assert.equal(fireArcher.charge, null,
    "the reference DB's explicit zero must not resurrect the raw DAT charge");
  assert.equal(fireArcher.effects.extra_projectiles, 2);
  assert.deepEqual(fireArcher.ranged.extra_projectile_attacks, { "3": 3 });
  assert.equal(fireArcher.attack_classes["3"], 10,
    "the primary arrow includes the fully researched attack upgrades");
});


test("Elite Konnik spawns its complete foot form after the DAT dismount time", async () => {
  const konnik = await mechanics("elite_konnik_bulgarians");
  const paladin = await mechanics("paladin");
  assert.deepEqual({
    master: konnik.dismount_form.unit_master,
    hp: konnik.dismount_form.hp,
    attack: konnik.dismount_form.attack_classes[4],
    meleeArmor: konnik.dismount_form.armor_classes[4],
    pierceArmor: konnik.dismount_form.armor_classes[3],
    speed: konnik.dismount_form.speed_tiles_per_second,
    reload: konnik.dismount_form.reload_seconds,
    spawnDelay: konnik.dismount_form.spawn_delay_seconds,
  }, {
    master: 1253,
    hp: 50,
    attack: 17,
    meleeArmor: 5,
    pierceArmor: 6,
    speed: 0.99,
    reload: 2.4,
    spawnDelay: 3,
  });

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
  const inheritedPatrol = Object.freeze({
    kind: "scenario-patrol",
    x: 10,
    y: 10,
    commandX: 10,
    commandY: 10,
    motionStartTick: 0,
    nextOpeningScanTick: 0,
  });
  const fragileMountedForm = { ...konnik, hp: 1 };
  const lethalPaladin = {
    ...paladin,
    speed_tiles_per_second: 0,
    attack_delay_seconds: 0,
    attack_animation: { ...paladin.attack_animation, seconds: 0.1 },
  };
  let world = createWorld({
    ratio: "konnik-dismount-test",
    units: [
      Object.freeze({
        ...spawn(1, 2, 4, fragileMountedForm),
        moveOrder: inheritedPatrol,
        openingAcquisitionComplete: true,
      }),
      spawn(2, 3, 4.4, lethalPaladin),
    ],
  });
  for (let tick = 0; tick < 360 && !world.eventLog.some(
    ({ type }) => type === "unit-dismounted",
  ); tick += 1) {
    world = stepWorld(world);
  }

  const death = world.eventLog.find(({ type, targetId }) => (
    type === "death" && targetId === 1
  ));
  const dismount = world.eventLog.find(({ type, actorId }) => (
    type === "unit-dismounted" && actorId === 1
  ));
  const foot = world.units.find(({ referenceId }) => referenceId === 1);
  assert.ok(death);
  assert.ok(dismount);
  assert.equal(dismount.tick - death.tick, 180,
    "the foot form appears after the concrete form's three-second creation time");
  assert.equal(foot.alive, true);
  assert.equal(foot.unitMaster, 1253);
  assert.equal(foot.hp, 50, "same-tick mounted overkill does not damage the new body");
  assert.equal(foot.maxHp, 50);
  assert.deepEqual(foot.mechanics, konnik.dismount_form);
  assert.equal(foot.specialState.dismounted, true);
  assert.equal(foot.action, "idle");
  assert.equal(foot.actionTimers.reload, 0);
  assert.equal(foot.pursuitTargetId, null);
  assert.equal(foot.engagedTargetId, null);
  assert.equal(foot.attackTargetId, null);
  assert.deepEqual(foot.moveOrder, inheritedPatrol,
    "the spawned replacement keeps the parent's durable patrol command");
  assert.equal(foot.patrolFormationTransit, true);
});


test("damage over time keeps one independently expiring stack per projectile", async () => {
  const blackwood = await mechanics("elite_blackwood_archer_tupi");
  const paladin = await mechanics("paladin");
  const oneShotBlackwood = {
    ...blackwood,
    reload_seconds: 100,
    ranged: {
      ...blackwood.ranged,
      accuracy_percent: 100,
      base_accuracy_percent: 100,
      smart_mode: 1,
    },
    effects: {
      ...blackwood.effects,
      base_accuracy: 100,
      bleed_dps: 2 / 15,
      bleed_duration: 15,
    },
  };
  const durableTarget = {
    ...paladin,
    hp: 1000,
    speed_tiles_per_second: 0,
    attack_classes: { 4: 1 },
  };
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
    ratio: "bleed-stack-test",
    units: [
      spawn(1, 2, 4, 3.8, oneShotBlackwood),
      spawn(2, 2, 4, 4.2, oneShotBlackwood),
      spawn(3, 3, 8, 4, durableTarget),
    ],
  });
  for (let tick = 0; tick < 2 * 60; tick += 1) world = stepWorld(world);
  const activeTarget = world.units.find(({ referenceId }) => referenceId === 3);
  assert.equal(activeTarget.specialState.bleedStacks.length, 2,
    "both successful arrows retain their own poison lifetime");
  for (let tick = 2 * 60; tick < 17 * 60; tick += 1) world = stepWorld(world);
  const finalTarget = world.units.find(({ referenceId }) => referenceId === 3);
  const directDamage = world.eventLog
    .filter(({ type, targetId, kind }) => type === "damage" && targetId === 3 && kind !== "bleed")
    .reduce((total, { amount }) => total + amount, 0);
  const bleedDamage = world.eventLog
    .filter(({ type, targetId, kind }) => type === "damage" && targetId === 3 && kind === "bleed")
    .reduce((total, { amount }) => total + amount, 0);
  assert.equal(directDamage, 2);
  assert.ok(Math.abs(bleedDamage - 4) < 0.01, `expected 4 poison damage, got ${bleedDamage}`);
  assert.ok(Math.abs(finalTarget.hp - 994) < 0.01);
  assert.equal(finalTarget.specialState.bleedStacks.length, 0,
    "each stack expires after its own fifteen-second lifetime");
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
    assert.equal(grenade.extraProjectileCount, 0);
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
    assert.equal(chu.projectileHitMode, 0);
    assert.equal(chu.secondaryProjectileHitMode, 0);

    const kipchak = rangedSpec(await mechanics("elite_kipchak_cumans"));
    assert.equal(kipchak.extraProjectileCount, 3);
    assert.deepEqual(kipchak.extraProjectileAttacks, { 3: 3 });
    assert.equal(kipchak.projectileHitMode, 0);
    assert.equal(kipchak.secondaryProjectileHitMode, 0);
  });


test("Thunderclap uses delayed melee bursts and an immediate hostile-only death blast",
  async () => {
    const grenadier = await mechanics("grenadier_jurchens");
    const paladin = await mechanics("paladin");
    assert.deepEqual({
      attack: grenadier.effects.delayed_impact_melee_attack,
      radius: grenadier.effects.delayed_impact_radius_tiles,
      delay: grenadier.effects.delayed_impact_delay_seconds,
      repeats: grenadier.effects.delayed_impact_repeat_count,
      interval: grenadier.effects.delayed_impact_repeat_interval_seconds,
      deathAttack: grenadier.effects.death_explosion_melee_attack,
      deathRadius: grenadier.effects.death_explosion_radius_tiles,
    }, {
      attack: 4,
      radius: 0.65,
      delay: 1.5,
      repeats: 3,
      interval: 1.5,
      deathAttack: 15,
      deathRadius: 0.75,
    });
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
    const oneShotGrenadier = {
      ...grenadier,
      reload_seconds: 100,
      ranged: {
        ...grenadier.ranged,
        accuracy_percent: 100,
        base_accuracy_percent: 100,
      },
    };
    const stationaryPaladin = {
      ...paladin,
      hp: 1000,
      speed_tiles_per_second: 0,
      attack_classes: { 4: 1 },
    };
    let world = createWorld({
      ratio: "thunderclap-impact-test",
      units: [
        spawn(1, 2, 4, oneShotGrenadier),
        spawn(2, 3, 8, stationaryPaladin),
      ],
    });
    for (let tick = 0; tick < 8 * 60; tick += 1) world = stepWorld(world);
    const primary = world.eventLog.filter((event) => (
      event.type === "damage" && event.actorId === 1 && event.targetId === 2
        && event.kind === "grenade-splash"
    ));
    const delayed = world.eventLog.filter((event) => (
      event.type === "damage" && event.actorId === 1 && event.targetId === 2
        && event.kind === "delayed-impact-explosion"
    ));
    assert.equal(primary.length, 1, "Thunderclap is not a second immediate grenade");
    assert.equal(delayed.length, 3);
    assert.deepEqual(delayed.map(({ amount }) => amount), [1, 1, 1]);
    assert.equal(delayed[0].tick - primary[0].tick, 90);
    assert.deepEqual(delayed.slice(1).map((hit, index) => hit.tick - delayed[index].tick),
      [90, 90]);

    // Lou Chuan uses two weapon channels. Thunderclap belongs to the
    // trebuchet/grenade channel only; its ordinary tower arrows must not
    // schedule the delayed blast.
    const modeGated = {
      ...oneShotGrenadier,
      effects: {
        ...oneShotGrenadier.effects,
        delayed_impact_weapon_mode: "trebuchet",
      },
    };
    const runWeaponMode = (weaponMode) => {
      let modeWorld = createWorld({
        ratio: `thunderclap-${weaponMode}-mode-test`,
        units: [
          spawn(21, 2, 4, {
            ...modeGated,
            ranged: { ...modeGated.ranged, weapon_mode: weaponMode },
          }),
          spawn(22, 3, 8, stationaryPaladin),
        ],
      });
      for (let tick = 0; tick < 8 * 60; tick += 1) modeWorld = stepWorld(modeWorld);
      return modeWorld.eventLog.filter((event) => (
        event.type === "damage" && event.actorId === 21 && event.targetId === 22
          && event.kind === "delayed-impact-explosion"
      ));
    };
    assert.equal(runWeaponMode("arrows").length, 0);
    assert.equal(runWeaponMode("trebuchet").length, 3);

    const fragileGrenadier = {
      ...grenadier,
      hp: 1,
      speed_tiles_per_second: 0,
      attack_classes: { 3: 1 },
    };
    const stationaryMeleePaladin = {
      ...paladin,
      speed_tiles_per_second: 0,
    };
    world = createWorld({
      ratio: "thunderclap-death-test",
      units: [
        spawn(10, 3, 4, stationaryMeleePaladin),
        spawn(11, 2, 4.4, fragileGrenadier),
      ],
    });
    for (let tick = 0; tick < 3 * 60; tick += 1) world = stepWorld(world);
    const death = world.eventLog.find((event) => (
      event.type === "death" && event.targetId === 11
    ));
    const deathBlast = world.eventLog.find((event) => (
      event.type === "damage" && event.actorId === 11 && event.targetId === 10
        && event.kind === "death-explosion"
    ));
    assert.ok(death);
    assert.ok(deathBlast);
    assert.equal(deathBlast.tick, death.tick);
    assert.equal(deathBlast.amount, 10);
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


test("Jian regeneration reverses its complete stat block at the 45 HP boundary", async () => {
  const jian = await mechanics("jian_swordsman_wu");
  const arbalester = await mechanics("arbalester");
  assert.equal(jian.effects.hp_regen, 30);
  assert.equal(jian.effects.hp_transform_threshold * jian.hp, 45);
  assert.equal(jian.effects.hp_transform_reversible, true);
  assert.deepEqual({
    attack: jian.attack_classes[4],
    pierceArmor: jian.armor_classes[3],
    speed: jian.speed_tiles_per_second,
    reload: jian.reload_seconds,
  }, { attack: 14, pierceArmor: 9, speed: 1.100000023841858, reload: 2 });
  assert.deepEqual({
    attack: jian.effects.transform_attacks[4],
    pierceArmor: jian.effects.transform_armors[3],
    speed: jian.effects.transform_movement_speed,
    reload: 1 / jian.effects.transform_attack_speed,
  }, { attack: 17, pierceArmor: 6, speed: 1.21, reload: 2 });

  const base = createUnitState({
    referenceId: 1,
    owner: 2,
    x: 4,
    y: 4,
    facing: 0,
    mechanics: jian,
    acquisitionRank: 0,
    acquisitionCount: 1,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
  const wounded = Object.freeze({ ...base, hp: 44.5 });
  const arbalesterActor = {
    mechanics: arbalester,
    specialState: { transformed: false, killAttackBonus: 0, nearbyAttackBonus: 0 },
  };
  const inertEnemyMechanics = {
    ...arbalester,
    speed_tiles_per_second: 0,
    attack_classes: { 3: 1 },
    reload_seconds: 1000,
  };
  const enemy = createUnitState({
    referenceId: 2,
    owner: 3,
    x: 14,
    y: 14,
    facing: 0,
    mechanics: inertEnemyMechanics,
    acquisitionRank: 0,
    acquisitionCount: 1,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
  let world = createWorld({ ratio: "jian-reversible-transform", units: [wounded, enemy] });
  world = stepWorld(world);
  let activeJian = world.units.find(({ referenceId }) => referenceId === 1);
  assert.equal(activeJian.specialState.transformed, true);
  assert.equal(activeJian.mechanics.speed_tiles_per_second, 1.21);
  assert.equal(calculateDamage(arbalesterActor, activeJian), 4,
    "the unshielded form immediately loses three pierce armor");

  while (world.tick < 61) world = stepWorld(world);
  activeJian = world.units.find(({ referenceId }) => referenceId === 1);
  assert.ok(Math.abs(activeJian.hp - 45.00833333333333) < 1e-9);
  assert.equal(activeJian.specialState.transformed, false);
  assert.equal(activeJian.mechanics.speed_tiles_per_second, jian.speed_tiles_per_second);
  assert.equal(calculateDamage(arbalesterActor, activeJian), 1,
    "restoring the shield restores the base pierce armor");
  assert.equal(world.eventLog.filter(({ type }) => type === "unit-transformed").length, 1);
  assert.equal(world.eventLog.filter(({ type }) => type === "unit-form-restored").length, 1);
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


test("Elite Ratha melee slash is a permanent 20% radial attack", async () => {
  const ratha = await mechanics("elite_ratha_(melee)_bengalis");
  const arbalester = await mechanics("arbalester");
  assert.deepEqual(trampleSpec(ratha), {
    shape: "radial",
    widthTiles: 0.5,
    damageFraction: 0.2,
  });

  const inertRatha = { ...ratha, speed_tiles_per_second: 0, reload_seconds: 1000 };
  const inertArbalester = {
    ...arbalester,
    ranged: null,
    attack_range_tiles: 0,
    speed_tiles_per_second: 0,
    attack_classes: { 4: 1 },
    reload_seconds: 1000,
  };
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
    ratio: "ratha-melee-slash-test",
    units: [
      spawn(1, 2, 5, 5, inertRatha),
      spawn(2, 3, 4.5, 5, inertArbalester),
      // The collision box begins 0.45 tiles from the Ratha, inside the
      // authored 0.5-tile radial slash.
      spawn(3, 3, 5, 5.65, inertArbalester),
      // This collision box begins 0.51 tiles away and must not be struck.
      spawn(4, 3, 5, 4.29, inertArbalester),
      // The same in-radius geometry is never friendly fire.
      spawn(5, 2, 5.65, 5, inertArbalester),
    ],
  });
  for (let tick = 0; tick < 180; tick += 1) {
    world = stepWorld(world);
    if (world.eventLog.some((event) => (
      event.type === "damage" && event.actorId === 1
    ))) break;
  }
  assert.deepEqual(world.eventLog.filter((event) => (
    event.type === "damage" && event.actorId === 1
  )).map(({ targetId, amount, kind }) => ({
    targetId, amount, kind: kind ?? "primary",
  })), [
    { targetId: 2, amount: 13, kind: "primary" },
    { targetId: 3, amount: 2.6, kind: "trample" },
  ]);
});


test("Elite Urumi uses Wootz armor bypass and charge-only ranged splash", async () => {
  const urumi = await mechanics("elite_urumi_swordsman_dravidians");
  const paladin = await mechanics("paladin");
  assert.equal(urumi.effects.ignores_melee_armor, 1);
  assert.deepEqual(meleeChargeSpec(urumi), {
    chargeType: 3,
    maxCharge: 15,
    rechargeRate: 0.75,
    rechargeSeconds: 20,
    attackBonus: 15,
    attackRangeTiles: 0.75,
    splashRadiusTiles: 0.75,
    splashDamageFraction: 0.5,
    windupTicks: 42,
    animationTicks: 84,
  });
  assert.deepEqual(trampleSpec(urumi), {
    shape: "radial",
    widthTiles: 0.75,
    damageFraction: 0.5,
    chargedOnly: true,
  });

  const actor = {
    mechanics: urumi,
    specialState: { transformed: false, killAttackBonus: 0, nearbyAttackBonus: 0 },
  };
  assert.equal(calculateDamage(actor, { mechanics: paladin, hp: paladin.hp }), 15,
    "Wootz ignores the Paladin's five base melee armor");
  const bonusArmorTarget = {
    mechanics: { armor_classes: { 4: 5, 21: 3 } },
    hp: 100,
  };
  assert.equal(calculateDamage(actor, bonusArmorTarget), 16,
    "Wootz does not erase armor against bonus attack classes");

  const inertPaladin = {
    ...paladin,
    hp: 1000,
    speed_tiles_per_second: 0,
    attack_classes: { 4: 1 },
    reload_seconds: 1000,
  };
  const inertUrumi = { ...urumi, speed_tiles_per_second: 0 };
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
  const firstSwing = (chargeReadyTick, targetX = 4.5, bystanderY = 5.55) => {
    const baseActor = spawn(1, 2, 5, 5, inertUrumi);
    const configuredActor = Object.freeze({
      ...baseActor,
      specialState: Object.freeze({
        ...baseActor.specialState,
        meleeChargeReadyTick: chargeReadyTick,
      }),
    });
    let world = createWorld({
      ratio: "urumi-area-charge-test",
      units: [
        configuredActor,
        spawn(2, 3, targetX, 5, inertPaladin),
        spawn(3, 3, 5, bystanderY, inertPaladin),
      ],
    });
    for (let tick = 0; tick < 180; tick += 1) {
      world = stepWorld(world);
      const hits = world.eventLog.filter((event) => (
        event.type === "damage" && event.actorId === 1
      ));
      if (hits.length > 0) return hits;
    }
    throw new Error("Elite Urumi did not land its first swing");
  };

  const chargedHits = firstSwing(0, 4, 6);
  assert.deepEqual(chargedHits.map(({ targetId, amount, kind }) => ({
    targetId, amount, kind: kind ?? "primary",
  })), [
    { targetId: 2, amount: 30, kind: "primary" },
    { targetId: 3, amount: 15, kind: "trample" },
  ]);
  const regularHits = firstSwing(10000);
  assert.deepEqual(regularHits.map(({ targetId, amount, kind }) => ({
    targetId, amount, kind: kind ?? "primary",
  })), [
    { targetId: 2, amount: 15, kind: "primary" },
  ], "an ordinary Urumi attack never emits the charge splash");
});
