import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { calculateDamage } from "../src/combat/attacks.js";


async function mechanics(name) {
  return JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${name}`, import.meta.url),
    "utf8",
  ));
}

function combatant(unitMechanics) {
  return { mechanics: unitMechanics };
}

test("Royal Heirs reduces incoming mounted melee and ranged damage by three", async () => {
  const shotel = combatant(await mechanics("elite_shotel_warrior_ethiopians_imperial.json"));
  const plainShotel = combatant({
    ...shotel.mechanics,
    damage_reduction_by_attacker_category: null,
  });
  for (const name of [
    "paladin_spanish_imperial.json",
    "heavy_cav_archer_saracens_imperial.json",
  ]) {
    const attacker = combatant(await mechanics(name));
    assert.equal(
      calculateDamage(attacker, shotel),
      Math.max(1, calculateDamage(attacker, plainShotel) - 3),
      name,
    );
  }
});

test("Royal Heirs does not become generic armor against foot units", async () => {
  const shotel = combatant(await mechanics("elite_shotel_warrior_ethiopians_imperial.json"));
  const plainShotel = combatant({
    ...shotel.mechanics,
    damage_reduction_by_attacker_category: null,
  });
  for (const name of [
    "champion_chinese_imperial.json",
    "arbalester_chinese_imperial.json",
  ]) {
    const attacker = combatant(await mechanics(name));
    assert.equal(calculateDamage(attacker, shotel), calculateDamage(attacker, plainShotel), name);
  }
});

test("conditional reduction follows bonus calculation and preserves minimum damage", () => {
  const mounted = combatant({
    attack_classes: { "4": 6, "12": 5, "39": -3 },
  });
  const reduced = combatant({
    armor_classes: { "4": 2, "12": 1 },
    damage_reduction_by_attacker_category: { mounted: 3 },
  });
  const ordinary = combatant({
    armor_classes: { "4": 2, "12": 1 },
    damage_reduction_by_attacker_category: null,
  });
  assert.equal(calculateDamage(mounted, ordinary), 8, "base 4 + bonus 4");
  assert.equal(calculateDamage(mounted, reduced), 5, "subtract after bonus resolution");

  const weakMounted = combatant({ attack_classes: { "4": 3, "39": -3 } });
  const armored = combatant({
    armor_classes: { "4": 2 },
    damage_reduction_by_attacker_category: { mounted: 3 },
  });
  assert.equal(calculateDamage(weakMounted, armored), 1, "flat reduction cannot bypass floor");
});
