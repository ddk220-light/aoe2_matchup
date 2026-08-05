import { resolveMovementProposals } from "./collision.js";
import { planLocalAvoidance } from "./local-avoidance.js";
import { proposeMovement } from "./movement.js";
import { selectTarget } from "./targeting.js";
import { TICKS_PER_SECOND } from "../simulation-clock.js";
import {
  attackDelayTicks,
  calculateDamage,
  createAttackCanceledEvent,
  createAttackStartEvent,
  createDamageEvent,
  createDeathEvent,
  isInAttackRange,
  orderReadyAttacks,
  reloadTicks,
} from "./attacks.js";


const DEFAULT_MAP = Object.freeze({
  width: 16,
  height: 16,
  obstacles: Object.freeze([]),
});
const MAX_WORLD_TICKS = 3600;


function freezeUnit(unit) {
  return Object.freeze({
    ...unit,
    avoidance: unit.avoidance === null || unit.avoidance === undefined
      ? null
      : Object.freeze({ ...unit.avoidance }),
    actionTimers: Object.freeze({ ...unit.actionTimers }),
  });
}


function immutableClone(value) {
  if (!value || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    return Object.freeze(value.map(immutableClone));
  }
  return Object.freeze(Object.fromEntries(
    Object.entries(value).map(([name, child]) => [name, immutableClone(child)]),
  ));
}


function event(tick, type, actorId, targetId, details = {}) {
  const id = `${tick}:${type}:${actorId}:${targetId ?? "-"}`;
  return Object.freeze({
    id,
    eventId: id,
    type,
    tick,
    actorId,
    targetId,
    ...details,
  });
}


function canonicalUnits(units, { cloneMechanics = false } = {}) {
  if (!Array.isArray(units)) throw new TypeError("scenario units must be an array");
  const references = new Set();
  const result = units.map((unit) => {
    if (!Number.isSafeInteger(unit?.referenceId)) {
      throw new TypeError("unit reference ID must be a safe integer");
    }
    if (references.has(unit.referenceId)) {
      throw new Error(`duplicate unit reference ${unit.referenceId}`);
    }
    references.add(unit.referenceId);
    return freezeUnit({
      ...unit,
      mechanics: cloneMechanics ? immutableClone(unit.mechanics) : unit.mechanics,
    });
  }).sort((a, b) => a.referenceId - b.referenceId);
  return Object.freeze(result);
}


function mutableUnit(unit) {
  return {
    ...unit,
    avoidance: unit.avoidance === null ? null : { ...unit.avoidance },
    actionTimers: { ...unit.actionTimers },
  };
}


function freezeMap(map) {
  return immutableClone({ ...map, obstacles: [...(map.obstacles ?? [])] });
}


function createSnapshot(tick, units, events) {
  return Object.freeze({ tick, units, events });
}


export function createWorld(scenario) {
  if (!scenario || typeof scenario !== "object") {
    throw new TypeError("scenario is required");
  }
  const units = canonicalUnits(scenario.units, { cloneMechanics: true });
  const events = Object.freeze([]);
  const snapshot = createSnapshot(0, units, events);
  return Object.freeze({
    tick: 0,
    ratio: scenario.ratio,
    mapHash: scenario.mapHash,
    map: scenario.map ? freezeMap(scenario.map) : DEFAULT_MAP,
    units,
    events,
    eventLog: events,
    snapshots: Object.freeze([snapshot]),
  });
}


function validateTargets(units, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (!unit.alive) {
      unit.targetId = null;
      unit.avoidance = null;
      unit.action = "dead";
      unit.actionTimers = { windup: 0, reload: 0 };
      continue;
    }
    if (unit.targetId === null || unit.targetId === undefined) continue;
    const target = byReference.get(unit.targetId);
    if (target?.alive && target.owner !== unit.owner) continue;

    const invalidTargetId = unit.targetId;
    events.push(event(
      tick,
      "target-invalidated",
      unit.referenceId,
      invalidTargetId,
      { reason: target?.alive ? "friendly-target" : "target-dead" },
    ));
    if (unit.action === "attacking") {
      events.push(createAttackCanceledEvent({
        tick,
        actorId: unit.referenceId,
        targetId: invalidTargetId,
        readyTick: tick + Math.max(0, unit.actionTimers.windup - 1),
        reason: "target-invalidated",
      }));
    }
    unit.targetId = null;
    unit.avoidance = null;
    unit.actionTimers.windup = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
  }
}


function acquireTargets(units, tick, events) {
  const snapshot = Object.freeze(units.map(freezeUnit));
  for (const unit of units) {
    if (!unit.alive || unit.targetId !== null) continue;
    const candidate = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    const target = selectTarget(candidate, snapshot);
    if (target === null) continue;
    events.push(event(tick, "target-acquired", unit.referenceId, target.referenceId));
    unit.targetId = target.referenceId;
  }
}


function moveUnits(units, map, tick, events) {
  const live = units.filter(({ alive }) => alive).map(freezeUnit);
  const byReference = new Map(live.map((unit) => [unit.referenceId, unit]));
  const proposals = live.map((unit) => {
    const target = byReference.get(unit.targetId);
    return target && unit.action !== "attacking" && !isInAttackRange(unit, target)
      ? proposeMovement(unit, target, TICKS_PER_SECOND)
      : Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
  });
  const planned = planLocalAvoidance(live, proposals);
  const moved = resolveMovementProposals(planned.units, planned.proposals, map);
  const movedByReference = new Map(moved.map((unit) => [unit.referenceId, unit]));
  const proposalByReference = new Map(proposals.map((proposal) => [proposal.referenceId, proposal]));
  const moveEvents = [];
  const blockedEvents = [];
  for (const unit of units) {
    const before = byReference.get(unit.referenceId);
    if (!before) continue;
    const result = movedByReference.get(unit.referenceId);
    const dx = result.x - before.x;
    const dy = result.y - before.y;
    unit.x = result.x;
    unit.y = result.y;
    unit.avoidance = result.avoidance;
    if (dx !== 0 || dy !== 0) {
      unit.facing = Math.atan2(dy, dx);
      moveEvents.push(event(tick, "move", unit.referenceId, unit.targetId, { dx, dy }));
    }
    const proposal = proposalByReference.get(unit.referenceId);
    if (Math.abs(dx - proposal.dx) > 1e-12 || Math.abs(dy - proposal.dy) > 1e-12) {
      blockedEvents.push(event(tick, "blocked", unit.referenceId, unit.targetId, {
        proposedDx: proposal.dx,
        proposedDy: proposal.dy,
        actualDx: dx,
        actualDy: dy,
      }));
    }
  }
  events.push(...moveEvents, ...blockedEvents);

  const currentByReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (!unit.alive || unit.targetId === null) continue;
    const target = currentByReference.get(unit.targetId);
    if (!target?.alive || !isInAttackRange(unit, target)) continue;
    if (unit.action === "idle" || unit.action === "moving") {
      events.push(event(tick, "contact", unit.referenceId, target.referenceId));
    }
  }
}


function progressAttacks(units, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const ready = [];
  for (const unit of units) {
    if (!unit.alive) continue;
    const target = byReference.get(unit.targetId);
    if (unit.action === "attacking") {
      if (unit.actionTimers.windup > 0) unit.actionTimers.windup -= 1;
      if (unit.actionTimers.windup === 0) {
        ready.push({
          type: "attack-ready",
          readyTick: tick,
          actorId: unit.referenceId,
          targetId: unit.targetId,
          amount: target ? calculateDamage(unit, target) : 0,
        });
      }
      continue;
    }

    if (unit.actionTimers.reload > 0) {
      unit.actionTimers.reload -= 1;
      unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
    }
    if (
      unit.actionTimers.reload !== 0 ||
      !target?.alive ||
      target.owner === unit.owner ||
      !isInAttackRange(unit, target)
    ) continue;

    const delay = attackDelayTicks(unit.mechanics);
    const readyTick = tick + delay;
    events.push(createAttackStartEvent({
      tick,
      actorId: unit.referenceId,
      targetId: target.referenceId,
      readyTick,
    }));
    unit.action = "attacking";
    unit.actionTimers.windup = delay;
    if (delay === 0) {
      ready.push({
        type: "attack-ready",
        readyTick,
        actorId: unit.referenceId,
        targetId: target.referenceId,
        amount: calculateDamage(unit, target),
      });
    }
  }
  return ready;
}


function commitReadyAttacks(units, ready, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const attack of orderReadyAttacks(ready)) {
    const actor = byReference.get(attack.actorId);
    const target = byReference.get(attack.targetId);
    if (!actor?.alive) {
      events.push(createAttackCanceledEvent({
        tick,
        actorId: attack.actorId,
        targetId: attack.targetId,
        readyTick: attack.readyTick,
        reason: "actor-dead",
      }));
      continue;
    }
    if (!target?.alive || target.owner === actor.owner || actor.targetId !== target.referenceId) {
      actor.action = actor.actionTimers.reload > 0 ? "reload" : "idle";
      actor.actionTimers.windup = 0;
      events.push(createAttackCanceledEvent({
        tick,
        actorId: attack.actorId,
        targetId: attack.targetId,
        readyTick: attack.readyTick,
        reason: !target?.alive ? "target-dead" : "target-invalidated",
      }));
      continue;
    }

    const hpBefore = target.hp;
    const hpAfter = Math.max(0, hpBefore - attack.amount);
    target.hp = hpAfter;
    actor.action = "reload";
    actor.actionTimers = { windup: 0, reload: reloadTicks(actor.mechanics) };
    events.push(createDamageEvent({
      tick,
      actorId: attack.actorId,
      targetId: attack.targetId,
      readyTick: attack.readyTick,
      amount: attack.amount,
      hpBefore,
      hpAfter,
    }));
    if (hpAfter > 0) continue;

    target.alive = false;
    target.targetId = null;
    target.avoidance = null;
    target.action = "dead";
    target.actionTimers = { windup: 0, reload: 0 };
    events.push(createDeathEvent({
      tick,
      actorId: attack.actorId,
      targetId: attack.targetId,
      readyTick: attack.readyTick,
    }));
  }
}


export function stepWorld(world) {
  if (!world || typeof world !== "object") throw new TypeError("world is required");
  const tick = world.tick + 1;
  const events = [];

  const snapshot = Object.freeze([...world.units]);
  const units = snapshot.map(mutableUnit);
  validateTargets(units, tick, events);
  acquireTargets(units, tick, events);
  moveUnits(units, world.map, tick, events);
  const ready = progressAttacks(units, tick, events);
  commitReadyAttacks(units, ready, tick, events);

  const publishedUnits = canonicalUnits(units);
  const publishedEvents = Object.freeze(events);
  const eventLog = Object.freeze([...world.eventLog, ...publishedEvents]);
  const snapshots = Object.freeze([
    ...world.snapshots,
    createSnapshot(tick, publishedUnits, publishedEvents),
  ]);
  return Object.freeze({
    ...world,
    tick,
    units: publishedUnits,
    events: publishedEvents,
    eventLog,
    snapshots,
  });
}


function outcome(world) {
  const liveOwners = new Set(
    world.units.filter(({ alive }) => alive).map(({ owner }) => owner),
  );
  if (liveOwners.size === 0) {
    throw new Error(`invalid terminal world at tick ${world.tick}: no live owners`);
  }
  if (liveOwners.size > 1) return null;
  const [winner] = liveOwners;
  return Object.freeze({
    outcome: "win",
    winner,
    ticks: world.tick,
    world,
    snapshots: world.snapshots,
    events: world.eventLog,
  });
}


export function runWorld(world, { maxTicks = MAX_WORLD_TICKS } = {}) {
  if (!Number.isSafeInteger(maxTicks) || maxTicks < 0) {
    throw new RangeError("max ticks must be a nonnegative safe integer");
  }
  if (maxTicks > MAX_WORLD_TICKS) {
    throw new RangeError(`max ticks must not exceed ${MAX_WORLD_TICKS}`);
  }
  let current = world;
  const initialOutcome = outcome(current);
  if (initialOutcome !== null) return initialOutcome;
  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
    current = stepWorld(current);
    const result = outcome(current);
    if (result !== null) return result;
  }
  throw new Error(`world exceeded ${maxTicks} ticks`);
}
