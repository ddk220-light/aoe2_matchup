import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";

import { createWorld, stepWorld } from "../../src/combat/world.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";
import {
  normalizeSimulationSnapshots,
  normalizeTapeFrames,
} from "../../tools/measure_pair_contact_states.mjs";
import { analyzePairContactFrames } from "../../tools/pair-contact-metrics.mjs";


const ROOT = new URL("../../", import.meta.url);
const ROW_ID = "elite_janissary_vs_elite_elephant";
const EXPECTED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const SEED = 20260817;
const TICKS_PER_SECOND = 60;
const CADENCE_MS = 100;
const TRACE = new URL(
  "janissary_elephant_2026-08-19/"
    + "elite_janissary_turks__vs__elite_elephant.tape_trace.jsonl",
  import.meta.url,
);
const ALL_ENTITY_TRACE = new URL(
  "janissary_elephant_all_entities_2026-08-19/"
    + "elite_janissary_turks__vs__elite_elephant.tape_trace.jsonl",
  import.meta.url,
);
const OUTPUT = new URL(
  "../reports/janissary_elephant_independent_cohort_2026-08-19/report.json",
  import.meta.url,
);


const truth = await loadPhase2Batch1Truth(ROOT);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row || row.runs.length !== 1 || truth.archive?.zip_sha256 !== EXPECTED_SHA256) {
  throw new Error("missing authorized Elite Janissary-Elite Battle Elephant row");
}
const archivePath = new URL(`../../${truth.archive.path}`, ROOT);
const observedHash = await sha256(archivePath);
if (observedHash !== EXPECTED_SHA256) {
  throw new Error(`Phase 2 archive hash mismatch: ${observedHash}`);
}
const context = await loadPhase2Batch1Context(ROOT, truth);
const rosterIds = new Set(row.runs[0].starting_units.map(({ id }) => id));
const rawTapeFrames = await readTapeTrace(TRACE, rosterIds);
const tapeFrames = trimCombatFrames(normalizeTapeFrames(
  rawTapeFrames,
  context.mechanicsByMaster,
  { cadenceMs: CADENCE_MS },
));
const tapeFullRate = trimCombatFrames(normalizeRawTapeFrames(
  rawTapeFrames,
  context.mechanicsByMaster,
));
const tapeEntityCounts = await countTapeEntities(ALL_ENTITY_TRACE, rosterIds);

const scenario = scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: 0,
  seed: SEED,
  context,
});
let world = createWorld(scenario);
const snapshots = [{ tick: 0, units: world.units }];
const events = [];
const shotKeys = new Set();
for (let elapsed = 0; elapsed < PHASE2_MAX_TICKS; elapsed += 1) {
  try {
    world = stepWorld(world);
  } catch (error) {
    const implicated = world.units.filter(({ referenceId }) => (
      referenceId === 1612 || referenceId === 1618
    ));
    error.message += `; priorTick=${world.tick}; implicated=${JSON.stringify(implicated.map((unit) => ({
      referenceId: unit.referenceId,
      x: unit.x,
      y: unit.y,
      action: unit.action,
      pursuitTargetId: unit.pursuitTargetId,
      engagedTargetId: unit.engagedTargetId,
      attackTargetId: unit.attackTargetId,
      moveOrder: unit.moveOrder ?? null,
    })))}; reservation=${JSON.stringify(world.contactReservationState?.reservations?.get("1612:1618") ?? null)}; inherited=${JSON.stringify(world.contactReservationState?.inheritedExtents?.get("1612:1618") ?? null)}`;
    throw error;
  }
  snapshots.push({ tick: world.tick, units: world.units });
  events.push(...world.events);
  for (const projectile of world.projectiles ?? []) {
    if (projectile.firedTick === world.tick) {
      shotKeys.add(`${projectile.actorId}:${projectile.firedTick}`);
    }
  }
  if (liveOwnerCount(world.units) <= 1) break;
  world = Object.freeze({ ...world, snapshots: Object.freeze([]), eventLog: Object.freeze([]) });
}
const simulationFrames = trimCombatFrames(normalizeSimulationSnapshots(
  snapshots,
  { cadenceMs: CADENCE_MS },
));
const simulationFullRate = trimCombatFrames(normalizeSimulationSnapshots(
  snapshots,
  { cadenceMs: 1000 / TICKS_PER_SECOND },
));

const report = Object.freeze({
  schemaVersion: 1,
  rowId: ROW_ID,
  source: Object.freeze({
    archive: truth.archive.name,
    expectedZipSha256: EXPECTED_SHA256,
    observedZipSha256: observedHash,
    tapeTrace: TRACE.pathname,
  }),
  roster: Object.freeze({ side2: row.side2, side3: row.side3 }),
  outcome: Object.freeze({
    tape: Object.freeze({
      winnerOwner: row.runs[0].winner_owner,
      winnerHp: row.runs[0].winner_hp,
      winnerHpPercent: Math.abs(row.runs[0].signed_score),
      survivors: row.runs[0].survivors,
      combatDurationSeconds: durationSeconds(tapeFrames),
    }),
    simulation: simulationOutcome(world, row),
  }),
  tape: Object.freeze({
    frames: tapeFrames.length,
    fullRateFrames: tapeFullRate.length,
    movement: analyzeMovement(tapeFrames),
    overlap: analyzeOverlap(tapeFrames),
    damage: analyzeFrameDamage(tapeFullRate),
    damageQuanta: analyzeTapeDamageQuanta(tapeFullRate),
    elephantDamageGeometry: analyzeTapeElephantDamageGeometry(tapeFullRate),
    meleeContactGeometry: analyzeTapeMeleeContactGeometry(tapeFullRate),
    attackStates: analyzeTapeAttackStates(tapeFullRate),
    observableEntityCreations: tapeEntityCounts,
  }),
  simulation: Object.freeze({
    frames: simulationFrames.length,
    fullRateFrames: simulationFullRate.length,
    movement: analyzeMovement(simulationFrames),
    overlap: analyzeOverlap(simulationFrames),
    damage: analyzeSimulationEvents(events, snapshots[0].units),
    damageQuanta: analyzeSimulationDamageQuanta(events, snapshots[0].units),
    elephantDamageGeometry: analyzeSimulationElephantDamageGeometry(
      events,
      snapshots,
      snapshots[0].units,
    ),
    meleeContactGeometry: analyzeSimulationMeleeContactGeometry(
      simulationFullRate,
      events,
      snapshots[0].units,
    ),
    shotsFired: shotKeys.size,
    pursuitRouting: summarizePursuitRouting(events),
  }),
});

await mkdir(new URL(
  "../reports/janissary_elephant_independent_cohort_2026-08-19/",
  import.meta.url,
), {
  recursive: true,
});
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);


async function sha256(url) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(url)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}


async function readTapeTrace(url, roster) {
  const frames = [];
  let timeMs = null;
  let units = [];
  const lines = createInterface({ input: createReadStream(url), crlfDelay: Infinity });
  for await (const line of lines) {
    if (!line) continue;
    const raw = JSON.parse(line);
    if (!roster.has(raw.id)) continue;
    if (timeMs !== null && raw.t_ms !== timeMs) {
      frames.push({ timeMs, units });
      units = [];
    }
    timeMs = raw.t_ms;
    units.push(raw);
  }
  if (timeMs !== null) frames.push({ timeMs, units });
  return frames;
}


function normalizeRawTapeFrames(rawFrames, mechanicsByMaster) {
  const previous = new Map();
  return rawFrames.map((frame) => Object.freeze({
    timeMs: frame.timeMs,
    units: Object.freeze(frame.units.map((raw) => {
      const mechanics = mechanicsByMaster.get(raw.master);
      if (!mechanics) throw new Error(`missing mechanics for master ${raw.master}`);
      const before = previous.get(raw.id);
      const moving = before !== undefined
        && Math.hypot(raw.x - before.x, raw.y - before.y) > 1e-9;
      previous.set(raw.id, raw);
      const targetId = Number.isSafeInteger(raw.target_id) && raw.target_id >= 0
        ? raw.target_id
        : null;
      return Object.freeze({
        id: raw.id,
        owner: raw.owner,
        master: raw.master,
        x: raw.x,
        y: raw.y,
        hp: raw.hp,
        radius: Math.max(
          mechanics.collision_size_tiles.x,
          mechanics.collision_size_tiles.y,
        ),
        minCollisionMultiplier: mechanics.min_collision_size_multiplier ?? 1,
        moving,
        attacking: raw.action_state === 7,
        pursuitTargetId: targetId,
        engagedTargetId: targetId,
        attackTargetId: raw.action_state === 7 ? targetId : null,
      });
    })),
  }));
}


async function countTapeEntities(url, roster) {
  const byOwnerMaster = new Map();
  const lines = createInterface({ input: createReadStream(url), crlfDelay: Infinity });
  for await (const line of lines) {
    if (!line) continue;
    const raw = JSON.parse(line);
    if (roster.has(raw.id)) continue;
    const key = `${raw.owner}:${raw.master}`;
    if (!byOwnerMaster.has(key)) byOwnerMaster.set(key, new Set());
    byOwnerMaster.get(key).add(raw.id);
  }
  return Object.freeze(Object.fromEntries([...byOwnerMaster]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, ids]) => [key, ids.size])));
}


function trimCombatFrames(frames) {
  const first = frames.findIndex(({ units }) => liveOwnerCount(units) >= 2);
  if (first < 0) throw new Error("no two-owner combat frame");
  let last = frames.length - 1;
  for (let index = first + 1; index < frames.length; index += 1) {
    if (liveOwnerCount(frames[index].units) < 2) {
      last = index;
      break;
    }
  }
  return frames.slice(first, last + 1);
}


function liveOwnerCount(units) {
  return new Set(units.filter(({ hp, alive = hp > 0 }) => alive && hp > 0)
    .map(({ owner }) => owner)).size;
}


function durationSeconds(frames) {
  return (frames.at(-1).timeMs - frames[0].timeMs) / 1000;
}


function analyzeMovement(frames) {
  const accumulators = new Map([
    [2, movementAccumulator()],
    [3, movementAccumulator()],
  ]);
  for (let frameIndex = 1; frameIndex < frames.length; frameIndex += 1) {
    const before = frames[frameIndex - 1];
    const after = frames[frameIndex];
    const beforeById = new Map(before.units.map((unit) => [unit.id, unit]));
    const afterById = new Map(after.units.map((unit) => [unit.id, unit]));
    for (const unit of before.units) {
      if (unit.hp <= 0 || !accumulators.has(unit.owner)) continue;
      const next = afterById.get(unit.id);
      if (!next || next.hp <= 0) continue;
      const accumulator = accumulators.get(unit.owner);
      accumulator.unitSteps += 1;
      const dx = next.x - unit.x;
      const dy = next.y - unit.y;
      const distance = Math.hypot(dx, dy);
      accumulator.distance += distance;
      if (distance <= 1e-9) {
        accumulator.stalled += 1;
        continue;
      }
      accumulator.moving += 1;
      const target = targetFor(unit, before.units, beforeById);
      if (!target) continue;
      accumulator.targetedMoving += 1;
      const tx = target.x - unit.x;
      const ty = target.y - unit.y;
      const targetDistance = Math.hypot(tx, ty);
      if (targetDistance <= 1e-9) continue;
      const cosine = (dx * tx + dy * ty) / (distance * targetDistance);
      if (cosine >= 0.5) accumulator.direct += 1;
      else if (cosine > 0.05) accumulator.oblique += 1;
      else if (cosine >= -0.05) accumulator.lateral += 1;
      else accumulator.away += 1;

      const targetNext = afterById.get(target.id) ?? target;
      const afterDistance = Math.hypot(targetNext.x - next.x, targetNext.y - next.y);
      const progress = targetDistance - afterDistance;
      accumulator.netTargetProgress += progress;
      if (progress > 1e-6) accumulator.closing += 1;
      else if (progress < -1e-6) accumulator.opening += 1;
      else accumulator.neutral += 1;
    }
  }
  const cadenceSeconds = (frames.at(-1).timeMs - frames[0].timeMs)
    / Math.max(1, frames.length - 1) / 1000;
  return Object.freeze(Object.fromEntries([...accumulators].map(([owner, value]) => [
    owner,
    Object.freeze({
      unitSteps: value.unitSteps,
      movingShare: ratio(value.moving, value.unitSteps),
      stalledShare: ratio(value.stalled, value.unitSteps),
      meanSpeedWhileMoving: value.moving
        ? value.distance / (value.moving * cadenceSeconds)
        : 0,
      headingShares: Object.freeze({
        direct: ratio(value.direct, value.targetedMoving),
        oblique: ratio(value.oblique, value.targetedMoving),
        lateral: ratio(value.lateral, value.targetedMoving),
        away: ratio(value.away, value.targetedMoving),
      }),
      targetDistanceShares: Object.freeze({
        closing: ratio(value.closing, value.targetedMoving),
        opening: ratio(value.opening, value.targetedMoving),
        neutral: ratio(value.neutral, value.targetedMoving),
      }),
      netTargetProgressTiles: clean(value.netTargetProgress),
    }),
  ])));
}


function movementAccumulator() {
  return {
    unitSteps: 0,
    moving: 0,
    stalled: 0,
    targetedMoving: 0,
    direct: 0,
    oblique: 0,
    lateral: 0,
    away: 0,
    closing: 0,
    opening: 0,
    neutral: 0,
    distance: 0,
    netTargetProgress: 0,
  };
}


function targetFor(unit, units, byId) {
  for (const candidate of [unit.attackTargetId, unit.engagedTargetId, unit.pursuitTargetId]) {
    const target = byId.get(candidate);
    if (target?.hp > 0 && target.owner !== unit.owner) return target;
  }
  let nearest = null;
  let nearestDistance = Infinity;
  for (const target of units) {
    if (target.hp <= 0 || target.owner === unit.owner) continue;
    const distance = Math.hypot(target.x - unit.x, target.y - unit.y);
    if (distance < nearestDistance) {
      nearest = target;
      nearestDistance = distance;
    }
  }
  return nearest;
}


function analyzeOverlap(frames) {
  const ownerMetric = (owner) => overlapSummary(analyzePairContactFrames(frames.map((frame) => ({
    ...frame,
    units: frame.units.filter((unit) => unit.owner === owner),
  }))).relationships["same-master-allies"]);
  return Object.freeze({
    owner2: ownerMetric(2),
    owner3: ownerMetric(3),
    enemies: overlapSummary(analyzePairContactFrames(frames).relationships.enemies),
  });
}


function overlapSummary(metric) {
  if (!metric) return null;
  return Object.freeze({
    overlapPairShare: metric.overlapPairShare,
    framesWithOverlap: metric.framesWithOverlap,
    frameCount: metric.frameCount,
    frameOverlapShare: ratio(metric.framesWithOverlap, metric.frameCount),
    medianDepth: metric.medianDepth,
    p95Depth: metric.p95Depth,
    maximumDepth: metric.maximumDepth,
    medianContactWindowMs: metric.contactWindowMs?.median ?? null,
    maximumContactWindowMs: metric.contactWindowMs?.maximum ?? null,
    maximumLocalDegree: metric.maximumLocalDegree,
    maximumComponentSize: metric.maximumComponentSize,
  });
}


function analyzeFrameDamage(frames) {
  const summaries = new Map([[2, damageAccumulator()], [3, damageAccumulator()]]);
  const firstSeen = new Map();
  const lastSeen = new Map();
  for (let frameIndex = 0; frameIndex < frames.length; frameIndex += 1) {
    const frame = frames[frameIndex];
    const beforeById = frameIndex > 0
      ? new Map(frames[frameIndex - 1].units.map((unit) => [unit.id, unit]))
      : new Map();
    for (const unit of frame.units) {
      if (!firstSeen.has(unit.id)) firstSeen.set(unit.id, frame.timeMs);
      lastSeen.set(unit.id, { timeMs: frame.timeMs, owner: unit.owner, hp: unit.hp });
      const before = beforeById.get(unit.id);
      if (!before || !Number.isFinite(before.hp) || !Number.isFinite(unit.hp)) continue;
      const amount = before.hp - unit.hp;
      if (amount <= 1e-9) continue;
      const attackerOwner = unit.owner === 2 ? 3 : 2;
      const summary = summaries.get(attackerOwner);
      summary.damageEvents += 1;
      summary.damage += amount;
      summary.firstDamageMs ??= frame.timeMs;
      summary.lastDamageMs = frame.timeMs;
    }
  }
  const finalTime = frames.at(-1).timeMs;
  const deathTimes = new Map([[2, []], [3, []]]);
  for (const [id, state] of lastSeen) {
    if (state.hp <= 0 || state.timeMs < finalTime - 50) {
      const attackerOwner = state.owner === 2 ? 3 : 2;
      deathTimes.get(attackerOwner).push(state.timeMs);
    }
  }
  for (const [owner, times] of deathTimes) {
    if (!times.length) continue;
    const summary = summaries.get(owner);
    summary.deaths = times.length;
    summary.firstDeathMs = Math.min(...times);
    summary.lastDeathMs = Math.max(...times);
  }
  return finishDamage(summaries, frames[0].timeMs, finalTime);
}


function analyzeSimulationEvents(events, initialUnits) {
  const ownerById = new Map(initialUnits.map((unit) => [unit.referenceId, unit.owner]));
  const summaries = new Map([[2, damageAccumulator()], [3, damageAccumulator()]]);
  for (const event of events) {
    const attackerOwner = ownerById.get(event.actorId);
    if (!summaries.has(attackerOwner)) continue;
    const summary = summaries.get(attackerOwner);
    if (event.type === "attack-start") summary.attackStarts += 1;
    if (event.type === "attack-canceled") summary.attackCanceled += 1;
    if (event.type === "damage") {
      summary.damageEvents += 1;
      summary.damage += event.hpBefore - event.hpAfter;
      summary.firstDamageMs ??= 1000 * event.tick / TICKS_PER_SECOND;
      summary.lastDamageMs = 1000 * event.tick / TICKS_PER_SECOND;
    }
    if (event.type === "death") {
      summary.deaths += 1;
      summary.firstDeathMs ??= 1000 * event.tick / TICKS_PER_SECOND;
      summary.lastDeathMs = 1000 * event.tick / TICKS_PER_SECOND;
    }
  }
  return finishDamage(summaries, 0, 1000 * world.tick / TICKS_PER_SECOND);
}


function analyzeTapeDamageQuanta(frames) {
  const byAttackerOwner = new Map([[2, []], [3, []]]);
  for (let frameIndex = 1; frameIndex < frames.length; frameIndex += 1) {
    const beforeById = new Map(frames[frameIndex - 1].units.map((unit) => [unit.id, unit]));
    const grouped = new Map([[2, []], [3, []]]);
    for (const unit of frames[frameIndex].units) {
      const before = beforeById.get(unit.id);
      if (!before) continue;
      const amount = before.hp - unit.hp;
      if (amount <= 1e-9) continue;
      grouped.get(unit.owner === 2 ? 3 : 2).push(amount);
    }
    for (const [owner, amounts] of grouped) {
      if (!amounts.length) continue;
      byAttackerOwner.get(owner).push(Object.freeze({
        timeMs: frames[frameIndex].timeMs,
        victimCount: amounts.length,
        damage: amounts.reduce((total, amount) => total + amount, 0),
        amounts: Object.freeze(amounts.map(clean).sort((left, right) => left - right)),
      }));
    }
  }
  return Object.freeze(Object.fromEntries([...byAttackerOwner].map(([owner, groups]) => [
    owner,
    summarizeDamageGroups(groups),
  ])));
}


function analyzeTapeAttackStates(frames) {
  const prior = new Map();
  const starts = new Map([[2, 0], [3, 0]]);
  const attackingUnitFrames = new Map([[2, 0], [3, 0]]);
  const liveUnitFrames = new Map([[2, 0], [3, 0]]);
  for (const frame of frames) {
    for (const unit of frame.units) {
      if (unit.hp <= 0 || !starts.has(unit.owner)) continue;
      const attacking = unit.attacking === true;
      if (attacking && prior.get(unit.id) !== true) starts.set(unit.owner, starts.get(unit.owner) + 1);
      prior.set(unit.id, attacking);
      liveUnitFrames.set(unit.owner, liveUnitFrames.get(unit.owner) + 1);
      if (attacking) attackingUnitFrames.set(unit.owner, attackingUnitFrames.get(unit.owner) + 1);
    }
  }
  return Object.freeze(Object.fromEntries([...starts].map(([owner, value]) => [owner, Object.freeze({
    observedAttackStateEntries: value,
    attackingUnitFrameShare: ratio(attackingUnitFrames.get(owner), liveUnitFrames.get(owner)),
  })])));
}


function analyzeTapeElephantDamageGeometry(frames) {
  const swings = [];
  for (let frameIndex = 1; frameIndex < frames.length; frameIndex += 1) {
    const beforeById = new Map(frames[frameIndex - 1].units.map((unit) => [unit.id, unit]));
    const frame = frames[frameIndex];
    const damaged = frame.units.filter((unit) => {
      const before = beforeById.get(unit.id);
      return unit.owner === 2 && before && before.hp - unit.hp > 1e-9;
    });
    if (!damaged.length) continue;
    const damagedIds = new Set(damaged.map(({ id }) => id));
    const attackers = frame.units.filter((unit) => (
      unit.owner === 3 && unit.attacking && damagedIds.has(unit.attackTargetId)
    ));
    for (const actor of attackers) {
      const eligible = frame.units.filter((unit) => (
        unit.owner === 2 && unit.hp > 0 && blastBoxReach(actor, unit) <= 0.4 + 1e-12
      ));
      swings.push(Object.freeze({
        timeMs: frame.timeMs,
        actorId: actor.id,
        targetId: actor.attackTargetId,
        actorPosition: Object.freeze({ x: clean(actor.x), y: clean(actor.y) }),
        observedDamagedVictims: damaged.length,
        blastEligibleVictims: eligible.length,
        blastEligibleNonTargets: eligible.filter(({ id }) => id !== actor.attackTargetId).length,
        eligibleIds: Object.freeze(eligible.map(({ id }) => id)),
      }));
    }
  }
  return summarizeElephantGeometry(swings);
}


function analyzeTapeMeleeContactGeometry(frames) {
  const delivered = new Set();
  for (let frameIndex = 1; frameIndex < frames.length; frameIndex += 1) {
    const beforeById = new Map(frames[frameIndex - 1].units.map((unit) => [unit.id, unit]));
    const frame = frames[frameIndex];
    const damagedIds = new Set(frame.units
      .filter((unit) => {
        const before = beforeById.get(unit.id);
        return unit.owner === 2 && before && before.hp - unit.hp > 1e-9;
      })
      .map(({ id }) => id));
    for (const actor of frame.units) {
      if (actor.owner !== 3 || !actor.attacking || !damagedIds.has(actor.attackTargetId)) continue;
      delivered.add(`${frame.timeMs}:${actor.id}:${actor.attackTargetId}`);
    }
  }
  return analyzeMeleeContactGeometry(frames, delivered);
}


function analyzeSimulationMeleeContactGeometry(frames, events, initialUnits) {
  const ownerById = new Map(initialUnits.map((unit) => [unit.referenceId, unit.owner]));
  const delivered = new Set(events
    .filter((event) => (
      event.type === "damage"
        && event.kind !== "trample"
        && ownerById.get(event.actorId) === 3
    ))
    .map((event) => `${clean(1000 * event.tick / TICKS_PER_SECOND)}:${event.actorId}:${event.targetId}`));
  return analyzeMeleeContactGeometry(frames, delivered);
}


function analyzeMeleeContactGeometry(frames, delivered) {
  const attackSamples = [];
  const pairStates = new Map([
    ["both-moving", pairStateAccumulator()],
    ["moving-through-attacker", pairStateAccumulator()],
    ["both-attacking", pairStateAccumulator()],
    ["one-moving", pairStateAccumulator()],
    ["neither-moving", pairStateAccumulator()],
  ]);
  const attackersPerTarget = [];
  for (const frame of frames) {
    const byId = new Map(frame.units.map((unit) => [unit.id, unit]));
    const elephants = frame.units.filter((unit) => unit.owner === 3 && unit.hp > 0);
    const attackingByTarget = new Map();
    for (const actor of elephants) {
      if (!actor.attacking) continue;
      const target = byId.get(actor.attackTargetId);
      if (!target || target.hp <= 0 || target.owner === actor.owner) continue;
      if (!attackingByTarget.has(target.id)) attackingByTarget.set(target.id, []);
      attackingByTarget.get(target.id).push(actor);
      const blockers = alliedLineBlockers(actor, target, elephants);
      const overlappingAllies = elephants.filter((ally) => (
        ally.id !== actor.id && pairOverlapDepth(actor, ally) > 1e-12
      ));
      attackSamples.push(Object.freeze({
        delivered: delivered.has(`${clean(frame.timeMs)}:${actor.id}:${target.id}`),
        occluded: blockers.length > 0,
        occludedByAttackingAlly: blockers.some(({ attacking }) => attacking),
        occludedBySameTargetAttacker: blockers.some((ally) => (
          ally.attacking && ally.attackTargetId === target.id
        )),
        blockerCount: blockers.length,
        overlappingAllyCount: overlappingAllies.length,
        overlappingAttackingAllyCount: overlappingAllies.filter(({ attacking }) => attacking).length,
        targetSurfaceGap: pairSurfaceGap(actor, target),
      }));
    }
    for (const attackers of attackingByTarget.values()) attackersPerTarget.push(attackers.length);

    for (let leftIndex = 0; leftIndex < elephants.length; leftIndex += 1) {
      const left = elephants[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < elephants.length; rightIndex += 1) {
        const right = elephants[rightIndex];
        const state = elephantPairState(left, right);
        const accumulator = pairStates.get(state);
        const depth = pairOverlapDepth(left, right);
        accumulator.observations += 1;
        accumulator.minimumSeparation = Math.min(
          accumulator.minimumSeparation,
          chebyshevSeparation(left, right),
        );
        if (depth <= 1e-12) continue;
        accumulator.overlaps += 1;
        accumulator.depths.push(depth);
      }
    }
  }
  const deliveredSamples = attackSamples.filter(({ delivered: hit }) => hit);
  return Object.freeze({
    definition: Object.freeze({
      occludedAttack: "actor-target center segment intersects a live allied collision square whose center projects between actor and target",
      overlapDepth: "max(0, allied collision-radius sum minus Chebyshev center separation)",
    }),
    attackState: summarizeAttackContactSamples(attackSamples),
    deliveredPrimaryHits: summarizeAttackContactSamples(deliveredSamples),
    targetOccupancy: Object.freeze({
      observedTargetFrames: attackersPerTarget.length,
      meanAttackersPerTarget: clean(mean(attackersPerTarget)),
      maximumAttackersPerTarget: attackersPerTarget.length ? Math.max(...attackersPerTarget) : 0,
      multipleAttackersShare: ratio(
        attackersPerTarget.filter((count) => count > 1).length,
        attackersPerTarget.length,
      ),
      histogram: histogram(attackersPerTarget),
    }),
    alliedPairStates: Object.freeze(Object.fromEntries([...pairStates].map(([state, value]) => [
      state,
      summarizePairState(value),
    ]))),
  });
}


function alliedLineBlockers(actor, target, allies) {
  const dx = target.x - actor.x;
  const dy = target.y - actor.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared <= 1e-18) return [];
  return allies.filter((ally) => {
    if (ally.id === actor.id || ally.hp <= 0) return false;
    const centerProjection = ((ally.x - actor.x) * dx + (ally.y - actor.y) * dy)
      / lengthSquared;
    if (centerProjection <= 1e-9 || centerProjection >= 1 - 1e-9) return false;
    return segmentIntersectsSquare(actor, target, ally, ally.radius);
  });
}


function segmentIntersectsSquare(start, end, square, radius) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  let entry = 0;
  let exit = 1;
  for (const [origin, delta, minimum, maximum] of [
    [start.x, dx, square.x - radius, square.x + radius],
    [start.y, dy, square.y - radius, square.y + radius],
  ]) {
    if (Math.abs(delta) <= 1e-18) {
      if (origin < minimum || origin > maximum) return false;
      continue;
    }
    const first = (minimum - origin) / delta;
    const second = (maximum - origin) / delta;
    const near = Math.min(first, second);
    const far = Math.max(first, second);
    entry = Math.max(entry, near);
    exit = Math.min(exit, far);
    if (entry > exit) return false;
  }
  return exit > 1e-9 && entry < 1 - 1e-9;
}


function elephantPairState(left, right) {
  if (left.attacking && right.attacking) return "both-attacking";
  if ((left.attacking && right.moving) || (right.attacking && left.moving)) {
    return "moving-through-attacker";
  }
  if (left.moving && right.moving) return "both-moving";
  if (left.moving || right.moving) return "one-moving";
  return "neither-moving";
}


function pairStateAccumulator() {
  return { observations: 0, overlaps: 0, depths: [], minimumSeparation: Infinity };
}


function summarizePairState(value) {
  return Object.freeze({
    observations: value.observations,
    overlaps: value.overlaps,
    overlapShare: ratio(value.overlaps, value.observations),
    medianDepth: clean(median(value.depths)),
    p95Depth: clean(percentileValue(value.depths, 0.95)),
    maximumDepth: value.depths.length ? clean(Math.max(...value.depths)) : 0,
    minimumSeparation: Number.isFinite(value.minimumSeparation)
      ? clean(value.minimumSeparation)
      : null,
  });
}


function summarizeAttackContactSamples(samples) {
  return Object.freeze({
    samples: samples.length,
    occludedByAnyAllyShare: ratio(samples.filter(({ occluded }) => occluded).length, samples.length),
    occludedByAttackingAllyShare: ratio(
      samples.filter(({ occludedByAttackingAlly }) => occludedByAttackingAlly).length,
      samples.length,
    ),
    occludedBySameTargetAttackerShare: ratio(
      samples.filter(({ occludedBySameTargetAttacker }) => occludedBySameTargetAttacker).length,
      samples.length,
    ),
    withOverlappingAllyShare: ratio(
      samples.filter(({ overlappingAllyCount }) => overlappingAllyCount > 0).length,
      samples.length,
    ),
    withOverlappingAttackingAllyShare: ratio(
      samples.filter(({ overlappingAttackingAllyCount }) => (
        overlappingAttackingAllyCount > 0
      )).length,
      samples.length,
    ),
    meanBlockerCount: clean(mean(samples.map(({ blockerCount }) => blockerCount))),
    maximumBlockerCount: samples.length ? Math.max(...samples.map(({ blockerCount }) => blockerCount)) : 0,
    medianTargetSurfaceGap: clean(median(samples.map(({ targetSurfaceGap }) => targetSurfaceGap))),
    p95TargetSurfaceGap: clean(percentileValue(
      samples.map(({ targetSurfaceGap }) => targetSurfaceGap),
      0.95,
    )),
  });
}


function pairOverlapDepth(left, right) {
  return Math.max(0, left.radius + right.radius - chebyshevSeparation(left, right));
}


function pairSurfaceGap(left, right) {
  return chebyshevSeparation(left, right) - left.radius - right.radius;
}


function chebyshevSeparation(left, right) {
  return Math.max(Math.abs(left.x - right.x), Math.abs(left.y - right.y));
}


function percentileValue(values, quantile) {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  const index = (sorted.length - 1) * quantile;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}


function analyzeSimulationDamageQuanta(events, initialUnits) {
  const ownerById = new Map(initialUnits.map((unit) => [unit.referenceId, unit.owner]));
  const grouped = new Map();
  for (const event of events) {
    if (event.type !== "damage") continue;
    const owner = ownerById.get(event.actorId);
    if (owner !== 2 && owner !== 3) continue;
    const key = `${owner}:${event.actorId}:${event.tick}`;
    if (!grouped.has(key)) grouped.set(key, { owner, actorId: event.actorId, tick: event.tick, events: [] });
    grouped.get(key).events.push(event);
  }
  const byOwner = new Map([[2, []], [3, []]]);
  for (const group of grouped.values()) {
    byOwner.get(group.owner).push(Object.freeze({
      actorId: group.actorId,
      tick: group.tick,
      victimCount: group.events.length,
      damage: group.events.reduce((total, event) => total + event.hpBefore - event.hpAfter, 0),
      primaryVictims: group.events.filter(({ kind }) => kind !== "trample").length,
      trampleVictims: group.events.filter(({ kind }) => kind === "trample").length,
      amounts: Object.freeze(group.events
        .map((event) => clean(event.hpBefore - event.hpAfter))
        .sort((left, right) => left - right)),
    }));
  }
  return Object.freeze(Object.fromEntries([...byOwner].map(([owner, groups]) => [
    owner,
    summarizeDamageGroups(groups),
  ])));
}


function analyzeSimulationElephantDamageGeometry(events, snapshots, initialUnits) {
  const ownerById = new Map(initialUnits.map((unit) => [unit.referenceId, unit.owner]));
  const swings = [];
  const groups = new Map();
  for (const event of events) {
    if (event.type !== "damage" || ownerById.get(event.actorId) !== 3) continue;
    const key = `${event.actorId}:${event.tick}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(event);
  }
  for (const group of groups.values()) {
    const primary = group.find(({ kind }) => kind !== "trample");
    if (!primary) continue;
    const frame = snapshots[primary.tick];
    const actor = frame.units.find(({ referenceId }) => referenceId === primary.actorId);
    if (!actor) continue;
    const eligible = frame.units.filter((unit) => (
      unit.alive && unit.owner === 2 && blastBoxReach(actor, unit) <= 0.4 + 1e-12
    ));
    swings.push(Object.freeze({
      tick: primary.tick,
      actorId: primary.actorId,
      targetId: primary.targetId,
      actorPosition: Object.freeze({ x: clean(actor.x), y: clean(actor.y) }),
      observedDamagedVictims: group.length,
      blastEligibleVictims: eligible.length,
      blastEligibleNonTargets: eligible.filter(
        ({ referenceId }) => referenceId !== primary.targetId,
      ).length,
      eligibleIds: Object.freeze(eligible.map(({ referenceId }) => referenceId)),
    }));
  }
  return summarizeElephantGeometry(swings);
}


function summarizeElephantGeometry(swings) {
  const usesTicks = swings.some(({ tick }) => Number.isSafeInteger(tick));
  const swingsByActor = new Map();
  for (const swing of swings) {
    if (!swingsByActor.has(swing.actorId)) swingsByActor.set(swing.actorId, []);
    swingsByActor.get(swing.actorId).push(swing.tick ?? swing.timeMs);
  }
  const swingCounts = [...swingsByActor.values()].map(({ length }) => length);
  const repeatIntervalsMs = [];
  for (const values of swingsByActor.values()) {
    values.sort((left, right) => left - right);
    for (let index = 1; index < values.length; index += 1) {
      repeatIntervalsMs.push(usesTicks
        ? (values[index] - values[index - 1]) * 1000 / TICKS_PER_SECOND
        : values[index] - values[index - 1]);
    }
  }
  return Object.freeze({
    matchedSwings: swings.length,
    actorsWithSwings: swingsByActor.size,
    meanSwingsPerActor: clean(mean(swingCounts)),
    maximumSwingsPerActor: swingCounts.length ? Math.max(...swingCounts) : 0,
    swingCountHistogram: histogram(swingCounts),
    medianRepeatIntervalMs: clean(median(repeatIntervalsMs)),
    meanBlastEligibleVictims: clean(mean(swings.map(({ blastEligibleVictims }) => (
      blastEligibleVictims
    )))),
    maximumBlastEligibleVictims: swings.length
      ? Math.max(...swings.map(({ blastEligibleVictims }) => blastEligibleVictims))
      : 0,
    eligibleVictimHistogram: histogram(swings.map(({ blastEligibleVictims }) => (
      blastEligibleVictims
    ))),
    largest: Object.freeze([...swings]
      .sort((left, right) => right.blastEligibleVictims - left.blastEligibleVictims)
      .slice(0, 8)),
  });
}


function blastBoxReach(actor, victim) {
  const radius = victim.radius ?? Math.max(
    victim.mechanics.collision_size_tiles.x,
    victim.mechanics.collision_size_tiles.y,
  );
  return Math.hypot(
    Math.max(0, Math.abs(victim.x - actor.x) - radius),
    Math.max(0, Math.abs(victim.y - actor.y) - radius),
  );
}


function summarizeDamageGroups(groups) {
  const victimCounts = groups.map(({ victimCount }) => victimCount);
  const damageAmounts = groups.flatMap(({ amounts }) => amounts);
  const trampleVictims = groups.reduce((total, group) => total + (group.trampleVictims ?? 0), 0);
  return Object.freeze({
    hitGroups: groups.length,
    victims: victimCounts.reduce((total, count) => total + count, 0),
    meanVictimsPerHitGroup: clean(mean(victimCounts)),
    maximumVictimsPerHitGroup: victimCounts.length ? Math.max(...victimCounts) : 0,
    trampleVictims,
    meanTrampleVictimsPerHitGroup: clean(trampleVictims / Math.max(1, groups.length)),
    victimCountHistogram: histogram(victimCounts),
    damageAmountHistogram: histogram(damageAmounts.map((value) => clean(value))),
  });
}


function histogram(values) {
  const counts = new Map();
  for (const value of values) counts.set(String(value), (counts.get(String(value)) ?? 0) + 1);
  return Object.freeze(Object.fromEntries([...counts].sort(([left], [right]) => Number(left) - Number(right))));
}


function mean(values) {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : 0;
}


function median(values) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}


function damageAccumulator() {
  return {
    attackStarts: 0,
    attackCanceled: 0,
    damageEvents: 0,
    damage: 0,
    deaths: 0,
    firstDamageMs: null,
    lastDamageMs: null,
    firstDeathMs: null,
    lastDeathMs: null,
  };
}


function finishDamage(summaries, startMs, endMs) {
  const duration = (endMs - startMs) / 1000;
  return Object.freeze(Object.fromEntries([...summaries].map(([owner, value]) => [
    owner,
    Object.freeze({
      ...value,
      damage: clean(value.damage),
      damagePerSecond: clean(value.damage / duration),
      damageEventsPerSecond: clean(value.damageEvents / duration),
      firstDamageSeconds: value.firstDamageMs === null
        ? null
        : clean((value.firstDamageMs - startMs) / 1000),
      lastDamageSeconds: value.lastDamageMs === null
        ? null
        : clean((value.lastDamageMs - startMs) / 1000),
      firstDeathSeconds: value.firstDeathMs === null
        ? null
        : clean((value.firstDeathMs - startMs) / 1000),
      lastDeathSeconds: value.lastDeathMs === null
        ? null
        : clean((value.lastDeathMs - startMs) / 1000),
    }),
  ])));
}


function summarizePursuitRouting(events) {
  const counts = {};
  for (const event of events) {
    if (!event.type.startsWith("pursuit-route-")) continue;
    const key = event.reason ? `${event.type}:${event.reason}` : event.type;
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.freeze(counts);
}


function simulationOutcome(finalWorld, selectedRow) {
  const live = finalWorld.units.filter(({ alive }) => alive);
  const winnerOwner = new Set(live.map(({ owner }) => owner)).size === 1
    ? live[0]?.owner ?? null
    : null;
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    winnerOwner,
    winnerHp,
    winnerHpPercent: winnerOwner === null
      ? null
      : 100 * winnerHp / selectedRow.runs[0].starting_hp_by_owner[winnerOwner],
    survivors: live.length,
    ticks: finalWorld.tick,
    combatDurationSeconds: finalWorld.tick / TICKS_PER_SECOND,
  });
}


function ratio(numerator, denominator) {
  return denominator ? clean(numerator / denominator) : 0;
}


function clean(value) {
  return Math.round(value * 1e9) / 1e9;
}
