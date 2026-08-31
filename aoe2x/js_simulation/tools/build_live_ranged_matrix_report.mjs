import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";


const DEFAULT_INPUT = resolve(
  "calibration/reports/ranged_matrix_patrol_engine_2026-08-30/results.json",
);
const DEFAULT_OUTPUT = resolve(
  "calibration/reports/ranged_combat_comprehensive_2026-08-29/artifact.json",
);
const VIEWER_BASE = "https://starlight.tail82a190.ts.net/golden-map/";
const LIVE_MANIFEST =
  "aoe2x/js_simulation/calibration/live_observations/ranged_matrix_5x_2026-08-29/capture_manifest.json";
const LIVE_FRAMES_ANALYSIS =
  "aoe2x/js_simulation/calibration/live_observations/ranged_matrix_5x_2026-08-29/grpc_matrix_analysis.json";
const COMPARISON_RESULTS =
  "aoe2x/js_simulation/calibration/reports/ranged_matrix_patrol_engine_2026-08-30/results.json";
const ARB_HCA_DIAGNOSTIC =
  "aoe2x/js_simulation/calibration/reports/ranged_matrix_patrol_engine_2026-08-30/arbalester_vs_heavy_cav_archer_diagnostic.json";
const HP_TARGET = 0.20;


const UNIT_LABELS = Object.freeze({
  arbalester: "Arbalester",
  champion: "Champion",
  elite_steppe: "Elite Steppe Lancer",
  hand_cannoneer: "Hand Cannoneer",
  heavy_cav_archer: "Heavy Cavalry Archer",
  hussar: "Hussar",
  paladin: "Paladin",
});


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function round(value, digits = 2) {
  if (!Number.isFinite(value)) return null;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


function signed(value, digits = 2) {
  if (!Number.isFinite(value)) return "N/A";
  const rounded = value.toFixed(digits);
  return value > 0 ? `+${rounded}` : rounded.replace("-", "−");
}


function familyLabel(value) {
  return value.split("_").map((part, index) => (
    index === 0 ? `${part[0].toUpperCase()}${part.slice(1)}` : part
  )).join(" ");
}


function matchupLabel(row) {
  const side = (value) => `${value.civ} ${UNIT_LABELS[value.slug] ?? value.slug} (${value.count})`;
  return `${side(row.side2)} vs ${side(row.side3)}`;
}


function classify(row) {
  const attempts = row.simulation.runs.length;
  const completed = row.simulation.runs.filter(({ score }) => Number.isFinite(score));
  const liveOwners = [...new Set(row.tape.winnerOwners)];
  const stableLiveWinner = liveOwners.length === 1 ? liveOwners[0] : null;
  const wrongWinnerSeeds = stableLiveWinner === null
    ? completed.length
    : completed.filter(({ winnerOwner }) => winnerOwner !== stableLiveWinner).length;
  const timeoutSeeds = row.simulation.runs
    .filter(({ score }) => !Number.isFinite(score))
    .map(({ openingSeed }) => openingSeed);
  const completedAll = completed.length === attempts;
  const allWinnersCorrect = stableLiveWinner !== null && wrongWinnerSeeds === 0;
  const liveWinnerHpMean = mean(row.tape.winnerHp);
  const simulationWinnerHpMean = completed.length
    ? mean(completed.map(({ winnerHp }) => winnerHp)
    ) : null;
  const hpDelta = completedAll && allWinnersCorrect
    ? simulationWinnerHpMean - liveWinnerHpMean
    : null;
  const hpDeltaPct = hpDelta === null ? null : Math.abs(hpDelta) / liveWinnerHpMean;
  const simulationScore = completed.length ? mean(completed.map(({ score }) => score)) : null;
  const scoreGap = completedAll ? simulationScore - row.tape.mean : null;

  let className;
  let verdict;
  let priorityClass;
  if (!completedAll) {
    className = "unresolved";
    verdict = `UNRESOLVED — ${timeoutSeeds.length}/${attempts} timeout`;
    priorityClass = 0;
  } else if (!allWinnersCorrect) {
    className = "wrong-winner";
    verdict = stableLiveWinner === null
      ? "LIVE WINNER VARIES"
      : `WRONG WINNER — ${wrongWinnerSeeds}/${attempts} seeds`;
    priorityClass = 1;
  } else if (hpDeltaPct > HP_TARGET) {
    className = "hp-outside-target";
    verdict = "HP OUTSIDE TARGET";
    priorityClass = 2;
  } else {
    className = "pass";
    verdict = "MEETS TARGET";
    priorityClass = 3;
  }

  return {
    row,
    attempts,
    completed,
    stableLiveWinner,
    wrongWinnerSeeds,
    timeoutSeeds,
    completedAll,
    allWinnersCorrect,
    liveWinnerHpMean,
    simulationWinnerHpMean,
    hpDelta,
    hpDeltaPct,
    simulationScore,
    scoreGap,
    className,
    verdict,
    priorityClass,
  };
}


function problemSeverity(row) {
  if (row.className === "unresolved") return row.timeoutSeeds.length * 1000 + row.wrongWinnerSeeds * 100;
  if (row.className === "wrong-winner") return row.wrongWinnerSeeds * 1000;
  return (row.hpDeltaPct ?? 0) * 1000;
}


function displayRow(item, priority) {
  const seedOwners = item.row.simulation.runs.map((run) => (
    Number.isFinite(run.score) ? `P${run.winnerOwner}` : `seed ${run.openingSeed} timeout`
  ));
  const hpDisplay = item.hpDeltaPct === null
    ? "Not valid"
    : `${(item.hpDeltaPct * 100).toFixed(1)}% (${signed(item.hpDelta, 1)} HP)`;
  const scoreDisplay = item.simulationScore === null
    ? "Unresolved"
    : `${signed(item.simulationScore)}${item.completedAll ? "" : ` completed ${item.completed.length}/${item.attempts}`}`;
  return {
    priority,
    verdict: item.verdict,
    matchup: matchupLabel(item.row),
    family: familyLabel(item.row.family),
    live_score: round(item.row.tape.mean),
    sim_score_display: scoreDisplay,
    score_gap_display: item.scoreGap === null ? "Not valid" : `${signed(item.scoreGap)} points`,
    live_winner_hp: round(item.liveWinnerHpMean, 1),
    sim_winner_hp_display: item.simulationWinnerHpMean === null
      ? "N/A"
      : `${round(item.simulationWinnerHpMean, 1)}${item.completedAll ? "" : " (completed seeds)"}`,
    hp_delta_display: hpDisplay,
    wrong_winner_seeds: item.wrongWinnerSeeds,
    timeout_seeds: item.timeoutSeeds.length,
    seed_record: seedOwners.join(", "),
  };
}


function representativeRun(item) {
  const completed = item.completed;
  if (completed.length === 0) return null;
  const wrong = item.stableLiveWinner === null
    ? completed
    : completed.filter(({ winnerOwner }) => winnerOwner !== item.stableLiveWinner);
  const candidates = wrong.length ? wrong : completed;
  const target = wrong.length
    ? mean(candidates.map(({ score }) => score))
    : item.simulationWinnerHpMean;
  const distance = wrong.length
    ? ({ score }) => Math.abs(score - target)
    : ({ winnerHp }) => Math.abs(winnerHp - target);
  return candidates.toSorted((left, right) => (
    distance(left) - distance(right) || left.openingSeed - right.openingSeed
  ))[0];
}


function problemViewerUrl(item) {
  const url = new URL(VIEWER_BASE);
  url.searchParams.set("mode", "problem-matchups");
  url.searchParams.set("matchup", item.row.key);
  return url.href;
}


export async function buildReport({ input = DEFAULT_INPUT, output = DEFAULT_OUTPUT } = {}) {
  const diagnosticPath = resolve(dirname(input), "arbalester_vs_heavy_cav_archer_diagnostic.json");
  const [report, arbHcaDiagnostic] = await Promise.all([
    readFile(input, "utf8").then(JSON.parse),
    readFile(diagnosticPath, "utf8").then(JSON.parse),
  ]);
  if (report.rows.length !== 14) throw new Error(`expected 14 matchups, found ${report.rows.length}`);
  const classified = report.rows.map(classify);
  const problemRows = classified
    .filter(({ className }) => className !== "pass")
    .sort((left, right) => (
      left.priorityClass - right.priorityClass || problemSeverity(right) - problemSeverity(left)
    ));
  const passingRows = classified.filter(({ className }) => className === "pass");
  const unresolved = classified.filter(({ className }) => className === "unresolved");
  const wrongWinners = classified.filter(({ className }) => className === "wrong-winner");
  const hpMisses = classified.filter(({ className }) => className === "hp-outside-target");
  const completedAttempts = classified.reduce((total, item) => total + item.completed.length, 0);
  const totalAttempts = classified.reduce((total, item) => total + item.attempts, 0);
  const stableLiveRows = classified.filter(({ stableLiveWinner }) => stableLiveWinner !== null).length;
  const resolvedCorrect = classified.filter(({ completedAll, allWinnersCorrect }) => (
    completedAll && allWinnersCorrect
  ));
  const generatedAt = new Date().toISOString();
  const allSorted = classified.toSorted((left, right) => (
    left.priorityClass - right.priorityClass || problemSeverity(right) - problemSeverity(left)
  ));
  const allRows = allSorted.map((item, index) => displayRow(item, index + 1));
  const problemDataset = problemRows.map((item, index) => displayRow(item, index + 1));
  const viewerProblemRows = problemRows.map((item) => {
    const representative = representativeRun(item);
    if (!representative) {
      throw new Error(`${item.row.key} has no completed seed to expose in the viewer`);
    }
    const wrongWinnerSeedNumbers = item.completed
      .filter(({ winnerOwner }) => winnerOwner !== item.stableLiveWinner)
      .map(({ openingSeed }) => openingSeed);
    const issue = item.className === "unresolved"
      ? `${item.timeoutSeeds.length}/${item.attempts} seeds time out`
      : item.className === "wrong-winner"
        ? `${item.wrongWinnerSeeds}/${item.attempts} seeds pick the wrong winner`
        : `${(item.hpDeltaPct * 100).toFixed(1)}% winner-HP delta`;
    const representativeReason = item.className === "wrong-winner"
      ? "wrong-winner seed"
      : item.className === "hp-outside-target"
        ? "completed seed closest to the simulation mean winner HP"
        : "completed seed closest to the completed-run mean";
    return Object.freeze({
      id: item.row.key,
      label: matchupLabel(item.row),
      family: item.row.family,
      status: item.className,
      issue,
      liveScore: item.row.tape.mean,
      simulationScore: item.simulationScore,
      simulationScoreIsPartial: !item.completedAll,
      liveWinnerOwner: item.stableLiveWinner,
      liveWinnerHpMean: item.liveWinnerHpMean,
      simulationWinnerHpMean: item.simulationWinnerHpMean,
      relativeWinnerHpDeltaPct: item.hpDeltaPct === null ? null : item.hpDeltaPct * 100,
      resolvedSeeds: item.completed.length,
      timeoutSeeds: item.timeoutSeeds,
      wrongWinnerSeeds: item.wrongWinnerSeeds,
      wrongWinnerSeedNumbers,
      representativeSeed: representative.openingSeed,
      representativeReason,
      representativeWinnerOwner: representative.winnerOwner,
      representativeWinnerHp: representative.winnerHp,
      viewerUrl: problemViewerUrl(item),
      side2: {
        ...item.row.side2,
        label: UNIT_LABELS[item.row.side2.slug] ?? item.row.side2.slug,
      },
      side3: {
        ...item.row.side3,
        label: UNIT_LABELS[item.row.side3.slug] ?? item.row.side3.slug,
      },
    });
  });
  const problemViewerLinks = viewerProblemRows.map((row) => (
    `- [View ${row.label} — seed ${row.representativeSeed}](${row.viewerUrl}) · ${row.issue}`
  )).join("\n");
  const resolvedDataset = resolvedCorrect
    .map((item) => ({
      matchup: matchupLabel(item.row),
      hp_delta_pct: round(item.hpDeltaPct * 100, 3),
      hp_delta: round(item.hpDelta, 1),
      live_winner_hp: round(item.liveWinnerHpMean, 1),
      sim_winner_hp: round(item.simulationWinnerHpMean, 1),
      live_score: round(item.row.tape.mean),
      sim_score: round(item.simulationScore),
      verdict: item.className === "pass" ? "Meets target" : "HP outside target",
    }))
    .sort((left, right) => right.hp_delta_pct - left.hp_delta_pct);
  const largestMiss = resolvedDataset[0] ?? null;
  const meanAbsoluteScoreError = classified
    .filter(({ completedAll }) => completedAll)
    .map(({ scoreGap }) => Math.abs(scoreGap));
  const unresolvedText = unresolved.length
    ? `${unresolved.length} matchup${unresolved.length === 1 ? " is" : "s are"} unresolved (${unresolved.map((item) => `${matchupLabel(item.row)}: ${item.timeoutSeeds.length}/${item.attempts} timeouts`).join("; ")}).`
    : "All 14 matchups resolve in all five seeds.";
  const wrongWinnerText = wrongWinners.length
    ? `${wrongWinners.length} fully resolved matchup${wrongWinners.length === 1 ? " has" : "s have"} seed-level wrong winners (${wrongWinners.map((item) => `${matchupLabel(item.row)}: ${item.wrongWinnerSeeds}/${item.attempts}`).join("; ")}).`
    : "Every fully resolved matchup chooses the live winner in all five seeds.";
  const largestMissText = largestMiss
    ? `The largest valid survivor-HP miss is **${largestMiss.matchup}** at **${largestMiss.hp_delta_pct.toFixed(1)}%** (${signed(largestMiss.hp_delta, 1)} HP).`
    : "No matchup has a valid survivor-HP comparison.";
  const opening = arbHcaDiagnostic.openingTwoSecondsAfterFirstDamage;
  const targets = arbHcaDiagnostic.firstTargetDistribution;
  const wholeFight = arbHcaDiagnostic.wholeFight;
  const damageModel = arbHcaDiagnostic.damageModel;
  const pctDelta = (simulationValue, liveValue) => (
    100 * (simulationValue - liveValue) / liveValue
  );
  const arbHcaDiagnosticRows = [
    {
      metric: "Damage per hit — Arbalester → HCA",
      live: `${damageModel.damagePerHit["2"]} HP`,
      simulation: `${damageModel.simulationMeanDamagePerRecordedHit["2"]} HP`,
      delta: "0",
      reading: `${damageModel.liveHpDeltaCompatibility.side2.compatibleIntervals}/${damageModel.liveHpDeltaCompatibility.side2.intervals} unchanged-roster live HP intervals match the 4-HP signature`,
    },
    {
      metric: "Damage per hit — HCA → Arbalester",
      live: `${damageModel.damagePerHit["3"]} HP`,
      simulation: `${damageModel.simulationMeanDamagePerRecordedHit["3"]} HP`,
      delta: "0",
      reading: `${damageModel.liveHpDeltaCompatibility.side1.compatibleIntervals}/${damageModel.liveHpDeltaCompatibility.side1.intervals} unchanged-roster live HP intervals match the 7-HP signature`,
    },
    {
      metric: "Arbalester unique first targets",
      live: targets.live["2"].uniqueTargets.toFixed(1),
      simulation: targets.simulation["2"].uniqueTargets.toFixed(1),
      delta: `+${(targets.simulation["2"].uniqueTargets - targets.live["2"].uniqueTargets).toFixed(1)}`,
      reading: "The simulator fans the opening across more cavalry archers",
    },
    {
      metric: "Arbalesters sharing the busiest first target",
      live: `${(targets.live["2"].maximumSharedTargetShare * 100).toFixed(1)}%`,
      simulation: `${(targets.simulation["2"].maximumSharedTargetShare * 100).toFixed(1)}%`,
      delta: `${(100 * (targets.simulation["2"].maximumSharedTargetShare - targets.live["2"].maximumSharedTargetShare)).toFixed(1)} pp`,
      reading: "Live is almost a single-target lock; simulation is materially dispersed",
    },
    {
      metric: "Arbalester damaging hits in opening 2 s",
      live: opening.live["2"].hits.toFixed(1),
      simulation: opening.simulation["2"].hits.toFixed(1),
      delta: `+${pctDelta(opening.simulation["2"].hits, opening.live["2"].hits).toFixed(1)}%`,
      reading: "Simulation converts the dispersed target map into nearly twice as many early hits",
    },
    {
      metric: "Distinct Arbalester opening hitters",
      live: opening.live["2"].uniqueAttackers.toFixed(1),
      simulation: opening.simulation["2"].uniqueAttackers.toFixed(1),
      delta: `+${pctDelta(opening.simulation["2"].uniqueAttackers, opening.live["2"].uniqueAttackers).toFixed(1)}%`,
      reading: "Visible idle units remain, but three times as many Arbalesters still land early hits",
    },
    {
      metric: "HCA first damage",
      live: `${opening.live["3"].firstDamageSeconds.toFixed(2)} s`,
      simulation: `${opening.simulation["3"].firstDamageSeconds.toFixed(2)} s`,
      delta: `${(opening.simulation["3"].firstDamageSeconds - opening.live["3"].firstDamageSeconds).toFixed(2)} s`,
      reading: "HCA begins dealing damage earlier in simulation, so a late first shot is not the loss mechanism",
    },
    {
      metric: "Whole-fight Arbalester damage",
      live: `${wholeFight.liveMeanDamageByOwner["2"].toFixed(1)} HP`,
      simulation: `${wholeFight.simulationMeanDamageByOwner["2"].toFixed(1)} HP`,
      delta: `+${wholeFight.simulationDamageDeltaPct["2"].toFixed(1)}%`,
      reading: "Arbalesters finish the cavalry-archer army in simulation",
    },
    {
      metric: "Whole-fight HCA damage",
      live: `${wholeFight.liveMeanDamageByOwner["3"].toFixed(1)} HP`,
      simulation: `${wholeFight.simulationMeanDamageByOwner["3"].toFixed(1)} HP`,
      delta: `${wholeFight.simulationDamageDeltaPct["3"].toFixed(1)}%`,
      reading: "Correct per-hit damage, but too few sustained attack opportunities after the opening cascade",
    },
  ];

  const source = {
    id: "patrol-engine-source",
    label: "Patrol-engine five-seed comparison",
    path: COMPARISON_RESULTS,
    query: {
      engine: "DuckDB",
      language: "SQL",
      description: "Reads the 14 matchup rows from the saved five-seed engine rerun; the report builder then applies the documented seed-level acceptance rule.",
      executed_at: generatedAt,
      tables_used: [COMPARISON_RESULTS, LIVE_MANIFEST, LIVE_FRAMES_ANALYSIS],
      filters: [
        "Current 14-matchup ranged-vs-ranged and ranged-vs-melee capture matrix",
        "Five live runs and simulation opening seeds 0-4 per matchup",
        "Pass requires 5/5 completion, 5/5 stable live winner agreement, and relative mean winner-HP error at or below 20%",
      ],
      metric_definitions: [
        "Signed score = surviving winner HP / that winner owner's starting HP × 100; negative is Player 2 and positive is Player 3.",
        "Relative winner-HP error = abs(simulation mean winner HP - live mean winner HP) / live mean winner HP, and is valid only when all five seeds resolve with the same winner as live.",
        "Exact frames.bin paths and run identifiers for all 70 live runs are recorded in grpc_matrix_analysis.json.",
      ],
      sql: `WITH document AS (SELECT rows FROM read_json_auto('${COMPARISON_RESULTS}', format = 'auto')) SELECT unnest(rows, recursive := true) FROM document`,
    },
  };
  const diagnosticSource = {
    id: "arb-hca-diagnostic-source",
    label: "Arbalester-versus-HCA focused mechanics diagnosis",
    path: ARB_HCA_DIAGNOSTIC,
    query: {
      engine: "Node.js",
      language: "JavaScript",
      description: "Reconciles five live gRPC analyses, five live aggregate-HP sidecars, and five current-engine seeds for target distribution, opening participation, damage signatures, and whole-fight damage.",
      executed_at: arbHcaDiagnostic.generatedAt,
      tables_used: [ARB_HCA_DIAGNOSTIC, LIVE_MANIFEST, LIVE_FRAMES_ANALYSIS, COMPARISON_RESULTS],
      filters: [
        "Chinese Arbalester 27 vs Saracen Heavy Cavalry Archer 18",
        "Five live repeats and simulation opening seeds 0-4",
        "Opening window is the first two raw game seconds after the first recorded damage event",
      ],
      metric_definitions: [
        "Unique opening hitters count distinct attacker slots with a damaging hit inside the opening window.",
        "Live whole-fight damage is starting enemy HP minus surviving enemy HP; all five live runs are HCA wins and all five simulation seeds are Arbalester wins.",
        "Damage-signature compatibility uses positive aggregate-HP drops only where the roster count is unchanged, avoiding capped lethal-hit intervals.",
      ],
      sql: `SELECT * FROM read_json_auto('${ARB_HCA_DIAGNOSTIC}', format = 'auto')`,
    },
  };

  const artifact = {
    surface: "report",
    manifest: {
      version: 1,
      surface: "report",
      title: "AoE2 Ranged Combat — Patrol-Engine Accuracy",
      description: "A five-seed technical audit of the updated patrol engine against the current 70-run live capture matrix.",
      generatedAt,
      blocks: [
        {
          id: "title",
          type: "markdown",
          body: "# AoE2 Ranged Combat — Patrol-Engine Accuracy",
        },
        {
          id: "technical-summary",
          type: "markdown",
          sourceId: source.id,
          body: `## Technical summary\n\n**${passingRows.length} of 14 matchups meet the complete acceptance rule.** ${problemRows.length} remain wrong, materially off, or unresolved.\n\n- ${unresolvedText}\n- ${wrongWinnerText}\n- ${hpMisses.length} additional fully resolved matchup${hpMisses.length === 1 ? " misses" : "s miss"} the 20% winner-HP target despite stable winner direction.\n- ${largestMissText}\n- ${completedAttempts} of ${totalAttempts} simulation attempts completed; all ${stableLiveRows} live matchup rows have a stable winner across their five recordings.`,
        },
        {
          id: "problems-heading",
          type: "markdown",
          sourceId: source.id,
          body: `## ${problemRows.length} matchups still fail\n\nEvery failing row opens directly in the Tailnet engine viewer. Wrong-winner rows use an actual wrong-winner seed; survivor-HP rows use the completed seed closest to that matchup's simulation mean winner HP.\n\n${problemViewerLinks}\n\nRows are ordered by failure class: unresolved first, then wrong-winner seeds, then valid survivor-HP misses. HP error is deliberately marked invalid when a seed times out or picks the other unit type as winner.`,
        },
        { id: "problem-table-block", type: "table", tableId: "problem-table", layout: "full" },
        {
          id: "arb-hca-diagnosis",
          type: "markdown",
          sourceId: diagnosticSource.id,
          body: "## Why Arbalester vs Heavy Cavalry Archer flips\n\n**The evidence points to opening target acquisition and attack participation—not damage per hit.** The live game averages 26.4 of 27 Arbalesters on the busiest first target, while the simulator averages only 15.6 and fans the rest across additional cavalry archers. That dispersion lets 18.4 distinct simulated Arbalesters land an opening hit versus 6.2 live, producing 27.4 opening hits versus 14.4.\n\nThe visual observation that some simulated Arbalesters do not fire is real, but it is not the direction of this error: the simulator still activates roughly three times as many opening Arbalester shooters as live. Meanwhile, HCA damage begins **0.86 raw game seconds earlier** in simulation and each hit deals the correct 7 HP, so delayed HCA firing or incorrect damage cannot explain the loss. The HCA army instead reaches only 732.2 total damage in simulation versus the 1,080 required and observed live because the excessive parallel Arbalester opening starts a casualty cascade.\n\nConfidence is **high** that the first-target distribution and opening participation are wrong. Confidence is **medium** that this is the only missing mechanic; that requires implementing a shared acquisition/retarget rule and rerunning the same five seeds rather than fitting this matchup's outcome.",
        },
        { id: "arb-hca-table-block", type: "table", tableId: "arb-hca-table", layout: "full" },
        {
          id: "chart-heading",
          type: "markdown",
          sourceId: source.id,
          body: "## Valid winner-HP error by matchup\n\nThis ranking includes only matchups where all five simulation seeds finish and choose the stable live winner. The acceptance ceiling is 20%; larger bars remain materially inaccurate even when the winner is correct.",
        },
        { id: "hp-chart-block", type: "chart", chartId: "hp-error-chart", layout: "full" },
        {
          id: "scope-definitions",
          type: "markdown",
          body: "## What was measured\n\nThe scope is the current **14-matchup captured matrix**: 2 ranged-vs-ranged compositions and 12 ranged-vs-melee compositions, each with five saved live gRPC runs and five simulation opening seeds. Melee-vs-ranged mirror captures are not present in this 70-run matrix, so they are not claimed here.\n\n**Signed score** is surviving winner HP divided by that winning owner's starting test-army HP, multiplied by 100. Negative means Player 2 won; positive means Player 3 won. **Winner-HP error** compares raw mean surviving HP for the same winning unit type. Player 4's auxiliary army is part of the scenario and diplomacy gate, but its HP is not added to the P2/P3 winner denominator.",
        },
        {
          id: "all-heading",
          type: "markdown",
          sourceId: source.id,
          body: "## Complete 14-matchup results\n\nThe exact table exposes winner direction, signed score, live and simulated survivor HP, relative HP error, and all five seed outcomes. A clean row requires 5/5 completion, 0 wrong-winner seeds, and no more than 20% relative mean winner-HP error.",
        },
        { id: "all-table-block", type: "table", tableId: "all-table", layout: "full" },
        {
          id: "methodology",
          type: "markdown",
          sourceId: source.id,
          body: `## Engine and comparison method\n\nThe game was not launched. The updated shared engine reran simulation seeds 0–4 using literal first-N golden-scenario placements, scenario patrol destinations, Player 4's authored army and directional diplomacy, and the owner-defeat trigger that releases the melee side to attack the ranged side. The comparison then used the saved live winner and survivor HP from each of the five gRPC recordings.\n\nThe mean absolute signed-score error across fully resolved rows is **${meanAbsoluteScoreError.length ? mean(meanAbsoluteScoreError).toFixed(2) : "N/A"} points**. This is descriptive, not a fitted objective: no matchup-specific winner, HP, engagement-time, or output correction was introduced.`,
        },
        {
          id: "limits",
          type: "markdown",
          body: "## Limits and robustness\n\nFive live runs and five engine seeds are enough to expose large errors and seed instability, but they do not estimate a narrow confidence interval. Live runs and simulation seeds are independent samples rather than paired trials. The 20% threshold is an engineering acceptance rule, not a statistical significance test.\n\nA timeout or wrong-winner seed blocks survivor-HP acceptance because raw survivor HP would then mix incomplete fights or different winning unit types. This report therefore shows those rows as unresolved/wrong-winner first and does not use their nominal HP ratio as evidence of accuracy.",
        },
        {
          id: "next-steps",
          type: "markdown",
          body: "## Recommended next steps\n\n1. Fix unresolved seeds first by tracing post-acquisition pursuit, collision, and reachable attack-position behavior; do not add matchup timers or outcome overrides.\n2. For wrong-winner rows, compare the first two attack cycles, target retention, and retarget behavior against the recorded frames before changing damage mechanics.\n3. For stable-winner HP misses, inspect reusable projectile cadence, attack delay, collision/overlap, and target-distribution mechanics in descending error order.\n4. Rerun this exact 14 × 5 audit after each shared-mechanics change and keep the same acceptance rule.",
        },
        {
          id: "further-questions",
          type: "markdown",
          body: "## Further questions\n\n- Do melee-vs-ranged mirrored scenarios need a separate live capture matrix, or should they be added to this same benchmark?\n- Are the remaining deltas concentrated in unit-class mechanics (projectile/ranged cadence, cavalry collision) or in formation-scale target acquisition?\n- Does increasing the seed count change any row currently close to the 20% boundary?",
        },
      ],
      charts: [
        {
          id: "hp-error-chart",
          title: "Relative mean winner-HP error",
          subtitle: "Only 5/5 resolved, 5/5 correct-winner rows; 20% is the acceptance ceiling",
          showDescription: true,
          question: "Which valid matchup comparisons remain farthest from the live survivor HP?",
          rationale: "A ranked horizontal bar supports direct comparison across long matchup labels.",
          intent: "ranking",
          type: "horizontalBar",
          dataset: "resolved_rows",
          sourceId: source.id,
          encodings: {
            x: { field: "matchup", type: "nominal", label: "Matchup" },
            y: { field: "hp_delta_pct", type: "quantitative", format: "number", label: "Winner HP error", unit: "%" },
            tooltip: [
              { field: "verdict", type: "nominal", label: "Verdict" },
              { field: "live_winner_hp", type: "quantitative", format: "number", label: "Live winner HP" },
              { field: "sim_winner_hp", type: "quantitative", format: "number", label: "Simulation winner HP" },
              { field: "hp_delta", type: "quantitative", format: "number", label: "HP difference" },
            ],
          },
          valueFormat: "number",
          layout: "full",
          maxRows: 14,
          surface: { legend: "none", valueLabels: true },
        },
      ],
      tables: [
        {
          id: "arb-hca-table",
          title: "Chinese Arbalester vs Saracen Heavy Cavalry Archer — mechanics reconciliation",
          subtitle: "Five live repeats vs five current-engine seeds; opening window is two raw game seconds after first damage",
          showDescription: true,
          dataset: "arb_hca_diagnostic_rows",
          sourceId: diagnosticSource.id,
          defaultSort: { field: "metric", direction: "asc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "metric", label: "Metric", type: "text" },
            { field: "live", label: "Live", type: "text" },
            { field: "simulation", label: "Simulation", type: "text" },
            { field: "delta", label: "Delta", type: "text" },
            { field: "reading", label: "What it means", type: "text" },
          ],
        },
        {
          id: "problem-table",
          title: "Matchups that do not pass",
          subtitle: "Five live runs vs simulation seeds 0–4, ordered by failure class and severity",
          showDescription: true,
          dataset: "problem_rows",
          sourceId: source.id,
          defaultSort: { field: "priority", direction: "asc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "priority", label: "#", format: "number", role: "value" },
            { field: "verdict", label: "Current result", type: "text" },
            { field: "matchup", label: "Matchup", type: "text" },
            { field: "live_score", label: "Live score", format: "number", role: "value" },
            { field: "sim_score_display", label: "Simulation score", type: "text" },
            { field: "hp_delta_display", label: "Winner HP off by", type: "text" },
            { field: "wrong_winner_seeds", label: "Wrong seeds", format: "number", role: "value" },
            { field: "timeout_seeds", label: "Timeouts", format: "number", role: "value" },
          ],
        },
        {
          id: "all-table",
          title: "All current matchup results",
          subtitle: "Exact live/simulation survivor HP and all five seed outcomes",
          showDescription: true,
          dataset: "all_rows",
          sourceId: source.id,
          defaultSort: { field: "priority", direction: "asc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "priority", label: "#", format: "number", role: "value" },
            { field: "verdict", label: "Verdict", type: "text" },
            { field: "matchup", label: "Matchup", type: "text" },
            { field: "family", label: "Family", type: "text" },
            { field: "live_score", label: "Live score", format: "number", role: "value" },
            { field: "sim_score_display", label: "Simulation score", type: "text" },
            { field: "live_winner_hp", label: "Live winner HP", format: "number", role: "value" },
            { field: "sim_winner_hp_display", label: "Simulation winner HP", type: "text" },
            { field: "hp_delta_display", label: "Winner HP off by", type: "text" },
            { field: "seed_record", label: "Seed outcomes", type: "text" },
          ],
        },
      ],
      sources: [source, diagnosticSource, {
        id: "live-frames-source",
        label: "Live gRPC frame analysis with exact capture paths",
        path: LIVE_FRAMES_ANALYSIS,
      }],
    },
    snapshot: {
      version: 1,
      status: "ready",
      generatedAt,
      datasets: {
        problem_rows: problemDataset,
        resolved_rows: resolvedDataset,
        all_rows: allRows,
        arb_hca_diagnostic_rows: arbHcaDiagnosticRows,
      },
      sources: [],
    },
    sources: [],
  };
  await mkdir(dirname(output), { recursive: true });
  const viewerCatalogueOutput = resolve(dirname(output), "viewer_problem_catalogue.json");
  await Promise.all([
    writeFile(output, `${JSON.stringify(artifact, null, 2)}\n`, "utf8"),
    writeFile(viewerCatalogueOutput, `${JSON.stringify({
      schemaVersion: 2,
      generatedAt,
      repositoryBase: report.source?.repositoryBase ?? null,
      comparisonResults: COMPARISON_RESULTS,
      rows: viewerProblemRows,
    }, null, 2)}\n`, "utf8"),
  ]);
  return {
    output,
    viewerCatalogueOutput,
    matchups: classified.length,
    passing: passingRows.length,
    problem: problemRows.length,
    unresolved: unresolved.length,
    wrongWinners: wrongWinners.length,
    hpMisses: hpMisses.length,
    completedAttempts,
    totalAttempts,
  };
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname.slice(1))) {
  const inputArgument = process.argv.find((value) => value.startsWith("--input="));
  const outputArgument = process.argv.find((value) => value.startsWith("--output="));
  const result = await buildReport({
    input: inputArgument ? resolve(inputArgument.slice("--input=".length)) : DEFAULT_INPUT,
    output: outputArgument ? resolve(outputArgument.slice("--output=".length)) : DEFAULT_OUTPUT,
  });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}
