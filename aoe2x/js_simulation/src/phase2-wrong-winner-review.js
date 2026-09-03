import { readFile } from "node:fs/promises";

import { hashCanonicalJson } from "./canonical-json.js";
import { createWorld, runWorld } from "./combat/world.js";
import { slimSnapshot } from "./fight.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "./phase2-batch1-comparison.js";
import { resolveFamily } from "./placement.js";
import { UNIT_REGISTRY } from "./unit-registry.js";


export const PHASE2_WRONG_WINNER_REPORT =
  "phase2_all_120_post_capacity_2026-08-20";
export const PHASE2_FLIPPED_REVIEW_ROW_IDS = Object.freeze([
  "elite_conquistador_vs_elite_elephant",
  "elite_janissary_vs_elite_elephant",
  "elite_janissary_vs_paladin",
  "elite_karambit_warrior_vs_heavy_cav_archer",
  "elite_karambit_warrior_vs_paladin",
  "elite_throwing_axeman_vs_arbalester",
  "elite_war_wagon_vs_champion",
  "elite_woad_raider_vs_heavy_cav_archer",
]);
const REPORT_URL = `calibration/reports/${PHASE2_WRONG_WINNER_REPORT}/results.json`;
const registryByMaster = new Map(UNIT_REGISTRY.map((unit) => [unit.master, unit]));
const dataByRoot = new Map();


function rootKey(root) {
  return root instanceof URL ? root.href : String(root);
}


function reviewRow(row) {
  const simulationScore = row.comparison.mean;
  const simulationSign = Math.sign(simulationScore);
  const selectedSample = row.samples.find(({ score }) => (
    Number.isFinite(score) && Math.sign(score) === simulationSign
  ));
  if (!selectedSample) throw new Error(`wrong-winner row ${row.id} has no matching playback`);
  return Object.freeze({
    id: row.id,
    matchup: row.matchup,
    side2: Object.freeze({
      slug: row.side2.slug,
      label: row.side2.unit,
      count: row.side2.count,
    }),
    side3: Object.freeze({
      slug: row.side3.slug,
      label: row.side3.unit,
      count: row.side3.count,
    }),
    tapeScore: row.tape.mean,
    simulationScore,
    delta: simulationScore - row.tape.mean,
    sampleIndex: selectedSample.sampleIndex,
  });
}


async function loadData(root) {
  const key = rootKey(root);
  if (!dataByRoot.has(key)) {
    dataByRoot.set(key, Promise.all([
      readFile(new URL(REPORT_URL, root), "utf8").then(JSON.parse),
      loadPhase2Batch1Truth(root),
    ]).then(async ([report, truth]) => {
      const context = await loadPhase2Batch1Context(root, truth);
      const reportRows = new Map(report.rows.map((row) => [row.id, row]));
      const rows = Object.freeze(PHASE2_FLIPPED_REVIEW_ROW_IDS.map((rowId) => {
        const row = reportRows.get(rowId);
        if (!row || row.comparison.wrongStableWinner !== true
            || !Number.isFinite(row.comparison.mean)
            || !row.samples?.some(({ score }) => Number.isFinite(score))) {
          throw new Error(`latest Phase 2 report cannot play flipped row ${rowId}`);
        }
        return reviewRow(row);
      }));
      return Object.freeze({
        report,
        truth,
        context,
        catalogue: Object.freeze({
          schemaVersion: 1,
          report: PHASE2_WRONG_WINNER_REPORT,
          source: Object.freeze({
            archive: report.source.archive.name,
            zipSha256: report.source.archive.zip_sha256,
          }),
          rows,
        }),
      });
    }));
  }
  return dataByRoot.get(key);
}


export async function loadPhase2WrongWinnerCatalogue(root) {
  return (await loadData(root)).catalogue;
}


async function selectedReview(root, rowId) {
  const data = await loadData(root);
  const preset = data.catalogue.rows.find(({ id }) => id === rowId);
  if (!preset) throw new RangeError(`row ${rowId} is not a resolved wrong-winner review row`);
  const row = data.truth.rows.find(({ id }) => id === rowId);
  if (!row) throw new Error(`Phase 2 truth is missing ${rowId}`);
  return Object.freeze({ ...data, preset, row });
}


function unitMetadata(units) {
  return Object.freeze(Object.fromEntries(units.map((unit) => {
    const registry = registryByMaster.get(unit.mechanics.unit_master);
    if (!registry) throw new Error(`unit registry is missing master ${unit.mechanics.unit_master}`);
    return [unit.referenceId, Object.freeze({
      owner: unit.owner,
      slug: registry.slug,
      label: registry.label,
      maxHp: unit.mechanics.hp,
      master: unit.mechanics.unit_master,
      collisionRadius: Math.max(
        unit.mechanics.collision_size_tiles.x,
        unit.mechanics.collision_size_tiles.y,
      ),
      attackRange: unit.mechanics.attack_range_tiles,
    })];
  })));
}


export async function runPhase2WrongWinnerPlayback(root, rowId) {
  const { context, preset, report, row } = await selectedReview(root, rowId);
  const sampleIndex = preset.sampleIndex;
  const seed = report.config.seed;
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex, seed, context });
  const persistentPursuit = scenario.persistentMeleePursuitRouting === true;
  const playbackScenario = persistentPursuit
    ? Object.freeze({ ...scenario, persistentMeleePursuitRouting: true })
    : scenario;
  const result = runWorld(createWorld(playbackScenario), {
    maxTicks: PHASE2_MAX_TICKS,
    retainSnapshots: true,
  });
  const side2Registry = registryByMaster.get(row.side2.master);
  const side3Registry = registryByMaster.get(row.side3.master);
  if (!side2Registry || !side3Registry) throw new Error(`unit registry is incomplete for ${rowId}`);
  const family = resolveFamily({
    side2Class: side2Registry.class,
    side3Class: side3Registry.class,
  });
  const live = result.world.units.filter(({ alive }) => alive);
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    schemaVersion: 1,
    mode: "phase2-wrong-winner-review",
    review: Object.freeze({
      report: PHASE2_WRONG_WINNER_REPORT,
      rowId,
      sampleIndex,
      tapeScore: preset.tapeScore,
      simulationScore: preset.simulationScore,
      delta: preset.delta,
      placement: "exact canonical golden starting_units",
      ...(persistentPursuit ? { pursuitRouting: "persistent-grid" } : {}),
    }),
    side2: Object.freeze({
      slug: row.side2.slug,
      label: row.side2.unit,
      civ: side2Registry.civ,
      count: row.side2.count,
      class: side2Registry.class,
    }),
    side3: Object.freeze({
      slug: row.side3.slug,
      label: row.side3.unit,
      civ: side3Registry.civ,
      count: row.side3.count,
      class: side3Registry.class,
    }),
    family,
    orientationNormalised: false,
    derivedCounts: false,
    budget: null,
    kiteOwner: scenario.kiteOwner ?? null,
    ticks: result.ticks,
    winnerOwner: result.winner,
    winnerHp,
    finalStateHash: hashCanonicalJson({
      tick: result.world.tick,
      ratio: scenario.ratio,
      units: result.world.units,
    }),
    eventLogHash: hashCanonicalJson(result.events),
    unitIndex: unitMetadata(scenario.units),
    snapshots: Object.freeze(result.snapshots.map(slimSnapshot)),
  });
}
