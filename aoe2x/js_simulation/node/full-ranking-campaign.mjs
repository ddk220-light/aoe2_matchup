#!/usr/bin/env node
// Durable, phased collection using the frozen V3 engine. No ranking formula.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync, openSync,
  closeSync, fsyncSync, appendFileSync, unlinkSync, renameSync } from "node:fs";
import { resolve, dirname, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawn, execFileSync } from "node:child_process";
import { DatabaseSync } from "node:sqlite";
import { hashCanonicalJson as digest } from "../src/canonical-json.js";
import { unitDescriptorFromMechanics, validateMechanicsProfile } from "../src/mechanics-schema.js";
import { loadLabScenario } from "../src/lab-scenario.js";
import { deriveRecordedBattleSetup } from "../src/battle-setup.js";
import { atomicJson, loadCampaign, openCampaignDb, storedRuns, saveRun, requiredSeeds,
  summarize } from "./ranking-campaign.mjs";
import { RankingWorkerPool } from "./ranking-worker-pool.mjs";
import { assignEquivalence } from "./ranking-equivalence.mjs";

const SIM = fileURLToPath(new URL("../", import.meta.url));
const ROOT = resolve(SIM, "../..");
const now = () => new Date().toISOString();
const sha = value => createHash("sha256").update(value).digest("hex");
function currentCommit() {
  return execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
}
const DECIDED = new Set(["win", "loss", "draw"]);
export const OPPONENTS = {
  champion: ["Spanish", "champion"], hussar: ["Spanish", "hussar"],
  arbalester: ["Chinese", "arbalester"], paladin: ["Spanish", "paladin"],
  cavalier: ["Turks", "paladin"], halberdier: ["Spanish", "halberdier"],
  camel: ["Turks", "heavy_camel"], hca: ["Saracens", "heavy_cav_archer"],
  hand_cannoneer: ["Saracens", "hand_cannoneer"], skirmisher: ["Spanish", "imp_elite_skirm"],
};
export const POOLS = {
  Infantry: ["champion", "hussar", "arbalester", "paladin", "cavalier"],
  Ranged: ["champion", "arbalester", "cavalier", "hca", "hand_cannoneer", "hussar", "skirmisher"],
  Cavalry: ["champion", "arbalester", "paladin", "halberdier", "camel", "cavalier", "hca"],
};
const EARLY = [
  ["Jurchens", "elite_iron_pagoda_jurchens", "champion"],
  ["Khitans", "hussar", "champion"],
  ["Varangians", "elite_varangian_guard", "arbalester"],
  ["Saxons", "elite_hearth_troop_saxons", "arbalester"],
  ["Varangians", "elite_jarl_varangians", "hussar"],
  ["Danes", "elite_jomsviking_danes", "champion"],
  ["Georgians", "elite_monaspa_georgians", "paladin"],
  ["Gurjaras", "elite_shrivamsha_rider_gurjaras", "hca"],
  ["Shu", "war_chariot_shu", "cavalier"],
  ["Khitans", "mounted_trebuchet_khitans", "champion"],
  ["Tatars", "elite_keshik_tatars", "halberdier"],
  ["Khitans", "elite_liao_dao_khitans", "champion"],
  ["Wei", "elite_tiger_cavalry_wei", "camel"],
  ["Muisca", "elite_guecha_warrior_muisca", "arbalester"],
  ["Tupi", "elite_blackwood_archer_tupi", "hussar"],
  ["Bengalis", "elite_ele_archer", "hussar"],
  ["Mapuche", "elite_bolas_rider_mapuche", "hussar"],
  ["Chinese", "heavy_scorpion", "champion"],
];
function atomicText(path, text) {
  mkdirSync(dirname(path), { recursive: true });
  const fd = openSync(`${path}.tmp`, "w");
  try { writeFileSync(fd, text); fsyncSync(fd); } finally { closeSync(fd); }
  renameSync(`${path}.tmp`, path);
}
function appendJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const fd = openSync(path, "a");
  try { appendFileSync(fd, `${JSON.stringify(value)}\n`); fsyncSync(fd); } finally { closeSync(fd); }
}
function readLines(path) {
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n");
  return lines.flatMap((line, i) => {
    if (!line) return [];
    try { return [JSON.parse(line)]; }
    catch (error) { if (i === lines.length - 1 && !text.endsWith("\n")) return []; throw error; }
  });
}
function csv(rows, columns) {
  return `${columns.join(",")}\n${rows.map(r => columns.map(k => r[k] == null ? ""
    : `"${String(r[k]).replaceAll('"', '""')}"`).join(",")).join("\n")}\n`;
}
export function hydrate(manifest, m) {
  return { ...m, scenario: manifest.scenarios[m.scenarioHash], teams: m.teamKeys.map((key, i) => ({
    ...manifest.profiles[key], count: m.counts[i], weightedCost: m.weightedCosts[i],
  })) };
}
export function jobFor(manifest, m, seed) {
  const matchup = hydrate(manifest, m);
  return { jobId: m.id, seed, teams: matchup.teams.map(({ mechanics, count }) => ({ mechanics, count })),
    scenario: matchup.scenario, disableAiOrders: true, disableKiting: true,
    preserveOwnerOrientation: true, retainSnapshots: false };
}
export async function prepareFull(directory, rosterPath, pilotDirectory, referenceDb, reuseDirectory = null) {
  if (existsSync(resolve(directory, "manifest.json"))) throw new Error("campaign exists; resume it");
  const pilot = loadCampaign(pilotDirectory);
  if (sha(readFileSync(referenceDb)) !== pilot.referenceDbSha256) throw new Error("reference changed since pilot");
  const roster = JSON.parse(readFileSync(rosterPath, "utf8"));
  const benchmark = JSON.parse(readFileSync("/tmp/ranking-pool-benchmark.json", "utf8"));
  if (!benchmark.allExact || benchmark.jobs !== 10) throw new Error("persistent-worker parity must pass first");
  const equivalenceVerification = JSON.parse(readFileSync("/tmp/ranking-equivalence-verification.json", "utf8"));
  if (!equivalenceVerification.allExact || equivalenceVerification.pairs !== 5) throw new Error("cross-civilization equivalence checks must pass");
  const db = new DatabaseSync(referenceDb, { readOnly: true });
  const query = db.prepare(`SELECT u.id,u.final_cost_food,u.final_cost_wood,u.final_cost_gold,
    m.mechanics_json,m.mechanics_hash,m.source_build FROM ref_units u
    JOIN ref_unit_mechanics m ON m.ref_unit_id=u.id
    WHERE u.civ_name=? AND u.unit_slug=? AND u.age='Imperial' AND m.is_default=1`);
  const profiles = {}, scenarios = {}, matchups = [];
  const team = (civ, slug) => {
    const key = `${civ}|${slug}`;
    if (profiles[key]) return key;
    const rows = query.all(civ, slug);
    if (rows.length !== 1) throw new Error(`missing/ambiguous ${key}`);
    const r = rows[0], mechanics = validateMechanicsProfile(JSON.parse(r.mechanics_json));
    profiles[key] = { mechanics, profileHash: digest(mechanics), referenceId: r.id,
    sourceBuild: r.source_build, storedMechanicsHash: r.mechanics_hash,
      referencePurchaseCost: { food: r.final_cost_food, wood: r.final_cost_wood, gold: r.final_cost_gold } };
    return key;
  };
  try {
    for (const unit of roster.units) {
      for (const opponent of POOLS[unit.group]) {
        const teamKeys = [team(unit.civilization, unit.slug), team(...OPPONENTS[opponent])];
        const mechanics = teamKeys.map(k => profiles[k].mechanics);
        const descriptors = mechanics.map(unitDescriptorFromMechanics);
        const setup = deriveRecordedBattleSetup(...descriptors.map((d, i) => ({ ...d, effectiveCost: mechanics[i].cost })), { cap: 27 });
        const scenario = await loadLabScenario(pathToFileURL(`${SIM}/`), ...descriptors, { includeBuffer: false });
        if (Object.keys(scenario.auxiliaryArmiesByOwner ?? {}).length) throw new Error("unexpected buffer army");
        const scenarioHash = digest(scenario);
        scenarios[scenarioHash] = scenario;
        matchups.push({ id: `m_${digest([teamKeys, scenarioHash]).slice(0, 20)}`, group: unit.group,
          line: unit.line, civilization: unit.civilization, slug: unit.slug, opponent,
          teamKeys, counts: [setup.n2, setup.n3], weightedCosts: [setup.cost2, setup.cost3], scenarioHash });
      }
    }
  } finally { db.close(); }
  const preferredIds = pilot.matchups.map(old => matchups.find(m => digest(m.teamKeys)
    === digest(old.teams.map(t => `${t.mechanics.civilization}|${t.mechanics.unit_slug}`)))?.id).filter(Boolean);
  let reuseCampaign = null;
  if (reuseDirectory) {
    const previous = JSON.parse(readFileSync(resolve(reuseDirectory, "manifest.json"), "utf8"));
    reuseCampaign = { directory: relative(ROOT, reuseDirectory), campaignHash: previous.campaignHash };
    for (const name of readdirSync(resolve(reuseDirectory, "runs")).filter(n => n.endsWith(".jsonl"))) {
      for (const row of readLines(resolve(reuseDirectory, "runs", name))) preferredIds.push(row.matchupId);
    }
  }
  const equivalence = assignEquivalence({ profiles, matchups }, [...new Set(preferredIds)]);
  const canonicalMatchups = matchups.filter(m => m.canonicalMatchupId === m.id);
  const phases = [];
  const early = EARLY.map(([civ, slug, opponent]) => {
    const found = matchups.find(m => m.civilization === civ && m.slug === slug && m.opponent === opponent);
    if (!found) throw new Error(`missing validation matchup: ${civ}/${slug}/${opponent}`);
    return canonicalMatchups.find(m => m.id === found.canonicalMatchupId);
  });
  const assign = (label, items) => {
    const id = `${String(phases.length + 1).padStart(2, "0")}-${label}`;
    items.forEach(m => { m.phase = id; });
    phases.push({ id, label, matchupIds: items.map(m => m.id), minimumRuns: items.length * 3 });
  };
  assign("mechanics-validation", [...new Map(early.map(m => [m.id, m])).values()]);
  for (const group of ["Infantry", "Ranged", "Cavalry"]) {
    const remaining = canonicalMatchups.filter(m => m.group === group && !m.phase);
    for (let i = 0; i < remaining.length; i += 120) assign(`${group.toLowerCase()}-${Math.floor(i / 120) + 1}`, remaining.slice(i, i + 120));
  }
  for (const m of matchups) m.phase = canonicalMatchups.find(c => c.id === m.canonicalMatchupId).phase;
  const extraFiles = ["node/full-ranking-campaign.mjs", "node/ranking-worker-pool.mjs", "node/ranking-pool-worker.mjs",
    "node/ranking-equivalence.mjs",
    "tools/export_ranking_roster.py"].map(p => ({ path: relative(ROOT, resolve(SIM, p)), sha256: sha(readFileSync(resolve(SIM, p))) }));
  const definition = { schemaVersion: 3, campaignName: "unit-rankings-full-deduplicated-2026-10-29", createdAt: now(),
    scope: roster.scope, sourceCommit: currentCommit(), engineBaseCommit: "58e480b76c9382b699fcea1980e63a81ef8da70d",
    nodeVersion: process.version, runtimeFiles: [...pilot.runtimeFiles, ...extraFiles],
    simulationEnvironment: pilot.simulationEnvironment, engineConfig: pilot.engineConfig,
    referenceDb: relative(ROOT, referenceDb), referenceDbSha256: pilot.referenceDbSha256,
    pilotDirectory: relative(ROOT, pilotDirectory), pilotCampaignHash: pilot.campaignHash,
    policy: { ...pilot.policy, workers: 4, chunkMatchups: 120,
      playbackPolicy: "results and replay inputs for every run; no per-tick animation export", phasesAdvanceAutomatically: true },
    roster, profiles, scenarios, matchups, phases, benchmark, equivalence, equivalenceVerification, reuseCampaign };
  const manifest = { ...definition, campaignHash: digest(definition) };
  atomicJson(resolve(directory, "manifest.json"), manifest);
  atomicText(resolve(directory, ".gitignore"), "*.sqlite*\n*.tmp\n.runner.lock\n*.log\n*.pid\n");
  atomicJson(resolve(directory, "benchmark.json"), benchmark);
  atomicJson(resolve(directory, "equivalence.json"), equivalence);
  atomicJson(resolve(directory, "equivalence-verification.json"), equivalenceVerification);
  return manifest;
}
export function loadFull(directory) {
  const manifest = JSON.parse(readFileSync(resolve(directory, "manifest.json"), "utf8"));
  const { campaignHash, ...definition } = manifest;
  if (digest(definition) !== campaignHash) throw new Error("manifest hash mismatch");
  if (process.version !== manifest.nodeVersion) throw new Error("Node version changed");
  const environment = Object.fromEntries(Object.keys(process.env).filter(k => k.startsWith("AOE2X_EXP_")).sort().map(k => [k, process.env[k]]));
  if (digest(environment) !== digest(manifest.simulationEnvironment)) throw new Error("simulation environment changed");
  for (const entry of manifest.runtimeFiles) {
    if (sha(readFileSync(resolve(ROOT, entry.path))) !== entry.sha256) throw new Error(`frozen source changed: ${entry.path}`);
  }
  return manifest;
}
export function validateRecord(manifest, m, row) {
  if (row.campaignHash !== manifest.campaignHash || row.matchupId !== m.id
    || !Number.isSafeInteger(row.seed) || row.seed < 0 || row.seed > 9) throw new Error("record identity mismatch");
  if (!DECIDED.has(row.outcome) && !["undecided", "error"].includes(row.outcome)) throw new Error("invalid outcome");
  if (row.unitCount !== m.counts[0] || row.opponentCount !== m.counts[1]) throw new Error("record army counts changed");
  if (DECIDED.has(row.outcome)) {
    for (const k of ["unitStartingHp", "opponentStartingHp", "unitRemainingHp", "opponentRemainingHp", "unitHpPercent", "opponentHpPercent", "ticks"]) {
      if (!Number.isFinite(row[k]) || row[k] < 0) throw new Error(`invalid ${k}`);
    }
    if (!row.finalStateHash || !row.eventLogHash) throw new Error("missing replay hashes");
    if (row.ticks > (manifest.policy?.maxSimulationTicks ?? 9000)) throw new Error("simulation ceiling exceeded");
  }
}
export function restoreFullDb(directory, manifest) {
  const db = openCampaignDb(directory, manifest.campaignHash);
  const byId = new Map(manifest.matchups.map(m => [m.id, m]));
  if (!db.prepare("SELECT 1 FROM runs LIMIT 1").get()) {
    const journals = resolve(directory, "runs");
    if (existsSync(journals)) for (const name of readdirSync(journals).filter(n => n.endsWith(".jsonl"))) {
      for (const row of readLines(resolve(journals, name))) {
        const matchup = byId.get(row.matchupId);
        if (!matchup) throw new Error("unknown recovered matchup");
        validateRecord(manifest, matchup, row);
        saveRun(db, row);
      }
    }
    if (existsSync(resolve(directory, "attempts.json"))) {
      for (const a of JSON.parse(readFileSync(resolve(directory, "attempts.json"), "utf8"))) {
        db.prepare("INSERT OR IGNORE INTO attempts VALUES(?,?,?,?,?,?,?)")
          .run(a.id, a.matchup_id, a.seed, a.status, a.started_at, a.finished_at, a.detail);
      }
    }
  }
  return db;
}
export function importPilot(directory, manifest, db) {
  if (manifest.policy?.reusePilotRuns === false) return 0;
  const pilotDirectory = resolve(ROOT, manifest.pilotDirectory);
  const pilot = loadCampaign(pilotDirectory);
  if (pilot.campaignHash !== manifest.pilotCampaignHash) throw new Error("pilot changed");
  const imported = [];
  for (const original of readLines(resolve(pilotDirectory, "runs.jsonl"))) {
    const old = pilot.matchups.find(m => m.id === original.matchupId);
    const keys = old.teams.map(t => `${t.mechanics.civilization}|${t.mechanics.unit_slug}`);
    const m = manifest.matchups.find(m => digest(m.teamKeys) === digest(keys));
    if (!m || m.scenarioHash !== old.scenarioHash
      || digest(m.counts) !== digest(old.teams.map(t => t.count))
      || m.teamKeys.some((k, i) => manifest.profiles[k].profileHash !== old.teams[i].profileHash)) {
      throw new Error(`pilot inputs do not match full campaign: ${old.id}`);
    }
    if (m.canonicalMatchupId !== m.id) throw new Error("pilot must be the canonical equivalent matchup");
    if (db.prepare("SELECT 1 FROM runs WHERE matchup_id=? AND seed=?").get(m.id, original.seed)) continue;
    const record = { ...original, campaignHash: manifest.campaignHash, matchupId: m.id, attempt: null,
      provenance: { kind: "pilot", campaignHash: pilot.campaignHash, matchupId: original.matchupId, attempt: original.attempt,
        directory: manifest.pilotDirectory }, playbackPath: null };
    validateRecord(manifest, m, record);
    saveRun(db, record);
    appendJson(resolve(directory, "runs", `${m.phase}.jsonl`), record);
    imported.push(record);
  }
  return imported.length;
}
export function importEarlier(directory, manifest, db) {
  if (!manifest.reuseCampaign) return 0;
  const previousDirectory = resolve(ROOT, manifest.reuseCampaign.directory);
  const previous = JSON.parse(readFileSync(resolve(previousDirectory, "manifest.json"), "utf8"));
  const { campaignHash, ...definition } = previous;
  if (digest(definition) !== campaignHash || campaignHash !== manifest.reuseCampaign.campaignHash) throw new Error("previous campaign manifest changed");
  // Orchestration changes are allowed; simulation source and fixtures must be identical.
  for (const entry of previous.runtimeFiles.filter(e => e.path.includes("/src/") || e.path.includes("/fixtures/") || e.path.endsWith("/run-job.mjs"))) {
    if (sha(readFileSync(resolve(ROOT, entry.path))) !== entry.sha256) throw new Error("previous simulation source changed");
  }
  let imported = 0;
  for (const name of readdirSync(resolve(previousDirectory, "runs")).filter(n => n.endsWith(".jsonl"))) {
    for (const original of readLines(resolve(previousDirectory, "runs", name))) {
      if (original.campaignHash !== campaignHash) throw new Error("previous record campaign mismatch");
      const m = manifest.matchups.find(m => m.id === original.matchupId);
      const old = previous.matchups.find(m => m.id === original.matchupId);
      if (!m || !old || m.canonicalMatchupId !== m.id || m.scenarioHash !== old.scenarioHash
        || digest(m.counts) !== digest(old.counts)
        || m.teamKeys.some(k => manifest.profiles[k].profileHash !== previous.profiles[k].profileHash)) throw new Error("previous run input mismatch");
      if (db.prepare("SELECT 1 FROM runs WHERE matchup_id=? AND seed=?").get(m.id, original.seed)) continue;
      const row = { ...original, campaignHash: manifest.campaignHash, attempt: null,
        provenance: { kind: "earlier_campaign", campaignHash, matchupId: original.matchupId,
          attempt: original.attempt, directory: manifest.reuseCampaign.directory } };
      validateRecord(manifest, m, row);
      saveRun(db, row);
      appendJson(resolve(directory, "runs", `${m.phase}.jsonl`), row);
      imported++;
    }
  }
  return imported;
}
export function recordFromMessage(manifest, m, seed, message, timing) {
  const result = message.result;
  if (result && (!['win', 'draw', 'timeout'].includes(result.outcome)
    || Object.keys(result.remainingByOwner).some(owner => !['2', '3'].includes(owner)))) throw new Error("unexpected worker result");
  const outcome = message.watchdog || result?.outcome === "timeout" ? "undecided"
    : message.error ? "error" : result.outcome === "draw" ? "draw" : result.winnerOwner === 2 ? "win" : "loss";
  const row = { campaignHash: manifest.campaignHash, matchupId: m.id, seed, ...timing,
    outcome, reason: message.watchdog ? "wall_timeout" : result?.outcome === "timeout" ? "simulation_timeout" : message.error?.message ?? null,
    error: message.error ?? null, winnerOwner: result?.winnerOwner ?? null,
    unitCount: m.counts[0], opponentCount: m.counts[1],
    unitStartingHp: result?.startingHpByOwner[2] ?? manifest.profiles[m.teamKeys[0]].mechanics.hp * m.counts[0],
    opponentStartingHp: result?.startingHpByOwner[3] ?? manifest.profiles[m.teamKeys[1]].mechanics.hp * m.counts[1],
    unitRemainingHp: result?.remainingByOwner[2]?.hp ?? null, opponentRemainingHp: result?.remainingByOwner[3]?.hp ?? null,
    unitSurvivors: result?.remainingByOwner[2]?.units ?? null, opponentSurvivors: result?.remainingByOwner[3]?.units ?? null,
    ticks: result?.ticks ?? message.lastProgress?.tick ?? null,
    simulationSeconds: result ? result.ticks / 60 : message.lastProgress?.simulationSeconds ?? null,
    partialSimulationTime: !result, finalStateHash: result?.finalStateHash ?? null, eventLogHash: result?.eventLogHash ?? null,
    playbackPath: null, result: result ?? null };
  row.unitHpPercent = row.unitRemainingHp === null ? null : 100 * row.unitRemainingHp / row.unitStartingHp;
  row.opponentHpPercent = row.opponentRemainingHp === null ? null : 100 * row.opponentRemainingHp / row.opponentStartingHp;
  validateRecord(manifest, m, row);
  return row;
}
export function phasePending(matchups, records, active = new Set()) {
  return matchups.flatMap(m => {
    const rows = records.get(m.id) ?? [];
    return requiredSeeds(m, rows).filter(seed => !rows.some(r => r.seed === seed) && !active.has(`${m.id}:${seed}`))
      .map(seed => ({ matchup: m, seed }));
  }).sort((a, b) => Number(a.seed >= 3) - Number(b.seed >= 3) || a.seed - b.seed);
}
export function exportFull(directory, manifest, db, state) {
  const all = storedRuns(db), byMatchup = new Map();
  for (const row of all) {
    if (!byMatchup.has(row.matchupId)) byMatchup.set(row.matchupId, []);
    byMatchup.get(row.matchupId).push(row);
  }
  const summaries = manifest.matchups.map(m => ({ phase: m.phase, civilization: m.civilization, slug: m.slug,
    opponentKey: m.opponent, simulationSourceMatchupId: m.canonicalMatchupId,
    sharedEquivalentResults: m.canonicalMatchupId !== m.id,
    ...summarize({ matchups: [hydrate(manifest, m)] }, (byMatchup.get(m.canonicalMatchupId) ?? [])
      .map(r => ({ ...r, matchupId: m.id })))[0] }));
  for (const phase of manifest.phases) {
    const ids = new Set(phase.matchupIds), rows = all.filter(r => ids.has(r.matchupId));
    if (rows.length) atomicText(resolve(directory, "runs", `${phase.id}.jsonl`), rows.map(r => JSON.stringify(r)).join("\n") + "\n");
  }
  const physicalSummaries = summaries.filter(r => r.matchupId === r.simulationSourceMatchupId);
  const pendingRuns = physicalSummaries.reduce((sum, r) => sum + r.requiredRuns - r.recordedRuns, 0);
  const computedRuns = all.filter(r => !r.provenance).length;
  const elapsedSeconds = (Date.now() - Date.parse(state.startedAt)) / 1000;
  const progress = { campaignHash: manifest.campaignHash, updatedAt: now(), status: state.status,
    activePhase: state.activePhase, workers: state.workers, recordedRuns: all.length,
    requiredRuns: physicalSummaries.reduce((n, r) => n + r.requiredRuns, 0), pendingRuns,
    uniqueMatchups: manifest.equivalence.distinctMatchups, distinctUnitProfiles: manifest.equivalence.distinctUnitProfiles,
    avoidedBaselineRuns: manifest.equivalence.avoidedBaselineRuns,
    totalMatchups: manifest.matchups.length, completeMatchups: summaries.filter(r => r.state === "complete").length,
    reviewMatchups: summaries.filter(r => r.state === "needs_review").length,
    undecidedRuns: all.filter(r => r.outcome === "undecided").length, errors: all.filter(r => r.outcome === "error").length,
    reusedPilotRuns: all.filter(r => r.provenance?.kind === "pilot").length,
    reusedEarlierCampaignRuns: all.filter(r => r.provenance?.kind === "earlier_campaign").length,
    workerSeconds: all.filter(r => !r.provenance).reduce((sum, r) => sum + r.wallSeconds, 0),
    startedAt: state.startedAt, phasesReviewed: Object.keys(state.reviews ?? {}).length,
    totalPhases: manifest.phases.length,
    observedRunsPerHour: computedRuns >= 25 ? computedRuns / elapsedSeconds * 3600 : null,
    estimatedRemainingHoursAtCurrentRate: computedRuns >= 25 ? pendingRuns * elapsedSeconds / computedRuns / 3600 : null };
  atomicJson(resolve(directory, "progress.json"), progress);
  atomicJson(resolve(directory, "state.json"), state);
  atomicJson(resolve(directory, "summary.json"), summaries);
  atomicText(resolve(directory, "summary.csv"), csv(summaries, Object.keys(summaries[0])));
  atomicJson(resolve(directory, "undecided.json"), all.filter(r => !DECIDED.has(r.outcome)));
  atomicJson(resolve(directory, "attempts.json"), db.prepare("SELECT * FROM attempts ORDER BY id").all());
  atomicText(resolve(directory, "README.md"), `# Full Imperial land rankings campaign\n\n`
    + `Status: **${state.status}**. ${all.length}/${progress.requiredRuns} currently required runs; `
    + `${progress.completeMatchups}/${manifest.matchups.length} complete matchups; ${progress.reviewMatchups} flagged for review.\n\n`
    + `${manifest.roster.units.length} civilization/unit variants across ${manifest.roster.civilizations} civilizations. Infantry ${manifest.roster.counts.Infantry}, `
    + `Ranged ${manifest.roster.counts.Ranged}, Cavalry ${manifest.roster.counts.Cavalry}. `
    + `Imperial units only; naval and anti-building groups are outside the agreed opponent pools. Scoring remains deferred.\n\n`
    + `Exact profile sharing reduces this to **${manifest.equivalence.distinctMatchups} distinct matchups** `
    + `(${manifest.equivalence.distinctUnitProfiles} combat profiles), avoiding ${manifest.equivalence.avoidedBaselineRuns} baseline runs. `
    + `Only the civilization label is excluded from equality; every other profile field, cost, count and scenario must match. `
    + `The summary retains all civilization rows and identifies their shared simulation source. [Equivalence map](equivalence.json).\n\n`
    + `27 on the cheaper side; expensive side = round(27 × sqrt(cheaper / expensive weighted unit cost)). `
    + `Weights: food 1, wood 0.9, gold 1.1; full discounts and per-physical-unit batch costs. No buffers or scripted kiting.\n\n`
    + `Three seeds per matchup, expanding to ten when the initial completed outcomes differ. `
    + `${manifest.policy?.maxSimulationTicks === Number.MAX_SAFE_INTEGER ? "No practical game-time ceiling" : `${(manifest.policy?.maxSimulationTicks ?? 9000) / 60} game seconds`} / ${manifest.policy?.wallTimeoutSeconds ?? 120} wall seconds per attempt. Undecided/error cases are saved and excluded from decided averages.\n\n`
    + `${state.workers} persistent workers run sequential phases automatically. Each phase verifies coverage, record validity, `
    + `source hashes, SQLite integrity and a separate exact-seed replay before continuing. `
    + `Each result commits to SQLite and a flushed JSONL journal. GitHub checkpoints occur at phase boundaries, `
    + `250 new results or ten minutes; network failures do not discard results.\n\n`
    + `- [Plan](PLAN.md), [progress](progress.json), [phase reviews](state.json), [summary table](summary.csv), [undecided](undecided.json).\n`
    + `- Every individual run is in [phase journals](runs/); these restore SQLite after a fresh checkout.\n`
    + `- [Manifest](manifest.json) freezes all profiles, formations, seeds, cost rules and source hashes.\n`
    + (manifest.policy?.reusePilotRuns === false
      ? `- All results are recomputed on this engine version; historical pilot/campaign results are not imported.\n\n`
      : `- The [pilot](../unit-rankings-pilot-2026-10-29/) supplies 37 reused results with recorded provenance.\n\n`)
    + `Resume (Node ${process.version}):\n\n\`\`\`bash\nnode aoe2x/js_simulation/node/full-ranking-campaign.mjs run --campaign ${relative(ROOT, directory)} --publish true\n\`\`\`\n`);
  return progress;
}
async function command(args) {
  return new Promise((resolveCommand, reject) => {
    const child = spawn("git", args, { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0" } });
    let stdout = "", stderr = "";
    child.stdout.on("data", chunk => { stdout += chunk; });
    child.stderr.on("data", chunk => { stderr += chunk; });
    const timeout = setTimeout(() => child.kill("SIGTERM"), 60000);
    child.on("error", error => { clearTimeout(timeout); reject(error); });
    child.on("close", code => { clearTimeout(timeout); code === 0 ? resolveCommand(stdout.trim()) : reject(new Error(`git ${args[0]} failed (${code}): ${stderr.slice(-1500)}`)); });
  });
}
async function publish(directory, state, manifest) {
  try {
    const branch = await command(["branch", "--show-current"]);
    if (branch !== (manifest.publishBranch ?? "simulations/v3-engine-ranking-pilot-2026-10-29")) throw new Error("unexpected publishing branch");
    const prefix = relative(ROOT, directory);
    const staged = await command(["diff", "--cached", "--name-only"]);
    if (staged.split("\n").some(p => p && !p.startsWith(`${prefix}/`))) throw new Error("unrelated staged changes; checkpoint retained locally");
    await command(["add", "--", prefix]);
    if ((await command(["diff", "--cached", "--name-only"])).trim()) {
      await command(["commit", "-m", `Checkpoint full ranking campaign: ${state.activePhase ?? state.status}`]);
    }
    await command(["push", "origin", branch]);
    state.lastPublishedAt = now(); state.lastPublishError = null;
    console.log(JSON.stringify({ published: state.lastPublishedAt, phase: state.activePhase }));
  } catch (error) {
    state.lastPublishError = { at: now(), message: error.message };
    console.error(JSON.stringify({ publishError: state.lastPublishError }));
  }
}
async function reviewPhase(directory, manifest, phase, db, pool) {
  loadFull(directory);
  const integrity = db.prepare("PRAGMA integrity_check").get().integrity_check;
  if (integrity !== "ok") throw new Error(`SQLite integrity: ${integrity}`);
  const matchups = manifest.matchups.filter(m => m.phase === phase.id && m.canonicalMatchupId === m.id);
  const all = storedRuns(db), rowsById = new Map(matchups.map(m => [m.id, all.filter(r => r.matchupId === m.id)]));
  if (phasePending(matchups, rowsById).length) throw new Error("phase has missing seeds");
  for (const m of matchups) for (const row of rowsById.get(m.id)) validateRecord(manifest, m, row);
  const candidate = matchups.find(m => rowsById.get(m.id).some(r => DECIDED.has(r.outcome) && !r.provenance));
  let replay = null;
  if (candidate) {
    const original = rowsById.get(candidate.id).find(r => DECIDED.has(r.outcome) && !r.provenance);
    const message = await pool.run(jobFor(manifest, candidate, original.seed), 120);
    const exact = message.result?.finalStateHash === original.finalStateHash && message.result?.eventLogHash === original.eventLogHash;
    replay = { matchupId: candidate.id, seed: original.seed, exact, error: message.error ?? null, watchdog: message.watchdog ?? false };
    if (!exact) throw new Error(`phase replay failed: ${JSON.stringify(replay)}`);
  }
  const phaseRows = [...rowsById.values()].flat();
  return { reviewedAt: now(), status: phaseRows.some(r => !DECIDED.has(r.outcome)) ? "complete_with_review_cases" : "passed",
    matchups: matchups.length, runs: phaseRows.length, undecided: phaseRows.filter(r => r.outcome === "undecided").length,
    errors: phaseRows.filter(r => r.outcome === "error").length, integrity, sourceHashes: "passed", replay };
}
export async function runFull(directory, { workers = 4, publishResults = false, maxPhases = Infinity } = {}) {
  if (!Number.isSafeInteger(workers) || workers < 1) throw new Error("workers must be positive");
  const manifest = loadFull(directory), lock = resolve(directory, ".runner.lock");
  if (existsSync(lock)) {
    const pid = Number(readFileSync(lock, "utf8"));
    try { process.kill(pid, 0); throw new Error(`already running under PID ${pid}`); }
    catch (error) { if (error.code !== "ESRCH") throw error; unlinkSync(lock); }
  }
  const lockFd = openSync(lock, "wx"); writeFileSync(lockFd, String(process.pid)); closeSync(lockFd);
  let db, pool, state;
  let stopping = false;
  const stop = () => { stopping = true; };
  process.on("SIGTERM", stop); process.on("SIGINT", stop);
  try {
    db = restoreFullDb(directory, manifest);
    db.prepare("UPDATE attempts SET status='interrupted',finished_at=? WHERE status='running'").run(now());
    importPilot(directory, manifest, db);
    importEarlier(directory, manifest, db);
    state = existsSync(resolve(directory, "state.json")) ? JSON.parse(readFileSync(resolve(directory, "state.json"), "utf8"))
      : { startedAt: now(), reviews: {} };
    state.status = "running"; state.workers = workers; state.pid = process.pid;
    pool = new RankingWorkerPool(workers, manifest.policy?.maxSimulationTicks ? {
      workerUrl: new URL("./collision-validation-worker.mjs", import.meta.url),
      maxTicks: manifest.policy?.maxSimulationTicks,
    } : {});
    let lastExport = 0, lastPublish = Date.now(), sincePublish = 0, completedHere = 0;
    exportFull(directory, manifest, db, state);
    for (const phase of manifest.phases) {
      if (stopping || completedHere >= maxPhases) break;
      if (state.reviews[phase.id]) {
        const all = storedRuns(db), items = manifest.matchups.filter(m => m.phase === phase.id && m.canonicalMatchupId === m.id);
        if (!phasePending(items, new Map(items.map(m => [m.id, all.filter(r => r.matchupId === m.id)]))).length) continue;
        delete state.reviews[phase.id];
      }
      loadFull(directory);
      state.activePhase = phase.id;
      console.log(JSON.stringify({ phaseStarted: phase.id, matchups: phase.matchupIds.length }));
      const matchups = manifest.matchups.filter(m => m.phase === phase.id && m.canonicalMatchupId === m.id);
      const allSaved = storedRuns(db);
      const byId = new Map(matchups.map(m => [m.id, allSaved.filter(r => r.matchupId === m.id)]));
      const active = new Map();
      while (!stopping || active.size) {
        if (!stopping) {
          const pending = phasePending(matchups, byId, new Set(active.keys()));
          while (active.size < workers && pending.length) {
            const { matchup: m, seed } = pending.shift(), key = `${m.id}:${seed}`, startedAt = now(), start = performance.now();
            const attempt = Number(db.prepare("INSERT INTO attempts(matchup_id,seed,status,started_at) VALUES(?,?,'running',?)")
              .run(m.id, seed, startedAt).lastInsertRowid);
            active.set(key, pool.run(jobFor(manifest, m, seed), manifest.policy.wallTimeoutSeconds)
              .then(message => ({ key, m, seed, message, timing: { attempt, startedAt, finishedAt: now(), wallSeconds: (performance.now() - start) / 1000 } })));
          }
        }
        if (!active.size) break;
        const done = await Promise.race(active.values());
        active.delete(done.key);
        const row = recordFromMessage(manifest, done.m, done.seed, done.message, done.timing);
        saveRun(db, row, row.attempt);
        appendJson(resolve(directory, "runs", `${phase.id}.jsonl`), row);
        byId.get(done.m.id).push(row);
        sincePublish++;
        console.log(JSON.stringify({ saved: done.key, outcome: row.outcome, wallSeconds: row.wallSeconds, phase: phase.id }));
        if (Date.now() - lastExport >= 30000) { exportFull(directory, manifest, db, state); lastExport = Date.now(); }
        if (sincePublish >= 250 || Date.now() - lastPublish >= 600000) {
          exportFull(directory, manifest, db, state);
          if (publishResults) await publish(directory, state, manifest);
          sincePublish = 0; lastPublish = Date.now();
        }
      }
      if (stopping) break;
      state.reviews[phase.id] = await reviewPhase(directory, manifest, phase, db, pool);
      completedHere++;
      exportFull(directory, manifest, db, state);
      if (publishResults) await publish(directory, state, manifest);
      sincePublish = 0; lastPublish = Date.now();
      console.log(JSON.stringify({ phaseCompleted: phase.id, review: state.reviews[phase.id] }));
    }
    state.status = Object.keys(state.reviews).length === manifest.phases.length ? "complete" : "paused";
    if (state.status === "complete") { state.activePhase = null; state.completedAt = now(); }
    const progress = exportFull(directory, manifest, db, state);
    if (state.status === "complete" && progress.pendingRuns !== 0) throw new Error("completion coverage mismatch");
    if (publishResults) await publish(directory, state, manifest);
    return progress;
  } catch (error) {
    if (state && db) {
      state.status = "failed"; state.failure = { at: now(), message: error.message };
      exportFull(directory, manifest, db, state);
      if (publishResults) await publish(directory, state, manifest);
    }
    throw error;
  } finally {
    await pool?.close(); db?.close(); unlinkSync(lock);
    process.off("SIGTERM", stop); process.off("SIGINT", stop);
  }
}
async function main() {
  const [commandName, ...args] = process.argv.slice(2), options = {};
  for (let i = 0; i < args.length; i += 2) options[args[i]] = args[i + 1];
  if (!options["--campaign"]) throw new Error("--campaign required");
  const directory = resolve(options["--campaign"]);
  if (commandName === "prepare") {
    const manifest = await prepareFull(directory, resolve(options["--roster"]),
      resolve(options["--pilot"]), resolve(options["--reference-db"] ?? "data/golden/aoe2_reference_simulation.db"),
      options["--reuse-campaign"] ? resolve(options["--reuse-campaign"]) : null);
    console.log(JSON.stringify({ campaignHash: manifest.campaignHash, units: manifest.roster.units.length,
      matchups: manifest.matchups.length, distinctMatchups: manifest.equivalence.distinctMatchups,
      minimumRuns: manifest.equivalence.distinctMatchups * 3, phases: manifest.phases.length }));
  } else if (commandName === "run") console.log(JSON.stringify(await runFull(directory, {
    workers: Number(options["--workers"] ?? 4), publishResults: options["--publish"] === "true",
    maxPhases: options["--max-phases"] === undefined ? Infinity : Number(options["--max-phases"]),
  })));
  else throw new Error("command must be prepare or run");
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) await main();
