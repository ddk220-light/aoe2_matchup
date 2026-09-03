import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  loadDedicatedComparisonContext,
  scenarioFromDedicatedRun,
} from "../../../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../../../src/dedicated-golden-corpus.js";
import { createWorld, runWorld } from "../../../src/combat/world.js";

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const root = new URL("../../../", import.meta.url);
const [corpus, context] = await Promise.all([
  loadDedicatedGoldenCorpus(root),
  loadDedicatedComparisonContext(root),
]);

const variants = [
  {
    id: "baseline_kiter_navigation",
    preventiveContactSteering: true,
    strength: 0.5,
    omitKiteNavigation: true,
  },
];
const matchupIds = [
  "heavy_cav_archer_vs_elite_steppe",
];

function round(value, digits = 2) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function runVariant(matchup, row, run, variant) {
  const base = scenarioFromDedicatedRun({
    row,
    run,
    mechanicsByMaster: context.mechanicsByMaster,
    map: context.map,
  });
  const scenario = {
    ...base,
    preventiveContactSteering: variant.preventiveContactSteering,
    ...(variant.strength === undefined
      ? {}
      : { preventiveContactSteeringStrength: variant.strength }),
  };
  if (variant.omitKiteNavigation) delete scenario.kiteNavigation;
  const result = runWorld(createWorld(scenario), { maxTicks: 9000, retainSnapshots: false });
  const initialById = new Map(run.starting_units.map((unit) => [unit.id, unit]));
  const winnerUnits = result.world.units.filter((unit) => unit.alive && unit.owner === result.winner);
  const winnerHp = winnerUnits.reduce((sum, unit) => sum + unit.hp, 0);
  const winnerStartHp = run.starting_hp_by_owner[String(result.winner)];
  const score = (result.winner === 2 ? -1 : 1) * winnerHp / winnerStartHp * 100;
  const chaserIds = new Set(run.starting_units
    .filter((unit) => unit.owner === 3)
    .map((unit) => unit.id));
  const hcaIds = new Set(run.starting_units
    .filter((unit) => unit.owner === 2)
    .map((unit) => unit.id));
  const chaserEvents = result.events.filter((event) => chaserIds.has(event.actorId));
  const hcaEvents = result.events.filter((event) => hcaIds.has(event.actorId));
  const damageEvents = chaserEvents.filter((event) => event.type === "damage");
  const hcaDamageEvents = hcaEvents.filter((event) => event.type === "damage");
  const engagementStarts = chaserEvents.filter((event) => event.type === "engagement-started");
  const attackStarts = chaserEvents.filter((event) => event.type === "attack-start");
  const moveEvents = chaserEvents.filter((event) => event.type === "move");
  const blockedEvents = chaserEvents.filter((event) => event.type === "blocked");
  const firstDamageTick = damageEvents.length ? Math.min(...damageEvents.map((event) => event.tick)) : null;
  const uniqueChasersToDamage = new Set(damageEvents.map((event) => event.actorId)).size;
  const finalChaserHp = result.world.units
    .filter((unit) => initialById.get(unit.referenceId)?.owner === 3)
    .reduce((sum, unit) => sum + unit.hp, 0);
  return {
    repeat: run.repeat,
    tapeScore: run.signed_score,
    winnerOwner: result.winner,
    score: round(score),
    delta: round(score - run.signed_score),
    ticks: result.ticks,
    firstDamageTick,
    firstDamageSeconds: firstDamageTick === null ? null : round(firstDamageTick / 60),
    engagementStarts: engagementStarts.length,
    attackStarts: attackStarts.length,
    damagingHits: damageEvents.length,
    damageDealt: round(damageEvents.reduce((sum, event) => sum + event.amount, 0)),
    uniqueChasersToDamage,
    hcaAttackStarts: hcaEvents.filter((event) => event.type === "attack-start").length,
    hcaDamagingHits: hcaDamageEvents.length,
    hcaDamageDealt: round(hcaDamageEvents.reduce((sum, event) => sum + event.amount, 0)),
    chaserMoveEvents: moveEvents.length,
    chaserBlockedEvents: blockedEvents.length,
    finalChaserHp,
  };
}

const rows = [];
for (const matchupId of matchupIds) {
  const matchup = corpus.matchups.find(({ id }) => id === matchupId);
  for (const row of matchup.ratios.filter(({ ratio }) => ratio === "20v20")) {
    for (const variant of variants) {
      const samples = row.runs.slice(0, 1).map((run) => (
        runVariant(matchup, row, run, variant)
      ));
      rows.push({
        matchupId,
        ratio: row.ratio,
        variant: variant.id,
        tapeMean: round(mean(samples.map(({ tapeScore }) => tapeScore))),
        simulationMean: round(mean(samples.map(({ score }) => score))),
        meanDelta: round(mean(samples.map(({ delta }) => delta))),
        meanTicks: round(mean(samples.map(({ ticks }) => ticks))),
        meanFirstDamageSeconds: round(mean(samples.map(({ firstDamageSeconds }) => firstDamageSeconds))),
        meanEngagementStarts: round(mean(samples.map(({ engagementStarts }) => engagementStarts))),
        meanAttackStarts: round(mean(samples.map(({ attackStarts }) => attackStarts))),
        meanDamagingHits: round(mean(samples.map(({ damagingHits }) => damagingHits))),
        meanDamageDealt: round(mean(samples.map(({ damageDealt }) => damageDealt))),
        meanUniqueChasersToDamage: round(mean(samples.map(({ uniqueChasersToDamage }) => uniqueChasersToDamage))),
        meanHcaAttackStarts: round(mean(samples.map(({ hcaAttackStarts }) => hcaAttackStarts))),
        meanHcaDamagingHits: round(mean(samples.map(({ hcaDamagingHits }) => hcaDamagingHits))),
        meanHcaDamageDealt: round(mean(samples.map(({ hcaDamageDealt }) => hcaDamageDealt))),
        meanChaserMoveEvents: round(mean(samples.map(({ chaserMoveEvents }) => chaserMoveEvents))),
        meanChaserBlockedEvents: round(mean(samples.map(({ chaserBlockedEvents }) => chaserBlockedEvents))),
        samples,
      });
    }
  }
}

const output = {
  generatedAt: new Date().toISOString(),
  description: "One exact-start HCA-Steppe 20v20 repeat per physics-policy counterfactual; no engine source changes.",
  rows,
};
const outputPath = path.join(outputDir, "steppe_navigation_counterfactual.json");
fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
