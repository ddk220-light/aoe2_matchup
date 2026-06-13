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
const simBuilt = g.events.filter((e) => e.kind === "built");

const truthSpawns = truth.spawns ?? (truth.spawn ? [truth.spawn] : []);
const truthTotal = truth.total_collected ?? truth.total_delivered;
const simTotal = dep.reduce((s, d) => s + d.amount, 0);

const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok, detail });

// 1. Buildings: every truth building must be constructed; where the capture
// pinned a completion time (HP ramp), match it ±3s — this is the pop-cap
// critical path (house completion unfreezes the TC train timer).
const truthBuilt = (truth.buildings || []).filter((b) => b.eid > 0);
truthBuilt.forEach((tb, i) => {
  const sb = simBuilt[i];
  if (tb.completed_t != null) {
    add(`building #${i + 1} completed ±3s`,
        !!sb && Math.abs(sb.t - tb.completed_t) <= 3.0,
        `truth ${tb.completed_t}  sim ${sb ? `${sb.t} (${sb.building})` : "never"}`);
  } else {
    add(`building #${i + 1} constructed`, !!sb,
        sb ? `done t=${sb.t}` : "never built");
  }
});

// 2. Trained-villager count + spawn timing (±1s). With a pop cap in play the
// spawn gaps encode the housed-freeze: spawn #2 = house_complete + 25.0.
add(`trained villager count = ${truthSpawns.length}`,
    simSpawns.length === truthSpawns.length,
    `truth ${truthSpawns.length}  sim ${simSpawns.length}`);
truthSpawns.forEach((ts, i) => {
  const sp = simSpawns[i];
  add(`spawn #${i + 1} ±1s`, !!sp && Math.abs(sp.t - ts.t) <= 1.0,
      `truth ${ts.t}  sim ${sp?.t ?? "—"}`);
});

// 3. Total collected — the headline metric. Tolerance ~1.5 loads: the last
// seconds before RESIGN deposit in-transit loads, and the sim's villagers
// finish slightly more synchronized than the real (desynced) ones.
add("total collected ±15", Math.abs(simTotal - truthTotal) <= 15,
    `truth ${truthTotal}  sim ${simTotal.toFixed(1)}  (${((simTotal/truthTotal-1)*100).toFixed(1)}%)`);

// 4. Collection curve at 40s checkpoints
if (truth.rows && truth.rows[0] && "collected" in truth.rows[0]) {
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
