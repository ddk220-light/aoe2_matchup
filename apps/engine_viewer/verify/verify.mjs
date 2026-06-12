// Headless acceptance test: run the engine on a scenario's commands.json and
// score it against truth.json. Scenario-generic (feature-detects truth shape).
//
// Usage: node verify/verify.mjs [scenario]   (default: camp300)
import { readFileSync } from "node:fs";
import { createGame, run } from "../public/engine.js";

const scenName = process.argv[2] || "camp300";
const dir = new URL(`../data/${scenName}/`, import.meta.url);
const scen = JSON.parse(readFileSync(new URL("commands.json", dir)));
const truth = JSON.parse(readFileSync(new URL("truth.json", dir)));

const g = run(createGame(scen), scen.duration + 1);
const dep = g.events.filter((e) => e.kind === "deposit");
const simSpawns = g.events.filter((e) => e.kind === "spawn");
const built = g.events.find((e) => e.kind === "built" || e.kind === "tree_empty");

const truthSpawns = truth.spawns ?? (truth.spawn ? [truth.spawn] : []);
const truthTotal = truth.total_collected ?? truth.total_delivered;
const simTotal = dep.reduce((s, d) => s + d.amount, 0);

const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok, detail });

// 1. Building / construction
if (truth.buildings && truth.buildings.length) {
  const simBuilt = g.events.find((e) => e.kind === "built");
  add("lumber camp constructed", !!simBuilt,
      simBuilt ? `done t=${simBuilt.t}` : "never built");
}

// 2. Trained-villager count + spawn timing (±1s; sequential train queue)
add(`trained villager count = ${truthSpawns.length}`,
    simSpawns.length === truthSpawns.length,
    `truth ${truthSpawns.length}  sim ${simSpawns.length}`);
truthSpawns.forEach((ts, i) => {
  const sp = simSpawns[i];
  add(`spawn #${i + 1} ±1s`, !!sp && Math.abs(sp.t - ts.t) <= 1.0,
      `truth ${ts.t}  sim ${sp?.t ?? "—"}`);
});

// 3. Total wood collected — the headline metric. Tolerance ~1.5 loads: the
// last seconds before RESIGN deposit in-transit loads, and the sim's villagers
// finish slightly more synchronized than the real (desynced) ones.
add("total wood collected ±15", Math.abs(simTotal - truthTotal) <= 15,
    `truth ${truthTotal}  sim ${simTotal.toFixed(1)}  (${((simTotal/truthTotal-1)*100).toFixed(1)}%)`);

// 4. Collection curve at 20s checkpoints (camp300 rows carry `collected`)
if (truth.rows && truth.rows[0] && "collected" in truth.rows[0]) {
  // build a sim collected-by-time series from deposit events
  const simCurve = (t) => dep.filter((d) => d.t <= t).reduce((s, d) => s + d.amount, 0);
  for (const r of truth.rows) {
    if (Math.round(r.t) % 40 !== 0 || r.t === 0) continue;
    const sc = simCurve(r.t);
    add(`collected @${r.t}s ±25`, Math.abs(sc - r.collected) <= 25,
        `truth ${r.collected}  sim ${sc.toFixed(0)}`);
  }
}

let fails = 0;
for (const c of checks) {
  if (!c.ok) fails++;
  console.log(`${c.ok ? "PASS" : "FAIL"}  ${c.name}  [${c.detail}]`);
}
console.log(fails ? `\n${scenName}: ${fails}/${checks.length} FAILED`
                  : `\n${scenName}: ALL ${checks.length} PASSED`);
process.exit(fails ? 1 : 0);
