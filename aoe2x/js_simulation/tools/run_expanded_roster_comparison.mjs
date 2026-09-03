// Outcome comparison for a manifest produced by record_ranged_matrix_repeats.py
// --matrix expanded. Every simulation reuses the exact captured counts and the
// literal first-N placements, patrols, diplomacy and triggers from the matching
// current golden scenario. Combat mechanics remain wholly generic.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";
import { unitBySlug } from "../src/unit-registry.js";


const ROOT = new URL("../", import.meta.url);
const DEFAULT_CAPTURE = new URL(
  "../calibration/live_observations/expanded_roster_smoke_1x_2026-08-31/",
  import.meta.url,
);
const DEFAULT_OUTPUT = new URL(
  "../calibration/reports/expanded_roster_smoke_current_engine_2026-08-31/results.json",
  import.meta.url,
);


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function summary(values) {
  return {
    mean: mean(values),
    min: Math.min(...values),
    max: Math.max(...values),
  };
}


async function loadMechanics(unit) {
  return JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${unit.fixture}`, import.meta.url), "utf8"));
}


function positionCells(side) {
  return side.map(({ position }) => ({ x: position.x, y: position.y }));
}


function mixedVictoryTeams(family) {
  if (family !== "ranged_vs_melee" && family !== "melee_vs_ranged") return undefined;
  const rangedOwner = family === "ranged_vs_melee" ? 2 : 3;
  const meleeOwner = rangedOwner === 2 ? 3 : 2;
  return [
    { winnerOwner: rangedOwner, owners: [rangedOwner, 4] },
    { winnerOwner: meleeOwner, owners: [meleeOwner] },
  ];
}


function scenarioInputs(matchup, rangedFormations, meleeFormation) {
  if (matchup.family === "melee_vs_melee") {
    return {
      placementByOwner: {
        2: positionCells(meleeFormation.sides["2"]),
        3: positionCells(meleeFormation.sides["3"]),
      },
      openingPatrolByOwner: Object.fromEntries(
        Object.entries(meleeFormation.opening_patrol.by_owner)
          .map(([owner, patrol]) => [owner, { x: patrol.x, y: patrol.y }]),
      ),
    };
  }
  const formation = rangedFormations.families[matchup.family];
  if (!formation) throw new RangeError(`missing golden formation ${matchup.family}`);
  return {
    placementByOwner: {
      2: positionCells(formation.sides["2"]),
      3: positionCells(formation.sides["3"]),
    },
    ...(formation.sides["4"]?.length ? {
      auxiliaryArmiesByOwner: {
        4: { slug: "scout_cavalry", cells: positionCells(formation.sides["4"]) },
      },
    } : {}),
    diplomacyByOwner: formation.initial_diplomacy,
    triggers: formation.triggers,
    victoryTeams: mixedVictoryTeams(matchup.family),
  };
}


function observedOwner(observed, side2, side3) {
  if (observed.winner === side2.slug) return 2;
  if (observed.winner === side3.slug) return 3;
  throw new Error(`capture winner ${observed.winner} does not match either roster side`);
}


function simulationMetrics(run) {
  const ownerOf = (referenceId) => run.unitIndex[referenceId]?.owner;
  const formationSummary = (rawUnits, owner) => {
    const selected = rawUnits.filter((raw) => raw[5] === 1 && ownerOf(raw[0]) === owner);
    const aliveByReference = new Map(rawUnits
      .filter((raw) => raw[5] === 1)
      .map((raw) => [raw[0], raw]));
    const assignedTargetIds = selected.map((raw) => raw[9] ?? raw[8] ?? raw[7])
      .filter((targetId) => (
        Number.isSafeInteger(targetId)
          && aliveByReference.has(targetId)
          && ownerOf(targetId) !== owner
      ));
    const assignedTargetCounts = Object.fromEntries([...new Set(assignedTargetIds)]
      .sort((left, right) => left - right)
      .map((targetId) => [
        targetId,
        assignedTargetIds.filter((current) => current === targetId).length,
      ]));
    let overlapPairs = 0;
    let overlapDepthSum = 0;
    let maxOverlapDepth = 0;
    const overlapped = new Set();
    let boxOverlapPairs = 0;
    let boxOverlapDepthSum = 0;
    let maxBoxOverlapDepth = 0;
    const boxOverlapped = new Set();
    const boxOverlapByCommitment = {
      committedCommitted: { pairs: 0, depth: 0 },
      mixed: { pairs: 0, depth: 0 },
      uncommittedUncommitted: { pairs: 0, depth: 0 },
    };
    const boxNeighbors = new Map(selected.map((raw) => [raw[0], new Set()]));
    const nearest = new Map(selected.map((raw) => [raw[0], Number.POSITIVE_INFINITY]));
    for (let left = 0; left < selected.length; left += 1) {
      for (let right = left + 1; right < selected.length; right += 1) {
        const a = selected[left];
        const b = selected[right];
        const extent = run.unitIndex[a[0]].collisionRadius
          + run.unitIndex[b[0]].collisionRadius;
        const dx = Math.abs(a[1] - b[1]);
        const dy = Math.abs(a[2] - b[2]);
        const distance = Math.hypot(dx, dy);
        nearest.set(a[0], Math.min(nearest.get(a[0]), distance));
        nearest.set(b[0], Math.min(nearest.get(b[0]), distance));
        const overlapDepth = extent - distance;
        if (overlapDepth > 1e-12) {
          overlapPairs += 1;
          overlapDepthSum += overlapDepth;
          maxOverlapDepth = Math.max(maxOverlapDepth, overlapDepth);
          overlapped.add(a[0]);
          overlapped.add(b[0]);
        }
        const boxOverlapDepth = extent - Math.max(dx, dy);
        if (boxOverlapDepth > 1e-12) {
          boxOverlapPairs += 1;
          boxOverlapDepthSum += boxOverlapDepth;
          maxBoxOverlapDepth = Math.max(maxBoxOverlapDepth, boxOverlapDepth);
          boxOverlapped.add(a[0]);
          boxOverlapped.add(b[0]);
          boxNeighbors.get(a[0]).add(b[0]);
          boxNeighbors.get(b[0]).add(a[0]);
          const committed = [a, b].map((raw) => (
            raw[6] === "attacking" || raw[6] === "reload"
          ));
          const commitment = committed.every(Boolean)
            ? "committedCommitted"
            : committed.some(Boolean) ? "mixed" : "uncommittedUncommitted";
          boxOverlapByCommitment[commitment].pairs += 1;
          boxOverlapByCommitment[commitment].depth += boxOverlapDepth;
        }
      }
    }
    const byReference = new Map(selected.map((raw) => [raw[0], raw]));
    const sharedBoxFraction = (referenceIds) => {
      const members = referenceIds.map((referenceId) => byReference.get(referenceId));
      const radii = referenceIds.map((referenceId) => (
        run.unitIndex[referenceId].collisionRadius
      ));
      const width = Math.max(0,
        Math.min(...members.map((raw, index) => raw[1] + radii[index]))
          - Math.max(...members.map((raw, index) => raw[1] - radii[index])));
      const height = Math.max(0,
        Math.min(...members.map((raw, index) => raw[2] + radii[index]))
          - Math.max(...members.map((raw, index) => raw[2] - radii[index])));
      const smallestArea = Math.min(...radii.map((radius) => (2 * radius) ** 2));
      return width * height / smallestArea;
    };
    let tripleStacks = 0;
    let fourStacks = 0;
    let maxSharedTripleFraction = 0;
    let maxSharedFourFraction = 0;
    const orderedIds = [...byReference.keys()].sort((left, right) => left - right);
    for (let aIndex = 0; aIndex < orderedIds.length; aIndex += 1) {
      const aId = orderedIds[aIndex];
      const laterB = [...boxNeighbors.get(aId)]
        .filter((referenceId) => referenceId > aId)
        .sort((left, right) => left - right);
      for (const bId of laterB) {
        const commonC = [...boxNeighbors.get(aId)]
          .filter((referenceId) => referenceId > bId
            && boxNeighbors.get(bId).has(referenceId))
          .sort((left, right) => left - right);
        for (const cId of commonC) {
          const tripleFraction = sharedBoxFraction([aId, bId, cId]);
          if (tripleFraction <= 1e-12) continue;
          tripleStacks += 1;
          maxSharedTripleFraction = Math.max(maxSharedTripleFraction, tripleFraction);
          const commonD = commonC.filter((referenceId) => referenceId > cId
            && boxNeighbors.get(cId).has(referenceId));
          for (const dId of commonD) {
            const fourFraction = sharedBoxFraction([aId, bId, cId, dId]);
            if (fourFraction <= 1e-12) continue;
            fourStacks += 1;
            maxSharedFourFraction = Math.max(maxSharedFourFraction, fourFraction);
          }
        }
      }
    }
    const nearestValues = [...nearest.values()].filter(Number.isFinite);
    return {
      alive: selected.length,
      hp: selected.reduce((total, raw) => total + raw[4], 0),
      meanX: selected.length === 0 ? null
        : selected.reduce((total, raw) => total + raw[1], 0) / selected.length,
      meanY: selected.length === 0 ? null
        : selected.reduce((total, raw) => total + raw[2], 0) / selected.length,
      minX: selected.length === 0 ? null : Math.min(...selected.map((raw) => raw[1])),
      maxX: selected.length === 0 ? null : Math.max(...selected.map((raw) => raw[1])),
      minY: selected.length === 0 ? null : Math.min(...selected.map((raw) => raw[2])),
      maxY: selected.length === 0 ? null : Math.max(...selected.map((raw) => raw[2])),
      xSpan: selected.length === 0 ? 0
        : Math.max(...selected.map((raw) => raw[1])) - Math.min(...selected.map((raw) => raw[1])),
      ySpan: selected.length === 0 ? 0
        : Math.max(...selected.map((raw) => raw[2])) - Math.min(...selected.map((raw) => raw[2])),
      possiblePairs: selected.length * (selected.length - 1) / 2,
      overlapPairs,
      overlapDepthSum,
      meanOverlapDepth: overlapDepthSum / Math.max(1, overlapPairs),
      maxOverlapDepth,
      overlappedUnits: overlapped.size,
      boxOverlapPairs,
      boxOverlapDepthSum,
      meanBoxOverlapDepth: boxOverlapDepthSum / Math.max(1, boxOverlapPairs),
      maxBoxOverlapDepth,
      boxOverlappedUnits: boxOverlapped.size,
      boxCommittedCommittedOverlapPairs: boxOverlapByCommitment.committedCommitted.pairs,
      meanBoxCommittedCommittedOverlapDepth:
        boxOverlapByCommitment.committedCommitted.depth
          / Math.max(1, boxOverlapByCommitment.committedCommitted.pairs),
      boxMixedOverlapPairs: boxOverlapByCommitment.mixed.pairs,
      meanBoxMixedOverlapDepth: boxOverlapByCommitment.mixed.depth
        / Math.max(1, boxOverlapByCommitment.mixed.pairs),
      boxUncommittedUncommittedOverlapPairs:
        boxOverlapByCommitment.uncommittedUncommitted.pairs,
      meanBoxUncommittedUncommittedOverlapDepth:
        boxOverlapByCommitment.uncommittedUncommitted.depth
          / Math.max(1, boxOverlapByCommitment.uncommittedUncommitted.pairs),
      tripleStacks,
      fourStacks,
      maxSharedTripleFraction,
      maxSharedFourFraction,
      meanNearestFriendlyDistance: nearestValues.length === 0 ? null
        : nearestValues.reduce((total, value) => total + value, 0) / nearestValues.length,
      assignedTargets: {
        actors: assignedTargetIds.length,
        uniqueTargets: Object.keys(assignedTargetCounts).length,
        maximumLoad: Math.max(0, ...Object.values(assignedTargetCounts)),
        targetCounts: assignedTargetCounts,
      },
      actionCounts: Object.fromEntries([...new Set(selected.map((raw) => raw[6]))]
        .sort().map((action) => [
          action,
          selected.filter((raw) => raw[6] === action).length,
        ])),
    };
  };
  const events = run.snapshots.flatMap(({ events: current }) => current);
  const damage = events.filter(({ type }) => type === "damage");
  const shellImpactGroups = new Map();
  for (const current of damage.filter(({ kind }) => (
    kind === "shell-projectile" || kind === "pebble-projectile"
  ))) {
    const key = `${current.tick}:${current.actorId}`;
    const group = shellImpactGroups.get(key) ?? {
      tick: current.tick,
      actorId: current.actorId,
      primaryHits: 0,
      debrisHits: 0,
      damage: 0,
      damageByTargetOwner: { 2: 0, 3: 0, 4: 0 },
      victims: [],
    };
    if (current.kind === "shell-projectile") group.primaryHits += 1;
    else group.debrisHits += 1;
    group.damage += current.amount;
    const targetOwner = ownerOf(current.targetId);
    group.damageByTargetOwner[targetOwner] = (
      group.damageByTargetOwner[targetOwner] ?? 0
    ) + current.amount;
    group.victims.push({
      targetId: current.targetId,
      targetOwner,
      amount: current.amount,
      kind: current.kind,
    });
    shellImpactGroups.set(key, group);
  }
  const snapshotByTick = new Map(run.snapshots.map((snapshot) => [snapshot.tick, snapshot]));
  for (const group of shellImpactGroups.values()) {
    const snapshot = snapshotByTick.get(group.tick);
    const primaryIds = [...new Set(group.victims
      .filter(({ kind }) => kind === "shell-projectile")
      .map(({ targetId }) => targetId))];
    const positions = primaryIds.map((targetId) => (
      snapshot?.units.find((raw) => raw[0] === targetId)
    )).filter(Boolean);
    group.primaryVictimGeometry = {
      uniqueVictims: positions.length,
      xSpan: positions.length === 0 ? 0
        : Math.max(...positions.map((raw) => raw[1]))
          - Math.min(...positions.map((raw) => raw[1])),
      ySpan: positions.length === 0 ? 0
        : Math.max(...positions.map((raw) => raw[2]))
          - Math.min(...positions.map((raw) => raw[2])),
    };
  }
  const player4DefeatTick = events.find(({ type, owner }) => (
    type === "owner-defeated" && owner === 4
  ))?.tick ?? 0;
  const firstAcquisitionByActor = new Map();
  for (const current of events) {
    if (current.type !== "pursuit-acquired"
        || firstAcquisitionByActor.has(current.actorId)) continue;
    firstAcquisitionByActor.set(current.actorId, current);
  }
  const byOwner = Object.fromEntries([2, 3, 4].map((owner) => {
    const attacks = events.filter(({ type, actorId }) => (
      type === "attack-start" && ownerOf(actorId) === owner
    ));
    const pursuits = events.filter(({ type, actorId }) => (
      type === "pursuit-acquired" && ownerOf(actorId) === owner
    ));
    const hits = damage.filter(({ actorId }) => ownerOf(actorId) === owner);
    const windupRetargets = events.filter(({ type, actorId }) => (
      type === "attack-retargeted" && ownerOf(actorId) === owner
    ));
    const attackCancellations = events.filter(({ type, actorId }) => (
      type === "attack-canceled" && ownerOf(actorId) === owner
    ));
    const hitsFirst20Seconds = hits.filter(({ tick }) => tick < 20 * 60);
    const ownerOpeningEvents = [...firstAcquisitionByActor.values()]
      .filter(({ actorId, targetId }) => (
        ownerOf(actorId) === owner && ownerOf(targetId) !== owner
      ))
      .sort((left, right) => left.tick - right.tick || left.actorId - right.actorId);
    const openingTargets = ownerOpeningEvents.map(({ targetId }) => targetId);
    const openingTargetCounts = Object.fromEntries([...new Set(openingTargets)]
      .sort((left, right) => left - right)
      .map((targetId) => [targetId, openingTargets.filter((id) => id === targetId).length]));
    const firstAttackByActor = new Map();
    for (const current of attacks) {
      if (!firstAttackByActor.has(current.actorId)) {
        firstAttackByActor.set(current.actorId, current);
      }
    }
    const openingShotEvents = [...firstAttackByActor.values()]
      .filter(({ targetId }) => ownerOf(targetId) !== owner)
      .sort((left, right) => left.tick - right.tick || left.actorId - right.actorId);
    const openingShotTargets = openingShotEvents.map(({ targetId }) => targetId);
    const openingShotTargetCounts = Object.fromEntries([...new Set(openingShotTargets)]
      .sort((left, right) => left - right)
      .map((targetId) => [
        targetId,
        openingShotTargets.filter((id) => id === targetId).length,
      ]));
    const minRange = {
      actorFrames: 0,
      pinnedActorFrames: 0,
      pinnedWithShootableAlternativeFrames: 0,
      attackingWhilePinnedFrames: 0,
    };
    for (const snapshot of run.snapshots) {
      if (snapshot.tick < player4DefeatTick || snapshot.tick >= 20 * 60) continue;
      const alive = snapshot.units.filter((raw) => raw[5] === 1);
      const hostiles = alive.filter((raw) => {
        const hostileOwner = ownerOf(raw[0]);
        return (owner === 2 && hostileOwner === 3)
          || (owner === 3 && hostileOwner === 2);
      });
      for (const actor of alive.filter((raw) => ownerOf(raw[0]) === owner)) {
        const actorMeta = run.unitIndex[actor[0]];
        if (!(actorMeta?.minRange > 0)) continue;
        minRange.actorFrames += 1;
        const distances = hostiles.map((target) => ({
          target,
          distance: Math.hypot(target[1] - actor[1], target[2] - actor[2]),
        }));
        if (!distances.some(({ distance }) => distance < actorMeta.minRange - 1e-12)) {
          continue;
        }
        minRange.pinnedActorFrames += 1;
        if (actor[6] === "attacking") minRange.attackingWhilePinnedFrames += 1;
        if (distances.some(({ target, distance }) => {
          if (distance < actorMeta.minRange - 1e-12) return false;
          const targetMeta = run.unitIndex[target[0]];
          const edgeDistance = distance
            - (actorMeta.outlineRadius ?? actorMeta.collisionRadius)
            - (targetMeta?.outlineRadius ?? targetMeta?.collisionRadius ?? 0);
          return edgeDistance <= actorMeta.attackRange + 0.1 + 1e-12;
        })) {
          minRange.pinnedWithShootableAlternativeFrames += 1;
        }
      }
    }
    return [owner, {
      attackStarts: attacks.length,
      windupRetargets: {
        count: windupRetargets.length,
        details: windupRetargets.map((current) => ({
          tick: current.tick,
          actorId: current.actorId,
          fromTargetId: current.fromTargetId,
          targetId: current.targetId,
          swingTick: current.swingTick ?? null,
          releaseTicks: current.releaseTicks ?? null,
          remainingWindupTicks: current.remainingWindupTicks ?? null,
        })),
      },
      attackCancellations: {
        count: attackCancellations.length,
        reasons: Object.fromEntries([...new Set(attackCancellations.map(({ reason }) => (
          reason ?? "unspecified"
        )))].sort().map((reason) => [
          reason,
          attackCancellations.filter((current) => (
            (current.reason ?? "unspecified") === reason
          )).length,
        ])),
      },
      pursuitAcquisitionsByTargetOwner: Object.fromEntries([2, 3, 4]
        .map((targetOwner) => {
          const selected = pursuits.filter(({ targetId }) => ownerOf(targetId) === targetOwner);
          return [targetOwner, {
            count: selected.length,
            beforePlayer4Defeat: selected.filter(({ tick }) => (
              player4DefeatTick > 0 && tick <= player4DefeatTick
            )).length,
            reasons: Object.fromEntries([...new Set(selected.map(({ reason }) => (
              reason ?? "unspecified"
            )))].sort().map((reason) => [
              reason,
              selected.filter((row) => (row.reason ?? "unspecified") === reason).length,
            ])),
          }];
        })),
      attackStartTicks: [...new Set(attacks.map(({ tick }) => tick))],
      attackStartsFirst20Seconds: attacks.filter(({ tick }) => tick < 20 * 60).length,
      attackTargetCounts: Object.fromEntries([...new Set(attacks
        .map(({ targetId }) => targetId)
        .filter(Number.isSafeInteger))]
        .sort((left, right) => left - right)
        .map((targetId) => [
          targetId,
          attacks.filter((event) => event.targetId === targetId).length,
        ])),
      attackStartsByTargetOwner: Object.fromEntries([2, 3, 4].map((targetOwner) => {
        const selected = attacks.filter(({ targetId }) => ownerOf(targetId) === targetOwner);
        return [targetOwner, {
          count: selected.length,
          firstTick: selected[0]?.tick ?? null,
          lastTick: selected.at(-1)?.tick ?? null,
          bySecond: Object.fromEntries([...new Set(selected.map(({ tick }) => (
            Math.floor(tick / 60)
          )))].sort((left, right) => left - right).map((second) => [
            second,
            selected.filter(({ tick }) => Math.floor(tick / 60) === second).length,
          ])),
        }];
      })),
      openingAcquisition: {
        actors: openingTargets.length,
        uniqueTargets: Object.keys(openingTargetCounts).length,
        maximumTargetLoad: Math.max(0, ...Object.values(openingTargetCounts)),
        targetCounts: openingTargetCounts,
        details: ownerOpeningEvents.map(({ tick, actorId, targetId }) => {
          const snapshot = snapshotByTick.get(tick);
          const actor = snapshot?.units.find((raw) => raw[0] === actorId);
          const target = snapshot?.units.find((raw) => raw[0] === targetId);
          return {
            tick,
            actorId,
            actorX: actor?.[1] ?? null,
            actorY: actor?.[2] ?? null,
            targetId,
            targetX: target?.[1] ?? null,
            targetY: target?.[2] ?? null,
          };
        }),
      },
      openingShot: {
        actors: openingShotTargets.length,
        uniqueTargets: Object.keys(openingShotTargetCounts).length,
        maximumTargetLoad: Math.max(0, ...Object.values(openingShotTargetCounts)),
        targetCounts: openingShotTargetCounts,
        details: openingShotEvents.map(({ tick, actorId, targetId }) => ({
          tick,
          actorId,
          targetId,
        })),
      },
      hits: hits.length,
      damage: hits.reduce((total, { amount }) => total + amount, 0),
      hitsFirst20Seconds: hitsFirst20Seconds.length,
      damageFirst20Seconds: hitsFirst20Seconds
        .reduce((total, { amount }) => total + amount, 0),
      uniqueAttackersFirst20Seconds: new Set(
        hitsFirst20Seconds.map(({ actorId }) => actorId),
      ).size,
      damageByKindFirst20Seconds: Object.fromEntries([...new Set(
        hitsFirst20Seconds.map(({ kind }) => kind ?? "direct"),
      )].sort().map((kind) => {
        const selected = hitsFirst20Seconds
          .filter((event) => (event.kind ?? "direct") === kind);
        return [kind, {
          hits: selected.length,
          damage: selected.reduce((total, { amount }) => total + amount, 0),
        }];
      })),
      damageByKind: Object.fromEntries([...new Set(hits.map(({ kind }) => kind ?? "direct"))]
        .sort().map((kind) => {
          const selected = hits.filter((event) => (event.kind ?? "direct") === kind);
          return [kind, {
            hits: selected.length,
            damage: selected.reduce((total, { amount }) => total + amount, 0),
          }];
        })),
      damageByTargetOwner: Object.fromEntries([2, 3, 4].map((targetOwner) => {
        const selected = hits.filter(({ targetId }) => ownerOf(targetId) === targetOwner);
        return [targetOwner, {
          hits: selected.length,
          damage: selected.reduce((total, { amount }) => total + amount, 0),
          firstTick: selected[0]?.tick ?? null,
          lastTick: selected.at(-1)?.tick ?? null,
          bySecond: Object.fromEntries([...new Set(selected.map(({ tick }) => (
            Math.floor(tick / 60)
          )))].sort((left, right) => left - right).map((second) => {
            const rows = selected.filter(({ tick }) => Math.floor(tick / 60) === second);
            return [second, {
              hits: rows.length,
              damage: rows.reduce((total, { amount }) => total + amount, 0),
            }];
          })),
        }];
      })),
      uniqueAttackers: new Set(hits.map(({ actorId }) => actorId)).size,
      uniqueVictims: new Set(hits.map(({ targetId }) => targetId)).size,
      minRangeWindowFirst20Seconds: {
        ...minRange,
        pinnedShare: minRange.pinnedActorFrames / Math.max(1, minRange.actorFrames),
        shootableAlternativeShareOfPinned: minRange.pinnedWithShootableAlternativeFrames
          / Math.max(1, minRange.pinnedActorFrames),
        attackingShareOfPinned: minRange.attackingWhilePinnedFrames
          / Math.max(1, minRange.pinnedActorFrames),
      },
    }];
  }));
  return {
    firstDamageTick: damage[0]?.tick ?? null,
    lastDamageTick: damage.at(-1)?.tick ?? null,
    player4DefeatTick: player4DefeatTick || null,
    shellImpacts: [...shellImpactGroups.values()].sort((left, right) => (
      left.tick - right.tick || left.actorId - right.actorId
    )),
    formationPerSecond: run.snapshots
      // Retain the first minute: the expanded melee fights can match during
      // initial contact yet diverge only as the exposed attack surface decays.
      // All current golden bouts finish inside this compact diagnostic window.
      .filter(({ tick }) => tick % 60 === 0 && tick <= 60 * 60)
      .map((snapshot) => ({
        second: snapshot.tick / 60,
        2: formationSummary(snapshot.units, 2),
        3: formationSummary(snapshot.units, 3),
        4: formationSummary(snapshot.units, 4),
      })),
    byOwner,
  };
}


export async function runExpandedComparison({
  captureDirectory = DEFAULT_CAPTURE,
  outputFile = DEFAULT_OUTPUT,
  openingSeeds = [0],
  matchupKeys = null,
  rangedWindupRetargetOwner = null,
  retainSimulationSnapshots = true,
} = {}) {
  const captureUrl = captureDirectory instanceof URL
    ? captureDirectory
    : pathToFileURL(`${resolve(captureDirectory)}\\`);
  const [capture, rangedFormations, meleeFormation, mapFixture] = await Promise.all([
    readFile(new URL("capture_manifest.json", captureUrl), "utf8").then(JSON.parse),
    readFile(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/golden_formation_27v27.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/golden_map.json", import.meta.url), "utf8")
      .then(JSON.parse),
  ]);
  const selectedKeys = matchupKeys ?? capture.matchup_keys;
  const map = buildArenaPhysicsMap(mapFixture);
  const rows = [];
  for (const key of selectedKeys) {
    const matchup = capture.matchups[key];
    if (!matchup) throw new RangeError(`capture manifest has no matchup ${key}`);
    const capturedRuns = (capture.runs?.[key] ?? [])
      .toSorted((left, right) => left.repeat - right.repeat);
    if (capturedRuns.length === 0) throw new Error(`${key} has no completed live captures`);
    const side2 = unitBySlug(matchup.side1.slug);
    const side3 = unitBySlug(matchup.side2.slug);
    if (!side2 || !side3) throw new RangeError(`${key} has an unregistered unit`);
    const [mechanics2, mechanics3] = await Promise.all([
      loadMechanics(side2), loadMechanics(side3),
    ]);
    const count2 = matchup.side1.count;
    const count3 = matchup.side2.count;
    const live = capturedRuns.map(({ repeat, capture: observed }) => ({
      repeat,
      winnerOwner: observedOwner(observed, side2, side3),
      winnerHp: observed.winner_hp,
      survivorCount: observed.survivors,
      eliminationSeconds: observed.elimination_time_s,
      framesBin: `${fileURLToPath(captureUrl)}${key}\\run_${String(repeat).padStart(3, "0")}`
        + `\\raw recordings\\${key}.frames.bin`,
      framesSha256: observed.frames_sha256,
    }));
    const simulation = [];
    for (const openingSeed of openingSeeds) {
      try {
        let run = await runFight(pathToFileURL(fileURLToPath(ROOT)), {
          side2Slug: side2.slug,
          n2: count2,
          side3Slug: side3.slug,
          n3: count3,
          map,
          ...scenarioInputs(matchup, rangedFormations, meleeFormation),
          preserveOwnerOrientation: true,
          disableAiOrders: true,
          disableKiting: true,
          openingSeed,
          retainSnapshots: retainSimulationSnapshots,
          ...(Number.isSafeInteger(rangedWindupRetargetOwner)
            ? { rangedWindupRetargetOwner }
            : {}),
        });
        const result = {
          openingSeed,
          winnerOwner: run.winnerOwner,
          winnerHp: run.winnerHp,
          ticks: run.ticks,
          eliminationSeconds: run.ticks / 60,
          finalStateHash: run.finalStateHash,
          eventLogHash: run.eventLogHash,
          metrics: retainSimulationSnapshots ? simulationMetrics(run) : null,
        };
        simulation.push(result);
        // Detailed snapshots are only needed to derive the compact metrics above.
        // Drop their references before the next seed so long fights do not make a
        // serial comparison progressively slower through garbage-collection pressure.
        run = null;
        globalThis.gc?.();
        process.stderr.write(
          `  ${key} seed ${openingSeed}: P${result.winnerOwner} `
          + `${result.winnerHp.toFixed(1)} HP at ${result.eliminationSeconds.toFixed(2)}s\n`,
        );
      } catch (error) {
        simulation.push({ openingSeed, error: String(error?.message ?? error) });
        process.stderr.write(`  ${key} seed ${openingSeed}: ERROR ${error?.message ?? error}\n`);
      }
    }
    const resolved = simulation.filter(({ winnerOwner }) => Number.isSafeInteger(winnerOwner));
    const liveHp = summary(live.map(({ winnerHp }) => winnerHp));
    const simHp = resolved.length ? summary(resolved.map(({ winnerHp }) => winnerHp)) : null;
    const liveWinnerOwners = live.map(({ winnerOwner }) => winnerOwner);
    const simulationWinnerOwners = resolved.map(({ winnerOwner }) => winnerOwner);
    const stableLiveWinner = liveWinnerOwners.every((owner) => owner === liveWinnerOwners[0])
      ? liveWinnerOwners[0] : null;
    const correctWinnerRuns = stableLiveWinner === null
      ? null
      : simulationWinnerOwners.filter((owner) => owner === stableLiveWinner).length;
    const relativeWinnerHpDelta = simHp === null
      ? null : Math.abs(simHp.mean - liveHp.mean) / liveHp.mean;
    const row = {
      key,
      family: matchup.family,
      side2: { slug: side2.slug, civ: matchup.side1.civ, count: count2, hp: mechanics2.hp },
      side3: { slug: side3.slug, civ: matchup.side2.civ, count: count3, hp: mechanics3.hp },
      live,
      liveSummary: { winnerOwners: liveWinnerOwners, winnerHp: liveHp },
      simulation,
      simulationSummary: {
        resolved: resolved.length,
        winnerOwners: simulationWinnerOwners,
        winnerHp: simHp,
        correctWinnerRuns,
        relativeWinnerHpDelta,
        success: stableLiveWinner !== null
          && correctWinnerRuns === resolved.length
          && resolved.length === openingSeeds.length
          && relativeWinnerHpDelta < 0.10,
      },
    };
    rows.push(row);
    const liveWinner = stableLiveWinner === null ? "mixed" : `P${stableLiveWinner}`;
    const simWinner = simulationWinnerOwners.length === 0
      ? "unresolved" : simulationWinnerOwners.map((owner) => `P${owner}`).join(",");
    const hpText = relativeWinnerHpDelta === null
      ? "n/a" : `${(relativeWinnerHpDelta * 100).toFixed(1)}%`;
    process.stderr.write(
      `${key}: live ${liveWinner} ${liveHp.mean.toFixed(1)} HP; `
      + `sim ${simWinner} ${simHp?.mean.toFixed(1) ?? "n/a"} HP; delta ${hpText}\n`,
    );
  }
  const failures = rows.filter(({ simulationSummary }) => simulationSummary.success !== true);
  const report = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    source: {
      captureManifest: fileURLToPath(new URL("capture_manifest.json", captureUrl)),
      captureRoot: fileURLToPath(captureUrl),
      rangedFormationFixture: "fixtures/current_ranged_golden_formations.json",
      meleeFormationFixture: "fixtures/golden_formation_27v27.json",
      mapFixture: "fixtures/golden_map.json",
    },
    config: {
      openingSeeds,
      rangedOpportunityRetargeting: "generic-in-range-opportunity",
      rangedWindupRetargetOwner,
      retainSimulationSnapshots,
      purchaseRule: "exact unweighted counts from live capture manifest",
      placementRule: "literal first-N current golden scenario order",
      acceptance: "stable correct winner and <10% mean survivor-HP delta",
    },
    summary: {
      matchups: rows.length,
      successes: rows.length - failures.length,
      failures: failures.length,
      wrongWinnerMatchups: failures.filter(({ liveSummary, simulationSummary }) => (
        liveSummary.winnerOwners.every((owner) => owner === liveSummary.winnerOwners[0])
          && simulationSummary.winnerOwners.some((owner) => owner !== liveSummary.winnerOwners[0])
      )).length,
      aboveTenPercentHp: failures.filter(({ simulationSummary }) => (
        simulationSummary.relativeWinnerHpDelta >= 0.10
      )).length,
    },
    failureKeys: failures.map(({ key }) => key),
    rows,
  };
  const outputPath = outputFile instanceof URL ? fileURLToPath(outputFile) : resolve(outputFile);
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`);
  return report;
}


function argument(prefix) {
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length);
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const seedCount = Number.parseInt(argument("--seed-count=") ?? "1", 10);
  if (!Number.isSafeInteger(seedCount) || seedCount < 1) {
    throw new RangeError("--seed-count must be a positive integer");
  }
  const rangedWindupOwnerArgument = argument("--ranged-windup-retarget-owner=");
  const rangedWindupRetargetOwner = rangedWindupOwnerArgument === undefined
    ? null
    : Number.parseInt(rangedWindupOwnerArgument, 10);
  if (rangedWindupRetargetOwner !== null
      && (!Number.isSafeInteger(rangedWindupRetargetOwner)
        || rangedWindupRetargetOwner < 1)) {
    throw new RangeError("--ranged-windup-retarget-owner must be a positive integer");
  }
  const report = await runExpandedComparison({
    captureDirectory: argument("--capture=") ?? DEFAULT_CAPTURE,
    outputFile: argument("--output=") ?? DEFAULT_OUTPUT,
    openingSeeds: Array.from({ length: seedCount }, (_, seed) => seed),
    matchupKeys: argument("--matchup=") ? [argument("--matchup=")] : null,
    rangedWindupRetargetOwner,
    retainSimulationSnapshots: !process.argv.includes("--summary-only"),
  });
  process.stdout.write(`${JSON.stringify(report.summary)}\n`);
}
