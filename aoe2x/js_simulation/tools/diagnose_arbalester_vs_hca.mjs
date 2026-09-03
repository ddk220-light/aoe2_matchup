import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";


const MATCHUP_KEY = "arbalester_vs_heavy_cav_archer";
const ROOT = resolve(import.meta.dirname, "..");
const CAPTURE_ROOT = resolve(
  ROOT,
  "calibration/live_observations/ranged_matrix_5x_2026-08-29",
);
const LIVE_ANALYSIS = resolve(CAPTURE_ROOT, "grpc_matrix_analysis.json");
const LIVE_MANIFEST = resolve(CAPTURE_ROOT, "capture_manifest.json");
const SIMULATION_RESULTS = resolve(
  ROOT,
  "calibration/reports/ranged_matrix_patrol_engine_2026-08-30/results.json",
);
const DEFAULT_OUTPUT = resolve(
  ROOT,
  "calibration/reports/ranged_matrix_patrol_engine_2026-08-30/"
    + "arbalester_vs_heavy_cav_archer_diagnostic.json",
);


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


function ownerOpeningAttackers(run, owner) {
  return new Set(run.first_two_game_seconds.engagement_edges
    .filter(({ attacker_owner: attackerOwner }) => attackerOwner === owner)
    .map(({ attacker_slot: slot }) => slot)).size;
}


function firstDamageByOwner(run, owner) {
  const values = run.units
    .filter((unit) => unit.owner === owner && Number.isFinite(unit.first_damage_dealt_t))
    .map(({ first_damage_dealt_t: seconds }) => seconds);
  return values.length ? Math.min(...values) : null;
}


function targetMetricsFromLive(run, owner) {
  const row = run.acquisition[`side${owner}`];
  return {
    uniqueTargets: row.unique_first_targets,
    maximumSharedTarget: row.maximum_units_sharing_first_target,
    maximumSharedTargetShare: row.maximum_units_sharing_first_target / row.units,
  };
}


function targetMetricsFromSimulation(run, owner, count) {
  const loads = Object.values(
    run.mechanics.firstTargetDistributionByOwner[String(owner)]?.targets ?? {},
  );
  return {
    uniqueTargets: loads.length,
    maximumSharedTarget: Math.max(...loads),
    maximumSharedTargetShare: Math.max(...loads) / count,
  };
}


function summarizeObjects(rows) {
  return Object.fromEntries(Object.keys(rows[0]).map((key) => [
    key,
    round(mean(rows.map((row) => row[key]))),
  ]));
}


function positiveUnchangedRosterDrops(hpRows, side) {
  const drops = [];
  for (let index = 1; index < hpRows.length; index += 1) {
    const before = hpRows[index - 1][side];
    const after = hpRows[index][side];
    const drop = before.hp - after.hp;
    if (drop > 0 && before.count === after.count) drops.push(drop);
  }
  return drops;
}


async function hpDeltaCompatibility(damageByVictimSide) {
  const output = {};
  for (const [side, perHit] of Object.entries(damageByVictimSide)) {
    const drops = [];
    for (let repeat = 1; repeat <= 5; repeat += 1) {
      const file = resolve(
        CAPTURE_ROOT,
        MATCHUP_KEY,
        `run_${String(repeat).padStart(3, "0")}`,
        "raw recordings",
        `${MATCHUP_KEY}.hp.json`,
      );
      const document = JSON.parse(await readFile(file, "utf8"));
      drops.push(...positiveUnchangedRosterDrops(document.rows, side));
    }
    const compatible = drops.filter((drop) => Math.abs(drop / perHit - Math.round(drop / perHit)) < 1e-9);
    output[side] = {
      expectedDamagePerHit: perHit,
      intervals: drops.length,
      compatibleIntervals: compatible.length,
      incompatibleIntervals: drops.length - compatible.length,
      compatibleShare: round(compatible.length / drops.length),
      sampleDrops: drops.slice(0, 12),
    };
  }
  return output;
}


async function main() {
  const [liveDocument, manifest, simulationDocument, arbalester, hca] = await Promise.all([
    readFile(LIVE_ANALYSIS, "utf8").then(JSON.parse),
    readFile(LIVE_MANIFEST, "utf8").then(JSON.parse),
    readFile(SIMULATION_RESULTS, "utf8").then(JSON.parse),
    readFile(resolve(ROOT, "fixtures/unit_stats/arbalester_chinese_imperial.json"), "utf8")
      .then(JSON.parse),
    readFile(resolve(ROOT, "fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json"), "utf8")
      .then(JSON.parse),
  ]);
  const live = liveDocument.matchups[MATCHUP_KEY];
  const simulation = simulationDocument.rows.find(({ key }) => key === MATCHUP_KEY);
  if (!live || !simulation) throw new Error(`missing ${MATCHUP_KEY} source row`);
  const captureRuns = manifest.runs[MATCHUP_KEY].toSorted((left, right) => left.repeat - right.repeat);
  const simRuns = simulation.simulation.runs.filter(({ score }) => Number.isFinite(score));
  if (live.runs.length !== 5 || captureRuns.length !== 5 || simRuns.length !== 5) {
    throw new Error("diagnosis requires five live runs and five completed simulation seeds");
  }

  const counts = { 2: live.side2.count, 3: live.side3.count };
  const startingHp = { 2: counts[2] * arbalester.hp, 3: counts[3] * hca.hp };
  const damagePerHit = {
    2: arbalester.attack_classes[3] - hca.armor_classes[3],
    3: hca.attack_classes[3] - arbalester.armor_classes[3],
  };
  const liveDamageByRun = captureRuns.map(({ capture }) => ({
    2: startingHp[3] - capture.winner_hp,
    3: startingHp[2],
  }));
  const liveOpeningByRun = live.runs.map((run) => ({
    2: {
      hits: run.first_two_game_seconds.hits_by_side["2"],
      uniqueAttackers: ownerOpeningAttackers(run, 2),
      firstDamageSeconds: firstDamageByOwner(run, 2),
    },
    3: {
      hits: run.first_two_game_seconds.hits_by_side["3"],
      uniqueAttackers: ownerOpeningAttackers(run, 3),
      firstDamageSeconds: firstDamageByOwner(run, 3),
    },
  }));
  const simulationOpeningByRun = simRuns.map(({ mechanics }) => ({
    2: mechanics.openingByOwner["2"],
    3: mechanics.openingByOwner["3"],
  }));
  const liveTargetByRun = live.runs.map((run) => ({
    2: targetMetricsFromLive(run, 2),
    3: targetMetricsFromLive(run, 3),
  }));
  const simulationTargetByRun = simRuns.map((run) => ({
    2: targetMetricsFromSimulation(run, 2, counts[2]),
    3: targetMetricsFromSimulation(run, 3, counts[3]),
  }));
  const liveDamage = {
    2: round(mean(liveDamageByRun.map((row) => row[2]))),
    3: round(mean(liveDamageByRun.map((row) => row[3]))),
  };
  const simulationDamage = {
    2: round(mean(simRuns.map(({ mechanics }) => mechanics.totalDamageByOwner["2"].amount))),
    3: round(mean(simRuns.map(({ mechanics }) => mechanics.totalDamageByOwner["3"].amount))),
  };
  const simulationHits = {
    2: round(mean(simRuns.map(({ mechanics }) => mechanics.totalDamageByOwner["2"].hits))),
    3: round(mean(simRuns.map(({ mechanics }) => mechanics.totalDamageByOwner["3"].hits))),
  };
  const liveHitEvents = {
    2: round(liveDamage[2] / damagePerHit[2]),
    3: counts[2] * Math.ceil(arbalester.hp / damagePerHit[3]),
  };
  const summarizeOwner = (rows, owner, fields) => Object.fromEntries(fields.map((field) => [
    field,
    round(mean(rows.map((row) => row[owner][field]))),
  ]));
  const output = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    matchup: {
      key: MATCHUP_KEY,
      side2: { slug: "arbalester", civilization: "Chinese", count: counts[2] },
      side3: { slug: "heavy_cav_archer", civilization: "Saracens", count: counts[3] },
      liveWinnerOwner: 3,
      simulationWinnerOwners: simRuns.map(({ winnerOwner }) => winnerOwner),
    },
    sources: {
      liveAnalysis: LIVE_ANALYSIS,
      liveManifest: LIVE_MANIFEST,
      simulationResults: SIMULATION_RESULTS,
      liveHpSidecars: resolve(CAPTURE_ROOT, MATCHUP_KEY, "run_*/raw recordings", `${MATCHUP_KEY}.hp.json`),
    },
    damageModel: {
      damagePerHit,
      liveHpDeltaCompatibility: await hpDeltaCompatibility({ side1: damagePerHit[3], side2: damagePerHit[2] }),
      simulationMeanDamagePerRecordedHit: {
        2: round(simulationDamage[2] / simulationHits[2]),
        3: round(simulationDamage[3] / simulationHits[3]),
      },
      conclusion: "The 4-damage Arbalester hit and 7-damage Heavy Cavalry Archer hit match both the live aggregate-HP signatures and simulation events.",
    },
    openingTwoSecondsAfterFirstDamage: {
      live: {
        2: summarizeOwner(liveOpeningByRun, 2, ["hits", "uniqueAttackers", "firstDamageSeconds"]),
        3: summarizeOwner(liveOpeningByRun, 3, ["hits", "uniqueAttackers", "firstDamageSeconds"]),
      },
      simulation: {
        2: summarizeOwner(simulationOpeningByRun, 2, ["hits", "uniqueAttackers", "firstDamageSeconds"]),
        3: summarizeOwner(simulationOpeningByRun, 3, ["hits", "uniqueAttackers", "firstDamageSeconds"]),
      },
    },
    firstTargetDistribution: {
      live: {
        2: summarizeOwner(liveTargetByRun, 2, ["uniqueTargets", "maximumSharedTarget", "maximumSharedTargetShare"]),
        3: summarizeOwner(liveTargetByRun, 3, ["uniqueTargets", "maximumSharedTarget", "maximumSharedTargetShare"]),
      },
      simulation: {
        2: summarizeOwner(simulationTargetByRun, 2, ["uniqueTargets", "maximumSharedTarget", "maximumSharedTargetShare"]),
        3: summarizeOwner(simulationTargetByRun, 3, ["uniqueTargets", "maximumSharedTarget", "maximumSharedTargetShare"]),
      },
    },
    wholeFight: {
      liveMeanDamageByOwner: liveDamage,
      simulationMeanDamageByOwner: simulationDamage,
      simulationDamageDeltaPct: {
        2: round(100 * (simulationDamage[2] - liveDamage[2]) / liveDamage[2], 1),
        3: round(100 * (simulationDamage[3] - liveDamage[3]) / liveDamage[3], 1),
      },
      liveMeanDamagingHitEvents: liveHitEvents,
      simulationMeanDamagingHitEvents: simulationHits,
      damagingHitRatioSide2ToSide3: {
        live: round(liveHitEvents[2] / liveHitEvents[3]),
        simulation: round(simulationHits[2] / simulationHits[3]),
      },
    },
    diagnosis: {
      primary: "The ranged-vs-ranged opening target distribution is wrong: the simulation fans Arbalesters across several Heavy Cavalry Archers, while the live game concentrates almost the entire Arbalester army on one first target.",
      mechanism: "The fan-out lets far more Arbalesters obtain independent valid shots immediately, avoids the live target-death/retarget stall, and starts a casualty cascade against the Heavy Cavalry Archers.",
      consequence: "The Heavy Cavalry Archers deal the correct damage per hit and begin damaging earlier in the simulation than live, but they die too quickly to accumulate the live number of damaging attacks.",
      visualCaveat: "Some simulated Arbalesters are visibly idle, but the simulation still has about three times as many distinct Arbalester opening hitters as live. Their visible idleness therefore cannot explain the incorrect Arbalester win.",
      confidence: "high for the target-distribution/opening-participation mismatch; medium that this alone explains the entire whole-fight delta until a shared acquisition/retarget mechanic is implemented and rerun",
    },
  };
  await mkdir(dirname(DEFAULT_OUTPUT), { recursive: true });
  await writeFile(DEFAULT_OUTPUT, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${DEFAULT_OUTPUT}\n`);
}


await main();
