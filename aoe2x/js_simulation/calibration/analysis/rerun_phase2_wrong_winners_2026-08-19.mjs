import { readFile } from "node:fs/promises";

import { hashCanonicalJson } from "../../src/canonical-json.js";
import { createWorld, runWorld } from "../../src/combat/world.js";
import {
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";
import { signedScore } from "../../src/standard-units-comparison.js";
import {
  runPhase2Batch1Suite,
  writePhase2Batch1Outputs,
} from "../../tools/run_phase2_batch1_suite.mjs";


const ROOT = new URL("../../", import.meta.url);
const BASELINE_URL = new URL(
  "../reports/phase2_reachable_opening_body_formation_full_2026-08-19/results.json",
  import.meta.url,
);
const OUTPUT_URL = new URL(
  "../reports/phase2_wrong_winners_persistent_pursuit_2026-08-19/",
  import.meta.url,
);
const EXPECTED_ZIP_SHA256 =
  "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const SEED = 20260817;


const baseline = JSON.parse(await readFile(BASELINE_URL, "utf8"));
if (baseline.source?.archive?.zip_sha256 !== EXPECTED_ZIP_SHA256) {
  throw new Error("baseline report does not reference the authorized Phase 2 archive hash");
}

const rowIds = baseline.rows
  .filter((row) => row.comparison?.wrongStableWinner === true)
  .map((row) => row.id);
if (!rowIds.length || rowIds.length > 15 || new Set(rowIds).size !== rowIds.length) {
  throw new Error(`wrong-winner cohort must contain 1-15 unique rows, got ${rowIds.length}`);
}

const runLatestEngine = ({ row, sampleIndex, seed, context }) => {
  const baseScenario = scenarioFromPhase2Batch1Row({ row, sampleIndex, seed, context });
  const scenario = baseScenario.kiteOwner === null || baseScenario.kiteOwner === undefined
    ? baseScenario
    : Object.freeze({ ...baseScenario, persistentMeleePursuitRouting: true });
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
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    rowId: row.id,
    sampleIndex,
    seed,
    outcome: "win",
    winnerOwner: result.winner,
    winnerHp,
    score: signedScore({
      winnerOwner: result.winner,
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
};

const rawReport = await runPhase2Batch1Suite({
  root: ROOT,
  rowIds,
  samples: 1,
  volatileSamples: 1,
  seed: SEED,
  runImpl: runLatestEngine,
  onProgress: ({ completed, total, rowId }) => {
    process.stderr.write(`[${completed}/${total}] ${rowId}\n`);
  },
});

const report = Object.freeze({
  ...rawReport,
  source: Object.freeze({
    ...rawReport.source,
    cohortReport:
      "aoe2x/js_simulation/calibration/reports/phase2_reachable_opening_body_formation_full_2026-08-19/results.json",
    zipSha256VerifiedBeforeRun: EXPECTED_ZIP_SHA256,
  }),
  config: Object.freeze({
    ...rawReport.config,
    samples: 1,
    volatileSamples: 1,
    totalRunCap: 15,
    persistentMeleePursuitRouting: "enabled whenever the scenario has a kite owner",
  }),
});

await writePhase2Batch1Outputs(report, OUTPUT_URL);
process.stdout.write(`${JSON.stringify({
  cohortRows: rowIds.length,
  completedRuns: report.schedule.totalRuns - report.summary.unresolvedRuns,
  unresolvedRuns: report.summary.unresolvedRuns,
  remainingWrongWinners: report.summary.wrongStableWinnerCount,
  output: OUTPUT_URL.pathname,
})}\n`);
