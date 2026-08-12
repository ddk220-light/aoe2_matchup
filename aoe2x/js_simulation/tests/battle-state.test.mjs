import assert from "node:assert/strict";
import test from "node:test";
import * as battleStateModule from "../viewer/battle-state.js";

import {
  buildFightQuery,
  createBattleState,
  searchCatalogue,
  selectCivilization,
  selectUnit,
  selectionCapacity,
  setArmyCount,
  setBattleMode,
  setResourceBudget,
  unitsForCivilization,
} from "../viewer/battle-state.js";


const catalogue = {
  schemaVersion: 1,
  civilizations: [
    {
      name: "Chinese",
      units: [
        { catalogueKey: "chinese:champion:1", name: "Champion", slug: "militia", type: "standard", className: "Infantry" },
        { catalogueKey: "chinese:chu-ko-nu:2", name: "Elite Chu Ko Nu", slug: "chu_ko_nu", type: "unique", className: "Archer" },
      ],
    },
    {
      name: "Slavs",
      units: [
        { catalogueKey: "slavs:siege-onager:3", name: "Siege Onager", slug: "mangonel", type: "standard", className: "Siege Weapon" },
      ],
    },
  ],
  enabled: [
    { catalogueKey: "chinese:champion:1", engineSlug: "champion", civ: "Chinese", name: "Champion", class: "melee", baseCost: { food: 50, wood: 0, gold: 20 } },
    { catalogueKey: "slavs:siege-onager:3", engineSlug: "siege_onager", civ: "Slavs", name: "Siege Onager", class: "siege_ranged", baseCost: { food: 0, wood: 160, gold: 135 } },
  ],
};

const units = {
  capacityByFamily: {
    waves: { side2: 21, side3: 21 },
    kite: { side2: 21, side3: 21 },
    rvr: { side2: 21, side3: 21 },
    siege: { side2: 16, side3: 21 },
  },
};


test("civilization-first browsing keeps unsupported units visible but unavailable", () => {
  let state = createBattleState({ catalogue, units });
  state = selectCivilization(state, 1, "Chinese");

  assert.deepEqual(unitsForCivilization(state, "Chinese").map(({ name, enabled }) => [name, enabled]), [
    ["Champion", true],
    ["Elite Chu Ko Nu", false],
  ]);
  assert.throws(
    () => selectUnit(state, 1, "chinese:chu-ko-nu:2"),
    /not calibrated/,
  );
  state = selectUnit(state, 1, "chinese:champion:1");
  assert.equal(state.teams[1].engineSlug, "champion");
});


test("search returns disabled units instead of hiding them", () => {
  const state = createBattleState({ catalogue, units });
  assert.deepEqual(searchCatalogue(state, "chu ko").map(({ type, name, enabled }) => [
    type, name, enabled,
  ]), [["unit", "Elite Chu Ko Nu", false]]);
  assert.deepEqual(searchCatalogue(state, "slav").map(({ type, name, enabled }) => [
    type, name, enabled,
  ]), [
    ["civilization", "Slavs", true],
    ["unit", "Siege Onager", true],
  ]);
});


test("role-normalized capacity follows the siege unit into the second picker", () => {
  let state = createBattleState({ catalogue, units });
  state = selectCivilization(state, 1, "Chinese");
  state = selectUnit(state, 1, "chinese:champion:1");
  state = selectCivilization(state, 2, "Slavs");
  state = selectUnit(state, 2, "slavs:siege-onager:3");

  assert.deepEqual(selectionCapacity(state), {
    family: "siege",
    team1: 21,
    team2: 16,
    orientationNormalised: true,
  });
  state = setArmyCount(state, 1, 20);
  state = setArmyCount(state, 2, 16);
  assert.equal(
    buildFightQuery(state),
    "side2=champion&side3=siege_onager&n2=20&n3=16",
  );
  assert.throws(() => setArmyCount(state, 2, 17), /count must be an integer 1-16/);
});


test("equal resources sends only a validated budget", () => {
  let state = createBattleState({ catalogue, units });
  state = selectCivilization(state, 1, "Chinese");
  state = selectUnit(state, 1, "chinese:champion:1");
  state = selectCivilization(state, 2, "Slavs");
  state = selectUnit(state, 2, "slavs:siege-onager:3");
  state = setBattleMode(state, "resources");
  state = setResourceBudget(state, 4200);

  assert.equal(
    buildFightQuery(state),
    "side2=champion&side3=siege_onager&budget=4200",
  );
  assert.throws(() => setResourceBudget(state, 99), /budget must be an integer 100-20000/);
  assert.throws(() => setBattleMode(state, "resources_upgrades"), /not calibrated/);
});


test("the dedicated Hand Cannoneer movement link exposes three saved navigation variants", () => {
  assert.equal(typeof battleStateModule.soloMovementRequest, "function");
  assert.deepEqual(
    battleStateModule.soloMovementRequest(
      "http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement",
    ),
    {
      endpoint: "api/solo-hand-cannoneers",
      unit: "hand_cannoneer",
      navigation: "cohesive",
      query: "unit=hand_cannoneer&navigation=cohesive",
    },
  );
  const units = [
    "hand_cannoneer",
    "arbalester",
    "heavy_cav_archer",
    "heavy_scorpion",
    "imp_elite_skirm",
  ];
  for (const [unit, navigation] of units.map((unit, index) => [
    unit,
    ["baseline", "per-unit-grid", "cohesive"][index % 3],
  ])) {
    assert.deepEqual(
      battleStateModule.soloMovementRequest(
        `http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=${unit}&navigation=${navigation}`,
      ),
      {
        endpoint: "api/solo-hand-cannoneers",
        unit,
        navigation,
        query: `unit=${unit}&navigation=${navigation}`,
      },
    );
  }
  for (const url of [
    "http://127.0.0.1:5011/",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&count=20",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=champion",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=arbalester&unit=heavy_cav_archer",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=unknown",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=cohesive&count=21",
    "http://127.0.0.1:5011/?mode=champion-solo-movement",
  ]) {
    assert.equal(battleStateModule.soloMovementRequest(url), null);
  }
});
