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
    readFile(new URL("fixtures/golden_map.json", root), "utf8").then(JSON.parse),
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
    return createUnitState({
      referenceId: unit.id,
      owner: unit.owner,
      x: unit.x,
      y: unit.y,
      facing: 0,
      mechanics,
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
  const kiteOwner = family === "kite" && mobileOwners.length === 1 ? mobileOwners[0] : null;
  const meleeCrowdOwner = side2Unit.class === "melee"
    ? 2
    : (side3Unit.class === "melee" ? 3 : null);
  const kiter = kiteOwner === 2 ? side2Unit : (kiteOwner === 3 ? side3Unit : null);
  const kiterMechanics = kiteOwner === null
    ? null
    : context.mechanicsByMaster.get(kiter.master);
  const chaserMechanics = kiteOwner === 2
    ? context.mechanicsByMaster.get(side3Unit.master)
    : (kiteOwner === 3 ? context.mechanicsByMaster.get(side2Unit.master) : null);
  const reachMeleeWedgeTransit = kiteOwner !== null
    && (chaserMechanics?.attack_range_tiles ?? 0) >= 1;
  const warWagonKiter = kiter?.slug === "elite_war_wagon";
  return Object.freeze({
    ratio: `${row.side2.count}v${row.side3.count}`,
    units: Object.freeze(units),
    map: context.map,
    ...(kiteOwner === null
      ? {}
      : {
        kiteOwner,
        kiteProfile: deriveKiteProfile(kiterMechanics, kitePolicyFor(kiter.slug)),
        kiteNavigation: "cohesive",
        kiteMeleeOpeningOrder: "attack-move-all",
        chaseCapture: true,
        kiteChaseDwellTicks: 0,
        pairwiseAlliedTransit: false,
        reachMeleeWedgeTransit,
        ...(warWagonKiter ? warWagonChasePolicy(kiter.slug, chaserMechanics) : {}),
      }),
    ...(meleeCrowdOwner === null
      ? {}
      : {
        meleeCrowdOwner,
        preventiveContactSteering: true,
      }),
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
