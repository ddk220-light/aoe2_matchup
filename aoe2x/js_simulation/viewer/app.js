import { validateMapFixture } from "../src/map-model.js";
import {
  formationUnits,
  validateFormationFixture,
} from "../src/formation-model.js";
import { createMapRenderer } from "./map-renderer.js";


const byId = (id) => document.getElementById(id);

function prettyName(value) {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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

async function start() {
  const [mapResponse, formationResponse] = await Promise.all([
    fetch("api/map", { cache: "no-store" }),
    fetch("api/formation", { cache: "no-store" }),
  ]);
  if (!mapResponse.ok) throw new Error(`Map API returned ${mapResponse.status}`);
  if (!formationResponse.ok) {
    throw new Error(`Formation API returned ${formationResponse.status}`);
  }
  const fixture = validateMapFixture(await mapResponse.json());
  const formation = validateFormationFixture(await formationResponse.json());
  const units = formationUnits(formation);
  const canvas = byId("mapCanvas");
  const renderer = createMapRenderer(canvas, fixture.map);
  renderer.setUnits(units);

  byId("sourceBadge").innerHTML = `
    <span class="seal-dot"></span>
    <span><strong>Scenario source verified</strong><small>${fixture.source.filename}</small></span>
  `;
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
  byId("resetView").addEventListener("click", () => renderer.resetView());

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
      const selected = inspection.unit || inspection.object;
      renderer.setSelected(inspection.unit ? null : inspection.object);
      renderer.setSelectedUnit(inspection.unit);
      setSelection(selected);
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
}


start().catch((error) => {
  const panel = byId("errorPanel");
  panel.hidden = false;
  panel.textContent = `The map inspector could not start: ${error.message}`;
  console.error(error);
});
