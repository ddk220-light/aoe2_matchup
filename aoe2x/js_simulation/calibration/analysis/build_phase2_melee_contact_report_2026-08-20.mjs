import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const OUTPUT_DIR = resolve(ROOT, "calibration/reports/phase2_batch1_melee_contact_slots_2026-08-19");
const CURRENT_RESULTS_PATH = resolve(OUTPUT_DIR, "results.json");
const CURRENT_MANIFEST_PATH = resolve(OUTPUT_DIR, "run-manifest.json");
const PREVIOUS_RESULTS_PATH = resolve(
  ROOT,
  "calibration/reports/phase2_reachable_opening_body_formation_full_2026-08-19/results.json",
);
const ARCHIVE_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";

const [results, manifest, previousResults] = await Promise.all([
  readJson(CURRENT_RESULTS_PATH),
  readJson(CURRENT_MANIFEST_PATH),
  readJson(PREVIOUS_RESULTS_PATH).catch(() => null),
]);

if (results.rows.length !== 120) {
  throw new Error(`Expected 120 completed rows, found ${results.rows.length}.`);
}

const previousById = new Map((previousResults?.rows ?? []).map((row) => [row.id, row]));
const rows = results.rows.map((row) => rowView(row, previousById.get(row.id)));
const stableRows = rows.filter((row) => !row.tapeVolatile);
const wrongWinnerRows = rows.filter((row) => row.wrongStableWinner).sort(bySeverity);
const largeDeltaRows = rows.filter((row) => row.absoluteDelta > 25).sort(bySeverity);
const unresolvedRows = rows
  .filter((row) => row.unresolvedRuns > 0)
  .sort((left, right) => right.unresolvedRuns - left.unresolvedRuns || bySeverity(left, right));
const fixedRows = rows.filter((row) => row.previousWrongStableWinner && !row.wrongStableWinner);
const regressedRows = rows.filter((row) => !row.previousWrongStableWinner && row.wrongStableWinner);
const janissaryElephant = rows.find((row) => row.id === "elite_janissary_vs_elite_elephant");
const generatedAt = new Date().toISOString();

const technicalSummary = [
  `The latest engine completed **${results.summary.resolvedRuns} of ${results.summary.totalRuns} attempts** across all **120 exact Phase-2 golden rows**.`,
  `It has **${wrongWinnerRows.length} stable wrong-winner rows**, **${largeDeltaRows.length} rows above 25 outcome points**, and **${results.summary.fullyUnresolvedRows} fully unresolved rows**.`,
  janissaryElephant
    ? `The target Janissary–Elephant row now reports **${janissaryElephant.tapeOutcome}** on tape and **${janissaryElephant.simulationOutcome}** in simulation (${formatNumber(janissaryElephant.absoluteDelta)} points apart).`
    : "The target Janissary–Elephant row was not found in the completed result set.",
  previousResults
    ? `Against the prior full-engine snapshot, **${fixedRows.length} stable rows were corrected** and **${regressedRows.length} stable rows regressed to the wrong winner**.`
    : "No prior complete 120-row result set was available for flip analysis.",
].join("\n\n");

const analysis = {
  generatedAt,
  sourceArchiveSha256: ARCHIVE_SHA256,
  runSignature: manifest.runSignature,
  reportQuestion: "Did the melee contact-slot fix solve Janissary versus Elite Elephant, and what does the same engine do across all 120 Phase-2 golden rows?",
  comparisonBasis: "Exact golden unit counts, side assignments, and starting positions; five samples for stable rows and no more than fifteen for knife-edge rows.",
  visualOmissionReason: "Exact row-level winner and HP lookup is the decision task, so dense audit tables are more informative than aggregate charts.",
  headline: {
    rows: results.summary.rows,
    attempts: results.summary.totalRuns,
    resolvedAttempts: results.summary.resolvedRuns,
    unresolvedAttempts: results.summary.unresolvedRuns,
    fullyUnresolvedRows: results.summary.fullyUnresolvedRows,
    wrongStableWinners: wrongWinnerRows.length,
    rowsOver25: largeDeltaRows.length,
    rowsInsideTapeBand: results.summary.rowsInsideTapeBand,
    meanAbsoluteDelta: round(results.summary.meanAbsoluteMeanDelta),
    medianAbsoluteDelta: round(results.summary.medianAbsoluteMeanDelta),
    maximumAbsoluteDelta: round(results.summary.maximumAbsoluteMeanDelta),
    fixedSincePrevious: fixedRows.length,
    regressedSincePrevious: regressedRows.length,
  },
  janissaryElephant,
  datasets: {
    wrongWinnerRows,
    largeDeltaRows,
    unresolvedRows,
    fixedRows,
    regressedRows,
    allRows: [...rows].sort(bySeverity),
  },
};

const source = {
  id: "latest-results",
  label: "Latest recoverable Phase-2 120-row engine run",
  path: "aoe2x/js_simulation/calibration/reports/phase2_batch1_melee_contact_slots_2026-08-19/results.json",
  query: {
    language: "javascript",
    description: "Reads the completed row checkpoints merged by the recoverable Phase-2 runner and derives winner, HP, threshold, and flip tables.",
    tables_used: [
      "aoe2x/js_simulation/calibration/reports/phase2_batch1_melee_contact_slots_2026-08-19/results.json",
      "aoe2x/js_simulation/calibration/reports/phase2_batch1_melee_contact_slots_2026-08-19/run-manifest.json",
      "aoe2x/js_simulation/calibration/reports/phase2_reachable_opening_body_formation_full_2026-08-19/results.json",
    ],
    filters: [
      "All 120 exact Phase-2 Batch-1 golden rows",
      "Five samples for stable rows",
      "At most fifteen samples for volatile rows",
      "Current engine signature only",
    ],
    metric_definitions: {
      outcome_hp_percent: "Absolute signed outcome score: surviving winner HP divided by that side's starting HP, multiplied by 100.",
      wrong_stable_winner: "The resolved simulation mean selects the opposite winner from a non-volatile tape row, or no simulation attempt resolves.",
      absolute_delta: "Absolute difference between simulation mean signed outcome score and tape mean signed outcome score.",
      knife_edge: "Tape repeats contain winners on both sides; the row is not counted as a stable wrong-winner failure.",
    },
  },
};

const truthSource = {
  id: "golden-truth",
  label: "Authorized Phase-2 golden archive and imported truth fixture",
  path: "aoe2x/js_simulation/calibration/fixtures/phase2/batch1_truth.json",
  sha256: ARCHIVE_SHA256,
};

const artifact = {
  surface: "report",
  manifest: {
    version: 1,
    surface: "report",
    title: "Phase 2 engine after the melee contact-slot fix",
    description: "Tape versus simulation outcomes for the Janissary–Elephant target and all 120 Phase-2 golden rows.",
    generatedAt,
    blocks: [
      markdown("title", "# Phase 2 engine after the melee contact-slot fix"),
      markdown("technical-summary", `## The target matchup is fixed; the full corpus shows what remains\n\n${technicalSummary}`, "latest-results"),
      markdown(
        "winner-failures-intro",
        `## ${wrongWinnerRows.length} stable rows still choose the wrong winner\n\nTape and simulation outcomes below are expressed directly as the winning side and that side's remaining HP percentage. Delta is retained only as a secondary severity measure. Fully unresolved stable rows remain failures because they do not produce a simulated winner.`,
        "latest-results",
      ),
      tableBlock("wrong-winners", "wrong-winner-table"),
      markdown(
        "large-delta-intro",
        `## ${largeDeltaRows.length} rows are more than 25 outcome points from tape\n\nThis includes both wrong-winner reversals and same-winner fights whose remaining HP is materially different. Knife-edge tape rows are kept in this calibration list but are not labeled stable winner failures.`,
        "latest-results",
      ),
      tableBlock("large-deltas", "large-delta-table"),
      markdown(
        "flip-analysis-intro",
        `## The new physics corrected ${fixedRows.length} stable rows and regressed ${regressedRows.length}\n\nThe comparison uses the prior complete 120-row run only as a baseline snapshot. A flip is evidence about the net engine change; it does not by itself prove which individual mechanic caused the change.`,
        "latest-results",
      ),
      tableBlock("fixed-rows", "fixed-table"),
      tableBlock("regressed-rows", "regressed-table"),
      markdown(
        "unresolved-intro",
        `## ${unresolvedRows.length} rows contain at least one unresolved attempt\n\nThese rows are separated from resolved outcome misses because a tick-limit result is an engine-completion failure, not a simulated victory.`,
        "latest-results",
      ),
      tableBlock("unresolved-rows", "unresolved-table"),
      markdown(
        "definitions",
        "## How to read the results\n\nEach row uses the exact unit counts, team assignment, and starting positions recorded in the authorized golden tape. The displayed HP percentage is the winner's remaining HP divided by that side's starting HP. Positive internal scores mean Team 3 won and negative scores mean Team 2 won, but the report converts that sign into unit names. Stable rows use five deterministic samples; tape knife-edge rows use no more than fifteen. The 25-point boundary is a triage threshold, not a statistical confidence interval.",
        "golden-truth",
      ),
      markdown(
        "methodology",
        `## The run is recoverable and tied to one engine signature\n\nThe runner used ${manifest.workers} workers on ${manifest.availableParallelism} available logical CPUs, targeting ${Math.round(100 * manifest.cpuUtilizationTarget)}% utilization. It wrote one atomic checkpoint after every completed matchup and merged only checkpoints carrying engine signature \`${manifest.runSignature.slice(0, 12)}\`. This prevents a crash or restart from repeating completed rows or mixing engine versions.`,
        "latest-results",
      ),
      markdown(
        "limitations",
        "## Limits and robustness\n\nMost golden rows contain only a small number of tape repeats, so this report compares against the authorized recorded corpus rather than estimating the game's full random outcome distribution. Simulation samples vary deterministic seeds but can still converge on the same result. Winner agreement is the primary gate; remaining-HP delta is the calibration-strength measure. Overlap/contact forensics were performed in detail for Janissary–Elephant, while the other 119 rows are outcome-level checks in this report.",
        "latest-results",
      ),
      markdown(
        "next-steps",
        "## Recommended next pass\n\n1. Review stable wrong winners before same-winner HP misses.\n2. Treat fully unresolved rows as engine reliability failures.\n3. For each remaining wrong winner, compare tape and simulation overlap during movement and attacking before changing damage or unit statistics.\n4. Preserve the zero-through-ally melee contact rule as a regression control while adjusting broader pathing or collision behavior.",
      ),
      markdown(
        "further-questions",
        "## Questions for the next diagnosis\n\nWhich remaining reversals cluster around one opponent or movement archetype? Do regressed rows show the same contact-slot signature as Janissary–Elephant, or a different acquisition/pathing mechanism? Are unresolved rows low-damage knife edges that need a terminal classification, or true progress failures?",
      ),
      markdown("complete-results-intro", "## Complete 120-row audit\n\nThe final table is sorted by severity and includes tape, current simulation, previous simulation, delta, status, sample counts, and unresolved attempts.", "latest-results"),
      tableBlock("all-rows", "all-rows-table"),
    ],
    tables: [
      outcomeTable("wrong-winner-table", "Stable wrong-winner rows", "wrong_winner_rows"),
      outcomeTable("large-delta-table", "Rows above 25 outcome points", "large_delta_rows"),
      outcomeTable("fixed-table", "Stable rows corrected since the previous full run", "fixed_rows"),
      outcomeTable("regressed-table", "Stable rows that regressed since the previous full run", "regressed_rows"),
      outcomeTable("unresolved-table", "Rows with unresolved attempts", "unresolved_rows"),
      outcomeTable("all-rows-table", "All 120 exact golden rows", "all_rows"),
    ],
    sources: [source, truthSource],
  },
  snapshot: {
    version: 1,
    status: "ready",
    generatedAt,
    datasets: {
      wrong_winner_rows: wrongWinnerRows,
      large_delta_rows: largeDeltaRows,
      fixed_rows: fixedRows,
      regressed_rows: regressedRows,
      unresolved_rows: unresolvedRows,
      all_rows: [...rows].sort(bySeverity),
    },
    accessIssues: [],
  },
  sources: [source, truthSource],
};

await Promise.all([
  writeFile(resolve(OUTPUT_DIR, "analysis.json"), `${JSON.stringify(analysis, null, 2)}\n`, "utf8"),
  writeFile(resolve(OUTPUT_DIR, "artifact.json"), `${JSON.stringify(artifact, null, 2)}\n`, "utf8"),
]);

process.stdout.write(`${JSON.stringify({
  analysis: resolve(OUTPUT_DIR, "analysis.json"),
  artifact: resolve(OUTPUT_DIR, "artifact.json"),
  headline: analysis.headline,
  janissaryElephant,
})}\n`);

function rowView(row, previousRow) {
  const simulationMean = row.comparison.mean;
  const previousMean = previousRow?.comparison?.mean;
  const tapeWinner = winnerFor(row, row.tape.mean);
  const simulationWinner = winnerFor(row, simulationMean);
  const previousWinner = previousRow ? winnerFor(previousRow, previousMean) : null;
  const wrongStableWinner = Boolean(row.comparison.wrongStableWinner);
  const previousWrongStableWinner = previousRow
    ? Boolean(previousRow.comparison.wrongStableWinner)
    : null;
  const signedDelta = Number.isFinite(simulationMean) ? simulationMean - row.tape.mean : null;

  return {
    id: row.id,
    matchup: row.matchup,
    ratio: `${row.side2.count}v${row.side3.count}`,
    tapeVolatile: Boolean(row.tape.volatile),
    tapeOutcome: outcomeLabel(tapeWinner, row.tape.mean, row.tape.volatile),
    simulationOutcome: outcomeLabel(simulationWinner, simulationMean, false),
    previousSimulationOutcome: previousRow
      ? outcomeLabel(previousWinner, previousMean, false)
      : "Not available",
    tapeHpPercent: round(Math.abs(row.tape.mean)),
    simulationHpPercent: round(Math.abs(simulationMean)),
    previousSimulationHpPercent: round(Math.abs(previousMean)),
    absoluteDelta: round(Math.abs(signedDelta)),
    status: row.tape.volatile
      ? "Tape knife edge"
      : wrongStableWinner
        ? "Wrong winner"
        : "Winner matched",
    previousStatus: previousRow
      ? previousRow.tape.volatile
        ? "Tape knife edge"
        : previousWrongStableWinner
          ? "Wrong winner"
          : "Winner matched"
      : "Not available",
    simulationRuns: row.comparison.simulationRuns,
    unresolvedRuns: row.comparison.unresolvedRuns,
    tapeRuns: row.tape.scoredRuns,
    wrongStableWinner,
    previousWrongStableWinner,
  };
}

function winnerFor(row, score) {
  if (!Number.isFinite(score)) return null;
  return score > 0 ? row.side3.unit : row.side2.unit;
}

function outcomeLabel(winner, score, volatile) {
  if (volatile) return `Knife edge — mean ${formatNumber(Math.abs(score))}% HP`;
  if (!winner || !Number.isFinite(score)) return "Unresolved";
  return `${winner} — ${formatNumber(Math.abs(score))}% HP`;
}

function round(value, digits = 2) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}

function formatNumber(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "—";
}

function bySeverity(left, right) {
  return Number(right.wrongStableWinner) - Number(left.wrongStableWinner)
    || (right.absoluteDelta ?? -1) - (left.absoluteDelta ?? -1)
    || left.matchup.localeCompare(right.matchup);
}

function markdown(id, body, sourceId = undefined) {
  return { id, type: "markdown", layout: "full", body, ...(sourceId ? { sourceId } : {}) };
}

function tableBlock(id, tableId) {
  return { id, type: "table", layout: "full", tableId };
}

function column(field, label, format = undefined) {
  return { field, label, ...(format ? { format } : {}) };
}

function outcomeTable(id, title, dataset) {
  return {
    id,
    title,
    description: "Tape and simulation show the winning unit and that winner's remaining HP as a percentage of starting HP.",
    dataset,
    density: "dense",
    columns: [
      column("matchup", "Matchup"),
      column("ratio", "Ratio"),
      column("tapeOutcome", "Tape result"),
      column("simulationOutcome", "Latest simulation"),
      column("previousSimulationOutcome", "Previous simulation"),
      column("absoluteDelta", "Abs. delta", "number"),
      column("status", "Latest status"),
      column("simulationRuns", "Resolved samples", "number"),
      column("unresolvedRuns", "Unresolved samples", "number"),
    ],
    defaultSort: { field: "absoluteDelta", direction: "desc" },
    sourceId: "latest-results",
  };
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}
