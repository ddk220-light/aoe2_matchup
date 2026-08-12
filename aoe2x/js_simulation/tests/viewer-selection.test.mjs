import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../viewer/index.html", import.meta.url), "utf8");
const app = await readFile(new URL("../viewer/app.js", import.meta.url), "utf8");

test("the local viewer uses the production Battle Simulation control structure", () => {
  for (const id of [
    "simPage", "simOptions", "optionsCurrent", "team1Count", "team2Count",
    "totalResources", "startBtn", "pauseBtn", "resetBtn", "speedSlider",
    "team1Rail", "team2Rail", "team1Search", "team2Search",
    "team1Selection", "team2Selection", "mapCanvas",
  ]) {
    assert.ok(html.includes(`id="${id}"`), `missing #${id}`);
  }
  assert.ok(html.includes("Battle Simulation"));
  assert.ok(html.includes("Pick a unit for each side, then watch who wins"));
});

test("upgrade-inclusive resources stay visible but disabled", () => {
  assert.match(html, /value="resources_upgrades" disabled/);
  assert.match(html, /Not calibrated/);
});

test("the viewer drives only clean-room catalogue and fight endpoints", () => {
  assert.ok(app.includes("api/catalogue"), "app.js must load the display catalogue");
  assert.ok(app.includes("api/fight"), "app.js must call api/fight");
  assert.ok(app.includes("api/units"), "app.js must call api/units");
  assert.ok(!app.includes("api/ref/"), "app.js must not depend on Flask reference APIs");
  assert.ok(!app.includes("static/js/engine"), "app.js must not load the old simulator");
});

test("calibration tools and map inspection remain available", () => {
  for (const id of [
    "unitTelemetry", "eventTimeline", "runFlagged", "reviewNote",
    "topDownToggle", "gridToggle", "tickReadout", "simWinner",
    "playPause", "resetPlayback", "stepTick", "nextEvent",
  ]) {
    assert.ok(html.includes(`id="${id}"`), `lab control #${id} was removed`);
  }
});
