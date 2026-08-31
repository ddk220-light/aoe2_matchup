// Export first-20-second engagement participation from the current simulation
// for the exact 27 Chinese Arbalester vs 18 Saracen Heavy Cavalry Archer
// ranged-vs-ranged golden scenario. The output is diagnostic evidence only;
// it does not feed runtime matchup parameters back into the engine.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";
import { unitBySlug } from "../src/unit-registry.js";


const ROOT = new URL("../", import.meta.url);
const MATCHUP_KEY = "arbalester_vs_heavy_cav_archer";
const WINDOW_SECONDS = 20;
const OUTPUT = new URL(
  "../calibration/reports/arbalester_hca_participation_2026-08-30/"
    + "simulation_participation.json",
  import.meta.url,
);
const CAPTURE_ROOT = new URL(
  "../calibration/live_observations/ranged_matrix_5x_2026-08-29/",
  import.meta.url,
);


function round(value, digits = 4) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


function slugMechanics(unit, mechanics) {
  return Object.freeze({
    slug: unit.slug,
    attackRange: mechanics.attack_range_tiles,
    minRange: mechanics.ranged?.min_range_tiles ?? 0,
    outlineRadius: mechanics.outline_size_tiles.x,
    collisionRadius: mechanics.collision_size_tiles.x,
  });
}


function withinReach(actor, target, mechanicsBySlug) {
  const actorMechanics = mechanicsBySlug.get(actor.slug);
  const targetMechanics = mechanicsBySlug.get(target.slug);
  const distance = Math.hypot(target.x - actor.x, target.y - actor.y);
  if (actorMechanics.minRange > 0 && distance < actorMechanics.minRange - 1e-12) {
    return false;
  }
  return distance - actorMechanics.outlineRadius - targetMechanics.outlineRadius
    <= actorMechanics.attackRange + 0.1 + 1e-12;
}


function stateRows(run, mechanicsBySlug) {
  const snapshots = run.snapshots;
  const index = run.unitIndex;
  const rows = [];
  for (let snapshotIndex = 0; snapshotIndex < snapshots.length; snapshotIndex += 1) {
    const snapshot = snapshots[snapshotIndex];
    if (snapshot.tick >= WINDOW_SECONDS * 60) break;
    const prior = snapshots[Math.max(0, snapshotIndex - 1)];
    const priorById = new Map(prior.units.map((unit) => [unit[0], unit]));
    const byId = new Map(snapshot.units.map((unit) => [unit[0], unit]));
    const countsByOwner = {};
    for (const owner of [2, 3]) {
      countsByOwner[owner] = {
        alive: 0,
        active: 0,
        firing: 0,
        notFiring: 0,
        windup: 0,
        reload: 0,
        inRangeNotFiring: 0,
        seekingMoving: 0,
        seekingStationary: 0,
        untargetedMoving: 0,
        untargetedStationary: 0,
        staleTarget: 0,
      };
    }
    for (const raw of snapshot.units) {
      const [referenceId, x, y, , , alive, action, pursuitTargetId,
        engagedTargetId, attackTargetId] = raw;
      if (alive !== 1) continue;
      const meta = index[referenceId];
      if (!meta || !countsByOwner[meta.owner]) continue;
      const counts = countsByOwner[meta.owner];
      counts.alive += 1;
      const actor = { referenceId, owner: meta.owner, slug: meta.slug, x, y };
      const rawTargetId = attackTargetId ?? engagedTargetId ?? pursuitTargetId;
      const targetRaw = rawTargetId === null || rawTargetId === undefined
        ? null
        : byId.get(rawTargetId);
      const targetMeta = targetRaw ? index[targetRaw[0]] : null;
      const target = targetRaw && targetRaw[5] === 1 && targetMeta
        && targetMeta.owner !== meta.owner
        ? {
          referenceId: targetRaw[0], owner: targetMeta.owner, slug: targetMeta.slug,
          x: targetRaw[1], y: targetRaw[2],
        }
        : null;
      const inReach = target ? withinReach(actor, target, mechanicsBySlug) : false;
      const firing = target && inReach && action === "attacking";
      if (firing) {
        counts.active += 1;
        counts.firing += 1;
        counts.windup += 1;
        continue;
      }
      counts.notFiring += 1;
      if (action === "reload") {
        counts.reload += 1;
        if (target && inReach) counts.active += 1;
        continue;
      }
      const previous = priorById.get(referenceId);
      const dt = Math.max(1, snapshot.tick - prior.tick) / 60;
      const speed = previous
        ? Math.hypot(x - previous[1], y - previous[2]) / dt
        : 0;
      const moving = speed > 0.05;
      if (rawTargetId !== null && rawTargetId !== undefined && target === null) {
        counts.staleTarget += 1;
      }
      if (target && inReach) {
        counts.inRangeNotFiring += 1;
      } else if (target) {
        counts[moving ? "seekingMoving" : "seekingStationary"] += 1;
      } else {
        counts[moving ? "untargetedMoving" : "untargetedStationary"] += 1;
      }
    }
    rows.push({
      tick: snapshot.tick,
      countsByOwner,
      pairsByOwner: pairMetrics(snapshot, index, mechanicsBySlug),
    });
  }
  return rows;
}


function pairMetrics(snapshot, index, mechanicsBySlug) {
  const output = {};
  for (const owner of [2, 3]) {
    const units = snapshot.units.filter((raw) => (
      raw[5] === 1 && index[raw[0]]?.owner === owner
    ));
    let overlapPairs = 0;
    let overlapDepthSum = 0;
    let maxOverlapDepth = 0;
    let tripleStacks = 0;
    let fourStacks = 0;
    let maxSharedTripleFraction = 0;
    let maxSharedFourFraction = 0;
    const overlapped = new Set();
    const nearest = new Map(units.map((raw) => [raw[0], Number.POSITIVE_INFINITY]));
    for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
      const left = units[leftIndex];
      const leftMechanics = mechanicsBySlug.get(index[left[0]].slug);
      for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
        const right = units[rightIndex];
        const rightMechanics = mechanicsBySlug.get(index[right[0]].slug);
        const distance = Math.max(
          Math.abs(right[1] - left[1]),
          Math.abs(right[2] - left[2]),
        );
        nearest.set(left[0], Math.min(nearest.get(left[0]), distance));
        nearest.set(right[0], Math.min(nearest.get(right[0]), distance));
        const overlapDepth = leftMechanics.collisionRadius
          + rightMechanics.collisionRadius - distance;
        if (overlapDepth > 1e-12) {
          overlapPairs += 1;
          overlapDepthSum += overlapDepth;
          maxOverlapDepth = Math.max(maxOverlapDepth, overlapDepth);
          overlapped.add(left[0]);
          overlapped.add(right[0]);
        }
      }
    }
    const sharedFraction = (members) => {
      const entries = members.map((raw) => ({
        raw,
        radius: mechanicsBySlug.get(index[raw[0]].slug).collisionRadius,
      }));
      const width = Math.max(0,
        Math.min(...entries.map(({ raw, radius }) => raw[1] + radius))
          - Math.max(...entries.map(({ raw, radius }) => raw[1] - radius)));
      const height = Math.max(0,
        Math.min(...entries.map(({ raw, radius }) => raw[2] + radius))
          - Math.max(...entries.map(({ raw, radius }) => raw[2] - radius)));
      const smallestArea = Math.min(...entries.map(({ radius }) => (2 * radius) ** 2));
      return width * height / smallestArea;
    };
    for (let a = 0; a < units.length; a += 1) {
      for (let b = a + 1; b < units.length; b += 1) {
        for (let c = b + 1; c < units.length; c += 1) {
          const tripleFraction = sharedFraction([units[a], units[b], units[c]]);
          if (tripleFraction <= 1e-12) continue;
          tripleStacks += 1;
          maxSharedTripleFraction = Math.max(maxSharedTripleFraction, tripleFraction);
          for (let d = c + 1; d < units.length; d += 1) {
            const fourFraction = sharedFraction([units[a], units[b], units[c], units[d]]);
            if (fourFraction <= 1e-12) continue;
            fourStacks += 1;
            maxSharedFourFraction = Math.max(maxSharedFourFraction, fourFraction);
          }
        }
      }
    }
    const nearestValues = [...nearest.values()].filter(Number.isFinite);
    output[owner] = {
      alive: units.length,
      possiblePairs: units.length * (units.length - 1) / 2,
      overlapPairs,
      overlapDepthSum,
      maxOverlapDepth,
      tripleStacks,
      fourStacks,
      maxSharedTripleFraction,
      maxSharedFourFraction,
      overlappedUnits: overlapped.size,
      nearestDistanceSum: nearestValues.reduce((total, value) => total + value, 0),
      nearestDistanceCount: nearestValues.length,
    };
  }
  return output;
}


function summarizePairRows(rows, owner) {
  const source = rows.map(({ pairsByOwner }) => pairsByOwner[owner]);
  const sum = (field) => source.reduce((total, row) => total + row[field], 0);
  return {
    meanOverlapPairs: round(sum("overlapPairs") / Math.max(source.length, 1)),
    meanPossiblePairs: round(sum("possiblePairs") / Math.max(source.length, 1)),
    overlapPairShare: round(sum("overlapPairs") / Math.max(sum("possiblePairs"), 1), 6),
    meanOverlappedUnits: round(sum("overlappedUnits") / Math.max(source.length, 1)),
    overlappedUnitShare: round(sum("overlappedUnits") / Math.max(sum("alive"), 1), 6),
    meanOverlapDepth: round(sum("overlapDepthSum") / Math.max(sum("overlapPairs"), 1), 6),
    maxOverlapDepth: round(Math.max(0, ...source.map(({ maxOverlapDepth }) => maxOverlapDepth)), 6),
    meanTripleStacks: round(sum("tripleStacks") / Math.max(source.length, 1)),
    meanFourStacks: round(sum("fourStacks") / Math.max(source.length, 1)),
    maxSharedTripleFraction: round(Math.max(
      0,
      ...source.map(({ maxSharedTripleFraction }) => maxSharedTripleFraction),
    ), 6),
    maxSharedFourFraction: round(Math.max(
      0,
      ...source.map(({ maxSharedFourFraction }) => maxSharedFourFraction),
    ), 6),
    meanNearestFriendlyDistance: round(
      sum("nearestDistanceSum") / Math.max(sum("nearestDistanceCount"), 1), 6,
    ),
  };
}


function attackStartRanges(run, mechanicsBySlug) {
  const rows = [];
  for (const snapshot of run.snapshots) {
    if (snapshot.tick >= WINDOW_SECONDS * 60) break;
    const byId = new Map(snapshot.units.map((unit) => [unit[0], unit]));
    for (const event of snapshot.events) {
      if (event.type !== "attack-start") continue;
      const actorRaw = byId.get(event.actorId);
      const targetRaw = byId.get(event.targetId);
      const actorMeta = run.unitIndex[event.actorId];
      const targetMeta = run.unitIndex[event.targetId];
      if (!actorRaw || !targetRaw || !actorMeta || !targetMeta) continue;
      if (actorMeta.owner === targetMeta.owner) continue;
      const actorMechanics = mechanicsBySlug.get(actorMeta.slug);
      const targetMechanics = mechanicsBySlug.get(targetMeta.slug);
      if (!actorMechanics || !targetMechanics) continue;
      const centerDistance = Math.hypot(targetRaw[1] - actorRaw[1], targetRaw[2] - actorRaw[2]);
      const edgeDistance = centerDistance
        - actorMechanics.outlineRadius - targetMechanics.outlineRadius;
      rows.push({
        tick: snapshot.tick,
        second: snapshot.tick / 60,
        owner: actorMeta.owner,
        actorId: event.actorId,
        targetId: event.targetId,
        centerDistance: round(centerDistance, 6),
        edgeDistance: round(edgeDistance, 6),
        nominalRange: actorMechanics.attackRange,
        rangeUtilization: round(edgeDistance / actorMechanics.attackRange, 6),
        nominalHeadroom: round(actorMechanics.attackRange - edgeDistance, 6),
      });
    }
  }
  return rows;
}


function perSecond(run, mechanicsBySlug) {
  const rows = stateRows(run, mechanicsBySlug);
  const events = run.snapshots.flatMap(({ events }) => events);
  return Array.from({ length: WINDOW_SECONDS }, (_, second) => {
    const samples = rows.filter(({ tick }) => tick >= second * 60 && tick < (second + 1) * 60);
    const result = { second };
    for (const owner of [2, 3]) {
      const ownerRows = samples.map(({ countsByOwner }) => countsByOwner[owner]);
      const fields = Object.keys(ownerRows[0] ?? {});
      const metrics = Object.fromEntries(fields.map((field) => [
        field,
        round(ownerRows.reduce((total, row) => total + row[field], 0)
          / Math.max(1, ownerRows.length)),
      ]));
      const attackStarts = events.filter(({ type, tick, actorId }) => (
        type === "attack-start"
        && tick >= second * 60 && tick < (second + 1) * 60
        && indexOwner(run, actorId) === owner
      ));
      const damage = events.filter(({ type, tick, actorId }) => (
        type === "damage"
        && tick >= second * 60 && tick < (second + 1) * 60
        && indexOwner(run, actorId) === owner
      ));
      result[owner] = {
        ...metrics,
        ...summarizePairRows(samples, owner),
        shotStarts: attackStarts.length,
        uniqueShotStarters: new Set(attackStarts.map(({ actorId }) => actorId)).size,
        damageHits: damage.length,
        uniqueDamageDealers: new Set(damage.map(({ actorId }) => actorId)).size,
      };
    }
    return result;
  });
}


function indexOwner(run, referenceId) {
  return run.unitIndex[referenceId]?.owner ?? null;
}


function meanRows(runs) {
  return Array.from({ length: WINDOW_SECONDS }, (_, second) => {
    const output = { second };
    for (const owner of [2, 3]) {
      const rows = runs.map((run) => run.perSecond[second][owner]);
      output[owner] = Object.fromEntries(Object.keys(rows[0]).map((field) => [
        field,
        round(rows.reduce((total, row) => total + row[field], 0) / rows.length),
      ]));
    }
    return output;
  });
}


async function main() {
  const singleRun = process.argv.includes("--single-run");
  const [capture, formations, mapFixture] = await Promise.all([
    readFile(new URL("capture_manifest.json", CAPTURE_ROOT), "utf8").then(JSON.parse),
    readFile(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/golden_map.json", import.meta.url), "utf8").then(JSON.parse),
  ]);
  const matchup = capture.matchups[MATCHUP_KEY];
  if (!matchup) throw new Error(`missing ${MATCHUP_KEY} in capture manifest`);
  const side2 = unitBySlug(matchup.side1.slug);
  const side3 = unitBySlug(matchup.side2.slug);
  const [mechanics2, mechanics3] = await Promise.all([
    readFile(new URL(`../fixtures/unit_stats/${side2.fixture}`, import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL(`../fixtures/unit_stats/${side3.fixture}`, import.meta.url), "utf8")
      .then(JSON.parse),
  ]);
  const mechanicsBySlug = new Map([
    [side2.slug, slugMechanics(side2, mechanics2)],
    [side3.slug, slugMechanics(side3, mechanics3)],
  ]);
  const formation = formations.families[matchup.family];
  const placementByOwner = {
    2: formation.sides["2"].map(({ position }) => ({ x: position.x, y: position.y })),
    3: formation.sides["3"].map(({ position }) => ({ x: position.x, y: position.y })),
  };
  const map = buildArenaPhysicsMap(mapFixture);
  const runs = [];
  for (const openingSeed of (singleRun ? [0] : [0, 1, 2, 3, 4])) {
    const run = await runFight(pathToFileURL(fileURLToPath(ROOT)), {
      side2Slug: side2.slug,
      n2: matchup.side1.count,
      side3Slug: side3.slug,
      n3: matchup.side2.count,
      map,
      placementByOwner,
      diplomacyByOwner: formation.initial_diplomacy,
      triggers: formation.triggers,
      preserveOwnerOrientation: true,
      disableAiOrders: true,
      disableKiting: true,
      openingSeed,
    });
    runs.push({
      openingSeed,
      winnerOwner: run.winnerOwner,
      winnerHp: run.winnerHp,
      ticks: run.ticks,
      attackStartRanges: attackStartRanges(run, mechanicsBySlug),
      perSecond: perSecond(run, mechanicsBySlug),
    });
  }
  const output = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    matchup: {
      key: MATCHUP_KEY,
      side2: { slug: side2.slug, civilization: matchup.side1.civ, count: matchup.side1.count },
      side3: { slug: side3.slug, civilization: matchup.side2.civ, count: matchup.side2.count },
    },
    metricDefinition: {
      windowSeconds: WINDOW_SECONDS,
      active: "alive, hostile target resolves, target is in the DAT attack envelope, and action is attacking or reload",
      firing: "alive, hostile target resolves inside the DAT attack envelope, and action is attacking/windup",
      notFiring: "alive minus firing; reload and every movement/targeting state remain included",
      seekingStationary: "alive with a valid hostile target outside attack range and speed <= 0.05 tiles/s",
      seekingMoving: "alive with a valid hostile target outside attack range and speed > 0.05 tiles/s",
      inRangeNotFiring: "alive with a valid hostile target inside attack range but not attacking/reloading",
      shotStarts: "attack-start engine events in the one-second bucket",
      engagementRange: "center and outline-edge distance at each attack-start event; nominalHeadroom is DAT range minus edge distance",
    },
    sources: {
      captureManifest: fileURLToPath(new URL("capture_manifest.json", CAPTURE_ROOT)),
      formationFixture: fileURLToPath(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url)),
      mapFixture: fileURLToPath(new URL("../fixtures/golden_map.json", import.meta.url)),
      engine: fileURLToPath(new URL("../src/fight.js", import.meta.url)),
    },
    runs,
    meanPerSecond: meanRows(runs),
  };
  await mkdir(dirname(fileURLToPath(OUTPUT)), { recursive: true });
  await writeFile(OUTPUT, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${fileURLToPath(OUTPUT)}\n`);
}


await main();
