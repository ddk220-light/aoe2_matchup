import test from "node:test";
import assert from "node:assert/strict";
import { CasualtyTracker, formatResources, investmentComparisonText } from "../apps/website/static/js/battle/army-economics.js";

const index = new Map([[9000, {owner: 2}], [9001, {owner: 2}], [9500, {owner: 3}], [10000, {owner: 4}]]);
const row = (id, hp, alive) => [id, 0, 0, 0, hp, alive, "idle", null, null, null];

test("wounds, healing, auxiliary deaths and mode changes do not incur replacements", () => {
    const tracker = new CasualtyTracker();
    tracker.consume({tick: 1, units: [row(9000, 1, 1), row(9500, 20, 1), row(10000, 0, 0)],
        events: [{type: "unit-transformed", actorId: 9000}, {type: "death", targetId: 10000}]}, index);
    tracker.consume({tick: 2, units: [row(9000, 50, 1)]}, index);
    assert.deepEqual(tracker.counts, [0, 0]);
});

test("mounted loss is retained after respawn; foot death is never charged again", () => {
    const tracker = new CasualtyTracker();
    const crossed = [
        {tick: 1, units: [row(9000, 0, 0)], events: [{type: "death", targetId: 9000}, {type: "unit-dismount-pending", actorId: 9000}]},
        {tick: 2, units: [row(9000, 30, 1)], events: [{type: "unit-dismounted", actorId: 9000}]},
        {tick: 3, units: [row(9000, 0, 0), row(9001, 0, 0), row(9500, 0, 0)], events: [{type: "death", targetId: 9000}]},
    ];
    crossed.forEach(snapshot => tracker.consume(snapshot, index));
    assert.deepEqual(tracker.counts, [2, 1]);
    tracker.consume(crossed[2], index);
    assert.deepEqual(tracker.counts, [2, 1]);
    tracker.reset();
    assert.deepEqual(tracker.counts, [0, 0]);
});

test("a dismount event alone records a loss even if the visible body is alive", () => {
    const tracker = new CasualtyTracker();
    tracker.consume({tick: 90, units: [row(9000, 50, 1)], events: [{type: "unit-dismounted", actorId: 9000}]}, index);
    assert.deepEqual(tracker.counts, [1, 0]);
    tracker.consume({tick: 0, units: [row(9000, 100, 1)]}, index);
    assert.deepEqual(tracker.counts, [0, 0]);
});

test("resource display preserves refunds and fractional physical costs", () => {
    assert.equal(formatResources({food: 0, wood: 22.5, gold: -20}), "22.5W · -20G");
    assert.equal(formatResources({}), "0");
    assert.equal(formatResources(null), "Unavailable");
});

test("investment comparison names the correct army and withholds unknown comparisons", () => {
    assert.equal(investmentComparisonText({status: "available", lowerTeam: 1, savingPercent: 20}),
        "Army A needs 20% less weighted investment than Army B.");
    assert.equal(investmentComparisonText({status: "available", lowerTeam: 2, savingPercent: 20}),
        "Army B needs 20% less weighted investment than Army A.");
    assert.match(investmentComparisonText({status: "available", lowerTeam: null}), /equal/);
    assert.match(investmentComparisonText({status: "unavailable"}), /unavailable/);
});
