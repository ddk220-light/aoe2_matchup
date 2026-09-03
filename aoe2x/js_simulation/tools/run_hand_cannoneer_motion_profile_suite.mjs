import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  compareRow,
  loadStandardUnitsTruth,
  runTapeConditioned,
  summarizeTape,
} from "../src/standard-units-comparison.js";


const ROOT = new URL("../", import.meta.url);
const BASELINE = new URL(
  "../calibration/reports/standard_units_simulation_results_2026-08-08.json",
  import.meta.url,
);
const HCA_CONTROL = new URL(
  "../calibration/fixtures/standard_units/hca_vs_champion_pre_hc_escape_control_2026-08-08.json",
  import.meta.url,
);
const EXPECTED_ARCHIVE_SHA256 = "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D";
const HC_MASTER = 5;
const SCREEN_SAMPLES = 5;
const VOLATILE_SAMPLES = 100;
const MELEE_MASTERS = new Set([359, 441, 567, 1903, 330, 569, 1134, 1372]);
const HCA_VS_CHAMPION = "Heavy Cavalry Archer vs Champion";
const CANDIDATES = Object.freeze({
  measured_spacing: Object.freeze({
    label: "HC-only formation spacing 0.35 tiles",
    experiment: Object.freeze({ formationSpacingTiles: 0.35 }),
  }),
  translated_offsets: Object.freeze({
    label: "HC-only rigid translation of existing formation offsets",
    experiment: Object.freeze({ formationMotion: "translated_offsets" }),
  }),
  opening_volley: Object.freeze({
    label: "HC-only opening attack on the first 0.667-second order clock",
    experiment: Object.freeze({ firstBeatTick: 40 }),
  }),
  translated_opening: Object.freeze({
    label: "HC-only rigid formation translation plus measured opening volley",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 40,
    }),
  }),
  immediate_opening: Object.freeze({
    label: "HC-only opening attack active from the first simulation tick",
    experiment: Object.freeze({ firstBeatTick: 1 }),
  }),
  translated_immediate: Object.freeze({
    label: "HC-only rigid formation translation plus immediate opening attack",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
    }),
  }),
  closing_opening: Object.freeze({
    label: "HC-only immediate opening order that closes to firing range",
    experiment: Object.freeze({
      firstBeatTick: 1,
      openingVolley: "close_to_fire",
    }),
  }),
  translated_closing: Object.freeze({
    label: "HC-only rigid formation translation plus closing opening volley",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      openingVolley: "close_to_fire",
    }),
  }),
  persistent_volleys: Object.freeze({
    label: "HC-only immediate opening plus close-to-fire pursuit on every volley",
    experiment: Object.freeze({
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
    }),
  }),
  translated_persistent: Object.freeze({
    label: "HC-only rigid translation plus persistent close-to-fire volleys",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
    }),
  }),
  translated_persistent_escape: Object.freeze({
    label: "HC-only translated persistent volleys with contact escape steering",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      kitedEscape: true,
    }),
  }),
  translated_persistent_capture: Object.freeze({
    label: "HC-only translated persistent volleys with contact target capture",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      chaseCapture: true,
    }),
  }),
  translated_persistent_half_wave: Object.freeze({
    label: "HC-only translated persistent volleys with measured half-roster melee wave",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      meleeWave: "half_roster",
    }),
  }),
  translated_persistent_locations: Object.freeze({
    label: "HC-only translated persistent volleys with tape-location melee approach",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
      meleeWave: "location_approach",
    }),
  }),
  translated_persistent_measured_phase: Object.freeze({
    label: "HC-only translated persistent volleys on the measured 0.2/1.33-second phase",
    experiment: Object.freeze({
      formationMotion: "translated_offsets",
      firstBeatTick: 12,
      moveOffsetTicks: Object.freeze([68, 148, 228]),
      volleyPursuit: "close_to_fire",
    }),
  }),
});


export function physicsCandidate(name) {
  const candidate = CANDIDATES[name];
  if (!candidate) throw new RangeError(`unknown HC physics candidate: ${name}`);
  return {
    name,
    label: candidate.label,
    experiment: { ...candidate.experiment },
  };
}


export function evaluateFiveSampleGate(rows, hcaIdentity) {
  const baselineBandError = sum(rows.map(({ baseline }) => baseline.bandError));
  const candidateBandError = sum(rows.map(({ candidate }) => candidate.bandError));
  const stableWinnerFailures = rows.filter(({ candidate }) => candidate.wrongStableWinner);
  const goodRowRegressions = rows.filter(({ baseline, candidate }) => (
    baseline.bandError <= 10 && candidate.bandError - baseline.bandError > 10
  ));
  const unresolvedRuns = sum(rows.map(({ candidate }) => candidate.unresolvedRuns));
  const expandVolatile = hcaIdentity
    && unresolvedRuns === 0
    && stableWinnerFailures.length === 0
    && goodRowRegressions.length === 0
    && candidateBandError < baselineBandError;
  return Object.freeze({
    expandVolatile,
    baselineBandError,
    candidateBandError,
    improvement: baselineBandError - candidateBandError,
    stableWinnerFailures: stableWinnerFailures.map(({ matchup }) => matchup),
    goodRowRegressions: goodRowRegressions.map(({ matchup }) => matchup),
    unresolvedRuns,
    hcaIdentity,
    over25: rows.filter(({ candidate }) => candidate.bandError > 25)
      .map(({ matchup, candidate }) => ({ matchup, delta: candidate.bandError })),
  });
}


export function handCannoneerRows(truth) {
  return truth.rows.filter((row) => (
    row.side2.master === HC_MASTER && MELEE_MASTERS.has(row.side3.master)
  ));
}


export async function runMotionProfileSuite({
  candidate = physicsCandidate("measured_spacing"),
} = {}) {
  const [truth, baseline, hcaControl] = await Promise.all([
    loadStandardUnitsTruth(ROOT),
    readFile(BASELINE, "utf8").then(JSON.parse),
    readFile(HCA_CONTROL, "utf8").then(JSON.parse),
  ]);
  requireAuthorizedSources(truth, baseline, hcaControl);
  const seed = baseline.config.seed;
  const sourceRows = handCannoneerRows(truth);
  const samplesByRow = new Map();

  for (const row of sourceRows) {
    samplesByRow.set(row.id, await runSamples(
      row, 0, SCREEN_SAMPLES, seed, candidate.experiment,
    ));
  }
  const screenRows = comparisonRows(sourceRows, baseline, samplesByRow);
  const hcaGate = await runHcaIdentityGate(truth, hcaControl);
  const screen = evaluateFiveSampleGate(screenRows, hcaGate.identical);

  if (screen.expandVolatile) {
    for (const row of sourceRows) {
      if (!summarizeTape(row).volatile) continue;
      samplesByRow.get(row.id).push(
        ...await runSamples(
          row, SCREEN_SAMPLES, VOLATILE_SAMPLES, seed, candidate.experiment,
        ),
      );
    }
  }

  const rows = comparisonRows(sourceRows, baseline, samplesByRow);
  const finalGate = evaluateFiveSampleGate(rows, hcaGate.identical);
  const accepted = screen.expandVolatile && finalGate.expandVolatile;
  return Object.freeze({
    schemaVersion: 1,
    source: truth.archive,
    candidate: Object.freeze({
      name: candidate.name,
      label: candidate.label,
      experiment: Object.freeze({ ...candidate.experiment }),
    }),
    config: Object.freeze({
      screenSamples: SCREEN_SAMPLES,
      volatileSamples: VOLATILE_SAMPLES,
      seed,
      exactCanonicalStarts: true,
    }),
    screen,
    volatileExpansionRan: screen.expandVolatile,
    accepted,
    acceptance: finalGate,
    rows: Object.freeze(rows),
    hcaGate,
  });
}


async function runSamples(row, start, end, seed, experiment) {
  const samples = [];
  for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
    samples.push(await runTapeConditioned(
      ROOT,
      row,
      sampleIndex,
      seed,
      experiment,
    ));
  }
  return samples;
}


function comparisonRows(sourceRows, baseline, samplesByRow) {
  return sourceRows.map((row) => {
    const tape = summarizeTape(row);
    const samples = samplesByRow.get(row.id);
    const baselineRow = baseline.rows.find(({ id }) => id === row.id);
    if (!baselineRow) throw new Error(`baseline missing ${row.id}`);
    return Object.freeze({
      id: row.id,
      matchup: row.matchup,
      tape,
      baseline: baselineRow.comparison,
      candidate: compareRow({ row, tape, simulationScores: samples.map(({ score }) => score) }),
      samples: Object.freeze([...samples]),
    });
  });
}


async function runHcaIdentityGate(truth, hcaControl) {
  const row = truth.rows.find(({ matchup }) => matchup === HCA_VS_CHAMPION);
  if (!row || hcaControl.matchup !== HCA_VS_CHAMPION) {
    throw new Error("HCA-vs-Champion identity row is missing");
  }
  const samples = [];
  for (let sampleIndex = 0; sampleIndex < SCREEN_SAMPLES; sampleIndex += 1) {
    const current = await runTapeConditioned(ROOT, row, sampleIndex, hcaControl.seed);
    const before = hcaControl.samples[sampleIndex];
    samples.push(Object.freeze({
      sampleIndex,
      scoreIdentical: current.score === before.score,
      finalStateHashIdentical: current.finalStateHash === before.final_state_hash,
      eventLogHashIdentical: current.eventLogHash === before.event_log_hash,
      before: Object.freeze({
        score: before.score,
        finalStateHash: before.final_state_hash,
        eventLogHash: before.event_log_hash,
      }),
      current: Object.freeze({
        score: current.score,
        finalStateHash: current.finalStateHash,
        eventLogHash: current.eventLogHash,
      }),
    }));
  }
  return Object.freeze({
    matchup: HCA_VS_CHAMPION,
    identical: samples.every((sample) => (
      sample.scoreIdentical
      && sample.finalStateHashIdentical
      && sample.eventLogHashIdentical
    )),
    samples: Object.freeze(samples),
  });
}


function requireAuthorizedSources(truth, baseline, hcaControl) {
  const hashes = [
    truth?.archive?.zip_sha256,
    baseline?.source?.zip_sha256,
    hcaControl?.archive_zip_sha256,
  ];
  if (hashes.some((hash) => hash !== EXPECTED_ARCHIVE_SHA256)) {
    throw new Error("HC motion-profile suite requires the verified standard-units archive");
  }
}


export function renderMotionProfileMarkdown(report) {
  const lines = [
    "# Hand Cannoneer tape-motion profile A/B results",
    "",
    `- Decision: **${report.accepted ? "ACCEPT" : "REJECT"}**`,
    `- Source SHA-256: \`${report.source.zip_sha256}\``,
    `- Candidate: ${report.candidate.label}`,
    "- Starts: exact canonical positions imported from each authorized `frames.bin` run",
    `- Five-sample screen: ${report.screen.expandVolatile ? "PASS" : "FAIL"}`,
    `- 100-sample volatile expansion: ${report.volatileExpansionRan ? "ran" : "skipped by gate"}`,
    `- HCA-vs-Champion hashes bit-identical: ${report.hcaGate.identical ? "yes" : "no"}`,
    `- Aggregate HC tape-band error: ${fmt(report.acceptance.baselineBandError)} -> ${fmt(report.acceptance.candidateBandError)} (${fmt(report.acceptance.improvement)} better)`,
    "",
    "| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Timeouts |",
    "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ...report.rows.map((row) => `| ${row.matchup} | ${row.candidate.simulationRuns} | ${fmt(row.tape.mean)} / ${fmt(row.tape.min)}…${fmt(row.tape.max)} | ${fmt(row.baseline.mean)} | ${fmt(row.candidate.mean)} | ${fmt(row.baseline.bandError)} | ${fmt(row.candidate.bandError)} | ${row.candidate.unresolvedRuns} |`),
    "",
    "## Gate failures and greater-than-25-point deltas",
    "",
    report.acceptance.stableWinnerFailures.length
      ? `- Wrong stable winners: ${report.acceptance.stableWinnerFailures.join(", ")}`
      : "- Wrong stable winners: none.",
    report.acceptance.goodRowRegressions.length
      ? `- Greater-than-10-point regressions on good rows: ${report.acceptance.goodRowRegressions.join(", ")}`
      : "- Greater-than-10-point regressions on good rows: none.",
    report.acceptance.unresolvedRuns
      ? `- Unresolved simulations: ${report.acceptance.unresolvedRuns}.`
      : "- Unresolved simulations: none.",
    ...report.acceptance.over25.map(({ matchup, delta }) => (
      `- ${matchup}: ${fmt(delta)} points outside the tape band.`
    )),
    "",
    report.accepted
      ? "The candidate passed the full gate and is eligible for product-profile generation."
      : "The candidate remains calibration-only; the generated product profile is unchanged.",
  ];
  return `${lines.join("\n")}\n`;
}


export async function main(argv = process.argv.slice(2)) {
  if (argv.length > 1) {
    throw new Error("usage: run_hand_cannoneer_motion_profile_suite.mjs [measured_spacing|translated_offsets|opening_volley|translated_opening|immediate_opening|translated_immediate|closing_opening|translated_closing|persistent_volleys|translated_persistent|translated_persistent_escape|translated_persistent_capture|translated_persistent_half_wave|translated_persistent_locations|translated_persistent_measured_phase]");
  }
  const candidate = physicsCandidate(argv[0] ?? "measured_spacing");
  const outputStem = candidate.name === "measured_spacing"
    ? "hand_cannoneer_motion_profile_results_2026-08-09"
    : `hand_cannoneer_${candidate.name}_results_2026-08-09`;
  const outputJson = new URL(`../calibration/reports/${outputStem}.json`, import.meta.url);
  const outputMarkdown = new URL(`../calibration/reports/${outputStem}.md`, import.meta.url);
  const report = await runMotionProfileSuite({ candidate });
  await mkdir(new URL("../calibration/reports/", import.meta.url), { recursive: true });
  await Promise.all([
    writeFile(outputJson, `${JSON.stringify(report, null, 2)}\n`, "utf8"),
    writeFile(outputMarkdown, renderMotionProfileMarkdown(report), "utf8"),
  ]);
  return report;
}


function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}


function fmt(value) {
  return Number.isFinite(value) ? Number(value.toFixed(3)).toString() : "—";
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const report = await main();
  console.log(renderMotionProfileMarkdown(report));
  if (!report.accepted) process.exitCode = 1;
}
