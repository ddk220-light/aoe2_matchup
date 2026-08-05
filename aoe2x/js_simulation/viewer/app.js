import { validateMapFixture } from "../src/map-model.js";
import {
  formationUnits,
  validateFormationFixture,
} from "../src/formation-model.js";
import { createMapRenderer } from "./map-renderer.js";
import {
  createPlaybackCursor,
  createReviewFeedback,
  downloadJsonDocument,
  parseReviewSelection,
  selectionUrl,
} from "./simulation-review.js";


const byId = (id) => document.getElementById(id);
const TICKS_PER_SECOND = 60;


function prettyName(value) {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function deepFreeze(value, visited = new Set()) {
  if (!value || typeof value !== "object" || visited.has(value)) return value;
  visited.add(value);
  for (const child of Object.values(value)) deepFreeze(child, visited);
  return Object.freeze(value);
}


function setSelection(record) {
  byId("selectionEmpty").hidden = Boolean(record);
  byId("selectionDetails").hidden = !record;
  if (!record) return;
  const isUnit = Boolean(record.position);
  const position = isUnit ? record.position : record;
  byId("selectedName").textContent = prettyName(record.name);
  byId("selectedPlayer").textContent = isUnit ? `Player ${record.player_id}` : "Gaia";
  byId("selectedId").textContent = String(record.unit_const);
  byId("selectedReference").textContent = String(record.reference_id);
  byId("selectedPosition").textContent = `${position.x.toFixed(2)}, ${position.y.toFixed(2)}`;
  byId("selectedRotation").textContent = `${record.rotation.toFixed(3)} rad`;
}


function renderInventory(counts) {
  const container = byId("objectInventory");
  container.replaceChildren(...Object.entries(counts)
    .sort(([, left], [, right]) => right - left)
    .map(([key, count]) => {
      const row = document.createElement("div");
      row.className = "inventory-row";
      const swatch = document.createElement("span");
      swatch.className = "inventory-swatch";
      const label = document.createElement("span");
      label.textContent = prettyName(key.split(":")[1]);
      const value = document.createElement("b");
      value.textContent = String(count);
      row.append(swatch, label, value);
      return row;
    }));
}


function targetLabel(unit) {
  const values = [
    ["P", unit.pursuitTargetId],
    ["E", unit.engagedTargetId],
    ["A", unit.attackTargetId],
  ].filter(([, target]) => target !== null);
  return values.length ? values.map(([kind, target]) => `${kind}:${target}`).join(" · ") : "no target";
}


function renderUnitTelemetry(snapshot) {
  const rows = snapshot.units.map((unit) => {
    const row = document.createElement("div");
    row.className = `telemetry-row owner-${unit.owner}${unit.alive ? "" : " is-dead"}`;
    const identity = document.createElement("span");
    identity.className = "telemetry-identity";
    identity.textContent = `P${unit.owner} · ${unit.referenceId}`;
    const hp = document.createElement("span");
    hp.className = "telemetry-hp";
    hp.textContent = `${unit.hp}/${unit.mechanics.hp} HP`;
    const meter = document.createElement("i");
    meter.style.setProperty("--hp", `${Math.max(0, unit.hp / unit.mechanics.hp * 100)}%`);
    const state = document.createElement("small");
    state.textContent = `${unit.alive ? unit.action : "dead"} · ${targetLabel(unit)}`;
    row.append(identity, hp, meter, state);
    return row;
  });
  byId("unitTelemetry").replaceChildren(...rows);
  const live = snapshot.units.filter(({ alive }) => alive).length;
  byId("unitCount").textContent = `${live}/${snapshot.units.length} alive`;
}


function eventLabel(event) {
  const subject = event.targetId === undefined
    ? `${event.actorId}`
    : `${event.actorId} → ${event.targetId}`;
  if (event.type === "damage") return `${subject} · −${event.amount} · ${event.hpAfter} HP`;
  if (event.type === "death") return `${subject} · eliminated`;
  if (event.type === "move") return `${subject} · Δ ${event.dx.toFixed(3)}, ${event.dy.toFixed(3)}`;
  return subject;
}


function renderTimeline(events, tick) {
  const firstFuture = events.findIndex((event) => event.tick > tick);
  const split = firstFuture === -1 ? events.length : firstFuture;
  const visible = events.slice(Math.max(0, split - 8), Math.min(events.length, split + 4));
  const rows = visible.map((event) => {
    const row = document.createElement("li");
    row.className = event.tick === tick ? "is-current" : event.tick > tick ? "is-future" : "";
    const time = document.createElement("time");
    time.textContent = `T${String(event.tick).padStart(4, "0")}`;
    const body = document.createElement("span");
    const kind = document.createElement("b");
    kind.textContent = event.type.replaceAll("-", " ");
    const detail = document.createElement("small");
    detail.textContent = eventLabel(event);
    body.append(kind, detail);
    row.append(time, body);
    return row;
  });
  byId("eventTimeline").replaceChildren(...rows);
  byId("eventCount").textContent = `${events.filter((event) => event.tick <= tick).length}/${events.length}`;
}


async function start() {
  const [mapResponse, formationResponse, truthResponse, mechanicsResponse] = await Promise.all([
    fetch("api/map", { cache: "no-store" }),
    fetch("api/formation", { cache: "no-store" }),
    fetch("api/champion/truth", { cache: "no-store" }),
    fetch("api/champion/mechanics", { cache: "no-store" }),
  ]);
  for (const [label, response] of [
    ["Map", mapResponse],
    ["Formation", formationResponse],
    ["Champion truth", truthResponse],
    ["Champion mechanics", mechanicsResponse],
  ]) {
    if (!response.ok) throw new Error(`${label} API returned ${response.status}`);
  }

  const fixture = validateMapFixture(await mapResponse.json());
  const formation = validateFormationFixture(await formationResponse.json());
  const truth = deepFreeze(await truthResponse.json());
  const mechanics = deepFreeze(await mechanicsResponse.json());
  const formationRoster = formationUnits(formation);
  const canvas = byId("mapCanvas");
  const renderer = createMapRenderer(canvas, fixture.map);
  renderer.setUnits(formationRoster);
  const feedback = createReviewFeedback({ storage: localStorage });

  byId("sourceBadge").innerHTML = `
    <span class="seal-dot"></span>
    <span><strong>Clean-room source verified</strong><small>${truth.archive.recordings} tapes · ${fixture.source.filename}</small></span>
  `;
  byId("mapSize").textContent = `${fixture.map.width} × ${fixture.map.height}`;
  byId("tileCount").textContent = fixture.map.tiles.length.toLocaleString();
  byId("objectCount").textContent = fixture.map.gaia_objects.length.toLocaleString();
  byId("player2Count").textContent = formation.sides["2"].length.toLocaleString();
  byId("player3Count").textContent = formation.sides["3"].length.toLocaleString();
  byId("player2Name").textContent = prettyName(formation.sides["2"][0].name);
  byId("player3Name").textContent = prettyName(formation.sides["3"][0].name);
  byId("clockRate").textContent = `${mechanics.clockTicksPerSecond} Hz`;
  byId("sourceFile").textContent = fixture.source.filename;
  byId("sourceHash").textContent = fixture.source.sha256;
  byId("sourceVersion").textContent = `Scenario ${fixture.source.scenario_version} · ${fixture.source.parser} ${fixture.source.parser_version}`;
  renderInventory(fixture.object_counts);

  const initial = parseReviewSelection(location.href);
  byId("ratioSelect").value = initial.ratio;
  byId("repeatSelect").value = String(initial.repeat);
  history.replaceState(null, "", selectionUrl(location.href, initial));

  let selected = initial;
  let activeResult = null;
  let cursor = null;
  let playing = false;
  let animationFrame = null;
  let lastFrameAt = null;
  let tickAccumulator = 0;
  let requestSerial = 0;

  function setPlaying(value) {
    playing = Boolean(value) && Boolean(cursor) && !cursor.atEnd();
    byId("playPause").textContent = playing ? "Pause" : cursor?.atEnd() ? "Replay" : "Play";
    byId("playPause").setAttribute("aria-pressed", String(playing));
    byId("playbackMode").textContent = playing ? "running · 60 Hz" : "paused";
    lastFrameAt = null;
    tickAccumulator = 0;
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    animationFrame = playing ? requestAnimationFrame(animate) : null;
  }

  function present(snapshot) {
    renderer.setSimulationSnapshot(snapshot);
    byId("tickReadout").textContent = String(snapshot.tick).padStart(4, "0");
    byId("secondsReadout").textContent = (snapshot.tick / TICKS_PER_SECOND).toFixed(3);
    renderUnitTelemetry(snapshot);
    renderTimeline(activeResult.playback.events, snapshot.tick);
    byId("mapStatus").innerHTML = `<span class="status-light"></span>${selected.ratio} Champion simulation · tape repeat ${selected.repeat} diagnostic`;
    if (cursor?.atEnd()) setPlaying(false);
  }

  function animate(timestamp) {
    if (!playing) return;
    if (lastFrameAt === null) lastFrameAt = timestamp;
    tickAccumulator += (timestamp - lastFrameAt) * TICKS_PER_SECOND / 1000;
    lastFrameAt = timestamp;
    const steps = Math.min(12, Math.floor(tickAccumulator));
    tickAccumulator -= steps;
    for (let index = 0; index < steps && !cursor.atEnd(); index += 1) cursor.step();
    if (cursor.atEnd()) setPlaying(false);
    else animationFrame = requestAnimationFrame(animate);
  }

  function displayFeedback() {
    const row = feedback.get(selected);
    byId("runFlagged").checked = row.flagged;
    byId("reviewNote").value = row.note;
  }

  async function loadSimulation(nextSelection) {
    const serial = requestSerial += 1;
    setPlaying(false);
    selected = nextSelection;
    history.replaceState(null, "", selectionUrl(location.href, selected));
    byId("playbackMode").textContent = "loading trace";
    byId("mapStatus").innerHTML = `<span class="status-light is-loading"></span>Loading ${selected.ratio} verified playback…`;
    for (const control of ["playPause", "resetPlayback", "stepTick", "nextEvent"]) {
      byId(control).disabled = true;
    }
    const matchup = selected.matchup ?? "champion";
    const endpoint = matchup === "champion"
      ? `api/champion/result?ratio=${encodeURIComponent(selected.ratio)}&repeat=${selected.repeat}`
      : `api/matchup/result?matchup=${encodeURIComponent(matchup)}`
        + `&ratio=${encodeURIComponent(selected.ratio)}&repeat=${selected.repeat}`;
    const response = await fetch(endpoint, { cache: "no-store" });
    if (!response.ok) throw new Error(`Result API returned ${response.status}`);
    const result = deepFreeze(await response.json());
    if (serial !== requestSerial) return;
    activeResult = result;
    cursor = createPlaybackCursor({ snapshots: result.playback.snapshots, onSnapshot: present });
    byId("simWinner").textContent = `Player ${result.playback.winnerOwner}`;
    byId("simWinnerHp").textContent = `${result.playback.winnerHp} HP`;
    byId("tapeWinner").textContent = `Player ${result.tapeDiagnostic.winnerOwner}`;
    byId("tapeWinnerHp").textContent = `${result.tapeDiagnostic.winnerHp} HP`;
    byId("ledgerNumber").textContent = `${selected.ratio.toUpperCase()}–0${selected.repeat}`;
    byId("playPause").textContent = "Play";
    byId("playbackMode").textContent = "paused";
    for (const control of ["playPause", "resetPlayback", "stepTick", "nextEvent"]) {
      byId(control).disabled = false;
    }
    displayFeedback();
  }

  for (const [elementId, option] of [
    ["gridToggle", "grid"],
    ["objectsToggle", "objects"],
    ["footprintsToggle", "footprints"],
    ["labelsToggle", "labels"],
  ]) {
    byId(elementId).addEventListener("change", (event) => {
      renderer.setOption(option, event.currentTarget.checked);
    });
  }
  // Top-down removes the 2:1 isometric squash so overlap and obstruction can be
  // read directly: collision boxes are axis-aligned squares in world space and
  // only look like squares here.
  byId("topDownToggle").addEventListener("change", (event) => {
    renderer.setProjection(event.currentTarget.checked ? "orthographic" : "isometric");
  });
  byId("resetView").addEventListener("click", () => renderer.resetView());

  const CHAMPION_RATIO_OPTIONS = ["1v1", "2v1", "2v3", "5v3", "6v3"];
  let matchupRatioOptions = null;

  async function ratiosFor(matchup) {
    if (matchup === "champion") return CHAMPION_RATIO_OPTIONS;
    if (!matchupRatioOptions) {
      const listed = await (await fetch("api/matchup/list", { cache: "no-store" })).json();
      matchupRatioOptions = new Map(listed.matchups.map((m) => [m.name, m.ratios]));
    }
    return matchupRatioOptions.get(matchup) ?? CHAMPION_RATIO_OPTIONS;
  }

  async function repopulateRatios(matchup) {
    const ratios = await ratiosFor(matchup);
    const select = byId("ratioSelect");
    const previous = select.value;
    select.replaceChildren(...ratios.map((ratio) => {
      const option = document.createElement("option");
      option.value = ratio;
      option.textContent = ratio.replace("v", " vs ");
      return option;
    }));
    select.value = ratios.includes(previous) ? previous : ratios[0];
    return select.value;
  }

  byId("matchupSelect").addEventListener("change", () => {
    const matchup = byId("matchupSelect").value;
    repopulateRatios(matchup)
      .then((ratio) => loadSimulation({
        matchup,
        ratio,
        repeat: Number(byId("repeatSelect").value),
      }))
      .catch(showError);
  });

  for (const id of ["ratioSelect", "repeatSelect"]) {
    byId(id).addEventListener("change", () => {
      loadSimulation({
        matchup: byId("matchupSelect").value,
        ratio: byId("ratioSelect").value,
        repeat: Number(byId("repeatSelect").value),
      }).catch(showError);
    });
  }
  byId("playPause").addEventListener("click", () => {
    if (cursor?.atEnd()) cursor.reset();
    setPlaying(!playing);
  });
  byId("resetPlayback").addEventListener("click", () => {
    setPlaying(false);
    cursor?.reset();
  });
  byId("stepTick").addEventListener("click", () => {
    setPlaying(false);
    cursor?.step();
  });
  byId("nextEvent").addEventListener("click", () => {
    setPlaying(false);
    cursor?.nextEvent();
  });
  byId("returnFormation").addEventListener("click", () => {
    setPlaying(false);
    renderer.showFormation();
    byId("mapStatus").innerHTML = '<span class="status-light"></span>Locked 21 vs 21 melee formation';
    byId("playbackMode").textContent = "formation";
  });

  function saveFeedback() {
    feedback.set({
      ...selected,
      flagged: byId("runFlagged").checked,
      note: byId("reviewNote").value,
    });
  }
  byId("runFlagged").addEventListener("change", saveFeedback);
  byId("reviewNote").addEventListener("input", saveFeedback);
  byId("clearFeedback").addEventListener("click", () => {
    feedback.clear();
    displayFeedback();
  });
  byId("exportFeedback").addEventListener("click", () => {
    downloadJsonDocument({
      value: feedback.exportJson(),
      filename: "champion-simulation-review.json",
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea, select, button")) return;
    if (event.code === "Space") {
      event.preventDefault();
      byId("playPause").click();
    } else if (event.key === "ArrowRight" && event.shiftKey) {
      event.preventDefault();
      byId("nextEvent").click();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      byId("stepTick").click();
    } else if (event.key === "Home") {
      event.preventDefault();
      byId("resetPlayback").click();
    } else if (event.key.toLowerCase() === "f") {
      byId("returnFormation").click();
    }
  });

  const pointers = new Map();
  let moved = false;
  let lastCentroid = null;
  let lastDistance = null;

  function pointerCentroid() {
    const values = [...pointers.values()];
    return {
      x: values.reduce((sum, point) => sum + point.x, 0) / values.length,
      y: values.reduce((sum, point) => sum + point.y, 0) / values.length,
    };
  }

  function pointerDistance() {
    const values = [...pointers.values()];
    if (values.length < 2) return null;
    return Math.hypot(values[0].x - values[1].x, values[0].y - values[1].y);
  }

  canvas.addEventListener("pointerdown", (event) => {
    canvas.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.offsetX, y: event.offsetY });
    moved = false;
    lastCentroid = pointerCentroid();
    lastDistance = pointerDistance();
  });

  canvas.addEventListener("pointermove", (event) => {
    const inspection = renderer.inspectAt(event.offsetX, event.offsetY);
    const inMap = inspection.tile.x >= 0 && inspection.tile.x < 16 && inspection.tile.y >= 0 && inspection.tile.y < 16;
    byId("cursorReadout").textContent = inMap
      ? `Tile ${inspection.tile.x.toFixed(2)}, ${inspection.tile.y.toFixed(2)}`
      : "Tile —, —";

    if (!pointers.has(event.pointerId)) {
      renderer.setHovered(inspection.object);
      return;
    }

    pointers.set(event.pointerId, { x: event.offsetX, y: event.offsetY });
    const centroid = pointerCentroid();
    const distance = pointerDistance();
    const deltaX = centroid.x - lastCentroid.x;
    const deltaY = centroid.y - lastCentroid.y;
    if (Math.abs(deltaX) + Math.abs(deltaY) > 0.5) moved = true;
    renderer.panBy(deltaX, deltaY);
    if (distance && lastDistance && Math.abs(distance - lastDistance) > 0.5) {
      renderer.zoomAt(distance / lastDistance, centroid.x, centroid.y);
      moved = true;
    }
    lastCentroid = centroid;
    lastDistance = distance;
  });

  function releasePointer(event) {
    if (!pointers.has(event.pointerId)) return;
    pointers.delete(event.pointerId);
    if (!moved && pointers.size === 0) {
      const inspection = renderer.inspectAt(event.offsetX, event.offsetY);
      const selectedRecord = inspection.unit || inspection.object;
      renderer.setSelected(inspection.unit ? null : inspection.object);
      renderer.setSelectedUnit(inspection.unit);
      setSelection(selectedRecord);
    }
    lastCentroid = pointers.size ? pointerCentroid() : null;
    lastDistance = pointerDistance();
  }

  canvas.addEventListener("pointerup", releasePointer);
  canvas.addEventListener("pointercancel", releasePointer);
  canvas.addEventListener("pointerleave", () => renderer.setHovered(null));
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    renderer.zoomAt(event.deltaY < 0 ? 1.12 : 0.89, event.offsetX, event.offsetY);
  }, { passive: false });

  const observer = new ResizeObserver(() => renderer.resize());
  observer.observe(canvas);
  renderer.resize();
  await loadSimulation(initial);
}


function showError(error) {
  const panel = byId("errorPanel");
  panel.hidden = false;
  panel.textContent = `The combat chronograph could not continue: ${error.message}`;
  console.error(error);
}


start().catch(showError);
