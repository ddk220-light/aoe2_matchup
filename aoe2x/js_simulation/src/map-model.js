const EXPECTED_MAP_SIZE = 16;
const EXPECTED_TILE_COUNT = EXPECTED_MAP_SIZE * EXPECTED_MAP_SIZE;


function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}


export function validateMapFixture(data) {
  if (!data || data.schema_version !== 1) {
    throw new Error("golden map fixture must use schema version 1");
  }
  if (
    data.map?.width !== EXPECTED_MAP_SIZE ||
    data.map?.height !== EXPECTED_MAP_SIZE
  ) {
    throw new Error("golden map fixture must be exactly 16 by 16 tiles");
  }
  if (!Array.isArray(data.map.tiles)) {
    throw new Error("golden map fixture must include terrain tiles");
  }
  const coordinates = new Set(
    data.map.tiles.map(({ x, y }) => `${Number(x)},${Number(y)}`),
  );
  if (
    data.map.tiles.length !== EXPECTED_TILE_COUNT ||
    coordinates.size !== EXPECTED_TILE_COUNT
  ) {
    throw new Error("golden map fixture must contain exactly 256 unique terrain tiles");
  }
  if (!Array.isArray(data.map.gaia_objects)) {
    throw new Error("golden map fixture must include Gaia objects");
  }
  if (!data.source?.sha256 || !data.source?.filename) {
    throw new Error("golden map fixture must identify its source scenario");
  }
  return deepFreeze(data);
}


export function createProjection({
  mapWidth,
  mapHeight,
  tileWidth,
  tileHeight,
  originX,
  originY,
  elevationHeight = tileHeight / 2,
  orientation = "default",
  // "isometric" is the game's own 2:1 dimetric view. "orthographic" is a
  // straight top-down view with equal scale on both axes, which is the only way
  // to read overlap and obstruction honestly: in the isometric view two bodies
  // that merely look adjacent can be a tile apart, and axis-aligned collision
  // boxes render as diamonds rather than squares.
  projection = "isometric",
}) {
  for (const [name, value] of Object.entries({
    mapWidth,
    mapHeight,
    tileWidth,
    tileHeight,
    originX,
    originY,
    elevationHeight,
  })) {
    if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  }
  if (mapWidth <= 0 || mapHeight <= 0 || tileWidth <= 0 || tileHeight <= 0) {
    throw new RangeError("map and tile dimensions must be positive");
  }
  if (!['default', 'counterclockwise'].includes(orientation)) {
    throw new RangeError(`unknown map orientation: ${orientation}`);
  }
  if (!["isometric", "orthographic"].includes(projection)) {
    throw new RangeError(`unknown map projection: ${projection}`);
  }
  // Square cells in top-down, sized so the map covers a similar area.
  const orthoScale = tileWidth / 2;

  function orient(x, y) {
    if (orientation === "counterclockwise") return { x: y, y: mapWidth - x };
    return { x, y };
  }

  function restore(x, y) {
    if (orientation === "counterclockwise") return { x: mapWidth - y, y: x };
    return { x, y };
  }

  return Object.freeze({
    mapWidth,
    mapHeight,
    tileWidth,
    tileHeight,
    originX,
    originY,
    elevationHeight,
    orientation,
    projection,

    tileToScreen(x, y, elevation = 0) {
      const viewed = orient(x, y);
      if (projection === "orthographic") {
        return {
          x: originX + viewed.x * orthoScale,
          y: originY + viewed.y * orthoScale - elevation * elevationHeight,
        };
      }
      return {
        x: originX + (viewed.x - viewed.y) * tileWidth / 2,
        y: originY + (viewed.x + viewed.y) * tileHeight / 2 - elevation * elevationHeight,
      };
    },

    screenToTile(screenX, screenY) {
      const dx = screenX - originX;
      const dy = screenY - originY;
      if (projection === "orthographic") {
        return restore(dx / orthoScale, dy / orthoScale);
      }
      const viewed = {
        x: dx / tileWidth + dy / tileHeight,
        y: dy / tileHeight - dx / tileWidth,
      };
      return restore(viewed.x, viewed.y);
    },
  });
}


export function compareMapDepth(a, b, {
  mapWidth = 0,
  orientation = "default",
} = {}) {
  const viewedA = orientation === "counterclockwise"
    ? { x: a.y, y: mapWidth - a.x }
    : a;
  const viewedB = orientation === "counterclockwise"
    ? { x: b.y, y: mapWidth - b.x }
    : b;
  return (
    (viewedA.x + viewedA.y) - (viewedB.x + viewedB.y) ||
    viewedA.y - viewedB.y ||
    viewedA.x - viewedB.x
  );
}


export function sortObjectsForRender(objects, options = {}) {
  return [...objects].sort(
    (a, b) =>
      compareMapDepth(a, b, options) ||
      (a.reference_id ?? 0) - (b.reference_id ?? 0),
  );
}


export function objectAtTile(objects, x, y, radius = 0.45) {
  const radiusSquared = radius * radius;
  let nearest = null;
  let nearestDistance = Infinity;
  for (const object of objects) {
    const dx = object.x - x;
    const dy = object.y - y;
    const distance = dx * dx + dy * dy;
    if (distance <= radiusSquared && distance < nearestDistance) {
      nearest = object;
      nearestDistance = distance;
    }
  }
  return nearest;
}
