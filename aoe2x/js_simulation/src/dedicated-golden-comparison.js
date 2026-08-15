import { readFile } from "node:fs/promises";

import { buildArenaPhysicsMap } from "./arena-physics-map.js";
import { hashCanonicalJson } from "./canonical-json.js";
import { deriveKiteProfile, kitePolicyFor } from "./combat/kite-timing.js";
import { createUnitState } from "./combat/unit-state.js";
import { createWorld, runWorld } from "./combat/world.js";
import { UNIT_REGISTRY } from "./unit-registry.js";


export const DEDICATED_MAX_TICKS = 9000;
const unitBySlug = new Map(UNIT_REGISTRY.map((unit) => [unit.slug, unit]));


export async function loadDedicatedComparisonContext(root) {
  const slugs = [
    "arbalester", "imp_elite_skirm", "heavy_cav_archer", "heavy_scorpion",
    "champion", "elite_elephant", "elite_fire_lancer", "paladin", "elite_steppe",
  ];
  const [mapFixture, mechanicsEntries] = await Promise.all([
    readFile(new URL("fixtures/golden_map.json", root), "utf8").then(JSON.parse),
    Promise.all(slugs.map(async (slug) => {
      const unit = unitBySlug.get(slug);
      const mechanics = JSON.parse(await readFile(
        new URL(`fixtures/unit_stats/${unit.fixture}`, root),
        "utf8",
      ));
      return [unit.master, mechanics];
    })),
  ]);
  return Object.freeze({
    map: buildArenaPhysicsMap(mapFixture),
    mechanicsByMaster: new Map(mechanicsEntries),
  });
}


export function scenarioFromDedicatedRun({ row, run, mechanicsByMaster, map }) {
  const units = run.starting_units.map((unit, acquisitionRank) => {
    const mechanics = mechanicsByMaster.get(unit.master);
    if (!mechanics) throw new RangeError(`missing mechanics for master ${unit.master}`);
    return createUnitState({
      referenceId: unit.id,
      owner: unit.owner,
      x: unit.x,
      y: unit.y,
      facing: 0,
      mechanics,
      acquisitionRank,
      acquisitionCount: run.starting_units.length,
    });
  });
  const ranged = unitBySlug.get(row.rangedSlug);
  if (!ranged) throw new RangeError(`unknown ranged unit ${row.rangedSlug}`);
  const rangedMechanics = mechanicsByMaster.get(ranged.master);
  const reachMeleeWedgeTransit = units.some((unit) => (
    unit.owner === 3 && (unit.mechanics?.attack_range_tiles ?? 0) >= 1
  ));
  return Object.freeze({
    ratio: row.ratio,
    units: Object.freeze(units),
    map,
    kiteOwner: 2,
    kiteProfile: deriveKiteProfile(rangedMechanics, kitePolicyFor(ranged.slug)),
    kiteNavigation: "cohesive",
    kiteMeleeOpeningOrder: "attack-move-all",
    chaseCapture: true,
    kiteChaseDwellTicks: 0,
    pairwiseAlliedTransit: false,
    reachMeleeWedgeTransit,
    preventiveContactSteering: true,
  });
}


export function runDedicatedTapeRepeat({ row, run, context }) {
  const scenario = scenarioFromDedicatedRun({
    row,
    run,
    mechanicsByMaster: context.mechanicsByMaster,
    map: context.map,
  });
  let result;
  try {
    result = runWorld(createWorld(scenario), {
      maxTicks: DEDICATED_MAX_TICKS,
      retainSnapshots: false,
    });
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded")) throw error;
    return Object.freeze({
      rowId: row.id,
      repeat: run.repeat,
      outcome: "timeout",
      winnerOwner: null,
      winnerHp: null,
      score: null,
      ticks: DEDICATED_MAX_TICKS,
      tapeScore: run.signed_score,
      delta: null,
    });
  }
  const live = result.world.units.filter(({ alive }) => alive);
  const winnerOwner = result.winner;
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  const score = signedScore(winnerOwner, winnerHp, run.starting_hp_by_owner);
  return Object.freeze({
    rowId: row.id,
    repeat: run.repeat,
    outcome: "win",
    winnerOwner,
    winnerHp,
    score,
    ticks: result.ticks,
    tapeScore: run.signed_score,
    delta: score - run.signed_score,
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick,
      ratio: scenario.ratio,
      units: result.world.units,
    }),
    eventLogHash: hashCanonicalJson(result.events),
  });
}


export function compareDedicatedRow(row, samples) {
  const tapeScores = row.runs.map(({ signed_score: score }) => score);
  const simulationScores = samples.map(({ score }) => score).filter(Number.isFinite);
  const sampleByRepeat = new Map(samples.map((sample) => [sample.repeat, sample]));
  const repeatDeltas = row.runs.map((run) => {
    const score = sampleByRepeat.get(run.repeat)?.score;
    return Number.isFinite(score) ? score - run.signed_score : null;
  });
  const tapeMean = mean(tapeScores);
  const simulationMean = simulationScores.length ? mean(simulationScores) : null;
  const tapeMin = Math.min(...tapeScores);
  const tapeMax = Math.max(...tapeScores);
  const meanDelta = simulationMean === null ? null : simulationMean - tapeMean;
  return Object.freeze({
    tape: summary(tapeScores),
    simulation: summary(simulationScores),
    meanDelta,
    absoluteMeanDelta: meanDelta === null ? null : Math.abs(meanDelta),
    tapeBandError: simulationMean === null ? null : bandDistance(simulationMean, tapeMin, tapeMax),
    tapeBandCoverage: simulationScores.length === 0
      ? 0
      : simulationScores.filter((score) => score >= tapeMin && score <= tapeMax).length
        / simulationScores.length,
    repeatDeltas: Object.freeze(repeatDeltas),
    unresolvedRuns: samples.filter(({ score }) => !Number.isFinite(score)).length,
    wrongWinnerRuns: row.runs.filter((run) => {
      const score = sampleByRepeat.get(run.repeat)?.score;
      return Number.isFinite(score) && Math.sign(score) !== Math.sign(run.signed_score);
    }).length,
  });
}


function signedScore(winnerOwner, winnerHp, startingHpByOwner) {
  const starting = startingHpByOwner[winnerOwner] ?? startingHpByOwner[String(winnerOwner)];
  const magnitude = 100 * winnerHp / starting;
  return winnerOwner === 2 ? -magnitude : magnitude;
}


function summary(scores) {
  return Object.freeze({
    runs: scores.length,
    mean: scores.length ? mean(scores) : null,
    min: scores.length ? Math.min(...scores) : null,
    max: scores.length ? Math.max(...scores) : null,
    owner3WinRate: scores.length
      ? scores.filter((score) => score > 0).length / scores.length
      : null,
  });
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function bandDistance(value, minimum, maximum) {
  if (value < minimum) return minimum - value;
  if (value > maximum) return value - maximum;
  return 0;
}
