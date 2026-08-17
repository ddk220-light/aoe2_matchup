import { readFile, writeFile } from "node:fs/promises";


const generatedAt = new Date().toISOString();
const batchResults = JSON.parse(await readFile(
  new URL("../phase2_batch1_current_engine_2026-08-17/results.json", import.meta.url),
  "utf8",
));
const trace = JSON.parse(await readFile(
  new URL("war_wagon_paladin_analysis.json", import.meta.url),
  "utf8",
));
const warWagonRows = batchResults.rows
  .filter(({ subjectSlug }) => subjectSlug === "elite_war_wagon")
  .map(outcomeRow);


const tape = trace.tapeRuns;
const sim = trace.simulation;
const tapeMetrics = {
  wagonMoveSpeed: band(tape.map((run) => run.effectiveSpeedWhileMovingTilesPerSecond[2])),
  wagonAttackRate: band(tape.map((run) => run.attackStartsPer100AliveUnitSeconds[2])),
  paladinFirstDamage: band(tape.map((run) => run.firstDamageSecondsByOwner[3])),
  paladinMoveSpeed: band(tape.map((run) => run.effectiveSpeedWhileMovingTilesPerSecond[3])),
  paladinProgressSpeed: band(tape.map((run) => run.progressSpeedAcrossAliveTimeTilesPerSecond[3])),
  paladinStallShare: band(tape.map((run) => run.stalledShareOfPaladinChaseObservations)),
  paladinAttackRate: band(tape.map((run) => run.attackStartsPer100AliveUnitSeconds[3])),
  paladinHitRate: band(tape.map((run) => run.damageEventsPerAttackStartByOwner[3])),
  paladinDistinctTargets: band(tape.map((run) => run.paladinPursuitTargetConcentration.medianDistinctTargets)),
  paladinLargestTargetShare: band(tape.map((run) => run.paladinPursuitTargetConcentration.medianLargestTargetShare)),
  paladinP10Gap: band(tape.map((run) => run.paladinNearestWagonSurfaceGapTiles.p10)),
  paladinNearShare: band(tape.map((run) => run.paladinProximityShare.within0_25)),
  paladinsNearMax: band(tape.map((run) => run.maximumSimultaneousPaladinsNearWagon.within0_25)),
  paladinAttackersMax: band(tape.map((run) => run.maximumSimultaneousAttackers[3])),
  paladinDamage: band(tape.map((run) => run.damageDealtByOwner[3])),
};


const diagnosticMetrics = [
  metric("Paladin first damage", tapeMetrics.paladinFirstDamage, sim.firstDamageSecondsByOwner[3], "seconds", "Initial arrival is not late"),
  metric("Paladin effective speed while moving", tapeMetrics.paladinMoveSpeed, sim.effectiveSpeedWhileMovingTilesPerSecond[3], "tiles/s", "Collision and steering cut actual motion"),
  metric("Paladin progress across alive time", tapeMetrics.paladinProgressSpeed, sim.progressSpeedAcrossAliveTimeTilesPerSecond[3], "tiles/s", "Net chase progress is much lower"),
  metric("Paladin stalled chase share", percentBand(tapeMetrics.paladinStallShare), 100 * sim.stalledShareOfPaladinChaseObservations, "%", "Higher is worse"),
  metric("Median distinct Wagon targets", tapeMetrics.paladinDistinctTargets, sim.paladinPursuitTargetConcentration.medianDistinctTargets, "targets", "Simulation collapses the chase onto one target"),
  metric("Largest pursuit-target share", percentBand(tapeMetrics.paladinLargestTargetShare), 100 * sim.paladinPursuitTargetConcentration.medianLargestTargetShare, "%", "Simulation sends every Paladin to the same Wagon"),
  metric("P10 target surface gap", tapeMetrics.paladinP10Gap, sim.paladinNearestWagonSurfaceGapTiles.p10, "tiles", "Lower means sustained close contact"),
  metric("Paladin observations within 0.25 surface tiles", percentBand(tapeMetrics.paladinNearShare), 100 * sim.paladinProximityShare.within0_25, "%", "Close contact almost disappears in simulation"),
  metric("Maximum Paladins within 0.25 surface tiles", tapeMetrics.paladinsNearMax, sim.maximumSimultaneousPaladinsNearWagon.within0_25, "units", "Tape forms a surrounding contact front"),
  metric("Maximum simultaneous Paladin attackers", tapeMetrics.paladinAttackersMax, sim.maximumSimultaneousAttackers[3], "units", "Only two can attack together in simulation"),
  metric("Paladin attack starts per 100 alive-unit seconds", tapeMetrics.paladinAttackRate, sim.attackStartsPer100AliveUnitSeconds[3], "starts", "The engagement opportunity collapses"),
  metric("Paladin hit completion per attack start", percentBand(tapeMetrics.paladinHitRate), 100 * sim.damageEventsPerAttackStartByOwner[3], "%", "Once an attack starts, damage works"),
  metric("Paladin damage dealt", tapeMetrics.paladinDamage, sim.damageDealtByOwner[3], "HP", "Tape kills all Wagons; simulation kills one"),
  metric("War Wagon effective move speed", tapeMetrics.wagonMoveSpeed, sim.effectiveSpeedWhileMovingTilesPerSecond[2], "tiles/s", "Base Wagon speed is close"),
  metric("War Wagon attack starts per 100 alive-unit seconds", tapeMetrics.wagonAttackRate, sim.attackStartsPer100AliveUnitSeconds[2], "starts", "Normalized firing rate is only modestly high"),
];


const tapeMedian = (values) => median(values.filter(Number.isFinite));
const contactRatios = [
  ratioRow("Distinct pursuit targets", sim.paladinPursuitTargetConcentration.medianDistinctTargets, tapeMedian(tape.map((run) => run.paladinPursuitTargetConcentration.medianDistinctTargets)), false),
  ratioRow("Effective moving speed", sim.effectiveSpeedWhileMovingTilesPerSecond[3], tapeMedian(tape.map((run) => run.effectiveSpeedWhileMovingTilesPerSecond[3])), false),
  ratioRow("Net chase progress", sim.progressSpeedAcrossAliveTimeTilesPerSecond[3], tapeMedian(tape.map((run) => run.progressSpeedAcrossAliveTimeTilesPerSecond[3])), false),
  ratioRow("Attack-start rate", sim.attackStartsPer100AliveUnitSeconds[3], tapeMedian(tape.map((run) => run.attackStartsPer100AliveUnitSeconds[3])), false),
  ratioRow("Close-contact share", sim.paladinProximityShare.within0_25, tapeMedian(tape.map((run) => run.paladinProximityShare.within0_25)), false),
  ratioRow("Simultaneous attackers", sim.maximumSimultaneousAttackers[3], tapeMedian(tape.map((run) => run.maximumSimultaneousAttackers[3])), false),
  ratioRow("Stalled chase share", sim.stalledShareOfPaladinChaseObservations, tapeMedian(tape.map((run) => run.stalledShareOfPaladinChaseObservations)), true),
];


const sources = [
  {
    id: "war-wagon-results",
    label: "Completed Phase 2 Batch 1 current-engine results",
    path: "aoe2x/js_simulation/calibration/reports/phase2_batch1_current_engine_2026-08-17/results.json",
    query: {
      language: "sql",
      engine: "portable-snapshot",
      sql: "SELECT matchup, ratio, tapeOutcome, tapeMean, tapeRange, simulationOutcome, simulationMean, simulationRange, absoluteDelta, status FROM war_wagon_matchups ORDER BY absoluteDelta DESC;",
      description: "Selects all six exact golden Elite War Wagon rows from the completed recoverable benchmark.",
      tables_used: [
        "aoe2x/js_simulation/calibration/reports/phase2_batch1_current_engine_2026-08-17/results.json",
      ],
      filters: [
        "Phase-2 subject: Elite War Wagon",
        "Exact golden starting roster, ratios, and positions",
        "Five current-engine simulation attempts per stable row",
      ],
      metric_definitions: {
        signed_outcome_score: "Winner remaining HP divided by that winner's starting HP, multiplied by 100; positive means owner 3 and negative means owner 2.",
        absolute_delta: "Absolute difference between the simulation mean signed outcome and tape mean signed outcome.",
      },
    },
  },
  {
    id: "war-wagon-trace",
    label: "War Wagon versus Paladin tape and simulation trace analysis",
    path: "aoe2x/js_simulation/calibration/reports/phase2_war_wagon_diagnosis_2026-08-17/war_wagon_paladin_analysis.json",
    query: {
      language: "sql",
      engine: "portable-snapshot",
      sql: "SELECT metric, tapeBand, simulation, unit, interpretation FROM diagnostic_metrics; SELECT metric, percentOfTapeMedian, tapeMedian, simulation, direction FROM contact_ratios ORDER BY percentOfTapeMedian ASC;",
      description: "Compares four decoded full-rate frames.bin repeats with one exact-start current-engine trace; all five saved engine samples have the same final score.",
      tables_used: [
        "aoe2x/js_simulation/calibration/reports/phase2_war_wagon_diagnosis_2026-08-17/war_wagon_paladin_analysis.json",
      ],
      filters: [
        "15 Elite War Wagons versus 17 Paladins",
        "Four authorized tape repeats",
        "Simulation sample 0, seed 20260817",
        "Combat window from first active movement/targeting through final death",
      ],
      metric_definitions: {
        attack_start: "Tape: transition into decoded action_state 7. Simulation: transition into the attacking action.",
        effective_speed_while_moving: "Observed path length divided by seconds in which the unit position changed; this captures collision and steering effects rather than nominal stat speed.",
        surface_gap: "Center-to-center distance minus the War Wagon and Paladin collision radii (0.45 and 0.25 tiles).",
        stalled_chase_share: "Chase-state observations where the unit's position did not change, divided by all chase-state observations.",
        pursuit_target_concentration: "Live Paladins grouped by their current target; the largest group divided by Paladins holding a target.",
      },
    },
  },
  {
    id: "phase2-archive",
    label: "Authorized Phase 2 golden archive",
    path: "aoe2x/js_simulation/calibration/source/aoe2_golden_phase2_WITH_TAPES.zip",
    sha256: "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6",
  },
];


const artifact = {
  surface: "report",
  manifest: {
    version: 1,
    surface: "report",
    title: "Elite War Wagon: tape versus simulation diagnosis",
    description: "All six standard-unit outcomes and a full-rate diagnosis of the Paladin reversal.",
    generatedAt,
    blocks: [
      { id: "title", type: "markdown", layout: "full", body: "# Elite War Wagon: tape versus simulation diagnosis" },
      {
        id: "technical-summary",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-results",
        body: "## Paladin is a singular engagement failure, not a generally overpowered War Wagon\n\nFour of the six standard-unit rows are winner-correct with absolute deltas between **1.60 and 12.51 points**. The Battle Elephant row never terminates. Paladin is the sole resolved reversal: tape has Paladin winning all four repeats with **30.00–39.80%** remaining HP, while all five simulations give War Wagon the win with **83.33%** remaining HP. The **118.77-point delta** is caused primarily by Paladins converging on one target and losing movement under crowd pressure; War Wagon base speed, normalized firing rate, Paladin first-hit timing, and Paladin damage after attack start are close to tape.",
      },
      {
        id: "six-row-finding",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-results",
        body: "## Five resolved controls isolate Paladin as the outlier\n\nChampion is almost exact and falls inside the observed tape band. Arbalester, Heavy Cavalry Archer, and Heavy Scorpion retain the correct winner with single-digit to low-teens deltas. That pattern argues against changing War Wagon HP, raw damage, range, or general kiting policy before fixing the Paladin engagement bottleneck.",
      },
      { id: "six-row-chart", type: "chart", layout: "full", chartId: "war-wagon-delta-chart" },
      { id: "six-row-table", type: "table", layout: "full", tableId: "war-wagon-matchups-table" },
      {
        id: "paladin-outcome",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-trace",
        body: "## The fight begins correctly and then diverges at sustained contact\n\nPaladins land their first damage at **3.45s** in simulation versus **3.58–3.60s** on tape, so the opening attack-move and initial arrival are not late. After that, tape Paladins deal all **3,000 War Wagon HP**, while simulation Paladins deal only **500 HP** and kill one Wagon. Tape records **219–223 Paladin attack starts**; simulation records only **35**. Yet hit completion after an attack begins is **97.1%** in simulation versus **93.7–95.9%** on tape. Damage arithmetic is functioning—the Paladins are not being allowed to start enough attacks.",
      },
      {
        id: "contact-finding",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-trace",
        body: "## Target concentration creates the crowd jam\n\nTape Paladins pursue a median of **5–6 distinct War Wagons**, with the largest target group holding **38.5–45.5%** of current targets. Simulation collapses to **one distinct target and 100% concentration**. The direct paths therefore converge through the same allied cluster. Actual Paladin speed while position changes falls from **1.485 tiles/s** on tape to **0.955**, and stalled chase observations rise from **12.7–13.6%** to **34.9%**.",
      },
      { id: "contact-chart", type: "chart", layout: "full", chartId: "contact-ratio-chart" },
      { id: "diagnostic-table", type: "table", layout: "full", tableId: "diagnostic-table" },
      {
        id: "contact-envelope",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-trace",
        body: "## Tape forms a surrounding contact front; simulation forms a queue\n\nIn tape, **6–11 Paladins** can simultaneously sit within 0.25 surface tiles of a Wagon and **7–10** can attack at once. Simulation reaches only **one** Paladin in that close shell and at most **two** simultaneous attackers. The robust P10 surface gap is **0.10–0.15 tiles** on tape versus **0.57** in simulation. Rare tape frames go deeper, but matching the extreme overlap is unnecessary; the important target is sustained multi-unit access around several Wagons.",
      },
      {
        id: "war-wagon-controls",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-trace",
        body: "## War Wagon mechanics are not the primary lever\n\nObserved Wagon movement speed is **1.300–1.306 tiles/s** on tape and **1.320** in simulation. Normalized firing is **34.5–36.3 attack starts per 100 alive-Wagon seconds** on tape versus **37.2** in simulation—a modest overshoot, not enough to explain the winner reversal. Raw simulation attack totals are larger because almost every Wagon survives for the entire fight. The kiting clock should remain unchanged for the first experiment.",
      },
      {
        id: "diagnosis",
        type: "markdown",
        layout: "full",
        body: "## Recommended engine experiment: congestion-aware melee target assignment\n\nDo not add a War-Wagon-versus-Paladin exception and do not shrink either collision box. When several melee chasers select targets, add a general congestion cost based on allied pursuers already assigned to the target and occupied approach sectors around it. A chaser whose direct path crosses an already saturated allied group should select another reachable enemy or persist around the tangent to an unoccupied approach sector. Preserve the existing allied-overlap cap. This should spread the 17 Paladins across the available 15 Wagons, prevent the one-target queue, and allow the contact solver to capture attacks when a chaser enters a valid target-surface envelope.",
      },
      {
        id: "methods",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-trace",
        body: "## Method and definitions\n\nThe four authorized `frames.bin` members were decoded at full render cadence and filtered to masters 829 and 569. HP changes, action-state transitions, targets, paths, collision-surface gaps, and simultaneous contact counts were measured from first active movement/targeting through the final death. The simulation used the exact canonical 15v17 starting roster, coordinates, golden map, sample 0, and seed 20260817. All five saved simulation samples have the same final score. Surface gap subtracts the fixture collision radii—0.45 tiles for Elite War Wagon and 0.25 for Paladin—from center distance.",
      },
      {
        id: "limitations",
        type: "markdown",
        layout: "full",
        sourceId: "war-wagon-trace",
        body: "## Limitations and robustness\n\nTape action-state 7 is a proxy for attack starts rather than a byte-identical engine event. HP drops can aggregate simultaneous projectile hits in one rendered frame, so ranged hit-event counts are less directly comparable than melee attack-start and damage-completion rates. The causal diagnosis is strongly supported by four consistent tape repeats and one deterministic trace whose final result matches all five saved samples, but the proposed target-assignment mechanism still requires a controlled engine experiment and regression checks.",
      },
      {
        id: "next-step",
        type: "markdown",
        layout: "full",
        body: "## Next step and decision gate\n\nImplement the congestion-aware target-selection experiment behind a general engine option, run only the 15v17 War Wagon–Paladin row first, and compare five samples with these trace targets: **5–6 distinct Paladin targets, 6–11 close-contact Paladins, 7–10 simultaneous attackers, 12.7–13.6% stalled chase, and 219–223 attack starts**. If those mechanics move toward tape and Paladin becomes the winner, then run the other five War Wagon controls to ensure Champion, Arbalester, HCA, and Scorpion do not regress and the Elephant timeout does not worsen.",
      },
      {
        id: "further-question",
        type: "markdown",
        layout: "full",
        body: "## What would falsify this diagnosis?\n\nIf spreading Paladin targets and preserving tangent detours restores contact metrics but Paladin damage remains near 500 HP, the next suspect would be the melee engagement envelope around a large moving target. If contact and attack-start counts reach tape while the result still favors War Wagon, only then should War Wagon projectile resolution or recovery timing be investigated.",
      },
    ],
    charts: [
      {
        id: "war-wagon-delta-chart",
        title: "Absolute outcome delta across resolved War Wagon rows",
        description: "Five simulation samples per exact golden row; Battle Elephant is excluded because all attempts time out.",
        type: "bar",
        intent: "comparison",
        question: "Is the War Wagon error general or opponent-specific?",
        rationale: "Five categorical bars make the Paladin outlier visible without obscuring exact values.",
        dataset: "resolved_matchup_deltas",
        encodings: { x: { field: "opponent" }, y: { field: "absoluteDelta" } },
        labels: { values: "all" },
        sourceId: "war-wagon-results",
      },
      {
        id: "contact-ratio-chart",
        title: "Simulation Paladin engagement metrics relative to tape",
        description: "Tape median is 100%; stalled chase is higher-is-worse, while all other metrics are higher-is-better.",
        type: "bar",
        intent: "comparison",
        question: "Where does Paladin engagement fall away relative to tape?",
        rationale: "A normalized metric comparison separates target access, movement, attack opportunity, and stalling on one scale.",
        dataset: "contact_ratios",
        encodings: { x: { field: "metric" }, y: { field: "percentOfTapeMedian" } },
        labels: { values: "all" },
        sourceId: "war-wagon-trace",
      },
    ],
    tables: [
      {
        id: "war-wagon-matchups-table",
        title: "All six Elite War Wagon golden comparisons",
        description: "Exact tape ratios and the completed current-engine results.",
        dataset: "war_wagon_matchups",
        columns: [
          column("matchup", "Matchup"), column("ratio", "Ratio"),
          column("tapeOutcome", "Tape outcome"), column("tapeMean", "Tape mean", "number"),
          column("tapeRange", "Tape range"), column("simulationOutcome", "Simulation outcome"),
          column("simulationMean", "Simulation mean", "number"), column("simulationRange", "Simulation range"),
          column("absoluteDelta", "Abs. delta", "number"), column("status", "Status"),
        ],
        defaultSort: { field: "absoluteDelta", direction: "desc" },
        sourceId: "war-wagon-results",
      },
      {
        id: "diagnostic-table",
        title: "War Wagon–Paladin trace metrics",
        description: "Tape min–max across four repeats compared with the exact-start simulation trace.",
        dataset: "diagnostic_metrics",
        density: "dense",
        columns: [
          column("metric", "Metric"), column("tapeBand", "Tape range"),
          column("simulation", "Simulation", "number"), column("unit", "Unit"),
          column("interpretation", "Interpretation"),
        ],
        defaultSort: { field: "metric", direction: "asc" },
        sourceId: "war-wagon-trace",
      },
    ],
    sources,
  },
  snapshot: {
    version: 1,
    status: "ready",
    generatedAt,
    datasets: {
      war_wagon_matchups: warWagonRows,
      resolved_matchup_deltas: warWagonRows
        .filter(({ absoluteDelta }) => Number.isFinite(absoluteDelta))
        .map(({ opponent, absoluteDelta, status }) => ({ opponent, absoluteDelta, status })),
      diagnostic_metrics: diagnosticMetrics,
      contact_ratios: contactRatios,
    },
    accessIssues: [],
  },
  sources,
};


await writeFile(new URL("artifact.json", import.meta.url), `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({
  artifact: new URL("artifact.json", import.meta.url).pathname,
  warWagonRows,
  contactRatios,
})}\n`);


function outcomeRow(row) {
  const tapeOutcome = winner(row, row.tape.mean);
  const simulationOutcome = winner(row, row.comparison.mean);
  const absoluteDelta = Number.isFinite(row.comparison.mean)
    ? Math.abs(row.comparison.mean - row.tape.mean)
    : null;
  return {
    opponent: humanize(row.opponentSlug),
    matchup: row.matchup,
    ratio: `${row.side2.count}v${row.side3.count}`,
    tapeOutcome,
    tapeMean: round(row.tape.mean),
    tapeRange: `${round(row.tape.min)} to ${round(row.tape.max)}`,
    simulationOutcome,
    simulationMean: round(row.comparison.mean),
    simulationRange: Number.isFinite(row.comparison.mean)
      ? `${round(row.comparison.min)} to ${round(row.comparison.max)}`
      : "Unresolved",
    absoluteDelta: round(absoluteDelta),
    status: row.comparison.simulationRuns === 0
      ? "Unresolved"
      : row.comparison.wrongStableWinner
        ? "Wrong winner"
        : "Winner matched",
  };
}


function winner(row, score) {
  if (!Number.isFinite(score)) return "Unresolved";
  return score > 0 ? row.side3.unit : row.side2.unit;
}


function humanize(slug) {
  return slug.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
}


function band(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  return { min: sorted[0], median: median(sorted), max: sorted.at(-1) };
}


function percentBand(value) {
  return { min: 100 * value.min, median: 100 * value.median, max: 100 * value.max };
}


function metric(name, tapeBand, simulation, unit, interpretation) {
  return {
    metric: name,
    tapeBand: `${round(tapeBand.min)}–${round(tapeBand.max)}`,
    tapeMedian: round(tapeBand.median),
    simulation: round(simulation),
    unit,
    interpretation,
  };
}


function ratioRow(metricName, simulation, medianTape, higherIsWorse) {
  return {
    metric: metricName,
    percentOfTapeMedian: round(100 * simulation / medianTape, 1),
    tapeMedian: round(medianTape, 4),
    simulation: round(simulation, 4),
    direction: higherIsWorse ? "Higher is worse" : "Higher is better",
  };
}


function column(field, label, format = undefined) {
  return { field, label, ...(format ? { format } : {}) };
}


function median(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


function round(value, digits = 2) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
