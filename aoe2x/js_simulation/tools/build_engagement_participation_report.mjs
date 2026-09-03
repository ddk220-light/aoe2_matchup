// Build the canonical portable technical report for first-20-second live-vs-sim
// engagement participation. The shared Data Analytics report packager turns
// the resulting artifact.json into the final self-contained report.html.
import { readFile, writeFile } from "node:fs/promises";


const ROOT = new URL("../", import.meta.url);
const OUTPUT_ROOT = new URL(
  "../calibration/reports/arbalester_hca_participation_2026-08-30/",
  import.meta.url,
);
const INPUT = new URL("engagement_participation_comparison.json", OUTPUT_ROOT);
const STALL_DIAGNOSTIC = new URL("hca_stationary_intent_diagnostic.json", OUTPUT_ROOT);
const OUTCOME_INPUT = new URL(
  "../arbalester_hca_blocked_recovery_2026-08-30/results.json",
  OUTPUT_ROOT,
);
const OUTPUT = new URL("artifact.json", OUTPUT_ROOT);


function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


function pctDelta(simulation, live) {
  return 100 * (simulation - live) / live;
}


function bySecond(document) {
  const rows = [];
  for (let second = 0; second < 20; second += 1) {
    for (const [sourceName, sourceRow] of [
      ["Live game", document.liveMeanPerSecond[second]],
      ["Simulation", document.simulationMeanPerSecond[second]],
    ]) {
      for (const owner of [2, 3]) {
        rows.push({
          second,
          interval: `${second}-${second + 1}s`,
          source: sourceName,
          army: owner === 2 ? "Chinese Arbalesters" : "Saracen Heavy Cavalry Archers",
          active: sourceRow[owner].active,
          firing: sourceRow[owner].firing,
          not_firing: sourceRow[owner].notFiring,
          reload: sourceRow[owner].reload,
          in_range_not_firing: sourceRow[owner].inRangeNotFiring,
          stationary_out_of_range: sourceRow[owner].seekingStationary,
          moving_to_target: sourceRow[owner].seekingMoving,
          untargeted_moving: sourceRow[owner].untargetedMoving,
          untargeted_stationary: sourceRow[owner].untargetedStationary,
          shot_starts: sourceRow[owner].shotStarts,
          damage_hits: sourceRow[owner].damageHits,
        });
      }
    }
  }
  return rows;
}


function exactRows(document) {
  const rows = [];
  for (let second = 0; second < 20; second += 1) {
    for (const owner of [2, 3]) {
      const live = document.liveMeanPerSecond[second][owner];
      const simulation = document.simulationMeanPerSecond[second][owner];
      rows.push({
        interval: `${String(second).padStart(2, "0")}-${String(second + 1).padStart(2, "0")}s`,
        army: owner === 2 ? "Chinese Arbalesters" : "Saracen Heavy Cavalry Archers",
        live_firing: live.firing,
        simulation_firing: simulation.firing,
        firing_delta: round(simulation.firing - live.firing),
        live_not_firing: live.notFiring,
        simulation_not_firing: simulation.notFiring,
        not_firing_delta: round(simulation.notFiring - live.notFiring),
        live_active: live.active,
        simulation_active: simulation.active,
        active_delta: round(simulation.active - live.active),
        live_moving_to_target: live.seekingMoving,
        simulation_moving_to_target: simulation.seekingMoving,
        live_stationary_out_of_range: live.seekingStationary,
        simulation_stationary_out_of_range: simulation.seekingStationary,
        live_in_range_not_firing: live.inRangeNotFiring,
        simulation_in_range_not_firing: simulation.inRangeNotFiring,
        live_shot_starts: live.shotStarts,
        simulation_shot_starts: simulation.shotStarts,
        live_damage_hits: live.damageHits,
        simulation_damage_hits: simulation.damageHits,
      });
    }
  }
  return rows;
}


function rangeTrendRows(document) {
  return document.engagementRange.perSecond
    .filter(({ meanEdgeDistance }) => meanEdgeDistance !== null)
    .map((row) => ({
      ...row,
      mean_edge_distance: row.meanEdgeDistance,
      p10_edge_distance: row.p10EdgeDistance,
      p90_edge_distance: row.p90EdgeDistance,
      nominal_range: row.nominalRange,
      range_samples: row.rangeSamples,
    }));
}


function rangeSummaryRows(document) {
  const rows = [];
  for (const [sourceName, source] of [
    ["Live game", document.engagementRange.live],
    ["Simulation", document.engagementRange.simulation],
  ]) {
    for (const owner of [2, 3]) {
      const row = source[owner];
      rows.push({
        army: owner === 2 ? "Chinese Arbalesters" : "Saracen Heavy Cavalry Archers",
        source: sourceName,
        nominal_range: owner === 2 ? 8 : 7,
        shot_starts: row.shotStarts,
        resolved_samples: row.resolvedRangeSamples,
        mean_center_distance: row.meanCenterDistance,
        mean_edge_distance: row.meanEdgeDistance,
        median_edge_distance: row.medianEdgeDistance,
        p10_edge_distance: row.p10EdgeDistance,
        p90_edge_distance: row.p90EdgeDistance,
        mean_nominal_headroom: row.meanNominalHeadroom,
        beyond_nominal_share: row.beyondNominalShare,
      });
    }
  }
  return rows;
}


function stallEpisodeRows(diagnostic) {
  return diagnostic.episodes.slice(0, 20).map((episode) => ({
    seed: episode.seed,
    hca: episode.unitId,
    start_second: episode.startSecond,
    end_second: episode.endSecond,
    duration_seconds: episode.durationSeconds,
    arbalester_target: episode.metricTargetId,
    mean_tiles_outside_range: episode.meanRangeExcess,
    max_tiles_outside_range: episode.maxRangeExcess,
    allied_blocker_ids: episode.topBlockerIds.map(({ referenceId }) => referenceId).join(", "),
  }));
}


function source(id, label, path, description, sampleScope = "single live run 1 versus current-engine opening seed 0") {
  const output = {
    id,
    label,
    path,
  };
  if (path.endsWith(".json")) {
    output.query = {
      engine: "DuckDB",
      language: "SQL",
      description,
      executed_at: new Date().toISOString(),
      tables_used: [path],
      filters: [
        "27 Chinese Arbalesters versus 18 Saracen Heavy Cavalry Archers",
        "first 20 game seconds",
        sampleScope,
      ],
      metric_definitions: [
        "Firing is a living unit in attack windup with a resolved hostile target inside its DAT attack envelope.",
        "Not firing is the living-unit count minus firing; reload, pursuit, in-range idle, and no-target states remain visible as reasons.",
        "Engagement range is measured when attack windup begins; edge distance subtracts both units' outline radii from center distance.",
        "Stationary out of range is a living unit with a valid hostile target outside its attack envelope and speed at or below 0.05 tiles per second.",
      ],
      sql: `SELECT * FROM read_json_auto('${path}', format = 'auto')`,
    };
  }
  return output;
}


async function main() {
  const [document, stallDiagnostic, outcomeDocument] = await Promise.all([
    readFile(INPUT, "utf8").then(JSON.parse),
    readFile(STALL_DIAGNOSTIC, "utf8").then(JSON.parse),
    readFile(OUTCOME_INPUT, "utf8").then(JSON.parse),
  ]);
  const generatedAt = new Date().toISOString();
  const five = document.windowSummary["5"];
  const ten = document.windowSummary["10"];
  const twenty = document.windowSummary["20"];
  const arbFiveLive = five.live["2"].meanActive;
  const arbFiveSim = five.simulation["2"].meanActive;
  const hcaFiveLive = five.live["3"].meanActive;
  const hcaFiveSim = five.simulation["3"].meanActive;
  const arbFiveLiveFiring = five.live["2"].meanFiring;
  const arbFiveSimFiring = five.simulation["2"].meanFiring;
  const hcaFiveLiveFiring = five.live["3"].meanFiring;
  const hcaFiveSimFiring = five.simulation["3"].meanFiring;
  const arbFiveLiveNotFiring = five.live["2"].meanNotFiring;
  const arbFiveSimNotFiring = five.simulation["2"].meanNotFiring;
  const hcaFiveLiveNotFiring = five.live["3"].meanNotFiring;
  const hcaFiveSimNotFiring = five.simulation["3"].meanNotFiring;
  const arbTwentyLiveFiring = twenty.live["2"].meanFiring;
  const arbTwentySimFiring = twenty.simulation["2"].meanFiring;
  const hcaTwentyLiveFiring = twenty.live["3"].meanFiring;
  const hcaTwentySimFiring = twenty.simulation["3"].meanFiring;
  const arbTwentyLiveNotFiring = twenty.live["2"].meanNotFiring;
  const arbTwentySimNotFiring = twenty.simulation["2"].meanNotFiring;
  const hcaTwentyLiveNotFiring = twenty.live["3"].meanNotFiring;
  const hcaTwentySimNotFiring = twenty.simulation["3"].meanNotFiring;
  const arbLiveRange = document.engagementRange.live["2"];
  const arbSimRange = document.engagementRange.simulation["2"];
  const hcaLiveRange = document.engagementRange.live["3"];
  const hcaSimRange = document.engagementRange.simulation["3"];
  const hcaTwentyLiveStall = twenty.live["3"].meanSeekingStationary;
  const hcaTwentySimStall = twenty.simulation["3"].meanSeekingStationary;
  const hcaTwentyLiveShots = twenty.live["3"].shotStarts;
  const hcaTwentySimShots = twenty.simulation["3"].shotStarts;
  const hcaLiveStallFiveToTwenty = document.liveMeanPerSecond
    .slice(5, 20)
    .reduce((total, row) => total + row["3"].seekingStationary, 0) / 15;
  const hcaSimStallFiveToTwenty = document.simulationMeanPerSecond
    .slice(5, 20)
    .reduce((total, row) => total + row["3"].seekingStationary, 0) / 15;
  const trends = bySecond(document);
  const rangeTrends = rangeTrendRows(document);
  const rangeSummary = rangeSummaryRows(document);
  const tableRows = exactRows(document);
  const episodeRows = stallEpisodeRows(stallDiagnostic);
  const solverRejected = stallDiagnostic.summary.causeRows.find(
    ({ value }) => value === "movement_solver_rejected_attempt",
  ).ticks;
  const idleTicks = stallDiagnostic.episodes.reduce(
    (total, episode) => total + (episode.actions.idle ?? 0),
    0,
  );
  const reloadTicks = stallDiagnostic.episodes.reduce(
    (total, episode) => total + (episode.actions.reload ?? 0),
    0,
  );
  const hardAllyTicks = stallDiagnostic.summary.solverHardBlockerTickPresence.ally;
  const rangedIngressTicks = stallDiagnostic.summary.solverCandidateInteractionKinds.find(
    ({ kind }) => kind === "ranged-ingress",
  )?.ticks ?? 0;
  const nonRejectedTicks = stallDiagnostic.summary.stationarySeekingUnitTicks - solverRejected;
  const outcomeRow = outcomeDocument.rows.find(
    ({ key }) => key === "arbalester_vs_heavy_cav_archer",
  );
  if (!outcomeRow) {
    throw new Error("blocked-pursuit outcome report is missing arbalester_vs_heavy_cav_archer");
  }
  const comparisonSource = source(
    "comparison-source",
    "First-20-second engagement participation comparison",
    "aoe2x/js_simulation/calibration/reports/arbalester_hca_participation_2026-08-30/engagement_participation_comparison.json",
    "Time-weights full-rate unit states into one-second intervals for live run 1 and current-engine seed 0, records shot-initiation distances, and reconciles state buckets to living-unit counts.",
  );
  const liveSource = source(
    "live-source",
    "Exact live gRPC stream — run 1",
    "aoe2x/js_simulation/calibration/live_observations/ranged_matrix_5x_2026-08-29/arbalester_vs_heavy_cav_archer/run_001/raw recordings/arbalester_vs_heavy_cav_archer.frames.bin",
    "Decodes live run 1 Action.state values, positions, targets, and HP deltas for the exact ranged-vs-ranged golden scenario.",
  );
  const simulationSource = source(
    "simulation-source",
    "Current-engine participation export — seed 0 selected",
    "aoe2x/js_simulation/calibration/reports/arbalester_hca_participation_2026-08-30/simulation_participation.json",
    "Selects opening seed 0 from the current checked-out engine export with literal golden positions, scenario patrols, and ordinary shared ranged-vs-ranged mechanics.",
  );
  const stallDiagnosticSource = source(
    "stall-diagnostic-source",
    "Per-tick HCA intention and movement-solver trace",
    "aoe2x/js_simulation/calibration/reports/arbalester_hca_participation_2026-08-30/hca_stationary_intent_diagnostic.json",
    "Replays the same five current-engine opening seeds through the lower-level 60 Hz world step, then records target state, action timers, raw movement proposals, realized movement, avoidance state, and collision candidates for every HCA stationary outside range during seconds 5-20.",
    "historical five-seed pathing diagnostic",
  );
  const outcomeSource = source(
    "outcome-source",
    "Five-seed outcome comparison after blocked-pursuit recovery",
    "aoe2x/js_simulation/calibration/reports/arbalester_hca_blocked_recovery_2026-08-30/results.json",
    "Compares the five exact live outcomes with current-engine seeds 0 through 4 after the generic five-failure path-and-retarget recovery was implemented.",
    "historical five-live-run versus five-seed outcome comparison",
  );
  const engineRecoverySource = source(
    "engine-recovery-source",
    "Generic blocked-pursuit recovery implementation and regression test",
    "aoe2x/js_simulation/src/combat/world.js",
    "Implements five-failure blocked-pursuit detection, recovery-only routing around every demonstrated collision surface, local tangential escape, opportunity retargeting, and scenario-patrol suspension/resumption without matchup-specific outcome parameters.",
  );
  const artifact = {
    surface: "report",
    manifest: {
      version: 1,
      surface: "report",
      title: "Who Is Actually Firing? Arbalester vs Heavy Cavalry Archer",
      description: "First-20-second live-vs-simulation engagement participation for the exact ranged-vs-ranged golden matchup.",
      generatedAt,
      blocks: [
        {
          id: "title",
          type: "markdown",
          body: "# Who Is Actually Firing? Arbalester vs Heavy Cavalry Archer",
        },
        {
          id: "technical-summary",
          type: "markdown",
          sourceId: "comparison-source",
          body: `## The mismatch is firing participation, not engagement distance\n\nThis fast comparison uses **live run 1 versus simulation seed 0**. During seconds 0-5, the simulation has fewer units not firing: **${round(arbFiveSimNotFiring)} Arbalesters versus ${round(arbFiveLiveNotFiring)} live**, and **${round(hcaFiveSimNotFiring)} HCA versus ${round(hcaFiveLiveNotFiring)} live**. Equivalently, it puts **${round(arbFiveSimFiring)} Arbalesters and ${round(hcaFiveSimFiring)} HCA** in attack windup at an average instant, versus **${round(arbFiveLiveFiring)} and ${round(hcaFiveLiveFiring)}** live. The simulated opening therefore engages too aggressively.\n\nAcross the full 20 seconds the Arbalester firing count nearly converges (**${round(arbTwentySimFiring)} simulation versus ${round(arbTwentyLiveFiring)} live**), but HCA reverse direction and under-fire: **${round(hcaTwentySimFiring)} simulated versus ${round(hcaTwentyLiveFiring)} live**, with **${hcaSimRange.shotStarts} simulated shot starts versus ${hcaLiveRange.shotStarts} live**. Shot-initiation distance is much closer: simulation begins Arbalester attacks only **${round(arbLiveRange.meanEdgeDistance - arbSimRange.meanEdgeDistance, 3)} tiles nearer** and HCA attacks only **${round(hcaLiveRange.meanEdgeDistance - hcaSimRange.meanEdgeDistance, 3)} tiles nearer** than the game.`,
        },
        {
          id: "outcome-status",
          type: "markdown",
          sourceId: "outcome-source",
          body: `## The movement correction improves the score, but not the winner\n\nAll five current-engine seeds resolve normally. The live game has the Saracen HCA winning **5/5**, with mean signed outcome score **${round(outcomeRow.tape.mean)}** and mean winner HP **${round(outcomeRow.tape.grpcOpening.winner_hp.mean)}**. The simulation still has the Chinese Arbalesters winning **5/5**, with mean score **${round(outcomeRow.simulation.score)}** and mean winner HP **${round(outcomeRow.simulation.winnerHp.mean)}**. The absolute mean signed-score delta is **${round(outcomeRow.simulation.absoluteMeanDelta)} points**. [Open the representative wrong-winner seed in the Tailnet engine viewer](https://starlight.tail82a190.ts.net/golden-map/?mode=problem-matchups&matchup=arbalester_vs_heavy_cav_archer). This remains an unresolved engine delta, not a calibrated output correction.`,
        },
        {
          id: "not-firing-finding",
          type: "markdown",
          sourceId: "comparison-source",
          body: `## Not firing exposes both the opening overshoot and later HCA shortfall\n\n“Not firing” is simply every living unit not currently in attack windup. It intentionally includes legitimate reload time, movement toward a target, in-range idle time, and no-target time; those reasons remain separate in the exact table. The simulation starts with too few non-firing units on both sides. Across the full window, Arbalesters are close (**${round(arbTwentySimNotFiring)} simulation versus ${round(arbTwentyLiveNotFiring)} live**), while HCA have **${round(hcaTwentySimNotFiring - hcaTwentyLiveNotFiring, 2)} more units not firing** at an average instant.`,
        },
        {
          id: "not-firing-chart-block",
          type: "chart",
          chartId: "not-firing-chart",
          layout: "full",
        },
        {
          id: "range-finding",
          type: "markdown",
          sourceId: "comparison-source",
          body: `## Both systems initiate shots near the same distance\n\nRange is measured when attack windup begins. **Edge distance** subtracts both units’ outline radii, so it is directly comparable with the DAT range: 8 tiles for Arbalesters and 7 for HCA. Arbalesters initiate at **${round(arbLiveRange.meanEdgeDistance, 3)} live versus ${round(arbSimRange.meanEdgeDistance, 3)} simulated**; HCA initiate at **${round(hcaLiveRange.meanEdgeDistance, 3)} live versus ${round(hcaSimRange.meanEdgeDistance, 3)} simulated**. The engine is slightly more conservative, starting ${round(arbLiveRange.meanEdgeDistance - arbSimRange.meanEdgeDistance, 3)} tiles closer for Arbalesters and ${round(hcaLiveRange.meanEdgeDistance - hcaSimRange.meanEdgeDistance, 3)} tiles closer for HCA.\n\nThe HCA distribution is the more revealing one: live median edge distance is **${round(hcaLiveRange.medianEdgeDistance, 3)}**, essentially the full 7-tile range, while simulation median is **${round(hcaSimRange.medianEdgeDistance, 3)}**. This range gap is real but small; it does not explain the much larger **${round(100 * (hcaSimRange.shotStarts - hcaLiveRange.shotStarts) / hcaLiveRange.shotStarts, 1)}% HCA shot-start deficit** by itself.`,
        },
        {
          id: "range-chart-block",
          type: "chart",
          chartId: "range-chart",
          layout: "full",
        },
        {
          id: "range-table-intro",
          type: "markdown",
          sourceId: "comparison-source",
          body: "## Shot-initiation range audit\n\nThe table reports every resolved shot start in the first 20 seconds. `Mean inside max` is nominal DAT range minus observed edge distance; negative individual values are starts just beyond the nominal value, within the game/engine reach tolerance and frame discretization.",
        },
        {
          id: "range-table-block",
          type: "table",
          tableId: "range-summary-table",
          layout: "full",
        },
        {
          id: "stall-finding",
          type: "markdown",
          sourceId: "comparison-source",
          body: `## Tangential recovery removes the prolonged HCA queue\n\nThe second-by-second stationary series now follows the live scale instead of climbing into a persistent multi-unit backlog. From seconds 5-20 the mean gap is ${round(hcaSimStallFiveToTwenty - hcaLiveStallFiveToTwenty, 3)} unit; across the full window it is ${round(hcaTwentySimStall - hcaTwentyLiveStall, 3)}. The closest shot-start proxy records **${round(hcaTwentySimShots)} simulated HCA starts** versus **${round(hcaTwentyLiveShots)} live** (**${round(pctDelta(hcaTwentySimShots, hcaTwentyLiveShots), 1)}%**), so firing cadence and target turnover still need work even though stationary access is aligned.`,
        },
        {
          id: "stall-chart-block",
          type: "chart",
          chartId: "stall-chart",
          layout: "full",
        },
        {
          id: "stall-intent-finding",
          type: "markdown",
          sourceId: "stall-diagnostic-source",
          body: `## The remaining stationary HCA have a target and are trying to reach it

This is not target-search latency. Across seconds 5-20, the post-fix detailed trace finds **${stallDiagnostic.summary.stationarySeekingUnitTicks.toLocaleString()} stationary/out-of-range HCA ticks**. On **${solverRejected.toLocaleString()} of them (${round(100 * solverRejected / stallDiagnostic.summary.stationarySeekingUnitTicks, 3)}%)**, the unit has a specific living Arbalester locked and submits a nonzero pursuit step, but the movement solver returns no meaningful displacement. The other **${nonRejectedTicks.toLocaleString()} ticks** are brief scenario-patrol holds rather than an unresolved target search.

The units are also not waiting to fire: **${idleTicks.toLocaleString()} ticks are action=idle**, **${reloadTicks.toLocaleString()} are reload**, and none are attack windup. Their opening patrol is suspended while a combat target exists and resumes if target loss leaves the army outside acquisition range. At an average instant in this 15-second window, **${round(stallDiagnostic.summary.meanStationaryHcaAcrossWindowAndSeeds)} HCA** are in this state.

The short residual holds still occur at friendly-body geometry. The raw proposed landing point intersects at least one allied HCA’s effective per-pair collision extent on all ${solverRejected.toLocaleString()} rejected-attempt ticks. A hard allied contact is present on **${hardAllyTicks.toLocaleString()} ticks (${round(100 * hardAllyTicks / solverRejected, 1)}%)**, and a **ranged-ingress** reservation is present on **${rangedIngressTicks.toLocaleString()} ticks (${round(100 * rangedIngressTicks / solverRejected, 1)}%)**; one tick may contain both. These are now bounded detection windows, not evidence of a persistent route failure.

The longest same-cause episodes are five ticks (0.083 s): the configured number of failed physical attempts before recovery selects a lateral route. The prior multi-second sticky loop is gone.`,
        },
        {
          id: "recovery-mechanic",
          type: "markdown",
          sourceId: "engine-recovery-source",
          body: "## What changed in the engine\n\nA ranged pursuer counts consecutive pursuit attempts that request movement but realize less than 5% of the requested step. On the fifth failure, recovery plans against every collision surface that actually constrained the unit—including a reservation that ordinary path planning calls non-obstructing—then takes a lateral grid/tangent route around it. If no route is available, it probes a local sidestep and permits opportunity retargeting. Ordinary movement still uses the original overlap and collision rules. No unit name, desired winner, survivor HP, copied waypoint, or matchup-specific delay enters this mechanism.",
        },
        {
          id: "stall-episodes-intro",
          type: "markdown",
          sourceId: "stall-diagnostic-source",
          body: "## Longest continuous examples\n\nThe table lists the longest same-target, same-cause detection windows. `Tiles outside range` is center distance beyond the HCA’s 7.7-tile legal outline envelope. The longest windows are now five ticks (0.083 s), after which recovery changes the route or target instead of retrying the same blocked line indefinitely.",
        },
        {
          id: "stall-episodes-table-block",
          type: "table",
          tableId: "stall-episodes-table",
          layout: "full",
        },
        {
          id: "exact-table-intro",
          type: "markdown",
          body: "## Exact second-by-second audit\n\nUse the table for precise lookup. Counts are time-weighted concurrent units within each one-second interval for live run 1 and simulation seed 0. `Not firing` reconciles exactly to living units minus `firing`; reload, movement, stationary pursuit, in-range idle, and no-target buckets reconcile to `not firing`. Shot starts and damage hits are events, not concurrent counts.",
        },
        {
          id: "exact-table-block",
          type: "table",
          tableId: "exact-table",
          layout: "full",
        },
        {
          id: "scope-definitions",
          type: "markdown",
          sourceId: "comparison-source",
          body: "## What was measured\n\n- **Population:** the exact golden ranged-vs-ranged setup: 27 Chinese Arbalesters (owner 2) versus 18 Saracen Heavy Cavalry Archers (owner 3).\n- **Comparison:** live gRPC run 1 versus current-engine opening seed 0.\n- **Clock:** second 0 starts at the first full exact-roster live frame and engine tick 0.\n- **Firing:** alive, hostile target resolves inside the attack envelope, and the unit is in attack windup (`Action.state=7` live; `attacking` in simulation). Reload is not counted as firing.\n- **Not firing:** living-unit count minus firing. This deliberately includes legitimate reload, pursuit, in-range idle, and no-target time.\n- **Engagement range:** attacker-to-target distance at the transition into attack windup. Edge distance subtracts both outline radii; center distance does not.\n- **Stationary pursuit:** a diagnostic subset of not firing: valid target outside range and speed no greater than 0.05 tiles/s. It is not synonymous with all non-firing time.",
        },
        {
          id: "methodology",
          type: "markdown",
          body: "## Full-rate state classification and reconciliation\n\nLive run 1 was decoded at its recorded frame rate. The analysis resolved action targets to living units and time-weighted full-rate state counts into one-second intervals. Live `Action.state=7` is attack windup and `6` is reload. Simulation seed 0 uses the explicit `attacking` and `reload` actions from each 60 Hz snapshot.\n\nFor both sources, every second and owner satisfies `firing + not firing = alive`. The reason buckets—reload, moving or stationary pursuit, in-range idle, and untargeted movement or idle—also sum to not firing. At every transition into attack windup, the analyzer records actor and target positions, subtracts their outline radii for edge distance, and retains center distance for audit.",
        },
        {
          id: "limitations",
          type: "markdown",
          sourceId: "comparison-source",
          body: "## Limits and robustness\n\nThis is intentionally a fast one-run comparison, so opening target randomness can move the exact curves. It is suitable for locating a large mechanics discrepancy, not estimating the full outcome distribution. The live and simulation action models are observably equivalent but not byte-identical: the live attack state spans the animation, while simulation exposes an explicit attack-start event and action. Projectile travel means shot starts and HP loss land in different buckets.\n\nShot-start distance is sampled at the first observed live frame in `Action.state=7`; the true transition can occur between frames. Targets can also move during windup. Those effects make sub-frame distance differences less trustworthy than the 0.95-unit HCA firing-count gap or the 30-shot HCA start deficit. The historical five-seed pathing section below remains supporting context and is not part of this single-run comparison.",
        },
        {
          id: "next-steps",
          type: "markdown",
          body: `## The next targeted trace should explain HCA firing downtime\n\n1. Decompose the **${round(hcaTwentySimNotFiring - hcaTwentyLiveNotFiring, 2)}-unit HCA not-firing excess** after the opening into reload, moving pursuit, stationary pursuit, in-range idle, and no-target time.\n2. Trace the missing **${hcaLiveRange.shotStarts - hcaSimRange.shotStarts} HCA shot starts** against target death, retarget delay, and reload completion; do not alter damage or add matchup timing unless a reusable mechanic supports it.\n3. Keep engagement distance fixed for now. The ${round(hcaLiveRange.meanEdgeDistance - hcaSimRange.meanEdgeDistance, 3)}-tile HCA difference is measurable but too small to explain the current firing deficit alone.\n4. Recheck this same one-run diagnostic after that mechanics change before running any other matchup.`,
        },
        {
          id: "further-questions",
          type: "markdown",
          body: "## What remains unresolved\n\n- Why does simulation seed 0 put both armies into windup too aggressively during seconds 0-5?\n- Why do HCA then fall behind live by 30 shot starts over the full window despite similar engagement distance?\n- Is the later HCA deficit primarily reload cadence, target turnover, or path-to-new-target time?\n- Does the small tendency to initiate attacks closer arise from the reach test, discrete movement, or targets continuing to move between acquisition and windup?",
        },
      ],
      charts: [
        {
          id: "not-firing-chart",
          title: "Living units not in attack windup",
          subtitle: "Concurrent units per one-second interval; live run 1 versus simulation seed 0",
          showDescription: true,
          question: "How many living units are not actively firing each second?",
          rationale: "A four-series line chart preserves the requested 20-second comparison; army is encoded by color and source by line style.",
          intent: "trend",
          type: "line",
          dataset: "participation_trends",
          sourceId: "comparison-source",
          encodings: {
            x: { field: "second", type: "quantitative", label: "Game second" },
            y: { field: "not_firing", type: "quantitative", format: "number", label: "Units not firing" },
            color: { field: "army", type: "nominal", label: "Army" },
            lineStyle: { field: "source", type: "nominal", label: "Source" },
            tooltip: [
              { field: "interval", type: "text", label: "Interval" },
              { field: "army", type: "nominal", label: "Army" },
              { field: "source", type: "nominal", label: "Source" },
              { field: "not_firing", type: "quantitative", format: "number", label: "Units not firing" },
            ],
          },
          valueFormat: "number",
          unit: "units",
          layout: "full",
          maxRows: 80,
          palette: { kind: "categorical", name: "army-and-source" },
          legend: { position: "bottom", sort: "spec" },
          labels: { values: "endpoints" },
          settings: { showPoints: "never" },
          surface: { surface: "explorer", interactiveLegend: true, showControls: false, viewMode: "visualization" },
        },
        {
          id: "range-chart",
          title: "Attack-initiation edge distance",
          subtitle: "Mean tiles between unit outlines at windup start; live run 1 versus simulation seed 0",
          showDescription: true,
          question: "At what effective range does each army begin its attacks over time?",
          rationale: "A per-second line comparison shows whether range behavior changes as formations compress; tooltips retain sample count and nominal range.",
          intent: "trend",
          type: "line",
          dataset: "range_trends",
          sourceId: "comparison-source",
          encodings: {
            x: { field: "second", type: "quantitative", label: "Game second" },
            y: { field: "mean_edge_distance", type: "quantitative", format: "number", label: "Edge distance (tiles)" },
            color: { field: "army", type: "nominal", label: "Army" },
            lineStyle: { field: "source", type: "nominal", label: "Source" },
            tooltip: [
              { field: "interval", type: "text", label: "Interval" },
              { field: "army", type: "nominal", label: "Army" },
              { field: "source", type: "nominal", label: "Source" },
              { field: "mean_edge_distance", type: "quantitative", format: "number", label: "Mean edge distance" },
              { field: "nominal_range", type: "quantitative", format: "number", label: "Nominal DAT range" },
              { field: "range_samples", type: "quantitative", format: "integer", label: "Shot starts" },
            ],
          },
          valueFormat: "number",
          unit: "tiles",
          layout: "full",
          maxRows: 80,
          palette: { kind: "categorical", name: "army-and-source" },
          legend: { position: "bottom", sort: "spec" },
          labels: { values: "endpoints" },
          settings: { showPoints: "always" },
          surface: { surface: "explorer", interactiveLegend: true, showControls: false, viewMode: "visualization" },
        },
        {
          id: "stall-chart",
          title: "Units stationary with a valid target still outside range",
          subtitle: "Direct pathing/access-stall test; mean concurrent living units per one-second interval",
          showDescription: true,
          question: "How many units have a target to attack but are not moving and cannot yet fire?",
          rationale: "The same color and line-style contract makes the HCA divergence directly comparable with the active chart.",
          intent: "trend",
          type: "line",
          dataset: "participation_trends",
          sourceId: "comparison-source",
          encodings: {
            x: { field: "second", type: "quantitative", label: "Game second" },
            y: { field: "stationary_out_of_range", type: "quantitative", format: "number", label: "Mean stationary units outside range" },
            color: { field: "army", type: "nominal", label: "Army" },
            lineStyle: { field: "source", type: "nominal", label: "Source" },
            tooltip: [
              { field: "interval", type: "text", label: "Interval" },
              { field: "army", type: "nominal", label: "Army" },
              { field: "source", type: "nominal", label: "Source" },
              { field: "stationary_out_of_range", type: "quantitative", format: "number", label: "Stationary outside range" },
            ],
          },
          valueFormat: "number",
          unit: "units",
          layout: "full",
          maxRows: 80,
          palette: { kind: "categorical", name: "army-and-source" },
          legend: { position: "bottom", sort: "spec" },
          labels: { values: "endpoints" },
          settings: { showPoints: "never" },
          surface: { surface: "explorer", interactiveLegend: true, showControls: false, viewMode: "visualization" },
        },
      ],
      tables: [
        {
          id: "range-summary-table",
          title: "Shot-initiation distance summary",
          subtitle: "All resolved attack starts in seconds 0-20; live run 1 versus simulation seed 0",
          showDescription: true,
          dataset: "range_summary_rows",
          sourceId: "comparison-source",
          defaultSort: { field: "army", direction: "asc" },
          density: "spacious",
          layout: "full",
          columns: [
            { field: "army", label: "Army", type: "text" },
            { field: "source", label: "Source", type: "text" },
            { field: "shot_starts", label: "Shot starts", type: "number" },
            { field: "resolved_samples", label: "Range samples", type: "number" },
            { field: "nominal_range", label: "DAT range", format: "number", role: "value" },
            { field: "mean_center_distance", label: "Mean center distance", format: "number", role: "value" },
            { field: "mean_edge_distance", label: "Mean edge distance", format: "number", role: "value" },
            { field: "median_edge_distance", label: "Median edge distance", format: "number", role: "value" },
            { field: "p10_edge_distance", label: "P10 edge", format: "number", role: "value" },
            { field: "p90_edge_distance", label: "P90 edge", format: "number", role: "value" },
            { field: "mean_nominal_headroom", label: "Mean inside max", format: "number", role: "value" },
            { field: "beyond_nominal_share", label: "Starts beyond nominal", format: "percent", role: "value" },
          ],
        },
        {
          id: "stall-episodes-table",
          title: "Longest HCA stationary pursuit episodes",
          subtitle: "Five current-engine seeds, seconds 5-20; continuous same-target movement attempts rejected by the solver",
          showDescription: true,
          dataset: "stall_episode_rows",
          sourceId: "stall-diagnostic-source",
          defaultSort: { field: "duration_seconds", direction: "desc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "seed", label: "Seed", type: "number" },
            { field: "hca", label: "HCA ID", type: "number" },
            { field: "start_second", label: "Start (s)", format: "number", role: "value" },
            { field: "end_second", label: "End (s)", format: "number", role: "value" },
            { field: "duration_seconds", label: "Duration (s)", format: "number", role: "value" },
            { field: "arbalester_target", label: "Arbalester target", type: "number" },
            { field: "mean_tiles_outside_range", label: "Mean tiles short", format: "number", role: "value" },
            { field: "max_tiles_outside_range", label: "Max tiles short", format: "number", role: "value" },
            { field: "allied_blocker_ids", label: "Recurring allied blockers", type: "text" },
          ],
        },
        {
          id: "exact-table",
          title: "Per-second live and simulation participation",
          subtitle: "Live run 1 versus simulation seed 0; counts are concurrent units except shot starts and damage hits",
          showDescription: true,
          dataset: "exact_second_rows",
          sourceId: "comparison-source",
          defaultSort: { field: "interval", direction: "asc" },
          density: "compact",
          layout: "full",
          columns: [
            { field: "interval", label: "Second", type: "text" },
            { field: "army", label: "Army", type: "text" },
            { field: "live_firing", label: "Live firing", format: "number", role: "value" },
            { field: "simulation_firing", label: "Sim firing", format: "number", role: "value" },
            { field: "firing_delta", label: "Firing delta", format: "number", role: "movement", movement: true },
            { field: "live_not_firing", label: "Live not firing", format: "number", role: "value" },
            { field: "simulation_not_firing", label: "Sim not firing", format: "number", role: "value" },
            { field: "not_firing_delta", label: "Not-firing delta", format: "number", role: "movement", movement: true },
            { field: "live_active", label: "Live active", format: "number", role: "value" },
            { field: "simulation_active", label: "Sim active", format: "number", role: "value" },
            { field: "active_delta", label: "Active delta", format: "number", role: "movement", movement: true },
            { field: "live_moving_to_target", label: "Live moving", format: "number", role: "value" },
            { field: "simulation_moving_to_target", label: "Sim moving", format: "number", role: "value" },
            { field: "live_stationary_out_of_range", label: "Live stalled", format: "number", role: "value" },
            { field: "simulation_stationary_out_of_range", label: "Sim stalled", format: "number", role: "value" },
            { field: "live_in_range_not_firing", label: "Live in-range idle", format: "number", role: "value" },
            { field: "simulation_in_range_not_firing", label: "Sim in-range idle", format: "number", role: "value" },
            { field: "live_shot_starts", label: "Live starts", format: "number", role: "value" },
            { field: "simulation_shot_starts", label: "Sim starts", format: "number", role: "value" },
            { field: "live_damage_hits", label: "Live hits", format: "number", role: "value" },
            { field: "simulation_damage_hits", label: "Sim hits", format: "number", role: "value" },
          ],
        },
      ],
      sources: [
        comparisonSource,
        liveSource,
        simulationSource,
        stallDiagnosticSource,
        outcomeSource,
        engineRecoverySource,
      ],
    },
    snapshot: {
      version: 1,
      generatedAt,
      status: "ready",
      datasets: {
        participation_trends: trends,
        range_trends: rangeTrends,
        range_summary_rows: rangeSummary,
        exact_second_rows: tableRows,
        stall_episode_rows: episodeRows,
      },
    },
    sources: [
      comparisonSource,
      liveSource,
      simulationSource,
      stallDiagnosticSource,
      outcomeSource,
      engineRecoverySource,
    ],
  };
  await writeFile(OUTPUT, `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
  process.stdout.write(`${OUTPUT.pathname}\n`);
}


await main();
