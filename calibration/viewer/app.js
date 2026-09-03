const $ = (id) => document.getElementById(id);
const STEP = 1 / 60;
const MAX_SECONDS = 600;

let catalog;
let family;
let recording;
let variantId = "base";
let engine;
let constants;
let renderer;
let sim = null;
let running = false;
let raf = null;
let lastFrame = null;
let tickCarry = 0;
let boardBusy = false;

const fmt = (value, digits = 1) => Number(value).toFixed(digits);
const hpPct = (team) => {
  const max = team.reduce((sum, unit) => sum + unit.maxHp, 0);
  const hp = team.filter((unit) => unit.state !== "dead").reduce((sum, unit) => sum + unit.currentHp, 0);
  return max ? (100 * hp) / max : 0;
};
const living = (team) => team.filter((unit) => unit.state !== "dead");

function setError(message = "") {
  $("error").textContent = message;
}

function selectedFamily() {
  return catalog.families.find((item) => item.id === $("matchup").value);
}

function selectedRecording() {
  return family.recordings.find((item) => item.tag === $("recording").value);
}

function updateUrl() {
  const params = new URLSearchParams({
    match: family.id,
    variant: variantId,
    tag: recording.tag,
    seed: String(currentSeed()),
  });
  history.replaceState(null, "", `?${params}`);
}

function currentSeed() {
  return Math.max(1, Number.parseInt($("seed").value, 10) || 1) >>> 0;
}

function populateMatchups(initial) {
  $("matchup").innerHTML = catalog.families.map((item) =>
    `<option value="${item.id}">#${item.rank} · ${item.label}</option>`
  ).join("");
  if (catalog.families.some((item) => item.id === initial)) $("matchup").value = initial;
}

function populateVariants(initial) {
  $("variant").innerHTML = Object.entries(catalog.variants).map(([id, item]) =>
    `<option value="${id}">${item.label}</option>`
  ).join("");
  if (catalog.variants[initial]) $("variant").value = initial;
}

function populateRecordings(wantedTag = null) {
  family = selectedFamily();
  $("recording").innerHTML = family.recordings.map((item) => {
    const truth = item.tape;
    return `<option value="${item.tag}">${item.tag.replace(family.id, "run")}: ${truth.winner_label} ${fmt(truth.winner_hp_pct)}% · ${fmt(item.duration_s)}s</option>`;
  }).join("");
  const target = family.recordings.some((item) => item.tag === wantedTag)
    ? wantedTag
    : family.representative_tag;
  $("recording").value = target;
  recording = selectedRecording();
  renderTruthCards();
}

function renderTruthCards() {
  const tape = family.tape;
  const base = family.baseline;
  $("tapeTruth").innerHTML = `${tape.winner_label} <span class="good">${fmt(tape.winner_hp_pct)}%</span>`;
  $("tapeMeta").textContent = `${tape.winner_runs}/${tape.recordings} tape wins · representative ${family.representative_tag}`;
  $("baseTruth").innerHTML = `${base.winner_label} <span class="${base.wrong_winner ? "danger" : ""}">${fmt(base.winner_hp_pct)}%</span>`;
  $("baseMeta").textContent = `${base.wrong_winner ? "WRONG WINNER · " : ""}${fmt(base.signed_gap_pp)} percentage-point signed gap · ${base.samples} sim samples`;
  $("activeTag").textContent = recording.tag;
  $("liveTruth").textContent = "not run";
  $("liveMeta").textContent = `Selected tape: ${recording.tape.winner_label} ${fmt(recording.tape.winner_hp_pct)}% in ${fmt(recording.duration_s)}s.`;
}

function renderVariantNote() {
  const variant = catalog.variants[variantId];
  $("variantCode").textContent = variant.short;
  $("variantNote").textContent = variant.description;
}

async function loadVariant(id) {
  variantId = id;
  [engine, constants] = await Promise.all([
    import(`/bundle/${id}/engine/index.js`),
    import(`/bundle/${id}/engine/constants.js`),
  ]);
  const rendererModule = await import(`/bundle/${id}/physics_renderer.js`);
  renderer = new rendererModule.PhysicsSimRenderer($("battle"));
  configureFlags();
  renderVariantNote();
}

function configureFlags() {
  const spec = catalog.variants[variantId].flags || {};
  if (spec.c3 && constants.setC3) {
    constants.setC3(Object.fromEntries(spec.c3.map((name) => [name, true])));
  }
  if (spec.h2 && constants.setH2) {
    constants.setH2(Object.fromEntries(spec.h2.map((name) => [name, true])));
  }
}

function makeSimulation(seed) {
  configureFlags();
  const teams = recording.teams.map((team, index) => ({
    combatDict: team.combat_dict,
    slug: team.slug,
    civ: team.civ,
    count: team.count,
    positions: recording.positions[String(index + 1)],
  }));
  return engine.createSimulation({
    teams,
    seed,
    arena: catalog.variants[variantId].arena,
  });
}

function resetBattle(autoplay = false) {
  stopAnimation();
  setError();
  sim = makeSimulation(currentSeed());
  renderer.setLabels({
    team1Civ: recording.teams[0].civ,
    team1Unit: recording.teams[0].label,
    team2Civ: recording.teams[1].civ,
    team2Unit: recording.teams[1].label,
  });
  $("team1Name").textContent = `${recording.teams[0].label} ×${recording.teams[0].count}`;
  $("team2Name").textContent = `${recording.teams[1].label} ×${recording.teams[1].count}`;
  $("seedEcho").textContent = `${variantId.toUpperCase()} · seed ${currentSeed()} · exact FINAL spawn`;
  $("pause").disabled = false;
  $("step").disabled = false;
  tickCarry = 0;
  paint();
  updateUrl();
  if (autoplay) startAnimation();
}

function stopAnimation() {
  running = false;
  lastFrame = null;
  if (raf !== null) cancelAnimationFrame(raf);
  raf = null;
  $("pause").textContent = "Resume";
}

function startAnimation() {
  if (!sim) resetBattle(false);
  if (sim.winner !== null || sim.battleTime >= MAX_SECONDS) resetBattle(false);
  running = true;
  lastFrame = null;
  $("pause").textContent = "Pause";
  raf = requestAnimationFrame(frame);
}

function frame(now) {
  if (!running || !sim) return;
  if (lastFrame === null) lastFrame = now;
  const elapsed = Math.min(0.1, (now - lastFrame) / 1000);
  lastFrame = now;
  const speed = Number.parseFloat($("speed").value) || 1;
  tickCarry += (elapsed * speed) / STEP;
  const steps = Math.min(90, Math.floor(tickCarry));
  tickCarry -= steps;
  for (let i = 0; i < steps && sim.winner === null && sim.battleTime < MAX_SECONDS; i++) {
    sim.step(STEP);
  }
  paint();
  if (sim.winner !== null || sim.battleTime >= MAX_SECONDS) {
    stopAnimation();
    showOutcome(sim);
    return;
  }
  raf = requestAnimationFrame(frame);
}

function stepOnce() {
  if (!sim) resetBattle(false);
  stopAnimation();
  if (sim.winner === null && sim.battleTime < MAX_SECONDS) sim.step(STEP);
  paint();
  if (sim.winner !== null) showOutcome(sim);
}

function drawTargetOverlay() {
  const ctx = renderer.ctx;
  ctx.save();
  ctx.setTransform(renderer.renderScaleX, 0, 0, renderer.renderScaleY, 0, 0);
  ctx.lineWidth = 0.7;
  ctx.globalAlpha = 0.14;
  for (const unit of [...sim.team1, ...sim.team2]) {
    if (unit.state === "dead" || !unit.target || unit.target.state === "dead") continue;
    ctx.strokeStyle = unit.team === 1 ? "#62b8ff" : "#ff6961";
    ctx.beginPath();
    ctx.moveTo(unit.x, unit.y);
    ctx.lineTo(unit.target.x, unit.target.y);
    ctx.stroke();
  }
  ctx.restore();
}

function metricRows(team, teamNo) {
  const alive = living(team);
  const states = Counter(alive.map((unit) => unit.state));
  const stats = sim.combatStats[teamNo];
  return [
    ["alive", `${alive.length} / ${team.length}`],
    ["army HP", `${fmt(hpPct(team))}%`],
    ["moving / kiting", `${states.moving || 0} / ${states.kiting || 0}`],
    ["attacking / committed", `${states.attacking || 0} / ${states.committed || 0}`],
    ["swings / hits", `${stats.swings} / ${stats.hitsLanded}`],
    ["damage dealt", fmt(stats.damageDealt, 0)],
  ].map(([label, value]) => `<div class="metric-row"><span>${label}</span><span>${value}</span></div>`).join("");
}

function Counter(values) {
  return values.reduce((counts, value) => {
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

function paint() {
  if (!sim || !renderer) return;
  renderer.render(sim);
  drawTargetOverlay();
  $("clock").textContent = `${fmt(sim.battleTime)}s`;
  $("team1Metrics").innerHTML = metricRows(sim.team1, 1);
  $("team2Metrics").innerHTML = metricRows(sim.team2, 2);
  if (sim.winner === null) {
    const lead = hpPct(sim.team1) >= hpPct(sim.team2) ? 1 : 2;
    const team = lead === 1 ? sim.team1 : sim.team2;
    $("liveTruth").innerHTML = `${recording.teams[lead - 1].label} <span>${fmt(hpPct(team))}%</span>`;
    $("liveMeta").textContent = `Live leader at ${fmt(sim.battleTime)}s · ${variantId.toUpperCase()} seed ${currentSeed()}.`;
  }
}

function outcomeOf(result) {
  if (result.winner !== 1 && result.winner !== 2) {
    return { winner: result.winner === 0 ? "Mutual" : "600s cap", hp: 0 };
  }
  const team = result.winner === 1 ? result.team1 : result.team2;
  return { winner: recording.teams[result.winner - 1].label, hp: hpPct(team) };
}

function showOutcome(result) {
  const out = outcomeOf(result);
  $("liveTruth").innerHTML = `${out.winner} <span class="good">${fmt(out.hp)}%</span>`;
  $("liveMeta").textContent = `${variantId.toUpperCase()} · seed ${currentSeed()} · ${fmt(result.battleTime)}s.`;
}

function runToEnd(seed) {
  const result = makeSimulation(seed);
  const maxTicks = Math.round(MAX_SECONDS / STEP);
  let ticks = 0;
  while (result.winner === null && ticks < maxTicks) {
    result.step(STEP);
    ticks++;
  }
  return result;
}

async function runFive() {
  if (boardBusy) return;
  boardBusy = true;
  $("boardRun").disabled = true;
  $("runFive").disabled = true;
  $("boardBody").innerHTML = "";
  const seed0 = currentSeed();
  const outcomes = [];
  const started = performance.now();
  try {
    for (let i = 0; i < 5; i++) {
      $("boardStatus").textContent = `running ${i + 1}/5…`;
      await new Promise((resolve) => setTimeout(resolve, 0));
      const result = runToEnd(seed0 + i);
      const out = outcomeOf(result);
      outcomes.push(out);
      const row = document.createElement("tr");
      row.innerHTML = `<td>${seed0 + i}</td><td>${out.winner}</td><td>${fmt(result.battleTime)}s</td><td>${fmt(out.hp)}%</td>`;
      $("boardBody").appendChild(row);
    }
    const winners = Counter(outcomes.map((item) => item.winner));
    const modal = Object.entries(winners).sort((a, b) => b[1] - a[1])[0][0];
    const hp = outcomes.filter((item) => item.winner === modal).map((item) => item.hp).sort((a, b) => a - b);
    const median = hp.length % 2 ? hp[(hp.length - 1) / 2] : (hp[hp.length / 2 - 1] + hp[hp.length / 2]) / 2;
    $("boardStatus").textContent = `${modal} median ${fmt(median)}% · ${fmt((performance.now() - started) / 1000)}s wall time`;
  } catch (error) {
    setError(error.stack || error.message || String(error));
  } finally {
    boardBusy = false;
    $("boardRun").disabled = false;
    $("runFive").disabled = false;
  }
}

async function changeVariant(id) {
  stopAnimation();
  setError();
  try {
    await loadVariant(id);
    resetBattle(false);
  } catch (error) {
    setError(error.stack || error.message || String(error));
  }
}

function wire() {
  $("matchup").addEventListener("change", () => {
    populateRecordings();
    resetBattle(false);
  });
  $("recording").addEventListener("change", () => {
    recording = selectedRecording();
    renderTruthCards();
    resetBattle(false);
  });
  $("variant").addEventListener("change", (event) => changeVariant(event.target.value));
  $("seed").addEventListener("change", () => resetBattle(false));
  $("run").addEventListener("click", () => resetBattle(true));
  $("pause").addEventListener("click", () => running ? stopAnimation() : startAnimation());
  $("play").addEventListener("click", startAnimation);
  $("step").addEventListener("click", stepOnce);
  $("single").addEventListener("click", stepOnce);
  $("reset").addEventListener("click", () => resetBattle(false));
  $("rewind").addEventListener("click", () => resetBattle(false));
  $("runFive").addEventListener("click", runFive);
  $("boardRun").addEventListener("click", runFive);
  $("boardClear").addEventListener("click", () => {
    $("boardBody").innerHTML = "";
    $("boardStatus").textContent = "";
  });
}

async function init() {
  try {
    catalog = await fetch("/api/catalog", { cache: "no-store" }).then((response) => {
      if (!response.ok) throw new Error(`catalog HTTP ${response.status}`);
      return response.json();
    });
    $("archive").textContent = `${catalog.source.archive} · ${catalog.source.recordings} runs`;
    $("hash").textContent = `SHA-256 ${catalog.source.sha256.slice(0, 16)}…`;
    const query = new URLSearchParams(location.search);
    populateMatchups(query.get("match"));
    populateVariants(query.get("variant"));
    family = selectedFamily();
    populateRecordings(query.get("tag"));
    if (query.get("seed")) $("seed").value = query.get("seed");
    variantId = $("variant").value;
    wire();
    await loadVariant(variantId);
    resetBattle(false);
  } catch (error) {
    setError(error.stack || error.message || String(error));
  }
}

init();
