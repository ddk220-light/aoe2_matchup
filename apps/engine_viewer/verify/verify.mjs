// Headless acceptance test: run the engine on a scenario's commands.json and
// score it against truth.json. Scenario-generic (feature-detects truth shape).
//
// Usage: node verify/verify.mjs [scenario]   (default: camp300)
import { readFileSync } from "node:fs";
import { createGame, run, step } from "../public/engine.js";

const scenName = process.argv[2] || "camp300";
const dir = new URL(`../data/${scenName}/`, import.meta.url);
const scen = JSON.parse(readFileSync(new URL("commands.json", dir)));
const truth = JSON.parse(readFileSync(new URL("truth.json", dir)));

const deerMode = !!(truth.deer && truth.deer.length);

// In deer mode we STEP the engine so we can sample each pushed deer's position
// over time (the headline metric: does our flee model push the deer like the
// real game). Otherwise a single run() to completion is enough.
const trace = new Map();          // eid -> [[t,x,y]] for pushed deer
let g;
if (deerMode) {
  g = createGame(scen);
  for (const d of truth.deer) trace.set(d.eid, []);
  let lastSamp = -1;
  while (g.t < scen.duration + 1 && !g.ended) {
    step(g);
    if (g.t - lastSamp >= 0.25) {
      lastSamp = g.t;
      for (const d of truth.deer) {
        const e = g.ents.get(d.eid);
        if (e) trace.get(d.eid).push([+g.t.toFixed(2), e.x, e.y]);
      }
    }
  }
} else {
  g = run(createGame(scen), scen.duration + 1);
}

const dep = g.events.filter((e) => e.kind === "deposit");
const simSpawns = g.events.filter((e) => e.kind === "spawn");
const simBuilt = g.events.filter((e) => e.kind === "built");
const simKills = g.events.filter((e) => e.kind === "kill");

const truthSpawns = truth.spawns ?? (truth.spawn ? [truth.spawn] : []);
const truthTotal = truth.total_collected ?? truth.total_delivered;
const simTotal = dep.reduce((s, d) => s + d.amount, 0);

const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok, detail });

// linear-interp an [[t,x,y]] trace at time t (clamped to its ends)
function posAt(arr, t) {
  if (!arr.length) return [NaN, NaN];
  if (t <= arr[0][0]) return [arr[0][1], arr[0][2]];
  if (t >= arr[arr.length - 1][0]) return [arr.at(-1)[1], arr.at(-1)[2]];
  let lo = 0, hi = arr.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; (arr[m][0] <= t ? lo = m : hi = m); }
  const f = (t - arr[lo][0]) / (arr[hi][0] - arr[lo][0] || 1);
  return [arr[lo][1] + (arr[hi][1] - arr[lo][1]) * f,
          arr[lo][2] + (arr[hi][2] - arr[lo][2]) * f];
}

// 1. Buildings (skipped when none): completion ±3s where the capture pinned it.
const truthBuilt = (truth.buildings || []).filter((b) => b.eid > 0);
truthBuilt.forEach((tb, i) => {
  const sb = simBuilt[i];
  if (tb.completed_t != null) {
    add(`building #${i + 1} completed ±3s`,
        !!sb && Math.abs(sb.t - tb.completed_t) <= 3.0,
        `truth ${tb.completed_t}  sim ${sb ? `${sb.t} (${sb.building})` : "never"}`);
  } else {
    add(`building #${i + 1} constructed`, !!sb, sb ? `done t=${sb.t}` : "never built");
  }
});

if (deerMode) {
  // ---- DEER PUSH: the trajectory match is the headline ----
  // The scout drives the deer; our flee model must reproduce its path closely
  // enough to land it at the TC (or, for the mistimed one, back at spawn).
  const tc = scen.entities.find((e) => e.type === "town_center");
  for (const td of truth.deer) {
    const arr = trace.get(td.eid) || [];
    const errs = td.traj.map(([t, tx, ty]) => {
      const [ex, ey] = posAt(arr, t);
      return Math.hypot(ex - tx, ey - ty);
    });
    const mean = errs.reduce((a, b) => a + b, 0) / errs.length;
    const max = Math.max(...errs);
    add(`deer ${td.eid} traj mean err <=4t`, mean <= 4,
        `mean ${mean.toFixed(2)}  max ${max.toFixed(2)} tiles  (${errs.length} samples)`);
    const [ex, ey] = posAt(arr, td.traj.at(-1)[0]);
    const sk = simKills.find((k) => k.eid === td.eid);
    if (td.kill_t != null) {
      // pushed + killed: it must die AT the TC (the exact spot is micro-
      // dependent — the TC's solid back can stall an NE approach a few tiles
      // short of the real front-courtyard kill) and at ~the right time.
      const dTC = tc ? Math.hypot(ex - tc.x, ey - tc.y) : 99;
      add(`deer ${td.eid} killed at the TC (<=5t)`, dTC <= 5,
          `death ${[ex.toFixed(1), ey.toFixed(1)]}  TC ${[tc.x, tc.y]}  d=${dTC.toFixed(1)}`);
      add(`deer ${td.eid} killed ±10s`, !!sk && Math.abs(sk.t - td.kill_t) <= 10,
          `truth ${td.kill_t}  sim ${sk ? sk.t : "never"}`);
    } else {
      // mistimed push: survives and walks back to spawn
      const homeErr = Math.hypot(ex - td.home[0], ey - td.home[1]);
      add(`deer ${td.eid} survives + walks home <=4t`, !sk && homeErr <= 4,
          `killed=${!!sk}  home ${td.home}  err ${homeErr.toFixed(1)}`);
    }
  }
  // ---- BOARS: HP combat — baited to the TC (arrows) or swarm-killed ----
  for (const tb of truth.boars || []) {
    const sk = simKills.find((k) => k.eid === tb.eid);
    add(`boar ${tb.eid} killed ±15s`, !!sk && Math.abs(sk.t - tb.kill_t) <= 15,
        `truth ${tb.kill_t.toFixed(0)}  sim ${sk ? sk.t.toFixed(0) : "never"}`);
  }
  // The first unit death: exactly one villager dies (boar2's first attacker).
  const simDeaths = g.events.filter((e) => e.kind === "death");
  add(`villager deaths = ${(truth.deaths || []).length}`,
      simDeaths.length === (truth.deaths || []).length,
      `truth ${(truth.deaths || []).length}  sim ${simDeaths.length}`);
  for (const td of truth.deaths || []) {
    const sd = simDeaths.find((d) => d.eid === td.eid);
    add(`death ${td.eid} ±15s`, !!sd && Math.abs(sd.t - td.t) <= 15,
        `truth ${td.t.toFixed(0)}  sim ${sd ? sd.t.toFixed(0) : "—"}`);
  }
  add("Loom researched", !!g.loom, g.loom ? "yes" : "no");
  // food banked: deer fully eaten + boars partly (the big boar carcasses are
  // eaten slower than the capture — fewer villagers swarm them before the boar2
  // order + final garrison pull them away — so this is a one-sided sanity bound).
  const foodBanked = dep.filter((d) => d.res === "food").reduce((s, d) => s + d.amount, 0);
  add(`food banked (real ${truth.herd_gathered}; boars eaten slower)`,
      foodBanked >= truth.herd_gathered * 0.5 && foodBanked <= truth.herd_gathered + 30,
      `sim ${foodBanked.toFixed(0)}  rot ${g.rotted.toFixed(0)}`);
  add(`villagers trained ≈ ${truthSpawns.length}`,
      Math.abs(simSpawns.length - truthSpawns.length) <= 1,
      `truth ${truthSpawns.length}  sim ${simSpawns.length}`);
} else {
  // 2. Trained-villager count + spawn timing (±1s).
  add(`trained villager count = ${truthSpawns.length}`,
      simSpawns.length === truthSpawns.length,
      `truth ${truthSpawns.length}  sim ${simSpawns.length}`);
  truthSpawns.forEach((ts, i) => {
    const sp = simSpawns[i];
    add(`spawn #${i + 1} ±1s`, !!sp && Math.abs(sp.t - ts.t) <= 1.0,
        `truth ${ts.t}  sim ${sp?.t ?? "—"}`);
  });

  // 3. Total collected — the headline metric.
  add("total collected ±15", Math.abs(simTotal - truthTotal) <= 15,
      `truth ${truthTotal}  sim ${simTotal.toFixed(1)}  (${((simTotal/truthTotal-1)*100).toFixed(1)}%)`);

  // 4. Herdables (sheep): conversions, kill count + order, and rot.
  if (truth.kills && truth.kills.length) {
    const simConv = g.events.filter((e) => e.kind === "convert");
    const preOwned = scen.entities.filter((e) => e.type === "herdable" && e.owner === 1).length;
    const truthConv = (truth.herdables || []).filter((h) => h.convert_t != null).length;
    add(`herdables converted = ${truthConv}`, simConv.length + preOwned >= truthConv,
        `truth ${truthConv}  sim ${simConv.length}+${preOwned} owned`);
    add(`sheep killed = ${truth.kills.length}`, simKills.length === truth.kills.length,
        `truth ${truth.kills.length}  sim ${simKills.length}`);
    truth.kills.forEach((tk, i) => {
      const sk = simKills[i];
      add(`kill #${i + 1} ${tk.eid} (order exact, time ±15s)`,
          !!sk && sk.eid === tk.eid && Math.abs(sk.t - tk.t) <= 15,
          `truth ${tk.eid}@${tk.t}  sim ${sk ? `${sk.eid}@${sk.t}` : "—"}`);
    });
    if (truth.herd_rot != null) {
      add("food rot ±12", Math.abs(g.rotted - truth.herd_rot) <= 12,
          `truth ${truth.herd_rot}  sim ${g.rotted.toFixed(1)}`);
    }
  }

  // 5. Collection curve at 40s checkpoints
  if (truth.rows && truth.rows[0] && "collected" in truth.rows[0]) {
    const simCurve = (t) => dep.filter((d) => d.t <= t).reduce((s, d) => s + d.amount, 0);
    for (const r of truth.rows) {
      if (Math.round(r.t) % 40 !== 0 || r.t === 0) continue;
      const sc = simCurve(r.t);
      add(`collected @${r.t}s ±30`, Math.abs(sc - r.collected) <= 30,
          `truth ${r.collected}  sim ${sc.toFixed(0)}`);
    }
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
