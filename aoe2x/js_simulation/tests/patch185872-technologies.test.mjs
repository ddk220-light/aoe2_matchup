import assert from "node:assert/strict";
import test from "node:test";
import { calculateDamage, chargeProjectileDamage } from "../src/combat/attacks.js";
import { readFile } from "node:fs/promises";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld } from "../src/combat/world.js";

function jom(hp, maxHp = 75) {
  return { hp, maxHp, mechanics: { hp: maxHp, attack_classes: { 4: 13 }, effects: {
    missing_hp_attack_per_step: 1, missing_hp_attack_step: 0.1,
  } } };
}
const target = armor => ({ hp: 100, maxHp: 100, mechanics: { armor_classes: { 4: armor } } });

test("Hamask uses the attacker's lost HP, including partial HP and healing", () => {
  // Effects.xs function30/task160: +1 attack per 10% own HP lost.
  // First three amounts independently observed in Jomsviking/Jaguar frames.
  for (const [hp, expected] of [[75, 8], [47, 11], [3, 17], [65.5, 9], [75, 8]]) {
    assert.equal(calculateDamage(jom(hp), target(5)), expected, `HP ${hp}`);
  }
  assert.equal(calculateDamage(jom(75, 100), target(5)), 10);
  assert.equal(calculateDamage(jom(75), { ...target(5), hp: 1 }), 8);
});

test("Hamask modifies base attack before armor and the final one-damage minimum", () => {
  assert.equal(calculateDamage(jom(75), target(13)), 1);
  assert.equal(calculateDamage(jom(59), target(13)), 2);
  assert.equal(calculateDamage(jom(43), target(13)), 4);
  assert.equal(calculateDamage(jom(3), target(100)), 1);
  const actor = jom(37);
  actor.mechanics.attack_classes[5] = 27;
  const elephant = target(1);
  elephant.mechanics.armor_classes[5] = 0;
  assert.equal(calculateDamage(actor, elephant), 44, "bonus classes do not get multiplied");
});

test("smart-mode-8 charge uses carrier attack and current HP-dependent modifiers", () => {
  const actor = jom(47);
  const spec = { projectileAttacks: { 4: 13 }, inheritsUnitAttack: true, ignoresArmor: false };
  assert.equal(chargeProjectileDamage(spec, target(5), actor), 11);
  actor.hp = 75;
  assert.equal(chargeProjectileDamage(spec, target(5), actor), 8);
});

const infantry = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url), "utf8"));

test("Shield Wall counts other living own infantry within seven tiles, capped at three armor", () => {
  for (const [others, armor] of [[14, 0], [15, 1], [29, 1], [30, 2], [44, 2], [45, 3], [60, 3]]) {
    const mechanics = { ...infantry, unit_class: 6, effects: {
      nearby_infantry_armor_step: 15, nearby_infantry_armor_max: 3,
      nearby_infantry_armor_radius: 7,
    } };
    const make = (id, owner, x, profile = mechanics) => createUnitState({
      referenceId: id, owner, x, y: 10, facing: 0, mechanics: profile,
    });
    const units = [make(1, 2, 10), ...Array.from({ length: others }, (_, i) => make(i + 2, 2, 11))];
    units.push(make(100, 3, 11), make(101, 2, 17.1), make(102, 2, 11, { ...mechanics, unit_class: 12 }));
    units.push({ ...make(103, 2, 11), alive: false, hp: 0 });
    const world = createWorld({ ratio: "1v1", units });
    const defender = world.units.find(u => u.referenceId === 1);
    assert.equal(defender.specialState.nearbyArmorBonus, armor, `${others} other infantry`);
    assert.equal(calculateDamage({ mechanics: { attack_classes: { 4: 20 } } }, defender), 20 - infantry.armor_classes[4] - armor);
    assert.equal(calculateDamage({ mechanics: { attack_classes: { 3: 20 } } }, defender), 20 - infantry.armor_classes[3] - armor);
    assert.equal(chargeProjectileDamage({ projectileAttacks: { 3: 20 }, ignoresArmor: false }, defender),
      20 - infantry.armor_classes[3] - armor);
  }
});
