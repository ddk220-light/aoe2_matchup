import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";


const attacksModuleUrl = new URL("../src/combat/attacks.js", import.meta.url);
const worldModuleUrl = new URL("../src/combat/world.js", import.meta.url);
const mechanicsUrl = new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
);
const mechanics = JSON.parse(await readFile(mechanicsUrl, "utf8"));


function unit({
  referenceId,
  owner,
  x,
  y,
  hp = mechanics.hp,
  alive = true,
  targetId = null,
  action = "idle",
  windup = 0,
  reload = 0,
  unitMechanics = mechanics,
} = {}) {
  return {
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics: unitMechanics,
    unitMaster: unitMechanics.unit_master,
    hp,
    alive,
    targetId,
    action,
    actionTimers: { windup, reload },
  };
}


function scenario(units, overrides = {}) {
  return {
    ratio: "test",
    units,
    mapHash: "test-map",
    map: { width: 10, height: 10, obstacles: [] },
    ...overrides,
  };
}


async function loadWorld() {
  assert.equal(existsSync(fileURLToPath(worldModuleUrl)), true);
  return import(worldModuleUrl);
}


async function loadAttacks() {
  assert.equal(existsSync(fileURLToPath(attacksModuleUrl)), true);
  return import(attacksModuleUrl);
}


function normalizeWorld(world) {
  return {
    tick: world.tick,
    units: [...world.units]
      .sort((a, b) => a.referenceId - b.referenceId)
      .map((entry) => ({ ...entry, mechanics: undefined })),
    events: [...world.events].map(({ id, ...event }) => event),
  };
}


test("both sides decide from the same start-of-tick snapshot", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const units = [
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5 }),
    unit({ referenceId: 1628, owner: 2, x: 4, y: 5 }),
  ];

  const forward = stepWorld(createWorld(scenario(units)));
  const reversed = stepWorld(createWorld(scenario([...units].reverse())));

  assert.deepEqual(normalizeWorld(forward), normalizeWorld(reversed));
  assert.deepEqual(
    forward.units.map(({ referenceId, targetId }) => [referenceId, targetId]),
    [[1628, 1699], [1699, 1628]],
  );
  assert.ok(Math.abs(forward.units[0].x + forward.units[1].x - 9) < 1e-12);
  assert.deepEqual(
    forward.events.map(({ type, actorId }) => [type, actorId]),
    [
      ["target-acquired", 1628],
      ["target-acquired", 1699],
      ["move", 1628],
      ["move", 1699],
    ],
  );
});


test("same-tick attacks use reference IDs rather than owner or input order", async () => {
  const { orderReadyAttacks } = await loadAttacks();
  const attackFrom1699 = {
    type: "attack-ready",
    readyTick: 9,
    actorId: 1699,
    targetId: 1628,
  };
  const attackFrom1628 = {
    type: "attack-ready",
    readyTick: 9,
    actorId: 1628,
    targetId: 1699,
  };

  const events = orderReadyAttacks([attackFrom1699, attackFrom1628]);

  assert.deepEqual(events.map((event) => event.actorId), [1628, 1699]);
});


test("ready attack ordering uses ready tick, actor, target, then event type", async () => {
  const { orderReadyAttacks } = await loadAttacks();
  const attacks = [
    { type: "z", readyTick: 10, actorId: 1, targetId: 2 },
    { type: "z", readyTick: 9, actorId: 2, targetId: 3 },
    { type: "z", readyTick: 9, actorId: 2, targetId: 2 },
    { type: "a", readyTick: 9, actorId: 2, targetId: 2 },
    { type: "z", readyTick: 9, actorId: 1, targetId: 3 },
  ];

  assert.deepEqual(
    orderReadyAttacks(attacks).map(({ readyTick, actorId, targetId, type }) => (
      [readyTick, actorId, targetId, type]
    )),
    [
      [9, 1, 3, "z"],
      [9, 2, 2, "a"],
      [9, 2, 2, "z"],
      [9, 2, 3, "z"],
      [10, 1, 2, "z"],
    ],
  );
});


test("Champion attack timing is converted once to integer ticks", async () => {
  const { attackDelayTicks, reloadTicks } = await loadAttacks();

  assert.equal(attackDelayTicks(mechanics), 0);
  assert.equal(reloadTicks(mechanics), 120);
});


test("melee range compares body surfaces rather than centers", async () => {
  const { isInAttackRange } = await loadAttacks();
  const attacker = unit({ referenceId: 1628, owner: 2, x: 4, y: 4 });
  const touching = unit({ referenceId: 1699, owner: 3, x: 4.4, y: 4 });
  const separated = unit({ referenceId: 1700, owner: 3, x: 4.400001, y: 4 });

  assert.equal(isInAttackRange(attacker, touching), true);
  assert.equal(isInAttackRange(attacker, separated), false);
});


test("damage is derived from attack and armor classes", async () => {
  const { calculateDamage } = await loadAttacks();
  const attacker = unit({ referenceId: 1628, owner: 2, x: 4, y: 4 });
  const target = unit({ referenceId: 1699, owner: 3, x: 4.4, y: 4 });
  const poisonedDerivedValue = {
    ...attacker,
    mechanics: { ...mechanics, derived: { damage_vs_self: 99 } },
  };

  assert.equal(calculateDamage(poisonedDerivedValue, target), 14);
});


test("attack event constructors publish frozen reference-ID records", async () => {
  const {
    createAttackStartEvent,
    createDamageEvent,
    createDeathEvent,
    createAttackCanceledEvent,
  } = await loadAttacks();
  const records = [
    createAttackStartEvent({ tick: 7, actorId: 1628, targetId: 1699, readyTick: 7 }),
    createDamageEvent({
      tick: 7,
      actorId: 1628,
      targetId: 1699,
      readyTick: 7,
      amount: 14,
      hpBefore: 70,
      hpAfter: 56,
    }),
    createDeathEvent({ tick: 7, actorId: 1628, targetId: 1699, readyTick: 7 }),
    createAttackCanceledEvent({
      tick: 7,
      actorId: 1699,
      targetId: 1628,
      readyTick: 7,
      reason: "actor-dead",
    }),
  ];

  assert.deepEqual(records.map(({ type }) => type), [
    "attack-start", "damage", "death", "attack-canceled",
  ]);
  assert.equal(new Set(records.map(({ id }) => id)).size, records.length);
  assert.equal(records.every((record) => record.eventId === record.id), true);
  assert.equal(records.every(Object.isFrozen), true);
});


test("movement contact and zero-delay attacks publish in phase order", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const start = scenario([
    unit({ referenceId: 1699, owner: 3, x: 4.42, y: 4 }),
    unit({ referenceId: 1628, owner: 2, x: 4, y: 4 }),
  ]);

  const next = stepWorld(createWorld(start));

  assert.ok(Math.abs(next.units[0].x - 4.01) < 1e-12);
  assert.ok(Math.abs(next.units[1].x - 4.41) < 1e-12);
  assert.deepEqual(next.events.map(({ type, actorId }) => [type, actorId]), [
    ["target-acquired", 1628],
    ["target-acquired", 1699],
    ["move", 1628],
    ["move", 1699],
    ["blocked", 1628],
    ["blocked", 1699],
    ["contact", 1628],
    ["contact", 1699],
    ["attack-start", 1628],
    ["attack-start", 1699],
    ["damage", 1628],
    ["damage", 1699],
  ]);
  assert.deepEqual(next.units.map(({ hp }) => hp), [56, 56]);
  assert.deepEqual(next.units.map(({ action, actionTimers }) => [action, actionTimers]), [
    ["reload", { windup: 0, reload: 120 }],
    ["reload", { windup: 0, reload: 120 }],
  ]);
  assert.equal(next.events.every((entry) => entry.id === entry.eventId), true);
  assert.equal(next.events.every(Object.isFrozen), true);
});


test("attack delay and reload advance only on integer ticks", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const delayedMechanics = {
    ...mechanics,
    attack_delay_seconds: 2 / 60,
  };
  let world = createWorld(scenario([
    unit({
      referenceId: 1628,
      owner: 2,
      x: 4,
      y: 4,
      unitMechanics: delayedMechanics,
    }),
    unit({
      referenceId: 1699,
      owner: 3,
      x: 4.4,
      y: 4,
      unitMechanics: delayedMechanics,
    }),
  ]));

  world = stepWorld(world);
  assert.deepEqual(world.units.map(({ hp }) => hp), [70, 70]);
  assert.deepEqual(world.units.map(({ actionTimers }) => actionTimers.windup), [2, 2]);
  world = stepWorld(world);
  assert.deepEqual(world.units.map(({ hp }) => hp), [70, 70]);
  assert.deepEqual(world.units.map(({ actionTimers }) => actionTimers.windup), [1, 1]);
  world = stepWorld(world);
  assert.deepEqual(world.units.map(({ hp }) => hp), [56, 56]);
  assert.deepEqual(
    world.events.filter(({ type }) => type === "damage").map(({ readyTick }) => readyTick),
    [3, 3],
  );

  for (let index = 0; index < 119; index += 1) world = stepWorld(world);
  assert.deepEqual(world.units.map(({ hp }) => hp), [56, 56]);
  assert.deepEqual(world.units.map(({ actionTimers }) => actionTimers.reload), [1, 1]);
  world = stepWorld(world);
  world = stepWorld(world);
  world = stepWorld(world);
  assert.deepEqual(world.units.map(({ hp }) => hp), [42, 42]);
  assert.deepEqual(
    world.events.filter(({ type }) => type === "damage").map(({ readyTick }) => readyTick),
    [125, 125],
  );
});


test("a lower-reference lethal attack cancels a ready attacker killed earlier", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1699, owner: 3, x: 4.4, y: 4, hp: 14 }),
    unit({ referenceId: 1628, owner: 2, x: 4, y: 4, hp: 14 }),
  ])));

  assert.deepEqual(next.units.map(({ referenceId, hp, alive }) => (
    [referenceId, hp, alive]
  )), [
    [1628, 14, true],
    [1699, 0, false],
  ]);
  assert.deepEqual(
    next.events
      .filter(({ type }) => ["damage", "death", "attack-canceled"].includes(type))
      .map(({ type, actorId, targetId, reason }) => [type, actorId, targetId, reason]),
    [
      ["damage", 1628, 1699, undefined],
      ["death", 1628, 1699, undefined],
      ["attack-canceled", 1699, 1628, "actor-dead"],
    ],
  );
  assert.equal(next.events.some(({ type, actorId }) => type === "damage" && actorId === 1699), false);
});


test("later ready attacks do not damage a target that is already dead", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1629, owner: 2, x: 5, y: 4.6, hp: 14 }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5, hp: 14 }),
    unit({ referenceId: 1628, owner: 2, x: 4.6, y: 5, hp: 14 }),
  ])));

  assert.deepEqual(
    next.events.filter(({ type }) => type === "damage").map(({ actorId, targetId }) => (
      [actorId, targetId]
    )),
    [[1628, 1699]],
  );
  assert.equal(
    next.events.some(({ type, actorId }) => type === "attack-canceled" && actorId === 1629),
    true,
  );
});


test("death-tick publication preserves a non-ready attack on the new corpse", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const deathTick = stepWorld(createWorld(scenario([
    unit({ referenceId: 1629, owner: 2, x: 5, y: 4.6, hp: 14, targetId: 1699, action: "attacking", windup: 3 }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5, hp: 14 }),
    unit({ referenceId: 1628, owner: 2, x: 4.6, y: 5, hp: 14 }),
  ])));
  const windingUp = deathTick.units.find(({ referenceId }) => referenceId === 1629);

  assert.deepEqual(
    {
      targetId: windingUp.targetId,
      action: windingUp.action,
      windup: windingUp.actionTimers.windup,
    },
    { targetId: 1699, action: "attacking", windup: 2 },
  );
  assert.equal(
    deathTick.events.some(({ actorId, type }) => (
      actorId === 1629 && ["target-invalidated", "attack-canceled"].includes(type)
    )),
    false,
  );
});


test("the next validation tick invalidates and cancels a preserved windup", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const deathTick = stepWorld(createWorld(scenario([
    unit({ referenceId: 1629, owner: 2, x: 5, y: 4.6, hp: 14, targetId: 1699, action: "attacking", windup: 3 }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5, hp: 14 }),
    unit({ referenceId: 1628, owner: 2, x: 4.6, y: 5, hp: 14 }),
  ])));

  const validationTick = stepWorld(deathTick);
  const canceled = validationTick.units.find(({ referenceId }) => referenceId === 1629);

  assert.deepEqual(
    validationTick.events
      .filter(({ actorId }) => actorId === 1629)
      .map(({ type, targetId, readyTick, reason }) => (
        [type, targetId, readyTick, reason]
      )),
    [
      ["target-invalidated", 1699, undefined, "target-dead"],
      ["attack-canceled", 1699, 3, "target-invalidated"],
    ],
  );
  assert.deepEqual(
    {
      targetId: canceled.targetId,
      action: canceled.action,
      timers: canceled.actionTimers,
    },
    { targetId: null, action: "idle", timers: { windup: 0, reload: 0 } },
  );
});


test("validation cancellation projects the scheduled readiness from windup", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const next = stepWorld(createWorld(scenario([
    unit({
      referenceId: 1628,
      owner: 2,
      x: 4,
      y: 4,
      targetId: 1699,
      action: "attacking",
      windup: 2,
    }),
    unit({ referenceId: 1699, owner: 3, x: 4.4, y: 4, hp: 0, alive: false }),
  ])));

  const canceled = next.events.find(({ type }) => type === "attack-canceled");
  assert.equal(next.tick, 1);
  assert.equal(canceled.readyTick, 2);
});


test("friendly and dead locks invalidate before same-tick reacquisition", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const next = stepWorld(createWorld(scenario([
    unit({ referenceId: 1628, owner: 2, x: 4, y: 4, targetId: 1629 }),
    unit({ referenceId: 1629, owner: 2, x: 7, y: 7 }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 4 }),
    unit({ referenceId: 1700, owner: 3, x: 6, y: 6, hp: 0, alive: false }),
  ])));
  const actor = next.units.find(({ referenceId }) => referenceId === 1628);

  assert.equal(actor.targetId, 1699);
  assert.deepEqual(
    next.events
      .filter(({ actorId }) => actorId === 1628)
      .slice(0, 2)
      .map(({ type, targetId }) => [type, targetId]),
    [["target-invalidated", 1629], ["target-acquired", 1699]],
  );
  assert.equal(next.units.some((entry) => {
    if (!entry.alive || entry.targetId === null) return false;
    const target = next.units.find(({ referenceId }) => referenceId === entry.targetId);
    return !target?.alive || target.owner === entry.owner;
  }), false);
});


test("the runner fails rather than returning a timeout outcome", async () => {
  const { createWorld, runWorld } = await loadWorld();
  const stalemate = createWorld(scenario([
    unit({ referenceId: 1628, owner: 2, x: 1, y: 1 }),
    unit({ referenceId: 1699, owner: 3, x: 9, y: 9 }),
  ]));

  assert.throws(
    () => runWorld(stalemate, { maxTicks: 3600 }),
    /exceeded 3600 ticks/,
  );
});


test("the runner rejects an all-dead world as an invalid terminal", async () => {
  const { createWorld, runWorld } = await loadWorld();
  const allDead = createWorld(scenario([
    unit({ referenceId: 1628, owner: 2, x: 4, y: 4, hp: 0, alive: false }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5, hp: 0, alive: false }),
  ]));

  assert.throws(
    () => runWorld(allDead, { maxTicks: 1 }),
    /invalid terminal.*no live owners/i,
  );
});


test("the runner rejects safety ceilings above 3600 ticks", async () => {
  const { createWorld, runWorld } = await loadWorld();
  const stalemate = createWorld(scenario([
    unit({ referenceId: 1628, owner: 2, x: 1, y: 1 }),
    unit({ referenceId: 1699, owner: 3, x: 9, y: 9 }),
  ]));

  assert.throws(
    () => runWorld(stalemate, { maxTicks: 3601 }),
    /max ticks must not exceed 3600/i,
  );
});


test("runWorld preserves snapshots without friendly live locks", async () => {
  const { createWorld, runWorld } = await loadWorld();
  const result = runWorld(createWorld(scenario([
    unit({ referenceId: 1629, owner: 2, x: 5, y: 4.6 }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5 }),
    unit({ referenceId: 1628, owner: 2, x: 4.6, y: 5 }),
  ])), { maxTicks: 1000 });

  assert.equal(result.outcome, "win");
  assert.equal(result.winner, 2);
  assert.equal(result.snapshots.length, result.ticks + 1);
  assert.equal(result.snapshots.some((snapshot) => snapshot.units.some((entry) => {
    if (!entry.alive || entry.targetId === null) return false;
    const target = snapshot.units.find(({ referenceId }) => referenceId === entry.targetId);
    return target?.owner === entry.owner;
  })), false);
});


test("complete fights are invariant to reversing scenario arrays", async () => {
  const { createWorld, runWorld } = await loadWorld();
  const units = [
    unit({ referenceId: 1629, owner: 2, x: 5, y: 4.6 }),
    unit({ referenceId: 1699, owner: 3, x: 5, y: 5 }),
    unit({ referenceId: 1628, owner: 2, x: 4.6, y: 5 }),
  ];

  const forward = runWorld(createWorld(scenario(units)), { maxTicks: 1000 });
  const reversed = runWorld(
    createWorld(scenario([...units].reverse())),
    { maxTicks: 1000 },
  );

  assert.deepEqual(
    {
      outcome: forward.outcome,
      winner: forward.winner,
      ticks: forward.ticks,
      units: forward.world.units.map(({ referenceId, hp, alive }) => (
        [referenceId, hp, alive]
      )),
      events: forward.events,
    },
    {
      outcome: reversed.outcome,
      winner: reversed.winner,
      ticks: reversed.ticks,
      units: reversed.world.units.map(({ referenceId, hp, alive }) => (
        [referenceId, hp, alive]
      )),
      events: reversed.events,
    },
  );
});


test("published worlds snapshots events and nested state are immutable", async () => {
  const { createWorld, stepWorld } = await loadWorld();
  const privateMechanics = JSON.parse(JSON.stringify(mechanics));
  const input = scenario([
    unit({
      referenceId: 1628,
      owner: 2,
      x: 4,
      y: 4,
      unitMechanics: privateMechanics,
    }),
    unit({
      referenceId: 1699,
      owner: 3,
      x: 4.42,
      y: 4,
      unitMechanics: privateMechanics,
    }),
  ], {
    map: {
      width: 10,
      height: 10,
      obstacles: [{ referenceId: 9000, x: 8, y: 8, radius: 0.2 }],
    },
  });
  const originalX = input.units[0].x;
  const world = createWorld(input);
  const before = JSON.stringify(world);
  input.units[0].x = 9;
  privateMechanics.attack_classes["4"] = 999;
  input.map.obstacles[0].x = 1;
  const next = stepWorld(world);

  assert.equal(world.units.find(({ referenceId }) => referenceId === 1628).x, originalX);
  assert.equal(world.units[0].mechanics.attack_classes["4"], 18);
  assert.equal(world.map.obstacles[0].x, 8);
  assert.equal(JSON.stringify(world), before);
  assert.equal(Object.isFrozen(next), true);
  assert.equal(Object.isFrozen(next.units), true);
  assert.equal(next.units.every(Object.isFrozen), true);
  assert.equal(next.units.every(({ actionTimers }) => Object.isFrozen(actionTimers)), true);
  assert.equal(next.units.every(({ mechanics: value }) => Object.isFrozen(value)), true);
  assert.equal(next.units.every(({ mechanics: value }) => Object.isFrozen(value.attack_classes)), true);
  assert.equal(Object.isFrozen(next.map), true);
  assert.equal(Object.isFrozen(next.map.obstacles), true);
  assert.equal(next.map.obstacles.every(Object.isFrozen), true);
  assert.equal(Object.isFrozen(next.events), true);
  assert.equal(next.events.every(Object.isFrozen), true);
  assert.equal(Object.isFrozen(next.eventLog), true);
  assert.equal(Object.isFrozen(next.snapshots), true);
  assert.equal(next.snapshots.every(Object.isFrozen), true);
  assert.equal(next.snapshots.every(({ units }) => Object.isFrozen(units)), true);
  assert.equal(next.snapshots.every(({ events }) => Object.isFrozen(events)), true);
});
