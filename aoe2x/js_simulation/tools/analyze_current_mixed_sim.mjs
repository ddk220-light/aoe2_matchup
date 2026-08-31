import { readFile } from "node:fs/promises";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";


const ROOT = new URL("../", import.meta.url);
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


async function runFamily(familyName, openingSeed = 0) {
  const family = formations.families[familyName];
  const rangedOwner = familyName === "ranged_vs_melee" ? 2 : 3;
  const meleeOwner = rangedOwner === 2 ? 3 : 2;
  const fight = await runFight(ROOT, {
    side2Slug: rangedOwner === 2 ? "arbalester" : "paladin",
    n2: rangedOwner === 2 ? 27 : 14,
    side3Slug: rangedOwner === 3 ? "arbalester" : "paladin",
    n3: rangedOwner === 3 ? 27 : 14,
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
  const events = fight.snapshots.flatMap(({ events: tickEvents }) => tickEvents);
  const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
  const firstTargets = {};
  const firstTargetTicks = {};
  const firstAttackTicks = {};
  for (const currentOwner of [2, 3, 4]) {
    const firstByActor = new Map();
    for (const current of events) {
      if (current.type !== "pursuit-acquired") continue;
      if (ownerOf(current.actorId) !== currentOwner || firstByActor.has(current.actorId)) continue;
      firstByActor.set(current.actorId, current.targetId);
    }
    firstTargets[currentOwner] = Object.fromEntries([...new Set(firstByActor.values())]
      .sort((left, right) => left - right)
      .map((targetId) => [targetId, [...firstByActor.values()]
        .filter((value) => value === targetId).length]));
    firstTargetTicks[currentOwner] = events
      .filter(({ type, actorId }) => type === "pursuit-acquired"
        && ownerOf(actorId) === currentOwner)
      .map(({ tick: eventTick }) => eventTick)
      .sort((left, right) => left - right);
    const attacked = new Set();
    firstAttackTicks[currentOwner] = events
      .filter(({ type, actorId }) => {
        if (type !== "attack-start" || ownerOf(actorId) !== currentOwner
            || attacked.has(actorId)) return false;
        attacked.add(actorId);
        return true;
      })
      .map(({ tick: eventTick }) => eventTick)
      .sort((left, right) => left - right);
  }
  const p4Defeat = events.find(({ type, owner }) => type === "owner-defeated" && owner === 4);
  const deaths = events.filter(({ type, targetId }) => (
    type === "death" && ownerOf(targetId) === 4
  )).map(({ tick }) => tick);
  const samples = [];
  const preScanDistances = {};
  for (const [currentOwner, scanTick] of [[2, 95], [3, 89], [4, 91]]) {
    const unitsAtTick = fight.snapshots[scanTick]?.units ?? [];
    const hostileOwners = currentOwner === meleeOwner
      ? [4]
      : currentOwner === 4 ? [meleeOwner] : [meleeOwner];
    const enemies = unitsAtTick.filter(([referenceId, , , , , alive]) => (
      alive === 1 && hostileOwners.includes(ownerOf(referenceId))
    ));
    preScanDistances[currentOwner] = unitsAtTick
      .filter(([referenceId, , , , , alive]) => (
        alive === 1 && ownerOf(referenceId) === currentOwner
      ))
      .map(([referenceId, x, y]) => ({
        referenceId,
        nearest: Math.min(...enemies.map(([, ex, ey]) => Math.hypot(ex - x, ey - y))),
      }))
      .sort((left, right) => left.nearest - right.nearest);
  }
  for (let tick = 120; tick <= (p4Defeat?.tick ?? 0) + 120; tick += 120) {
    const snapshot = fight.snapshots[tick];
    if (!snapshot) break;
    const p4 = snapshot.units.filter(([referenceId, , , , , alive]) => (
      fight.unitIndex[referenceId].owner === 4 && alive === 1
    ));
    const melee = snapshot.units.filter(([referenceId, , , , , alive]) => (
      fight.unitIndex[referenceId].owner === meleeOwner && alive === 1
    ));
    samples.push({
      tick,
      p4Live: p4.length,
      p4Hp: p4.reduce((total, unit) => total + unit[4], 0),
      meleeAttackingP4: melee.filter(([, , , , , , action, , , attackTargetId]) => (
        action === "attacking" && ownerOf(attackTargetId) === 4
      )).length,
    });
  }
  return {
    family: familyName,
    openingSeed,
    rangedOwner,
    meleeOwner,
    winnerOwner: fight.winnerOwner,
    winnerHp: fight.winnerHp,
    ticks: fight.ticks,
    p4DefeatTick: p4Defeat?.tick ?? null,
    p4DeathTicks: deaths,
    firstTargets,
    firstTargetTicks,
    firstAttackTicks,
    preScanDistances,
    samples,
  };
}


const result = [];
const seeds = process.argv.includes("--five-seeds") ? [0, 1, 2, 3, 4] : [0];
const familiesToRun = process.argv.includes("--rvm-only")
  ? ["ranged_vs_melee"]
  : process.argv.includes("--mvr-only") ? ["melee_vs_ranged"]
    : ["ranged_vs_melee", "melee_vs_ranged"];
for (const openingSeed of seeds) {
  for (const family of familiesToRun) {
    result.push(await runFamily(family, openingSeed));
  }
}
const published = process.argv.includes("--summary")
  ? familiesToRun.map((family) => {
    const rows = result.filter(({ family: rowFamily }) => rowFamily === family);
    return {
      family,
      runs: rows.length,
      winnerOwners: rows.map(({ winnerOwner }) => winnerOwner),
      winnerHp: stats(rows.map(({ winnerHp }) => winnerHp)),
      durationSeconds: stats(rows.map(({ ticks }) => ticks / 60)),
      player4DefeatSeconds: stats(rows.map(({ p4DefeatTick }) => p4DefeatTick / 60)),
      firstTargets: rows.map(({ openingSeed, firstTargets }) => ({ openingSeed, firstTargets })),
    };
  })
  : process.argv.includes("--compact")
  ? result.map(({ firstTargetTicks, firstAttackTicks, preScanDistances, ...row }) => ({
    ...row,
    firstTargetTicks: Object.fromEntries(Object.entries(firstTargetTicks).map(([owner, ticks]) => (
      [owner, ticks.slice(0, Number(fightCountForOwner(owner, row)))]
    ))),
    firstAttackTicks,
  }))
  : result;
process.stdout.write(`${JSON.stringify(published, null, 2)}\n`);


function fightCountForOwner(owner, row) {
  if (Number(owner) === 4) return 9;
  return Number(owner) === row.rangedOwner ? 27 : 14;
}


function stats(values) {
  return {
    min: Math.min(...values),
    mean: values.reduce((total, value) => total + value, 0) / values.length,
    max: Math.max(...values),
    values,
  };
}
