import test from "node:test";
import assert from "node:assert/strict";
import { readBattleOptions } from "../apps/website/static/js/battle/selection.js";

test("default selection requests cost-efficient setup and retains manual count mode", () => {
  const previous = globalThis.document;
  let mode = "cost";
  const inputs = { rangedBuffer: { checked: true }, team1Count: { value: "7" }, team2Count: { value: "19" } };
  globalThis.document = { querySelector: () => ({ value: mode }), getElementById: id => inputs[id] };
  try {
    const teams = { 1: { civ: "Saxons", unitSlug: "elite_hearth_troop_saxons", age: "Imperial" },
      2: { civ: "Danes", unitSlug: "elite_jomsviking_danes", age: "Imperial" } };
    assert.equal(readBattleOptions(teams, 1).army.mode, "cost_efficient");
    mode = "count";
    assert.deepEqual(readBattleOptions(teams, 1).teams.map(t => t.count), [7, 19]);
  } finally { globalThis.document = previous; }
});
