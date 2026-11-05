// Read-only analysis of existing results. Does not import or execute combat.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const base = resolve(here, '../../campaigns/unit-rankings-consolidated-2026-10-29');
const inputs = ['runs.jsonl', 'additional-recorded-runs.jsonl'];
const sourceFiles = [];
const groups = new Map();
const increment = (counts, key) => { counts[key] = (counts[key] ?? 0) + 1; };
const engineCounts = {};
for (const file of inputs) {
  const raw = readFileSync(resolve(base, file));
  const rows = raw.toString('utf8').trim().split('\n').map(JSON.parse);
  sourceFiles.push({ file, rows: rows.length, sha256: createHash('sha256').update(raw).digest('hex') });
  for (const row of rows) {
    assert.equal(row.error, null);
    assert(['win', 'loss', 'draw'].includes(row.outcome));
    const provenance = row.selectionProvenance;
    increment(engineCounts, provenance.engineVersion);
    if (!groups.has(row.matchupId)) groups.set(row.matchupId, []);
    groups.get(row.matchupId).push({ row, file });
  }
}

const correctedGroups = [];
const qualityCounts = {};
const selectedVersionCounts = {};
for (const [matchupId, entries] of groups) {
  const selected = entries.filter(e => e.file === 'runs.jsonl').map(e => e.row);
  const versions = new Set(selected.map(r => r.selectionProvenance.engineVersion));
  increment(selectedVersionCounts, versions.size === 1 ? [...versions][0] : 'mixed');
  const corrected = entries.filter(e => e.row.selectionProvenance.engineVersion === 'corrected').map(e => e.row);
  if (!corrected.length) { increment(qualityCounts, 'no_corrected_records'); continue; }
  // Distinct engine/input contexts cannot be merged just because the matchup ID matches.
  const contexts = new Set(corrected.map(r => JSON.stringify({
    campaign: r.selectionProvenance.inputCampaignHash,
    profiles: r.selectionProvenance.profileHashes,
    scenario: r.selectionProvenance.scenarioHash,
    counts: [r.unitCount, r.opponentCount],
  })));
  assert.equal(contexts.size, 1, `multiple corrected contexts for ${matchupId}`);
  const seeds = new Map();
  for (const r of corrected) {
    assert(!seeds.has(r.seed), `duplicate corrected seed for ${matchupId}:${r.seed}`);
    seeds.set(r.seed, r.outcome);
  }
  const initialComplete = [0, 1, 2].every(s => seeds.has(s));
  const tenComplete = Array.from({ length: 10 }, (_, i) => i).every(s => seeds.has(s));
  const outcomesVary = new Set(seeds.values()).size > 1;
  const status = !initialComplete ? 'incomplete_initial_seeds'
    : !outcomesVary ? 'complete_initial_unanimous_all_available_seeds'
      : tenComplete ? 'complete_ten_seed_sensitive' : 'seed_sensitive_incomplete_extension';
  increment(qualityCounts, status);
  correctedGroups.push({ matchupId, status, seeds: [...seeds.entries()].sort((a, b) => a[0] - b[0]) });
}
assert.equal(groups.size, 2398);
const result = {
  scope: 'Offline evidence inventory for the phase-one implementation plan; not an outcome table or anchor certification',
  sourceFiles, selectedVersionCounts, allAvailableEngineRecordCounts: engineCounts,
  canonicalGroups: groups.size, correctedEvidenceQuality: qualityCounts,
  correctedGroups,
  notes: [
    'Includes all 77 preserved extra records, not only the 7600 selected ranking runs.',
    '183 groups have complete corrected initial seed sets with unanimous initial results; one has contradictory extra corrected seeds, leaving 182 unanimous across all available corrected seeds.',
    'These are source-group counts, not counts of eligible distinct cross-civilization pairs.',
    'Complete source seeds do not certify new scenario/orientation compatibility or a transfer rule.',
    'Partial or original-engine evidence is retained as prior evidence, never silently promoted to a corrected-engine result.',
  ],
  newSimulationsRun: 0,
};
writeFileSync(resolve(here, 'source-evidence-audit.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ ...result, correctedGroups: `${correctedGroups.length} entries in output file` }, null, 2));
