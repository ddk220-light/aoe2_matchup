import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { runHeadlessJob } from "../node/run-job.mjs";
import { parallelJobs, parseInput } from "../node/headless-runner.mjs";
import {
  MECHANICS_SCHEMA_VERSION,
  unitDescriptorFromMechanics,
  validateMechanicsProfile,
} from "../src/mechanics-schema.js";


const root = new URL("../", import.meta.url);


async function profile(filename, identity) {
  const fixture = JSON.parse(await readFile(
    new URL(`../fixtures/unit_stats/${filename}`, import.meta.url), "utf8",
  ));
  delete fixture.provenance;
  delete fixture.mode_validation;
  return {
    ...fixture,
    mechanics_schema_version: MECHANICS_SCHEMA_VERSION,
    mode: "default",
    behavior_class: identity.behavior_class,
    unit_slug: identity.unit_slug,
    unit_name: identity.unit_name,
    cost: identity.cost,
    population_space: fixture.population_space ?? 1,
    ranged: fixture.ranged ?? null,
  };
}


test("database mechanics schema creates an engine descriptor", async () => {
  const champion = await profile("champion_chinese_imperial.json", {
    behavior_class: "melee",
    unit_slug: "champion",
    unit_name: "Champion",
    cost: { food: 60, wood: 0, gold: 20 },
  });
  assert.equal(validateMechanicsProfile(champion), champion);
  assert.deepEqual(unitDescriptorFromMechanics(champion), {
    slug: "champion",
    label: "Champion",
    civ: "Chinese",
    master: champion.unit_master,
    class: "melee",
    baseCost: { food: 60, wood: 0, gold: 20 },
  });
});


test("headless jobs are deterministic with injected mechanics", async () => {
  const [champion, paladin] = await Promise.all([
    profile("champion_chinese_imperial.json", {
      behavior_class: "melee",
      unit_slug: "champion",
      unit_name: "Champion",
      cost: { food: 60, wood: 0, gold: 20 },
    }),
    profile("paladin_spanish_imperial.json", {
      behavior_class: "melee",
      unit_slug: "paladin",
      unit_name: "Paladin",
      cost: { food: 60, wood: 0, gold: 75 },
    }),
  ]);
  const job = {
    teams: [
      { mechanics: champion, count: 3 },
      { mechanics: paladin, count: 2 },
    ],
    engagementMode: "direct",
    seed: 123,
  };
  const first = await runHeadlessJob(job);
  const second = await runHeadlessJob(job);
  assert.equal(first.finalStateHash, second.finalStateHash);
  assert.equal(first.eventLogHash, second.eventLogHash);
  assert.equal(first.winnerOwner, second.winnerOwner);

  const jobs = [0, 1, 2].map((seed) => ({ ...job, seed }));
  const serial = await parallelJobs(jobs, 1);
  const parallel = await parallelJobs(jobs, 2);
  assert.deepEqual(
    parallel.map(({ finalStateHash, eventLogHash }) => ({ finalStateHash, eventLogHash })),
    serial.map(({ finalStateHash, eventLogHash }) => ({ finalStateHash, eventLogHash })),
  );
});


test("headless runner accepts JSON lines and isolates invalid jobs", async () => {
  assert.deepEqual(parseInput('{"jobId":"a"}\n{"jobId":"b"}'), [
    { jobId: "a" },
    { jobId: "b" },
  ]);
  const results = await parallelJobs([{ jobId: "bad" }, { jobId: "also-bad" }], 2);
  assert.deepEqual(results.map(({ jobId }) => jobId), ["bad", "also-bad"]);
  assert.equal(results.every(({ error }) => error?.message), true);
});


test("mechanics schema rejects provenance and incompatible versions", async () => {
  const champion = await profile("champion_chinese_imperial.json", {
    behavior_class: "melee",
    unit_slug: "champion",
    unit_name: "Champion",
    cost: { food: 60, wood: 0, gold: 20 },
  });
  assert.throws(
    () => validateMechanicsProfile({ ...champion, provenance: {} }),
    /must not contain calibration provenance/,
  );
  assert.throws(
    () => validateMechanicsProfile({ ...champion, mechanics_schema_version: 999 }),
    /unsupported mechanics schema/,
  );
});
