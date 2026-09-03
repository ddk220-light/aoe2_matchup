import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { unitBySlug } from "../src/unit-registry.js";


const SIM_ROOT = fileURLToPath(new URL(
  "../calibration/reports/expanded_roster_5x_current_engine_2026-08-31/",
  import.meta.url,
));
const REPORT_ROOT = fileURLToPath(new URL(
  "../calibration/reports/expanded_roster_progress_2026-08-31/",
  import.meta.url,
));
const CAPTURE_ROOT = fileURLToPath(new URL(
  "../calibration/live_observations/expanded_roster_5x_2026-08-31/",
  import.meta.url,
));
const CAPTURE_MANIFEST = resolve(CAPTURE_ROOT, "capture_manifest.json");
const DEDICATED_CAPTURE_ROOT = fileURLToPath(new URL(
  "../calibration/live_observations/heavy_scorpion_vs_arbalester_20x_2026-08-31/",
  import.meta.url,
));
const DEDICATED_CAPTURE_MANIFEST = resolve(DEDICATED_CAPTURE_ROOT, "capture_manifest.json");
const DEDICATED_KEY = "heavy_scorpion_vs_arbalester";
const REPORT_RESULTS = resolve(REPORT_ROOT, "results.json");
const VIEWER_CATALOGUE = resolve(REPORT_ROOT, "viewer_problem_catalogue.json");
const DATA_APP_SNAPSHOT = resolve(REPORT_ROOT, "app", "src", "data.json");
const TAILNET_BASE = "https://starlight.tail82a190.ts.net/golden-map/";
const REQUIRED_LIVE_RUNS = 5;
const REQUIRED_SIM_SEEDS = 5;


async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}


function resultCandidates(key) {
  const candidates = key === DEDICATED_KEY
    ? [resolve(REPORT_ROOT, "simulation_20x.json")]
    : [resolve(REPORT_ROOT, "simulation_5x.json")];
  if (key === "heavy_scorpion_vs_paladin" || key === "heavy_scorpion_vs_elite_steppe") {
    candidates.push(resolve(SIM_ROOT, "experiments", `${key}_retarget_5x.json`));
  }
  candidates.push(resolve(REPORT_ROOT, "singles", `${key}.json`));
  candidates.push(resolve(SIM_ROOT, `${key}.json`));
  return candidates;
}


async function selectedResult(key) {
  for (const path of resultCandidates(key)) {
    if (!await exists(path)) continue;
    const report = JSON.parse(await readFile(path, "utf8"));
    const row = report.rows?.find((candidate) => candidate.key === key);
    if (row) return { path, report, row };
  }
  throw new Error(`no simulator comparison result is available for completed matchup ${key}`);
}


function sideLabel(row, owner) {
  const side = owner === 2 ? row.side2 : row.side3;
  const unit = unitBySlug(side.slug);
  return `${side.civ} ${unit?.label ?? side.slug}`;
}


function winnerCounts(runs) {
  return runs.reduce((counts, run) => {
    counts.set(run.winnerOwner, (counts.get(run.winnerOwner) ?? 0) + 1);
    return counts;
  }, new Map());
}


function resultLabel(row, runs) {
  const counts = winnerCounts(runs);
  return [...counts.entries()]
    .sort(([left], [right]) => left - right)
    .map(([owner, count]) => `${sideLabel(row, owner)} ${count}/${runs.length}`)
    .join(" · ");
}


function signedMean(runs) {
  return runs.reduce((total, run) => (
    total + (run.winnerOwner === 2 ? run.winnerHp : -run.winnerHp)
  ), 0) / runs.length;
}


function nearestToMean(runs) {
  const mean = runs.reduce((total, run) => total + run.winnerHp, 0) / runs.length;
  return [...runs].sort((left, right) => (
    Math.abs(left.winnerHp - mean) - Math.abs(right.winnerHp - mean)
      || left.openingSeed - right.openingSeed
  ))[0];
}


function classify(row) {
  const liveOwners = row.live.map(({ winnerOwner }) => winnerOwner);
  const sim = row.simulation.filter(({ winnerOwner }) => Number.isSafeInteger(winnerOwner));
  const stableLiveWinner = liveOwners.every((owner) => owner === liveOwners[0])
    ? liveOwners[0] : null;
  const wrong = stableLiveWinner === null
    ? [] : sim.filter(({ winnerOwner }) => winnerOwner !== stableLiveWinner);
  const delta = row.simulationSummary.relativeWinnerHpDelta;
  const accepted = stableLiveWinner !== null
    && sim.length > 0
    && wrong.length === 0
    && delta < 0.10;
  const provisional = sim.length < REQUIRED_SIM_SEEDS;
  let status;
  if (stableLiveWinner === null) status = "Live mixed";
  else if (wrong.length > 0) status = "Wrong winner";
  else if (!(delta < 0.10)) status = "HP miss";
  else status = provisional ? "Provisional pass" : "Pass";
  return { accepted, delta, provisional, sim, stableLiveWinner, status, wrong };
}


function issueText(row, classification) {
  if (classification.stableLiveWinner === null) {
    return `live winner varies across ${row.live.length} runs`;
  }
  if (classification.wrong.length > 0) {
    return `${classification.wrong.length}/${classification.sim.length} simulator seeds pick the wrong winner`;
  }
  if (!(classification.delta < 0.10)) {
    return `${(classification.delta * 100).toFixed(1)}% mean survivor-HP delta`;
  }
  return "provisional simulator sample";
}


function problemRow(row, classification) {
  let representative;
  let representativeReason;
  if (classification.wrong.length > 0) {
    representative = classification.wrong[0];
    representativeReason = "wrong-winner seed";
  } else {
    representative = nearestToMean(classification.sim);
    representativeReason = classification.stableLiveWinner === null
      ? "completed seed nearest simulation mean for mixed live result"
      : "winner-HP seed nearest simulation mean";
  }
  const url = new URL(TAILNET_BASE);
  url.searchParams.set("mode", "problem-matchups");
  url.searchParams.set("matchup", row.key);
  url.searchParams.set("seed", String(representative.openingSeed));
  return {
    id: row.key,
    label: `${sideLabel(row, 2)} (${row.side2.count}) vs ${sideLabel(row, 3)} (${row.side3.count})`,
    family: row.family,
    status: classification.wrong.length > 0 ? "wrong-winner"
      : classification.stableLiveWinner === null ? "live-mixed" : "hp-delta",
    issue: issueText(row, classification),
    liveScore: signedMean(row.live),
    simulationScore: signedMean(classification.sim),
    simulationScoreIsPartial: classification.provisional,
    liveWinnerOwner: classification.stableLiveWinner,
    liveWinnerHpMean: row.liveSummary.winnerHp.mean,
    simulationWinnerHpMean: row.simulationSummary.winnerHp.mean,
    relativeWinnerHpDeltaPct: classification.delta * 100,
    resolvedSeeds: classification.sim.length,
    timeoutSeeds: [],
    wrongWinnerSeeds: classification.wrong.length,
    wrongWinnerSeedNumbers: classification.wrong.map(({ openingSeed }) => openingSeed),
    representativeSeed: representative.openingSeed,
    representativeReason,
    representativeWinnerOwner: representative.winnerOwner,
    representativeWinnerHp: representative.winnerHp,
    viewerUrl: url.href,
    rangedOpportunityRetargeting: "generic-in-range-opportunity",
    side2: {
      slug: row.side2.slug,
      civ: row.side2.civ,
      count: row.side2.count,
      label: unitBySlug(row.side2.slug)?.label ?? row.side2.slug,
    },
    side3: {
      slug: row.side3.slug,
      civ: row.side3.civ,
      count: row.side3.count,
      label: unitBySlug(row.side3.slug)?.label ?? row.side3.slug,
    },
  };
}


const capture = JSON.parse(await readFile(CAPTURE_MANIFEST, "utf8"));
const completedRegularKeys = capture.matchup_keys.filter((key) => (
  (capture.runs?.[key] ?? []).length >= REQUIRED_LIVE_RUNS
));
let dedicatedCapture = null;
if (await exists(DEDICATED_CAPTURE_MANIFEST)) {
  dedicatedCapture = JSON.parse(await readFile(DEDICATED_CAPTURE_MANIFEST, "utf8"));
}
const dedicatedComplete = (dedicatedCapture?.runs?.[DEDICATED_KEY] ?? []).length >= 20;
const completedKeys = [
  ...completedRegularKeys,
  ...(dedicatedComplete ? [DEDICATED_KEY] : []),
];
const captureManifests = [
  CAPTURE_MANIFEST,
  ...(dedicatedComplete ? [DEDICATED_CAPTURE_MANIFEST] : []),
];
const selected = [];
for (const key of completedKeys) selected.push(await selectedResult(key));

const generatedAt = new Date().toISOString();
const comparisonRows = selected.map(({ path, report, row }) => {
  const classification = classify(row);
  const problem = classification.accepted ? null : problemRow(row, classification);
  return {
    key: row.key,
    family: row.family,
    matchup: `${sideLabel(row, 2)} vs ${sideLabel(row, 3)}`,
    roster: `${row.side2.count} vs ${row.side3.count}`,
    liveResult: resultLabel(row, row.live),
    simulationResult: resultLabel(row, classification.sim),
    liveMeanHp: row.liveSummary.winnerHp.mean,
    simulationMeanHp: row.simulationSummary.winnerHp.mean,
    hpDeltaPct: classification.delta * 100,
    status: classification.status,
    accepted: classification.accepted,
    provisional: classification.provisional,
    liveRuns: row.live.length,
    simulationSeeds: classification.sim.length,
    viewerUrl: problem?.viewerUrl ?? "",
    simulationSource: relative(REPORT_ROOT, path).replaceAll("\\", "/"),
    captureRuns: row.live.map(({ repeat, framesBin, framesSha256 }) => (
      `run_${String(repeat).padStart(3, "0")}: ${framesBin} [sha256 ${framesSha256}]`
    )).join(" | "),
    retargetRule: "all ranged owners take an in-range opportunity over an out-of-range lock",
  };
});
const accepted = comparisonRows.filter(({ accepted: value }) => value);
const provisional = comparisonRows.filter(({ provisional: value }) => value);
const problems = selected.flatMap(({ row }) => {
  const classification = classify(row);
  return classification.accepted ? [] : [problemRow(row, classification)];
});

const aggregate = {
  schemaVersion: 1,
  generatedAt,
  source: {
    captureManifest: CAPTURE_MANIFEST,
    captureManifests,
    captureRoot: CAPTURE_ROOT,
    ...(dedicatedComplete ? { dedicatedCaptureRoot: DEDICATED_CAPTURE_ROOT } : {}),
    selectedComparisonFiles: selected.map(({ path }) => path),
  },
  config: {
    requiredLiveRuns: REQUIRED_LIVE_RUNS,
    dedicatedRequiredLiveRuns: 20,
    expectedSimulationSeeds: REQUIRED_SIM_SEEDS,
    rangedOpportunityRetargeting: "generic-in-range-opportunity",
    acceptance: "stable correct winner and <10% mean survivor-HP delta",
  },
  summary: {
    completedMatchups: comparisonRows.length,
    completedRegularMatchups: completedRegularKeys.length,
    completedDedicatedMatchups: dedicatedComplete ? 1 : 0,
    completedLiveRuns: comparisonRows.reduce((total, row) => total + row.liveRuns, 0),
    acceptedMatchups: accepted.length,
    provisionalRows: provisional.length,
    problemMatchups: problems.length,
    remainingRegularMatchups: Math.max(0, 49 - completedRegularKeys.length),
    remainingDedicatedMatchups: dedicatedComplete ? 0 : 1,
  },
  rows: comparisonRows,
};

const catalogue = {
  schemaVersion: 2,
  generatedAt,
  repositoryBase: fileURLToPath(new URL("../../", import.meta.url)),
  comparisonResults: REPORT_RESULTS,
  rows: problems,
};

const selectedFiles = selected.map(({ path }) => path);
const snapshot = {
  id: "34b8e22a-5bbc-4ddd-88a7-8f2ebdf67ea9",
  surface: "report",
  title: `Expanded roster progress: ${comparisonRows.length} completed matchups`,
  generatedAt,
  status: "observed",
  filters: [],
  report: { asOf: "2026-08-31" },
  queries: {
    expanded_comparisons: {
      rows: comparisonRows,
      source: {
        label: "Expanded-roster live captures and current simulator comparisons",
        files: [...captureManifests, ...selectedFiles],
        filters: [
          "Regular matchups require five archived live runs; the reserved Heavy Scorpion–Arbalester row requires its dedicated twenty-run set.",
          "Acceptance requires a stable correct winner and less than 10% mean survivor-HP delta.",
          "The selected owner-2 ranged opportunity retarget rule is used where a retarget result exists; each row records its exact simulator source.",
        ],
        metricDefinitions: [
          {
            label: "Live mean winner HP",
            definition: "Arithmetic mean of final surviving HP across the five archived live game runs, regardless of which side won a mixed-outcome set.",
            variable: "liveMeanHp",
            componentIds: ["expanded-summary", "expanded-comparison-table", "expanded-scope"],
            sourceLineage: [{ files: captureManifests }],
          },
          {
            label: "Simulation mean winner HP",
            definition: "Arithmetic mean of final surviving HP across the resolved current-engine opening seeds listed for the row.",
            variable: "simulationMeanHp",
            componentIds: ["expanded-summary", "expanded-comparison-table", "expanded-scope"],
            sourceLineage: [{ files: selectedFiles }],
          },
          {
            label: "Winner-HP delta",
            definition: "Absolute difference between simulation mean winner HP and live mean winner HP, divided by live mean winner HP. Mixed live winners make this descriptive rather than an acceptance measure.",
            formula: "abs(simulationMeanHp - liveMeanHp) / liveMeanHp",
            dependencies: ["simulationMeanHp", "liveMeanHp"],
            componentIds: ["expanded-summary", "expanded-comparison-table", "expanded-scope"],
            sourceLineage: [{ files: [...captureManifests, ...selectedFiles] }],
          },
        ],
        evidenceFlow: [
          "Read the current capture manifest and retain only matchups with five completed runs.",
          "Use each row's archived frames.bin path and recorded run outcome as live evidence.",
          "Compare against the selected current-engine output and classify winner correctness plus survivor-HP delta.",
        ],
      },
    },
  },
};

await mkdir(dirname(REPORT_RESULTS), { recursive: true });
await Promise.all([
  writeFile(REPORT_RESULTS, `${JSON.stringify(aggregate, null, 2)}\n`),
  writeFile(VIEWER_CATALOGUE, `${JSON.stringify(catalogue, null, 2)}\n`),
  writeFile(DATA_APP_SNAPSHOT, `${JSON.stringify(snapshot, null, 2)}\n`),
]);

process.stdout.write(`${JSON.stringify(aggregate.summary)}\n`);
