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


test("a direct engine-only battle link can launch a 20v20 matchup without tape state", () => {
  assert.deepEqual(
    battleStateModule.directFightRequest(
      "https://starlight.tail82a190.ts.net/golden-map/"
        + "?mode=battle&side2=champion&side3=paladin&n2=20&n3=20",
    ),
    {
      endpoint: "api/fight",
      side2: "champion",
      side3: "paladin",
      n2: 20,
      n3: 20,
      query: "side2=champion&side3=paladin&n2=20&n3=20",
    },
  );
  for (const url of [
    "http://127.0.0.1:5011/",
    "http://127.0.0.1:5011/?mode=battle&side2=champion&side3=paladin&n2=20",
    "http://127.0.0.1:5011/?mode=battle&side2=champion&side3=paladin&n2=0&n3=20",
    "http://127.0.0.1:5011/?mode=battle&side2=champion&side3=paladin&n2=20&n3=20&extra=1",
  ]) {
    assert.equal(battleStateModule.directFightRequest(url), null);
  }
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


test("the Hand Cannoneer versus Champion observation link is locked to cohesive combat", () => {
  assert.equal(typeof battleStateModule.kitingFightRequest, "function");
  assert.deepEqual(
    battleStateModule.kitingFightRequest(
      "http://127.0.0.1:5011/?mode=hand-cannoneer-vs-champion-kiting",
    ),
    {
      endpoint: "api/hand-cannoneer-vs-champion-kiting",
      navigation: "cohesive",
      query: "navigation=cohesive",
    },
  );
  assert.deepEqual(
    battleStateModule.kitingFightRequest(
      "https://dragonstar.tail82a190.ts.net/golden-map/"
        + "?mode=hand-cannoneer-vs-champion-kiting&navigation=per-unit-grid",
    ),
    {
      endpoint: "api/hand-cannoneer-vs-champion-kiting",
      navigation: "per-unit-grid",
      query: "navigation=per-unit-grid",
    },
  );
  for (const url of [
    "http://127.0.0.1:5011/",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-vs-champion-kiting&count=21",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-vs-champion-kiting&unit=arbalester",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-vs-champion-kiting&navigation=unknown",
    "http://127.0.0.1:5011/?mode=hand-cannoneer-vs-champion-kiting&navigation=cohesive&navigation=baseline",
  ]) {
    assert.equal(battleStateModule.kitingFightRequest(url), null);
  }
});


test("the generalized kiting lab accepts only supported ranged-versus-melee pairs", () => {
  assert.deepEqual(
    battleStateModule.kitingFightRequest(
      "https://dragonstar.tail82a190.ts.net/golden-map/"
        + "?mode=ranged-vs-melee-kiting&ranged=heavy_cav_archer&melee=paladin"
        + "&navigation=cohesive&n2=20&n3=15&enemyTransit=pairwise",
    ),
    {
      endpoint: "api/ranged-vs-melee-kiting",
      ranged: "heavy_cav_archer",
      melee: "paladin",
      navigation: "cohesive",
      enemyTransit: "pairwise",
      n2: 20,
      n3: 15,
      query: "ranged=heavy_cav_archer&melee=paladin&navigation=cohesive&enemyTransit=pairwise&n2=20&n3=15",
    },
  );
  assert.deepEqual(
    battleStateModule.kitingFightRequest(
      "https://dragonstar.tail82a190.ts.net/golden-map/"
        + "?mode=ranged-vs-melee-kiting&ranged=heavy_scorpion&melee=paladin"
        + "&navigation=cohesive&n2=12&n3=17",
    ),
    {
      endpoint: "api/ranged-vs-melee-kiting",
      ranged: "heavy_scorpion",
      melee: "paladin",
      navigation: "cohesive",
      n2: 12,
      n3: 17,
      query: "ranged=heavy_scorpion&melee=paladin&navigation=cohesive&n2=12&n3=17",
    },
  );
  assert.deepEqual(
    battleStateModule.kitingFightRequest(
      "https://dragonstar.tail82a190.ts.net/golden-map/"
        + "?mode=ranged-vs-melee-kiting&ranged=heavy_scorpion&melee=paladin"
        + "&navigation=cohesive",
    ),
    {
      endpoint: "api/ranged-vs-melee-kiting",
      ranged: "heavy_scorpion",
      melee: "paladin",
      navigation: "cohesive",
      query: "ranged=heavy_scorpion&melee=paladin&navigation=cohesive",
    },
  );
  assert.deepEqual(
    battleStateModule.kitingFightRequest(
      "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting",
    ),
    {
      endpoint: "api/ranged-vs-melee-kiting",
      ranged: "hand_cannoneer",
      melee: "champion",
      navigation: "cohesive",
      query: "ranged=hand_cannoneer&melee=champion&navigation=cohesive",
    },
  );
  for (const [ranged, n2, n3] of [
    ["imp_elite_skirm", 21, 15],
    ["siege_onager", 4, 21],
  ]) {
    assert.deepEqual(
      battleStateModule.kitingFightRequest(
        `http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=${ranged}`
          + `&melee=champion&navigation=cohesive&n2=${n2}&n3=${n3}`,
      ),
      {
        endpoint: "api/ranged-vs-melee-kiting",
        ranged,
        melee: "champion",
        navigation: "cohesive",
        n2,
        n3,
        query: `ranged=${ranged}&melee=champion&navigation=cohesive&n2=${n2}&n3=${n3}`,
      },
    );
  }
  for (const url of [
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=champion&melee=paladin",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=arbalester&melee=arbalester",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=arbalester&melee=unknown",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=arbalester&ranged=heavy_scorpion",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&navigation=unknown",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&n2=10",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&n2=0&n3=10",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&n2=1.5&n3=10",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&n2=21&n3=22",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=heavy_scorpion&n2=17&n3=10",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=siege_onager&n2=17&n3=10",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&n2=10&n2=11&n3=10",
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&enemyTransit=unknown",
  ]) {
    assert.equal(battleStateModule.kitingFightRequest(url), null);
  }
});


test("kiting setup links preserve manual counts and clamp them to the selected formation", () => {
  assert.equal(typeof battleStateModule.kitingFightHref, "function");
  assert.equal(
    battleStateModule.kitingFightHref(
      "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&navigation=cohesive"
        + "&ranged=hand_cannoneer&melee=champion&n2=21&n3=18",
      { ranged: "heavy_scorpion", melee: "champion", n2: 21, n3: 18, max2: 16, max3: 21 },
    ),
    "http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&navigation=cohesive"
      + "&ranged=heavy_scorpion&melee=champion&n2=16&n3=18",
  );
  assert.equal(
    battleStateModule.kitingFightHref(
      "https://dragonstar.tail82a190.ts.net/golden-map/"
        + "?mode=ranged-vs-melee-kiting&navigation=cohesive"
        + "&ranged=heavy_scorpion&melee=champion&n2=8&n3=21",
      { ranged: "arbalester", melee: "paladin" },
    ),
    "https://dragonstar.tail82a190.ts.net/golden-map/"
      + "?mode=ranged-vs-melee-kiting&navigation=cohesive"
      + "&ranged=arbalester&melee=paladin",
  );
});


test("wrong-winner review URLs select one exact golden row and reject extra state", () => {
  assert.equal(typeof battleStateModule.phase2WrongWinnerRequest, "function");
  assert.equal(typeof battleStateModule.phase2WrongWinnerHref, "function");
  assert.deepEqual(
    battleStateModule.phase2WrongWinnerRequest(
      "https://dragonstar.tail82a190.ts.net/golden-map/"
        + "?mode=phase2-wrong-winners&row=elite_boyar_vs_heavy_cav_archer",
    ),
    {
      endpoint: "api/phase2/wrong-winner",
      rowId: "elite_boyar_vs_heavy_cav_archer",
      query: "row=elite_boyar_vs_heavy_cav_archer",
    },
  );
  assert.equal(
    battleStateModule.phase2WrongWinnerHref(
      "https://dragonstar.tail82a190.ts.net/golden-map/?old=1",
      "elite_war_wagon_vs_champion",
    ),
    "https://dragonstar.tail82a190.ts.net/golden-map/"
      + "?mode=phase2-wrong-winners&row=elite_war_wagon_vs_champion",
  );
  for (const url of [
    "?mode=phase2-wrong-winners",
    "?mode=phase2-wrong-winners&row=bad row",
    "?mode=phase2-wrong-winners&row=elite_boyar_vs_heavy_cav_archer&extra=1",
    "?mode=phase2-wrong-winners&row=a&row=b",
  ]) {
    assert.equal(battleStateModule.phase2WrongWinnerRequest(url), null, url);
  }
});


test("problem-matchup URLs select one current ranged row and remain shareable", () => {
  assert.deepEqual(
    battleStateModule.problemMatchupRequest(
      "https://starlight.tail82a190.ts.net/golden-map/"
        + "?mode=problem-matchups&matchup=hand_cannoneer_vs_elite_steppe",
    ),
    {
      endpoint: "api/problem-matchup",
      matchupId: "hand_cannoneer_vs_elite_steppe",
      query: "matchup=hand_cannoneer_vs_elite_steppe",
    },
  );
  assert.equal(
    battleStateModule.problemMatchupHref(
      "https://starlight.tail82a190.ts.net/golden-map/?old=1#inspect",
      "arbalester_vs_heavy_cav_archer",
    ),
    "https://starlight.tail82a190.ts.net/golden-map/"
      + "?mode=problem-matchups&matchup=arbalester_vs_heavy_cav_archer#inspect",
  );
  assert.deepEqual(
    battleStateModule.problemMatchupRequest(
      "https://starlight.tail82a190.ts.net/golden-map/"
        + "?mode=problem-matchups&matchup=arbalester_vs_heavy_cav_archer&seed=4",
    ),
    {
      endpoint: "api/problem-matchup",
      matchupId: "arbalester_vs_heavy_cav_archer",
      openingSeed: 4,
      query: "matchup=arbalester_vs_heavy_cav_archer&seed=4",
    },
  );
  assert.equal(
    battleStateModule.problemMatchupHref(
      "https://starlight.tail82a190.ts.net/golden-map/?old=1#inspect",
      "arbalester_vs_heavy_cav_archer",
      4,
    ),
    "https://starlight.tail82a190.ts.net/golden-map/"
      + "?mode=problem-matchups&matchup=arbalester_vs_heavy_cav_archer&seed=4#inspect",
  );
  for (const url of [
    "?mode=problem-matchups",
    "?mode=problem-matchups&matchup=bad row",
    "?mode=problem-matchups&matchup=arbalester_vs_paladin&extra=1",
    "?mode=problem-matchups&matchup=avsb",
    "?mode=problem-matchups&matchup=a_vs_b&matchup=c_vs_d",
    "?mode=problem-matchups&matchup=a_vs_b&seed=-1",
    "?mode=problem-matchups&matchup=a_vs_b&seed=4.5",
    "?mode=problem-matchups&matchup=a_vs_b&seed=3&seed=4",
  ]) {
    assert.equal(battleStateModule.problemMatchupRequest(url), null, url);
  }
});
