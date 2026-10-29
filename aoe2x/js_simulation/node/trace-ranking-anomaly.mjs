// Read-only instrumentation for contact handoffs and stalled attack positions.
import { registerHooks } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync, appendFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';

const [campaign, matchupId, seedText, outputPath, wallText = '120'] = process.argv.slice(2);
const output = resolve(outputPath); mkdirSync(output, { recursive: true });
const manifest = JSON.parse(readFileSync(resolve(campaign, 'manifest.json')));
const matchup = manifest.matchups.find(row => row.id === matchupId);
if (!matchup) throw new Error('unknown matchup');
const started = performance.now();
globalThis.__anomalyDeadline = started + Number(wallText) * 1000;
let lastSample = -Infinity, lastWorld, lastContacts;
const contacts = [];
const serializable = value => JSON.stringify(value, (_, item) => item instanceof Map
  ? { mapEntries: [...item] } : item instanceof Set ? { setValues: [...item] } : item);
globalThis.__anomalyContacts = input => {
  lastContacts = input;
  const key = '9006:9010';
  if (input.tick < 828) return;
  contacts.push({ tick: input.tick,
    units: input.units.filter(unit => [9006, 9010].includes(unit.referenceId)),
    proposals: input.proposals.filter(unit => [9006, 9010].includes(unit.referenceId)),
    previousReservation: input.state?.reservations.get(key) ?? null,
    previousInheritedExtent: input.state?.inheritedExtents.get(key) ?? null,
    previousFormationPair: input.state?.formationPairs?.get(key) ?? null,
    externalReservation: input.externalReservations.get(key) ?? null });
  if (contacts.length > 12) contacts.shift();
};
globalThis.__anomalyObserve = world => {
  lastWorld = world;
  if (performance.now() - lastSample < 1000) return;
  lastSample = performance.now();
  const totals = {};
  for (const unit of world.units.filter(unit => unit.alive)) {
    totals[unit.owner] ??= { count: 0, hp: 0 };
    totals[unit.owner].count++; totals[unit.owner].hp += unit.hp;
  }
  appendFileSync(resolve(output, 'timeline.jsonl'), JSON.stringify({ tick: world.tick,
    gameSeconds: world.tick / 60, wallSeconds: (performance.now() - started) / 1000,
    totals, units: world.units.filter(unit => unit.alive).map(unit => ({
      id: unit.referenceId, owner: unit.owner, x: unit.x, y: unit.y, hp: unit.hp,
      action: unit.action, pursuitTargetId: unit.pursuitTargetId,
      engagedTargetId: unit.engagedTargetId, attackTargetId: unit.attackTargetId,
      actionTimers: unit.actionTimers,
    })) }) + '\n');
};
registerHooks({ load(url, context, nextLoad) {
  const result = nextLoad(url, context);
  let source = String(result.source);
  if (url.endsWith('/src/fight.js')) {
    source = source.replace('maxTicks: MAX_TICKS,', 'maxTicks: Number.MAX_SAFE_INTEGER,');
  } else if (url.endsWith('/src/combat/world.js')) {
    source = source.replace('const MAX_WORLD_TICKS = 9000;', 'const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;')
      .replace('  const publish = (current) => {',
        '  const publish = (current) => {\n    globalThis.__anomalyObserve(current);')
      .replaceAll('elapsed < maxTicks;', 'elapsed < maxTicks && performance.now() < globalThis.__anomalyDeadline;')
      .replace('  const contactUpdate = contactReservationState',
        `  globalThis.__anomalyContacts({ state: contactReservationState, units: live,
    proposals, tick, externalReservations: rangedCrowdPlan.contactReservations,
    inheritedOverlapReferenceIds: allowedStartingOverlapReferenceIds });
  const contactUpdate = contactReservationState`);
  } else return result;
  return { ...result, source };
} });
const { jobFor } = await import('./full-ranking-campaign.mjs');
const { runHeadlessJob } = await import('./run-job.mjs');
let result = null, error = null;
try { result = await runHeadlessJob(jobFor(manifest, matchup, Number(seedText))); }
catch (caught) { error = { name: caught.name, message: caught.message, stack: caught.stack }; }
if (error && lastContacts) writeFileSync(resolve(output, 'contact-input.json'), serializable(lastContacts) + '\n');
if (error) writeFileSync(resolve(output, 'contact-history.json'), serializable(contacts) + '\n');
const sourceHashes = Object.fromEntries(['world.js', 'contact-reservations.js', 'collision.js'].map(name =>
  [name, createHash('sha256').update(readFileSync(new URL('../src/combat/' + name, import.meta.url))).digest('hex')]));
const record = { matchupId, seed: Number(seedText), sourceHashes,
  wallSeconds: (performance.now() - started) / 1000, tick: lastWorld?.tick,
  gameSeconds: lastWorld?.tick / 60, result, error };
writeFileSync(resolve(output, 'result.json'), JSON.stringify(record, null, 2) + '\n');
console.log(JSON.stringify({ ...record, result: result && { outcome: result.outcome, ticks: result.ticks } }));
