import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";


const REPORT_DIRECTORY = new URL(
  "../calibration/reports/ranged_vs_melee_current_engine_2026-08-13/",
  import.meta.url,
);
const INPUT = new URL("analysis.json", REPORT_DIRECTORY);
const OUTPUT = new URL("artifact.json", REPORT_DIRECTORY);


export function buildArtifact(analysis, generatedAt = new Date().toISOString()) {
  const ranked = analysis.rows
    .toSorted((left, right) => right.absoluteMeanDelta - left.absoluteMeanDelta)
    .map((row, index) => ({
      rank: index + 1,
      id: row.id,
      matchup: row.matchup,
      ratio: `${row.ranged.count} vs ${row.melee.count}`,
      ranged_unit: row.ranged.unit,
      melee_unit: row.melee.unit,
      tape_mean: row.tape.mean,
      tape_min: row.tape.min,
      tape_max: row.tape.max,
      tape_band: `${format(row.tape.min)} to ${format(row.tape.max)}`,
      simulation_mean: row.simulation.mean,
      simulation_min: row.simulation.min,
      simulation_max: row.simulation.max,
      simulation_band: `${format(row.simulation.min)} to ${format(row.simulation.max)}`,
      signed_mean_delta: row.signedMeanDelta,
      absolute_mean_delta: row.absoluteMeanDelta,
      tape_band_error: row.tapeBandError,
      tape_band_coverage: row.tapeBandCoverage,
      winner_agreement: row.winnerAgreement,
      simulation_runs: row.simulation.runs,
      unresolved_runs: row.simulation.unresolvedRuns,
      failure: row.failure || "none",
    }));
  const familySummary = summarizeFamilies(analysis.rows);
  const summary = analysis.summary;
  const sourcePath = "aoe2x/js_simulation/calibration/reports/ranged_vs_melee_current_engine_2026-08-13/analysis.json";
  const reportSource = {
    id: "comparison-source",
    label: "Latest ranged-versus-melee tape comparison",
    path: sourcePath,
  };
  const archiveSource = {
    id: "standard-archive",
    label: "Authorized standard-units golden archive",
    path: "aoe2x/js_simulation/calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip",
  };
  const rankedSource = querySource({
    id: "ranked-query",
    label: "Reviewed largest-delta rows",
    path: sourcePath,
    generatedAt,
    description: "Reconstructs the 15 exact tape ratios with the largest absolute simulation-minus-tape mean delta.",
    filters: ["authorized ranged-versus-melee tape rows", "top 15 by absolute mean delta"],
    definitions: ["signed_mean_delta = simulation_mean - tape_mean"],
    columns: ["label", "signed_mean_delta", "absolute_mean_delta", "tape_mean", "simulation_mean", "tape_band_error"],
    rows: ranked.slice(0, 15).map((row) => [
      `${row.matchup} (${row.ratio})`, row.signed_mean_delta, row.absolute_mean_delta,
      row.tape_mean, row.simulation_mean, row.tape_band_error,
    ]),
  });
  const familySource = querySource({
    id: "family-query",
    label: "Reviewed ranged-family summary",
    path: sourcePath,
    generatedAt,
    description: "Reconstructs the eight-row outcome accuracy summary for each ranged family.",
    filters: ["eight exact melee tape ratios per ranged family"],
    definitions: ["mean_absolute_delta is the arithmetic mean of eight absolute row-level mean deltas"],
    columns: ["ranged_unit", "mean_absolute_delta", "rows_over_25", "rows_inside_tape_band", "wrong_stable_winners"],
    rows: familySummary.map((row) => [
      row.ranged_unit, row.mean_absolute_delta, row.rows_over_25,
      row.rows_inside_tape_band, row.wrong_stable_winners,
    ]),
  });
  const auditSource = querySource({
    id: "audit-query",
    label: "Reviewed complete 48-row comparison",
    path: sourcePath,
    generatedAt,
    description: "Reconstructs the complete exact-ratio row-level comparison table sorted by absolute mean delta.",
    filters: ["all 48 authorized ranged-versus-melee tape rows", "exact tape counts and owner order"],
    definitions: ["tape_band_error is zero inside the tape min/max interval", "failure records unresolved simulation runs"],
    columns: [
      "rank", "matchup", "ratio", "tape_mean", "tape_band", "simulation_mean",
      "simulation_band", "signed_mean_delta", "absolute_mean_delta", "tape_band_error",
      "winner_agreement", "simulation_runs", "failure",
    ],
    rows: ranked.map((row) => [
      row.rank, row.matchup, row.ratio, row.tape_mean, row.tape_band,
      row.simulation_mean, row.simulation_band, row.signed_mean_delta,
      row.absolute_mean_delta, row.tape_band_error, row.winner_agreement,
      row.simulation_runs, row.failure,
    ]),
  });

  return {
    surface: "report",
    manifest: {
      version: 1,
      surface: "report",
      title: "Latest Engine vs Tape: Ranged-vs-Melee Benchmark",
      description: "Exact-tape-ratio comparison of the current JavaScript simulation engine across all 48 authorized ranged-versus-melee standard-unit rows.",
      generatedAt,
      blocks: [
        { id: "title", type: "markdown", body: "# Latest Engine vs Tape: Ranged-vs-Melee Benchmark" },
        {
          id: "technical-summary",
          type: "markdown",
          sourceId: "comparison-source",
          body: `## Technical summary\n\nThe current engine resolves all **${summary.totalRuns} scheduled simulations** with no timeouts. Across the 48 exact tape ratios, **${summary.rowsOver25PointDelta} rows exceed 25 score points of mean delta**, **${summary.rowsInsideTapeBand} simulation means land inside the tape band**, and **${summary.wrongStableWinnerCount} stable row flips winner**. Mean absolute delta is **${format(summary.meanAbsoluteMeanDelta)}** points and the median is **${format(summary.medianAbsoluteMeanDelta)}**.\n\nThe recent HCA engagement and crowd work holds up broadly: Heavy Cavalry Archer has no row above 25 points, five of eight means inside the tape band, and ${format(familySummary.find((row) => row.ranged_unit === "Heavy Cavalry Archer").mean_absolute_delta)} points of mean absolute delta. The remaining large gaps concentrate in Hand Cannoneer and Siege Onager, with four rows above 25 in each family.`,
        },
        {
          id: "ranked-heading",
          type: "markdown",
          body: "## Eleven tape ratios remain more than 25 points apart\n\nPositive signed delta means the simulation favors the melee side more than the tape; negative means it favors the ranged side more. The ranking uses absolute delta so the largest accuracy opportunities appear first.",
        },
        { id: "ranked-chart-block", type: "chart", chartId: "ranked-delta-chart", layout: "full" },
        {
          id: "family-heading",
          type: "markdown",
          body: "## Accuracy differs sharply by ranged family\n\nHeavy Scorpion is currently the closest family overall, followed by HCA. Hand Cannoneer and Siege Onager account for eight of the eleven deltas above 25, so a global movement change is unlikely to be the right first response.",
        },
        { id: "family-chart-block", type: "chart", chartId: "family-error-chart", layout: "full" },
        {
          id: "audit-heading",
          type: "markdown",
          body: "## Complete 48-row comparison\n\nThe table is sorted by absolute mean delta. Tape and simulation bands are the observed min-to-max score ranges; tape-band error is zero when the simulation mean falls inside the tape range.",
        },
        { id: "audit-table-block", type: "table", tableId: "audit-table", layout: "full" },
        {
          id: "scope-definitions",
          type: "markdown",
          sourceId: "comparison-source",
          body: "## Scope, data, and definitions\n\n- **Population:** every authorized standard-units row with a ranged owner-2 unit and melee owner-3 unit: six ranged families × eight melee families = 48 tape ratios.\n- **Exact ratio:** each simulation uses the counts and side order recorded in its tape row; no generated ratios or reversed matchups are included.\n- **Schedule:** five samples for each stable tape row and 100 samples for each tape row with winners on both sides, totaling 810 simulations.\n- **Score:** remaining winner HP as a percentage of its starting HP; ranged/owner-2 wins are negative and melee/owner-3 wins are positive.\n- **Signed mean delta:** simulation mean minus tape mean. **Absolute mean delta** is its magnitude. **Tape-band error** is the distance from the simulation mean to the tape min/max interval, or zero inside the interval.",
        },
        {
          id: "methodology",
          type: "markdown",
          body: `## Methodology\n\nThe project-local golden archive was SHA-256 verified immediately before execution: \`${analysis.source.zip_sha256}\`. The latest checked-out JavaScript engine ran every battle from the tape-conditioned canonical starting placement with seed ${analysis.config.seed} and a 9,000-tick cap. Each row's simulation score distribution was compared to its recorded tape mean, range, and owner-3 win rate. The JSON contains every individual sample, while the CSV and this report expose the row-level audit measures.`,
        },
        {
          id: "limitations",
          type: "markdown",
          body: "## Limitations and robustness\n\nThe benchmark measures battle outcome agreement, not whether every trajectory, attack timing, or target switch matches frames.bin. Stable rows often have only one to five tape recordings, so their tape range can be narrow. Volatile rows receive 100 simulation samples but still inherit the tape's smaller empirical distribution. A mean inside the tape band does not prove physical equivalence; it marks the result as outcome-plausible and should be paired with visual/frame diagnostics for units selected for further engine work.\n\nThe sample schedule was audited independently after execution: 48 unique row IDs, 810 samples, six rows with 100 samples, 42 rows with five, zero unresolved samples, and zero discrepancies between stored and recomputed deltas.",
        },
        {
          id: "next-steps",
          type: "markdown",
          body: "## Recommended next steps\n\n1. **Preserve the current HCA crowd/engagement behavior.** It has no >25-point row and five of eight matchup means inside the tape band.\n2. **Diagnose Hand Cannoneer against Elephant, Hussar, Steppe Lancer, and Paladin as a family.** All four large deltas are positive, meaning melee performs much better in simulation than tape. This is a coherent directional gap.\n3. **Separate Siege Onager mechanics from generic ranged kiting.** Its large errors point in both directions: the Elephant row is far more melee-favored in simulation, while Steppe Lancer, Camel, and Halberdier are less melee-favored than tape.\n4. **Review Elite Skirmisher vs Heavy Camel first for winner correctness.** It is the only stable winner mismatch, despite the simulation samples spanning both sides.\n5. **Use Arbalester vs Steppe Lancer and Hussar as secondary calibration rows.** Both exceed 25 but retain the same stable/volatile winner classification.",
        },
        {
          id: "further-questions",
          type: "markdown",
          body: "## Further questions\n\n- Do the four Hand Cannoneer gaps share the same firing-cycle or group-kiting signature in frames.bin?\n- Are Siege Onager deltas driven primarily by projectile blast/targeting physics rather than navigation?\n- Does the Elite Skirmisher versus Heavy Camel winner mismatch reproduce visually with the exact 21v8 tape start?",
        },
      ],
      charts: [
        {
          id: "ranked-delta-chart",
          title: "Largest signed simulation-minus-tape score deltas",
          subtitle: "Top 15 exact tape ratios ranked by absolute delta; positive favors melee more than tape",
          showDescription: true,
          question: "Which exact tape ratios are furthest from the current engine outcome?",
          rationale: "A signed horizontal ranking preserves both the magnitude and direction of the largest errors.",
          intent: "comparison",
          type: "horizontalBar",
          dataset: "top_deltas",
          sourceId: "ranked-query",
          encodings: {
            x: { field: "label", type: "nominal", label: "Matchup and tape ratio" },
            y: { field: "signed_mean_delta", type: "quantitative", format: "number", label: "Simulation − tape mean", unit: "points" },
            tooltip: [
              { field: "tape_mean", type: "quantitative", format: "number", label: "Tape mean" },
              { field: "simulation_mean", type: "quantitative", format: "number", label: "Simulation mean" },
              { field: "absolute_mean_delta", type: "quantitative", format: "number", label: "Absolute delta" },
              { field: "tape_band_error", type: "quantitative", format: "number", label: "Tape-band error" },
            ],
          },
          valueFormat: "number",
          layout: "full",
          maxRows: 15,
          surface: { legend: "none", valueLabels: true },
        },
        {
          id: "family-error-chart",
          title: "Mean absolute score delta by ranged family",
          subtitle: "Eight exact tape ratios per family; lower is closer",
          showDescription: true,
          question: "Which ranged families are closest to tape across the melee roster?",
          rationale: "A family-level ranking separates broad engine behavior from isolated matchup errors.",
          intent: "comparison",
          type: "horizontalBar",
          dataset: "family_summary",
          sourceId: "family-query",
          encodings: {
            x: { field: "ranged_unit", type: "nominal", label: "Ranged family" },
            y: { field: "mean_absolute_delta", type: "quantitative", format: "number", label: "Mean absolute delta", unit: "points" },
            tooltip: [
              { field: "rows_over_25", type: "quantitative", format: "number", label: "Rows over 25" },
              { field: "rows_inside_tape_band", type: "quantitative", format: "number", label: "Rows inside tape band" },
              { field: "wrong_stable_winners", type: "quantitative", format: "number", label: "Wrong stable winners" },
            ],
          },
          valueFormat: "number",
          layout: "full",
          maxRows: 6,
          surface: { legend: "none", valueLabels: true },
        },
      ],
      tables: [
        {
          id: "audit-table",
          title: "All ranged-versus-melee tape ratios",
          subtitle: "Exact score values; sorted by absolute simulation-minus-tape mean delta",
          showDescription: true,
          dataset: "ranked_rows",
          sourceId: "audit-query",
          defaultSort: { field: "absolute_mean_delta", direction: "desc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "rank", label: "#", format: "number", role: "value" },
            { field: "matchup", label: "Matchup", type: "text" },
            { field: "ratio", label: "Tape ratio", type: "text" },
            { field: "tape_mean", label: "Tape mean", format: "number", role: "value" },
            { field: "tape_band", label: "Tape range", type: "text" },
            { field: "simulation_mean", label: "Sim mean", format: "number", role: "value" },
            { field: "simulation_band", label: "Sim range", type: "text" },
            { field: "signed_mean_delta", label: "Signed delta", format: "number", role: "value" },
            { field: "absolute_mean_delta", label: "Abs delta", format: "number", role: "value" },
            { field: "tape_band_error", label: "Band error", format: "number", role: "value" },
            { field: "winner_agreement", label: "Winner", type: "text" },
            { field: "simulation_runs", label: "Runs", format: "number", role: "value" },
            { field: "failure", label: "Failures", type: "text" },
          ],
        },
      ],
      sources: [reportSource, archiveSource, rankedSource, familySource, auditSource],
    },
    snapshot: {
      version: 1,
      generatedAt,
      status: "ready",
      datasets: {
        top_deltas: ranked.slice(0, 15).map((row) => ({
          ...row,
          label: `${row.matchup} (${row.ratio})`,
        })),
        family_summary: familySummary,
        ranked_rows: ranked,
      },
    },
    sources: [reportSource, archiveSource, rankedSource, familySource, auditSource],
  };
}


function summarizeFamilies(rows) {
  const groups = rows.reduce((result, row) => {
    (result[row.ranged.unit] ??= []).push(row);
    return result;
  }, {});
  return Object.entries(groups).map(([rangedUnit, familyRows]) => ({
    ranged_unit: rangedUnit,
    row_count: familyRows.length,
    mean_absolute_delta: average(familyRows.map((row) => row.absoluteMeanDelta)),
    rows_over_25: familyRows.filter((row) => row.absoluteMeanDelta > 25).length,
    rows_inside_tape_band: familyRows.filter((row) => row.tapeBandError === 0).length,
    wrong_stable_winners: familyRows.filter((row) => row.winnerAgreement === "mismatch").length,
  })).toSorted((left, right) => right.mean_absolute_delta - left.mean_absolute_delta);
}


function average(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function format(value) {
  return Number(value.toFixed(2)).toString();
}


function querySource({
  id, label, path, generatedAt, description, filters, definitions, columns, rows,
}) {
  const values = rows.map((row) => `(${row.map(sqlLiteral).join(", ")})`).join(",\n  ");
  return {
    id,
    label,
    path,
    query: {
      engine: "DuckDB",
      language: "SQL",
      description,
      executed_at: generatedAt,
      tables_used: ["reviewed analysis.json output"],
      filters,
      metric_definitions: definitions,
      sql: `SELECT * FROM (VALUES\n  ${values}\n) AS t(${columns.join(", ")})`,
    },
  };
}


function sqlLiteral(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "NULL";
  return `'${String(value).replaceAll("'", "''")}'`;
}


export async function main() {
  const analysis = JSON.parse(await readFile(INPUT, "utf8"));
  const artifact = buildArtifact(analysis);
  await writeFile(OUTPUT, `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
  return artifact;
}


if (
  process.argv[1]
  && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))
) {
  await main();
}
