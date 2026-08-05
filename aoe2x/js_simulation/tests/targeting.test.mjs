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


function unit({
  referenceId,
  owner = 2,
  x = 0,
  y = 0,
  alive = true,
  targetId = null,
  unitMechanics = mechanics,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive,
    targetId,
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
  const { selectTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 3.5, y: 6.5 });
  const nearest = unit({ referenceId: 1700, owner: 3, x: 4.5, y: 6.5 });
  const farther = unit({ referenceId: 1699, owner: 3, x: 5.5, y: 6.5 });
  const snapshot = Object.freeze([attacker, farther, nearest]);

  assert.equal(selectTarget(attacker, snapshot).referenceId, nearest.referenceId);
});


test("an exact distance tie is broken by reference ID and not owner or array order", async () => {
  const { selectTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 4, y: 4 });
  const lowerReference = unit({ referenceId: 1699, owner: 4, x: 3, y: 4 });
  const higherReference = unit({ referenceId: 1700, owner: 3, x: 5, y: 4 });
  const snapshot = [attacker, higherReference, lowerReference];

  assert.equal(selectTarget(attacker, snapshot).referenceId, 1699);
  assert.equal(selectTarget(attacker, [...snapshot].reverse()).referenceId, 1699);
});


test("acquisition filters dead, friendly, and out-of-sight units", async () => {
  const { selectTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 0, y: 0 });
  const friendly = unit({ referenceId: 1629, x: 1, y: 0 });
  const deadEnemy = unit({ referenceId: 1699, owner: 3, x: 2, y: 0, alive: false });
  const unseenEnemy = unit({ referenceId: 1700, owner: 3, x: 5.01, y: 0 });

  assert.equal(
    selectTarget(attacker, [unseenEnemy, friendly, attacker, deadEnemy]),
    null,
  );
});


test("a live locked target is retained without switching", async () => {
  const { selectTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 0, targetId: 1700 });
  const lockedOutsideLos = unit({ referenceId: 1700, owner: 3, x: 8 });
  const nearer = unit({ referenceId: 1699, owner: 3, x: 1 });
  const snapshot = [attacker, nearer, lockedOutsideLos];
  const before = JSON.stringify(snapshot);

  assert.equal(selectTarget(attacker, snapshot), lockedOutsideLos);
  assert.equal(JSON.stringify(snapshot), before);
});


test("a dead lock is released for normal acquisition", async () => {
  const { selectTarget } = await loadTargeting();
  const attacker = unit({ referenceId: 1628, x: 0, targetId: 1700 });
  const deadLock = unit({ referenceId: 1700, owner: 3, x: 1, alive: false });
  const replacement = unit({ referenceId: 1699, owner: 3, x: 2 });

  assert.equal(
    selectTarget(attacker, [attacker, deadLock, replacement]),
    replacement,
  );
});
