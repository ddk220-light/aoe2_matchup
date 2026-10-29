#!/usr/bin/env node
// User-authorized consolidation across engine versions. Never overwrite source campaigns.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync,
  openSync, appendFileSync, fsyncSync, closeSync, renameSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { hashCanonicalJson as digest } from '../src/canonical-json.js';
import { loadFull, hydrate, jobFor, validateRecord, recordFromMessage } from './full-ranking-campaign.mjs';
import { requiredSeeds, summarize } from './ranking-campaign.mjs';
import { RankingWorkerPool } from './ranking-worker-pool.mjs';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const campaigns = resolve(root, 'aoe2x/js_simulation/calibration/campaigns');
const oldDir = resolve(campaigns, 'unit-rankings-full-deduplicated-2026-10-29');
const fixedDir = resolve(campaigns, 'unit-rankings-path-recovery-2026-10-29');
const validationDir = resolve(campaigns, 'path-recovery-final-validation-2026-10-29');
const output = resolve(campaigns, 'unit-rankings-consolidated-2026-10-29');
const supplement = resolve(output, 'supplemental-runs.jsonl');
const decided = new Set(['win', 'loss', 'draw']);
const now = () => new Date().toISOString();
const sha = data => createHash('sha256').update(data).digest('hex');
const read = path => JSON.parse(readFileSync(path, 'utf8'));
const key = row => `${row.matchupId}:${row.seed}`;
const inputs = new Map();
const fingerprint = path => {
  const entry = { path: relative(root, path), sha256: sha(readFileSync(path)) };
  inputs.set(entry.path, entry); return entry;
};
const jsonInput = path => { fingerprint(path); return read(path); };
const atomic = (name, content) => {
  const path = resolve(output, name);
  writeFileSync(path + '.tmp', content); renameSync(path + '.tmp', path);
};
const json = (name, value) => atomic(name, JSON.stringify(value, null, 2) + '\n');
const lines = (name, rows) => atomic(name, rows.map(r => JSON.stringify(r)).join('\n') + (rows.length ? '\n' : ''));
function sourceLines(path) {
  const input = fingerprint(path);
  return readFileSync(path, 'utf8').split('\n').flatMap((line, index) => line.trim() ? [{
    raw: JSON.parse(line), source: { file: input.path, line: index + 1,
      fileSha256: input.sha256, recordSha256: sha(line) },
  }] : []);
}
function campaignRows(directory) {
  return readdirSync(resolve(directory, 'runs')).filter(n => n.endsWith('.jsonl')).sort()
    .flatMap(name => sourceLines(resolve(directory, 'runs', name)));
}
function verifiedManifest(directory) {
  const m = jsonInput(resolve(directory, 'manifest.json'));
  const { campaignHash, ...definition } = m;
  assert.equal(digest(definition), campaignHash, 'manifest hash mismatch');
  return m;
}
const original = verifiedManifest(oldDir), corrected = verifiedManifest(fixedDir);
loadFull(fixedDir); // Checks frozen source files, Node version and simulation environment.
const stop = jsonInput(resolve(fixedDir, 'user-stop.json'));
assert.equal(stop.restartAllowed, false);
assert.equal(jsonInput(resolve(fixedDir, 'progress.json')).status, 'paused');
for (const field of ['roster', 'profiles', 'scenarios', 'matchups', 'phases', 'equivalence',
  'engineConfig', 'simulationEnvironment', 'referenceDbSha256']) {
  assert.equal(digest(original[field]), digest(corrected[field]), `changed campaign inputs: ${field}`);
}
for (const field of ['cap', 'weights', 'countFormula', 'bufferUnits', 'initialSeeds', 'extraSeeds']) {
  assert.equal(digest(original.policy[field]), digest(corrected.policy[field]), `changed policy: ${field}`);
}
const validationManifest = jsonInput(resolve(validationDir, 'manifest.json'));
assert.equal(validationManifest.campaignHash, original.campaignHash);
for (const [name, hash] of Object.entries(validationManifest.sourceHashes)) {
  assert.equal(corrected.runtimeFiles.find(f => f.path === `aoe2x/js_simulation/src/${name}`)?.sha256, hash);
}
const byId = new Map(original.matchups.map(m => [m.id, m]));
const canonical = original.matchups.filter(m => m.id === m.canonicalMatchupId);
const selected = new Map(), replacements = [], sourceStats = {}, originalUnresolved = [];
let sameEngineOverlapChecks = 0;
function accept(row, source, engineVersion, sourceKind, manifest) {
  const m = byId.get(row.matchupId);
  assert(m && m.canonicalMatchupId === m.id, 'only canonical matchup records may be selected');
  validateRecord(manifest, m, row);
  if (!decided.has(row.outcome)) {
    if (sourceKind === 'original_campaign') originalUnresolved.push(key(row));
    return;
  }
  const result = row.result;
  assert(result && result.seed === row.seed);
  assert.equal(row.outcome, result.outcome === 'draw' ? 'draw' : result.winnerOwner === 2 ? 'win' : 'loss');
  assert.equal(result.ticks, row.ticks);
  assert.equal(row.simulationSeconds, row.ticks / 60);
  for (const [i, side, owner, prefix] of [[0, 'side2', 2, 'unit'], [1, 'side3', 3, 'opponent']]) {
    assert.equal(result[side].count, m.counts[i]);
    assert.equal(`${result[side].civ}|${result[side].slug}`, m.teamKeys[i]);
    assert.equal(row[`${prefix}StartingHp`], result.startingHpByOwner[owner]);
    assert.equal(row[`${prefix}RemainingHp`], result.remainingByOwner[owner].hp);
    assert.equal(row[`${prefix}Survivors`], result.remainingByOwner[owner].units);
    assert.equal(row[`${prefix}HpPercent`], 100 * result.remainingByOwner[owner].hp / result.startingHpByOwner[owner]);
  }
  assert.equal(row.finalStateHash, result.finalStateHash);
  assert.equal(row.eventLogHash, result.eventLogHash);
  assert(Number.isFinite(row.wallSeconds) && row.wallSeconds >= 0);
  const previous = selected.get(key(row));
  if (previous) {
    if (previous.selectionProvenance.engineVersion === engineVersion) {
      assert.equal(previous.finalStateHash, row.finalStateHash, 'same-engine state mismatch');
      assert.equal(previous.eventLogHash, row.eventLogHash, 'same-engine event mismatch');
      sameEngineOverlapChecks++;
    }
    replacements.push({ matchupId: row.matchupId, seed: row.seed,
      previousSource: previous.selectionProvenance, replacementSource: { ...source, engineVersion, sourceKind } });
  }
  selected.set(key(row), { ...row, selectionProvenance: { ...source, engineVersion, sourceKind,
    inputCampaignHash: manifest.campaignHash, scenarioHash: m.scenarioHash,
    profileHashes: m.teamKeys.map(k => original.profiles[k].profileHash) } });
}
function consume(rows, sourceKind, engineVersion, manifest, normalize = false) {
  const seen = new Map();
  for (const { raw, source } of rows) {
    assert(!seen.has(key(raw)) || (sourceKind === 'supplemental' && !decided.has(seen.get(key(raw)))),
      `duplicate decided source record: ${sourceKind} ${key(raw)}`);
    seen.set(key(raw), raw.outcome);
    if (normalize) assert.equal(digest(raw.sourceHashes), digest(validationManifest.sourceHashes));
    const row = normalize ? recordFromMessage(corrected, byId.get(raw.matchupId), raw.seed, raw,
      { attempt: null, startedAt: null, finishedAt: null, wallSeconds: raw.wallSeconds }) : raw;
    accept(row, source, engineVersion, sourceKind, manifest);
  }
  sourceStats[sourceKind] = rows.length;
}
consume(campaignRows(oldDir), 'original_campaign', 'original', original);
consume(sourceLines(resolve(validationDir, 'runs.jsonl')), 'corrected_validation', 'corrected', corrected, true);
consume(campaignRows(fixedDir), 'stopped_refresh', 'corrected', corrected);
if (existsSync(supplement)) consume(sourceLines(supplement), 'supplemental', 'corrected', corrected);
function missingJobs() {
  return canonical.flatMap(m => {
    const records = [...Array(10)].flatMap((_, seed) => selected.has(`${m.id}:${seed}`) ? [selected.get(`${m.id}:${seed}`)] : []);
    return requiredSeeds(m, records).filter(seed => !selected.has(`${m.id}:${seed}`)).map(seed => ({ m, seed }));
  });
}
mkdirSync(output, { recursive: true });
let pending = missingJobs();
json('pending.json', pending.map(({ m, seed }) => ({ matchupId: m.id, teamKeys: m.teamKeys, seed })));
console.log(JSON.stringify({ selected: selected.size, pending: pending.length, sourceStats }));
if (pending.length && process.argv.includes('--fill-missing')) {
  // This bounded job only fills actual gaps. Longer work requires a fresh user approval.
  assert(pending.every(({ seed }) => seed >= 3), 'unexpected missing initial seed');
  const timeoutSeconds = Number(process.argv.find(a => a.startsWith('--wall-seconds='))?.split('=')[1] ?? 120);
  assert(Number.isFinite(timeoutSeconds) && timeoutSeconds >= 120);
  const maximumSeconds = Math.ceil(pending.length / 4) * timeoutSeconds + 300;
  assert(maximumSeconds < 3600, 'estimate exceeds one hour: user approval required');
  const plans = existsSync(resolve(output, 'supplement-plan.json')) ? read(resolve(output, 'supplement-plan.json')) : [];
  const history = Array.isArray(plans) ? plans : [plans];
  json('supplement-plan.json', [...history, { createdAt: now(), jobs: pending.map(({ m, seed }) => ({ matchupId: m.id, seed })),
    estimatedTypicalSeconds: Math.ceil(pending.length / 4) * 30, maximumSeconds,
    reason: 'Fill only missing extra seeds triggered by the consolidated initial outcomes.',
    timeoutSeconds, engineCampaignHash: corrected.campaignHash }]);
  let next = 0;
  const pool = new RankingWorkerPool(4, { workerUrl: new URL('./collision-validation-worker.mjs', import.meta.url),
    maxTicks: Number.MAX_SAFE_INTEGER });
  const heartbeat = setInterval(() => json('supplement-progress.json', { updatedAt: now(),
    active: pool.slots.filter(s => s.task).map(s => ({ matchupId: s.task.job.jobId,
      seed: s.task.job.seed, lastProgress: s.task.lastProgress ?? null })) }), 10000);
  try {
    await Promise.all(Array.from({ length: 4 }, async () => {
      while (next < pending.length) {
        const { m, seed } = pending[next++], startedAt = now(), start = performance.now();
        const message = await pool.run(jobFor(corrected, m, seed), timeoutSeconds);
        const row = recordFromMessage(corrected, m, seed, message,
          { attempt: null, startedAt, finishedAt: now(), wallSeconds: (performance.now() - start) / 1000 });
        const fd = openSync(supplement, 'a');
        try { appendFileSync(fd, JSON.stringify(row) + '\n'); fsyncSync(fd); } finally { closeSync(fd); }
        console.log(JSON.stringify({ supplementalSaved: key(row), outcome: row.outcome, wallSeconds: row.wallSeconds }));
      }
    }));
  } finally { clearInterval(heartbeat); await pool.close(); }
  // Read back durable records and check them using the same source/provenance path.
  for (const [id, row] of selected) {
    if (row.selectionProvenance.sourceKind === 'supplemental') selected.delete(id);
  }
  consume(sourceLines(supplement), 'supplemental', 'corrected', corrected);
  pending = missingJobs();
  json('pending.json', pending.map(({ m, seed }) => ({ matchupId: m.id, teamKeys: m.teamKeys, seed })));
}
assert.equal(pending.length, 0, 'required seeds remain; no completed table will be published');
json('supplement-progress.json', { updatedAt: now(), status: 'complete', active: [], pending: 0 });
if (existsSync(resolve(output, 'supplement-plan.json'))) jsonInput(resolve(output, 'supplement-plan.json'));
const used = [], additional = [], byCanonical = new Map();
for (const m of canonical) {
  const records = [...selected.values()].filter(r => r.matchupId === m.id).sort((a, b) => a.seed - b.seed);
  const required = new Set(requiredSeeds(m, records));
  byCanonical.set(m.id, records.filter(r => required.has(r.seed)));
  for (const row of records) (required.has(row.seed) ? used : additional).push(row);
  assert.equal(byCanonical.get(m.id).length, required.size);
}
const countBy = (rows, field) => rows.reduce((counts, row) => {
  const value = row.selectionProvenance[field]; counts[value] = (counts[value] ?? 0) + 1; return counts;
}, {});
const table = original.matchups.map(m => {
  const rows = byCanonical.get(m.canonicalMatchupId);
  const versions = [...new Set(rows.map(r => r.selectionProvenance.engineVersion))].sort();
  return { phase: m.phase, civilization: m.civilization, slug: m.slug, opponentKey: m.opponent,
    simulationSourceMatchupId: m.canonicalMatchupId, sharedEquivalentResults: m.id !== m.canonicalMatchupId,
    ...summarize({ matchups: [hydrate(original, m)] }, rows.map(r => ({ ...r, matchupId: m.id })))[0],
    engineVersions: versions.join(';'), mixedEngineVersions: versions.length > 1,
    originalEngineRuns: rows.filter(r => r.selectionProvenance.engineVersion === 'original').length,
    correctedEngineRuns: rows.filter(r => r.selectionProvenance.engineVersion === 'corrected').length,
  };
});
assert.equal(table.length, 3591); assert.equal(canonical.length, 2398);
const rosterKeys = new Set(original.roster.units.map(u => `${u.civilization}|${u.slug}`));
assert.equal(rosterKeys.size, 555);
assert.deepEqual(new Set(table.map(r => `${r.civilization}|${r.slug}`)), rosterKeys);
assert(table.every(r => r.state === 'complete' && r.recordedRuns === r.requiredRuns && r.undecided === 0));
assert.equal(new Set(used.map(key)).size, used.length);
assert(originalUnresolved.every(k => selected.has(k)), 'an original failure still lacks a decided replacement');
for (const input of inputs.values()) assert.equal(sha(readFileSync(resolve(root, input.path))), input.sha256, 'source changed during consolidation');
loadFull(fixedDir);
const phases = original.phases.map(p => ({ phase: p.id, status: 'passed',
  tableRows: table.filter(r => r.phase === p.id).length,
  distinctMatchups: canonical.filter(m => m.phase === p.id).length,
  missing: 0, unresolved: 0, check: 'consolidated seed, identity, provenance and coverage checks; no new combat replay' }));
json('summary.json', table);
const columns = Object.keys(table[0]);
const cell = value => value == null ? '' : `"${String(value).replaceAll('"', '""')}"`;
atomic('summary.csv', columns.join(',') + '\n' + table.map(row => columns.map(k => cell(row[k])).join(',')).join('\n') + '\n');
lines('runs.jsonl', used); lines('additional-recorded-runs.jsonl', additional);
json('replacements.json', replacements); json('undecided.json', []);
const validation = { completedAt: now(), status: 'complete', validationScope: 'data consolidation, not single-engine equivalence',
  civilizationUnitVariants: rosterKeys.size, civilizations: original.roster.civilizations,
  distinctMechanicsProfiles: original.equivalence.distinctUnitProfiles, distinctMatchups: canonical.length,
  tableRows: table.length, requiredRuns: used.length, recordedRuns: used.length,
  additionalRecordedRuns: additional.length, totalUniqueSavedResults: selected.size,
  pendingRuns: 0, unresolvedErrorsOrTimeouts: 0, duplicateSelectedRuns: 0,
  repairedOriginalFailures: originalUnresolved.length, sameEngineOverlapChecks,
  includedSourceCounts: countBy(used, 'sourceKind'), includedEngineCounts: countBy(used, 'engineVersion'),
  allSavedSourceCounts: countBy([...selected.values()], 'sourceKind'),
  mixedEngineTableRows: table.filter(r => r.mixedEngineVersions).length,
  checks: { manifestHashes: 'passed', unchangedMatrixProfilesCountsScenarios: 'passed',
    currentSourceHashesAndEnvironment: 'passed', perRunRawResultAndProvenance: 'passed',
    exactRequiredSeedSets: 'passed', allRosterAndOpponentRows: 'passed', sourceFilesUnchanged: 'passed' }, phases };
json('validation.json', validation);
const supplementalAttempts = existsSync(supplement) ? sourceLines(supplement).map(({ raw }) => raw) : [];
const definition = { schemaVersion: 1, datasetName: 'unit-rankings-consolidated-2026-10-29',
  datasetKind: 'user-authorized-mixed-engine-consolidation', completedAt: validation.completedAt,
  authorization: '2026-10-29: stop full refresh, reuse old results and combine everything into one completed table. Ask before work estimated over one hour.',
  selectionPolicy: ['Decided results only; one selected result per canonical matchup and seed.',
    'Prefer corrected-engine stopped-refresh results, then corrected-engine validation, then original results.',
    'Fill only absent required seeds on the frozen corrected engine.',
    'Reevaluate seeds 0..2; include 3..9 only if their selected decided outcomes differ.',
    'Preserve already-recorded extra seeds separately when no longer required; exclude them from table averages.'],
  scoring: 'deferred', physicsChangedDuringConsolidation: false,
  supplementalExecution: { planPath: 'supplement-plan.json', journalPath: 'supplemental-runs.jsonl',
    totalAttempts: supplementalAttempts.length,
    decidedRuns: supplementalAttempts.filter(r => decided.has(r.outcome)).length,
    preservedFailedAttempts: supplementalAttempts.filter(r => !decided.has(r.outcome)).map(r => ({ matchupId: r.matchupId,
      seed: r.seed, outcome: r.outcome, reason: r.reason, wallSeconds: r.wallSeconds, simulationSeconds: r.simulationSeconds })),
    maxDecidedWallSeconds: Math.max(0, ...supplementalAttempts.filter(r => decided.has(r.outcome)).map(r => r.wallSeconds)),
    note: 'Only missing required seeds were simulated. Failed attempts remain in the journal; longer processing limits are recorded in the plan. Stop controls do not change combat physics.' },
  roster: original.roster, matchups: original.matchups, equivalence: original.equivalence,
  policy: { ...original.policy, sourceMixing: 'explicitly authorized; per-run and per-row engine provenance retained' },
  engineVersions: Object.fromEntries([['original', original, oldDir], ['corrected', corrected, fixedDir]].map(([name, m, directory]) =>
    [name, { campaignHash: m.campaignHash, manifestPath: relative(root, resolve(directory, 'manifest.json')),
      sourceCommit: m.sourceCommit, runtimeFiles: m.runtimeFiles, nodeVersion: m.nodeVersion,
      simulationEnvironment: m.simulationEnvironment, engineConfig: m.engineConfig }])),
  sources: [...inputs.values()], generator: fingerprint(fileURLToPath(import.meta.url)),
  outputs: ['summary.json', 'summary.csv', 'runs.jsonl', 'additional-recorded-runs.jsonl', 'replacements.json',
    'validation.json', 'undecided.json', 'pending.json'].map(name => ({ path: name, sha256: sha(readFileSync(resolve(output, name))) })),
};
json('manifest.json', { ...definition, datasetHash: digest(definition) });
atomic('README.md', `# Consolidated unit-ranking results\n\nComplete: **${table.length} opponent rows for ${rosterKeys.size} civilization/unit variants**, covering ${canonical.length} distinct matchups and ${used.length} required decided runs. No pending seeds, unresolved errors or timeouts. Scoring remains deferred.\n\n`
  + `The owner stopped the full recomputation and explicitly requested reuse of old results with completed corrected-engine results. **This dataset combines two engine versions.** It is complete under that requested consolidation policy; it is not a uniformly rerun corrected-engine benchmark. Each run identifies its source file, line, record/file hashes, input campaign and engine version; each table row identifies the versions contributing to its averages. Original campaigns are preserved.\n\n`
  + `- [Final table (CSV)](summary.csv) and [JSON](summary.json)\n- [Every included run](runs.jsonl)\n- [Validation and coverage](validation.json) and [independent audit](independent-validation.json)\n- [Manifest and source fingerprints](manifest.json)\n- [Superseded result references](replacements.json)\n- [Additional already-recorded seeds](additional-recorded-runs.jsonl)\n\n`
  + `Included sources: ${JSON.stringify(validation.includedSourceCounts)}. All 107 originally unresolved cases have decided replacements. ${additional.length} existing extra-seed results are retained separately because their selected initial outcomes no longer trigger expansion; averages use exactly the required 3 or 10 seeds. New supplemental simulations fill only gaps created by the expansion rule.\n\n`
  + `The 27-unit weighted-cost balance, zero buffers, opponent pools and exact mechanics-profile sharing are unchanged. The full refresh and scheduled check are stopped. Any future work estimated above one hour requires prior user approval.\n\n`
  + `Rebuild from saved inputs without simulations:\n\n\`\`\`bash\nnode aoe2x/js_simulation/node/consolidate-ranking-results.mjs\n\`\`\`\n`);
console.log(JSON.stringify(validation));
