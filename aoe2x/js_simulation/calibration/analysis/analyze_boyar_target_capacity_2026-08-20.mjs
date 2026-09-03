import { createWorld, stepWorld } from "../../src/combat/world.js";
import {
  hasDirectMeleeApproach,
  meleeContactCapacity,
  openingMeleeContactCapacity,
} from "../../src/combat/targeting.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../", import.meta.url);
const truth = await loadPhase2Batch1Truth(ROOT);
const rowId = process.argv[2] ?? "elite_boyar_vs_arbalester";
const row = truth.rows.find(({ id }) => id === rowId);
if (!row) throw new RangeError(`unknown row: ${rowId}`);
const context = await loadPhase2Batch1Context(ROOT, truth);
const maxTicks = Number(process.argv[3] ?? PHASE2_MAX_TICKS);
if (!Number.isSafeInteger(maxTicks) || maxTicks < 1) throw new RangeError("invalid max ticks");
let world = createWorld(scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: 0,
  seed: 20260817,
  context,
}));
const boyarIds = new Set(world.units
  .filter(({ owner }) => owner === 3)
  .map(({ referenceId }) => referenceId));
const switchesByActor = new Map([...boyarIds].map((id) => [id, 0]));
const firstPursuitByActor = new Map();
const windows = [];
const capacityAssignments = [];
const priorCapacityTargetByActor = new Map();
const pursuitLoadsAtAcquisitionTicks = [];
const pendingOpeningStates = [];
let currentWindow = { startTick: 1, acquisitions: 0, damageEvents: 0 };
let lastDamageTick = null;

for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
  const pending = world.units.filter((unit) => (
    boyarIds.has(unit.referenceId)
    && (unit.pursuitTargetId === null || unit.pursuitTargetId === undefined)
    && unit.actionTimers.acquire <= 1
  ));
  if ([37, 41, 54, 80, 82, 84, 86, 114, 136, 155].includes(world.tick + 1)
      && pending.length > 0) {
    const loads = new Map();
    for (const actor of world.units.filter(({ referenceId }) => boyarIds.has(referenceId))) {
      if (actor.pursuitTargetId === null || actor.pursuitTargetId === undefined) continue;
      loads.set(actor.pursuitTargetId, (loads.get(actor.pursuitTargetId) ?? 0) + 1);
    }
    pendingOpeningStates.push({
      beforeTick: world.tick + 1,
      pending: pending.map((actor) => ({
        actorId: actor.referenceId,
        pursuitTargetId: actor.pursuitTargetId,
        acquire: actor.actionTimers.acquire,
        zeroRange: actor.mechanics.ranged == null && actor.mechanics.attack_range_tiles === 0,
      })),
      loads: Object.fromEntries(loads),
    });
  }
  world = stepWorld(world);
  const acquisitionsThisTick = world.events.filter((event) => (
    event.type === "pursuit-acquired" && boyarIds.has(event.actorId)
  ));
  if (acquisitionsThisTick.length > 0) {
    const loads = new Map();
    for (const actor of world.units.filter(({ referenceId }) => boyarIds.has(referenceId))) {
      if (actor.pursuitTargetId === null || actor.pursuitTargetId === undefined) continue;
      loads.set(actor.pursuitTargetId, (loads.get(actor.pursuitTargetId) ?? 0) + 1);
    }
    const capacities = {};
    const exemplar = world.units.find(({ referenceId }) => boyarIds.has(referenceId));
    for (const targetId of loads.keys()) {
      const target = world.units.find(({ referenceId }) => referenceId === targetId);
      if (target?.alive) capacities[targetId] = openingMeleeContactCapacity(
        exemplar,
        target,
        world.units,
      );
    }
    pursuitLoadsAtAcquisitionTicks.push({
      tick: world.tick,
      acquired: acquisitionsThisTick.map(({ actorId, targetId }) => ({ actorId, targetId })),
      loads: Object.fromEntries(loads),
      capacities,
    });
  }
  for (const actor of world.units.filter(({ referenceId }) => boyarIds.has(referenceId))) {
    const prior = priorCapacityTargetByActor.get(actor.referenceId);
    if (actor.meleeCapacityTargetId !== undefined
        && actor.meleeCapacityTargetId !== prior) {
      const target = world.units.find(({ referenceId }) => (
        referenceId === actor.meleeCapacityTargetId
      ));
      if (target?.alive) capacityAssignments.push({
        tick: world.tick,
        actorId: actor.referenceId,
        targetId: target.referenceId,
        actorAction: actor.action,
        targetAction: target.action,
        capacity: meleeContactCapacity(actor, target, world.units),
        direct: hasDirectMeleeApproach(actor, target, world.units),
      });
    }
    priorCapacityTargetByActor.set(actor.referenceId, actor.meleeCapacityTargetId);
  }
  for (const event of world.events) {
    if (event.type === "pursuit-acquired" && boyarIds.has(event.actorId)) {
      switchesByActor.set(event.actorId, switchesByActor.get(event.actorId) + 1);
      if (!firstPursuitByActor.has(event.actorId)) {
        firstPursuitByActor.set(event.actorId, {
          tick: world.tick,
          targetId: event.targetId,
        });
      }
      currentWindow.acquisitions += 1;
    }
    if (event.type === "damage") {
      currentWindow.damageEvents += 1;
      lastDamageTick = world.tick;
    }
  }
  if (world.tick % 600 === 0) {
    windows.push({ ...currentWindow, endTick: world.tick });
    currentWindow = { startTick: world.tick + 1, acquisitions: 0, damageEvents: 0 };
  }
  if (new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner)).size <= 1) {
    break;
  }
  world = Object.freeze({ ...world, snapshots: Object.freeze([]), eventLog: Object.freeze([]) });
}
if (currentWindow.startTick <= world.tick) windows.push({ ...currentWindow, endTick: world.tick });

const aliveByOwner = new Map();
for (const unit of world.units.filter(({ alive }) => alive)) {
  if (!aliveByOwner.has(unit.owner)) aliveByOwner.set(unit.owner, { units: 0, hp: 0 });
  const summary = aliveByOwner.get(unit.owner);
  summary.units += 1;
  summary.hp += unit.hp;
}
process.stdout.write(`${JSON.stringify({
  ticks: world.tick,
  lastDamageTick,
  live: Object.fromEntries(aliveByOwner),
  boyarTargetAcquisitions: Object.fromEntries(switchesByActor),
  totalBoyarTargetAcquisitions: [...switchesByActor.values()]
    .reduce((sum, count) => sum + count, 0),
  firstPursuitByActor: Object.fromEntries(firstPursuitByActor),
  initialAssignmentsByTarget: Object.fromEntries([...firstPursuitByActor.values()]
    .reduce((counts, { targetId }) => {
      counts.set(targetId, (counts.get(targetId) ?? 0) + 1);
      return counts;
    }, new Map())),
  capacityAssignments,
  pursuitLoadsAtAcquisitionTicks,
  pendingOpeningStates,
  windows,
}, null, 2)}\n`);
