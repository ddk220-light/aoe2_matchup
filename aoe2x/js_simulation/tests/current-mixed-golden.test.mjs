import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";


const root = new URL("../", import.meta.url);
const formations = JSON.parse(await readFile(new URL(
  "../fixtures/current_ranged_golden_formations.json",
  import.meta.url,
), "utf8"));
const map = buildArenaPhysicsMap(JSON.parse(await readFile(new URL(
  "../fixtures/golden_map.json",
  import.meta.url,
), "utf8")));


function cells(family, owner) {
  return family.sides[String(owner)].map(({ position }) => ({
    x: position.x,
    y: position.y,
  }));
}


async function runMixed({ familyName, side2Slug, n2, side3Slug, n3, openingSeed = 0 }) {
  const family = formations.families[familyName];
  const rangedOwner = familyName === "ranged_vs_melee" ? 2 : 3;
  return runFight(root, {
    side2Slug,
    n2,
    side3Slug,
    n3,
    map,
    placementByOwner: { 2: cells(family, 2), 3: cells(family, 3) },
    auxiliaryArmiesByOwner: {
      4: { slug: "scout_cavalry", cells: cells(family, 4) },
    },
    diplomacyByOwner: family.initial_diplomacy,
    triggers: family.triggers,
    victoryTeams: rangedOwner === 2
      ? [{ winnerOwner: 2, owners: [2, 4] }, { winnerOwner: 3, owners: [3] }]
      : [{ winnerOwner: 2, owners: [2] }, { winnerOwner: 3, owners: [3, 4] }],
    preserveOwnerOrientation: true,
    disableAiOrders: true,
    disableKiting: true,
    openingSeed,
  });
}


function assertTransition(fight, { meleeOwner, rangedOwner }) {
  const events = fight.snapshots.flatMap(({ events }) => events);
  const diplomacy = events.find(({ type, sourceOwner, targetOwner }) => (
    type === "diplomacy-changed"
      && sourceOwner === meleeOwner
      && targetOwner === rangedOwner
  ));
  assert.ok(diplomacy, "Player 4 defeat must change melee-to-ranged diplomacy");
  assert.equal(events.some(({ type, owner }) => (
    type === "owner-defeated" && owner === 4
  )), true);
  const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
  const earlyMeleeTarget = events.find(({ type, tick, actorId, targetId }) => (
    tick < diplomacy.tick
      && ["pursuit-acquired", "attack-start", "damage"].includes(type)
      && ownerOf(actorId) === meleeOwner
      && ownerOf(targetId) === rangedOwner
  ));
  assert.equal(earlyMeleeTarget, undefined);
  assert.equal(events.some(({ type, tick, actorId, targetId }) => (
    tick > diplomacy.tick
      && ["pursuit-acquired", "attack-start", "damage"].includes(type)
      && ownerOf(actorId) === meleeOwner
      && ownerOf(targetId) === rangedOwner
  )), true);
  assert.equal(events.some(({ type, tick, actorId, targetId }) => (
    tick < diplomacy.tick
      && ["attack-start", "damage"].includes(type)
      && ownerOf(actorId) === rangedOwner
      && ownerOf(targetId) === meleeOwner
  )), true);
}


test("ranged-vs-melee runs real Player 4 combat before directional hostility", async () => {
  const fight = await runMixed({
    familyName: "ranged_vs_melee",
    side2Slug: "arbalester",
    n2: 27,
    side3Slug: "paladin",
    n3: 14,
  });
  assert.equal(Object.values(fight.unitIndex).filter(({ owner }) => owner === 4).length, 9);
  assert.equal(fight.orientationNormalised, false);
  assert.equal(fight.winnerOwner, 3);
  assert.ok(fight.winnerHp > 0);
  assertTransition(fight, { meleeOwner: 3, rangedOwner: 2 });
  const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
  const firstAuxiliaryTargetByActor = new Map();
  for (const current of fight.snapshots.flatMap(({ events }) => events)) {
    if (current.type !== "pursuit-acquired"
        || ownerOf(current.actorId) !== 3
        || ownerOf(current.targetId) !== 4
        || firstAuxiliaryTargetByActor.has(current.actorId)) continue;
    firstAuxiliaryTargetByActor.set(current.actorId, current.targetId);
  }
  assert.equal(firstAuxiliaryTargetByActor.size, 14);
  assert.equal(
    new Set(firstAuxiliaryTargetByActor.values()).size,
    1,
    "a compact melee cohort commits its first lock to one central Player-4 breach",
  );
});


test("melee-vs-ranged mirrors the golden roles without relabelling owners", async () => {
  const fight = await runMixed({
    familyName: "melee_vs_ranged",
    side2Slug: "paladin",
    n2: 14,
    side3Slug: "arbalester",
    n3: 27,
  });
  assert.equal(Object.values(fight.unitIndex).filter(({ owner }) => owner === 4).length, 9);
  assert.equal(fight.orientationNormalised, false);
  assert.equal(fight.winnerOwner, 2);
  assert.ok(fight.winnerHp > 0);
  assertTransition(fight, { meleeOwner: 2, rangedOwner: 3 });
});


test("Ratha melee versus Arbalester preserves ranged fallback and post-gate lanes", async () => {
  const fight = await runMixed({
    familyName: "melee_vs_ranged",
    side2Slug: "elite_ratha_(melee)_bengalis",
    n2: 15,
    side3Slug: "arbalester",
    n3: 27,
    openingSeed: 3,
  });
  assert.equal(fight.winnerOwner, 2);
  const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
  const firstTargetByActor = new Map();
  for (const current of fight.snapshots.flatMap(({ events }) => events)) {
    if (current.type !== "pursuit-acquired"
        || firstTargetByActor.has(current.actorId)) continue;
    firstTargetByActor.set(current.actorId, current.targetId);
  }
  const rangedOpeningTargets = new Set([...firstTargetByActor]
    .filter(([actorId, targetId]) => ownerOf(actorId) === 3 && ownerOf(targetId) === 2)
    .map(([, targetId]) => targetId));
  assert.equal(rangedOpeningTargets.size, 2,
    "the ranged cohort keeps a small adjacent first-lock fallback");

  const events = fight.snapshots.flatMap(({ events }) => events);
  const diplomacyTick = events.find(({ type, sourceOwner, targetOwner }) => (
    type === "diplomacy-changed" && sourceOwner === 2 && targetOwner === 3
  )).tick;
  const meleePostGateFirstTargets = new Map();
  for (const current of events) {
    if (current.tick <= diplomacyTick || current.type !== "pursuit-acquired"
        || ownerOf(current.actorId) !== 2 || ownerOf(current.targetId) !== 3
        || meleePostGateFirstTargets.has(current.actorId)) continue;
    meleePostGateFirstTargets.set(current.actorId, current.targetId);
  }
  assert.ok(new Set(meleePostGateFirstTargets.values()).size >= 3,
    "an experienced melee cohort retains multiple ranged-front contact lanes");
});


test("RvR first acquisition follows the exposed firing front", async () => {
  const family = formations.families.ranged_vs_ranged;
  const fight = await runFight(root, {
    side2Slug: "arbalester",
    n2: 27,
    side3Slug: "hand_cannoneer",
    n3: 19,
    map,
    placementByOwner: { 2: cells(family, 2), 3: cells(family, 3) },
    diplomacyByOwner: family.initial_diplomacy,
    triggers: family.triggers,
    preserveOwnerOrientation: true,
    disableAiOrders: true,
    disableKiting: true,
    openingSeed: 0,
  });
  const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
  const firstByActor = new Map();
  const firstAttackByActor = new Map();
  for (const current of fight.snapshots.flatMap(({ events }) => events)) {
    if (current.type !== "pursuit-acquired" || firstByActor.has(current.actorId)) continue;
    firstByActor.set(current.actorId, current.targetId);
  }
  for (const current of fight.snapshots.flatMap(({ events }) => events)) {
    if (current.type === "attack-start" && !firstAttackByActor.has(current.actorId)) {
      firstAttackByActor.set(current.actorId, current.tick);
    }
  }
  for (const [actorId, attackTick] of firstAttackByActor) {
    const acquired = fight.snapshots.flatMap(({ events }) => events).find((current) => (
      current.type === "pursuit-acquired" && current.actorId === actorId
    ));
    assert.ok(acquired, `unit ${actorId} attacked without first acquiring a target`);
    assert.ok(
      attackTick >= acquired.tick,
      `unit ${actorId} attacked at ${attackTick} before acquisition at ${acquired.tick}`,
    );
  }
  const distinctTargets = (owner) => new Set([...firstByActor]
    .filter(([actorId]) => ownerOf(actorId) === owner)
    .map(([, targetId]) => targetId)).size;
  // Both cohorts distribute first acquisition across the exposed front rather
  // than collapsing the whole army onto one roster-ordered target. Exact
  // target counts are stochastic opening output, not an engine invariant.
  assert.ok(distinctTargets(2) >= 2);
  assert.ok(distinctTargets(3) >= 2);
  assert.equal(fight.winnerOwner, 2);
});
