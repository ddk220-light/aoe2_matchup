// tests/test_sim_params.js
const assert = require("assert");
const { readSimParams } = require("../apps/website/static/js/sim_params.js");

const p = readSimParams("?civ1=Wei&unit1=tiger_cavalry_wei&civ2=Franks&unit2=knight&mode=count&age1=Imperial&autorun=1");
assert.strictEqual(p.civ1, "Wei");
assert.strictEqual(p.unit1, "tiger_cavalry_wei");
assert.strictEqual(p.civ2, "Franks");
assert.strictEqual(p.unit2, "knight");
assert.strictEqual(p.mode, "count");
assert.strictEqual(p.age1, "Imperial");
assert.strictEqual(p.autorun, true);

const empty = readSimParams("");
assert.strictEqual(empty.civ1, null);
assert.strictEqual(empty.autorun, false);

const r = readSimParams("?civ1=A&unit1=b&civ2=C&unit2=d&mode=resources&resources=3000");
assert.strictEqual(r.mode, "resources");
assert.strictEqual(r.resources, "3000");

const c = readSimParams("?civ1=Lithuanians&unit1=paladin&relics1=2&civ2=Aztecs&unit2=elite_jaguar_warrior_aztecs&kills2=3");
assert.strictEqual(c.relics1, "2");
assert.strictEqual(c.relics2, null);
assert.strictEqual(c.kills1, null);
assert.strictEqual(c.kills2, "3");
console.log("sim_params tests passed");
