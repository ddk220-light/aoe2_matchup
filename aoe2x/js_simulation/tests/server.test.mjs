import assert from "node:assert/strict";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { createMapServer } from "../server.mjs";


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


test("server exposes the map-only viewer and literal fixture", async () => {
  await withServer(async (baseUrl) => {
    const page = await fetch(`${baseUrl}/`);
    assert.equal(page.status, 200);
    assert.match(page.headers.get("content-type"), /text\/html/);
    const pageBody = await page.text();
    assert.match(pageBody, /Golden Arena/);
    assert.match(pageBody, /location\.pathname\.endsWith\("\/"\)/);
    assert.match(pageBody, /document\.head\.append\(mountBase\)/);
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


test("viewer page exposes the complete Champion review instrument without a seed control", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/?ratio=5v3&repeat=3`);
    const body = await response.text();

    for (const id of [
      "ratioSelect",
      "repeatSelect",
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
    assert.match(body, /aria-label=["']Simulation playback controls["']/);

    const reviewModule = await fetch(`${baseUrl}/viewer/simulation-review.js`);
    assert.equal(reviewModule.status, 200);
    assert.match(reviewModule.headers.get("content-type"), /javascript/);
  });
});
