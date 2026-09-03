import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

import {
  PHASE2_MAX_TICKS,
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  scenarioFromPhase2Batch1Row,
} from "../../../src/phase2-batch1-comparison.js";
import { signedScore } from "../../../src/standard-units-comparison.js";
import { createWorld, stepWorld } from "../../../src/combat/world.js";

const ROOT = new URL("../../../", import.meta.url);
const HERE = dirname(fileURLToPath(import.meta.url));
const OUTPUT_ARGUMENT = process.argv.indexOf("--output-dir");
const REPORT_DIR = OUTPUT_ARGUMENT >= 0
  ? resolve(process.argv[OUTPUT_ARGUMENT + 1] ?? "")
  : resolve(HERE, "../../reports/conquistador_arbalester_diagnosis_2026-08-19");
if (OUTPUT_ARGUMENT >= 0 && !process.argv[OUTPUT_ARGUMENT + 1]) {
  throw new Error("--output-dir requires a path");
}
const AUTHORIZED_SHA = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const ROW_ID = "elite_conquistador_vs_arbalester";
const CADENCE_MS = 100;
const TAPE_ATTACK_STATE = 7;
const TICKS_PER_SECOND = 60;
const OWNER_LABEL = Object.freeze({ 2: "Elite Conquistador", 3: "Arbalester" });
const RADIUS = Object.freeze({ 2: 0.25, 3: 0.2 });
const OUTLINE_RADIUS = Object.freeze({ 2: 0.4, 3: 0.2 });
const RANGE = Object.freeze({ 2: 6, 3: 8 });
const ATTACK_DELAY_MS = Object.freeze({ 2: 404.4444300234318, 3: 342.2222286462784 });

const truth = await loadPhase2Batch1Truth(ROOT);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row) throw new Error(`missing Phase 2 row ${ROW_ID}`);
if (truth.archive?.zip_sha256 !== AUTHORIZED_SHA && truth.zip_sha256 !== AUTHORIZED_SHA) {
  throw new Error("truth fixture is not pinned to the authorized Phase 2 archive");
}
const archivePath = resolve(fileURLToPath(new URL("../../", ROOT)), truth.archive.path);
const observedSha = await sha256(archivePath);
if (observedSha !== AUTHORIZED_SHA) {
  throw new Error(`authorized archive hash mismatch: ${observedSha}`);
}

const context = await loadPhase2Batch1Context(ROOT, truth);
const tapeRuns = [];
for (const run of row.runs) {
  const tag = run.tag;
  const tracePath = join(HERE, `${tag}.tape_trace.jsonl`);
  const summaryPath = join(HERE, `${tag}.summary.json`);
  const [frames, summary] = await Promise.all([
    readTrace(tracePath, new Set(run.starting_units.map(({ id }) => id))),
    readFile(summaryPath, "utf8").then(JSON.parse),
  ]);
  tapeRuns.push(analyzeRun({
    source: "tape",
    label: `repeat-${run.repeat}`,
    frames,
    summaryHits: {
      2: summary.sides.side2.hits_landed,
      3: summary.sides.side3.hits_landed,
    },
    signedScore: run.signed_score,
  }));
}

const simulationRuns = [];
for (let sampleIndex = 0; sampleIndex < 5; sampleIndex += 1) {
  simulationRuns.push(runSimulation({ row, context, sampleIndex, seed: 20260817 }));
}

const report = Object.freeze({
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  source: Object.freeze({
    archive: truth.archive.path,
    requiredSha256: AUTHORIZED_SHA,
    observedSha256: observedSha,
    tapeMembers: Object.freeze(row.runs.map(({ source_members }) => source_members.frames)),
  }),
  matchup: Object.freeze({
    id: row.id,
    label: row.matchup,
    side2: row.side2,
    side3: row.side3,
  }),
  definitions: Object.freeze({
    cadenceMs: CADENCE_MS,
    overlap: "Chebyshev center separation below the sum of same-army collision radii",
    depth: "sum of collision radii minus Chebyshev center separation",
    frontRear: "live units split into thirds by projection toward the opposing live-army centroid",
    tapeShotRelease: "an observed attack-state episode that lasts through the sourced projectile release delay, with one raw-frame tolerance",
    tapeHit: "decoded golden summary hit attribution",
    simulationShotRelease: "a newly queued ranged or stray projectile on its fired tick",
    simulationHit: "a ranged-projectile or stray-projectile damage event",
  }),
  tape: Object.freeze({
    runs: Object.freeze(tapeRuns),
    aggregate: aggregateRuns(tapeRuns),
  }),
  simulation: Object.freeze({
    runs: Object.freeze(simulationRuns),
    aggregate: aggregateRuns(simulationRuns),
  }),
});

const markdown = renderMarkdown(report);
await mkdir(REPORT_DIR, { recursive: true });
await atomicWrite(join(REPORT_DIR, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
await atomicWrite(join(REPORT_DIR, "report.md"), markdown);
await atomicWrite(join(REPORT_DIR, "run-manifest.json"), `${JSON.stringify({
  schemaVersion: 1,
  rowId: ROW_ID,
  archiveSha256: AUTHORIZED_SHA,
  tapeRuns: tapeRuns.length,
  simulationRuns: simulationRuns.length,
  cadenceMs: CADENCE_MS,
  files: ["report.json", "report.md", "run-manifest.json"],
}, null, 2)}\n`);

process.stdout.write(`${JSON.stringify({
  reportDirectory: REPORT_DIR,
  tape: compact(report.tape.aggregate),
  simulation: compact(report.simulation.aggregate),
}, null, 2)}\n`);

async function readTrace(path, rosterIds) {
  const byTime = new Map();
  const input = createInterface({ input: createReadStream(path), crlfDelay: Infinity });
  for await (const line of input) {
    if (!line) continue;
    const unit = JSON.parse(line);
    if (!rosterIds.has(unit.id)) continue;
    let units = byTime.get(unit.t_ms);
    if (!units) {
      units = [];
      byTime.set(unit.t_ms, units);
    }
    units.push(normalizeTapeUnit(unit));
  }
  return [...byTime.entries()]
    .sort(([left], [right]) => left - right)
    .map(([timeMs, units]) => ({ timeMs, units }));
}

function normalizeTapeUnit(unit) {
  return Object.freeze({
    id: unit.id,
    owner: unit.owner,
    master: unit.master,
    x: unit.x,
    y: unit.y,
    hp: unit.hp ?? 0,
    alive: (unit.hp ?? 0) > 0,
    attacking: unit.action_state === TAPE_ATTACK_STATE,
    actionState: unit.action_state ?? null,
    actionModelType: unit.action_model_type ?? null,
    targetId: Number.isSafeInteger(unit.target_id) && unit.target_id >= 0 ? unit.target_id : null,
    targetX: Number.isFinite(unit.target_x) ? unit.target_x : null,
    targetY: Number.isFinite(unit.target_y) ? unit.target_y : null,
  });
}

function runSimulation({ row: selectedRow, context: selectedContext, sampleIndex, seed }) {
  const scenario = scenarioFromPhase2Batch1Row({
    row: selectedRow,
    context: selectedContext,
    sampleIndex,
    seed,
  });
  let world = createWorld(scenario);
  const frames = [{ timeMs: 0, units: world.units.map(normalizeSimulationUnit) }];
  const events = [...world.eventLog];
  const releaseCounts = { 2: 0, 3: 0 };
  const unitOwner = new Map(world.units.map(({ referenceId, owner }) => [referenceId, owner]));
  world = Object.freeze({ ...world, eventLog: Object.freeze([]), snapshots: Object.freeze([]) });
  let winner = null;
  for (let elapsed = 0; elapsed < PHASE2_MAX_TICKS; elapsed += 1) {
    const next = stepWorld(world);
    events.push(...next.eventLog);
    for (const projectile of next.projectiles ?? []) {
      if (projectile.firedTick !== next.tick) continue;
      if (!["ranged", "stray"].includes(projectile.kind)) continue;
      const owner = unitOwner.get(projectile.actorId);
      if (owner === 2 || owner === 3) releaseCounts[owner] += 1;
    }
    if (next.tick % 6 === 0) {
      frames.push({
        timeMs: 1000 * next.tick / TICKS_PER_SECOND,
        units: next.units.map(normalizeSimulationUnit),
      });
    }
    const liveOwners = new Set(next.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (liveOwners.size <= 1) {
      winner = [...liveOwners][0] ?? null;
      if (frames.at(-1)?.timeMs !== 1000 * next.tick / TICKS_PER_SECOND) {
        frames.push({
          timeMs: 1000 * next.tick / TICKS_PER_SECOND,
          units: next.units.map(normalizeSimulationUnit),
        });
      }
      world = next;
      break;
    }
    world = Object.freeze({ ...next, eventLog: Object.freeze([]), snapshots: Object.freeze([]) });
  }
  const hitCounts = { 2: 0, 3: 0 };
  for (const entry of events) {
    if (entry.type !== "damage") continue;
    if (!["ranged-projectile", "stray-projectile"].includes(entry.kind)) continue;
    const owner = unitOwner.get(entry.actorId);
    if (owner === 2 || owner === 3) hitCounts[owner] += 1;
  }
  const analyzed = analyzeRun({
    source: "simulation",
    label: `sample-${sampleIndex}`,
    frames,
    summaryHits: hitCounts,
    explicitReleases: releaseCounts,
    events,
  });
  const live = world.units.filter(({ alive }) => alive);
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    ...analyzed,
    winnerOwner: winner,
    winnerHp,
    signedScore: signedScore({
      winnerOwner: winner,
      winnerHp,
      startingHpByOwner: selectedRow.runs[0].starting_hp_by_owner,
    }),
    ticks: world.tick,
    scenarioOrders: Object.freeze({
      rangedTargetPressureOwner: scenario.rangedTargetPressureOwner ?? null,
      rangedOpportunityRetargetOwner: scenario.rangedOpportunityRetargetOwner ?? null,
      rangedWindupRetargetOwner: scenario.rangedWindupRetargetOwner ?? null,
      kiteOwner: scenario.kiteOwner ?? null,
    }),
  });
}

function normalizeSimulationUnit(unit) {
  return Object.freeze({
    id: unit.referenceId,
    owner: unit.owner,
    master: unit.mechanics.unit_master,
    x: unit.x,
    y: unit.y,
    hp: unit.hp,
    alive: unit.alive,
    attacking: unit.action === "attacking",
    actionState: unit.action,
    actionModelType: null,
    targetId: unit.attackTargetId ?? unit.engagedTargetId ?? unit.pursuitTargetId ?? null,
    targetX: null,
    targetY: null,
  });
}

function analyzeRun({ source, label, frames, summaryHits, explicitReleases = null, events = [] }) {
  const sampled = sampleFrames(trimCombatFrames(frames), CADENCE_MS);
  const overlap = { 2: analyzeOverlap(sampled, 2), 3: analyzeOverlap(sampled, 3) };
  const ranks = { 2: analyzeRanks(sampled, 2), 3: analyzeRanks(sampled, 3) };
  const observedOrders = analyzeObservedOrders(frames);
  const inferredReleases = source === "tape"
    ? { 2: inferTapeReleases(frames, 2), 3: inferTapeReleases(frames, 3) }
    : null;
  const releases = explicitReleases ?? {
    2: inferredReleases[2].releasedEpisodes,
    3: inferredReleases[3].releasedEpisodes,
  };
  const shots = {};
  for (const owner of [2, 3]) {
    const hits = summaryHits[owner];
    const fired = releases[owner];
    shots[owner] = Object.freeze({
      fired,
      hits,
      misses: Math.max(0, fired - hits),
      hitRate: fired > 0 ? hits / fired : null,
      ...(source === "tape" ? { inference: inferredReleases[owner] } : {}),
    });
  }
  return Object.freeze({
    source,
    label,
    durationSeconds: (sampled.at(-1).timeMs - sampled[0].timeMs) / 1000,
    signedScore: arguments[0].signedScore ?? null,
    overlap: Object.freeze(overlap),
    ranks: Object.freeze(ranks),
    observedOrders,
    shots: Object.freeze(shots),
    eventTypes: source === "simulation" ? countBy(events, ({ type }) => type) : null,
  });
}

function analyzeOverlap(frames, owner) {
  let pairObservations = 0;
  let overlappingPairObservations = 0;
  let liveUnitObservations = 0;
  let overlappingUnitObservations = 0;
  let framesWithOverlap = 0;
  let maximumPairs = 0;
  let maximumDegree = 0;
  let maximumComponent = 0;
  const depths = [];
  const separations = [];
  const attacking = { overlapping: 0, overlappingTotal: 0, clear: 0, clearTotal: 0 };
  for (const frame of frames) {
    const units = frame.units.filter((unit) => unit.owner === owner && unit.alive);
    liveUnitObservations += units.length;
    const adjacency = new Map(units.map(({ id }) => [id, new Set()]));
    let pairs = 0;
    for (let left = 0; left < units.length; left += 1) {
      for (let right = left + 1; right < units.length; right += 1) {
        pairObservations += 1;
        const separation = Math.max(
          Math.abs(units[left].x - units[right].x),
          Math.abs(units[left].y - units[right].y),
        );
        if (separation >= 2 * RADIUS[owner] - 1e-12) continue;
        overlappingPairObservations += 1;
        pairs += 1;
        separations.push(separation);
        depths.push(2 * RADIUS[owner] - separation);
        adjacency.get(units[left].id).add(units[right].id);
        adjacency.get(units[right].id).add(units[left].id);
      }
    }
    if (pairs > 0) framesWithOverlap += 1;
    maximumPairs = Math.max(maximumPairs, pairs);
    maximumDegree = Math.max(maximumDegree, ...[...adjacency.values()].map((set) => set.size), 0);
    maximumComponent = Math.max(maximumComponent, largestComponent(adjacency));
    for (const unit of units) {
      const hasOverlap = adjacency.get(unit.id).size > 0;
      if (hasOverlap) {
        overlappingUnitObservations += 1;
        attacking.overlappingTotal += 1;
        attacking.overlapping += Number(unit.attacking);
      } else {
        attacking.clearTotal += 1;
        attacking.clear += Number(unit.attacking);
      }
    }
  }
  return Object.freeze({
    pairObservations,
    overlappingPairObservations,
    overlapPairShare: ratio(overlappingPairObservations, pairObservations),
    frameOverlapShare: ratio(framesWithOverlap, frames.length),
    overlappingUnitShare: ratio(overlappingUnitObservations, liveUnitObservations),
    separation: distribution(separations),
    depth: distribution(depths),
    minimumSeparation: distribution(separations).minimum,
    medianSeparation: distribution(separations).median,
    medianDepth: distribution(depths).median,
    maximumDepth: distribution(depths).maximum,
    maximumSimultaneousPairs: maximumPairs,
    maximumLocalDegree: maximumDegree,
    maximumComponentSize: maximumComponent,
    attackingShareWhenOverlapping: ratio(attacking.overlapping, attacking.overlappingTotal),
    attackingShareWhenClear: ratio(attacking.clear, attacking.clearTotal),
  });
}

function analyzeRanks(frames, owner) {
  const totals = { front: 0, middle: 0, rear: 0 };
  const attacking = { front: 0, middle: 0, rear: 0 };
  const inRange = { front: 0, middle: 0, rear: 0 };
  const targeted = { front: 0, middle: 0, rear: 0 };
  for (const frame of frames) {
    const own = frame.units.filter((unit) => unit.owner === owner && unit.alive);
    const enemy = frame.units.filter((unit) => unit.owner !== owner && unit.alive);
    if (!own.length || !enemy.length) continue;
    const ownCenter = centroid(own);
    const enemyCenter = centroid(enemy);
    const directionLength = Math.hypot(enemyCenter.x - ownCenter.x, enemyCenter.y - ownCenter.y) || 1;
    const dx = (enemyCenter.x - ownCenter.x) / directionLength;
    const dy = (enemyCenter.y - ownCenter.y) / directionLength;
    const ranked = own.slice().sort((left, right) => (
      ((right.x - ownCenter.x) * dx + (right.y - ownCenter.y) * dy)
      - ((left.x - ownCenter.x) * dx + (left.y - ownCenter.y) * dy)
    ));
    const byId = new Map(frame.units.map((unit) => [unit.id, unit]));
    ranked.forEach((unit, index) => {
      const band = index < Math.ceil(ranked.length / 3)
        ? "front"
        : (index >= ranked.length - Math.ceil(ranked.length / 3) ? "rear" : "middle");
      totals[band] += 1;
      attacking[band] += Number(unit.attacking);
      const target = byId.get(unit.targetId);
      if (target?.alive && target.owner !== owner) {
        targeted[band] += 1;
        const centerDistance = Math.hypot(target.x - unit.x, target.y - unit.y);
        const reach = RANGE[owner] + 0.1 + OUTLINE_RADIUS[owner] + OUTLINE_RADIUS[target.owner];
        inRange[band] += Number(centerDistance <= reach + 1e-12);
      }
    });
  }
  return Object.freeze(Object.fromEntries(["front", "middle", "rear"].map((band) => [band, {
    observations: totals[band],
    attackingShare: ratio(attacking[band], totals[band]),
    targetAssignedShare: ratio(targeted[band], totals[band]),
    inRangeGivenTargetShare: ratio(inRange[band], targeted[band]),
  }])));
}

function analyzeObservedOrders(frames) {
  const state = { 2: new Map(), 3: new Map() };
  const firstTargets = { 2: new Map(), 3: new Map() };
  const firstActionTimes = { 2: [], 3: [] };
  const targetChanges = { 2: 0, 3: 0 };
  const actionTransitions = { 2: new Map(), 3: new Map() };
  for (const frame of frames) {
    for (const unit of frame.units) {
      if (![2, 3].includes(unit.owner)) continue;
      const previous = state[unit.owner].get(unit.id);
      if (unit.targetId !== null && previous?.targetId !== unit.targetId) {
        if (previous?.targetId !== null && previous?.targetId !== undefined) targetChanges[unit.owner] += 1;
        if (!firstTargets[unit.owner].has(unit.id)) {
          firstTargets[unit.owner].set(unit.id, unit.targetId);
          firstActionTimes[unit.owner].push(frame.timeMs);
        }
      }
      if (unit.actionState !== previous?.actionState && unit.actionState !== null) {
        const key = String(unit.actionState);
        actionTransitions[unit.owner].set(key, (actionTransitions[unit.owner].get(key) ?? 0) + 1);
      }
      state[unit.owner].set(unit.id, unit);
    }
  }
  return Object.freeze(Object.fromEntries([2, 3].map((owner) => {
    const targetCounts = countBy([...firstTargets[owner].values()], (value) => value);
    const loads = Object.values(targetCounts);
    return [owner, Object.freeze({
      unitsReceivingTarget: firstTargets[owner].size,
      distinctFirstTargets: loads.length,
      largestFirstTargetLoad: loads.length ? Math.max(...loads) : 0,
      firstTargetConcentration: ratio(loads.length ? Math.max(...loads) : 0, firstTargets[owner].size),
      firstActionTimeMs: distribution(firstActionTimes[owner]),
      targetChanges: targetChanges[owner],
      actionTransitions: Object.freeze(Object.fromEntries(actionTransitions[owner])),
    })];
  })));
}

function inferTapeReleases(frames, owner) {
  const active = new Map();
  const episodes = [];
  let previousTime = frames[0]?.timeMs ?? 0;
  for (const frame of frames) {
    const liveIds = new Set();
    for (const unit of frame.units.filter((candidate) => candidate.owner === owner)) {
      liveIds.add(unit.id);
      const before = active.get(unit.id);
      if (unit.attacking) {
        if (!before || before.targetId !== unit.targetId) {
          if (before) episodes.push({ ...before, endMs: previousTime });
          active.set(unit.id, { id: unit.id, targetId: unit.targetId, startMs: frame.timeMs });
        }
      } else if (before) {
        episodes.push({ ...before, endMs: previousTime });
        active.delete(unit.id);
      }
    }
    for (const [id, episode] of active) {
      if (!liveIds.has(id)) {
        episodes.push({ ...episode, endMs: previousTime });
        active.delete(id);
      }
    }
    previousTime = frame.timeMs;
  }
  for (const episode of active.values()) episodes.push({ ...episode, endMs: previousTime });
  const toleranceMs = 34;
  const durations = episodes.map(({ startMs, endMs }) => endMs - startMs);
  const released = durations.filter((duration) => duration + toleranceMs >= ATTACK_DELAY_MS[owner]);
  return Object.freeze({
    attackEpisodes: episodes.length,
    releasedEpisodes: released.length,
    canceledBeforeRelease: episodes.length - released.length,
    durationMs: distribution(durations),
  });
}

function trimCombatFrames(frames) {
  const first = frames.findIndex(({ units }) => liveOwnerCount(units) >= 2);
  if (first < 0) throw new Error("trace has no two-owner frame");
  let last = frames.length - 1;
  for (let index = first + 1; index < frames.length; index += 1) {
    if (liveOwnerCount(frames[index].units) < 2) {
      last = index;
      break;
    }
  }
  return frames.slice(first, last + 1);
}

function sampleFrames(frames, cadenceMs) {
  if (!frames.length) return [];
  const sampled = [];
  let cursor = 0;
  for (let target = frames[0].timeMs; target <= frames.at(-1).timeMs; target += cadenceMs) {
    while (cursor + 1 < frames.length
        && Math.abs(frames[cursor + 1].timeMs - target) <= Math.abs(frames[cursor].timeMs - target)) {
      cursor += 1;
    }
    if (sampled.at(-1) !== frames[cursor]) sampled.push(frames[cursor]);
  }
  return sampled;
}

function aggregateRuns(runs) {
  const aggregate = { overlap: {}, ranks: {}, observedOrders: {}, shots: {} };
  for (const owner of [2, 3]) {
    aggregate.overlap[owner] = aggregateObject(runs.map((run) => run.overlap[owner]), [
      "overlapPairShare", "frameOverlapShare", "overlappingUnitShare",
      "minimumSeparation", "medianSeparation", "medianDepth", "maximumDepth",
      "maximumSimultaneousPairs", "maximumLocalDegree", "maximumComponentSize",
      "attackingShareWhenOverlapping", "attackingShareWhenClear",
    ]);
    aggregate.ranks[owner] = Object.fromEntries(["front", "middle", "rear"].map((band) => [
      band,
      aggregateObject(runs.map((run) => run.ranks[owner][band]), [
        "attackingShare", "targetAssignedShare", "inRangeGivenTargetShare",
      ]),
    ]));
    aggregate.observedOrders[owner] = aggregateObject(runs.map((run) => run.observedOrders[owner]), [
      "unitsReceivingTarget", "distinctFirstTargets", "largestFirstTargetLoad",
      "firstTargetConcentration", "targetChanges",
    ]);
    aggregate.shots[owner] = aggregateObject(runs.map((run) => run.shots[owner]), [
      "fired", "hits", "misses", "hitRate",
    ]);
  }
  return Object.freeze(aggregate);
}

function aggregateObject(objects, fields) {
  return Object.freeze(Object.fromEntries(fields.map((field) => [
    field,
    distribution(objects.map((object) => object[field]).filter(Number.isFinite)),
  ])));
}

function renderMarkdown(value) {
  const lines = [
    "# Elite Conquistador versus Arbalester: tape/simulation diagnosis",
    "",
    "## Technical summary",
    "",
    "This report compares all four authorized Phase 2 golden recordings with five current-engine samples for the exact 12 Elite Conquistador versus 21 Arbalester row. It is diagnostic only; no engine behavior is changed.",
    "",
    `- Archive SHA-256: \`${value.source.observedSha256}\``,
    `- Geometry cadence: ${CADENCE_MS} ms`,
    "- Tape projectile hits come from the archive's decoded hit attribution; tape releases are inferred from full-rate action episodes that persist through the sourced release frame.",
    "",
    "## Same-army overlap",
    "",
    "| Unit | Source | Pair overlap share | Unit overlap share | Median depth | Max depth | Frames with overlap | Max pairs | Max neighbor degree | Max component | Attacking while overlapped | Attacking while clear |",
    "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
  ];
  for (const owner of [2, 3]) {
    for (const [source, data] of [["Tape", value.tape.aggregate], ["Simulation", value.simulation.aggregate]]) {
      const metrics = data.overlap[owner];
      lines.push(`| ${OWNER_LABEL[owner]} | ${source} | ${range(metrics.overlapPairShare, true)} | ${range(metrics.overlappingUnitShare, true)} | ${range(metrics.medianDepth)} | ${range(metrics.maximumDepth)} | ${range(metrics.frameOverlapShare, true)} | ${range(metrics.maximumSimultaneousPairs)} | ${range(metrics.maximumLocalDegree)} | ${range(metrics.maximumComponentSize)} | ${range(metrics.attackingShareWhenOverlapping, true)} | ${range(metrics.attackingShareWhenClear, true)} |`);
    }
  }
  lines.push("", "## Front/middle/rear firing access", "", "| Unit | Source | Rank | Attacking share | Target assigned | In range given target |", "|---|---|---|---:|---:|---:|");
  for (const owner of [2, 3]) {
    for (const [source, data] of [["Tape", value.tape.aggregate], ["Simulation", value.simulation.aggregate]]) {
      for (const band of ["front", "middle", "rear"]) {
        const metrics = data.ranks[owner][band];
        lines.push(`| ${OWNER_LABEL[owner]} | ${source} | ${band} | ${range(metrics.attackingShare, true)} | ${range(metrics.targetAssignedShare, true)} | ${range(metrics.inRangeGivenTargetShare, true)} |`);
      }
    }
  }
  lines.push("", "## Target/order observations", "", "| Unit | Source | Units assigned | Distinct first targets | Largest first-target load | First-target concentration | Target changes |", "|---|---|---:|---:|---:|---:|---:|");
  for (const owner of [2, 3]) {
    for (const [source, data] of [["Tape", value.tape.aggregate], ["Simulation", value.simulation.aggregate]]) {
      const metrics = data.observedOrders[owner];
      lines.push(`| ${OWNER_LABEL[owner]} | ${source} | ${range(metrics.unitsReceivingTarget)} | ${range(metrics.distinctFirstTargets)} | ${range(metrics.largestFirstTargetLoad)} | ${range(metrics.firstTargetConcentration, true)} | ${range(metrics.targetChanges)} |`);
    }
  }
  lines.push("", "The raw tape exposes effective per-unit action/target state, not a named high-level command packet. The simulation scenario uses ordinary ranged combat with owner 3 target pressure, owner 2 opportunity retargeting, and owner 3 windup retargeting; neither side has the cohesive kiting order in this row.", "", "## Shots", "", "| Unit | Source | Fired | Hits | Misses | Hit rate |", "|---|---|---:|---:|---:|---:|");
  for (const owner of [2, 3]) {
    for (const [source, data] of [["Tape", value.tape.aggregate], ["Simulation", value.simulation.aggregate]]) {
      const metrics = data.shots[owner];
      lines.push(`| ${OWNER_LABEL[owner]} | ${source} | ${range(metrics.fired)} | ${range(metrics.hits)} | ${range(metrics.misses)} | ${range(metrics.hitRate, true)} |`);
    }
  }
  lines.push("", "## Scope and limitations", "", "- Tape release counts are an inference from the full-rate action channel; hit counts are authoritative decoded archive values. A target death can truncate an action episode, and raw frame loss at the exact transition can shift release inference by one.", "- Rank is recomputed each sampled frame from the direction between army centroids. It measures firing access, not a persistent formation slot.", "- Overlap uses collision boxes, not outline boxes. Projectile reach uses sourced outline/range geometry.", "", "## Next step", "", "Use the overlap and rank-access gaps to decide whether the generic ranged ingress/spacing rule is suppressing rear-rank Conquistador access. Accuracy should be adjusted only if release opportunity first matches the tape and the residual hit rate still differs.", "");
  return `${lines.join("\n").trimEnd()}\n`;
}

function compact(data) {
  return Object.fromEntries([2, 3].map((owner) => [OWNER_LABEL[owner], {
    overlapPairShare: data.overlap[owner].overlapPairShare,
    overlappingUnitShare: data.overlap[owner].overlappingUnitShare,
    rearAttackingShare: data.ranks[owner].rear.attackingShare,
    fired: data.shots[owner].fired,
    hits: data.shots[owner].hits,
    misses: data.shots[owner].misses,
    hitRate: data.shots[owner].hitRate,
  }]));
}

function liveOwnerCount(units) {
  return new Set(units.filter(({ alive, hp }) => alive && hp > 0).map(({ owner }) => owner)).size;
}

function centroid(units) {
  return {
    x: units.reduce((sum, unit) => sum + unit.x, 0) / units.length,
    y: units.reduce((sum, unit) => sum + unit.y, 0) / units.length,
  };
}

function largestComponent(adjacency) {
  const visited = new Set();
  let maximum = 0;
  for (const id of adjacency.keys()) {
    if (visited.has(id)) continue;
    let size = 0;
    const pending = [id];
    visited.add(id);
    while (pending.length) {
      const current = pending.pop();
      size += 1;
      for (const neighbor of adjacency.get(current) ?? []) {
        if (visited.has(neighbor)) continue;
        visited.add(neighbor);
        pending.push(neighbor);
      }
    }
    maximum = Math.max(maximum, size);
  }
  return maximum;
}

function distribution(values) {
  const finite = values.filter(Number.isFinite).sort((left, right) => left - right);
  if (!finite.length) return Object.freeze({ count: 0, minimum: null, median: null, maximum: null });
  return Object.freeze({
    count: finite.length,
    minimum: finite[0],
    median: percentile(finite, 0.5),
    maximum: finite.at(-1),
  });
}

function percentile(sorted, probability) {
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] * (upper - index) + sorted[upper] * (index - lower);
}

function ratio(numerator, denominator) {
  return denominator > 0 ? numerator / denominator : null;
}

function countBy(values, keyOf) {
  const result = {};
  for (const value of values) {
    const key = String(keyOf(value));
    result[key] = (result[key] ?? 0) + 1;
  }
  return result;
}

function range(metric, percent = false) {
  if (!metric || !Number.isFinite(metric.median)) return "—";
  const scale = percent ? 100 : 1;
  const suffix = percent ? "%" : "";
  const format = (number) => `${Math.round(number * scale * 100) / 100}${suffix}`;
  return `${format(metric.median)} (${format(metric.minimum)}–${format(metric.maximum)})`;
}

async function sha256(path) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}

async function atomicWrite(path, contents) {
  const temporary = `${path}.${process.pid}.tmp`;
  await writeFile(temporary, contents, "utf8");
  await rename(temporary, path);
}
