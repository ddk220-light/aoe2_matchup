import { mkdir, readFile, writeFile } from "node:fs/promises";

import { createWorld, runWorld } from "../../src/combat/world.js";
import {
  DEDICATED_MAX_TICKS,
  loadDedicatedComparisonContext,
  scenarioFromDedicatedRun,
} from "../../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../../src/dedicated-golden-corpus.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";
import { signedScore } from "../../src/standard-units-comparison.js";


const ROOT = new URL("../../", import.meta.url);
const OUTPUT = new URL(
  "../reports/persistent_melee_pursuit_2026-08-19/results.json",
  import.meta.url,
);
const PHASE2_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const HCA_PALADIN_SHA256 = "8902DE64B120E6302860F8F9B35B572523B29B4C0F305C65A7DA6D0C286F7968";
const SAMPLE_COUNT = Number(process.argv[2] ?? 5);
const SEED = 20260817;
if (!Number.isSafeInteger(SAMPLE_COUNT) || SAMPLE_COUNT < 1 || SAMPLE_COUNT > 5) {
  throw new RangeError("route sample count must be an integer from 1 to 5");
}


const phase2Source = JSON.parse(await readFile(
  new URL("calibration/source/phase2_source.json", ROOT), "utf8",
));
if (phase2Source.authorized !== true || phase2Source.zip_sha256 !== PHASE2_SHA256) {
  throw new Error(`unauthorized Phase 2 source ${phase2Source.zip_sha256}`);
}
const phase2Truth = await loadPhase2Batch1Truth(ROOT);
const phase2Context = await loadPhase2Batch1Context(ROOT, phase2Truth);
const boyarRow = phase2Truth.rows.find(({ id }) => id === "elite_boyar_vs_heavy_cav_archer");
if (!boyarRow || phase2Truth.archive?.zip_sha256 !== PHASE2_SHA256) {
  throw new Error("missing authorized Elite Boyar-HCA row");
}

const dedicated = await loadDedicatedGoldenCorpus(ROOT);
const dedicatedContext = await loadDedicatedComparisonContext(ROOT);
const paladinRow = dedicated.rows.find(({ id }) => (
  id === "heavy_cav_archer_vs_paladin_20v15"
));
if (!paladinRow || paladinRow.zipSha256 !== HCA_PALADIN_SHA256) {
  throw new Error("missing authorized HCA-Paladin 20v15 row");
}

const latestPhase2Report = JSON.parse(await readFile(new URL(
  "../reports/phase2_reachable_opening_body_formation_full_2026-08-19/results.json",
  import.meta.url,
), "utf8"));
const boyarBaseline = latestPhase2Report.rows.find(({ id }) => id === boyarRow.id);
const paladinBaselineCheckpoint = JSON.parse(await readFile(new URL(
  "../reports/shared_enemy_pair_transit_2026-08-18/checkpoints/"
    + "heavy_cav_archer_vs_paladin_20v15.json",
  import.meta.url,
), "utf8"));

const boyarSamples = [];
for (let sampleIndex = 0; sampleIndex < SAMPLE_COUNT; sampleIndex += 1) {
  const base = scenarioFromPhase2Batch1Row({
    row: boyarRow,
    sampleIndex,
    seed: SEED,
    context: phase2Context,
  });
  boyarSamples.push(runCandidate({
    scenario: Object.freeze({ ...base, persistentMeleePursuitRouting: true }),
    maxTicks: PHASE2_MAX_TICKS,
    startingHpByOwner: boyarRow.runs[0].starting_hp_by_owner,
    meleeMaster: boyarRow.side3.master,
    retainSnapshots: sampleIndex === 0,
    sample: sampleIndex,
  }));
}

const paladinSamples = paladinRow.runs.slice(0, SAMPLE_COUNT).map((run, sampleIndex) => {
  const base = scenarioFromDedicatedRun({
    row: paladinRow,
    run,
    mechanicsByMaster: dedicatedContext.mechanicsByMaster,
    map: dedicatedContext.map,
  });
  return runCandidate({
    scenario: Object.freeze({ ...base, persistentMeleePursuitRouting: true }),
    maxTicks: DEDICATED_MAX_TICKS,
    startingHpByOwner: run.starting_hp_by_owner,
    meleeMaster: paladinRow.side3.master,
    retainSnapshots: sampleIndex === 0,
    sample: run.repeat,
  });
});

const report = Object.freeze({
  schemaVersion: 1,
  experiment: "persistent-melee-pursuit-routing",
  samplesRun: boyarSamples.length + paladinSamples.length,
  source: Object.freeze({
    phase2: PHASE2_SHA256,
    hcaPaladin: HCA_PALADIN_SHA256,
  }),
  rows: Object.freeze([
    Object.freeze({
      id: boyarRow.id,
      matchup: boyarRow.matchup,
      ratio: `${boyarRow.side2.count}v${boyarRow.side3.count}`,
      tape: summarize(boyarRow.runs.map(({ signed_score: score }) => score)),
      previousEngine: Object.freeze({
        ...boyarBaseline.comparison,
        report: latestPhase2Report.config?.reportId
          ?? "phase2_reachable_opening_body_formation_full_2026-08-19",
      }),
      candidate: summarizeSamples(boyarSamples),
      diagnosticSample: boyarSamples[0].diagnostics,
    }),
    Object.freeze({
      id: paladinRow.id,
      matchup: "Heavy Cavalry Archer vs Paladin",
      ratio: paladinRow.ratio,
      tape: summarize(paladinRow.runs.map(({ signed_score: score }) => score)),
      previousEngine: Object.freeze({
        samples: paladinBaselineCheckpoint.samples.length,
        score: paladinBaselineCheckpoint.samples[0].outcome.score,
        winnerOwner: paladinBaselineCheckpoint.samples[0].outcome.winnerOwner,
        ticks: paladinBaselineCheckpoint.samples[0].outcome.ticks,
        report: "shared_enemy_pair_transit_2026-08-18",
      }),
      candidate: summarizeSamples(paladinSamples),
      diagnosticSample: paladinSamples[0].diagnostics,
    }),
  ]),
});

await mkdir(new URL("../reports/persistent_melee_pursuit_2026-08-19/", import.meta.url), {
  recursive: true,
});
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);


function runCandidate({
  scenario,
  maxTicks,
  startingHpByOwner,
  meleeMaster,
  retainSnapshots,
  sample,
}) {
  let result;
  try {
    result = runWorld(createWorld(scenario), { maxTicks, retainSnapshots });
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded")) throw error;
    return Object.freeze({
      sample,
      outcome: "timeout",
      winnerOwner: null,
      winnerHp: null,
      score: null,
      ticks: maxTicks,
      diagnostics: null,
    });
  }
  const live = result.world.units.filter(({ alive }) => alive);
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    sample,
    outcome: "win",
    winnerOwner: result.winner,
    winnerHp,
    score: signedScore({
      winnerOwner: result.winner,
      winnerHp,
      startingHpByOwner,
    }),
    ticks: result.ticks,
    diagnostics: retainSnapshots
      ? routeDiagnostics(result, meleeMaster)
      : null,
  });
}


function routeDiagnostics(result, meleeMaster) {
  const meleeIds = new Set(result.world.units
    .filter(({ mechanics }) => mechanics.unit_master === meleeMaster)
    .map(({ referenceId }) => referenceId));
  const routeEvents = result.events.filter(({ actorId }) => meleeIds.has(actorId));
  const reasons = {};
  for (const row of routeEvents.filter(({ type }) => type === "pursuit-route-invalidated")) {
    reasons[row.reason] = (reasons[row.reason] ?? 0) + 1;
  }
  const modes = { direct: 0, oblique: 0, lateral: 0, away: 0, stall: 0 };
  let chaseTicks = 0;
  for (let index = 1; index < result.snapshots.length; index += 1) {
    const before = result.snapshots[index - 1];
    const after = result.snapshots[index];
    const afterById = new Map(after.units.map((unit) => [unit.referenceId, unit]));
    for (const mover of before.units) {
      if (!meleeIds.has(mover.referenceId) || !mover.alive
          || mover.action === "attacking"
          || !Number.isSafeInteger(mover.pursuitTargetId)) continue;
      const next = afterById.get(mover.referenceId);
      const target = before.units.find(({ referenceId }) => referenceId === mover.pursuitTargetId);
      if (!next?.alive || !target?.alive) continue;
      chaseTicks += 1;
      const dx = next.x - mover.x;
      const dy = next.y - mover.y;
      const distance = Math.hypot(dx, dy);
      if (distance <= 1e-9) {
        modes.stall += 1;
        continue;
      }
      const tx = target.x - mover.x;
      const ty = target.y - mover.y;
      const cosine = Math.max(-1, Math.min(1, (dx * tx + dy * ty)
        / (distance * Math.hypot(tx, ty))));
      const degrees = Math.acos(cosine) * 180 / Math.PI;
      if (degrees < 30) modes.direct += 1;
      else if (degrees < 60) modes.oblique += 1;
      else if (degrees <= 120) modes.lateral += 1;
      else modes.away += 1;
    }
  }
  return Object.freeze({
    routePlans: routeEvents.filter(({ type }) => type === "pursuit-route-planned").length,
    routeAdvances: routeEvents.filter(({ type }) => type === "pursuit-route-advanced").length,
    routeInvalidations: routeEvents.filter(({ type }) => (
      type === "pursuit-route-invalidated"
    )).length,
    invalidationReasons: Object.freeze(reasons),
    invalidationExamples: Object.freeze(routeEvents
      .filter(({ type, reason }) => type === "pursuit-route-invalidated"
        && reason === "no-progress")
      .slice(0, 12)
      .map(({
        tick, actorId, targetId, waypointX, waypointY,
        beforeX, beforeY, proposedX, proposedY, afterX, afterY,
        blockingReferenceIds,
      }) => Object.freeze({
        tick, actorId, targetId, waypointX, waypointY,
        beforeX, beforeY, proposedX, proposedY, afterX, afterY,
        blockingReferenceIds,
      }))),
    chaseUnitTicks: chaseTicks,
    modeShares: Object.freeze(Object.fromEntries(Object.entries(modes).map(([mode, count]) => [
      mode,
      chaseTicks === 0 ? null : count / chaseTicks,
    ]))),
  });
}


function summarizeSamples(samples) {
  const scores = samples.map(({ score }) => score).filter(Number.isFinite);
  return Object.freeze({
    ...summarize(scores),
    unresolved: samples.length - scores.length,
    samples: Object.freeze(samples.map(({ diagnostics: _diagnostics, ...sample }) => sample)),
  });
}


function summarize(scores) {
  if (scores.length === 0) {
    return Object.freeze({ runs: 0, mean: null, min: null, max: null, owner3WinRate: null });
  }
  return Object.freeze({
    runs: scores.length,
    mean: scores.reduce((total, score) => total + score, 0) / scores.length,
    min: Math.min(...scores),
    max: Math.max(...scores),
    owner3WinRate: scores.filter((score) => score > 0).length / scores.length,
  });
}
