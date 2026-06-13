// Viewer wiring: load scenario, drive the engine in real time, render the 2D
// grid, and show the verification overlay (scorecard + wood-collected chart).
import { createGame, step, run, popCount, popCap } from "./engine.js";
import { BUILDINGS } from "./constants.js";
import { createRenderer } from "./render.js";

const $ = (id) => document.getElementById(id);
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

const params = new URLSearchParams(location.search);
const SCEN = params.get("scenario") || "sheep";

const scen = await (await fetch(`data/${SCEN}/commands.json`)).json();
const truth = await (await fetch(`data/${SCEN}/truth.json`)).json();
const GOAL = scen.players[0].goal_wood_collected
          || scen.players[0].goal_collected || null;
const DUR = Math.ceil(scen.duration);

let g = createGame(scen, { vision: true });   // viewer tracks fog of war
let playing = false;
let speed = 4;

function rebuildTo(t) {
  g = createGame(scen, { vision: true });
  run(g, Math.max(0, Math.min(t, DUR)));
  updateHud();
  renderer.draw(g);    // repaint immediately (don't depend on RAF timing)
}

function updateHud() {
  $("clock").textContent = fmt(g.t);
  $("wood").textContent = Math.round(g.collected);
  const cap = popCap(g);
  const pop = popCount(g);
  $("pop").textContent = `${pop}/${cap === Infinity ? "∞" : cap}`;
  // housed = the cap is actively blocking a queued unit right now
  const tc = [...g.ents.values()].find((e) => e.type === "town_center");
  const housed = tc && tc.queue.length > 0 && pop + 1 > cap;
  $("housed").textContent = housed ? "HOUSED" : "";
  $("popWrap").classList.toggle("full", !!housed);
  const status = [];
  for (const e of g.ents.values()) {
    const spec = BUILDINGS[e.type];
    if (spec && spec.t1 && !e.built) {
      status.push(`${e.type.replace("_", " ")}: ${Math.round((e.progress / spec.t1) * 100)}%`);
    }
  }
  $("status").textContent = status.join("  ");
}

// ------------------------------------------------------------ verification
// Mirrors verify/verify.mjs (keep in lockstep) — headline metric is wood
// collected, plus camp construction, trained-villager timing, and the curve.
function scorecard() {
  const full = run(createGame(scen), DUR + 1);
  const dep = full.events.filter((e) => e.kind === "deposit");
  const simSpawns = full.events.filter((e) => e.kind === "spawn");
  const truthSpawns = truth.spawns ?? (truth.spawn ? [truth.spawn] : []);
  const truthTotal = truth.total_collected ?? truth.total_delivered;
  const simTotal = dep.reduce((s, d) => s + d.amount, 0);
  const checks = [];
  const add = (name, ok, detail) => checks.push({ name, ok, detail });

  const simBuilt = full.events.filter((e) => e.kind === "built");
  const truthBuilt = (truth.buildings || []).filter((b) => b.eid > 0);
  truthBuilt.forEach((tb, i) => {
    const sb = simBuilt[i];
    if (tb.completed_t != null) {
      add(`building #${i + 1} done ±3s`,
          !!sb && Math.abs(sb.t - tb.completed_t) <= 3.0,
          `${tb.completed_t} → ${sb ? `${sb.t} (${sb.building})` : "never"}`);
    } else {
      add(`building #${i + 1} constructed`, !!sb, sb ? `done ${sb.t}s` : "never");
    }
  });
  add(`trained villagers = ${truthSpawns.length}`, simSpawns.length === truthSpawns.length,
      `${truthSpawns.length} → ${simSpawns.length}`);
  truthSpawns.forEach((ts, i) => {
    const sp = simSpawns[i];
    add(`spawn #${i + 1} ±1s`, !!sp && Math.abs(sp.t - ts.t) <= 1.0,
        `${ts.t} → ${sp?.t ?? "—"}`);
  });
  add("collected ±15", Math.abs(simTotal - truthTotal) <= 15,
      `${truthTotal} → ${simTotal.toFixed(0)} (${((simTotal / truthTotal - 1) * 100).toFixed(1)}%)`);

  // herdables: conversions, kill count + order, food rot (sheep scenario)
  if (truth.kills && truth.kills.length) {
    const simKills = full.events.filter((e) => e.kind === "kill");
    const simConv = full.events.filter((e) => e.kind === "convert");
    const preOwned = scen.entities.filter((e) => e.type === "herdable" && e.owner === 1).length;
    const truthConv = (truth.herdables || []).filter((h) => h.convert_t != null).length;
    add(`sheep converted = ${truthConv}`, simConv.length + preOwned >= truthConv,
        `${truthConv} → ${simConv.length}+${preOwned}`);
    add(`sheep killed = ${truth.kills.length}`, simKills.length === truth.kills.length,
        `${truth.kills.length} → ${simKills.length}`);
    truth.kills.forEach((tk, i) => {
      const sk = simKills[i];
      add(`kill #${i + 1} order+time ±15s`,
          !!sk && sk.eid === tk.eid && Math.abs(sk.t - tk.t) <= 15,
          `${tk.t.toFixed(0)} → ${sk ? sk.t.toFixed(0) : "—"}`);
    });
    if (truth.herd_rot != null) {
      add("food rot ±12", Math.abs(full.rotted - truth.herd_rot) <= 12,
          `${truth.herd_rot} → ${full.rotted.toFixed(1)}`);
    }
  }

  if (truth.rows && truth.rows[0] && "collected" in truth.rows[0]) {
    const curve = (t) => dep.filter((d) => d.t <= t).reduce((s, d) => s + d.amount, 0);
    for (const r of truth.rows) {
      if (Math.round(r.t) % 40 !== 0 || r.t === 0) continue;
      const sc = curve(r.t);
      add(`collected @${r.t}s ±30`, Math.abs(sc - r.collected) <= 30,
          `${r.collected} → ${sc.toFixed(0)}`);
    }
  }

  const el = $("scorecard");
  el.innerHTML = "";
  let fails = 0;
  for (const c of checks) {
    if (!c.ok) fails++;
    const row = document.createElement("div");
    row.className = `row ${c.ok ? "pass" : "fail"}`;
    row.innerHTML = `<span class="tag">${c.ok ? "PASS" : "FAIL"}</span>
                     <span>${c.name}</span><span class="detail">${c.detail}</span>`;
    el.appendChild(row);
  }
  const head = document.createElement("div");
  head.className = "row";
  head.style.cssText = "font-weight:700;border-bottom:1px solid var(--line);margin-bottom:4px";
  head.innerHTML = fails
    ? `<span style="color:var(--bad)">${fails}/${checks.length} checks failed</span>`
    : `<span style="color:var(--ok)">ALL ${checks.length} CHECKS PASS</span>`;
  el.prepend(head);
  return dep;
}

// --------------------------------------------------------------- chart
function drawChart(dep) {
  const cv = $("chart"), ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height, PAD = 8;
  ctx.clearRect(0, 0, W, H);
  const yMax = Math.max(GOAL || 0, truth.total_collected || 0, 320);
  const x = (t) => PAD + (t / DUR) * (W - 2 * PAD);
  const y = (w) => H - PAD - (w / yMax) * (H - 2 * PAD);

  if (GOAL) {                       // goal line
    ctx.strokeStyle = "rgba(212,168,67,.4)"; ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(x(0), y(GOAL)); ctx.lineTo(x(DUR), y(GOAL)); ctx.stroke();
    ctx.setLineDash([]);
  }
  // truth collected curve (blue)
  ctx.strokeStyle = "rgba(79,127,217,.95)"; ctx.lineWidth = 2;
  ctx.beginPath();
  truth.rows.forEach((r, i) => { const yy = y(r.collected); i ? ctx.lineTo(x(r.t), yy) : ctx.moveTo(x(r.t), yy); });
  ctx.stroke();
  // sim collected curve (gold) — stepped from deposit events
  ctx.strokeStyle = "rgba(212,168,67,.95)"; ctx.beginPath();
  let w = 0, py = y(0); ctx.moveTo(x(0), py);
  for (const d of [...dep].sort((a, b) => a.t - b.t)) {
    ctx.lineTo(x(d.t), py); w += d.amount; py = y(w); ctx.lineTo(x(d.t), py);
  }
  ctx.lineTo(x(DUR), py); ctx.stroke();
}

// --------------------------------------------------------------- main loop
const renderer = createRenderer($("view"), scen);
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (playing && g.t < DUR) {
    const target = Math.min(g.t + dt * speed, DUR);
    while (g.t < target && !g.ended) step(g);
    $("scrub").value = g.t;
  }
  renderer.draw(g);
  updateHud();
  requestAnimationFrame(frame);
}

$("play").addEventListener("click", () => {
  if (g.t >= DUR) rebuildTo(0);
  playing = !playing;
  $("play").textContent = playing ? "⏸ Pause" : "▶ Play";
});
$("speed").value = String(speed);
$("speed").addEventListener("change", (e) => (speed = +e.target.value));
$("scrub").max = DUR;
$("scrub").addEventListener("input", (e) => {
  playing = false; $("play").textContent = "▶ Play"; rebuildTo(+e.target.value);
});

// Fog-of-war toggles. Two checkboxes drive three modes:
//   neither = fog of war (explore as you go)
//   "reveal map" = whole map's static content shown, units only in LOS
//   "show all" = everything visible everywhere (the old spectator view)
function applyFog() {
  const reveal = $("reveal")?.checked, showAll = $("showall")?.checked;
  renderer.setFog(showAll ? "all" : reveal ? "nofog" : "fog");
  renderer.draw(g);
}
$("reveal")?.addEventListener("change", applyFog);
$("showall")?.addEventListener("change", applyFog);
applyFog();

if (GOAL) $("goal").textContent = `/ ${GOAL} goal`;
$("title").textContent = `⚙ AoE2 Engine — ${SCEN}`;

drawChart(scorecard());
requestAnimationFrame(frame);
window.__ev = { game: () => g, rebuildTo };
