import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

import { createChampionScenario } from "../../src/champion-scenarios.js";
import { createWorld, runWorld } from "../../src/combat/world.js";
import { validateFormationFixture } from "../../src/formation-model.js";
import { TICKS_PER_SECOND } from "../../src/simulation-clock.js";


const formationUrl = new URL("../../fixtures/golden_formation_21v21.json", import.meta.url);
const truthUrl = new URL("../../calibration/fixtures/champion_basics.json", import.meta.url);
const mechanicsUrl = new URL("../../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url);

const [formationData, truth, mechanics] = await Promise.all([
  readFile(formationUrl, "utf8").then(JSON.parse),
  readFile(truthUrl, "utf8").then(JSON.parse),
  readFile(mechanicsUrl, "utf8").then(JSON.parse),
]);
const formation = validateFormationFixture(formationData);


function hashJson(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}


function round(value) {
  return Number(value.toFixed(6));
}


function difference(left, right) {
  return Number.isFinite(left) && Number.isFinite(right) ? round(left - right) : null;
}


function movementDirection(dx, dy) {
  return { x: Math.sign(dx), y: Math.sign(dy) };
}


function simulationTrace(result, damageEvents) {
  const starts = result.snapshots[0].units.map((unit) => ({
    id: unit.referenceId,
    owner: unit.owner,
    master: unit.unitMaster,
    x: unit.x,
    y: unit.y,
  }));
  const firstMoves = starts.map(({ id }) => {
    const move = result.events.find((event) => event.type === "move" && event.actorId === id);
    if (!move) return { id, tick: null, seconds: null, x: null, y: null, dx: null, dy: null };
    const unit = result.snapshots[move.tick].units.find(({ referenceId }) => referenceId === id);
    return {
      id,
      tick: move.tick,
      seconds: round(move.tick / TICKS_PER_SECOND),
      x: unit.x,
      y: unit.y,
      dx: move.dx,
      dy: move.dy,
    };
  });
  const movementDirections = firstMoves.map(({ id, dx, dy }) => ({
    id,
    ...(Number.isFinite(dx) && Number.isFinite(dy)
      ? movementDirection(dx, dy)
      : { x: null, y: null }),
  }));

  const contactEvent = result.events.find(({ type }) => type === "contact");
  let surfaceContact = null;
  if (contactEvent) {
    const snapshot = result.snapshots[contactEvent.tick];
    const actor = snapshot.units.find(({ referenceId }) => referenceId === contactEvent.actorId);
    const target = snapshot.units.find(({ referenceId }) => referenceId === contactEvent.targetId);
    const centerDistance = Math.hypot(target.x - actor.x, target.y - actor.y);
    surfaceContact = {
      tick: contactEvent.tick,
      seconds: round(contactEvent.tick / TICKS_PER_SECOND),
      pair: [contactEvent.actorId, contactEvent.targetId].sort((left, right) => left - right),
      centerDistance,
      surfaceGap: centerDistance
        - actor.mechanics.collision_size_tiles.x
        - target.mechanics.collision_size_tiles.x,
    };
  }

  const firstDamageEvent = damageEvents[0];
  const firstDamage = firstDamageEvent ? {
    tick: firstDamageEvent.tick,
    seconds: round(firstDamageEvent.tick / TICKS_PER_SECOND),
    actorId: firstDamageEvent.actorId,
    targetId: firstDamageEvent.targetId,
    amount: firstDamageEvent.amount,
    hpAfter: firstDamageEvent.hpAfter,
  } : null;
  const attackerIds = [...new Set(damageEvents.map(({ actorId }) => actorId))]
    .sort((left, right) => left - right);
  const sameAttackerIntervals = attackerIds.map((id) => {
    const ticks = damageEvents
      .filter(({ actorId }) => actorId === id)
      .map(({ tick }) => tick);
    return {
      id,
      ticks: ticks.slice(1).map((tick, index) => tick - ticks[index]),
      seconds: ticks.slice(1).map((tick, index) => round(
        (tick - ticks[index]) / TICKS_PER_SECOND,
      )),
    };
  });
  const killEvent = damageEvents.find(({ hpAfter }) => hpAfter === 0);
  const kill = killEvent ? {
    tick: killEvent.tick,
    seconds: round(killEvent.tick / TICKS_PER_SECOND),
    actorId: killEvent.actorId,
    targetId: killEvent.targetId,
  } : null;
  const ownerById = new Map(starts.map(({ id, owner }) => [id, owner]));
  const hitsPerOwner = {};
  for (const event of damageEvents) {
    const owner = ownerById.get(event.actorId);
    hitsPerOwner[owner] = (hitsPerOwner[owner] ?? 0) + 1;
  }
  return {
    starts,
    firstMoves,
    movementDirections,
    surfaceContact,
    firstDamage,
    sameAttackerIntervals,
    kill,
    hitsPerOwner,
    winnerHp: result.world.units
      .filter(({ owner, alive }) => owner === result.winner && alive)
      .reduce((total, unit) => total + unit.hp, 0),
  };
}


function tapeElapsedSeconds(run, timestamp) {
  return round(timestamp - (run.metadata?.fight_t_start ?? 0));
}


function tapeSurfaceContact(run) {
  const firstDamageTime = run.damage_events[0]?.t ?? Number.POSITIVE_INFINITY;
  const state = new Map(run.starting_units.map((unit) => [unit.id, unit]));
  const samplesByTime = new Map();
  for (const sample of run.unit_samples) {
    if (sample.t > firstDamageTime) break;
    if (!samplesByTime.has(sample.t)) samplesByTime.set(sample.t, []);
    samplesByTime.get(sample.t).push(sample);
  }

  let closest = null;
  const radius = mechanics.collision_size_tiles.x;
  for (const [timestamp, samples] of samplesByTime) {
    for (const sample of samples) state.set(sample.id, sample);
    const units = [...state.values()].sort((left, right) => left.id - right.id);
    for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
        const left = units[leftIndex];
        const right = units[rightIndex];
        if (left.owner === right.owner) continue;
        const centerDistance = Math.hypot(right.x - left.x, right.y - left.y);
        if (closest && centerDistance >= closest.centerDistance - 1e-12) continue;
        closest = {
          t: timestamp,
          elapsedSeconds: tapeElapsedSeconds(run, timestamp),
          pair: [left.id, right.id],
          centerDistance,
          surfaceGap: centerDistance - radius * 2,
        };
      }
    }
  }
  return closest;
}


function tapeTrace(run) {
  const starts = run.starting_units.map(({ id, owner, master, x, y }) => ({
    id, owner, master, x, y,
  }));
  const firstMoves = starts.map((start) => {
    const sample = run.unit_samples.find((row) => (
      row.id === start.id && (row.x !== start.x || row.y !== start.y)
    ));
    if (!sample) {
      return {
        id: start.id,
        t: null,
        elapsedSeconds: null,
        x: null,
        y: null,
        dx: null,
        dy: null,
      };
    }
    return {
      id: start.id,
      t: sample.t,
      elapsedSeconds: tapeElapsedSeconds(run, sample.t),
      x: sample.x,
      y: sample.y,
      dx: sample.x - start.x,
      dy: sample.y - start.y,
    };
  });
  const movementDirections = firstMoves.map(({ id, dx, dy }) => ({
    id,
    ...(Number.isFinite(dx) && Number.isFinite(dy)
      ? movementDirection(dx, dy)
      : { x: null, y: null }),
  }));
  const firstDamageEvent = run.damage_events[0];
  const firstDamage = firstDamageEvent ? {
    t: firstDamageEvent.t,
    elapsedSeconds: tapeElapsedSeconds(run, firstDamageEvent.t),
    provisionalTick: Math.round(tapeElapsedSeconds(run, firstDamageEvent.t) * TICKS_PER_SECOND),
    actorId: firstDamageEvent.attacker,
    targetId: firstDamageEvent.victim,
    amount: firstDamageEvent.damage,
    hpAfter: firstDamageEvent.victim_hp_after,
  } : null;
  const attackerIds = [...new Set(run.damage_events.map(({ attacker }) => attacker))]
    .sort((left, right) => left - right);
  const sameAttackerIntervals = attackerIds.map((id) => {
    const times = run.damage_events
      .filter(({ attacker }) => attacker === id)
      .map(({ t }) => t);
    return {
      id,
      seconds: times.slice(1).map((timestamp, index) => round(timestamp - times[index])),
    };
  });
  const killEvent = run.damage_events.find(({ kill }) => kill);
  const kill = killEvent ? {
    t: killEvent.t,
    elapsedSeconds: tapeElapsedSeconds(run, killEvent.t),
    provisionalTick: Math.round(tapeElapsedSeconds(run, killEvent.t) * TICKS_PER_SECOND),
    actorId: killEvent.attacker,
    targetId: killEvent.victim,
  } : null;
  const hitsPerOwner = {};
  for (const event of run.damage_events) {
    hitsPerOwner[event.attacker_owner] = (hitsPerOwner[event.attacker_owner] ?? 0) + 1;
  }
  return {
    starts,
    firstMoves,
    movementDirections,
    surfaceContact: tapeSurfaceContact(run),
    firstDamage,
    sameAttackerIntervals,
    kill,
    hitsPerOwner,
    winnerHp: run.aggregate_hp[run.winner].remaining,
  };
}


function compareTrace(simulation, tape) {
  const startsById = new Map(tape.starts.map((row) => [row.id, row]));
  const firstMovesById = new Map(tape.firstMoves.map((row) => [row.id, row]));
  const directionsById = new Map(tape.movementDirections.map((row) => [row.id, row]));
  const intervalsById = new Map(tape.sameAttackerIntervals.map((row) => [row.id, row]));
  return {
    starts: simulation.starts.map((row) => {
      const expected = startsById.get(row.id);
      return {
        id: row.id,
        owner: difference(row.owner, expected?.owner),
        master: difference(row.master, expected?.master),
        x: difference(row.x, expected?.x),
        y: difference(row.y, expected?.y),
      };
    }),
    firstMoves: simulation.firstMoves.map((row) => {
      const expected = firstMovesById.get(row.id);
      return {
        id: row.id,
        seconds: difference(row.seconds, expected?.elapsedSeconds),
        x: difference(row.x, expected?.x),
        y: difference(row.y, expected?.y),
        dx: difference(row.dx, expected?.dx),
        dy: difference(row.dy, expected?.dy),
      };
    }),
    movementDirections: simulation.movementDirections.map((row) => {
      const expected = directionsById.get(row.id);
      return {
        id: row.id,
        xMatches: expected ? row.x === expected.x : null,
        yMatches: expected ? row.y === expected.y : null,
      };
    }),
    surfaceContact: {
      seconds: difference(
        simulation.surfaceContact?.seconds,
        tape.surfaceContact?.elapsedSeconds,
      ),
      ticks: difference(
        simulation.surfaceContact?.tick,
        tape.surfaceContact
          ? Math.round(tape.surfaceContact.elapsedSeconds * TICKS_PER_SECOND)
          : null,
      ),
      centerDistance: difference(
        simulation.surfaceContact?.centerDistance,
        tape.surfaceContact?.centerDistance,
      ),
      surfaceGap: difference(
        simulation.surfaceContact?.surfaceGap,
        tape.surfaceContact?.surfaceGap,
      ),
    },
    firstDamage: {
      seconds: difference(simulation.firstDamage?.seconds, tape.firstDamage?.elapsedSeconds),
      ticks: difference(simulation.firstDamage?.tick, tape.firstDamage?.provisionalTick),
      actorMatches: tape.firstDamage
        ? simulation.firstDamage?.actorId === tape.firstDamage.actorId
        : null,
      targetMatches: tape.firstDamage
        ? simulation.firstDamage?.targetId === tape.firstDamage.targetId
        : null,
      amount: difference(simulation.firstDamage?.amount, tape.firstDamage?.amount),
      hpAfter: difference(simulation.firstDamage?.hpAfter, tape.firstDamage?.hpAfter),
    },
    sameAttackerIntervals: simulation.sameAttackerIntervals.map((row) => {
      const expected = intervalsById.get(row.id)?.seconds ?? [];
      const length = Math.max(row.seconds.length, expected.length);
      return {
        id: row.id,
        seconds: Array.from(
          { length },
          (_, index) => difference(row.seconds[index], expected[index]),
        ),
      };
    }),
    kill: {
      seconds: difference(simulation.kill?.seconds, tape.kill?.elapsedSeconds),
      ticks: difference(simulation.kill?.tick, tape.kill?.provisionalTick),
      actorMatches: tape.kill ? simulation.kill?.actorId === tape.kill.actorId : null,
      targetMatches: tape.kill ? simulation.kill?.targetId === tape.kill.targetId : null,
    },
    hitsPerOwner: Object.fromEntries(
      [...new Set([
        ...Object.keys(simulation.hitsPerOwner),
        ...Object.keys(tape.hitsPerOwner),
      ])].sort().map((owner) => [
        owner,
        (simulation.hitsPerOwner[owner] ?? 0) - (tape.hitsPerOwner[owner] ?? 0),
      ]),
    ),
    winnerHp: difference(simulation.winnerHp, tape.winnerHp),
  };
}


export function runChampionRatio(ratio, { reverseUnits = false } = {}) {
  const scenario = createChampionScenario({ ratio, formation, truth, mechanics });
  const orderedScenario = reverseUnits
    ? { ...scenario, units: [...scenario.units].reverse() }
    : scenario;
  const result = runWorld(createWorld(orderedScenario));
  const livingUnits = result.world.units.filter(({ alive }) => alive);
  const deadUnits = result.world.units.filter(({ alive }) => !alive);
  const damageEvents = Object.freeze(result.events.filter(({ type }) => type === "damage"));
  const trace = simulationTrace(result, damageEvents);
  const tapeComparisons = truth.ratios[ratio].runs.map((run) => {
    const tape = tapeTrace(run);
    return {
      tag: run.tag,
      simulation: trace,
      tape,
      deltas: compareTrace(trace, tape),
    };
  });
  const finalState = {
    tick: result.world.tick,
    ratio: result.world.ratio,
    mapHash: result.world.mapHash,
    units: result.world.units,
  };

  return Object.freeze({
    ...result,
    damageEvents,
    diagnostics: Object.freeze({ tapeComparisons: Object.freeze(tapeComparisons) }),
    eventLogHash: hashJson(result.events),
    finalStateHash: hashJson(finalState),
    livingUnits: Object.freeze(livingUnits),
    winner: livingUnits[0],
    loser: deadUnits[0],
  });
}
