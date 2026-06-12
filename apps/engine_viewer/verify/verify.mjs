// Headless acceptance test: run the engine on commands.json and score the
// economy timeline against truth.json (tolerances from the design spec).
import { readFileSync } from "node:fs";
import { createGame, run } from "../public/engine.js";

const dir = new URL("../data/4_lumber/", import.meta.url);
const scen = JSON.parse(readFileSync(new URL("commands.json", dir)));
const truth = JSON.parse(readFileSync(new URL("truth.json", dir)));

const g = run(createGame(scen), scen.duration + 1);
const dep = g.events.filter((e) => e.kind === "deposit");
const spawn = g.events.find((e) => e.kind === "spawn");
const empty = g.events.find((e) => e.kind === "tree_empty");

const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok, detail });

add("4th villager spawn ±0.5s",
    !!spawn && Math.abs(spawn.t - truth.spawn.t) <= 0.5,
    `truth ${truth.spawn.t}  sim ${spawn?.t ?? "-"}`);

// Pair deposits by villager identity + ordinal. Sim keeps the replay's
// entity ids for starting units; trained units pair by spawn order.
const eidMap = new Map();
const simSpawns = g.events.filter((e) => e.kind === "spawn");
(truth.spawns ?? [truth.spawn]).forEach((ts, i) => {
  if (simSpawns[i]) eidMap.set(ts.eid, simSpawns[i].eid);
});
const simByEid = new Map();
for (const sd of dep) {
  if (!simByEid.has(sd.eid)) simByEid.set(sd.eid, []);
  simByEid.get(sd.eid).push(sd);
}
const ordinal = new Map();
let matched = 0;
for (const td of truth.deposits) {
  const simEid = eidMap.get(td.eid) ?? td.eid;
  const k = ordinal.get(simEid) ?? 0;
  ordinal.set(simEid, k + 1);
  const best = (simByEid.get(simEid) ?? [])[k];
  // Post-depletion partial loads: the real engine auto-retargets villagers
  // to neighboring trees before they head home (out of scope in v1), which
  // delays those deposits — they get a wider, documented time window.
  const tol = td.amount >= 9.5 ? 1.5 : 4.0;
  const ok = !!best && Math.abs(best.t - td.t) <= tol
             && Math.abs(best.amount - td.amount) <= 0.5;
  add(`deposit vill ${td.eid} #${k + 1} @${td.t.toFixed(1).padStart(6)} (${td.amount})`,
      ok, best ? `sim ${best.t} (${best.amount}) ±${tol}s` : "no sim match");
  if (best) matched++;
}
add("no extra sim deposits", dep.length === matched,
    `${dep.length - matched} extra`);

add("tree empty ±3s",
    !!empty && Math.abs(empty.t - truth.tree.empty_t) <= 3,
    `truth ${truth.tree.empty_t}  sim ${empty?.t ?? "-"}`);

const total = dep.reduce((s, d) => s + d.amount, 0);
add("total wood ±1",
    Math.abs(total - truth.total_delivered) <= 1,
    `truth ${truth.total_delivered}  sim ${total.toFixed(2)}`);

const vills = [...g.ents.values()].filter((e) => e.type === "villager").length;
add("final villager count = 4", vills === 4, `sim ${vills}`);

let fails = 0;
for (const c of checks) {
  if (!c.ok) fails++;
  console.log(`${c.ok ? "PASS" : "FAIL"}  ${c.name}  [${c.detail}]`);
}
console.log(fails ? `\n${fails}/${checks.length} FAILED`
                  : `\nALL ${checks.length} PASSED`);
process.exit(fails ? 1 : 0);
