import { readFile } from "node:fs/promises";

import { buildArenaPhysicsMap } from "./arena-physics-map.js";
import { hashCanonicalJson } from "./canonical-json.js";
import {
  deriveKiteProfile,
  kitePolicyFor,
  warWagonChasePolicy,
} from "./combat/kite-timing.js";
import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld } from "./combat/world.js";
import { resolveFamily } from "./placement.js";
import { signedScore } from "./standard-units-comparison.js";
import { UNIT_REGISTRY } from "./unit-registry.js";


export const PHASE2_MAX_TICKS = 9000;
export const PHASE2_OPENING_VOLLEY_TICK = 1;
const unitByMaster = new Map(UNIT_REGISTRY.map((unit) => [unit.master, unit]));


export async function loadPhase2Batch1Truth(root) {
  return JSON.parse(await readFile(
    new URL("calibration/fixtures/phase2/batch1_truth.json", root),
    "utf8",
  ));
}


export async function loadPhase2Batch1Context(root, truth = undefined) {
  const selectedTruth = truth ?? await loadPhase2Batch1Truth(root);
  const masters = [...new Set(selectedTruth.rows.flatMap((row) => [
    row.side2.master,
    row.side3.master,
  ]))];
  const [mapFixture, mechanicsEntries] = await Promise.all([
    readFile(new URL("fixtures/golden_map_legacy.json", root), "utf8").then(JSON.parse),
    Promise.all(masters.map(async (master) => {
      const unit = unitByMaster.get(master);
      if (!unit) throw new RangeError(`no unit registry entry for master ${master}`);
      const mechanics = JSON.parse(await readFile(
        new URL(`fixtures/unit_stats/${unit.fixture}`, root),
        "utf8",
      ));
      return [master, mechanics];
    })),
  ]);
  return Object.freeze({
    map: buildArenaPhysicsMap(mapFixture),
    mechanicsByMaster: new Map(mechanicsEntries),
  });
}


export function scenarioFromPhase2Batch1Row({ row, sampleIndex, seed, context }) {
  requireSampleInputs(row, sampleIndex, seed, context);
  const canonical = row.runs[0];
  const ranks = acquisitionRanks(canonical.starting_units, sampleIndex, seed, row.id);
  const units = canonical.starting_units.map((unit) => {
    const mechanics = context.mechanicsByMaster.get(unit.master);
    if (!mechanics) throw new RangeError(`missing mechanics for master ${unit.master}`);
    const registryUnit = unitByMaster.get(unit.master);
    return createUnitState({
      referenceId: unit.id,
      owner: unit.owner,
      x: unit.x,
      y: unit.y,
      facing: 0,
      mechanics,
      ...(registryUnit?.behaviorFamily === undefined
        ? {}
        : { behaviorFamily: registryUnit.behaviorFamily }),
      acquisitionRank: ranks.get(unit.id),
      acquisitionCount: canonical.starting_units.length,
    });
  });
  const side2Unit = unitByMaster.get(row.side2.master);
  const side3Unit = unitByMaster.get(row.side3.master);
  if (!side2Unit || !side3Unit) throw new RangeError(`unknown unit in ${row.id}`);
  const family = resolveFamily({
    side2Class: side2Unit.class,
    side3Class: side3Unit.class,
  });
  const mobileOwners = [
    side2Unit.class === "mobile_ranged" ? 2 : null,
    side3Unit.class === "mobile_ranged" ? 3 : null,
  ].filter(Number.isSafeInteger);
  // In the raw Phase 2 ranged-versus-ranged recordings, the unique-unit
  // subject is the player-commanded shoot-and-move side while its standard
  // opponent continues through ordinary ranged unit/AI combat. Comparison
  // normalization can swap that subject to owner 3 (Gbeto-vs-HCA), so carry
  // the order role through the swap instead of keying behavior to a player
  // number. This is scenario command fidelity, not a unit matchup modifier.
  const subjectOwner = row.side2.slug === row.subject_slug
    ? 2
    : (row.side3.slug === row.subject_slug ? 3 : null);
  const subjectUnit = subjectOwner === 2 ? side2Unit : (subjectOwner === 3 ? side3Unit : null);
  const opposingUnit = subjectOwner === 2 ? side3Unit : (subjectOwner === 3 ? side2Unit : null);
  const subjectMechanics = subjectUnit
    ? context.mechanicsByMaster.get(subjectUnit.master)
    : null;
  const opposingMechanics = opposingUnit
    ? context.mechanicsByMaster.get(opposingUnit.master)
    : null;
  // A shoot-and-move order can maintain or increase separation only when the
  // commanded side can fire from at least the opponent's range. A shorter-
  // ranged subject (Gbeto into HCA) has no kiting envelope and remains an
  // ordinary ranged engagement, matching the absence of patrol movement in
  // that command stream.
  const hasRangedKitingEnvelope = (subjectMechanics?.attack_range_tiles ?? -Infinity)
    >= (opposingMechanics?.attack_range_tiles ?? Infinity);
  const orderedRangedOwner = family === "rvr"
      && subjectUnit?.class === "mobile_ranged" && hasRangedKitingEnvelope
    ? subjectOwner
    : null;
  const kiteOwner = orderedRangedOwner
    ?? (family === "kite" && mobileOwners.length === 1 ? mobileOwners[0] : null);
  const hasMelee = side2Unit.class === "melee" || side3Unit.class === "melee";
  const kiter = kiteOwner === 2 ? side2Unit : (kiteOwner === 3 ? side3Unit : null);
  const kiterMechanics = kiteOwner === null
    ? null
    : context.mechanicsByMaster.get(kiter.master);
  const chaserMechanics = kiteOwner === 2
    ? context.mechanicsByMaster.get(side3Unit.master)
    : (kiteOwner === 3 ? context.mechanicsByMaster.get(side2Unit.master) : null);
  const warWagonKiter = kiter?.slug === "elite_war_wagon";
  return Object.freeze({
    ratio: `${row.side2.count}v${row.side3.count}`,
    units: Object.freeze(units),
    map: context.map,
    ...(family === "rvr" && orderedRangedOwner === null ? {
      rangedTargetPressureOwner: 3,
    } : {}),
    ...(kiteOwner === null
      ? {}
      : {
        kiteOwner,
        // Every Phase 2 ranged-melee tape opens with an immediate attack
        // command and then settles onto the mechanics-derived recurring beat.
        // This is scenario order state, not a unit/outcome calibration: the
        // same tick-one opening applies whichever eligible ranged unit owns
        // the kiting side, while its reload and release timing remain sourced
        // from that unit's mechanics.
        kiteProfile: deriveKiteProfile(kiterMechanics, {
          ...kitePolicyFor(kiter.slug),
          openingVolleyTick: PHASE2_OPENING_VOLLEY_TICK,
          openingVolley: "close_to_fire",
        }),
        kiteNavigation: "cohesive",
        ...(orderedRangedOwner === null
          ? {
            kiteMeleeOpeningOrder: "attack-move-all",
            chaseCapture: true,
            kiteChaseDwellTicks: 0,
            ...(warWagonKiter ? warWagonChasePolicy(kiter.slug, chaserMechanics) : {}),
          }
          : { kiteOpponentMode: "ordinary-ranged" }),
      }),
    ...(hasMelee ? { preventiveContactSteering: true } : {}),
  });
}


export function runPhase2Batch1Sample({ row, sampleIndex, seed, context }) {
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex, seed, context });
  let result;
  try {
    result = runWorld(createWorld(scenario), {
      maxTicks: PHASE2_MAX_TICKS,
      retainSnapshots: false,
    });
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded")) throw error;
    return Object.freeze({
      rowId: row.id,
      sampleIndex,
      seed,
      outcome: "timeout",
      winnerOwner: null,
      winnerHp: null,
      score: null,
      ticks: PHASE2_MAX_TICKS,
      finalStateHash: null,
      eventLogHash: null,
    });
  }
  const live = result.world.units.filter(({ alive }) => alive);
  const winnerOwner = result.winner;
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    rowId: row.id,
    sampleIndex,
    seed,
    outcome: "win",
    winnerOwner,
    winnerHp,
    score: signedScore({
      winnerOwner,
      winnerHp,
      startingHpByOwner: row.runs[0].starting_hp_by_owner,
    }),
    ticks: result.ticks,
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick,
      ratio: scenario.ratio,
      units: result.world.units,
    }),
    eventLogHash: hashCanonicalJson(result.events),
  });
}


function requireSampleInputs(row, sampleIndex, seed, context) {
  if (!row?.runs?.[0]?.starting_units?.length) {
    throw new RangeError("Phase 2 row requires a canonical starting roster");
  }
  if (!Number.isSafeInteger(sampleIndex) || sampleIndex < 0) {
    throw new RangeError(`sampleIndex must be a nonnegative safe integer, got ${sampleIndex}`);
  }
  if (!Number.isSafeInteger(seed)) throw new RangeError(`seed must be a safe integer, got ${seed}`);
  if (!(context?.mechanicsByMaster instanceof Map) || !context.map) {
    throw new TypeError("Phase 2 comparison context is required");
  }
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
