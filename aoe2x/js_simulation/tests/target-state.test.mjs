import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


const mechanicsUrl = new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
);
const mechanics = JSON.parse(await readFile(mechanicsUrl, "utf8"));
const heavyCavArcherMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json",
  import.meta.url,
), "utf8"));
const stoppedMechanics = Object.freeze({ ...mechanics, speed_tiles_per_second: 0 });


function unit({
  referenceId,
  owner,
  x,
  y,
  hp = 70,
  alive = true,
  pursuitTargetId = null,
  engagedTargetId = null,
  attackTargetId = null,
  action = "idle",
  windup = 0,
  reload = 0,
  acquire = 0,
  unitMechanics = mechanics,
} = {}) {
  return {
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics: unitMechanics,
    unitMaster: 567,
    hp,
    alive,
    pursuitTargetId,
    engagedTargetId,
    attackTargetId,
    avoidance: null,
    action,
    actionTimers: { windup, reload, acquire },
  };
}


function scenario(units, options = {}) {
  return {
    ratio: "target-state-test",
    units,
    mapHash: "target-state-map",
    map: { width: 10, height: 10, obstacles: [] },
    ...options,
  };
}


test("resolved collision exposes a pure immutable enemy-contact manifold", async () => {
  const { queryEnemyContactManifold } = await import("../src/combat/collision.js");
  const before = Object.freeze([
    Object.freeze(unit({ referenceId: 1, owner: 2, x: 2, y: 5 })),
    Object.freeze(unit({ referenceId: 2, owner: 3, x: 2.42, y: 5 })),
    Object.freeze(unit({ referenceId: 3, owner: 2, x: 7, y: 5 })),
  ]);
  const after = Object.freeze([
    Object.freeze({ ...before[0], x: 2.02 }),
    before[1],
    before[2],
  ]);
  const beforeJson = JSON.stringify(before);
  const afterJson = JSON.stringify(after);

  const contacts = queryEnemyContactManifold(before, after);

  assert.deepEqual(contacts.map(({ leftId, rightId }) => [leftId, rightId]), [[1, 2]]);
  assert.ok(Math.abs(contacts[0].sweptToi - 1) < 1e-12);
  assert.ok(Math.abs(contacts[0].finalSurfaceGap) < 1e-12);
  assert.equal(Object.isFrozen(contacts), true);
  assert.equal(contacts.every(Object.isFrozen), true);
  assert.equal(JSON.stringify(before), beforeJson);
  assert.equal(JSON.stringify(after), afterJson);
});


test("published unit state rejects the ambiguous legacy target field", async () => {
  const { createWorld } = await import("../src/combat/world.js");
  const legacy = { ...unit({ referenceId: 1, owner: 2, x: 2, y: 5 }), targetId: 2 };

  assert.throws(
    () => createWorld(scenario([
      legacy,
      unit({ referenceId: 2, owner: 3, x: 4, y: 5 }),
    ])),
    /legacy targetId.*ambiguous/i,
  );
});


test("initial idle and reload states reject stale attack targets", async () => {
  const { createWorld } = await import("../src/combat/world.js");
  const friendly = unit({ referenceId: 2, owner: 2, x: 3, y: 5 });
  const enemy = unit({ referenceId: 3, owner: 3, x: 4, y: 5 });

  assert.throws(
    () => createWorld(scenario([
      unit({
        referenceId: 1,
        owner: 2,
        x: 2,
        y: 5,
        attackTargetId: 99,
      }),
      friendly,
      enemy,
    ])),
    /idle.*attackTargetId/i,
  );
  assert.throws(
    () => createWorld(scenario([
      unit({
        referenceId: 1,
        owner: 2,
        x: 2,
        y: 5,
        attackTargetId: 2,
        action: "reload",
        reload: 1,
      }),
      friendly,
      enemy,
    ])),
    /reload.*attackTargetId/i,
  );
});


test("initial attacking state requires a live enemy swing target and coherent windup", async () => {
  const { createWorld } = await import("../src/combat/world.js");
  const delayedMechanics = Object.freeze({
    ...mechanics,
    attack_delay_seconds: 2 / 60,
  });
  const friendly = unit({ referenceId: 2, owner: 2, x: 3, y: 5 });
  const enemy = unit({ referenceId: 3, owner: 3, x: 4, y: 5 });
  const deadEnemy = unit({ referenceId: 4, owner: 3, x: 5, y: 5, hp: 0, alive: false });
  const attacking = (attackTargetId, windup) => unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    attackTargetId,
    action: "attacking",
    windup,
    unitMechanics: delayedMechanics,
  });

  for (const [attackTargetId, windup] of [[null, 2], [99, 2], [2, 2], [4, 2]]) {
    assert.throws(
      () => createWorld(scenario([
        attacking(attackTargetId, windup),
        friendly,
        enemy,
        deadEnemy,
      ])),
      /attacking.*attackTargetId/i,
    );
  }
  for (const windup of [0, 3]) {
    assert.throws(
      () => createWorld(scenario([
        attacking(3, windup),
        friendly,
        enemy,
        deadEnemy,
      ])),
      /attacking.*windup/i,
    );
  }
  assert.doesNotThrow(() => createWorld(scenario([
    attacking(3, 2),
    friendly,
    enemy,
    deadEnemy,
  ])));
});


test("a unit pursues A but engages and attacks intervening enemy B after contact", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 3 }),
    unit({
      referenceId: 2,
      owner: 3,
      x: 2 + mechanics.speed_tiles_per_second / 60 + 0.4,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 3,
      x: 4,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
  ])));
  const actor = next.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(actor.pursuitTargetId, 3);
  assert.equal(actor.engagedTargetId, 2);
  assert.equal(actor.attackTargetId, null);
  assert.deepEqual(
    next.events
      .filter(({ actorId }) => actorId === 1)
      .map(({ type, targetId }) => [type, targetId]),
    [
      ["move", 3],
      ["engagement-started", 2],
      ["attack-start", 2],
      ["damage", 2],
    ],
  );
});


test("a separated enemy cannot become an engagement", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 3 }),
    unit({
      referenceId: 2,
      owner: 3,
      x: 3,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 3,
      x: 5,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
  ])));
  const actor = next.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(actor.engagedTargetId, null);
  assert.equal(actor.attackTargetId, null);
  assert.equal(next.events.some(({ type, actorId }) => (
    type === "engagement-started" && actorId === 1
  )), false);
});


test("engagement ends on separation and movement resumes toward pursuit", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 2,
      x: 2,
      y: 5,
      pursuitTargetId: 3,
      engagedTargetId: 2,
      action: "reload",
      reload: 10,
    }),
    unit({
      referenceId: 2,
      owner: 3,
      x: 1.6,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 3,
      x: 4,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
  ])));
  const actor = next.units.find(({ referenceId }) => referenceId === 1);

  assert.ok(actor.x > 2);
  assert.equal(actor.pursuitTargetId, 3);
  assert.equal(actor.engagedTargetId, null);
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "engagement-ended" && actorId === 1 && targetId === 2
  )));
});


test("a kiting-world chaser holds an outer-envelope engagement and starts its swing", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 3,
      x: 2,
      y: 5,
      pursuitTargetId: 2,
      engagedTargetId: 2,
    }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 2.6,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], { kiteOwner: 2, kiteMeleeOpeningOrder: "attack-move-all" })));
  const champion = next.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(champion.x, 2);
  assert.equal(champion.engagedTargetId, 2);
  assert.equal(champion.attackTargetId, 2);
  assert.equal(champion.action, "attacking");
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "attack-start" && actorId === 1 && targetId === 2
  )));
});


test("a zero-dwell viewer chaser engages on its first legal range-entry tick", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const first = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 3,
      x: 2,
      y: 5,
      pursuitTargetId: 2,
    }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 2.6,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
    kiteChaseDwellTicks: 0,
  })));
  const firstChampion = first.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(firstChampion.engagedTargetId, 2);
  assert.equal(firstChampion.attackTargetId, null);

  const second = stepWorld(first);
  const secondChampion = second.units.find(({ referenceId }) => referenceId === 1);
  assert.equal(secondChampion.attackTargetId, 2);
  assert.equal(secondChampion.action, "attacking");
});


test("an attack-moving chaser acquires a visible target before reaching its waypoint", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  let world = createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 3,
      x: 2,
      y: 5,
      acquire: 100,
    }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 6,
      y: 5,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
  }));

  while (world.tick < 36) world = stepWorld(world);
  const ordered = world.units.find(({ referenceId }) => referenceId === 1);
  assert.equal(ordered.pursuitTargetId, null);
  assert.ok(ordered.x > 2);
  assert.ok(world.events.some(({ type, tick, actorId }) => (
    type === "ai-location-order" && tick === 36 && actorId === 1
  )));

  world = stepWorld(world);
  const acquired = world.units.find(({ referenceId }) => referenceId === 1);
  assert.equal(acquired.pursuitTargetId, 2);
  assert.ok(world.events.some(({ type, tick, actorId, targetId }) => (
    type === "pursuit-acquired" && tick === 37 && actorId === 1 && targetId === 2
  )));
});


test("unified contact lets a reloading melee engagement close to its stop surface", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 3,
      x: 2,
      y: 5,
      pursuitTargetId: 2,
      engagedTargetId: 2,
      action: "reload",
      reload: 10,
    }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 2.6,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
  })));
  const champion = next.units.find(({ referenceId }) => referenceId === 1);

  assert.ok(champion.x > 2);
});


test("an attack-move scan can account for targets claimed earlier in the same scan", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  let world = createWorld(scenario([
    unit({ referenceId: 1, owner: 3, x: 2, y: 5, acquire: 100 }),
    unit({ referenceId: 2, owner: 3, x: 2, y: 5.05, acquire: 100 }),
    unit({
      referenceId: 3,
      owner: 2,
      x: 6,
      y: 5,
      acquire: 100,
      unitMechanics: heavyCavArcherMechanics,
    }),
    unit({
      referenceId: 4,
      owner: 2,
      x: 6.3,
      y: 5,
      acquire: 100,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
    attackMoveTargetPressureTiles: 0.5,
  }));

  while (world.tick < 37) world = stepWorld(world);
  const chasers = world.units
    .filter(({ owner }) => owner === 3)
    .sort((left, right) => left.referenceId - right.referenceId);

  assert.deepEqual(chasers.map(({ pursuitTargetId }) => pursuitTargetId), [3, 4]);
});


test("preventive contact steering derives its owners independently of kite state", async () => {
  const { createWorld } = await import("../src/combat/world.js");
  const units = [
    unit({ referenceId: 1, owner: 3, x: 2, y: 5, pursuitTargetId: 2 }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 6,
      y: 5,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ];
  const baseline = createWorld(scenario(units, {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
  }));
  const enabled = createWorld(scenario(units, {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
    preventiveContactSteering: true,
    preventiveContactSteeringStrength: 0.5,
  }));
  const nativeSiege = createWorld(scenario(units, {
    preventiveContactSteering: true,
    preventiveContactSteeringStrength: 0.5,
  }));

  assert.equal(baseline.contactSteeringStates, undefined);
  assert.deepEqual([...enabled.contactSteeringStates.keys()], [3]);
  assert.equal(enabled.contactSteeringStates.get(3).strength, 0.5);
  assert.equal(enabled.contactSteeringStates.get(3).steeredSteps, 0);
  assert.deepEqual([...enabled.contactSteeringStates.get(3).steeredUnits], []);
  assert.equal(nativeSiege.kiteState, undefined);
  assert.deepEqual([...nativeSiege.contactSteeringStates.keys()], [3]);
  assert.throws(() => createWorld(scenario(units.map((entry) => ({
    ...entry,
    mechanics: heavyCavArcherMechanics,
  })), {
    preventiveContactSteering: true,
  })), /preventive contact steering requires a melee unit/);
  assert.throws(() => createWorld(scenario(units, {
    preventiveContactSteering: true,
    preventiveContactSteeringStrength: 1.01,
  })), /preventive contact steering strength must be between 0 and 1/);
});


test("multiple melee owners receive independent symmetric steering state", async () => {
  const { createWorld } = await import("../src/combat/world.js");
  const units = [
    unit({ referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 2 }),
    unit({ referenceId: 2, owner: 3, x: 6, y: 5, pursuitTargetId: 1 }),
  ];
  const world = createWorld(scenario(units, {
    preventiveContactSteering: true,
    preventiveContactSteeringStrength: 0.5,
  }));

  assert.deepEqual([...world.contactSteeringStates.keys()], [2, 3]);
  assert.notEqual(
    world.contactSteeringStates.get(2),
    world.contactSteeringStates.get(3),
  );
  assert.ok([...world.contactSteeringStates.values()].every(({ strength }) => (
    strength === 0.5
  )));
});


test("a blocked attack-moving chaser retargets to the nearest visible enemy", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const blockedChampion = unit({
    referenceId: 1,
    owner: 3,
    x: 2,
    y: 5,
    pursuitTargetId: 2,
  });
  blockedChampion.experimentBlocked = true;
  const next = stepWorld(createWorld(scenario([
    blockedChampion,
    unit({
      referenceId: 2,
      owner: 2,
      x: 6,
      y: 5,
      unitMechanics: heavyCavArcherMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 2,
      x: 3,
      y: 5,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
  })));
  const champion = next.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(champion.pursuitTargetId, 3);
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "pursuit-acquired" && actorId === 1 && targetId === 3
  )));
});


test("a sticky attack-move target does not thrash merely because pursuit is blocked", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const blockedChampion = unit({
    referenceId: 1,
    owner: 3,
    x: 2,
    y: 5,
    pursuitTargetId: 2,
  });
  blockedChampion.experimentBlocked = true;
  const next = stepWorld(createWorld(scenario([
    blockedChampion,
    unit({
      referenceId: 2,
      owner: 2,
      x: 6,
      y: 5,
      unitMechanics: heavyCavArcherMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 2,
      x: 3,
      y: 5,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    kiteMeleeOpeningOrder: "attack-move-all",
    attackMoveStickyPursuit: true,
  })));
  const champion = next.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(champion.pursuitTargetId, 2);
  assert.equal(next.events.some(({ type, actorId }) => (
    type === "pursuit-acquired" && actorId === 1
  )), false);
});


test("a kiting-world chaser resumes pursuit when its engagement leaves reach", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 3,
      x: 2,
      y: 5,
      pursuitTargetId: 2,
      engagedTargetId: 2,
      action: "reload",
      reload: 10,
    }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 3,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], { kiteOwner: 2, kiteMeleeOpeningOrder: "attack-move-all" })));
  const champion = next.units.find(({ referenceId }) => referenceId === 1);

  assert.ok(champion.x > 2);
  assert.equal(champion.pursuitTargetId, 2);
  assert.equal(champion.engagedTargetId, null);
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "engagement-ended" && actorId === 1 && targetId === 2
  )));
});


test("an attack-moving chaser captures a different kiter at frontal body contact", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1, owner: 3, x: 2, y: 5, pursuitTargetId: 2 }),
    unit({
      referenceId: 2,
      owner: 2,
      x: 4,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: heavyCavArcherMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 2,
      x: 2.45,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: heavyCavArcherMechanics,
    }),
  ], {
    kiteOwner: 2,
    chaseCapture: true,
    kiteMeleeOpeningOrder: "attack-move-all",
  })));
  const champion = next.units.find(({ referenceId }) => referenceId === 1);

  assert.equal(champion.pursuitTargetId, 3);
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "contact-capture" && actorId === 1 && targetId === 3
  )));
});


test("a swing keeps its captured target after engagement separation", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const oneTickWindupMechanics = Object.freeze({
    ...mechanics,
    attack_delay_seconds: 1 / 60,
  });
  const next = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1,
      owner: 2,
      x: 2,
      y: 5,
      pursuitTargetId: 3,
      engagedTargetId: 2,
      attackTargetId: 2,
      action: "attacking",
      windup: 1,
      unitMechanics: oneTickWindupMechanics,
    }),
    unit({ referenceId: 4, owner: 2, x: 4, y: 5, unitMechanics: stoppedMechanics }),
    unit({ referenceId: 2, owner: 3, x: 2.4, y: 5, pursuitTargetId: 4 }),
    unit({ referenceId: 3, owner: 3, x: 6, y: 5, unitMechanics: stoppedMechanics }),
  ])));
  const actor = next.units.find(({ referenceId }) => referenceId === 1);
  const formerEngagement = next.units.find(({ referenceId }) => referenceId === 2);

  assert.equal(actor.pursuitTargetId, 3);
  assert.equal(actor.engagedTargetId, null);
  assert.equal(actor.attackTargetId, null);
  assert.equal(formerEngagement.hp, 56);
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "engagement-ended" && actorId === 1 && targetId === 2
  )));
  assert.ok(next.events.some(({ type, actorId, targetId }) => (
    type === "damage" && actorId === 1 && targetId === 2
  )));
});


test("simultaneous physical contacts choose deterministically by final gap then reference ID", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const vertical = Math.sqrt(0.4 ** 2 - 0.2 ** 2);
  const units = [
    unit({
      referenceId: 1,
      owner: 2,
      x: 5,
      y: 5,
      pursuitTargetId: 4,
      unitMechanics: stoppedMechanics,
    }),
    unit({
      referenceId: 2,
      owner: 3,
      x: 5.2,
      y: 5 + vertical,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
    unit({
      referenceId: 3,
      owner: 3,
      x: 5.2,
      y: 5 - vertical,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
    unit({
      referenceId: 4,
      owner: 3,
      x: 8,
      y: 5,
      pursuitTargetId: 1,
      unitMechanics: stoppedMechanics,
    }),
  ];
  const forward = stepWorld(createWorld(scenario(units)));
  const reversed = stepWorld(createWorld(scenario([...units].reverse())));

  assert.equal(
    forward.units.find(({ referenceId }) => referenceId === 1).engagedTargetId,
    2,
  );
  assert.deepEqual(forward.units, reversed.units);
  assert.deepEqual(forward.events, reversed.events);
});


test("every engagement transition carries physical contact evidence", async () => {
  const { createWorld, stepWorld } = await import("../src/combat/world.js");
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 3 }),
    unit({
      referenceId: 2,
      owner: 3,
      x: 2 + mechanics.speed_tiles_per_second / 60 + 0.4,
      y: 5,
      unitMechanics: stoppedMechanics,
    }),
    unit({ referenceId: 3, owner: 3, x: 4, y: 5, unitMechanics: stoppedMechanics }),
  ])));
  const started = next.events.filter(({ type }) => type === "engagement-started");

  assert.ok(started.length > 0);
  for (const row of started) {
    assert.ok(row.sweptToi >= 0 && row.sweptToi <= 1);
    assert.ok(Number.isFinite(row.finalSurfaceGap));
  }
});
