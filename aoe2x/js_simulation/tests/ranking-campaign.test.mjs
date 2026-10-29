import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, cpSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { prepareCampaign, loadCampaign, runCampaign, requiredSeeds, summarize,
  openCampaignDb, storedRuns, saveRun } from "../node/ranking-campaign.mjs";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const reference = resolve(root, "data/golden/aoe2_reference_simulation.db");
const temporary = () => mkdtempSync(resolve(tmpdir(), "ranking-campaign-test-"));
function fakeExecutor(calls) {
  return async job => {
    calls.push(`${job.jobId}:${job.seed}`);
    const winnerOwner = job.jobId === "champion_mirror" && job.seed % 2 ? 3 : 2;
    const startingHpByOwner = Object.fromEntries(job.teams.map((t, i) => [i + 2, t.count * t.mechanics.hp]));
    return { lastTick: 60, result: { outcome: "win", winnerOwner, ticks: 60,
      startingHpByOwner, remainingByOwner: {
        2: { hp: winnerOwner === 2 ? 10 : 0, units: winnerOwner === 2 ? 1 : 0 },
        3: { hp: winnerOwner === 3 ? 10 : 0, units: winnerOwner === 3 ? 1 : 0 },
      }, finalStateHash: job.jobId, eventLogHash: String(job.seed) } };
  };
}

test("pilot freezes ten valid matchups, 27-unit formula, actual Cavalier and zero buffers", async () => {
  const directory = temporary();
  try {
    const manifest = await prepareCampaign(directory, reference);
    assert.equal(manifest.matchups.length, 10);
    for (const matchup of manifest.matchups) {
      assert.equal(Math.max(...matchup.teams.map(t => t.count)), 27);
      const [a, b] = matchup.teams.map(t => t.weightedCost).sort((a, b) => a - b);
      assert.equal(Math.min(...matchup.teams.map(t => t.count)), Math.round(27 * Math.sqrt(a / b)));
      assert.deepEqual(Object.keys(matchup.scenario.auxiliaryArmiesByOwner ?? {}), []);
      assert.ok(matchup.scenario.placementByOwner[2].length >= matchup.teams[0].count);
      assert.ok(matchup.scenario.placementByOwner[3].length >= matchup.teams[1].count);
    }
    const cavalier = manifest.matchups.find(m => m.id === "arbalester_cavalier").teams[1];
    assert.equal(cavalier.mechanics.unit_name, "Cavalier");
    assert.equal(cavalier.mechanics.hp, 140);
    assert.equal(manifest.matchups.find(m => m.id === "jarl_hussar").group, "Ranged");
    const blackwood = manifest.matchups.find(m => m.id === "blackwood_hussar").teams[0];
    assert.equal(blackwood.mechanics.cost.wood, blackwood.referencePurchaseCost.wood / 2);
    assert.equal(blackwood.mechanics.population_space, 0.5);
    assert.equal(loadCampaign(directory).campaignHash, manifest.campaignHash);
    const altered = { ...manifest, policy: { ...manifest.policy, cap: 30 } };
    writeFileSync(resolve(directory, "manifest.json"), JSON.stringify(altered));
    assert.throws(() => loadCampaign(directory), /manifest hash mismatch/);
  } finally { rmSync(directory, { recursive: true }); }
});

test("expansion needs three saved initial seeds and ignores timeouts as winning outcomes", () => {
  const matchup = { id: "m" };
  const rows = outcomes => outcomes.map((outcome, seed) => ({ matchupId: "m", outcome, seed }));
  assert.equal(requiredSeeds(matchup, rows(["win", "loss"])).length, 3);
  assert.equal(requiredSeeds(matchup, rows(["win", "win", "win"])).length, 3);
  assert.equal(requiredSeeds(matchup, rows(["win", "loss", "win"])).length, 10);
  assert.equal(requiredSeeds(matchup, rows(["win", "draw", "win"])).length, 10);
  assert.equal(requiredSeeds(matchup, rows(["win", "undecided", "win"])).length, 3);
});

test("run interruption preserves individual seeds; resume skips them and expands only the flip", async () => {
  const directory = temporary();
  const portable = temporary();
  const calls = [];
  try {
    const manifest = await prepareCampaign(directory, reference);
    let saved = 0;
    await assert.rejects(runCampaign(directory, { workers: 1, executor: fakeExecutor(calls),
      onSaved() { if (++saved === 2) throw new Error("simulated interruption"); },
    }), /simulated interruption/);
    const before = readFileSync(resolve(directory, "runs.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
    assert.equal(before.length, 2);
    assert.equal(existsSync(resolve(directory, ".runner.lock")), false);
    const result = await runCampaign(directory, { workers: 3, executor: fakeExecutor(calls) });
    assert.equal(result.reusedRuns, 2);
    assert.equal(result.executedRuns, 35);
    assert.equal(result.recordedRuns, 37);
    assert.equal(new Set(calls).size, calls.length);
    let db = openCampaignDb(directory, manifest.campaignHash);
    const all = storedRuns(db);
    for (const row of before) assert.deepEqual(all.find(r => r.matchupId === row.matchupId && r.seed === row.seed), row);
    assert.throws(() => saveRun(db, all[0]), /UNIQUE/);
    db.close();
    const secondResume = await runCampaign(directory, { workers: 3, executor: fakeExecutor(calls) });
    assert.equal(secondResume.executedRuns, 0);
    for (const name of ["manifest.json", "runs.jsonl", "attempts.json"]) cpSync(resolve(directory, name), resolve(portable, name));
    const recovered = await runCampaign(portable, { workers: 1, executor: fakeExecutor(calls) });
    assert.equal(recovered.executedRuns, 0);
    assert.equal(recovered.recordedRuns, 37);
    db = openCampaignDb(portable, manifest.campaignHash);
    assert.deepEqual(storedRuns(db), all);
    assert.equal(db.prepare("SELECT COUNT(*) AS n FROM attempts").get().n, 37);
    db.close();
  } finally { rmSync(directory, { recursive: true }); rmSync(portable, { recursive: true }); }
});

test("wall timeouts and exceptions persist as review cases without poisoning HP averages", async () => {
  const directory = temporary();
  try {
    const manifest = await prepareCampaign(directory, reference);
    const executor = async job => job.seed === 0 ? { watchdog: true, lastTick: 120 }
      : job.seed === 1 ? Promise.reject(new Error("test worker failure"))
        : fakeExecutor([])(job);
    const result = await runCampaign(directory, { workers: 1, maxNewRuns: 3, executor });
    assert.equal(result.recordedRuns, 3);
    const db = openCampaignDb(directory, manifest.campaignHash);
    const rows = storedRuns(db);
    assert.deepEqual(rows.map(r => r.outcome), ["undecided", "error", "win"]);
    const summary = summarize(manifest, rows)[0];
    assert.equal(summary.state, "needs_review");
    assert.equal(summary.undecided, 2);
    assert.equal(summary.meanUnitHpPercentDecided, rows[2].unitHpPercent);
    db.close();
    writeFileSync(resolve(directory, ".runner.lock"), String(process.pid));
    await assert.rejects(runCampaign(directory, { executor }), /already running/);
  } finally { rmSync(directory, { recursive: true }); }
});
