import assert from "node:assert/strict";
import test from "node:test";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import { calculateDamage } from "../src/combat/attacks.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld, runWorld } from "../src/combat/world.js";
import { collisionRadius } from "../src/combat/targeting.js";
import { validateMechanicsProfile } from "../src/mechanics-schema.js";
import { advanceDefenseCharge, consumeDamageBlock, incomingDamageMultiplier } from "../src/combat/unit-defenses.js";

// Exercise the web application's committed profiles, never legacy fixtures.
const db = new DatabaseSync(fileURLToPath(new URL(
  "../../../data/golden/aoe2_reference_simulation.db", import.meta.url)), { readOnly: true });
const rows = db.prepare("SELECT u.civ_name,u.unit_slug,m.is_default,m.mechanics_json FROM ref_units u "
  + "JOIN ref_unit_mechanics m ON m.ref_unit_id=u.id").all();
db.close();
function profile(civ, slug) {
  const row = rows.find(r => r.civ_name === civ && r.unit_slug === slug && r.is_default);
  assert.ok(row, `${civ}/${slug}`);
  return JSON.parse(row.mechanics_json);
}
const champion = () => profile("Spanish", "champion");
const spawn = (id, owner, x, mechanics, hp = mechanics.hp) => Object.freeze({ ...createUnitState({
  referenceId: id, owner, x, y: 5, facing: 0, hp, mechanics,
  acquisitionRank: 0, acquisitionCount: 1,
  actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
}), hp });
const fast = mechanics => ({ ...mechanics, speed_tiles_per_second: 0,
  attack_delay_seconds: 0, reload_seconds: 0.1,
  attack_animation: { ...mechanics.attack_animation, seconds: 0.1 } });
const idle = mechanics => ({ ...mechanics, speed_tiles_per_second: 0,
  attack_delay_seconds: 1000, attack_animation: { ...mechanics.attack_animation, seconds: 1000 } });
function advance(world, ticks) {
  for (let i = 0; i < ticks; i++) world = stepWorld(world);
  return world;
}

test("all reference defensive and kill-income abilities reach web runtime profiles", () => {
  assert.equal(rows.length, 1031);
  for (const row of rows) validateMechanicsProfile(JSON.parse(row.mechanics_json));
  assert.equal(profile("Gurjaras", "elite_shrivamsha_rider_gurjaras").effects.dodge_shield_max, 7);
  assert.equal(profile("Jurchens", "elite_iron_pagoda_jurchens").effects.melee_block_recharge_seconds, 30);
  assert.equal(profile("Sicilians", "hussar").effects.bonus_damage_reduction, 0.4);
  assert.equal(profile("Bengalis", "elite_elephant").effects.bonus_damage_reduction, 0.25);
  assert.equal(profile("Khitans", "champion").effects.damage_reflect_percent, 0.25);
  assert.ok(rows.some(r => JSON.parse(r.mechanics_json).effects?.gold_per_kill > 0));
});

test("invalid resistance and shield definitions are rejected at the browser boundary", () => {
  const bad = champion();
  bad.effects.bonus_damage_reduction = 2;
  assert.throws(() => validateMechanicsProfile(bad), /bonus_damage_reduction/);
  const shield = profile("Gurjaras", "elite_shrivamsha_rider_gurjaras");
  delete shield.effects.dodge_shield_recharge;
  assert.throws(() => validateMechanicsProfile(shield), /recharge time/);
});

test("bonus resistance changes only bonus damage; rams retain negative native armor", () => {
  const halb = { mechanics: profile("Spanish", "halberdier") };
  assert.equal(calculateDamage(halb, { mechanics: profile("Sicilians", "hussar") }), 26);
  assert.equal(calculateDamage({ mechanics: { attack_classes: { 4: 20 } } },
    { mechanics: { armor_classes: { 4: 5 }, effects: { bonus_damage_reduction: 0.4 } } }), 15);
  assert.equal(calculateDamage({ mechanics: champion() },
    { mechanics: profile("Spanish", "siege_ram") }), 19);
  const target = { mechanics: { armor_classes: { 4: -2 } }, specialState: { armorStripped: 8 } };
  assert.equal(calculateDamage({ mechanics: { attack_classes: { 4: 10 } } }, target), 12);
});

test("group and kill attack bonuses are applied before armor and the one-damage floor", () => {
  const actor = { mechanics: { attack_classes: { 4: 10 } },
    specialState: { killAttackBonus: 4, nearbyAttackBonus: 2 } };
  assert.equal(calculateDamage(actor, { mechanics: { armor_classes: { 4: 20 } } }), 1);
  assert.equal(calculateDamage(actor, { mechanics: { armor_classes: { 4: 15 } } }), 1);
});

test("Composite Bowman and Leitis bypass only non-siege land targets", () => {
  for (const [mechanics, kind] of [[profile("Armenians", "elite_composite_bowman_armenians"), 3],
    [profile("Lithuanians", "elite_leitis_lithuanians"), 4]]) {
    const target = { hp: 100, mechanics: { armor_classes: { [kind]: 100 }, unit_type: 70, unit_traits: 0 } };
    assert.equal(calculateDamage({ mechanics }, target), mechanics.attack_classes[kind]);
    for (const excluded of [ { unit_type: 80 }, { unit_traits: 2 }, { armor_classes: { [kind]: 100, 20: 0 } } ]) {
      assert.equal(calculateDamage({ mechanics }, { ...target, mechanics: { ...target.mechanics, ...excluded } }), 1);
    }
  }
});

test("Monaspa counts seven other own qualifying units per tier within 15 tiles", () => {
  const monaspa = profile("Georgians", "elite_monaspa_georgians");
  const knight = profile("Georgians", "paladin");
  for (const [count, expected] of [[6, 0], [7, 1], [13, 1], [14, 2], [28, 4], [35, 4]]) {
    const units = [spawn(1, 2, 5, monaspa),
      ...Array.from({ length: count }, (_, i) => spawn(i + 2, 2, 20, knight)),
      spawn(100, 3, 6, monaspa), spawn(101, 2, 20.01, monaspa), spawn(102, 2, 6, champion())];
    const world = createWorld({ ratio: "unit-aura", units });
    assert.equal(world.units[0].specialState.nearbyAttackBonus, expected, `${count} allies`);
  }
});

test("Shrivamsha blocks seven rapid projectiles, but neither melee nor fractional shield charge", () => {
  const mechanics = profile("Gurjaras", "elite_shrivamsha_rider_gurjaras");
  const unit = { mechanics, specialState: { dodgeShieldCharges: 7 } };
  const hit = { kind: "charge-projectile" };
  for (let n = 0; n < 7; n++) assert.equal(consumeDamageBlock(unit, hit, 0), "projectile-shield");
  assert.equal(consumeDamageBlock(unit, hit, 0), null);
  for (let n = 0; n < 171; n++) advanceDefenseCharge(unit);
  assert.equal(consumeDamageBlock(unit, hit, 171), null);
  advanceDefenseCharge(unit);
  assert.equal(consumeDamageBlock(unit, hit, 172), "projectile-shield");
  assert.equal(consumeDamageBlock(unit, { triggersOnHit: true }, 172), null);

  let world = createWorld({ ratio: "projectile-shield", units: [
    spawn(1, 2, 2, fast(profile("Chinese", "arbalester"))), spawn(2, 3, 6, idle(mechanics))] });
  world = advance(world, 100);
  const hits = world.eventLog.filter(e => e.targetId === 2 && ["damage", "damage-blocked"].includes(e.type));
  assert.deepEqual(hits.slice(0, 8).map(e => e.type), [...Array(7).fill("damage-blocked"), "damage"]);
  assert.equal(hits[7].amount, 5);
});

test("Iron Pagoda recharges its ordinary melee block after 30 seconds", () => {
  const unit = { owner: 2, mechanics: profile("Jurchens", "elite_iron_pagoda_jurchens"), specialState: {} };
  assert.equal(consumeDamageBlock(unit, { kind: "ranged-projectile" }, 0), null);
  assert.equal(consumeDamageBlock(unit, { triggersOnHit: true }, 0), "melee-block");
  assert.equal(consumeDamageBlock(unit, { triggersOnHit: true }, 1799), null);
  for (const kind of ["death-explosion", "delayed-impact-explosion", "trample", "melee-charge"]) {
    assert.equal(consumeDamageBlock(unit, { kind }, 1800), null);
  }
  assert.equal(consumeDamageBlock(unit, { triggersOnHit: true }, 1800), "melee-block");
  assert.equal(consumeDamageBlock(unit, { kind: "bleed" }, 3600), null);
  assert.equal(incomingDamageMultiplier(unit, { owner: 2 }), 0.5);
  assert.equal(incomingDamageMultiplier(unit, { owner: 3 }), 1);
});

test("a blocked regular strike still takes special charge damage", () => {
  const coustillier = fast(profile("Burgundians", "elite_coustillier_burgundians"));
  const pagoda = idle(profile("Jurchens", "elite_iron_pagoda_jurchens"));
  const x = 4 + collisionRadius({ mechanics: coustillier }) + collisionRadius({ mechanics: pagoda }) + 0.05;
  let world = createWorld({ ratio: "blocked-charge", units: [spawn(1, 2, 4, coustillier), spawn(2, 3, x, pagoda)] });
  world = stepWorld(world);
  assert.ok(world.events.some(e => e.type === "damage-blocked"));
  assert.equal(world.units[1].hp, pagoda.hp - coustillier.effects.charge_attack_melee);
  assert.ok(world.units[0].specialState.meleeChargeReadyTick > world.tick);
  world = advance(world, 12);
  assert.ok(world.eventLog.some(e => e.type === "damage" && e.charged && e.targetId === 2));
  assert.ok(world.units[0].specialState.meleeChargeReadyTick > world.tick);
});

test("military kill income is credited once in immutable unit state", () => {
  const original = rows.map(r => JSON.parse(r.mechanics_json))
    .find(p => !p.ranged && p.effects?.gold_per_kill > 0);
  assert.ok(original);
  const actor = fast(original);
  const target = idle(champion());
  const x = 4 + collisionRadius({ mechanics: actor }) + collisionRadius({ mechanics: target }) + 0.05;
  let world = createWorld({ ratio: "kill-income", units: [spawn(1, 2, 4, actor), spawn(2, 3, x, target, 1)] });
  world = advance(world, 10);
  assert.equal(world.units[0].specialState.resourcesGained.gold, original.effects.gold_per_kill);
  assert.ok(Object.isFrozen(world.units[0].specialState.resourcesGained));
  const ranged = rows.map(r => JSON.parse(r.mechanics_json))
    .find(p => p.ranged && p.effects?.gold_per_kill > 0);
  assert.ok(ranged);
  world = createWorld({ ratio: "posthumous-income", units: [spawn(1, 2, 2, fast(ranged)),
    spawn(2, 3, 2 + ranged.attack_range_tiles - 0.5, idle(champion()), 1)] });
  for (let i = 0; i < 180 && !world.projectiles?.length; i++) world = stepWorld(world);
  assert.ok(world.projectiles?.length);
  const deadShooter = { ...world.units[0], hp: 0, alive: false, action: "dead",
    pursuitTargetId: null, engagedTargetId: null, attackTargetId: null };
  world = Object.freeze({ ...world, units: Object.freeze([deadShooter, ...world.units.slice(1)]) });
  world = advance(world, 120);
  assert.equal(world.units[1].alive, false);
  assert.equal(world.units[0].specialState.resourcesGained.gold, ranged.effects.gold_per_kill);
});

test("Khitan reflection applies to melee hits without reflection recursion", () => {
  let world = createWorld({ ratio: "reflection", units: [
    spawn(1, 2, 4, fast(profile("Khitans", "champion"))),
    spawn(2, 3, 4.4, idle(profile("Khitans", "champion")))] });
  world = stepWorld(world);
  const hits = world.events.filter(e => e.type === "damage");
  assert.equal(hits.length, 2);
  assert.equal(hits[1].kind, "damage-reflection");
  assert.equal(hits[1].amount, hits[0].amount * 0.25);
  assert.equal(world.units[0].hp, world.units[0].mechanics.hp - hits[1].amount);
});

test("Tupi death refunds use the per-physical-unit cost exactly once", () => {
  for (const slug of ["elite_blackwood_archer_tupi", "elite_ibirapema_warrior_tupi"]) {
    const target = profile("Tupi", slug);
    const attacker = fast(champion());
    const x = 4 + collisionRadius({ mechanics: attacker }) + collisionRadius({ mechanics: target }) + 0.05;
    let world = createWorld({ ratio: "death-refund", units: [spawn(1, 2, 4, attacker),
      spawn(2, 3, x, idle(target), 1)] });
    world = advance(world, 20);
    assert.equal(world.units[1].alive, false);
    for (const resource of ["food", "wood", "gold"]) {
      assert.equal(world.units[1].specialState.resourcesGained[resource], 0.15 * target.cost[resource]);
    }
  }
});

test("Tiger Cavalry gains maximum and current HP on its first four kills", () => {
  const tiger = fast(profile("Wei", "elite_tiger_cavalry_wei"));
  let world = createWorld({ ratio: "veterancy", units: [spawn(1, 2, 4, tiger),
    ...Array.from({ length: 6 }, (_, i) => spawn(i + 2, 3, 4.5, idle(champion()), 1))] });
  world = advance(world, 120);
  assert.equal(world.units.filter(u => u.owner === 3 && u.alive).length, 0);
  const unit = world.units[0];
  assert.equal(unit.maxHp, tiger.hp + 40);
  assert.equal(unit.hp, tiger.hp + 40);
  assert.equal(unit.specialState.killAttackBonus, 4);
});

test("Guecha heal requires a Guecha death within six tiles and expires at full health", () => {
  const guecha = profile("Muisca", "elite_guecha_warrior_muisca");
  for (const [victim, x, expected] of [[guecha, 7.5, 5], [champion(), 7.5, 0], [guecha, 8.01, 0]]) {
    let world = createWorld({ ratio: "death-heal", units: [
      spawn(1, 2, 2, idle(guecha), 40), spawn(2, 2, x, idle(victim), 1),
      spawn(3, 3, x + 0.4, fast(champion()))] });
    world = advance(world, 181);
    assert.ok(Math.abs(world.units[0].hp - (40 + expected)) < 1e-8);
  }
  let world = createWorld({ ratio: "unused-heal", units: [spawn(1, 2, 2, idle(guecha)),
    spawn(2, 2, 7.5, idle(guecha), 1), spawn(3, 3, 7.9, fast(champion()))] });
  world = advance(world, 200);
  const wounded = { ...world.units[0], hp: 40 };
  world = Object.freeze({ ...world, units: Object.freeze([wounded, ...world.units.slice(1)]) });
  world = advance(world, 60);
  assert.equal(world.units[0].hp, 40);
});

test("Liao Dao applies exactly nine bleed damage to organic land targets, not mechanical siege", () => {
  const attacker = { ...fast(profile("Khitans", "elite_liao_dao_khitans")), reload_seconds: 1000 };
  for (const [target, expected] of [[champion(), 9], [profile("Spanish", "siege_ram"), 0],
    [profile("Khitans", "mounted_trebuchet_khitans"), 9]]) {
    const x = 4 + collisionRadius({ mechanics: attacker }) + collisionRadius({ mechanics: target }) + 0.05;
    let world = createWorld({ ratio: "bleed", units: [spawn(1, 2, 4, attacker),
      spawn(2, 3, x, { ...idle(target), hp: 1000 })] });
    world = advance(world, 190);
    const damage = world.eventLog.filter(e => e.type === "damage" && e.kind === "bleed")
      .reduce((sum, e) => sum + e.amount, 0);
    assert.ok(Math.abs(damage - expected) < 1e-8, `${target.unit_slug}: ${damage}`);
  }
});

test("Ordo is melee-only, preserves fractional rates, and heals through attack reload", () => {
  assert.equal(profile("Khitans", "hussar").effects.hp_regen_in_combat, 112.5);
  for (const slug of ["heavy_cav_archer", "mounted_trebuchet_khitans"]) {
    assert.equal(profile("Khitans", slug).effects.hp_regen_in_combat, undefined);
  }
  const hussar = { ...fast(profile("Khitans", "hussar")), reload_seconds: 2 };
  let world = createWorld({ ratio: "ordo", units: [
    spawn(1, 2, 4, hussar, 30), spawn(2, 3, 4.5, idle(champion()))] });
  world = advance(world, 60);
  assert.equal(world.units[0].action, "reload");
  assert.ok(Math.abs(world.units[0].hp - 31.875) < 1e-8);
  const hp = world.units[0].hp;
  const distant = { ...world.units[1], x: 12 };
  world = { ...world, units: [world.units[0], distant] };
  world = advance(world, 60);
  assert.equal(world.units[0].hp, hp, "no after-combat healing window");
  // A moving unit has a nearby target and is reloading, but earns no regen.
  const mobile = profile("Khitans", "hussar");
  world = createWorld({ ratio: "ordo-moving", units: [spawn(1, 2, 4, mobile, 30),
    spawn(2, 3, 9, idle(champion()))] });
  const moving = { ...world.units[0], action: "reload", pursuitTargetId: 2,
    actionTimers: { ...world.units[0].actionTimers, reload: 120 } };
  world = stepWorld({ ...world, units: [moving, world.units[1]] });
  assert.ok(world.units[0].x > 4);
  assert.equal(world.units[0].hp, 30);
});

test("Centurion aura affects own militia only, never stacks, and disappears outside range or on death", () => {
  const centurion = idle(profile("Romans", "elite_centurion_romans"));
  const legionary = profile("Romans", "champion");
  let world = createWorld({ ratio: "centurion", map: { width: 40, height: 20, obstacles: [] }, units: [
    spawn(1, 2, 4, idle(legionary)), spawn(2, 2, 16, centurion),
    spawn(3, 2, 16, centurion), spawn(4, 3, 4, idle(legionary)),
    spawn(5, 2, 4, idle(profile("Romans", "halberdier")))] });
  assert.equal(world.units[0].specialState.auraMoveMultiplier, 1.15);
  assert.equal(world.units[0].specialState.auraAttackRateMultiplier, 1.2);
  assert.equal(world.units[3].specialState.auraAttackRateMultiplier, 1);
  assert.equal(world.units[4].specialState.auraAttackRateMultiplier, 1);
  world = stepWorld({ ...world, units: world.units.map(u => u.referenceId === 2
    ? { ...u, x: 16.01 } : u.referenceId === 3 ? { ...u, alive: false, hp: 0 } : u) });
  assert.equal(world.units[0].specialState.auraAttackRateMultiplier, 1);
  assert.equal(world.units[0].mechanics.speed_tiles_per_second, 0);
  // Rate, not a subtraction of 20% from the reload period.
  const attacker = { ...fast(legionary), reload_seconds: 2 };
  world = createWorld({ ratio: "centurion-cadence", units: [spawn(1, 2, 4, attacker),
    spawn(2, 3, 4.5, idle({ ...champion(), hp: 1000 })), spawn(3, 2, 10, centurion)] });
  world = advance(world, 205);
  const starts = world.eventLog.filter(e => e.type === "attack-start" && e.actorId === 1);
  assert.ok(starts.length >= 3);
  assert.equal(starts[1].tick - starts[0].tick, 100);
});

test("shared fighting income pays fractional gold during animation, excludes reload and buildings", () => {
  for (const [civ, slug, rate] of [["Tatars", "elite_keshik_tatars", 0.5],
    ["Byzantines", "elite_varangian_guard", 0.015908999368548393 * 50],
    ["Varangians", "elite_varangian_guard", 0.015908999368548393 * 50 * 1.333299994468689]]) {
    const actor = { ...profile(civ, slug), charge: null, speed_tiles_per_second: 0,
      attack_delay_seconds: 0, attack_animation: { seconds: 1 }, reload_seconds: 2 };
    for (const [unitType, expected] of [[70, rate], [80, 0]]) {
      let world = createWorld({ ratio: "fighting-income", units: [spawn(1, 2, 4, actor),
        spawn(2, 3, 4.5, idle({ ...champion(), unit_type: unitType, hp: 10000 }))] });
      world = advance(world, 120);
      assert.ok(Math.abs(world.units[0].specialState.resourcesGained.gold - expected) < 1e-8);
      assert.ok(Object.isFrozen(world.units[0].specialState.resourcesGained));
      const dead = { ...world.units[1], alive: false, hp: 0 };
      world = advance({ ...world, units: [world.units[0], dead] }, 120);
      assert.ok(Math.abs(world.units[0].specialState.resourcesGained.gold - expected) < 1e-8);
    }
  }
});

test("Gothikon recharges both spent slots independently and releases axes in rapid pairs", () => {
  const guard = { ...profile("Varangians", "elite_varangian_guard"), speed_tiles_per_second: 0 };
  let world = createWorld({ ratio: "independent-charges", units: [spawn(1, 2, 4, guard),
    spawn(2, 3, 6, idle({ ...champion(), hp: 10000 }))] });
  world = advance(world, 2100);
  const shots = world.eventLog.filter(e => e.type === "charge-volley" && e.actorId === 1);
  assert.equal(shots.length, 4);
  assert.equal(shots[1].tick - shots[0].tick, 96);
  assert.equal(shots[3].tick - shots[2].tick, 96);
  assert.ok(shots[2].tick - shots[0].tick >= 1800);
  assert.ok(shots[2].tick - shots[0].tick < 1900);
  assert.ok(Object.isFrozen(world.units[0].specialState.chargeReadyTicks));
});

test("runWorld waits for the last Konnik's foot form, in both snapshot modes", () => {
  for (const retainSnapshots of [true, false]) {
    const konnik = idle(profile("Bulgarians", "elite_konnik_bulgarians"));
    const killer = { ...fast(champion()), reload_seconds: 1000 };
    const world = createWorld({ ratio: "konnik-victory", units: [spawn(1, 2, 4, konnik, 1),
      spawn(2, 3, 4.5, killer, 1)] });
    const result = runWorld(world, { maxTicks: 1500, retainSnapshots });
    assert.equal(result.winner, 2, "foot form wins after mounted form dies");
    assert.ok(result.events.some(e => e.type === "unit-dismounted"));
    assert.ok(result.ticks > 180);
  }
});
