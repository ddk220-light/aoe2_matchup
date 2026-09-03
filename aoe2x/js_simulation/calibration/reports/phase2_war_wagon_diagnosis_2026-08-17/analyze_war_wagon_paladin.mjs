import { createReadStream } from "node:fs";
import { writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";

import {
  PHASE2_MAX_TICKS,
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  scenarioFromPhase2Batch1Row,
} from "../../../src/phase2-batch1-comparison.js";
import { createWorld, runWorld } from "../../../src/combat/world.js";


const ROOT = new URL("../../../", import.meta.url);
const TAPE_ROOT = new URL("./tape/", import.meta.url);
const TAGS = Object.freeze([
  "elite_war_wagon_koreans__vs__paladin",
  "elite_war_wagon_koreans__vs__paladin_r2",
  "elite_war_wagon_koreans__vs__paladin_r3",
  "elite_war_wagon_koreans__vs__paladin_r4",
]);
const OWNER_WAGON = 2;
const OWNER_PALADIN = 3;
const STARTING_COUNTS = Object.freeze({ 2: 15, 3: 17 });
const COLLISION_RADIUS = Object.freeze({ 2: 0.45, 3: 0.25 });
const TAPE_MOVE_STATE = 4;
const TAPE_ATTACK_STATE = 7;
const DIAGNOSTIC_VARIANT = process.env.AOE2X_WW_DIAGNOSTIC ?? "baseline";
const SPACING_MATCH = /^sticky-pressure-spacing-(0_[0-9]+)(?:-contact-(0_[0-9]+)(-always)?)?(?:-wide-pressure)?$/.exec(
  DIAGNOSTIC_VARIANT,
);
if (!["baseline", "sticky-pressure"].includes(DIAGNOSTIC_VARIANT) && !SPACING_MATCH) {
  throw new RangeError(`unknown War Wagon diagnostic variant ${DIAGNOSTIC_VARIANT}`);
}


const truth = await loadPhase2Batch1Truth(ROOT);
const row = truth.rows.find(({ id }) => id === "elite_war_wagon_vs_paladin");
if (!row) throw new Error("missing Elite War Wagon versus Paladin truth row");

const tapeRuns = [];
for (const tag of TAGS) {
  tapeRuns.push(await analyzeTapeTrace(new URL(`${tag}.tape_trace.jsonl`, TAPE_ROOT), tag));
}

const context = await loadPhase2Batch1Context(ROOT, truth);
const baseScenario = scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: 0,
  seed: 20260817,
  context,
});
const chaserMechanics = context.mechanicsByMaster.get(row.side3.master);
const kiterMechanics = context.mechanicsByMaster.get(row.side2.master);
const stickyPressure = DIAGNOSTIC_VARIANT !== "baseline";
const formationSpacingTiles = SPACING_MATCH
  ? Number(SPACING_MATCH[1].replace("_", "."))
  : null;
const contactDepthTiles = SPACING_MATCH?.[2]
  ? Number(SPACING_MATCH[2].replace("_", "."))
  : null;
const scenario = stickyPressure
  ? Object.freeze({
    ...baseScenario,
    ...(formationSpacingTiles === null
      ? {}
      : {
        kiteProfile: Object.freeze({
          ...baseScenario.kiteProfile,
          formationSpacingTiles,
        }),
      }),
    attackMoveTargetPressureTiles: DIAGNOSTIC_VARIANT.endsWith("-wide-pressure")
      ? 2 * kiterMechanics.collision_size_tiles.x
      : 2 * chaserMechanics.collision_size_tiles.x,
    attackMoveStickyPursuit: true,
    ...(contactDepthTiles === null
      ? {}
      : {
        warWagonEnemyOverlapDepthTiles: contactDepthTiles,
        warWagonEnemyOverlapMode: SPACING_MATCH?.[3] ? "always" : "attacking-target",
      }),
  })
  : baseScenario;
let simResult;
try {
  simResult = runWorld(createWorld(scenario), {
    maxTicks: PHASE2_MAX_TICKS,
    retainSnapshots: true,
  });
} catch (error) {
  if (!String(error?.message ?? error).includes("world exceeded")) throw error;
  simResult = Object.freeze({
    winner: null,
    ticks: PHASE2_MAX_TICKS,
    world: error.world,
    snapshots: error.world.snapshots,
    events: error.world.eventLog,
  });
}
const simulation = analyzeSimulation(simResult);

const output = Object.freeze({
  generatedAt: new Date().toISOString(),
  matchup: row.matchup,
  ratio: `${row.side2.count}v${row.side3.count}`,
  tapeRuns,
  tapeBand: summarizeTapeRuns(tapeRuns),
  simulation,
  eventTypes: countBy(simResult.events, ({ type }) => type),
  source: Object.freeze({
    archive: truth.archive,
    archiveSha256: truth.zip_sha256,
    tapeMembers: row.runs.map(({ source_members }) => source_members.frames),
    startingUnitsHash: row.runs[0].starting_units_hash,
    simulationSample: Object.freeze({
      sampleIndex: 0,
      seed: 20260817,
      variant: DIAGNOSTIC_VARIANT,
    }),
  }),
});

const outputStem = DIAGNOSTIC_VARIANT === "baseline"
  ? "war_wagon_paladin"
  : `war_wagon_paladin_${DIAGNOSTIC_VARIANT.replaceAll("-", "_")}`;
await Promise.all([
  writeFile(new URL(`${outputStem}_analysis.json`, import.meta.url), `${JSON.stringify(output, null, 2)}\n`, "utf8"),
  writeFile(new URL(`${outputStem}_sim_events.json`, import.meta.url), `${JSON.stringify(simResult.events, null, 2)}\n`, "utf8"),
]);
process.stdout.write(`${JSON.stringify({
  tapeBand: output.tapeBand,
  simulation: output.simulation,
  eventTypes: output.eventTypes,
}, null, 2)}\n`);


async function analyzeTapeTrace(url, tag) {
  const state = createAnalysisState("tape", tag);
  const lines = createInterface({ input: createReadStream(url), crlfDelay: Number.POSITIVE_INFINITY });
  let frameTime = null;
  let frameRows = [];
  for await (const line of lines) {
    if (!line) continue;
    const raw = JSON.parse(line);
    const time = raw.t_ms / 1000;
    if (frameTime !== null && time !== frameTime) {
      finishFrame(state, frameTime, frameRows);
      frameRows = [];
    }
    frameTime = time;
    frameRows.push(observeUnit(state, {
      time,
      id: raw.id,
      owner: raw.owner,
      x: raw.x,
      y: raw.y,
      hp: raw.hp ?? 0,
      alive: (raw.hp ?? 0) > 0,
      attacking: raw.action_state === TAPE_ATTACK_STATE,
      chasing: raw.action_state === TAPE_MOVE_STATE,
      targetId: raw.target_id ?? null,
    }));
  }
  if (frameTime !== null) finishFrame(state, frameTime, frameRows);
  return finalizeAnalysis(state);
}


function analyzeSimulation(result) {
  const state = createAnalysisState("simulation", "sample_0");
  for (const snapshot of result.snapshots) {
    const time = snapshot.tick / 60;
    const rows = snapshot.units.map((unit) => observeUnit(state, {
      time,
      id: unit.referenceId,
      owner: unit.owner,
      x: unit.x,
      y: unit.y,
      hp: unit.hp,
      alive: unit.alive,
      attacking: unit.action === "attacking",
      chasing: unit.action !== "attacking" && unit.pursuitTargetId !== null,
      targetId: unit.attackTargetId ?? unit.engagedTargetId ?? unit.pursuitTargetId,
    }));
    finishFrame(state, time, rows);
  }
  const summary = finalizeAnalysis(state);
  return Object.freeze({
    ...summary,
    winnerOwner: result.winner,
    ticks: result.ticks,
    score: -100 * summary.finalHpByOwner[OWNER_WAGON] / 3000,
  });
}


function createAnalysisState(source, tag) {
  return {
    source,
    tag,
    previousById: new Map(),
    firstActiveTime: null,
    frames: [],
    attackStarts: { 2: 0, 3: 0 },
    attackStartRecords: { 2: [], 3: [] },
    attackers: { 2: new Set(), 3: new Set() },
    damageEvents: { 2: 0, 3: 0 },
    damageDealt: { 2: 0, 3: 0 },
    firstDamageTime: { 2: null, 3: null },
    deaths: { 2: [], 3: [] },
    pathById: new Map(),
    targetChanges: { 2: 0, 3: 0 },
    finalHpByOwner: { 2: 0, 3: 0 },
    finalAliveByOwner: { 2: 0, 3: 0 },
  };
}


function observeUnit(state, current) {
  const previous = state.previousById.get(current.id);
  const step = previous
    ? Math.hypot(current.x - previous.x, current.y - previous.y)
    : 0;
  const moved = step > 1e-7;
  if (moved) {
    state.pathById.set(current.id, (state.pathById.get(current.id) ?? 0) + step);
  }
  if (
    state.firstActiveTime === null
    && (moved || current.attacking || current.chasing || current.targetId !== null)
  ) {
    state.firstActiveTime = current.time;
  }
  if (current.attacking && !previous?.attacking) {
    state.attackStarts[current.owner] += 1;
    state.attackers[current.owner].add(current.id);
    state.attackStartRecords[current.owner].push(Object.freeze({
      time: current.time,
      actorId: current.id,
      targetId: current.targetId,
    }));
  }
  if (
    previous
    && current.targetId !== previous.targetId
    && current.targetId !== null
  ) {
    state.targetChanges[current.owner] += 1;
  }
  if (previous?.alive && current.hp < previous.hp) {
    const attackerOwner = current.owner === OWNER_WAGON ? OWNER_PALADIN : OWNER_WAGON;
    const damage = previous.hp - current.hp;
    state.damageEvents[attackerOwner] += 1;
    state.damageDealt[attackerOwner] += damage;
    state.firstDamageTime[attackerOwner] ??= current.time;
  }
  if (previous?.alive && !current.alive) state.deaths[current.owner].push(current.time);
  state.previousById.set(current.id, current);
  return Object.freeze({ ...current, moved });
}


function finishFrame(state, time, rows) {
  const live = rows.filter(({ alive }) => alive);
  const wagons = live.filter(({ owner }) => owner === OWNER_WAGON);
  const paladins = live.filter(({ owner }) => owner === OWNER_PALADIN);
  const wagonWagonSurfaceGaps = pairwiseSurfaceGaps(wagons, wagons, {
    samePopulation: true,
    leftRadius: COLLISION_RADIUS[OWNER_WAGON],
    rightRadius: COLLISION_RADIUS[OWNER_WAGON],
  });
  const wagonPaladinSurfaceGaps = pairwiseSurfaceGaps(wagons, paladins, {
    samePopulation: false,
    leftRadius: COLLISION_RADIUS[OWNER_WAGON],
    rightRadius: COLLISION_RADIUS[OWNER_PALADIN],
  });
  const closestWagonWagonPair = closestPair(wagons, wagons, {
    samePopulation: true,
    extent: COLLISION_RADIUS[OWNER_WAGON] + COLLISION_RADIUS[OWNER_WAGON],
    time,
  });
  const closestWagonPaladinPair = closestPair(wagons, paladins, {
    samePopulation: false,
    extent: COLLISION_RADIUS[OWNER_WAGON] + COLLISION_RADIUS[OWNER_PALADIN],
    time,
  });
  const wagonWagonContacts = overlapContacts(
    wagons,
    wagons,
    COLLISION_RADIUS[OWNER_WAGON] + COLLISION_RADIUS[OWNER_WAGON],
    true,
  );
  const wagonPaladinContacts = overlapContacts(
    wagons,
    paladins,
    COLLISION_RADIUS[OWNER_WAGON] + COLLISION_RADIUS[OWNER_PALADIN],
    false,
  );
  const nearestSurfaceGaps = paladins.map((paladin) => {
    if (!wagons.length) return null;
    const centerDistance = Math.min(...wagons.map((wagon) => (
      Math.hypot(paladin.x - wagon.x, paladin.y - wagon.y)
    )));
    return centerDistance - COLLISION_RADIUS[OWNER_WAGON] - COLLISION_RADIUS[OWNER_PALADIN];
  }).filter(Number.isFinite);
  const paladinTargetCounts = countBy(
    paladins.filter(({ targetId }) => targetId !== null),
    ({ targetId }) => targetId,
  );
  const paladinTargets = Object.values(paladinTargetCounts);
  state.frames.push(Object.freeze({
    time,
    aliveWagons: wagons.length,
    alivePaladins: paladins.length,
    hpWagons: sum(wagons.map(({ hp }) => hp)),
    hpPaladins: sum(paladins.map(({ hp }) => hp)),
    movingWagons: wagons.filter(({ moved }) => moved).length,
    movingPaladins: paladins.filter(({ moved }) => moved).length,
    attackingWagons: wagons.filter(({ attacking }) => attacking).length,
    attackingPaladins: paladins.filter(({ attacking }) => attacking).length,
    chasingPaladins: paladins.filter(({ chasing }) => chasing).length,
    stalledChasingPaladins: paladins.filter(({ chasing, moved }) => chasing && !moved).length,
    paladinsWithTarget: sum(paladinTargets),
    paladinDistinctTargets: paladinTargets.length,
    paladinsOnLargestTarget: paladinTargets.length ? Math.max(...paladinTargets) : 0,
    nearestSurfaceGaps: Object.freeze(nearestSurfaceGaps),
    wagonWagonSurfaceGaps: Object.freeze(wagonWagonSurfaceGaps),
    wagonPaladinSurfaceGaps: Object.freeze(wagonPaladinSurfaceGaps),
    closestWagonWagonPair,
    closestWagonPaladinPair,
    wagonWagonOverlapPairs: wagonWagonContacts.pairs,
    wagonWagonOverlappingWagons: wagonWagonContacts.leftUnitsWithContact,
    maximumWagonWagonNeighbors: wagonWagonContacts.maximumLeftContacts,
    wagonPaladinOverlapPairs: wagonPaladinContacts.pairs,
    wagonsOverlappingPaladins: wagonPaladinContacts.leftUnitsWithContact,
    paladinsOverlappingWagons: wagonPaladinContacts.rightUnitsWithContact,
    maximumPaladinsOverlappingOneWagon: wagonPaladinContacts.maximumLeftContacts,
    maximumWagonsOverlappingOnePaladin: wagonPaladinContacts.maximumRightContacts,
  }));
}


function finalizeAnalysis(state) {
  const lastDeathTime = Math.max(
    ...state.deaths[OWNER_WAGON],
    ...state.deaths[OWNER_PALADIN],
  );
  const combatStart = state.firstActiveTime ?? state.frames[0]?.time ?? 0;
  const combatEnd = Number.isFinite(lastDeathTime)
    ? lastDeathTime
    : state.frames.at(-1)?.time ?? combatStart;
  const frames = state.frames.filter(({ time }) => time >= combatStart && time <= combatEnd);
  const gaps = frames.flatMap(({ nearestSurfaceGaps }) => nearestSurfaceGaps);
  const wagonWagonOverlap = summarizeOverlap(frames, {
    gapField: "wagonWagonSurfaceGaps",
    pairCountField: "wagonWagonOverlapPairs",
    leftContactField: "wagonWagonOverlappingWagons",
    leftAliveField: "aliveWagons",
    maximumPairsField: "wagonWagonOverlapPairs",
    maximumLeftContactsField: "maximumWagonWagonNeighbors",
    closestPairField: "closestWagonWagonPair",
  });
  const wagonPaladinOverlap = summarizeOverlap(frames, {
    gapField: "wagonPaladinSurfaceGaps",
    pairCountField: "wagonPaladinOverlapPairs",
    leftContactField: "wagonsOverlappingPaladins",
    leftAliveField: "aliveWagons",
    rightContactField: "paladinsOverlappingWagons",
    rightAliveField: "alivePaladins",
    maximumPairsField: "wagonPaladinOverlapPairs",
    maximumLeftContactsField: "maximumPaladinsOverlappingOneWagon",
    maximumRightContactsField: "maximumWagonsOverlappingOnePaladin",
    closestPairField: "closestWagonPaladinPair",
  });
  const paladinObservations = sum(frames.map(({ alivePaladins }) => alivePaladins));
  const chasingObservations = sum(frames.map(({ chasingPaladins }) => chasingPaladins));
  const aliveUnitSeconds = {
    2: integrateFrames(frames, "aliveWagons"),
    3: integrateFrames(frames, "alivePaladins"),
  };
  const movingUnitSeconds = {
    2: integrateFrames(frames, "movingWagons"),
    3: integrateFrames(frames, "movingPaladins"),
  };
  const pathByOwner = {
    2: sumPath(state, 2),
    3: sumPath(state, 3),
  };
  const final = state.frames.at(-1) ?? {};
  state.finalHpByOwner = {
    2: final.hpWagons ?? 0,
    3: final.hpPaladins ?? 0,
  };
  state.finalAliveByOwner = {
    2: final.aliveWagons ?? 0,
    3: final.alivePaladins ?? 0,
  };
  return Object.freeze({
    source: state.source,
    tag: state.tag,
    combatStartSeconds: round(combatStart),
    combatEndSeconds: round(combatEnd),
    combatDurationSeconds: round(combatEnd - combatStart),
    finalHpByOwner: Object.freeze(state.finalHpByOwner),
    finalAliveByOwner: Object.freeze(state.finalAliveByOwner),
    attackStartsByOwner: Object.freeze({ ...state.attackStarts }),
    attackStartTargetingByOwner: Object.freeze({
      2: targetingSummary(state.attackStartRecords[2]),
      3: targetingSummary(state.attackStartRecords[3]),
    }),
    unitsStartingAttacksByOwner: Object.freeze({
      2: state.attackers[2].size,
      3: state.attackers[3].size,
    }),
    damageEventsByOwner: Object.freeze({ ...state.damageEvents }),
    damageDealtByOwner: Object.freeze({
      2: round(state.damageDealt[2]),
      3: round(state.damageDealt[3]),
    }),
    damageEventsPerAttackStartByOwner: Object.freeze({
      2: ratio(state.damageEvents[2], state.attackStarts[2]),
      3: ratio(state.damageEvents[3], state.attackStarts[3]),
    }),
    firstDamageSecondsByOwner: Object.freeze({
      2: roundRelative(state.firstDamageTime[2], combatStart),
      3: roundRelative(state.firstDamageTime[3], combatStart),
    }),
    deathsByOwner: Object.freeze({
      2: state.deaths[2].length,
      3: state.deaths[3].length,
    }),
    firstDeathSecondsByOwner: Object.freeze({
      2: roundRelative(Math.min(...state.deaths[2]), combatStart),
      3: roundRelative(Math.min(...state.deaths[3]), combatStart),
    }),
    targetChangesByOwner: Object.freeze({ ...state.targetChanges }),
    meanPathTilesPerStartingUnit: Object.freeze({
      2: round(pathByOwner[2] / STARTING_COUNTS[2]),
      3: round(pathByOwner[3] / STARTING_COUNTS[3]),
    }),
    aliveUnitSecondsByOwner: Object.freeze({
      2: round(aliveUnitSeconds[2]),
      3: round(aliveUnitSeconds[3]),
    }),
    attackStartsPer100AliveUnitSeconds: Object.freeze({
      2: round(100 * state.attackStarts[2] / aliveUnitSeconds[2]),
      3: round(100 * state.attackStarts[3] / aliveUnitSeconds[3]),
    }),
    effectiveSpeedWhileMovingTilesPerSecond: Object.freeze({
      2: round(pathByOwner[2] / movingUnitSeconds[2]),
      3: round(pathByOwner[3] / movingUnitSeconds[3]),
    }),
    progressSpeedAcrossAliveTimeTilesPerSecond: Object.freeze({
      2: round(pathByOwner[2] / aliveUnitSeconds[2]),
      3: round(pathByOwner[3] / aliveUnitSeconds[3]),
    }),
    movingShareOfAliveObservations: Object.freeze({
      2: ratio(sum(frames.map(({ movingWagons }) => movingWagons)), sum(frames.map(({ aliveWagons }) => aliveWagons))),
      3: ratio(sum(frames.map(({ movingPaladins }) => movingPaladins)), paladinObservations),
    }),
    attackingShareOfAliveObservations: Object.freeze({
      2: ratio(sum(frames.map(({ attackingWagons }) => attackingWagons)), sum(frames.map(({ aliveWagons }) => aliveWagons))),
      3: ratio(sum(frames.map(({ attackingPaladins }) => attackingPaladins)), paladinObservations),
    }),
    stalledShareOfPaladinChaseObservations: ratio(
      sum(frames.map(({ stalledChasingPaladins }) => stalledChasingPaladins)),
      chasingObservations,
    ),
    paladinPursuitTargetConcentration: Object.freeze({
      medianDistinctTargets: round(median(frames.map(({ paladinDistinctTargets }) => paladinDistinctTargets))),
      medianLargestTargetShare: round(median(frames.map((frame) => ratio(
        frame.paladinsOnLargestTarget,
        frame.paladinsWithTarget,
      )).filter(Number.isFinite))),
      maximumPaladinsOnOneTarget: Math.max(0, ...frames.map(({ paladinsOnLargestTarget }) => paladinsOnLargestTarget)),
      openingTenSecondsMedianDistinctTargets: round(median(frames
        .filter(({ time }) => time <= combatStart + 10)
        .map(({ paladinDistinctTargets }) => paladinDistinctTargets))),
      openingTenSecondsMedianLargestTargetShare: round(median(frames
        .filter(({ time }) => time <= combatStart + 10)
        .map((frame) => ratio(frame.paladinsOnLargestTarget, frame.paladinsWithTarget))
        .filter(Number.isFinite))),
    }),
    paladinNearestWagonSurfaceGapTiles: quantiles(gaps),
    paladinProximityShare: Object.freeze({
      within0_10: ratio(gaps.filter((gap) => gap <= 0.10).length, gaps.length),
      within0_25: ratio(gaps.filter((gap) => gap <= 0.25).length, gaps.length),
      within0_50: ratio(gaps.filter((gap) => gap <= 0.50).length, gaps.length),
      within1_00: ratio(gaps.filter((gap) => gap <= 1.00).length, gaps.length),
    }),
    maximumSimultaneousPaladinsNearWagon: Object.freeze({
      within0_10: Math.max(0, ...frames.map(({ nearestSurfaceGaps }) => nearestSurfaceGaps.filter((gap) => gap <= 0.10).length)),
      within0_25: Math.max(0, ...frames.map(({ nearestSurfaceGaps }) => nearestSurfaceGaps.filter((gap) => gap <= 0.25).length)),
      within0_50: Math.max(0, ...frames.map(({ nearestSurfaceGaps }) => nearestSurfaceGaps.filter((gap) => gap <= 0.50).length)),
      within1_00: Math.max(0, ...frames.map(({ nearestSurfaceGaps }) => nearestSurfaceGaps.filter((gap) => gap <= 1.00).length)),
    }),
    maximumSimultaneousAttackers: Object.freeze({
      2: Math.max(0, ...frames.map(({ attackingWagons }) => attackingWagons)),
      3: Math.max(0, ...frames.map(({ attackingPaladins }) => attackingPaladins)),
    }),
    overlap: Object.freeze({
      wagonWagon: wagonWagonOverlap,
      wagonPaladin: wagonPaladinOverlap,
    }),
  });
}


function pairwiseSurfaceGaps(leftUnits, rightUnits, {
  samePopulation,
  leftRadius,
  rightRadius,
}) {
  const gaps = [];
  for (let leftIndex = 0; leftIndex < leftUnits.length; leftIndex += 1) {
    const rightStart = samePopulation ? leftIndex + 1 : 0;
    for (let rightIndex = rightStart; rightIndex < rightUnits.length; rightIndex += 1) {
      const left = leftUnits[leftIndex];
      const right = rightUnits[rightIndex];
      gaps.push(Math.hypot(left.x - right.x, left.y - right.y) - leftRadius - rightRadius);
    }
  }
  return gaps;
}


function closestPair(leftUnits, rightUnits, { samePopulation, extent, time }) {
  let closest = null;
  for (let leftIndex = 0; leftIndex < leftUnits.length; leftIndex += 1) {
    const rightStart = samePopulation ? leftIndex + 1 : 0;
    for (let rightIndex = rightStart; rightIndex < rightUnits.length; rightIndex += 1) {
      const left = leftUnits[leftIndex];
      const right = rightUnits[rightIndex];
      const centerDistance = Math.hypot(left.x - right.x, left.y - right.y);
      if (closest && centerDistance >= closest.centerDistanceTiles) continue;
      closest = Object.freeze({
        time: round(time),
        leftId: left.id,
        rightId: right.id,
        leftPosition: Object.freeze({ x: round(left.x), y: round(left.y) }),
        rightPosition: Object.freeze({ x: round(right.x), y: round(right.y) }),
        centerDistanceTiles: round(centerDistance),
        surfaceGapTiles: round(centerDistance - extent),
        overlapDepthTiles: round(Math.max(0, extent - centerDistance)),
      });
    }
  }
  return closest;
}


function overlapContacts(leftUnits, rightUnits, extent, samePopulation) {
  const leftContacts = new Map(leftUnits.map(({ id }) => [id, 0]));
  const rightContacts = samePopulation
    ? leftContacts
    : new Map(rightUnits.map(({ id }) => [id, 0]));
  let pairs = 0;
  for (let leftIndex = 0; leftIndex < leftUnits.length; leftIndex += 1) {
    const rightStart = samePopulation ? leftIndex + 1 : 0;
    for (let rightIndex = rightStart; rightIndex < rightUnits.length; rightIndex += 1) {
      const left = leftUnits[leftIndex];
      const right = rightUnits[rightIndex];
      if (Math.hypot(left.x - right.x, left.y - right.y) >= extent - 1e-9) continue;
      pairs += 1;
      leftContacts.set(left.id, (leftContacts.get(left.id) ?? 0) + 1);
      rightContacts.set(right.id, (rightContacts.get(right.id) ?? 0) + 1);
    }
  }
  return Object.freeze({
    pairs,
    leftUnitsWithContact: [...leftContacts.values()].filter((count) => count > 0).length,
    rightUnitsWithContact: [...rightContacts.values()].filter((count) => count > 0).length,
    maximumLeftContacts: Math.max(0, ...leftContacts.values()),
    maximumRightContacts: Math.max(0, ...rightContacts.values()),
  });
}


function summarizeOverlap(frames, {
  gapField,
  pairCountField,
  leftContactField,
  leftAliveField,
  rightContactField = null,
  rightAliveField = null,
  maximumPairsField,
  maximumLeftContactsField,
  maximumRightContactsField = null,
  closestPairField,
}) {
  const allGaps = frames.flatMap((frame) => frame[gapField]);
  const overlapDepths = allGaps.filter((gap) => gap < -1e-9).map((gap) => -gap);
  const closestGapByFrame = frames
    .map((frame) => frame[gapField].length ? Math.min(...frame[gapField]) : null)
    .filter(Number.isFinite);
  const output = {
    pairObservations: allGaps.length,
    overlappingPairObservations: overlapDepths.length,
    overlappingPairObservationShare: ratio(overlapDepths.length, allGaps.length),
    framesWithAnyOverlapShare: ratio(
      frames.filter((frame) => frame[pairCountField] > 0).length,
      frames.length,
    ),
    closestPairSurfaceGapTilesByFrame: quantiles(closestGapByFrame),
    overlapDepthTilesWhenOverlapping: quantiles(overlapDepths),
    leftUnitObservationOverlapShare: ratio(
      sum(frames.map((frame) => frame[leftContactField])),
      sum(frames.map((frame) => frame[leftAliveField])),
    ),
    maximumSimultaneousOverlapPairs: Math.max(0, ...frames.map((frame) => frame[maximumPairsField])),
    maximumContactsOnOneLeftUnit: Math.max(0, ...frames.map((frame) => frame[maximumLeftContactsField])),
    deepestOverlapExample: frames
      .map((frame) => frame[closestPairField])
      .filter(Boolean)
      .toSorted((left, right) => left.surfaceGapTiles - right.surfaceGapTiles)[0] ?? null,
  };
  if (rightContactField && rightAliveField) {
    output.rightUnitObservationOverlapShare = ratio(
      sum(frames.map((frame) => frame[rightContactField])),
      sum(frames.map((frame) => frame[rightAliveField])),
    );
  }
  if (maximumRightContactsField) {
    output.maximumContactsOnOneRightUnit = Math.max(
      0,
      ...frames.map((frame) => frame[maximumRightContactsField]),
    );
  }
  return Object.freeze(output);
}


function targetingSummary(records) {
  const byTime = new Map();
  for (const record of records) {
    if (!byTime.has(record.time)) byTime.set(record.time, []);
    byTime.get(record.time).push(record);
  }
  const volleys = [...byTime.entries()].toSorted(([left], [right]) => left - right).map(([time, rows]) => {
    const targetCounts = countBy(rows.filter(({ targetId }) => targetId !== null), ({ targetId }) => targetId);
    const counts = Object.values(targetCounts);
    return Object.freeze({
      time,
      attackers: rows.length,
      distinctTargets: counts.length,
      largestTargetShare: rows.length && counts.length ? Math.max(...counts) / rows.length : null,
    });
  });
  const opening = volleys[0] ?? null;
  return Object.freeze({
    volleys: volleys.length,
    opening: opening === null ? null : Object.freeze({
      time: round(opening.time),
      attackers: opening.attackers,
      distinctTargets: opening.distinctTargets,
      largestTargetShare: round(opening.largestTargetShare),
    }),
    medianAttackersPerVolley: median(volleys.map(({ attackers }) => attackers)),
    medianDistinctTargetsPerVolley: median(volleys.map(({ distinctTargets }) => distinctTargets)),
    medianLargestTargetShare: round(median(volleys.map(({ largestTargetShare }) => largestTargetShare).filter(Number.isFinite))),
  });
}


function integrateFrames(frames, field) {
  let total = 0;
  for (let index = 0; index < frames.length - 1; index += 1) {
    const delta = frames[index + 1].time - frames[index].time;
    if (delta > 0) total += frames[index][field] * delta;
  }
  return total;
}


function summarizeTapeRuns(runs) {
  const metrics = [
    ["combatDurationSeconds", (run) => run.combatDurationSeconds],
    ["wagonAttackStarts", (run) => run.attackStartsByOwner[2]],
    ["paladinAttackStarts", (run) => run.attackStartsByOwner[3]],
    ["wagonDamageEvents", (run) => run.damageEventsByOwner[2]],
    ["paladinDamageEvents", (run) => run.damageEventsByOwner[3]],
    ["wagonDamageDealt", (run) => run.damageDealtByOwner[2]],
    ["paladinDamageDealt", (run) => run.damageDealtByOwner[3]],
    ["paladinFirstDamageSeconds", (run) => run.firstDamageSecondsByOwner[3]],
    ["wagonFirstDeathSeconds", (run) => run.firstDeathSecondsByOwner[2]],
    ["paladinAttackShare", (run) => run.attackingShareOfAliveObservations[3]],
    ["paladinStalledChaseShare", (run) => run.stalledShareOfPaladinChaseObservations],
    ["paladinMedianSurfaceGap", (run) => run.paladinNearestWagonSurfaceGapTiles.median],
    ["paladinP10SurfaceGap", (run) => run.paladinNearestWagonSurfaceGapTiles.p10],
    ["paladinWithin0_25Share", (run) => run.paladinProximityShare.within0_25],
    ["maxPaladinsWithin0_25", (run) => run.maximumSimultaneousPaladinsNearWagon.within0_25],
    ["maxSimultaneousPaladinAttackers", (run) => run.maximumSimultaneousAttackers[3]],
  ];
  return Object.freeze({
    ...Object.fromEntries(metrics.map(([name, select]) => [
      name,
      quantiles(runs.map(select).filter(Number.isFinite)),
    ])),
    overlap: Object.freeze({
      wagonWagon: summarizeOverlapRuns(runs, "wagonWagon"),
      wagonPaladin: summarizeOverlapRuns(runs, "wagonPaladin"),
    }),
  });
}


function summarizeOverlapRuns(runs, key) {
  const metrics = [
    ["overlappingPairObservationShare", (value) => value.overlappingPairObservationShare],
    ["framesWithAnyOverlapShare", (value) => value.framesWithAnyOverlapShare],
    ["medianOverlapDepthTiles", (value) => value.overlapDepthTilesWhenOverlapping.median],
    ["p90OverlapDepthTiles", (value) => value.overlapDepthTilesWhenOverlapping.p90],
    ["maximumOverlapDepthTiles", (value) => value.overlapDepthTilesWhenOverlapping.max],
    ["leftUnitObservationOverlapShare", (value) => value.leftUnitObservationOverlapShare],
    ["rightUnitObservationOverlapShare", (value) => value.rightUnitObservationOverlapShare],
    ["maximumSimultaneousOverlapPairs", (value) => value.maximumSimultaneousOverlapPairs],
    ["maximumContactsOnOneLeftUnit", (value) => value.maximumContactsOnOneLeftUnit],
    ["maximumContactsOnOneRightUnit", (value) => value.maximumContactsOnOneRightUnit],
  ];
  return Object.freeze(Object.fromEntries(metrics.map(([name, select]) => [
    name,
    quantiles(runs.map(({ overlap }) => select(overlap[key])).filter(Number.isFinite)),
  ])));
}


function sumPath(state, owner) {
  return sum([...state.pathById.entries()]
    .filter(([id]) => state.previousById.get(id)?.owner === owner)
    .map(([, distance]) => distance));
}


function countBy(values, select) {
  const counts = {};
  for (const value of values) {
    const key = select(value);
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.freeze(counts);
}


function quantiles(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  if (!sorted.length) return Object.freeze({ min: null, p10: null, median: null, p90: null, max: null });
  return Object.freeze({
    min: round(sorted[0]),
    p10: round(sorted[Math.floor((sorted.length - 1) * 0.10)]),
    median: round(sorted[Math.floor((sorted.length - 1) * 0.50)]),
    p90: round(sorted[Math.floor((sorted.length - 1) * 0.90)]),
    max: round(sorted.at(-1)),
  });
}


function median(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


function roundRelative(value, origin) {
  return Number.isFinite(value) ? round(value - origin) : null;
}


function ratio(numerator, denominator) {
  return denominator ? round(numerator / denominator, 4) : null;
}


function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}


function round(value, digits = 3) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
