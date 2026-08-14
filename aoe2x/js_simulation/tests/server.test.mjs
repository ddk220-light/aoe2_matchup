import assert from "node:assert/strict";
import { once } from "node:events";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

import * as serverModule from "../server.mjs";


const { createMapServer } = serverModule;


const root = fileURLToPath(new URL("..", import.meta.url));

async function withServer(run) {
  const server = createMapServer({ root });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  try {
    await run(`http://127.0.0.1:${address.port}`);
  } finally {
    server.close();
    await once(server, "close");
  }
}


test("server exposes the website-style Battle Simulation shell and literal map fixture", async () => {
  await withServer(async (baseUrl) => {
    const page = await fetch(`${baseUrl}/`);
    assert.equal(page.status, 200);
    assert.match(page.headers.get("content-type"), /text\/html/);
    const pageBody = await page.text();
    assert.match(pageBody, /Battle Simulation/);
    assert.match(pageBody, /location\.pathname\.endsWith\("\/"\)/);
    assert.match(pageBody, /document\.head\.append\(mountBase\)/);
    assert.match(pageBody, /href="static\/css\/base\.css"/);
    assert.match(pageBody, /href="static\/css\/simulate\.css"/);
    assert.match(pageBody, /href="viewer\/styles\.css"/);
    assert.match(pageBody, /src="viewer\/app\.js"/);

    const appResponse = await fetch(`${baseUrl}/viewer/app.js`);
    const appBody = await appResponse.text();
    assert.match(appBody, /fetch\("api\/map"/);

    const mapResponse = await fetch(`${baseUrl}/api/map`);
    assert.equal(mapResponse.status, 200);
    assert.equal(mapResponse.headers.get("cache-control"), "no-store");
    const fixture = await mapResponse.json();
    assert.equal(fixture.schema_version, 1);
    assert.equal(fixture.map.gaia_objects.length, 101);

    const formationResponse = await fetch(`${baseUrl}/api/formation`);
    assert.equal(formationResponse.status, 200);
    const formation = await formationResponse.json();
    assert.equal(formation.sides["2"].length, 21);
    assert.equal(formation.sides["3"].length, 21);

    const module = await fetch(`${baseUrl}/src/map-model.js`);
    assert.equal(module.status, 200);
    assert.match(module.headers.get("content-type"), /javascript/);
  });
});


test("server rejects paths outside its explicit public surface", async () => {
  await withServer(async (baseUrl) => {
    for (const path of [
      "/package.json",
      "/..%2Fpackage.json",
      "/fixtures/source/golden_meleevsmelee.aoe2scenario",
      "/missing-file.js",
    ]) {
      const response = await fetch(`${baseUrl}${path}`);
      assert.equal(response.status, 404, path);
      assert.equal(response.headers.get("cache-control"), "no-store");
    }
  });
});


test("viewer shell exposes unit and count controls for the generalized kiting lab", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/`);
    assert.equal(response.status, 200);
    const body = await response.text();
    assert.match(body, /id="kitingRangedUnit"/);
    assert.match(body, /id="kitingMeleeUnit"/);
    assert.match(body, /id="kitingRangedCount"/);
    assert.match(body, /id="kitingMeleeCount"/);
    assert.match(body, /aria-label="Kiting ranged unit"/);
    assert.match(body, /aria-label="Chasing melee unit"/);
    assert.match(body, /aria-label="Kiting unit count"/);
    assert.match(body, /aria-label="Chasing unit count"/);
  });
});


test("kiting viewer request selection validates manual counts without running a battle", () => {
  assert.equal(typeof serverModule.kitingObservationSelection, "function");
  assert.deepEqual(
    serverModule.kitingObservationSelection(new URL(
      "http://127.0.0.1/api/ranged-vs-melee-kiting"
        + "?ranged=heavy_scorpion&melee=champion&navigation=cohesive&n2=16&n3=21",
    )),
    {
      rangedSlug: "heavy_scorpion",
      meleeSlug: "champion",
      navigation: "cohesive",
      n2: 16,
      n3: 21,
    },
  );
  assert.deepEqual(
    serverModule.kitingObservationSelection(new URL(
      "http://127.0.0.1/api/ranged-vs-melee-kiting",
    )),
    {
      rangedSlug: "hand_cannoneer",
      meleeSlug: "champion",
      navigation: "cohesive",
    },
  );
  for (const query of [
    "n2=10",
    "n2=0&n3=10",
    "n2=10&n3=22",
    "n2=1.5&n3=10",
    "ranged=heavy_scorpion&n2=17&n3=10",
    "n2=10&n2=11&n3=10",
    "n2=10&n3=10&extra=true",
  ]) {
    assert.equal(serverModule.kitingObservationSelection(new URL(
      `http://127.0.0.1/api/ranged-vs-melee-kiting?${query}`,
    )), null, query);
  }
});


test("manual 5 HCA versus 10 Champion setup preserves the tape's matchup order", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(
      `${baseUrl}/api/ranged-vs-melee-kiting`
        + "?ranged=heavy_cav_archer&melee=champion&navigation=cohesive&n2=5&n3=10",
    );
    const run = await response.json();
    assert.equal(response.status, 200, run.error);
    assert.equal(run.alliedTransitMode, "soft-allied");
    assert.equal(run.contactSteeringMode, "preventive-contact-graph");
    assert.ok(run.contactSteeringSummary.steeredSteps > 0);
    assert.ok(run.contactSteeringSummary.steeredUnitCount > 0);
    assert.ok(run.contactSteeringSummary.steeredUnitCount <= 10);
    const opening = run.snapshots[0].units;
    const positionsFor = (owner) => opening
      .filter(([referenceId]) => run.unitIndex[referenceId].owner === owner)
      .sort(([leftId], [rightId]) => leftId - rightId)
      .map(([, x, y]) => [x, y]);

    // Literal frames.bin creation order. A family-wide geometric sort picks
    // a different five-cell HCA subset and changes first contact materially.
    assert.deepEqual(positionsFor(2), [
      [6.5, 4.5],
      [10.5, 2.5],
      [7.5, 3.5],
      [9.5, 4.5],
      [6.5, 5.5],
    ]);
    assert.deepEqual(positionsFor(3), [
      [4.5, 12.5],
      [5.5, 11.5],
      [4.5, 10.5],
      [2.5, 12.5],
      [3.5, 12.5],
      [5.5, 12.5],
      [6.5, 11.5],
      [3.5, 11.5],
      [2.5, 11.5],
      [3.5, 13.5],
    ]);
  });
});


test("dense HCA versus Champion tape rosters converge without relaxing geometry", async () => {
  await withServer(async (baseUrl) => {
    for (const [n2, n3] of [[15, 20], [20, 20]]) {
      const response = await fetch(
        `${baseUrl}/api/ranged-vs-melee-kiting`
          + `?ranged=heavy_cav_archer&melee=champion&navigation=cohesive&n2=${n2}&n3=${n3}`,
      );
      const run = await response.json();
      assert.equal(response.status, 200, `${n2}v${n3}: ${run.error ?? "unknown error"}`);
      assert.equal(run.side2.count, n2);
      assert.equal(run.side3.count, n3);
    }
  });
});


test("local shared assets expose presentation files but never the old simulator", async () => {
  await withServer(async (baseUrl) => {
    for (const asset of [
      ["/static/css/base.css", /--gold/],
      ["/static/css/simulate.css", /\.sim-stage/],
      ["/static/js/constants.js", /function spriteFor/],
      ["/static/js/unit_sprites.js", /UNIT_SPRITES/],
    ]) {
      const response = await fetch(`${baseUrl}${asset[0]}`);
      assert.equal(response.status, 200, asset[0]);
      assert.match(await response.text(), asset[1], asset[0]);
    }
    for (const forbidden of [
      "/static/js/simulate.js",
      "/static/js/engine/index.js",
      "/static/lab/sim_harness.js",
    ]) {
      assert.equal((await fetch(`${baseUrl}${forbidden}`)).status, 404, forbidden);
    }
  });
});


test("catalogue keeps every website unit visible and enables exactly the registry rows", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/catalogue`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    const catalogue = await response.json();

    assert.equal(catalogue.schemaVersion, 1);
    assert.equal(catalogue.civilizations.length, 53);
    assert.equal(catalogue.civilizations.reduce(
      (total, civilization) => total + civilization.units.length, 0), 972);
    assert.equal(catalogue.enabled.length, 14);
    assert.equal(new Set(catalogue.enabled.map(({ catalogueKey }) => catalogueKey)).size, 14);
    assert.deepEqual(catalogue.enabled.find(({ engineSlug }) => engineSlug === "heavy_cav_archer"), {
      catalogueKey: "saracens:heavy-cavalry-archer:1411",
      engineSlug: "heavy_cav_archer",
      civ: "Saracens",
      name: "Heavy Cavalry Archer",
      class: "mobile_ranged",
      baseCost: { food: 0, wood: 40, gold: 60 },
    });
  });
});


test("units endpoint publishes every authorized ranged-versus-melee tape roster", async () => {
  const truth = JSON.parse(await readFile(
    new URL("../calibration/fixtures/standard_units/standard_units_truth.json", import.meta.url),
    "utf8",
  ));
  const rangedByMaster = new Map([
    [5, "hand_cannoneer"],
    [6, "imp_elite_skirm"],
    [492, "arbalester"],
    [474, "heavy_cav_archer"],
    [542, "heavy_scorpion"],
    [588, "siege_onager"],
  ]);
  const meleeByMaster = new Map([
    [567, "champion"],
    [1134, "elite_elephant"],
    [1903, "elite_fire_lancer"],
    [1372, "elite_steppe"],
    [359, "halberdier"],
    [330, "heavy_camel"],
    [441, "hussar"],
    [569, "paladin"],
  ]);
  const expected = truth.rows.flatMap((row) => {
    const rangedSlug = rangedByMaster.get(row.side2.master);
    const meleeSlug = meleeByMaster.get(row.side3.master);
    if (!rangedSlug || !meleeSlug) return [];
    return [{
      id: row.id,
      rangedSlug,
      rangedCount: row.side2.count,
      meleeSlug,
      meleeCount: row.side3.count,
      tapeRunCount: row.runs.length,
    }];
  }).sort((a, b) => `${a.rangedSlug}|${a.meleeSlug}`.localeCompare(
    `${b.rangedSlug}|${b.meleeSlug}`,
  ));
  assert.equal(expected.length, 48);

  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/units`);
    assert.equal(response.status, 200);
    const units = await response.json();
    assert.deepEqual(units.kitingObservationMatchups, expected);
  });
});


test("fight endpoint accepts a derived resource budget and rejects mixed sizing", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(
      `${baseUrl}/api/fight?side2=champion&side3=elite_elephant&budget=800`,
    );
    assert.equal(response.status, 200);
    const fight = await response.json();
    assert.equal(fight.derivedCounts, true);
    assert.equal(fight.budget, 800);
    assert.equal(fight.side2.count, 10);
    assert.equal(fight.side3.count, 3);

    for (const query of [
      "side2=champion&side3=paladin&budget=0",
      "side2=champion&side3=paladin&budget=800.5",
      "side2=champion&side3=paladin&n2=5&n3=5&budget=800",
    ]) {
      const rejected = await fetch(`${baseUrl}/api/fight?${query}`);
      assert.equal(rejected.status, 400, query);
    }
  });
});


test("fight endpoint keeps units outside every visible Golden Arena obstruction", async () => {
  await withServer(async (baseUrl) => {
    const [mapResponse, fightResponse] = await Promise.all([
      fetch(`${baseUrl}/api/map`),
      fetch(`${baseUrl}/api/fight?side2=hand_cannoneer&n2=5&side3=champion&n3=5`),
    ]);
    assert.equal(mapResponse.status, 200);
    assert.equal(fightResponse.status, 200);
    const fixture = await mapResponse.json();
    const fight = await fightResponse.json();
    const obstacles = fixture.map.gaia_objects;
    const obstacleRadius = 0.5;
    let nearestGap = Infinity;

    for (const snapshot of fight.snapshots) {
      for (const unit of snapshot.units) {
        if (!unit[5]) continue;
        const unitRadius = fight.unitIndex[unit[0]].collisionRadius;
        for (const obstacle of obstacles) {
          const gap = Math.hypot(unit[1] - obstacle.x, unit[2] - obstacle.y)
            - unitRadius - obstacleRadius;
          nearestGap = Math.min(nearestGap, gap);
          assert.ok(
            gap >= -1e-9,
            `tick ${snapshot.tick} unit ${unit[0]} entered ${obstacle.name} ${obstacle.reference_id}`,
          );
        }
      }
    }
    assert.ok(nearestGap < 0.02, "the regression fight must exercise obstacle contact");
    assert.ok(fight.winnerOwner === 2 || fight.winnerOwner === 3, "the routed fight must finish");
  });
});


test("solo movement endpoint runs only 21 owner-2 Hand Cannoneers under kite orders", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/solo-hand-cannoneers`);
    assert.equal(response.status, 200);
    const run = await response.json();

    assert.equal(run.mode, "solo-movement");
    assert.equal(run.navigationVariant, "cohesive");
    assert.deepEqual(run.navigationOptions, ["baseline", "per-unit-grid", "cohesive"]);
    assert.deepEqual(run.side2, {
      slug: "hand_cannoneer",
      label: "Hand Cannoneer",
      civ: "Bohemians",
      count: 21,
      class: "mobile_ranged",
    });
    assert.equal(run.side3.count, 0);
    assert.equal(run.kiteOwner, 2);
    assert.equal(run.ticks, 3600);
    assert.equal(run.snapshots.length, 3601);
    assert.deepEqual([...new Set(Object.values(run.unitIndex).map(({ owner }) => owner))], [2]);
    assert.equal(Object.keys(run.unitIndex).length, 21);

    const moveOrderTicks = new Set(run.snapshots.flatMap(({ events }) => events
      .filter(({ type }) => type === "kite-move")
      .map(({ tick }) => tick)));
    assert.ok(moveOrderTicks.size >= 40);

    const initial = new Map(run.snapshots[0].units.map((unit) => [unit[0], unit]));
    const maximumDisplacement = new Map([...initial.keys()].map((id) => [id, 0]));
    for (const snapshot of run.snapshots) {
      for (const unit of snapshot.units) {
        const spawn = initial.get(unit[0]);
        maximumDisplacement.set(unit[0], Math.max(
          maximumDisplacement.get(unit[0]),
          Math.hypot(unit[1] - spawn[1], unit[2] - spawn[2]),
        ));
      }
    }
    assert.equal([...maximumDisplacement.values()].every((distance) => distance > 1), true);
  });
});


test("Hand Cannoneer versus Champion observation uses the tape roster with a live chase", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(
      `${baseUrl}/api/hand-cannoneer-vs-champion-kiting?navigation=cohesive`,
    );
    assert.equal(response.status, 200);
    const run = await response.json();

    assert.equal(run.mode, "kiting-observation");
    assert.equal(run.navigationVariant, "cohesive");
    assert.deepEqual(run.navigationOptions, ["baseline", "per-unit-grid", "cohesive"]);
    assert.deepEqual(run.side2, {
      slug: "hand_cannoneer",
      label: "Hand Cannoneer",
      civ: "Bohemians",
      count: 14,
      class: "mobile_ranged",
    });
    assert.deepEqual(run.side3, {
      slug: "champion",
      label: "Champion",
      civ: "Chinese",
      count: 21,
      class: "melee",
    });
    assert.equal(run.family, "kite");
    assert.equal(run.kiteOwner, 2);
    // Viewer engagement physics intentionally changes battle outcomes as it
    // is reviewed. This endpoint test owns roster/order/playback shape, not a
    // calibrated winner that the user will validate separately against tape.
    assert.ok(run.winnerOwner === 2 || run.winnerOwner === 3);
    assert.ok(run.winnerHp > 0);
    assert.equal(Object.keys(run.unitIndex).length, 35);
    assert.deepEqual(
      Object.values(run.unitIndex).reduce((counts, { owner }) => ({
        ...counts,
        [owner]: (counts[owner] ?? 0) + 1,
      }), {}),
      { 2: 14, 3: 21 },
    );
    assert.equal(run.snapshots[0].navigation.variant, "cohesive");
    assert.equal(run.snapshots.some(({ navigation }) => navigation?.phase === "routing"), true);

    const events = run.snapshots.flatMap(({ events: entries }) => entries);
    assert.equal(events.some(({ type, actorId }) =>
      type === "kite-move" && run.unitIndex[actorId]?.owner === 2), true);
    assert.equal(events.some(({ type, actorId }) =>
      type === "attack-start" && run.unitIndex[actorId]?.owner === 2), true);

    const championIds = Object.entries(run.unitIndex)
      .filter(([, { owner }]) => owner === 3)
      .map(([referenceId]) => Number(referenceId))
      .sort((a, b) => a - b);
    const openingAttackMove = events.filter(({ type, tick, actorId }) => (
      type === "ai-location-order"
      && tick === 36
      && run.unitIndex[actorId]?.owner === 3
    ));
    assert.equal(openingAttackMove.length, 21);
    assert.deepEqual(
      openingAttackMove.map(({ actorId }) => actorId).sort((a, b) => a - b),
      championIds,
    );
    assert.equal(new Set(openingAttackMove.map(({ x, y }) => `${x},${y}`)).size, 1);

    const preOrder = run.snapshots.find(({ tick }) => tick === 35);
    const handCannoneers = preOrder.units.filter((unit) => run.unitIndex[unit[0]].owner === 2);
    const handCannoneerCentroid = {
      x: handCannoneers.reduce((sum, unit) => sum + unit[1], 0) / handCannoneers.length,
      y: handCannoneers.reduce((sum, unit) => sum + unit[2], 0) / handCannoneers.length,
    };
    assert.ok(Math.abs(openingAttackMove[0].x - handCannoneerCentroid.x) < 1e-9);
    assert.ok(Math.abs(openingAttackMove[0].y - handCannoneerCentroid.y) < 1e-9);

    const first = new Map(run.snapshots[0].units.map((unit) => [unit[0], unit]));
    const afterOpeningOrder = run.snapshots.find(({ tick }) => tick === 120);
    for (const referenceId of championIds.slice(0, 4)) {
      const start = first.get(referenceId);
      const current = afterOpeningOrder.units.find((unit) => unit[0] === referenceId);
      assert.ok(Math.hypot(current[1] - start[1], current[2] - start[2]) > 0.25,
        `Champion ${referenceId} did not start moving after the group attack-move`);
    }
    assert.equal(run.snapshots.some(({ units }) => units.some((unit) => (
      championIds.includes(unit[0])
        && Math.hypot(unit[1] - first.get(unit[0])[1], unit[2] - first.get(unit[0])[2]) > 1
    ))), true);
    assert.equal(run.snapshots.some(({ units }) => units.some((unit) => (
      championIds.includes(unit[0])
        && (unit[7] !== null || unit[8] !== null || unit[9] !== null)
    ))), true);

    const map = await (await fetch(`${baseUrl}/api/map`)).json();
    for (const snapshot of run.snapshots) {
      for (const unit of snapshot.units) {
        if (!unit[5]) continue;
        const unitRadius = run.unitIndex[unit[0]].collisionRadius;
        for (const obstacle of map.map.gaia_objects) {
          const obstacleRadius = obstacle.reference_id === 1604 ? 1.5 : 0.5;
          const clearance = Math.hypot(unit[1] - obstacle.x, unit[2] - obstacle.y)
            - unitRadius - obstacleRadius;
          assert.ok(clearance >= -1e-9,
            `tick ${snapshot.tick} unit ${unit[0]} overlapped obstacle ${obstacle.reference_id}`);
        }
      }
    }
  });
});


test("generalized kiting endpoint gives the tape-roster Heavy Scorpions a live kite cycle", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(
      `${baseUrl}/api/ranged-vs-melee-kiting`
        + "?ranged=heavy_scorpion&melee=champion&navigation=cohesive",
    );
    assert.equal(response.status, 200);
    const run = await response.json();

    assert.equal(run.mode, "kiting-observation");
    assert.equal(run.navigationVariant, "cohesive");
    assert.deepEqual(run.side2, {
      slug: "heavy_scorpion",
      label: "Heavy Scorpion",
      civ: "Japanese",
      count: 8,
      class: "siege_ranged",
    });
    assert.deepEqual(run.side3, {
      slug: "champion",
      label: "Champion",
      civ: "Chinese",
      count: 21,
      class: "melee",
    });
    assert.equal(run.family, "siege");
    assert.equal(run.kiteOwner, 2);

    const scorpionIds = Object.entries(run.unitIndex)
      .filter(([, { owner }]) => owner === 2)
      .map(([referenceId]) => Number(referenceId));
    const championIds = Object.entries(run.unitIndex)
      .filter(([, { owner }]) => owner === 3)
      .map(([referenceId]) => Number(referenceId));
    const events = run.snapshots.flatMap(({ events: entries }) => entries);
    assert.equal(events.some(({ type, actorId }) => (
      type === "kite-move" && scorpionIds.includes(actorId)
    )), true);
    assert.equal(events.some(({ type, actorId }) => (
      type === "attack-start" && scorpionIds.includes(actorId)
    )), true);

    const openingAttackMove = events.filter(({ type, tick, actorId }) => (
      type === "ai-location-order" && tick === 36 && championIds.includes(actorId)
    ));
    assert.equal(openingAttackMove.length, 21);
    assert.equal(new Set(openingAttackMove.map(({ x, y }) => `${x},${y}`)).size, 1);

    const first = new Map(run.snapshots[0].units.map((unit) => [unit[0], unit]));
    assert.equal(run.snapshots.some(({ units }) => units.some((unit) => (
      scorpionIds.includes(unit[0])
      && Math.hypot(unit[1] - first.get(unit[0])[1], unit[2] - first.get(unit[0])[2]) > 1
    ))), true);
  });
});


test("Heavy Scorpion versus Heavy Camel observation resolves after close contact", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(
      `${baseUrl}/api/ranged-vs-melee-kiting`
        + "?ranged=heavy_scorpion&melee=heavy_camel&navigation=cohesive",
    );
    assert.equal(response.status, 200);
    const run = await response.json();
    assert.equal(run.side2.count, 15);
    assert.equal(run.side3.count, 20);
    assert.ok(run.winnerOwner === 2 || run.winnerOwner === 3);
    assert.ok(run.ticks < 9000);
  });
});


test("generalized kiting endpoint rejects units outside the tape-roster matrix", async () => {
  await withServer(async (baseUrl) => {
    for (const query of [
      "ranged=champion&melee=paladin&navigation=cohesive",
      "ranged=arbalester&melee=arbalester&navigation=cohesive",
      "ranged=heavy_scorpion&melee=unknown&navigation=cohesive",
      "ranged=heavy_scorpion&melee=champion&navigation=unknown",
      "ranged=heavy_scorpion&melee=champion&extra=1",
    ]) {
      const response = await fetch(`${baseUrl}/api/ranged-vs-melee-kiting?${query}`);
      assert.equal(response.status, 400, query);
    }
  });
});


test("solo movement endpoint runs each selectable ranged unit with its own mechanics", async () => {
  await withServer(async (baseUrl) => {
    const expected = {
      hand_cannoneer: { label: "Hand Cannoneer", civ: "Bohemians", master: 5, radius: 0.2 },
      arbalester: { label: "Arbalester", civ: "Chinese", master: 492, radius: 0.2 },
      heavy_cav_archer: { label: "Heavy Cav Archer", civ: "Saracens", master: 474, radius: 0.25 },
      heavy_scorpion: { label: "Heavy Scorpion", civ: "Japanese", master: 542, radius: 0.5 },
      imp_elite_skirm: { label: "Elite Skirmisher", civ: "Chinese", master: 6, radius: 0.2 },
    };

    const unitsResponse = await fetch(`${baseUrl}/api/units`);
    const units = await unitsResponse.json();
    assert.deepEqual(units.soloMovementSlugs, Object.keys(expected));

    for (const [slug, row] of Object.entries(expected)) {
      const response = await fetch(
        `${baseUrl}/api/solo-hand-cannoneers?unit=${slug}&navigation=cohesive`,
      );
      assert.equal(response.status, 200, slug);
      const run = await response.json();
      assert.deepEqual(run.side2, {
        slug,
        label: row.label,
        civ: row.civ,
        count: 21,
        class: slug === "heavy_scorpion" ? "siege_ranged" : "mobile_ranged",
      });
      assert.equal(run.side3.count, 0);
      assert.equal(run.kiteOwner, 2);
      assert.equal(Object.keys(run.unitIndex).length, 21);
      for (const meta of Object.values(run.unitIndex)) {
        assert.equal(meta.owner, 2);
        assert.equal(meta.slug, slug);
        assert.equal(meta.master, row.master);
        assert.equal(meta.collisionRadius, row.radius);
      }
    }

    for (const query of [
      "unit=champion",
      "unit=unknown",
      "unit=arbalester&unit=heavy_cav_archer",
      "unit=arbalester&count=21",
    ]) {
      assert.equal(
        (await fetch(`${baseUrl}/api/solo-hand-cannoneers?${query}`)).status,
        400,
        query,
      );
    }
  });
});


test("solo movement endpoint saves baseline, per-unit-grid, and cohesive navigation runs", async () => {
  await withServer(async (baseUrl) => {
    for (const navigation of ["baseline", "per-unit-grid", "cohesive"]) {
      const response = await fetch(
        `${baseUrl}/api/solo-hand-cannoneers?navigation=${navigation}`,
      );
      assert.equal(response.status, 200, navigation);
      const run = await response.json();
      assert.equal(run.navigationVariant, navigation);
      assert.equal(run.snapshots[0].navigation.variant, navigation);
      assert.equal(run.snapshots.at(-1).navigation.variant, navigation);
    }

    const invalid = await fetch(`${baseUrl}/api/solo-hand-cannoneers?navigation=unknown`);
    assert.equal(invalid.status, 400);
  });
});


test("cohesive solo navigation publishes formation-route diagnostics and preserves a compact group", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/solo-hand-cannoneers?navigation=cohesive`);
    assert.equal(response.status, 200);
    const run = await response.json();
    assert.equal(run.navigationSummary.unitCount, 21);
    assert.ok(run.navigationSummary.totalAnchorDistance > 8);
    assert.ok(run.navigationSummary.maxReplans >= 0);

    const active = run.snapshots.filter(({ tick }) => tick >= 900);
    assert.ok(active.length > 2000);
    assert.equal(active.every(({ navigation }) =>
      navigation.unitDestinations.length === 21
      && Number.isFinite(navigation.anchor.x)
      && Number.isFinite(navigation.routeWaypoint.x)
      && Number.isFinite(navigation.aiWaypoint.x)), true);
    const compactRatio = active.filter(({ navigation }) =>
      navigation.cohesionRadius <= 2.25).length / active.length;
    assert.ok(compactRatio >= 0.95, `compact snapshot ratio ${compactRatio}`);

    const mapResponse = await fetch(`${baseUrl}/api/map`);
    const map = (await mapResponse.json()).map;
    const obstacles = map.gaia_objects.map((obstacle) => ({
      ...obstacle,
      radius: obstacle.reference_id === 1604 ? 1.5 : 0.5,
    }));
    for (const snapshot of run.snapshots) {
      for (const unit of snapshot.units) {
        for (const obstacle of obstacles) {
          const clearance = Math.hypot(
            unit[1] - obstacle.x,
            unit[2] - obstacle.y,
          ) - 0.2 - obstacle.radius;
          assert.ok(clearance >= -1e-9,
            `tick ${snapshot.tick} unit ${unit[0]} overlapped obstacle ${obstacle.reference_id}`);
        }
      }
    }
  });
});


test("cohesive solo navigation clears obstacles with Heavy Scorpion collision bodies", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(
      `${baseUrl}/api/solo-hand-cannoneers?unit=heavy_scorpion&navigation=cohesive`,
    );
    assert.equal(response.status, 200);
    const run = await response.json();
    const radius = Object.values(run.unitIndex)[0].collisionRadius;
    assert.equal(radius, 0.5);

    const moveOrderTicks = [...new Set(run.snapshots.flatMap(({ events }) => events
      .filter(({ type }) => type === "kite-move")
      .map(({ tick }) => tick)))];
    assert.deepEqual(moveOrderTicks.slice(0, 5), [80, 160, 280, 360, 440]);

    // No hidden pre-order staging: the opening formation is the first actual
    // AI destination. The Scorpions should hold through tick 79, begin
    // translating on the tick-80 right-click, and form at its safe projected
    // group destination before the shared route anchor begins its lap.
    const spawn = new Map(run.snapshots[0].units.map((unit) => [unit[0], unit]));
    assert.equal(run.snapshots[0].navigation.phase, "awaiting-first-order");
    for (const snapshot of run.snapshots.slice(0, 80)) {
      assert.equal(snapshot.units.every((unit) => {
        const initial = spawn.get(unit[0]);
        return Math.hypot(unit[1] - initial[1], unit[2] - initial[2]) <= 1e-12;
      }), true, `unit moved before the first AI order at tick ${snapshot.tick}`);
    }
    const firstOrder = run.snapshots[80];
    assert.equal(firstOrder.navigation.phase, "forming-first-order");
    assert.ok(Math.abs(
      firstOrder.navigation.firstFormationTarget.x - firstOrder.navigation.aiWaypoint.x,
    ) <= 1e-9);
    assert.ok(firstOrder.navigation.firstFormationTarget.y
      < firstOrder.navigation.aiWaypoint.y);
    assert.equal(firstOrder.units.some((unit) => {
      const initial = spawn.get(unit[0]);
      return Math.hypot(unit[1] - initial[1], unit[2] - initial[2]) > 1e-6;
    }), true);
    const destinationCentroid = firstOrder.navigation.unitDestinations.reduce(
      (point, destination) => ({
        x: point.x + destination.x / firstOrder.navigation.unitDestinations.length,
        y: point.y + destination.y / firstOrder.navigation.unitDestinations.length,
      }),
      { x: 0, y: 0 },
    );
    assert.ok(Math.hypot(
      destinationCentroid.x - firstOrder.navigation.firstFormationTarget.x,
      destinationCentroid.y - firstOrder.navigation.firstFormationTarget.y,
    ) <= 1e-9);
    assert.ok(run.snapshots.some(({ navigation }) => navigation.phase === "routing"));
    assert.ok(run.navigationSummary.totalAnchorDistance > 20);

    for (const snapshot of run.snapshots) {
      const destinations = snapshot.navigation.unitDestinations;
      for (let left = 0; left < destinations.length; left += 1) {
        for (let right = left + 1; right < destinations.length; right += 1) {
          const separation = Math.max(
            Math.abs(destinations[left].x - destinations[right].x),
            Math.abs(destinations[left].y - destinations[right].y),
          );
          // Formation movers use the engine's measured ally-overlap rule;
          // Scorpion slots therefore keep the common half-tile lattice rather
          // than expanding to the full one-tile collision diameter.
          assert.ok(separation >= 0.48 - 1e-9,
            `tick ${snapshot.tick} destinations ${destinations[left].referenceId} and `
            + `${destinations[right].referenceId} are only ${separation} tiles apart`);
        }
      }
    }

    const mapResponse = await fetch(`${baseUrl}/api/map`);
    const map = (await mapResponse.json()).map;
    const obstacles = map.gaia_objects.map((obstacle) => ({
      ...obstacle,
      radius: obstacle.reference_id === 1604 ? 1.5 : 0.5,
    }));
    for (const snapshot of run.snapshots) {
      for (const unit of snapshot.units) {
        for (const obstacle of obstacles) {
          const clearance = Math.hypot(
            unit[1] - obstacle.x,
            unit[2] - obstacle.y,
          ) - radius - obstacle.radius;
          assert.ok(clearance >= -1e-9,
            `tick ${snapshot.tick} unit ${unit[0]} overlapped obstacle ${obstacle.reference_id}`);
        }
      }
    }
  });
});


test("server exposes only curated no-store Champion diagnostics", async () => {
  await withServer(async (baseUrl) => {
    const truthResponse = await fetch(`${baseUrl}/api/champion/truth`);
    assert.equal(truthResponse.status, 200);
    assert.match(truthResponse.headers.get("content-type"), /application\/json/);
    assert.equal(truthResponse.headers.get("cache-control"), "no-store");
    const truth = await truthResponse.json();
    assert.equal(truth.archive.sha256, "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE");
    assert.deepEqual(truth.ratios.map(({ ratio, medianWinnerHpPct, repeats }) => [
      ratio,
      medianWinnerHpPct,
      repeats.map(({ repeat }) => repeat),
    ]), [
      ["1v1", 20, [1, 2, 3]],
      ["2v1", 80, [1, 2, 3]],
      ["2v3", 60, [1, 2, 3]],
      ["5v3", 72, [1, 2, 3]],
      ["6v3", 80, [1, 2, 3]],
    ]);
    assert.equal(JSON.stringify(truth).includes("unit_samples"), false);

    const mechanicsResponse = await fetch(`${baseUrl}/api/champion/mechanics`);
    assert.equal(mechanicsResponse.status, 200);
    assert.equal(mechanicsResponse.headers.get("cache-control"), "no-store");
    const mechanics = await mechanicsResponse.json();
    assert.deepEqual({
      unitMaster: mechanics.unitMaster,
      hp: mechanics.hp,
      damage: mechanics.damageVsSelf,
      collisionRadius: mechanics.collisionRadiusTiles,
      attackRange: mechanics.attackRangeTiles,
    }, {
      unitMaster: 567,
      hp: 70,
      damage: 14,
      collisionRadius: 0.2,
      attackRange: 0,
    });
  });
});


test("Champion result endpoint returns verified deterministic playback for the selected tape repeat", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/champion/result?ratio=2v3&repeat=2`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    const result = await response.json();

    assert.equal(result.ratio, "2v3");
    assert.equal(result.repeat, 2);
    assert.equal(result.deterministic, true);
    assert.equal(result.tapeDiagnostic.repeat, 2);
    assert.equal(result.tapeDiagnostic.winnerOwner, 3);
    assert.equal(result.playback.ratio, "2v3");
    assert.equal(result.playback.snapshots[0].tick, 0);
    assert.equal(result.playback.snapshots.at(-1).tick, result.playback.ticks);
    assert.ok(result.playback.events.length > 0);
    assert.equal(result.playback.source.zipSha256, "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE");
  });
});


test("Champion result endpoint strictly validates ratio and repeat", async () => {
  await withServer(async (baseUrl) => {
    for (const requestPath of [
      "/api/champion/result",
      "/api/champion/result?ratio=unknown&repeat=1",
      "/api/champion/result?ratio=1v1&repeat=0",
      "/api/champion/result?ratio=1v1&repeat=4",
      "/api/champion/result?ratio=1v1&repeat=1.5",
    ]) {
      const response = await fetch(`${baseUrl}${requestPath}`);
      assert.equal(response.status, 400, requestPath);
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.match(response.headers.get("content-type"), /application\/json/);
    }
  });
});


test("server keeps source archives and raw calibration fixtures inaccessible", async () => {
  await withServer(async (baseUrl) => {
    for (const requestPath of [
      "/aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip",
      "/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip",
      "/calibration/fixtures/champion_basics.json",
      "/fixtures/unit_stats/champion_chinese_imperial.json",
    ]) {
      const response = await fetch(`${baseUrl}${requestPath}`);
      assert.equal(response.status, 404, requestPath);
      assert.equal(response.headers.get("cache-control"), "no-store");
    }
  });
});


test("viewer page exposes battle controls and local calibration tools without a seed control", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/?ratio=5v3&repeat=3`);
    const body = await response.text();

    for (const id of [
      "simOptions",
      "team1Count",
      "team2Count",
      "totalResources",
      "startBtn",
      "pauseBtn",
      "resetBtn",
      "speedSlider",
      "team1Search",
      "team2Search",
      "team1Selection",
      "team2Selection",
      "mapCanvas",
      "soloMovementUnit",
      "navigationVariant",
      "navigationDebugToggle",
      "navigationStats",
      "navPhase",
      "navContactMode",
      "navContactSteps",
      "playPause",
      "resetPlayback",
      "stepTick",
      "nextEvent",
      "returnFormation",
      "tickReadout",
      "unitTelemetry",
      "eventTimeline",
      "runFlagged",
      "reviewNote",
      "clearFeedback",
      "exportFeedback",
    ]) {
      assert.match(body, new RegExp(`id=["']${id}["']`), id);
    }
    assert.doesNotMatch(body, /id=["'][^"']*seed/i);
    assert.match(body, /5,000 incl\. Upgrades/);
    assert.match(body, /value=["']resources_upgrades["'][^>]*disabled/);
    assert.match(body, /Calibration tools/);

    const appModule = await fetch(`${baseUrl}/viewer/app.js`);
    const appBody = await appModule.text();
    assert.match(appBody, /soloMovementSlugs/);
    assert.match(appBody, /searchParams\.set\("unit"/);

    const reviewModule = await fetch(`${baseUrl}/viewer/simulation-review.js`);
    assert.equal(reviewModule.status, 200);
    assert.match(reviewModule.headers.get("content-type"), /javascript/);
  });
});


test("phone layout stacks the battle stage and keeps map tools reachable", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/viewer/styles.css`);
    assert.equal(response.status, 200);
    const body = await response.text();
    const compactPhoneRules = body.match(/@media \(max-width: 720px\) \{([\s\S]*?)\n\}/)?.[1];

    assert.ok(compactPhoneRules, "expected a compact-phone breakpoint through 480px");
    assert.match(compactPhoneRules, /\.sim-stage\s*\{[\s\S]*grid-template-columns:\s*1fr;/);
    assert.match(compactPhoneRules, /\.map-tool-rail\s*\{[\s\S]*grid-template-columns:\s*repeat\(2, 1fr\);/);
  });
});
