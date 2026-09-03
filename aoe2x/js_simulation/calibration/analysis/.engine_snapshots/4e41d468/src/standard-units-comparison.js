// Standard-units benchmark support.  This module is deliberately a consumer
// of the engine: it recreates tape starting rosters and measures outcomes, but
// contains no combat-rule overrides.
import { readFile } from "node:fs/promises";

import { hashCanonicalJson } from "./canonical-json.js";
import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld } from "./combat/world.js";
import { KITE_PROFILES } from "./kite-profiles.js";
import { resolveFamily } from "./placement.js";
import { UNIT_REGISTRY } from "./unit-registry.js";


export const STANDARD_UNITS_MAX_TICKS = 9000;
const unitByMaster = new Map(UNIT_REGISTRY.map((unit) => [unit.master, unit]));
const mechanicsCache = new Map();


export async function loadStandardUnitsTruth(root) {
  return JSON.parse(await readFile(
    new URL("calibration/fixtures/standard_units/standard_units_truth.json", root),
    "utf8",
  ));
}


export function signedScore({ winnerOwner, winnerHp, startingHpByOwner }) {
  if (winnerOwner === null || winnerOwner === undefined) return null;
  if (winnerOwner !== 2 && winnerOwner !== 3) {
    throw new RangeError(`winnerOwner must be 2 or 3, got ${winnerOwner}`);
  }
  const startingHp = startingHpByOwner[winnerOwner] ?? startingHpByOwner[String(winnerOwner)];
  if (!Number.isFinite(winnerHp) || !Number.isFinite(startingHp) || startingHp <= 0) {
    throw new TypeError("winner HP and tape starting HP must be finite positive numbers");
  }
  const magnitude = 100 * winnerHp / startingHp;
  return winnerOwner === 2 ? -magnitude : magnitude;
}


export function summarizeTape(row) {
  const scored = row.runs.filter(({ status, signed_score: score }) => (
    status === "scored" && Number.isFinite(score)
  ));
  if (scored.length === 0) throw new RangeError(`row ${row.id ?? row.matchup} has no scored tape runs`);
  const scores = scored.map(({ signed_score: score }) => score);
  const side3Wins = scores.filter((score) => score > 0).length;
  const side2Wins = scores.filter((score) => score < 0).length;
  return Object.freeze({
    scoredRuns: scored.length,
    timeoutRuns: row.runs.filter(({ status }) => status === "timeout").length,
    mean: mean(scores),
    min: Math.min(...scores),
    max: Math.max(...scores),
    side3WinRate: side3Wins / scored.length,
    volatile: side2Wins > 0 && side3Wins > 0,
  });
}


export function compareRow({ row, tape = summarizeTape(row), simulationScores }) {
  const scores = simulationScores.filter(Number.isFinite);
  const simulationMean = scores.length === 0 ? null : mean(scores);
  const simulationSide3WinRate = scores.length === 0
    ? null
    : scores.filter((score) => score > 0).length / scores.length;
  const simulatedWinner = simulationMean === null || simulationMean === 0
    ? null
    : simulationMean < 0 ? 2 : 3;
  const tapeWinner = tape.volatile ? null : tape.mean < 0 ? 2 : 3;
  return Object.freeze({
    simulationRuns: scores.length,
    unresolvedRuns: simulationScores.length - scores.length,
    mean: simulationMean,
    min: scores.length === 0 ? null : Math.min(...scores),
    max: scores.length === 0 ? null : Math.max(...scores),
    side3WinRate: simulationSide3WinRate,
    side3WinRateError: simulationSide3WinRate === null
      ? null
      : Math.abs(simulationSide3WinRate - tape.side3WinRate),
    bandError: simulationMean === null ? null : bandDistance(simulationMean, tape.min, tape.max),
    tapeBandCoverage: scores.length === 0
      ? 0
      : scores.filter((score) => score >= tape.min && score <= tape.max).length / scores.length,
    wrongStableWinner: tapeWinner !== null && simulatedWinner !== tapeWinner,
  });
}


export async function runTapeConditioned(root, row, sampleIndex, seed, experiment = undefined) {
  if (!Number.isSafeInteger(sampleIndex) || sampleIndex < 0) {
    throw new RangeError(`sampleIndex must be a nonnegative safe integer, got ${sampleIndex}`);
  }
  if (!Number.isSafeInteger(seed)) throw new RangeError(`seed must be a safe integer, got ${seed}`);
  const canonical = row.runs[0];
  if (!canonical?.starting_units?.length) {
    throw new RangeError(`row ${row.id ?? row.matchup} has no canonical starting units`);
  }
  const roster = canonical.starting_units;
  const ranks = acquisitionRanks(roster, sampleIndex, seed, row.id ?? row.matchup ?? "standard-row");
  const mechanics = await mechanicsByMaster(root, roster);
  const units = roster.map((unit) => createUnitState({
    referenceId: unit.id,
    owner: unit.owner,
    x: unit.x,
    y: unit.y,
    facing: 0,
    mechanics: mechanics.get(unit.master),
    acquisitionRank: ranks.get(unit.id),
    acquisitionCount: roster.length,
  }));
  const kite = kiteScenario(row);
  const experimentalKiteProfile = kiteProfileExperiment(kite.kiteProfile, experiment);
  const scenario = {
    ratio: `${row.side2.count}v${row.side3.count}`,
    units,
    ...kite,
    ...(experiment?.chaseCapture === true && Number.isSafeInteger(kite.kiteOwner)
      ? { chaseCapture: true }
      : {}),
    ...(experiment?.kitedEscape === true && Number.isSafeInteger(kite.kiteOwner)
      ? { kitedEscape: true }
      : {}),
    ...(experimentalKiteProfile ? { kiteProfile: experimentalKiteProfile } : {}),
  };

  let result;
  try {
    result = runWorld(createWorld(scenario), {
      maxTicks: STANDARD_UNITS_MAX_TICKS,
      retainSnapshots: false,
    });
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded")) throw error;
    return Object.freeze({
      rowId: row.id,
      matchup: row.matchup,
      sampleIndex,
      seed,
      outcome: "timeout",
      winnerOwner: null,
      winnerHp: null,
      score: null,
      ticks: STANDARD_UNITS_MAX_TICKS,
      finalStateHash: null,
      eventLogHash: null,
      diagnostics: error.world
        ? timeoutDiagnostics(error.world, error.events)
        : Object.freeze({}),
    });
  }

  const live = result.world.units.filter(({ alive }) => alive);
  const winnerOwner = result.winner;
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    rowId: row.id,
    matchup: row.matchup,
    sampleIndex,
    seed,
    outcome: "win",
    winnerOwner,
    winnerHp,
    score: signedScore({
      winnerOwner,
      winnerHp,
      startingHpByOwner: canonical.starting_hp_by_owner,
    }),
    ticks: result.ticks,
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick,
      ratio: scenario.ratio,
      units: result.world.units,
    }),
    eventLogHash: hashCanonicalJson(result.events),
    diagnostics: diagnostics(result.events, result.world.units),
  });
}


function kiteProfileExperiment(profile, experiment) {
  if (!profile || !experiment) return undefined;
  const overrides = {
    ...(experiment.kitedPath === "clearance_grid" ? { kitedPath: "clearance_grid" } : {}),
    ...(experiment.cohortMotion === "contact_heading"
      ? { cohortMotion: "contact_heading" }
      : {}),
    ...(Number.isFinite(experiment.formationSpacingTiles)
        && experiment.formationSpacingTiles > 0
      ? { formationSpacingTiles: experiment.formationSpacingTiles }
      : {}),
    ...(experiment.formationMotion === "translated_offsets"
      ? { formationMotion: "translated_offsets" }
      : {}),
    ...(experiment.openingVolley === "close_to_fire"
      ? { openingVolley: "close_to_fire" }
      : {}),
    ...(experiment.volleyPursuit === "close_to_fire"
      ? { volleyPursuit: "close_to_fire" }
      : {}),
    ...(experiment.meleeWave === "half_roster"
      ? { meleeWave: "half_roster" }
      : {}),
    ...(experiment.meleeWave === "location_approach"
      ? { meleeWave: "location_approach" }
      : {}),
    ...([1, 12, 40].includes(experiment.firstBeatTick)
      ? { firstBeatTick: experiment.firstBeatTick }
      : {}),
    ...(Array.isArray(experiment.moveOffsetTicks)
        && experiment.moveOffsetTicks.length === 3
        && experiment.moveOffsetTicks.every((tick, index) => (
          tick === [68, 148, 228][index]
        ))
      ? { moveOffsetTicks: [...experiment.moveOffsetTicks] }
      : {}),
  };
  return Object.keys(overrides).length === 0 ? undefined : { ...profile, ...overrides };
}


async function mechanicsByMaster(root, roster) {
  const values = new Map();
  for (const master of new Set(roster.map(({ master }) => master))) {
    const unit = unitByMaster.get(master);
    if (!unit) throw new RangeError(`no unit registry entry for master ${master}`);
    values.set(master, await loadMechanics(root, unit));
  }
  return values;
}


async function loadMechanics(root, unit) {
  const key = `${root.href ?? root}|${unit.fixture}`;
  if (!mechanicsCache.has(key)) {
    mechanicsCache.set(key, readFile(
      new URL(`fixtures/unit_stats/${unit.fixture}`, root), "utf8",
    ).then(JSON.parse));
  }
  return mechanicsCache.get(key);
}


function kiteScenario(row) {
  const sides = [row.side2, row.side3].map((side) => ({
    ...side,
    unit: unitByMaster.get(side.master),
  }));
  const family = resolveFamily({
    side2Class: sides[0].unit?.class,
    side3Class: sides[1].unit?.class,
  });
  if (family !== "kite") return {};
  const kiters = sides.filter(({ unit }) => unit?.class === "mobile_ranged");
  if (kiters.length !== 1) {
    throw new RangeError(`kite row ${row.id ?? row.matchup} must have exactly one mobile ranged side`);
  }
  const [kiter] = kiters;
  const profile = KITE_PROFILES[kiter.unit.slug];
  if (!profile) throw new RangeError(`no kite profile for ${kiter.unit.slug}`);
  return {
    kiteOwner: kiter.owner,
    kiteProfile: profile,
    ...(row.matchup === "Elite Skirmisher vs Heavy Camel Rider"
      ? { chaseCapture: true }
      : {}),
    ...(row.matchup === "Heavy Cavalry Archer vs Champion"
      ? { kitedEscape: true }
      : {}),
  };
}


function acquisitionRanks(roster, sampleIndex, seed, rowId) {
  const ordered = [...roster];
  if (sampleIndex !== 0) {
    const random = mulberry32(mixSeed(seed, sampleIndex, rowId));
    for (let index = ordered.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(random() * (index + 1));
      [ordered[index], ordered[swap]] = [ordered[swap], ordered[index]];
    }
  }
  return new Map(ordered.map(({ id }, index) => [id, index]));
}


function mixSeed(seed, sampleIndex, rowId) {
  let value = (seed ^ sampleIndex) >>> 0;
  for (const char of rowId) value = Math.imul(value ^ char.charCodeAt(0), 16777619) >>> 0;
  return value;
}


function mulberry32(initial) {
  let state = initial >>> 0;
  return () => {
    state = (state + 0x6D2B79F5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}


function diagnostics(events, units) {
  const counts = new Map();
  const ownerByReference = new Map(units.map((unit) => [unit.referenceId, unit.owner]));
  const damageEventsByOwner = {};
  const damageAmountByOwner = {};
  const firstDamageTickByOwner = {};
  const firstDamageEventByOwner = {};
  for (const { type } of events) counts.set(type, (counts.get(type) ?? 0) + 1);
  for (const entry of events) {
    if (entry.type !== "damage") continue;
    const owner = ownerByReference.get(entry.actorId);
    if (owner === undefined) continue;
    const key = String(owner);
    damageEventsByOwner[key] = (damageEventsByOwner[key] ?? 0) + 1;
    damageAmountByOwner[key] = (damageAmountByOwner[key] ?? 0) + entry.amount;
    if (firstDamageEventByOwner[key] === undefined) {
      firstDamageEventByOwner[key] = Object.freeze({
        tick: entry.tick,
        actorId: entry.actorId,
        targetId: entry.targetId,
      });
    }
    firstDamageTickByOwner[key] = Math.min(
      firstDamageTickByOwner[key] ?? entry.tick,
      entry.tick,
    );
  }
  return Object.freeze({
    eventCount: events.length,
    damageEvents: counts.get("damage") ?? 0,
    damageEventsByOwner: Object.freeze(damageEventsByOwner),
    damageAmountByOwner: Object.freeze(damageAmountByOwner),
    firstDamageTickByOwner: Object.freeze(firstDamageTickByOwner),
    firstDamageEventByOwner: Object.freeze(firstDamageEventByOwner),
    blockedEvents: counts.get("blocked") ?? 0,
    targetAcquisitions: counts.get("pursuit-acquired") ?? 0,
    targetInvalidations: counts.get("pursuit-invalidated") ?? 0,
  });
}


function timeoutDiagnostics(world, retainedEvents = world.eventLog) {
  const live = world.units.filter(({ alive }) => alive);
  const liveByOwner = {};
  const hpByOwner = {};
  for (const unit of live) {
    const key = String(unit.owner);
    liveByOwner[key] = (liveByOwner[key] ?? 0) + 1;
    hpByOwner[key] = (hpByOwner[key] ?? 0) + unit.hp;
  }
  const damage = retainedEvents.filter(({ type }) => type === "damage");
  let minEnemyDistance = Infinity;
  for (let left = 0; left < live.length; left += 1) {
    for (let right = left + 1; right < live.length; right += 1) {
      if (live[left].owner === live[right].owner) continue;
      minEnemyDistance = Math.min(minEnemyDistance, Math.hypot(
        live[left].x - live[right].x,
        live[left].y - live[right].y,
      ));
    }
  }
  return Object.freeze({
    liveByOwner: Object.freeze(liveByOwner),
    hpByOwner: Object.freeze(hpByOwner),
    lastDamageTick: damage.at(-1)?.tick ?? null,
    minEnemyDistance: Number.isFinite(minEnemyDistance) ? minEnemyDistance : null,
    liveUnits: Object.freeze(live.map((unit) => Object.freeze({
      referenceId: unit.referenceId,
      owner: unit.owner,
      x: unit.x,
      y: unit.y,
      hp: unit.hp,
      action: unit.action,
      pursuitTargetId: unit.pursuitTargetId,
      engagedTargetId: unit.engagedTargetId,
      moveOrder: unit.moveOrder ?? null,
    }))),
  });
}


function bandDistance(value, minimum, maximum) {
  if (value < minimum) return minimum - value;
  if (value > maximum) return value - maximum;
  return 0;
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}
