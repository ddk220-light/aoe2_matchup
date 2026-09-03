const GAIA_OBSTRUCTION_RADIUS_TILES = 0.5;

// The visible Golden Arena grove is eight perimeter objects around a rock.
// Half-tile discs leave sub-tile seams between diagonal objects; once a unit
// enters one, the surrounding constraints can trap it inside the grove. A
// 1.5-tile central core reaches every inward seam while keeping the original
// perimeter bodies and their outer footprint. In particular, it does not
// bulge into the tape's siege spawn at (9.5, 4.5).
const CENTER_REFERENCE_IDS = Object.freeze(new Set([
  1577, 1578, 1579, 1580, 1581, 1582, 1583, 1584, 1604,
]));

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
  const central = map.gaia_objects.filter(({ reference_id: referenceId }) => (
    CENTER_REFERENCE_IDS.has(referenceId)
  ));
  if (central.length !== CENTER_REFERENCE_IDS.size) {
    throw new Error(
      `Golden Arena center is incomplete: expected ${CENTER_REFERENCE_IDS.size} objects, `
      + `found ${central.length}`,
    );
  }

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
        radius: object.reference_id === ARENA_CENTER_CORE.referenceId
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
