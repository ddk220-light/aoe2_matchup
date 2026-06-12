// Viewer wiring: load scenario, drive the engine in real time, render,
// and show the verification overlay (scorecard + wood chart).
import { createGame, step, run } from "./engine.js";
import { createRenderer } from "./render.js";

const $ = (id) => document.getElementById(id);
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

const scen = await (await fetch("data/4_lumber/commands.json")).json();
const truth = await (await fetch("data/4_lumber/truth.json")).json();

const tree = scen.entities.find((e) => e.type === "tree");
scen.treeId = tree.id;
scen.treeX = tree.x;
scen.treeY = tree.y;

// ---------------------------------------------------------------- sim state
let g = createGame(scen);
g.treeWasRemoved = false;
let playing = false;
let speed = 2;
const DUR = Math.ceil(scen.duration);

function rebuildTo(t) {
  g = createGame(scen);
  run(g, Math.max(0, Math.min(t, DUR)));
  g.treeWasRemoved = !g.ents.has(scen.treeId) && g.t > 1;
  updateHud();
}

function updateHud() {
  $("clock").textContent = fmt(g.t);
  $("wood").textContent = Math.round(g.wood);
  const tr = g.ents.get(scen.treeId);
  $("status").textContent = tr
    ? `tree: ${tr.wood.toFixed(1)} wood`
    : (g.t > 1 ? "tree exhausted" : "");
}

// ------------------------------------------------------------ verification
// Scoring mirrors verify/verify.mjs (keep in lockstep) — runs a throwaway
// full sim, pairs deposits by villager id + spawn-order, builds the panel.
function scorecard() {
  const fullG = run(createGame(scen), scen.duration + 1);
  const dep = fullG.events.filter((e) => e.kind === "deposit");
  const spawnEvents = fullG.events.filter((e) => e.kind === "spawn");
  const empty = fullG.events.find((e) => e.kind === "tree_empty");
  const checks = [];
  const add = (name, ok, detail) => checks.push({ name, ok, detail });

  const sp = spawnEvents[0];
  add("4th villager spawn ±0.5s", !!sp && Math.abs(sp.t - truth.spawn.t) <= 0.5,
      `${truth.spawn.t} → ${sp?.t ?? "—"}`);

  const eidMap = new Map();
  (truth.spawns ?? [truth.spawn]).forEach((ts, i) => {
    if (spawnEvents[i]) eidMap.set(ts.eid, spawnEvents[i].eid);
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
    const tol = td.amount >= 9.5 ? 1.5 : 4.0;
    const ok = !!best && Math.abs(best.t - td.t) <= tol
               && Math.abs(best.amount - td.amount) <= 0.5;
    add(`deposit v${td.eid} #${k + 1}`, ok,
        `${td.t}s/${td.amount} → ${best ? `${best.t}s/${best.amount}` : "—"}`);
    if (best) matched++;
  }
  add("no extra deposits", dep.length === matched, `${dep.length - matched} extra`);
  add("tree empty ±3s", !!empty && Math.abs(empty.t - truth.tree.empty_t) <= 3,
      `${truth.tree.empty_t} → ${empty?.t ?? "—"}`);
  const total = dep.reduce((s, d) => s + d.amount, 0);
  add("total wood ±1", Math.abs(total - truth.total_delivered) <= 1,
      `${truth.total_delivered} → ${total.toFixed(1)}`);
  const vills = [...fullG.ents.values()].filter((e) => e.type === "villager").length;
  add("villager count = 4", vills === 4, `${vills}`);

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
  head.style.fontWeight = "700";
  head.style.borderBottom = "1px solid var(--line)";
  head.style.marginBottom = "4px";
  head.innerHTML = fails
    ? `<span style="color:var(--bad)">${fails}/${checks.length} checks failed</span>`
    : `<span style="color:var(--ok)">ALL ${checks.length} CHECKS PASS</span>`;
  el.prepend(head);
  return { sim: fullG, dep };
}

// --------------------------------------------------------------- wood chart
function drawChart(dep) {
  const cv = $("chart");
  const ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height, PAD = 8;
  ctx.clearRect(0, 0, W, H);
  const x = (t) => PAD + (t / DUR) * (W - 2 * PAD);
  const yMax = 260;
  const y = (w) => H - PAD - (w / yMax) * (H - 2 * PAD);

  const stepLine = (deposits, start, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    let wood = start, px = x(0), py = y(wood);
    ctx.moveTo(px, py);
    for (const d of [...deposits].sort((a, b) => a.t - b.t)) {
      ctx.lineTo(x(d.t), py);
      wood += d.amount;
      py = y(wood);
      ctx.lineTo(x(d.t), py);
    }
    ctx.lineTo(x(DUR), py);
    ctx.stroke();
  };
  // truth tree wood (green, scaled to same axis)
  ctx.strokeStyle = "rgba(111,191,95,.8)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  truth.rows.forEach((r, i) => {
    const yy = y(r.tree_wood);
    if (i === 0) ctx.moveTo(x(r.t), yy); else ctx.lineTo(x(r.t), yy);
  });
  ctx.stroke();
  stepLine(truth.deposits, 150, "rgba(79,127,217,.9)");
  stepLine(dep, 150, "rgba(212,168,67,.95)");
}

// --------------------------------------------------------------- main loop
const renderer = createRenderer($("view"), scen);

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (playing && g.t < DUR) {
    const target = Math.min(g.t + dt * speed, DUR);
    while (g.t < target && !g.ended) step(g);
    if (!g.ents.has(scen.treeId) && g.t > 1) g.treeWasRemoved = true;
    $("scrub").value = g.t;
  }
  renderer.draw(g, scen);
  updateHud();
  requestAnimationFrame(frame);
}

$("play").addEventListener("click", () => {
  if (g.t >= DUR) rebuildTo(0);
  playing = !playing;
  $("play").textContent = playing ? "⏸ Pause" : "▶ Play";
});
$("speed").addEventListener("change", (e) => (speed = +e.target.value));
$("scrub").addEventListener("input", (e) => {
  playing = false;
  $("play").textContent = "▶ Play";
  rebuildTo(+e.target.value);
});
$("scrub").max = DUR;

const { dep } = scorecard();
drawChart(dep);
requestAnimationFrame(frame);

// Debug hook (used by automated checks; harmless in production).
window.__ev = { game: () => g, rebuildTo };
