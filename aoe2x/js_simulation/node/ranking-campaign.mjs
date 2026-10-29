#!/usr/bin/env node
// Resumable raw-results collection. This module deliberately computes no ranking score.
import { DatabaseSync } from "node:sqlite";
import { availableParallelism } from "node:os";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, renameSync, readdirSync,
  existsSync, unlinkSync, openSync, closeSync, fsyncSync, statSync } from "node:fs";
import { dirname, resolve, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { Worker } from "node:worker_threads";
import { hashCanonicalJson } from "../src/canonical-json.js";
import { loadLabScenario } from "../src/lab-scenario.js";
import { deriveRecordedBattleSetup } from "../src/battle-setup.js";
import { validateMechanicsProfile, unitDescriptorFromMechanics } from "../src/mechanics-schema.js";
import { ENGINE_CONFIG } from "../src/engine-config.js";

const SIM = fileURLToPath(new URL("../", import.meta.url));
const ROOT = resolve(SIM, "../..");
const sha = value => createHash("sha256").update(value).digest("hex");
const digest = hashCanonicalJson;
const now = () => new Date().toISOString();
const DECIDED = new Set(["win", "loss", "draw"]);
export const PILOT = [
  ["champion_mirror", "Infantry", "Spanish", "champion", "Spanish", "champion", "Mirror and seed variability"],
  ["champion_paladin", "Infantry", "Spanish", "champion", "Spanish", "paladin", "Cost balance and melee"],
  ["arbalester_cavalier", "Ranged", "Chinese", "arbalester", "Turks", "paladin", "Ranged vs actual Turkish Cavalier"],
  ["hca_skirmisher", "Ranged", "Saracens", "heavy_cav_archer", "Spanish", "imp_elite_skirm", "Ranged counter"],
  ["hand_cannoneer_arbalester", "Ranged", "Saracens", "hand_cannoneer", "Chinese", "arbalester", "Gunpowder accuracy"],
  ["war_elephant_halberdier", "Cavalry", "Persians", "elite_war_elephant_persians", "Spanish", "halberdier", "Large bodies and trample"],
  ["varangian_guard_arbalester", "Infantry", "Varangians", "elite_varangian_guard", "Chinese", "arbalester", "Independent charged projectiles"],
  ["jarl_hussar", "Ranged", "Varangians", "elite_jarl_varangians", "Spanish", "hussar", "Jarl in the Ranged group"],
  ["konnik_camel", "Cavalry", "Bulgarians", "elite_konnik_bulgarians", "Turks", "heavy_camel", "Dismount and cavalry counter"],
  ["blackwood_hussar", "Ranged", "Tupi", "elite_blackwood_archer_tupi", "Spanish", "hussar", "Batch cost, half population, poison"],
];

export function atomicJson(path, value) { atomicText(path, `${JSON.stringify(value, null, 2)}\n`); }
function atomicText(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.tmp`;
  const fd = openSync(temporary, "w");
  try { writeFileSync(fd, value); fsyncSync(fd); } finally { closeSync(fd); }
  renameSync(temporary, path);
}
function listFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => (
    entry.isDirectory() ? listFiles(resolve(directory, entry.name)) : [resolve(directory, entry.name)]
  ));
}
function runtimeFiles() {
  return [...listFiles(resolve(SIM, "src")).filter(p => p.endsWith(".js")),
    ...["run-job.mjs", "campaign-worker.mjs", "ranking-campaign.mjs"].map(p => resolve(SIM, "node", p)),
    ...["golden_map.json", "golden_formation_27v27.json", "current_ranged_golden_formations.json"]
      .map(p => resolve(SIM, "fixtures", p)),
  ].sort().map(path => ({ path: relative(ROOT, path), sha256: sha(readFileSync(path)) }));
}
function simulationEnvironment() {
  // Only simulation switches are inspected; never collect credentials/environment wholesale.
  return Object.fromEntries(Object.keys(process.env).filter(k => k.startsWith("AOE2X_EXP_"))
    .sort().map(k => [k, process.env[k]]));
}

function sourceCommit() {
  const dotGit = resolve(ROOT, ".git");
  const gitDir = statSync(dotGit).isDirectory() ? dotGit
    : resolve(ROOT, readFileSync(dotGit, "utf8").trim().replace(/^gitdir: /, ""));
  const head = readFileSync(resolve(gitDir, "HEAD"), "utf8").trim();
  if (/^[0-9a-f]{40}$/.test(head)) return head;
  const ref = head.replace(/^ref: /, "");
  const common = existsSync(resolve(gitDir, "commondir"))
    ? resolve(gitDir, readFileSync(resolve(gitDir, "commondir"), "utf8").trim()) : gitDir;
  for (const directory of [gitDir, common]) {
    if (existsSync(resolve(directory, ref))) return readFileSync(resolve(directory, ref), "utf8").trim();
  }
  const line = readFileSync(resolve(common, "packed-refs"), "utf8").split("\n").find(l => l.endsWith(` ${ref}`));
  if (!line) throw new Error("cannot resolve source commit");
  return line.split(" ")[0];
}

export async function prepareCampaign(directory, referenceDb) {
  if (existsSync(resolve(directory, "manifest.json"))) throw new Error("campaign already exists; use run to resume");
  const db = new DatabaseSync(referenceDb, { readOnly: true });
  const query = db.prepare(`SELECT u.id,u.unit_name,u.unit_master,u.civ_name,u.unit_slug,
    u.final_cost_food,u.final_cost_wood,u.final_cost_gold,m.mechanics_json,m.mechanics_hash,m.source_build
    FROM ref_units u JOIN ref_unit_mechanics m ON m.ref_unit_id=u.id
    WHERE u.civ_name=? AND u.unit_slug=? AND u.age='Imperial' AND m.is_default=1`);
  const team = (civ, slug) => {
    const rows = query.all(civ, slug);
    if (rows.length !== 1) throw new Error(`ambiguous/missing profile ${civ}/${slug}`);
    const row = rows[0];
    const mechanics = validateMechanicsProfile(JSON.parse(row.mechanics_json));
    return { mechanics, profileHash: digest(mechanics), referenceId: row.id,
      sourceBuild: row.source_build, storedMechanicsHash: row.mechanics_hash,
      referencePurchaseCost: { food: row.final_cost_food, wood: row.final_cost_wood, gold: row.final_cost_gold } };
  };
  const matchups = [];
  try {
    for (const [id, group, civ, slug, opponentCiv, opponentSlug, purpose] of PILOT) {
      const teams = [team(civ, slug), team(opponentCiv, opponentSlug)];
      const descriptors = teams.map(({ mechanics }) => unitDescriptorFromMechanics(mechanics));
      const setup = deriveRecordedBattleSetup(...teams.map(({ mechanics }, i) => ({
        ...descriptors[i], effectiveCost: mechanics.cost,
      })), { cap: 27 });
      const scenario = await loadLabScenario(pathToFileURL(`${SIM}/`), ...descriptors, { includeBuffer: false });
      if (scenario.auxiliaryArmiesByOwner && Object.keys(scenario.auxiliaryArmiesByOwner).length) {
        throw new Error("campaign cannot contain buffer armies");
      }
      teams.forEach((entry, i) => {
        entry.count = i === 0 ? setup.n2 : setup.n3;
        entry.weightedCost = i === 0 ? setup.cost2 : setup.cost3;
        entry.armyPopulation = entry.count * entry.mechanics.population_space;
        entry.armyWeightedCost = entry.count * entry.weightedCost;
      });
      matchups.push({ id, group, purpose, teams, scenario, scenarioHash: digest(scenario) });
    }
  } finally { db.close(); }
  const definition = {
    schemaVersion: 1, campaignName: "unit-rankings-pilot-2026-10-29", createdAt: now(),
    scope: "10-matchup pilot; no ranking scores or production update",
    nodeVersion: process.version, sourceCommit: sourceCommit(),
    runtimeFiles: runtimeFiles(), engineConfig: ENGINE_CONFIG, simulationEnvironment: simulationEnvironment(),
    referenceDb: relative(ROOT, referenceDb), referenceDbSha256: sha(readFileSync(referenceDb)),
    policy: { cap: 27, weights: { food: 1, wood: 0.9, gold: 1.1 },
      countFormula: "round(27 * sqrt(cheaperWeightedCost / expensiveWeightedCost)); cheaper side 27",
      costBasis: "runtime cost per physical unit, full civilization discounts and batch division",
      bufferUnits: 0, disableKiting: true, disableAiOrders: true,
      initialSeeds: [0, 1, 2], extraSeeds: [3, 4, 5, 6, 7, 8, 9],
      expansionRule: "different completed win/loss/draw outcomes among the first three seeds",
      maxSimulationTicks: 9000, wallTimeoutSeconds: 120,
      checkpointEveryRuns: 250, checkpointEverySeconds: 600,
      groupConvention: "existing ranking groups; Jarl is Ranged", scoring: "deferred" },
    matchups,
  };
  const manifest = { ...definition, campaignHash: digest(definition) };
  atomicJson(resolve(directory, "manifest.json"), manifest);
  atomicText(resolve(directory, ".gitignore"), "*.sqlite*\nplaybacks/\n.runner.lock\n*.tmp\ncheckpoint-request.json\n");
  return manifest;
}

export function loadCampaign(directory) {
  const manifest = JSON.parse(readFileSync(resolve(directory, "manifest.json"), "utf8"));
  const { campaignHash, ...definition } = manifest;
  if (digest(definition) !== campaignHash) throw new Error("campaign manifest hash mismatch");
  if (manifest.nodeVersion !== process.version) throw new Error("Node version differs from frozen campaign");
  if (digest(simulationEnvironment()) !== digest(manifest.simulationEnvironment)) throw new Error("simulation environment changed");
  for (const entry of manifest.runtimeFiles) {
    if (sha(readFileSync(resolve(ROOT, entry.path))) !== entry.sha256) {
      throw new Error(`runtime changed: ${entry.path}; start a new campaign instead of mixing results`);
    }
  }
  return manifest;
}

export function openCampaignDb(directory, campaignHash) {
  mkdirSync(directory, { recursive: true });
  const db = new DatabaseSync(resolve(directory, "results.sqlite"));
  db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs(matchup_id TEXT,seed INTEGER,record_json TEXT NOT NULL,
      PRIMARY KEY(matchup_id,seed));
    CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,matchup_id TEXT,seed INTEGER,
      status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,detail TEXT);`);
  const previous = db.prepare("SELECT value FROM metadata WHERE key='campaignHash'").get();
  if (previous && previous.value !== campaignHash) { db.close(); throw new Error("database belongs to a different campaign"); }
  db.prepare("INSERT OR IGNORE INTO metadata VALUES('campaignHash',?)").run(campaignHash);
  // Portable recovery from the GitHub JSONL export, when local SQLite is unavailable.
  if (!db.prepare("SELECT 1 FROM runs LIMIT 1").get() && existsSync(resolve(directory, "runs.jsonl"))) {
    const records = readFileSync(resolve(directory, "runs.jsonl"), "utf8").trim().split("\n").filter(Boolean).map(JSON.parse);
    db.exec("BEGIN IMMEDIATE");
    try {
      for (const row of records) {
        if (row.campaignHash !== campaignHash) throw new Error("export belongs to a different campaign");
        db.prepare("INSERT INTO runs VALUES(?,?,?)").run(row.matchupId, row.seed, JSON.stringify(row));
      }
      if (existsSync(resolve(directory, "attempts.json"))) {
        for (const attempt of JSON.parse(readFileSync(resolve(directory, "attempts.json"), "utf8"))) {
          db.prepare("INSERT OR IGNORE INTO attempts VALUES(?,?,?,?,?,?,?)").run(attempt.id,
            attempt.matchup_id, attempt.seed, attempt.status, attempt.started_at, attempt.finished_at, attempt.detail);
        }
      }
      for (const row of records) {
        db.prepare("INSERT OR IGNORE INTO attempts VALUES(?,?,?,?,?,?,?)").run(row.attempt,
          row.matchupId, row.seed, row.outcome, row.startedAt, row.finishedAt, row.reason);
      }
      db.exec("COMMIT");
    } catch (error) { db.exec("ROLLBACK"); db.close(); throw error; }
  }
  return db;
}
export function storedRuns(db) {
  return db.prepare("SELECT record_json FROM runs ORDER BY matchup_id,seed").all().map(r => JSON.parse(r.record_json));
}
export function requiredSeeds(matchup, records) {
  const initial = records.filter(r => r.matchupId === matchup.id && r.seed < 3);
  const distinct = new Set(initial.filter(r => DECIDED.has(r.outcome)).map(r => r.outcome));
  return Array.from({ length: initial.length === 3 && distinct.size > 1 ? 10 : 3 }, (_, i) => i);
}
export function pendingJobs(manifest, records) {
  const done = new Set(records.map(r => `${r.matchupId}:${r.seed}`));
  return manifest.matchups.flatMap(matchup => requiredSeeds(matchup, records)
    .filter(seed => !done.has(`${matchup.id}:${seed}`)).map(seed => ({ matchup, seed })))
    .sort((a, b) => Number(a.seed >= 3) - Number(b.seed >= 3));
}
export function saveRun(db, record, attemptId = null) {
  db.exec("BEGIN IMMEDIATE");
  try {
    db.prepare("INSERT INTO runs VALUES(?,?,?)").run(record.matchupId, record.seed, JSON.stringify(record));
    if (attemptId !== null) db.prepare("UPDATE attempts SET status=?,finished_at=?,detail=? WHERE id=?")
      .run(record.outcome, record.finishedAt, record.reason ?? null, attemptId);
    db.exec("COMMIT");
  } catch (error) { db.exec("ROLLBACK"); throw error; }
}
const mean = values => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
export function summarize(manifest, records) {
  return manifest.matchups.map(matchup => {
    const runs = records.filter(r => r.matchupId === matchup.id);
    const decided = runs.filter(r => DECIDED.has(r.outcome));
    const target = requiredSeeds(matchup, records).length;
    const unresolved = runs.filter(r => !DECIDED.has(r.outcome));
    return { matchupId: matchup.id, group: matchup.group,
      unit: `${matchup.teams[0].mechanics.civilization} ${matchup.teams[0].mechanics.unit_name}`,
      opponent: `${matchup.teams[1].mechanics.civilization} ${matchup.teams[1].mechanics.unit_name}`,
      unitCount: matchup.teams[0].count, opponentCount: matchup.teams[1].count,
      requiredRuns: target, recordedRuns: runs.length,
      wins: runs.filter(r => r.outcome === "win").length, losses: runs.filter(r => r.outcome === "loss").length,
      draws: runs.filter(r => r.outcome === "draw").length, undecided: unresolved.length,
      state: runs.length < target ? "pending" : unresolved.length ? "needs_review" : "complete",
      meanUnitHpPercentDecided: mean(decided.map(r => r.unitHpPercent)),
      meanOpponentHpPercentDecided: mean(decided.map(r => r.opponentHpPercent)),
      minUnitHpPercentDecided: decided.length ? Math.min(...decided.map(r => r.unitHpPercent)) : null,
      maxUnitHpPercentDecided: decided.length ? Math.max(...decided.map(r => r.unitHpPercent)) : null,
      meanSimulationSecondsDecided: mean(decided.map(r => r.simulationSeconds)),
      meanWallSeconds: mean(runs.map(r => r.wallSeconds)),
    };
  });
}
function csv(rows, columns) {
  const cell = v => v == null ? "" : `"${String(v).replaceAll('"', '""')}"`;
  return `${columns.join(",")}\n${rows.map(r => columns.map(k => cell(r[k])).join(",")).join("\n")}${rows.length ? "\n" : ""}`;
}
export function exportCampaign(directory, manifest, db) {
  const records = storedRuns(db);
  const summary = summarize(manifest, records);
  const attempts = db.prepare("SELECT * FROM attempts ORDER BY id").all();
  atomicText(resolve(directory, "runs.jsonl"), records.map(r => JSON.stringify(r)).join("\n") + (records.length ? "\n" : ""));
  atomicText(resolve(directory, "runs.csv"), csv(records, ["matchupId", "seed", "outcome", "reason", "winnerOwner",
    "unitCount", "opponentCount", "unitStartingHp", "opponentStartingHp", "unitRemainingHp", "opponentRemainingHp",
    "unitSurvivors", "opponentSurvivors", "unitHpPercent", "opponentHpPercent", "simulationSeconds", "wallSeconds",
    "finalStateHash", "eventLogHash", "campaignHash", "playbackPath"]));
  atomicJson(resolve(directory, "summary.json"), summary);
  atomicText(resolve(directory, "summary.csv"), csv(summary, Object.keys(summary[0])));
  atomicJson(resolve(directory, "undecided.json"), records.filter(r => !DECIDED.has(r.outcome)));
  atomicJson(resolve(directory, "attempts.json"), attempts);
  const progress = { campaignHash: manifest.campaignHash, updatedAt: now(), recordedRuns: records.length,
    requiredRuns: summary.reduce((n, r) => n + r.requiredRuns, 0),
    completedMatchups: summary.filter(r => r.state === "complete").length,
    reviewMatchups: summary.filter(r => r.state === "needs_review").length,
    pendingRuns: pendingJobs(manifest, records).length,
    cumulativeWorkerSeconds: records.reduce((n, r) => n + r.wallSeconds, 0) };
  atomicJson(resolve(directory, "progress.json"), progress);
  atomicText(resolve(directory, "README.md"), `# Unit rankings pilot — October 29, 2026\n\n`
    + `Raw results only; scoring is deferred. Campaign: \`${manifest.campaignHash}\`.\n\n`
    + `27 units on the cheaper side; expensive count = round(27 × sqrt(cheap/expensive weighted cost)). `
    + `Resource weights: food 1, wood 0.9, gold 1.1. Full discounts and cost per physical unit. `
    + `No buffers or scripted kiting; current golden formations and patrols. Jarl is Ranged.\n\n`
    + `Three seeds initially; seven additional seeds if completed outcomes differ. `
    + `150 game-second limit; ${manifest.policy.wallTimeoutSeconds}s wall-clock watchdog. Timeouts/errors are flagged for review.\n\n`
    + `Recorded ${progress.recordedRuns}/${progress.requiredRuns} currently required runs; `
    + `${progress.completedMatchups} complete matchups; ${progress.reviewMatchups} need review.\n\n`
    + `| Unit | Opponent | Counts | Runs | W/L/D | Undecided | Mean unit HP%* | Mean opponent HP%* |\n`
    + `|---|---|---|---|---|---|---|---|\n`
    + summary.map(r => `| ${r.unit} | ${r.opponent} | ${r.unitCount}:${r.opponentCount} | ${r.recordedRuns}/${r.requiredRuns} | `
      + `${r.wins}/${r.losses}/${r.draws} | ${r.undecided} | ${r.meanUnitHpPercentDecided?.toFixed(2) ?? "—"} | `
      + `${r.meanOpponentHpPercentDecided?.toFixed(2) ?? "—"} |`).join("\n")
    + `\n\n*Descriptive averages over decided runs only, not ranking scores. Review rows remain incomplete.\n\n`
    + `- [Every run (CSV)](runs.csv), [lossless JSONL](runs.jsonl), [matchup summary](summary.csv), [undecided](undecided.json).\n`
    + `- [Frozen profiles, setup and source hashes](manifest.json); seeds reconstruct every run.\n`
    + `- SQLite commits each run immediately. JSONL can restore the database on another checkout.\n`
    + `- Full per-tick playbacks are saved locally as compressed JSONL in playbacks/.\n\n`
    + `Resume from the repository root using Node ${process.version}:\n\n\`\`\`bash\n`
    + `node aoe2x/js_simulation/node/ranking-campaign.mjs run --campaign ${relative(ROOT, directory)} --workers 3\n\`\`\`\n`);
  return progress;
}

function executeJob(job, playbackPath, wallSeconds, onProgress) {
  return new Promise(resolveResult => {
    const worker = new Worker(new URL("./campaign-worker.mjs", import.meta.url), { workerData: { job, playbackPath } });
    let finished = false;
    let lastTick = 0;
    const finish = message => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      worker.terminate().then(() => resolveResult({ ...message, lastTick }));
    };
    const timer = setTimeout(() => finish({ watchdog: true }), wallSeconds * 1000);
    worker.on("message", message => {
      if (message.progress !== undefined) { lastTick = message.progress; onProgress?.(lastTick); }
      else finish(message);
    });
    worker.on("error", error => finish({ error: { name: error.name, message: error.message } }));
    worker.on("exit", code => { if (!finished) finish({ error: { name: "WorkerExit", message: `worker exited ${code}` } }); });
  });
}

export async function runCampaign(directory, { workers = Math.max(1, Math.floor(availableParallelism() * 0.8)),
  maxNewRuns = Infinity, onSaved, executor = executeJob } = {}) {
  if (!Number.isSafeInteger(workers) || workers < 1) throw new Error("workers must be positive");
  if (maxNewRuns !== Infinity && (!Number.isSafeInteger(maxNewRuns) || maxNewRuns < 0)) throw new Error("max-new-runs must be nonnegative");
  const manifest = loadCampaign(directory);
  const lock = resolve(directory, ".runner.lock");
  if (existsSync(lock)) {
    const pid = Number(readFileSync(lock, "utf8"));
    try { process.kill(pid, 0); throw new Error(`campaign is already running under PID ${pid}`); }
    catch (error) { if (error.code !== "ESRCH") throw error; unlinkSync(lock); }
  }
  const lockFd = openSync(lock, "wx"); writeFileSync(lockFd, String(process.pid)); closeSync(lockFd);
  let db;
  let stopping = false;
  const stop = () => { stopping = true; };
  process.on("SIGINT", stop); process.on("SIGTERM", stop);
  try {
    db = openCampaignDb(directory, manifest.campaignHash);
    db.prepare("UPDATE attempts SET status='interrupted',finished_at=? WHERE status='running'").run(now());
    mkdirSync(resolve(directory, "playbacks"), { recursive: true });
    const reused = storedRuns(db).length;
    const active = new Set();
    let dispatched = 0;
    let savedSinceCheckpoint = 0;
    let lastCheckpoint = Date.now();
    exportCampaign(directory, manifest, db);
    const workerResults = await Promise.allSettled(Array.from({ length: workers }, async () => {
      try {
      while (!stopping && dispatched < maxNewRuns) {
        const item = pendingJobs(manifest, storedRuns(db)).find(({ matchup, seed }) => !active.has(`${matchup.id}:${seed}`));
        if (!item) return;
        const { matchup, seed } = item;
        const key = `${matchup.id}:${seed}`;
        active.add(key); dispatched++;
        const startedAt = now();
        const start = performance.now();
        const attempt = Number(db.prepare("INSERT INTO attempts(matchup_id,seed,status,started_at) VALUES(?,?,'running',?)")
          .run(matchup.id, seed, startedAt).lastInsertRowid);
        const playbackPath = `playbacks/${matchup.id}-seed-${seed}-attempt-${attempt}.jsonl.gz`;
        const job = { jobId: matchup.id, seed, teams: matchup.teams.map(({ mechanics, count }) => ({ mechanics, count })),
          scenario: matchup.scenario, disableAiOrders: true, disableKiting: true,
          preserveOwnerOrientation: true, retainSnapshots: false };
        let message;
        try { message = await executor(job, resolve(directory, playbackPath), manifest.policy.wallTimeoutSeconds); }
        catch (error) { message = { error: { name: error.name, message: error.message }, lastTick: 0 }; }
        const result = message.result;
        if (result && (!['win', 'draw', 'timeout'].includes(result.outcome)
            || Object.keys(result.remainingByOwner).some(owner => !['2', '3'].includes(owner)))) {
          throw new Error("worker returned an invalid outcome or unexpected army");
        }
        const wallSeconds = (performance.now() - start) / 1000;
        const outcome = message.watchdog || result?.outcome === "timeout" ? "undecided"
          : message.error ? "error" : result.outcome === "draw" ? "draw" : result.winnerOwner === 2 ? "win" : "loss";
        const record = { campaignHash: manifest.campaignHash, matchupId: matchup.id, seed, attempt,
          startedAt, finishedAt: now(), outcome,
          reason: message.watchdog ? "wall_timeout" : result?.outcome === "timeout" ? "simulation_timeout"
            : message.error ? message.error.message : null,
          error: message.error ?? null, winnerOwner: result?.winnerOwner ?? null,
          unitCount: matchup.teams[0].count, opponentCount: matchup.teams[1].count,
          unitStartingHp: result?.startingHpByOwner[2] ?? matchup.teams[0].count * matchup.teams[0].mechanics.hp,
          opponentStartingHp: result?.startingHpByOwner[3] ?? matchup.teams[1].count * matchup.teams[1].mechanics.hp,
          unitRemainingHp: result?.remainingByOwner[2]?.hp ?? null,
          opponentRemainingHp: result?.remainingByOwner[3]?.hp ?? null,
          unitSurvivors: result?.remainingByOwner[2]?.units ?? null,
          opponentSurvivors: result?.remainingByOwner[3]?.units ?? null,
          ticks: result?.ticks ?? message.lastTick, simulationSeconds: (result?.ticks ?? message.lastTick) / 60,
          partialSimulationTime: !result, wallSeconds,
          finalStateHash: result?.finalStateHash ?? null, eventLogHash: result?.eventLogHash ?? null,
          playbackPath: result ? playbackPath : `${playbackPath}.partial`, result: result ?? null };
        record.unitHpPercent = record.unitRemainingHp === null ? null : 100 * record.unitRemainingHp / record.unitStartingHp;
        record.opponentHpPercent = record.opponentRemainingHp === null ? null : 100 * record.opponentRemainingHp / record.opponentStartingHp;
        saveRun(db, record, attempt);
        active.delete(key);
        const progress = exportCampaign(directory, manifest, db);
        console.log(JSON.stringify({ saved: key, outcome, gameSeconds: record.simulationSeconds,
          wallSeconds: Math.round(wallSeconds * 100) / 100, ...progress }));
        onSaved?.(record);
        savedSinceCheckpoint++;
        if (savedSinceCheckpoint >= manifest.policy.checkpointEveryRuns
            || Date.now() - lastCheckpoint >= manifest.policy.checkpointEverySeconds * 1000) {
          atomicJson(resolve(directory, "checkpoint-request.json"), progress);
          savedSinceCheckpoint = 0; lastCheckpoint = Date.now();
        }
      }
      } catch (error) { stopping = true; throw error; }
    }));
    const failure = workerResults.find(r => r.status === "rejected");
    if (failure) throw failure.reason;
    const progress = exportCampaign(directory, manifest, db);
    atomicJson(resolve(directory, "checkpoint-request.json"), progress);
    return { ...progress, reusedRuns: reused, executedRuns: dispatched, stopped: stopping };
  } finally {
    db?.close(); unlinkSync(lock);
    process.off("SIGINT", stop); process.off("SIGTERM", stop);
  }
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i += 2) options[args[i]] = args[i + 1];
  if (!options["--campaign"]) throw new Error("--campaign is required");
  const directory = resolve(options["--campaign"]);
  if (command === "prepare") {
    const manifest = await prepareCampaign(directory, resolve(options["--reference-db"] ?? "data/golden/aoe2_reference_simulation.db"));
    console.log(JSON.stringify({ campaignHash: manifest.campaignHash, matchups: manifest.matchups.length }));
  } else if (command === "run") {
    console.log(JSON.stringify(await runCampaign(directory, {
      ...(options["--workers"] ? { workers: Number(options["--workers"]) } : {}),
      ...(options["--max-new-runs"] ? { maxNewRuns: Number(options["--max-new-runs"]) } : {}),
    })));
  } else throw new Error("command must be prepare or run");
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) await main();
