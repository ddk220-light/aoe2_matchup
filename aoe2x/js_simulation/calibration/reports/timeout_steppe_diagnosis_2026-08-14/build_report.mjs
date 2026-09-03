import { readFile, writeFile } from "node:fs/promises";

const reportDirectory = new URL("./", import.meta.url);
const analysis = await readFile(new URL("analysis.json", reportDirectory), "utf8").then(JSON.parse);
const tapeTrace = await readFile(new URL("steppe_tape_trace_analysis.json", reportDirectory), "utf8").then(JSON.parse);
const current = await readFile(new URL("steppe_current_event_analysis.json", reportDirectory), "utf8").then(JSON.parse);
const baselineNavigation = await readFile(
  new URL("steppe_navigation_counterfactual.json", reportDirectory),
  "utf8",
).then(JSON.parse);

const generatedAt = new Date().toISOString();
const currentRow = current.rows[0];
const baselineRow = baselineNavigation.rows[0];
const timeoutState = analysis.timeoutStates[0].states[0];

const durationSource = {
  id: "duration-analysis",
  label: "Current-engine duration and timeout analysis",
  path: "aoe2x/js_simulation/calibration/reports/timeout_steppe_diagnosis_2026-08-14/analysis.json",
  query: {
    language: "sql",
    engine: "portable-snapshot",
    sql: "SELECT statistic, seconds FROM duration_distribution ORDER BY seconds ASC; SELECT measure, value FROM timeout_policy; SELECT matchup, meanAbsoluteDelta, maxAbsoluteDelta, rowsAbove25, wrongWinnerRuns FROM steppe_controls ORDER BY meanAbsoluteDelta DESC;",
    description: "Aggregates 425 exact golden-ratio attempts from the recoverable current-engine comparison run and inspects the retained world state for every timeout.",
    tables_used: [
      "aoe2x/js_simulation/calibration/reports/dedicated_ranged_melee_steering_050_parallel_2026-08-14/results.json",
    ],
    filters: [
      "Authorized golden-kiting matchups only",
      "Five simulation attempts per golden row",
      "Resolved-duration statistics exclude timeouts",
    ],
    metric_definitions: {
      duration_seconds: "Simulation ticks divided by the engine clock rate of 60 ticks per second.",
      normalized_remaining_hp: "Side remaining HP divided by that side's starting HP.",
      knife_edge: "Proposed reporting outcome when both sides have lost at least 50% of starting HP and normalized remaining-HP fractions are within 5 percentage points at the hard cap.",
    },
  },
};

const traceSource = {
  id: "steppe-tape-trace",
  label: "Verified HCA versus Elite Steppe Lancer 20v20 tape trace",
  path: "aoe2x/js_simulation/calibration/reports/timeout_steppe_diagnosis_2026-08-14/steppe_tape_trace_analysis.json",
  query: {
    language: "javascript",
    description: "Decodes repeat 1 frames.bin and tape trace from the SHA-verified authorized HCA-versus-Steppe golden archive.",
    tables_used: [
      "aoe2x/js_simulation/calibration/reports/timeout_steppe_diagnosis_2026-08-14/tape/20v20.tape_trace.jsonl",
    ],
    filters: ["Ratio: 20 HCA versus 20 Elite Steppe Lancers", "Repeat: 1"],
    metric_definitions: {
      tape_attack_actions: "Entries into decoded action_state 7; a tape proxy for attack starts rather than an engine event count.",
      signed_outcome_score: "Winner remaining HP divided by winner starting HP, multiplied by 100; negative is an HCA win and positive is a Steppe Lancer win.",
    },
  },
};

const engineSource = {
  id: "steppe-engine-control",
  label: "Exact-start current engine and navigation isolation control",
  path: "aoe2x/js_simulation/calibration/reports/timeout_steppe_diagnosis_2026-08-14/steppe_navigation_counterfactual.json",
  query: {
    language: "sql",
    engine: "portable-snapshot",
    sql: "SELECT conditionAndSide, attackCycles FROM exchange_cycles; SELECT condition, outcomeScore, winner, steppeAttackActivity, steppeDamagingHits, hcaAttackActivity, firstSteppeDamageSeconds FROM navigation_conditions;",
    description: "Runs the same exact 20v20 start once with current cohesive kiter navigation and once with only kiteNavigation omitted; combat mechanics, starting units, map, steering strength, and tick limit remain unchanged.",
    tables_used: [
      "aoe2x/js_simulation/calibration/reports/timeout_steppe_diagnosis_2026-08-14/steppe_current_event_analysis.json",
      "aoe2x/js_simulation/calibration/reports/timeout_steppe_diagnosis_2026-08-14/steppe_navigation_counterfactual.json",
    ],
    filters: [
      "Ratio: 20 HCA versus 20 Elite Steppe Lancers",
      "Exact starting state: golden repeat 1",
      "One deterministic run per condition",
      "Isolation change: omit scenario.kiteNavigation only",
    ],
    metric_definitions: traceSource.query.metric_definitions,
  },
};

const archiveSource = {
  id: "authorized-steppe-archive",
  label: "Authorized HCA versus Elite Steppe Lancer golden archive",
  path: "aoe2x/js_simulation/calibration/source/aoe2_golden_kiting_hcavarchervssteppe_2026-08-06.zip",
  sha256: tapeTrace.zipSha256,
};

const durationDistribution = [
  { statistic: "Mean", seconds: analysis.duration.meanSeconds },
  { statistic: "Median", seconds: analysis.duration.medianSeconds },
  { statistic: "P90", seconds: analysis.duration.p90Seconds },
  { statistic: "P95", seconds: analysis.duration.p95Seconds },
  { statistic: "P99", seconds: analysis.duration.p99Seconds },
  { statistic: "Longest resolved", seconds: analysis.duration.maxSeconds },
  { statistic: "Hard cap", seconds: analysis.duration.tickLimitSeconds },
];

const steppeControls = analysis.steppeMatchups.map((row) => ({
  matchup: row.matchup,
  meanAbsoluteDelta: row.meanAbsoluteDelta,
  maxAbsoluteDelta: row.maxAbsoluteDelta,
  rowsAbove25: row.rowsAbove25,
  wrongWinnerRuns: row.wrongWinnerRuns,
}));

const exchangeCycles = [
  { conditionAndSide: "Tape - HCA", attackCycles: tapeTrace.attackActionEntries.owner2Hca },
  { conditionAndSide: "Tape - Steppe", attackCycles: tapeTrace.attackActionEntries.owner3Steppe },
  { conditionAndSide: "Current cohesive - HCA", attackCycles: currentRow.meanHcaAttackStarts },
  { conditionAndSide: "Current cohesive - Steppe", attackCycles: currentRow.meanAttackStarts },
  { conditionAndSide: "Baseline navigation - HCA", attackCycles: baselineRow.meanHcaAttackStarts },
  { conditionAndSide: "Baseline navigation - Steppe", attackCycles: baselineRow.meanAttackStarts },
];

const navigationConditions = [
  {
    condition: "Tape repeat 1",
    outcomeScore: tapeTrace.tapeOutcome.signedScore,
    winner: "Elite Steppe Lancer",
    steppeAttackActivity: tapeTrace.attackActionEntries.owner3Steppe,
    steppeDamagingHits: 160,
    hcaAttackActivity: tapeTrace.attackActionEntries.owner2Hca,
    firstSteppeDamageSeconds: tapeTrace.firstHpLossSeconds.owner2Hca,
  },
  {
    condition: "Current cohesive navigation",
    outcomeScore: currentRow.simulationMean,
    winner: "Heavy Cav Archer",
    steppeAttackActivity: currentRow.meanAttackStarts,
    steppeDamagingHits: currentRow.meanDamagingHits,
    hcaAttackActivity: currentRow.meanHcaAttackStarts,
    firstSteppeDamageSeconds: currentRow.meanFirstDamageSeconds,
  },
  {
    condition: "Baseline kiter navigation",
    outcomeScore: baselineRow.simulationMean,
    winner: "Elite Steppe Lancer",
    steppeAttackActivity: baselineRow.meanAttackStarts,
    steppeDamagingHits: baselineRow.meanDamagingHits,
    hcaAttackActivity: baselineRow.meanHcaAttackStarts,
    firstSteppeDamageSeconds: baselineRow.meanFirstDamageSeconds,
  },
];

const timeoutPolicy = [
  { measure: "Hard cap", value: "9,000 ticks / 150 seconds / 2.5 minutes" },
  { measure: "Resolved mean", value: `${analysis.duration.meanSeconds} seconds` },
  { measure: "Resolved P99", value: `${analysis.duration.p99Seconds} seconds` },
  { measure: "Longest resolved", value: `${analysis.duration.maxSeconds} seconds` },
  { measure: "Resolved fights beyond 120 seconds", value: "0 of 420" },
  { measure: "Timed-out final state", value: "Elite Skirmisher 5 HP vs Champion 8 HP" },
  { measure: "Normalized HP separation", value: `${timeoutState.normalizedHpLeadOwner3Points} percentage points` },
  { measure: "Recommended label", value: "Knife edge" },
];

const sources = [durationSource, traceSource, engineSource, archiveSource];
const artifact = {
  surface: "report",
  manifest: {
    version: 1,
    surface: "report",
    title: "Fight time limit and HCA-Steppe Lancer diagnosis",
    description: "Decision-ready timeout policy and causal diagnosis of the Heavy Cav Archer versus Elite Steppe Lancer regression.",
    generatedAt,
    blocks: [
      {
        id: "title",
        type: "markdown",
        layout: "full",
        body: "# Fight time limit and HCA-Steppe Lancer diagnosis",
      },
      {
        id: "executive-summary",
        type: "markdown",
        layout: "full",
        sourceId: "duration-analysis",
        body: "## Keep the 9,000-tick cap and classify the sole timeout as a knife edge\n\nAt 60 ticks per second, **9,000 ticks is 150 seconds, or 2 minutes 30 seconds**. The 420 resolved attempts average **43.39s**, the 99th percentile is **112.94s**, and the longest is **114.43s**; none exceeds two minutes. The only timed-out row ends with one Elite Skirmisher at 5/350 starting HP versus one Champion at 8/350, a normalized separation of only 0.86 percentage points. Raising the cap would add runtime without improving the interpretation.",
      },
      {
        id: "duration-chart-intro",
        type: "markdown",
        layout: "full",
        sourceId: "duration-analysis",
        body: "## The existing cap already has comfortable headroom\n\nThe cap is **35.57s beyond the longest resolved fight** and **37.06s beyond P99**. This is enough separation to treat a surviving fight at the cap as a reporting outcome rather than an engine crash.",
      },
      { id: "duration-chart-block", type: "chart", layout: "full", chartId: "duration-chart" },
      {
        id: "timeout-policy-intro",
        type: "markdown",
        layout: "full",
        sourceId: "duration-analysis",
        body: "## Use normalized HP only for non-knife-edge time-limit decisions\n\nAt the cap, first check whether both sides have lost at least 50% of starting HP and their normalized remaining-HP fractions are within 5 percentage points. If so, report **knife edge**. Otherwise report a provisional **time-limit leader** using remaining HP divided by that side's starting HP, never raw HP. This avoids declaring the current 8-HP Champion a meaningful winner over the 5-HP Skirmisher.",
      },
      { id: "timeout-policy-table-block", type: "table", layout: "full", tableId: "timeout-policy-table" },
      {
        id: "steppe-scope",
        type: "markdown",
        layout: "full",
        sourceId: "duration-analysis",
        body: "## The bad Steppe result is specific to the fast HCA interaction\n\nElite Steppe Lancer outcomes are already close against slower ranged controls: Arbalester rows have **8.36 mean absolute delta** and no wrong winners; Elite Skirmisher rows have **2.03** and no wrong winners. Only HCA rows deteriorate to **32.65 mean absolute delta**, three rows above 25 points, and five wrong-winner runs. That rules out a broad Steppe attack-stat or +1-range failure.",
      },
      { id: "steppe-controls-table-block", type: "table", layout: "full", tableId: "steppe-controls-table" },
      {
        id: "causal-finding",
        type: "markdown",
        layout: "full",
        sourceId: "steppe-engine-control",
        body: "## Cohesive HCA navigation is the decisive regression\n\nIn the exact 20v20 start, the current cohesive layer produces an HCA win at **-41.87**, while tape produces a Steppe win at **+25.75**. Omitting only `kiteNavigation` flips the same simulation to a Steppe win at **+33.25**, just 7.5 points from tape. It restores **173 Steppe attack starts and 160 damaging hits**, almost exactly the tape's **169 attack-action entries and about 160 effective hits**. No combat statistic, reach rule, spawn, map, steering strength, or time cap changed in this isolation.",
      },
      { id: "exchange-chart-block", type: "chart", layout: "full", chartId: "exchange-chart" },
      { id: "navigation-table-block", type: "table", layout: "full", tableId: "navigation-table" },
      {
        id: "mechanism",
        type: "markdown",
        layout: "full",
        sourceId: "steppe-tape-trace",
        body: "## The +1 reach works; sustained pressure does not\n\nThe Lancers do not arrive late: current simulation damage begins at **2.20s**, earlier than the tape's first HCA HP loss at **4.04s**. Once an engine swing starts, 93 of 99 attacks damage, so attack cancellation is small. The divergence is repeated cycling under pressure: cohesive navigation lets HCA produce **513 attack starts**, 31.5% above tape's 390, while Steppe starts fall to 99, 41.4% below tape's 169. The baseline-navigation control reverses both distortions. The most likely mechanism is that the cohesive formation keeps HCA moving and scheduling volleys as an orderly protected group after contact, while near-equal-speed Lancers repeatedly lose a stable outer-reach attack position.",
      },
      {
        id: "recommendation",
        type: "markdown",
        layout: "full",
        body: "## Recommended engine direction\n\nDo not tune Elite Steppe Lancer damage, speed, or a matchup-specific range constant. Preserve the generic reach envelope and fix the cohesive kiter-navigation response to sustained melee contact: pressure should disrupt clean group translation and repeated ranged firing, while allowing reach melee already in the contact shell to chain attacks. Validate any navigation-level change against all five HCA-Steppe ratios and the already-good Arbalester-Steppe and Elite Skirmisher-Steppe controls.",
      },
      {
        id: "caveats",
        type: "markdown",
        layout: "full",
        sourceId: "steppe-engine-control",
        body: "## Scope and caveats\n\nThe outcome statistics cover five runs for every golden row. The event-level causal isolation uses one deterministic exact-start 20v20 repeat; its near-exact restoration of both winner and attack exchange is strong causal evidence, but the candidate fix still needs the full five-ratio regression suite. Tape action-state 7 is a behavioral proxy for attack starts, not a byte-identical engine event. This work changed no engine source files.",
      },
    ],
    charts: [
      {
        id: "duration-chart",
        title: "Resolved fight duration statistics and hard cap",
        description: "Seconds across 420 resolved current-engine attempts; timeouts excluded from distribution statistics.",
        type: "bar",
        intent: "comparison",
        question: "How much headroom does the 150-second cap have over normal fight durations?",
        rationale: "A bar comparison makes the high-percentile tail and cap separation directly visible.",
        dataset: "duration_distribution",
        encodings: { x: { field: "statistic" }, y: { field: "seconds" } },
        labels: { values: "all" },
        sourceId: "duration-analysis",
      },
      {
        id: "exchange-chart",
        title: "Attack cycles in HCA versus Elite Steppe Lancer 20v20",
        description: "Tape action-state entries compared with engine attack-start events for the same exact start.",
        type: "bar",
        intent: "comparison",
        question: "Which navigation condition reproduces the tape attack exchange?",
        rationale: "The side-by-condition labels show both the excess HCA firing and the missing Steppe follow-up attacks.",
        dataset: "exchange_cycles",
        encodings: { x: { field: "conditionAndSide" }, y: { field: "attackCycles" } },
        labels: { values: "all" },
        sourceId: "steppe-engine-control",
      },
    ],
    tables: [
      {
        id: "timeout-policy-table",
        title: "Duration evidence and proposed timeout disposition",
        description: "The current 9,000-tick cap and the only observed timeout state.",
        dataset: "timeout_policy",
        columns: [
          { field: "measure", label: "Measure" },
          { field: "value", label: "Value" },
        ],
        defaultSort: { field: "measure", direction: "asc" },
        sourceId: "duration-analysis",
      },
      {
        id: "steppe-controls-table",
        title: "Elite Steppe Lancer accuracy by ranged opponent",
        description: "Five golden ratios per matchup, five simulation runs per ratio.",
        dataset: "steppe_controls",
        columns: [
          { field: "matchup", label: "Matchup" },
          { field: "meanAbsoluteDelta", label: "Mean abs. delta", format: "number" },
          { field: "maxAbsoluteDelta", label: "Max abs. delta", format: "number" },
          { field: "rowsAbove25", label: "Rows >25", format: "number" },
          { field: "wrongWinnerRuns", label: "Wrong-winner runs", format: "number" },
        ],
        defaultSort: { field: "meanAbsoluteDelta", direction: "desc" },
        sourceId: "duration-analysis",
      },
      {
        id: "navigation-table",
        title: "Exact-start 20v20 tape and navigation isolation",
        description: "Positive outcome score is a Steppe win; negative is an HCA win.",
        dataset: "navigation_conditions",
        columns: [
          { field: "condition", label: "Condition" },
          { field: "outcomeScore", label: "Outcome score", format: "number" },
          { field: "winner", label: "Winner" },
          { field: "steppeAttackActivity", label: "Steppe attack activity", format: "number" },
          { field: "steppeDamagingHits", label: "Steppe damaging hits", format: "number" },
          { field: "hcaAttackActivity", label: "HCA attack activity", format: "number" },
          { field: "firstSteppeDamageSeconds", label: "First Steppe damage (s)", format: "number" },
        ],
        defaultSort: { field: "condition", direction: "asc" },
        sourceId: "steppe-engine-control",
      },
    ],
    sources,
  },
  snapshot: {
    version: 1,
    status: "ready",
    generatedAt,
    datasets: {
      duration_distribution: durationDistribution,
      timeout_policy: timeoutPolicy,
      steppe_controls: steppeControls,
      exchange_cycles: exchangeCycles,
      navigation_conditions: navigationConditions,
    },
    accessIssues: [],
  },
  sources,
};

await writeFile(new URL("artifact.json", reportDirectory), `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
process.stdout.write(new URL("artifact.json", reportDirectory).pathname);
