import { mkdir, writeFile } from "node:fs/promises";

import { createWorld, stepWorld } from "../../src/combat/world.js";
import { isWithinReach } from "../../src/combat/targeting.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../", import.meta.url);
const ROW_ID = "elite_boyar_vs_arbalester";
const SAMPLE_INDEX = 0;
const SEED = 20260817;
const TICKS_PER_SECOND = 60;
const SUSTAINED_TICKS = 30;
const EARLY_TICKS = 12 * TICKS_PER_SECOND;
const OUTPUT = new URL("boyar_arbalester_2026-08-20/stalls.json", import.meta.url);


const truth = await loadPhase2Batch1Truth(ROOT);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row) throw new Error(`missing Phase 2 row: ${ROW_ID}`);
const context = await loadPhase2Batch1Context(ROOT, truth);
const scenario = scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: SAMPLE_INDEX,
  seed: SEED,
  context,
});
let world = createWorld(scenario);
const boyarIds = world.units.filter(({ owner }) => owner === 3)
  .map(({ referenceId }) => referenceId)
  .sort((left, right) => left - right);
const observations = new Map(boyarIds.map((id) => [id, []]));
const eventSummary = new Map(boyarIds.map((id) => [id, {
  attackStarts: 0,
  attackCancels: 0,
  damageEvents: 0,
  damage: 0,
  damageTicks: [],
  firstAliveTick: 0,
  lastAliveTick: 0,
}]));
const earlyDamage = [];

for (let elapsed = 0; elapsed < PHASE2_MAX_TICKS; elapsed += 1) {
  const before = new Map(world.units.map((unit) => [unit.referenceId, unit]));
  const next = stepWorld(world);
  const after = new Map(next.units.map((unit) => [unit.referenceId, unit]));
  const eventsByActor = groupEvents(next.events ?? []);

  for (const id of boyarIds) {
    const unit = after.get(id);
    const previous = before.get(id);
    const summary = eventSummary.get(id);
    const events = eventsByActor.get(id) ?? [];
    for (const event of events) {
      if (event.type === "attack-start") summary.attackStarts += 1;
      if (event.type === "attack-canceled") summary.attackCancels += 1;
      if (event.type !== "damage") continue;
      summary.damageEvents += 1;
      summary.damage += event.amount;
      summary.damageTicks.push(next.tick);
      if (next.tick <= EARLY_TICKS) earlyDamage.push(event);
    }
    if (!unit?.alive || unit.hp <= 0) continue;
    summary.lastAliveTick = next.tick;
    const movedDistance = previous
      ? Math.hypot(unit.x - previous.x, unit.y - previous.y)
      : 0;
    const targetId = firstTargetId(unit);
    const target = targetId === null ? null : after.get(targetId);
    const liveTarget = target?.alive && target.hp > 0 && target.owner !== unit.owner
      ? target
      : null;
    const nearestEnemy = nearestLiveEnemy(unit, next.units);
    const attacking = unit.action === "attacking";
    const dealtDamage = events.some(({ type }) => type === "damage");
    const attackStarted = events.some(({ type }) => type === "attack-start");
    const expectedStep = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
    const lowProgressThreshold = expectedStep * 0.1;
    observations.get(id).push(Object.freeze({
      tick: next.tick,
      x: unit.x,
      y: unit.y,
      movedDistance,
      exactStationary: movedDistance <= 1e-9,
      lowProgress: movedDistance < lowProgressThreshold,
      action: unit.action,
      attacking,
      dealtDamage,
      attackStarted,
      targetId,
      hasLiveTarget: liveTarget !== null,
      targetInReach: liveTarget ? isWithinReach(unit, liveTarget) : false,
      targetDistance: liveTarget ? centerDistance(unit, liveTarget) : null,
      nearestEnemyDistance: nearestEnemy ? centerDistance(unit, nearestEnemy) : null,
      moveOrder: unit.moveOrder ?? null,
      pursuitRoute: unit.pursuitRoute ?? null,
    }));
  }

  world = next;
  if (liveOwnerCount(world.units) <= 1) break;
  world = Object.freeze({ ...world, snapshots: Object.freeze([]), eventLog: Object.freeze([]) });
}

const unitReports = boyarIds.map((id) => analyzeBoyar(
  id,
  observations.get(id),
  eventSummary.get(id),
  world.tick,
));
const sustainedHardStalls = unitReports.flatMap(({ id, hardStalls }) => (
  hardStalls.map((window) => ({ id, ...window }))
)).sort((left, right) => right.durationSeconds - left.durationSeconds);
const sustainedLowProgress = unitReports.flatMap(({ id, lowProgressStalls }) => (
  lowProgressStalls.map((window) => ({ id, ...window }))
)).sort((left, right) => right.durationSeconds - left.durationSeconds);
const sustainedUntargeted = unitReports.flatMap(({ id, untargetedStalls }) => (
  untargetedStalls.map((window) => ({ id, ...window }))
)).sort((left, right) => right.durationSeconds - left.durationSeconds);

const report = Object.freeze({
  schemaVersion: 1,
  rowId: ROW_ID,
  sampleIndex: SAMPLE_INDEX,
  seed: SEED,
  ticks: world.tick,
  durationSeconds: world.tick / TICKS_PER_SECOND,
  definitions: Object.freeze({
    hardStall: "alive, exact zero displacement, not attacking, no damage, live target outside attack reach",
    lowProgressStall: "same, but displacement below 10% of sourced per-tick movement speed",
    untargetedStall: "alive, exact zero displacement, not attacking, no damage, no live captured target while an enemy remains",
    sustainedMinimumSeconds: SUSTAINED_TICKS / TICKS_PER_SECOND,
  }),
  summary: Object.freeze({
    boyars: boyarIds.length,
    boyarsDealingDamage: unitReports.filter(({ damageEvents }) => damageEvents > 0).length,
    boyarsNeverDealingDamage: unitReports.filter(({ damageEvents }) => damageEvents === 0)
      .map(({ id }) => id),
    boyarsWithSustainedHardStall: uniqueIds(sustainedHardStalls),
    boyarsWithSustainedLowProgressStall: uniqueIds(sustainedLowProgress),
    boyarsWithSustainedUntargetedStall: uniqueIds(sustainedUntargeted),
    sustainedHardStallWindows: sustainedHardStalls.length,
    sustainedLowProgressWindows: sustainedLowProgress.length,
    sustainedUntargetedWindows: sustainedUntargeted.length,
  }),
  longestHardStalls: Object.freeze(sustainedHardStalls.slice(0, 20)),
  longestLowProgressStalls: Object.freeze(sustainedLowProgress.slice(0, 20)),
  longestUntargetedStalls: Object.freeze(sustainedUntargeted.slice(0, 20)),
  earlyDamage: summarizeEarlyDamage(earlyDamage),
  units: Object.freeze(unitReports),
});

await mkdir(new URL("boyar_arbalester_2026-08-20/", import.meta.url), { recursive: true });
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({
  summary: report.summary,
  longestHardStalls: report.longestHardStalls,
  longestLowProgressStalls: report.longestLowProgressStalls,
  longestUntargetedStalls: report.longestUntargetedStalls,
  earlyDamage: report.earlyDamage,
}, null, 2)}\n`);


function groupEvents(events) {
  const grouped = new Map();
  for (const event of events) {
    if (!Number.isSafeInteger(event.actorId)) continue;
    if (!grouped.has(event.actorId)) grouped.set(event.actorId, []);
    grouped.get(event.actorId).push(event);
  }
  return grouped;
}


function firstTargetId(unit) {
  for (const candidate of [unit.attackTargetId, unit.engagedTargetId, unit.pursuitTargetId]) {
    if (Number.isSafeInteger(candidate)) return candidate;
  }
  return null;
}


function nearestLiveEnemy(unit, units) {
  let nearest = null;
  let distance = Infinity;
  for (const candidate of units) {
    if (!candidate.alive || candidate.hp <= 0 || candidate.owner === unit.owner) continue;
    const candidateDistance = centerDistance(unit, candidate);
    if (candidateDistance < distance) {
      nearest = candidate;
      distance = candidateDistance;
    }
  }
  return nearest;
}


function centerDistance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}


function liveOwnerCount(units) {
  return new Set(units.filter(({ alive }) => alive).map(({ owner }) => owner)).size;
}


function analyzeBoyar(id, samples, events, terminalTick) {
  const hardStalls = findWindows(samples, (sample) => (
    sample.exactStationary
      && !sample.attacking
      && !sample.dealtDamage
      && sample.hasLiveTarget
      && !sample.targetInReach
  ));
  const lowProgressStalls = findWindows(samples, (sample) => (
    sample.lowProgress
      && !sample.attacking
      && !sample.dealtDamage
      && sample.hasLiveTarget
      && !sample.targetInReach
  ));
  const untargetedStalls = findWindows(samples, (sample) => (
    sample.exactStationary
      && !sample.attacking
      && !sample.dealtDamage
      && !sample.hasLiveTarget
      && Number.isFinite(sample.nearestEnemyDistance)
  ));
  return Object.freeze({
    id,
    aliveTicks: events.lastAliveTick - events.firstAliveTick,
    attackStarts: events.attackStarts,
    attackCancels: events.attackCancels,
    damageEvents: events.damageEvents,
    damage: events.damage,
    firstDamageSeconds: events.damageTicks.length
      ? events.damageTicks[0] / TICKS_PER_SECOND
      : null,
    lastDamageSeconds: events.damageTicks.length
      ? events.damageTicks.at(-1) / TICKS_PER_SECOND
      : null,
    longestDamageGapSeconds: longestGap(
      [events.firstAliveTick, ...events.damageTicks, Math.min(events.lastAliveTick, terminalTick)],
    ) / TICKS_PER_SECOND,
    hardStalls: Object.freeze(hardStalls),
    lowProgressStalls: Object.freeze(lowProgressStalls),
    untargetedStalls: Object.freeze(untargetedStalls),
  });
}


function findWindows(samples, predicate) {
  const windows = [];
  let start = null;
  let previous = null;
  for (const sample of samples) {
    if (predicate(sample)) {
      if (start === null) start = sample;
      previous = sample;
      continue;
    }
    finishWindow(windows, start, previous);
    start = null;
    previous = null;
  }
  finishWindow(windows, start, previous);
  return windows.filter(({ ticks }) => ticks >= SUSTAINED_TICKS);
}


function finishWindow(windows, start, end) {
  if (!start || !end) return;
  const ticks = end.tick - start.tick + 1;
  windows.push(Object.freeze({
    startTick: start.tick,
    endTick: end.tick,
    ticks,
    startSeconds: clean(start.tick / TICKS_PER_SECOND),
    endSeconds: clean(end.tick / TICKS_PER_SECOND),
    durationSeconds: clean(ticks / TICKS_PER_SECOND),
    startPosition: Object.freeze({ x: clean(start.x), y: clean(start.y) }),
    endPosition: Object.freeze({ x: clean(end.x), y: clean(end.y) }),
    actionAtStart: start.action,
    actionAtEnd: end.action,
    targetIdAtStart: start.targetId,
    targetIdAtEnd: end.targetId,
    targetDistanceAtStart: clean(start.targetDistance),
    targetDistanceAtEnd: clean(end.targetDistance),
    nearestEnemyDistanceAtStart: clean(start.nearestEnemyDistance),
    nearestEnemyDistanceAtEnd: clean(end.nearestEnemyDistance),
    moveOrderAtStart: start.moveOrder,
    pursuitRouteAtStart: start.pursuitRoute,
  }));
}


function longestGap(ticks) {
  if (ticks.length < 2) return 0;
  let maximum = 0;
  for (let index = 1; index < ticks.length; index += 1) {
    maximum = Math.max(maximum, ticks[index] - ticks[index - 1]);
  }
  return maximum;
}


function uniqueIds(windows) {
  return Object.freeze([...new Set(windows.map(({ id }) => id))].sort((left, right) => left - right));
}


function summarizeEarlyDamage(events) {
  const byTarget = new Map();
  for (const event of events) {
    if (!byTarget.has(event.targetId)) byTarget.set(event.targetId, {
      targetId: event.targetId,
      damageEvents: 0,
      damage: 0,
      actors: new Set(),
      firstTick: event.tick,
      lastTick: event.tick,
    });
    const summary = byTarget.get(event.targetId);
    summary.damageEvents += 1;
    summary.damage += event.amount;
    summary.actors.add(event.actorId);
    summary.firstTick = Math.min(summary.firstTick, event.tick);
    summary.lastTick = Math.max(summary.lastTick, event.tick);
  }
  return Object.freeze({
    throughSeconds: EARLY_TICKS / TICKS_PER_SECOND,
    totalDamageEvents: events.length,
    uniqueTargetsDamaged: byTarget.size,
    targets: Object.freeze([...byTarget.values()]
      .map((summary) => Object.freeze({
        targetId: summary.targetId,
        damageEvents: summary.damageEvents,
        damage: summary.damage,
        uniqueBoyars: summary.actors.size,
        boyarIds: Object.freeze([...summary.actors].sort((left, right) => left - right)),
        firstDamageSeconds: clean(summary.firstTick / TICKS_PER_SECOND),
        lastDamageSeconds: clean(summary.lastTick / TICKS_PER_SECOND),
      }))
      .sort((left, right) => right.damage - left.damage)),
  });
}


function clean(value) {
  return Number.isFinite(value) ? Math.round(value * 1e9) / 1e9 : null;
}
