import assert from "node:assert/strict";
import test from "node:test";

import {
  createPlaybackCursor,
  createReviewFeedback,
  downloadJsonDocument,
  parseReviewSelection,
  selectionUrl,
} from "../viewer/simulation-review.js";


function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    removeItem(key) { values.delete(key); },
    setItem(key, value) { values.set(key, String(value)); },
  };
}


const snapshots = Object.freeze([
  Object.freeze({ tick: 0, units: Object.freeze([]), events: Object.freeze([]) }),
  Object.freeze({ tick: 1, units: Object.freeze([]), events: Object.freeze([]) }),
  Object.freeze({ tick: 2, units: Object.freeze([]), events: Object.freeze([
    Object.freeze({ id: "2:damage:1:2", type: "damage", tick: 2 }),
  ]) }),
  Object.freeze({ tick: 3, units: Object.freeze([]), events: Object.freeze([]) }),
  Object.freeze({ tick: 4, units: Object.freeze([]), events: Object.freeze([
    Object.freeze({ id: "4:death:1:2", type: "death", tick: 4 }),
  ]) }),
]);


test("playback cursor advances only across supplied snapshots and finds the next event exactly", () => {
  const seen = [];
  const cursor = createPlaybackCursor({ snapshots, onSnapshot: (snapshot) => seen.push(snapshot.tick) });

  assert.equal(cursor.current().tick, 0);
  assert.equal(cursor.step().tick, 1);
  assert.equal(cursor.nextEvent().tick, 2);
  assert.equal(cursor.nextEvent().tick, 4);
  assert.equal(cursor.step().tick, 4);
  assert.deepEqual(seen, [0, 1, 2, 4, 4]);
  assert.equal(cursor.reset().tick, 0);
});


test("review flags round-trip without changing the supplied simulation state", () => {
  const storage = memoryStorage();
  const feedback = createReviewFeedback({ storage, now: () => "2026-08-05T07:00:00.000Z" });
  const before = snapshots[2];

  feedback.flag({ ratio: "2v3", repeat: 2, note: "target switch looks late" });

  assert.equal(snapshots[2], before);
  assert.deepEqual(feedback.get({ ratio: "2v3", repeat: 2 }), {
    ratio: "2v3", repeat: 2, flagged: true, note: "target switch looks late",
  });
  assert.deepEqual(feedback.exportJson().runs, [{
    ratio: "2v3", repeat: 2, flagged: true, note: "target switch looks late",
  }]);

  const reloaded = createReviewFeedback({ storage, now: () => "later" });
  assert.deepEqual(reloaded.get({ ratio: "2v3", repeat: 2 }), {
    ratio: "2v3", repeat: 2, flagged: true, note: "target switch looks late",
  });
  reloaded.clear();
  assert.deepEqual(reloaded.exportJson().runs, []);
});


test("review feedback validates ratio, repeat, and note length", () => {
  const feedback = createReviewFeedback({ storage: memoryStorage() });

  assert.throws(() => feedback.flag({ ratio: "7v7", repeat: 1, note: "" }), /ratio/i);
  assert.throws(() => feedback.flag({ ratio: "1v1", repeat: 0, note: "" }), /repeat/i);
  assert.throws(
    () => feedback.flag({ ratio: "1v1", repeat: 1, note: "x".repeat(2001) }),
    /note/i,
  );
});


test("ratio and tape repeat are parsed from and written to shareable URLs", () => {
  assert.deepEqual(parseReviewSelection("https://example.test/golden-map?ratio=5v3&repeat=3"), {
    ratio: "5v3",
    repeat: 3,
  });
  assert.deepEqual(parseReviewSelection("https://example.test/golden-map?ratio=nope&repeat=99"), {
    ratio: "1v1",
    repeat: 1,
  });
  assert.equal(
    selectionUrl("https://example.test/golden-map?old=1#inspect", { ratio: "6v3", repeat: 2 }),
    "https://example.test/golden-map?old=1&ratio=6v3&repeat=2#inspect",
  );
});


test("JSON review export keeps its object URL alive through a mounted-anchor click", () => {
  const events = [];
  const link = {
    hidden: false,
    click() { events.push("click"); },
    remove() { events.push("remove"); },
  };
  const documentRef = {
    body: {
      append(candidate) {
        assert.equal(candidate, link);
        events.push("append");
      },
    },
    createElement(tagName) {
      assert.equal(tagName, "a");
      events.push("create");
      return link;
    },
  };
  const urlApi = {
    createObjectURL(blob) {
      assert.deepEqual(blob.parts, ['{\n  "schemaVersion": 1\n}\n']);
      assert.deepEqual(blob.options, { type: "application/json" });
      events.push("object-url");
      return "blob:review";
    },
    revokeObjectURL(href) {
      assert.equal(href, "blob:review");
      events.push("revoke");
    },
  };
  class FakeBlob {
    constructor(parts, options) {
      this.parts = parts;
      this.options = options;
    }
  }
  const scheduled = [];

  downloadJsonDocument({
    value: { schemaVersion: 1 },
    filename: "champion-review.json",
    documentRef,
    urlApi,
    BlobCtor: FakeBlob,
    schedule(callback) {
      events.push("schedule");
      scheduled.push(callback);
    },
  });

  assert.equal(link.href, "blob:review");
  assert.equal(link.download, "champion-review.json");
  assert.equal(link.hidden, true);
  assert.deepEqual(events, ["object-url", "create", "append", "click", "remove", "schedule"]);
  scheduled[0]();
  assert.deepEqual(events, [
    "object-url", "create", "append", "click", "remove", "schedule", "revoke",
  ]);
});
