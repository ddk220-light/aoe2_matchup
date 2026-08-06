import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { isWithinStopRange } from "../src/combat/attacks.js";
import { isWithinReach } from "../src/combat/targeting.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const championMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url), "utf8"));
const paladinMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/paladin_spanish_imperial.json", import.meta.url), "utf8"));
const elephantMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_battle_elephant_burmese_imperial.json", import.meta.url), "utf8"));
const lancerMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_steppe_lancer_cumans_imperial.json", import.meta.url), "utf8"));


function unit({ referenceId, owner, x, y, mechanics, hp = mechanics.hp }) {
  return {
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    unitMaster: mechanics.unit_master,
    hp,
    alive: true,
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
    action: "idle",
    actionTimers: { windup: 0, reload: 0 },
  };
}


test("the lancer's movement stop is collision gap <= range, range-0 units keep 0.1", () => {
  const lancer = unit({ referenceId: 1, owner: 2, x: 4, y: 4, mechanics: lancerMechanics });
  // Collision half-extents 0.25 + 0.2: center 1.45 is exactly gap 1.0.
  const championAtStop = unit({ referenceId: 2, owner: 3, x: 5.45, y: 4, mechanics: championMechanics });
  const championBeyond = unit({ referenceId: 3, owner: 3, x: 5.5, y: 4, mechanics: championMechanics });

  assert.equal(isWithinStopRange(lancer, championAtStop), true);
  assert.equal(isWithinStopRange(lancer, championBeyond), false);
  // The range-0 champion at the same separation is nowhere near ITS stop range.
  assert.equal(isWithinStopRange(championAtStop, lancer), false);
});


test("attack reach uses outline boxes and Chebyshev geometry", () => {
  const lancer = unit({ referenceId: 1, owner: 2, x: 4, y: 4, mechanics: lancerMechanics });
  // Outline half-extents 0.4 + 0.2: center 1.7 is exactly outline gap 1.1.
  const atReach = unit({ referenceId: 2, owner: 3, x: 5.7, y: 4, mechanics: championMechanics });
  const beyond = unit({ referenceId: 3, owner: 3, x: 5.76, y: 4, mechanics: championMechanics });
  // Chebyshev: the same 1.7 on BOTH axes is still in reach (Euclid center 2.40).
  const diagonal = unit({ referenceId: 4, owner: 3, x: 5.7, y: 5.7, mechanics: championMechanics });

  assert.equal(isWithinReach(lancer, atReach), true);
  assert.equal(isWithinReach(lancer, beyond), false);
  assert.equal(isWithinReach(lancer, diagonal), true);

  // Range-0 units use their outline too: the paladin (collision 0.25,
  // outline 0.4) reaches a lancer from collision gap 0.35 = outline gap 0.05.
  const paladin = unit({ referenceId: 5, owner: 3, x: 4.85, y: 4, mechanics: paladinMechanics });
  assert.equal(isWithinReach(paladin, lancer), true);
});


test("a back-line lancer fights over the front line from outline reach", () => {
  // Champion walks in against lancer A; blocked lancer B lands hits from the
  // second row, where the old collision-based reach could never fire.
  let world = createWorld({
    ratio: "steppe-stack-test",
    units: [
      unit({ referenceId: 1, owner: 2, x: 4, y: 4, mechanics: championMechanics }),
      unit({ referenceId: 2, owner: 3, x: 5.45, y: 4, mechanics: lancerMechanics }),
      unit({ referenceId: 3, owner: 3, x: 6.45, y: 4, mechanics: lancerMechanics }),
    ],
  });
  for (let i = 0; i < 900; i += 1) {
    world = stepWorld(world);
    if (!world.units.find(({ referenceId }) => referenceId === 1).alive) break;
  }
  const champion = world.units.find(({ referenceId }) => referenceId === 1);
  assert.equal(champion.alive, false, "two lancers must kill the champion");
  const hitsByA = world.eventLog.filter((e) => e.type === "damage" && e.actorId === 2);
  const hitsByB = world.eventLog.filter((e) => e.type === "damage" && e.actorId === 3);
  assert.ok(hitsByA.length > 0, "front lancer must land hits");
  assert.ok(hitsByB.length > 0, "back-line lancer must land hits");

  const firstB = hitsByB[0];
  const snapshot = world.snapshots.find(({ tick }) => tick === firstB.tick);
  const attacker = snapshot.units.find(({ referenceId }) => referenceId === 3);
  const victim = snapshot.units.find(({ referenceId }) => referenceId === 1);
  const collisionGap = Math.max(
    Math.abs(attacker.x - victim.x), Math.abs(attacker.y - victim.y)) - 0.25 - 0.2;
  assert.ok(attacker.x > 5.45 + 0.4, "back lancer must still be behind the front lancer");
  assert.ok(collisionGap > 0.15, "the hit must come from beyond old collision reach");
});


test("outline reach across the spawn gap never fires before acquisition", () => {
  // Lancer and elephant spawn at Chebyshev 2.0 = outline gap exactly 1.1:
  // eligible from tick one, but the tapes show no swing before the engine's
  // acquisition delay has run.
  let world = createWorld({
    ratio: "steppe-acquire-test",
    units: [
      createUnitState({
        referenceId: 1, owner: 2, x: 4, y: 4, facing: 0,
        mechanics: lancerMechanics, acquisitionRank: 0, acquisitionCount: 2,
      }),
      createUnitState({
        referenceId: 2, owner: 3, x: 6, y: 4, facing: 0,
        mechanics: elephantMechanics, acquisitionRank: 1, acquisitionCount: 2,
      }),
    ],
  });
  for (let i = 0; i < 240; i += 1) world = stepWorld(world);
  const starts = world.eventLog.filter((e) => e.type === "attack-start");
  assert.ok(starts.length > 0, "the fight must start");
  // Rank 0 of 2 acquires at 0.952 + (1/3)(0.756) = 1.204 s -> tick 72.
  assert.ok(starts[0].tick >= 70, `first swing at tick ${starts[0].tick} precedes acquisition`);

  // And the approaching lancer's first swing comes only after it has closed
  // to its movement stop range, never mid-walk from outer outline reach.
  const lancerStart = starts.find(({ actorId }) => actorId === 1);
  assert.ok(lancerStart, "lancer must eventually swing");
  const snapshot = world.snapshots.find(({ tick }) => tick === lancerStart.tick);
  const lancer = snapshot.units.find(({ referenceId }) => referenceId === 1);
  const elephant = snapshot.units.find(({ referenceId }) => referenceId === 2);
  const collisionGap = Math.max(
    Math.abs(lancer.x - elephant.x), Math.abs(lancer.y - elephant.y)) - 0.5;
  assert.ok(collisionGap <= 1.0 + 1e-9,
    `lancer swung mid-approach from collision gap ${collisionGap.toFixed(3)}`);
});
