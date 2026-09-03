import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";


const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUTPUT_DIRECTORY = path.join(
  ROOT,
  "calibration",
  "reports",
  "remaining_hp_percentage_points_2026-09-01",
);
const REPORT_SOURCE = "calibration/reports/remaining_hp_percentage_points_2026-09-01/calculation.json";
const VIEWER_BASE_URL = "https://starlight.tail82a190.ts.net/golden-map/";

const UNIT_HP = Object.freeze({
  arbalester: 40,
  champion: 70,
  elite_steppe: 100,
  halberdier: 60,
  hand_cannoneer: 40,
  heavy_cav_archer: 80,
  hussar: 95,
  paladin: 180,
});

const UNIT_LABEL = Object.freeze({
  arbalester: "Arbalester",
  champion: "Champion",
  elite_elephant: "Elite Battle Elephant",
  elite_steppe: "Elite Steppe Lancer",
  halberdier: "Halberdier",
  hand_cannoneer: "Hand Cannoneer",
  heavy_camel: "Heavy Camel Rider",
  heavy_cav_archer: "Heavy Caval Archer",
  heavy_scorpion: "Heavy Scorpion",
  hussar: "Hussar",
  imp_elite_skirm: "Elite Skirmisher",
  paladin: "Paladin",
  siege_onager: "Siege Onager",
});

const ORIGINAL_BASE = "calibration/reports/ranged_matrix_patrol_engine_2026-08-30/results.json";
const EXPANDED_BASE = "calibration/reports/expanded_roster_progress_2026-08-31/simulation_5x.json";
const EXPANDED_DEDICATED = "calibration/reports/expanded_roster_progress_2026-08-31/simulation_20x.json";
const OVERRIDE_FILES = Object.freeze([
  "calibration/reports/accepted_arb_hca_type_scoped_pressure_5x_2026-08-31/results.json",
  "calibration/reports/current_engine_paused_snapshot_5x_2026-08-31/results.json",
  "calibration/reports/post_heavy_camel_regression_2026-08-31/arbalester_vs_paladin/results.json",
  "calibration/reports/heavy_camel_focus_2026-08-31/ranged_surface_capacity3_elephant_5x.json",
  "calibration/reports/heavy_camel_focus_2026-08-31/ranged_surface_capacity3_hc_5x.json",
  "calibration/reports/heavy_camel_focus_2026-08-31/ranged_surface_capacity3_hca_5x.json",
  "calibration/reports/post_heavy_camel_regression_2026-08-31/paladin_vs_elephant.json",
]);
const FINAL_OVERRIDE_FILES = Object.freeze([
  "calibration/reports/scorpion_hca_hc_deep_dive_2026-09-01/candidate_reload_refund_5x_heavy_scorpion_vs_hand_cannoneer.json",
  "calibration/reports/scorpion_hca_hc_deep_dive_2026-09-01/final_reload_refund_5x_heavy_scorpion_vs_heavy_cav_archer.json",
]);


const round = (value, digits = 2) => Number(value.toFixed(digits));


function mean(values) {
  if (!values.length) throw new Error("cannot average an empty series");
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}


function labelForSide(side) {
  return `${side.civ} ${UNIT_LABEL[side.slug] ?? side.slug}`;
}


function normalizeSide(side, key) {
  const hp = side.hp ?? UNIT_HP[side.slug];
  if (!Number.isSafeInteger(side.count) || side.count < 1 || !Number.isFinite(hp) || hp <= 0) {
    throw new Error(`${key} has no valid starting-HP denominator for ${side.slug}`);
  }
  return Object.freeze({ ...side, hp, label: labelForSide(side), startingHp: side.count * hp });
}


function runsFromTape(row) {
  if (Array.isArray(row.live)) return row.live;
  if (!Array.isArray(row.tape?.winnerOwners) || !Array.isArray(row.tape?.winnerHp)) {
    throw new Error(`${row.key} has no live run series`);
  }
  return row.tape.winnerOwners.map((winnerOwner, index) => ({
    repeat: index + 1,
    winnerOwner,
    winnerHp: row.tape.winnerHp[index],
  }));
}


function runsFromSimulation(row) {
  if (Array.isArray(row.simulation)) return row.simulation;
  if (Array.isArray(row.simulation?.runs)) return row.simulation.runs;
  throw new Error(`${row.key} has no simulation run series`);
}


function ownerCounts(runs) {
  const counts = new Map();
  for (const run of runs) {
    if (run.winnerOwner !== 2 && run.winnerOwner !== 3) continue;
    counts.set(run.winnerOwner, (counts.get(run.winnerOwner) ?? 0) + 1);
  }
  return counts;
}


function modalOwner(runs) {
  const counts = [...ownerCounts(runs).entries()].sort((left, right) => right[1] - left[1]);
  if (!counts.length || (counts[1] && counts[0][1] === counts[1][1])) return null;
  return counts[0][0];
}


function winnerBreakdown(runs, side2, side3) {
  const counts = ownerCounts(runs);
  return [2, 3]
    .filter((owner) => (counts.get(owner) ?? 0) > 0)
    .map((owner) => `${owner === 2 ? side2.label : side3.label} ${counts.get(owner)}/${runs.length}`)
    .join(" · ");
}


function scoreRun(run, liveModalOwner, side2, side3) {
  if ((run.winnerOwner !== 2 && run.winnerOwner !== 3) || !Number.isFinite(run.winnerHp)) {
    return null;
  }
  const denominator = run.winnerOwner === 2 ? side2.startingHp : side3.startingHp;
  const direction = run.winnerOwner === liveModalOwner ? 1 : -1;
  return direction * (100 * run.winnerHp / denominator);
}


function representativeRun(simulationRuns, liveModalOwner, side2, side3, wrongWinner) {
  const scored = simulationRuns
    .map((run, index) => ({
      run,
      index,
      score: scoreRun(run, liveModalOwner, side2, side3),
    }))
    .filter(({ score }) => score !== null);
  const candidates = wrongWinner
    ? scored.filter(({ run }) => run.winnerOwner !== liveModalOwner)
    : scored;
  const pool = candidates.length ? candidates : scored;
  const target = mean(scored.map(({ score }) => score));
  return pool.toSorted((left, right) => (
    Math.abs(left.score - target) - Math.abs(right.score - target)
  ))[0];
}


async function readResult(relativePath) {
  const absolutePath = path.join(ROOT, relativePath);
  const document = JSON.parse(await readFile(absolutePath, "utf8"));
  const modifiedAt = (await stat(absolutePath)).mtime.toISOString();
  return Object.freeze({
    relativePath: relativePath.replaceAll("\\", "/"),
    generatedAt: document.generatedAt ?? modifiedAt,
    config: document.config ?? {},
    rows: document.rows ?? [],
  });
}


async function currentRerunFiles() {
  const relativeDirectory = "calibration/reports/scorpion_onager_current_engine_rerun_2026-09-01";
  return (await readdir(path.join(ROOT, relativeDirectory)))
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => `${relativeDirectory}/${name}`);
}


function applyDocument(rowsByKey, document) {
  for (const row of document.rows) {
    rowsByKey.set(row.key, Object.freeze({
      row,
      sourcePath: document.relativePath,
      sourceGeneratedAt: document.generatedAt,
      rangedOpportunityRetargetOwner: document.config.rangedOpportunityRetargetOwner ?? null,
    }));
  }
}


function evaluateEntry(entry) {
  const { row } = entry;
  const side2 = normalizeSide(row.side2, row.key);
  const side3 = normalizeSide(row.side3, row.key);
  const liveRuns = runsFromTape(row).filter(({ winnerOwner }) => winnerOwner === 2 || winnerOwner === 3);
  const simulationRuns = runsFromSimulation(row)
    .filter(({ winnerOwner }) => winnerOwner === 2 || winnerOwner === 3);
  const liveModalOwner = modalOwner(liveRuns);
  const simulationModalOwner = modalOwner(simulationRuns);
  if (liveModalOwner === null) throw new Error(`${row.key} has no unique live majority winner`);

  const liveScores = liveRuns.map((run) => scoreRun(run, liveModalOwner, side2, side3));
  const simulationScores = simulationRuns.map(
    (run) => scoreRun(run, liveModalOwner, side2, side3),
  );
  const liveScorePp = mean(liveScores);
  const simulationScorePp = mean(simulationScores);
  const deltaPp = simulationScorePp - liveScorePp;
  const absoluteDeltaPp = Math.abs(deltaPp);
  const wrongWinner = simulationModalOwner === null || simulationModalOwner !== liveModalOwner;
  const representative = representativeRun(
    simulationRuns,
    liveModalOwner,
    side2,
    side3,
    wrongWinner,
  );
  const wrongWinnerSeedNumbers = simulationRuns
    .filter(({ winnerOwner }) => winnerOwner !== liveModalOwner)
    .map((run, index) => run.openingSeed ?? index);
  const classification = wrongWinner
    ? "Wrong winner"
    : absoluteDeltaPp > 25
      ? ">25 pp"
      : absoluteDeltaPp > 10
        ? "10–25 pp"
        : "Pass";
  const expectedLabel = liveModalOwner === 2 ? side2.label : side3.label;
  const simulationLabel = simulationModalOwner === 2
    ? side2.label
    : simulationModalOwner === 3
      ? side3.label
      : "No unique majority";

  return Object.freeze({
    key: row.key,
    family: row.family,
    matchup: `${side2.label} vs ${side3.label}`,
    side2,
    side3,
    liveRuns: liveRuns.length,
    simulationRuns: simulationRuns.length,
    liveModalOwner,
    simulationModalOwner,
    expectedWinner: expectedLabel,
    simulationWinner: simulationLabel,
    liveOutcome: winnerBreakdown(liveRuns, side2, side3),
    simulationOutcome: winnerBreakdown(simulationRuns, side2, side3),
    liveScorePp: round(liveScorePp),
    simulationScorePp: round(simulationScorePp),
    deltaPp: round(deltaPp),
    absoluteDeltaPp: round(absoluteDeltaPp),
    wrongWinner,
    classification,
    representativeSeed: representative.run.openingSeed ?? representative.index,
    representativeWinnerOwner: representative.run.winnerOwner,
    representativeWinnerHp: round(representative.run.winnerHp),
    wrongWinnerSeedNumbers,
    sourcePath: entry.sourcePath,
    sourceGeneratedAt: entry.sourceGeneratedAt,
    rangedOpportunityRetargetOwner: entry.rangedOpportunityRetargetOwner,
  });
}


function catalogueRow(row) {
  const status = row.wrongWinner ? "wrong-winner" : "hp-delta";
  const issue = row.wrongWinner
    ? `simulation majority winner differs from live (${row.simulationOutcome})`
    : `${row.absoluteDeltaPp} percentage-point survivor-HP delta`;
  const viewerUrl = `https://starlight.tail82a190.ts.net/golden-map/?mode=problem-matchups&matchup=${row.key}&seed=${row.representativeSeed}`;
  return Object.freeze({
    id: row.key,
    label: `${row.matchup} (${row.side2.count} vs ${row.side3.count})`,
    family: row.family,
    status,
    issue,
    liveScore: row.liveScorePp,
    simulationScore: row.simulationScorePp,
    simulationScoreIsPartial: false,
    liveWinnerOwner: row.liveModalOwner,
    liveWinnerHpMean: null,
    simulationWinnerHpMean: null,
    relativeWinnerHpDeltaPct: null,
    remainingHpPercentagePointDelta: row.absoluteDeltaPp,
    resolvedSeeds: row.simulationRuns,
    timeoutSeeds: [],
    wrongWinnerSeeds: row.wrongWinnerSeedNumbers.length,
    wrongWinnerSeedNumbers: row.wrongWinnerSeedNumbers,
    representativeSeed: row.representativeSeed,
    representativeReason: row.wrongWinner
      ? "recorded wrong-winner seed"
      : "recorded seed nearest simulation mean remaining-HP%",
    representativeWinnerOwner: row.representativeWinnerOwner,
    representativeWinnerHp: row.representativeWinnerHp,
    viewerUrl,
    rangedOpportunityRetargetOwner: row.rangedOpportunityRetargetOwner,
    side2: {
      slug: row.side2.slug,
      civ: row.side2.civ,
      count: row.side2.count,
      label: UNIT_LABEL[row.side2.slug] ?? row.side2.slug,
    },
    side3: {
      slug: row.side3.slug,
      civ: row.side3.civ,
      count: row.side3.count,
      label: UNIT_LABEL[row.side3.slug] ?? row.side3.slug,
    },
  });
}


function artifactFor(calculation) {
  const { summary, rows } = calculation;
  const problemRows = rows
    .filter(({ wrongWinner, absoluteDeltaPp }) => wrongWinner || absoluteDeltaPp > 10)
    .toSorted((left, right) => right.absoluteDeltaPp - left.absoluteDeltaPp)
    .map((row, index) => ({
      rank: index + 1,
      matchup: row.matchup,
      category: row.classification,
      live_outcome: row.liveOutcome,
      simulation_outcome: row.simulationOutcome,
      live_score_pp: row.liveScorePp,
      simulation_score_pp: row.simulationScorePp,
      delta_signed_pp: row.deltaPp,
      delta_abs_pp: row.absoluteDeltaPp,
      live_runs: row.liveRuns,
      simulation_runs: row.simulationRuns,
      replay_viewer: `${VIEWER_BASE_URL}?mode=problem-matchups&matchup=${encodeURIComponent(row.key)}&seed=${row.representativeSeed}`,
      source_file: row.sourcePath,
    }));
  const chartRows = problemRows.slice(0, 15);
  const generatedAt = calculation.generatedAt;
  const source = {
    id: "remaining_hp_pp_calculation",
    label: "Consolidated remaining-HP percentage-point calculation",
    path: REPORT_SOURCE,
    query: {
      engine: "DuckDB",
      sql: `SELECT row.*\nFROM read_json_auto('${REPORT_SOURCE}') AS report,\nUNNEST(report.rows) AS t(row)\nWHERE row.classification IN ('Wrong winner', '>25 pp', '10–25 pp')\nORDER BY row.absoluteDeltaPp DESC;`,
      description: "Reads the consolidated per-matchup calculation, keeps every wrong-majority-winner row and every correct-winner row above the 10 percentage-point threshold, then ranks them by absolute gap.",
      tables_used: [REPORT_SOURCE],
      filters: ["classification is Wrong winner, >25 pp, or 10–25 pp"],
      metric_definitions: [
        "Run remaining HP % = winning army remaining HP / that army's initial total HP × 100.",
        "Live modal winner defines positive direction; opposite-side run wins are negative.",
        "Delta pp = simulation mean signed remaining-HP % − live mean signed remaining-HP %.",
        "Wrong winner = simulation modal winner differs from live modal winner.",
      ],
    },
  };
  return {
    surface: "report",
    manifest: {
      version: 1,
      surface: "report",
      title: "Remaining-HP Accuracy Recalculation",
      description: "AoE2 live-versus-simulation evaluation using percentage-point survivor HP deltas.",
      generatedAt,
      sources: [source],
      cards: [
        {
          id: "coverage",
          description: "Completed matchups included in the consolidated evidence set.",
          dataset: "headline",
          sourceId: source.id,
          metrics: [{ label: "Matchups evaluated", field: "coverage", format: "number" }],
        },
        {
          id: "wrong_winners",
          description: "Matchups whose simulation majority winner differs from live.",
          dataset: "headline",
          sourceId: source.id,
          metrics: [{ label: "Wrong winners", field: "wrong_winners", format: "number" }],
        },
        {
          id: "above_ten",
          description: "Correct-majority matchups above the 10 percentage-point target.",
          dataset: "headline",
          sourceId: source.id,
          metrics: [{ label: "Above 10 pp", field: "above_ten", format: "number" }],
        },
        {
          id: "above_twenty_five",
          description: "Correct-majority matchups above 25 percentage points; this is a subset of above 10 pp.",
          dataset: "headline",
          sourceId: source.id,
          metrics: [{ label: "Above 25 pp", field: "above_twenty_five", format: "number" }],
        },
      ],
      charts: [
        {
          id: "largest_deltas",
          title: "Largest survivor-HP score deltas",
          subtitle: "Absolute percentage-point gap; wrong-winner rows use the signed outcome scale.",
          type: "horizontalBar",
          dataset: "largest_deltas",
          sourceId: source.id,
          valueFormat: "number",
          unit: "pp",
          maxRows: 15,
          encodings: {
            x: { field: "matchup", type: "nominal", label: "Matchup" },
            y: { field: "delta_abs_pp", type: "quantitative", label: "Absolute delta (pp)" },
            tooltip: [
              { field: "category", type: "nominal", label: "Classification" },
              { field: "live_score_pp", type: "quantitative", label: "Live score (pp)" },
              { field: "simulation_score_pp", type: "quantitative", label: "Simulation score (pp)" },
            ],
          },
          referenceLines: [
            { value: 10, label: "10 pp target" },
            { value: 25, label: "25 pp severe" },
          ],
        },
      ],
      tables: [
        {
          id: "problem_matchups",
          title: "Wrong-winner and above-target matchups",
          subtitle: "Newest completed multi-seed result selected for each matchup; sorted by absolute percentage-point gap.",
          dataset: "problem_matchups",
          sourceId: source.id,
          density: "compact",
          layout: "full",
          defaultSort: { field: "delta_abs_pp", direction: "desc" },
          columns: [
            { field: "matchup", label: "Matchup", type: "text" },
            { field: "category", label: "Category", type: "text" },
            { field: "live_outcome", label: "Live outcome", type: "text" },
            { field: "simulation_outcome", label: "Simulation outcome", type: "text" },
            { field: "live_score_pp", label: "Live HP score", type: "number", format: "number", unit: "%" },
            { field: "simulation_score_pp", label: "Simulation HP score", type: "number", format: "number", unit: "%" },
            { field: "delta_signed_pp", label: "Signed delta", type: "number", format: "number", unit: "pp", movement: true },
            { field: "delta_abs_pp", label: "Absolute delta", type: "number", format: "number", unit: "pp" },
            { field: "replay_viewer", label: "Replay viewer", type: "text" },
          ],
        },
      ],
      blocks: [
        { id: "title", type: "markdown", body: "# Remaining-HP Accuracy Recalculation" },
        {
          id: "executive_summary",
          type: "markdown",
          sourceId: source.id,
          body: `## Executive Summary\n\n- **${summary.wrongWinnerMatchups} matchups have the wrong majority winner.** Winner direction remains a separate hard failure.\n- **${summary.aboveTenCorrectWinnerMatchups} correct-winner matchups exceed 10 percentage points.** This replaces the old raw-HP relative-error threshold.\n- **${summary.aboveTwentyFiveCorrectWinnerMatchups} correct-winner matchups exceed 25 percentage points.** These are the severe HP-shape misses and are a subset of the above-10 group.`,
        },
        { id: "headline_metrics", type: "metric-strip", cardIds: ["coverage", "wrong_winners", "above_ten", "above_twenty_five"] },
        {
          id: "definition",
          type: "markdown",
          body: "## The new metric compares like with like\n\nEach run is converted to remaining HP as a share of that winning army’s starting HP before runs are averaged. The live majority winner defines the positive direction; a run won by the other side is negative. The reported delta is simulation mean minus live mean in percentage points. Wrong-winner rows are classified separately and are not counted in the HP-only threshold totals.",
        },
        {
          id: "largest_gap_context",
          type: "markdown",
          sourceId: source.id,
          body: "## The remaining misses are concentrated\n\nThe ranked view separates outcome errors from HP-shape errors. Use the 10 pp line as the normal acceptance target and 25 pp as the severe-error line; exact outcomes and scores are in the table below.",
        },
        { id: "largest_gap_chart", type: "chart", chartId: "largest_deltas", layout: "full" },
        {
          id: "problem_detail_context",
          type: "markdown",
          body: "## Exact problem-matchup lookup\n\nThe table contains every wrong-majority matchup plus every correct-majority matchup above 10 pp. Rows above 25 pp also appear in the above-10 group by definition.",
        },
        { id: "problem_detail", type: "table", tableId: "problem_matchups", layout: "full" },
        {
          id: "next_steps",
          type: "markdown",
          body: "## Recommended next step\n\nUse this score in every comparison generator and viewer catalogue. Prioritize wrong winners first, then correct-winner rows above 25 pp, then the remaining 10–25 pp rows. Do not tune rows that already fall below 10 pp.",
        },
        {
          id: "further_questions",
          type: "markdown",
          body: "## Further question\n\nA fresh full-matrix rerun would make every row reflect one identical engine revision. Until then, this report intentionally uses the newest completed multi-seed file available for each matchup rather than substituting newer one-seed smoke checks.",
        },
        {
          id: "caveats",
          type: "markdown",
          body: "## Caveats and assumptions\n\nLive and simulation run counts vary between five and twenty. Majority-winner classification is used for matchups with naturally mixed outcomes. The starting-HP denominator includes only the two testing armies, not Player 4’s trigger units. Percentage-point thresholds are applied only when live and simulation have the same majority winner.",
        },
      ],
    },
    snapshot: {
      version: 1,
      generatedAt,
      status: "ready",
      datasets: {
        headline: [{
          coverage: summary.matchups,
          wrong_winners: summary.wrongWinnerMatchups,
          above_ten: summary.aboveTenCorrectWinnerMatchups,
          above_twenty_five: summary.aboveTwentyFiveCorrectWinnerMatchups,
        }],
        largest_deltas: chartRows,
        problem_matchups: problemRows,
        all_matchups: rows.map((row) => ({
          matchup: row.matchup,
          family: row.family,
          live_outcome: row.liveOutcome,
          simulation_outcome: row.simulationOutcome,
          live_score_pp: row.liveScorePp,
          simulation_score_pp: row.simulationScorePp,
          delta_signed_pp: row.deltaPp,
          delta_abs_pp: row.absoluteDeltaPp,
          classification: row.classification,
          source_file: row.sourcePath,
        })),
      },
    },
    sources: [source],
  };
}


async function main() {
  const rowsByKey = new Map();
  const selectedDocuments = [];
  for (const file of [ORIGINAL_BASE, EXPANDED_BASE, EXPANDED_DEDICATED]) {
    const document = await readResult(file);
    selectedDocuments.push(document);
    applyDocument(rowsByKey, document);
  }
  for (const file of [
    ...OVERRIDE_FILES,
    ...await currentRerunFiles(),
    ...FINAL_OVERRIDE_FILES,
  ]) {
    const document = await readResult(file);
    selectedDocuments.push(document);
    applyDocument(rowsByKey, document);
  }

  const rows = [...rowsByKey.values()]
    .map(evaluateEntry)
    .toSorted((left, right) => (
      Number(right.wrongWinner) - Number(left.wrongWinner)
      || right.absoluteDeltaPp - left.absoluteDeltaPp
      || left.key.localeCompare(right.key)
    ));
  if (rows.length !== 64) {
    throw new Error(`expected 64 consolidated matchups, found ${rows.length}`);
  }
  const wrongWinners = rows.filter(({ wrongWinner }) => wrongWinner);
  const aboveTen = rows.filter(({ wrongWinner, absoluteDeltaPp }) => (
    !wrongWinner && absoluteDeltaPp > 10
  ));
  const aboveTwentyFive = aboveTen.filter(({ absoluteDeltaPp }) => absoluteDeltaPp > 25);
  const generatedAt = new Date().toISOString();
  const calculation = {
    schemaVersion: 1,
    generatedAt,
    metric: {
      runScore: "winner remaining HP / that winner's starting army HP * 100; negative when the run winner differs from the live majority winner",
      comparison: "simulation mean run score - live mean run score, in percentage points",
      threshold: "absolute percentage-point delta",
      wrongWinner: "simulation majority winner differs from live majority winner",
    },
    sourceSelection: selectedDocuments.map(({ relativePath, generatedAt: sourceGeneratedAt }) => ({
      path: relativePath,
      generatedAt: sourceGeneratedAt,
    })),
    summary: {
      matchups: rows.length,
      wrongWinnerMatchups: wrongWinners.length,
      aboveTenCorrectWinnerMatchups: aboveTen.length,
      aboveTwentyFiveCorrectWinnerMatchups: aboveTwentyFive.length,
      withinTenCorrectWinnerMatchups: rows.filter(({ wrongWinner, absoluteDeltaPp }) => (
        !wrongWinner && absoluteDeltaPp <= 10
      )).length,
    },
    wrongWinnerKeys: wrongWinners.map(({ key }) => key),
    aboveTenKeys: aboveTen.map(({ key }) => key),
    aboveTwentyFiveKeys: aboveTwentyFive.map(({ key }) => key),
    rows,
  };
  const catalogue = {
    schemaVersion: 2,
    generatedAt,
    repositoryBase: "C:\\dev\\aoe2\\aoe2_matchup\\aoe2x\\",
    comparisonResults: path.join(OUTPUT_DIRECTORY, "calculation.json"),
    rows: rows
      .filter(({ wrongWinner, absoluteDeltaPp }) => wrongWinner || absoluteDeltaPp > 10)
      .map(catalogueRow),
  };
  const artifact = artifactFor(calculation);

  await mkdir(OUTPUT_DIRECTORY, { recursive: true });
  await Promise.all([
    writeFile(path.join(OUTPUT_DIRECTORY, "calculation.json"), `${JSON.stringify(calculation, null, 2)}\n`),
    writeFile(path.join(OUTPUT_DIRECTORY, "viewer_problem_catalogue.json"), `${JSON.stringify(catalogue, null, 2)}\n`),
    writeFile(path.join(OUTPUT_DIRECTORY, "artifact.json"), `${JSON.stringify(artifact, null, 2)}\n`),
  ]);
  console.log(JSON.stringify(calculation.summary));
  for (const row of rows.filter(({ wrongWinner, absoluteDeltaPp }) => (
    wrongWinner || absoluteDeltaPp > 10
  ))) {
    console.log(`${row.classification.padEnd(12)} ${String(row.absoluteDeltaPp).padStart(6)} pp  ${row.key}`);
  }
}


await main();
