// One separately budgeted diagnostic run. Called only after the bulk campaign.
import { readFileSync, writeFileSync, renameSync, appendFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { Session } from 'node:inspector/promises';

const specification = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const output = resolve(specification.output);
mkdirSync(output, { recursive: true });
const atomic = (name, value) => {
  const path = resolve(output, name);
  writeFileSync(`${path}.tmp`, JSON.stringify(value));
  renameSync(`${path}.tmp`, path);
};
const started = performance.now(), cpuStart = process.cpuUsage();
let stepStarted = started, lastPublished = -Infinity, lastSampleTick = -Infinity;
let latest = null, lastWorld = null, lastCombatTick = 0, lastMovementTick = 0;
let lastTotals = null, stepMilliseconds = [], maxStep = { tick: 0, milliseconds: 0 };
let budgetReached = false;
const eventCounts = {};
const elapsed = () => (performance.now() - started) / 1000;
function observe(world, force = false) {
  lastWorld = world;
  if (world.tick > 0 && !force) {
    const duration = performance.now() - stepStarted;
    stepMilliseconds.push(duration);
    if (duration > maxStep.milliseconds) maxStep = { tick: world.tick, milliseconds: duration };
    for (const event of world.events ?? []) eventCounts[event.type] = (eventCounts[event.type] ?? 0) + 1;
  }
  const wallSeconds = elapsed();
  if (!force && wallSeconds - lastPublished < 1 && world.tick - lastSampleTick < 300) return;
  const live = world.units.filter(unit => unit.alive);
  const totals = {};
  for (const unit of live) {
    totals[unit.owner] ??= { units: 0, hp: 0 };
    totals[unit.owner].units++; totals[unit.owner].hp += unit.hp;
  }
  const signature = JSON.stringify(totals);
  if (signature !== lastTotals) { lastCombatTick = world.tick; lastTotals = signature; }
  const positions = live.map(unit => [unit.referenceId, unit.x, unit.y]);
  if (!latest || JSON.stringify(positions) !== JSON.stringify(latest.positions)) lastMovementTick = world.tick;
  const cpu = process.cpuUsage(cpuStart);
  latest = {
    tick: world.tick, simulationSeconds: world.tick / 60, wallSeconds,
    cpuSeconds: (cpu.user + cpu.system) / 1e6, remainingByOwner: totals,
    gameSecondsSinceHpOrSurvivorChange: (world.tick - lastCombatTick) / 60,
    gameSecondsSincePositionChange: (world.tick - lastMovementTick) / 60,
    projectileCount: world.projectiles?.length ?? 0, eventCounts: { ...eventCounts },
    maxStep: { ...maxStep }, positions,
    units: live.map(unit => ({ id: unit.referenceId, owner: unit.owner,
      x: unit.x, y: unit.y, hp: unit.hp, action: unit.action,
      pursuitTargetId: unit.pursuitTargetId, engagedTargetId: unit.engagedTargetId,
      attackTargetId: unit.attackTargetId, actionTimers: unit.actionTimers,
      minRange: unit.mechanics.ranged?.min_range_tiles ?? 0,
      range: unit.mechanics.attack_range_tiles, speed: unit.mechanics.speed_tiles_per_second })),
  };
  atomic('heartbeat.json', latest);
  appendFileSync(resolve(output, 'timeline.jsonl'), `${JSON.stringify(latest)}\n`);
  lastPublished = wallSeconds; lastSampleTick = world.tick;
}
globalThis.__rankingDiagnostic = {
  maxTicks: specification.removeGameCap ? Number.MAX_SAFE_INTEGER : 9000,
  beforeStep() { stepStarted = performance.now(); },
  observe,
  stopRequested() {
    budgetReached = elapsed() >= specification.wallSeconds;
    return budgetReached;
  },
};

const session = new Session(); session.connect();
await session.post('Profiler.enable');
await session.post('Profiler.setSamplingInterval', { interval: 5000 });
await session.post('Profiler.start');
let result = null, error = null;
try {
  const { runHeadlessJob } = await import(pathToFileURL(resolve(specification.runtime,
    'aoe2x/js_simulation/node/run-job.mjs')).href);
  result = await runHeadlessJob(specification.job);
} catch (caught) {
  error = { name: caught.name, message: caught.message, stack: caught.stack };
} finally {
  if (lastWorld) observe(lastWorld, true);
}
const { profile } = await session.post('Profiler.stop');
session.disconnect();
atomic('cpu.cpuprofile', profile);
const nodes = new Map(profile.nodes.map(node => [node.id, node]));
const totals = new Map();
for (let index = 0; index < (profile.samples ?? []).length; index++) {
  const node = nodes.get(profile.samples[index]); if (!node) continue;
  const frame = node.callFrame;
  const key = `${frame.functionName || '(anonymous)'} ${frame.url}:${frame.lineNumber + 1}`;
  totals.set(key, (totals.get(key) ?? 0) + (profile.timeDeltas?.[index] ?? 0));
}
const sampledUs = [...totals.values()].reduce((a, b) => a + b, 0);
const hotFunctions = [...totals].sort((a, b) => b[1] - a[1]).slice(0, 20)
  .map(([frame, microseconds]) => ({ frame: frame.replaceAll(specification.runtime, '<runtime>'),
    sampledSeconds: microseconds / 1e6, percent: sampledUs ? microseconds * 100 / sampledUs : 0 }));
stepMilliseconds.sort((a, b) => a - b);
const percentile = q => stepMilliseconds[Math.floor((stepMilliseconds.length - 1) * q)] ?? null;
atomic('result.json', {
  task: specification.task, matchupId: specification.job.jobId, seed: specification.job.seed,
  teams: specification.job.teams.map(team => `${team.mechanics.civilization} ${team.mechanics.unit_name}`),
  removeGameCap: specification.removeGameCap, nominalWallLimitSeconds: specification.wallSeconds,
  processingWallSeconds: elapsed(), cpuSeconds: latest?.cpuSeconds ?? null,
  stopReason: error ? 'engine_error' : budgetReached ? 'processing_limit'
    : result?.outcome === 'timeout' ? 'game_time_limit' : 'decided',
  result, error, lastProgress: latest, hotFunctions,
  tickMilliseconds: { p50: percentile(.5), p95: percentile(.95), p99: percentile(.99), max: maxStep },
  notes: 'Diagnostic tracing and CPU profiling add overhead. HP/position inactivity is sampled, not a proof of deadlock.',
});
