import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../viewer/index.html", import.meta.url), "utf8");
const app = await readFile(new URL("../viewer/app.js", import.meta.url), "utf8");

test("the selector markup carries the four selection controls", () => {
  for (const id of ["side2Select", "n2Input", "side3Select", "n3Input", "resetCounts"]) {
    assert.ok(html.includes(`id="${id}"`), `missing #${id}`);
  }
});

test("the old matchup and ratio controls are gone", () => {
  for (const id of ["matchupSelect", "ratioSelect", "ratioOptions"]) {
    assert.ok(!html.includes(`id="${id}"`), `#${id} should have been removed`);
  }
});

test("the viewer drives the fight endpoint and not the matchup endpoints", () => {
  assert.ok(app.includes("api/fight"), "app.js must call api/fight");
  assert.ok(app.includes("api/units"), "app.js must call api/units");
  assert.ok(!app.includes("api/matchup/"), "app.js must not call api/matchup/*");
  assert.ok(!app.includes("api/champion/result"), "app.js must not call api/champion/result");
});

test("the lab panels are still present", () => {
  for (const id of ["unitTelemetry", "eventTimeline", "runFlagged", "reviewNote",
    "topDownToggle", "gridToggle", "tickReadout", "simWinner"]) {
    assert.ok(html.includes(`id="${id}"`), `lab control #${id} was removed`);
  }
});

import { createReviewFeedback } from "../viewer/simulation-review.js";

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => { map.set(key, value); },
  };
}

test("review rows for different unit pairs at the same counts do not collide", () => {
  const feedback = createReviewFeedback({ storage: memoryStorage() });
  feedback.flag({ pair: "champion-vs-paladin", ratio: "5v3", repeat: 1, note: "a" });
  feedback.flag({ pair: "arbalester-vs-champion", ratio: "5v3", repeat: 1, note: "b" });
  assert.equal(feedback.get({ pair: "champion-vs-paladin", ratio: "5v3", repeat: 1 }).note, "a");
  assert.equal(feedback.get({ pair: "arbalester-vs-champion", ratio: "5v3", repeat: 1 }).note, "b");
});

test("a malformed pair is rejected", () => {
  const feedback = createReviewFeedback({ storage: memoryStorage() });
  assert.throws(
    () => feedback.flag({ pair: "Champion vs Paladin", ratio: "5v3", repeat: 1, note: "" }),
    /pair/i);
});

test("a note with a pair survives a reload -- a fresh instance over the same storage", () => {
  const storage = memoryStorage();
  const feedback = createReviewFeedback({ storage });
  feedback.flag({ pair: "champion-vs-paladin", ratio: "5v3", repeat: 1, note: "reload me" });

  // A page reload is exactly this: a brand-new createReviewFeedback reading
  // whatever readRuns() pulls back out of the same storage object.
  const reloaded = createReviewFeedback({ storage });
  assert.equal(reloaded.get({ pair: "champion-vs-paladin", ratio: "5v3", repeat: 1 }).note, "reload me");
  // And it must not have also collided with (or duplicated over) a different
  // pair at the same ratio/repeat.
  assert.equal(reloaded.get({ pair: "arbalester-vs-champion", ratio: "5v3", repeat: 1 }).note, "");
});

test("a legacy row written before pair existed still loads after a reload", () => {
  const storage = memoryStorage();
  storage.setItem("aoe2.cleanroom.champion.review.v1", JSON.stringify([
    { ratio: "2v3", repeat: 2, flagged: true, note: "pre-existing note, no pair" },
  ]));

  const feedback = createReviewFeedback({ storage });
  assert.deepEqual(feedback.get({ ratio: "2v3", repeat: 2 }), {
    ratio: "2v3", repeat: 2, flagged: true, note: "pre-existing note, no pair",
  });
});
