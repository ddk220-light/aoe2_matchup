import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";


const REPORT_DIR = dirname(fileURLToPath(import.meta.url));
const RESULTS_PATH = resolve(REPORT_DIR, "results.json");
const ANALYSIS_PATH = resolve(REPORT_DIR, "analysis.json");
const ARTIFACT_PATH = resolve(REPORT_DIR, "artifact.json");
const GENERATED_AT = "2026-08-17T22:19:37.000Z";


const results = JSON.parse(await readFile(RESULTS_PATH, "utf8"));


function round(value, digits = 2) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}


function winnerFor(row, score) {
  if (!Number.isFinite(score)) return "Unresolved";
  return score > 0 ? row.side3.unit : row.side2.unit;
}


function rowView(row) {
  const simulationMean = row.comparison.mean;
  const signedDelta = Number.isFinite(simulationMean)
    ? simulationMean - row.tape.mean
    : null;
  const absoluteDelta = Number.isFinite(signedDelta) ? Math.abs(signedDelta) : null;
  const tapeClassification = row.tape.volatile ? "Knife edge" : "Stable";
  const tapeWinner = row.tape.volatile ? "Knife edge" : winnerFor(row, row.tape.mean);
  const simulationWinner = winnerFor(row, simulationMean);
  const winnerStatus = row.tape.volatile
    ? "Knife edge — no stable-winner failure"
    : row.comparison.simulationRuns === 0
      ? "Unresolved"
      : row.comparison.wrongStableWinner
        ? "Wrong winner"
        : "Winner matched";
  return Object.freeze({
    id: row.id,
    subject: humanize(row.subjectSlug),
    opponent: humanize(row.opponentSlug),
    matchup: row.matchup,
    ratio: `${row.side2.count}v${row.side3.count}`,
    tapeClassification,
    tapeWinner,
    simulationWinner,
    tapeRuns: row.tape.scoredRuns,
    tapeMean: round(row.tape.mean),
    tapeMin: round(row.tape.min),
    tapeMax: round(row.tape.max),
    simulationRuns: row.comparison.simulationRuns,
    unresolvedRuns: row.comparison.unresolvedRuns,
    simulationMean: round(simulationMean),
    simulationMin: round(row.comparison.min),
    simulationMax: round(row.comparison.max),
    signedDelta: round(signedDelta),
    absoluteDelta: round(absoluteDelta),
    tapeBandError: round(row.comparison.bandError),
    winnerStatus,
    wrongStableWinner: row.comparison.wrongStableWinner,
  });
}


function humanize(slug) {
  return slug
    .split("_")
    .map((part) => part === "cav" ? "Cav" : part[0].toUpperCase() + part.slice(1))
    .join(" ");
}


function aggregate(rows, field, labelField) {
  return [...new Set(rows.map((row) => row[field]))].map((key) => {
    const group = rows.filter((row) => row[field] === key);
    const resolved = group.filter((row) => Number.isFinite(row.absoluteDelta));
    const deltas = resolved.map((row) => row.absoluteDelta);
    return Object.freeze({
      [labelField]: humanize(key),
      rows: group.length,
      meanAbsoluteDelta: round(deltas.reduce((sum, value) => sum + value, 0) / deltas.length),
      maximumAbsoluteDelta: round(Math.max(...deltas)),
      wrongStableWinners: group.filter((row) => row.wrongStableWinner).length,
      rowsOver25: group.filter((row) => row.absoluteDelta > 25).length,
      fullyUnresolved: group.filter((row) => row.simulationRuns === 0).length,
      insideTapeBand: group.filter((row) => row.tapeBandError === 0).length,
    });
  }).sort((left, right) => (
    right.wrongStableWinners - left.wrongStableWinners
      || right.meanAbsoluteDelta - left.meanAbsoluteDelta
  ));
}


const rows = results.rows.map(rowView);
const stableRows = rows.filter((row) => row.tapeClassification === "Stable");
const stableWinnerMatches = stableRows.filter((row) => row.winnerStatus === "Winner matched").length;
const fullyUnresolvedRows = rows.filter((row) => row.simulationRuns === 0);
const partialUnresolvedRows = rows.filter((row) => (
  row.simulationRuns > 0 && row.unresolvedRuns > 0
));
const wrongWinnerRows = rows
  .filter((row) => row.wrongStableWinner)
  .sort((left, right) => (
    (right.absoluteDelta ?? Number.POSITIVE_INFINITY)
      - (left.absoluteDelta ?? Number.POSITIVE_INFINITY)
  ));
const largeDeltaRows = rows
  .filter((row) => row.absoluteDelta > 25)
  .sort((left, right) => right.absoluteDelta - left.absoluteDelta);
const subjectSummary = aggregate(rows, "subject", "subject");
const opponentSummary = aggregate(rows, "opponent", "opponent");


const analysis = Object.freeze({
  generatedAt: GENERATED_AT,
  sourceArchiveSha256: "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6",
  headline: Object.freeze({
    goldenRows: results.summary.rows,
    subjects: results.summary.subjects,
    simulationAttempts: results.summary.totalRuns,
    resolvedAttempts: results.summary.resolvedRuns,
    stableRows: stableRows.length,
    stableWinnerMatches,
    stableWinnerAgreementPercent: round(100 * stableWinnerMatches / stableRows.length, 1),
    wrongStableWinners: results.summary.wrongStableWinnerCount,
    rowsOver25: results.summary.rowsOver25PointDelta,
    rowsInsideTapeBand: results.summary.rowsInsideTapeBand,
    fullyUnresolvedRows: results.summary.fullyUnresolvedRows,
    unresolvedAttempts: results.summary.unresolvedRuns,
    meanAbsoluteMeanDelta: round(results.summary.meanAbsoluteMeanDelta),
    medianAbsoluteMeanDelta: round(results.summary.medianAbsoluteMeanDelta),
    maximumAbsoluteMeanDelta: round(results.summary.maximumAbsoluteMeanDelta),
  }),
  chartMap: Object.freeze([
    Object.freeze({
      section: "Opponent-level accuracy",
      question: "Which standard opponents expose the largest aggregate gaps?",
      type: "bar",
      fields: ["opponent", "meanAbsoluteDelta"],
      takeaway: "Paladin and Heavy Cavalry Archer are the hardest resolved opponent lanes.",
    }),
    Object.freeze({
      section: "Unit-family triage",
      question: "Which Phase-2 subjects should be investigated first?",
      type: "bar",
      fields: ["subject", "meanAbsoluteDelta"],
      takeaway: "War Wagon is the largest outlier; Keshik is the only other subject with two stable failures.",
    }),
  ]),
  datasets: Object.freeze({
    wrongWinnerRows,
    largeDeltaRows,
    fullyUnresolvedRows,
    partialUnresolvedRows,
    subjectSummary,
    opponentSummary,
    allRows: rows,
  }),
});


const sources = Object.freeze([
  Object.freeze({
    id: "phase2-results",
    label: "Completed Phase 2 Batch 1 current-engine benchmark",
    path: "aoe2x/js_simulation/calibration/reports/phase2_batch1_current_engine_2026-08-17/results.json",
    query: Object.freeze({
      language: "sql",
      engine: "portable-snapshot",
      sql: "SELECT opponent, rows, meanAbsoluteDelta, maximumAbsoluteDelta, wrongStableWinners, rowsOver25, fullyUnresolved, insideTapeBand FROM opponent_summary ORDER BY wrongStableWinners DESC, meanAbsoluteDelta DESC; SELECT subject, rows, meanAbsoluteDelta, maximumAbsoluteDelta, wrongStableWinners, rowsOver25, fullyUnresolved, insideTapeBand FROM subject_summary ORDER BY wrongStableWinners DESC, meanAbsoluteDelta DESC; SELECT * FROM wrong_winner_rows ORDER BY absoluteDelta DESC; SELECT * FROM large_delta_rows ORDER BY absoluteDelta DESC; SELECT * FROM unresolved_rows ORDER BY unresolvedRuns DESC; SELECT * FROM all_rows ORDER BY absoluteDelta DESC;",
      description: "Queries the reviewed report datasets produced reproducibly by build_report.mjs from the completed recoverable benchmark results.",
      tables_used: Object.freeze([
        "aoe2x/js_simulation/calibration/reports/phase2_batch1_current_engine_2026-08-17/results.json",
        "aoe2x/js_simulation/calibration/reports/phase2_batch1_current_engine_2026-08-17/analysis.json",
      ]),
      filters: Object.freeze([
        "All 120 exact Phase 2 Batch 1 golden rows",
        "Exact tape starting positions and unit-count ratios",
        "Five simulation samples for stable rows",
        "Historical completed run used 100 samples for eight split-winner tape rows",
        "Maximum 9,000 simulation ticks per attempt",
      ]),
      metric_definitions: Object.freeze({
        signed_outcome_score: "Winner remaining HP divided by that winner's starting HP, multiplied by 100. Positive means owner 3 won; negative means owner 2 won.",
        absolute_mean_delta: "Absolute difference between the mean simulation signed outcome score and the mean tape signed outcome score for the exact golden row.",
        wrong_stable_winner: "The simulation mean has the opposite sign from a non-volatile tape mean, or the simulation row produced no resolved score.",
        knife_edge: "A tape row whose recorded repeats contain winners on both sides. It is excluded from stable-winner failure counts.",
        tape_band_error: "Distance from the simulation mean to the nearest edge of the observed tape score range; zero means the simulation mean is inside that range.",
      }),
    }),
  }),
  Object.freeze({
    id: "phase2-truth",
    label: "Phase 2 Batch 1 tape truth fixture",
    path: "aoe2x/js_simulation/calibration/fixtures/phase2/batch1_truth.json",
    query: Object.freeze({
      language: "javascript",
      description: "Imports exact matchup ratios, canonical starting units, tape repeat outcomes, and provenance from the authorized Phase 2 archive.",
      tables_used: Object.freeze([
        "aoe2x/js_simulation/calibration/fixtures/phase2/batch1_truth.json",
      ]),
      filters: Object.freeze([
        "First twenty Phase-2 subject units",
        "Six recorded standard opponents per subject",
        "Authorized project-local archive only",
      ]),
    }),
  }),
  Object.freeze({
    id: "phase2-archive",
    label: "Authorized Phase 2 golden archive",
    path: "aoe2x/js_simulation/calibration/source/aoe2_golden_phase2_WITH_TAPES.zip",
    sha256: "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6",
  }),
]);


const artifact = Object.freeze({
  surface: "report",
  manifest: Object.freeze({
    version: 1,
    surface: "report",
    title: "Phase 2 Batch 1: tape versus simulation",
    description: "Current JavaScript engine accuracy across the first twenty unique and regional units against six standard opponents.",
    generatedAt: GENERATED_AT,
    blocks: Object.freeze([
      Object.freeze({ id: "title", type: "markdown", layout: "full", body: "# Phase 2 Batch 1: tape versus simulation" }),
      Object.freeze({
        id: "technical-summary",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## The engine gets most stable winners right, but four failure clusters remain\n\nAcross **120 exact golden rows**, the engine matches the stable tape winner on **100 of 112 rows (89.3%)**. Row-level outcome strength is usually reasonably close: median absolute mean delta is **10.91 points**, while **18 rows** exceed 25 points. The actionable failures are **nine resolved wrong-winner rows**, **three fully unresolved rows**, and one partially unresolved knife-edge row. The largest miss is Elite War Wagon versus Paladin: tape favors Paladin at **+35.44**, while simulation strongly favors War Wagon at **−83.33**, a **118.77-point delta**.",
      }),
      Object.freeze({
        id: "opponent-finding",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Fast ranged and heavy cavalry opponents expose the broadest gaps\n\nPaladin and Heavy Cavalry Archer lanes have the highest resolved mean absolute deltas, **19.53** and **19.12** points respectively, with three stable-winner failures each. Elite Battle Elephant also has three failed rows, but those are non-convergence failures rather than incorrect resolved winners. This split suggests separate workstreams: engagement/kiting interactions for HCA and Paladin, and termination or low-damage combat progress for Elephant rows.",
      }),
      Object.freeze({ id: "opponent-chart", type: "chart", layout: "full", chartId: "opponent-delta-chart" }),
      Object.freeze({
        id: "wrong-winner-finding",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Nine resolved rows pick the wrong winner; three more never finish\n\nThe resolved flips are not one universal balance drift. HCA reverses the tape against Boyar, Gbeto, and Woad Raider; Keshik loses two tape-favored melee outcomes; and War Wagon versus Paladin reverses by the largest margin in the batch. The three Elephant rows below are marked unresolved because all five attempts reached the 9,000-tick cap, so they should be treated as engine-completion failures rather than simulated victories.",
      }),
      Object.freeze({ id: "wrong-winner-table", type: "table", layout: "full", tableId: "wrong-winner-table" }),
      Object.freeze({
        id: "large-delta-finding",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Ten additional rows keep the winner but miss outcome strength by more than 25 points\n\nThere are **18 resolved rows above the 25-point threshold**. Eight are also wrong-winner rows, leaving ten cases where the correct side wins but with materially different surviving HP. Two of those ten are split-winner tape rows and should remain labeled knife-edge rather than winner failures. They still matter for calibration because their mean outcome lies far from the observed tape mean.",
      }),
      Object.freeze({ id: "large-delta-table", type: "table", layout: "full", tableId: "large-delta-table" }),
      Object.freeze({
        id: "subject-finding",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## War Wagon is the clear first investigation; Keshik is the second cross-matchup signal\n\nWar Wagon has two failed stable rows, including the largest resolved miss and one fully unresolved Elephant row. Keshik is the only other subject with two stable-winner failures. Longbowman and Mangudai each have two rows over 25 points but no winner flips, so they are lower priority than the units whose simulated winner is wrong.",
      }),
      Object.freeze({ id: "subject-chart", type: "chart", layout: "full", chartId: "subject-delta-chart" }),
      Object.freeze({ id: "subject-table", type: "table", layout: "full", tableId: "subject-summary-table" }),
      Object.freeze({
        id: "nonconvergence-finding",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Non-convergence is concentrated and reproducible\n\nAll five attempts time out for Conquistador versus Elite Battle Elephant, Plumed Archer versus Elite Battle Elephant, and War Wagon versus Elite Battle Elephant. Gbeto versus Heavy Scorpion resolves 98 of 100 historical attempts and times out twice; because its tape winners split, it remains a knife-edge row. In total, **1,343 of 1,360 attempts resolve (98.8%)**, but the three repeatable all-timeout rows must be fixed before this batch can be called complete.",
      }),
      Object.freeze({ id: "unresolved-table", type: "table", layout: "full", tableId: "unresolved-table" }),
      Object.freeze({
        id: "definitions",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Scope and metric definitions\n\nThe cohort is the first **20 Phase-2 units**, each tested only against the **six standard opponents recorded in the authorized golden archive**, for **120 exact matchup rows**. Counts and starting coordinates come directly from each golden row. Signed outcome score is surviving winner HP as a percentage of that side's starting HP: positive means owner 3 won and negative means owner 2 won. Absolute mean delta compares the row's mean simulation score with the row's mean tape score. A tape-band error of zero means the simulation mean falls inside the min–max range observed across tape repeats.",
      }),
      Object.freeze({
        id: "methodology",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-truth",
        body: "## Method used for this comparison\n\nThe archive hash was verified before import. Every simulation uses the tape's canonical roster, side assignment, unit-count ratio, and starting positions on the golden map. The current checked-out engine runs cohesive navigation, mechanics-derived kiting clocks, attack-move melee openings, zero melee engagement dwell, reach-derived wedge transit, and a 9,000-tick cap. Stable rows ran five deterministic samples. This completed historical run used 100 samples for eight split-winner tape rows; the runner has since been changed to enforce a 15-sample maximum for future volatile rows.",
      }),
      Object.freeze({
        id: "limitations",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Limitations and robustness\n\nThis is a first-pass outcome comparison, not yet a mechanics diagnosis for every failure. Most stable rows have one to three recorded tape repeats, so the tape mean is a precise result for this corpus rather than an estimate of the game's full random distribution. Simulation samples vary acquisition ordering but are frequently deterministic in final score. The 25-point threshold is a triage rule, not a statistical confidence boundary. Volatile tape rows are never counted as wrong stable winners. The completed 100-sample volatile results remain valid historical evidence, but future runs will stop at 15 and report knife-edge status.",
      }),
      Object.freeze({
        id: "next-steps",
        type: "markdown",
        layout: "full",
        body: "## Recommended next investigations\n\n1. Fix the three all-timeout Elephant rows without changing already-resolved Elephant controls.\n2. Diagnose War Wagon versus Paladin first; it is the largest and most decisive outcome reversal.\n3. Compare HCA engagement traces against Boyar, Gbeto, and Woad Raider, which all flip in HCA's favor in simulation.\n4. Inspect Keshik versus Champion and Paladin as a shared melee durability or engagement signal.\n5. Treat same-winner rows above 25 as secondary calibration work after winner and completion failures are resolved.",
      }),
      Object.freeze({
        id: "further-questions",
        type: "markdown",
        layout: "full",
        body: "## Questions the next tape pass should answer\n\nFor the unresolved Elephant rows, is damage actually occurring too slowly, or are units failing to maintain valid targets? For the HCA flips, does the tape show more successful melee contacts, fewer ranged firing cycles, or both? For War Wagon versus Paladin, is the main gap projectile behavior, kiting cadence, target concentration, or Paladin surround quality? Those trace-level checks will distinguish general physics gaps from missing unit-specific mechanics before any engine change is made.",
      }),
      Object.freeze({
        id: "complete-results",
        type: "markdown",
        layout: "full",
        sourceId: "phase2-results",
        body: "## Complete row-level results\n\nThe final audit table contains every exact golden row, including rows that already match closely. Use the tape class and winner-status columns to distinguish stable winner agreement from split-winner knife-edge evidence; use absolute delta and tape-band error to assess outcome-strength calibration.",
      }),
      Object.freeze({ id: "all-rows-table", type: "table", layout: "full", tableId: "all-rows-table" }),
    ]),
    charts: Object.freeze([
      Object.freeze({
        id: "opponent-delta-chart",
        title: "Mean absolute outcome delta by standard opponent",
        description: "Twenty Phase-2 subject rows per opponent; unresolved rows excluded from the mean.",
        type: "bar",
        intent: "comparison",
        question: "Which opponent lanes produce the largest row-level outcome errors?",
        rationale: "Six categorical bars make opponent-level concentration directly comparable.",
        dataset: "opponent_summary",
        encodings: Object.freeze({ x: Object.freeze({ field: "opponent" }), y: Object.freeze({ field: "meanAbsoluteDelta" }) }),
        labels: Object.freeze({ values: "all" }),
        sourceId: "phase2-results",
      }),
      Object.freeze({
        id: "subject-delta-chart",
        title: "Mean absolute outcome delta by Phase-2 subject",
        description: "Six golden opponent rows per subject; unresolved rows excluded from the mean.",
        type: "bar",
        intent: "ranking",
        question: "Which new units have the largest average calibration gap?",
        rationale: "A ranked categorical bar chart supports unit-by-unit triage in one consistent view.",
        dataset: "subject_summary",
        encodings: Object.freeze({ x: Object.freeze({ field: "subject" }), y: Object.freeze({ field: "meanAbsoluteDelta" }) }),
        labels: Object.freeze({ values: "all" }),
        sourceId: "phase2-results",
      }),
    ]),
    tables: Object.freeze([
      tableSpec("wrong-winner-table", "Stable winner failures", "All twelve stable-row failures, including three fully unresolved rows.", "wrong_winner_rows"),
      tableSpec("large-delta-table", "Resolved rows above 25 outcome points", "All eighteen resolved rows whose simulation mean is more than 25 points from tape.", "large_delta_rows"),
      Object.freeze({
        id: "subject-summary-table",
        title: "Phase-2 subject accuracy summary",
        description: "Six golden opponent rows per subject; sorted by stable-winner failures, then mean absolute delta.",
        dataset: "subject_summary",
        columns: Object.freeze([
          column("subject", "Subject"),
          column("meanAbsoluteDelta", "Mean abs. delta", "number"),
          column("maximumAbsoluteDelta", "Max abs. delta", "number"),
          column("wrongStableWinners", "Stable failures", "number"),
          column("rowsOver25", "Rows >25", "number"),
          column("fullyUnresolved", "Unresolved rows", "number"),
          column("insideTapeBand", "Inside tape band", "number"),
        ]),
        defaultSort: Object.freeze({ field: "wrongStableWinners", direction: "desc" }),
        sourceId: "phase2-results",
      }),
      Object.freeze({
        id: "unresolved-table",
        title: "Rows with unresolved simulation attempts",
        description: "Three rows time out in all five attempts; one knife-edge row times out twice in 100 historical attempts.",
        dataset: "unresolved_rows",
        columns: Object.freeze([
          column("matchup", "Matchup"),
          column("ratio", "Ratio"),
          column("tapeClassification", "Tape class"),
          column("tapeWinner", "Tape outcome"),
          column("unresolvedRuns", "Unresolved", "number"),
          column("totalAttempts", "Attempts", "number"),
        ]),
        defaultSort: Object.freeze({ field: "unresolvedRuns", direction: "desc" }),
        sourceId: "phase2-results",
      }),
      Object.freeze({
        id: "all-rows-table",
        title: "All 120 tape-versus-simulation rows",
        description: "Exact audit table for the complete Phase-2 Batch-1 corpus.",
        dataset: "all_rows",
        density: "dense",
        columns: Object.freeze([
          column("matchup", "Matchup"),
          column("ratio", "Ratio"),
          column("tapeClassification", "Tape class"),
          column("tapeWinner", "Tape outcome"),
          column("simulationWinner", "Simulation outcome"),
          column("tapeMean", "Tape mean", "number"),
          column("simulationMean", "Simulation mean", "number"),
          column("absoluteDelta", "Abs. delta", "number"),
          column("tapeBandError", "Band error", "number"),
          column("winnerStatus", "Status"),
          column("unresolvedRuns", "Unresolved", "number"),
        ]),
        defaultSort: Object.freeze({ field: "absoluteDelta", direction: "desc" }),
        sourceId: "phase2-results",
      }),
    ]),
    sources,
  }),
  snapshot: Object.freeze({
    version: 1,
    status: "ready",
    generatedAt: GENERATED_AT,
    datasets: Object.freeze({
      opponent_summary: opponentSummary,
      subject_summary: subjectSummary,
      wrong_winner_rows: wrongWinnerRows,
      large_delta_rows: largeDeltaRows,
      unresolved_rows: [...fullyUnresolvedRows, ...partialUnresolvedRows].map((row) => Object.freeze({
        ...row,
        totalAttempts: row.simulationRuns + row.unresolvedRuns,
      })),
      all_rows: rows,
    }),
    accessIssues: Object.freeze([]),
  }),
  sources,
});


function column(field, label, format = undefined) {
  return Object.freeze({ field, label, ...(format ? { format } : {}) });
}


function tableSpec(id, title, description, dataset) {
  return Object.freeze({
    id,
    title,
    description,
    dataset,
    density: "dense",
    columns: Object.freeze([
      column("matchup", "Matchup"),
      column("ratio", "Ratio"),
      column("tapeClassification", "Tape class"),
      column("tapeWinner", "Tape outcome"),
      column("simulationWinner", "Simulation outcome"),
      column("tapeMean", "Tape mean", "number"),
      column("simulationMean", "Simulation mean", "number"),
      column("absoluteDelta", "Abs. delta", "number"),
      column("winnerStatus", "Status"),
      column("unresolvedRuns", "Unresolved", "number"),
    ]),
    defaultSort: Object.freeze({ field: "absoluteDelta", direction: "desc" }),
    sourceId: "phase2-results",
  });
}


await Promise.all([
  writeFile(ANALYSIS_PATH, `${JSON.stringify(analysis, null, 2)}\n`, "utf8"),
  writeFile(ARTIFACT_PATH, `${JSON.stringify(artifact, null, 2)}\n`, "utf8"),
]);

process.stdout.write(`${JSON.stringify({
  analysis: ANALYSIS_PATH,
  artifact: ARTIFACT_PATH,
  headline: analysis.headline,
})}\n`);
