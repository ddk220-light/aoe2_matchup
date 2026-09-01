import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

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


function argument(name) {
  const prefix = `--${name}=`;
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length);
}


async function runFamily(familyName, openingSeed = 0, matchup = {}) {
  const family = formations.families[familyName];
  const rangedOwner = familyName === "ranged_vs_melee" ? 2 : 3;
  const meleeOwner = rangedOwner === 2 ? 3 : 2;
  const defaultSide2Slug = rangedOwner === 2 ? "arbalester" : "paladin";
  const defaultSide3Slug = rangedOwner === 3 ? "arbalester" : "paladin";
  const defaultN2 = rangedOwner === 2 ? 27 : 14;
  const defaultN3 = rangedOwner === 3 ? 27 : 14;
  const fight = await runFight(ROOT, {
    side2Slug: matchup.side2Slug ?? defaultSide2Slug,
    n2: matchup.n2 ?? defaultN2,
    side3Slug: matchup.side3Slug ?? defaultSide3Slug,
    n3: matchup.n3 ?? defaultN3,
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
    ...(process.argv.includes("--ranged-pressure")
      ? { rangedTargetPressureOwner: rangedOwner }
      : {}),
    openingSeed,
  });
  const events = fight.snapshots.flatMap(({ events: tickEvents }) => tickEvents);
  const ownerOf = (referenceId) => fight.unitIndex[referenceId]?.owner;
  const firstTargets = {};
  const pursuitTargetSequences = {};
  const firstTargetTicks = {};
  const firstAttackTicks = {};
  for (const currentOwner of [2, 3, 4]) {
    const firstByActor = new Map();
    const sequenceByActor = new Map();
    for (const current of events) {
      if (current.type !== "pursuit-acquired") continue;
      if (ownerOf(current.actorId) !== currentOwner) continue;
      const sequence = sequenceByActor.get(current.actorId) ?? [];
      if (sequence.at(-1)?.targetId !== current.targetId) {
        sequence.push({ tick: current.tick, targetId: current.targetId });
        sequenceByActor.set(current.actorId, sequence);
      }
      if (!firstByActor.has(current.actorId)) firstByActor.set(current.actorId, current.targetId);
    }
    firstTargets[currentOwner] = Object.fromEntries([...new Set(firstByActor.values())]
      .sort((left, right) => left - right)
      .map((targetId) => [targetId, [...firstByActor.values()]
        .filter((value) => value === targetId).length]));
    pursuitTargetSequences[currentOwner] = {
      unitsRetargeting: [...sequenceByActor.values()]
        .filter((sequence) => sequence.length > 1).length,
      retargets: [...sequenceByActor.values()]
        .reduce((total, sequence) => total + Math.max(0, sequence.length - 1), 0),
      units: Object.fromEntries([...sequenceByActor]
        .sort(([left], [right]) => left - right)),
    };
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
  const gateSnapshot = p4Defeat ? fight.snapshots[p4Defeat.tick] : null;
  const gateStateByOwner = gateSnapshot ? Object.fromEntries([2, 3, 4].map((owner) => {
    const gateUnits = gateSnapshot.units.filter(([referenceId, , , , , alive]) => (
      alive === 1 && ownerOf(referenceId) === owner
    ));
    return [owner, {
      live: gateUnits.length,
      hp: gateUnits.reduce((total, unit) => total + unit[4], 0),
    }];
  })) : null;
  const damageByOwner = Object.fromEntries([2, 3, 4].map((owner) => {
    const hits = events.filter(({ type, actorId }) => (
      type === "damage" && ownerOf(actorId) === owner
    ));
    const byAmount = {};
    for (const hit of hits) {
      const key = String(Math.round(hit.amount * 10000) / 10000);
      byAmount[key] = (byAmount[key] ?? 0) + 1;
    }
    return [owner, {
      hits: hits.length,
      damage: hits.reduce((total, hit) => total + hit.amount, 0),
      byAmount,
    }];
  }));
  const principalPostGateFirstByActor = new Map();
  for (const current of events) {
    if (current.type !== "pursuit-acquired"
        || ownerOf(current.actorId) !== meleeOwner
        || ownerOf(current.targetId) !== rangedOwner
        || (p4Defeat && current.tick < p4Defeat.tick)
        || principalPostGateFirstByActor.has(current.actorId)) continue;
    principalPostGateFirstByActor.set(current.actorId, current.targetId);
  }
  const principalPostGateTargets = Object.fromEntries(
    [...new Set(principalPostGateFirstByActor.values())]
      .sort((left, right) => left - right)
      .map((targetId) => [
        targetId,
        [...principalPostGateFirstByActor.values()].filter((value) => value === targetId).length,
      ]),
  );
  const auxiliarySequenceByActor = new Map();
  for (const current of events) {
    if (current.type !== "pursuit-acquired"
        || ownerOf(current.actorId) !== meleeOwner
        || ownerOf(current.targetId) !== 4
        || (p4Defeat && current.tick > p4Defeat.tick)) continue;
    const sequence = auxiliarySequenceByActor.get(current.actorId) ?? [];
    if (sequence.at(-1)?.targetId !== current.targetId) {
      sequence.push({ tick: current.tick, targetId: current.targetId });
      auxiliarySequenceByActor.set(current.actorId, sequence);
    }
  }
  const auxiliaryPursuit = {
    units: auxiliarySequenceByActor.size,
    unitsRetargeting: [...auxiliarySequenceByActor.values()]
      .filter((sequence) => sequence.length > 1).length,
    retargets: [...auxiliarySequenceByActor.values()]
      .reduce((total, sequence) => total + Math.max(0, sequence.length - 1), 0),
    sequences: Object.fromEntries([...auxiliarySequenceByActor]
      .sort(([left], [right]) => left - right)),
  };
  const deaths = events.filter(({ type, targetId }) => (
    type === "death" && ownerOf(targetId) === 4
  )).map(({ tick }) => tick);
  const deathTickByReference = Object.fromEntries(events
    .filter(({ type }) => type === "death")
    .map(({ targetId, tick }) => [targetId, tick]));
  const firstAuxiliaryContact = events.find(({ type, actorId, targetId }) => (
    type === "pursuit-acquired"
      && ownerOf(actorId) === meleeOwner
      && ownerOf(targetId) === 4
  ));
  const openingContactGeometry = firstAuxiliaryContact
    ? auxiliaryContactGeometry({
      fight,
      family,
      meleeOwner,
      event: firstAuxiliaryContact,
      ownerOf,
    })
    : null;
  const samples = [];
  const combatSamples = [];
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
  for (let tick = 0; tick <= fight.ticks; tick += 60) {
    const snapshot = fight.snapshots[tick];
    if (!snapshot) break;
    const tickEvents = events.filter((current) => (
      current.tick >= tick && current.tick < tick + 60
    ));
    const byOwner = Object.fromEntries([2, 3, 4].map((owner) => {
      const army = snapshot.units.filter(([referenceId, , , , , alive]) => (
        ownerOf(referenceId) === owner && alive === 1
      ));
      const activeAgainst = (targetOwner) => army.filter(([
        , , , , , , action, pursuitTargetId, engagedTargetId, attackTargetId,
      ]) => {
        const targetId = attackTargetId ?? engagedTargetId ?? pursuitTargetId;
        return (action === "attacking" || action === "reload")
          && ownerOf(targetId) === targetOwner;
      }).length;
      return [owner, {
        live: army.length,
        hp: army.reduce((total, unit) => total + unit[4], 0),
        attacking: army.filter(([, , , , , , action]) => action === "attacking").length,
        reloading: army.filter(([, , , , , , action]) => action === "reload").length,
        activeAgainstPlayer4: activeAgainst(4),
        activeAgainstPrincipal: activeAgainst(owner === 2 ? 3 : 2),
        attackStarts: tickEvents.filter(({ type, actorId }) => (
          type === "attack-start" && ownerOf(actorId) === owner
        )).length,
        damageHits: tickEvents.filter(({ type, actorId }) => (
          type === "damage" && ownerOf(actorId) === owner
        )).length,
      }];
    }));
    combatSamples.push({ tick, seconds: tick / 60, byOwner });
  }
  const unitDebug = process.argv.includes("--unit-debug")
    ? buildUnitDebug({ fight, ownerOf, p4DefeatTick: p4Defeat?.tick ?? 0, events })
    : null;
  return {
    family: familyName,
    openingSeed,
    rangedOwner,
    meleeOwner,
    winnerOwner: fight.winnerOwner,
    winnerHp: fight.winnerHp,
    ticks: fight.ticks,
    p4DefeatTick: p4Defeat?.tick ?? null,
    gateStateByOwner,
    damageByOwner,
    p4DeathTicks: deaths,
    deathTickByReference,
    auxiliaryPursuit,
    principalPostGateTargets,
    openingContactGeometry,
    firstTargets,
    pursuitTargetSequences,
    firstTargetTicks,
    firstAttackTicks,
    preScanDistances,
    samples,
    combatSamples,
    ...(unitDebug ? { unitDebug } : {}),
  };
}


function buildUnitDebug({ fight, ownerOf, p4DefeatTick, events }) {
  const actorCombat = Object.fromEntries(
    Object.keys(fight.unitIndex).map((referenceId) => [referenceId, {
      owner: ownerOf(Number(referenceId)),
      attackStarts: 0,
      damageHits: 0,
      firstAttackTick: null,
      lastAttackTick: null,
    }]),
  );
  for (const current of events) {
    if (current.tick < p4DefeatTick) continue;
    const row = actorCombat[current.actorId];
    if (!row) continue;
    if (current.type === "attack-start") {
      row.attackStarts += 1;
      row.firstAttackTick ??= current.tick;
      row.lastAttackTick = current.tick;
    }
    if (current.type === "damage") row.damageHits += 1;
  }
  const samples = [];
  for (let tick = 0; tick <= fight.ticks; tick += 60) {
    const snapshot = fight.snapshots[tick];
    if (!snapshot) break;
    const live = snapshot.units.filter(([, , , , , alive]) => alive === 1);
    const byId = new Map(live.map((unit) => [unit[0], unit]));
    samples.push({
      tick,
      secondsAfterGate: (tick - p4DefeatTick) / 60,
      units: live.filter(([referenceId]) => [2, 3].includes(ownerOf(referenceId)))
        .map(([
          referenceId, x, y, , hp, , action,
          pursuitTargetId, engagedTargetId, attackTargetId,
        ]) => {
          const hostiles = live.filter(([candidateId]) => (
            ownerOf(candidateId) !== ownerOf(referenceId)
              && ownerOf(candidateId) !== 4
          ));
          const targetId = attackTargetId ?? engagedTargetId ?? pursuitTargetId;
          const target = byId.get(targetId);
          return {
            referenceId,
            owner: ownerOf(referenceId),
            x,
            y,
            hp,
            action,
            pursuitTargetId,
            engagedTargetId,
            attackTargetId,
            targetOwner: ownerOf(targetId),
            targetDistance: target ? Math.hypot(target[1] - x, target[2] - y) : null,
            nearestHostileDistance: hostiles.length > 0
              ? Math.min(...hostiles.map(([, hx, hy]) => Math.hypot(hx - x, hy - y)))
              : null,
          };
        }),
    });
  }
  return { actorCombat, samples };
}


function auxiliaryContactGeometry({ fight, family, meleeOwner, event, ownerOf }) {
  const snapshot = fight.snapshots[event.tick];
  const initial = fight.snapshots[0];
  const cohort = initial.units.filter(([referenceId]) => ownerOf(referenceId) === meleeOwner);
  const originX = cohort.reduce((total, [, x]) => total + x, 0) / cohort.length;
  const originY = cohort.reduce((total, [, , y]) => total + y, 0) / cohort.length;
  const patrol = family.triggers
    .flatMap(({ effects = [] }) => effects)
    .find(({ type, owner }) => type === "patrol" && owner === meleeOwner);
  const directionX = patrol.x - originX;
  const directionY = patrol.y - originY;
  const length = Math.hypot(directionX, directionY);
  const actor = snapshot.units.find(([referenceId]) => referenceId === event.actorId);
  const scenarioCells = family.sides["4"].map(({ reference_id: scenarioReferenceId, position }) => ({
    scenarioReferenceId,
    x: position.x,
    y: position.y,
  }));
  const auxiliaryIds = initial.units
    .filter(([referenceId]) => ownerOf(referenceId) === 4)
    .map(([referenceId]) => referenceId);
  return {
    tick: event.tick,
    seconds: event.tick / 60,
    actorId: event.actorId,
    selectedTargetId: event.targetId,
    units: snapshot.units
      .filter(([referenceId, , , , , alive]) => ownerOf(referenceId) === 4 && alive === 1)
      .map(([referenceId, x, y]) => {
        const relativeX = x - originX;
        const relativeY = y - originY;
        const scenario = scenarioCells[auxiliaryIds.indexOf(referenceId)] ?? null;
        return {
          referenceId,
          scenarioReferenceId: scenario?.scenarioReferenceId ?? null,
          x,
          y,
          longitudinal: (relativeX * directionX + relativeY * directionY) / length,
          lateral: (relativeX * -directionY + relativeY * directionX) / length,
          actorDistance: actor ? Math.hypot(x - actor[1], y - actor[2]) : null,
        };
      })
      .sort((left, right) => left.lateral - right.lateral
        || left.longitudinal - right.longitudinal
        || left.referenceId - right.referenceId),
  };
}


const result = [];
const seeds = process.argv.includes("--five-seeds") ? [0, 1, 2, 3, 4] : [0];
const familiesToRun = process.argv.includes("--rvm-only")
  ? ["ranged_vs_melee"]
  : process.argv.includes("--mvr-only") ? ["melee_vs_ranged"]
    : ["ranged_vs_melee", "melee_vs_ranged"];
const matchup = {
  ...(argument("side2") ? { side2Slug: argument("side2") } : {}),
  ...(argument("n2") ? { n2: Number.parseInt(argument("n2"), 10) } : {}),
  ...(argument("side3") ? { side3Slug: argument("side3") } : {}),
  ...(argument("n3") ? { n3: Number.parseInt(argument("n3"), 10) } : {}),
};
for (const openingSeed of seeds) {
  for (const family of familiesToRun) {
    result.push(await runFamily(family, openingSeed, matchup));
  }
}
const published = process.argv.includes("--unit-debug")
  ? result
  : process.argv.includes("--trajectory")
  ? result.map(({
    family, openingSeed, rangedOwner, meleeOwner, winnerOwner, winnerHp, ticks,
    p4DefeatTick, combatSamples,
  }) => ({
    family, openingSeed, rangedOwner, meleeOwner, winnerOwner, winnerHp, ticks,
    player4DefeatSeconds: p4DefeatTick / 60,
    combatSamples,
  }))
  : process.argv.includes("--summary")
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
      principalPostGateTargets: rows.map(({
        openingSeed, principalPostGateTargets,
      }) => ({ openingSeed, principalPostGateTargets })),
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
const outputPath = argument("output");
if (outputPath) {
  const resolvedOutput = resolve(outputPath);
  await mkdir(dirname(resolvedOutput), { recursive: true });
  await writeFile(resolvedOutput, `${JSON.stringify(published, null, 2)}\n`);
  process.stdout.write(`${resolvedOutput}\n`);
} else {
  process.stdout.write(`${JSON.stringify(published, null, 2)}\n`);
}


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
