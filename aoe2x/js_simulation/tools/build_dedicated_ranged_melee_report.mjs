import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";


const DEFAULT_RESULTS = new URL(
  "../calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/results.json",
  import.meta.url,
);
const DEFAULT_OUTPUT = new URL(
  "../calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/",
  import.meta.url,
);
const PROJECT_ROOT = resolve(fileURLToPath(new URL("../", import.meta.url)));


export function buildDedicatedGoldenAnalysis(report) {
  validateInputReport(report);
  const allRows = report.rows.map((row) => {
    const resolved = Number.isFinite(row.comparison.absoluteMeanDelta);
    return Object.freeze({
      rowId: row.id,
      matchup: row.matchup,
      ratio: row.ratio,
      rangedCount: row.ranged.count,
      meleeCount: row.melee.count,
      status: resolved ? "resolved" : "engine failure",
      tapeMean: row.comparison.tape.mean,
      tapeMin: row.comparison.tape.min,
      tapeMax: row.comparison.tape.max,
      simulationMean: row.comparison.simulation.mean,
      simulationMin: row.comparison.simulation.min,
      simulationMax: row.comparison.simulation.max,
      meanDelta: row.comparison.meanDelta,
      absoluteMeanDelta: row.comparison.absoluteMeanDelta,
      tapeBandError: row.comparison.tapeBandError,
      wrongWinnerRuns: row.comparison.wrongWinnerRuns,
      unresolvedRuns: row.comparison.unresolvedRuns,
      archive: row.archive,
      zipSha256: row.zipSha256,
      failure: resolved ? null : describeFailure(row.samples),
    });
  });
  const resolvedRows = allRows.filter(({ status }) => status === "resolved");
  const failedRows = allRows.filter(({ status }) => status === "engine failure");
  const rowsOver25 = resolvedRows
    .filter(({ absoluteMeanDelta }) => absoluteMeanDelta > 25)
    .toSorted((left, right) => right.absoluteMeanDelta - left.absoluteMeanDelta);
  const failureByCategory = new Map();
  for (const row of failedRows) {
    const category = categorizeFailure(row.failure);
    const value = failureByCategory.get(category) ?? { category, rows: 0, attempts: 0 };
    value.rows += 1;
    value.attempts += row.unresolvedRuns;
    failureByCategory.set(category, value);
  }
  const matchupSummaries = report.matchupSummaries.map((summary) => Object.freeze({
    matchupId: summary.matchupId,
    matchup: summary.matchup,
    resolvedRows: summary.rows - summary.unresolvedRuns / 5,
    failedRows: summary.unresolvedRuns / 5,
    resolvedAttempts: summary.tapeRuns - summary.unresolvedRuns,
    unresolvedAttempts: summary.unresolvedRuns,
    meanAbsoluteMeanDelta: summary.meanAbsoluteMeanDelta,
    maxAbsoluteMeanDelta: summary.maxAbsoluteMeanDelta,
    rowsOver25PointDelta: summary.rowsOver25PointDelta,
    rowsInsideTapeBand: summary.rowsInsideTapeBand,
    wrongWinnerRuns: summary.wrongWinnerRuns,
  })).toSorted((left, right) => right.meanAbsoluteMeanDelta - left.meanAbsoluteMeanDelta);
  return Object.freeze({
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    coverage: Object.freeze({
      matchups: report.summary.matchups,
      totalRows: report.summary.rows,
      resolvedRows: resolvedRows.length,
      failedRows: failedRows.length,
      totalAttempts: report.summary.totalRuns,
      resolvedAttempts: report.summary.resolvedRuns,
      failedAttempts: report.summary.unresolvedRuns,
      fullyUnresolvedRows: report.summary.fullyUnresolvedRows,
      partiallyUnresolvedRows: report.summary.partiallyUnresolvedRows,
    }),
    accuracy: Object.freeze({
      meanAbsoluteMeanDelta: report.summary.meanAbsoluteMeanDelta,
      medianAbsoluteMeanDelta: report.summary.medianAbsoluteMeanDelta,
      maximumAbsoluteMeanDelta: report.summary.maximumAbsoluteMeanDelta,
      rowsInsideTapeBand: report.summary.rowsInsideTapeBand,
      wrongWinnerRuns: report.summary.wrongWinnerRuns,
    }),
    thresholds: Object.freeze({
      resolvedRows: resolvedRows.length,
      rowsAtOrUnder25Points: resolvedRows.length - rowsOver25.length,
      rowsOver25Points: rowsOver25.length,
    }),
    failureCategories: Object.freeze([...failureByCategory.values()].toSorted((left, right) => (
      right.attempts - left.attempts
    ))),
    rowsOver25: Object.freeze(rowsOver25),
    matchupSummaries: Object.freeze(matchupSummaries),
    allRows: Object.freeze(allRows.toSorted((left, right) => left.rowId.localeCompare(right.rowId))),
  });
}


function describeFailure(samples) {
  const explicit = samples.find(({ failure }) => (
    typeof failure === "string" && failure.length > 0
  ))?.failure;
  if (explicit) return explicit;
  const timeoutTicks = samples
    .filter(({ outcome }) => outcome === "timeout")
    .map(({ ticks }) => ticks)
    .filter(Number.isFinite);
  if (timeoutTicks.length) return `world exceeded ${Math.max(...timeoutTicks)} ticks`;
  return "unknown";
}


export function buildDedicatedGoldenArtifact({
  report,
  analysis,
  execution = null,
  sourcePath = "aoe2x/js_simulation/calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/results.json",
}) {
  const generatedAt = analysis.generatedAt;
  const manifestPath = "aoe2x/js_simulation/calibration/source/dedicated_ranged_melee_sources.json";
  const truthPath = "aoe2x/js_simulation/calibration/fixtures/dedicated_ranged_melee/dedicated_ranged_melee_truth.json";
  const resolvedShare = percent(analysis.coverage.resolvedRows / analysis.coverage.totalRows);
  const within25Share = percent(
    analysis.thresholds.rowsAtOrUnder25Points / analysis.thresholds.resolvedRows,
  );
  const wrongWinnerShare = percent(
    analysis.accuracy.wrongWinnerRuns / analysis.coverage.resolvedAttempts,
  );
  const failureShare = percent(
    analysis.coverage.failedAttempts / analysis.coverage.totalAttempts,
  );
  const resolvedAllAttempts = analysis.coverage.resolvedAttempts === analysis.coverage.totalAttempts;
  const executionSentence = execution?.workers && execution?.availableParallelism
    ? `The recoverable runner used **${execution.workers} child processes** across ${execution.availableParallelism} available logical CPUs. Each ${execution.checkpointUnit ?? "completed ratio row"} was flushed to an atomic checkpoint, so a restart skips already validated work.`
    : "The recoverable runner used independent child processes and atomically checkpointed each complete ratio row so a restart skips already validated work.";
  const largeDeltaCounts = new Map();
  for (const row of analysis.rowsOver25) {
    largeDeltaCounts.set(row.matchup, (largeDeltaCounts.get(row.matchup) ?? 0) + 1);
  }
  const dominantLargeDelta = [...largeDeltaCounts]
    .toSorted((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0] ?? null;
  const topWrongWinner = analysis.matchupSummaries
    .filter(({ wrongWinnerRuns }) => wrongWinnerRuns > 0)
    .toSorted((left, right) => right.wrongWinnerRuns - left.wrongWinnerRuns)[0] ?? null;
  const closestMatchup = analysis.matchupSummaries
    .filter(({ resolvedRows, meanAbsoluteMeanDelta }) => (
      resolvedRows > 0 && Number.isFinite(meanAbsoluteMeanDelta)
    ))
    .toSorted((left, right) => left.meanAbsoluteMeanDelta - right.meanAbsoluteMeanDelta)[0] ?? null;
  const largestResolvedRow = analysis.allRows
    .filter(({ absoluteMeanDelta }) => Number.isFinite(absoluteMeanDelta))
    .toSorted((left, right) => right.absoluteMeanDelta - left.absoluteMeanDelta)[0] ?? null;
  const technicalTitle = analysis.coverage.failedRows > 0
    ? "Resolved rows are measurable, but engine failures limit corpus-wide confidence"
    : analysis.thresholds.rowsOver25Points > 0 || analysis.accuracy.wrongWinnerRuns > 0
      ? "Every row resolved; the remaining misses are concentrated"
      : "Every row resolved within the 25-point outcome threshold";
  const resolutionSentence = resolvedAllAttempts
    ? `all **${analysis.coverage.totalAttempts} attempts** resolved.`
    : `**${analysis.coverage.resolvedAttempts}/${analysis.coverage.totalAttempts} attempts** resolved (${resolvedShare}); ${analysis.coverage.failedAttempts} attempts failed (${failureShare}). No failed attempt was silently dropped.`;
  const thresholdSentence = analysis.thresholds.rowsOver25Points === 0
    ? "No ratio row exceeds 25 points."
    : `${analysis.thresholds.rowsOver25Points} ratio rows exceed 25 points.`;
  const winnerSentence = analysis.accuracy.wrongWinnerRuns === 0
    ? "Every resolved attempt selects the same winner as its tape repeat."
    : `${analysis.accuracy.wrongWinnerRuns}/${analysis.coverage.resolvedAttempts} resolved attempts (${wrongWinnerShare}) select the wrong winner.`;
  const keyFindingTitle = dominantLargeDelta
    ? `${dominantLargeDelta[0]} contributes the most >25-point rows`
    : "No ratio row exceeds the 25-point threshold";
  const largestMissSentence = analysis.rowsOver25[0]
    ? `The largest miss is **${analysis.rowsOver25[0].matchup} ${analysis.rowsOver25[0].ratio}**: tape ${signed(analysis.rowsOver25[0].tapeMean)} versus simulation ${signed(analysis.rowsOver25[0].simulationMean)}, an **${round(analysis.rowsOver25[0].absoluteMeanDelta)}-point** difference.`
    : largestResolvedRow
      ? `The largest remaining resolved difference is **${largestResolvedRow.matchup} ${largestResolvedRow.ratio}** at **${round(largestResolvedRow.absoluteMeanDelta)} points**.`
      : "No resolved outcome delta is available.";
  const concentrationSentence = dominantLargeDelta
    ? `**${dominantLargeDelta[0]}** contributes ${dominantLargeDelta[1]} of ${analysis.thresholds.rowsOver25Points} rows above 25 points.${topWrongWinner ? ` **${topWrongWinner.matchup}** contributes the most wrong-winner attempts (${topWrongWinner.wrongWinnerRuns}).` : ""}`
    : "No ratio row exceeds 25 points in this run.";
  const closestSentence = closestMatchup
    ? `The closest matchup is **${closestMatchup.matchup}**, with a ${round(closestMatchup.meanAbsoluteMeanDelta)}-point mean absolute row delta, a ${round(closestMatchup.maxAbsoluteMeanDelta)}-point maximum, ${closestMatchup.wrongWinnerRuns} wrong-winner attempts, and ${closestMatchup.failedRows} failed rows.`
    : "No matchup-level resolved comparison is available.";
  const failureTitle = analysis.coverage.failedAttempts === 0
    ? "No engine failures occurred"
    : `${analysis.coverage.failedAttempts} attempts remain unresolved`;
  const failureBody = analysis.coverage.failedAttempts === 0
    ? `All ${analysis.coverage.totalRows} ratio rows and ${analysis.coverage.totalAttempts} exact-repeat attempts completed, so every row contributes to the delta distribution.`
    : `${analysis.coverage.failedRows} ratio rows are fully unresolved and ${analysis.coverage.partiallyUnresolvedRows} are partially unresolved. Failure categories are ${analysis.failureCategories.map(({ category, attempts }) => `${category} (${attempts} attempts)`).join(", ")}. Failed attempts are excluded from delta averages rather than treated as zero error; the ${round(analysis.accuracy.meanAbsoluteMeanDelta)}-point mean describes ${analysis.coverage.resolvedRows} resolved rows.`;
  const limitationBody = analysis.coverage.failedRows === 0
    ? `All rows resolved, so aggregate delta metrics cover the complete corpus. The engine is deterministic for each exact starting state; tape variability comes from five recorded repeats, not repeated random seeds from one state. Outcome score measures winner and survivor HP, but does not by itself establish that movement, targeting, damage timing, or battle duration followed the tape.`
    : `Aggregate accuracy metrics are conditional on successful completion: ${analysis.coverage.failedRows} rows (${percent(analysis.coverage.failedRows / analysis.coverage.totalRows)} of the corpus) have no complete simulation score. The engine is deterministic for each exact starting state; tape variability comes from five recorded repeats, not repeated random seeds from one state. Outcome score measures winner and survivor HP, but does not by itself establish that movement, targeting, damage timing, or battle duration followed the tape.`;
  const nextSteps = [];
  if (analysis.coverage.failedRows > 0) {
    nextSteps.push(`Resolve and rerun the ${analysis.coverage.failedRows} failed rows using their retained checkpoints and typed failure evidence.`);
  }
  if (analysis.thresholds.rowsOver25Points > 0) {
    nextSteps.push(`Review the ${analysis.thresholds.rowsOver25Points} rows above 25 points, starting with ${analysis.rowsOver25.slice(0, 3).map(({ matchup, ratio }) => `${matchup} ${ratio}`).join("; ")}.`);
  }
  if (analysis.accuracy.wrongWinnerRuns > 0) {
    nextSteps.push(`Prioritize the ${analysis.accuracy.wrongWinnerRuns} wrong-winner attempts before tuning same-winner survivor-HP severity.`);
  }
  nextSteps.push("Retain the recoverable child-process runner for future corpus jobs; its signature and per-row checkpoints make interrupted runs resumable without repeated work.");
  const furtherQuestions = [
    analysis.thresholds.rowsOver25Points > 0
      ? "Do the remaining >25-point rows share one movement or combat mechanism, or are they unit-class-specific physics gaps?"
      : "Do movement, engagement timing, and target selection also match tape in the rows whose final outcomes are already close?",
    analysis.accuracy.wrongWinnerRuns > 0
      ? "Are wrong-winner attempts concentrated in one density, obstruction, or range regime?"
      : "Does winner agreement remain stable under newly recorded starting formations?",
    "Which outcome-accurate rows still have materially different battle duration or survivor trajectories from tape?",
  ];
  return {
    surface: "report",
    manifest: {
      version: 1,
      surface: "report",
      title: "Dedicated Golden Ranged-vs-Melee Engine Comparison",
      description: "Exact-repeat comparison of the current JavaScript engine against 17 explicitly authorized dedicated golden archives.",
      generatedAt,
      blocks: [
        {
          id: "title",
          type: "markdown",
          body: "# Dedicated Golden Ranged-vs-Melee Engine Comparison",
        },
        {
          id: "technical-summary",
          type: "markdown",
          sourceId: "results-source",
          body: `## ${technicalTitle}\n\nThe run preserved **${analysis.coverage.totalAttempts} exact tape-repeat attempts** across ${analysis.coverage.matchups} authorized golden matchups; ${resolutionSentence}\n\nAmong ${analysis.coverage.resolvedRows} comparable ratio rows, the median absolute tape delta is **${round(analysis.accuracy.medianAbsoluteMeanDelta)} percentage points** and **${analysis.thresholds.rowsAtOrUnder25Points}/${analysis.thresholds.resolvedRows} (${within25Share})** are at or below 25 points. ${thresholdSentence} ${winnerSentence}`,
        },
        {
          id: "key-findings-heading",
          type: "markdown",
          body: `## ${keyFindingTitle}\n\n${concentrationSentence} ${largestMissSentence}\n\n${closestSentence}`,
          sourceId: "results-source",
        },
        { id: "matchup-chart-block", type: "chart", chartId: "matchup-accuracy-chart", layout: "full" },
        { id: "large-delta-chart-block", type: "chart", chartId: "large-delta-chart", layout: "full" },
        {
          id: "threshold-interpretation",
          type: "markdown",
          body: "### The >25-point list is short but consequential\n\nThe table below is the complete threshold list, not a sample. Positive signed scores mean the melee side won with that percentage of its starting HP; negative scores mean the ranged side won. A wrong sign is therefore a winner flip, while a same-sign delta reflects survivor-HP severity.",
        },
        { id: "large-delta-table-block", type: "table", tableId: "large-delta-table", layout: "full" },
        {
          id: "failures-heading",
          type: "markdown",
          sourceId: "results-source",
          body: `## ${failureTitle}\n\n${failureBody}`,
        },
        { id: "failure-table-block", type: "table", tableId: "failure-table", layout: "full" },
        {
          id: "scope-definitions",
          type: "markdown",
          sourceId: "results-source",
          body: "## Scope, data, and metric definitions\n\n- **Corpus:** 17 project-local, SHA-256-manifested dedicated golden archives only: five Arbalester matchups, five Elite Skirmisher matchups, five Heavy Cavalry Archer matchups, and two Heavy Scorpion matchups. No Standard Units substitution, Hand Cannoneer, Heavy Camel, Onager, or Panther row is included.\n- **Rows and repeats:** each matchup has five tape ratios and each ratio has five recorded repeats, giving 85 rows and 425 attempts.\n- **Starting state:** every simulation uses the exact `starting_units` positions from its corresponding tape repeat; automatic placement is not used.\n- **Signed outcome score:** ranged/owner-2 wins are negative and melee/owner-3 wins are positive; magnitude is winner remaining HP divided by that owner's starting HP, in percent.\n- **Absolute mean delta:** absolute difference, in percentage points, between the mean simulation score and mean tape score for a ratio row.\n- **Tape-band hit:** the simulation mean lies inside that row's five-repeat tape minimum-to-maximum band.\n- **Wrong winner:** simulation and tape signed scores have opposite signs for the same repeat.",
        },
        {
          id: "methodology",
          type: "markdown",
          body: `## Exact-repeat methodology\n\nEach external golden ZIP was hashed before intake, copied byte-for-byte into the clean-room source directory, hashed again, and recorded in the active dedicated manifest. \`frames.bin\`, \`summary.json\`, and exact starting-unit records were imported reproducibly into the dedicated truth fixture. The current checked-out JavaScript engine ran each repeat on the golden map with cohesive kiting, mechanics-derived kiting clock, melee attack-move-all, chase capture enabled, zero melee engagement dwell, preventive contact steering at **0.50 strength**, and a 9,000-tick limit.\n\n${executionSentence} The strict merge rejects duplicate or incomplete coverage and verifies exactly ${analysis.coverage.matchups} matchups, ${analysis.coverage.totalRows} rows, and ${analysis.coverage.totalAttempts} attempts.`,
        },
        {
          id: "limitations",
          type: "markdown",
          sourceId: "results-source",
          body: `## Limitations, uncertainty, and robustness\n\n${limitationBody}\n\nRobustness checks cover provenance and schedule completeness: ${analysis.coverage.matchups} unique authorized archives, five ratios per matchup, five repeats per ratio, exact repeat starts, no duplicate rows, atomic row checkpoints, and no partially written results.`,
        },
        { id: "all-rows-table-block", type: "table", tableId: "all-rows-table", layout: "full" },
        {
          id: "next-steps",
          type: "markdown",
          body: `## Recommended next steps\n\n${nextSteps.map((step, index) => `${index + 1}. ${step}`).join("\n")}`,
        },
        {
          id: "further-questions",
          type: "markdown",
          body: `## Further questions\n\n${furtherQuestions.map((question) => `- ${question}`).join("\n")}`,
        },
      ],
      charts: [
        {
          id: "matchup-accuracy-chart",
          title: "Mean absolute outcome delta by dedicated matchup",
          subtitle: "Percentage points across resolved ratio rows only; failed rows are shown in tooltips",
          showDescription: true,
          question: "Which dedicated matchups are closest to or furthest from their tape outcomes?",
          rationale: "Sorted horizontal bars preserve long unit names and make the Scorpion outliers immediately visible.",
          intent: "comparison",
          type: "horizontalBar",
          dataset: "matchup_summaries",
          sourceId: "matchup-source",
          encodings: {
            x: { field: "matchup", type: "nominal", label: "Matchup" },
            y: { field: "mean_absolute_delta", type: "quantitative", format: "number", label: "Mean absolute delta", unit: "pp" },
            tooltip: [
              { field: "resolved_rows", type: "quantitative", format: "number", label: "Resolved rows" },
              { field: "failed_rows", type: "quantitative", format: "number", label: "Failed rows" },
              { field: "rows_over_25", type: "quantitative", format: "number", label: "Rows >25 pp" },
              { field: "wrong_winner_runs", type: "quantitative", format: "number", label: "Wrong-winner attempts" },
            ],
          },
          valueFormat: "number",
          layout: "full",
          maxRows: 17,
          surface: { legend: "none", valueLabels: true },
        },
        {
          id: "large-delta-chart",
          title: "Resolved ratio rows above 25-point absolute delta",
          subtitle: "Absolute difference between simulation mean and five-repeat tape mean; percentage points",
          showDescription: true,
          question: "How large are the remaining outcome misses above the agreed 25-point threshold?",
          rationale: "A ranked single-series horizontal bar shows magnitude without obscuring winner-sign details retained in the table.",
          intent: "ranking",
          type: "horizontalBar",
          dataset: "rows_over_25",
          sourceId: "results-source",
          encodings: {
            x: { field: "label", type: "nominal", label: "Matchup and ratio" },
            y: { field: "absolute_mean_delta", type: "quantitative", format: "number", label: "Absolute mean delta", unit: "pp" },
            tooltip: [
              { field: "tape_mean", type: "quantitative", format: "number", label: "Tape mean" },
              { field: "simulation_mean", type: "quantitative", format: "number", label: "Simulation mean" },
              { field: "wrong_winner_runs", type: "quantitative", format: "number", label: "Wrong-winner attempts" },
            ],
          },
          valueFormat: "number",
          layout: "full",
          maxRows: Math.max(1, analysis.rowsOver25.length),
          surface: { legend: "none", valueLabels: true },
        },
      ],
      tables: [
        {
          id: "large-delta-table",
          title: "Complete >25-point threshold list",
          subtitle: "Tape and simulation values are signed outcome scores; pp = percentage points",
          showDescription: true,
          dataset: "rows_over_25",
          sourceId: "results-source",
          defaultSort: { field: "absolute_mean_delta", direction: "desc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "matchup", label: "Matchup", type: "text" },
            { field: "ratio", label: "Ratio", type: "text" },
            { field: "tape_mean", label: "Tape mean", format: "number", role: "value" },
            { field: "simulation_mean", label: "Simulation mean", format: "number", role: "value" },
            { field: "mean_delta", label: "Signed delta", format: "number", role: "value" },
            { field: "absolute_mean_delta", label: "Absolute delta", format: "number", role: "value" },
            { field: "wrong_winner_runs", label: "Wrong winners", format: "number", role: "value" },
          ],
        },
        {
          id: "failure-table",
          title: "Unresolved attempt categories",
          subtitle: "Rows are fully unresolved when all five exact tape-repeat starts fail",
          showDescription: true,
          dataset: "failure_categories",
          sourceId: "results-source",
          defaultSort: { field: "attempts", direction: "desc" },
          density: "spacious",
          layout: "full",
          columns: [
            { field: "category", label: "Failure category", type: "text" },
            { field: "rows", label: "Ratio rows", format: "number", role: "value" },
            { field: "attempts", label: "Attempts", format: "number", role: "value" },
          ],
        },
        {
          id: "all-rows-table",
          title: `All ${analysis.coverage.totalRows} dedicated golden ratio rows`,
          subtitle: "Exact audit view; unresolved rows retain their failure status and have no simulation delta",
          showDescription: true,
          dataset: "all_rows",
          sourceId: "results-source",
          defaultSort: { field: "row_id", direction: "asc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "row_id", label: "Row", type: "text" },
            { field: "status", label: "Status", type: "text" },
            { field: "tape_mean", label: "Tape", format: "number", role: "value" },
            { field: "simulation_mean", label: "Simulation", format: "number", role: "value" },
            { field: "absolute_mean_delta", label: "Abs delta", format: "number", role: "value" },
            { field: "wrong_winner_runs", label: "Wrong winners", format: "number", role: "value" },
            { field: "unresolved_runs", label: "Failed attempts", format: "number", role: "value" },
          ],
        },
      ],
      sources: [
        {
          id: "results-source",
          label: "Dedicated golden current-engine result rows",
          path: sourcePath,
          query: {
            engine: "DuckDB",
            language: "SQL",
            description: "Loads and recursively expands the 85 reviewed ratio rows from the completed dedicated-golden JSON report.",
            executed_at: generatedAt,
            tables_used: [sourcePath],
            filters: ["17 authorized dedicated golden matchups", "5 ratios per matchup", "5 exact tape-repeat starts per ratio"],
            metric_definitions: ["Absolute mean delta is abs(simulation mean signed outcome score - tape mean signed outcome score) in percentage points"],
            sql: `WITH document AS (SELECT rows FROM read_json_auto('${sourcePath}', format = 'auto')) SELECT unnest(rows, recursive := true) FROM document`,
          },
        },
        {
          id: "matchup-source",
          label: "Dedicated golden current-engine matchup summaries",
          path: sourcePath,
          query: {
            engine: "DuckDB",
            language: "SQL",
            description: "Loads and recursively expands the 17 reviewed matchup summaries from the completed dedicated-golden JSON report.",
            executed_at: generatedAt,
            tables_used: [sourcePath],
            filters: ["Resolved ratio rows contribute to delta aggregates", "Unresolved attempts are retained as failure counts"],
            metric_definitions: ["Mean absolute mean delta averages the absolute ratio-row mean deltas over resolved rows only"],
            sql: `WITH document AS (SELECT matchupSummaries FROM read_json_auto('${sourcePath}', format = 'auto')) SELECT unnest(matchupSummaries, recursive := true) FROM document`,
          },
        },
        { id: "manifest-source", label: "Authorized dedicated golden archive manifest", path: manifestPath },
        { id: "truth-source", label: "Imported exact-repeat dedicated golden truth", path: truthPath },
      ],
    },
    snapshot: {
      version: 1,
      generatedAt,
      status: "ready",
      datasets: {
        matchup_summaries: analysis.matchupSummaries.map((row) => ({
          matchup: row.matchup,
          mean_absolute_delta: round(row.meanAbsoluteMeanDelta),
          maximum_absolute_delta: round(row.maxAbsoluteMeanDelta),
          resolved_rows: row.resolvedRows,
          failed_rows: row.failedRows,
          rows_over_25: row.rowsOver25PointDelta,
          rows_inside_tape_band: row.rowsInsideTapeBand,
          wrong_winner_runs: row.wrongWinnerRuns,
        })),
        rows_over_25: analysis.rowsOver25.map((row) => ({
          label: `${row.matchup} ${row.ratio}`,
          matchup: row.matchup,
          ratio: row.ratio,
          tape_mean: round(row.tapeMean),
          simulation_mean: round(row.simulationMean),
          mean_delta: round(row.meanDelta),
          absolute_mean_delta: round(row.absoluteMeanDelta),
          wrong_winner_runs: row.wrongWinnerRuns,
        })),
        failure_categories: analysis.failureCategories,
        all_rows: analysis.allRows.map((row) => ({
          row_id: row.rowId,
          matchup: row.matchup,
          ratio: row.ratio,
          status: row.status,
          tape_mean: roundOrNull(row.tapeMean),
          simulation_mean: roundOrNull(row.simulationMean),
          mean_delta: roundOrNull(row.meanDelta),
          absolute_mean_delta: roundOrNull(row.absoluteMeanDelta),
          tape_band_error: roundOrNull(row.tapeBandError),
          wrong_winner_runs: row.wrongWinnerRuns,
          unresolved_runs: row.unresolvedRuns,
          archive: row.archive,
          zip_sha256: row.zipSha256,
        })),
      },
    },
    sources: [
      { id: "results-source", label: "Dedicated golden current-engine results", path: sourcePath },
    ],
  };
}


export async function main(argv = process.argv.slice(2)) {
  const resultsPath = argv[0] ? resolve(argv[0]) : DEFAULT_RESULTS;
  const outputDirectory = argv[1] ? resolve(argv[1]) : DEFAULT_OUTPUT;
  const report = JSON.parse(await readFile(resultsPath, "utf8"));
  const execution = await readOptionalJson(resolve(dirname(resultsPath), "run-manifest.json"));
  const analysis = buildDedicatedGoldenAnalysis(report);
  const artifact = buildDedicatedGoldenArtifact({
    report,
    analysis,
    execution,
    sourcePath: relative(PROJECT_ROOT, resultsPath).replaceAll("\\", "/"),
  });
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all([
    writeFile(resolveOutput(outputDirectory, "analysis.json"), `${JSON.stringify(analysis, null, 2)}\n`, "utf8"),
    writeFile(resolveOutput(outputDirectory, "artifact.json"), `${JSON.stringify(artifact, null, 2)}\n`, "utf8"),
  ]);
  process.stdout.write(`${JSON.stringify({ analysis: analysis.coverage, outputDirectory: String(outputDirectory) })}\n`);
  return { analysis, artifact };
}


async function readOptionalJson(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw error;
  }
}


function validateInputReport(report) {
  if (report?.summary?.matchups !== 17 || report?.summary?.rows !== 85
      || report?.summary?.totalRuns !== 425 || report?.rows?.length !== 85) {
    throw new Error("dedicated report must contain exactly 17 matchups, 85 rows, and 425 attempts");
  }
  const attempts = report.rows.reduce((total, row) => total + row.samples.length, 0);
  if (attempts !== 425 || new Set(report.rows.map(({ id }) => id)).size !== 85) {
    throw new Error("dedicated report row/repeat coverage is invalid");
  }
}


function categorizeFailure(message) {
  if (message.includes("collision constraints did not converge")) return "collision convergence";
  if (message.includes("world exceeded")) return "tick limit";
  return "other engine error";
}


function resolveOutput(directory, fileName) {
  return directory instanceof URL ? new URL(fileName, directory) : resolve(directory, fileName);
}


function round(value) {
  return Math.round(value * 100) / 100;
}


function roundOrNull(value) {
  return Number.isFinite(value) ? round(value) : null;
}


function signed(value) {
  const rounded = round(value);
  return `${rounded >= 0 ? "+" : ""}${rounded}`;
}


function percent(value) {
  return `${round(value * 100)}%`;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
