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


function renderUnitTelemetry(snapshot, index) {
  const rows = snapshot.units.map(([referenceId, , , , hp, alive, action,
    pursuitTargetId, engagedTargetId, attackTargetId]) => {
    const meta = index[referenceId];
    const row = document.createElement("div");
    row.className = `telemetry-row owner-${meta.owner}${alive ? "" : " is-dead"}`;
    const identity = document.createElement("span");
    identity.className = "telemetry-identity";
    identity.textContent = `P${meta.owner} · ${referenceId}`;
    const hpText = document.createElement("span");
    hpText.className = "telemetry-hp";
    hpText.textContent = `${hp}/${meta.maxHp} HP`;
    const meter = document.createElement("i");
    meter.style.setProperty("--hp", `${Math.max(0, hp / meta.maxHp * 100)}%`);
    const state = document.createElement("small");
    state.textContent = `${alive ? action : "dead"} · ${targetLabel(
      { pursuitTargetId, engagedTargetId, attackTargetId })}`;
    row.append(identity, hpText, meter, state);
    return row;
  });
  byId("unitTelemetry").replaceChildren(...rows);
  const live = snapshot.units.filter(([, , , , , alive]) => alive).length;
  byId("unitCount").textContent = `${live}/${snapshot.units.length} alive`;
}


// The status line carries server text (rejection messages among it), so it is
// built from nodes and textContent -- never an innerHTML template a `<` in an
// error string could break out of.
function setMapStatus(text, { loading = false } = {}) {
  const light = document.createElement("span");
  light.className = loading ? "status-light is-loading" : "status-light";
  byId("mapStatus").replaceChildren(light, document.createTextNode(text));
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
  const [mapResponse, formationResponse, unitsResponse] = await Promise.all([
    fetch("api/map", { cache: "no-store" }),
    fetch("api/formation", { cache: "no-store" }),
    fetch("api/units", { cache: "no-store" }),
  ]);
  for (const [label, response] of [
    ["Map", mapResponse],
    ["Formation", formationResponse],
    ["Units", unitsResponse],
  ]) {
    if (!response.ok) throw new Error(`${label} API returned ${response.status}`);
  }
  const catalogue = deepFreeze(await unitsResponse.json());

  const fixture = validateMapFixture(await mapResponse.json());
  const formation = validateFormationFixture(await formationResponse.json());
  const formationRoster = formationUnits(formation);
  const canvas = byId("mapCanvas");
  const renderer = createMapRenderer(canvas, fixture.map);
  renderer.setUnits(formationRoster);
  const feedback = createReviewFeedback({ storage: localStorage });

  byId("sourceBadge").innerHTML = `
    <span class="seal-dot"></span>
    <span><strong>Clean-room engine</strong><small>${catalogue.units.length} measured units · ${fixture.source.filename}</small></span>
  `;
  byId("clockRate").textContent = `${TICKS_PER_SECOND} Hz`;
  byId("mapSize").textContent = `${fixture.map.width} × ${fixture.map.height}`;
  byId("tileCount").textContent = fixture.map.tiles.length.toLocaleString();
  byId("objectCount").textContent = fixture.map.gaia_objects.length.toLocaleString();
  byId("player2Count").textContent = formation.sides["2"].length.toLocaleString();
  byId("player3Count").textContent = formation.sides["3"].length.toLocaleString();
  byId("player2Name").textContent = prettyName(formation.sides["2"][0].name);
  byId("player3Name").textContent = prettyName(formation.sides["3"][0].name);
  byId("sourceFile").textContent = fixture.source.filename;
  byId("sourceHash").textContent = fixture.source.sha256;
  byId("sourceVersion").textContent = `Scenario ${fixture.source.scenario_version} · ${fixture.source.parser} ${fixture.source.parser_version}`;
  renderInventory(fixture.object_counts);

  function populateUnitSelects() {
    for (const [id, fallback] of [["side2Select", "champion"], ["side3Select", "paladin"]]) {
      const select = byId(id);
      select.replaceChildren(...catalogue.units.map(({ slug, label, civ }) => {
        const option = document.createElement("option");
        option.value = slug;
        option.textContent = `${label} (${civ})`;
        return option;
      }));
      select.value = fallback;
    }
  }
  populateUnitSelects();

  // Mirrors placement.js's resolveFamily so the picker can size its own count
  // inputs -- kept as the one place that reads the four conditions, rather
  // than duplicating them at each call site.
  const classBySlug = new Map(catalogue.units.map(({ slug, class: unitClass }) => [slug, unitClass]));
  const RANGED_CLASSES = new Set(["mobile_ranged", "siege_ranged"]);
  function familyFor(side2Class, side3Class) {
    if (RANGED_CLASSES.has(side2Class) && RANGED_CLASSES.has(side3Class)) return "rvr";
    if (side2Class === "mobile_ranged" || side3Class === "mobile_ranged") return "kite";
    if (side2Class === "siege_ranged" || side3Class === "siege_ranged") return "siege";
    return "waves";
  }

  // Capacity is per (owner, family) -- e.g. a side-2 siege formation holds 16,
  // not 21 -- so the count inputs' ceilings have to track whichever pair is
  // currently selected instead of the flat max="21" they boot with.
  function syncCountCaps() {
    const family = familyFor(
      classBySlug.get(byId("side2Select").value),
      classBySlug.get(byId("side3Select").value),
    );
    const capacity = catalogue.capacityByFamily[family];
    byId("n2Input").max = String(capacity.side2);
    byId("n3Input").max = String(capacity.side3);
  }
  syncCountCaps();

  function currentSelection() {
    return {
      side2Slug: byId("side2Select").value,
      n2: Number(byId("n2Input").value),
      side3Slug: byId("side3Select").value,
      n3: Number(byId("n3Input").value),
    };
  }

  // Boot with no counts: the server derives the even-fight purchase and the
  // inputs are filled in from what it chose.
  let selected = {
    side2Slug: byId("side2Select").value,
    side3Slug: byId("side3Select").value,
  };
  let activeResult = null;
  let eventLog = [];
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
    // map-renderer requires DEEPLY frozen objects in the legacy unit shape, so
    // the slim positional records are rehydrated here and nowhere else. Note
    // alive is 1|0 on the wire and the renderer tests `=== false`. The three
    // target ids are rehydrated too -- the map overlay's pursuit/engaged/attack
    // lines read them straight off each unit.
    renderer.setSimulationSnapshot(Object.freeze({
      tick: snapshot.tick,
      units: Object.freeze(snapshot.units.map(
        ([referenceId, x, y, facing, hp, alive, action,
          pursuitTargetId, engagedTargetId, attackTargetId]) => {
          const meta = activeResult.unitIndex[referenceId];
          return Object.freeze({
            referenceId, x, y, facing, hp, action,
            pursuitTargetId, engagedTargetId, attackTargetId,
            alive: alive === 1,
            owner: meta.owner,
            label: meta.label,
            unitMaster: meta.master,
            mechanics: Object.freeze({
              hp: meta.maxHp,
              attack_range_tiles: meta.attackRange,
              collision_size_tiles: Object.freeze({ x: meta.collisionRadius }),
            }),
          });
        })),
      events: snapshot.events,
    }));
    byId("tickReadout").textContent = String(snapshot.tick).padStart(4, "0");
    byId("secondsReadout").textContent = (snapshot.tick / TICKS_PER_SECOND).toFixed(3);
    renderUnitTelemetry(snapshot, activeResult.unitIndex);
    renderTimeline(eventLog, snapshot.tick);
    setMapStatus(`${activeResult.side2.label} ${activeResult.side2.count}`
      + ` vs ${activeResult.side3.label} ${activeResult.side3.count}`);
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
    const key = feedbackKey();
    const row = key ? feedback.get(key) : { flagged: false, note: "" };
    byId("runFlagged").checked = row.flagged;
    byId("reviewNote").value = row.note;
  }

  async function loadSimulation(nextSelection) {
    const serial = requestSerial += 1;
    setPlaying(false);
    selected = nextSelection;
    byId("playbackMode").textContent = "loading trace";
    // n2/n3 are absent while a derived-count request is in flight (every unit
    // change, and the very first boot request) -- fall back to a placeholder
    // rather than printing the literal word "undefined".
    setMapStatus(`Running ${selected.n2 ?? "…"}v${selected.n3 ?? "…"}…`, { loading: true });
    for (const control of ["playPause", "resetPlayback", "stepTick", "nextEvent"]) {
      byId(control).disabled = true;
    }
    // Counts are omitted entirely when the caller wants the derived purchase;
    // the server sends back what it chose and the inputs are synced from it.
    const counts = selected.n2 === undefined || selected.n3 === undefined
      ? "" : `&n2=${selected.n2}&n3=${selected.n3}`;
    const endpoint = `api/fight?side2=${encodeURIComponent(selected.side2Slug)}`
      + `&side3=${encodeURIComponent(selected.side3Slug)}${counts}`;
    const response = await fetch(endpoint, { cache: "no-store" });
    // Checked immediately on the freshest signal available (before spending
    // time on response.ok or parsing a body) so a superseded request never
    // touches the UI, whichever way it resolved.
    if (serial !== requestSerial) return;
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      if (serial !== requestSerial) return;
      rejectFight(detail?.error ?? `Fight API returned ${response.status}`);
      return;
    }
    const result = deepFreeze(await response.json());
    if (serial !== requestSerial) return;
    activeResult = result;
    // The wire carries events per snapshot (movement filtered out); the
    // timeline wants one flat list, so flatten it once rather than per frame.
    eventLog = result.snapshots.flatMap(({ events }) => events);
    // Whatever the server ran is what the inputs show, derived or not.
    selected = { ...selected, n2: result.side2.count, n3: result.side3.count };
    byId("n2Input").value = String(result.side2.count);
    byId("n3Input").value = String(result.side3.count);
    cursor = createPlaybackCursor({ snapshots: result.snapshots, onSnapshot: present });
    byId("simWinner").textContent = result.winnerOwner === null
      ? "—" : `Player ${result.winnerOwner}`;
    byId("simWinnerHp").textContent = `${result.winnerHp} HP`;
    byId("player2Name").textContent = result.side2.label;
    byId("player3Name").textContent = result.side3.label;
    byId("player2Count").textContent = String(result.side2.count);
    byId("player3Count").textContent = String(result.side3.count);
    // Computed from the fight that ran, not a fixed 21v21 literal. The
    // orientation note is the one place the viewer says out loud that an
    // asymmetric pair was run in the archive's measured orientation rather
    // than the order the dropdowns were left in.
    byId("placementAudit").textContent =
      `${result.side2.count + result.side3.count} spawn cells · ${result.family} block`
      + (result.orientationNormalised ? " · measured orientation" : "");
    byId("ledgerNumber").textContent = `${result.side2.count}V${result.side3.count}`;
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

  // Changing a unit re-derives the counts -- a new pair gets the even-fight
  // purchase, which is what the recorded fights were bought at. Typing a count
  // sends both counts explicitly. Either way the server decides and the inputs
  // are synced from its answer, so the purchase rule lives only in purchase.js.
  function loadDerived() {
    return loadSimulation({
      side2Slug: byId("side2Select").value,
      side3Slug: byId("side3Select").value,
    });
  }
  for (const id of ["side2Select", "side3Select"]) {
    byId(id).addEventListener("change", () => {
      syncCountCaps();
      loadDerived().catch(showError);
    });
  }
  for (const id of ["n2Input", "n3Input"]) {
    byId(id).addEventListener("change", () => {
      loadSimulation(currentSelection()).catch(showError);
    });
  }
  byId("resetCounts").addEventListener("click", () => { loadDerived().catch(showError); });

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
    setMapStatus("Locked 21 vs 21 melee formation");
    byId("playbackMode").textContent = "formation";
  });

  // Keyed on activeResult, not `selected`: a rejected request updates
  // `selected` to the attempted (failed) pick but leaves whatever fight was
  // last loaded on screen, and the review panel must describe what is
  // actually visible, not a fight that never ran. null in the boot window
  // before the first fight has resolved, and after a rejection with nothing
  // loaded yet -- either way, there is nothing to key a review row on.
  function feedbackKey() {
    if (!activeResult) return null;
    return {
      pair: `${activeResult.side2.slug}-vs-${activeResult.side3.slug}`,
      ratio: `${activeResult.side2.count}v${activeResult.side3.count}`,
      repeat: 1,
    };
  }

  function saveFeedback() {
    const key = feedbackKey();
    if (!key) return;
    feedback.set({
      ...key,
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
  await loadSimulation(selected);
}


// A rejected fight (an impossible pick, an engine-tick ceiling, a formation
// over capacity) is a routine, recoverable outcome of free selection, not a
// boot failure -- so it goes to the status line the user is already reading,
// never the full-screen modal, and always leaves the transport controls (and
// whatever fight was already loaded) usable.
function rejectFight(message) {
  setMapStatus(`Rejected: ${message}`);
  byId("playbackMode").textContent = "paused";
  for (const control of ["playPause", "resetPlayback", "stepTick", "nextEvent"]) {
    byId(control).disabled = false;
  }
}


// The modal is reserved for genuine boot failures -- map/formation/units
// fetch failing -- which leave nothing usable on screen to fall back to.
function showError(error) {
  const panel = byId("errorPanel");
  panel.hidden = false;
  panel.textContent = `The combat chronograph could not continue: ${error.message}`;
  console.error(error);
}


start().catch(showError);
