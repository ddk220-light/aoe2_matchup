import {
  compareMapDepth,
  createProjection,
  objectAtTile,
  sortObjectsForRender,
} from "../src/map-model.js";


const TILE_WIDTH = 86;
const TILE_HEIGHT = 43;
const MAP_CENTRE_WORLD = { x: 0, y: 16 * TILE_HEIGHT / 2 };
const VIEW_ORIENTATION = "counterclockwise";

const TERRAIN = Object.freeze({
  DIRT_1: { top: "#788b50", edge: "#53633a", grain: "#91a760" },
  FOREST_DRY_SOUTH_AMERICAN: { top: "#49643a", edge: "#2e472c", grain: "#66804d" },
  FOREST_JUNGLE: { top: "#315a38", edge: "#1f3d29", grain: "#4d7548" },
  FOREST_OAK: { top: "#3f5b36", edge: "#2b432b", grain: "#587246" },
  FOREST_AUTUMN: { top: "#75633d", edge: "#51442f", grain: "#987a47" },
  FOREST_BIRCH: { top: "#586b46", edge: "#3b4d35", grain: "#74875a" },
  FOREST_RAINFOREST: { top: "#31503a", edge: "#1f392c", grain: "#4d6d4c" },
});


function playerTeam(playerId) {
  if (playerId === 2) return "p2";
  if (playerId === 4) return "p4";
  return "p3";
}


function objectKind(name) {
  if (name === "PANDA_ROCK") return "rock";
  if (name === "BUSH_B") return "bush";
  if (name.includes("ITALIAN_PINE")) return "pine";
  if (name.includes("MONKEY_PUZZLE")) return "monkey-puzzle";
  if (name.includes("ACACIA")) return "acacia";
  if (name.includes("OLIVE")) return "olive";
  if (name.includes("RAINFOREST")) return "rainforest";
  if (name.includes("JUNGLE")) return "jungle";
  if (name.includes("BIRCH")) return "birch";
  if (name.includes("AUTUMN")) return "autumn";
  return "oak";
}


export function buildRenderScene(map, { orientation = "default" } = {}) {
  const depthOptions = { mapWidth: map.width, orientation };
  return Object.freeze({
    tiles: Object.freeze([...map.tiles].sort(
      (a, b) => compareMapDepth(a, b, depthOptions),
    )),
    objects: Object.freeze(sortObjectsForRender(map.gaia_objects, depthOptions).map(
      (object) => Object.freeze({ ...object, kind: objectKind(object.name) }),
    )),
  });
}


export function buildFormationScene(units, {
  mapWidth = 16,
  orientation = VIEW_ORIENTATION,
} = {}) {
  return Object.freeze(units
    .map((unit) => Object.freeze({
      ...unit,
      team: playerTeam(unit.player_id),
    }))
    .sort((a, b) => compareMapDepth(
      { x: a.position.x, y: a.position.y },
      { x: b.position.x, y: b.position.y },
      { mapWidth, orientation },
    )));
}


export function pickFormationUnit(units, x, y, radius = 0.42) {
  const radiusSquared = radius * radius;
  let nearest = null;
  let nearestDistance = Infinity;
  for (const unit of units) {
    const dx = unit.position.x - x;
    const dy = unit.position.y - y;
    const distance = dx * dx + dy * dy;
    if (distance <= radiusSquared && distance < nearestDistance) {
      nearest = unit;
      nearestDistance = distance;
    }
  }
  return nearest;
}


export function buildSimulationScene(snapshot, {
  mapWidth = 16,
  orientation = VIEW_ORIENTATION,
} = {}) {
  if (!immutableSimulationSnapshot(snapshot)) {
    throw new TypeError("simulation scene requires an immutable simulation snapshot");
  }
  return Object.freeze(snapshot.units
    .map((unit) => Object.freeze({
      ...unit,
      reference_id: unit.referenceId,
      player_id: unit.owner,
      unit_const: unit.unitMaster,
      name: unit.label,
      position: Object.freeze({ x: unit.x, y: unit.y }),
      rotation: unit.facing,
      team: playerTeam(unit.owner),
      maxHp: unit.mechanics.hp,
    }))
    .sort((a, b) => compareMapDepth(
      { x: a.position.x, y: a.position.y },
      { x: b.position.x, y: b.position.y },
      { mapWidth, orientation },
    )));
}


function deeplyFrozen(value, visited = new Set()) {
  if (!value || typeof value !== "object" || visited.has(value)) return true;
  if (!Object.isFrozen(value)) return false;
  visited.add(value);
  return Object.values(value).every((child) => deeplyFrozen(child, visited));
}


function immutableSimulationSnapshot(snapshot) {
  return (
    deeplyFrozen(snapshot)
    && Number.isInteger(snapshot.tick)
    && snapshot.tick >= 0
    && Array.isArray(snapshot.units)
    && Object.isFrozen(snapshot.units)
    && Array.isArray(snapshot.events)
    && Object.isFrozen(snapshot.events)
  );
}


export function createSimulationPresenter({ present }) {
  if (typeof present !== "function") throw new TypeError("present must be a function");
  let snapshot = null;
  return Object.freeze({
    setSimulationSnapshot(value) {
      if (!immutableSimulationSnapshot(value)) {
        throw new TypeError("renderer requires an immutable simulation snapshot");
      }
      snapshot = value;
      present(value);
    },
    getSimulationSnapshot() { return snapshot; },
    getDisplayedTick() { return snapshot?.tick ?? null; },
  });
}


function seeded(referenceId, salt = 0) {
  const value = Math.sin(referenceId * 91.733 + salt * 17.117) * 43758.5453;
  return value - Math.floor(value);
}


function diamond(ctx, points) {
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let index = 1; index < points.length; index += 1) {
    ctx.lineTo(points[index].x, points[index].y);
  }
  ctx.closePath();
}


function drawCanopyBlob(ctx, x, y, radius, color, seed) {
  const lobes = 5;
  ctx.fillStyle = color;
  for (let index = 0; index < lobes; index += 1) {
    const angle = index * Math.PI * 2 / lobes + seeded(seed, index) * 0.5;
    const distance = radius * (0.24 + seeded(seed, index + 8) * 0.18);
    const lobeRadius = radius * (0.56 + seeded(seed, index + 16) * 0.18);
    ctx.beginPath();
    ctx.arc(
      x + Math.cos(angle) * distance,
      y + Math.sin(angle) * distance * 0.58,
      lobeRadius,
      0,
      Math.PI * 2,
    );
    ctx.fill();
  }
}


function drawTree(ctx, object, x, y, scale) {
  const size = Math.max(11, 22 * scale);
  const trunkHeight = size * (object.kind === "monkey-puzzle" ? 1.45 : 0.9);
  ctx.save();
  ctx.globalAlpha = 0.22;
  ctx.fillStyle = "#101a12";
  ctx.beginPath();
  ctx.ellipse(x + size * 0.18, y + 4, size * 0.75, size * 0.25, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.strokeStyle = "#4a3322";
  ctx.lineWidth = Math.max(2, scale * 4);
  ctx.beginPath();
  ctx.moveTo(x, y + 1);
  ctx.lineTo(x, y - trunkHeight);
  ctx.stroke();

  if (object.kind === "pine") {
    for (let index = 0; index < 3; index += 1) {
      const top = y - trunkHeight - size * 0.65 + index * size * 0.38;
      ctx.fillStyle = ["#173d2f", "#24533a", "#2e6543"][index];
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x - size * (0.62 + index * 0.12), top + size * 0.95);
      ctx.lineTo(x + size * (0.62 + index * 0.12), top + size * 0.95);
      ctx.closePath();
      ctx.fill();
    }
    return;
  }

  if (object.kind === "monkey-puzzle") {
    ctx.strokeStyle = "#244c31";
    ctx.lineWidth = Math.max(2, scale * 3);
    for (let index = 0; index < 4; index += 1) {
      const branchY = y - trunkHeight * (0.35 + index * 0.16);
      const span = size * (0.95 - index * 0.12);
      ctx.beginPath();
      ctx.moveTo(x - span, branchY + size * 0.12);
      ctx.quadraticCurveTo(x, branchY - size * 0.22, x + span, branchY + size * 0.12);
      ctx.stroke();
    }
    drawCanopyBlob(ctx, x, y - trunkHeight, size * 0.62, "#2c6640", object.reference_id);
    return;
  }

  if (object.kind === "acacia") {
    ctx.fillStyle = "#3e6e39";
    ctx.beginPath();
    ctx.ellipse(x, y - trunkHeight, size * 1.15, size * 0.47, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#628346";
    ctx.beginPath();
    ctx.ellipse(x - size * 0.2, y - trunkHeight - size * 0.1, size * 0.72, size * 0.3, 0, 0, Math.PI * 2);
    ctx.fill();
    return;
  }

  const palette = {
    olive: ["#6d8056", "#8d9d6c"],
    rainforest: ["#174c38", "#2f6a48"],
    jungle: ["#1d5531", "#367747"],
    birch: ["#537349", "#789266"],
    autumn: ["#80562f", "#a8793f"],
    oak: ["#285b36", "#3e7545"],
  }[object.kind] || ["#285b36", "#3e7545"];
  drawCanopyBlob(ctx, x, y - trunkHeight, size, palette[0], object.reference_id);
  drawCanopyBlob(ctx, x - size * 0.1, y - trunkHeight - size * 0.16, size * 0.72, palette[1], object.reference_id + 1);
}


function drawBush(ctx, object, x, y, scale) {
  const size = Math.max(7, 12 * scale);
  drawCanopyBlob(ctx, x, y - size * 0.25, size, "#416c36", object.reference_id);
  ctx.fillStyle = "#95ad58";
  for (let index = 0; index < 5; index += 1) {
    ctx.beginPath();
    ctx.arc(
      x + (seeded(object.reference_id, index) - 0.5) * size * 1.2,
      y - size * (0.3 + seeded(object.reference_id, index + 5) * 0.45),
      Math.max(1.5, scale * 2),
      0,
      Math.PI * 2,
    );
    ctx.fill();
  }
}


function drawRock(ctx, x, y, scale) {
  const size = Math.max(12, 20 * scale);
  ctx.fillStyle = "#2d312d";
  ctx.beginPath();
  ctx.moveTo(x - size, y);
  ctx.lineTo(x - size * 0.62, y - size * 0.72);
  ctx.lineTo(x + size * 0.12, y - size);
  ctx.lineTo(x + size * 0.95, y - size * 0.32);
  ctx.lineTo(x + size * 0.75, y + size * 0.18);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#62675f";
  ctx.beginPath();
  ctx.moveTo(x - size * 0.55, y - size * 0.67);
  ctx.lineTo(x + size * 0.12, y - size);
  ctx.lineTo(x + size * 0.54, y - size * 0.46);
  ctx.lineTo(x - size * 0.05, y - size * 0.28);
  ctx.closePath();
  ctx.fill();
}


export function createMapRenderer(canvas, map) {
  const ctx = canvas.getContext("2d");
  const scene = buildRenderScene(map, { orientation: VIEW_ORIENTATION });
  function buildProjection(mode) {
    return createProjection({
      mapWidth: map.width,
      mapHeight: map.height,
      tileWidth: TILE_WIDTH,
      tileHeight: TILE_HEIGHT,
      originX: 0,
      originY: 0,
      orientation: VIEW_ORIENTATION,
      projection: mode,
    });
  }
  let projectionMode = "isometric";
  let projection = buildProjection(projectionMode);

  // Centre of the projected map, in world units. The isometric footprint is a
  // diamond centred on x = 0; the top-down footprint is a square whose centre
  // is half the map span on both axes.
  function mapCentreWorld() {
    if (projectionMode === "orthographic") {
      return { x: map.width * TILE_WIDTH / 4, y: map.height * TILE_WIDTH / 4 };
    }
    return MAP_CENTRE_WORLD;
  }
  const state = {
    width: 1,
    height: 1,
    fitZoom: 1,
    zoom: 1,
    panX: 0,
    panY: 0,
    selected: null,
    selectedUnit: null,
    hovered: null,
    formationUnits: Object.freeze([]),
    units: Object.freeze([]),
    simulationSnapshot: null,
    mode: "formation",
    options: {
      grid: false,
      objects: true,
      footprints: false,
      labels: false,
      navigation: true,
    },
  };

  const simulationPresenter = createSimulationPresenter({
    present(snapshot) {
      state.simulationSnapshot = snapshot;
      state.mode = "simulation";
      state.units = buildSimulationScene(snapshot, { mapWidth: map.width });
      if (state.selectedUnit) {
        state.selectedUnit = state.units.find(
          ({ reference_id: id }) => id === state.selectedUnit.reference_id,
        ) ?? null;
      }
      draw();
    },
  });

  function worldToCanvas(point) {
    return {
      x: state.width / 2 + state.panX + (point.x - mapCentreWorld().x) * state.zoom,
      y: state.height / 2 + state.panY + (point.y - mapCentreWorld().y) * state.zoom,
    };
  }

  function canvasToWorld(x, y) {
    return {
      x: (x - state.width / 2 - state.panX) / state.zoom + mapCentreWorld().x,
      y: (y - state.height / 2 - state.panY) / state.zoom + mapCentreWorld().y,
    };
  }

  function tilePolygon(tile) {
    return [
      projection.tileToScreen(tile.x, tile.y, tile.elevation),
      projection.tileToScreen(tile.x + 1, tile.y, tile.elevation),
      projection.tileToScreen(tile.x + 1, tile.y + 1, tile.elevation),
      projection.tileToScreen(tile.x, tile.y + 1, tile.elevation),
    ].map(worldToCanvas);
  }

  function drawTile(tile) {
    const points = tilePolygon(tile);
    const style = TERRAIN[tile.terrain_name] || TERRAIN.DIRT_1;
    diamond(ctx, points);
    ctx.fillStyle = style.top;
    ctx.fill();
    ctx.strokeStyle = state.options.grid ? "rgba(224, 215, 174, .36)" : style.edge;
    ctx.lineWidth = state.options.grid ? 0.8 : 0.35;
    ctx.stroke();

    if (seeded(tile.x * 31 + tile.y * 71, tile.terrain_id) > 0.44) {
      const centre = worldToCanvas(
        projection.tileToScreen(tile.x + 0.5, tile.y + 0.5, tile.elevation),
      );
      ctx.fillStyle = style.grain;
      ctx.globalAlpha = 0.18;
      ctx.beginPath();
      ctx.arc(centre.x, centre.y, Math.max(0.8, state.zoom * 1.4), 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }
  }

  function drawObjectCell(object) {
    const tile = { x: Math.floor(object.x), y: Math.floor(object.y), elevation: 0 };
    const points = tilePolygon(tile);
    diamond(ctx, points);
    ctx.fillStyle = "rgba(211, 151, 72, .16)";
    ctx.fill();
    ctx.strokeStyle = "rgba(235, 178, 85, .85)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  function drawObject(object) {
    const base = worldToCanvas(projection.tileToScreen(object.x, object.y, object.z));
    if (object.kind === "rock") drawRock(ctx, base.x, base.y, state.zoom);
    else if (object.kind === "bush") drawBush(ctx, object, base.x, base.y, state.zoom);
    else drawTree(ctx, object, base.x, base.y, state.zoom);

    if (state.options.labels && state.zoom >= 0.45) {
      ctx.font = `${Math.max(9, 10 * state.zoom)}px Verdana, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.lineWidth = 3;
      ctx.strokeStyle = "rgba(12, 18, 13, .86)";
      ctx.fillStyle = "#f3e9c8";
      const label = object.name.replaceAll("_", " ");
      ctx.strokeText(label, base.x, base.y - Math.max(18, 45 * state.zoom));
      ctx.fillText(label, base.x, base.y - Math.max(18, 45 * state.zoom));
    }
  }

  function drawMarker(object, color) {
    if (!object) return;
    const base = worldToCanvas(projection.tileToScreen(object.x, object.y, object.z));
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(base.x, base.y - Math.max(10, 18 * state.zoom), Math.max(10, 18 * state.zoom), 0, Math.PI * 2);
    ctx.stroke();
  }

  function unitBase(unit) {
    const { x, y, z = 0 } = unit.position;
    return worldToCanvas(projection.tileToScreen(x, y, z));
  }

  function drawWorldCircle(unit, radius, color, dash = []) {
    if (!(radius > 0)) return;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.15;
    ctx.setLineDash(dash);
    ctx.beginPath();
    for (let index = 0; index <= 40; index += 1) {
      const angle = index / 40 * Math.PI * 2;
      const projected = worldToCanvas(projection.tileToScreen(
        unit.position.x + Math.cos(angle) * radius,
        unit.position.y + Math.sin(angle) * radius,
        0,
      ));
      if (index === 0) ctx.moveTo(projected.x, projected.y);
      else ctx.lineTo(projected.x, projected.y);
    }
    ctx.stroke();
    ctx.restore();
  }

  function drawTargetLine(unit, target, color, dash, width) {
    if (!target) return;
    const start = unitBase(unit);
    const finish = unitBase(target);
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(start.x, start.y - 5 * state.zoom);
    ctx.lineTo(finish.x, finish.y - 5 * state.zoom);
    ctx.stroke();
    ctx.restore();
  }

  function drawSimulationOverlays() {
    if (!state.simulationSnapshot) return;
    const byReference = new Map(state.units.map((unit) => [unit.reference_id, unit]));
    for (const unit of state.units) {
      if (!unit.alive) continue;
      const radius = unit.mechanics.collision_size_tiles.x;
      const targetRadius = radius;
      drawWorldCircle(unit, radius, "rgba(241, 226, 178, .54)");
      drawWorldCircle(
        unit,
        radius + targetRadius + unit.mechanics.attack_range_tiles,
        "rgba(241, 226, 178, .22)",
        [3, 4],
      );
      drawTargetLine(
        unit,
        byReference.get(unit.attackTargetId),
        unit.team === "p2"
          ? "rgba(240, 102, 78, .92)"
          : "rgba(105, 201, 255, .92)",
        [],
        2.2,
      );
    }

    const navigation = state.simulationSnapshot.navigation;
    if (!state.options.navigation || !navigation) return;
    const point = (value) => worldToCanvas(projection.tileToScreen(value.x, value.y, 0));
    const anchor = point(navigation.anchor);
    const route = point(navigation.routeWaypoint);
    const ai = point(navigation.aiWaypoint);
    const centre = point(navigation.centroid);
    const firstFormation = navigation.firstFormationTarget
      ? point(navigation.firstFormationTarget)
      : null;
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    // Anchor -> route subgoal -> current tape-derived AI waypoint.
    ctx.strokeStyle = "rgba(105, 201, 255, .92)";
    ctx.lineWidth = 2.2;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(anchor.x, anchor.y);
    ctx.lineTo(route.x, route.y);
    ctx.stroke();
    ctx.strokeStyle = "rgba(244, 202, 91, .78)";
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(route.x, route.y);
    ctx.lineTo(ai.x, ai.y);
    ctx.stroke();

    // Each unit's effective formation slot. Thin lines make lag and crossing
    // immediately visible while the circles show the actual target positions.
    const byId = new Map(state.units.map((unit) => [unit.reference_id, unit]));
    ctx.setLineDash([2, 4]);
    ctx.lineWidth = 0.8;
    for (const destination of navigation.unitDestinations) {
      const unit = byId.get(destination.referenceId);
      if (!unit) continue;
      const start = unitBase(unit);
      const finish = point(destination);
      ctx.strokeStyle = "rgba(133, 226, 194, .32)";
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(finish.x, finish.y);
      ctx.stroke();
      ctx.fillStyle = "rgba(133, 226, 194, .9)";
      ctx.beginPath();
      ctx.arc(finish.x, finish.y, Math.max(2, 2.8 * state.zoom), 0, Math.PI * 2);
      ctx.fill();
    }

    const marker = (position, color, radius, label) => {
      ctx.setLineDash([]);
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.beginPath();
      ctx.arc(position.x, position.y, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.font = `${Math.max(8, 9 * state.zoom)}px Consolas, monospace`;
      ctx.textAlign = "left";
      ctx.fillText(label, position.x + radius + 3, position.y - radius - 1);
    };
    marker(ai, "#f4ca5b", 6, "AI order");
    if (firstFormation) marker(firstFormation, "#ff9b73", 6, "first formation");
    marker(route, "#69c9ff", 5, "route");
    marker(anchor, "#ffffff", 4, "anchor");
    marker(centre, "#85e2c2", 3, "group");
    ctx.restore();
  }

  function drawUnit(unit) {
    const { x, y, z = 0 } = unit.position;
    const base = worldToCanvas(projection.tileToScreen(x, y, z));
    const size = Math.max(7, 13 * state.zoom);
    const palette = unit.team === "p2"
      ? { fill: "#d65d50", rim: "#ffab83", dark: "#602d2a" }
      : unit.team === "p4"
        ? { fill: "#d6ad36", rim: "#ffe58a", dark: "#6d5318" }
        : { fill: "#4b9b72", rim: "#9ed5a8", dark: "#214b39" };

    ctx.save();
    if (unit.alive === false) ctx.globalAlpha = 0.36;
    ctx.fillStyle = "rgba(8, 14, 10, .42)";
    ctx.beginPath();
    ctx.ellipse(base.x + size * 0.18, base.y + size * 0.3, size * 0.85, size * 0.35, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = palette.dark;
    ctx.beginPath();
    ctx.arc(base.x, base.y - size * 0.3, size * 0.72, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = palette.fill;
    ctx.beginPath();
    ctx.arc(base.x, base.y - size * 0.42, size * 0.58, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = palette.rim;
    ctx.lineWidth = Math.max(1.2, state.zoom * 2);
    ctx.stroke();

    if (unit.alive === false) {
      ctx.strokeStyle = "#d9cba6";
      ctx.lineWidth = Math.max(1.2, state.zoom * 2);
      ctx.beginPath();
      ctx.moveTo(base.x - size * 0.55, base.y - size * 0.85);
      ctx.lineTo(base.x + size * 0.55, base.y + size * 0.15);
      ctx.moveTo(base.x + size * 0.55, base.y - size * 0.85);
      ctx.lineTo(base.x - size * 0.55, base.y + size * 0.15);
      ctx.stroke();
    }

    if (Number.isFinite(unit.hp) && Number.isFinite(unit.maxHp)) {
      const barWidth = Math.max(18, 28 * state.zoom);
      const barY = base.y - size * 1.55;
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(8, 12, 10, .9)";
      ctx.fillRect(base.x - barWidth / 2, barY, barWidth, Math.max(2, 3 * state.zoom));
      ctx.fillStyle = unit.hp / unit.maxHp > 0.4 ? "#b8d56e" : "#ee8b5c";
      ctx.fillRect(
        base.x - barWidth / 2,
        barY,
        barWidth * Math.max(0, unit.hp / unit.maxHp),
        Math.max(2, 3 * state.zoom),
      );
    }

    const facingWorld = projection.tileToScreen(
      x + Math.cos(unit.rotation) * 0.45,
      y + Math.sin(unit.rotation) * 0.45,
      z,
    );
    const facing = worldToCanvas(facingWorld);
    ctx.strokeStyle = "#f5e7bd";
    ctx.lineWidth = Math.max(1.4, state.zoom * 2.3);
    ctx.beginPath();
    ctx.moveTo(base.x, base.y - size * 0.42);
    ctx.lineTo(facing.x, facing.y - size * 0.42);
    ctx.stroke();

    if (state.selectedUnit?.reference_id === unit.reference_id) {
      ctx.strokeStyle = "#ffe08a";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(base.x, base.y - size * 0.35, size * 1.05, 0, Math.PI * 2);
      ctx.stroke();
    }

    if (state.options.labels && state.simulationSnapshot && state.zoom >= 0.5) {
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#f3e7c1";
      ctx.font = `${Math.max(8, 9 * state.zoom)}px Consolas, monospace`;
      ctx.textAlign = "center";
      ctx.fillText(
        `${unit.reference_id} · ${unit.action}`,
        base.x,
        base.y + size * 1.25,
      );
    }
    ctx.restore();
  }

  function draw() {
    const pixelRatio = window.devicePixelRatio || 1;
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    ctx.clearRect(0, 0, state.width, state.height);
    const gradient = ctx.createRadialGradient(
      state.width * 0.5,
      state.height * 0.42,
      20,
      state.width * 0.5,
      state.height * 0.5,
      Math.max(state.width, state.height) * 0.7,
    );
    gradient.addColorStop(0, "#28372c");
    gradient.addColorStop(1, "#111a17");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, state.width, state.height);

    ctx.save();
    ctx.shadowColor = "rgba(0, 0, 0, .48)";
    ctx.shadowBlur = 28;
    ctx.shadowOffsetY = 20;
    const border = [
      projection.tileToScreen(0, 0),
      projection.tileToScreen(map.width, 0),
      projection.tileToScreen(map.width, map.height),
      projection.tileToScreen(0, map.height),
    ].map(worldToCanvas);
    diamond(ctx, border);
    ctx.fillStyle = "#1b251f";
    ctx.fill();
    ctx.restore();

    for (const tile of scene.tiles) drawTile(tile);
    if (state.options.footprints) {
      for (const object of scene.objects) drawObjectCell(object);
    }
    if (state.options.objects) {
      for (const object of scene.objects) drawObject(object);
    }
    drawSimulationOverlays();
    for (const unit of state.units) drawUnit(unit);
    drawMarker(state.hovered, "rgba(239, 205, 112, .75)");
    drawMarker(state.selected, "#f3c55a");
  }

  function resize() {
    const rectangle = canvas.getBoundingClientRect();
    const pixelRatio = window.devicePixelRatio || 1;
    state.width = Math.max(1, rectangle.width);
    state.height = Math.max(1, rectangle.height);
    canvas.width = Math.round(state.width * pixelRatio);
    canvas.height = Math.round(state.height * pixelRatio);
    // Top-down uses square cells of TILE_WIDTH / 2, so the map is far taller
    // on screen than the 2:1 isometric footprint and needs its own fit.
    const spanX = projectionMode === "orthographic"
      ? map.width * TILE_WIDTH / 2
      : map.width * TILE_WIDTH;
    const spanY = projectionMode === "orthographic"
      ? map.height * TILE_WIDTH / 2
      : map.height * TILE_HEIGHT;
    state.fitZoom = Math.min((state.width - 48) / spanX, (state.height - 48) / spanY);
    if (!Number.isFinite(state.zoom) || state.zoom === 1) state.zoom = state.fitZoom;
    draw();
  }

  function screenToTile(x, y) {
    const world = canvasToWorld(x, y);
    return projection.screenToTile(world.x, world.y);
  }

  return Object.freeze({
    resize,
    draw,
    setProjection(mode) {
      if (!["isometric", "orthographic"].includes(mode)) {
        throw new RangeError(`unknown projection ${mode}`);
      }
      if (mode === projectionMode) return;
      projectionMode = mode;
      projection = buildProjection(mode);
      state.zoom = 1;
      state.panX = 0;
      state.panY = 0;
      resize();
    },
    getProjection() { return projectionMode; },
    resetView() {
      state.zoom = state.fitZoom;
      state.panX = 0;
      state.panY = 0;
      draw();
    },
    panBy(dx, dy) {
      state.panX += dx;
      state.panY += dy;
      draw();
    },
    zoomAt(factor, x, y) {
      const oldZoom = state.zoom;
      const nextZoom = Math.min(state.fitZoom * 5, Math.max(state.fitZoom * 0.75, oldZoom * factor));
      const relativeX = (x - state.width / 2 - state.panX) / oldZoom;
      const relativeY = (y - state.height / 2 - state.panY) / oldZoom;
      state.zoom = nextZoom;
      state.panX = x - state.width / 2 - relativeX * nextZoom;
      state.panY = y - state.height / 2 - relativeY * nextZoom;
      draw();
    },
    setOption(name, value) {
      if (!(name in state.options)) throw new Error(`unknown map overlay: ${name}`);
      state.options[name] = Boolean(value);
      draw();
    },
    inspectAt(x, y) {
      const tile = screenToTile(x, y);
      return {
        tile,
        unit: pickFormationUnit(state.units, tile.x, tile.y),
        object: objectAtTile(scene.objects, tile.x, tile.y, 0.48),
      };
    },
    setUnits(units) {
      state.formationUnits = buildFormationScene(units, { mapWidth: map.width });
      state.units = state.formationUnits;
      state.simulationSnapshot = null;
      state.mode = "formation";
      draw();
    },
    setSimulationSnapshot(snapshot) {
      simulationPresenter.setSimulationSnapshot(snapshot);
    },
    getSimulationSnapshot() {
      return simulationPresenter.getSimulationSnapshot();
    },
    getDisplayedTick() {
      return simulationPresenter.getDisplayedTick();
    },
    showFormation() {
      state.simulationSnapshot = null;
      state.mode = "formation";
      state.units = state.formationUnits;
      state.selectedUnit = null;
      draw();
    },
    setSelectedUnit(unit) {
      state.selectedUnit = unit;
      draw();
    },
    setHovered(object) {
      state.hovered = object;
      draw();
    },
    setSelected(object) {
      state.selected = object;
      draw();
    },
  });
}
