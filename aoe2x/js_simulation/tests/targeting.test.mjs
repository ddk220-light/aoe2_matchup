import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";


const targetingModuleUrl = new URL("../src/combat/targeting.js", import.meta.url);
const mechanicsUrl = new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
);
const mechanics = JSON.parse(await readFile(mechanicsUrl, "utf8"));
const boyarMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/elite_boyar_slavs_imperial.json",
  import.meta.url,
), "utf8"));
const arbalesterMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/arbalester_chinese_imperial.json",
  import.meta.url,
), "utf8"));
const elephantMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/elite_battle_elephant_burmese_imperial.json",
  import.meta.url,
), "utf8"));


function unit({
  referenceId,
  owner = 2,
  x = 0,
  y = 0,
  alive = true,
  pursuitTargetId = null,
  unitMechanics = mechanics,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive,
    pursuitTargetId,
    mechanics: unitMechanics,
  });
}


async function loadTargeting() {
  assert.equal(existsSync(fileURLToPath(targetingModuleUrl)), true);
  return import(targetingModuleUrl);
}


test("surface gap uses raw collision size rather than outline size", async () => {
  const { surfaceGap } = await loadTargeting();
  const oversizedOutline = Object.freeze({
    ...mechanics,
    outline_size_tiles: { x: 9, y: 9, z: 9 },
  });
  const left = unit({ referenceId: 1, x: 1, unitMechanics: oversizedOutline });
  const right = unit({ referenceId: 2, x: 2, unitMechanics: oversizedOutline });

  assert.ok(Math.abs(surfaceGap(left, right) - 0.6) < 1e-12);
});


test("a targetless unit chooses the nearest visible enemy by surface gap", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 3.5, y: 6.5 });
  const nearest = unit({ referenceId: 1700, owner: 3, x: 4.5, y: 6.5 });
  const farther = unit({ referenceId: 1699, owner: 3, x: 5.5, y: 6.5 });
  const snapshot = Object.freeze([attacker, farther, nearest]);

  assert.equal(selectPursuitTarget(attacker, snapshot).referenceId, nearest.referenceId);
});


test("an exact distance tie is broken by reference ID and not owner or array order", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 4, y: 4 });
  const lowerReference = unit({ referenceId: 1699, owner: 4, x: 3, y: 4 });
  const higherReference = unit({ referenceId: 1700, owner: 3, x: 5, y: 4 });
  const snapshot = [attacker, higherReference, lowerReference];

  assert.equal(selectPursuitTarget(attacker, snapshot).referenceId, 1699);
  assert.equal(selectPursuitTarget(attacker, [...snapshot].reverse()).referenceId, 1699);
});


test("acquisition filters dead, friendly, and out-of-sight units", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 0, y: 0 });
  const friendly = unit({ referenceId: 1629, x: 1, y: 0 });
  const deadEnemy = unit({ referenceId: 1699, owner: 3, x: 2, y: 0, alive: false });
  const unseenEnemy = unit({ referenceId: 1700, owner: 3, x: 5.01, y: 0 });

  assert.equal(
    selectPursuitTarget(attacker, [unseenEnemy, friendly, attacker, deadEnemy]),
    null,
  );
});


test("a live locked target is retained without switching", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 0, pursuitTargetId: 1700 });
  const lockedOutsideLos = unit({ referenceId: 1700, owner: 3, x: 8 });
  const nearer = unit({ referenceId: 1699, owner: 3, x: 1 });
  const snapshot = [attacker, nearer, lockedOutsideLos];
  const before = JSON.stringify(snapshot);

  assert.equal(selectPursuitTarget(attacker, snapshot), lockedOutsideLos);
  assert.equal(JSON.stringify(snapshot), before);
});


test("a dead lock is released for normal acquisition", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 0, pursuitTargetId: 1700 });
  const deadLock = unit({ referenceId: 1700, owner: 3, x: 1, alive: false });
  const replacement = unit({ referenceId: 1699, owner: 3, x: 2 });

  assert.equal(
    selectPursuitTarget(attacker, [attacker, deadLock, replacement]),
    replacement,
  );
});


test("melee contact capacity grows from target outline perimeter and attacker footprint", async () => {
  const { meleeContactCapacity } = await loadTargeting();
  const boyar = unit({
    referenceId: 1,
    unitMechanics: boyarMechanics,
  });
  const arbalester = unit({
    referenceId: 2,
    owner: 3,
    x: 4,
    unitMechanics: arbalesterMechanics,
  });
  const elephant = unit({
    referenceId: 3,
    owner: 3,
    x: 4,
    unitMechanics: elephantMechanics,
  });

  assert.equal(meleeContactCapacity(boyar, arbalester, [boyar, arbalester]), 4);
  assert.equal(meleeContactCapacity(boyar, elephant, [boyar, elephant]), 8);
});


test("nearby defenders reduce a target's exposed melee contact capacity", async () => {
  const { meleeContactCapacity } = await loadTargeting();
  const boyar = unit({
    referenceId: 1,
    x: 1,
    y: 5,
    unitMechanics: boyarMechanics,
  });
  const arbalester = unit({
    referenceId: 2,
    owner: 3,
    x: 5,
    y: 5,
    unitMechanics: arbalesterMechanics,
  });
  const defenders = [
    unit({
      referenceId: 3,
      owner: 3,
      x: 5.4,
      y: 5,
      unitMechanics: arbalesterMechanics,
    }),
    unit({
      referenceId: 4,
      owner: 3,
      x: 5,
      y: 5.4,
      unitMechanics: arbalesterMechanics,
    }),
  ];
  const isolated = meleeContactCapacity(boyar, arbalester, [boyar, arbalester]);
  const embedded = meleeContactCapacity(
    boyar,
    arbalester,
    [boyar, arbalester, ...defenders],
  );

  assert.ok(embedded >= 1);
  assert.ok(embedded < isolated);
});


test("a physically full melee target yields to a visible target with free contact capacity", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({
    referenceId: 1,
    x: 0,
    unitMechanics: boyarMechanics,
  });
  const near = unit({
    referenceId: 2,
    owner: 3,
    x: 2,
    unitMechanics: arbalesterMechanics,
  });
  const farther = unit({
    referenceId: 3,
    owner: 3,
    x: 3,
    unitMechanics: arbalesterMechanics,
  });
  const snapshot = [attacker, near, farther];

  assert.equal(selectPursuitTarget(attacker, snapshot, {
    targetLoadById: new Map([[near.referenceId, 3]]),
    targetCapacityFor: () => 3,
  }), farther);
});


test("melee capacity never strands surplus attackers when every target is full", async () => {
  const { selectPursuitTarget } = await loadTargeting();
  const attacker = unit({
    referenceId: 1,
    x: 0,
    unitMechanics: boyarMechanics,
  });
  const near = unit({
    referenceId: 2,
    owner: 3,
    x: 2,
    unitMechanics: arbalesterMechanics,
  });
  const farther = unit({
    referenceId: 3,
    owner: 3,
    x: 3,
    unitMechanics: arbalesterMechanics,
  });
  const snapshot = [attacker, near, farther];

  assert.equal(selectPursuitTarget(attacker, snapshot, {
    targetLoadById: new Map([
      [near.referenceId, 3],
      [farther.referenceId, 3],
    ]),
    targetCapacityFor: () => 3,
  }), near);
});


test("capacity rerouting ignores a target whose straight contact corridor is screened", async () => {
  const { hasDirectMeleeApproach, selectPursuitTarget } = await loadTargeting();
  const attacker = unit({
    referenceId: 1,
    x: 0,
    y: 5,
    unitMechanics: boyarMechanics,
  });
  const exposed = unit({
    referenceId: 2,
    owner: 3,
    x: 4,
    y: 4,
    unitMechanics: arbalesterMechanics,
  });
  const screen = unit({
    referenceId: 3,
    owner: 3,
    x: 3,
    y: 5,
    unitMechanics: arbalesterMechanics,
  });
  const screened = unit({
    referenceId: 4,
    owner: 3,
    x: 4,
    y: 5,
    unitMechanics: arbalesterMechanics,
  });
  const snapshot = [attacker, exposed, screen, screened];

  assert.equal(hasDirectMeleeApproach(attacker, exposed, snapshot), true);
  assert.equal(hasDirectMeleeApproach(attacker, screened, snapshot), false);
  assert.equal(selectPursuitTarget(attacker, snapshot, {
    targetCapacityLoadById: new Map([[screen.referenceId, 1]]),
    targetCapacityFor: () => 1,
    targetAvailabilityFor: (target) => hasDirectMeleeApproach(attacker, target, snapshot),
  }), exposed);
});
