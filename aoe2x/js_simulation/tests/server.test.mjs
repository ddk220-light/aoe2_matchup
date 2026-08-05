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
