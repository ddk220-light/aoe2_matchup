import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { validateFormationFixture } from "../src/formation-model.js";


const scenarioModuleUrl = new URL("../src/champion-scenarios.js", import.meta.url);
const unitStateModuleUrl = new URL("../src/combat/unit-state.js", import.meta.url);
const formationUrl = new URL("../fixtures/golden_formation_21v21.json", import.meta.url);
const truthUrl = new URL("../calibration/fixtures/champion_basics.json", import.meta.url);
const mechanicsUrl = new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url);

const CANONICAL_START_POSITIONS = {
  "1v1": [[1628, 3.5, 6.5], [1699, 5.5, 8.5]],
  "2v1": [[1628, 3.5, 6.5], [1629, 2.5, 5.5], [1699, 5.5, 8.5]],
  "2v3": [[1628, 3.5, 6.5], [1629, 2.5, 5.5], [1699, 5.5, 8.5], [1700, 6.5, 8.5], [1701, 2.5, 8.5]],
  "5v3": [[1628, 3.5, 6.5], [1629, 2.5, 5.5], [1630, 5.5, 4.5], [1631, 7.5, 4.5], [1632, 3.5, 5.5], [1699, 5.5, 8.5], [1700, 6.5, 8.5], [1701, 2.5, 8.5]],
  "6v3": [[1628, 3.5, 6.5], [1629, 2.5, 5.5], [1630, 5.5, 4.5], [1631, 7.5, 4.5], [1632, 3.5, 5.5], [1633, 1.5, 6.5], [1699, 5.5, 8.5], [1700, 6.5, 8.5], [1701, 2.5, 8.5]],
};


async function loadScenarioModules() {
  assert.equal(existsSync(fileURLToPath(scenarioModuleUrl)), true);
  assert.equal(existsSync(fileURLToPath(unitStateModuleUrl)), true);
  return {
    ...(await import(scenarioModuleUrl)),
    ...(await import(unitStateModuleUrl)),
  };
}


async function loadInputs() {
  const [formationData, truthData, mechanics] = await Promise.all([
    readFile(formationUrl, "utf8").then(JSON.parse),
    readFile(truthUrl, "utf8").then(JSON.parse),
    readFile(mechanicsUrl, "utf8").then(JSON.parse),
  ]);
  const canonicalTruth = {
    ...truthData,
    ratios: Object.fromEntries(
      Object.entries(truthData.ratios).map(([ratio, row]) => [ratio, {
        ...row,
        canonical_start_positions: row.runs[0].starting_units.map(
          ({ id, x, y }) => [id, x, y],
        ),
      }]),
    ),
  };
  assert.deepEqual(
    Object.fromEntries(
      Object.entries(canonicalTruth.ratios).map(([ratio, row]) => [ratio, row.canonical_start_positions]),
    ),
    CANONICAL_START_POSITIONS,
  );
  return {
    formation: validateFormationFixture(formationData),
    truth: truthData,
    canonicalTruth,
    mechanics,
  };
}


for (const [ratio, counts] of Object.entries({
  "1v1": [1, 1], "2v1": [2, 1], "2v3": [2, 3], "5v3": [5, 3], "6v3": [6, 3],
})) {
  test(`${ratio} uses the literal first source records`, async () => {
    const { createChampionScenario } = await loadScenarioModules();
    const { formation, canonicalTruth: truth, mechanics } = await loadInputs();
    const scenario = createChampionScenario({ ratio, formation, truth, mechanics });

    assert.equal(scenario.units.filter((unit) => unit.owner === 2).length, counts[0]);
    assert.equal(scenario.units.filter((unit) => unit.owner === 3).length, counts[1]);
    assert.deepEqual(
      scenario.units.map(({ referenceId, x, y }) => [referenceId, x, y]),
      truth.ratios[ratio].canonical_start_positions,
    );
    assert.equal(scenario.mapHash, formation.source.sha256);
  });
}


test("placement unit types cannot leak into the Champion roster", async () => {
  const { createChampionScenario } = await loadScenarioModules();
  const { formation, canonicalTruth: truth, mechanics } = await loadInputs();
  const scenario = createChampionScenario({ ratio: "1v1", formation, truth, mechanics });

  assert.deepEqual(new Set(scenario.units.map((unit) => unit.unitMaster)), new Set([567]));
  assert.deepEqual(new Set(scenario.units.map((unit) => unit.hp)), new Set([70]));
});


test("unit state is an immutable, idle Champion with integer action timers", async () => {
  const { createUnitState } = await loadScenarioModules();
  const { mechanics } = await loadInputs();
  const unit = createUnitState({
    referenceId: 1628,
    owner: 2,
    x: 3.5,
    y: 6.5,
    facing: 1.1780972480773926,
    mechanics,
  });

  assert.deepEqual(unit, {
    referenceId: 1628,
    owner: 2,
    x: 3.5,
    y: 6.5,
    facing: 1.1780972480773926,
    mechanics,
    unitMaster: 567,
    hp: 70,
    alive: true,
    targetId: null,
    action: "idle",
    actionTimers: { windup: 0, reload: 0 },
  });
  assert.ok(Object.isFrozen(unit));
  assert.ok(Object.isFrozen(unit.actionTimers));
});


test("direct unit state rejects master 568", async () => {
  const { createUnitState } = await loadScenarioModules();
  const { mechanics } = await loadInputs();

  assert.throws(() => createUnitState({
    referenceId: 1628,
    owner: 2,
    x: 3.5,
    y: 6.5,
    facing: 1.1780972480773926,
    mechanics: { ...mechanics, unit_master: 568 },
  }), /Champion mechanics must use master 567/);
});


test("direct unit state rejects HP 69", async () => {
  const { createUnitState } = await loadScenarioModules();
  const { mechanics } = await loadInputs();

  assert.throws(() => createUnitState({
    referenceId: 1628,
    owner: 2,
    x: 3.5,
    y: 6.5,
    facing: 1.1780972480773926,
    mechanics: { ...mechanics, hp: 69 },
  }), /Champion mechanics must use 70 HP/);
});


test("scenario validation rejects unknown ratios, duplicate IDs, nonfinite positions, and recorded conflicts", async () => {
  const { createChampionScenario } = await loadScenarioModules();
  const { formation, canonicalTruth: truth, mechanics } = await loadInputs();
  const create = (overrides) => createChampionScenario({
    ratio: "1v1",
    formation,
    truth,
    mechanics,
    ...overrides,
  });

  assert.throws(() => create({ ratio: "3v3" }), /unknown ratio/);
  assert.throws(() => create({
    mechanics: { ...mechanics, hp: 69 },
  }), /Champion mechanics must use 70 HP/);
  assert.throws(() => create({
    formation: {
      ...formation,
      source: { ...formation.source, sha256: "0".repeat(64) },
    },
  }), /source hash does not match/);
  assert.throws(() => create({
    truth: {
      ...truth,
      ratios: {
        ...truth.ratios,
        "1v1": { canonical_start_positions: [[1628, 3.5, 6.5], [1628, 5.5, 8.5]] },
      },
    },
  }), /duplicate scenario reference 1628/);
  assert.throws(() => create({
    truth: {
      ...truth,
      ratios: {
        ...truth.ratios,
        "1v1": { canonical_start_positions: [[1628, Number.NaN, 6.5], [1699, 5.5, 8.5]] },
      },
    },
  }), /position for scenario reference 1628 must be finite/);
  assert.throws(() => create({
    ratio: "1v1",
    truth: {
      ...truth,
      ratios: {
        ...truth.ratios,
        "1v1": { canonical_start_positions: [[1628, 3.5, 6.5]] },
      },
    },
  }), /must contain 1 owner 2 and 1 owner 3/);
  assert.throws(() => create({
    ratio: "2v1",
    truth: {
      ...truth,
      ratios: {
        ...truth.ratios,
        "2v1": {
          canonical_start_positions: [[1628, 3.5, 6.5], [1630, 5.5, 4.5], [1699, 5.5, 8.5]],
        },
      },
    },
  }), /locked references/);
  assert.throws(() => create({
    truth: {
      ...truth,
      ratios: {
        ...truth.ratios,
        "1v1": { canonical_start_positions: [[1699, 3.5, 6.5], [1628, 5.5, 8.5]] },
      },
    },
  }), /locked references/);
  assert.throws(() => create({
    ratio: "2v1",
    truth: {
      ...truth,
      ratios: {
        ...truth.ratios,
        "2v1": {
          canonical_start_positions: [[1628, 3.5, 6.5], [1629, 2.5, 5.5], [1699, 5.5, 8.5], [1700, 6.5, 8.5]],
        },
      },
    },
  }), /must contain 2 owner 2 and 1 owner 3/);
  assert.throws(() => create({
    formation: {
      ...formation,
      validation: { valid: false, conflicts: [{ reason: "occupied" }] },
    },
  }), /placement conflicts/);
});


test("raw clean-room truth derives canonical starts from its first recorded run", async () => {
  const { createChampionScenario } = await loadScenarioModules();
  const { formation, truth, mechanics } = await loadInputs();
  const scenario = createChampionScenario({ ratio: "2v3", formation, truth, mechanics });

  assert.deepEqual(
    scenario.units.map(({ referenceId, x, y }) => [referenceId, x, y]),
    CANONICAL_START_POSITIONS["2v3"],
  );
});
