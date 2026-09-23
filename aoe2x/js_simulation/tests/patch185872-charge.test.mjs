import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { chargeSpec, chargeCanTarget, chargeProjectileDamage } from "../src/combat/attacks.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";
import { estimateTimeToKill } from "../src/combat/matchup-summary.js";

const base = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url), "utf8"));
const jom = { ...base, charge: {
  charge_type: 6, max_charge: 1, recharge_rate: 100000, projectile_count: 1,
  projectile_speed_tiles_per_second: 4, projectile_attacks: {},
  attack_range_tiles: 3, windup_seconds: 1, charge_animation: { seconds: 1.8 },
  target_filter: "buildings_and_ships",
} };

test("Jom torch does not stop pursuit or replace melee against land soldiers", () => {
  const spec = chargeSpec(jom);
  assert.equal(chargeCanTarget(spec, { mechanics: base }), false);
  const units = [jom, base].map((mechanics, i) => createUnitState({
    referenceId: i + 1, owner: i + 2, x: 4 + i * 2, y: 4, facing: 0,
    mechanics, acquisitionRank: i, acquisitionCount: 2,
  }));
  let world = createWorld({ ratio: "1v1", units });
  for (let i = 0; i < 420; i += 1) world = stepWorld(world);
  assert.equal(world.eventLog.some(e => e.type === "charge-volley"), false);
  assert.ok(world.eventLog.some(e => e.type === "damage" && e.actorId === 1));
});

test("unvalidated torch damage fails explicitly for its eligible targets", () => {
  const ship = { mechanics: { unit_type: 70, unit_traits: 2, armor_classes: { 3: 0, 4: 0, 16: 0 } } };
  const building = { mechanics: { unit_type: 80, unit_traits: 0, armor_classes: { 3: 0, 4: 0, 11: 0 } } };
  const spec = chargeSpec(jom);
  assert.equal(chargeCanTarget(spec, ship), true);
  assert.equal(chargeCanTarget(spec, building), true);
  assert.throws(() => chargeProjectileDamage(spec, ship), /unresolved charge projectile attacks/);
});

test("Houfnice siege armor does not make it a ship or a torch target", () => {
  // Candidate master1709: armor class20 is siege, not ships (class16).
  const houfnice = { mechanics: { unit_type: 70, unit_traits: 0,
    armor_classes: { 3: 5, 4: 2, 20: 0 } } };
  assert.equal(chargeCanTarget(chargeSpec(jom), houfnice), false);
});

test("land matchup estimate uses the same charge target restriction", () => {
  assert.equal(estimateTimeToKill(jom, base), estimateTimeToKill(base, base));
});

test("Gothikon spends one axe at a time and can fire again after one 30-second recharge", () => {
  const guard = { ...base, hp: 10000, speed_tiles_per_second: 0,
    reload_seconds: 1.6, charge: { ...jom.charge, max_charge: 2,
      recharge_rate: 1 / 30, charge_cost: 1, projectile_count: 1,
      projectile_attacks: { 4: 13 }, target_filter: "non_siege_units",
      windup_seconds: 0.875, charge_animation: { seconds: 1.5 } } };
  const victim = { ...base, hp: 10000, speed_tiles_per_second: 0 };
  const units = [guard, victim].map((mechanics, i) => createUnitState({
    referenceId: i + 1, owner: i + 2, x: 4 + i * 2, y: 4, facing: 0, mechanics,
    actionTimers: { acquire: 0, reload: 0, windup: 0, swing: 0 },
  }));
  let world = createWorld({ ratio: "1v1", units });
  for (let i = 0; i < 2050; i++) world = stepWorld(world);
  const shots = world.eventLog.filter(e => e.type === "charge-volley" && e.actorId === 1);
  assert.equal(shots.length, 3);
  assert.equal(shots[1].tick - shots[0].tick, 96, "uses sourced 1.6-second weapon cycle");
  assert.ok(shots[2].tick - shots[0].tick >= 1800);
  assert.ok(shots[2].tick - shots[0].tick < 1900);
  assert.ok(shots.every(e => e.projectiles === 1));
  assert.equal(chargeCanTarget(chargeSpec(guard), { mechanics: { unit_type: 80 } }), false);
  assert.equal(chargeCanTarget(chargeSpec(guard), { mechanics: { armor_classes: { 20: 0 } } }), false);
});
