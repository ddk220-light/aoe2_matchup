import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { hydrate, jobFor, phasePending, recordFromMessage, validateRecord, restoreFullDb, POOLS, OPPONENTS } from "../node/full-ranking-campaign.mjs";
import { storedRuns } from "../node/ranking-campaign.mjs";

const pilotPath = fileURLToPath(new URL("../calibration/campaigns/unit-rankings-pilot-2026-10-29/", import.meta.url));
const pilot = JSON.parse(readFileSync(resolve(pilotPath, "manifest.json"), "utf8"));
const old = pilot.matchups[0];
const profiles = Object.fromEntries(old.teams.map((team, i) => [String(i), team]));
const m = { id: "mirror", teamKeys: ["0", "1"], counts: [27, 27], weightedCosts: [65, 65], scenarioHash: old.scenarioHash };
const manifest = { campaignHash: "test-campaign", profiles, scenarios: { [old.scenarioHash]: old.scenario }, matchups: [m] };
const saved = readFileSync(resolve(pilotPath, "runs.jsonl"), "utf8").trim().split("\n").map(JSON.parse)
  .find(r => r.matchupId === "champion_mirror" && r.seed === 0);
const timing = { attempt: 1, startedAt: "2026-10-29T00:00:00Z", finishedAt: "2026-10-29T00:00:01Z", wallSeconds: 1 };

test("normalized jobs preserve the complete validated pilot inputs and requested opponent pools", () => {
  assert.deepEqual(hydrate(manifest, m).scenario, old.scenario);
  assert.deepEqual(jobFor(manifest, m, 2).teams, old.teams.map(({ mechanics, count }) => ({ mechanics, count })));
  assert.equal(jobFor(manifest, m, 2).seed, 2);
  assert.deepEqual(POOLS.Infantry, ["champion", "hussar", "arbalester", "paladin", "cavalier"]);
  assert.equal(POOLS.Ranged.length, 7);
  assert.equal(POOLS.Cavalry.length, 7);
  assert.deepEqual(OPPONENTS.cavalier, ["Turks", "paladin"]);
  assert.equal(new Set(Object.values(OPPONENTS).map(JSON.stringify)).size, 10);
});

test("adaptive queue excludes saved and active seeds, then schedules exactly seven extras for a flip", () => {
  const records = new Map([[m.id, [{ matchupId: m.id, seed: 0, outcome: "win" }]]]);
  assert.deepEqual(phasePending([m], records, new Set(["mirror:1"])).map(r => r.seed), [2]);
  records.get(m.id).push({ matchupId: m.id, seed: 1, outcome: "loss" }, { matchupId: m.id, seed: 2, outcome: "win" });
  assert.deepEqual(phasePending([m], records).map(r => r.seed), [3, 4, 5, 6, 7, 8, 9]);
  records.get(m.id)[1].outcome = "undecided";
  assert.equal(phasePending([m], records).length, 0);
});

test("watchdogs and errors remain review cases; corrupted completed records are rejected", () => {
  const row = recordFromMessage(manifest, m, 0, { result: saved.result }, timing);
  assert.equal(row.unitHpPercent, saved.unitHpPercent);
  assert.equal(recordFromMessage(manifest, m, 1, { watchdog: true }, timing).outcome, "undecided");
  assert.equal(recordFromMessage(manifest, m, 1, { error: { message: "worker failed" } }, timing).outcome, "error");
  assert.throws(() => validateRecord(manifest, m, { ...row, unitCount: 30 }), /counts/);
  assert.throws(() => validateRecord(manifest, m, { ...row, unitRemainingHp: NaN }), /invalid/);
  assert.throws(() => validateRecord(manifest, m, { ...row, campaignHash: "wrong" }), /identity/);
});

test("portable journals recover every committed run and attempt, ignore only an interrupted last line, and resume without duplicates", () => {
  const directory = mkdtempSync(resolve(tmpdir(), "full-ranking-recovery-"));
  try {
    mkdirSync(resolve(directory, "runs"));
    const row = recordFromMessage(manifest, m, 0, { result: saved.result }, timing);
    writeFileSync(resolve(directory, "runs", "phase.jsonl"), `${JSON.stringify(row)}\n{"interrupted":`);
    writeFileSync(resolve(directory, "attempts.json"), JSON.stringify([{ id: 1, matchup_id: m.id, seed: 0,
      status: row.outcome, started_at: timing.startedAt, finished_at: timing.finishedAt, detail: null }]));
    let db = restoreFullDb(directory, manifest);
    assert.deepEqual(storedRuns(db), [row]);
    assert.equal(db.prepare("SELECT COUNT(*) n FROM attempts").get().n, 1);
    db.close();
    db = restoreFullDb(directory, manifest);
    assert.equal(storedRuns(db).length, 1);
    assert.deepEqual(phasePending([m], new Map([[m.id, storedRuns(db)]])).map(r => r.seed), [1, 2]);
    db.close();
  } finally { rmSync(directory, { recursive: true }); }
});
