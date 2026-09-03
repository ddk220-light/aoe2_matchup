import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { analyzePairContactFrames } from "../../tools/pair-contact-metrics.mjs";


const CURRENT_ROOT = new URL("../../", import.meta.url);
const DEFAULT_ROWS = Object.freeze([
  "elite_conquistador_vs_champion",
  "elite_janissary_vs_elite_elephant",
  "elite_keshik_vs_champion",
  "elite_keshik_vs_paladin",
  "elite_mangudai_vs_heavy_cav_archer",
  "elite_rattan_archer_vs_champion",
  "elite_rattan_archer_vs_heavy_scorpion",
  "elite_shotel_warrior_vs_paladin",
  "elite_war_wagon_vs_paladin",
]);
const TICKS_PER_SECOND = 60;
const SAMPLE_EVERY_TICKS = 6;
const EMPTY = Object.freeze([]);


const options = parseArguments(process.argv.slice(2));
const engineDirectory = resolve(options.engineRoot);
const engineRoot = pathToFileURL(`${engineDirectory}${sep}`);
const phase2 = await import(new URL("src/phase2-batch1-comparison.js", engineRoot));
const combat = await import(new URL("src/combat/world.js", engineRoot));
const truth = await phase2.loadPhase2Batch1Truth(CURRENT_ROOT);
const context = await phase2.loadPhase2Batch1Context(CURRENT_ROOT, truth);
const byId = new Map(truth.rows.map((row) => [row.id, row]));
const rows = options.rowIds.map((id) => {
  const row = byId.get(id);
  if (!row) throw new RangeError(`unknown Phase 2 row: ${id}`);
  return row;
});

const reportRows = [];
for (const row of rows) {
  const runs = [];
  for (let sampleIndex = 0; sampleIndex < options.samples; sampleIndex += 1) {
    runs.push(runSample({
      row,
      sampleIndex,
      seed: options.seed,
      context,
      createWorld: combat.createWorld,
      stepWorld: combat.stepWorld,
      scenarioFromRow: phase2.scenarioFromPhase2Batch1Row,
      maxTicks: phase2.PHASE2_MAX_TICKS,
    }));
  }
  reportRows.push(Object.freeze({
    id: row.id,
    matchup: row.matchup,
    side2: row.side2,
    side3: row.side3,
    runs: Object.freeze(runs),
    aggregate: aggregateRuns(runs),
  }));
  process.stderr.write(`[${reportRows.length}/${rows.length}] ${options.label}: ${row.id}\n`);
}

const report = Object.freeze({
  schemaVersion: 1,
  label: options.label,
  engineRoot: engineDirectory,
  samples: options.samples,
  seed: options.seed,
  samplingCadenceMs: 100,
  rows: Object.freeze(reportRows),
});
await mkdir(dirname(options.output), { recursive: true });
await writeFile(options.output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({
  label: report.label,
  rows: report.rows.length,
  samples: report.samples,
  output: options.output,
})}\n`);


function runSample({
  row,
  sampleIndex,
  seed,
  context: selectedContext,
  createWorld,
  stepWorld,
  scenarioFromRow,
  maxTicks,
}) {
  const scenario = scenarioFromRow({ row, sampleIndex, seed, context: selectedContext });
  let world = createWorld(scenario);
  const ownerById = new Map(world.units.map((unit) => [unit.referenceId, unit.owner]));
  const frames = [];
  const previousSample = new Map();
  frames.push(normalizeFrame(0, world.units, previousSample));
  const counts = {
    2: { attackStarts: 0, attackCanceled: 0, shotsFired: 0, hits: 0, projectileHits: 0 },
    3: { attackStarts: 0, attackCanceled: 0, shotsFired: 0, hits: 0, projectileHits: 0 },
  };
  let winnerOwner = null;
  let outcome = "timeout";
  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
    const next = stepWorld(world);
    const events = next.eventLog ?? EMPTY;
    observeEvents(events, ownerById, counts);
    observeShots(next.projectiles ?? EMPTY, next.tick, ownerById, counts);
    if (next.tick % SAMPLE_EVERY_TICKS === 0) {
      frames.push(normalizeFrame(next.tick, next.units, previousSample));
    }
    const liveOwners = new Set(next.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (liveOwners.size <= 1) {
      winnerOwner = [...liveOwners][0] ?? null;
      outcome = "win";
      if (frames.at(-1)?.timeMs !== 1000 * next.tick / TICKS_PER_SECOND) {
        frames.push(normalizeFrame(next.tick, next.units, previousSample));
      }
      world = next;
      break;
    }
    world = Object.freeze({ ...next, snapshots: EMPTY, eventLog: EMPTY });
  }
  const combatFrames = trimCombatFrames(frames);
  const winnerHp = winnerOwner === null
    ? null
    : world.units.filter((unit) => unit.alive && unit.owner === winnerOwner)
      .reduce((total, unit) => total + unit.hp, 0);
  const startingHp = row.runs[0].starting_hp_by_owner;
  const score = winnerOwner === null
    ? null
    : signedScore(winnerOwner, winnerHp, startingHp);
  return Object.freeze({
    sampleIndex,
    outcome,
    winnerOwner,
    winnerHp,
    score,
    ticks: world.tick,
    durationSeconds: world.tick / TICKS_PER_SECOND,
    counts: Object.freeze(counts),
    overlap: analyzeOverlap(combatFrames),
    scenario: Object.freeze({
      kiteOwner: scenario.kiteOwner ?? null,
      kiteOpponentMode: scenario.kiteOpponentMode ?? null,
      persistentMeleePursuitRouting: scenario.persistentMeleePursuitRouting ?? false,
      rangedTargetPressureOwner: scenario.rangedTargetPressureOwner ?? null,
      rangedOpportunityRetargetOwner: scenario.rangedOpportunityRetargetOwner ?? null,
      rangedWindupRetargetOwner: scenario.rangedWindupRetargetOwner ?? null,
    }),
  });
}


function observeEvents(events, ownerById, counts) {
  for (const event of events) {
    const owner = ownerById.get(event.actorId);
    if (owner !== 2 && owner !== 3) continue;
    if (event.type === "attack-start") counts[owner].attackStarts += 1;
    if (event.type === "attack-canceled") counts[owner].attackCanceled += 1;
    if (event.type !== "damage") continue;
    counts[owner].hits += 1;
    if (String(event.kind ?? "").includes("projectile")) counts[owner].projectileHits += 1;
  }
}


function observeShots(projectiles, tick, ownerById, counts) {
  const releases = new Set();
  for (const projectile of projectiles) {
    if (projectile.firedTick !== tick) continue;
    releases.add(`${String(projectile.actorId)}\0${tick}`);
  }
  for (const release of releases) {
    const actorId = Number(release.slice(0, release.indexOf("\0")));
    const owner = ownerById.get(actorId);
    if (owner === 2 || owner === 3) counts[owner].shotsFired += 1;
  }
}


function normalizeFrame(tick, units, previousSample) {
  const normalized = units.map((unit) => {
    const before = previousSample.get(unit.referenceId);
    const moving = before !== undefined
      && Math.hypot(unit.x - before.x, unit.y - before.y) > 1e-9;
    previousSample.set(unit.referenceId, { x: unit.x, y: unit.y });
    return Object.freeze({
      id: unit.referenceId,
      owner: unit.owner,
      master: unit.mechanics.unit_master,
      x: unit.x,
      y: unit.y,
      hp: unit.hp,
      radius: collisionRadius(unit.mechanics),
      minCollisionMultiplier: unit.mechanics.min_collision_size_multiplier ?? 1,
      moving,
      attacking: unit.action === "attacking",
      pursuitTargetId: unit.pursuitTargetId ?? null,
      engagedTargetId: unit.engagedTargetId ?? null,
      attackTargetId: unit.attackTargetId ?? null,
    });
  });
  return Object.freeze({
    timeMs: 1000 * tick / TICKS_PER_SECOND,
    units: Object.freeze(normalized),
  });
}


function analyzeOverlap(frames) {
  const owner2 = analyzePairContactFrames(frames.map((frame) => ({
    ...frame,
    units: frame.units.filter(({ owner }) => owner === 2),
  }))).relationships["same-master-allies"] ?? emptyOverlap();
  const owner3 = analyzePairContactFrames(frames.map((frame) => ({
    ...frame,
    units: frame.units.filter(({ owner }) => owner === 3),
  }))).relationships["same-master-allies"] ?? emptyOverlap();
  const enemies = analyzePairContactFrames(frames).relationships.enemies ?? emptyOverlap();
  return Object.freeze({
    side2: compactOverlap(owner2),
    side3: compactOverlap(owner3),
    enemies: compactOverlap(enemies),
  });
}


function compactOverlap(metrics) {
  return Object.freeze({
    overlapPairShare: metrics.overlapPairShare ?? 0,
    frameOverlapShare: metrics.frameCount > 0
      ? metrics.framesWithOverlap / metrics.frameCount
      : 0,
    medianDepth: metrics.medianDepth ?? null,
    p95Depth: metrics.p95Depth ?? null,
    maximumDepth: metrics.maximumDepth ?? null,
    maximumLocalDegree: metrics.maximumLocalDegree ?? 0,
    maximumComponentSize: metrics.maximumComponentSize ?? 0,
    maximumTriangles: metrics.maximumTriangles ?? 0,
  });
}


function emptyOverlap() {
  return Object.freeze({
    pairFrames: 0,
    overlapPairShare: 0,
    frameCount: 0,
    framesWithOverlap: 0,
  });
}


function trimCombatFrames(frames) {
  const first = frames.findIndex((frame) => liveOwnerCount(frame.units) >= 2);
  if (first < 0) return frames;
  let last = frames.length - 1;
  for (let index = first + 1; index < frames.length; index += 1) {
    if (liveOwnerCount(frames[index].units) < 2) {
      last = index;
      break;
    }
  }
  return frames.slice(first, last + 1);
}


function liveOwnerCount(units) {
  return new Set(units.filter(({ hp }) => hp > 0).map(({ owner }) => owner)).size;
}


function collisionRadius(mechanics) {
  const radius = Math.max(
    mechanics?.collision_size_tiles?.x ?? NaN,
    mechanics?.collision_size_tiles?.y ?? NaN,
  );
  if (!Number.isFinite(radius) || radius < 0) {
    throw new Error(`invalid collision radius for master ${mechanics?.unit_master}`);
  }
  return radius;
}


function signedScore(winnerOwner, winnerHp, startingHpByOwner) {
  const start = startingHpByOwner[winnerOwner] ?? startingHpByOwner[String(winnerOwner)];
  const magnitude = 100 * winnerHp / start;
  return winnerOwner === 2 ? -magnitude : magnitude;
}


function aggregateRuns(runs) {
  const metrics = {
    durationSeconds: distribution(runs.map(({ durationSeconds }) => durationSeconds)),
    score: distribution(runs.map(({ score }) => score).filter(Number.isFinite)),
    resolvedRuns: runs.filter(({ score }) => Number.isFinite(score)).length,
    winnerOwners: countBy(runs.map(({ winnerOwner }) => winnerOwner)),
    counts: {},
    overlap: {},
  };
  for (const owner of [2, 3]) {
    metrics.counts[owner] = Object.fromEntries([
      "attackStarts", "attackCanceled", "shotsFired", "hits", "projectileHits",
    ].map((field) => [field, distribution(runs.map((run) => run.counts[owner][field]))]));
  }
  for (const relationship of ["side2", "side3", "enemies"]) {
    metrics.overlap[relationship] = Object.fromEntries([
      "overlapPairShare", "frameOverlapShare", "medianDepth", "p95Depth", "maximumDepth",
      "maximumLocalDegree", "maximumComponentSize", "maximumTriangles",
    ].map((field) => [field, distribution(
      runs.map((run) => run.overlap[relationship][field]).filter(Number.isFinite),
    )]));
  }
  return Object.freeze(metrics);
}


function distribution(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  return Object.freeze({
    count: sorted.length,
    minimum: sorted.length ? sorted[0] : null,
    mean: sorted.length ? sorted.reduce((sum, value) => sum + value, 0) / sorted.length : null,
    median: percentile(sorted, 0.5),
    maximum: sorted.length ? sorted.at(-1) : null,
  });
}


function percentile(sorted, probability) {
  if (!sorted.length) return null;
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] * (upper - index) + sorted[upper] * (index - lower);
}


function countBy(values) {
  const result = {};
  for (const value of values) {
    const key = value === null ? "null" : String(value);
    result[key] = (result[key] ?? 0) + 1;
  }
  return Object.freeze(result);
}


function parseArguments(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      throw new Error(`expected --flag value, got ${flag ?? "end"}`);
    }
    values.set(flag, value);
  }
  const engineRoot = values.get("--engine-root");
  const label = values.get("--label");
  const output = values.get("--output");
  if (!engineRoot || !label || !output) {
    throw new Error("--engine-root, --label, and --output are required");
  }
  const samples = Number(values.get("--samples") ?? 5);
  if (!Number.isSafeInteger(samples) || samples < 1 || samples > 15) {
    throw new RangeError("samples must be from 1 through 15");
  }
  return Object.freeze({
    engineRoot,
    label,
    output: resolve(output),
    samples,
    seed: Number(values.get("--seed") ?? 20260817),
    rowIds: (values.get("--row-ids") ?? DEFAULT_ROWS.join(",")).split(",").filter(Boolean),
  });
}

