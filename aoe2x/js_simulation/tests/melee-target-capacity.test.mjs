import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";
import { meleeContactCapacity } from "../src/combat/targeting.js";


const boyarMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/elite_boyar_slavs_imperial.json",
  import.meta.url,
), "utf8"));
const arbalesterMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/arbalester_chinese_imperial.json",
  import.meta.url,
), "utf8"));
const heavyCavArcherMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json",
  import.meta.url,
), "utf8"));


function unit({ referenceId, owner, x, y, mechanics }) {
  return createUnitState({
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
}


function scenario(targets) {
  return {
    ratio: "melee-contact-capacity-test",
    mapHash: "melee-contact-capacity-map",
    map: { width: 20, height: 20, obstacles: [] },
    kiteOwner: 3,
    kiteMeleeOpeningOrder: "attack-move-all",
    units: [
      ...Array.from({ length: 5 }, (_, index) => unit({
        referenceId: 100 + index,
        owner: 2,
        x: 4.6 + index * 0.2,
        y: 5,
        mechanics: boyarMechanics,
      })),
      ...targets,
    ],
  };
}


test("contact capacity counts only complete attacker diameters on an exposed perimeter", () => {
  const attacker = unit({
    referenceId: 100,
    owner: 2,
    x: 5,
    y: 5,
    mechanics: boyarMechanics,
  });
  const target = unit({
    referenceId: 200,
    owner: 3,
    x: 8,
    y: 5,
    mechanics: heavyCavArcherMechanics,
  });

  assert.equal(meleeContactCapacity(attacker, target, [attacker, target]), 6);
});


test("opening zero-range melee acquisition fills exposed contact capacity before crowding one target", () => {
  const near = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const farther = unit({
    referenceId: 201,
    owner: 3,
    x: 6,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const farthest = unit({
    referenceId: 202,
    owner: 3,
    x: 7,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const next = stepWorld(createWorld(scenario([near, farther, farthest])));
  const targets = next.units
    .filter(({ owner }) => owner === 2)
    .map(({ pursuitTargetId }) => pursuitTargetId);

  assert.deepEqual(targets, [200, 200, 201, 201, 202]);
});


test("surplus zero-range melee attackers retain the sole live target", () => {
  const onlyTarget = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const next = stepWorld(createWorld(scenario([onlyTarget])));
  const targets = next.units
    .filter(({ owner }) => owner === 2)
    .map(({ pursuitTargetId }) => pursuitTargetId);

  assert.deepEqual(targets, Array(5).fill(200));
});


test("opening pursuit may reserve a visible screened target after nearer contact space fills", () => {
  const near = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const screened = unit({
    referenceId: 201,
    owner: 3,
    x: 5,
    y: 9,
    mechanics: arbalesterMechanics,
  });
  const next = stepWorld(createWorld(scenario([near, screened])));
  const targets = next.units
    .filter(({ owner }) => owner === 2)
    .map(({ pursuitTargetId }) => pursuitTargetId);

  assert.deepEqual(targets, [200, 200, 201, 201, 200]);
});


test("attack-move opening keeps scanning when its only visible target has no contact space", () => {
  const visible = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const outsideSight = unit({
    referenceId: 201,
    owner: 3,
    x: 5,
    y: 11,
    mechanics: arbalesterMechanics,
  });
  const start = scenario([visible, outsideSight]);
  start.units = start.units.map((entry) => (
    entry.owner !== 2
      ? entry
      : Object.freeze({
        ...entry,
        actionTimers: Object.freeze({ ...entry.actionTimers, acquire: 100 }),
      })
  ));
  let world = createWorld(start);
  for (let tick = 0; tick < 37; tick += 1) world = stepWorld(world);
  const targets = world.units
    .filter(({ owner }) => owner === 2)
    .map(({ pursuitTargetId }) => pursuitTargetId);

  assert.deepEqual(targets, [200, 200, null, null, null]);
});


test("surplus locked melee pursuers reconsider a saturated target without disturbing its front attackers", () => {
  const near = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const farther = unit({
    referenceId: 201,
    owner: 3,
    x: 6,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const start = scenario([near, farther]);
  start.units = start.units.map((entry, index) => (
    entry.owner !== 2
      ? entry
      : Object.freeze({
        ...entry,
        pursuitTargetId: 200,
        experimentBlocked: index === 4,
      })
  ));
  const next = stepWorld(createWorld(start));
  const boyars = next.units.filter(({ owner }) => owner === 2);

  assert.equal(
    boyars.filter(({ pursuitTargetId }) => pursuitTargetId === 200).length,
    4,
  );
  assert.equal(
    boyars.filter(({ pursuitTargetId }) => pursuitTargetId === 201).length,
    1,
  );
  assert.equal(
    boyars.find(({ pursuitTargetId }) => pursuitTargetId === 201).meleeCapacityTargetId,
    201,
    "the alternate contact assignment must remain sticky instead of being recomputed next tick",
  );

  const reroutedId = boyars.find(({ pursuitTargetId }) => pursuitTargetId === 201).referenceId;
  const forcedBlocked = Object.freeze({
    ...next,
    units: Object.freeze(next.units.map((entry) => Object.freeze({
      ...entry,
      experimentBlocked: entry.referenceId === reroutedId,
    }))),
  });
  const afterBlockedTick = stepWorld(forcedBlocked);
  const rerouted = afterBlockedTick.units.find(({ referenceId }) => referenceId === reroutedId);
  assert.equal(rerouted.pursuitTargetId, 201);
  assert.equal(rerouted.meleeCapacityTargetId, 201);
});


test("a blocked attack-move pursuer chooses an under-capacity target instead of joining a full queue", () => {
  const full = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const abandoned = unit({
    referenceId: 201,
    owner: 3,
    x: 15,
    y: 15,
    mechanics: arbalesterMechanics,
  });
  const available = unit({
    referenceId: 202,
    owner: 3,
    x: 7,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const start = scenario([full, abandoned, available]);
  start.units = start.units.map((entry, index) => (
    entry.owner !== 2
      ? entry
      : Object.freeze({
        ...entry,
        pursuitTargetId: index < 4 ? 200 : 201,
        experimentBlocked: index === 4,
      })
  ));
  const next = stepWorld(createWorld(start));
  const boyars = next.units.filter(({ owner }) => owner === 2);

  assert.deepEqual(boyars.map(({ pursuitTargetId }) => pursuitTargetId), [200, 200, 200, 200, 202]);
  assert.equal(boyars.at(-1).meleeCapacityTargetId, 202);
});


test("a blocked attack-move pursuer may reserve a screened target with contact capacity", () => {
  const full = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const screened = unit({
    referenceId: 201,
    owner: 3,
    x: 5,
    y: 9,
    mechanics: arbalesterMechanics,
  });
  const abandoned = unit({
    referenceId: 202,
    owner: 3,
    x: 15,
    y: 15,
    mechanics: arbalesterMechanics,
  });
  const start = scenario([full, screened, abandoned]);
  start.units = start.units.map((entry, index) => (
    entry.owner !== 2
      ? entry
      : Object.freeze({
        ...entry,
        pursuitTargetId: index < 4 ? 200 : 202,
        experimentBlocked: index === 4,
      })
  ));
  const next = stepWorld(createWorld(start));
  const boyars = next.units.filter(({ owner }) => owner === 2);

  assert.deepEqual(boyars.map(({ pursuitTargetId }) => pursuitTargetId), [200, 200, 200, 200, 201]);
  assert.equal(boyars.at(-1).meleeCapacityTargetId, 201);
});


test("a contact reservation is released when its pursuer becomes physical overflow", () => {
  const saturated = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const available = unit({
    referenceId: 201,
    owner: 3,
    x: 7,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const start = scenario([saturated, available]);
  start.units = start.units.map((entry, index) => (
    entry.owner !== 2
      ? entry
      : Object.freeze({
        ...entry,
        pursuitTargetId: 200,
        experimentBlocked: index === 4,
        ...(index === 4 ? { meleeCapacityTargetId: 200 } : {}),
      })
  ));
  const next = stepWorld(createWorld(start));
  const overflow = next.units.find(({ referenceId }) => referenceId === 104);

  assert.equal(overflow.pursuitTargetId, 201);
  assert.equal(overflow.meleeCapacityTargetId, 201);
});


test("frontal contact capture does not add a seventh zero-range pursuer", () => {
  const currentTarget = unit({
    referenceId: 200,
    owner: 3,
    x: 4,
    y: 5,
    mechanics: heavyCavArcherMechanics,
  });
  const fullContact = unit({
    referenceId: 201,
    owner: 3,
    x: 2.45,
    y: 5,
    mechanics: heavyCavArcherMechanics,
  });
  const actor = Object.freeze({
    ...unit({
      referenceId: 100,
      owner: 2,
      x: 2,
      y: 5,
      mechanics: boyarMechanics,
    }),
    pursuitTargetId: 200,
  });
  const existingPursuers = Array.from({ length: 6 }, (_, index) => Object.freeze({
    ...unit({
      referenceId: 101 + index,
      owner: 2,
      x: 8 + index,
      y: 12,
      mechanics: boyarMechanics,
    }),
    pursuitTargetId: 201,
  }));
  const next = stepWorld(createWorld({
    ratio: "contact-capture-capacity-test",
    mapHash: "contact-capture-capacity-map",
    map: { width: 20, height: 20, obstacles: [] },
    kiteOwner: 3,
    chaseCapture: true,
    kiteMeleeOpeningOrder: "attack-move-all",
    units: [actor, ...existingPursuers, currentTarget, fullContact],
  }));
  const updatedActor = next.units.find(({ referenceId }) => referenceId === 100);

  assert.equal(updatedActor.pursuitTargetId, 200);
  assert.equal(next.events.some(({ type, actorId, targetId }) => (
    type === "contact-capture" && actorId === 100 && targetId === 201
  )), false);
});


test("an unblocked surplus melee pursuer keeps its live target", () => {
  const near = unit({
    referenceId: 200,
    owner: 3,
    x: 5,
    y: 8,
    mechanics: arbalesterMechanics,
  });
  const farther = unit({
    referenceId: 201,
    owner: 3,
    x: 5,
    y: 9,
    mechanics: arbalesterMechanics,
  });
  const start = scenario([near, farther]);
  start.units = start.units.map((entry) => (
    entry.owner !== 2
      ? entry
      : Object.freeze({
        ...entry,
        pursuitTargetId: 200,
        experimentBlocked: false,
      })
  ));
  const next = stepWorld(createWorld(start));

  assert.deepEqual(
    next.units.filter(({ owner }) => owner === 2).map(({ pursuitTargetId }) => pursuitTargetId),
    Array(5).fill(200),
  );
});
