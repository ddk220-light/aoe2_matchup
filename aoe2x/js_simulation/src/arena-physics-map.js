const GAIA_OBSTRUCTION_RADIUS_TILES = 0.5;
const LEGACY_SOURCE_SHA256 = "f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4";

export const ARENA_CENTER_CORE = Object.freeze({
  referenceId: 1604,
  x: 9,
  y: 7,
  radius: 1.5,
});


function requireFixture(fixture) {
  const map = fixture?.map;
  if (fixture?.schema_version !== 1
      || !Number.isFinite(map?.width)
      || !Number.isFinite(map?.height)
      || map.width <= 0
      || map.height <= 0
      || !Array.isArray(map?.gaia_objects)) {
    throw new Error("Golden Arena map fixture is malformed");
  }
  return map;
}


export function buildArenaPhysicsMap(fixture) {
  const map = requireFixture(fixture);
  const usesLegacyCenterCore = fixture.source?.sha256 === LEGACY_SOURCE_SHA256;
  const obstacles = map.gaia_objects.map((object) => {
      if (!Number.isSafeInteger(object.reference_id)
          || !Number.isFinite(object.x)
          || !Number.isFinite(object.y)) {
        throw new Error("Golden Arena Gaia object is malformed");
      }
      return Object.freeze({
        referenceId: object.reference_id,
        x: object.x,
        y: object.y,
        radius: usesLegacyCenterCore
          && object.reference_id === ARENA_CENTER_CORE.referenceId
          ? ARENA_CENTER_CORE.radius
          : GAIA_OBSTRUCTION_RADIUS_TILES,
      });
    });
  obstacles.sort((left, right) => left.referenceId - right.referenceId);

  return Object.freeze({
    width: map.width,
    height: map.height,
    obstacles: Object.freeze(obstacles),
  });
}
