import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { calculateDamage } from "../src/combat/attacks.js";
import { runFight } from "../src/fight.js";


const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

async function mechanics(name) {
  return JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${name}`, import.meta.url),
    "utf8",
  ));
}

test("Gbeto and Throwing Axeman projectiles resolve against melee armor", async () => {
  for (const name of [
    "elite_gbeto_malians_imperial.json",
    "elite_throwing_axeman_franks_imperial.json",
  ]) {
    const attacker = { mechanics: await mechanics(name) };
    const lowPierce = { mechanics: { armor_classes: { "4": 3, "3": 0 } } };
    const highPierce = { mechanics: { armor_classes: { "4": 3, "3": 100 } } };
    const higherMelee = { mechanics: { armor_classes: { "4": 6, "3": 0 } } };
    assert.equal(calculateDamage(attacker, lowPierce), calculateDamage(attacker, highPierce),
      `${name} ignores pierce armor`);
    assert.ok(calculateDamage(attacker, higherMelee) < calculateDamage(attacker, lowPierce),
      `${name} is reduced by melee armor`);
  }
});

for (const slug of ["elite_gbeto", "elite_throwing_axeman"]) {
  test(`${slug} uses the generic cohesive move-fire cycle`, async () => {
    const fight = await runFight(root, {
      side2Slug: slug,
      n2: 3,
      side3Slug: "champion",
      n3: 5,
    });
    assert.equal(fight.family, "kite");
    assert.equal(fight.kiteOwner, 2);
    const events = fight.snapshots.flatMap(({ events: entries }) => entries);
    assert.ok(events.some(({ type, actorId }) => (
      type === "kite-move" && fight.unitIndex[actorId]?.owner === 2
    )), "the ranged formation must receive a move order");
    assert.ok(events.some(({ type, kind, actorId }) => (
      type === "damage"
      && kind === "ranged-projectile"
      && fight.unitIndex[actorId]?.owner === 2
    )), "the moving formation must still land projectile damage");
  });
}
